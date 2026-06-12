"""
test_aas.py

TDD test suite for the AAS feature (Phase 1 + Phase 2 + Phase 3).

Covers:
 - aas_manager: unit tests (no Flask, no DB, no Kafka needed)
 - aas_api:     integration tests via Flask test client
 - Phase 2:     AssetNameplate persistence, IDTA-02006 mandatory fields,
                DB/query-param merge behaviour
 - Phase 3:     OperationalData submodel (Temperature, Speed, Pressure)
                populated on-demand from Kafka data_store snapshot

Run inside Docker:
    docker compose exec vertebrate-app pytest /app/code/tests/test_aas.py -v

Run locally (from repo root):
    pytest code/tests/test_aas.py -v
"""

import json
import sys
import os
import pytest

# Make sure the code/ directory is on the path so imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ---------------------------------------------------------------------------
# aas_manager — pure unit tests (no network, no DB)
# ---------------------------------------------------------------------------

class TestAasManagerAssetId:
    """_make_asset_id produces consistent, lowercase URNs."""

    def test_urn_format(self):
        from aas_manager import _make_asset_id
        result = _make_asset_id('equipment', 'filling-machine-1')
        assert result.startswith('urn:vertebrate:')

    def test_urn_is_lowercase(self):
        from aas_manager import _make_asset_id
        result = _make_asset_id('Equipment', 'Filling-Machine-1')
        assert result == result.lower()

    def test_urn_contains_asset_type_and_id(self):
        from aas_manager import _make_asset_id
        result = _make_asset_id('equipment', 'fm-42')
        assert 'equipment' in result
        assert 'fm-42' in result


class TestDigitalNameplate:
    """build_digital_nameplate returns a valid AAS Submodel."""

    def test_returns_submodel(self):
        import basyx.aas.model as model
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-1')
        assert isinstance(sm, model.Submodel)

    def test_id_short_is_nameplate(self):
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-1')
        assert sm.id_short == 'DigitalNameplate'

    def test_extra_manufacturer_name_is_set(self):
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-1', extra={'ManufacturerName': 'Siemens'})
        props = {p.id_short: p.value for p in sm.submodel_element}
        assert props['ManufacturerName'] == 'Siemens'

    def test_serial_number_defaults_to_asset_id(self):
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-99')
        props = {p.id_short: p.value for p in sm.submodel_element}
        assert props['SerialNumber'] == 'fm-99'

    def test_extra_serial_overrides_default(self):
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-99', extra={'SerialNumber': 'SN-0001'})
        props = {p.id_short: p.value for p in sm.submodel_element}
        assert props['SerialNumber'] == 'SN-0001'

    def test_uri_of_product_field_is_present(self):
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-1')
        prop_ids = {p.id_short for p in sm.submodel_element}
        assert 'URIOfTheProduct' in prop_ids

    def test_manufacturer_product_root_field_is_present(self):
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-1')
        prop_ids = {p.id_short for p in sm.submodel_element}
        assert 'ManufacturerProductRoot' in prop_ids

    def test_year_of_construction_field_is_present(self):
        from aas_manager import build_digital_nameplate
        sm = build_digital_nameplate('equipment', 'fm-1')
        prop_ids = {p.id_short for p in sm.submodel_element}
        assert 'YearOfConstruction' in prop_ids


class TestSiteHierarchySubmodel:
    """build_site_hierarchy_submodel embeds ISA-95 config correctly."""

    def test_returns_submodel(self):
        import basyx.aas.model as model
        from aas_manager import build_site_hierarchy_submodel
        sm = build_site_hierarchy_submodel('equipment', 'fm-1')
        assert isinstance(sm, model.Submodel)

    def test_id_short_is_site_hierarchy(self):
        from aas_manager import build_site_hierarchy_submodel
        sm = build_site_hierarchy_submodel('equipment', 'fm-1')
        assert sm.id_short == 'SiteHierarchy'

    def test_contains_enterprise_from_config(self):
        from aas_manager import build_site_hierarchy_submodel, ENTERPRISE
        sm = build_site_hierarchy_submodel('equipment', 'fm-1')
        props = {p.id_short: p.value for p in sm.submodel_element}
        assert props['Enterprise'] == ENTERPRISE

    def test_contains_site_from_config(self):
        from aas_manager import build_site_hierarchy_submodel, SITE
        sm = build_site_hierarchy_submodel('equipment', 'fm-1')
        props = {p.id_short: p.value for p in sm.submodel_element}
        assert props['Site'] == SITE

    def test_exported_at_is_present(self):
        from aas_manager import build_site_hierarchy_submodel
        sm = build_site_hierarchy_submodel('equipment', 'fm-1')
        prop_ids = {p.id_short for p in sm.submodel_element}
        assert 'ExportedAt' in prop_ids


