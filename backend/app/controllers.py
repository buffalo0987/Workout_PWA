"""
Business Logic & Controllers for Workout App
Handles:
1. Exercise CRUD & routine templates (e.g. Push, Pull, Legs)
2. Workout session & Set CRUD
3. Progressive overload suggestion (/api/workouts/suggest) with Sparky nutrition & past sets
4. Weekly coaching feedback (/api/coaching/feedback) with 3-bullet insight
5. App Settings & Live Connectivity Testing (/api/settings, /api/settings/test-connection)
"""

import os
import json
import uuid
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from src.models.settings import SettingsRepository
from backend.app.services.ollama_client import generate_completion, get_available_models
from backend.app.services.sparky_client import get_daily_summary, format_date_key

DB_PATH = os.environ.get("DB_PATH", "workout_app.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------------------------------------------------------
# Settings CRUD & Connectivity Testing
# -----------------------------------------------------------------------------

def get_app_settings(user_id: str = 'default_user') -> Dict[str, Any]:
    repo = SettingsRepository(DB_PATH, user_id=user_id)
    all_settings = repo.get_all_settings()
    ollama_url = repo.get_ollama_base_url()
    
    # Auto-discover models from configured Ollama host
    discovered_models = get_available_models(base_url=ollama_url, timeout=4)
    model_names = [m.get("name") for m in discovered_models if m.get("name")]
    if not model_names:
        model_names = ["qwen3:14b", "gemma4:12b", "llama3.3:8b"]

    return {
        "settings": all_settings,
        "available_models": model_names,
        "active_model": repo.get_selected_ollama_model(),
        "ollama_base_url": ollama_url,
        "sparky_base_url": repo.get_sparky_base_url(),
        "sparky_api_token": repo.get_sparky_api_token(),
        "unit_preference": repo.get_unit_preference("lb")
    }

def update_app_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    user_id = data.get('user_id', 'default_user')
    repo = SettingsRepository(DB_PATH, user_id=user_id)
    if "selected_ollama_model" in data:
        repo.set_selected_ollama_model(str(data["selected_ollama_model"]).strip())
    if "ollama_base_url" in data:
        repo.set_ollama_base_url(str(data["ollama_base_url"]).strip())
    if "sparky_base_url" in data:
        repo.set_sparky_base_url(str(data["sparky_base_url"]).strip())
    if "sparky_api_token" in data:
        repo.set_sparky_api_token(str(data["sparky_api_token"]).strip())
    if "unit_preference" in data:
        repo.set_unit_preference(str(data["unit_preference"]).strip())
    if "gym_equipment" in data:
        repo.set_setting("gym_equipment", str(data["gym_equipment"]).strip(), "List of available gym equipment")
    return get_app_settings(user_id)

def test_service_connections(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Tests live HTTP network connectivity to configured Ollama and SparkyFitness servers.
    Returns status, latency (ms), and diagnostic details for each.
    """
    data = data or {}
    user_id = data.get("user_id", "default_user")
    repo = SettingsRepository(DB_PATH, user_id=user_id)
    
    ollama_url = (data.get("ollama_base_url") or repo.get_ollama_base_url()).rstrip("/")
    sparky_url = (data.get("sparky_base_url") or repo.get_sparky_base_url()).rstrip("/")
    sparky_token = data.get("sparky_api_token") if "sparky_api_token" in data else repo.get_sparky_api_token()

    results = {
        "ollama": {"status": "error", "message": "", "latency_ms": 0, "url": ollama_url},
        "sparky": {"status": "error", "message": "", "latency_ms": 0, "url": sparky_url},
    }

    # 1. Test Ollama
    try:
        t0 = datetime.now()
        endpoint = f"{ollama_url}/api/tags"
        req = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            latency = int((datetime.now() - t0).total_seconds() * 1000)
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8"))
                models = payload.get("models", [])
                results["ollama"] = {
                    "status": "success",
                    "message": f"Connected! Found {len(models)} installed model(s).",
                    "latency_ms": latency,
                    "url": ollama_url,
                    "models": [m.get("name") for m in models]
                }
            else:
                results["ollama"] = {
                    "status": "error",
                    "message": f"HTTP {resp.status}: {resp.reason}",
                    "latency_ms": latency,
                    "url": ollama_url
                }
    except Exception as e:
        results["ollama"] = {
            "status": "error",
            "message": f"Connection failed: {str(e)}",
            "latency_ms": 0,
            "url": ollama_url
        }

    # 2. Test SparkyFitness
    try:
        t0 = datetime.now()
        today_str = datetime.now().strftime("%Y-%m-%d")
        endpoint = f"{sparky_url}/api/v1/nutrition/summary?date={today_str}"
        headers = {"Accept": "application/json"}
        if sparky_token:
            headers["Authorization"] = f"Bearer {sparky_token}"
        req = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            latency = int((datetime.now() - t0).total_seconds() * 1000)
            if resp.status == 200:
                results["sparky"] = {
                    "status": "success",
                    "message": "Connected! Nutrition API responded successfully.",
                    "latency_ms": latency,
                    "url": sparky_url
                }
            else:
                results["sparky"] = {
                    "status": "error",
                    "message": f"HTTP {resp.status}: {resp.reason}",
                    "latency_ms": latency,
                    "url": sparky_url
                }
    except urllib.error.HTTPError as he:
        results["sparky"] = {
            "status": "error" if he.code != 401 else "auth_error",
            "message": f"HTTP {he.code}: {he.reason}" + (" (Invalid or missing token)" if he.code == 401 else ""),
            "latency_ms": 0,
            "url": sparky_url
        }
    except Exception as e:
        results["sparky"] = {
            "status": "error",
            "message": f"Connection failed: {str(e)}",
            "latency_ms": 0,
            "url": sparky_url
        }

    return results

# -----------------------------------------------------------------------------
# Exercise CRUD
# -----------------------------------------------------------------------------

def list_exercises() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exercises ORDER BY name ASC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def create_exercise(data: Dict[str, Any]) -> Dict[str, Any]:
    exercise_id = data.get("id") or str(uuid.uuid4())
    user_id = data.get("user_id") or "default_user"
    name = data.get("name")
    if not name:
        raise ValueError("Exercise 'name' is required")
    category = data.get("category", "barbell")
    primary_muscle = data.get("primary_muscle", "chest")
    secondary_muscles = json.dumps(data.get("secondary_muscles", []))
    description = data.get("description", "")
    equipment = data.get("equipment", "")
    animation_svg = data.get("animation_svg", "")
    is_custom = 1 if data.get("is_custom", True) else 0

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exercises (id, user_id, name, category, primary_muscle, secondary_muscles, is_custom, description, equipment, animation_svg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exercise_id, user_id, name, category, primary_muscle, secondary_muscles, is_custom, description, equipment, animation_svg))
        conn.commit()
        cursor.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,))
        return dict(cursor.fetchone())

def get_exercise_by_id(exercise_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# -----------------------------------------------------------------------------
# Routines & Splits (e.g. Push Pull Legs)
# -----------------------------------------------------------------------------

def list_routines(user_id: str = "default_user") -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM routines WHERE is_archived = 0 AND user_id = ? ORDER BY created_at ASC", (user_id,))
        routines = [dict(r) for r in cursor.fetchall()]
        for r in routines:
            try:
                r["schedule_days"] = json.loads(r.get("schedule_days") or "[]")
            except Exception:
                r["schedule_days"] = []
            cursor.execute("""
                SELECT re.*, e.name as exercise_name, e.category, e.primary_muscle
                FROM routine_exercises re
                JOIN exercises e ON re.exercise_id = e.id
                WHERE re.routine_id = ?
                ORDER BY re.order_index ASC
            """, (r["id"],))
            r["exercises"] = [dict(ex) for ex in cursor.fetchall()]
        return routines


def update_routine(routine_id: str, data: dict) -> list:
    title = data.get("title")
    description = data.get("description", "")
    import json
    schedule_days = json.dumps(data.get("schedule_days", []))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE routines 
            SET title = ?, description = ?, schedule_days = ?
            WHERE id = ?
        """, (title, description, schedule_days, routine_id))
        
        # Replace exercises
        cursor.execute("DELETE FROM routine_exercises WHERE routine_id = ?", (routine_id,))
        exercises = data.get("exercises", [])
        import uuid
        for idx, ex in enumerate(exercises):
            re_id = str(uuid.uuid4())
            ex_id = ex.get("exercise_id")
            target_sets = int(ex.get("target_sets", 3))
            min_reps = int(ex.get("min_reps", 8))
            max_reps = int(ex.get("max_reps", 12))
            rest_seconds = int(ex.get("rest_seconds", 90))
            cursor.execute("""
                INSERT INTO routine_exercises (id, routine_id, exercise_id, order_index, target_sets, min_reps, max_reps, rest_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (re_id, routine_id, ex_id, idx, target_sets, min_reps, max_reps, rest_seconds))
            
        conn.commit()
    return list_routines()

def create_routine(data: Dict[str, Any]) -> Dict[str, Any]:
    routine_id = data.get("id") or str(uuid.uuid4())
    user_id = data.get("user_id") or "default_user"
    title = data.get("title")
    if not title:
        raise ValueError("Routine 'title' is required")
    description = data.get("description", "")
    schedule_days = json.dumps(data.get("schedule_days", []))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO routines (id, user_id, title, description, schedule_days)
            VALUES (?, ?, ?, ?, ?)
        """, (routine_id, user_id, title, description, schedule_days))

        exercises = data.get("exercises", [])
        for idx, ex in enumerate(exercises):
            re_id = str(uuid.uuid4())
            ex_id = ex.get("exercise_id")
            target_sets = int(ex.get("target_sets", 3))
            min_reps = int(ex.get("min_reps", 8))
            max_reps = int(ex.get("max_reps", 12))
            rest = int(ex.get("rest_seconds", 90))
            cursor.execute("""
                INSERT INTO routine_exercises (id, routine_id, exercise_id, order_index, target_sets, min_reps, max_reps, rest_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (re_id, routine_id, ex_id, idx, target_sets, min_reps, max_reps, rest))

        conn.commit()
        return list_routines()

def delete_routine(routine_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE routines SET is_archived = 1 WHERE id = ?", (routine_id,))
        conn.commit()
    return {"success": True, "routine_id": routine_id}

# -----------------------------------------------------------------------------
# Workout Session & Set Logging CRUD
# -----------------------------------------------------------------------------

def create_workout_session(data: Dict[str, Any]) -> Dict[str, Any]:
    session_id = data.get("id") or str(uuid.uuid4())
    user_id = data.get("user_id") or "default_user"
    routine_id = data.get("routine_id")
    name = data.get("name") or "Workout Session"
    status = data.get("status", "in_progress")
    started_at = data.get("started_at") or datetime.now(timezone.utc).isoformat()
    notes = data.get("notes")
    source = data.get("source", "mobile_pwa")
    sync_id = data.get("sync_id") or session_id

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workout_sessions (id, user_id, routine_id, name, status, started_at, notes, source, sync_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, user_id, routine_id, name, status, started_at, notes, source, sync_id))
        conn.commit()
        cursor.execute("SELECT * FROM workout_sessions WHERE id = ?", (session_id,))
        return dict(cursor.fetchone())

def log_exercise_set(data: Dict[str, Any]) -> Dict[str, Any]:
    set_id = data.get("id") or str(uuid.uuid4())
    workout_exercise_id = data.get("workout_exercise_id")
    
    if not workout_exercise_id:
        session_id = data.get("workout_session_id")
        exercise_id = data.get("exercise_id")
        if not session_id or not exercise_id:
            raise ValueError("workout_exercise_id or (workout_session_id and exercise_id) required")
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM workout_exercises 
                WHERE workout_session_id = ? AND exercise_id = ?
            """, (session_id, exercise_id))
            row = cursor.fetchone()
            if row:
                workout_exercise_id = row[0]
            else:
                workout_exercise_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO workout_exercises (id, workout_session_id, exercise_id, order_index)
                    VALUES (?, ?, ?, ?)
                """, (workout_exercise_id, session_id, exercise_id, 0))
                conn.commit()

    set_number = int(data.get("set_number", 1))
    set_type = data.get("set_type", "working")
    weight = float(data.get("weight", 0.0))
    reps = int(data.get("reps", 0))
    rpe = float(data["rpe"]) if data.get("rpe") is not None else None
    rest_after = int(data.get("rest_after_seconds", 90))
    is_completed = 1 if data.get("is_completed", True) else 0
    completed_at = data.get("completed_at") or datetime.now(timezone.utc).isoformat()
    sync_id = data.get("sync_id") or set_id

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exercise_sets (id, workout_exercise_id, set_number, set_type, weight, reps, rpe, rest_after_seconds, is_completed, completed_at, sync_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (set_id, workout_exercise_id, set_number, set_type, weight, reps, rpe, rest_after, is_completed, completed_at, sync_id))
        conn.commit()
        cursor.execute("SELECT * FROM exercise_sets WHERE id = ?", (set_id,))
        return dict(cursor.fetchone())

def list_workout_sets(workout_exercise_id: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        if workout_exercise_id:
            cursor.execute("SELECT * FROM exercise_sets WHERE workout_exercise_id = ? ORDER BY set_number ASC", (workout_exercise_id,))
        elif session_id:
            cursor.execute("""
                SELECT es.*, we.exercise_id, e.name as exercise_name
                FROM exercise_sets es
                JOIN workout_exercises we ON es.workout_exercise_id = we.id
                JOIN exercises e ON we.exercise_id = e.id
                WHERE we.workout_session_id = ?
                ORDER BY we.order_index ASC, es.set_number ASC
            """, (session_id,))
        else:
            cursor.execute("SELECT * FROM exercise_sets ORDER BY created_at DESC LIMIT 50")
        return [dict(r) for r in cursor.fetchall()]

def list_workout_sessions(user_id: str = "default_user") -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workout_sessions WHERE user_id = ? ORDER BY started_at DESC LIMIT 50", (user_id,))
        return [dict(r) for r in cursor.fetchall()]

def update_workout_session(session_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if "status" in data:
            updates.append("status = ?")
            params.append(data["status"])
        if "ended_at" in data:
            updates.append("ended_at = ?")
            params.append(data["ended_at"])
        if "notes" in data:
            updates.append("notes = ?")
            params.append(data["notes"])
        
        if updates:
            params.append(session_id)
            cursor.execute(f"UPDATE workout_sessions SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            
        cursor.execute("SELECT * FROM workout_sessions WHERE id = ?", (session_id,))
        return dict(cursor.fetchone())

def get_workout_session_details(session_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workout_sessions WHERE id = ?", (session_id,))
        session = dict(cursor.fetchone())
        
        cursor.execute("""
            SELECT we.id as we_id, we.exercise_id, we.order_index, e.name, e.category, e.primary_muscle, e.images
            FROM workout_exercises we
            JOIN exercises e ON we.exercise_id = e.id
            WHERE we.workout_session_id = ?
            ORDER BY we.order_index ASC
        """, (session_id,))
        exercises = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT es.*
            FROM exercise_sets es
            JOIN workout_exercises we ON es.workout_exercise_id = we.id
            WHERE we.workout_session_id = ?
            ORDER BY es.set_number ASC
        """, (session_id,))
        sets = [dict(r) for r in cursor.fetchall()]
        
        for ex in exercises:
            ex["sets"] = [s for s in sets if s["workout_exercise_id"] == ex["we_id"]]
            
        session["exercises"] = exercises
        return session


