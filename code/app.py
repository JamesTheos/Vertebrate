from flask import Flask, render_template, jsonify, request, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
import sqlite3
from confluent_kafka import Consumer, Producer, KafkaError, OFFSET_BEGINNING
from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
#from LLM_Consumer import get_kafka_data
#from Neo4j import get_neo4j_data
from datetime import datetime, timedelta
## Import the blueprints from the other modules
from product_analytics_app import product_analytics_app
from DesignSpaceApp import design_space_app  # Import the blueprint from the DesignSpaceApp module
from process_qbd_analysis import process_qbd_analysis  # Import the process QbD analysis blueprint
from consumeWorkflows import consumeWorkflows, get_all_workflows_route as get_all_workflows
from colorsettings import colorsettings
from demo_consumer import tempConsumerChatbot
from auth import auth
from models import db, User, Role, RolePermission, Permission, Subscriptions
from functools import wraps
from timeout import register_timeout_hook
from subscriptions import check_subscription,subscriptions
from audit_trail import log_audit, log_field_change
from utils import permission_required
from aas_api import aas_bp

# User-defined Roles


#Dictionary for user-defined roles
Created_Roles = {}    

#from Nexus2PLC import nexus2plc

import threading
import json
import os
import time
import sys

# Load the configuration for the ISA95 model
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
        config = json.load(config_file)
    
# Determine Kafka bootstrap servers from env or config
Kafkaserver = os.environ.get('KAFKASERVER', config.get('Kafkaserver', 'localhost:9092'))
# When running inside Docker, we want to keep Docker-internal hostnames like 'kafka:29092'.
# Allow overriding this behavior on the host by not setting IN_DOCKER.
IN_DOCKER = os.environ.get('IN_DOCKER', '').lower() in ['1', 'true', 'yes']
if isinstance(Kafkaserver, str) and Kafkaserver.startswith('kafka:') and not IN_DOCKER:
    print(f"Warning: KAFKASERVER='{Kafkaserver}' is a Docker-internal hostname. Using host address from config instead.")
    Kafkaserver = config.get('Kafkaserver', 'localhost:9092')

clusterid = os.environ.get('CLUSTERID', config.get('clusterid'))
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit= config['unit'] 

# Get clusterid saved in Database
_DB_URL_ENV = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
if _DB_URL_ENV:
    # When using external DB (e.g., Postgres in Docker), defer to runtime DB and default to current config
    cluster_id_temp = clusterid
else:
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'UserManagement.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM metainfo")
        Metainfo = cursor.fetchall()
        if Metainfo and len(Metainfo[0]) > 0:
            cluster_id_temp = Metainfo[0][0]
        else:
            cluster_id_temp = None
        conn.close()
    else:
        cluster_id_temp = None


def is_kafka_available(bootstrap_servers):
    try:
        admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
        admin_client.list_topics(timeout=3)
        return True
    except KafkaException as e:
        print(f"Kafka not available (KafkaException): {e}")
        return False
    except Exception as e:
        # Fallback for any unexpected non-Kafka exceptions
        print(f"Kafka not available (Unexpected): {e}")
        return False



kafka_cons_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'flask-consumer-group',
    'auto.offset.reset': 'earliest'
}
kafka_prod_conf = {
    'bootstrap.servers': Kafkaserver
}

consumer = None
producer = None

if is_kafka_available(Kafkaserver):
    try:
        consumer = Consumer(kafka_cons_conf)
    except KafkaException as e:
        print(f"Kafka consumer could not be initialized: {e}")
        consumer = None
    try:
        producer = Producer(kafka_prod_conf)
    except KafkaException as e:
        print(f"Kafka producer could not be initialized: {e}")
        producer = None
else:
    print("Kafka is unavailable. Consumers and producers will not be started.")



