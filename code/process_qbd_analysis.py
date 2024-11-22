import threading
from flask import Blueprint, render_template, jsonify
from confluent_kafka import Consumer
import json
import numpy as np
import logging
from datetime import datetime
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']

# Create a blueprint
process_qbd_analysis = Blueprint('process_qbd_analysis', __name__)

# # Kafka consumer configuration
# Orders_Kafka_Config= {
#     'bootstrap.servers': Kafkaserver,
#     'group.id': 'process-analysis-Orders-group',
#     'auto.offset.reset': 'earliest'
# }

# Temps_Kafka_Config = {
#     'bootstrap.servers': Kafkaserver,
#     'group.id': 'process-analysis-Temp-group',
#     'auto.offset.reset': 'earliest'
# }
############################################
# Shared data structures
mutex_completed_orders = threading.Lock()
mutex_temp_values = threading.Lock()

completed_orders = {}  # {order_number: start_time_str}
temp_values = []       # List of (time_from_start, normalized_temp)
# Flag to check if consumers are running
consumers_running = False

def start_consumers():
    global consumers_running
    if not consumers_running:
        consumers_running = True
        print(f"QBD Consumers: {consumers_running}")
        threading.Thread(target=consume_orders, daemon=True).start()
        threading.Thread(target=consume_temperatures, daemon=True).start()
  
def consume_orders():
    kafka_conf_orders = {
        'bootstrap.servers': Kafkaserver,
        'group.id': 'process-analysis-orders-group',
        'auto.offset.reset': 'earliest'
    }
    orders_consumer = Consumer(kafka_conf_orders)
    orders_consumer.subscribe(['manufacturing_orders'])

    try:
        while True:
            msg = orders_consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logging.error(f"QBD: Orders Consumer error: {msg.error()}")
                continue
            order = json.loads(msg.value().decode('utf-8'))
            print(f"QBD Consumer order: {order}")
            if order.get('status') == 'Completed':
                order_number = order.get('orderNumber')
                start_time = order.get('startTime')
                with mutex_completed_orders:
                    completed_orders[order_number] = start_time
    except Exception as e:
        logging.error(f"QBD: Error in orders consumer: {e}")
    finally:
        orders_consumer.close()

def consume_temperatures():
    kafka_conf_temp = {
        'bootstrap.servers': Kafkaserver,
        'group.id': 'process-analysis-temp-group',
        'auto.offset.reset': 'earliest'
    }
    temp_consumer = Consumer(kafka_conf_temp)
    temp_consumer.subscribe(['ISPEMTemp'])

    try:
        while True:
            msg = temp_consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logging.error(f"QBD: Temperature Consumer error: {msg.error()}")
                continue
            temp_data = json.loads(msg.value().decode('utf-8'))
            order_number = temp_data.get('orderNumber')
            print(f"QBD Consumer temp: {temp_data}")
            with mutex_completed_orders:
                start_time_str = completed_orders.get(order_number)
            if start_time_str:
                try:
                    start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S')
                    current_time = datetime.strptime(temp_data['timestamp'], '%Y-%m-%dT%H:%M:%S')
                    time_from_start = (current_time - start_time).total_seconds()
                    temperature = temp_data.get('value')
                    # Normalize the temperature (15°C as 0%, 40°C as 100%)
                    normalized_temp = ((temperature - 15) / (40 - 15)) * 100
                    with mutex_temp_values:
                        temp_values.append((time_from_start, normalized_temp))
                except Exception as e:
                    logging.error(f"QBD: Error processing temperature data: {e}")
    except Exception as e:
        logging.error(f"Error in temperature consumer: {e}")
    finally:
        temp_consumer.close()

@process_qbd_analysis.route('/process-qbd-analysis')
def process_qbd_analysis_view():
    # Start the consumers if not already running
    start_consumers()

    # Prepare data to send to the template
    with mutex_temp_values:
        if temp_values:
            times, normalized_temps = zip(*temp_values)
            average_normalized_temp = np.mean(normalized_temps)
        else:
            times, normalized_temps = [], []
            average_normalized_temp = 0

    return render_template(
        'process-qbd-analysis.html',
        times=times,
        normalized_temps=normalized_temps,
        average_normalized_temp=average_normalized_temp
    )

# Optional: API endpoint for AJAX calls
@process_qbd_analysis.route('/api/process-qbd-analysis')
def process_qbd_analysis_api():
    with mutex_temp_values:
        if temp_values:
            times, normalized_temps = zip(*temp_values)
            average_normalized_temp = np.mean(normalized_temps)
        else:
            times, normalized_temps = [], []
            average_normalized_temp = 0

    return jsonify({
        'times': times,
        'normalized_temps': normalized_temps,
        'average_normalized_temp': average_normalized_temp
    })
 
start_consumers()
##########################################################################
       