# -----------------------------------------------------------------------------
# Progressive Overload Suggestion (/api/workouts/suggest)
# -----------------------------------------------------------------------------

def get_past_exercise_history(exercise_id: str, limit_sessions: int = 3) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT es.weight, es.reps, es.rpe, es.set_number, es.completed_at
            FROM exercise_sets es
            JOIN workout_exercises we ON es.workout_exercise_id = we.id
            WHERE we.exercise_id = ? AND es.is_completed = 1
            ORDER BY es.completed_at DESC
            LIMIT ?
        """, (exercise_id, limit_sessions * 4))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_recent_sparky_nutrition_averages(user_id: str = "default_user", days: int = 3) -> Dict[str, float]:
    today = datetime.now(timezone.utc)
    total_cals = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0
    days_found = 0

    repo = SettingsRepository(DB_PATH, user_id=user_id)
    sparky_url = repo.get_sparky_base_url()
    sparky_token = repo.get_sparky_api_token()

    for i in range(days):
        target_d = today - timedelta(days=i)
        summary = get_daily_summary(target_d, base_url=sparky_url, api_token=sparky_token)
        if not summary.get("is_fallback") or summary.get("calories", 0) > 0:
            total_cals += summary.get("calories", 0)
            total_protein += summary.get("protein_grams", 0)
            total_carbs += summary.get("carbs_grams", 0)
            total_fat += summary.get("fat_grams", 0)
            days_found += 1

    count = max(days_found, 1)
    return {
        "avg_calories": round(total_cals / count, 1),
        "avg_protein_g": round(total_protein / count, 1),
        "avg_carbs_g": round(total_carbs / count, 1),
        "avg_fat_g": round(total_fat / count, 1),
        "days_averaged": days_found,
    }

def calculate_double_progression(
    exercise_id: str,
    exercise_info: Optional[Dict[str, Any]],
    past_sets: List[Dict[str, Any]],
    unit: str = "lb",
    threshold_rpe: float = 8.5
) -> Dict[str, Any]:
    """
    Deterministic Double Progression Engine.
    Executes instantly in Python (<1ms) instead of sequential LLM inference loops.
    
    Rules:
    - If no history: establish reasonable category-based baseline load.
    - If last_reps >= max_reps and last_rpe <= threshold_rpe:
        Advance weight (+5 lb / +2.5 kg barbell, +2.5 lb / +1.0 kg dumbbell/cable)
        and reset reps to min_reps.
    - If last_rpe >= 9.5 or last_reps < min_reps:
        High exertion / fatigue: Maintain weight to consolidate form.
    - If min_reps <= last_reps < max_reps and last_rpe < 9.5:
        Advance reps towards max_reps (last_reps + 1).
    """
    category = (exercise_info.get("category") if exercise_info else "barbell") or "barbell"
    ex_name = exercise_info.get("name") if exercise_info else f"Exercise {exercise_id}"

    # Determine routine target rep bracket from routine_exercises if configured
    min_reps = 8
    max_reps = 12
    suggested_sets = 3
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT target_sets, min_reps, max_reps
                FROM routine_exercises
                WHERE exercise_id = ?
                LIMIT 1
            """, (exercise_id,))
            re_row = cursor.fetchone()
            if re_row:
                suggested_sets = int(re_row["target_sets"] or 3)
                min_reps = int(re_row["min_reps"] or 8)
                max_reps = int(re_row["max_reps"] or 12)
    except Exception:
        pass

    # Weight increments by category & unit
    is_metric = (unit.lower() == "kg")
    category_lower = category.lower()

    if "barbell" in category_lower:
        weight_increment = 2.5 if is_metric else 5.0
    elif any(k in category_lower for k in ["dumbbell", "cable", "machine"]):
        weight_increment = 1.0 if is_metric else 2.5
    else:  # bodyweight / other
        weight_increment = 1.0 if is_metric else 2.5

    # Case 1: No previous sets recorded (First session)
    if not past_sets:
        if "barbell" in category_lower:
            if any(k in ex_name.lower() for k in ["squat", "deadlift"]):
                base_wt = 60.0 if is_metric else 135.0
            elif "bench" in ex_name.lower():
                base_wt = 40.0 if is_metric else 95.0
            elif any(k in ex_name.lower() for k in ["press", "row"]):
                base_wt = 30.0 if is_metric else 65.0
            else:
                base_wt = 20.0 if is_metric else 45.0
        elif "dumbbell" in category_lower:
            base_wt = 10.0 if is_metric else 20.0
        elif any(k in category_lower for k in ["cable", "machine"]):
            base_wt = 15.0 if is_metric else 30.0
        else:
            base_wt = 0.0

        return {
            "suggested_weight": round(base_wt, 1),
            "target_reps": f"{min_reps}-{max_reps}",
            "suggested_sets": suggested_sets,
            "strategy": "baseline",
            "rationale": f"Initial baseline for {ex_name}. Target {min_reps}-{max_reps} controlled reps to gauge capacity."
        }

    # Case 2: Past sets exist
    last_weight = float(past_sets[0]["weight"])
    last_reps = int(past_sets[0]["reps"])
    last_rpe = float(past_sets[0]["rpe"]) if past_sets[0].get("rpe") is not None else 8.0

    # Rule A: Top of rep bracket reached with controlled fatigue
    if last_reps >= max_reps and last_rpe <= threshold_rpe:
        new_weight = round(last_weight + weight_increment, 1)
        return {
            "suggested_weight": new_weight,
            "target_reps": f"{min_reps}-{min_reps + 2}",
            "suggested_sets": suggested_sets,
            "strategy": "weight_increase",
            "rationale": (
                f"Bracket target hit ({last_reps} reps @ RPE {last_rpe} ≤ {threshold_rpe}). "
                f"Add +{weight_increment:g} {unit} and reset target to {min_reps} reps."
            )
        }

    # Rule B: High exertion / fatigue overreach
    if last_rpe >= 9.5 or last_reps < min_reps:
        return {
            "suggested_weight": round(last_weight, 1),
            "target_reps": f"{min_reps}-{max_reps}",
            "suggested_sets": suggested_sets,
            "strategy": "maintain",
            "rationale": (
                f"High exertion recorded (RPE {last_rpe} on {last_reps} reps). "
                f"Maintain {last_weight:g} {unit} to build technical capacity before adding load."
            )
        }

    # Rule C: Within rep bracket (Rep Progression)
    target_next_reps = min(last_reps + 1, max_reps)
    return {
        "suggested_weight": round(last_weight, 1),
        "target_reps": f"{target_next_reps}-{max_reps}",
        "suggested_sets": suggested_sets,
        "strategy": "rep_increase",
        "rationale": (
            f"Solid execution ({last_reps} reps @ RPE {last_rpe}). "
            f"Hold load at {last_weight:g} {unit} and aim for {target_next_reps} reps."
        )
    }

