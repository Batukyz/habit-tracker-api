from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
