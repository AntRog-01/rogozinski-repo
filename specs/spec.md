<!-- ai-generated: 90% - drafted specification with AI assistant -->
# svcdesk Specification (Lab 1)

## 1. System Overview
`svcdesk` is an HTTP REST service exposed on port 8080 providing ticket management and SLA tracking for internal IT service desk operations. All request and response bodies use `application/json`.

## 2. Selected Conflict Resolutions

### C1: SLA Clock for P1 (`wallclock`)
- Priority P1 tickets represent critical organizational impact and work stoppage. Their acknowledgement (15 min) and resolution (4 hours) SLA targets are measured on a 24/7 wall-clock basis (`created_at + target`).
- Priorities P2, P3, and P4 SLA targets run strictly on the business-hours clock (Monday to Friday, 08:00:00 to 16:00:00 Europe/Warsaw, DST-aware).
- The tie rule applies: a target completing exactly at 16:00:00 is due at 16:00:00 on that day.

### C2: Closed Tickets and Reopening (`immutable`)
- Closed tickets are immutable (R-09). Any attempt to reopen a ticket in `closed` state returns HTTP 409 Conflict.
- Subsequent issues must be tracked using a new ticket referencing the closed one via `related_to`.
- Reopening is supported exclusively for tickets in `resolved` state within a 7-day window from `resolved_at`. Reopening moves the ticket back to `in_progress` and clears `resolved_at` and `closed_at`.

### C3: VIP Reporters and Priority Matrix (`vip`)
- Priority is initially computed using the standard 3x3 Impact x Urgency matrix:
  - Impact 1: Org (1,1 -> P1, 1,2 -> P2, 1,3 -> P3)
  - Impact 2: Team (2,1 -> P2, 2,2 -> P3, 2,3 -> P4)
  - Impact 3: Individual (3,1 -> P3, 3,2 -> P4, 3,3 -> P4)
- If `reporter.vip` is `true`, any resulting priority of P3 or P4 is automatically promoted to `P2`. P1 and P2 remain unchanged.
- Explicit `priority` fields provided in request payloads are silently ignored.

## 3. API Endpoints and State Machine
- `GET /health` -> HTTP 200 `{"status": "ok", "service": "svcdesk"}`
- `POST /tickets` -> HTTP 201 with created Ticket model.
- `GET /tickets` -> HTTP 200 list of tickets, supporting exact filters `?state=` and `?priority=`.
- `GET /tickets/{id}` -> HTTP 200 Ticket, or HTTP 404 with `{"error": {...}}`.
- `GET /tickets/{id}/sla` -> HTTP 200 SLA evaluation `{priority, ack_due_at, resolve_due_at, ack_breached, resolve_breached, paused}`.
- State transitions (HTTP 200 Ticket, or HTTP 409 Conflict on invalid transition):
  - `POST /tickets/{id}/ack`: `new` -> `acknowledged`, sets `acknowledged_at = now`.
  - `POST /tickets/{id}/start`: `acknowledged` -> `in_progress`.
  - `POST /tickets/{id}/resolve`: `in_progress` -> `resolved`, sets `resolved_at = now`.
  - `POST /tickets/{id}/close`: `resolved` -> `closed`, sets `closed_at = now`.
  - `POST /tickets/{id}/reopen`: `resolved` (within 7 days) -> `in_progress`, clears `resolved_at` and `closed_at`.

## 4. Test Clock Contract
When `SVCDESK_TEST_CLOCK` is set to `"1"` or `"true"`, requests may supply an `X-Test-Clock` header containing an RFC 3339 timestamp. The service uses this instant as `now` strictly for that single request.