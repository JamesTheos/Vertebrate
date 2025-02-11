from flask import Flask, render_template, jsonify, request
from confluent_kafka import Consumer, Producer, KafkaException
from LLM_Consumer import get_kafka_data
from Neo4j import get_neo4j_data
from datetime import datetime
## Import the blueprints from the other modules
from product_analytics_app import product_analytics_app
from DesignSpaceApp import design_space_app  # Import the blueprint from the DesignSpaceApp module
from process_qbd_analysis import process_qbd_analysis  # Import the process QbD analysis blueprint
#from Nexus2PLC import nexus2plc
#from Chatbot import Chatbot, query_llama  # Import the chatbot blueprint

import threading
import json
import os
import time
import sys

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

# Create Flask application with custom static folder
app = Flask(__name__)

# Register the blueprints
app.register_blueprint(product_analytics_app)
app.register_blueprint(design_space_app)
app.register_blueprint(process_qbd_analysis)
#app.register_blueprint(nexus2plc)
def restart_app():
    print("App: Restarting application in 5 seconds...", flush=True)
    time.sleep(5)
    os.execv(sys.executable, ['python'] + sys.argv)

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"App: Exception occurred: {e}", flush=True)
    restart_app()
    return "An error occurred, restarting the application...", 500

#app.register_blueprint(Chatbot)

# Kafka consumer configuration
kafka_cons_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'flask-consumer-group',
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(kafka_cons_conf)
consumer.subscribe(['ISPEScene1', 'ISPEScene2','ISPEMTemp','ISPESpeed','ISPEPressure','ISPEAmbTemp','ISPEStartPhase1'])  # Kafka topics

# Kafka producer configuration
kafka_prod_conf = {
    'bootstrap.servers': Kafkaserver
}
producer = Producer(kafka_prod_conf)

def send_to_kafka(topic, value):
    producer.produce(topic, key="FromUX", value=json.dumps(value).encode('utf-8'))
    producer.flush()


data_store = {
    'ISPEScene1': [],
    'ISPEScene2': [],
    'ISPEMTemp': [],
    'ISPESpeed': [],
    'ISPEPressure': [],
    'ISPEAmbTemp': [],
    'ISPEStartPhase1': [],
    'ISPESelectPhase1': [],
    'manufacturing_orders': [],
    'order-management': []
}

def consume_messages():
    global data_store
    print("App: Starting consume_messages thread", flush=True)  # Initial print statement
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            ##print("message empty", flush=True)  # Debugging log
            continue
        if msg.error():
            if msg.error().code() == KafkaException._PARTITION_EOF:
                continue
            else:
                print(msg.error(), flush=True)
                break
        topic = msg.topic()
        data = json.loads(msg.value().decode('utf-8'))
        timestamp = msg.timestamp()[1]  # Get the timestamp from the message
        data_store[topic].append({
            'timestamp': timestamp,
            'value': data['value']  # Assuming the message contains 'value'
        })
        #print(f"New data for {topic}: {data['value']} at {timestamp}", flush=True)  # Debugging log
        #print("Current data store message to follow", flush=True)  # Debugging log
       # print(f"Current data store: {data_store}", flush=True)  # Debugging log
       # print("Current data store message above me", flush=True)  # Debugging log





#######################################################################################
#main route
@app.route('/')
def index():
    return render_template('index.html')

#######################################################################################
#analytics route
@app.route('/product_analytics')  # Define route for the product analytics page
def product_analytics():
    return render_template('product_analytics.html')  # Render the product_analytics.html template
@app.route('/process-qbd-analysis')
def trending():
   return render_template('process-qbd-analysis.html')

#######################################################################################
#Orders route
@app.route('/manufacturing-orders', methods=['GET', 'POST'])
def manufacturing_orders():
    if request.method == 'POST':
        order_data = request.json
        order_data['status'] = 'Created'
        producer.send('manufacturing_orders', order_data)
        data_store['manufacturing_orders'].append(order_data)
        return jsonify({'status': 'Order Created'}), 201
    return render_template('manufacturing-orders.html', orders=data_store['manufacturing_orders'])

