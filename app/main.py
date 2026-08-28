from datetime import date, datetime
from pathlib import Path

from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import models, schemas
from .admin_auth import require_admin
from .ecosystem import DEFAULT_MILESTONES, EcosystemInput, Milestone, compute_ecosystem_state
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


def _get_owned_event(event_id: int, owner_id: int, db: Session) -> models.Event:
    event = (
        db.query(models.Event)
        .filter(models.Event.id == event_id, models.Event.owner_id == owner_id)
        .first()
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/events", response_model=schemas.EventOut, status_code=201)
def create_event(
    event: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_event = models.Event(**event.model_dump(), owner_id=current_user.id)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@app.get("/events", response_model=list[schemas.EventOut])
def list_events(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    is_done: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Event).filter(models.Event.owner_id == current_user.id)
    if date_from is not None:
        query = query.filter(models.Event.event_date >= date_from)
    if date_to is not None:
        query = query.filter(models.Event.event_date <= date_to)
    if is_done is not None:
        query = query.filter(models.Event.is_done == is_done)
    return query.order_by(models.Event.event_date).all()


@app.get("/events/{event_id}", response_model=schemas.EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_event(event_id, current_user.id, db)


@app.put("/events/{event_id}", response_model=schemas.EventOut)
def update_event(
    event_id: int,
    update: schemas.EventUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    event = _get_owned_event(event_id, current_user.id, db)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


@app.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    event = _get_owned_event(event_id, current_user.id, db)
    db.delete(event)
    db.commit()


@app.get("/overview", response_model=schemas.OverviewOut)
def get_overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    today = date.today()

    habits = (
        db.query(models.Habit)
        .filter(models.Habit.owner_id == current_user.id, models.Habit.is_archived.is_(False))
        .all()
    )
    checked_in_today = 0
    best_current_streak = 0
    for habit in habits:
        dates = [
            log.completed_on
            for log in db.query(models.HabitLog).filter(models.HabitLog.habit_id == habit.id).all()
        ]
        if today in dates:
            checked_in_today += 1
        best_current_streak = max(best_current_streak, calculate_streak(dates, habit.frequency))

    today_events = (
        db.query(models.Event)
        .filter(models.Event.owner_id == current_user.id, models.Event.event_date == today)
        .all()
    )
    overdue_events = (
        db.query(models.Event)
        .filter(
            models.Event.owner_id == current_user.id,
            models.Event.event_date < today,
            models.Event.is_done.is_(False),
        )
        .count()
    )

    return schemas.OverviewOut(
        active_habits=len(habits),
        checked_in_today=checked_in_today,
        best_current_streak=best_current_streak,
        events_today_total=len(today_events),
        events_today_done=sum(1 for e in today_events if e.is_done),
        overdue_events=overdue_events,
    )


def _compute_user_ecosystem_input(db: Session, user_id: int) -> EcosystemInput:
    habits = (
        db.query(models.Habit)
        .filter(models.Habit.owner_id == user_id, models.Habit.is_archived.is_(False))
        .all()
    )

    total_logs = 0
    best_current = 0
    best_longest = 0
    completion_rates: list[float] = []
    for habit in habits:
        dates = [
            log.completed_on
            for log in db.query(models.HabitLog).filter(models.HabitLog.habit_id == habit.id).all()
        ]
        total_logs += len(dates)
        best_current = max(best_current, calculate_streak(dates, habit.frequency))
        best_longest = max(best_longest, longest_streak(dates, habit.frequency))
        completion_rates.append(
            completion_rate(dates, habit.frequency, since=habit.created_at.date(), until=date.today())
        )

    avg_completion_rate = round(sum(completion_rates) / len(completion_rates), 1) if completion_rates else 0.0

    return EcosystemInput(
        total_habits=len(habits),
        total_logs=total_logs,
        best_current_streak=best_current,
        best_longest_streak=best_longest,
        avg_completion_rate=avg_completion_rate,
    )


def _get_milestones(db: Session) -> list[Milestone]:
    milestone_rows = (
        db.query(models.EcosystemMilestone).order_by(models.EcosystemMilestone.threshold).all()
    )
    return [
        Milestone(threshold=row.threshold, stage_key=row.stage_key, name=row.name, description=row.description)
        for row in milestone_rows
    ] or DEFAULT_MILESTONES


def _ecosystem_state_to_schema(state, is_simulated: bool = False) -> schemas.EcosystemOut:
    return schemas.EcosystemOut(
        growth_level=state.growth_level,
        stage_key=state.stage_key,
        stage_name=state.stage_name,
        stage_description=state.stage_description,
        next_milestone=(
            schemas.EcosystemMilestoneOut(
                threshold=state.next_milestone.threshold,
                stage_key=state.next_milestone.stage_key,
                name=state.next_milestone.name,
                description=state.next_milestone.description,
            )
            if state.next_milestone
            else None
        ),
        progress_to_next=state.progress_to_next,
        best_current_streak=state.best_current_streak,
        best_longest_streak=state.best_longest_streak,
        avg_completion_rate=state.avg_completion_rate,
        total_habits=state.total_habits,
        total_logs=state.total_logs,
        is_simulated=is_simulated,
    )


@app.get("/ecosystem", response_model=schemas.EcosystemOut)
def get_ecosystem(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    inputs = _compute_user_ecosystem_input(db, current_user.id)

    override = (
        db.query(models.EcosystemOverride)
        .filter(models.EcosystemOverride.user_id == current_user.id)
        .first()
    )
    is_simulated = override is not None
    if override is not None:
        inputs = EcosystemInput(
            total_habits=inputs.total_habits,
            total_logs=inputs.total_logs,
            best_current_streak=override.simulated_streak,
            best_longest_streak=max(inputs.best_longest_streak, override.simulated_streak),
            avg_completion_rate=inputs.avg_completion_rate,
        )

    state = compute_ecosystem_state(inputs, _get_milestones(db))
    return _ecosystem_state_to_schema(state, is_simulated=is_simulated)


# --- Admin: ecosystem overview, milestone/growth-rule management, preview
# simulator, and per-user manual streak-override tools. All gated on
# User.is_admin via require_admin; there is no user-facing way to become an
# admin - the flag is set directly in the database.


@app.get("/admin/ecosystem/overview", response_model=schemas.AdminOverviewOut)
def admin_ecosystem_overview(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    milestones = _get_milestones(db)
    users = db.query(models.User).all()

    users_with_active_habits = 0
    growth_levels: list[int] = []
    streaks: list[int] = []
    for user in users:
        inputs = _compute_user_ecosystem_input(db, user.id)
        if inputs.total_habits == 0:
            continue
        users_with_active_habits += 1
        state = compute_ecosystem_state(inputs, milestones)
        growth_levels.append(state.growth_level)
        streaks.append(state.best_current_streak)

    return schemas.AdminOverviewOut(
        total_users=len(users),
        users_with_active_habits=users_with_active_habits,
        average_growth_level=round(sum(growth_levels) / len(growth_levels), 2) if growth_levels else 0.0,
        average_best_current_streak=round(sum(streaks) / len(streaks), 2) if streaks else 0.0,
        total_growth_points=sum(growth_levels),
        milestone_count=len(milestones),
    )


@app.get("/admin/ecosystem/milestones", response_model=list[schemas.AdminMilestoneOut])
def admin_list_milestones(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    return (
        db.query(models.EcosystemMilestone).order_by(models.EcosystemMilestone.threshold).all()
    )


@app.post("/admin/ecosystem/milestones", response_model=schemas.AdminMilestoneOut, status_code=201)
def admin_create_milestone(
    milestone: schemas.AdminMilestoneCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    existing = (
        db.query(models.EcosystemMilestone)
        .filter(models.EcosystemMilestone.threshold == milestone.threshold)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A milestone with this threshold already exists")
    row = models.EcosystemMilestone(**milestone.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_admin_milestone(milestone_id: int, db: Session) -> models.EcosystemMilestone:
    row = (
        db.query(models.EcosystemMilestone)
        .filter(models.EcosystemMilestone.id == milestone_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return row


@app.put("/admin/ecosystem/milestones/{milestone_id}", response_model=schemas.AdminMilestoneOut)
def admin_update_milestone(
    milestone_id: int,
    update: schemas.AdminMilestoneUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    row = _get_admin_milestone(milestone_id, db)
    changes = update.model_dump(exclude_unset=True)
    if "threshold" in changes and changes["threshold"] != row.threshold:
        clash = (
            db.query(models.EcosystemMilestone)
            .filter(
                models.EcosystemMilestone.threshold == changes["threshold"],
                models.EcosystemMilestone.id != milestone_id,
            )
            .first()
        )
        if clash is not None:
            raise HTTPException(status_code=409, detail="A milestone with this threshold already exists")
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/admin/ecosystem/milestones/{milestone_id}", status_code=204)
def admin_delete_milestone(
    milestone_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    row = _get_admin_milestone(milestone_id, db)
    db.delete(row)
    db.commit()


@app.get("/admin/ecosystem/preview", response_model=schemas.EcosystemOut)
def admin_preview_ecosystem(
    streak: int = Query(ge=0),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    inputs = EcosystemInput(
        total_habits=0,
        total_logs=0,
        best_current_streak=streak,
        best_longest_streak=streak,
        avg_completion_rate=0.0,
    )
    state = compute_ecosystem_state(inputs, _get_milestones(db))
    return _ecosystem_state_to_schema(state, is_simulated=True)


@app.get("/admin/users", response_model=list[schemas.AdminUserSummaryOut])
def admin_list_users(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    milestones = _get_milestones(db)
    overridden_ids = {row.user_id for row in db.query(models.EcosystemOverride.user_id).all()}
    summaries = []
    for user in db.query(models.User).order_by(models.User.id).all():
        inputs = _compute_user_ecosystem_input(db, user.id)
        state = compute_ecosystem_state(inputs, milestones)
        summaries.append(
            schemas.AdminUserSummaryOut(
                user_id=user.id,
                email=user.email,
                is_admin=user.is_admin,
                active_habits=inputs.total_habits,
                best_current_streak=state.best_current_streak,
                growth_level=state.growth_level,
                stage_name=state.stage_name,
                has_override=user.id in overridden_ids,
            )
        )
    return summaries


def _get_target_user(user_id: int, db: Session) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/admin/users/{user_id}/ecosystem", response_model=schemas.EcosystemOut)
def admin_get_user_ecosystem(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    _get_target_user(user_id, db)
    inputs = _compute_user_ecosystem_input(db, user_id)
    override = db.query(models.EcosystemOverride).filter(models.EcosystemOverride.user_id == user_id).first()
    is_simulated = override is not None
    if override is not None:
        inputs = EcosystemInput(
            total_habits=inputs.total_habits,
            total_logs=inputs.total_logs,
            best_current_streak=override.simulated_streak,
            best_longest_streak=max(inputs.best_longest_streak, override.simulated_streak),
            avg_completion_rate=inputs.avg_completion_rate,
        )
    state = compute_ecosystem_state(inputs, _get_milestones(db))
    return _ecosystem_state_to_schema(state, is_simulated=is_simulated)


@app.put("/admin/users/{user_id}/ecosystem/override", response_model=schemas.EcosystemOut)
def admin_set_user_ecosystem_override(
    user_id: int,
    override_in: schemas.EcosystemOverrideIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    _get_target_user(user_id, db)
    row = db.query(models.EcosystemOverride).filter(models.EcosystemOverride.user_id == user_id).first()
    if row is None:
        row = models.EcosystemOverride(user_id=user_id, simulated_streak=override_in.simulated_streak)
        db.add(row)
    else:
        row.simulated_streak = override_in.simulated_streak
    db.commit()

    inputs = _compute_user_ecosystem_input(db, user_id)
    inputs = EcosystemInput(
        total_habits=inputs.total_habits,
        total_logs=inputs.total_logs,
        best_current_streak=override_in.simulated_streak,
        best_longest_streak=max(inputs.best_longest_streak, override_in.simulated_streak),
        avg_completion_rate=inputs.avg_completion_rate,
    )
    state = compute_ecosystem_state(inputs, _get_milestones(db))
    return _ecosystem_state_to_schema(state, is_simulated=True)


@app.delete("/admin/users/{user_id}/ecosystem/override", response_model=schemas.EcosystemOut)
def admin_clear_user_ecosystem_override(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    _get_target_user(user_id, db)
    row = db.query(models.EcosystemOverride).filter(models.EcosystemOverride.user_id == user_id).first()
    if row is not None:
        db.delete(row)
        db.commit()

    inputs = _compute_user_ecosystem_input(db, user_id)
    state = compute_ecosystem_state(inputs, _get_milestones(db))
    return _ecosystem_state_to_schema(state, is_simulated=False)


# --- Friends: send/accept/decline requests, and a streak leaderboard. A
# single row per pair (Friendship) covers both the pending and accepted
# states; removing a friendship (unfriend, decline, or cancel a sent
# request) is always the same delete.


def _get_friendship_between(db: Session, user_a_id: int, user_b_id: int) -> models.Friendship | None:
    return (
        db.query(models.Friendship)
        .filter(
            or_(
                and_(models.Friendship.requester_id == user_a_id, models.Friendship.addressee_id == user_b_id),
                and_(models.Friendship.requester_id == user_b_id, models.Friendship.addressee_id == user_a_id),
            )
        )
        .first()
    )


@app.post("/friends/requests", response_model=schemas.FriendRequestOut, status_code=201)
def send_friend_request(
    payload: schemas.FriendRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    target = db.query(models.User).filter(models.User.email == payload.email).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Kendine istek gönderemezsin")
    if _get_friendship_between(db, current_user.id, target.id) is not None:
        raise HTTPException(status_code=409, detail="Zaten bir istek veya arkadaşlık var")

    row = models.Friendship(requester_id=current_user.id, addressee_id=target.id, status="pending")
    db.add(row)
    db.commit()
    db.refresh(row)
    return schemas.FriendRequestOut(
        id=row.id, requester_id=row.requester_id, requester_email=current_user.email, created_at=row.created_at
    )


@app.get("/friends/requests/incoming", response_model=list[schemas.FriendRequestOut])
def list_incoming_friend_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.Friendship)
        .filter(models.Friendship.addressee_id == current_user.id, models.Friendship.status == "pending")
        .all()
    )
    out = []
    for row in rows:
        requester = db.query(models.User).filter(models.User.id == row.requester_id).first()
        out.append(
            schemas.FriendRequestOut(
                id=row.id, requester_id=row.requester_id, requester_email=requester.email, created_at=row.created_at
            )
        )
    return out


@app.post("/friends/requests/{other_user_id}/accept", response_model=schemas.FriendOut)
def accept_friend_request(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = (
        db.query(models.Friendship)
        .filter(
            models.Friendship.requester_id == other_user_id,
            models.Friendship.addressee_id == current_user.id,
            models.Friendship.status == "pending",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Bekleyen istek bulunamadı")
    row.status = "accepted"
    row.responded_at = datetime.utcnow()
    db.commit()

    friend = db.query(models.User).filter(models.User.id == other_user_id).first()
    inputs = _compute_user_ecosystem_input(db, other_user_id)
    return schemas.FriendOut(
        user_id=friend.id,
        email=friend.email,
        best_current_streak=inputs.best_current_streak,
        best_longest_streak=inputs.best_longest_streak,
        active_habits=inputs.total_habits,
    )


@app.delete("/friends/{other_user_id}", status_code=204)
def remove_friendship(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = _get_friendship_between(db, current_user.id, other_user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="İlişki bulunamadı")
    db.delete(row)
    db.commit()


@app.get("/friends", response_model=list[schemas.FriendOut])
def list_friends(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.Friendship)
        .filter(
            or_(models.Friendship.requester_id == current_user.id, models.Friendship.addressee_id == current_user.id),
            models.Friendship.status == "accepted",
        )
        .all()
    )
    friends = []
    for row in rows:
        friend_id = row.addressee_id if row.requester_id == current_user.id else row.requester_id
        friend = db.query(models.User).filter(models.User.id == friend_id).first()
        inputs = _compute_user_ecosystem_input(db, friend_id)
        friends.append(
            schemas.FriendOut(
                user_id=friend.id,
                email=friend.email,
                best_current_streak=inputs.best_current_streak,
                best_longest_streak=inputs.best_longest_streak,
                active_habits=inputs.total_habits,
            )
        )
    friends.sort(key=lambda f: f.best_current_streak, reverse=True)
    return friends
