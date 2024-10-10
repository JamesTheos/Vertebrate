from flask import Flask, render_template, jsonify, request
from confluent_kafka import Consumer, Producer, KafkaException
import threading
import json

app = Flask(__name__)

# Kafka consumer configuration
kafka_conf = {
    'bootstrap.servers': '172.24.43.86:9092',
    'group.id': 'flask-consumer-group',
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(kafka_conf)
consumer.subscribe(['Test2', 'Test3'])  # Replace with your Kafka topics

# Kafka producer configuration
producer_conf = {
    'bootstrap.servers': '172.24.43.86:9092'
}
producer = Producer(producer_conf)

data_store = {
    'Test2': [],
    'Test3': [],
    'manufacturing_orders': []
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

@app.route('/manufacturing-orders')
def manufacturing_orders():
    return render_template('manufacturing-orders.html')

@app.route('/order-management')
def order_management():
    return render_template('order-management.html')

@app.route('/scada')
def scada():
    return render_template('scada.html')

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
    return render_template('overview.html')

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
        'orderNumber': order_number,
        'product': product,
        'lotNumber': lot_number
    }

    producer.produce('manufacturing_orders', json.dumps(message).encode('utf-8'))
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
