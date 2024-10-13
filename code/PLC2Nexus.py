from opcua import Client, ua
from opcua.common.subscription import Subscription
from confluent_kafka import Producer, KafkaException
import json
import time
from datetime import datetime
# OPC UA server details
opcua_url = "opc.tcp://localhost:4840"

# Kafka server details
kafka_bootstrap_servers = "172.18.192.25:9092"
#kafka_topic = "ISPE"  # Replace with your Kafka topic name
kafka_cluster_id = "SCRy-9XoRpWIsPQWoBU0-w"

# Connect to OPC UA server
opcua_client = Client(opcua_url)
opcua_client.connect()

# Kafka producer configuration
kafka_conf = {
    'bootstrap.servers': kafka_bootstrap_servers,
    'client.id': kafka_cluster_id
}
producer = Producer(kafka_conf)

# Dictionary mapping OPC UA node IDs to Kafka topics
node_topic_mapping = {
    #"ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.Scene1": "ISPEScene1",
   # "ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.Scene2": "ISPEScene2",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM001_Mat_Temp.CM001_MTemp": "ISPEMTemp",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM002_Speed.CM002_Speed": "ISPESpeed",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM003_Pressure.CM003_Pressure": "ISPEPressure",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.CM004_Amb_Temp.CM004_AmbTemp": "ISPEAmbTemp",
    #"ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.StartPhase1": "ISPEStartPhase1",
}
# Dictionary to store previous values
previous_values = {}


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
                "value": val,
                "timestamp": timestamp.isoformat(),
                "Producertimestamp": producertimestamp,
                "health_status": health_status
            }
            if val != previous_values.get(node_id):
                producer.produce(topic, key="FromPLC", value=json.dumps(data_dict))
                producer.flush()
                previous_values[node_id] = val
                print(f"Sent data to Kafka: {data_dict}")

# Create a subscription
subscription = opcua_client.create_subscription(500, SubHandler())

# Subscribe to nodes
for node_id in node_topic_mapping.keys():
    node = opcua_client.get_node(node_id)
    subscription.subscribe_data_change(node)

try:
    while True:
        pass  # Keep the script running to receive updates
except KeyboardInterrupt:
    pass
finally:
    subscription.delete()
    opcua_client.disconnect()

# def read_opcua_data():
#     data = {}
#     for node_id in node_topic_mapping.keys():
#         node = opcua_client.get_node(node_id)
#         data_value = node.get_value()  # Read the DataValue object
#         value = data_value
#         timestamp = data_value.SourceTimestamp  # Retrieve the SourceTimestamp
#                 
#         producertimestamp = datetime.utcnow().isoformat()  # Updated to use date and time format
#         health_status = node.get_status()  # Retrieve the status code of the node
#         data[node_id] = {"value": value, "timestamp": timestamp.isoformat(), "Producertimestamp": producertimestamp,"health_status": health_status}
#     return data

# def send_to_kafka(data):
#     for node_id, data_dict in data.items():
#         topic = node_topic_mapping[node_id]
#         value = data_dict["value"]
#         if value != previous_values.get(node_id):
#             producer.produce(topic, key="FromPLC", value=json.dumps(data_dict))
#             previous_values[node_id] = value
#     producer.flush()

# try:
#     while True:
#         data = read_opcua_data()
#         send_to_kafka(data)
#         time.sleep(1)  # Adjust the sleep time as needed
# except KeyboardInterrupt:
#     pass
# finally:
#         opcua_client.disconnect()
#         producer.flush()