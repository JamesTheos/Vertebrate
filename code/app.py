from flask import Flask, render_template, jsonify
from confluent_kafka import Consumer, KafkaException
import threading
import json

app = Flask(__name__)

# Kafka consumer configuration
kafka_conf = {
    'bootstrap.servers': '192.168.108.88:9092',
    'group.id': 'flask-consumer-group',
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(kafka_conf)
consumer.subscribe(['Test2', 'Test3'])  # Replace with your Kafka topics

data_store = {
    'Test2': [],
    'Test3': []
}

def consume_messages():
    global data_store
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaException._PARTITION_EOF:
                continue
            else:
                print(msg.error())
                break
        topic = msg.topic()
        data = json.loads(msg.value().decode('utf-8'))
        data_store[topic].append(data['value'])  # Read only the 'value' from the message
        print(f"New data for {topic}: {data['value']}")  # Add this line for debugging

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data/<topic>')
def get_data(topic):
    return jsonify(data_store.get(topic, []))

if __name__ == '__main__':
    threading.Thread(target=consume_messages, daemon=True).start()
    app.run(debug=True)