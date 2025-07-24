from app import create_app, create_topics_if_not_exist, consume_messages, data_store, Kafkaserver
import threading
import subprocess
import sys
import json
import os
import sqlite3

#Fetch cluster_id from the database
conn = sqlite3.connect('C:/Users/User/Documents/GitHub/Vertebrate/code/instance/UserManagement.db')
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

#check if cluster_id has changed
if cluster_id != cluster_id_temp:
    print("Cluster ID has changed.")
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'UserManagement.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    # Run createDB.py to recreate the database
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'createDB.py')])
else:
    print("Cluster ID has not changed.")
    # No need to recreate the database, it remains intact

#Database has been reset after cluster_id change

flask_app = create_app()

if __name__ == "__main__":
    create_topics_if_not_exist(Kafkaserver, data_store.keys())
    
    flask_app.run(debug=True, use_reloader=False,port=5001)
    threading.Thread(target=consume_messages, daemon=True).start()

