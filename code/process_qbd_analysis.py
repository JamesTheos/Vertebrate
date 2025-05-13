from flask import Blueprint, render_template, jsonify
from confluent_kafka import KafkaError, Consumer, OFFSET_BEGINNING
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

############### Define the global variable
data_lock = threading.Lock()
temp_values_normalized = {} #normalized values
completed_orders = [] #completed orders
aborted_orders = [] #aborted orders
active_orders = [] #active orders
averaged_normalized_data = [] #averaged normalized data
livetemp_values_normalized = {} #normalized values
livetemp_values = {} #live values
order_status = None #order status from the orders consumer
global_threading_var = 0

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
    global data_lock, temp_values_normalized, completed_orders,active_orders, aborted_orders, livetemp_values, livetemp_values_normalized, order_status, global_threading_var

    try:
        print("QBD Starting orders_consumers thread",completed_orders, flush=True)
        def on_assign(consumer, partitions):
            for partition in partitions:
                partition.offset = OFFSET_BEGINNING
            consumer.assign(partitions)

        Process_orders_consumer.subscribe(['manufacturing_orders'], on_assign=on_assign)
        while True:
          msgs = Process_orders_consumer.consume(num_messages, timeout=2.0)
          if msgs is None:
                #print(f"QBD - No new orders: completed are", completed_orders)
                continue  # Continue if no message is received
          for msg in msgs:
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    print(f"QBD msg Kafka error- orders_consumers_qbd thread", flush=True)
                    continue  # Continue if end of partition is reached
                else:
                    print(f"QBD msg error- orders_consumers_qbd thread: {msg.error()}")  # Log any other errors
                    continue
            msg_orders = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            order_number = msg_orders.get('orderNumber')
            order_status = msg_orders.get('status')
            print(f"\norders in Thread orders_consumers_qbd", order_number, order_status, flush=True)
           
            if order_status == 'Completed':
                # Add the order number to the list of completed orders if the order is completed and not already in the list
                if order_number:
                    with data_lock:
                        if order_number not in completed_orders:
                            completed_orders.append(order_number) # Add the order number to the list
                        if order_number in active_orders:
                            active_orders.remove(order_number)  # Remove the order number from the list
                            print(f"QBD: Completed removed from Active Orders", active_orders, flush=True)
                        if order_number in livetemp_values:
                            livetemp_values.clear()
                            livetemp_values_normalized.clear()
                            print(f"QBD: Completed-Live Data cleared", flush=True)
            elif order_status == 'Aborted':
                # Add the order number to the list of aborted orders if the order is aborted and not already in the list
                if order_number:
                    with data_lock:
                        if order_number not in aborted_orders:
                            aborted_orders.append(order_number) # Add the order number to the list of aborted orders if the order is aborted
                        if order_number in completed_orders:
                            completed_orders.remove(order_number)  # Remove the order number from the list
                        if order_number in active_orders:
                            active_orders.remove(order_number)  # Remove the order number from the list
                        if order_number in livetemp_values:
                            livetemp_values.clear()
                            livetemp_values_normalized.clear()
                            print(f"QBD: Aborted-Live Data cleared", flush=True)
            elif order_status == 'Started':
                # Add the order number to the list of active orders if the order is started and not already in the list
                if order_number:
                    with data_lock:
                        if order_number not in active_orders:
                            active_orders.append(order_number) # Add the order number to the list of active orders if the order is started
                            print(f"QBD: Active Orders", active_orders, flush=True)
            else:
                print(f"QBD: Order status not actionable",order_number,order_status, flush=True)  
                                    
    except Exception as e:
        logging.error(f"Error in orders_consumers_qbd: {e}")
        pass
    finally:
        Process_orders_consumer.close()

