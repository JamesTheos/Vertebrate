"""
aas_manager.py

Phase 1 MVP: One-time / on-demand AAS export.

Builds an Asset Administration Shell for a Vertebrate asset (equipment unit)
using the ISA-95 site hierarchy from config.json.  The shell is serialised to
AAS JSON (Part 2 API format) and can be returned directly from a Flask route.

No continuous sync, no BaSyx server — just a clean, stateless export function.
Phase 2 will add Kafka-driven live updates.
"""

import json
import os
from datetime import datetime, timezone

import basyx.aas.model as model
import basyx.aas.adapter.json as aas_json
import io

# ---------------------------------------------------------------------------
# Load site hierarchy from config.json
# ---------------------------------------------------------------------------

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

with open(_CONFIG_PATH, 'r') as _f:
    _SITE_CONFIG = json.load(_f)

ENTERPRISE   = _SITE_CONFIG.get('enterprise',    'Unknown')
SITE         = _SITE_CONFIG.get('site',          'Unknown')
AREA         = _SITE_CONFIG.get('area',          'Unknown')
PROCESS_CELL = _SITE_CONFIG.get('process_cell',  'Unknown')
UNIT         = _SITE_CONFIG.get('unit',          'Unknown')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_asset_id(asset_type: str, asset_id: str) -> str:
    """Build a deterministic URN for an asset.

    Format: urn:vertebrate:<enterprise>:<site>:<asset_type>:<asset_id>
    Example: urn:vertebrate:ISPE:Boston:equipment:filling-machine-1
    """
    return (
        f"urn:vertebrate:{ENTERPRISE.lower()}:{SITE.lower()}"
        f":{asset_type.lower()}:{asset_id.lower()}"
    )


def _prop(id_short: str, value: str, value_type=model.datatypes.String) -> model.Property:
    """Convenience wrapper for a typed AAS Property."""
    return model.Property(
        id_short=id_short,
        value_type=value_type,
        value=value,
    )


# ---------------------------------------------------------------------------
# Submodel builders
# ---------------------------------------------------------------------------

def build_digital_nameplate(asset_type: str, asset_id: str, extra: dict | None = None) -> model.Submodel:
    """
    IDTA-02006 Digital Nameplate Submodel (simplified).

    extra: optional dict of additional key/value properties to include,
           e.g. {"ManufacturerName": "Siemens", "SerialNumber": "SN-0042"}
    """
    extra = extra or {}

    elements = [
        _prop('ManufacturerName',    extra.get('ManufacturerName', 'Unknown')),
        _prop('ManufacturerProductDesignation', extra.get('ManufacturerProductDesignation', asset_type)),
        _prop('SerialNumber',        extra.get('SerialNumber', asset_id)),
        _prop('HardwareVersion',     extra.get('HardwareVersion', 'N/A')),
        _prop('SoftwareVersion',     extra.get('SoftwareVersion', 'N/A')),
        _prop('CountryOfOrigin',     extra.get('CountryOfOrigin', 'N/A')),
    ]

    return model.Submodel(
        id=_make_asset_id(asset_type, asset_id) + ':nameplate',
        id_short='DigitalNameplate',
        submodel_element=set(elements),
    )


def build_site_hierarchy_submodel(asset_type: str, asset_id: str) -> model.Submodel:
    """
    Custom Vertebrate Submodel: ISA-95 site location context.
    Tells a receiving system exactly where in the plant this asset lives.
    """
    elements = [
        _prop('Enterprise',   ENTERPRISE),
        _prop('Site',         SITE),
        _prop('Area',         AREA),
        _prop('ProcessCell',  PROCESS_CELL),
        _prop('Unit',         UNIT),
        _prop('AssetType',    asset_type),
        _prop('AssetId',      asset_id),
        _prop('ExportedAt',   datetime.now(timezone.utc).isoformat()),
    ]

    return model.Submodel(
        id=_make_asset_id(asset_type, asset_id) + ':site-hierarchy',
        id_short='SiteHierarchy',
        submodel_element=set(elements),
    )


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def build_aas_export(asset_type: str, asset_id: str, extra: dict | None = None) -> str:
    """
    Build a complete AAS for the given asset and return it as a JSON string.

    Parameters
    ----------
    asset_type : str
        e.g. 'equipment', 'batch', 'filling-line'
    asset_id   : str
        Unique identifier within that type, e.g. 'filling-machine-1'
    extra      : dict, optional
        Additional nameplate properties (ManufacturerName, SerialNumber, …)

    Returns
    -------
    str
        AAS JSON string ready to be served as an HTTP response or saved as .json
    """
    global_asset_id = _make_asset_id(asset_type, asset_id)

    asset_info = model.AssetInformation(
        global_asset_id=global_asset_id,
        asset_kind=model.AssetKind.INSTANCE,
    )

    nameplate_sm   = build_digital_nameplate(asset_type, asset_id, extra)
    site_hierarchy = build_site_hierarchy_submodel(asset_type, asset_id)

    shell = model.AssetAdministrationShell(
        id=global_asset_id + ':aas',
        asset_information=asset_info,
        submodel={
            model.ModelReference.from_referable(nameplate_sm),
            model.ModelReference.from_referable(site_hierarchy),
        },
    )

    # Collect into an object store and serialise
    object_store = model.DictObjectStore([
        shell,
        nameplate_sm,
        site_hierarchy,
    ])

    buf = io.StringIO()
    aas_json.write_aas_json_file(buf, object_store)
    return buf.getvalue()
