from flask import Flask, app, render_template, jsonify, request, abort
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
from consumeWorkflows import consumeWorkflows, get_all_workflows
from colorsettings import colorsettings
from demo_consumer import tempConsumerChatbot
from auth import auth
from models import db, User
from functools import wraps
from timeout import register_timeout_hook


# User-defined Roles
from models import db, Role, RolePermission

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
    
Kafkaserver= config['Kafkaserver']
clusterid= config['clusterid']
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit= config['unit'] 

#Get clusterid saved in Database
db_path = 'C:/Users/User/Documents/GitHub/Vertebrate/code/instance/UserManagement.db'
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

# Kafka consumer configuration
kafka_cons_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'flask-consumer-group',
    'auto.offset.reset': 'earliest'
}

try:
    consumer = Consumer(kafka_cons_conf)
    # consumer.subscribe(['ISPEScene1', 'ISPEScene2','ISPEMTemp','ISPESpeed','ISPEPressure','ISPEAmbTemp','ISPEStartPhase1'])  # Kafka topics
except KafkaException as e:
    print(f"Kafka consumer could not be initialized: {e}")
    consumer = None


# Kafka producer configuration
kafka_prod_conf = {
    'bootstrap.servers': Kafkaserver
}
producer = Producer(kafka_prod_conf)

def send_to_kafka(topic, value):
    producer.produce(topic, key="FromUX", value=json.dumps(value).encode('utf-8'))
    producer.flush()



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
            except Exception as e:
                print(f"Error when creating Topic: '{topic}': {e}")
    else:
        print("All topics registered.")

create_topics_if_not_exist(Kafkaserver, data_store.keys())

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
        except Exception as e:
            print("Exception in APP:Consume_Messages:", e, flush=True)
            pass


def create_app():
# Create Flask application with custom static folder
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///UserManagement.db'  # Example URI, change as needed
    app.secret_key = 'your_secret_key'  # Set a secret key for session management
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes = 10) #generalt time session

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    app.register_blueprint(auth)
    
    register_timeout_hook(app)


    # Register the blueprints
    app.register_blueprint(product_analytics_app)
    app.register_blueprint(design_space_app)
    app.register_blueprint(process_qbd_analysis)
    app.register_blueprint(consumeWorkflows)
    app.register_blueprint(colorsettings)
    app.register_blueprint(tempConsumerChatbot)
#app.register_blueprint(nexus2plc)

    @app.context_processor
    def inject_config():
        config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
        with open(config_path) as config_file:
            config = json.load(config_file)
        return dict(appconfig=config)
    
    #######################################################################################
    #User-defined Roles
