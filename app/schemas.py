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
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class MessageOut(BaseModel):
    detail: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)


class HabitBase(BaseModel):
    title: str
    description: Optional[str] = None
    frequency: str = "daily"
    is_completed: bool = False
    tracking_unit: Optional[str] = None
    category: Optional[str] = None


class HabitCreate(HabitBase):
    pass


class HabitUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    is_completed: Optional[bool] = None
    is_archived: Optional[bool] = None
    tracking_unit: Optional[str] = None
    category: Optional[str] = None


class HabitOut(HabitBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_archived: bool
    created_at: datetime


class HabitLogCreate(BaseModel):
    completed_on: Optional[date] = None
    amount: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = None


class HabitLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    habit_id: int
    completed_on: date
    amount: Optional[float] = None
    note: Optional[str] = None
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
    total_amount: Optional[float] = None
