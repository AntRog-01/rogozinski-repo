# ai-generated: 90% - unit and integration tests for DORA metrics engine
import pytest
from src.dora import (
    validate_and_compute_dora,
    compute_median,
    round_half_up,
    ValidationError
)

def test_round_half_up():
    assert round_half_up(1.5, 0) == 2
    assert round_half_up(1.4, 0) == 1
    assert round_half_up(2.5, 0) == 3
    assert round_half_up(0.1234567, 6) == 0.123457

def test_compute_median():
    assert compute_median([]) is None
    assert compute_median([10]) == 10
    assert compute_median([10, 20, 30]) == 20
    assert compute_median([10, 20]) == 15
    assert compute_median([10, 25]) == 18 # 17.5 rounds half up to 18

def test_empty_log():
    body = {
        "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
        "events": []
    }
    res = validate_and_compute_dora(body)
    assert res["spec_version"] == "1.0.0"
    assert res["deployment_frequency_per_day"] == 0.0
    assert res["change_lead_time_seconds_p50"] is None
    assert res["failed_deployment_recovery_time_seconds_p50"] is None
    assert res["change_fail_rate"] is None
    assert res["deployment_rework_rate"] is None
    assert res["counts"]["deployments"] == 0
    assert res["counts"]["changes"] == 0
    assert res["anomalies"]["negative_lead_time_pairs"] == 0
    assert res["ground_truth"]["changes_delivered"] == 0

def test_invalid_window_order():
    body = {
        "window": {"from": "2026-09-22T00:00:00Z", "to": "2026-09-01T00:00:00Z"},
        "events": []
    }
    with pytest.raises(ValidationError):
        validate_and_compute_dora(body)

def test_missing_window():
    body = {"events": []}
    with pytest.raises(ValidationError):
        validate_and_compute_dora(body)

def test_missing_events():
    body = {"window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}}
    with pytest.raises(ValidationError):
        validate_and_compute_dora(body)

def test_duplicate_events_ingested_once():
    c1 = {"event_id": "c1", "type": "commit", "at": "2026-09-01T10:00:00Z", "sha": "s1", "branch": "main", "change_id": "CH1", "reverts": None}
    d1 = {"event_id": "d1", "type": "deployment", "at": "2026-09-02T10:00:00Z", "deployment_id": "DEP1", "environment": "production", "outcome": "success", "commits": ["s1"], "unplanned": False, "caused_by": None}
    body = {
        "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
        "events": [c1, c1, d1, d1]
    }
    res = validate_and_compute_dora(body)
    assert res["counts"]["deployments"] == 1
    assert res["counts"]["lead_time_pairs"] == 1

def test_negative_lead_time_clamping_e1():
    # commit timestamp is after deployment timestamp
    c1 = {"event_id": "c1", "type": "commit", "at": "2026-09-05T12:00:00Z", "sha": "s1", "branch": "main", "change_id": "CH1", "reverts": None}
    d1 = {"event_id": "d1", "type": "deployment", "at": "2026-09-05T10:00:00Z", "deployment_id": "DEP1", "environment": "production", "outcome": "success", "commits": ["s1"], "unplanned": False, "caused_by": None}
    body = {
        "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
        "events": [c1, d1]
    }
    res = validate_and_compute_dora(body)
    assert res["anomalies"]["negative_lead_time_pairs"] == 1
    assert res["change_lead_time_seconds_p50"] == 0

def test_revert_chains_collapsed_e2():
    c1 = {"event_id": "c1", "type": "commit", "at": "2026-09-01T10:00:00Z", "sha": "s1", "branch": "main", "change_id": "CH1", "reverts": None}
    c2 = {"event_id": "c2", "type": "commit", "at": "2026-09-01T11:00:00Z", "sha": "s2", "branch": "main", "change_id": None, "reverts": "s1"}
    c3 = {"event_id": "c3", "type": "commit", "at": "2026-09-01T12:00:00Z", "sha": "s3", "branch": "main", "change_id": None, "reverts": "s2"}
    body = {
        "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
        "events": [c1, c2, c3]
    }
    res = validate_and_compute_dora(body)
    assert res["anomalies"]["revert_chains_collapsed"] == 2
    assert res["counts"]["changes"] == 1

def test_commits_never_on_main_e3():
    c1 = {"event_id": "c1", "type": "commit", "at": "2026-09-01T10:00:00Z", "sha": "s1", "branch": "hotfix/1", "change_id": "CH1", "reverts": None}
    d1 = {"event_id": "d1", "type": "deployment", "at": "2026-09-02T10:00:00Z", "deployment_id": "DEP1", "environment": "production", "outcome": "success", "commits": ["s1"], "unplanned": False, "caused_by": None}
    body = {
        "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
        "events": [c1, d1]
    }
    res = validate_and_compute_dora(body)
    assert res["anomalies"]["commits_never_on_main"] == 1

def test_deployments_without_commits_e4():
    d1 = {"event_id": "d1", "type": "deployment", "at": "2026-09-02T10:00:00Z", "deployment_id": "DEP1", "environment": "production", "outcome": "success", "commits": [], "unplanned": False, "caused_by": None}
    body = {
        "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
        "events": [d1]
    }
    res = validate_and_compute_dora(body)
    assert res["anomalies"]["deployments_without_commits"] == 1
    assert res["counts"]["deployments"] == 1
    assert res["counts"]["lead_time_pairs"] == 0

def test_open_and_recovered_failures_e5():
    d1 = {"event_id": "d1", "type": "deployment", "at": "2026-09-02T10:00:00Z", "deployment_id": "DEP1", "environment": "production", "outcome": "failure", "commits": [], "unplanned": False, "caused_by": None}
    d2 = {"event_id": "d2", "type": "deployment", "at": "2026-09-03T10:00:00Z", "deployment_id": "DEP2", "environment": "production", "outcome": "failure", "commits": [], "unplanned": False, "caused_by": None}
    i1 = {"event_id": "i1", "type": "incident", "at": "2026-09-02T11:00:00Z", "incident_id": "INC1", "phase": "opened", "deployments": ["DEP1"]}
    i2 = {"event_id": "i2", "type": "incident", "at": "2026-09-02T12:00:00Z", "incident_id": "INC1", "phase": "resolved", "deployments": ["DEP1"]}
    body = {
        "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
        "events": [d1, d2, i1, i2]
    }
    res = validate_and_compute_dora(body)
    assert res["counts"]["recovered_failures"] == 1
    assert res["counts"]["open_failures"] == 1
    assert res["failed_deployment_recovery_time_seconds_p50"] == 7200
