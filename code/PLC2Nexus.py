from flask import Flask
from opcua import Client, ua
from opcua.common.subscription import Subscription
from confluent_kafka import Producer, Consumer, KafkaException, OFFSET_BEGINNING
import json
import threading
import time
from datetime import datetime, timezone
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver = os.environ.get('KAFKASERVER', config['Kafkaserver'])
clusterid= config['clusterid']
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit= config['unit']

# OPC UA server details
opcua_url = os.environ.get("OPCUA_URL", "opc.tcp://localhost:4840")

PLC_WATCHDOG_S = 5    # how often the OPC UA connection is checked
PLC_RETRY_S = 3       # wait between reconnect attempts


# Kafka producer configuration
Producer_conf = {
    'bootstrap.servers': Kafkaserver,
    'client.id': clusterid,
}

Consumer_conf = {
    'bootstrap.servers': Kafkaserver,
    'client.id': clusterid,
    'group.id': 'plc-consumer-group',
    'auto.offset.reset': 'earliest',
    # after a restart the new member gets the partitions after ~6 s instead of 45 s
    'session.timeout.ms': 6000,
    'heartbeat.interval.ms': 2000,
}

producer = Producer(Producer_conf)


# Dictionary mapping OPC UA node IDs to Kafka topics
node_topic_mapping = {
    #"ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.Scene1": "ISPEScene1",
    #"ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.Scene2": "ISPEScene2",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM001_Mat_Temp.CM001_MTemp": "ISPEMTemp",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM002_Speed.CM002_Speed": "ISPESpeed",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM003_Pressure.CM003_Pressure": "ISPEPressure",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM004_Amb_Temp.CM004_AmbTemp": "ISPEAmbTemp",
    #"ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.StartPhase1": "ISPEStartPhase1",
}
# Dictionary to store previous values
previous_values = {}

# Initialize global variables
orderNumber = None
lotNumber = None
product = None

consumer = Consumer(Consumer_conf)
consumer.subscribe(['manufacturing_orders'])

# Function to consume messages from Kafka
def consume_messages():
    global orderNumber, lotNumber, product, latest_msg
    oldorderNumber = None
    
    # Define the number of messages to retrieve in one call
    num_messages = 10
    latest_msg = {}

    try:
        #print(f"\n PLC2Nexus orders consumption started",latest_msg, flush=True)
        while True:
            msgs = consumer.consume(num_messages, timeout=1.0)
            #print(f"\nNexus Received message from Kafka", msgs, flush=True)
            if msgs is None:
                #print('No messages consumed from Kafka')
                continue
            for msg in msgs:
                if msg.error():
                    print('PLC2Nexus error:',msg.error())
                    continue
                order_data = json.loads(msg.value().decode('utf-8'))
                #print(f"\nNexus Received message from Kafka: {order_data}")      
             
                if order_data.get('orderNumber') is not None and order_data.get('lotNumber') is not None and order_data.get('product') is not None and (order_data.get('status') == "Started"):        
                        orderNumber = order_data['orderNumber']
                        product = order_data['product']
                        lotNumber = order_data['lotNumber']
                        if oldorderNumber != orderNumber:
                            oldorderNumber = orderNumber
                        print(f"\nNexus processed order: {orderNumber}")
                else:
                    if order_data.get('orderNumber') is not None and order_data.get('lotNumber') is not None and order_data.get('product') is not None and (order_data.get('status') == "Completed"):
                                        orderNumber = None
                                        lotNumber = None
                                        product = None
                                        print(f"\nNexus Order not running", order_data.get('orderNumber'))

    except KafkaException as e:
        print("KafkaException in PLC2Nexus:consume_messages:", e, flush=True)

    except Exception as e:
        print("Exception in PLC2Nexus:consume_messages:", e, flush=True)
    finally:
        consumer.close()
    
    
def publish(node_id, val, source_timestamp, health_status, force=False):
    """Send one tag value to Kafka (same message as before); unchanged values are skipped unless forced."""
    topic = node_topic_mapping.get(node_id)
    if topic is None:
        return
    if not force and val == previous_values.get(node_id):
        return
    data_dict = {
        "Enterprise": enterprise,
        "Site": site,
        "Area": area,
        "Process Cell": process_cell,
        'Unit': unit,
        "value": val,
        "timestamp": (source_timestamp or datetime.now(timezone.utc)).isoformat(),
        "Producertimestamp": datetime.now(timezone.utc).isoformat(),
        "health_status": health_status,
        "orderNumber": orderNumber, #not in 2nd message
        "product": product,  #not in 2nd message
        "lotNumber" : lotNumber,  #not in 2nd message
        "QbD": topic
    }
    producer.produce(topic, key="FromPLC", value=json.dumps(data_dict))
    producer.flush()
    previous_values[node_id] = val
    print(f"Sent data to Kafka: {data_dict}")


# Handler for subscription events
class SubHandler(object):
    def datachange_notification(self, node, val, data):
        value = data.monitored_item.Value
        publish(node.nodeid.to_string(), val, value.SourceTimestamp, value.StatusCode.name)


def publish_current_values(client):
    """Publish the current value of every subscribed tag once, so consumers see the last known
    PLC state right after a (re)start, even if nothing changes on the PLC."""
    for node_id in node_topic_mapping:
        try:
            data_value = client.get_node(node_id).get_data_value()
            publish(node_id, data_value.Value.Value, data_value.SourceTimestamp, data_value.StatusCode.name, force=True)
        except Exception as e:
            print(f"PLC2Nexus: could not read {node_id}: {e}", flush=True)


def connect_and_subscribe():
    """Connect to the OPC UA server (retrying until it answers) and subscribe to all tags."""
    while True:
        client = Client(opcua_url)
        try:
            client.connect()
            subscription = client.create_subscription(1000, SubHandler())
            for node_id in node_topic_mapping:
                subscription.subscribe_data_change(client.get_node(node_id))
            print(f"PLC2Nexus: connected to {opcua_url}", flush=True)
            publish_current_values(client)
            return client, subscription
        except Exception as e:
            print(f"PLC2Nexus: OPC UA connect to {opcua_url} failed ({e}); retrying in {PLC_RETRY_S} s", flush=True)
            try:
                client.disconnect()
            except Exception:
                pass
            time.sleep(PLC_RETRY_S)


def plc_watchdog():
    """Keep the OPC UA connection alive: check it every few seconds and reconnect after a PLC restart."""
    client, subscription = connect_and_subscribe()
    status_node = ua.NodeId(ua.ObjectIds.Server_ServerStatus_State)
    while True:
        time.sleep(PLC_WATCHDOG_S)
        try:
            client.get_node(status_node).get_value()
        except Exception as e:
            print(f"PLC2Nexus: lost OPC UA connection ({e}); reconnecting", flush=True)
            for close in (subscription.delete, client.disconnect):
                try:
                    close()
                except Exception:
                    pass
            client, subscription = connect_and_subscribe()


threading.Thread(target=plc_watchdog, daemon=True).start()

try:
    consume_messages()
except KeyboardInterrupt:
    pass
