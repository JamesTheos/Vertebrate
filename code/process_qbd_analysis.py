from flask import Blueprint, render_template, jsonify
from kafka import KafkaConsumer
from datetime import datetime
import json
import numpy as np
import logging
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
kafka_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'process-qbd-analysis-group',
    'auto.offset.reset': 'earliest'
}

# Initialize Kafka consumers
orders_consumer = KafkaConsumer(
    'manufacturing_orders',
    bootstrap_servers=Kafkaserver,
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

temp_consumer = KafkaConsumer(
    'ISPEMTemp',
    bootstrap_servers=Kafkaserver,
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)
###############code below to be done################

@process_qbd_analysis.route('/process-qbd-analysis')
def process_qbd_analysis_view():
    logging.info("Processing QbD Analysis View")
    completed_orders = {}
    temp_values = []

    try:
        # Fetch completed orders
        orders_consumer.poll(timeout_ms=1000)
        for message in orders_consumer:
            order = message.value
            if order['status'] == 'Completed':
                completed_orders[order['orderNumber']] = order['startTime']

        # Fetch temperature values for completed orders
        temp_consumer.poll(timeout_ms=1000)
        for message in temp_consumer:
            temp_data = message.value
            if temp_data['orderNumber'] in completed_orders:
                start_time = datetime.strptime(completed_orders[temp_data['orderNumber']], '%Y-%m-%dT%H:%M:%S')
                current_time = datetime.strptime(temp_data['timestamp'], '%Y-%m-%dT%H:%M:%S')
                time_from_start = (current_time - start_time).total_seconds()
                temp_values.append((time_from_start, temp_data['value']))

        if temp_values:
            times, temperatures = zip(*temp_values)
            average_temp = np.mean(temperatures)
            normalized_temps = [(temp - average_temp) / average_temp for temp in temperatures]
        else:
            times = []
            normalized_temps = []

        logging.info(f"Times: {times}, Normalized Temps: {normalized_temps}")
        return render_template('process-qbd-analysis.html', times=times, normalized_temps=normalized_temps)
    except Exception as e:
        logging.error(f"Error processing QbD Analysis View: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@process_qbd_analysis.route('/api/process-qbd-analysis')
def process_qbd_analysis_api():
    logging.info("Processing QbD Analysis API")
    completed_orders = {}
    temp_values = []

    try:
        # Fetch completed orders
        orders_consumer.poll(timeout_ms=1000)
        for message in orders_consumer:
            order = message.value
            if order['status'] == 'Completed':
                completed_orders[order['orderNumber']] = order['startTime']

        # Fetch temperature values for completed orders
        temp_consumer.poll(timeout_ms=1000)
        for message in temp_consumer:
            temp_data = message.value
            if temp_data['orderNumber'] in completed_orders:
                start_time = datetime.strptime(completed_orders[temp_data['orderNumber']], '%Y-%m-%dT%H:%M:%S')
                current_time = datetime.strptime(temp_data['timestamp'], '%Y-%m-%dT%H:%M:%S')
                time_from_start = (current_time - start_time).total_seconds()
                temp_values.append((time_from_start, temp_data['value']))

        if temp_values:
            times, temperatures = zip(*temp_values)
            average_temp = np.mean(temperatures)
            normalized_temps = [(temp - average_temp) / average_temp for temp in temperatures]
        else:
            times = []
            normalized_temps = []

        logging.info(f"Times: {times}, Normalized Temps: {normalized_temps}")
        return jsonify({'times': times, 'normalized_temps': normalized_temps})
    except Exception as e:
        logging.error(f"Error processing QbD Analysis API: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500