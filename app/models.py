from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, Date, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    habits = relationship("Habit", back_populates="owner", cascade="all, delete-orphan")


class Habit(Base):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    frequency = Column(String, default="daily")  # daily / weekly
    is_completed = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    tracking_unit = Column(String, nullable=True)  # e.g. "litre", "sayfa" - null means plain check-in
    category = Column(String, nullable=True)  # e.g. "Sağlık", "Spor & Fitness"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(Integer, primary_key=True, index=True)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False)
    completed_on = Column(Date, server_default=func.current_date(), nullable=False)
    amount = Column(Float, nullable=True)  # e.g. liters drunk, pages read - null for plain check-ins
    note = Column(String, nullable=True)  # free-text detail, e.g. "yağ değişimi, 15.230 km"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    habit = relationship("Habit", back_populates="logs")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    """A one-off dated plan/task (e.g. a meeting on a specific day) - not a recurring habit."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    is_done = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EcosystemMilestone(Base):
    """A global, admin-editable growth-stage definition (e.g. 7-day streak -> 'Young Plant').

    Not per-user: a user's ecosystem state is always computed fresh from their
    habit data against the current milestone table, never stored - this keeps
    it deterministic (same data + same rules => same result).
    """

    __tablename__ = "ecosystem_milestones"

    id = Column(Integer, primary_key=True, index=True)
    threshold = Column(Integer, unique=True, nullable=False)  # streak days required
    stage_key = Column(String, nullable=False)  # stable id the frontend maps to a visual
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EcosystemOverride(Base):
    """An admin-set testing override for one user's ecosystem.

    When present, its simulated_streak is used in place of the user's real best
    current streak when computing their ecosystem state - everything downstream
    (stage, growth level, progress) is still derived by the same pure
    compute_ecosystem_state() function, so the override only substitutes one
    input rather than introducing a second, parallel notion of ecosystem state.
    Deleting the row (the admin "recalculate"/"reset" action) reverts the user
    to their real, fully-deterministic streak-derived state.
    """

    __tablename__ = "ecosystem_overrides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    simulated_streak = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())