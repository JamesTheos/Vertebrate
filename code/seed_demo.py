"""
Demo seed for the Vertebrate demo video. Idempotent, safe to run repeatedly:

    docker compose exec vertebrate-app python seed_demo.py            # full: also resets demo passwords etc.
    python seed_demo.py --startup                                      # run.py on container start: only adds what is missing

--startup never changes existing rows: no password resets, subscriptions, roles or the QbD set
stay as they are, and the workflow is only released if no release state is stored yet.

- Role 'Admin-All' (every permission key) -> User_Admin
- Roles 'Production Manager' / 'Operator' + users prod.manager / operator
  (passwords from DEMO_PM_PW / DEMO_OP_PW; User_Admin only gets DEMO_ADMIN_PW if it does not exist yet)
- All app subscriptions -> subscribed
- Workflow FluVaccineISPE released (same Kafka message as /release-workflow)
- QbD set 'FluVaccine'
"""
import json
import os
import sys
from datetime import datetime

from confluent_kafka import Producer
from flask import Flask
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from audit_trail import log_audit
from models import db, User, Role, Permission, Subscriptions, DesignSpaceSet, WorkflowRelease

# Every permission key checked by @permission_required / @check_subscription
ALL_PERMISSION_KEYS = [
    "manufacturing-orders", "order-management", "workflow-overview",
    "batch", "process-instructions", "sampling", "equipment", "equipment-overview",
    "pid", "3d-view", "design-space-definition", "design-space-representation",
    "product-analytics", "process-qbd-analytics", "plant-configuration",
    "process-configuration", "workflow-management", "user-management",
    "role-management", "data-tree",
]

ROLES = {
    "Production Manager": ["manufacturing-orders", "order-management", "workflow-overview", "data-tree"],
    "Operator": ["workflow-overview", "process-instructions", "pid", "design-space-representation", "data-tree"],
}

USERS = [
    # (username, password, role names, reset password on every run)
    ("User_Admin", os.environ.get("DEMO_ADMIN_PW", "12345"), ["Admin-All"], False),
    ("prod.manager", os.environ.get("DEMO_PM_PW", "VertDemo-PM26"), ["Production Manager"], True),
    ("operator", os.environ.get("DEMO_OP_PW", "VertDemo-OP26"), ["Operator"], True),
]

# Not importing app.py on purpose: its blueprints start Kafka consumers in the app's consumer
# groups at import time, which would steal partitions from the running app until they time out.
with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    Kafkaserver = os.environ.get('KAFKASERVER', json.load(f)['Kafkaserver'])

WORKFLOW = "FluVaccineISPE"

QBD_SET_ID = "fluvaccine"
QBD_SET_NAME = "FluVaccine"
QBD_POINTS = [(340, 2), (340, 10), (360, 10), (360, 2)]  # (ispespeed, ispetemp)
QBD_MARGIN = 10


