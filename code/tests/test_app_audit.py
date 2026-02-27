"""
test_app_audit.py
Integration tests for app.py audit logging — 21 CFR Part 11 compliance
Run: docker compose exec vertebrate-app sh -c "cd /app/code && python -m pytest tests/test_app_audit.py -v --noconftest --tb=line 2>/dev/null"
"""
import os
import json
import pytest

os.environ.setdefault('DISABLE_KAFKA', '1')


@pytest.fixture(scope='module')
def app():
    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.app_context():
        yield flask_app


@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


def get_latest_entry(app, action_type, record_type, record_id=None, field_name=None):
    from models import AuditLog
    with app.app_context():
        q = AuditLog.query.filter_by(action_type=action_type, record_type=record_type)
        if record_id:
            q = q.filter_by(record_id=str(record_id))
        if field_name:
            q = q.filter_by(field_name=field_name)
        return q.order_by(AuditLog.id.desc()).first()


def ensure_order_management_access(app, client):
    """Grant User_Admin full access to order-management and log in."""
    from models import Subscriptions, User, Role, RolePermission, Permission, db
    with app.app_context():
        # Enable subscription
        sub = Subscriptions.query.filter_by(apps='order-management').first()
        if sub:
            sub.subscribed = True
        else:
            db.session.add(Subscriptions(apps='order-management', subscribed=True))

        # Ensure permission exists
        perm = Permission.query.filter_by(key='order-management').first()
        if not perm:
            perm = Permission(key='order-management')
            db.session.add(perm)
            db.session.flush()

        # Get or create a role and assign to User_Admin
        user = User.query.filter_by(username='User_Admin').first()
        if user:
            if not user.roles:
                role = Role.query.filter_by(name='admin').first()
                if not role:
                    role = Role(name='admin')
                    db.session.add(role)
                    db.session.flush()
                from models import UserRoles
                db.session.add(UserRoles(user_id=user.uid, role_id=role.id))
                db.session.flush()
            else:
                role = user.roles[0]

            existing = RolePermission.query.filter_by(
                role_id=role.id, permission_id=perm.id).first()
            if not existing:
                db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

        db.session.commit()

    # Login
    resp = client.post('/loginUser',
                data=json.dumps({'username': 'User_Admin', 'password': '12345'}),
                content_type='application/json')
    print(f"\nLogin status: {resp.status_code}")


# ─── Submit Order ─────────────────────────────────────────────────────────────

