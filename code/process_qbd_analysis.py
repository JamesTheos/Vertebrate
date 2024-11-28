from flask import Blueprint, render_template, jsonify
from confluent_kafka import KafkaException, Consumer, OFFSET_BEGINNING
from datetime import datetime
import json
import logging
import threading
from collections import deque
import os
import time

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
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}

Temps_Kafka_Config = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'process-analysis-Temp-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}

Process_orders_consumer = Consumer(Orders_Kafka_Config)
Process_temp_consumer = Consumer(Temps_Kafka_Config)

############### prepare data ############################

mutex_completed_orders = threading.Lock()
mutex_temp_values = threading.Lock()
completed_orders = []
temp_values = {} #with datetime types
temp_values_normalized = {} #normalized values
livetemp_values = {} #with datetime types
livetemp_values_normalized = {} #normalized values
data_lock = threading.Lock()
averaged_normalized_data = []
all_values = []
averaged_points = []
order_status = None
#####################
# # Shared data structures: future use
# processed_data = {
#     'times': [],
#     'normalized_temps': [],
#     'average_normalized_temp': 0
# }
###################### Route ############################

@process_qbd_analysis.route('/process-qbd-analysis')
def process_qbd_analysis_view():
    logging.info("Processing QbD Analysis View")
    return render_template('process-qbd-analysis.html')
   
#################### api ###############################

@process_qbd_analysis.route('/api/process-qbd-analysis')
def process_qbd_analysis_api():
    with data_lock:
        return jsonify({
            'processed_data': temp_values_normalized,
            'completed_orders': completed_orders,
            'averaged_normalized_data': averaged_normalized_data,
            'latest_data' : livetemp_values_normalized,
        })

###################### new code Orders consume and process ############################
def orders_consumers_qbd():
    # Define the number of messages to retrieve in one call
    num_messages = 10
    global completed_orders, temp_values, temp_values_normalized, livetemp_values, livetemp_values_normalized, mutex_completed_orders, order_status
    
    try:
        print("QBD Starting orders_consumers thread",completed_orders, flush=True)
        def on_assign(consumer, partitions):
            for partition in partitions:
                partition.offset = OFFSET_BEGINNING
            consumer.assign(partitions)

        Process_orders_consumer.subscribe(['manufacturing_orders'], on_assign=on_assign)

        while True:
          msgs = Process_orders_consumer.consume(num_messages, timeout=1.0)
            #time.sleep(3)
            #print(f"QBD order msg:", msg, flush=True)
          if msgs is None:
                #time.sleep(2)
                #print(f"QBD - No new orders: completed are", completed_orders)

                continue  # Continue if no message is received
          for msg in msgs:
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    print(f"QBD msg Kafka error- orders_consumers_qbd thread", flush=True)
                    continue  # Continue if end of partition is reached
                else:
                    print(f"QBD msg error- orders_consumers_qbd thread: {msg.error()}")  # Log any other errors
                    continue
            msg_orders = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            order_number = msg_orders.get('orderNumber')
            order_status = msg_orders.get('status')
            #print(f"\norders in Thread orders_consumers_qbd", order_number)
            if order_number not in completed_orders:
                print(f"\nQBD: Orders Consumer Message:", order_number, flush=True)
                if msg_orders['status'] == 'Completed':
                    # Add the order number to the list of completed orders if the order is completed and not already in the list
                    if order_number:
                        with mutex_completed_orders:
                            completed_orders.append(order_number) # Add the order number to the list
                            if order_number in livetemp_values:
                                livetemp_values.clear()
                                livetemp_values_normalized.clear()
                                #print(f"QBD: Live Data cleared", flush=True)
                print(f"Completed_orders in Thread orders_consumers_qbd", completed_orders)
    except Exception as e:
        logging.error(f"Error in orders_consumers_qbd: {e}")
    finally:
        #print("QBD-ending Orders_consumers thread", flush=True)
        Process_orders_consumer.close()