def suggest_workout_progression(data: Dict[str, Any]) -> Dict[str, Any]:
    exercise_ids = data.get("exercise_ids") or []
    if isinstance(exercise_ids, str):
        exercise_ids = [exercise_ids]

    user_id = data.get("user_id") or "default_user"
    settings_repo = SettingsRepository(DB_PATH, user_id=user_id)
    unit = settings_repo.get_unit_preference("lb")
    try:
        threshold_rpe = float(settings_repo.get_setting("double_progression_threshold_rpe", "8.5"))
    except (ValueError, TypeError):
        threshold_rpe = 8.5

    # 1. Fetch 3-day Sparky nutrition summary
    nutrition_avg = get_recent_sparky_nutrition_averages(user_id=user_id, days=3)

    suggestions = []

    for ex_id in exercise_ids:
        exercise_info = get_exercise_by_id(ex_id)
        ex_name = exercise_info["name"] if exercise_info else f"Exercise {ex_id}"
        
        # 2. Fetch past sets
        past_sets = get_past_exercise_history(ex_id, limit_sessions=3)
        
        # 3. Calculate Double Progression deterministically in Python
        prog = calculate_double_progression(
            exercise_id=ex_id,
            exercise_info=exercise_info,
            past_sets=past_sets,
            unit=unit,
            threshold_rpe=threshold_rpe
        )

        rec_item = {
            "exercise_id": ex_id,
            "exercise_name": ex_name,
            "suggested_weight": prog["suggested_weight"],
            "target_reps": prog["target_reps"],
            "suggested_sets": prog["suggested_sets"],
            "strategy": prog["strategy"],
            "rationale": prog["rationale"],
            "unit": unit,
            "model_used": "DoubleProgressionEngine (Python)",
            "is_fallback": False
        }
        suggestions.append(rec_item)

        context_data = {
            "current_weight": past_sets[0]["weight"] if past_sets else 0.0,
            "last_reps": past_sets[0]["reps"] if past_sets else 0,
            "last_rpe": past_sets[0]["rpe"] if past_sets else 8.0,
            "nutrition": nutrition_avg,
            "unit": unit
        }

        with get_db() as conn:
            cursor = conn.cursor()
            rec_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO ai_recommendations (id, user_id, recommendation_type, input_context, suggested_targets, raw_response, model_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rec_id,
                user_id,
                "progressive_overload",
                json.dumps(context_data),
                json.dumps(rec_item),
                "Calculated deterministically via Double Progression Engine",
                "DoubleProgressionEngine (Python)"
            ))
            conn.commit()

    return {
        "nutrition_averages": nutrition_avg,
        "active_model": "DoubleProgressionEngine (Python)",
        "unit": unit,
        "suggestions": suggestions
    }

