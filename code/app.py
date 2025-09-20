import os
import json
import sqlite3

# Load existing config.json if present
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
config = {}
if os.path.exists(config_path):
    with open(config_path) as config_file:
        config = json.load(config_file)

# Environment-override for Kafka (Docker/container-friendly)
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', config.get('Kafkaserver', 'kafka:9092'))
clusterid = config.get('clusterid')

# Database path configurable via env; default to repo-relative instance path
DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'UserManagement.db'))

# Ensure instance directory exists and connect (create DB if missing)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH)

# Kafka client configurations use the env-overridden bootstrap servers
kafka_cons_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'flask-consumer-group',
    'auto.offset.reset': 'earliest'
}
kafka_prod_conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}

# -- The remainder of app.py should remain unchanged. These edits only make the broker and DB path configurable. --