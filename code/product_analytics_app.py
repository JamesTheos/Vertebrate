from flask import Blueprint, jsonify  # Import Flask and related modules for web server and request handling
from confluent_kafka import KafkaException, Consumer, OFFSET_BEGINNING  # Import Kafka modules for consuming messages
import json  # Import JSON module for data serialization
import logging  # Import logging module for logging
import threading  # Import threading module for running background tasks
from datetime import datetime  # Import datetime module for date and time handling
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']

orders_lock = threading.Lock()

product_analytics_app = Blueprint('product_analytics_app',__name__)  # Initialize Flask application

kafka_conf_init = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'manufacturing_orders_init',
    'auto.offset.reset': 'earliest'
}

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

# Kafka consumer for receiving data from 'manufacturing_orders' topic
orders_consumer = Consumer(kafka_conf_products)

# Kafka consumer for receiving data from 'ISPEMTemp' topic
temp_consumer = Consumer(kafka_conf_values)

# In-memory storage for products and their orders
products = {}  # Dictionary to store products
orders = {}  # Dictionary to store orders
average_data = {}
newest_order = {}
newest_order_data = {}


####### main program ########
@product_analytics_app.route('/get-products', methods=['GET'])  # Define route to get the list of products
def get_products():
    with orders_lock:
        #print(f"\n Products in get Products: {products} \n", flush=True)  # Print message to indicate route is called
        return jsonify({'products': list(products.keys())})  # Return the list as JSON
    

@product_analytics_app.route('/get-product-trend/<product>', methods=['GET'])  # Define route to get the trend data for a specific product
def get_product_trend(product):
    try:
        with orders_lock:
            #print(f"\n Product in get product trend: {product} \n", flush=True)  # Print message to indicate route is called
            if product not in products:  # Check if the product exists
                return jsonify({'status': 'error', 'message': 'Product not found'}), 404  # Return error if not found

            if product not in orders or not orders[product]:  # Check if there are orders for the product
                return jsonify({'status': 'error', 'message': 'No orders found for this product'}), 404

            #print(f"Newest Order Data: {newest_order_data}", flush=True)  # Print message to indicate average data
            #print(f"Average Data: {average_data}", flush=True)  # Print message to indicate average data
            
           
        return jsonify({'newestOrder': newest_order_data[product], 'average': average_data[product]})  # Return the trend data as JSON
    except Exception as e:
        logging.error(f"Error fetching product trend: {e}")  # Log any errors
        return jsonify({'status': 'error', 'message': str(e)}), 500  # Return error response
    
def consume_orders():
    global newest_order, newest_order_data, all_data
    global average_data
    print("Prodcut Analytics:Starting consume_orders thread", flush=True)  # Print message to indicate thread start
    # Define the number of messages to retrieve in one call
    num_messages = 10
    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)
    orders_consumer.subscribe(['manufacturing_orders'], on_assign=temp_on_assign)
    
    try:
      while True:
        msgs = orders_consumer.consume(num_messages, timeout=2.0)  # consume messages from the 'manufacturing_orders' topic
        if msgs is None:
                continue  # Continue if no message is received
        for msg in msgs:
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue  # Continue if end of partition is reached
                else:
                    logging.error(f"Prodcut Analytics:Consumer error: {msg.error()}")  # Log any other errors
                    continue
            order = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            #print(f"Prodcut Analytics:Received order: {order}", flush=True)  # Print message to indicate order received
            product = order['product']  # Get the product name from the order
            orderNumber = order['orderNumber']  # Get the order ID from the order
            with orders_lock:
                if product not in products:
                    products[product] = []  # Initialize product list if not already present
                if product not in orders:
                    orders[product] = []  # Initialize order list if not already present
                    orders[product].append(order)  # Add the order to the order list
                if product not in newest_order:
                    newest_order[product] = []
                if not any(ord['orderNumber'] == orderNumber for ord in orders[product]):
                    orders[product].append(order)
                for ord in orders[product]:
                    if ord['orderNumber'] == orderNumber and ord['status'] != order['status']:
                        ord['status'] = order['status']
                        ord['timestamp'] = order['timestamp']
                #print(f"Prodcut Analytics:\n\nOrders in Consume Orders: {orders}\n\n", flush=True)  # Print message to indicate orders list

                
                # Get the newest order for the product
                newest_order[product] = max((order for order in orders[product] if order['status'] == 'Started'), key=lambda x: x['timestamp'], default=None)
                if newest_order[product] == None:
                    newest_order_data[product] = []
        
                all_data = [order['data'] for order in orders[product] if ('data' in order and order['status'] == 'Completed')]
                if all_data:
                        # Find the maximum length of data points in all orders
                        max_length = max(len(data) for data in all_data)

                        # Initialize lists to store sum of values and count of values for each time point
                        sum_values = [0] * max_length
                        count_values = [0] * max_length
                        time_diff = [0] * max_length

                        # Sum up the values and count the occurrences for each time point
                        for data in all_data:
                            oldest_order_data_avg = min(data, key=lambda x: datetime.fromisoformat(x['time']))
                            for i, data_point in enumerate(data):
                                time_diff[i] = (datetime.fromisoformat(data_point['time']) - datetime.fromisoformat(oldest_order_data_avg['time'])).total_seconds() / 60
                                sum_values[i] += data_point['value']
                                count_values[i] += 1

                        #Calculate the average values for each time point
                            
                        average_data[product] = [{'time': time_diff[i], 'value': sum_values[i] / count_values[i]} for i in range(max_length)]
                        #print(f"Prodcut Analytics:\nAverage Data: {average_data}\n", flush=True)  # Print message to indicate average data
                else:
                    average_data[product] = []
            
    except KeyboardInterrupt:
        pass
    finally:
        orders_consumer.close()