# -----------------------------------------------------------------------------
# Coaching Feedback Endpoint (/api/coaching/feedback)
# -----------------------------------------------------------------------------

def get_weekly_volume_and_nutrition(user_id: str = "default_user") -> Dict[str, Any]:
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    repo = SettingsRepository(DB_PATH, user_id=user_id)
    unit = repo.get_unit_preference("lb")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(es.id) as total_sets,
                SUM(es.weight * es.reps) as total_volume_tonnage,
                AVG(es.rpe) as avg_rpe
            FROM exercise_sets es
            JOIN workout_exercises we ON es.workout_exercise_id = we.id
            JOIN workout_sessions ws ON we.workout_session_id = ws.id
            WHERE ws.user_id = ? AND es.completed_at >= ? AND es.is_completed = 1
        """, (user_id, seven_days_ago))
        row = cursor.fetchone()
        sets_count = row["total_sets"] or 0
        volume = float(row["total_volume_tonnage"] or 0.0)
        avg_rpe = float(row["avg_rpe"] or 8.0)

    nutrition = get_recent_sparky_nutrition_averages(user_id=user_id, days=7)

    return {
        "weekly_sets": sets_count,
        "total_volume": round(volume, 1),
        "unit": unit,
        "average_rpe": round(avg_rpe, 1),
        "weekly_nutrition": nutrition
    }

def get_weekly_muscle_volume(user_id: str = "default_user") -> Dict[str, Any]:
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    repo = SettingsRepository(DB_PATH, user_id=user_id)
    unit = repo.get_unit_preference("lb")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(NULLIF(e.primary_muscle, ''), 'Other') as muscle,
                COUNT(es.id) as set_count,
                ROUND(SUM(es.weight * es.reps), 1) as total_volume
            FROM exercise_sets es
            JOIN workout_exercises we ON es.workout_exercise_id = we.id
            JOIN exercises e ON we.exercise_id = e.id
            JOIN workout_sessions ws ON we.workout_session_id = ws.id
            WHERE ws.user_id = ? AND es.completed_at >= ? AND es.is_completed = 1
            GROUP BY muscle
            ORDER BY set_count DESC
        """, (user_id, seven_days_ago))
        rows = [dict(r) for r in cursor.fetchall()]
        
        # Categorize against scientific hypertrophy volume landmarks (10-20 sets/week)
        results = []
        for r in rows:
            cnt = r["set_count"]
            if cnt < 10:
                status = "maintenance"
                badge = "Maintenance (<10)"
                color = "var(--color-warning)"
            elif 10 <= cnt <= 20:
                status = "optimal"
                badge = "Optimal Zone (10-20)"
                color = "var(--color-success)"
            else:
                status = "high"
                badge = "High Volume (20+)"
                color = "var(--color-danger)"
            results.append({
                "muscle": r["muscle"].title(),
                "sets": cnt,
                "volume": r["total_volume"] or 0.0,
                "status": status,
                "badge": badge,
                "color": color
            })
            
        cursor.execute("""
            SELECT COUNT(es.id) as total_sets, SUM(es.weight * es.reps) as total_vol
            FROM exercise_sets es
            JOIN workout_exercises we ON es.workout_exercise_id = we.id
            JOIN workout_sessions ws ON we.workout_session_id = ws.id
            WHERE ws.user_id = ? AND es.completed_at >= ? AND es.is_completed = 1
        """, (user_id, seven_days_ago))
        tot = cursor.fetchone()
        
        return {
            "unit": unit,
            "total_weekly_sets": tot["total_sets"] or 0,
            "total_weekly_volume": round(tot["total_vol"] or 0.0, 1),
            "muscles": results
        }

