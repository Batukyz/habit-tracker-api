from datetime import date

from app.streak import calculate_streak


def test_calculate_streak_no_logs():
    assert calculate_streak([], "daily") == 0


def test_calculate_streak_daily_consecutive():
    dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    assert calculate_streak(dates, "daily") == 3


def test_calculate_streak_daily_with_gap():
    dates = [date(2026, 1, 1), date(2026, 1, 3)]
    assert calculate_streak(dates, "daily") == 1


def test_calculate_streak_daily_ignores_duplicates():
    dates = [date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 2)]
    assert calculate_streak(dates, "daily") == 2


def test_calculate_streak_weekly_consecutive():
    dates = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]
    assert calculate_streak(dates, "weekly") == 3


def test_calculate_streak_weekly_with_gap():
    dates = [date(2026, 1, 5), date(2026, 1, 26)]
    assert calculate_streak(dates, "weekly") == 1
