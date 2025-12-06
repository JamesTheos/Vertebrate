from confluent_kafka import Producer
import json

# Konfiguration
conf = {'bootstrap.servers': 'localhost:9092'}
producer = Producer(conf)

# Daten vorbereiten (Nexus2PLC erwartet 'value' und 'timestamp')
topic = 'ISPEScene1' 
payload = {
    'value': True, 
    'timestamp': '2023-01-01T12:00:00' 
}

print(f"Sende 'True' an Topic {topic}...")
producer.produce(topic, json.dumps(payload).encode('utf-8'))
producer.flush()
print("Gesendet!")