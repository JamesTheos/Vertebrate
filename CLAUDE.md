# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run (Docker — recommended):**
```bash
docker compose up --build        # start all services (Zookeeper, Kafka, PostgreSQL, Flask app)
docker compose down              # stop
docker compose up -d             # start detached
```

**Run (local, no Docker):**
```bash
python code/run.py               # starts Flask on http://localhost:5001
```
Local mode uses SQLite at `code/instance/UserManagement.db`. If Kafka is unreachable, the app starts anyway — Kafka-dependent features are simply skipped.

**Tests:**
```bash
pytest                           # run all tests (configured in pytest.ini → code/tests/)
pytest code/tests/test_audit_trail.py                     # single file
pytest code/tests/test_audit_trail.py -k test_checksum    # single test
```

Tests default to SQLite in-memory. Tests marked `@pytest.mark.postgres_only` are skipped unless `SQLALCHEMY_DATABASE_URI` points to a real PostgreSQL instance.

**Run tests inside Docker:**
```bash
docker compose exec vertebrate-app python /app/code/tests/run_all_tests.py
```

**Default login:** `User_Admin` / `12345` (seeded automatically on first start).

## Architecture

### Entry points
- `code/run.py` — local launcher: checks/creates the SQLite DB, resolves Kafka cluster ID, then calls `create_app()` and starts Flask.
- `code/app.py` — the Flask application factory (`create_app()`). Contains all core routes (SCADA, manufacturing orders, user/role management, settings) and registers all blueprints.
- `docker-compose.yml` — production-style stack: Zookeeper → Kafka → PostgreSQL → Flask app. The app container is passed `DATABASE_URL` (PostgreSQL) and `KAFKASERVER` (internal Docker hostname).

### Blueprint modules
Each feature area is a Flask Blueprint registered in `create_app()`:

| Blueprint | File(s) | Purpose |
|---|---|---|
| `auth` | `auth.py` | Login, logout, register, update user |
| `subscriptions` | `subscriptions.py` | Feature subscription gating |
| `colorsettings` | `colorsettings.py` | UI theme (sidebar/background colours) |
| `product_analytics_app` | `product_analytics_app.py` | Product analytics dashboard |
| `design_space_app` | `DesignSpaceApp.py` | Design space definition/representation |
| `process_qbd_analysis` | `process_qbd_analysis.py` | QbD process analysis |
| `consumeWorkflows` | `consumeWorkflows.py` | Workflow management and consumption |
| `tempConsumerChatbot` | `demo_consumer.py` | Chatbot demo consumer |
| `aas_bp` | `aas_api.py` + `aas_manager.py` | Asset Administration Shell export |

### Data flow
Kafka is the real-time data bus connecting PLCs to the web app:
- PLC → OPC-UA → `PLC2Nexus.py` (producer) → Kafka topics → `consume_messages()` thread in `app.py` → in-memory `data_store` dict → `/get-data` API → frontend charts (SCADA page)
- The `data_store` dict holds topic buffers for: `ISPEScene1`, `ISPEScene2`, `ISPEMTemp`, `ISPESpeed`, `ISPEPressure`, `ISPEAmbTemp`, `ISPEStartPhase1`, `manufacturing_orders`, etc.
- The app runs without Kafka — `is_kafka_available()` is called at startup; if false, no consumer/producer is initialised and Kafka-dependent routes silently no-op.

### Database
- **SQLite** (local dev): `code/instance/UserManagement.db`
- **PostgreSQL** (Docker): set via `DATABASE_URL` env var
- The DB is chosen automatically — if `DATABASE_URL` or `SQLALCHEMY_DATABASE_URI` is set, SQLite logic is skipped entirely.
- `createDB.py` bootstraps the schema and installs the PostgreSQL immutability trigger on `audit_trail.audit_logs` (blocks UPDATE/DELETE for 21 CFR Part 11 compliance).
- The Kafka cluster ID is stored in `metainfo` table. If the cluster ID changes in SQLite mode (new Kafka broker), the local DB is wiped and recreated.

### Auth & access control
Three layered guards are applied to routes (in decorator order, outermost first):
1. `@login_required` — Flask-Login session check
2. `@check_subscription` — checks `app_subscriptions` table; redirects to `subscription-denied.html` if not subscribed. Can be used bare (`@check_subscription`) or with an explicit name (`@check_subscription('app_name')`).
3. `@permission_required('key')` — checks `role_permissions` join table for a matching permission key; returns 403 if not found.

