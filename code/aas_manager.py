"""
aas_manager.py

Stateless AAS (Asset Administration Shell) export for Vertebrate assets.

Builds an IEC 63278 / Industry 4.0 AAS from the ISA-95 site hierarchy in
config.json and returns it as JSON (Part 2 API format) or as a binary AASX
package (IEC 63278-5).  Three submodels are always included:

  - DigitalNameplate  (IDTA-02006-3-0): manufacturer, serial, HW/SW version,
                       etc., each carrying its IDTA/IEC CDD semanticId.
  - SiteHierarchy:    ISA-95 location context (enterprise → unit)
  - OperationalData:  on-demand snapshot of live Kafka values (Temperature,
                      Speed, Pressure) supplied by the caller at export time.

No continuous sync with a BaSyx server — exports are generated on demand.
"""

import json
import os
from datetime import datetime, timezone

import basyx.aas.model as model
import basyx.aas.adapter.json as aas_json
import basyx.aas.adapter.aasx as aas_aasx
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

# Set of (type, id) tuples that are permitted to produce AAS output.
# Populated from the 'assets' list in config.json; empty means no assets defined.
KNOWN_ASSETS: frozenset = frozenset(
    (a['type'].lower(), a['id'].lower())
    for a in _SITE_CONFIG.get('assets', [])
)


def is_valid_asset(asset_type: str, asset_id: str) -> bool:
    """Return True if (asset_type, asset_id) is declared in config.json assets."""
    return (asset_type.lower(), asset_id.lower()) in KNOWN_ASSETS


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


def _external_ref(value: str) -> model.ExternalReference:
    """Build a semanticId (ExternalReference) from a single global-reference key."""
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, value),))


def _prop(id_short: str, value: str, value_type=model.datatypes.String,
          semantic_id: str | None = None) -> model.Property:
    """Convenience wrapper for a typed AAS Property.

    semantic_id: optional identifier string, wrapped as an ExternalReference so
                 receiving AAS tools can map the property to a standard concept.
    """
    return model.Property(
        id_short=id_short,
        value_type=value_type,
        value=value,
        semantic_id=_external_ref(semantic_id) if semantic_id else None,
    )


def _flatten_aas_json(raw: str) -> str:
    """
    basyx-python-sdk >= 1.1.0 writes the wrapped format:
        {"assetAdministrationShells": [...], "submodels": [...], ...}

    The Vertebrate API and tests expect a flat list:
        [{"modelType": "AssetAdministrationShell", ...}, {"modelType": "Submodel", ...}, ...]

    This function normalises both formats to the flat list so the rest of the
    codebase is insulated from SDK serialisation changes.
    """
    parsed = json.loads(raw)

    # Already a flat list (SDK < 1.1.0 format) — nothing to do
    if isinstance(parsed, list):
        return raw

    # Wrapped dict format (SDK >= 1.1.0)
    flat = []
    for shell in parsed.get('assetAdministrationShells', []):
        shell.setdefault('modelType', 'AssetAdministrationShell')
        flat.append(shell)
    for submodel in parsed.get('submodels', []):
        submodel.setdefault('modelType', 'Submodel')
        flat.append(submodel)
    for concept in parsed.get('conceptDescriptions', []):
        concept.setdefault('modelType', 'ConceptDescription')
        flat.append(concept)

    return json.dumps(flat)


# ---------------------------------------------------------------------------
# Submodel builders
# ---------------------------------------------------------------------------

# IDTA-02006-3-0 Digital Nameplate semanticIds, verified against the published
# IDTA submodel template (admin-shell-io/submodel-templates, Digital nameplate
# 3/0).  The submodel-level IRI lets AAS tooling recognise this as a standard
# Digital Nameplate; the per-field IEC CDD identifiers map each property to its
# standardised concept.
NAMEPLATE_SEMANTIC_ID = 'https://admin-shell.io/idta/nameplate/3/0/Nameplate'
_NAMEPLATE_FIELD_SEMANTIC_IDS = {
    'ManufacturerName':               '0112/2///61987#ABA565#009',
    'ManufacturerProductDesignation': '0112/2///61987#ABA567#009',
    'ManufacturerProductRoot':        '0112/2///61360_7#AAS011#001',
    'URIOfTheProduct':                '0112/2///61987#ABN590#002',
    'SerialNumber':                   '0112/2///61987#ABA951#009',
    'HardwareVersion':                '0112/2///61987#ABA926#008',
    'SoftwareVersion':                '0112/2///61987#ABA601#008',
    'CountryOfOrigin':                '0112/2///61987#ABP462#001',
    'YearOfConstruction':             '0112/2///61987#ABP000#002',
}


def build_digital_nameplate(asset_type: str, asset_id: str, extra: dict | None = None) -> model.Submodel:
    """
    IDTA-02006-3-0 Digital Nameplate Submodel (subset of fields).

    Each property and the submodel itself carry their IDTA/IEC CDD semanticId so
    receiving AAS tools recognise the export as a standard Digital Nameplate.

    extra: optional dict of additional key/value properties to include,
           e.g. {"ManufacturerName": "Siemens", "SerialNumber": "SN-0042"}
    """
    extra = extra or {}

    field_values = [
        ('ManufacturerName',               extra.get('ManufacturerName', 'Unknown')),
        ('ManufacturerProductDesignation', extra.get('ManufacturerProductDesignation', asset_type)),
        ('ManufacturerProductRoot',        extra.get('ManufacturerProductRoot', 'N/A')),
        ('URIOfTheProduct',                extra.get('URIOfTheProduct', 'N/A')),
        ('SerialNumber',                   extra.get('SerialNumber', asset_id)),
        ('HardwareVersion',                extra.get('HardwareVersion', 'N/A')),
        ('SoftwareVersion',                extra.get('SoftwareVersion', 'N/A')),
        ('CountryOfOrigin',                extra.get('CountryOfOrigin', 'N/A')),
        ('YearOfConstruction',             extra.get('YearOfConstruction', 'N/A')),
    ]
    elements = [
        _prop(id_short, value, semantic_id=_NAMEPLATE_FIELD_SEMANTIC_IDS.get(id_short))
        for id_short, value in field_values
    ]

    return model.Submodel(
        id_=_make_asset_id(asset_type, asset_id) + ':nameplate',
        id_short='DigitalNameplate',
        semantic_id=_external_ref(NAMEPLATE_SEMANTIC_ID),
        submodel_element=set(elements),
    )


