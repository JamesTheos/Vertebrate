# SIEM Audit Feed — Usage

`GET /audit/api/siem` is a machine-pollable, token-authenticated, incremental feed of the
21 CFR Part 11 audit trail. It is designed for a generic SIEM (Splunk, Sentinel, QRadar,
Elastic, …) to tail: the collector stores one integer cursor and polls on an interval.

It is separate from the human dashboard APIs — session cookies grant **no** access here,
and an API key grants access to **nothing else**.

## 1. Provision an API key

Keys are created out-of-band with a CLI (no self-service UI). Run inside the app container:

```bash
docker exec <app-container> python /app/code/create_siem_key.py splunk-prod
# SIEM API key 'splunk-prod' created. Raw key (shown once, store it now):
# xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The raw key is printed **once** and only its SHA-256 hash is stored (`siem_api_keys` table)
— it cannot be recovered later. Store it in the SIEM's secret store immediately.

Revoke a key (takes effect on the next poll):

```bash
docker exec <app-container> python /app/code/create_siem_key.py --deactivate splunk-prod
```

Each successful poll stamps the key's `last_used_at` — useful as a liveness check that the
SIEM is actually pulling. (By design, pulls are *not* written to the audit trail itself;
they would flood it at poll cadence.)

## 2. Authenticate

Send the raw key on every request, either way:

```
Authorization: Bearer <raw-key>
X-API-Key: <raw-key>
```

Missing, wrong, or deactivated keys always get `401` with a JSON body — never a redirect.

## 3. Poll with the cursor

```
GET /audit/api/siem?since_id=<int>&limit=<int>
```

| Parameter  | Default | Meaning |
|---|---|---|
| `since_id` | none (start of trail) | Return only events with `id > since_id`, ascending |
| `limit`    | 500 (max 5000) | Max events per response; oversized values are clamped |

The response ends with a `_meta` line/object:

- `next_since_id` — pass this as `since_id` on your next poll. When nothing new exists,
  your own cursor is echoed back, so **always** storing `next_since_id` is safe.
- `has_more` — `true` means a backlog remains; poll again immediately instead of waiting
  for the next interval.
- `applied_limit` — the limit actually used after clamping.

Audit log IDs are append-only and strictly increasing (PostgreSQL trigger blocks
UPDATE/DELETE), so this contract never skips or double-delivers an event.

## 4. Response format

Default is **NDJSON** (`application/x-ndjson`) — one event per line, then the `_meta` line:

```
{"id": 41, "timestamp": "2026-07-05T15:06:28.197056+00:00", "username": "User_Admin", "action_type": "LOGIN", "record_type": "USER", "record_id": "1", "field_name": null, "old_value": null, "new_value": null, "change_reason": "Successful login", "ip_address": "172.19.0.1", "endpoint": "auth.loginUser", "checksum": "68a6b402…"}
{"_meta": {"has_more": false, "next_since_id": 41, "applied_limit": 500}}
```

`?format=json` returns the same data as a single wrapped object instead
(`{"events": [...], "has_more": ..., "next_since_id": ..., "applied_limit": ...}`) for
collectors that can't ingest NDJSON.

Every event carries the same fields as the dashboard's `/audit/api/logs` (shared
serializer), including the per-entry SHA-256 `checksum`, so tamper-evidence travels into
the SIEM with the event.

## 5. Optional filters

Same query parameters as the dashboard APIs; combine freely with the cursor:

| Parameter | Example |
|---|---|
| `action_type` | `LOGIN_FAILED` |
| `username` | `User_Admin` |
| `record_type` | `ORDER` |
| `date_from` / `date_to` | `2026-07-01` (YYYY-MM-DD, UTC, inclusive) |

Malformed dates return `400` JSON. Note: if the SIEM should mirror the full trail, poll
unfiltered and filter downstream — a filtered cursor only advances past matching events.

## 6. Error responses

All errors are JSON, never HTML redirects:

| Status | Cause |
|---|---|
| `401` | Missing, invalid, or deactivated API key |
| `400` | Malformed `date_from` / `date_to` |

## 7. Minimal collector loop

```bash
API_KEY='...'; BASE='https://<host>:5001'; CURSOR=0
while true; do
  RESP=$(curl -s -H "Authorization: Bearer $API_KEY" \
         "$BASE/audit/api/siem?since_id=$CURSOR&limit=1000")
  echo "$RESP" | grep -v '"_meta"' >> audit-events.ndjson   # ship these lines
  CURSOR=$(echo "$RESP" | grep '"_meta"' | python -c \
           'import sys,json; print(json.load(sys.stdin)["_meta"]["next_since_id"])')
  echo "$RESP" | grep -q '"has_more": true' || sleep 60
done
```

In practice, point your collector's generic HTTP/JSON puller at the endpoint the same way
(e.g. Splunk HEC-adjacent scripted input, Elastic Agent `httpjson` input with
`response.pagination` on `_meta.next_since_id`).

## 8. Production checklist (not included in the MVP)

- Terminate TLS in front of the app — the key travels in a header.
- Add rate limiting / IP allow-listing before exposing beyond the lab network.
- Rotate keys by creating a new one, switching the SIEM, then `--deactivate` the old.

Design rationale and TDD history: see `siem-feed-plan.md`.