class TestBuildAasExport:
    """build_aas_export returns valid JSON containing expected AAS structure."""

    def test_returns_string(self):
        from aas_manager import build_aas_export
        result = build_aas_export('equipment', 'fm-1')
        assert isinstance(result, str)

    def test_output_is_valid_json(self):
        from aas_manager import build_aas_export
        result = build_aas_export('equipment', 'fm-1')
        parsed = json.loads(result)  # raises if invalid
        assert parsed is not None

    def test_output_contains_asset_administration_shell(self):
        from aas_manager import build_aas_export
        result = json.loads(build_aas_export('equipment', 'fm-1'))
        model_types = [item.get('modelType') for item in result]
        assert 'AssetAdministrationShell' in model_types

    def test_output_contains_three_submodels(self):
        from aas_manager import build_aas_export
        result = json.loads(build_aas_export('equipment', 'fm-1'))
        submodels = [item for item in result if item.get('modelType') == 'Submodel']
        assert len(submodels) == 3

    def test_nameplate_submodel_present(self):
        from aas_manager import build_aas_export
        result = json.loads(build_aas_export('equipment', 'fm-1'))
        id_shorts = [item.get('idShort') for item in result]
        assert 'DigitalNameplate' in id_shorts

    def test_site_hierarchy_submodel_present(self):
        from aas_manager import build_aas_export
        result = json.loads(build_aas_export('equipment', 'fm-1'))
        id_shorts = [item.get('idShort') for item in result]
        assert 'SiteHierarchy' in id_shorts

    def test_extra_params_reflected_in_output(self):
        from aas_manager import build_aas_export
        result = json.loads(build_aas_export('equipment', 'fm-1', extra={'ManufacturerName': 'Bosch'}))
        # Flatten all submodelElements to find ManufacturerName
        all_elements = []
        for item in result:
            all_elements.extend(item.get('submodelElements', []))
        mfr = next((e for e in all_elements if e.get('idShort') == 'ManufacturerName'), None)
        assert mfr is not None
        assert mfr.get('value') == 'Bosch'


# ---------------------------------------------------------------------------
# aas_api — Flask integration tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def client():
    """Full-app AAS test client with subscription, permission, and a seeded user.

    Uses create_app() so @check_subscription and @permission_required work
    against a real in-memory SQLite DB.  Scoped to module — all AAS API tests
    are read-only, so shared state is safe.
    """
    from app import create_app
    from models import db as _db, Subscriptions, Role, Permission, RolePermission, User
    from werkzeug.security import generate_password_hash

    app = create_app()
    app.config['TESTING'] = True

    with app.app_context():
        _db.create_all()

        if not Subscriptions.query.filter_by(apps='aas').first():
            _db.session.add(Subscriptions(apps='aas', subscribed=True))

        role = Role.query.filter_by(name='AasTester').first()
        if not role:
            role = Role(name='AasTester')
            _db.session.add(role)
            _db.session.flush()

        perm = Permission.query.filter_by(key='aas_export').first()
        if not perm:
            perm = Permission(key='aas_export')
            _db.session.add(perm)
            _db.session.flush()

        if not RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first():
            _db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

        if not User.query.filter_by(username='aas_test').first():
            user = User(username='aas_test', password=generate_password_hash('aas_pass'))
            user.roles.append(role)
            _db.session.add(user)

        _db.session.commit()

    with app.test_client() as c:
        c.post('/loginUser',
               data=json.dumps({'username': 'aas_test', 'password': 'aas_pass'}),
               content_type='application/json')
        yield c


