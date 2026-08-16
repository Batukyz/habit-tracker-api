from datetime import date


def _periods(dates: list[date], frequency: str) -> list[date]:
    """Reduces raw log dates to one representative date per period (day or ISO week)."""
    if frequency == "weekly":
        weeks = {d.isocalendar()[:2] for d in dates}
        return sorted(date.fromisocalendar(year, week, 1) for year, week in weeks)
    return sorted(set(dates))


def longest_streak(dates: list[date], frequency: str) -> int:
    periods = _periods(dates, frequency)
    if not periods:
        return 0

    step_days = 7 if frequency == "weekly" else 1
    longest = current = 1
    for previous, current_period in zip(periods, periods[1:]):
        if (current_period - previous).days == step_days:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def completion_rate(dates: list[date], frequency: str, since: date, until: date) -> float:
    """Percentage of expected periods (since the habit's creation) that have a log."""
    if until < since:
        return 0.0

    if frequency == "weekly":
        since_monday = date.fromisocalendar(*since.isocalendar()[:2], 1)
        until_monday = date.fromisocalendar(*until.isocalendar()[:2], 1)
        expected_periods = (until_monday - since_monday).days // 7 + 1
    else:
        expected_periods = (until - since).days + 1

    completed_periods = len(_periods(dates, frequency))
    return round(min(completed_periods, expected_periods) / expected_periods * 100, 1)
