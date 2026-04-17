"""
test_aas.py

TDD test suite for the AAS MVP (Phase 1).

Covers:
 - aas_manager: unit tests (no Flask, no DB, no Kafka needed)
 - aas_api:     integration tests via Flask test client

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

    def test_output_contains_two_submodels(self):
        from aas_manager import build_aas_export
        result = json.loads(build_aas_export('equipment', 'fm-1'))
        submodels = [item for item in result if item.get('modelType') == 'Submodel']
        assert len(submodels) == 2

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

@pytest.fixture
def client():
    """Minimal Flask test client — only registers the AAS blueprint.
    No DB, no Kafka required.
    """
    from flask import Flask
    from aas_api import aas_bp

    test_app = Flask(__name__)
    test_app.register_blueprint(aas_bp)
    test_app.config['TESTING'] = True

    with test_app.test_client() as c:
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
        response = client.get('/api/aas/equipment/fm-1?manufacturer=Siemens')
        data = json.loads(response.data)
        all_elements = []
        for item in data:
            all_elements.extend(item.get('submodelElements', []))
        mfr = next((e for e in all_elements if e.get('idShort') == 'ManufacturerName'), None)
        assert mfr is not None
        assert mfr.get('value') == 'Siemens'

    def test_different_asset_types_return_200(self, client):
        for asset_type in ['equipment', 'batch', 'filling-line']:
            response = client.get(f'/api/aas/{asset_type}/test-id-1')
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
