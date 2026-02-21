"""
test_colorsettings_audit.py
Integration tests for colorsettings.py audit logging — 21 CFR Part 11 compliance
Run: docker compose exec vertebrate-app sh -c "cd /app/code && python -m pytest tests/test_colorsettings_audit.py -v --noconftest"
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


def get_latest_entry(app, action_type, record_type, field_name=None):
    from models import AuditLog
    with app.app_context():
        q = AuditLog.query.filter_by(action_type=action_type, record_type=record_type)
        if field_name:
            q = q.filter_by(field_name=field_name)
        return q.order_by(AuditLog.id.desc()).first()


class TestSaveColorsAudit:

    def test_save_colors_creates_update_entries(self, app, client):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='SETTING').count()

        client.post('/api/colors',
                    data=json.dumps({
                        'textColor': '#ffffff',
                        'bgColor': '#000000',
                        'sbTColor': '#aaaaaa',
                        'sbColor': '#bbbbbb'
                    }),
                    content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='SETTING').count()
        assert after > before, "No UPDATE audit entries created for save_colors"

    def test_save_colors_logs_old_and_new_values(self, app, client):
        # Set a known color first
        client.post('/api/colors',
                    data=json.dumps({
                        'textColor': '#111111',
                        'bgColor': '#222222',
                        'sbTColor': '#333333',
                        'sbColor': '#444444'
                    }),
                    content_type='application/json')

        # Now change it
        client.post('/api/colors',
                    data=json.dumps({
                        'textColor': '#999999',
                        'bgColor': '#888888',
                        'sbTColor': '#777777',
                        'sbColor': '#666666'
                    }),
                    content_type='application/json')

        entry = get_latest_entry(app, 'UPDATE', 'SETTING', field_name='TextColor')
        assert entry is not None,            "TextColor UPDATE entry missing"
        assert entry.old_value == '#111111', f"Expected old #111111, got {entry.old_value}"
        assert entry.new_value == '#999999', f"Expected new #999999, got {entry.new_value}"
        assert entry.change_reason is not None

    def test_save_colors_entries_have_checksums(self, app, client):
        client.post('/api/colors',
                    data=json.dumps({
                        'textColor': '#ffffff',
                        'bgColor': '#ffffff',
                        'sbTColor': '#ffffff',
                        'sbColor': '#ffffff'
                    }),
                    content_type='application/json')

        entry = get_latest_entry(app, 'UPDATE', 'SETTING', field_name='TextColor')
        assert entry is not None
        assert entry.checksum is not None, "Checksum must not be NULL"


class TestResetColorsAudit:

    def test_reset_colors_creates_update_entries(self, app, client):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='SETTING').count()

        client.post('/api/colors/reset', content_type='application/json')

        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='UPDATE', record_type='SETTING').count()
        assert after > before, "No UPDATE audit entries created for reset_colors"

    def test_reset_colors_change_reason_mentions_reset(self, app, client):
        client.post('/api/colors/reset', content_type='application/json')
        entry = get_latest_entry(app, 'UPDATE', 'SETTING', field_name='TextColor')
        assert entry is not None
        assert 'reset' in entry.change_reason.lower(), \
            f"change_reason should mention 'reset', got: {entry.change_reason}"


class TestGetColorsNoAudit:

    def test_get_colors_does_not_create_audit_entry(self, app, client):
        """Read-only GET must never write audit rows."""
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(record_type='SETTING').count()

        client.get('/api/colors')

        with app.app_context():
            after = AuditLog.query.filter_by(record_type='SETTING').count()
        assert after == before, "GET /api/colors must not write audit entries"
