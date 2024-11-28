from opcua import Client, ua
from opcua.common.subscription import Subscription
from confluent_kafka import Producer, Consumer, KafkaException, OFFSET_BEGINNING
import json
import time
from datetime import datetime
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit= config['unit']

# OPC UA server details
opcua_url = "opc.tcp://localhost:4840"

# Connect to OPC UA server
opcua_client = Client(opcua_url)
opcua_client.connect()


# Kafka producer configuration
Producer_conf = {
    'bootstrap.servers': Kafkaserver,
    'client.id': clusterid,
}

Consumer_conf = {
    'bootstrap.servers': Kafkaserver,
    'client.id': clusterid,
    'group.id': 'plc-consumer-group',
    'auto.offset.reset': 'earliest'
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
        print(f"\n PLC2Nexus orders consumption started",latest_msg, flush=True)
        while True:
            msgs = consumer.consume(num_messages, timeout=1.0)
            #print(f"\nNexus Received message from Kafka", msgs, flush=True)
            if msgs is None:
                print('No messages consumed from Kafka')
                continue
            for msg in msgs:
                if msg.error():
                    print('PLC2Nexus error:',msg.error())
                    continue
                order_data = json.loads(msg.value().decode('utf-8'))
                print(f"\nNexus Received message from Kafka: {order_data}")      
             
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

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
    
    
# Handler for subscription events
class SubHandler(object):
    def datachange_notification(self, node, val, data):
        node_id = node.nodeid.to_string()
        if node_id in node_topic_mapping:
            topic = node_topic_mapping[node_id]
            timestamp = data.monitored_item.Value.SourceTimestamp
            producertimestamp = datetime.utcnow().isoformat()
            health_status = data.monitored_item.Value.StatusCode.name
            data_dict = {
                "Enterprise": enterprise,
                "Site": site,
                "Area": area,
                "Process Cell": process_cell,
                'Unit': unit,
                "value": val,
                "timestamp": timestamp.isoformat(),
                "Producertimestamp": producertimestamp,
                "health_status": health_status,
                "orderNumber": orderNumber, #not in 2nd message
                "product": product,  #not in 2nd message
                "lotNumber" : lotNumber,  #not in 2nd message
                "QbD": topic
            }
        if val != previous_values.get(node_id):
            producer.produce(topic, key="FromPLC", value=json.dumps(data_dict))
            producer.flush()
            previous_values[node_id] = val
            print(f"Sent data to Kafka: {data_dict}")


# Create a subscription
subscription = opcua_client.create_subscription(1000, SubHandler())

# Subscribe to nodes
for node_id in node_topic_mapping.keys():
    node = opcua_client.get_node(node_id)
    subscription.subscribe_data_change(node)

try:
    consume_messages()
    

except KeyboardInterrupt:
    pass
finally:
    subscription.delete()
    opcua_client.disconnect()


