"""Deterministic ecosystem growth calculation.

Mirrors the style of streak.py/stats.py: pure functions over plain data, no DB
access, no stored/mutable state. Given the same habit data and the same
milestone rules, this always produces the same result.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Milestone:
    threshold: int
    stage_key: str
    name: str
    description: Optional[str] = None


@dataclass(frozen=True)
class EcosystemInput:
    total_habits: int
    total_logs: int
    best_current_streak: int
    best_longest_streak: int
    avg_completion_rate: float


@dataclass(frozen=True)
class EcosystemState:
    growth_level: int
    stage_key: str
    stage_name: str
    stage_description: Optional[str]
    next_milestone: Optional[Milestone]
    progress_to_next: float
    best_current_streak: int
    best_longest_streak: int
    avg_completion_rate: float
    total_habits: int
    total_logs: int


def compute_ecosystem_state(inputs: EcosystemInput, milestones: list[Milestone]) -> EcosystemState:
    if not milestones:
        raise ValueError("At least one milestone is required to compute ecosystem state")

    ordered = sorted(milestones, key=lambda m: m.threshold)
    streak = inputs.best_current_streak

    current = ordered[0]
    current_index = 0
    next_milestone: Optional[Milestone] = None
    for index, milestone in enumerate(ordered):
        if streak >= milestone.threshold:
            current = milestone
            current_index = index
        else:
            next_milestone = milestone
            break

    if next_milestone is not None:
        span = next_milestone.threshold - current.threshold
        progressed = streak - current.threshold
        progress_to_next = 100.0 if span <= 0 else round(min(100.0, max(0.0, progressed / span * 100)), 1)
    else:
        progress_to_next = 100.0

    return EcosystemState(
        growth_level=current_index,
        stage_key=current.stage_key,
        stage_name=current.name,
        stage_description=current.description,
        next_milestone=next_milestone,
        progress_to_next=progress_to_next,
        best_current_streak=inputs.best_current_streak,
        best_longest_streak=inputs.best_longest_streak,
        avg_completion_rate=inputs.avg_completion_rate,
        total_habits=inputs.total_habits,
        total_logs=inputs.total_logs,
    )


DEFAULT_MILESTONES: list[Milestone] = [
    Milestone(0, "empty", "Boş Toprak", "Henüz bir seri başlatmadın."),
    Milestone(1, "seed", "Tohum", "İlk adımı attın."),
    Milestone(3, "sprout", "Filiz", "Küçük bir filiz toprağı yardı."),
    Milestone(7, "young_plant", "Genç Bitki", "Bitki kök salmaya başladı."),
    Milestone(14, "growing", "Büyüyen Bahçe", "Yapraklar ve ilk çiçekler belirdi."),
    Milestone(30, "garden", "İlk Bahçe", "Küçük bir yaşam alanı oluştu."),
    Milestone(60, "thriving", "Gelişen Ekosistem", "Çiçekler ve küçük canlılar katıldı."),
    Milestone(100, "mature", "Olgun Bahçe", "Ağaçlar büyüdü, ekosistem zenginleşti."),
    Milestone(365, "ancient", "Kadim Bahçe", "Uzun soluklu başarının nişanesi."),
]
