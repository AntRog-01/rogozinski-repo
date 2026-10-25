# ai-generated: 85% - DORA metrics engine and event lifecycle stream implementation
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

def round_half_up(val: Optional[float], decimals: int = 0) -> Optional[float]:
    if val is None:
        return None
    d = Decimal(str(val))
    if decimals == 0:
        return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    else:
        fmt = '0.' + '0' * decimals
        return float(d.quantize(Decimal(fmt), rounding=ROUND_HALF_UP))

def compute_median(values: List[int]) -> Optional[int]:
    if not values:
        return None
    sorted_v = sorted(values)
    n = len(sorted_v)
    if n % 2 == 1:
        return sorted_v[n // 2]
    else:
        mid = (Decimal(str(sorted_v[n // 2 - 1])) + Decimal(str(sorted_v[n // 2]))) / Decimal('2')
        return int(mid.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def parse_iso(iso_str: str) -> datetime:
    if not isinstance(iso_str, str):
        raise ValueError("Timestamp must be a string")
    s = iso_str.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    return datetime.fromisoformat(s)

class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

def validate_and_compute_dora(body: Any) -> Dict[str, Any]:
    if not isinstance(body, dict):
        raise ValidationError("invalid_body", "Request body must be a JSON object")

    if "window" not in body or not isinstance(body["window"], dict):
        raise ValidationError("missing_window", "window object is required")

    window = body["window"]
    if "from" not in window or "to" not in window:
        raise ValidationError("invalid_window", "window must specify 'from' and 'to'")

    try:
        w_from = parse_iso(window["from"])
        w_to = parse_iso(window["to"])
    except Exception:
        raise ValidationError("invalid_window", "window dates must be valid RFC 3339 timestamps")

    if w_to <= w_from:
        raise ValidationError("invalid_window", "'to' must be strictly after 'from'")

    if "events" not in body or not isinstance(body["events"], list):
        raise ValidationError("invalid_events", "events must be an array")

    raw_events = body["events"]

    # 1. Syntactic validation of each raw event
    for idx, e in enumerate(raw_events):
        if not isinstance(e, dict):
            raise ValidationError("malformed_log", f"Event at index {idx} must be an object")
        eid = e.get("event_id")
        if not isinstance(eid, str) or not (1 <= len(eid) <= 64):
            raise ValidationError("malformed_log", f"Invalid event_id at index {idx}")
        etype = e.get("type")
        if etype not in ("commit", "deployment", "incident"):
            raise ValidationError("malformed_log", f"Invalid event type at index {idx}")
        at_str = e.get("at")
        if not isinstance(at_str, str):
            raise ValidationError("malformed_log", f"Invalid event timestamp at index {idx}")
        try:
            parse_iso(at_str)
        except Exception:
            raise ValidationError("malformed_log", f"Non-RFC3339 timestamp at index {idx}")

    # R-05: Deduplicate events by event_id (first occurrence wins, duplicates ignored and not an error)
    events: List[Dict[str, Any]] = []
    seen_event_ids = set()
    for e in raw_events:
        eid = e["event_id"]
        if eid not in seen_event_ids:
            seen_event_ids.add(eid)
            events.append(e)

    # 2. Well-formedness checks on deduplicated events
    commits_by_sha: Dict[str, Dict[str, Any]] = {}
    commits_list: List[Dict[str, Any]] = []
    deployments_by_id: Dict[str, Dict[str, Any]] = {}
    deployments_list: List[Dict[str, Any]] = []
    incidents_by_id: Dict[str, Dict[str, Any]] = {}

    for e in events:
        etype = e["type"]
        at = parse_iso(e["at"])
        e["_parsed_at"] = at

        if etype == "commit":
            sha = e.get("sha")
            if not isinstance(sha, str) or not sha:
                raise ValidationError("malformed_log", "Commit must have non-empty sha")
            if sha in commits_by_sha:
                raise ValidationError("malformed_log", f"Duplicate commit sha: {sha}")
            reverts = e.get("reverts")
            change_id = e.get("change_id")
            # a commit carries a change_id exactly when reverts is null
            if reverts is not None:
                if not isinstance(reverts, str) or not reverts:
                    raise ValidationError("malformed_log", "reverts must be string or null")
                if change_id is not None:
                    raise ValidationError("malformed_log", "revert commit must have null change_id")
            else:
                if not isinstance(change_id, str) or not change_id:
                    raise ValidationError("malformed_log", "commit without reverts must have change_id")
            commits_by_sha[sha] = e
            commits_list.append(e)

        elif etype == "deployment":
            did = e.get("deployment_id")
            if not isinstance(did, str) or not did:
                raise ValidationError("malformed_log", "Deployment must have deployment_id")
            env = e.get("environment")
            if not isinstance(env, str):
                raise ValidationError("malformed_log", "Deployment must have environment")
            outcome = e.get("outcome")
            if outcome not in ("success", "failure"):
                raise ValidationError("malformed_log", "Deployment outcome must be success or failure")
            commits = e.get("commits")
            if not isinstance(commits, list):
                raise ValidationError("malformed_log", "Deployment commits must be a list")
            deployments_by_id[did] = e
            deployments_list.append(e)

        elif etype == "incident":
            iid = e.get("incident_id")
            if not isinstance(iid, str) or not iid:
                raise ValidationError("malformed_log", "Incident must have incident_id")
            phase = e.get("phase")
            if phase not in ("opened", "resolved"):
                raise ValidationError("malformed_log", "Incident phase must be opened or resolved")
            deps = e.get("deployments")
            if not isinstance(deps, list):
                raise ValidationError("malformed_log", "Incident deployments must be a list")

            if iid not in incidents_by_id:
                incidents_by_id[iid] = {"opened": None, "resolved": None, "deployments": set()}
            inc_entry = incidents_by_id[iid]
            if phase == "opened":
                if inc_entry["opened"] is not None:
                    raise ValidationError("malformed_log", f"Incident {iid} opened more than once")
                inc_entry["opened"] = at
            elif phase == "resolved":
                if inc_entry["resolved"] is not None:
                    raise ValidationError("malformed_log", f"Incident {iid} resolved more than once")
                inc_entry["resolved"] = at

            for d_ref in deps:
                if not isinstance(d_ref, str):
                    raise ValidationError("malformed_log", "Incident deployment ref must be string")
                inc_entry["deployments"].add(d_ref)

    # Cross-reference validation
    for c in commits_list:
        rev = c.get("reverts")
        if rev and rev not in commits_by_sha:
            raise ValidationError("malformed_log", f"Reverts sha {rev} not found in commits")

    for d in deployments_list:
        for c_sha in d.get("commits", []):
            if c_sha not in commits_by_sha:
                raise ValidationError("malformed_log", f"Deployment commit {c_sha} not found in commits")
        cb = d.get("caused_by")
        if cb and cb not in incidents_by_id:
            raise ValidationError("malformed_log", f"Deployment caused_by {cb} not found in incidents")

    for iid, inc_entry in incidents_by_id.items():
        if inc_entry["resolved"] is not None and inc_entry["opened"] is None:
            raise ValidationError("malformed_log", f"Incident {iid} resolved without being opened")
        for dep_ref in inc_entry["deployments"]:
            if dep_ref not in deployments_by_id:
                raise ValidationError("malformed_log", f"Incident deployment {dep_ref} not found in deployments")

    # If log has zero events
    if not events:
        return {
            "spec_version": "1.0.0",
            "window": {"from": window["from"], "to": window["to"]},
            "deployment_frequency_per_day": 0.0,
            "change_lead_time_seconds_p50": None,
            "failed_deployment_recovery_time_seconds_p50": None,
            "change_fail_rate": None,
            "deployment_rework_rate": None,
            "counts": {
                "deployments": 0,
                "successful_deployments": 0,
                "failed_deployments": 0,
                "recovered_failures": 0,
                "open_failures": 0,
                "rework_deployments": 0,
                "lead_time_pairs": 0,
                "changes": 0
            },
            "anomalies": {
                "negative_lead_time_pairs": 0,
                "deployments_without_commits": 0,
                "commits_never_on_main": 0,
                "revert_chains_collapsed": 0,
                "overlapping_incident_pairs": 0
            },
            "ground_truth": {
                "changes_delivered": 0,
                "true_change_lead_time_seconds_p50": None
            }
        }

    # R-06: Resolve change_id transitively
    def get_change_id(sha: str) -> Optional[str]:
        curr = commits_by_sha.get(sha)
        visited = set()
        while curr:
            if curr["sha"] in visited:
                break
            visited.add(curr["sha"])
            if curr.get("reverts"):
                curr = commits_by_sha.get(curr["reverts"])
            else:
                return curr.get("change_id")
        return None

    for c in commits_list:
        c["_resolved_change_id"] = get_change_id(c["sha"])

    # R-07: Change's first commit instant (anywhere in the log)
    change_first_commit: Dict[str, datetime] = {}
    for c in commits_list:
        chg = c["_resolved_change_id"]
        if chg:
            if chg not in change_first_commit or c["_parsed_at"] < change_first_commit[chg]:
                change_first_commit[chg] = c["_parsed_at"]

    # Filter deployments by R-01 (production only) and R-02 (w_from <= at < w_to)
    prod_deployments_in_window = [
        d for d in deployments_list
        if d.get("environment") == "production" and w_from <= d["_parsed_at"] < w_to
    ]
    prod_deployments_in_window.sort(key=lambda d: d["_parsed_at"])

    window_days = (w_to - w_from).total_seconds() / 86400.0
    dep_count = len(prod_deployments_in_window)
    if window_days > 0:
        deployment_frequency_per_day = round_half_up(dep_count / window_days, 6)
    else:
        deployment_frequency_per_day = 0.0

    seen_shas_in_success_deps = set()
    lead_time_pairs: List[int] = []
    negative_lead_time_pairs = 0
    seen_changes_delivered: Dict[str, datetime] = {}

    successful_deployments = 0
    failed_deployments = 0
    rework_deployments = 0
    deployments_without_commits = 0
    shas_in_window_deps = set()

    for d in prod_deployments_in_window:
        is_success = (d.get("outcome") == "success")
        is_failure = (d.get("outcome") == "failure")
        if is_success:
            successful_deployments += 1
        elif is_failure:
            failed_deployments += 1

        if d.get("unplanned") and d.get("caused_by") is not None:
            rework_deployments += 1

        d_commits = d.get("commits", [])
        if len(d_commits) == 0:
            deployments_without_commits += 1

        for sha in d_commits:
            shas_in_window_deps.add(sha)
            if is_success and sha not in seen_shas_in_success_deps:
                seen_shas_in_success_deps.add(sha)
                c = commits_by_sha.get(sha)
                if c:
                    diff_sec = (d["_parsed_at"] - c["_parsed_at"]).total_seconds()
                    if diff_sec < 0:
                        negative_lead_time_pairs += 1
                        diff_sec = 0
                    lead_time_pairs.append(round_half_up(diff_sec, 0))

                chg = c.get("_resolved_change_id") if c else None
                if chg and chg not in seen_changes_delivered:
                    seen_changes_delivered[chg] = d["_parsed_at"]

    change_lead_time_seconds_p50 = compute_median(lead_time_pairs)

    # R-12: failed_deployment_recovery_time_seconds_p50
    recovered_failures = 0
    open_failures = 0
    recovery_times: List[int] = []

    for d in prod_deployments_in_window:
        if d.get("outcome") == "failure":
            dep_id = d["deployment_id"]
            covering_candidates = []
            for iid, inc in incidents_by_id.items():
                if dep_id in inc["deployments"] and inc["opened"] is not None:
                    covering_candidates.append((inc["opened"], iid, inc))
            if covering_candidates:
                covering_candidates.sort(key=lambda x: (x[0], x[1]))
                best_inc = covering_candidates[0][2]
                if best_inc["resolved"] is not None:
                    diff_sec = (best_inc["resolved"] - d["_parsed_at"]).total_seconds()
                    diff_sec = max(0, diff_sec)
                    recovery_times.append(round_half_up(diff_sec, 0))
                    recovered_failures += 1
                else:
                    open_failures += 1
            else:
                open_failures += 1

    failed_deployment_recovery_time_seconds_p50 = compute_median(recovery_times)

    change_fail_rate = round_half_up(failed_deployments / dep_count, 6) if dep_count > 0 else None
    deployment_rework_rate = round_half_up(rework_deployments / dep_count, 6) if dep_count > 0 else None

    # E3: commits_never_on_main
    commits_never_on_main = sum(
        1 for sha in shas_in_window_deps
        if commits_by_sha.get(sha, {}).get("branch") != "main"
    )

    # E2: revert_chains_collapsed: number of commits whose reverts is non-null
    revert_chains_collapsed = sum(1 for c in commits_list if c.get("reverts") is not None)

    # E6: overlapping_incident_pairs
    inc_intervals = []
    for iid, inc in incidents_by_id.items():
        if inc["opened"] is not None:
            end = inc["resolved"] if inc["resolved"] is not None else w_to
            inc_intervals.append((iid, inc["opened"], end))

    overlapping_incident_pairs = 0
    for i in range(len(inc_intervals)):
        for j in range(i + 1, len(inc_intervals)):
            _, a_start, a_end = inc_intervals[i]
            _, b_start, b_end = inc_intervals[j]
            if a_start < b_end and b_start < a_end:
                overlapping_incident_pairs += 1

    # Ground truth R-16, R-17
    changes_delivered = len(seen_changes_delivered)
    gt_lead_times: List[int] = []
    for chg, first_dep_at in seen_changes_delivered.items():
        first_commit_at = change_first_commit[chg]
        diff_sec = (first_dep_at - first_commit_at).total_seconds()
        diff_sec = max(0, diff_sec)
        gt_lead_times.append(round_half_up(diff_sec, 0))

    true_change_lead_time_seconds_p50 = compute_median(gt_lead_times)

    all_changes = set(c["_resolved_change_id"] for c in commits_list if c["_resolved_change_id"] is not None)

    return {
        "spec_version": "1.0.0",
        "window": {
            "from": window["from"],
            "to": window["to"]
        },
        "deployment_frequency_per_day": deployment_frequency_per_day,
        "change_lead_time_seconds_p50": change_lead_time_seconds_p50,
        "failed_deployment_recovery_time_seconds_p50": failed_deployment_recovery_time_seconds_p50,
        "change_fail_rate": change_fail_rate,
        "deployment_rework_rate": deployment_rework_rate,
        "counts": {
            "deployments": dep_count,
            "successful_deployments": successful_deployments,
            "failed_deployments": failed_deployments,
            "recovered_failures": recovered_failures,
            "open_failures": open_failures,
            "rework_deployments": rework_deployments,
            "lead_time_pairs": len(lead_time_pairs),
            "changes": len(all_changes)
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_lead_time_pairs,
            "deployments_without_commits": deployments_without_commits,
            "commits_never_on_main": commits_never_on_main,
            "revert_chains_collapsed": revert_chains_collapsed,
            "overlapping_incident_pairs": overlapping_incident_pairs
        },
        "ground_truth": {
            "changes_delivered": changes_delivered,
            "true_change_lead_time_seconds_p50": true_change_lead_time_seconds_p50
        }
    }

def get_ticket_events(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT id, priority, created_at, acknowledged_at, resolved_at, closed_at FROM tickets")
    rows = cur.fetchall()
    
    events: List[Dict[str, Any]] = []
    for r in rows:
        tid = r["id"]
        prio = r["priority"]
        if r["created_at"]:
            events.append({"ticket_id": tid, "at": r["created_at"], "phase": "created", "priority": prio, "state": "new"})
        if r["acknowledged_at"]:
            events.append({"ticket_id": tid, "at": r["acknowledged_at"], "phase": "acknowledged", "priority": prio, "state": "acknowledged"})
        if r["resolved_at"]:
            events.append({"ticket_id": tid, "at": r["resolved_at"], "phase": "resolved", "priority": prio, "state": "resolved"})
        if r["closed_at"]:
            events.append({"ticket_id": tid, "at": r["closed_at"], "phase": "closed", "priority": prio, "state": "closed"})

    events.sort(key=lambda x: (x["at"], x["ticket_id"]))
    return events