class TestAasApiGetEndpoint:
    """GET /api/aas/<asset_type>/<asset_id>"""

    def test_returns_200(self, client):
        response = client.get('/api/aas/equipment/filling-machine-1')
        assert response.status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get('/api/aas/equipment/filling-machine-1')
        assert 'application/json' in response.content_type

    def test_response_is_valid_json(self, client):
        response = client.get('/api/aas/equipment/filling-machine-1')
        data = json.loads(response.data)
        assert data is not None

    def test_manufacturer_query_param_is_reflected(self, client):
        response = client.get('/api/aas/equipment/filling-machine-1?manufacturer=Siemens')
        data = json.loads(response.data)
        all_elements = []
        for item in data:
            all_elements.extend(item.get('submodelElements', []))
        mfr = next((e for e in all_elements if e.get('idShort') == 'ManufacturerName'), None)
        assert mfr is not None
        assert mfr.get('value') == 'Siemens'

    def test_known_asset_returns_200(self, client):
        response = client.get('/api/aas/equipment/filling-machine-1')
        assert response.status_code == 200


class TestAasApiExportEndpoint:
    """GET /api/aas/export/<asset_type>/<asset_id>"""

    def test_returns_200(self, client):
        response = client.get('/api/aas/export/equipment/filling-machine-1')
        assert response.status_code == 200

    def test_content_disposition_is_attachment(self, client):
        response = client.get('/api/aas/export/equipment/filling-machine-1')
        cd = response.headers.get('Content-Disposition', '')
        assert 'attachment' in cd

    def test_filename_contains_asset_type_and_id(self, client):
        response = client.get('/api/aas/export/equipment/filling-machine-1')
        cd = response.headers.get('Content-Disposition', '')
        assert 'equipment' in cd
        assert 'filling-machine-1' in cd

    def test_downloaded_file_is_valid_json(self, client):
        response = client.get('/api/aas/export/equipment/filling-machine-1')
        data = json.loads(response.data)
        assert data is not None


# ---------------------------------------------------------------------------
# Asset validation — only assets declared in config.json may produce AAS output
# ---------------------------------------------------------------------------

class TestAasAssetValidation:
    """
    is_valid_asset() checks the caller-supplied type/id against the 'assets'
    list in config.json.  The API must return 404 for any unknown asset.
    """

    # --- unit tests (no HTTP layer) ---

    def test_known_asset_is_valid(self):
        from aas_manager import is_valid_asset
        assert is_valid_asset('equipment', 'filling-machine-1') is True

    def test_unknown_id_is_invalid(self):
        from aas_manager import is_valid_asset
        assert is_valid_asset('equipment', 'ghost-machine-99') is False

    def test_unknown_type_is_invalid(self):
        from aas_manager import is_valid_asset
        assert is_valid_asset('sensor', 'filling-machine-1') is False

    def test_validation_is_case_insensitive(self):
        from aas_manager import is_valid_asset
        assert is_valid_asset('Equipment', 'Filling-Machine-1') is True

    # --- API integration tests ---

    def test_api_returns_404_for_unknown_asset(self, client):
        r = client.get('/api/aas/equipment/ghost-machine-99')
        assert r.status_code == 404

    def test_api_returns_404_for_unknown_type(self, client):
        r = client.get('/api/aas/sensor/filling-machine-1')
        assert r.status_code == 404

    def test_export_returns_404_for_unknown_asset(self, client):
        r = client.get('/api/aas/export/equipment/ghost-machine-99')
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Phase 2: AssetNameplate persistence
# ---------------------------------------------------------------------------