@app.route('/order-management', methods=['GET', 'POST'])
def order_management():
    if request.method == 'POST':
        action = request.json.get('action')
        order_id = request.json.get('order_id')
        if not action or not order_id:
            return jsonify({'error': 'Missing action or order_id'}), 400
        
        order_found = False
        for order in data_store['manufacturing_orders']:
            if order['orderNumber'] == order_id:
                order_found = True
                if action == 'release':
                    order['status'] = 'Released'
                elif action == 'abort':
                    order['status'] = 'Aborted'
                    send_to_kafka('ISPEScene1', {'value': False, **order})
                    send_to_kafka('ISPEScene2', {'value': False, **order})
                    send_to_kafka('ISPEStartPhase1', {'value': False, **order})
                else:
                    return jsonify({'error': 'Invalid action'}), 400
                producer.produce('manufacturing_orders', key="FromOrderManagement", value=json.dumps(order).encode('utf-8'))
                producer.flush()
                break
        if not order_found:
            return jsonify({'error': 'Order not found'}), 404
        return jsonify({'status': 'Action Completed'}), 200
    return render_template('order-management.html', orders=data_store['manufacturing_orders'])

@app.route('/data/<topic>')
def get_data(topic):
    data = data_store.get(topic, [])
    #print(f"Serving data for {topic}: {data}", flush=True)  # Debugging log
    return jsonify(data)

@app.route('/submit-order', methods=['POST'])
def submit_order():
    order_data = request.json
    print(f"Requested Action: {order_data}")
    order_number = order_data.get('orderNumber')
    product = order_data.get('product')
    lot_number = order_data.get('lotNumber')

    if not order_number or not product or not lot_number:
        return jsonify({'error': 'Missing data'}), 400

    message = {
        'Enterprise': enterprise,
        'Site': site,
        'Area': area,
        'Process Cell': process_cell,
        'Unit': unit,
        'orderNumber': order_number,
        'product': product,
        'lotNumber': lot_number,
        'timestamp': datetime.now().isoformat(),
        'status': 'Created'
    }

    producer.produce('manufacturing_orders', key="FromOrderCreation", value=json.dumps(message).encode('utf-8'))
    producer.flush()

    # Store the order in the data_store for order management
    data_store['manufacturing_orders'].append(message)

    return jsonify({'status': 'Order submitted successfully'})

@app.route('/orders')
def get_orders():
    orders = data_store.get('manufacturing_orders', [])
    return jsonify(orders)

#######################################################################################
#Scada route
@app.route('/scada')
def scada():
    return render_template('scada.html')
@app.route('/equipment-overview')
def equipmentoverview():
    return render_template('equipment-overview.html')
@app.route('/3d-view')
def view3d():
    return render_template('3d-view.html')

#######################################################################################
#design-space route
@app.route('/design-space-definition')
def designspacedefinition():
    return render_template('design-space-definition.html')

@app.route('/design-space-representation')
def designspacerepresentation():
    return render_template('design-space-representation.html')

############################################################################################################
#Workflows route
@app.route('/batch')
def batch():
    return render_template('batch.html')
# @app.route('/order-overview')
# def orderoverview():
#     return render_template('order-overview.html')
@app.route('/overview') # Define route for the overview page under workflows
def overview():
    relStaCom_orders = [order for order in data_store['manufacturing_orders'] if order['status'] == 'Started']
    return render_template('overview.html', orders=relStaCom_orders)


@app.route('/api/released-orders', methods=['GET'])
def get_released_orders():
    released_orders = [order for order in data_store['manufacturing_orders'] if order['status'] == 'Released']
    return jsonify({'orders': released_orders})

