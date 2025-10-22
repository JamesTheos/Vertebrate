from app import create_app, create_topics_if_not_exist, consume_messages, data_store, Kafkaserver,Subscriptions, db
import threading
import subprocess
import sys
import json
import os
import sqlite3
from confluent_kafka.admin import AdminClient


# Always check if database exists for local SQLite only.
# When DATABASE_URL is provided (e.g., in Docker), skip SQLite setup.
if os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI'):
    cluster_id_temp = None  # Will be handled by the app/DB itself
else:
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'UserManagement.db')
    if not os.path.exists(db_path):
        print("Database does not exist. Creating a new one.")
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'createDB.py')])
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM metainfo")
    Metainfo = cursor.fetchall()
    if Metainfo and len(Metainfo[0]) > 0:
        cluster_id_temp = Metainfo[0][0]
    else:
        cluster_id_temp = None
    conn.close()

# Load config.json (fallback) and attempt to fetch Kafka cluster_id from broker
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

# Try to get cluster ID directly from Kafka (container)
def get_kafka_cluster_id(bootstrap_servers: str):
    try:
        admin = AdminClient({'bootstrap.servers': bootstrap_servers})
        md = admin.list_topics(timeout=5)
        # md.cluster_id is available in recent librdkafka; fallback if missing
        return getattr(md, 'cluster_id', None)
    except Exception as e:
        print(f"Warning: Could not fetch cluster ID from Kafka at '{bootstrap_servers}': {e}")
        return None

cluster_id = get_kafka_cluster_id(Kafkaserver) or config.get("clusterid")
print("Cluster ID (active):", cluster_id)


# Only perform SQLite reset logic when not using an external DB
if not (os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')) and cluster_id != cluster_id_temp:
    print("Cluster ID has changed (SQLite mode). Resetting local DB.")
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'UserManagement.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'createDB.py')])

flask_app = create_app()


if __name__ == "__main__":
    try:
        create_topics_if_not_exist(Kafkaserver, data_store.keys())
    except Exception as e:
        print(f"Warning: Could not connect to Kafka to create topics: {e}")

    try:
        from app import consumer
    except ImportError:
        consumer = None

    if consumer is not None:
        import threading
        threading.Thread(target=consume_messages, daemon=True).start()
    else:
        print("Not starting consume_messages thread because Kafka is unavailable.")
    flask_app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5001)