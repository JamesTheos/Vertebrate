from flask import Blueprint, jsonify  # Import Flask and related modules for web server and request handling
from confluent_kafka import KafkaException, Producer, Consumer
import json  # Import JSON module for data serialization
import logging  # Import logging module for logging
import threading  # Import threading module for running background tasks
import statistics  # Import statistics module for calculating averages
import time  # Import time module for time-related functions

product_analytics_app = Blueprint('product_analytics_app',__name__)  # Initialize Flask application
Kafkaserver = 'DESKTOP-LU0K7N2.fritz.box:9092'  # Kafka server address
#kafka_cluster_id = "XZ0liWYxTL-YbnQvGKTnfA"

# Kafka producer configuration
kafka_conf = {
    'bootstrap.servers': Kafkaserver,
}
# Kafka producer configuration
kafka_conf_products = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'product-analysis-group-products',
    'auto.offset.reset': 'earliest'
}

kafka_conf_values = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'product-analysis-group-values',
    'auto.offset.reset': 'earliest'
}

# Configure logging to only show critical errors
logging.basicConfig(level=logging.CRITICAL)

# Kafka producer for sending data
producer = Producer(kafka_conf)

# Kafka consumer for receiving data from 'manufacturing_orders' topic
consumer = Consumer(kafka_conf_products)
consumer.subscribe(['manufacturing_orders'])

# Kafka consumer for receiving data from 'ISPEMTemp' topic
temp_consumer = Consumer(kafka_conf_values)
temp_consumer.subscribe(['ISPEMTemp'])

# In-memory storage for products and their orders
products = {}  # Dictionary to store products
orders = {}  # Dictionary to store orders

@product_analytics_app.route('/get-products', methods=['GET'])  # Define route to get the list of products
def get_products():
    print(products)  # Print message to indicate route is called
    return jsonify({'products': list(products.keys())})  # Return the list as JSON
    

@product_analytics_app.route('/get-product-trend/<product>', methods=['GET'])  # Define route to get the trend data for a specific product
def get_product_trend(product):
    try:
        if product not in products:  # Check if the product exists
            return jsonify({'status': 'error', 'message': 'Product not found'}), 404  # Return error if not found

        # Get the newest order for the product
        newest_order = max(orders[product], key=lambda x: x['timestamp'])
        
       
        newest_order_data = newest_order['data']
        

        # Calculate the average values for the product
        all_data = [order['data'] for order in orders[product]]
        average_data = []
        for i in range(len(all_data[0])):
            avg_value = statistics.mean([data[i]['value'] for data in all_data])
            average_data.append({'time': all_data[0][i]['time'], 'value': avg_value})

        return jsonify({'newestOrder': newest_order_data, 'average': average_data})  # Return the trend data as JSON
    except Exception as e:
        logging.error(f"Error fetching product trend: {e}")  # Log any errors
        return jsonify({'status': 'error', 'message': str(e)}), 500  # Return error response

def consume_orders():
    global products, orders  # Use global variables for products and orders
    print("Starting consume_orders thread 123", flush=True)  # Print message to indicate thread start
    try:
        while True:
            msg = consumer.poll(timeout=1)  # Poll for messages from the 'manufacturing_orders' topic
            if msg is None:
                continue  # Continue if no message is received
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue  # Continue if end of partition is reached
                else:
                    logging.error(f"Consumer error: {msg.error()}")  # Log any other errors
                    continue
            order = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            print(f"Received order: {order}", flush=True)  # Print message to indicate order received
            product = order['product']  # Get the product name from the order
            if product not in products:
                products[product] = []  # Initialize product list if not already present
            products[product].append(order)  # Add the order to the product list
            print(f"Products: {products}", flush=True)  # Print message to indicate products list
            if product not in orders:
                orders[product] = []  # Initialize order list if not already present
            orders[product].append(order)  # Add the order to the order list
            print(f"Orders: {orders}", flush=True)  # Print message to indicate orders list
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

def consume_temp():
    global orders  # Use global variable for orders
    print("Starting consume_temp thread 123", flush=True)  # Print message to indicate thread start
    try:
        while True:
            msg = temp_consumer.poll(timeout=1)  # Poll for messages from the 'ISPEMTemp' topic
            if msg is None:
                continue  # Continue if no message is received
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue  # Continue if end of partition is reached
                else:
                    logging.error(f"Consumer error: {msg.error()}")  # Log any other errors
                    continue
            temp_data = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            print(f"Received temperature data: {temp_data}", flush=True)  # Print message to indicate temperature data received
            order_id = temp_data['orderNumber']  # Get the order ID from the temperature data
            product = temp_data['product']  # Get the product name from the temperature data
            print(f"Product: {product}", flush=True)  # Print message to indicate product name
            print(f"Orders Consume: {orders}", flush=True)  # Print message to indicate order ID
            if product in orders:
                print("Product in Orders")
                for order in orders[product]:
                    if order['orderNumber'] == order_id:
                        if 'data' not in order: 
                            order['data'] = []  # Initialize data list if not already present
                        order['data'].append({'time': temp_data['timestamp'], 'value': temp_data['value']})  # Add the temperature data to the order
                        print(f"Updated order data: {order['data']}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        temp_consumer.close()


threading.Thread(target=consume_orders, daemon=True).start()  # Start the consume_orders thread
threading.Thread(target=consume_temp, daemon=True).start()  # Start the consume_temp thread
