from datetime import date
from pathlib import Path

from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    get_current_user,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    use_password_reset_token,
    use_refresh_token,
)
from .database import get_db
from .email import send_password_reset_email
from .logging_config import RequestLoggingMiddleware, configure_logging, logger
from .rate_limit import limiter
from .security import hash_password, verify_password
from .stats import completion_rate, longest_streak
from .streak import calculate_streak

configure_logging()

app = FastAPI(title="Habit Tracker API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestLoggingMiddleware)
app.mount("/app", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="frontend")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
@limiter.limit("5/minute")
def register(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = models.User(email=user.email, hashed_password=hash_password(user.password))
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/auth/login", response_model=schemas.Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return schemas.Token(
        access_token=create_access_token(subject=user.email),
        refresh_token=create_refresh_token(user_id=user.id, db=db),
    )


@app.post("/auth/refresh", response_model=schemas.Token)
def refresh(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    user = use_refresh_token(payload.refresh_token, db)
    revoke_refresh_token(payload.refresh_token, db)
    return schemas.Token(
        access_token=create_access_token(subject=user.email),
        refresh_token=create_refresh_token(user_id=user.id, db=db),
    )


@app.post("/auth/logout", status_code=204)
def logout(payload: schemas.LogoutRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(payload.refresh_token, db)


@app.post("/auth/forgot-password", response_model=schemas.MessageOut, status_code=202)
@limiter.limit("5/minute")
def forgot_password(
    request: Request, payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user is not None:
        token = create_password_reset_token(user_id=user.id, db=db)
        send_password_reset_email(user.email, token)
    # Always the same response, whether or not the email is registered,
    # so this endpoint can't be used to enumerate accounts.
    return schemas.MessageOut(detail="If that email is registered, a reset link has been sent.")


@app.post("/auth/reset-password", status_code=204)
@limiter.limit("5/minute")
def reset_password(
    request: Request, payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)
):
    user = use_password_reset_token(payload.token, db)
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    # Force re-login everywhere: a leaked/stale session shouldn't survive a reset.
    revoke_all_refresh_tokens(user.id, db)


@app.get("/me", response_model=schemas.UserOut)
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.put("/me", response_model=schemas.UserOut)
def update_me(
    update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if update.email is not None:
        existing = (
            db.query(models.User)
            .filter(models.User.email == update.email, models.User.id != current_user.id)
            .first()
        )
        if existing is not None:
            raise HTTPException(status_code=400, detail="Email already registered")
        current_user.email = update.email
    if update.password is not None:
        current_user.hashed_password = hash_password(update.password)
    db.commit()
    db.refresh(current_user)
    return current_user


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
    frequency: Optional[str] = None,
    is_completed: Optional[bool] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Habit).filter(models.Habit.owner_id == current_user.id)
    if not include_archived:
        query = query.filter(models.Habit.is_archived.is_(False))
    if frequency is not None:
        query = query.filter(models.Habit.frequency == frequency)
    if is_completed is not None:
        query = query.filter(models.Habit.is_completed == is_completed)
    if category is not None:
        query = query.filter(models.Habit.category == category)
    if search:
        query = query.filter(models.Habit.title.ilike(f"%{search}%"))
    return query.order_by(models.Habit.id).offset(skip).limit(limit).all()


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
    """Archives the habit rather than deleting it, so its log/streak history is preserved."""
    habit = _get_owned_habit(habit_id, current_user.id, db)
    habit.is_archived = True
    db.commit()


@app.delete("/habits/{habit_id}/permanent", status_code=204)
def delete_habit_permanently(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Irreversibly removes an already-archived habit and its logs. Archive first, delete second."""
    habit = _get_owned_habit(habit_id, current_user.id, db)
    if not habit.is_archived:
        raise HTTPException(status_code=400, detail="Habit must be archived before permanent deletion")
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
    db_log = models.HabitLog(
        habit_id=habit_id,
        completed_on=log.completed_on or date.today(),
        amount=log.amount,
        note=log.note,
    )
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


@app.get("/habits/{habit_id}/stats", response_model=schemas.HabitStatsOut)
def get_habit_stats(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    habit = _get_owned_habit(habit_id, current_user.id, db)
    logs = db.query(models.HabitLog).filter(models.HabitLog.habit_id == habit_id).all()
    dates = [log.completed_on for log in logs]
    total_amount = None
    if habit.tracking_unit is not None:
        total_amount = sum(log.amount for log in logs if log.amount is not None)
    return schemas.HabitStatsOut(
        habit_id=habit_id,
        total_completions=len(dates),
        current_streak=calculate_streak(dates, habit.frequency),
        longest_streak=longest_streak(dates, habit.frequency),
        completion_rate=completion_rate(
            dates, habit.frequency, since=habit.created_at.date(), until=date.today()
        ),
        total_amount=total_amount,
    )