###################### new code Temperatures consume and process ############################
def Temp_consume_and_process():
    
    # Define the number of messages to retrieve in one call
    num_messages = 100
    normalizeUpperLimit = 43
    normalizeLowerLimit = 17
    current_sum = 0
    count = 0
    current_time = 0
    normalizeFactor = normalizeUpperLimit - normalizeLowerLimit
    AverageCalculation = False
    all_values = []
    averaged_points = []
    averagetemp_values = {}
    averagetemp_values_normalized = {}
        
    global data_lock, temp_values_normalized, completed_orders,aborted_orders, active_orders, averaged_normalized_data, livetemp_values, livetemp_values_normalized, order_status, global_threading_var
    temp_values = {}  # Temperature values for each order

    print("QBD Starting TEMPS_consumers thread",completed_orders,temp_values_normalized, flush=True)
    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)
    Process_temp_consumer.subscribe(['ISPEMTemp'], on_assign=temp_on_assign)

    # Consume messages from the beginning of the topic
    while True:
        try:
            if completed_orders is None: 
                #print(f"QBD: No orders to process", flush=True)
                continue
            if completed_orders:  
                msgs = Process_temp_consumer.consume(num_messages, timeout=2.0)
                #print(f"QBD: TEMPS_consumers completed orders", completed_orders, flush=True)
                if not msgs:
                    continue
                for msg in msgs: 
                    if msg.error():
                        logging.error(f"QBD Temperature Consumer error: {msg.error()}")
                        continue
                    # Process message
                    temp_data = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
                    T_order_number = temp_data.get('orderNumber') # Order number from the temperature data
                    #print(f"\n QBD temps recieved for order_number:", T_order_number, flush=True)
                    if T_order_number and T_order_number in completed_orders:
                        with data_lock:
                            print(f"QBD value addition for order number:", T_order_number, flush=True)
                            if T_order_number in completed_orders: # process the values for the completed orders
                                    if T_order_number not in temp_values:
                                        temp_values[T_order_number] = []
                                    if T_order_number not in averagetemp_values:
                                        averagetemp_values[T_order_number] = []
                                        #print(f"QBD: Averaging Normalized Data requested", flush=True)
                                    timestamp = temp_data.get('timestamp')
                                    value = temp_data.get('value')
                                    averagetimestamp = timestamp #average data trending
                                    averagevalue = value #average data trending
                                    if timestamp and value is not None:
                                        temp_values[T_order_number].append((timestamp, value))
                                                                    
                                        # Normalize the temperature values
                                        timestamps, values = zip(*temp_values[T_order_number])
                                        min_timestamp = min(datetime.fromisoformat(ts) for ts in timestamps)
                                        times_in_minutes = [(datetime.fromisoformat(ts) - min_timestamp).total_seconds() / 60 for ts in timestamps]
                                        normalized_values = [((value - normalizeLowerLimit) / normalizeFactor) * 100 for value in values]
                                        temp_values_normalized[T_order_number] = list(zip(times_in_minutes, normalized_values))
                                        #print(f"Order {T_order_number}: Value Normalized \n",temp_values_normalized, flush=True)
                                        #print(f"Order {T_order_number}: Value Normalized \n", flush=True)
                                        
                                        # Check if the value already exists before adding
                                        if (averagetimestamp, averagevalue) not in averagetemp_values[T_order_number]:
                                            # average data trending
                                            averagetemp_values[T_order_number].append((averagetimestamp, averagevalue))
                                            averagetimestamps, averagevalues = zip(*averagetemp_values[T_order_number])
                                            averagemin_timestamp = min(datetime.fromisoformat(ts) for ts in averagetimestamps)
                                            averagetimes_in_minutes = [(datetime.fromisoformat(ts) - averagemin_timestamp).total_seconds() / 60 for ts in averagetimestamps]
                                            averagenormalized_values = [((averagevalue - normalizeLowerLimit) / normalizeFactor) * 100 for averagevalue in averagevalues]
                                            averagetemp_values_normalized[T_order_number] = list(zip(averagetimes_in_minutes, averagenormalized_values))
                                            AverageCalculation = True
                                        
                    elif T_order_number and T_order_number in active_orders: # order not completed yet
                        with data_lock: # process the values for the current orders to have them ready for the live view and next steps
                            if T_order_number:
                                    #print(f"QBD value prep for order number:", T_order_number, flush=True)
                                    if T_order_number not in temp_values:
                                        temp_values[T_order_number] = []
                                    if T_order_number not in livetemp_values:
                                        livetemp_values[T_order_number] = []
                                    if T_order_number not in averagetemp_values:
                                        averagetemp_values[T_order_number] = []
                            
                                    timestamp = temp_data.get('timestamp')
                                    value = temp_data.get('value')
                                    livetimestamp = timestamp #live data trending
                                    livevalue = value #live data trending
                                    averagetimestamp = timestamp #average data trending
                                    averagevalue = value #average data trending
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
                                        print(f"Order: Online Value Normalized \n", flush=True)  
                                        #print(f"\nQBD: livetemp_values_normalized",livetemp_values_normalized, flush=True)
                                        
                                        # Check if the value already exists before adding
                                        if (averagetimestamp, averagevalue) not in averagetemp_values[T_order_number]:
                                            # average data trending
                                            averagetemp_values[T_order_number].append((averagetimestamp, averagevalue))
                                            averagetimestamps, averagevalues = zip(*averagetemp_values[T_order_number])
                                            averagemin_timestamp = min(datetime.fromisoformat(ts) for ts in averagetimestamps)
                                            averagetimes_in_minutes = [(datetime.fromisoformat(ts) - averagemin_timestamp).total_seconds() / 60 for ts in averagetimestamps]
                                            averagenormalized_values = [((averagevalue - normalizeLowerLimit) / normalizeFactor) * 100 for averagevalue in averagevalues]
                                            averagetemp_values_normalized[T_order_number] = list(zip(averagetimes_in_minutes, averagenormalized_values))
                                            AverageCalculation = True
                                            
                    elif T_order_number and T_order_number in aborted_orders: # order not completed yet
                            with data_lock:
                                if T_order_number in livetemp_values:
                                    livetemp_values.remove(T_order_number)
                                    livetemp_values_normalized.remove(T_order_number)
                                    #print(f"QBD: Live Data cleared", flush=True)
                                
                                if T_order_number in averagetemp_values:
                                    averagetemp_values.remove(T_order_number)
                                    averagetemp_values_normalized.remove(T_order_number)
                                    #print(f"QBD: Averaged Data cleared", flush=True)
                    else:
                        print(f"QBD: T_Order not actionable",completed_orders,order_status, flush=True)
                                
                
                # Average the normalized temperature values
            if AverageCalculation and order_status == "Completed":
                        # print(f"\nQBD: Averaging Normalized Data", flush=True)
                        AverageCalculation = False

                        all_values.clear()
                        averaged_points.clear()
                        current_value_sum = 0.0
                        current_time_sum = 0.0
                        count = 0 
                        current_time = 0.0
                        
                        # Calculate the average value for all orders in the first 5 seconds, next 5 seconds, and so on
                        # Extract only the values (list of tuples) from the dictionary 
                        arrays_of_values = list(averagetemp_values_normalized.values())
                        for values in arrays_of_values:
                            all_values.extend(values)
                        all_values.sort(key=lambda x: x[0])  # Sort by timestamp
                        #print(f"\nQBD: All Values evaluated", all_values, flush=True)
                        for timestamp, value in all_values:
                            if timestamp - current_time <(5/60) :  # 5 seconds in minutes
                                current_value_sum += value
                                current_time_sum += timestamp
                                count += 1
                            else:
                                if count > 0:
                                    averagevalue= (current_value_sum/count)
                                    averagetime= (current_time_sum/count)
                                    averaged_points.append((averagetime, averagevalue))                             
                                    #print(f"\nQBD: Averaged Points evaluated", averaged_points, flush=True)
                                current_value_sum = value
                                current_time_sum = timestamp
                                count = 1
                                current_time += (5/60)  # Reset current_time to the new interval start
                                
                        # Append the last interval's average if there were any values accumulated
                        if count > 0:
                                averagevalue= (current_value_sum/count)
                                averagetime= (current_time_sum/count)
                                averaged_points.append((averagetime, averagevalue))  
                        #print(f"\nQBD: Final Averaged Points evaluated", averaged_points, flush=True)
                        print(f"\nQBD: Order Status", order_status, flush=True)     
            
            if order_status == "Completed":
                        averaged_normalized_data = averaged_points
        except Exception as e:
            logging.error(f"Error in Temp_consume_and_process: {e}")
            pass
        

threading.Thread(target=orders_consumers_qbd, daemon=True).start()
   
threading.Thread(target=Temp_consume_and_process, daemon=True).start()  

