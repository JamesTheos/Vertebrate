from app import create_app, create_topics_if_not_exist, consume_messages, data_store, Kafkaserver,Subscriptions, db
import threading
import subprocess
import sys
import json
import os
import sqlite3


#Always check if database exists, if not create it. No need to constantly check for database existence
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

# Load config.json to fetch current active cluster_id
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

cluster_id = config.get("clusterid")
print("Cluster ID:", cluster_id)


if cluster_id != cluster_id_temp:
    print("Cluster ID has changed.")
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
    flask_app.run(debug=True, use_reloader=False, port=5001)