###################### new code Temperatures consume and process ############################
def Temp_consume_and_process():
    
    # Define the number of messages to retrieve in one call
    num_messages = 100
    normalizeUpperLimit = 8
    normalizeLowerLimit = 2
    current_sum = 0
    count = 0
    current_time = 0
    normalizeFactor = normalizeUpperLimit - normalizeLowerLimit
    AverageCalculation = False
    
    global completed_orders, temp_values, temp_values_normalized, livetemp_values, livetemp_values_normalized, all_values, averaged_points, mutex_completed_orders, order_status, averaged_normalized_data
    
    print("QBD Starting TEMPS_consumers thread",completed_orders,temp_values_normalized, flush=True)
    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)
    Process_temp_consumer.subscribe(['ISPEMTemp'], on_assign=temp_on_assign)

    # Consume messages from the beginning of the topic
    while True:
      if completed_orders:  
        msgs = Process_temp_consumer.consume(num_messages, timeout=2.0)
        if not msgs:
           #print(f"QBD msgs empty", flush=True)
           continue
        for msg in msgs: 
            if msg.error():
                logging.error(f"QBD Temperature Consumer error: {msg.error()}")
                continue
            # Process message
            temp_data = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            T_order_number = temp_data.get('orderNumber')
            #print(f"\n QBD temps recieved for order_number:", order_number, flush=True)
            if T_order_number and T_order_number in completed_orders:
                with mutex_completed_orders:
                    print(f"QBD value addition for order number:", T_order_number, flush=True)
                    if T_order_number in completed_orders: # process the values for the completed orders
                            if T_order_number not in temp_values:
                                temp_values[T_order_number] = []
                                print(f"QBD: Averaging Normalized Data requested", flush=True)
                            timestamp = temp_data.get('timestamp')
                            value = temp_data.get('value')
                            if timestamp and value is not None:
                                temp_values[T_order_number].append((timestamp, value))
                                
                                # Normalize the temperature values
                                timestamps, values = zip(*temp_values[T_order_number])
                                min_timestamp = min(datetime.fromisoformat(ts) for ts in timestamps)
                                times_in_minutes = [(datetime.fromisoformat(ts) - min_timestamp).total_seconds() / 60 for ts in timestamps]
                                normalized_values = [((value - normalizeLowerLimit) / normalizeFactor) * 100 for value in values]
                                temp_values_normalized[T_order_number] = list(zip(times_in_minutes, normalized_values))
                                AverageCalculation = True
                                print(f"Order {T_order_number}: Value Normalized \n", flush=True)
 
            elif T_order_number: # order not completed yet
                with mutex_completed_orders: # process the values for the current orders to have them ready for the live view and next steps

                    if T_order_number:
                            print(f"QBD value prep for order number:", T_order_number, flush=True)
                            if T_order_number not in temp_values:
                                temp_values[T_order_number] = []
                            if T_order_number not in livetemp_values:
                                livetemp_values[T_order_number] = []
                       
                            timestamp = temp_data.get('timestamp')
                            value = temp_data.get('value')
                            livetimestamp = temp_data.get('timestamp') #live data trending
                            livevalue = temp_data.get('value') #live data trending
                            if timestamp and value is not None:
                                temp_values[T_order_number].append((timestamp, value))
                                # Normalize the temperature values
                                timestamps, values = zip(*temp_values[T_order_number])
                                min_timestamp = min(datetime.fromisoformat(ts) for ts in timestamps)
                                times_in_minutes = [(datetime.fromisoformat(ts) - min_timestamp).total_seconds() / 60 for ts in timestamps]
                                normalized_values = [((value - normalizeLowerLimit) / normalizeFactor) * 100 for value in values]
                                temp_values_normalized[T_order_number] = list(zip(times_in_minutes, normalized_values))
                               
                                
                                #live data trending
                                livetemp_values[T_order_number].append((livetimestamp, livevalue))
                                livetimestamps, livevalues = zip(*livetemp_values[T_order_number])
                                livemin_timestamp = min(datetime.fromisoformat(ts) for ts in livetimestamps)
                                livetimes_in_minutes = [(datetime.fromisoformat(ts) - livemin_timestamp).total_seconds() / 60 for ts in livetimestamps]
                                livenormalized_values = [((livevalue - normalizeLowerLimit) / normalizeFactor) * 100 for livevalue in livevalues]
                                livetemp_values_normalized[T_order_number] = list(zip(livetimes_in_minutes, livenormalized_values))
                                #print(f"Order {order_number}: Online Value Normalized \n", flush=True)  
                                #print(f"\nQBD: livetemp_values_normalized",livetemp_values_normalized, flush=True)
                    if order_status == "Completed":
                        AverageCalculation = True
                        print(f"QBD: Order Completed", flush=True)

        # Average the normalized temperature values
        # if order_number and order_number in completed_orders:
        if temp_values_normalized and AverageCalculation:
                AverageCalculation = False
                print(f"QBD: Averaging Normalized Data", flush=True)
                # Calculate the average value for all orders in the first 5 seconds, next 5 seconds, and so on
                for values in temp_values_normalized.values():
                    all_values.extend(values)
                    all_values.sort()  # Sort by timestamp
                # print(f"QBD: All Values evaluated", all_values, flush=True)
                for timestamp, value in all_values:
                    if timestamp - current_time < (0.08):  # 5 seconds in minutes
                        current_sum += value
                        count += 1
                    else:
                        if count > 0:
                            averaged_points.append((current_time, current_sum / count))
                        # current_sum = value
                        # count = 1
                        current_sum = 0
                        count = 0 
                        current_time += 0.08  # Move to the next 5-second interval
                        # print(f"test:", current_sum, current_time, flush=True)
                if count > 0:
                     averaged_points.append((current_time, current_sum / count))
                
                current_sum = 0
                count = 0    
                averaged_normalized_data = averaged_points
                #print(f"QBD: Averaged Normalized Data evaluated", flush=True)
                #print(f"\nQBD: Averaged Normalized Data\n", averaged_normalized_data, flush=True)
            
   
threading.Thread(target=orders_consumers_qbd, daemon=True).start()
#time.sleep(3)   
threading.Thread(target=Temp_consume_and_process, daemon=True).start()  
#time.sleep(3)

