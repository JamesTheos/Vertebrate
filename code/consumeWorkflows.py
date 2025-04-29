from flask import Blueprint, jsonify, request  # Import Flask and related modules for web server and request handling
from confluent_kafka import KafkaError, Consumer, Producer ,OFFSET_BEGINNING  # Import Kafka modules for consuming messages
from confluent_kafka.admin import AdminClient  # Import Kafka Admin module for managing Kafka topics
import json  # Import JSON module for data serialization
import logging  # Import logging module for logging
import threading  # Import threading module for running background tasks
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

all_workflows = {} # Dictionary to store released and deactivated workflows

released_workflows = {}

#Consumer
kafka_workflows = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'manufacturing_orders-workflows-released',
    'auto.offset.reset': 'earliest'
}

workflowsConsumer = Consumer(kafka_workflows)

#local memory to store released workflows



consumeWorkflows = Blueprint('consumerWorkflows',__name__)  # Initialize Flask application

# ************************ 

# Producer

# ************************
kafka_produce_conf = {
    'bootstrap.servers': Kafkaserver
}
producer = Producer(kafka_produce_conf)



def send_to_kafka(topic, value):
    producer.produce(topic, key="FromWorkflowRelease", value=json.dumps(value).encode('utf-8'))
    producer.flush()



#Function to fetch all topics
def get_all_topics(bootstrap_servers):
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    try:
        cluster_metadata = admin_client.list_topics(timeout=10)
        topics = sorted([topic for topic in cluster_metadata.topics.keys() if topic != '__consumer_offsets'])
        return topics
    except Exception as e:
        print(f"Error retrieving topics: {e}")
        return []


@consumeWorkflows.route('/save-workflow', methods=['POST'])
def save_workflow():
    data = request.json
    workflow_name = data.get('workflowName')
    options = data.get('options', [])

 
    if not workflow_name:
        return jsonify({'success': False, 'message': 'Workflow name is required.'}), 400

    if not options:
        return jsonify({'success': False, 'message': 'No options provided for the workflow.'}), 400

    save_path = os.path.join(os.path.dirname(__file__), 'workflows')
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    workflow_data = {
        "workflowName": workflow_name,
        "options": options
    }

    file_path = os.path.join(save_path, f'{workflow_name}.json')
    with open(file_path, 'w') as json_file:
        json.dump(workflow_data, json_file, indent=4)

    return jsonify({'success': True, 'message': 'Workflow saved successfully.'})

@consumeWorkflows.route('/get-workflows', methods=['GET'])
def get_workflows():
    save_path = os.path.join(os.path.dirname(__file__), 'workflows')
    if not os.path.exists(save_path):
        return jsonify({'workflows': []})

    workflows = [f.split('.')[0] for f in os.listdir(save_path) if f.endswith('.json')]
    return jsonify({'workflows': workflows})



@consumeWorkflows.route('/get-workflow/<workflow_name>', methods=['GET'])
def get_workflow(workflow_name):
    file_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
    if not os.path.exists(file_path):
        return jsonify({'error': 'Workflow not found'}), 404

    with open(file_path, 'r') as json_file:
        workflows = json.load(json_file)
        
    data = {
        'workflows': workflows,
        'released_workflows': all_workflows
    }
    return jsonify(data)

@consumeWorkflows.route('/delete-workflow/<workflow_name>', methods=['POST'])
def delete_workflow(workflow_name):
    file_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
    if not os.path.exists(file_path):
        return jsonify({'error': 'Workflow not found'}), 404

    os.remove(file_path)
    return jsonify({'success': True, 'message': 'Workflow deleted successfully.'})

@consumeWorkflows.route('/deactivate-workflow/<workflow_name>', methods=['POST'])   
def deactivate_workflow(workflow_name):
    send_to_kafka('workflows', {'workflow_name': workflow_name, 'released': 0, "timestamp": datetime.now().isoformat()})
        
    return jsonify({'success': True, 'message': 'Workflow deactivated successfully.'})

@consumeWorkflows.route('/release-workflow/<workflow_name>', methods=['POST'])
def release_workflow(workflow_name):
    send_to_kafka('workflows', {'workflow_name': workflow_name, 'released': 1, "timestamp": datetime.now().isoformat()})

    return jsonify({'success': True, 'message': 'Workflow released successfully.'})

@consumeWorkflows.route('/api/get-all-topics', methods=['GET'])
def get_topics():
    topics = get_all_topics(Kafkaserver)
    return jsonify({'topics': topics})



# ************************ 

# Consumer

# ************************







@consumeWorkflows.route('/get-released-workflows', methods=['GET'])
def get_released_workflows():
    return jsonify({'workflows': list(released_workflows.keys())})

@consumeWorkflows.route('/get-all-workflows', methods=['GET'])
def get_all_workflows():
    return jsonify([{'workflow_name': name, 'state': 'Released' if info['released'] == 1 else 'Deactivated'} for name, info in all_workflows.items()])

def consume_workflows():
    print("Manufacturing Orders: Starting consume_workflows thread \n", flush=True)  # Print message to indicate thread start
    # Define the number of messages to retrieve in one call
    num_messages = 5
    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)
    workflowsConsumer.subscribe(['workflows'], on_assign=temp_on_assign)
    
    try:
      while True:
        msgs = workflowsConsumer.consume(num_messages, timeout=1.0)  # consume messages from the 'workflows' topic
        if msgs is None:
                continue  # Continue if no message is received
        for msg in msgs:
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue  # Continue if end of partition is reached
                else:
                    logging.error(f"Manufacturing Order: Consumer error: {msg.error()}")  # Log any other errors
                    continue
            workflow = json.loads(msg.value().decode('utf-8'))  # Deserialize the message value
            print(workflow)
            workflow_name = workflow['workflow_name']  # Get the workflow name  
            state = workflow['released']  # Get the state of the workflow
            timestamp = datetime.fromisoformat(workflow['timestamp'])  # Parse the ISO format timestamp

            if state == 1:
                # Add or update the workflow in the dictionary
                all_workflows[workflow_name] = {'timestamp': timestamp, 'released': state}
                released_workflows[workflow_name] = {'timestamp': timestamp}
                print(f"Manufacturing Order: Workflow {workflow_name} released at {timestamp}", flush=True)
            elif state == 0 and workflow_name in released_workflows:
                # Remove the workflow if the new message has a newer timestamp
                if released_workflows[workflow_name]['timestamp'] < timestamp:
                    all_workflows[workflow_name] = {'timestamp': timestamp, 'released': state}
                    del released_workflows[workflow_name]
                    print(f"Manufacturing Order: Workflow {workflow_name} removed", flush=True)

    except Exception as e:
        print("Exception in consume_workflows:", e, flush=True)  # Log any exceptions that occur
        pass
    finally:
        workflowsConsumer.close()

threading.Thread(target=consume_workflows, daemon=True).start()  # Start the workflow consumption thread