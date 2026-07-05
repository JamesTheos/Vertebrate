"""
audit_dashboard.py
Flask Blueprint: Audit Log Dashboard — 21 CFR Part 11 compliance.
Read-only routes, gated by @api_permission_required / @login_required +
@permission_required('audit-view').
"""

from flask import Blueprint, render_template, jsonify, request, Response, stream_with_context
from flask_login import login_required, current_user
from functools import wraps
from models import db, AuditLog, RolePermission, Permission, SiemApiKey
from sqlalchemy import func
from audit_trail import _generate_checksum
from utils import permission_required
import csv
import hashlib
import io
import json
from datetime import datetime, timezone, timedelta

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

INTEGRITY_LIMIT = 500  # max rows per integrity check request

AUDIT_PERMISSION = 'audit-view'  # permission key required to read the audit trail


def _has_permission(*permission_keys):
    """True if any role the current user holds grants any of permission_keys."""
    role_ids = {
        r.id for r in getattr(current_user, 'roles', None) or []
        if getattr(r, 'id', None) is not None
    }
    if not role_ids:
        return False
    return db.session.query(RolePermission).join(
        Permission, RolePermission.permission_id == Permission.id
    ).filter(
        RolePermission.role_id.in_(list(role_ids)),
        Permission.key.in_(permission_keys)
    ).first() is not None


def api_permission_required(*permission_keys):
    """Machine-readable auth for API calls — never redirects (21 CFR Part 11).

    Returns 401 JSON when unauthenticated, 403 JSON when authenticated but
    lacking every one of permission_keys.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            if not _has_permission(*permission_keys):
                return jsonify({'error': 'Permission required'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def _authenticate_siem_key():
    """Resolve the presented API key (Authorization: Bearer <key> or X-API-Key
    header) to an active SiemApiKey row.  Returns the row or None.  Machine
    auth only — session cookies deliberately grant nothing here.
    """
    raw = None
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        raw = auth[len('Bearer '):].strip()
    if not raw:
        raw = request.headers.get('X-API-Key', '').strip() or None
    if not raw:
        return None
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return SiemApiKey.query.filter_by(key_hash=key_hash, active=True).first()


def siem_key_required(f):
    """401 JSON unless a valid, active SIEM API key is presented. Never redirects."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = _authenticate_siem_key()
        if api_key is None:
            return jsonify({'error': 'Valid API key required'}), 401
        return f(api_key, *args, **kwargs)
    return decorated


def _csv_safe(value):
    """Neutralise CSV/Excel formula injection (OWASP): a cell beginning with
    = + - @ (or tab/CR) is treated as a formula by spreadsheet apps, so prefix
    it with a single quote.  Always returns a string.
    """
    s = '' if value is None else str(value)
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


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


def _serialize_log(e):
    """Single JSON shape for one audit entry — used by /api/logs and /api/siem
    so human dashboard and SIEM feed can never drift apart."""
    return {
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
@permission_required(AUDIT_PERMISSION)
def dashboard():
    return render_template('audit_dashboard.html')


# ── API: Summary Stats ────────────────────────────────────────────────────────

@audit_bp.route('/api/stats')
@api_permission_required(AUDIT_PERMISSION)
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

    # func.date() is portable across SQLite and PostgreSQL (both return a
    # 'YYYY-MM-DD' day bucket).  cast(..., Date) breaks on SQLite, which has no
    # real DATE type, so the Date result-processor chokes on fromisoformat.
    day_rows = db.session.query(
        func.date(AuditLog.timestamp).label('day'),
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
@api_permission_required(AUDIT_PERMISSION)
def api_logs():
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    q, err = _apply_filters(AuditLog.query)
    if err:
        return err

    paginated = q.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    logs = [_serialize_log(e) for e in paginated.items]

    return jsonify({
        'logs':     logs,
        'total':    paginated.total,
        'page':     paginated.page,
        'pages':    paginated.pages,
        'per_page': per_page,
    })


# ── API: Integrity Check (paginated, max 500 rows per call) ──────────────────

@audit_bp.route('/api/integrity')
@api_permission_required(AUDIT_PERMISSION)
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
@api_permission_required(AUDIT_PERMISSION)
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
                _csv_safe(e.username),
                _csv_safe(e.action_type),
                _csv_safe(e.record_type),
                _csv_safe(e.record_id),
                _csv_safe(e.field_name),
                _csv_safe(e.old_value),
                _csv_safe(e.new_value),
                _csv_safe(e.change_reason),
                _csv_safe(e.ip_address),
                _csv_safe(e.endpoint),
                _csv_safe(e.checksum),
            ])
            yield buf.getvalue()

    return Response(
        stream_with_context(generate()),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


# ── API: SIEM Feed (token-authenticated, incremental NDJSON) ─────────────────

SIEM_DEFAULT_LIMIT = 500   # events per pull if the SIEM doesn't ask
SIEM_MAX_LIMIT = 5000      # hard cap, mirrors api_integrity


@audit_bp.route('/api/siem')
@siem_key_required
def api_siem(api_key):
    limit = max(1, min(request.args.get('limit', SIEM_DEFAULT_LIMIT, type=int),
                       SIEM_MAX_LIMIT))
    since_id = request.args.get('since_id', type=int)

    q = AuditLog.query
    if since_id is not None:
        q = q.filter(AuditLog.id > since_id)

    entries = q.order_by(AuditLog.id.asc()).limit(limit + 1).all()
    has_more = len(entries) > limit
    if has_more:
        entries = entries[:limit]

    # Cursor the SIEM should present on its next pull: last id delivered, or
    # its own cursor echoed back when there was nothing new.
    meta = {
        'has_more':      has_more,
        'next_since_id': entries[-1].id if entries else since_id,
        'applied_limit': limit,
    }

    if request.args.get('format', '').lower() == 'json':
        return jsonify({'events': [_serialize_log(e) for e in entries], **meta})

    # Default: NDJSON — one event per line, closed by a `_meta` cursor line
    # (NDJSON has no envelope, so the cursor travels as the final record).
    def generate():
        for e in entries:
            yield json.dumps(_serialize_log(e)) + '\n'
        yield json.dumps({'_meta': meta}) + '\n'

    return Response(stream_with_context(generate()),
                    mimetype='application/x-ndjson')