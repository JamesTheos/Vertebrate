from flask import Flask, jsonify
from kafka import KafkaConsumer
import json

app = Flask(__name__)
consumer = KafkaConsumer('design-space-topic', bootstrap_servers='localhost:9092', value_deserializer=lambda m: json.loads(m.decode('utf-8')))

@app.route('/get-live-data', methods=['GET'])
def get_live_data():
    data = []
    for message in consumer:
        data.append(message.value)
        if len(data) >= 20:  # Limit to the last 10 messages
            break
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)