def get_strength_records(user_id: str = "default_user") -> List[Dict[str, Any]]:
    repo = SettingsRepository(DB_PATH, user_id=user_id)
    unit = repo.get_unit_preference("lb")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                e.id as exercise_id,
                e.name as exercise_name,
                es.weight,
                es.reps,
                ROUND(es.weight * (1.0 + (CAST(es.reps AS FLOAT) / 30.0)), 1) as est_1rm,
                es.completed_at
            FROM exercise_sets es
            JOIN workout_exercises we ON es.workout_exercise_id = we.id
            JOIN exercises e ON we.exercise_id = e.id
            JOIN workout_sessions ws ON we.workout_session_id = ws.id
            WHERE ws.user_id = ? AND es.is_completed = 1 AND es.reps >= 1 AND es.reps <= 15 AND es.weight > 0
            ORDER BY est_1rm DESC
        """, (user_id,))
        all_sets = [dict(r) for r in cursor.fetchall()]
        
        seen = set()
        records = []
        for s in all_sets:
            eid = s["exercise_id"]
            if eid not in seen:
                seen.add(eid)
                records.append({
                    "exercise_id": eid,
                    "exercise_name": s["exercise_name"],
                    "best_weight": s["weight"],
                    "best_reps": s["reps"],
                    "est_1rm": s["est_1rm"],
                    "unit": unit,
                    "date": str(s["completed_at"])[:10] if s.get("completed_at") else ""
                })
                
        return records[:8]

def swap_workout_exercise(data: Dict[str, Any]) -> Dict[str, Any]:
    session_id = data.get("workout_session_id")
    old_exercise_id = data.get("old_exercise_id")
    new_exercise_id = data.get("new_exercise_id")
    
    with get_db() as conn:
        cursor = conn.cursor()
        if session_id and old_exercise_id and new_exercise_id:
            cursor.execute("""
                UPDATE workout_exercises 
                SET exercise_id = ? 
                WHERE workout_session_id = ? AND exercise_id = ?
            """, (new_exercise_id, session_id, old_exercise_id))
            conn.commit()
            
        cursor.execute("SELECT id, name, category, primary_muscle, equipment, images FROM exercises WHERE id = ?", (new_exercise_id,))
        new_ex = cursor.fetchone()
        return dict(new_ex) if new_ex else {"id": new_exercise_id}

def generate_coaching_feedback(data: Dict[str, Any]) -> Dict[str, Any]:
    user_id = data.get("user_id") or "default_user"
    settings_repo = SettingsRepository(DB_PATH, user_id=user_id)
    active_model = data.get("model") or settings_repo.get_selected_ollama_model("qwen3:14b")
    ollama_url = settings_repo.get_ollama_base_url()
    unit = settings_repo.get_unit_preference("lbs")

    weekly_metrics = get_weekly_volume_and_nutrition()

    prompt = f"""
