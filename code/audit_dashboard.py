"""
audit_dashboard.py
Flask Blueprint: Audit Log Dashboard — 21 CFR Part 11 compliance.
Read-only routes, protected by @api_login_required / @login_required.
"""

from flask import Blueprint, render_template, jsonify, request, Response, stream_with_context
from flask_login import login_required, current_user
from functools import wraps
from models import db, AuditLog
from sqlalchemy import func, cast, Date
from audit_trail import _generate_checksum
import csv
import io
from datetime import datetime, timezone, timedelta

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

INTEGRITY_LIMIT = 500  # max rows per integrity check request


def api_login_required(f):
    """Returns 401 JSON for unauthenticated API calls — never redirects.
    Required for 21 CFR Part 11: API consumers must receive machine-readable errors.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def _parse_date_param(value, field_name, end_of_day=False):
    """Parse YYYY-MM-DD string into UTC-aware datetime.
    Returns (datetime, None) on success or (None, error_response) on failure.
    """
    try:
        dt = datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        if end_of_day:
            dt = dt + timedelta(days=1) - timedelta(seconds=1)
        return dt, None
    except ValueError:
        return None, (jsonify({'error': f'Invalid {field_name}. Use YYYY-MM-DD format.'}), 400)


def _apply_filters(q):
    """Apply common query filters from request args. Returns (query, error_response|None)."""
    if action_type := request.args.get('action_type'):
        q = q.filter(AuditLog.action_type == action_type)
    if username := request.args.get('username'):
        q = q.filter(AuditLog.username == username)
    if record_type := request.args.get('record_type'):
        q = q.filter(AuditLog.record_type == record_type)
    if date_from := request.args.get('date_from'):
        dt, err = _parse_date_param(date_from, 'date_from')
        if err:
            return q, err
        q = q.filter(AuditLog.timestamp >= dt)
    if date_to := request.args.get('date_to'):
        dt, err = _parse_date_param(date_to, 'date_to', end_of_day=True)
        if err:
            return q, err
        q = q.filter(AuditLog.timestamp <= dt)
    return q, None


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

    q, err = _apply_filters(AuditLog.query)
    if err:
        return err

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


# ── API: Integrity Check (paginated, max 500 rows per call) ──────────────────

@audit_bp.route('/api/integrity')
@api_login_required
def api_integrity():
    limit    = min(request.args.get('limit', INTEGRITY_LIMIT, type=int), 5000)
    since_id = request.args.get('since_id', type=int)

    q = AuditLog.query.filter(
        AuditLog.checksum.isnot(None),
        func.length(AuditLog.checksum) == 64
    )
    if since_id is not None:
        q = q.filter(AuditLog.id > since_id)

    entries  = q.order_by(AuditLog.id.asc()).limit(limit + 1).all()
    has_more = len(entries) > limit
    if has_more:
        entries = entries[:limit]

    tampered_ids = [
        e.id for e in entries
        if e.checksum != _generate_checksum(e)
    ]

    return jsonify({
        'total_checked': len(entries),
        'tampered':      len(tampered_ids),
        'tampered_ids':  tampered_ids,
        'has_more':      has_more,
        'next_since_id': entries[-1].id if has_more and entries else None,
        'applied_limit': limit,
    })


# ── API: CSV Export (streamed) ────────────────────────────────────────────────

@audit_bp.route('/api/logs/export')
@api_login_required
def api_logs_export():
    q, err = _apply_filters(AuditLog.query)
    if err:
        return err

    q = q.order_by(AuditLog.timestamp.desc())
    filename = f"audit_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    HEADERS = [
        'id', 'timestamp', 'username', 'action_type', 'record_type',
        'record_id', 'field_name', 'old_value', 'new_value',
        'change_reason', 'ip_address', 'endpoint', 'checksum'
    ]

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(HEADERS)
        yield buf.getvalue()

        for e in q.yield_per(200):  # stream 200 rows at a time
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                e.id,
                e.timestamp.isoformat() if e.timestamp else '',
                e.username       or '',
                e.action_type    or '',
                e.record_type    or '',
                e.record_id      or '',
                e.field_name     or '',
                e.old_value      or '',
                e.new_value      or '',
                e.change_reason  or '',
                e.ip_address     or '',
                e.endpoint       or '',
                e.checksum       or '',
            ])
            yield buf.getvalue()

    return Response(
        stream_with_context(generate()),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )