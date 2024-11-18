from flask import Blueprint, render_template, jsonify
from kafka import KafkaConsumer
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

@process_qbd_analysis.route('/process-qbd-analysis')
def process_qbd_analysis_view():
    logging.info("Processing QbD Analysis View")
    completed_orders = set()
    temp_values = []

    # Fetch completed orders
    orders_consumer.poll(timeout_ms=1000)
    for message in orders_consumer:
        order = message.value
        if order['status'] == 'Completed':
            completed_orders.add(order['orderNumber'])

    # Fetch temperature values for completed orders
    temp_consumer.poll(timeout_ms=1000)
    for message in temp_consumer:
        temp_data = message.value
        if temp_data['orderNumber'] in completed_orders:
            temp_values.append(temp_data['value'])

    if temp_values:
        average_temp = np.mean(temp_values)
        spread_temp = np.std(temp_values)
    else:
        average_temp = 0
        spread_temp = 0

    logging.info(f"Average Temp: {average_temp}, Spread Temp: {spread_temp}")
    return render_template('process-qbd-analysis.html', average_temp=average_temp, spread_temp=spread_temp)

@process_qbd_analysis.route('/api/process-qbd-analysis')
def process_qbd_analysis_api():
    logging.info("Processing QbD Analysis API")
    completed_orders = set()
    temp_values = []

    # Fetch completed orders
    orders_consumer.poll(timeout_ms=1000)
    for message in orders_consumer:
        order = message.value
        if order['status'] == 'Completed':
            completed_orders.add(order['orderNumber'])

    # Fetch temperature values for completed orders
    temp_consumer.poll(timeout_ms=1000)
    for message in temp_consumer:
        temp_data = message.value
        if temp_data['orderNumber'] in completed_orders:
            temp_values.append(temp_data['value'])

    if temp_values:
        average_temp = np.mean(temp_values)
        spread_temp = np.std(temp_values)
    else:
        average_temp = 0
        spread_temp = 0

    logging.info(f"Average Temp: {average_temp}, Spread Temp: {spread_temp}")
    return jsonify({'average_temp': average_temp, 'spread_temp': spread_temp})