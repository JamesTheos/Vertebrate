"""
audit_dashboard.py
Flask Blueprint: Audit Log Dashboard — 21 CFR Part 11 compliance.
Read-only routes, protected by @login_required.
"""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from models import db, AuditLog
from sqlalchemy import func, cast, Date
from audit_trail import _generate_checksum
import csv
import io
from datetime import datetime, timezone

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')


def api_login_required(f):
    """Like @login_required but returns 401 JSON instead of redirecting.
    Used on all /audit/api/* routes so unauthenticated API calls are rejected,
    not silently passed through (required for 21 CFR Part 11 data protection).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


# ── HTML Dashboard ────────────────────────────────────────────────────────────

@audit_bp.route('/')
@login_required
def dashboard():
    return render_template('audit_dashboard.html')


# ── API: Summary Stats ────────────────────────────────────────────────────────

@audit_bp.route('/api/stats')
@api_login_required
def api_stats():
    total = db.session.query(func.count(AuditLog.id)).scalar() or 0

    by_action = {
        row[0]: row[1]
        for row in db.session.query(
            AuditLog.action_type, func.count(AuditLog.id)
        ).group_by(AuditLog.action_type).all()
    }

    by_record_type = {
        row[0]: row[1]
        for row in db.session.query(
            AuditLog.record_type, func.count(AuditLog.id)
        ).group_by(AuditLog.record_type).all()
    }

    failed_logins = db.session.query(func.count(AuditLog.id)).filter(
        AuditLog.action_type == 'LOGIN_FAILED'
    ).scalar() or 0

    day_rows = db.session.query(
        cast(AuditLog.timestamp, Date).label('day'),
        func.count(AuditLog.id).label('cnt')
    ).group_by('day').order_by('day').all()

    logs_by_day = [{'date': str(row.day), 'count': row.cnt} for row in day_rows]

    return jsonify({
        'total_logs':     total,
        'by_action':      by_action,
        'by_record_type': by_record_type,
        'failed_logins':  failed_logins,
        'logs_by_day':    logs_by_day,
    })


# ── API: Paginated, Filterable Log Table ──────────────────────────────────────

@audit_bp.route('/api/logs')
@api_login_required
def api_logs():
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    q = AuditLog.query

    if action_type := request.args.get('action_type'):
        q = q.filter(AuditLog.action_type == action_type)
    if username := request.args.get('username'):
        q = q.filter(AuditLog.username == username)
    if record_type := request.args.get('record_type'):
        q = q.filter(AuditLog.record_type == record_type)
    if date_from := request.args.get('date_from'):
        q = q.filter(AuditLog.timestamp >= date_from)
    if date_to := request.args.get('date_to'):
        q = q.filter(AuditLog.timestamp <= date_to)

    paginated = q.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    logs = [
        {
            'id':            e.id,
            'timestamp':     e.timestamp.isoformat() if e.timestamp else None,
            'username':      e.username,
            'action_type':   e.action_type,
            'record_type':   e.record_type,
            'record_id':     e.record_id,
            'field_name':    e.field_name,
            'old_value':     e.old_value,
            'new_value':     e.new_value,
            'change_reason': e.change_reason,
            'ip_address':    e.ip_address,
            'endpoint':      e.endpoint,
            'checksum':      e.checksum,
        }
        for e in paginated.items
    ]

    return jsonify({
        'logs':     logs,
        'total':    paginated.total,
        'page':     paginated.page,
        'pages':    paginated.pages,
        'per_page': per_page,
    })


# ── API: Integrity Check ──────────────────────────────────────────────────────

@audit_bp.route('/api/integrity')
@api_login_required
def api_integrity():
    # Only check real SHA-256 checksums (64 hex chars) — skip test/legacy stubs
    entries = AuditLog.query.filter(
        AuditLog.checksum.isnot(None),
        func.length(AuditLog.checksum) == 64
    ).all()
    tampered_ids = [
        e.id for e in entries
        if e.checksum != _generate_checksum(e)
    ]
    return jsonify({
        'total_checked': len(entries),
        'tampered':      len(tampered_ids),
        'tampered_ids':  tampered_ids,
    })


# ── API: CSV Export ───────────────────────────────────────────────────────────

@audit_bp.route('/api/logs/export')
@api_login_required
def api_logs_export():
    q = AuditLog.query

    if action_type := request.args.get('action_type'):
        q = q.filter(AuditLog.action_type == action_type)
    if username := request.args.get('username'):
        q = q.filter(AuditLog.username == username)
    if record_type := request.args.get('record_type'):
        q = q.filter(AuditLog.record_type == record_type)
    if date_from := request.args.get('date_from'):
        q = q.filter(AuditLog.timestamp >= date_from)
    if date_to := request.args.get('date_to'):
        q = q.filter(AuditLog.timestamp <= date_to)

    entries = q.order_by(AuditLog.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        'id', 'timestamp', 'username', 'action_type', 'record_type',
        'record_id', 'field_name', 'old_value', 'new_value',
        'change_reason', 'ip_address', 'endpoint', 'checksum'
    ])

    # Data rows
    for e in entries:
        writer.writerow([
            e.id,
            e.timestamp.isoformat() if e.timestamp else '',
            e.username,
            e.action_type,
            e.record_type,
            e.record_id or '',
            e.field_name or '',
            e.old_value or '',
            e.new_value or '',
            e.change_reason or '',
            e.ip_address or '',
            e.endpoint or '',
            e.checksum or '',
        ])

    output.seek(0)
    filename = f"audit_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return output.getvalue(), 200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': f'attachment; filename="{filename}"',
    }