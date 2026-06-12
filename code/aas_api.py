"""
aas_api.py

Flask Blueprint: AAS export endpoints (Phase 1 + Phase 2).

Routes
------
GET  /api/aas/<asset_type>/<asset_id>
    Returns AAS JSON for the requested asset.  Nameplate values are loaded
    from the DB first; query params override individual fields.

GET  /api/aas/export/<asset_type>/<asset_id>
    Same as above but triggers a file download (.json attachment).

GET  /api/aas/nameplate/<asset_type>/<asset_id>
    Returns the stored nameplate JSON for the asset (404 if none saved yet).

POST /api/aas/nameplate/<asset_type>/<asset_id>
    Save (or update) nameplate data for the asset.  Body: JSON dict of IDTA
    field names, e.g. {"ManufacturerName": "Siemens", "SerialNumber": "SN-42"}.

Examples
--------
    curl http://localhost:5001/api/aas/equipment/filling-machine-1
    curl "http://localhost:5001/api/aas/equipment/filling-machine-1?manufacturer=Siemens"
    curl -X POST http://localhost:5001/api/aas/nameplate/equipment/filling-machine-1 \\
         -H 'Content-Type: application/json' \\
         -d '{"ManufacturerName":"Siemens","SerialNumber":"SN-0042"}'
"""

from flask import Blueprint, jsonify, request, Response
from flask_login import login_required
from subscriptions import check_subscription
from utils import permission_required
from models import db, AssetNameplate
from aas_manager import build_aas_export, is_valid_asset
from audit_trail import log_audit
from audit_config import ACTION_VIEW, ACTION_EXPORT, ACTION_CREATE, ACTION_UPDATE, RECORD_AAS

aas_bp = Blueprint('aas', __name__, url_prefix='/api/aas')

# Query-param name → IDTA field name
_QP_MAP = {
    'manufacturer':        'ManufacturerName',
    'product_designation': 'ManufacturerProductDesignation',
    'product_root':        'ManufacturerProductRoot',
    'uri_of_product':      'URIOfTheProduct',
    'serial':              'SerialNumber',
    'hw_version':          'HardwareVersion',
    'sw_version':          'SoftwareVersion',
    'country':             'CountryOfOrigin',
    'year_of_construction':'YearOfConstruction',
}

# POST body field name → AssetNameplate column
_BODY_MAP = {
    'ManufacturerName':               'manufacturer_name',
    'ManufacturerProductDesignation': 'manufacturer_product_designation',
    'ManufacturerProductRoot':        'manufacturer_product_root',
    'URIOfTheProduct':                'uri_of_product',
    'SerialNumber':                   'serial_number',
    'HardwareVersion':                'hardware_version',
    'SoftwareVersion':                'software_version',
    'CountryOfOrigin':                'country_of_origin',
    'YearOfConstruction':             'year_of_construction',
}


def _collect_extra(req) -> dict:
    """Pull optional nameplate fields from query string."""
    return {
        aas_key: req.args[qp]
        for qp, aas_key in _QP_MAP.items()
        if qp in req.args
    }


def _load_db_nameplate(asset_type: str, asset_id: str) -> dict:
    """Return stored nameplate values as an IDTA-keyed dict, or {} if none."""
    stored = AssetNameplate.query.filter_by(
        asset_type=asset_type.lower(), asset_id=asset_id.lower()
    ).first()
    return stored.to_dict() if stored else {}


# ---------------------------------------------------------------------------
# AAS export routes
# ---------------------------------------------------------------------------

@aas_bp.route('/<asset_type>/<asset_id>', methods=['GET'])
@login_required
@check_subscription('aas')
@permission_required('aas_export')
def get_aas(asset_type: str, asset_id: str):
    """Return AAS JSON inline.  DB nameplate values are the base; query params override."""
    if not is_valid_asset(asset_type, asset_id):
        return jsonify({'error': f'Unknown asset: {asset_type}/{asset_id}'}), 404
    try:
        extra = {**_load_db_nameplate(asset_type, asset_id), **_collect_extra(request)}
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
    """Return AAS JSON as a downloadable file attachment."""
    if not is_valid_asset(asset_type, asset_id):
        return jsonify({'error': f'Unknown asset: {asset_type}/{asset_id}'}), 404
    try:
        extra = {**_load_db_nameplate(asset_type, asset_id), **_collect_extra(request)}
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


# ---------------------------------------------------------------------------
# Nameplate persistence routes (Phase 2)
# ---------------------------------------------------------------------------

@aas_bp.route('/nameplate/<asset_type>/<asset_id>', methods=['GET'])
@login_required
@check_subscription('aas')
@permission_required('aas_export')
def get_nameplate(asset_type: str, asset_id: str):
    """Return stored nameplate data for the asset (404 if not yet saved)."""
    if not is_valid_asset(asset_type, asset_id):
        return jsonify({'error': f'Unknown asset: {asset_type}/{asset_id}'}), 404
    stored = AssetNameplate.query.filter_by(
        asset_type=asset_type.lower(), asset_id=asset_id.lower()
    ).first()
    if not stored:
        return jsonify({'error': 'No nameplate saved for this asset'}), 404
    return jsonify(stored.to_dict())


@aas_bp.route('/nameplate/<asset_type>/<asset_id>', methods=['POST'])
@login_required
@check_subscription('aas')
@permission_required('aas_export')
def save_nameplate(asset_type: str, asset_id: str):
    """Save (upsert) nameplate data.  Body: JSON dict of IDTA field names."""
    if not is_valid_asset(asset_type, asset_id):
        return jsonify({'error': f'Unknown asset: {asset_type}/{asset_id}'}), 404

    data = request.get_json() or {}
    stored = AssetNameplate.query.filter_by(
        asset_type=asset_type.lower(), asset_id=asset_id.lower()
    ).first()
    action = ACTION_CREATE if stored is None else ACTION_UPDATE
    if stored is None:
        stored = AssetNameplate(asset_type=asset_type.lower(), asset_id=asset_id.lower())
        db.session.add(stored)

    for idta_key, col in _BODY_MAP.items():
        if idta_key in data:
            setattr(stored, col, data[idta_key])

    db.session.commit()
    log_audit(action, RECORD_AAS, record_id=f'{asset_type}/{asset_id}')
    return jsonify(stored.to_dict())
