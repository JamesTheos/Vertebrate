from flask import Flask, render_template, jsonify, request, abort, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
import sqlite3
from confluent_kafka import Consumer, Producer, KafkaError, OFFSET_BEGINNING
from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from datetime import datetime, timedelta
from product_analytics_app import product_analytics_app
from DesignSpaceApp import design_space_app
from process_qbd_analysis import process_qbd_analysis
from consumeWorkflows import consumeWorkflows, get_all_workflows_route as get_all_workflows
from colorsettings import colorsettings
from demo_consumer import tempConsumerChatbot
from auth import auth
from models import db, User, Role, RolePermission, Permission, Subscriptions
from functools import wraps
from timeout import register_timeout_hook
from subscriptions import check_subscription, subscriptions
from audit_trail import log_audit, log_field_change
from utils import permission_required
from aas_api import aas_bp
from werkzeug.security import generate_password_hash

Created_Roles = {}

import threading
import json
import os
import time
import sys

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

Kafkaserver = os.environ.get('KAFKASERVER', config.get('Kafkaserver', 'localhost:9092'))
IN_DOCKER = os.environ.get('IN_DOCKER', '').lower() in ['1', 'true', 'yes']
if isinstance(Kafkaserver, str) and Kafkaserver.startswith('kafka:') and not IN_DOCKER:
    print(f"Warning: KAFKASERVER='{Kafkaserver}' is a Docker-internal hostname. Using host address from config instead.")
    Kafkaserver = config.get('Kafkaserver', 'localhost:9092')

clusterid = os.environ.get('CLUSTERID', config.get('clusterid'))
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit = config['unit']

_DB_URL_ENV = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
if _DB_URL_ENV:
    cluster_id_temp = clusterid
else:
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'UserManagement.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM metainfo")
        Metainfo = cursor.fetchall()
        cluster_id_temp = Metainfo[0][0] if Metainfo and len(Metainfo[0]) > 0 else None
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
        print(f"Kafka not available (Unexpected): {e}")
        return False


kafka_cons_conf = {'bootstrap.servers': Kafkaserver, 'group.id': 'flask-consumer-group', 'auto.offset.reset': 'earliest'}
kafka_prod_conf = {'bootstrap.servers': Kafkaserver}

consumer = None
producer = None

if is_kafka_available(Kafkaserver):
    try:
        consumer = Consumer(kafka_cons_conf)
    except KafkaException as e:
        print(f"Kafka consumer could not be initialized: {e}")
    try:
        producer = Producer(kafka_prod_conf)
    except KafkaException as e:
        print(f"Kafka producer could not be initialized: {e}")
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
            print(f"Kafka error (Unexpected): {e}")
    else:
        print(f"Kafka producer unavailable, message for topic '{topic}' not sent: {value}")


data_store = {
    'ISPEScene1': [], 'ISPEScene2': [], 'ISPEMTemp': [], 'ISPESpeed': [],
    'ISPEPressure': [], 'ISPEAmbTemp': [], 'ISPEStartPhase1': [], 'ISPESelectPhase1': [],
    'manufacturing_orders': [], 'order-management': [], 'workflows': []
}


def create_topics_if_not_exist(bootstrap_servers, topics):
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    existing_topics = admin_client.list_topics(timeout=10).topics.keys()
    new_topics = [NewTopic(topic, num_partitions=1, replication_factor=1)
                  for topic in topics if topic not in existing_topics]
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
    print("App: Starting consume_messages thread", flush=True)

    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)

    consumer.subscribe(
        ['ISPEScene1', 'ISPEScene2', 'ISPEMTemp', 'ISPESpeed', 'ISPEPressure',
         'ISPEAmbTemp', 'ISPEStartPhase1', 'manufacturing_orders'],
        on_assign=temp_on_assign
    )
    while True:
        try:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(msg.error(), flush=True)
                    break
            topic = msg.topic()
            data = json.loads(msg.value().decode('utf-8'))
            timestamp = msg.timestamp()[1]
            if topic != 'manufacturing_orders':
                data_store[topic].append({'timestamp': timestamp, 'value': data['value']})
            else:
                existing = next(
                    (o for o in data_store[topic]
                     if o['orderNumber'] == data['orderNumber'] and o['product'] == data['product']),
                    None
                )
                if existing:
                    existing.update({'timestamp': timestamp, 'status': data['status']})
                else:
                    data_store[topic].append(data)
        except KafkaException as e:
            print("KafkaException in APP:Consume_Messages:", e, flush=True)
        except Exception as e:
            print("Exception in APP:Consume_Messages:", e, flush=True)


