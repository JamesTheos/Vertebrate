from flask import Blueprint, jsonify , request # Import Flask and related modules for web server and request handling
from confluent_kafka import KafkaException, Consumer, Producer, OFFSET_BEGINNING  # Import Kafka modules for consuming messages
import json  # Import JSON module for data serialization
from datetime import datetime  # Import datetime module for date and time handling
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit= config['unit'] 

kafka_produce_conf = {
    'bootstrap.servers': Kafkaserver
}
producer = Producer(kafka_produce_conf)

released_workflows = {}

def send_to_kafka(topic, value):
    producer.produce(topic, key="FromUX", value=json.dumps(value).encode('utf-8'))
    producer.flush()


processconfiguration = Blueprint('processconfiguration',__name__)  # Initialize Flask application




@processconfiguration.route('/save-workflow', methods=['POST'])
def save_workflow():
    data = request.json
    workflow_name = data.get('workflowName')
    
    save_path = os.path.join(os.path.dirname(__file__), 'workflows')
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    file_path = os.path.join(save_path, f'{workflow_name}.json')
    with open(file_path, 'w') as json_file:
        json.dump(data.get('selectedOptions'), json_file, indent=4)

    return jsonify({'success': True, 'message': 'Workflow saved successfully.'})


@processconfiguration.route('/get-workflows', methods=['GET'])
def get_workflows():
    save_path = os.path.join(os.path.dirname(__file__), 'workflows')
    if not os.path.exists(save_path):
        return jsonify({'workflows': []})

    workflows = [f.split('.')[0] for f in os.listdir(save_path) if f.endswith('.json')]
    return jsonify({'workflows': workflows})


@processconfiguration.route('/get-workflow/<workflow_name>', methods=['GET'])
def get_workflow(workflow_name):
    file_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
    if not os.path.exists(file_path):
        return jsonify({'error': 'Workflow not found'}), 404

    with open(file_path, 'r') as json_file:
        workflows = json.load(json_file)
        
    data = {
        'workflows': workflows,
        'released_workflows': released_workflows
    }
    return jsonify(data)

@processconfiguration.route('/delete-workflow/<workflow_name>', methods=['POST'])
def delete_workflow(workflow_name):
    file_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
    if not os.path.exists(file_path):
        return jsonify({'error': 'Workflow not found'}), 404

    os.remove(file_path)
    return jsonify({'success': True, 'message': 'Workflow deleted successfully.'})

@processconfiguration.route('/deactivate-workflow/<workflow_name>', methods=['POST'])   
def deactivate_workflow(workflow_name):
    send_to_kafka('workflows', {'workflow_name': workflow_name, 'released': 0})
    released_workflows[workflow_name]['released'] = 0
        
    return jsonify({'success': True, 'message': 'Workflow deactivated successfully.'})

@processconfiguration.route('/release-workflow/<workflow_name>', methods=['POST'])
def release_workflow(workflow_name):
    send_to_kafka('workflows', {'workflow_name': workflow_name, 'released': 1})
    released_workflows[workflow_name] = {'released': 1}
    print(released_workflows)

    return jsonify({'success': True, 'message': 'Workflow released successfully.'})