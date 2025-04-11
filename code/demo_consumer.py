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
kafka_temp = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'demo_test-workflows-released',
    'auto.offset.reset': 'earliest'
}

tempConsumer = Consumer(kafka_temp)

kafka_data_store = []  # Store Kafka messages

tempConsumerChatbot = Blueprint('temp_consumer_chatbot', __name__)


# New Endpoint to Get Kafka Data
@tempConsumerChatbot.route('/kafka-data', methods=['GET'])
def get_kafka_data():
    return jsonify(kafka_data_store)

# Kafka Consumer Function
def consume_temp_data_chatbot():
    print("Starting Kafka consumer thread", flush=True)
    
    tempConsumer.subscribe(['ISPEMTemp'])  # Ensure you're listening to the right topic

    try:
        while True:
            msgs = tempConsumer.consume(5, timeout=1.0)  # Fetch messages
            
            if not msgs:
                continue  

            for msg in msgs:
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        continue  
                    else:
                        logging.error(f"Kafka Consumer Error: {msg.error()}")
                        continue
                
                data = json.loads(msg.value().decode('utf-8'))  # Decode JSON message
                
                # Extract relevant data
                order_number = data.get("orderNumber")
                value = data.get("value")
                timestamp = datetime.fromisoformat(data.get("timestamp")).strftime("%Y-%m-%d %H:%M")
                Producertime = datetime.fromisoformat(data.get("Producertimestamp")).strftime("%Y-%m-%d %H:%M")
                

                # Store Kafka data in memory
                kafka_data_store.append({"orderNumber": order_number, "value": value, "timestamp": timestamp, "Producertimestamp": Producertime})
                
                # Optional: Print extracted values
                print(f"Received Order: {order_number}, Value: {value}, timestamp: {timestamp}, Producertime: {Producertime}", flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        tempConsumer.close()


# Start Kafka consumer in a separate thread
threading.Thread(target=consume_temp_data_chatbot, daemon=True).start()
