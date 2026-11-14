# ai-generated: 90% - comprehensive test suite for slaclock SLA arithmetic module to kill mutation testing mutants
from datetime import datetime, timedelta
import pytest
from slaclock import (
    OPENING,
    CLOSING,
    MAX_DAYS,
    WARNING_PERCENT,
    TARGETS,
    priority_of,
    targets,
    sla_state,
    is_business_time,
    add_business_minutes,
    business_minutes_between,
    escalation_tier,
    parse_duration,
)


# --- priority_of ---


def test_priority_of_valid_matrix():
    assert priority_of(1, 1, False) == "P1"
    assert priority_of(1, 2, False) == "P2"
    assert priority_of(2, 1, False) == "P2"
    assert priority_of(1, 3, False) == "P3"
    assert priority_of(2, 2, False) == "P3"
    assert priority_of(3, 1, False) == "P3"
    assert priority_of(2, 3, False) == "P4"
    assert priority_of(3, 2, False) == "P4"
    assert priority_of(3, 3, False) == "P4"


def test_priority_of_vip():
    # VIP keeps P1, P2; upgrades P3 and P4 to P2
    assert priority_of(1, 1, vip=True) == "P1"
    assert priority_of(1, 2, vip=True) == "P2"
    assert priority_of(2, 1, vip=True) == "P2"
    assert priority_of(1, 3, vip=True) == "P2"
    assert priority_of(2, 2, vip=True) == "P2"
    assert priority_of(3, 1, vip=True) == "P2"
    assert priority_of(2, 3, vip=True) == "P2"
    assert priority_of(3, 2, vip=True) == "P2"
    assert priority_of(3, 3, vip=True) == "P2"


@pytest.mark.parametrize("impact,urgency", [
    (0, 1), (4, 1), (1, 0), (1, 4), (-1, 2), (2, -1),
    (2.0, 1), (1, 2.0), (True, 1), (1, False), ("1", 2), (2, "1"),
    (None, 1), (1, None)
])
def test_priority_of_invalid(impact, urgency):
    with pytest.raises(ValueError):
        priority_of(impact, urgency)


# --- targets ---


def test_targets_lookup():
    assert targets("P1") == (15, 240)
    assert targets("P2") == (60, 480)
    assert targets("P3") == (240, 1440)
    assert targets("P4") == (480, 4320)


@pytest.mark.parametrize("invalid", ["p1", "p2", "P5", " P1", "P1 ", "", "P0", "P1\n", None, 1])
def test_targets_invalid(invalid):
    with pytest.raises(ValueError):
        targets(invalid)


# --- sla_state ---


def test_sla_state_boundaries():
    # target = 100: 75% is 75
    assert sla_state(0, 100) == "ok"
    assert sla_state(74, 100) == "ok"
    assert sla_state(75, 100) == "warning"
    assert sla_state(99, 100) == "warning"
    assert sla_state(100, 100) == "warning"  # equality is not a breach
    assert sla_state(101, 100) == "breached"

    # target = 15: 75% is 11.25 -> 11 ok, 12 warning
    assert sla_state(11, 15) == "ok"
    assert sla_state(12, 15) == "warning"
    assert sla_state(15, 15) == "warning"
    assert sla_state(16, 15) == "breached"

    # target = 4: 75% is 3.0 -> 2 ok, 3 warning
    assert sla_state(2, 4) == "ok"
    assert sla_state(3, 4) == "warning"
    assert sla_state(4, 4) == "warning"
    assert sla_state(5, 4) == "breached"


@pytest.mark.parametrize("elapsed,target", [
    (-1, 10), (-5, 10), (0, 0), (10, 0), (5, -1), (-1, -1)
])
def test_sla_state_invalid(elapsed, target):
    with pytest.raises(ValueError):
        sla_state(elapsed, target)


# --- is_business_time ---