def send_to_kafka(topic, value):
    if producer is not None:
        try:
            producer.produce(topic, key="FromUX", value=json.dumps(value).encode('utf-8'))
            producer.flush()
        except KafkaException as e:
            print(f"Kafka error (KafkaException): {e}")
        except Exception as e:
            # Fallback for non-Kafka related exceptions
            print(f"Kafka error (Unexpected): {e}")
    else:
        print(f"Kafka producer unavailable, message for topic '{topic}' not sent: {value}")


data_store = {
    'ISPEScene1': [],
    'ISPEScene2': [],
    'ISPEMTemp': [],
    'ISPESpeed': [],
    'ISPEPressure': [],
    'ISPEAmbTemp': [],
    'ISPEStartPhase1': [],
    'ISPESelectPhase1': [],
    'manufacturing_orders': [],
    'order-management': [],
    'workflows': []
}

#Add topics if they dont exist
def create_topics_if_not_exist(bootstrap_servers, topics):
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    existing_topics = admin_client.list_topics(timeout=10).topics.keys()

    # Erstellen Sie nur Topics, die noch nicht existieren
    new_topics = [NewTopic(topic, num_partitions=1, replication_factor=1) for topic in topics if topic not in existing_topics]

    if new_topics:
        futures = admin_client.create_topics(new_topics)
        for topic, future in futures.items():
            try:
                future.result()  
                print(f"Topic '{topic}' created.")
            except KafkaException as e:
                print(f"Error when creating Topic (KafkaException): '{topic}': {e}")
            except Exception as e:
                print(f"Error when creating Topic (Unexpected): '{topic}': {e}")
    else:
        print("All topics registered.")


def consume_messages():
    global data_store
    print("App: Starting consume_messages thread", flush=True)  # Initial print statement

    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)
    consumer.subscribe(['ISPEScene1', 'ISPEScene2','ISPEMTemp','ISPESpeed','ISPEPressure','ISPEAmbTemp','ISPEStartPhase1', 'manufacturing_orders'], on_assign=temp_on_assign)
    #tbd: Scene1, Scene2 Start, needed?
    while True:
        try:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                ##print("message empty", flush=True)  # Debugging log
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(msg.error(), flush=True)
                    break
            topic = msg.topic()
            data = json.loads(msg.value().decode('utf-8'))
            timestamp = msg.timestamp()[1]  # Get the timestamp from the message
            if topic != 'manufacturing_orders':
                data_store[topic].append({
                    'timestamp': timestamp,
                    'value': data['value']  # Assuming the message contains 'value'
                })

            elif topic == 'manufacturing_orders':
                existing_order = next((order for order in data_store[topic] if order['orderNumber'] == data['orderNumber'] and order['product'] == data['product']), None)
                if existing_order:
                # Replace the existing order with the new data and timestamp
                    existing_order.update({
                        'timestamp': timestamp,
                        'status': data['status']
                    })
                else:
                    data_store[topic].append(data)
            #print(f"New data for {topic}: {data['value']} at {timestamp}", flush=True)  # Debugging log
        except KafkaException as e:
            print("KafkaException in APP:Consume_Messages:", e, flush=True)
            pass
        except Exception as e:
            print("Exception in APP:Consume_Messages:", e, flush=True)
            pass