@app.route('/api/order-status', methods=['GET'])
def get_orderOverview():
    return jsonify({'ordersOverview': data_store['manufacturing_orders']})

@app.route('/workflow/select', methods=['POST'])
def workflow_select():
    order_id = request.json.get('data')
    for order in data_store['manufacturing_orders']:
        if order['orderNumber'] == order_id:
            timestamp = datetime.utcnow().isoformat()
            send_to_kafka('ISPESelectPhase1', {'value': True, 'timestamp': timestamp, **order})
    return jsonify({'success': True})

@app.route('/workflow/start', methods=['POST'])
def workflow_start():
    order_id = request.json.get('data')
    print(f"Requested Start Order_ID: {order_id}")
    for order in data_store['manufacturing_orders']:
        print(f"Order: {order}")
        if order['orderNumber'] == order_id:
            order['status'] = 'Started'
            order['timestamp'] = datetime.utcnow().isoformat()
            send_to_kafka('ISPEStartPhase1', {'value': True, **order})
            send_to_kafka('manufacturing_orders', {**order})
    return jsonify({'success': True})

@app.route('/workflow/scene1', methods=['POST'])
def workflow_scene1():
    order_id = request.json.get('data')
    for order in data_store['manufacturing_orders']:
        print(f"Scene 2 Order: {order}")
        if order['orderNumber'] == order_id:
            order['timestamp'] = datetime.utcnow().isoformat()
            send_to_kafka('ISPEScene1', {'value': True, **order})
            send_to_kafka('ISPEScene2', {'value': False, **order})
    return jsonify({'success': True})

@app.route('/workflow/scene2', methods=['POST'])
def workflow_scene2():
    order_id = request.json.get('data')
    for order in data_store['manufacturing_orders']:
        print(f"Scene 2 Order: {order}")
        if order['orderNumber'] == order_id:
            order['timestamp'] = datetime.utcnow().isoformat()
            send_to_kafka('ISPEScene1', {'value': False, **order})
            send_to_kafka('ISPEScene2', {'value': True, **order})
    return jsonify({'success': True})

@app.route('/workflow/end', methods=['POST'])
def workflow_end():
    order_id = request.json.get('data')
    print(f"Requested Start Order_ID: {order_id}")
    for order in data_store['manufacturing_orders']:
        print(f"Completed Order: {order}")
        if order['orderNumber'] == order_id:
            order['status'] = 'Completed'
            order['timestamp'] = datetime.utcnow().isoformat()
            send_to_kafka('ISPEScene1', {'value': False, **order})
            send_to_kafka('ISPEScene2', {'value': False, **order})
            send_to_kafka('ISPEStartPhase1', {'value': False, **order})
            send_to_kafka('manufacturing_orders', {**order})
    return jsonify({'success': True})


@app.route('/sampling')
def sampling():
    return render_template('sampling.html')

@app.route('/process-instructions')
def processinstructions():
    return render_template('process-instructions.html')

# ############################################################################################################
# # Chatbot route
# @app.route('/ask', methods=['POST'])
# def ask():
#     user_input = request.json['question']  # Get the user's question from the request
    
#     # Fetch data from Kafka
#     kafka_data = get_kafka_data()
    
#     # Fetch data from Neo4j
#     neo4j_query = "MATCH (n) RETURN n LIMIT 5"  # Example query to fetch data from Neo4j
#     neo4j_data = get_neo4j_data(neo4j_query)
    
#     # Prepare prompt for LLM
#     prompt = f"User asked: {user_input}\nKafka data: {kafka_data}\nNeo4j data: {neo4j_data}\nAnswer:"
    
#     # Get response from LLM
#     response = query_llama(prompt)
    
#     return jsonify({'response': response})  # Return the LLM's response as JSON
############################################################################################################

if __name__ == '__main__':
    threading.Thread(target=consume_messages, daemon=True).start()
    app.run(debug=True, use_reloader=True,port=5001)