def js_str(x):
    """String(x) as JavaScript formats a number (342.0 -> '342', 2.4 -> '2.4')."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def build_qbd_set():
    """Same payload and inner-margin math as saveSetAPI() in design-space-definition.html."""
    values = [{"ispespeed": str(s), "ispetemp": str(t), "margin": str(QBD_MARGIN)} for s, t in QBD_POINTS]
    cx = sum(float(v["ispespeed"]) for v in values) / len(values)
    cy = sum(float(v["ispetemp"]) for v in values) / len(values)
    for v in values:
        margin = float(v["margin"])
        speed, temp = float(v["ispespeed"]), float(v["ispetemp"])
        x_diff = -speed + cx
        y_diff = -temp + cy
        v["innerMarginTemp"] = js_str(min(temp + (margin / 100) * abs(y_diff), cy) if y_diff > 0
                                      else max(temp - (margin / 100) * abs(y_diff), cy))
        v["innerMarginSpeed"] = js_str(min(speed + (margin / 100) * abs(x_diff), cx) if x_diff > 0
                                       else max(speed - (margin / 100) * abs(x_diff), cx))
    return {"id": QBD_SET_ID, "name": QBD_SET_NAME, "values": values}


STARTUP = '--startup' in sys.argv
changes = []  # what this run created/changed, for the audit entry


def get_or_create_role(name, perm_keys):
    role = Role.query.filter_by(name=name).first()
    if role and STARTUP:
        return role  # never touch an existing role on startup
    if not role:
        role = Role(name=name)
        db.session.add(role)
        changes.append(f'role {name}')
        print(f"Role '{name}' created.")
    for key in perm_keys:
        perm = Permission.query.filter_by(key=key).first()
        if not perm:
            perm = Permission(key=key)
            db.session.add(perm)
        if perm not in role.permissions:
            role.permissions.append(perm)
    db.session.flush()
    return role


def seed_roles():
    db.session.flush()
    all_keys = sorted(set(ALL_PERMISSION_KEYS) | {p.key for p in Permission.query.all()})
    get_or_create_role("Admin-All", all_keys)
    for name, keys in ROLES.items():
        get_or_create_role(name, keys)


def seed_users():
    for username, password, role_names, reset_pw in USERS:
        user = User.query.filter_by(username=username).first()
        if user and STARTUP:
            continue  # never touch an existing user on startup
        if not user:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            changes.append(f'user {username}')
            print(f"User '{username}' created.")
        elif reset_pw:
            user.password = generate_password_hash(password)
        for role_name in role_names:
            role = Role.query.filter_by(name=role_name).first()
            if role not in user.roles:
                user.roles.append(role)
    db.session.flush()


def seed_subscriptions():
    existing = {s.apps: s for s in Subscriptions.query.all()}
    for app_name in set(ALL_PERMISSION_KEYS) | set(existing):
        sub = existing.get(app_name)
        if sub is None:
            db.session.add(Subscriptions(apps=app_name, subscribed=True))
            changes.append(f'subscription {app_name}')
        elif not STARTUP:
            sub.subscribed = True
    db.session.flush()


def seed_qbd_set():
    data = build_qbd_set()
    design_set = db.session.get(DesignSpaceSet, QBD_SET_ID)
    if design_set is not None and STARTUP:
        return
    if design_set is None:
        design_set = DesignSpaceSet(id=QBD_SET_ID)
        db.session.add(design_set)
        changes.append(f'QbD set {QBD_SET_NAME}')
    design_set.name = QBD_SET_NAME
    design_set.data = data
    db.session.flush()


def release_workflow():
    """Release like consumeWorkflows.release_workflow(): Kafka message + stored release state.

    On startup only if no release state is stored yet (a deliberate Deactivate is kept)."""
    row = db.session.get(WorkflowRelease, WORKFLOW)
    if row is not None and STARTUP:
        return False
    changed_at = datetime.now()
    if row is None:
        row = WorkflowRelease(name=WORKFLOW)
        db.session.add(row)
    row.released = True
    row.changed_at = changed_at
    db.session.commit()
    changes.append(f'workflow {WORKFLOW} released')

    producer = Producer({"bootstrap.servers": Kafkaserver})
    producer.produce("workflows", key="FromWorkflowRelease", value=json.dumps({
        "workflow_name": WORKFLOW, "released": 1,
        "timestamp": changed_at.isoformat(),
    }).encode("utf-8"))
    remaining = producer.flush(10)
    if remaining:
        # the stored release state already makes the workflow show as released
        print(f"Warning: could not publish workflow release to Kafka at {Kafkaserver}")
    return True


def create_seed_app():
    """Minimal Flask app on the same database as app.create_app()."""
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not db_url:
        db_file = os.path.join(os.path.dirname(__file__), 'instance', 'UserManagement.db')
        db_url = 'sqlite:///' + db_file.replace('\\', '/')
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def main():
    app = create_seed_app()
    with app.app_context():
        if db.engine.dialect.name == 'postgresql':
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS audit_trail'))
            db.session.commit()
        db.create_all()
        seed_roles()
        seed_users()
        seed_subscriptions()
        seed_qbd_set()
        db.session.commit()
        print("Roles, users, subscriptions and QbD set seeded.")

        if release_workflow():
            print(f"Workflow '{WORKFLOW}' released.")

        if changes or not STARTUP:
            log_audit(action_type='CREATE', record_type='DEMO_SEED',
                      record_id='seed_demo --startup' if STARTUP else 'seed_demo',
                      change_reason='Demo seed: ' + (', '.join(changes) if changes else 'demo data refreshed'))
    print("Demo seed complete" + (f" (startup: {len(changes)} item(s) added)." if STARTUP else "."))


if __name__ == "__main__":
    main()