def consume_temp():
    print("Prodcut Analytics:Starting consume_temp thread", flush=True)  # Print message to indicate thread start
    global newest_order_data, newest_order
    # Define the number of messages to retrieve in one call
    num_messages = 100
    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)
    temp_consumer.subscribe(['ISPEMTemp'], on_assign=temp_on_assign)

    try:
      while True:
        msgs = temp_consumer.consume(num_messages, timeout=2.0)  # consume messages from the 'ISPEMTemp' topic
        if msgs is None:
                continue  # Continue if no message is received
        for msg in msgs:
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue  # Continue if end of partition is reached
                else:
                    logging.error(f"Prodcut Analytics:Consumer error: {msg.error()}")  # Log any other errors
                    continue
            temp_data = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            print(f" Prod. Analytics: Received temperature data", flush=True)  # Print message to indicate temperature data received

            order_id = temp_data['orderNumber']  # Get the order ID from the temperature data
            product = temp_data['product']  # Get the product name from the temperature data
            #print(f"Prodcut Analytics:Product Consume Temp: {product}", flush=True)  # Print message to indicate product name
            #print(f"Prodcut Analytics:Orders Consume Temp: {orders}", flush=True)  # Print message to indicate order ID
            if product:  # Check if the product exists
                print("\nProdcut Analytics:Product has value")
                with orders_lock:
                    if product in orders:
                        print("Prodcut Analytics:Product in Orders")
                        for order in orders[product]:
                            if order['orderNumber'] == order_id:
                                if 'data' not in order: 
                                    order['data'] = []  # Initialize data list if not already present
                                order['data'].append({'time': temp_data['timestamp'], 'value': temp_data['value']})  # Add the temperature data to the order
                                #print(f"Prodcut Analytics:Updated order data: {order['data']}", flush=True)
                   
                    if newest_order[product]:   # Check there is a newest order
                            #print(f"\n Newest Order in get product trend: {newest_order} \n", flush=True)  # Print message to indicate newest order
                            if 'data' not in newest_order[product]:  # Check if there is data in the newest order
                                newest_order_data[product] = []
                            else:
                                # Get the timestamp of the newest order data oldest and newest
                                oldest_order_data = min(newest_order[product]['data'], key=lambda x: datetime.fromisoformat(x['time']))
                                newest_order_data[product] = [{'value': data_point['value'], 'time': (datetime.fromisoformat(data_point['time']) - datetime.fromisoformat(oldest_order_data['time'])).total_seconds() / 60} for data_point in newest_order[product]['data']]

                                #print(f"Prodcut Analytics:\nNewest Order Time: {newest_order_data}\n", flush=True)  # Print message to indicate newest order
                    else:
                        newest_order_data[product] = []
                    # Calculate the average values for the product
                    
                    #print(f"Prodcut Analytics:\nAll Data: {all_data}\n", flush=True)  # Print message to indicate all data
                    
               
    except KeyboardInterrupt:
        pass
    finally:
        temp_consumer.close()


threading.Thread(target=consume_orders, daemon=True).start()  # Start the consume_orders thread
threading.Thread(target=consume_temp, daemon=True).start()  # Start the consume_temp thread