Roles and permissions are managed at runtime via `/role-management` UI. The `User_Admin` seeded user has the `Admin` role.

### 21 CFR Part 11 audit trail
All state-changing operations on users, roles, orders, and configuration must be logged. The audit system lives in:
- `audit_trail.py` — `log_audit()` and `log_field_change()` functions. Each entry gets a SHA-256 checksum. Uses a dedicated SQLAlchemy session so audit writes never interfere with the caller's transaction.
- `audit_config.py` — constants: enabled flag, redacted fields, which record types/actions require a `change_reason`.
- `models.py` → `AuditLog` — maps to `audit_trail.audit_logs` (PostgreSQL schema `audit_trail`).
- `audit_decorators.py` — optional `@audit_action`, `@audit_login`, `@audit_logout` decorators for routes that don't need field-level diff logging.

**Rule:** `change_reason` is mandatory for DELETE actions, sensitive record types (`ROLE`, `PERMISSION`, `PASSWORD`), and sensitive field names (`password`, `permissions`, `subscribed`). `audit_trail.py:_validate_change_reason()` enforces this and raises `ValueError` if violated.

### AAS (Asset Administration Shell)
`aas_manager.py` builds a stateless IEC 62832 / Industry 4.0 AAS export using `basyx-python-sdk`. It reads the ISA-95 site hierarchy from `config.json` (enterprise → site → area → process_cell → unit) and produces a flat JSON list containing the shell, a Digital Nameplate submodel (IDTA-02006), and a custom SiteHierarchy submodel. `aas_api.py` exposes this as a Flask blueprint.

Both API routes (`/api/aas/*`) and the viewer page (`/aas-viewer`) require `@login_required`. The `_flatten_aas_json` helper in `aas_manager.py` normalises both the old flat-list and new wrapped-dict SDK serialisation formats so the rest of the code is insulated from basyx version changes.

#### AAS roadmap

**Phase 1 hardening (next up)**
- Add `@check_subscription('aas')` and `@permission_required('aas_export')` to the API routes and viewer — currently only `@login_required` is applied, which doesn't match the three-layer guard pattern used by SCADA and manufacturing_orders.
- Validate `asset_type` / `asset_id` against known assets defined in `config.json`; return 404 for unknowns rather than silently generating a shell for arbitrary strings.

**Phase 2 — Nameplate persistence**
- New `Asset` DB model to store per-asset nameplate data (manufacturer, serial, HW/SW version) so values survive between sessions instead of being passed as query params each time.
- Complete the IDTA-02006-2-0 mandatory fields that are currently missing: `URIOfTheProduct`, `ManufacturerProductRoot`, `YearOfConstruction`. Expose them as optional form inputs on the viewer.

**Phase 3 — Live operational data submodel**
- Add a third `OperationalData` submodel driven by the Kafka `data_store` (temperature, speed, pressure from `ISPEMTemp`, `ISPESpeed`, `ISPEPressure` topics). This is the "Phase 2" noted in `aas_manager.py`'s module docstring.
- The submodel should be populated on-demand from `data_store` at export time; no continuous sync needed for Phase 3.

**Phase 4 — AASX format**
- Add a `/api/aas/export-aasx/<asset_type>/<asset_id>` endpoint using `basyx.aas.adapter.aasx` to produce the binary AASX package format (IEC 63278-5). Required for real Industry 4.0 partner handover — the current JSON-only export is not accepted by most external BaSyx-based toolchains.

### Configuration
- `code/config.json` — ISA-95 hierarchy, Kafka server address, cluster ID. Read at startup by both `app.py` and `aas_manager.py`.
- `code/appconfig.json` — UI theme colours and current username. Written at login and by the colour settings feature.
- Environment variables override `config.json`: `KAFKASERVER`, `CLUSTERID`, `DATABASE_URL`, `SQLALCHEMY_DATABASE_URI`, `IN_DOCKER`.

### Session timeout
`timeout.py` registers a `before_request` hook that logs out inactive users after 300 seconds (5 minutes) of inactivity, tracked via `session['last_activity']`.
