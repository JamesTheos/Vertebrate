from flask import Blueprint, jsonify, request  
from confluent_kafka import KafkaException, Consumer, Producer, OFFSET_BEGINNING  
import json  
import logging  
import threading  
import os  
from datetime import datetime  

# Load the configuration
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)
    
Kafkaserver = config['Kafkaserver']

# Kafka Consumer Configuration
kafka_workflows = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'demo_test-workflows-released',
    'auto.offset.reset': 'earliest'
}

workflowsConsumer = Consumer(kafka_workflows)

# Local memory to store released workflows and Kafka messages
released_workflows = {}
all_workflows = {}
kafka_data_store = []  # Store Kafka messages

Workflows_for_demo = Blueprint('demo_consumer', __name__)


# New Endpoint to Get Kafka Data
@Workflows_for_demo.route('/kafka-data', methods=['GET'])
def get_kafka_data():
    return jsonify(kafka_data_store)

# Kafka Consumer Function
def consume_workflows_for_demo():
    print("Starting Kafka consumer thread", flush=True)
    
    workflowsConsumer.subscribe(['ISPEMTemp'])  # Ensure you're listening to the right topic

    try:
        while True:
            msgs = workflowsConsumer.consume(5, timeout=1.0)  # Fetch messages
            
            if not msgs:
                continue  

            for msg in msgs:
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        continue  
                    else:
                        logging.error(f"Kafka Consumer Error: {msg.error()}")
                        continue
                
                workflow = json.loads(msg.value().decode('utf-8'))  # Decode JSON message
                
                # Extract relevant data
                order_number = workflow.get("orderNumber")
                value = workflow.get("value")
                timestamp = datetime.fromisoformat(workflow.get("timestamp")).strftime("%Y-%m-%d %H:%M")
                Producertime = datetime.fromisoformat(workflow.get("Producertimestamp")).strftime("%Y-%m-%d %H:%M")
                

                # Store Kafka data in memory
                kafka_data_store.append({"orderNumber": order_number, "value": value, "timestamp": timestamp, "Producertimestamp": Producertime})
                
                # Optional: Print extracted values
                print(f"Received Order: {order_number}, Value: {value}, timestamp: {timestamp}, Producertime: {Producertime}", flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        workflowsConsumer.close()


# Start Kafka consumer in a separate thread
threading.Thread(target=consume_workflows_for_demo, daemon=True).start()
