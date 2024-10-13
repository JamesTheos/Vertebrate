from confluent_kafka import Consumer, KafkaException
import json
from opcua import Client
from datetime import datetime

# Kafka consumer configuration
kafka_conf = {
    'bootstrap.servers': '172.18.192.25:9092',
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

# Function to update OPC UA node value
def update_opcua_node(node_id, value):
    node = opcua_client.get_node(node_id)
    node.set_value(bool(value))  # Ensure the value is written as a boolean
    print(f"Updated OPC UA node {node_id} with value {value}")

def consume_messages():
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue
                else:
                    print(msg.error())
                    break

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

    except KeyboardInterrupt:
        pass
    finally:
        opcua_client.disconnect()
        consumer.close()

if __name__ == '__main__':
    consume_messages()