class TestAssetNameplatePersistence:
    """
    Nameplate data is saved to DB via POST and loaded via GET.
    AAS exports merge DB values with query params (query params win).
    Unknown assets return 404.  New IDTA-02006 mandatory fields are saved and
    round-trip correctly.

    Uses filling-machine-1 for read/write tests and filling-line-1 for the
    "no nameplate saved" test to avoid order-dependency within the module.
    """

    def test_get_returns_404_when_no_nameplate_saved(self, client):
        r = client.get('/api/aas/nameplate/filling-line/filling-line-1')
        assert r.status_code == 404

    def test_post_saves_nameplate_returns_200(self, client):
        r = client.post('/api/aas/nameplate/equipment/filling-machine-1',
                        json={'ManufacturerName': 'Siemens', 'SerialNumber': 'SN-001'})
        assert r.status_code == 200

    def test_get_returns_saved_values(self, client):
        client.post('/api/aas/nameplate/equipment/filling-machine-1',
                    json={'ManufacturerName': 'Bosch', 'SerialNumber': 'SN-999'})
        r = client.get('/api/aas/nameplate/equipment/filling-machine-1')
        assert r.status_code == 200
        data = r.get_json()
        assert data['ManufacturerName'] == 'Bosch'
        assert data['SerialNumber'] == 'SN-999'

    def test_post_updates_existing_nameplate(self, client):
        client.post('/api/aas/nameplate/equipment/filling-machine-1',
                    json={'ManufacturerName': 'ABB'})
        client.post('/api/aas/nameplate/equipment/filling-machine-1',
                    json={'ManufacturerName': 'Festo'})
        r = client.get('/api/aas/nameplate/equipment/filling-machine-1')
        assert r.get_json()['ManufacturerName'] == 'Festo'

    def test_get_nameplate_for_unknown_asset_returns_404(self, client):
        r = client.get('/api/aas/nameplate/equipment/ghost-machine')
        assert r.status_code == 404

    def test_post_nameplate_for_unknown_asset_returns_404(self, client):
        r = client.post('/api/aas/nameplate/equipment/ghost-machine',
                        json={'ManufacturerName': 'X'})
        assert r.status_code == 404

    def test_aas_export_uses_db_nameplate_values(self, client):
        client.post('/api/aas/nameplate/equipment/filling-machine-1',
                    json={'ManufacturerName': 'StoredMfr'})
        r = client.get('/api/aas/equipment/filling-machine-1')
        all_elements = []
        for item in r.get_json():
            all_elements.extend(item.get('submodelElements', []))
        mfr = next((e for e in all_elements if e.get('idShort') == 'ManufacturerName'), None)
        assert mfr is not None
        assert mfr['value'] == 'StoredMfr'

    def test_query_param_overrides_db_value(self, client):
        client.post('/api/aas/nameplate/equipment/filling-machine-1',
                    json={'ManufacturerName': 'DBValue'})
        r = client.get('/api/aas/equipment/filling-machine-1?manufacturer=QueryValue')
        all_elements = []
        for item in r.get_json():
            all_elements.extend(item.get('submodelElements', []))
        mfr = next((e for e in all_elements if e.get('idShort') == 'ManufacturerName'), None)
        assert mfr['value'] == 'QueryValue'

    def test_new_idta_fields_round_trip(self, client):
        client.post('/api/aas/nameplate/equipment/filling-machine-1', json={
            'URIOfTheProduct':      'https://example.com/product/fm1',
            'ManufacturerProductRoot': 'Filling Equipment',
            'YearOfConstruction':   '2022',
        })
        r = client.get('/api/aas/nameplate/equipment/filling-machine-1')
        data = r.get_json()
        assert data['URIOfTheProduct']         == 'https://example.com/product/fm1'
        assert data['ManufacturerProductRoot'] == 'Filling Equipment'
        assert data['YearOfConstruction']      == '2022'

    def test_post_malformed_json_returns_400(self, client):
        r = client.post(
            '/api/aas/nameplate/equipment/filling-machine-1',
            data=b'{"broken": json',
            content_type='application/json',
        )
        assert r.status_code == 400
        assert 'Invalid JSON' in r.get_json()['error']


# ---------------------------------------------------------------------------
# Phase 3: OperationalData submodel
# ---------------------------------------------------------------------------