def create_app():
    app = Flask(__name__)

    db_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not db_url:
        instance_dir = os.path.join(os.path.dirname(__file__), 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        db_file = os.path.join(instance_dir, 'UserManagement.db')
        db_url = 'sqlite:///' + db_file.replace('\\', '/')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'your_secret_key'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)

    db.init_app(app)

    with app.app_context():
        from sqlalchemy import text
        try:
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS audit_trail'))
            db.session.commit()
        except Exception as e:
            print(f"Note: Could not create audit_trail schema (may already exist): {e}")
            db.session.rollback()

        db.create_all()

        try:
            if not User.query.filter_by(username='User_Admin').first():
                admin_role = Role.query.filter_by(name='Admin').first()
                if not admin_role:
                    admin_role = Role(name='Admin')
                    db.session.add(admin_role)
                    db.session.flush()
                admin_user = User(
                    username='User_Admin',
                    password=generate_password_hash('12345')
                )
                admin_user.roles.append(admin_role)
                db.session.add(admin_user)
                db.session.commit()
                print("Seeded default admin: User_Admin / 12345", flush=True)
        except Exception as e:
            print(f"Note: Could not seed admin user: {e}", flush=True)
            db.session.rollback()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login_page'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    register_timeout_hook(app)

    @app.context_processor
    def inject_appconfig():
        _appconfig_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
        try:
            with open(_appconfig_path) as _f:
                _appconfig = json.load(_f)
        except Exception:
            _appconfig = {
                "SidebarColor": "#02000e",
                "SidebarTextColor": "#ffffff",
                "BackgroundColor": "#f0f2f5",
                "TextColor": "#02000e",
                "Username": "Guest"
            }
        return dict(appconfig=_appconfig)

    # ── Blueprints ──────────────────────────────────────────────────────────
    app.register_blueprint(product_analytics_app)
    app.register_blueprint(design_space_app)
    app.register_blueprint(process_qbd_analysis)
    app.register_blueprint(consumeWorkflows)
    app.register_blueprint(colorsettings)
    app.register_blueprint(tempConsumerChatbot)
    app.register_blueprint(auth)
    app.register_blueprint(subscriptions)
    app.register_blueprint(aas_bp)

    # ── Pages ───────────────────────────────────────────────────────────────

    @app.route('/login')
    def login_page():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('login.html')

    @app.route('/login-error')
    def Login_error():
        return render_template('login-error.html')

    @app.route('/logout-message')
    def Logout_message():
        return render_template('logout-message.html')

    @app.route('/updated-user')
    def updated_user():
        return render_template('Updated-User.html')

    @app.route('/')
    @app.route('/index')
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
    @check_subscription('aas')
    @permission_required('aas_export')
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

    # ── User management ─────────────────────────────────────────────────────

    @app.route('/get-users', methods=['GET'])
    @login_required
    def get_users():
        users = User.query.all()
        user_list = [{'id': user.uid, 'username': user.username,
                      'role': [r.name for r in user.roles]} for user in users]
        return jsonify(user_list)

    @app.route('/add-user', methods=['POST'])
    @login_required
    def add_user():
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role_name = data.get('role')
        if not username or not password:
            return jsonify({'message': 'Username and password required.'}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({'message': 'Username already exists. Please choose a different one.'}), 400
        new_user = User(username=username, password=generate_password_hash(password))
        if role_name:
            role = Role.query.filter_by(name=role_name).first()
            if role:
                new_user.roles.append(role)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User added successfully.', 'user_id': new_user.uid})

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
                user.password = generate_password_hash(new_password)
            if new_role:
                role = Role.query.filter_by(name=new_role).first()
                if role:
                    user.roles = [role]
            db.session.commit()
            return jsonify({'message': 'User updated successfully.'})
        return jsonify({'message': 'User not found.'}), 404

    @app.route('/get-user-data', methods=['GET'])
    @login_required
    def get_user_data():
        return jsonify({'username': current_user.username,
                        'role': [r.name for r in current_user.roles]})

    @app.route('/get-user-role', methods=['GET'])
    @login_required
    def get_user_role():
        return jsonify({'role': [r.name for r in current_user.roles]})

    @app.route('/check-permission', methods=['GET'])
    @login_required
    def check_permission():
        permission_key = request.args.get('key')
        if not permission_key:
            return jsonify({'has_permission': False, 'message': 'No permission key provided'}), 400
        user_role_ids = [r.id for r in current_user.roles]
        if not user_role_ids:
            return jsonify({'has_permission': False, 'message': 'User has no roles'}), 404
        permission = Permission.query.filter_by(key=permission_key).first()
        if not permission:
            return jsonify({'has_permission': False,
                            'message': f'Permission "{permission_key}" not found'}), 404
        has_permission = RolePermission.query.filter(
            RolePermission.role_id.in_(user_role_ids),
            RolePermission.permission_id == permission.id
        ).first() is not None
        return jsonify({'has_permission': has_permission})

    # ── Subscriptions ────────────────────────────────────────────────────────

    @app.route('/subscription-management')
    @login_required
    def subscription_management():
        from models import Subscriptions
        _all_apps = [
            'manufacturing-orders', 'order-management', 'workflow-overview',
            'batch', 'process-instructions', 'sampling', 'equipment', 'pid',
            '3d-view', 'design-space-definition', 'design-space-representation',
            'product-analytics', 'process-qbd-analytics', 'plant-configuration',
            'process-configuration', 'workflow-management', 'user-management',
            'role-management',
        ]
        subscribed = {s.apps for s in Subscriptions.query.filter_by(subscribed=True).all()}
        subscription_status = {app: (app in subscribed) for app in _all_apps}
        return render_template('subscription-management.html', subscription_status=subscription_status)

    @app.route('/subscription-denied')
    def subscription_denied():
        return render_template('subscription-denied.html')

    # ── SCADA ────────────────────────────────────────────────────────────────

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
        send_to_kafka(data.get('topic'), {'value': data.get('value')})
        return jsonify({'status': 'Message sent'})

    @app.route('/start-phase1', methods=['POST'])
    @login_required
    def start_phase1():
        data = request.get_json()
        send_to_kafka(data.get('topic'), {'value': data.get('value')})
        return jsonify({'status': 'Message sent'})

    # ── Manufacturing orders ──────────────────────────────────────────────────

    @app.route('/manufacturing-orders')
    @login_required
    @check_subscription
    @permission_required('manufacturing_orders')
    def manufacturing_orders():
        return render_template('manufacturing-orders.html')

    @app.route('/submit-order', methods=['POST'])
    @login_required
    def submit_order():
        """Create a new manufacturing order and write a CREATE audit entry."""
        data = request.get_json()
        order_number = data.get('orderNumber')
        product = data.get('product')
        lot_number = data.get('lotNumber')
        workflow = data.get('workflow')

        if not all([order_number, product, lot_number, workflow]):
            return jsonify({'message': 'Missing required fields'}), 400

        order = {
            'orderNumber': order_number,
            'product': product,
            'lotNumber': lot_number,
            'workflow': workflow,
            'status': 'Created',
            'timestamp': datetime.utcnow().isoformat()
        }
        data_store['manufacturing_orders'].append(order)
        send_to_kafka('manufacturing_orders', order)

        log_audit(
            action_type='CREATE',
            record_type='ORDER',
            record_id=order_number,
            change_reason=f'Order {order_number} submitted'
        )
        return jsonify({'status': 'Order submitted', 'orderNumber': order_number})

    @app.route('/order-management', methods=['GET'])
    @login_required
    @check_subscription
    @permission_required('order_management')
    def order_management_page():
        """Render the order-management UI."""
        return render_template('order-management.html')

    @app.route('/order-management', methods=['POST'])
    @login_required
    def order_management_action():
        """
        Handle order lifecycle actions: release | abort.

        Expected JSON body:
            { "action": "release" | "abort",
              "order_id": "<orderNumber>",
              "workflowName": "<name>" }
        """
        data = request.get_json()
        action = data.get('action')
        order_id = data.get('order_id')
        workflow_name = data.get('workflowName', '')

        if not action or not order_id:
            return jsonify({'message': 'action and order_id are required'}), 400

        # Find the order in data_store
        order = next(
            (o for o in data_store['manufacturing_orders']
             if o.get('orderNumber') == order_id),
            None
        )
        if order is None:
            return jsonify({'message': f'Order {order_id} not found'}), 404

        status_map = {'release': 'Released', 'abort': 'Aborted'}
        new_status = status_map.get(action)
        if new_status is None:
            return jsonify({'message': f'Unknown action "{action}"'}), 400

        old_status = order.get('status', 'Created')
        order['status'] = new_status

        # Send status update to Kafka (no-op when Kafka is unavailable)
        send_to_kafka('manufacturing_orders', order)

        # 21 CFR Part 11 — audit the status field change
        log_field_change(
            action_type='UPDATE',
            record_type='ORDER',
            record_id=order_id,
            field_name='status',
            old_value=old_status,
            new_value=new_status,
            change_reason=f'Order {action}d via order-management'
        )

        return jsonify({
            'status': 'ok',
            'orderNumber': order_id,
            'newStatus': new_status
        })

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

    # ── Settings ─────────────────────────────────────────────────────────────

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
        from models import Role, Subscriptions
        roles = Role.query.all()
        subscribed_apps = [s.apps for s in Subscriptions.query.filter_by(subscribed=True).all()]
        return render_template('role-management.html', roles=roles, subscribed_apps=subscribed_apps)

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
        _config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(_config_path) as f:
            return jsonify(json.load(f))

    @app.route('/save-plant-config', methods=['POST'])
    @login_required
    def save_plant_config():
        new_config = request.get_json()
        _config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(_config_path) as f:
            old_config = json.load(f)
        # Merge into the existing config so keys the caller didn't submit
        # (Kafkaserver, clusterid, assets, …) are preserved.  Overwriting the
        # whole file dropped them and crashed the app on next startup.
        merged_config = {**old_config, **new_config}
        with open(_config_path, 'w') as f:
            json.dump(merged_config, f, indent=4)
        for field in [k for k in new_config if new_config.get(k) != old_config.get(k)]:
            log_field_change(
                action_type='UPDATE',
                record_type='PLANT_CONFIG',
                record_id='plant_config',
                field_name=field,
                old_value=old_config.get(field),
                new_value=new_config.get(field),
                change_reason='Plant configuration updated'
            )
        return jsonify({'status': 'Configuration saved successfully'})

    # ── Role management ──────────────────────────────────────────────────────

    @app.route('/get-role', methods=['POST'], endpoint='define_role')
    @login_required
    def define_role():
        data = request.get_json()
        new_role = data.get('created_role')
        allowed_apps = data.get('role_apps')

        if not new_role or not allowed_apps:
            return jsonify({'message': 'Role name and at least one function required.'}), 400

        perm_keys = list(allowed_apps.keys()) if isinstance(allowed_apps, dict) else list(allowed_apps)

        existing_role = Role.query.filter_by(name=new_role).first()
        is_existing = existing_role is not None

        if is_existing:
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
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

        db.session.commit()

        log_audit(
            action_type='UPDATE' if is_existing else 'CREATE',
            record_type='ROLE',
            record_id=str(role.id),
            change_reason=f'Role "{new_role}" {"updated" if is_existing else "created"} with permissions: {perm_keys}'
        )
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

        return jsonify({'message': f'Role "{new_role}" saved in database.',
                        'role_id': role.id, 'permissions': perm_keys})

    @app.route('/update-role', methods=['POST'], endpoint='update_role')
    @login_required
    def update_role():
        data = request.get_json()
        role_name = data.get('role_name')
        updated_apps = data.get('updated_role_apps')

        if not role_name or not updated_apps:
            return jsonify({'message': 'Role name and at least one function required.'}), 400

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return jsonify({'message': 'Role not found'}), 404

        perm_keys = list(updated_apps.keys()) if isinstance(updated_apps, dict) else list(updated_apps)

        old_perm_keys = [
            row[0] for row in
            db.session.query(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role.id)
            .all()
        ]
        RolePermission.query.filter_by(role_id=role.id).delete()
        db.session.flush()

        for key in perm_keys:
            perm = Permission.query.filter_by(key=key).first()
            if not perm:
                perm = Permission(key=key)
                db.session.add(perm)
                db.session.flush()
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

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

    # ── Login / username save ────────────────────────────────────────────────

    @app.route('/api/login', methods=['POST'])
    def login():
        username = request.json.get('username')
        _config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
        with open(_config_path) as f:
            _cfg = json.load(f)
        _cfg['Username'] = username
        with open(_config_path, 'w') as f:
            json.dump(_cfg, f, indent=4)
        return jsonify({'status': 'Username saved successfully'})

    return app
