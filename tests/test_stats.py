from datetime import date

from app.stats import completion_rate, longest_streak


def test_longest_streak_no_logs():
    assert longest_streak([], "daily") == 0


def test_longest_streak_daily_picks_longest_run():
    dates = [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 1, 10),
        date(2026, 1, 11),
    ]
    assert longest_streak(dates, "daily") == 3


def test_longest_streak_weekly_picks_longest_run():
    dates = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 2, 2)]
    assert longest_streak(dates, "weekly") == 2


def test_completion_rate_full():
    dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    rate = completion_rate(dates, "daily", since=date(2026, 1, 1), until=date(2026, 1, 3))
    assert rate == 100.0


def test_completion_rate_half():
    dates = [date(2026, 1, 1), date(2026, 1, 3)]
    rate = completion_rate(dates, "daily", since=date(2026, 1, 1), until=date(2026, 1, 4))
    assert rate == 50.0


def test_completion_rate_no_logs():
    rate = completion_rate([], "daily", since=date(2026, 1, 1), until=date(2026, 1, 5))
    assert rate == 0.0
