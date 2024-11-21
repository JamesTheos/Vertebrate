from flask import Blueprint, render_template, jsonify
from kafka import KafkaProducer, KafkaConsumer, TopicPartition
from datetime import datetime
import json
import logging
import threading
import os

mutex_completed_orders = threading.Lock()
mutex_temp_values = threading.Lock()

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']

# Create a blueprint
process_qbd_analysis = Blueprint('process_qbd_analysis', __name__)

# Kafka consumer configuration
kafka_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'QBD-analysis-group',
    'auto.offset.reset': 'earliest'
}

# Initialize Kafka consumers
QBD_orders_consumer = KafkaConsumer(
    'manufacturing_orders',
    bootstrap_servers=Kafkaserver,
    group_id='QBD-orders-consumer-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

QBD_temp_consumer = KafkaConsumer(
    'ISPEMTemp',
    bootstrap_servers=Kafkaserver,
    group_id='QBD-temp-consumer-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)
###############code below to be done################

completed_orders = []
normalized_temps = []
temp_values = {}

# # Load existing sets from Kafka topic
# def load_existing_temp_sets():
#     while not QBD_temp_consumer.assignment():
#         QBD_temp_consumer.poll(timeout_ms=1000)
#     partitions = QBD_temp_consumer.assignment()
#     QBD_temp_consumer.seek_to_beginning(*partitions)
#     while True:
#         raw_msgs = QBD_temp_consumer.poll(timeout_ms=1000)
#         if not raw_msgs:
#             break
#         for tp, msgs in raw_msgs.items():
#             for message in msgs:
#                 temp_values[message.value['value']] = message.value
# # Load existing sets from Kafka topic
# load_existing_temp_sets()

######################### main - routes ############################
@process_qbd_analysis.route('/process-qbd-analysis')
def process_qbd_analysis_view():
    logging.info("Processing QbD Analysis View")
    print(f"Process QBD: View", flush=True)  # Print message for diagnostic purposes
    return render_template('process-qbd-analysis.html')
   
@process_qbd_analysis.route('/api/process-qbd-analysis')
def process_qbd_analysis_api():
    logging.info("Processing QbD Analysis API")
    print(f"Process QBD: API", flush=True)  # Print message for diagnostic purposes
    try:
        with mutex_temp_values:
            if temp_values:
                #send data to html
                return jsonify({'normalized_temps': temp_values})
    except Exception as e:
        logging.error(f"Error processing QbD Analysis API: {e}")
    return jsonify({'status': 'error', 'message': str(e)}), 500

######################### main thread -temperature ############################
def QBD_temp_consume():
    try:
        print(f"Process QBD:Starting temp_consumer_qbd thread", flush=True)
        normalizeUpperLimit = 30
        normalizeLowerLimit = 15
        #print("temp_consumer_qbd", flush=True)
        while True:
            with mutex_temp_values and mutex_completed_orders:
                QBD_temp_consumer.poll(timeout_ms=1000)
                for message in QBD_temp_consumer:
                    temp_data = message.value
                    if temp_data['orderNumber'] in completed_orders and temp_data['value'] is not None:
                        #Add the temp values for each completed order to the array list incl. timestamp
                        temp_values[temp_data['orderNumber']].append((temp_data['timestamp'], temp_data['value']))
                        print(F"Process QBD:Temp_values",temp_values)
                #processing of the timestamp --> converting into minutes for easier visualisation
                for order_number, temps in temp_values.items():
                    if temps:
                        timestamps, values = zip(*temps)
                        min_timestamp = min(datetime.fromisoformat(ts) for ts in timestamps)
                        max_timestamp = max(datetime.fromisoformat(ts) for ts in timestamps)
                        times_in_minutes = [(datetime.fromisoformat(ts) - min_timestamp).total_seconds() / 60 for ts in timestamps]
                        temp_values[order_number] = list(zip(times_in_minutes, values))
                        print(F"Process QBD: Times_in_minutes",times_in_minutes)
                        logging.info(f"Order {order_number}: Min Timestamp: {min_timestamp}, Max Timestamp: {max_timestamp}")
                #normalize the temperature values
                normalizeFactor = normalizeUpperLimit - normalizeLowerLimit
                for order_number, temps in temp_values.items():
                    if temps:
                        timestamps, values = zip(*temps)
                        normalized_values = [value / normalizeFactor for value in values]
                        temp_values[order_number] = list(zip(timestamps, normalized_values))
                        print(F"Process QBD: Normalized_values",normalized_values)
                        logging.info(f"Order {order_number}: Normalized Values: {normalized_values}")
                
    except Exception as e:
             pass
    finally:
        QBD_temp_consumer.close()
######################### main thread - orders ############################
def QBD_orders_consume():
    try:
        print(f"Process QBD:Starting orders_consumers_qbd thread", flush=True)
        while True:
            with mutex_temp_values and mutex_completed_orders:
                # Fetch completed orders
                QBD_orders_consumer.poll(timeout_ms=1000)
                for message in QBD_orders_consumer:
                    order = message.value
                    # Add the order number to the list of completed orders if the order is completed and not already in the list
                    if order['status'] == 'Completed' and order['orderNumber'] not in completed_orders:
                        completed_orders.append(order['orderNumber']) # Add the order number to the list
                        print(f"Process QBD:Completed_orders in Thread orders_consumers_qbd",completed_orders)
    except Exception as e:
             pass
    finally:
        QBD_orders_consumer.close()

######################### threading ############################
threading.Thread(target=QBD_orders_consume, daemon=True).start()  # Start the consume
threading.Thread(target=QBD_temp_consume, daemon=True).start()  # Start the consume