class TestSubmitOrderAudit:

    def test_submit_order_creates_create_entry(self, app, client):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='CREATE', record_type='ORDER').count()

        client.post('/submit-order',
                    data=json.dumps({
                        'orderNumber': 'TEST-ORD-001',
                        'product': 'TestProduct',
                        'lotNumber': 'LOT-001',
                        'workflow': 'test_workflow'
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='CREATE', record_type='ORDER').count()
        assert after > before, "CREATE audit entry missing for submit-order"

    def test_submit_order_logs_order_number_as_record_id(self, app, client):
        client.post('/submit-order',
                    data=json.dumps({
                        'orderNumber': 'TEST-ORD-002',
                        'product': 'TestProduct',
                        'lotNumber': 'LOT-002',
                        'workflow': 'test_workflow'
                    }),
                    content_type='application/json')

        entry = get_latest_entry(app, 'CREATE', 'ORDER', record_id='TEST-ORD-002')
        assert entry is not None, "CREATE entry missing for TEST-ORD-002"
        assert entry.record_id == 'TEST-ORD-002'
        assert entry.checksum is not None

    def test_submit_order_missing_fields_no_audit_entry(self, app, client):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='CREATE', record_type='ORDER').count()

        client.post('/submit-order',
                    data=json.dumps({'orderNumber': 'INCOMPLETE'}),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='CREATE', record_type='ORDER').count()
        assert after == before, "Audit entry must not be written for rejected order"


# ─── Order Management ─────────────────────────────────────────────────────────

class TestOrderManagementAudit:

    def _seed_order(self, app, order_number, status='Created'):
        import app as app_module
        app_module.data_store['manufacturing_orders'].append({
            'orderNumber': order_number,
            'product': 'TestProduct',
            'lotNumber': 'LOT-001',
            'workflow': 'test_workflow',
            'status': status,
            'timestamp': '2026-01-01T00:00:00'
        })

    def test_order_release_creates_update_entry(self, app, client):
        from models import AuditLog
        ensure_order_management_access(app, client)
        self._seed_order(app, 'TEST-ORD-REL-001')

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='ORDER').count()

        resp = client.post('/order-management',
                    data=json.dumps({
                        'action': 'release',
                        'order_id': 'TEST-ORD-REL-001',
                        'workflowName': 'test_workflow'
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='ORDER').count()
        assert resp.status_code == 200, f"Route returned {resp.status_code}"
        assert after > before, "UPDATE audit entry missing for order release"

    def test_order_abort_creates_update_entry(self, app, client):
        from models import AuditLog
        ensure_order_management_access(app, client)
        self._seed_order(app, 'TEST-ORD-ABT-001')

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='ORDER').count()

        resp = client.post('/order-management',
                    data=json.dumps({
                        'action': 'abort',
                        'order_id': 'TEST-ORD-ABT-001',
                        'workflowName': 'test_workflow'
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='ORDER').count()
        assert resp.status_code == 200, f"Route returned {resp.status_code}"
        assert after > before, "UPDATE audit entry missing for order abort"

    def test_order_status_change_logged_as_field_change(self, app, client):
        ensure_order_management_access(app, client)
        self._seed_order(app, 'TEST-ORD-STS-001')

        resp = client.post('/order-management',
                    data=json.dumps({
                        'action': 'release',
                        'order_id': 'TEST-ORD-STS-001',
                        'workflowName': 'test_workflow'
                    }),
                    content_type='application/json')

        assert resp.status_code == 200, f"Route returned {resp.status_code}"
        entry = get_latest_entry(app, 'UPDATE', 'ORDER',
                                 record_id='TEST-ORD-STS-001', field_name='status')
        assert entry is not None,             "status field change entry missing"
        assert entry.old_value == 'Created',  f"Expected old 'Created', got {entry.old_value}"
        assert entry.new_value == 'Released', f"Expected new 'Released', got {entry.new_value}"
        assert entry.checksum is not None


# ─── Plant Config ─────────────────────────────────────────────────────────────

class TestPlantConfigAudit:

    def test_save_plant_config_creates_update_entries(self, app, client):
        import time
        from models import AuditLog
        unique_site = f'Site-pytest-{int(time.time())}'

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='SETTING').count()

        client.post('/save-plant-config',
                    data=json.dumps({
                        'enterprise': 'TestCorp',
                        'site': unique_site,
                        'area': 'Area-1',
                        'process_cell': 'Cell-1',
                        'unit': 'Unit-1'
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='SETTING').count()
        assert after > before, "UPDATE audit entries missing for save-plant-config"


# ─── Role Management ──────────────────────────────────────────────────────────

class TestRoleManagementAudit:

    def _cleanup_role(self, app, role_name):
        from models import db, Role, RolePermission, AuditLog
        with app.app_context():
            role = Role.query.filter_by(name=role_name).first()
            if role:
                RolePermission.query.filter_by(role_id=role.id).delete()
                AuditLog.query.filter_by(record_type='ROLE', record_id=str(role.id)).delete()
                db.session.delete(role)
                db.session.commit()

    def test_create_role_creates_audit_entry(self, app, client):
        self._cleanup_role(app, 'pytest_test_role')   # ← ensure clean state
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='CREATE', record_type='ROLE').count()

        client.post('/get-role',
                    data=json.dumps({
                        'created_role': 'pytest_test_role',
                        'role_apps': ['order-management', 'batch']
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='CREATE', record_type='ROLE').count()
        assert after > before, "CREATE audit entry missing for new role"
        self._cleanup_role(app, 'pytest_test_role')   # ← clean up after

    def test_overwrite_existing_role_logs_update(self, app, client):
        # First create it so overwrite is genuinely an UPDATE
        self._cleanup_role(app, 'pytest_existing_role')
        client.post('/get-role',
                    data=json.dumps({
                        'created_role': 'pytest_existing_role',
                        'role_apps': ['batch']
                    }),
                    content_type='application/json')

        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='ROLE').count()

        client.post('/get-role',
                    data=json.dumps({
                        'created_role': 'pytest_existing_role',
                        'role_apps': ['batch', 'scada']
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='ROLE').count()
        assert after > before, "UPDATE audit entry missing for overwrite"
        self._cleanup_role(app, 'pytest_existing_role')
