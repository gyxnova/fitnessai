from datetime import date
import pytest
from missed_workout import next_action

planned_date = date(2026, 11, 10)


def test_future_session_gets_no_action():
    today = date(2026, 11, 9)
    assert next_action("planned", None, planned_date, today) == "none"


def test_planned_day_gets_gentle_remind():
    today = date(2026, 11, 10)
    assert next_action("planned", None, planned_date, today) == "gentle_remind"


def test_one_day_late_gets_remind():
    today = date(2026, 11, 11)
    assert next_action("planned", None, planned_date, today) == "remind"


def test_two_days_late_gets_shorter_session():
    today = date(2026, 11, 12)
    assert next_action("planned", None, planned_date, today) == "shorter_session"


def test_three_days_late_missed_status_gets_adjust_plan():
    today = date(2026, 11, 13)
    assert next_action("missed", None, planned_date, today) == "adjust_plan"


def test_completed_status_gets_no_action():
    today = date(2026, 11, 20)
    assert next_action("completed", None, planned_date, today) == "none"


def test_completed_at_filled_gets_no_action():
    today = date(2026, 11, 20)
    assert next_action("planned", date(2026, 11, 11), planned_date, today) == "none"


def test_threshold_is_a_real_setting():
    today = date(2026, 11, 12)
    assert next_action("planned", None, planned_date, today, threshold_days=3) == "remind"


def test_threshold_below_one_raises():
    today = date(2026, 11, 13)
    with pytest.raises(ValueError):
        next_action("planned", None, planned_date, today, threshold_days=0)