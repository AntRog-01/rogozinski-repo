# ai-generated: 90% - implementation of svcdesk HTTP API and SLA engine with AI assistant
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Any, Dict, List
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="svcdesk", docs_url=None, redoc_url=None)

DB_PATH = os.environ.get("SVCDESK_DB", "/data/svcdesk.db")
WARSAW_TZ = ZoneInfo("Europe/Warsaw")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            reporter_name TEXT NOT NULL,
            reporter_email TEXT,
            reporter_vip INTEGER NOT NULL,
            impact INTEGER NOT NULL,
            urgency INTEGER NOT NULL,
            priority TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            acknowledged_at TEXT,
            resolved_at TEXT,
            closed_at TEXT,
            related_to TEXT,
            ack_due_at TEXT NOT NULL,
            resolve_due_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def parse_iso(dt_str: str) -> datetime:
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.fromisoformat(dt_str)

def format_iso(dt: datetime) -> str:
    utc_dt = dt.astimezone(ZoneInfo("UTC"))
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def get_request_now(request: Request) -> datetime:
    test_clock_enabled = os.environ.get("SVCDESK_TEST_CLOCK", "").lower() in ("1", "true")
    if test_clock_enabled and "x-test-clock" in request.headers:
        raw = request.headers["x-test-clock"]
        try:
            return parse_iso(raw)
        except Exception:
            raise ValueError("Invalid X-Test-Clock format")
    return datetime.now(ZoneInfo("UTC"))

