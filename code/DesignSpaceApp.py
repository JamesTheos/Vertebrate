from flask import Blueprint, request, jsonify
from kafka import KafkaProducer, KafkaConsumer, TopicPartition
from kafka.errors import NoBrokersAvailable
import json
import logging
import uuid
import os
from models import db, DesignSpaceSet

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver = os.environ.get('KAFKASERVER', config['Kafkaserver'])
clusterid= config['clusterid']


# Create a blueprint
design_space_app = Blueprint('design_space_app', __name__)

# Configure logging to only show critical errors
logging.basicConfig(level=logging.CRITICAL)

# Kafka producer for sending data
try:
    producer = KafkaProducer(
        bootstrap_servers=Kafkaserver,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
except NoBrokersAvailable:
    print("Kafka broker not available. Please check your configuration and broker status.")
    producer = None


try:
    temp_consumer = KafkaConsumer(
        bootstrap_servers=Kafkaserver,
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
except NoBrokersAvailable:
    print("Kafka broker not available for temp_consumer.")
    temp_consumer = None

try:
    speed_consumer = KafkaConsumer(
        bootstrap_servers=Kafkaserver,
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
except NoBrokersAvailable:
    print("Kafka broker not available for speed_consumer.")
    speed_consumer = None

@design_space_app.route('/save-set', methods=['POST'])
def save_set():
    try:
        data = request.json
        if not data.get('id'):
            data['id'] = str(uuid.uuid4())
        design_set = db.session.get(DesignSpaceSet, data['id'])
        if design_set is None:
            design_set = DesignSpaceSet(id=data['id'])
            db.session.add(design_set)
        design_set.name = data.get('name') or data['id']
        design_set.data = data
        db.session.commit()
        if producer is not None:
            producer.send('design-space-topic', data)
            producer.flush()  # Ensure the message is sent
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving set: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@design_space_app.route('/get-sets', methods=['GET'])

# Endpoint to retrieve all sets from the storage.
# This function handles GET requests to the '/get-sets' route. It attempts to 
# fetch all sets stored in the design_space_sets table and return them as a JSON response.
# If an error occurs during the fetching process, it logs the error and returns 
# a JSON response with an error message and a 500 status code.
# Returns:
#     Response: A Flask Response object containing a JSON array of sets if successful,
#               or a JSON object with an error message and a 500 status code if an 
#               exception occurs.
def get_sets():
    try:
        sets = [s.data for s in DesignSpaceSet.query.order_by(DesignSpaceSet.name).all()]
        return jsonify(sets)
    except Exception as e:
        logging.error(f"Error fetching sets: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@design_space_app.route('/get-set/<set_id>', methods=['GET'])
def get_set(set_id):
    try:
        design_set = db.session.get(DesignSpaceSet, set_id)
        set_data = design_set.data if design_set else None
        if set_data:
            # print(f"DesignSpace:Fetched set with ID {set_id}: {set_data}")
            # border_points = [
            #     [float(point['ispespeed']), float(point['ispetemp'])]
            #     for point in set_data['values']
            #                 ]
            # print(f"DesignSpace:Border points for set {set_id}: {border_points}")
            return jsonify(set_data),200
        return jsonify({'status': 'error', 'message': 'Set not found'}), 404
    except Exception as e:
        logging.error(f"Error fetching set: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
       

##############################################################################################
@design_space_app.route('/get-latest-values', methods=['GET'])
def get_latest_values():
    try:
        if temp_consumer is None or speed_consumer is None:
            return jsonify({'status': 'error', 'message': 'Kafka not available'}), 503
        else:
            #print("DesignSpace:Assigning partitions and getting end offsets")
            # Assign partitions
            temp_partition = TopicPartition('ISPEMTemp', 0)
            speed_partition = TopicPartition('ISPESpeed', 0)
            
            temp_consumer.assign([temp_partition])
            speed_consumer.assign([speed_partition])

            # Get end offsets
            temp_end_offset = temp_consumer.end_offsets([temp_partition])[temp_partition]
            speed_end_offset = speed_consumer.end_offsets([speed_partition])[speed_partition]
            #print(f"DesignSpace:End offsets - ISPEMTemp: {temp_end_offset}, ISPESpeed: {speed_end_offset}")
                
            # Seek to the latest message
            temp_consumer.seek(temp_partition, temp_end_offset - 1)
            speed_consumer.seek(speed_partition, speed_end_offset - 1)
            
            #print("DesignSpace:Polling for the latest messages")
            # Poll for the latest messages
            temp_records = temp_consumer.poll(timeout_ms=1000)
            speed_records = speed_consumer.poll(timeout_ms=1000)
            
            latest_temp = None
            latest_speed = None
            
            #print("DesignSpace:Processing messages from ISPEMTemp")
            # Get the latest message from ISPEMTemp
            for tp, messages in temp_records.items():
                for message in messages:
                    latest_temp = message.value['value']
                    #print(f"Value for ISPEMTemp: {latest_temp}")

            #print("DesignSpace:Processing messages from ISPESpeed")
            # Get the latest message from ISPESpeed
            for tp, messages in speed_records.items():
                for message in messages:
                    latest_speed = message.value['value']
                    #print(f"Value for ISPESpeed: {latest_speed}")
            
            if latest_temp is None or latest_speed is None:
                #print("DesignSpace:No data available from ISPEMTemp or ISPESpeed topics")
                return jsonify({'status': 'error', 'message': 'No data available'}), 404
            
            #print(f"DesignSpace:Returning latest values: ISPESpeed={latest_speed}, ISPEMTemp={latest_temp}")
            return jsonify({'ispespeed': latest_speed, 'ispetemp': latest_temp})
    except Exception as e:
        #print(f"DesignSpace:Error fetching latest values: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
  