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
#Database has been reset after cluster_id change
flask_app = create_app()
# if cluster_id == cluster_id_temp:
#     print("Cluster ID has not changed.")
#     print("Checking for updates in subscriptions...")
#     # Update the subscriptions table based on subscribed_list and not_subscribed_list
#     with flask_app.app_context():
#         subscribed_only = set(subscribed_list) - set(not_subscribed_list)
#         not_subscribed_only = set(not_subscribed_list) - set(subscribed_list)

#         for app_name in subscribed_only:
#             sub = Subscriptions.query.filter_by(apps=app_name).first()
#             if sub:
#                 if not sub.subscribed:
#                     print(f"Updating {app_name} to subscribed=True")
#                     sub.subscribed = True
#             else:
#                 print(f"Adding new subscription: {app_name} subscribed=True")
#                 sub = Subscriptions(apps=app_name, subscribed=True)
#                 db.session.add(sub)

#         for app_name in not_subscribed_only:
#             sub = Subscriptions.query.filter_by(apps=app_name).first()
#             if sub:
#                 if sub.subscribed:
#                     print(f"Updating {app_name} to subscribed=False")
#                     sub.subscribed = False
#             else:
#                 print(f"Adding new subscription: {app_name} subscribed=False")
#                 sub = Subscriptions(apps=app_name, subscribed=False)
#                 db.session.add(sub)

#         db.session.commit()
    # No need to recreate the database, it remains intact

if __name__ == "__main__":
    try:
        create_topics_if_not_exist(Kafkaserver, data_store.keys())
    except Exception as e:
        print(f"Warning: Could not connect to Kafka to create topics: {e}")

    # Define or import 'consumer' here
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