def compute_priority(impact: int, urgency: int, vip: bool) -> str:
    matrix = {
        (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
        (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
        (3, 1): "P3", (3, 2): "P4", (3, 3): "P4"
    }
    prio = matrix.get((impact, urgency), "P4")
    # C3 = vip: promote P3 or P4 to P2 for VIPs
    if vip and prio in ("P3", "P4"):
        prio = "P2"
    return prio

def add_business_seconds(start_dt: datetime, seconds_to_add: int) -> datetime:
    dt = start_dt.astimezone(WARSAW_TZ)
    rem = seconds_to_add

    while True:
        # Check weekday
        if dt.weekday() >= 5: # Saturday or Sunday
            days_ahead = 7 - dt.weekday()
            dt = dt.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
            continue
        
        # Weekday: check hours
        if dt.hour < 8:
            dt = dt.replace(hour=8, minute=0, second=0, microsecond=0)
        elif dt.hour >= 16:
            dt = dt.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
            continue
        
        # Inside window [08:00, 16:00)
        close_today = dt.replace(hour=16, minute=0, second=0, microsecond=0)
        available_today = int((close_today - dt).total_seconds())

        if rem <= available_today:
            return dt + timedelta(seconds=rem)
        else:
            rem -= available_today
            dt = dt.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)

def compute_due_dates(created_at: datetime, priority: str):
    targets = {
        "P1": (15 * 60, 4 * 3600),
        "P2": (1 * 3600, 8 * 3600),
        "P3": (4 * 3600, 24 * 3600),
        "P4": (8 * 3600, 72 * 3600),
    }
    ack_sec, res_sec = targets[priority]

    # C1 = wallclock: P1 is wall-clock, P2-P4 are business
    if priority == "P1":
        ack_due = created_at + timedelta(seconds=ack_sec)
        res_due = created_at + timedelta(seconds=res_sec)
    else:
        ack_due = add_business_seconds(created_at, ack_sec)
        res_due = add_business_seconds(created_at, res_sec)

    return ack_due, res_due

def is_inside_business_hours(dt: datetime) -> bool:
    local_dt = dt.astimezone(WARSAW_TZ)
    if local_dt.weekday() >= 5:
        return False
    opening = local_dt.replace(hour=8, minute=0, second=0, microsecond=0)
    closing = local_dt.replace(hour=16, minute=0, second=0, microsecond=0)
    return opening <= local_dt < closing

def row_to_ticket(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"] or "",
        "reporter": {
            "name": row["reporter_name"],
            "email": row["reporter_email"],
            "vip": bool(row["reporter_vip"])
        },
        "impact": row["impact"],
        "urgency": row["urgency"],
        "priority": row["priority"],
        "state": row["state"],
        "created_at": row["created_at"],
        "acknowledged_at": row["acknowledged_at"],
        "resolved_at": row["resolved_at"],
        "closed_at": row["closed_at"],
        "related_to": row["related_to"],
        "sla": {
            "ack_due_at": row["ack_due_at"],
            "resolve_due_at": row["resolve_due_at"]
        }
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "svcdesk"}

@app.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(request: Request):
    try:
        now = get_request_now(request)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_clock", "message": "Malformed X-Test-Clock header"}})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_json", "message": "Invalid JSON"}})

    if not isinstance(body, dict):
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_payload", "message": "Expected JSON object"}})

    title = body.get("title")
    if not isinstance(title, str) or len(title) < 1 or len(title) > 200:
        return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": "Title must be 1..200 characters"}})

    desc = body.get("description", "")
    if desc is not None and not isinstance(desc, str):
        return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": "Invalid description"}})
    if desc and len(desc) > 4000:
        return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": "Description too long"}})

    reporter = body.get("reporter")
    if not isinstance(reporter, dict):
        return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": "Reporter object required"}})

    rep_name = reporter.get("name")
    if not isinstance(rep_name, str) or len(rep_name) < 1 or len(rep_name) > 100:
        return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": "Reporter name must be 1..100 characters"}})

    rep_email = reporter.get("email", None)
    rep_vip = bool(reporter.get("vip", False))

    impact = body.get("impact")
    urgency = body.get("urgency")
    if impact not in (1, 2, 3) or not isinstance(impact, int) or isinstance(impact, bool):
        return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": "Impact must be integer 1..3"}})
    if urgency not in (1, 2, 3) or not isinstance(urgency, int) or isinstance(urgency, bool):
        return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": "Urgency must be integer 1..3"}})

    related_to = body.get("related_to", None)

    priority = compute_priority(impact, urgency, rep_vip)
    ack_due, resolve_due = compute_due_dates(now, priority)

    t_id = str(uuid.uuid4())
    created_at_str = format_iso(now)
    ack_due_str = format_iso(ack_due)
    res_due_str = format_iso(resolve_due)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tickets (id, title, description, reporter_name, reporter_email, reporter_vip,
                            impact, urgency, priority, state, created_at, acknowledged_at,
                            resolved_at, closed_at, related_to, ack_due_at, resolve_due_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, NULL, NULL, NULL, ?, ?, ?)
    """, (t_id, title, desc, rep_name, rep_email, int(rep_vip), impact, urgency, priority,
          created_at_str, related_to, ack_due_str, res_due_str))
    conn.commit()

    cur.execute("SELECT * FROM tickets WHERE id = ?", (t_id,))
    row = cur.fetchone()
    conn.close()

    return row_to_ticket(row)

@app.get("/tickets")
def list_tickets(state: Optional[str] = None, priority: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if state:
        query += " AND state = ?"
        params.append(state)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [row_to_ticket(r) for r in rows]

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ticket not found"}})
    return row_to_ticket(row)

@app.get("/tickets/{ticket_id}/sla")
def get_ticket_sla(ticket_id: str, request: Request):
    try:
        now = get_request_now(request)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_clock", "message": "Malformed X-Test-Clock header"}})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ticket not found"}})

    ack_due = parse_iso(row["ack_due_at"])
    res_due = parse_iso(row["resolve_due_at"])
    priority = row["priority"]
    state = row["state"]

    # Ack breached evaluation
    if row["acknowledged_at"]:
        ack_breached = parse_iso(row["acknowledged_at"]) > ack_due
    else:
        ack_breached = now > ack_due

    # Resolve breached evaluation
    if state in ("resolved", "closed") and row["resolved_at"]:
        resolve_breached = parse_iso(row["resolved_at"]) > res_due
    else:
        resolve_breached = now > res_due

    # Paused evaluation
    if state in ("resolved", "closed"):
        paused = False
    elif priority == "P1":
        # C1 = wallclock -> P1 is never paused
        paused = False
    else:
        paused = not is_inside_business_hours(now)

    return {
        "priority": priority,
        "ack_due_at": row["ack_due_at"],
        "resolve_due_at": row["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused
    }

@app.post("/tickets/{ticket_id}/ack")
def ack_ticket(ticket_id: str, request: Request):
    try:
        now = get_request_now(request)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_clock", "message": "Malformed X-Test-Clock header"}})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ticket not found"}})

    if row["state"] != "new":
        conn.close()
        return JSONResponse(status_code=409, content={"error": {"code": "invalid_transition", "message": "Cannot ack ticket not in new state"}})

    now_str = format_iso(now)
    cur.execute("UPDATE tickets SET state = 'acknowledged', acknowledged_at = ? WHERE id = ?", (now_str, ticket_id))
    conn.commit()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    updated = cur.fetchone()
    conn.close()
    return row_to_ticket(updated)

@app.post("/tickets/{ticket_id}/start")
def start_ticket(ticket_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ticket not found"}})

    if row["state"] != "acknowledged":
        conn.close()
        return JSONResponse(status_code=409, content={"error": {"code": "invalid_transition", "message": "Cannot start ticket not in acknowledged state"}})

    cur.execute("UPDATE tickets SET state = 'in_progress' WHERE id = ?", (ticket_id,))
    conn.commit()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    updated = cur.fetchone()
    conn.close()
    return row_to_ticket(updated)

@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, request: Request):
    try:
        now = get_request_now(request)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_clock", "message": "Malformed X-Test-Clock header"}})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ticket not found"}})

    if row["state"] != "in_progress":
        conn.close()
        return JSONResponse(status_code=409, content={"error": {"code": "invalid_transition", "message": "Cannot resolve ticket not in in_progress state"}})

    now_str = format_iso(now)
    cur.execute("UPDATE tickets SET state = 'resolved', resolved_at = ? WHERE id = ?", (now_str, ticket_id))
    conn.commit()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    updated = cur.fetchone()
    conn.close()
    return row_to_ticket(updated)

@app.post("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, request: Request):
    try:
        now = get_request_now(request)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_clock", "message": "Malformed X-Test-Clock header"}})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ticket not found"}})

    if row["state"] != "resolved":
        conn.close()
        return JSONResponse(status_code=409, content={"error": {"code": "invalid_transition", "message": "Cannot close ticket not in resolved state"}})

    now_str = format_iso(now)
    cur.execute("UPDATE tickets SET state = 'closed', closed_at = ? WHERE id = ?", (now_str, ticket_id))
    conn.commit()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    updated = cur.fetchone()
    conn.close()
    return row_to_ticket(updated)

@app.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(ticket_id: str, request: Request):
    try:
        now = get_request_now(request)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_clock", "message": "Malformed X-Test-Clock header"}})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ticket not found"}})

    current_state = row["state"]

    # C2 = immutable: closed tickets answer 409 regardless of age
    if current_state == "closed":
        conn.close()
        return JSONResponse(status_code=409, content={"error": {"code": "ticket_closed", "message": "Closed tickets are immutable"}})

    if current_state != "resolved":
        conn.close()
        return JSONResponse(status_code=409, content={"error": {"code": "invalid_transition", "message": "Can only reopen resolved tickets"}})

    # Check 7-day window for resolved tickets
    resolved_at = parse_iso(row["resolved_at"])
    window_deadline = resolved_at + timedelta(days=7)

    if now > window_deadline:
        conn.close()
        return JSONResponse(status_code=409, content={"error": {"code": "reopen_window_expired", "message": "7-day reopen window expired"}})

    cur.execute("UPDATE tickets SET state = 'in_progress', resolved_at = NULL, closed_at = NULL WHERE id = ?", (ticket_id,))
    conn.commit()
    cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    updated = cur.fetchone()
    conn.close()
    return row_to_ticket(updated)

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def catch_all(path_name: str):
    return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": f"Path /{path_name} not found"}})