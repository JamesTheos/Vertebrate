from flask import Flask, render_template, jsonify, request
from confluent_kafka import Consumer, Producer, KafkaException
import threading
import json
from datetime import datetime
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit= config['unit'] 

Kafkaserver = '172.20.50.243:9092'
# Create Flask application with custom static folder
app = Flask(__name__)

# Kafka consumer configuration
kafka_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'flask-consumer-group',
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(kafka_conf)
consumer.subscribe(['ISPEScene1', 'ISPEScene2','ISPEMTemp','ISPESpeed','ISPEPressure','ISPEAmbTemp','ISPEStartPhase1'])  # Kafka topics

# Kafka producer configuration
producer_conf = {
    'bootstrap.servers': Kafkaserver
}
producer = Producer(producer_conf)

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
    'manufacturing_orders': [],
    'order-management': []
}

def consume_messages():
    global data_store
    print("Starting consume_messages thread", flush=True)  # Initial print statement
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
        print(f"New data for {topic}: {data['value']} at {timestamp}", flush=True)  # Debugging log
        #print("Current data store message to follow", flush=True)  # Debugging log
       # print(f"Current data store: {data_store}", flush=True)  # Debugging log
       # print("Current data store message above me", flush=True)  # Debugging log

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/trending')
def trending():
    return render_template('trending.html')

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
        for order in data_store['manufacturing_orders']:
            if order['id'] == order_id:
                if action == 'release':
                    order['status'] = 'Released'
                elif action == 'abort':
                    order['status'] = 'Aborted'
                producer.send('order_management', order)
                break
        return jsonify({'status': 'Action Completed'}), 200
    return render_template('order-management.html', orders=data_store['manufacturing_orders'])

@app.route('/scada')
def scada():
    return render_template('scada.html')
        
@app.route('/equipment-overview')
def equipmentoverview():
    return render_template('equipment-overview.html')

@app.route('/3d-view')
def view3d():
    return render_template('3d-view.html')

@app.route('/batch')
def batch():
    return render_template('batch.html')

@app.route('/design-space-definition')
def designspacedefinition():
    return render_template('design-space-definition.html')

@app.route('/design-space-representation')
def designspacerepresentation():
    return render_template('design-space-representation.html')

@app.route('/order-overview')
def orderoverview():
    return render_template('order-overview.html')

@app.route('/overview')
def overview():
    released_orders = [order for order in data_store['manufacturing_orders'] if order['status'] == 'Released']
    return render_template('overview.html', orders=released_orders)


@app.route('/workflow/start', methods=['POST'])
def workflow_start():
    timestamp = datetime.utcnow().isoformat()
    send_to_kafka('ISPEStartPhase1', {'value': True, 'timestamp': timestamp})
    return jsonify({'success': True})

@app.route('/workflow/scene1', methods=['POST'])
def workflow_scene1():
    timestamp = datetime.utcnow().isoformat()
    send_to_kafka('ISPEScene1', {'value': True, 'timestamp': timestamp})
    send_to_kafka('ISPEScene2', {'value': False, 'timestamp': timestamp})
    return jsonify({'success': True})

@app.route('/workflow/scene2', methods=['POST'])
def workflow_scene2():
    timestamp = datetime.utcnow().isoformat()
    send_to_kafka('ISPEScene1', {'value': False, 'timestamp': timestamp})
    send_to_kafka('ISPEScene2', {'value': True, 'timestamp': timestamp})
    return jsonify({'success': True})

@app.route('/workflow/end', methods=['POST'])
def workflow_end():
    timestamp = datetime.utcnow().isoformat()
    send_to_kafka('ISPEScene1', {'value': False, 'timestamp': timestamp})
    send_to_kafka('ISPEScene2', {'value': False, 'timestamp': timestamp})
    send_to_kafka('ISPEStartPhase1', {'value': False, 'timestamp': timestamp})
    return jsonify({'success': True})

@app.route('/sampling')
def sampling():
    return render_template('sampling.html')

@app.route('/process-instructions')
def processinstructions():
    return render_template('process-instructions.html')

@app.route('/data/<topic>')
def get_data(topic):
    data = data_store.get(topic, [])
    print(f"Serving data for {topic}: {data}", flush=True)  # Debugging log
    return jsonify(data)

@app.route('/submit-order', methods=['POST'])
def submit_order():
    order_data = request.json
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

    producer.produce('manufacturing_orders', key="FromOrderManagement", value=json.dumps(message).encode('utf-8'))
    producer.flush()

    # Store the order in the data_store for order management
    data_store['manufacturing_orders'].append(message)

    return jsonify({'status': 'Order submitted successfully'})

@app.route('/orders')
def get_orders():
    orders = data_store.get('manufacturing_orders', [])
    return jsonify(orders)

if __name__ == '__main__':
    threading.Thread(target=consume_messages, daemon=True).start()
    app.run(debug=True)
