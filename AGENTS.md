# AGENTS.md – Theos-CES Data Vertebrate

Instructions for any coding agent (Claude Code, Junie, Codex, Gemini, …) working in this repo.
Keep changes small, test-driven, and on a feature branch. When unsure, ask before acting.

## What this is
Theos-CES **Data Vertebrate**: an industrial data hub ("data backbone") for pharma manufacturing.
Flask app + Kafka event stream + PostgreSQL, PLC data via OPC UA bridges. Every value carries its
ISA-95 context (Enterprise › Site › Area › Process Cell › Unit) and, while an order runs, its order/lot.
Core flow: login → create order → release → process instructions drive the PLC → live values,
Data Tree, design-space (QbD) check → order completed with a traceable record.
Regulated context: 21 CFR Part 11 audit trail (immutable, checksummed) must never be weakened.

## Repo map
- `code/app.py` – Flask app factory, routes, Kafka consumer, workflow/step API
- `code/data_hub.py` – event store + `/api/tree`, `/api/topic/<t>/events`, `/api/events/recent`, `/api/health`
- `code/models.py` – SQLAlchemy models (users, roles, permissions, subscriptions, audit_logs, sets)
- `code/audit_trail.py`, `audit_config.py`, `audit_decorators.py` – 21 CFR Part 11 audit trail
- `code/PLC2Nexus.py` / `code/Nexus2PLC.py` – OPC UA ⇄ Kafka bridges
- `code/seed_demo.py` – idempotent demo seed (roles, users, subscriptions, released workflow, QbD set)
- `code/workflows/*.json` – workflows (electronic master recipes), e.g. `FluVaccineISPE`
- `code/templates/`, `code/static/` – Jinja templates, `static/css/theme.css` is the shared theme
- `plc-sim/` – Python OPC UA simulator replacing the CODESYS demo PLC (same node IDs, ns=4)
- `code/tests/` – pytest suite (SQLite in-memory, Kafka disabled via `DISABLE_KAFKA=1`)

## Run
```
docker compose --profile sim up --build          # app :5001, Kafka :9092, PLC sim OPC UA :4840, status :8081
docker compose exec vertebrate-app python seed_demo.py
```
Without `--profile sim` the bridges expect a real PLC. After a restart, run the seed again until
restart robustness is implemented (released workflows are not yet persisted).
Demo mode: manager on http://localhost:5001, operator on http://127.0.0.1:5001 (separate sessions).
Demo users: `User_Admin` (all permissions), `prod.manager` (Production Manager), `operator` (Operator).
Passwords come from `seed_demo.py` / env vars (`DEMO_PM_PW`, `DEMO_OP_PW`) – never write them into code,
docs or commits.

## Test-driven development (mandatory)
Work in red → green → refactor for every change, bug fix included:
1. **Red** – write or extend a test in `code/tests/` that describes the expected behaviour; run it and
   show that it fails for the right reason.
2. **Green** – write the smallest code change that makes it pass.
3. **Refactor** – clean up with all tests green; no behaviour change.
Rules:
- No production code without a failing test first. For a bug: reproduce it in a test before fixing.
- Run the full suite before you report a task as done; report the result (passed/failed/skipped).
- Tests are fast and isolated: SQLite in-memory, Kafka disabled, no network, no real PLC.
  Use fixtures from `conftest.py`; mock Kafka producers/consumers and OPC UA clients.
  Mark tests that need a live Postgres with `@pytest.mark.postgres_only`.
- Routes: test status codes, permission/subscription checks (403 / login page) and JSON shape.
- Audit trail: every new user/order/role/setting change must have a test asserting the audit entry.
- UI-only changes (templates/CSS) still need a route/render test where possible; describe the manual
  check in the report.
- Never delete or weaken an existing test to make the suite pass. Ask instead.

Commands:
```
pip install -r Requirements.txt -r requirements-dev.txt   # local
pytest                                                    # from repo root, uses pytest.ini
pytest code/tests/test_routes.py -k <name>                # single test
docker compose build --build-arg BUILD_ENV=dev vertebrate-app   # image with pytest
docker compose exec vertebrate-app python -m pytest /app/code/tests
```

## Git workflow
- Never commit to `main`. One branch per feature/fix: `feature/<topic>`, `fix/<topic>`, `docs/<topic>`.
  Current work: `feature/data-tree`. Audit-trail order history is its own branch/scope
  (`feature/order-audit-view`) – don't mix it in.
- Small, logical commits with conventional messages (`feat(scope): …`, `fix: …`, `test: …`, `docs: …`).
  Test and implementation of one behaviour may go in the same commit.
- **Ask before** committing, pushing, rebasing, merging or deleting branches. Never force-push.
- Don't commit: `__pycache__`, local DBs (`code/instance/`), `.idea/`, `CLAUDE.local.md`, secrets, `.env`.

## Do not change without explicit approval
- ISA-95 configuration values (`config.json`: ISPE / Boston / Manufacturing Area A / Filling Line 1 /
  Filling Machine 1) and Kafka topic names (`ISPE*`, `manufacturing_orders`).
- OPC UA node IDs and the PLC simulator logic (it mirrors the CODESYS project `ISPERome`).
- How audit entries are written (immutability trigger, checksums, required change reasons).
- Workflow JSON semantics in `code/workflows/` and the `/api/workflows` contract.
- Seeded role/permission keys (renaming breaks existing roles).

## Conventions
- Python 3.11, Flask blueprints, SQLAlchemy; keep functions small and typed where practical.
- Every new route: `@login_required` + `@permission_required(...)` (+ `@check_subscription(...)` for apps).
  Subscription keys and permission keys must match the ones in `seed_demo.py` / role management.
- UI language English; product name "Theos-CES Data Vertebrate"; use `theme.css` tokens, no inline styles
  for new UI; no `alert()` – use the page modal; no `console.log` of user data.
- Timestamps in UTC (`datetime.now(timezone.utc)`), shown in local time in the UI.
- Config via environment variables with safe defaults (e.g. `SESSION_IDLE_MINUTES`, `KAFKASERVER`, `OPCUA_URL`).

## Known backlog (don't fix unasked, but don't make worse)
- Security: unprotected admin endpoints (`/registerUser`, `/subscription-management`, `/get-role`,
  `/update-role`, `/save-plant-config`), default admin password, hard-coded Flask secret key.
- Dead nested routes in `create_app` (`GET /get-role/<name>`, `POST /api/login`).
- Restart robustness: persist released workflows, seed on start, PLC bridge publishes initial values.
- Chatbot (LLM) is hidden behind `SHOW_CHATBOT`; not part of the product scope right now.

## Reporting back
End every task with: changed files, tests added/changed, full-suite result, how to verify manually
(URL + user + steps), and anything you could not verify. Handover notes for testers live outside the
repo (Demo Video/Demo_Test_Findings.md); reference findings by their IDs (F1…, D1…, E1…).
