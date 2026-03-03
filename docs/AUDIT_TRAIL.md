# Audit Trail — 21 CFR Part 11 Compliance

## Overview
Vertebrate implements a compliant audit trail for all user and system actions
as required by FDA 21 CFR Part 11 §11.10(e).

---

## Implemented Requirements

| Requirement | Implementation |
|---|---|
| Computer-generated timestamps | `datetime.now(timezone.utc)` on every entry |
| User identification | `user_id` + `username` captured from `flask_login.current_user` |
| Action type recording | `action_type` field (CREATE, UPDATE, DELETE, LOGIN, LOGOUT, etc.) |
| Record linkage | `record_type` + `record_id` on every entry |
| Field-level change tracking | `field_name`, `old_value`, `new_value` |
| Sensitive field redaction | `password`, `token`, `api_key` values replaced with `[REDACTED]` |
| Change reason enforcement | `change_reason` required for DELETE, UPDATE, and sensitive fields |
| Tamper evidence | SHA-256 checksum generated and stored per entry |
| Immutability | PostgreSQL trigger blocks all UPDATE and DELETE on `audit_trail.audit_logs` |
| System action logging | Unauthenticated/system actions logged with `username = SYSTEM` |

---

## Architecture

- **`audit_trail.py`** — core logging functions (`log_audit`, `log_field_change`, `log_multiple_changes`)
- **`audit_config.py`** — configuration constants (action types, excluded fields, required reason rules)
- **`models.py`** — `AuditLog` SQLAlchemy model mapping to `audit_trail.audit_logs`
- **`createDB.py`** — installs the immutability trigger on DB initialisation

---

## Test Coverage

| File | Coverage |
|---|---|
| `audit_trail.py` | 96% |
| `models.py` | 100% |

Tests located in `tests/test_audit_trail.py`, `tests/test_audit_immutability.py`, `tests/test_auth_audit.py`.

---

## Known Gaps — To Be Addressed in Future Iterations

### 1. Electronic Signatures (§11.50, §11.70)
FDA requires electronic signatures to be permanently linked to their
corresponding audit record, including printed name, date/time, and the
meaning of the signature (e.g. approval, review).

**Action required when:** approval or sign-off workflows are introduced.

### 2. Audit Trail Retention Policy
Records must be retained at least as long as the records they describe.
Currently no automated retention or archival policy exists.

**Action required:** define and implement a retention period (e.g. 7 years)
and a documented SOP before production deployment.

### 3. Audit Trail Export
FDA inspectors must be able to review audit trails in a human-readable format.
Currently no export endpoint (CSV/PDF) exists.

**Action required:** implement an admin-facing export endpoint before
submitting to any regulatory inspection.

### 4. Periodic Audit Trail Review SOP
The regulation expects periodic review of audit trail entries by a qualified
person. This is a process requirement, not a code requirement.

**Action required:** document a review procedure before production deployment.

---

## References
- [21 CFR Part 11 — eCFR](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11)
- [FDA Guidance on Part 11 Scope and Application](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/part-11-electronic-records-electronic-signatures-scope-and-application)
