"""
test_aas_sync_seam.py

Prep for the next-sprint BaSyx push.  Two seams:

  - build_aas_model(): the single source of truth that both the JSON and AASX
    exports (and, next sprint, the BaSyx push) build on — must return the shell
    plus exactly the three expected submodels.
  - sync_to_basyx(): a no-op while no BaSyx server is configured, mirroring how
    the app treats Kafka as optional.  Must not raise and must report 'skipped'.
"""

import basyx.aas.model as model
from aas_manager import build_aas_model, sync_to_basyx


VALID_TYPE, VALID_ID = 'equipment', 'filling-machine-1'


class TestBuildAasModel:
    def test_returns_shell_and_three_submodels(self):
        shell, submodels = build_aas_model(VALID_TYPE, VALID_ID)
        assert isinstance(shell, model.AssetAdministrationShell)
        assert len(submodels) == 3
        id_shorts = {sm.id_short for sm in submodels}
        assert id_shorts == {'DigitalNameplate', 'SiteHierarchy', 'OperationalData'}

    def test_shell_references_every_submodel(self):
        shell, submodels = build_aas_model(VALID_TYPE, VALID_ID)
        assert len(shell.submodel) == len(submodels) == 3


class TestSyncToBasyxSeam:
    def test_unconfigured_sync_is_a_noop(self):
        result = sync_to_basyx(VALID_TYPE, VALID_ID)
        assert result['status'] == 'skipped'
        # The seam still builds the model, so it can't silently drift.
        assert result['submodel_count'] == 3
        assert result['shell_id']

    def test_unconfigured_sync_does_not_raise(self):
        # Smoke: invoking it unconditionally (as a caller would) is safe.
        sync_to_basyx(VALID_TYPE, VALID_ID, extra={'SerialNumber': 'SN-1'})
