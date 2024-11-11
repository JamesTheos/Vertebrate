from kafka import KafkaConsumer
import json

# Initialize Kafka consumer
consumer = KafkaConsumer(
    'your_topic',  # Kafka topic to subscribe to
    bootstrap_servers=['localhost:9092'],  # Kafka server address
    auto_offset_reset='earliest',  # Start reading at the earliest message
    enable_auto_commit=True,  # Automatically commit message offsets
    group_id='your_group_id',  # Consumer group ID
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))  # Deserialize message value from JSON
)

# Function to get data from Kafka
def get_kafka_data():
    for message in consumer:  # Iterate over messages in the Kafka topic
        return message.value  # Return the value of the first message