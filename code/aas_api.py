"""
aas_api.py

Flask Blueprint: AAS export endpoints (Phase 1 — read-only, on-demand).

Routes
------
GET /api/aas/<asset_type>/<asset_id>
    Returns AAS JSON for the requested asset.
    Query params:
        manufacturer  (str)  e.g. ?manufacturer=Siemens
        serial        (str)  e.g. ?serial=SN-0042
        hw_version    (str)
        sw_version    (str)

GET /api/aas/export/<asset_type>/<asset_id>
    Same as above but triggers a file download (.json attachment).

Examples
--------
    curl http://localhost:5001/api/aas/equipment/filling-machine-1
    curl "http://localhost:5001/api/aas/equipment/filling-machine-1?manufacturer=Siemens&serial=SN-0042"
"""

from flask import Blueprint, jsonify, request, Response
from flask_login import login_required
from subscriptions import check_subscription
from utils import permission_required
from aas_manager import build_aas_export, is_valid_asset
from audit_trail import log_audit
from audit_config import ACTION_VIEW, ACTION_EXPORT, RECORD_AAS

aas_bp = Blueprint('aas', __name__, url_prefix='/api/aas')


def _collect_extra(req) -> dict:
    """Pull optional nameplate fields from query string."""
    mapping = {
        'manufacturer': 'ManufacturerName',
        'product_designation': 'ManufacturerProductDesignation',
        'serial': 'SerialNumber',
        'hw_version': 'HardwareVersion',
        'sw_version': 'SoftwareVersion',
        'country': 'CountryOfOrigin',
    }
    return {
        aas_key: req.args[qp]
        for qp, aas_key in mapping.items()
        if qp in req.args
    }


@aas_bp.route('/<asset_type>/<asset_id>', methods=['GET'])
@login_required
@check_subscription('aas')
@permission_required('aas_export')
def get_aas(asset_type: str, asset_id: str):
    """
    Return AAS JSON inline (application/json).
    Useful for machine-to-machine consumption or browser inspection.
    """
    if not is_valid_asset(asset_type, asset_id):
        return jsonify({'error': f'Unknown asset: {asset_type}/{asset_id}'}), 404
    try:
        extra = _collect_extra(request)
        aas_json = build_aas_export(asset_type, asset_id, extra)
        log_audit(ACTION_VIEW, RECORD_AAS, record_id=f'{asset_type}/{asset_id}')
        return Response(aas_json, mimetype='application/json')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aas_bp.route('/export/<asset_type>/<asset_id>', methods=['GET'])
@login_required
@check_subscription('aas')
@permission_required('aas_export')
def export_aas(asset_type: str, asset_id: str):
    """
    Return AAS JSON as a downloadable file attachment.
    Useful for one-time handover to vendors / partner organisations.
    """
    if not is_valid_asset(asset_type, asset_id):
        return jsonify({'error': f'Unknown asset: {asset_type}/{asset_id}'}), 404
    try:
        extra = _collect_extra(request)
        aas_json = build_aas_export(asset_type, asset_id, extra)
        log_audit(ACTION_EXPORT, RECORD_AAS, record_id=f'{asset_type}/{asset_id}')
        filename = f"aas_{asset_type}_{asset_id}.json"
        return Response(
            aas_json,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