You are an expert strength and conditioning coach.
Analyze the athlete's training in {unit}:
- Completed Sets: {weekly_metrics['weekly_sets']}
- Total Training Volume: {weekly_metrics['total_volume']} {unit}
- Average RPE: {weekly_metrics['average_rpe']}
- Average Daily Nutrition: {weekly_metrics['weekly_nutrition']['avg_calories']} kcal, {weekly_metrics['weekly_nutrition']['avg_protein_g']}g protein, {weekly_metrics['weekly_nutrition']['avg_carbs_g']}g carbs

Provide exactly THREE distinct, high-impact bullet insights to optimize recovery and progression:
1. Training Load & Volume adjustment (using {unit}).
2. Nutritional & Fueling optimization based on protein/calories.
3. Recovery or Sleep/Fatigue guideline.

Respond in JSON format with key "insights" containing an array of exactly 3 bullet strings.
"""

    fallback_insights = [
        f"Training Load: Logged {weekly_metrics['weekly_sets']} sets totaling {weekly_metrics['total_volume']} {unit} this week. Maintain current split with focus on progressive overload.",
        f"Nutrition & Fueling: Aim for consistent 0.8-1.0g of protein per lb of body weight and ensure adequate carbohydrate timing around heavy lifts.",
        f"Recovery Management: Average exertion is at RPE {weekly_metrics['average_rpe']}. Deload or insert an extra rest day if morning readiness drops below threshold."
    ]

    ollama_res = generate_completion(
        prompt=prompt,
        model=active_model,
        base_url=ollama_url,
        raw_json_format=True,
        timeout=15
    )

    parsed = ollama_res.get("parsed_json") or {}
    insights = parsed.get("insights")
    if not isinstance(insights, list) or len(insights) < 3:
        insights = fallback_insights

    result = {
        "weekly_metrics": weekly_metrics,
        "insights": insights[:3],
        "model_used": ollama_res.get("model", active_model),
        "is_fallback": ollama_res.get("is_fallback", False)
    }

    with get_db() as conn:
        cursor = conn.cursor()
        rec_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ai_recommendations (id, user_id, recommendation_type, input_context, suggested_targets, raw_response, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rec_id,
            user_id,
            "weekly_coaching_feedback",
            json.dumps(weekly_metrics),
            json.dumps(result),
            ollama_res.get("content"),
            ollama_res.get("model", active_model)
        ))
        conn.commit()

    return result

def get_recent_workout_history_summary(user_id: str = "default_user", limit: int = 5) -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, started_at, status 
            FROM workout_sessions 
            WHERE user_id = ? 
            ORDER BY started_at DESC 
            LIMIT ?
        """, (user_id, limit))
        sessions = [dict(r) for r in cursor.fetchall()]
        if not sessions:
            return "No recorded workout sessions yet."
        
        summary = []
        for s in sessions:
            date_str = str(s.get("started_at", ""))[:10]
            name = s.get("name") or "Workout"
            cursor.execute("""
                SELECT e.name as ex_name, es.set_number, es.weight, es.reps, es.rpe
                FROM exercise_sets es
                JOIN workout_exercises we ON es.workout_exercise_id = we.id
                JOIN exercises e ON we.exercise_id = e.id
                WHERE we.workout_session_id = ? AND es.is_completed = 1
                ORDER BY we.order_index ASC, es.set_number ASC
            """, (s["id"],))
            sets = [dict(r) for r in cursor.fetchall()]
            
            ex_map = {}
            for st in sets:
                ex_n = st["ex_name"]
                if ex_n not in ex_map:
                    ex_map[ex_n] = []
                rpe_str = f" @ RPE {st['rpe']}" if st.get('rpe') else ""
                ex_map[ex_n].append(f"{st['weight']}x{st['reps']}{rpe_str}")
                
            ex_summary_list = []
            for ex_n, set_strs in ex_map.items():
                ex_summary_list.append(f"  - {ex_n}: {', '.join(set_strs)}")
                
            if ex_summary_list:
                summary.append(f"Session '{name}' on {date_str}:\n" + "\n".join(ex_summary_list))
            else:
                summary.append(f"Session '{name}' on {date_str} (no completed sets logged)")
                
        return "\n\n".join(summary)

# -----------------------------------------------------------------------------
# AI Coach Chat & Streaming (/api/coaching/chat & /api/coaching/chat/stream)
# -----------------------------------------------------------------------------