def test_is_business_time_boundaries():
    # Monday = 2026-10-12
    # 07:59 outside, 08:00 inside, 15:59 inside, 16:00 outside
    assert not is_business_time(datetime(2026, 10, 12, 7, 59))
    assert is_business_time(datetime(2026, 10, 12, 8, 0))
    assert is_business_time(datetime(2026, 10, 12, 12, 30))
    assert is_business_time(datetime(2026, 10, 12, 15, 59))
    assert not is_business_time(datetime(2026, 10, 12, 16, 0))
    assert not is_business_time(datetime(2026, 10, 12, 16, 1))
    assert not is_business_time(datetime(2026, 10, 12, 0, 0))
    assert not is_business_time(datetime(2026, 10, 12, 23, 59))

    # Friday = 2026-10-16
    assert is_business_time(datetime(2026, 10, 16, 8, 0))
    assert is_business_time(datetime(2026, 10, 16, 15, 59))
    assert not is_business_time(datetime(2026, 10, 16, 16, 0))

    # Saturday = 2026-10-17, Sunday = 2026-10-18
    assert not is_business_time(datetime(2026, 10, 17, 10, 0))
    assert not is_business_time(datetime(2026, 10, 18, 10, 0))


# --- add_business_minutes ---


def test_add_business_minutes_same_day():
    # Monday 08:00 + 60 min -> Monday 09:00
    mon = datetime(2026, 10, 12, 8, 0)
    assert add_business_minutes(mon, 60) == datetime(2026, 10, 12, 9, 0)

    # Monday 08:00 + 480 min (full day) -> Monday 16:00
    assert add_business_minutes(mon, 480) == datetime(2026, 10, 12, 16, 0)


def test_add_business_minutes_outside_hours_start():
    # Monday before opening 07:30 + 30 min -> Monday 08:30
    assert add_business_minutes(datetime(2026, 10, 12, 7, 30), 30) == datetime(2026, 10, 12, 8, 30)
    # Monday before opening 07:30 + 0 min -> Monday 08:00
    assert add_business_minutes(datetime(2026, 10, 12, 7, 30), 0) == datetime(2026, 10, 12, 8, 0)

    # Monday inside hours 09:15 + 0 min -> Monday 09:15
    assert add_business_minutes(datetime(2026, 10, 12, 9, 15, 45, 123), 0) == datetime(2026, 10, 12, 9, 15)

    # Monday evening 17:00 + 60 min -> Tuesday 09:00
    assert add_business_minutes(datetime(2026, 10, 12, 17, 0), 60) == datetime(2026, 10, 13, 9, 0)

    # Friday evening 16:00 + 60 min -> Monday 09:00
    assert add_business_minutes(datetime(2026, 10, 16, 16, 0), 60) == datetime(2026, 10, 19, 9, 0)

    # Weekend Saturday 12:00 + 60 min -> Monday 09:00
    assert add_business_minutes(datetime(2026, 10, 17, 12, 0), 60) == datetime(2026, 10, 19, 9, 0)
    # Sunday 22:00 + 0 min -> Monday 08:00
    assert add_business_minutes(datetime(2026, 10, 18, 22, 0), 0) == datetime(2026, 10, 19, 8, 0)


def test_add_business_minutes_multiday():
    # Monday 15:00 + 120 min -> 60 min on Mon (to 16:00), 60 min on Tue (to 09:00)
    assert add_business_minutes(datetime(2026, 10, 12, 15, 0), 120) == datetime(2026, 10, 13, 9, 0)

    # Friday 15:30 + 60 min -> 30 min on Fri, 30 min on Mon 08:30
    assert add_business_minutes(datetime(2026, 10, 16, 15, 30), 60) == datetime(2026, 10, 19, 8, 30)


def test_add_business_minutes_invalid():
    with pytest.raises(ValueError):
        add_business_minutes(datetime(2026, 10, 12, 10, 0), -1)

    # Exceeding MAX_DAYS (366)
    with pytest.raises(ValueError):
        add_business_minutes(datetime(2026, 10, 12, 10, 0), 367 * 480)


# --- business_minutes_between ---


def test_business_minutes_between_cases():
    mon_start = datetime(2026, 10, 12, 8, 0)
    mon_end = datetime(2026, 10, 12, 10, 30)
    assert business_minutes_between(mon_start, mon_end) == 150
    assert business_minutes_between(mon_start, mon_start) == 0

    # Outside hours before opening and after closing
    assert business_minutes_between(datetime(2026, 10, 12, 6, 0), datetime(2026, 10, 12, 8, 0)) == 0
    assert business_minutes_between(datetime(2026, 10, 12, 16, 0), datetime(2026, 10, 12, 20, 0)) == 0
    assert business_minutes_between(datetime(2026, 10, 12, 6, 0), datetime(2026, 10, 12, 18, 0)) == 480

    # Weekend
    assert business_minutes_between(datetime(2026, 10, 17, 8, 0), datetime(2026, 10, 18, 16, 0)) == 0

    # Across weekend: Friday 15:00 to Monday 09:00 -> 60 min Fri + 60 min Mon = 120 min
    fri = datetime(2026, 10, 16, 15, 0)
    mon_next = datetime(2026, 10, 19, 9, 0)
    assert business_minutes_between(fri, mon_next) == 120


