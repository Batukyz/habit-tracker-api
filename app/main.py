from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Habit Tracker API")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/habits", response_model=schemas.HabitOut, status_code=201)
def create_habit(habit: schemas.HabitCreate, db: Session = Depends(get_db)):
    db_habit = models.Habit(**habit.model_dump())
    db.add(db_habit)
    db.commit()
    db.refresh(db_habit)
    return db_habit


@app.get("/habits", response_model=list[schemas.HabitOut])
def list_habits(db: Session = Depends(get_db)):
    return db.query(models.Habit).all()


@app.get("/habits/{habit_id}", response_model=schemas.HabitOut)
def get_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = db.query(models.Habit).filter(models.Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit


@app.put("/habits/{habit_id}", response_model=schemas.HabitOut)
def update_habit(habit_id: int, habit_update: schemas.HabitUpdate, db: Session = Depends(get_db)):
    habit = db.query(models.Habit).filter(models.Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    for field, value in habit_update.model_dump(exclude_unset=True).items():
        setattr(habit, field, value)
    db.commit()
    db.refresh(habit)
    return habit


@app.delete("/habits/{habit_id}", status_code=204)
def delete_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = db.query(models.Habit).filter(models.Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    db.delete(habit)
    db.commit()


@app.post("/habits/{habit_id}/logs", response_model=schemas.HabitLogOut, status_code=201)
def create_habit_log(habit_id: int, log: schemas.HabitLogCreate, db: Session = Depends(get_db)):
    habit = db.query(models.Habit).filter(models.Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    db_log = models.HabitLog(habit_id=habit_id, completed_on=log.completed_on or date.today())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


@app.get("/habits/{habit_id}/logs", response_model=list[schemas.HabitLogOut])
def list_habit_logs(habit_id: int, db: Session = Depends(get_db)):
    habit = db.query(models.Habit).filter(models.Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    return (
        db.query(models.HabitLog)
        .filter(models.HabitLog.habit_id == habit_id)
        .order_by(models.HabitLog.completed_on)
        .all()
    )