def format_routines_yaml(routines: List[Dict[str, Any]]) -> str:
    if not routines:
        return "No routines created yet."
    lines = []
    for r in routines:
        title = r.get("title", "Untitled")
        rid = r.get("id", "")
        days = ", ".join(r.get("schedule_days") or ["Unscheduled"])
        desc = r.get("description", "")
        lines.append(f"- Routine: \"{title}\" (id: {rid})")
        lines.append(f"  Schedule: {days}")
        if desc:
            lines.append(f"  Notes: {desc}")
        lines.append("  Exercises:")
        for idx, ex in enumerate(r.get("exercises", []), 1):
            ex_name = ex.get("exercise_name") or ex.get("name") or "Exercise"
            sets = ex.get("target_sets", 3)
            min_r = ex.get("min_reps", 8)
            max_r = ex.get("max_reps", 12)
            rest = ex.get("rest_seconds", 90)
            lines.append(f"    {idx}. {ex_name}: {sets} sets × {min_r}-{max_r} reps ({rest}s rest)")
    return "\n".join(lines)

def build_coach_prompt(user_id: str, messages: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    settings_repo = SettingsRepository(DB_PATH, user_id=user_id)
    active_model = settings_repo.get_selected_ollama_model("qwen2.5:7b")
    ollama_url = settings_repo.get_ollama_base_url()
    unit = settings_repo.get_unit_preference("lb")

    from backend.app.services.coaching_analytics import compute_athlete_diagnostics
    diagnostics = compute_athlete_diagnostics(user_id, DB_PATH)

    routines = list_routines(user_id)
    routines_yaml = format_routines_yaml(routines)
    history_context = get_recent_workout_history_summary(user_id=user_id, limit=5)
    
    gym_equipment = settings_repo.get_setting("gym_equipment", "")
    equip_constraint = f"Available Equipment Constraint: {gym_equipment}" if gym_equipment else "Available Equipment: Full commercial gym"

    system_prompt = f"""You are Dr. Marcus Vance, an elite, world-class strength and hypertrophy coach (PhD in Exercise Physiology & CSCS). You coach competitive athletes and serious lifters.

ATHLETE CURRENT SETTINGS:
Weight Unit: {unit}
{equip_constraint}

{diagnostics}

CURRENT ATHLETE ROUTINES:
{routines_yaml}

RECENT WORKOUT LOGS (LAST 5 SESSIONS):
{history_context}

COACHING DIRECTIVES & PERSONA:
1. ZERO FLUFF: NEVER use sycophantic customer-service filler (NEVER say "Certainly!", "I would be happy to help", "As an AI coach", or "Great question!"). Jump straight into the physiological analysis or coaching directive with confidence.
2. REFERENCE THE DIAGNOSTICS: Actively cite the diagnostic signals above. If the athlete has stalled, reference their exact weights, reps, and RPE. If push:pull volume is imbalanced, explain the postural/injury risk.
3. BIOMECHANICAL SEQUENCING: When creating or modifying routines, sequence exercises strictly:
   1) Heavy compound lifts first (e.g. Barbell Squat, Deadlift, Bench Press, Overhead Press) when the central nervous system is fresh.
   2) Free-weight / compound accessories second (e.g. Incline DB Press, Romanian Deadlift, Rows, Dips, Pull-Ups).
   3) Isolation movements third (e.g. Cable Lateral Raises, Bicep Curls, Tricep Extensions).
   4) Core / Calves last.
4. ZERO SCHEDULE OVERLAP: Ensure no two routines share the same 'schedule_days'.
5. ACTIONS AT THE END: If the athlete requests routine changes, modifications, additions, or deletions, explain your scientific rationale in your message first, then provide the exact database mutations at the very end inside a ```json ... ``` block.

FEW-SHOT COACHING EXEMPLARS:

--- Example 1 (Stall Analysis) ---
User: "My bench press has been stuck at 185 for two weeks, what gives?"
Coach:
Looking at your diagnostic logs, you hit 185 lb for 6 reps on Sept 22 and again on Sept 25, with RPE peaking at 9.5. Your chest volume is currently at 12 direct sets, which is within the optimal hypertrophy landmark (10–20 sets). However, your push:pull ratio is skewed at 1.8:1, indicating your upper back and rotator cuff stabilizers are under-developed compared to your anterior delts and pecs.

Here is the plan to break this plateau:
1. **Micro-load or Drop Rep Range:** Switch to a 3×4-6 strength block at 190 lb to stimulate higher mechanical tension.
2. **Back Balance:** We need to increase your barbell row volume by 3 sets to build a stronger pushing platform.
3. **Caloric Check:** Ensure you're in a consistent 200–300 kcal surplus.

--- Example 2 (Routine Modification) ---
User: "Can you add a dedicated Leg Day on Wednesday?"
Coach:
Understood. Adding a focused lower-body session on Wednesday gives you 48 hours of recovery following your Monday upper body work and keeps your total weekly leg volume in the optimal hypertrophy window (14 sets total). 

I've sequenced your primary axial load (Barbell Squat) first while your spinal erectors and nervous system are completely fresh, followed by Romanian Deadlifts for posterior chain, finishing with Quad and Calf isolation:

```json
{{
  "routines_to_create": [
    {{
      "title": "Lower Body Hypertrophy",
      "description": "Quadriceps, Hamstrings, and Calves focus",
      "schedule_days": ["Wednesday"],
      "exercises": [
        {{"name": "Barbell Squat", "target_sets": 3, "min_reps": 6, "max_reps": 8, "rest_seconds": 180}},
        {{"name": "Romanian Deadlift", "target_sets": 3, "min_reps": 8, "max_reps": 10, "rest_seconds": 120}},
        {{"name": "Leg Extension", "target_sets": 3, "min_reps": 10, "max_reps": 15, "rest_seconds": 90}},
        {{"name": "Standing Calf Raise", "target_sets": 4, "min_reps": 12, "max_reps": 15, "rest_seconds": 60}}
      ]
    }}
  ]
}}
```
"""

    history_str = ""
    if messages:
        recent = messages[-5:]
        for m in recent:
            role = "Athlete" if m.get("role") == "user" else "Coach"
            history_str += f"\n{role}: {m.get('content', '')}"

    full_prompt = system_prompt + "\n\nCONVERSATION HISTORY:" + history_str + "\nCoach:"
    return full_prompt, active_model, ollama_url

def execute_routine_actions(user_id: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    routines_to_create = parsed.get("routines_to_create", [])
    routines_to_update = parsed.get("routines_to_update", [])
    routines_to_delete = parsed.get("routines_to_delete", [])
    details = []

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM exercises")
        all_ex = {r["name"].lower(): r["id"] for r in cursor.fetchall()}
        
        def match_exercises(rt):
            exercises_payload = []
            for ex in rt.get("exercises", []):
                ex_name = ex.get("name", "").lower()
                matched_id = ex.get("exercise_id")
                if not matched_id or len(matched_id) < 5:
                    matched_id = None
                    for db_name, db_id in all_ex.items():
                        if ex_name in db_name or db_name in ex_name:
                            matched_id = db_id
                            break
                if matched_id:
                    ex["exercise_id"] = matched_id
                    exercises_payload.append(ex)
            return exercises_payload

        for rt in routines_to_create:
            exercises_payload = match_exercises(rt)
            if exercises_payload:
                title = rt.get("title", "AI Generated Routine")
                create_routine({
                    "user_id": user_id,
                    "title": title,
                    "description": rt.get("description", "Generated by AI Coach"),
                    "schedule_days": rt.get("schedule_days", []),
                    "exercises": exercises_payload
                })
                details.append(f"Created '{title}'")
                
        for rt in routines_to_update:
            rt_id = rt.get("id")
            if rt_id:
                exercises_payload = match_exercises(rt)
                if exercises_payload:
                    rt["exercises"] = exercises_payload
                    update_routine(rt_id, rt)
                    details.append(f"Updated '{rt.get('title', rt_id)}'")
                    
        for rt_id in routines_to_delete:
            if rt_id:
                delete_routine(rt_id)
                details.append("Deleted routine")

    return {
        "routines_created": len(routines_to_create),
        "routines_updated": len(routines_to_update),
        "routines_deleted": len(routines_to_delete),
        "details": ", ".join(details) if details else ""
    }

def handle_coach_chat(data: Dict[str, Any]) -> Dict[str, Any]:
    user_id = data.get("user_id") or "default_user"
    messages = data.get("messages", [])
    
    full_prompt, active_model, ollama_url = build_coach_prompt(user_id, messages)

    ollama_res = generate_completion(
        prompt=full_prompt,
        model=active_model,
        base_url=ollama_url,
        raw_json_format=False,
        timeout=90
    )

    raw_text = ollama_res.get("content", "")
    
    import re
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    actions = {"routines_created": 0, "routines_updated": 0, "routines_deleted": 0, "details": ""}
    clean_reply = raw_text
    
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            actions = execute_routine_actions(user_id, parsed)
            clean_reply = raw_text[:json_match.start()].strip()
        except Exception as e:
            logger.warning(f"Failed to execute actions from non-stream chat: {e}")

    return {
        "reply": clean_reply,
        "raw_content": raw_text,
        "model_used": ollama_res.get("model", active_model),
        **actions
    }

def handle_coach_chat_stream(data: Dict[str, Any]):
    """
    Generator yielding Server-Sent Events (SSE) data chunks for streaming AI coaching:
    - data: {"type": "text", "delta": "..."}\n\n
    - data: {"type": "action", "routines_created": N, "details": "..."}\n\n
    - data: {"type": "done"}\n\n
    """
    from backend.app.services.ollama_client import stream_completion

    user_id = data.get("user_id") or "default_user"
    messages = data.get("messages", [])

    full_prompt, active_model, ollama_url = build_coach_prompt(user_id, messages)

    json_block_buffer = []
    in_json_block = False

    try:
        for chunk in stream_completion(prompt=full_prompt, model=active_model, base_url=ollama_url, temperature=0.3):
            token = chunk.get("token", "")
            done = chunk.get("done", False)

            if not in_json_block:
                if "```json" in token:
                    parts = token.split("```json")
                    if parts[0]:
                        yield f"data: {json.dumps({'type': 'text', 'delta': parts[0]})}\n\n"
                    in_json_block = True
                    if len(parts) > 1:
                        json_block_buffer.append(parts[1])
                else:
                    if token:
                        yield f"data: {json.dumps({'type': 'text', 'delta': token})}\n\n"
            else:
                if "```" in token:
                    parts = token.split("```")
                    json_block_buffer.append(parts[0])
                    in_json_block = False
                    if len(parts) > 1 and parts[1].strip():
                        yield f"data: {json.dumps({'type': 'text', 'delta': parts[1]})}\n\n"
                else:
                    json_block_buffer.append(token)

            if done:
                break

    except Exception as e:
        logger.exception("Error in handle_coach_chat_stream:")
        yield f"data: {json.dumps({'type': 'text', 'delta': f'\\n\\n*[Connection Error: {str(e)}]*'})}\n\n"

    if json_block_buffer:
        full_json_str = "".join(json_block_buffer).strip()
        try:
            import re
            cleaned = re.sub(r"^```(?:json)?|```$", "", full_json_str, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)
            actions = execute_routine_actions(user_id, parsed)
            yield f"data: {json.dumps({'type': 'action', **actions})}\n\n"
        except Exception as e:
            logger.warning(f"Failed to parse or execute action JSON: {e}")

    yield f"data: {json.dumps({'type': 'done'})}\n\n"



def delete_all_user_data(user_id: str) -> dict:
    if not user_id:
        return {"error": "user_id required"}
    with get_db() as conn:
        cursor = conn.cursor()
        # Delete routines (routine_exercises should cascade or be orphaned if not, but let's delete explicitly if needed)
        cursor.execute("DELETE FROM routines WHERE user_id = ?", (user_id,))
        # Delete workout sessions
        cursor.execute("DELETE FROM workout_sessions WHERE user_id = ?", (user_id,))
        # Delete user settings
        cursor.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        # Delete ai recommendations
        cursor.execute("DELETE FROM ai_recommendations WHERE user_id = ?", (user_id,))
        # Delete nutrition logs
        cursor.execute("DELETE FROM nutrition_logs WHERE user_id = ?", (user_id,))
        conn.commit()
    return {"status": "success", "message": f"All data for {user_id} deleted."}
