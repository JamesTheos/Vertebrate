from flask import Blueprint, render_template, jsonify
from confluent_kafka import KafkaException, Consumer, OFFSET_BEGINNING
from datetime import datetime
import json
import logging
import threading
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']

# Create a blueprint
process_qbd_analysis = Blueprint('process_qbd_analysis', __name__)

# Kafka consumer configuration
Orders_Kafka_Config= {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'process-analysis-Orders-group',
    'auto.offset.reset': 'earliest'
}

Temps_Kafka_Config = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'process-analysis-Temp-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}

Process_orders_consumer = Consumer(Orders_Kafka_Config)
Process_orders_consumer.subscribe(['manufacturing_orders'])
Process_temp_consumer = Consumer(Temps_Kafka_Config)
Process_temp_consumer.subscribe(['ISPEMTemp'])

def reset_offsets(consumer):
    partitions = consumer.assignment()
    for partition in partitions:
        partition.offset = OFFSET_BEGINNING
        consumer.seek(partition)
    consumer.assign(partitions)

###############code below to be done################

mutex_completed_orders = threading.Lock()
mutex_temp_values = threading.Lock()
completed_orders = []
temp_values = {} #with datetime types
temp_values_normalized = {} #normalized values


@process_qbd_analysis.route('/process-qbd-analysis')
def process_qbd_analysis_view():
    logging.info("Processing QbD Analysis View")
    return render_template('process-qbd-analysis.html')
   


@process_qbd_analysis.route('/api/process-qbd-analysis')
def process_qbd_analysis_api():
    logging.info("Processing QbD Analysis API")
    try:
        normalizeUpperLimit = 8
        normalizeLowerLimit = 2
        with mutex_temp_values:
            for order_number, temps in temp_values.items():
                    if temps:
                        timestamps, values = zip(*temps)
                        min_timestamp = min(datetime.fromisoformat(ts) for ts in timestamps)
                        max_timestamp = max(datetime.fromisoformat(ts) for ts in timestamps)
                        times_in_minutes = [(datetime.fromisoformat(ts) - min_timestamp).total_seconds() / 60 for ts in timestamps]
                        if order_number not in temp_values:
                            temp_values_normalized[order_number] = []
                        temp_values_normalized[order_number] = list(zip(times_in_minutes, values))
                        logging.info(f"Order {order_number}: Min Timestamp: {min_timestamp}, Max Timestamp: {max_timestamp}")
                #normalize the temperature values

            normalizeFactor = normalizeUpperLimit - normalizeLowerLimit
            for order_number, temps in temp_values_normalized.items():
                if temps:
                    timestamps, values = zip(*temps)
                    normalized_values = [((value - normalizeLowerLimit) / normalizeFactor)*100 for value in values]
                    temp_values_normalized[order_number] = list(zip(timestamps, normalized_values))
                    print("Normalized Values:",temp_values_normalized)
                    logging.info(f"Order {order_number}: Normalized Values: {normalized_values}")

            return jsonify({'normalized_temps': temp_values_normalized})
    except Exception as e:
        logging.error(f"Error processing QbD Analysis API: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


def temp_consumer_qbd():
    try:
        print("Starting temp_consumer_qbd thread, Im Running", flush=True)
    
        while True:
            
            with mutex_temp_values and mutex_completed_orders:
                msg = Process_temp_consumer.poll(timeout=1.0)
                if msg is None:
                    continue  # Continue if no message is received
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        continue  # Continue if end of partition is reached
                    else:
                        logging.error(f"Prodcut Analytics:Consumer error: {msg.error()} \n")  # Log any other errors
                        continue
                message_temp = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value

                #print("QBD: Consumer Temp: ", message_temp, flush=True)
                if message_temp['orderNumber'] in completed_orders and message_temp['value'] is not None:
                    #Add the temp values for each completed order to the array list incl. timestamp
                    if message_temp['orderNumber'] not in temp_values:
                        temp_values[message_temp['orderNumber']] = []
                    temp_values[message_temp['orderNumber']].append((message_temp['timestamp'], message_temp['value']))
                    #print("Temp_values after:",temp_values)
                #processing of the timestamp --> converting into minutes for easier visualisation
                
                
    except Exception as e:
             pass
    finally:
        Process_temp_consumer.close()

def orders_consumers_qbd():
    try:
        print("Starting orders_consumers_qbd thread", flush=True)
        while True:
            with mutex_temp_values and mutex_completed_orders:
                # Fetch completed orders
                msg = Process_orders_consumer.poll(1.0)
                if msg is None:
                    #print("msg none- orders_consumers_qbd thread", flush=True)
                    continue  # Continue if no message is received
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        #print("msg error- orders_consumers_qbd thread", flush=True)
                        continue  # Continue if end of partition is reached
                    else:
                        logging.error(f"Prodcut Analytics:Consumer error: {msg.error()}")  # Log any other errors
                        continue
                msg_orders = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
                print("QBD: Orders Consumer Message:", msg_orders, flush=True)
                # Add the order number to the list of completed orders if the order is completed and not already in the list
                if msg_orders['status'] == 'Completed' and msg_orders['orderNumber'] not in completed_orders:
                    completed_orders.append(msg_orders['orderNumber']) # Add the order number to the list
                    print("Completed_orders in Thread orders_consumers_qbd",completed_orders)
                    reset_offsets(Process_temp_consumer)
    except Exception as e:
            pass
    finally:
        print("ending orders_consumers_qbd thread", flush=True)
        Process_orders_consumer.close()


threading.Thread(target=orders_consumers_qbd, daemon=True).start()  # Start thread
threading.Thread(target=temp_consumer_qbd, daemon=True).start()  # Start thead