# # Initialize Kafka consumers
# Process_orders_consumer = Consumer(Orders_Kafka_Config)
# Process_orders_consumer.subscribe(['manufacturing_orders'])
# Process_temp_consumer = Consumer(Temps_Kafka_Config)
# Process_temp_consumer.subscribe(['ISPEMTemp'])

# ############### code below to be tested  ################

# mutex_completed_orders = threading.Lock()
# mutex_temp_values = threading.Lock()

# completed_orders = []
# normalized_temps = []
# temp_values = []

# ######################### main - routes ############################
# @process_qbd_analysis.route('/process-qbd-analysis')
# def process_qbd_analysis_view():
#     logging.info("Processing QbD Analysis View")
#     print(f"Process QBD: View", flush=True)  # Print message for diagnostic purposes
#     return render_template('process-qbd-analysis.html')
   
# @process_qbd_analysis.route('/api/process-qbd-analysis')
# def process_qbd_analysis_api():
#     logging.info("Processing QbD Analysis API")
#     print(f"Process QBD: API", flush=True)  # Print message for diagnostic purposes
#     try:
#         with mutex_temp_values:
#             #if temp_values:
#                 #send data to html
#             return jsonify({'normalized_temps': temp_values})
#     except Exception as e:
#         logging.error(f"Error processing QbD Analysis API: {e}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# ######################## main thread -temperature ############################
# def QBD_temp_consume():
#     try:
#         print(f"Process QBD:Starting temp_consumer_qbd thread", flush=True)
#         normalizeUpperLimit = 30
#         normalizeLowerLimit = 15
#         #print("temp_consumer_qbd", flush=True)
#         while True:
#             with mutex_temp_values and mutex_completed_orders:
#                 Process_temp_consumer.poll(timeout_ms=1000)
#                 for message in Process_temp_consumer:
#                     temp_data = message.value
#                     if temp_data['orderNumber'] in completed_orders and temp_data['value'] is not None:
#                         #Add the temp values for each completed order to the array list incl. timestamp
#                         temp_values[temp_data['orderNumber']].append((temp_data['timestamp'], temp_data['value']))
#                         print(F"Process QBD:Temp_values",temp_values)
#                 #processing of the timestamp --> converting into minutes for easier visualisation
#                 for order_number, temps in temp_values.items():
#                     if temps:
#                         timestamps, values = zip(*temps)
#                         min_timestamp = min(datetime.fromisoformat(ts) for ts in timestamps)
#                         max_timestamp = max(datetime.fromisoformat(ts) for ts in timestamps)
#                         times_in_minutes = [(datetime.fromisoformat(ts) - min_timestamp).total_seconds() / 60 for ts in timestamps]
#                         temp_values[order_number] = list(zip(times_in_minutes, values))
#                         print(F"Process QBD: Times_in_minutes",times_in_minutes)
#                         logging.info(f"Order {order_number}: Min Timestamp: {min_timestamp}, Max Timestamp: {max_timestamp}")
#                 #normalize the temperature values
#                 normalizeFactor = normalizeUpperLimit - normalizeLowerLimit
#                 for order_number, temps in temp_values.items():
#                     if temps:
#                         timestamps, values = zip(*temps)
#                         normalized_values = [(value - normalizeLowerLimit)/ normalizeFactor for value in values]
#                         temp_values[order_number] = list(zip(timestamps, normalized_values))
#                         print(F"Process QBD: Normalized_values",normalized_values)
#                         logging.info(f"Order {order_number}: Normalized Values: {normalized_values}")
                
#     except Exception as e:
#              pass
#     finally:
#         Process_temp_consumer.close()
# ######################### main thread - orders ############################
# def QBD_orders_consume():
#     try:
#         print(f"Process QBD:Starting orders_consumers_qbd thread", flush=True)
#         while True:
#             with mutex_temp_values and mutex_completed_orders:
#                 print(f"Process QBD fetching orders", flush=True)
#                       # Fetch completed orders
#                 Process_orders_consumer.poll(timeout_ms=1000)
#                 for message in Process_orders_consumer:
#                     order = message.value
#                     print(f"Process QBD fetched orders {order}", flush=True)
#                     # Add the order number to the list of completed orders if the order is completed and not already in the list
#                     if order['status'] == 'Completed' and order['orderNumber'] not in completed_orders:
#                         completed_orders.append(order['orderNumber']) # Add the order number to the list
#                         print(f"Process QBD:Completed_orders in Thread orders_consumers_qbd",completed_orders)
#     except Exception as e:
#              pass
#     finally:
#         Process_orders_consumer.close()

# ######################### threading ############################
# threading.Thread(target=QBD_orders_consume, daemon=True).start()  # Start the consume
# threading.Thread(target=QBD_temp_consume, daemon=True).start()  # Start the consume
