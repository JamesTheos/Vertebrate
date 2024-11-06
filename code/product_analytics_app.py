from flask import Flask, request, jsonify, render_template  # Import Flask and related modules for web server and request handling
from kafka import KafkaProducer, KafkaConsumer, TopicPartition  # Import Kafka modules for producer and consumer
from confluent_kafka import KafkaException
import json  # Import JSON module for data serialization
import logging  # Import logging module for logging
import threading  # Import threading module for running background tasks
import statistics  # Import statistics module for calculating averages

app = Flask(__name__)  # Initialize Flask application
Kafkaserver = '172.20.50.243:9092'  # Kafka server address

# Configure logging to only show critical errors
logging.basicConfig(level=logging.CRITICAL)

# Kafka producer for sending data
producer = KafkaProducer(
    bootstrap_servers=Kafkaserver,  # Kafka server address
    value_serializer=lambda v: json.dumps(v).encode('utf-8')  # Serialize data to JSON and encode to UTF-8
)

# Kafka consumer for receiving data from 'manufacturing_orders' topic
consumer = KafkaConsumer(
    'manufacturing_orders',  # Topic name
    bootstrap_servers=Kafkaserver,  # Kafka server address
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))  # Deserialize data from JSON and decode from UTF-8
)

# Kafka consumer for receiving data from 'ISPEMTemp' topic
temp_consumer = KafkaConsumer(
    'ISPEMTemp',  # Topic name
    bootstrap_servers=Kafkaserver,  # Kafka server address
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))  # Deserialize data from JSON and decode from UTF-8
)

# In-memory storage for products and their orders
products = {}  # Dictionary to store products
orders = {}  # Dictionary to store orders

#@app.route('/')  # Define route for the home page
#def index():
 #   return render_template('index.html')  # Render the index.html template

#@app.route('/product-analytics')  # Define route for the product analytics page
#def product_analytics():
 #   return render_template('product_analytics.html')  # Render the product_analytics.html template

@app.route('/get-products', methods=['GET'])  # Define route to get the list of products
def get_products():
    try:
        products_list = list(products.keys())  # Get the list of product names
        return jsonify(products_list)  # Return the list as JSON
    except Exception as e:
        logging.error(f"Error fetching products: {e}")  # Log any errors
        return jsonify({'status': 'error', 'message': str(e)}), 500  # Return error response

@app.route('/get-product-trend/<product>', methods=['GET'])  # Define route to get the trend data for a specific product
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
    print("Starting consume_orders thread", flush=True)  # Print message to indicate thread start
    while True:
        msg = consumer.poll(timeout=1.0)  # Poll for messages from the 'manufacturing_orders' topic
        if msg is None:
            continue  # Continue if no message is received
        if msg.error():
            if msg.error().code() == KafkaException._PARTITION_EOF:
                continue  # Continue if end of partition is reached
            else:
                logging.error(f"Consumer error: {msg.error()}")  # Log any other errors
                continue
        order = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
        product = order['product']  # Get the product name from the order
        if product not in products:
            products[product] = []  # Initialize product list if not already present
        products[product].append(order)  # Add the order to the product list
        if product not in orders:
            orders[product] = []  # Initialize order list if not already present
        orders[product].append(order)  # Add the order to the order list

def consume_temp():
    global orders  # Use global variable for orders
    print("Starting consume_temp thread", flush=True)  # Print message to indicate thread start
    while True:
        msg = temp_consumer.poll(timeout=1.0)  # Poll for messages from the 'ISPEMTemp' topic
        if msg is None:
            continue  # Continue if no message is received
        if msg.error():
            if msg.error().code() == KafkaException._PARTITION_EOF:
                continue  # Continue if end of partition is reached
            else:
                logging.error(f"Consumer error: {msg.error()}")  # Log any other errors
                continue
        temp_data = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
        order_id = temp_data['order_id']  # Get the order ID from the temperature data
        product = temp_data['product']  # Get the product name from the temperature data
        if product in orders:
            for order in orders[product]:
                if order['order_id'] == order_id:
                    order['data'].append({'time': temp_data['time'], 'value': temp_data['value']})  # Add the temperature data to the order

if __name__ == '__main__':
    threading.Thread(target=consume_orders, daemon=True).start()  # Start the consume_orders thread
    threading.Thread(target=consume_temp, daemon=True).start()  # Start the consume_temp thread
    app.run(debug=True)  # Run the Flask app in debug mode