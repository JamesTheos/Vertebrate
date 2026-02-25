"""
test_consumeWorkflows_audit.py
Integration tests for consumeWorkflows.py audit logging — 21 CFR Part 11 compliance
Run: docker compose exec vertebrate-app sh -c "cd /app/code && python -m pytest tests/test_consumeWorkflows_audit.py -v --noconftest --tb=line --timeout=10 2>/dev/null"
"""
import os
import json
import pytest
from unittest.mock import patch

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


# ─── Save Workflow ─────────────────────────────────────────────────────────────

class TestSaveWorkflowAudit:

    def _unique_name(self, base):
        import time
        return f"{base}_{int(time.time())}"

    def _cleanup(self, *names):
        """Remove test workflow files if they exist."""
        for name in names:
            path = os.path.join(os.path.dirname(__file__), '..', 'workflows', f'{name}.json')
            if os.path.exists(path):
                os.remove(path)

    def test_save_new_workflow_creates_create_entry(self, app, client):
        from models import AuditLog
        name = self._unique_name('pytest_wf_create')
        self._cleanup(name)

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='CREATE', record_type='WORKFLOW').count()

        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': name,
                        'options': [{'step': 1, 'label': 'Start', 'actions': []}]
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='CREATE', record_type='WORKFLOW').count()
        assert after > before, "CREATE audit entry missing for new workflow"

    def test_save_existing_workflow_creates_update_entry(self, app, client):
        from models import AuditLog
        name = self._unique_name('pytest_wf_update')
        self._cleanup(name)

        # Create first
        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': name,
                        'options': [{'step': 1, 'label': 'Start', 'actions': []}]
                    }),
                    content_type='application/json')

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='WORKFLOW').count()

        # Save again — should be UPDATE
        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': name,
                        'options': [{'step': 1, 'label': 'Modified', 'actions': []}]
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='WORKFLOW').count()
        assert after > before, "UPDATE audit entry missing for overwritten workflow"

    def test_save_workflow_logs_name_as_record_id(self, app, client):
        name = self._unique_name('pytest_wf_recordid')
        self._cleanup(name)

        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': name,
                        'options': [{'step': 1, 'label': 'Start', 'actions': []}]
                    }),
                    content_type='application/json')

        entry = get_latest_entry(app, 'CREATE', 'WORKFLOW', record_id=name)
        assert entry is not None,        f"No entry found for {name}"
        assert entry.record_id == name
        assert entry.checksum is not None



# ─── Release / Deactivate Workflow ────────────────────────────────────────────

class TestReleaseDeactivateAudit:

    @patch('consumeWorkflows.send_to_kafka')
    def test_release_workflow_creates_update_entry(self, mock_kafka, app, client):
        from models import AuditLog
        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': 'pytest_wf_release',
                        'options': [{'step': 1, 'label': 'Start', 'actions': []}]
                    }),
                    content_type='application/json')

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='WORKFLOW').count()

        resp = client.post('/release-workflow/pytest_wf_release')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='WORKFLOW').count()
        assert resp.status_code == 200, f"Route returned {resp.status_code}"
        assert after > before, "UPDATE audit entry missing for workflow release"

    @patch('consumeWorkflows.send_to_kafka')
    def test_release_workflow_logs_status_change(self, mock_kafka, app, client):
        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': 'pytest_wf_rel_status',
                        'options': [{'step': 1, 'label': 'Start', 'actions': []}]
                    }),
                    content_type='application/json')

        client.post('/release-workflow/pytest_wf_rel_status')

        entry = get_latest_entry(app, 'UPDATE', 'WORKFLOW',
                                 record_id='pytest_wf_rel_status', field_name='status')
        assert entry is not None,           "status field entry missing for release"
        assert entry.new_value == 'Released'
        assert entry.checksum is not None

    @patch('consumeWorkflows.send_to_kafka')
    def test_deactivate_workflow_creates_update_entry(self, mock_kafka, app, client):
        from models import AuditLog
        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': 'pytest_wf_deactivate',
                        'options': [{'step': 1, 'label': 'Start', 'actions': []}]
                    }),
                    content_type='application/json')

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='WORKFLOW').count()

        resp = client.post('/deactivate-workflow/pytest_wf_deactivate')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='WORKFLOW').count()
        assert resp.status_code == 200, f"Route returned {resp.status_code}"
        assert after > before, "UPDATE audit entry missing for workflow deactivation"


# ─── Delete Workflow ───────────────────────────────────────────────────────────

class TestDeleteWorkflowAudit:

    def test_delete_workflow_creates_delete_entry(self, app, client):
        from models import AuditLog
        client.post('/save-workflow',
                    data=json.dumps({
                        'workflowName': 'pytest_wf_delete',
                        'options': [{'step': 1, 'label': 'Start', 'actions': []}]
                    }),
                    content_type='application/json')

        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='DELETE', record_type='WORKFLOW').count()

        resp = client.post('/delete-workflow/pytest_wf_delete')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='DELETE', record_type='WORKFLOW').count()
        assert resp.status_code == 200, f"Route returned {resp.status_code}"
        assert after > before, "DELETE audit entry missing for workflow deletion"

    def test_delete_nonexistent_workflow_no_audit_entry(self, app, client):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='DELETE', record_type='WORKFLOW').count()

        client.post('/delete-workflow/nonexistent_workflow_xyz')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='DELETE', record_type='WORKFLOW').count()
        assert after == before, "DELETE entry must not be written for nonexistent workflow"
