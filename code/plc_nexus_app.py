from flask import Flask, Blueprint, request, jsonify
from neo4j import get_neo4j_data
from opcua import Client
import json
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']

# Create a blueprint
plc_nexus_app = Flask( __name__)

# Initialize OPC UA client
opcua_client = Client("opc.tcp://localhost:4840")  # Replace with your OPC UA server address
opcua_client.connect()

# Function to update OPC UA node value
def update_opcua_node(node_id, value):
    node = opcua_client.get_node(node_id)
    node.set_value(bool(value))  # Ensure the value is written as a boolean
    print(f"Updated OPC UA node {node_id} with value {value}")

# Route to handle PLC to Nexus communication
@plc_nexus_app.route('/plc2nexus', methods=['POST'])
def plc2nexus():
    try:
        data = request.json
        node_id = data.get('node_id')
        value = data.get('value')
        if node_id and value is not None:
            update_opcua_node(node_id, value)
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route to handle Nexus to PLC communication
@plc_nexus_app.route('/nexus2plc', methods=['POST'])
def nexus2plc():
    try:
        data = request.json
        query = data.get('query')
        if query:
            neo4j_data = get_neo4j_data(query)
            return jsonify({'status': 'success', 'data': neo4j_data}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid query'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500