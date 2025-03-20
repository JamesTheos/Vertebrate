from flask import Blueprint, jsonify  # Import Flask and related modules for web server and request handling
from confluent_kafka import KafkaException, Consumer, OFFSET_BEGINNING  # Import Kafka modules for consuming messages
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

kafka_workflows = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'manufacturing_orders-workflows-released',
    'auto.offset.reset': 'earliest'
}

workflowsConsumer = Consumer(kafka_workflows)

#local memory to store released workflows

all_workflows = {} # Dictionary to store released and deactivated workflows

released_workflows = {}

consumeWorkflows = Blueprint('consumerWorkflows',__name__)  # Initialize Flask application

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
                if msg.error().code() == KafkaException._PARTITION_EOF:
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

    except KeyboardInterrupt:
        pass
    finally:
        workflowsConsumer.close()

threading.Thread(target=consume_workflows, daemon=True).start()  # Start the workflow consumption thread