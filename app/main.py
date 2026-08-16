from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import create_access_token, get_current_user
from .database import Base, engine, get_db
from .security import hash_password, verify_password
from .streak import calculate_streak

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Habit Tracker API")


def _get_owned_habit(habit_id: int, owner_id: int, db: Session) -> models.Habit:
    habit = (
        db.query(models.Habit)
        .filter(models.Habit.id == habit_id, models.Habit.owner_id == owner_id)
        .first()
    )
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = models.User(email=user.email, hashed_password=hash_password(user.password))
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return schemas.Token(access_token=create_access_token(subject=user.email))


@app.post("/habits", response_model=schemas.HabitOut, status_code=201)
def create_habit(
    habit: schemas.HabitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_habit = models.Habit(**habit.model_dump(), owner_id=current_user.id)
    db.add(db_habit)
    db.commit()
    db.refresh(db_habit)
    return db_habit


@app.get("/habits", response_model=list[schemas.HabitOut])
def list_habits(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Habit).filter(models.Habit.owner_id == current_user.id).all()


@app.get("/habits/{habit_id}", response_model=schemas.HabitOut)
def get_habit(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_habit(habit_id, current_user.id, db)


@app.put("/habits/{habit_id}", response_model=schemas.HabitOut)
def update_habit(
    habit_id: int,
    habit_update: schemas.HabitUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    habit = _get_owned_habit(habit_id, current_user.id, db)
    for field, value in habit_update.model_dump(exclude_unset=True).items():
        setattr(habit, field, value)
    db.commit()
    db.refresh(habit)
    return habit


@app.delete("/habits/{habit_id}", status_code=204)
def delete_habit(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    habit = _get_owned_habit(habit_id, current_user.id, db)
    db.delete(habit)
    db.commit()


@app.post("/habits/{habit_id}/logs", response_model=schemas.HabitLogOut, status_code=201)
def create_habit_log(
    habit_id: int,
    log: schemas.HabitLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_owned_habit(habit_id, current_user.id, db)
    db_log = models.HabitLog(habit_id=habit_id, completed_on=log.completed_on or date.today())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


@app.get("/habits/{habit_id}/logs", response_model=list[schemas.HabitLogOut])
def list_habit_logs(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_owned_habit(habit_id, current_user.id, db)
    return (
        db.query(models.HabitLog)
        .filter(models.HabitLog.habit_id == habit_id)
        .order_by(models.HabitLog.completed_on)
        .all()
    )


@app.delete("/habits/{habit_id}/logs/{log_id}", status_code=204)
def delete_habit_log(
    habit_id: int,
    log_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_owned_habit(habit_id, current_user.id, db)
    log = (
        db.query(models.HabitLog)
        .filter(models.HabitLog.id == log_id, models.HabitLog.habit_id == habit_id)
        .first()
    )
    if log is None:
        raise HTTPException(status_code=404, detail="Habit log not found")
    db.delete(log)
    db.commit()


@app.get("/habits/{habit_id}/streak", response_model=schemas.HabitStreakOut)
def get_habit_streak(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    habit = _get_owned_habit(habit_id, current_user.id, db)
    dates = [
        log.completed_on
        for log in db.query(models.HabitLog).filter(models.HabitLog.habit_id == habit_id).all()
    ]
    return schemas.HabitStreakOut(
        habit_id=habit_id, current_streak=calculate_streak(dates, habit.frequency)
    )
