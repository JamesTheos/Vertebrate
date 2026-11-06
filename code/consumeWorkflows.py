from flask import Blueprint, jsonify, request
from confluent_kafka import KafkaError, Consumer, Producer, OFFSET_BEGINNING
from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient
import json
import logging
import threading
from datetime import datetime
import os
from audit_trail import log_audit, log_field_change
from models import db, WorkflowRelease

# Load config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

Kafkaserver = os.environ.get('KAFKASERVER', config['Kafkaserver'])
clusterid = config['clusterid']
enterprise = config['enterprise']
site = config['site']
area = config['area']
process_cell = config['process_cell']
unit = config['unit']

all_workflows = {}
released_workflows = {}

consumeWorkflows = Blueprint('consumerWorkflows', __name__)


# ── Release state ────────────────────────────────────────────────────────────
# Kafka 'workflows' events fill all_workflows; the workflow_releases table keeps the state across
# restarts. For each workflow the newer of the two wins.

def persist_release(workflow_name, released, changed_at=None):
    """Upsert the release state in the database (needs an app context)."""
    try:
        row = db.session.get(WorkflowRelease, workflow_name)
        if row is None:
            row = WorkflowRelease(name=workflow_name)
            db.session.add(row)
        row.released = bool(released)
        row.changed_at = changed_at or datetime.now()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Could not persist release state of {workflow_name}: {e}")


def release_state():
    """{workflow_name: {'released': 0|1, 'timestamp': datetime}} from Kafka events and the database."""
    state = {name: dict(info) for name, info in all_workflows.items()}
    try:
        rows = WorkflowRelease.query.all()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Could not read release state: {e}")
        rows = []
    for row in rows:
        known = state.get(row.name)
        if known is None or known['timestamp'] <= row.changed_at:
            state[row.name] = {'released': 1 if row.released else 0, 'timestamp': row.changed_at}
    return state


# ── Kafka helpers ────────────────────────────────────────────────────────────

def _is_kafka_available(bootstrap_servers):
    try:
        AdminClient({'bootstrap.servers': bootstrap_servers}).list_topics(timeout=3)
        return True
    except Exception:
        return False


kafka_workflows_conf = {
    'bootstrap.servers': Kafkaserver,
    'group.id': 'manufacturing_orders-workflows-released',
    'auto.offset.reset': 'earliest',
    # reads from the beginning on every start anyway; a short session lets a restarted app take over
    # the partitions after ~6 s instead of waiting 45 s for the old, uncleanly closed member
    'session.timeout.ms': 6000,
    'heartbeat.interval.ms': 2000,
}
kafka_produce_conf = {'bootstrap.servers': Kafkaserver}

workflowsConsumer = None
producer = None

_kafka_disabled = os.environ.get('DISABLE_KAFKA', '0') == '1'

if _kafka_disabled:
    print("Kafka disabled via DISABLE_KAFKA env var — consumer/producer not started.")
elif _is_kafka_available(Kafkaserver):
    try:
        workflowsConsumer = Consumer(kafka_workflows_conf)
    except KafkaException as e:
        print(f"Workflow consumer could not be initialized: {e}")
    try:
        producer = Producer(kafka_produce_conf)
    except KafkaException as e:
        print(f"Workflow producer could not be initialized: {e}")
else:
    print("Kafka unavailable — workflow consumer/producer not started.")

def send_to_kafka(topic, value):
    if producer is not None:
        try:
            producer.produce(topic, key="FromWorkflowRelease",
                             value=json.dumps(value).encode('utf-8'))
            producer.flush()
        except KafkaException as e:
            logging.error(f"KafkaException while producing workflow event: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while producing workflow event: {e}")
    else:
        print(f"Kafka producer unavailable, message for topic '{topic}' not sent.")


def get_all_topics(bootstrap_servers):
    try:
        admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
        cluster_metadata = admin_client.list_topics(timeout=10)
        return sorted([t for t in cluster_metadata.topics.keys()
                       if t != '__consumer_offsets'])
    except KafkaException as e:
        print(f"Error retrieving topics (KafkaException): {e}")
        return []
    except Exception as e:
        print(f"Error retrieving topics (Unexpected): {e}")
        return []


# ── Routes ───────────────────────────────────────────────────────────────────

@consumeWorkflows.route('/save-workflow', methods=['POST'])
def save_workflow():
    data = request.json
    workflow_name = data.get('workflowName')
    options = data.get('options', [])

    if not workflow_name:
        return jsonify({'success': False, 'message': 'Workflow name is required.'}), 400
    if not options:
        return jsonify({'success': False, 'message': 'No options provided for the workflow.'}), 400

    save_path = os.path.join(os.path.dirname(__file__), 'workflows')
    os.makedirs(save_path, exist_ok=True)

    file_path = os.path.join(save_path, f'{workflow_name}.json')
    already_exists = os.path.exists(file_path)

    workflow_data = {"workflowName": workflow_name, "options": options}
    with open(file_path, 'w') as json_file:
        json.dump(workflow_data, json_file, indent=4)

    action_type = 'UPDATE' if already_exists else 'CREATE'
    log_audit(
        action_type=action_type,
        record_type='WORKFLOW',
        record_id=workflow_name,
        change_reason=f'Workflow "{workflow_name}" {"updated" if already_exists else "created"} with {len(options)} steps'
    )

    return jsonify({'success': True, 'message': 'Workflow saved successfully.'})


@consumeWorkflows.route('/get-workflows', methods=['GET'])
def get_workflows():
    save_path = os.path.join(os.path.dirname(__file__), 'workflows')
    if not os.path.exists(save_path):
        return jsonify({'workflows': []})
    workflows = [f.split('.')[0] for f in os.listdir(save_path) if f.endswith('.json')]
    return jsonify({'workflows': workflows})


