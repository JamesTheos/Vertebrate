from kafka import KafkaConsumer
import json
import os

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']

# Initialize Kafka consumer
consumer = KafkaConsumer(
    bootstrap_servers=Kafkaserver,  # Kafka server address
    auto_offset_reset='earliest',  # Start reading at the earliest message
    enable_auto_commit=True,  # Automatically commit message offsets
    group_id='LLM_Consumer_group',  # Consumer group ID
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))  # Deserialize message value from JSON
)

# Subscribe to multiple Kafka topics
consumer.subscribe(['ISPEMTemp', 'ISPESpeed', 'ISPEPressure','ISPEAmbTemp'])  # List of Kafka topics to subscribe to

# Function to get data from Kafka
def get_kafka_data():
    for message in consumer:  # Iterate over messages in the Kafka topics
        return message.value  # Return the value of the first message