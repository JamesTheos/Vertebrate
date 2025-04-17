from flask import Blueprint, Flask, request, jsonify, render_template
from kafka import KafkaProducer, KafkaConsumer, TopicPartition
import json
import logging
import uuid
#import threading
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']


# Create a blueprint
design_space_app = Blueprint('design_space_app', __name__)

# Configure logging to only show critical errors
logging.basicConfig(level=logging.CRITICAL)

# Kafka producer for sending data
producer = KafkaProducer(
    bootstrap_servers=Kafkaserver,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Kafka consumer for receiving data
consumer = KafkaConsumer(
    'design-space-topic',
    bootstrap_servers=Kafkaserver,
    auto_offset_reset='earliest',  # Read from the beginning of the topic
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

# Initialize storage for sets
sets_storage = {}

# Load existing sets from Kafka topic
def load_existing_sets():
    while not consumer.assignment():
        consumer.poll(timeout_ms=1000)
    partitions = consumer.assignment()
    consumer.seek_to_beginning(*partitions)
    while True:
        raw_msgs = consumer.poll(timeout_ms=1000)
        if not raw_msgs:
            break
        for tp, msgs in raw_msgs.items():
            for message in msgs:
                sets_storage[message.value['id']] = message.value
# Load existing sets from Kafka topic
load_existing_sets()

# Kafka consumers for ISPEMTemp and ISPESpeed topics
temp_consumer = KafkaConsumer(
    bootstrap_servers=Kafkaserver,
    auto_offset_reset='earliest',  # Read from the beginning of the topic
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

speed_consumer = KafkaConsumer(
    bootstrap_servers=Kafkaserver,
    auto_offset_reset='earliest',  # Read from the beginning of the topic
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

@design_space_app.route('/design-space-definition')
def design_space_definition():
    return render_template('design-space-definition.html')

@design_space_app.route('/design-space-representation')
def design_space_representation():
    return render_template('design-space-representation.html')

@design_space_app.route('/save-set', methods=['POST'])
def save_set():
    try:
        data = request.json
        if not data.get('id'):
            data['id'] = str(uuid.uuid4())
        sets_storage[data['id']] = data
        producer.send('design-space-topic', data)
        producer.flush()  # Ensure the message is sent
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logging.error(f"Error saving set: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@design_space_app.route('/get-sets', methods=['GET'])

# Endpoint to retrieve all sets from the storage.
# This function handles GET requests to the '/get-sets' route. It attempts to 
# fetch all sets stored in the `sets_storage` and return them as a JSON response.
# If an error occurs during the fetching process, it logs the error and returns 
# a JSON response with an error message and a 500 status code.
# Returns:
#     Response: A Flask Response object containing a JSON array of sets if successful,
#               or a JSON object with an error message and a 500 status code if an 
#               exception occurs.
def get_sets():
    try:
        sets = list(sets_storage.values())
        return jsonify(sets)
    except Exception as e:
        logging.error(f"Error fetching sets: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@design_space_app.route('/get-set/<set_id>', methods=['GET'])
def get_set(set_id):
    try:
        set_data = sets_storage.get(set_id)
        if set_data:
            return jsonify(set_data)
        return jsonify({'status': 'error', 'message': 'Set not found'}), 404
    except Exception as e:
        logging.error(f"Error fetching set: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
       

##############################################################################################
@design_space_app.route('/get-latest-values', methods=['GET'])
def get_latest_values():
    try:
        print("DesignSpace:Assigning partitions and getting end offsets")
        # Assign partitions
        temp_partition = TopicPartition('ISPEMTemp', 0)
        speed_partition = TopicPartition('ISPESpeed', 0)
        
        temp_consumer.assign([temp_partition])
        speed_consumer.assign([speed_partition])

        # Get end offsets
        temp_end_offset = temp_consumer.end_offsets([temp_partition])[temp_partition]
        speed_end_offset = speed_consumer.end_offsets([speed_partition])[speed_partition]
        print(f"DesignSpace:End offsets - ISPEMTemp: {temp_end_offset}, ISPESpeed: {speed_end_offset}")
            
        # Seek to the latest message
        temp_consumer.seek(temp_partition, temp_end_offset - 1)
        speed_consumer.seek(speed_partition, speed_end_offset - 1)
        
        print("DesignSpace:Polling for the latest messages")
        # Poll for the latest messages
        temp_records = temp_consumer.poll(timeout_ms=1000)
        speed_records = speed_consumer.poll(timeout_ms=1000)
        
        latest_temp = None
        latest_speed = None
        
        print("DesignSpace:Processing messages from ISPEMTemp")
        # Get the latest message from ISPEMTemp
        for tp, messages in temp_records.items():
            for message in messages:
                latest_temp = message.value['value']
                print(f"Value for ISPEMTemp: {latest_temp}")

        print("DesignSpace:Processing messages from ISPESpeed")
        # Get the latest message from ISPESpeed
        for tp, messages in speed_records.items():
            for message in messages:
                latest_speed = message.value['value']
                print(f"Value for ISPESpeed: {latest_speed}")
        
        if latest_temp is None or latest_speed is None:
            print("DesignSpace:No data available from ISPEMTemp or ISPESpeed topics")
            return jsonify({'status': 'error', 'message': 'No data available'}), 404
        
        print(f"DesignSpace:Returning latest values: ISPESpeed={latest_speed}, ISPEMTemp={latest_temp}")
        return jsonify({'ispespeed': latest_speed, 'ispetemp': latest_temp})
    except Exception as e:
        print(f"DesignSpace:Error fetching latest values: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
  