class TestOperationalDataSubmodel:
    """build_operational_data_submodel returns a valid AAS Submodel."""

    def test_returns_submodel(self):
        import basyx.aas.model as model
        from aas_manager import build_operational_data_submodel
        sm = build_operational_data_submodel('equipment', 'fm-1', {})
        assert isinstance(sm, model.Submodel)

    def test_id_short_is_operational_data(self):
        from aas_manager import build_operational_data_submodel
        sm = build_operational_data_submodel('equipment', 'fm-1', {})
        assert sm.id_short == 'OperationalData'

    def test_contains_temperature_speed_pressure(self):
        from aas_manager import build_operational_data_submodel
        sm = build_operational_data_submodel('equipment', 'fm-1', {})
        prop_ids = {p.id_short for p in sm.submodel_element}
        assert 'Temperature' in prop_ids
        assert 'Speed' in prop_ids
        assert 'Pressure' in prop_ids

    def test_snapshot_timestamp_present(self):
        from aas_manager import build_operational_data_submodel
        sm = build_operational_data_submodel('equipment', 'fm-1', {})
        prop_ids = {p.id_short for p in sm.submodel_element}
        assert 'SnapshotTimestamp' in prop_ids

    def test_values_reflected_from_operational_data(self):
        from aas_manager import build_operational_data_submodel
        ops = {'Temperature': '72.5', 'Speed': '120.0', 'Pressure': '1.8'}
        sm = build_operational_data_submodel('equipment', 'fm-1', ops)
        props = {p.id_short: p.value for p in sm.submodel_element}
        assert props['Temperature'] == '72.5'
        assert props['Speed']       == '120.0'
        assert props['Pressure']    == '1.8'

    def test_missing_values_default_to_na(self):
        from aas_manager import build_operational_data_submodel
        sm = build_operational_data_submodel('equipment', 'fm-1', {})
        props = {p.id_short: p.value for p in sm.submodel_element}
        assert props['Temperature'] == 'N/A'
        assert props['Speed']       == 'N/A'
        assert props['Pressure']    == 'N/A'


class TestBuildAasExportPhase3:
    """build_aas_export includes OperationalData as the third submodel."""

    def test_operational_data_submodel_present(self):
        from aas_manager import build_aas_export
        result = json.loads(build_aas_export('equipment', 'fm-1'))
        id_shorts = [item.get('idShort') for item in result]
        assert 'OperationalData' in id_shorts

    def test_operational_values_passed_through(self):
        from aas_manager import build_aas_export
        ops = {'Temperature': '55.0', 'Speed': '200.0', 'Pressure': '3.2'}
        result = json.loads(build_aas_export('equipment', 'fm-1', operational_data=ops))
        all_elements = []
        for item in result:
            all_elements.extend(item.get('submodelElements', []))
        temp = next((e for e in all_elements if e.get('idShort') == 'Temperature'), None)
        assert temp is not None
        assert temp['value'] == '55.0'


class TestAasOperationalDataApi:
    """API returns OperationalData submodel; values come from data_store snapshot."""

    def test_api_response_includes_operational_data_submodel(self, client):
        r = client.get('/api/aas/equipment/filling-machine-1')
        result = r.get_json()
        id_shorts = [item.get('idShort') for item in result]
        assert 'OperationalData' in id_shorts

    def test_operational_data_has_na_when_kafka_unavailable(self, client):
        r = client.get('/api/aas/equipment/filling-machine-1')
        all_elements = []
        for item in r.get_json():
            all_elements.extend(item.get('submodelElements', []))
        temp = next((e for e in all_elements if e.get('idShort') == 'Temperature'), None)
        assert temp is not None
        assert temp['value'] == 'N/A'

    def test_export_endpoint_also_includes_operational_data(self, client):
        r = client.get('/api/aas/export/equipment/filling-machine-1')
        result = r.get_json()
        id_shorts = [item.get('idShort') for item in result]
        assert 'OperationalData' in id_shorts


# ---------------------------------------------------------------------------
# Phase 4: AASX binary export
# ---------------------------------------------------------------------------

class TestBuildAasAasx:
    """build_aas_aasx returns a valid AASX binary package."""

    def test_returns_bytes(self):
        from aas_manager import build_aas_aasx
        result = build_aas_aasx('equipment', 'fm-1')
        assert isinstance(result, bytes)

    def test_output_is_nonempty(self):
        from aas_manager import build_aas_aasx
        result = build_aas_aasx('equipment', 'fm-1')
        assert len(result) > 0

    def test_output_is_zip_format(self):
        from aas_manager import build_aas_aasx
        result = build_aas_aasx('equipment', 'fm-1')
        assert result[:2] == b'PK', 'AASX must start with ZIP magic bytes PK'

    def test_accepts_extra_and_operational_data(self):
        from aas_manager import build_aas_aasx
        result = build_aas_aasx(
            'equipment', 'fm-1',
            extra={'ManufacturerName': 'Siemens'},
            operational_data={'Temperature': '72.5'},
        )
        assert isinstance(result, bytes)
        assert result[:2] == b'PK'

    def test_aasx_contains_aas_json(self):
        import zipfile, io
        from aas_manager import build_aas_aasx
        result = build_aas_aasx('equipment', 'fm-1')
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        assert any(name.endswith('.json') for name in names)


