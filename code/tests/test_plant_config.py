"""
test_plant_config.py

Regression guard for /save-plant-config.

The route used to write the POST body to config.json wholesale, dropping every
key the caller didn't submit (Kafkaserver, clusterid, assets).  Saving the plant
hierarchy through the UI therefore corrupted config.json and crashed the app on
next startup (product_analytics_app.py reads config['Kafkaserver'] at import).

A partial save must MERGE into the existing config, preserving unrelated keys.
"""

import json
import os


CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json'
)


def _login_admin(client):
    client.post('/logoutUser', content_type='application/json')
    return client.post(
        '/loginUser',
        data=json.dumps({'username': 'User_Admin', 'password': '12345'}),
        content_type='application/json',
    )


def _read_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


class TestSavePlantConfigMerge:
    """POSTing only the ISA-95 hierarchy must not drop infrastructure keys."""

    def test_partial_save_preserves_unrelated_keys(self, app, client):
        _login_admin(client)
        before = _read_config()
        # Sanity: the keys we expect to be preserved are actually present.
        assert 'Kafkaserver' in before
        assert 'clusterid' in before
        assert 'assets' in before

        resp = client.post(
            '/save-plant-config',
            data=json.dumps({
                'enterprise': 'MergeCorp',
                'site': 'Site-Merge',
                'area': 'Area-1',
                'process_cell': 'Cell-1',
                'unit': 'Unit-1',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200

        after = _read_config()
        # Submitted fields are updated …
        assert after['enterprise'] == 'MergeCorp'
        assert after['site'] == 'Site-Merge'
        # … and unrelated infrastructure keys are preserved (the bug).
        assert after.get('Kafkaserver') == before['Kafkaserver'], \
            "Kafkaserver was dropped — save overwrote config.json instead of merging"
        assert after.get('clusterid') == before['clusterid'], \
            "clusterid was dropped — save overwrote config.json instead of merging"
        assert after.get('assets') == before['assets'], \
            "assets were dropped — save overwrote config.json instead of merging"