def create_app():
# Create Flask application with custom static folder
    app = Flask(__name__)

    # Determine database URL (prefer env for containerized DB)
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not db_url:
        # Use SQLite file in code/instance as fallback for local development
        instance_dir = os.path.join(os.path.dirname(__file__), 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        db_file = os.path.join(instance_dir, 'UserManagement.db')
        # SQLAlchemy SQLite URI must use forward slashes
        db_url = 'sqlite:///' + db_file.replace('\\', '/')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.secret_key = 'your_secret_key'  # Set a secret key for session management
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes = 10) #generalt time session

    db.init_app(app)


    # Ensure tables exist (idempotent)
    with app.app_context():
        # Create audit_trail schema if it doesn't exist (for 21 CFR Part 11 compliance)
        from sqlalchemy import text
        try:
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS audit_trail'))
            db.session.commit()
        except Exception as e:
            print(f"Note: Could not create audit_trail schema (may already exist): {e}")
            db.session.rollback()

        # Now create 
        db.create_all()

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    register_timeout_hook(app)

    ##########################################################################################################################
    #USER MANAGEMENT
    ##########################################################################################################################

    app.register_blueprint(product_analytics_app)
    app.register_blueprint(design_space_app)
    app.register_blueprint(process_qbd_analysis)
    app.register_blueprint(consumeWorkflows)
    app.register_blueprint(colorsettings)
    app.register_blueprint(tempConsumerChatbot)
    app.register_blueprint(auth)
    app.register_blueprint(subscriptions)
    app.register_blueprint(aas_bp)

    ##########################################################################################################################
    #USER MANAGEMENT
    ##########################################################################################################################

    @app.route('/')
    @login_required
    def index():
        return render_template('index.html')
    
    @app.route('/3d-view')
    @login_required
    def view_3d():
        return render_template('3d-view.html')
    
    @app.route('/workflow-overview')
    @login_required
    def workflow_overview():
        return render_template('workflow-overview.html')

    @app.route('/equipment-overview')
    @login_required
    def equipment_overview():
        return render_template('equipment-overview.html')
    
    @app.route('/aas-viewer')
    @login_required
    def aas_viewer():
        return render_template('aas-viewer.html')

    @app.route('/sampling')
    @login_required
    def sampling():
        return render_template('sampling.html')

    @app.route('/batch')
    @login_required
    def batch():
        return render_template('batch.html')

    @app.route('/get-users', methods=['GET'])
    @login_required
    def get_users():
        users = User.query.all()
        user_list = [{'id': user.id, 'username': user.username, 'role': user.role} for user in users]
        return jsonify(user_list)

    @app.route('/add-user', methods=['POST'])
    @login_required
    def add_user():
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role = data.get('role')
        
        if not username or not password:
            return jsonify({'message': 'Username and password required.'}), 400

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'message': 'Username already exists. Please choose a different one.'}), 400

        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User added successfully.', 'user_id': new_user.id})

    @app.route('/delete-user', methods=['DELETE'])
    @login_required
    def delete_user():
        data = request.get_json()
        username = data.get('username')
        user = User.query.filter_by(username=username).first()
        if user:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'message': 'User deleted successfully.'})
        else:
            return jsonify({'message': 'User not found.'}), 404

    @app.route('/update-user', methods=['POST'])
    @login_required
    def update_user():
        data = request.get_json()
        username = data.get('username')
        new_password = data.get('new_password')
        new_role = data.get('new_role')
        user = User.query.filter_by(username=username).first()
        if user:
            if new_password:
                user.set_password(new_password)
            if new_role:
                user.role = new_role
            db.session.commit()
            return jsonify({'message': 'User updated successfully.'})
        else:
            return jsonify({'message': 'User not found.'}), 404

    @app.route('/get-user-data', methods=['GET'])
    @login_required
    def get_user_data():
        user = current_user
        return jsonify({'username': user.username, 'role': user.role})

    @app.route('/get-user-role', methods=['GET'])
    @login_required
    def get_user_role():
        user = current_user
        return jsonify({'role': user.role})

    @app.route('/check-permission', methods=['GET'])
    @login_required
    def check_permission():
        user = current_user
        permission_key = request.args.get('key')
        
        if not permission_key:
            return jsonify({'has_permission': False, 'message': 'No permission key provided'}), 400

        role = Role.query.filter_by(name=user.role).first()
        if not role:
            return jsonify({'has_permission': False, 'message': f'Role "{user.role}" not found'}), 404

        permission = Permission.query.filter_by(key=permission_key).first()
        if not permission:
            return jsonify({'has_permission': False, 'message': f'Permission "{permission_key}" not found'}), 404

        has_permission = RolePermission.query.filter_by(
            role_id=role.id, 
            permission_id=permission.id
        ).first() is not None

        return jsonify({'has_permission': has_permission})


    ##########################################################################################################################
    #SUBSCRIPTIONS
    ##########################################################################################################################

    @app.route('/subscription-management')
    @login_required
    def subscription_management():
        return render_template('subscription-management.html')

    @app.route('/subscription-denied')
    def subscription_denied():
        return render_template('subscription-denied.html')

    ##########################################################################################################################
    #SCADA
    ##########################################################################################################################

    @app.route('/scada')
    @login_required
    @check_subscription
    @permission_required('scada')
    def scada():
        return render_template('scada.html')

    @app.route('/get-data', methods=['GET'])
    @login_required
    def get_data():
        topic = request.args.get('topic')
        return jsonify(data_store.get(topic, []))

    @app.route('/send-data', methods=['POST'])
    @login_required
    def send_data():
        data = request.get_json()
        topic = data.get('topic')
        value = data.get('value')
        send_to_kafka(topic, {'value': value})
        return jsonify({'status': 'Message sent'})
    
    @app.route('/start-phase1', methods=['POST'])
    @login_required
    def start_phase1():
        data = request.get_json()
        topic = data.get('topic')
        value = data.get('value')
        send_to_kafka(topic, {'value': value})
        return jsonify({'status': 'Message sent'})


    ##########################################################################################################################
    #MANUFACTURING ORDERS
    ##########################################################################################################################

    @app.route('/manufacturing-orders')
    @login_required
    @check_subscription
    @permission_required('manufacturing_orders')
    def manufacturing_orders():
        return render_template('manufacturing-orders.html')

    @app.route('/order-management')
    @login_required
    @check_subscription
    @permission_required('order_management')
    def order_management():
        return render_template('order-management.html')

    @app.route('/get-manufacturing-orders', methods=['GET'])
    @login_required
    def get_manufacturing_orders():
        return jsonify(data_store['manufacturing_orders'])

    @app.route('/add-manufacturing-order', methods=['POST'])
    @login_required
    def add_manufacturing_order():
        data = request.get_json()
        send_to_kafka('manufacturing_orders', data)
        return jsonify({'status': 'Order sent to Kafka'})

    ##########################################################################################################################
    #SETTINGS
    ##########################################################################################################################

    @app.route('/settings')
    @login_required
    def settings():
        return render_template('settings.html')

    @app.route('/basesettings')
    @login_required
    def basesettings():
        return render_template('basesettings.html')

    @app.route('/user-management')
    @login_required
    def user_management():
        return render_template('user-management.html')

    @app.route('/role-management')
    @login_required
    def role_management():
        return render_template('role-management.html')

    @app.route('/user-profile')
    @login_required
    def user_profile():
        return render_template('user-profile.html')

    @app.route('/plant-config')
    @login_required
    def plant_config():
        return render_template('plantconfig.html')

    @app.route('/process-config')
    @login_required
    def process_config():
        return render_template('processconfig.html')

    @app.route('/get-plant-config', methods=['GET'])
    @login_required
    def get_plant_config():
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path) as config_file:
            config = json.load(config_file)
        return jsonify(config)

    @app.route('/save-plant-config', methods=['POST'])
    @login_required
    def save_plant_config():
        new_config = request.get_json()
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')

        with open(config_path) as f:
            old_config = json.load(f)

        with open(config_path, 'w') as f:
            json.dump(new_config, f, indent=4)

        changed_fields = [k for k in new_config if new_config.get(k) != old_config.get(k)]
        for field in changed_fields:
            log_field_change(
                action_type='UPDATE',
                record_type='PLANT_CONFIG',
                record_id='plant_config', field_name=field,
                old_value=old_config.get(field), new_value=new_config.get(field),
                change_reason='Plant configuration updated'
            )

        return jsonify({'status': 'Configuration saved successfully'})

    ###########################################################################################################################
    #ROLES EDITING
    ###########################################################################################################################

    @app.route('/get-role', methods=["POST"], endpoint='define_role')
    def define_role():
        data = request.get_json()
        new_role = data.get('created_role')
        allowed_apps = data.get('role_apps')

        if not new_role or not allowed_apps:
            return jsonify({'message': 'Role name and at least one function required.'}), 400

        if isinstance(allowed_apps, dict):
            perm_keys = list(allowed_apps.keys())
        else:
            perm_keys = list(allowed_apps)

        # Capture existence BEFORE any mutations
        existing_role = Role.query.filter_by(name=new_role).first()
        is_existing = existing_role is not None

        if is_existing:
            # Capture real old permissions BEFORE deletion
            old_perm_keys = [
                row[0] for row in
                db.session.query(Permission.key)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .filter(RolePermission.role_id == existing_role.id)
                .all()
            ]
            RolePermission.query.filter_by(role_id=existing_role.id).delete()
            db.session.flush()
            role = existing_role
        else:
            old_perm_keys = []
            role = Role(name=new_role)
            db.session.add(role)
            db.session.flush()

        for key in perm_keys:
            perm = Permission.query.filter_by(key=key).first()
            if not perm:
                perm = Permission(key=key)
                db.session.add(perm)
                db.session.flush()
            rp = RolePermission(role_id=role.id, permission_id=perm.id)
            db.session.add(rp)

        db.session.commit()

        action_type = 'UPDATE' if is_existing else 'CREATE'
        log_audit(
            action_type=action_type,
            record_type='ROLE',
            record_id=str(role.id),
            change_reason=f'Role "{new_role}" {"updated" if is_existing else "created"} with permissions: {perm_keys}'
        )

        # Log field-level change for UPDATE so old vs new permissions are captured
        if is_existing:
            log_field_change(
                action_type='UPDATE',
                record_type='ROLE',
                record_id=str(role.id),
                field_name='permissions',
                old_value=str(old_perm_keys),
                new_value=str(perm_keys),
                change_reason=f'Role "{new_role}" permissions updated'
            )

        return jsonify({'message': f'Role "{new_role}" saved in database.', 'role_id': role.id, 'permissions': perm_keys})

    @app.route('/update-role', methods=["POST"], endpoint='update_role')
    def update_role():
        data = request.get_json()
        role_name = data.get('role_name')
        updated_apps = data.get('updated_role_apps')

        if not role_name or not updated_apps:
            return jsonify({'message': 'Role name and at least one function required.'}), 400

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return jsonify({'message': 'Role not found'}), 404

        if isinstance(updated_apps, dict):
            perm_keys = list(updated_apps.keys())
        else:
            perm_keys = list(updated_apps)

        # Capture real old permissions BEFORE deletion
        old_perm_keys = [
            row[0] for row in
            db.session.query(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role.id)
            .all()
        ]

        # Remove existing permissions
        RolePermission.query.filter_by(role_id=role.id).delete()
        db.session.flush()

        # Recreate permissions
        for key in perm_keys:
            perm = Permission.query.filter_by(key=key).first()
            if not perm:
                perm = Permission(key=key)
                db.session.add(perm)
                db.session.flush()
            rp = RolePermission(role_id=role.id, permission_id=perm.id)
            db.session.add(rp)

        db.session.commit()

        log_field_change(
            action_type='UPDATE',
            record_type='ROLE',
            record_id=str(role.id),
            field_name='permissions',
            old_value=str(old_perm_keys),
            new_value=str(perm_keys),
            change_reason=f'Role "{role_name}" permissions updated'
        )

        return jsonify({'message': f'Role "{role_name}" updated successfully.', 'permissions': perm_keys})

    ##########################################################################################################################
    #LOGIN - USERNAME
    ##########################################################################################################################



    @app.route('/api/login', methods=['POST'])
    def login():

        username = request.json.get('username')
        password = request.json.get('password')

        config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
        with open(config_path) as config_file:
            config = json.load(config_file)

        config['Username'] = username

        with open(config_path, 'w') as config_file:
            json.dump(config, config_file, indent=4)

        return jsonify({'status': 'Username saved successfully'})
    

    return app
    



#if __name__ == '__main__':
    #threading.Thread(target=consume_messages, daemon=True).start()

    #app.run(debug=True, use_reloader=False,port=5001)
