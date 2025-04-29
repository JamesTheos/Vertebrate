from flask import Blueprint
from confluent_kafka import Consumer    # Import the Kafka consumer class
import threading
import json
from opcua import Client
#from datetime import datetime
import os


# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']

# Create a blueprint
nexus2plc = Blueprint('nexus2plc', __name__)


# Kafka consumer configuration
kafka_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'plc-consumer-group',
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(kafka_conf)
consumer.subscribe(['ISPEScene1', 'ISPEScene2', 'ISPEStartPhase1'])

# OPC UA client configuration
opcua_client = Client("opc.tcp://localhost:4840")
opcua_client.connect()

# Node to topic mapping
node_topic_mapping = {
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.Scene1": "ISPEScene1",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.Scene2": "ISPEScene2",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.Main.StartPhase1": "ISPEStartPhase1",
}

# Dictionary to store previous values
previous_values = {}

###################### Route ############################
@nexus2plc.route('/start-consumer', methods=['POST'])
def start_consumer():
    consume_messages()
    return "Consumer started"

###################### Functions ############################

# Function to update OPC UA node value
def update_opcua_node(node_id, value):
    node = opcua_client.get_node(node_id)
    node.set_value(bool(value))  # Ensure the value is written as a boolean
    print(f"N2P Updated OPC UA node {node_id} with value {value}")

def consume_messages():
    num_messages = 10

    try:
        print("N2P Starting Nexus 2 PLC thread", flush=True)
        while True:
            msgs = consumer.consume(num_messages,timeout=2.0)
            if msgs is None:
                continue
            for msg in msgs:
                if msg.error():
                        print(f"NexustoPLCerror",msg.error())
                        continue

                # Parse the message
                topic = msg.topic()
                message = json.loads(msg.value().decode('utf-8'))
                value = message['value']
                timestamp = message['timestamp']

                # Find the corresponding OPC UA node ID
                node_id = None
                for key, val in node_topic_mapping.items():
                    if val == topic:
                        node_id = key
                        break

                # Update OPC UA node if the value has changed
                if node_id and (topic not in previous_values or previous_values[topic] != value):
                    update_opcua_node(node_id, value)
                    previous_values[topic] = value

    except Exception as e:
        print("Exception in Nexus2PLC:consume_messages:", e, flush=True)
        pass
    finally:
        opcua_client.disconnect()
        consumer.close()

# Start the consumer thread
threading.Thread(target=consume_messages, daemon=True).start()