def next_action(status, completed_at, planned_date, today, threshold_days=2):
    if threshold_days < 1:
        raise ValueError("threshold_days must be at least 1")

    # Done sessions never get a nudge
    if status == "completed" or completed_at is not None:
        return "none"

    days_late = (today - planned_date).days

    if days_late < 0:
        return "none"             # planned for a future day
    if days_late == 0:
        return "gentle_remind"    # the planned day itself
    if days_late < threshold_days:
        return "remind"
    if days_late == threshold_days:
        return "shorter_session"
    return "adjust_plan"