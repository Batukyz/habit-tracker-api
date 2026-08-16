from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HabitBase(BaseModel):
    title: str
    description: Optional[str] = None
    frequency: str = "daily"
    is_completed: bool = False


class HabitCreate(HabitBase):
    pass


class HabitUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    is_completed: Optional[bool] = None


class HabitOut(HabitBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class HabitLogCreate(BaseModel):
    completed_on: Optional[date] = None


class HabitLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    habit_id: int
    completed_on: date
    created_at: datetime


class HabitStreakOut(BaseModel):
    habit_id: int
    current_streak: int


class HabitStatsOut(BaseModel):
    habit_id: int
    total_completions: int
    current_streak: int
    longest_streak: int
    completion_rate: float