class TestAasAasxEndpoint:
    """GET /api/aas/export-aasx/<asset_type>/<asset_id>"""

    def test_returns_200(self, client):
        r = client.get('/api/aas/export-aasx/equipment/filling-machine-1')
        assert r.status_code == 200

    def test_content_disposition_is_attachment_with_aasx_extension(self, client):
        r = client.get('/api/aas/export-aasx/equipment/filling-machine-1')
        cd = r.headers.get('Content-Disposition', '')
        assert 'attachment' in cd
        assert '.aasx' in cd

    def test_filename_contains_asset_type_and_id(self, client):
        r = client.get('/api/aas/export-aasx/equipment/filling-machine-1')
        cd = r.headers.get('Content-Disposition', '')
        assert 'equipment' in cd
        assert 'filling-machine-1' in cd

    def test_response_is_zip_binary(self, client):
        r = client.get('/api/aas/export-aasx/equipment/filling-machine-1')
        assert r.data[:2] == b'PK'

    def test_returns_404_for_unknown_asset(self, client):
        r = client.get('/api/aas/export-aasx/equipment/ghost-machine')
        assert r.status_code == 404

    def test_unauthenticated_request_is_rejected(self):
        from app import create_app
        app = create_app()
        with app.test_client() as anon:
            r = anon.get('/api/aas/export-aasx/equipment/filling-machine-1')
        assert r.status_code in (302, 401)


# ---------------------------------------------------------------------------
# Operational data with real values (mocked snapshot)
# ---------------------------------------------------------------------------

class TestOperationalDataWithValues:
    """Verifies that values returned by _operational_snapshot() appear in AAS output."""

    def test_values_from_snapshot_appear_in_aas_output(self, client):
        from unittest.mock import patch
        import aas_api
        mock_ops = {'Temperature': '75.5', 'Speed': '150.0', 'Pressure': '2.3'}
        with patch.object(aas_api, '_operational_snapshot', return_value=mock_ops):
            r = client.get('/api/aas/equipment/filling-machine-1')
        assert r.status_code == 200
        all_elements = []
        for item in r.get_json():
            all_elements.extend(item.get('submodelElements', []))
        by_id = {e['idShort']: e['value'] for e in all_elements if 'idShort' in e}
        assert by_id.get('Temperature') == '75.5'
        assert by_id.get('Speed')       == '150.0'
        assert by_id.get('Pressure')    == '2.3'

    def test_aasx_also_uses_snapshot_values(self, client):
        from unittest.mock import patch
        import aas_api, zipfile, io, json as _json
        mock_ops = {'Temperature': '99.9', 'Speed': '0.0', 'Pressure': '5.0'}
        with patch.object(aas_api, '_operational_snapshot', return_value=mock_ops):
            r = client.get('/api/aas/export-aasx/equipment/filling-machine-1')
        assert r.status_code == 200
        # Parse the AASX ZIP and find the embedded JSON
        with zipfile.ZipFile(io.BytesIO(r.data)) as zf:
            json_names = [n for n in zf.namelist() if n.endswith('.json')]
            assert json_names, 'No JSON file found inside AASX package'
            content = _json.loads(zf.read(json_names[0]))
        # SDK writes wrapped format inside AASX: {"submodels": [...], ...}
        items = content.get('submodels', []) if isinstance(content, dict) else content
        all_elements = []
        for item in items:
            all_elements.extend(item.get('submodelElements', []))
        by_id = {e['idShort']: e['value'] for e in all_elements if 'idShort' in e}
        assert by_id.get('Temperature') == '99.9'