def build_operational_data_submodel(
    asset_type: str, asset_id: str, operational_data: dict | None = None
) -> model.Submodel:
    """
    Custom Vertebrate Submodel: on-demand snapshot of live process values.

    operational_data: dict with string-valued keys Temperature, Speed, Pressure
                      (sourced from Kafka data_store at export time).
                      Missing or None values default to 'N/A'.
    """
    ops = operational_data or {}

    def _val(key: str) -> str:
        v = ops.get(key)
        return str(v) if v is not None else 'N/A'

    elements = [
        _prop('Temperature',      _val('Temperature')),
        _prop('Speed',            _val('Speed')),
        _prop('Pressure',         _val('Pressure')),
        _prop('SnapshotTimestamp', datetime.now(timezone.utc).isoformat()),
    ]

    return model.Submodel(
        id_=_make_asset_id(asset_type, asset_id) + ':operational-data',
        id_short='OperationalData',
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
        id_=_make_asset_id(asset_type, asset_id) + ':site-hierarchy',
        id_short='SiteHierarchy',
        submodel_element=set(elements),
    )


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def build_aas_export(
    asset_type: str,
    asset_id: str,
    extra: dict | None = None,
    operational_data: dict | None = None,
) -> str:
    """
    Build a complete AAS for the given asset and return it as a JSON string.

    Parameters
    ----------
    asset_type       : str   e.g. 'equipment', 'batch', 'filling-line'
    asset_id         : str   Unique identifier, e.g. 'filling-machine-1'
    extra            : dict  Nameplate overrides (ManufacturerName, SerialNumber, …)
    operational_data : dict  Live process values (Temperature, Speed, Pressure)

    Returns
    -------
    str
        Flat-list AAS JSON string.  Format: [{"modelType": ..., ...}, ...]
    """
    global_asset_id = _make_asset_id(asset_type, asset_id)

    asset_info = model.AssetInformation(
        global_asset_id=global_asset_id,
        asset_kind=model.AssetKind.INSTANCE,
    )

    nameplate_sm   = build_digital_nameplate(asset_type, asset_id, extra)
    site_hierarchy = build_site_hierarchy_submodel(asset_type, asset_id)
    operational_sm = build_operational_data_submodel(asset_type, asset_id, operational_data)

    shell = model.AssetAdministrationShell(
        id_=global_asset_id + ':aas',
        asset_information=asset_info,
        submodel={
            model.ModelReference.from_referable(nameplate_sm),
            model.ModelReference.from_referable(site_hierarchy),
            model.ModelReference.from_referable(operational_sm),
        },
    )

    # Collect into an object store and serialise
    object_store = model.DictObjectStore([
        shell,
        nameplate_sm,
        site_hierarchy,
        operational_sm,
    ])

    buf = io.StringIO()
    aas_json.write_aas_json_file(buf, object_store)

    # Normalise to flat list regardless of SDK version
    return _flatten_aas_json(buf.getvalue())


def build_aas_aasx(
    asset_type: str,
    asset_id: str,
    extra: dict | None = None,
    operational_data: dict | None = None,
) -> bytes:
    """
    Build a complete AAS for the given asset and return it as an AASX binary.

    AASX is an OPC/ZIP package (IEC 63278-5) required by most Industry 4.0
    toolchains.  The same three submodels produced by build_aas_export() are
    embedded as JSON inside the package.

    Returns
    -------
    bytes
        Raw AASX package bytes suitable for serving as a binary download.
    """
    global_asset_id = _make_asset_id(asset_type, asset_id)

    asset_info = model.AssetInformation(
        global_asset_id=global_asset_id,
        asset_kind=model.AssetKind.INSTANCE,
    )

    nameplate_sm   = build_digital_nameplate(asset_type, asset_id, extra)
    site_hierarchy = build_site_hierarchy_submodel(asset_type, asset_id)
    operational_sm = build_operational_data_submodel(asset_type, asset_id, operational_data)

    shell = model.AssetAdministrationShell(
        id_=global_asset_id + ':aas',
        asset_information=asset_info,
        submodel={
            model.ModelReference.from_referable(nameplate_sm),
            model.ModelReference.from_referable(site_hierarchy),
            model.ModelReference.from_referable(operational_sm),
        },
    )

    object_store = model.DictObjectStore([
        shell,
        nameplate_sm,
        site_hierarchy,
        operational_sm,
    ])

    all_ids = [shell.id, nameplate_sm.id, site_hierarchy.id, operational_sm.id]
    files   = aas_aasx.DictSupplementaryFileContainer()

    buf = io.BytesIO()
    with aas_aasx.AASXWriter(buf) as writer:
        writer.write_aas_objects(
            '/aasx/data.json',
            all_ids,
            object_store,
            files,
            write_json=True,
        )

    return buf.getvalue()
