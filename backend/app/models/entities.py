"""
SQLAlchemy ORM Entities
Strictly mapping models from architecture.md for FastAPI / PostgreSQL / SQLite.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    Text,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(128), nullable=False)
    unit_preference = Column(String(8), default="kg")
    settings = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    routines = relationship("Routine", back_populates="user", cascade="all, delete-orphan")
    workouts = relationship("WorkoutSession", back_populates="user", cascade="all, delete-orphan")
    nutrition_logs = relationship("NutritionLog", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("AIRecommendation", back_populates="user", cascade="all, delete-orphan")
    watch_devices = relationship("WatchDevice", back_populates="user", cascade="all, delete-orphan")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(128), nullable=False, index=True)
    category = Column(String(64), nullable=False) # barbell, dumbbell, machine, cable, bodyweight
    primary_muscle = Column(String(64), nullable=False)
    secondary_muscles = Column(Text, default="[]") # JSON encoded list
    is_custom = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Routine(Base):
    __tablename__ = "routines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="routines")
    exercises = relationship("RoutineExercise", back_populates="routine", cascade="all, delete-orphan")


class RoutineExercise(Base):
    __tablename__ = "routine_exercises"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    routine_id = Column(String(36), ForeignKey("routines.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(String(36), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    target_sets = Column(Integer, default=3, nullable=False)
    min_reps = Column(Integer, default=8, nullable=False)
    max_reps = Column(Integer, default=12, nullable=False)
    rest_seconds = Column(Integer, default=90)

    routine = relationship("Routine", back_populates="exercises")
    exercise = relationship("Exercise")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    routine_id = Column(String(36), ForeignKey("routines.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), default="in_progress", nullable=False) # in_progress, completed, discarded
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    source = Column(String(32), default="mobile_pwa") # mobile_pwa, watch, web
    sync_id = Column(String(64), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="workouts")
    routine = relationship("Routine")
    exercises = relationship("WorkoutExercise", back_populates="workout_session", cascade="all, delete-orphan")


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workout_session_id = Column(String(36), ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(String(36), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)

    workout_session = relationship("WorkoutSession", back_populates="exercises")
    exercise = relationship("Exercise")
    sets = relationship("ExerciseSet", back_populates="workout_exercise", cascade="all, delete-orphan")


class ExerciseSet(Base):
    __tablename__ = "exercise_sets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workout_exercise_id = Column(String(36), ForeignKey("workout_exercises.id", ondelete="CASCADE"), nullable=False)
    set_number = Column(Integer, nullable=False)
    set_type = Column(String(32), default="working") # warmup, working, dropset, failure
    weight = Column(Numeric(7, 2), default=0.0, nullable=False)
    reps = Column(Integer, default=0, nullable=False)
    rpe = Column(Numeric(3, 1), nullable=True)
    rest_after_seconds = Column(Integer, default=90)
    is_completed = Column(Boolean, default=True)
    completed_at = Column(DateTime, nullable=True)
    sync_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    workout_exercise = relationship("WorkoutExercise", back_populates="sets")


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workout_exercise_id = Column(String(36), ForeignKey("workout_exercises.id", ondelete="SET NULL"), nullable=True)
    recommendation_type = Column(String(64), nullable=False) # progressive_overload, recovery_nutrition
    input_context = Column(Text, nullable=False) # JSON payload of contextual volume & diet
    suggested_targets = Column(Text, nullable=False) # JSON payload: weight, reps, sets, rationale
    raw_response = Column(Text, nullable=True)
    model_used = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="recommendations")


class NutritionLog(Base):
    __tablename__ = "nutrition_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    log_date = Column(Date, nullable=False)
    calories = Column(Numeric(7, 2), default=0.0, nullable=False)
    protein_grams = Column(Numeric(6, 2), default=0.0, nullable=False)
    carbs_grams = Column(Numeric(6, 2), default=0.0, nullable=False)
    fat_grams = Column(Numeric(6, 2), default=0.0, nullable=False)
    water_ml = Column(Numeric(7, 2), default=0.0)
    raw_sparky_payload = Column(Text, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "log_date", name="uq_user_nutrition_date"),
    )

    user = relationship("User", back_populates="nutrition_logs")


class WatchDevice(Base):
    __tablename__ = "watch_devices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String(128), nullable=False)
    device_type = Column(String(32), nullable=False) # wear_os, apple_watch
    device_name = Column(String(128), nullable=True)
    pairing_token = Column(String(255), nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_user_watch_device"),
    )

    user = relationship("User", back_populates="watch_devices")
