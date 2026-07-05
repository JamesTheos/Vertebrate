# SIEM Audit-Feed Endpoint — Implementation Plan (TDD)

**Branch:** `audit-dashboard` (do **not** merge — still pending the coordinated merge with `feature/aas-integration`)
**Goal:** A machine-pollable, token-authenticated, incremental audit-event feed that a SIEM (Splunk / Sentinel / QRadar / Elastic) can tail.
**Status:** ✅ IMPLEMENTED (2026-07-05) — all 5 TDD steps committed on `audit-dashboard` (18 new tests in `code/tests/test_siem_feed.py`; full suite 120 passed / 0 regressions). E2E-verified against the running app: key provisioned via `create_siem_key.py`, NDJSON event + `_meta` cursor line delivered, incremental re-pull empty, bad key → 401 JSON.

**Decisions resolved (user, 2026-07-05):**
- Target SIEM is *generic* → NDJSON confirmed sufficient, no CEF/LEEF.
- Keys live in a DB table (`siem_api_keys`, SHA-256 hash only) provisioned via `python code/create_siem_key.py <name>` / `--deactivate <name>`.
- SIEM pulls are **not** written to the audit trail (would flood it at poll cadence); `last_used_at` on the key is the liveness/traceability signal.

## Design summary

New route: `GET /audit/api/siem`

- **Auth:** static API key via `Authorization: Bearer <key>` or `X-API-Key` header (not session cookies).
- **Cursor:** `?since_id=<int>&limit=<int>` → events with `id > since_id`, `ORDER BY id ASC` (copies the proven pattern from `api_integrity`). Returns `next_since_id` + `has_more` so the SIEM never skips or double-reads.
- **Format:** NDJSON (JSON Lines), streamed — one event per line. Reuses the streaming-generator pattern from `api_logs_export`. Optional `?format=json` for a wrapped array.
- **Filters:** reuse existing `_apply_filters` (date/action/user/record type) unchanged.
- **Payload per line:** same serialization as `api_logs`, including `checksum` for tamper-evidence.

### The one genuinely new piece: token auth

- New `SiemApiKey` model (`models.py`): `id`, `name`, `key_hash` (SHA-256, never store raw), `active`, `created_at`, `last_used_at`.
- Helper `_authenticate_siem_key()` → hashes presented key, looks up an `active` match. Returns **401 JSON** if missing/invalid — never redirects (matches `api_permission_required` convention).
- Keys provisioned out-of-band (a small CLI/seed helper, or manual DB insert for MVP). No self-service UI in this phase.

## TDD sequence (RED → GREEN → commit per step)

Tests live in `code/tests/test_siem_feed.py`, following the existing `test_audit_dashboard.py` fixture style (module-scoped `create_app()`, `DISABLE_KAFKA=1`, in-memory SQLite). Run inside Docker per CLAUDE.md.

**Step 1 — Auth gate (the security core, first)**
- `test_siem_requires_key` — no header → 401 JSON.
- `test_siem_rejects_bad_key` — wrong/inactive key → 401 JSON.
- `test_siem_accepts_valid_key` — valid key → 200.
- Implement: `SiemApiKey` model + `_authenticate_siem_key()` + route skeleton.

**Step 2 — Cursor pagination**
- `test_siem_returns_events_after_since_id` — seed N logs, `since_id=X` returns only `id > X`, ascending.
- `test_siem_respects_limit_and_reports_next_cursor` — `has_more` + `next_since_id` correct at the boundary.
- `test_siem_empty_when_caught_up` — `since_id` = max → empty, `has_more=false`.

**Step 3 — NDJSON payload + integrity field**
- `test_siem_emits_ndjson_one_event_per_line` — each line parses as JSON independently.
- `test_siem_payload_includes_checksum_and_core_fields` — timestamp/username/action_type/ip_address/checksum present.

**Step 4 — Filters + input hardening**
- `test_siem_filters_by_action_and_date` — `_apply_filters` wired in.
- `test_siem_rejects_bad_date_param` — 400 JSON (reuses `_parse_date_param`).
- `test_siem_limit_is_capped` — oversized `limit` clamped (mirror the 5000 cap in `api_integrity`).

**Step 5 — Key lifecycle touch-up**
- `test_siem_updates_last_used_at` — successful auth stamps `last_used_at` (SIEM liveness signal).

## Files touched

| File | Change |
|---|---|
| `code/models.py` | + `SiemApiKey` model |
| `code/audit_dashboard.py` | + `/api/siem` route, `_authenticate_siem_key()`, NDJSON streamer |
| `code/tests/test_siem_feed.py` | new test module (all steps above) |
| `code/createDB.py` | ensure `siem_api_keys` table created (+ optional seed helper) |

## Explicitly out of scope (flag for review)

- **Key-management UI** — MVP provisions keys via CLI/DB insert. A `/role-management`-style admin screen is a follow-up.
- **CEF/LEEF/syslog formats** — NDJSON only for now; add a formatter later only if a specific collector needs it.
- **Rate limiting / IP allow-listing** on the endpoint — recommend adding before production exposure.
- **Should the SIEM feed itself be audited?** (i.e. log that a pull happened.) Worth a decision — it's a read of regulated data.

## Open questions

1. Which SIEM(s) are the target? (Confirms NDJSON is acceptable vs. needing CEF/syslog.)
2. Key storage: DB table (this plan) vs. env/secret-manager? Regulated environments often mandate the latter.
3. Does pulling the audit trail need to be recorded in the audit trail itself (Part 11 traceability)?

## Estimate

~1–2 days: token auth + tests is the bulk; the cursor endpoint and NDJSON streamer are thin adaptations of code already on the `audit-dashboard` branch.

## Reusable groundwork already on `audit-dashboard`

- `AuditLog` model (`models.py`) — SIEM-ready fields incl. UTC timestamp, username, action_type, ip_address, endpoint, checksum.
- `api_permission_required` (`audit_dashboard.py`) — 401/403 JSON, never redirects. Auth convention to mirror.
- `api_integrity` (`audit_dashboard.py`) — `id > since_id`, ascending cursor pattern to copy.
- `api_logs_export` (`audit_dashboard.py`) — streaming generator pattern for NDJSON.
- `_apply_filters` / `_parse_date_param` (`audit_dashboard.py`) — reuse verbatim.
- PostgreSQL immutability trigger on `audit_trail.audit_logs` — append-only source of truth.
