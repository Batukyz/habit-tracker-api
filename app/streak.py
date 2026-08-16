from datetime import date


def calculate_streak(dates: list[date], frequency: str) -> int:
    """Counts the consecutive daily/weekly periods ending at the most recent log."""
    if not dates:
        return 0

    if frequency == "weekly":
        periods = sorted({d.isocalendar()[:2] for d in dates}, reverse=True)
        mondays = [date.fromisocalendar(year, week, 1) for year, week in periods]
        step_days = 7
    else:
        mondays = sorted(set(dates), reverse=True)
        step_days = 1

    streak = 1
    for previous, current in zip(mondays, mondays[1:]):
        if (previous - current).days == step_days:
            streak += 1
        else:
            break
    return streak