#    @app.route('/get-role',methods = ["POST"])
#   def define_role():
#        new_role = request.json.get('created_role')
#        allowed_apps = request.json.get('role_apps')
#        if new_role not in Created_Roles.keys():
#            Created_Roles[new_role] = allowed_apps
#        else:
#            Created_Roles[new_role] = allowed_apps
#        return Created_Roles

    #######################################################################################
    #main route
    
    #One-time check to set the main route based on clusterid
    if clusterid != cluster_id_temp:
        @app.route('/')
        def initial_index_redirect():
            return render_template('initial-index.html')
    else:
        @app.route('/')
        def index_redirect():
            return render_template('index.html')
    @app.route('/initial-index')
    def initial_index():
        return render_template('initial-index.html')

    #@app.route('/')
    @app.route('/index')
    def index():
        return render_template('index.html')
    
    #login-error route
    @app.route('/login-error')
    def Login_error():
        return render_template('Login-error.html')
    
    #logout-message route
    @app.route('/logout-message')
    def Logout_message():
        return render_template('Logout-message.html')
    
    #Updated User Info route
    @app.route('/updated-user')
    def updated_user():
        return render_template('Updated-User.html')

    #######################################################################################
    #analytics route
    @app.route('/product_analytics')
    #@roles_required('admin')
    def product_analytics():
        return render_template('product_analytics.html')

    @app.route('/process-qbd-analysis')
    #@roles_required('user')
    def trending():
        return render_template('process-qbd-analysis.html')

    #######################################################################################
    #Orders route
    @app.route('/manufacturing-orders', methods=['GET', 'POST'])
    #@roles_required('guest')
    def manufacturing_orders():
        return render_template('manufacturing-orders.html')
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('access.html'), 403

    @app.route('/order-management', methods=['GET', 'POST'])
    def order_management():
        if request.method == 'POST':
            action = request.json.get('action')
            order_id = request.json.get('order_id')
            workflow_name = request.json.get('workflowName')


            if not workflow_name or not order_id or not action:
                return jsonify({'error': 'Missing required fields'}), 400

            # Load the workflow data from the JSON file
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
            if not os.path.exists(workflow_path):
                return jsonify({'error': 'Workflow not found'}), 404

            with open(workflow_path) as workflow_file:
                workflow_data = json.load(workflow_file)

            
            order_found = False
            for order in data_store['manufacturing_orders']:
                if order['orderNumber'] == order_id:
                    order_found = True
                    if action == 'release':
                        order['status'] = 'Released'
                    elif action == 'abort':
                        order['status'] = 'Aborted'

                        # Reset all values to null for all external topics
                        for step in workflow_data['options']:
                            for action in step.get('actions', []):
                                if action.get('external'):
                                    topic = action.get('topic')
                                    send_to_kafka(topic, {'value': False, **order})
                    else:
                        return jsonify({'error': 'Invalid action'}), 400
                    producer.produce('manufacturing_orders', key="FromOrderManagement", value=json.dumps(order).encode('utf-8'))
                    producer.flush()
                    break
            if not order_found:
                return jsonify({'error': 'Order not found'}), 404
            return jsonify({'status': 'Action Completed'}), 200
        return render_template('order-management.html', orders=data_store['manufacturing_orders'])

    @app.route('/data/<topic>')
    def get_data(topic):
        data = data_store.get(topic, [])
        #print(f"Serving data for {topic}: {data}", flush=True)  # Debugging log
        return jsonify(data)

    @app.route('/submit-order', methods=['POST'])
    def submit_order():
        order_data = request.json
        print(f"Requested Action: {order_data}")
        order_number = order_data.get('orderNumber')
        product = order_data.get('product')
        lot_number = order_data.get('lotNumber')
        workflow = order_data.get('workflow')

        if not order_number or not product or not lot_number:
            return jsonify({'error': 'Missing data'}), 400

        message = {
            'Enterprise': enterprise,
            'Site': site,
            'Area': area,
            'Process Cell': process_cell,
            'Unit': unit,
            'orderNumber': order_number,
            'product': product,
            'lotNumber': lot_number,
            'workflow': workflow,
            'timestamp': datetime.now().isoformat(),
            'status': 'Created'
        }
        print(f"Order Submitted: {message}")
        producer.produce('manufacturing_orders', key="FromOrderCreation", value=json.dumps(message).encode('utf-8'))
        producer.flush()

        return jsonify({'status': 'Order submitted successfully'})

    @app.route('/orders')
    def get_orders():
        orders = data_store.get('manufacturing_orders', [])
        return jsonify(orders)

    #######################################################################################
    #Scada route
    @app.route('/scada')
    def scada():
        return render_template('scada.html')
    @app.route('/equipment-overview')
    def equipmentoverview():
        return render_template('equipment-overview.html')
    @app.route('/3d-view')
    def view3d():
        return render_template('3d-view.html')

    #######################################################################################
    #design-space route
    @app.route('/design-space-definition')
    def designspacedefinition():
        return render_template('design-space-definition.html')

    @app.route('/design-space-representation')
    def designspacerepresentation():
        return render_template('design-space-representation.html')

    ############################################################################################################
    #Workflows route
    @app.route('/batch')
    def batch():
        return render_template('batch.html')

    @app.route('/overview') # Define route for the overview page under workflows
    def overview():
        workflows = get_all_workflows().json
        relStaCom_orders = [order for order in data_store['manufacturing_orders'] if order['status'] == 'Started']
        print(f"Orders: {relStaCom_orders}")
        print(f"Workflows: {workflows}")
        return render_template('overview.html', running_orders=relStaCom_orders, workflows=workflows)


    @app.route('/api/released-orders', methods=['GET'])
    def get_released_orders():
        released_orders = [order for order in data_store['manufacturing_orders'] if order['status'] == 'Released' or order['status'] == 'Started']
        return jsonify({'orders': released_orders})

    @app.route('/api/order-status', methods=['GET'])
    def get_orderOverview():
        return jsonify({'ordersOverview': data_store['manufacturing_orders']})




    @app.route('/api/workflows', methods=['POST'])
    def workflow_steps():
        try:
            data = request.json
            workflow_name = data.get('workflow_name')
            order_number = data.get('orderNumber')
            current_step_index = data.get('currentStep')
            button_pressed = data.get('action')

            if not workflow_name or not order_number or current_step_index is None or not button_pressed:
                return jsonify({'error': 'Missing required fields'}), 400

            # Load the workflow data from the JSON file
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
            if not os.path.exists(workflow_path):
                return jsonify({'error': 'Workflow not found'}), 404

            with open(workflow_path) as workflow_file:
                workflow_data = json.load(workflow_file)

            # Index each step in the workflow starting from 0
            for index, step in enumerate(workflow_data.get('options', [])):
                step['stepIndex'] = index + 1

            total_steps = len(workflow_data.get('options', []))
            if total_steps == 0:
                return jsonify({'error': 'No steps found in the workflow'}), 400

            # Handle the first step of the workflow
            if current_step_index == 1 and total_steps > 1:
                for order in data_store['manufacturing_orders']:
                    if order['orderNumber'] == order_number:
                        order['status'] = 'Started'
                        order['timestamp'] = datetime.utcnow().isoformat()
                        for actions in workflow_data['options'][0].get('actions', []):
                            if actions.get('action') == button_pressed:
                                if actions.get('external'):
                                    topic = actions.get('topic')
                                    external_action = actions.get('externalAction')
                                    send_to_kafka(topic, {'value': external_action, **order})

                                    #Demo adaptation to add second action
                                    if topic == 'ISPEScene1':
                                        if external_action == True:
                                            send_to_kafka('ISPEScene2', {'value': False, **order})
                                        elif external_action == False:   
                                            send_to_kafka('ISPEScene2', {'value': True, **order})

                                    elif topic == 'ISPEScene2':
                                        if external_action == True:
                                            send_to_kafka('ISPEScene1', {'value': False, **order})
                                        elif external_action == False:   
                                            send_to_kafka('ISPEScene1', {'value': True, **order})
                                    break
                        send_to_kafka('manufacturing_orders', {**order})

            if current_step_index < total_steps and current_step_index > 1:
                for order in data_store['manufacturing_orders']:
                    if order['orderNumber'] == order_number:
                        order['timestamp'] = datetime.utcnow().isoformat()

                        for option in workflow_data['options'][current_step_index - 1].get('actions', []):
                            if option.get('action') == button_pressed:
                                if option.get('external'):
                                    step_current_topic = option.get('topic')
                                    action_current = option.get('externalAction')
                                    send_to_kafka(step_current_topic, {'value': action_current, **order})

                                    #Demo adaptation to add second action
                                    if step_current_topic == 'ISPEScene1':
                                        if action_current == True:
                                            send_to_kafka('ISPEScene2', {'value': False, **order})
                                        elif action_current == False:   
                                            send_to_kafka('ISPEScene2', {'value': True, **order})

                                    elif step_current_topic == 'ISPEScene2':
                                        if action_current == True:
                                            send_to_kafka('ISPEScene1', {'value': False, **order})
                                        elif action_current == False:   
                                            send_to_kafka('ISPEScene1', {'value': True, **order})
                                    break

            if current_step_index == total_steps:
                for order in data_store['manufacturing_orders']:
                    if order['orderNumber'] == order_number:
                        order['status'] = 'Completed'
                        order['timestamp'] = datetime.utcnow().isoformat()

                        for actions in workflow_data['options'][current_step_index - 1].get('actions', []):
            
                            if actions.get('action') == button_pressed:
                                if actions.get('external'):
                                    topic = actions.get('topic')
                                    external_action = actions.get('externalAction')
                                    send_to_kafka(topic, {'value': external_action, **order})

                                    #Demo adaptation to add second action
                                    if topic == 'ISPEScene1':
                                        if external_action == True:
                                            send_to_kafka('ISPEScene2', {'value': False, **order})
                                        elif external_action == False:   
                                            send_to_kafka('ISPEScene2', {'value': True, **order})

                                    elif topic == 'ISPEScene2':
                                        if external_action == True:
                                            send_to_kafka('ISPEScene1', {'value': False, **order})
                                        elif external_action == False:   
                                            send_to_kafka('ISPEScene1', {'value': True, **order})
                                    break

                        send_to_kafka('manufacturing_orders', {**order})

                        # Reset all values to null for all external topics
                        for step in workflow_data['options']:
                            for action in step.get('actions'):
                                if action.get('external') == True:
                                    topic = action.get('topic')
                                    send_to_kafka(topic, {'value': False, **order})

            return jsonify({'success': True})

        except Exception as e:
            print(f"Error in /api/workflows: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    


    #returns workflow for process instructions
    @app.route('/api/get-workflow', methods=['GET'])
    def get_workflow():
        orderNumber = request.args.get('orderNumber')
        print(f"Requested Order: {orderNumber}")
        order = next((order for order in data_store['manufacturing_orders'] if order['orderNumber'] == orderNumber), None)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        workflow = order.get('workflow')

    
        workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow}.json')
        if os.path.exists(workflow_path):
            with open(workflow_path) as workflow_file:
                workflow_data = json.load(workflow_file)

            data = {
                'workflows': workflow_data.get('options'),
                'workflow_name': workflow_data.get('workflowName'),
            }
            return jsonify(data)
        else:
            return jsonify({'error': 'Workflow not found'}), 404

    @app.route('/sampling')
    def sampling():
        return render_template('sampling.html')

    @app.route('/process-instructions')
    def processinstructions():
        return render_template('process-instructions.html' )

    @app.route('/settings')
    def settings():
        return render_template('settings.html')
    
    @app.route('/role-management')
    def role_management():
        roles = Role.query.all()
        # Optionally, get permissions for each role
        roles_with_permissions = [
            {
                'name': role.name,
                'permissions': [perm.permission for perm in role.permissions]
            }
            for role in roles
        ]
        return render_template('role-management.html', roles=roles_with_permissions)    

    @app.route('/user-management')
    #@roles_required('admin')
    def user_man():
        roles = Role.query.all()
        return render_template('user-management.html', roles=roles)

    @app.route('/user-profile')
    def user_profile():
        return render_template('user-profile.html')

    @app.route('/plantconfig')
    def plantconfig():
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path) as config_file:
            config = json.load(config_file)
        return render_template('plantconfig.html', config=config)

    @app.route('/processconfig')
    def processconfig():
        return render_template('processconfig.html')

    @app.route('/workflow-management')
    def workflow_management():
        return render_template('workflowmanagement.html')


    @app.route('/save-plant-config', methods=['POST'])
    def save_plant_config():
        new_config = request.json
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        
        # Ensure Kafkaserver and clusterid remain unchanged
        new_config['Kafkaserver'] = Kafkaserver
        new_config['clusterid'] = clusterid
        
        with open(config_path, 'w') as config_file:
            json.dump(new_config, config_file, indent=4)
        
        # Update the global config variable
        global enterprise, site, area, process_cell, unit
        enterprise = new_config['enterprise']
        site = new_config['site']
        area = new_config['area']
        process_cell = new_config['process_cell']
        unit = new_config['unit']
        
        return jsonify({'status': 'Configuration saved successfully'})


    


    @app.route('/get-role', methods=["POST"])
    def define_role():
        data = request.get_json()
        new_role = data.get('created_role')
        allowed_apps = data.get('role_apps')
        if not new_role or not allowed_apps:
            return jsonify({'message': 'Role name and at least one function required.'}), 400

        # Check if role already exists
        role = Role.query.filter_by(name=new_role).first()
        if role:
            # Update permissions: remove old permissions
            RolePermission.query.filter_by(role_id=role.id).delete()
        else:
            role = Role(name=new_role)
            db.session.add(role)
            db.session.flush()  # To get role.id

        # Add new permissions
        # allowed_apps can be a list or dict depending on your frontend
        if isinstance(allowed_apps, dict):
            perms = allowed_apps.keys()
        else:
            perms = allowed_apps

        for perm in perms:
            db.session.add(RolePermission(permission=perm, role=role))

        db.session.commit()
        return jsonify({'message': f'Role "{new_role}" saved in database.'})


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
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app
    



#if __name__ == '__main__':
    #threading.Thread(target=consume_messages, daemon=True).start()

    #app.run(debug=True, use_reloader=False,port=5001)