@consumeWorkflows.route('/get-workflow/<workflow_name>', methods=['GET'])
def get_workflow(workflow_name):
    file_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
    if not os.path.exists(file_path):
        return jsonify({'error': 'Workflow not found'}), 404
    with open(file_path, 'r') as json_file:
        workflows = json.load(json_file)
    return jsonify({'workflows': workflows, 'released_workflows': release_state()})


@consumeWorkflows.route('/delete-workflow/<workflow_name>', methods=['POST'])
def delete_workflow(workflow_name):
    file_path = os.path.join(os.path.dirname(__file__), 'workflows', f'{workflow_name}.json')
    if not os.path.exists(file_path):
        return jsonify({'error': 'Workflow not found'}), 404

    os.remove(file_path)

    log_audit(
        action_type='DELETE',
        record_type='WORKFLOW',
        record_id=workflow_name,
        change_reason=f'Workflow "{workflow_name}" deleted'
    )

    return jsonify({'success': True, 'message': 'Workflow deleted successfully.'})


@consumeWorkflows.route('/deactivate-workflow/<workflow_name>', methods=['POST'])
def deactivate_workflow(workflow_name):
    # Derive real current state (Kafka + database) before changing it
    current_info = release_state().get(workflow_name)
    if current_info is not None:
        old_status = 'Released' if current_info.get('released') == 1 else 'Deactivated'
    else:
        old_status = 'Unknown'  # workflow not yet seen via Kafka

    changed_at = datetime.now()
    send_to_kafka('workflows', {
        'workflow_name': workflow_name, 'released': 0,
        'timestamp': changed_at.isoformat()
    })
    persist_release(workflow_name, 0, changed_at)

    log_field_change(
        action_type='UPDATE',
        record_type='WORKFLOW',
        record_id=workflow_name,
        field_name='status',
        old_value=old_status,
        new_value='Deactivated',
        change_reason=f'Workflow "{workflow_name}" deactivated'
    )

    return jsonify({'success': True, 'message': 'Workflow deactivated successfully.'})


@consumeWorkflows.route('/release-workflow/<workflow_name>', methods=['POST'])
def release_workflow(workflow_name):
    # Derive real current state (Kafka + database) before changing it
    current_info = release_state().get(workflow_name)
    if current_info is not None:
        old_status = 'Released' if current_info.get('released') == 1 else 'Deactivated'
    else:
        old_status = 'Unknown'  # workflow not yet seen via Kafka

    changed_at = datetime.now()
    send_to_kafka('workflows', {
        'workflow_name': workflow_name, 'released': 1,
        'timestamp': changed_at.isoformat()
    })
    persist_release(workflow_name, 1, changed_at)

    log_field_change(
        action_type='UPDATE',
        record_type='WORKFLOW',
        record_id=workflow_name,
        field_name='status',
        old_value=old_status,
        new_value='Released',
        change_reason=f'Workflow "{workflow_name}" released for production use'
    )

    return jsonify({'success': True, 'message': 'Workflow released successfully.'})


@consumeWorkflows.route('/api/get-all-topics', methods=['GET'])
def get_topics():
    topics = get_all_topics(Kafkaserver)
    return jsonify({'topics': topics})


@consumeWorkflows.route('/get-released-workflows', methods=['GET'])
def get_released_workflows():
    return jsonify({'workflows': [name for name, info in release_state().items() if info['released'] == 1]})


@consumeWorkflows.route('/get-all-workflows', methods=['GET'])
def get_all_workflows_route():
    return jsonify([
        {'workflow_name': name, 'state': 'Released' if info['released'] == 1 else 'Deactivated'}
        for name, info in release_state().items()
    ])


# ── Background consumer thread ───────────────────────────────────────────────

def consume_workflows():
    if workflowsConsumer is None:
        print("Workflow consumer unavailable, thread exiting.", flush=True)
        return

    print("Manufacturing Orders: Starting consume_workflows thread\n", flush=True)

    def temp_on_assign(consumer, partitions):
        for partition in partitions:
            partition.offset = OFFSET_BEGINNING
        consumer.assign(partitions)

    workflowsConsumer.subscribe(['workflows'], on_assign=temp_on_assign)

    try:
        while True:
            msgs = workflowsConsumer.consume(5, timeout=1.0)
            if not msgs:
                continue
            for msg in msgs:
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logging.error(f"Workflow consumer error: {msg.error()}")
                    continue
                workflow = json.loads(msg.value().decode('utf-8'))
                workflow_name = workflow['workflow_name']
                state = workflow['released']
                timestamp = datetime.fromisoformat(workflow['timestamp'])

                if state == 1:
                    all_workflows[workflow_name] = {'timestamp': timestamp, 'released': state}
                    released_workflows[workflow_name] = {'timestamp': timestamp}
                    print(f"Workflow {workflow_name} released at {timestamp}", flush=True)
                elif state == 0 and workflow_name in released_workflows:
                    if released_workflows[workflow_name]['timestamp'] < timestamp:
                        all_workflows[workflow_name] = {'timestamp': timestamp, 'released': state}
                        del released_workflows[workflow_name]
                        print(f"Workflow {workflow_name} deactivated", flush=True)

    except KafkaException as e:
        print(f"KafkaException in consume_workflows: {e}", flush=True)
    except Exception as e:
        print(f"Exception in consume_workflows: {e}", flush=True)
    finally:
        workflowsConsumer.close()


if not _kafka_disabled:
    threading.Thread(target=consume_workflows, daemon=True).start()