def test_business_minutes_between_roundtrip():
    # Property test: business_minutes_between(start, add_business_minutes(start, minutes)) == minutes
    for start_hour in [6, 8, 12, 15, 17, 22]:
        for minutes in [0, 1, 30, 100, 480, 1000]:
            start = datetime(2026, 10, 12, start_hour, 15)
            due = add_business_minutes(start, minutes)
            assert business_minutes_between(start, due) == minutes


def test_business_minutes_between_invalid():
    # end before start
    with pytest.raises(ValueError):
        business_minutes_between(datetime(2026, 10, 12, 10, 0), datetime(2026, 10, 12, 9, 0))

    # span > MAX_DAYS
    with pytest.raises(ValueError):
        business_minutes_between(datetime(2026, 1, 1, 8, 0), datetime(2028, 1, 1, 8, 0))


# --- escalation_tier ---


def test_escalation_tier_matrix():
    # P1: base 1, breached +2, reopens>=2 +1 -> capped at 3
    assert escalation_tier("P1", False, 0) == 1
    assert escalation_tier("P1", False, 1) == 1
    assert escalation_tier("P1", False, 2) == 2
    assert escalation_tier("P1", True, 0) == 3   # 1 + 2 = 3
    assert escalation_tier("P1", True, 2) == 3   # min(1+2+1, 3) = 3

    # P2: base 1, breached +1, reopens>=2 +1
    assert escalation_tier("P2", False, 0) == 1
    assert escalation_tier("P2", False, 1) == 1
    assert escalation_tier("P2", False, 2) == 2
    assert escalation_tier("P2", True, 0) == 2
    assert escalation_tier("P2", True, 1) == 2
    assert escalation_tier("P2", True, 2) == 3

    # P3: base 0, breached +1, reopens>=2 +1
    assert escalation_tier("P3", False, 0) == 0
    assert escalation_tier("P3", False, 1) == 0
    assert escalation_tier("P3", False, 2) == 1
    assert escalation_tier("P3", True, 0) == 1
    assert escalation_tier("P3", True, 1) == 1
    assert escalation_tier("P3", True, 2) == 2

    # P4: base 0, breached +1, reopens>=2 +1
    assert escalation_tier("P4", False, 0) == 0
    assert escalation_tier("P4", False, 1) == 0
    assert escalation_tier("P4", False, 2) == 1
    assert escalation_tier("P4", True, 0) == 1
    assert escalation_tier("P4", True, 1) == 1
    assert escalation_tier("P4", True, 2) == 2


@pytest.mark.parametrize("priority,reopens", [
    ("p1", 0), ("P5", 0), ("invalid", 0), ("", 0),
    ("P1", -1), ("P2", -5), ("P3", -1), ("P4", -2)
])
def test_escalation_tier_invalid(priority, reopens):
    with pytest.raises(ValueError):
        escalation_tier(priority, False, reopens)


# --- parse_duration ---


def test_parse_duration_valid():
    assert parse_duration("90m") == 90
    assert parse_duration("4h") == 240
    assert parse_duration("1h30m") == 90
    assert parse_duration("2d") == 2880
    assert parse_duration("1d4h") == 1680
    assert parse_duration("1d0h5m") == 1445
    assert parse_duration("1h59m") == 119
    assert parse_duration("60m") == 60
    assert parse_duration("0h60m") == 60
    assert parse_duration("0d0h60m") == 60
    assert parse_duration("  2h30m  ") == 150


@pytest.mark.parametrize("text", [
    "", "   ", "0m", "0h", "0d", "0d0h0m", "1.5h", "30m1h", "-5m", "1 h", "1h 30m",
    "1h60m", "2d60m", "1d2h65m", "abc", "2d1d", "4h2h", "10m5m", "d", "h", "m"
])
def test_parse_duration_invalid(text):
    with pytest.raises(ValueError):
        parse_duration(text)
