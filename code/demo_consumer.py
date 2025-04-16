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

# ISPEMTemp Consumer Configuration
kafka_temp = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'demo_test-workflows-released',
    'auto.offset.reset': 'earliest'
}

tempConsumer = Consumer(kafka_temp)

kafka_data_store = []  # Store Kafka messages

# Manufacutiring orders Consumer config
man_order_temp = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'demo_manufacturing-orders-temp',
    'auto.offset.reset': 'earliest',
}

temp_man_order_consumer = Consumer(man_order_temp)

order_number_dict = {}  # Store manufacturing order numbers
productName = None  # Initialize productName variable


tempConsumerChatbot = Blueprint('temp_consumer_chatbot', __name__)


# New Endpoint to Get Kafka Data
@tempConsumerChatbot.route('/IMPEMTemp-data', methods=['GET'])
def get_kafka_data():
    return jsonify(kafka_data_store)

@tempConsumerChatbot.route('/manufacturing-orders-data', methods=['POST', 'GET'])
def get_manufacturing_orders_data():
    global productName  # Declare productName as global to modify it
    if request.method == 'POST':
        man_data = request.json
        productName = man_data.get("productName")  
        print(f"Received productName: {productName}", flush=True)
        if not productName:
            return jsonify({"error": "productName is required"}), 400
        else:
            return jsonify({"message": "Product name set successfully"}), 200    
    elif request.method == 'GET':
        if productName not in order_number_dict.keys():
            order_number_dict[productName] = 0  # Initialize order number for the product if not already present
        #print("All tracked order numbers:", order_number_dict[productName], flush=True)
        submitted_order_number = order_number_dict[productName] + 1
        #print(f"Sent Order Number: {submitted_order_number}", flush=True)	
        return jsonify({"orderNumber": submitted_order_number})


        
    
# ISPEMTemp Consumer Function
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



#Manfucaturing Orders Consumer Function

def consume_man_orders():
    print("Starting Manufacturing orders consumer thread", flush=True)

    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)

    temp_man_order_consumer.subscribe(['manufacturing_orders'], on_assign=temp_on_assign)  # Ensure you're listening to the right topic

    try:
        while True:
            msgs = temp_man_order_consumer.consume(5, timeout=1.0)  # Fetch messages
            print(f"Received messages: {msgs}", flush=True)  # Debugging line
            
            if not msgs:
                continue  

            for msg in msgs:
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        continue  
                    else:
                        logging.error(f"Kafka Consumer Error: {msg.error()}")
                        continue
                
                man_order_data = json.loads(msg.value().decode('utf-8'))  # Decode JSON message
                product_name = man_order_data.get("product")
                order_number = int(man_order_data.get("orderNumber"))
                if product_name not in order_number_dict.keys():
                    order_number_dict[product_name] = 0
                if order_number > order_number_dict[product_name]:
                    order_number_dict[product_name] = order_number  # Store order number in dictionary
                
                print(f"max number for each product name",{product_name},{order_number_dict[product_name]}, flush =True)
                
                
                    # Store order number in memory
                
                    

        
    except KeyboardInterrupt:
        pass
    finally:
        temp_man_order_consumer.close()

# Start Kafka consumer in a separate thread
threading.Thread(target=consume_temp_data_chatbot, daemon=True).start()
threading.Thread(target=consume_man_orders, daemon=True).start()