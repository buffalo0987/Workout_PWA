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
from typing import Dict, Any, List, Optional

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

def get_recent_sparky_nutrition_averages(days: int = 3) -> Dict[str, float]:
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

def suggest_workout_progression(data: Dict[str, Any]) -> Dict[str, Any]:
    exercise_ids = data.get("exercise_ids") or []
    if isinstance(exercise_ids, str):
        exercise_ids = [exercise_ids]

    user_id = data.get("user_id") or "default_user"
    settings_repo = SettingsRepository(DB_PATH, user_id=user_id)
    active_model = data.get("model") or settings_repo.get_selected_ollama_model("qwen3:14b")
    ollama_url = settings_repo.get_ollama_base_url()
    unit = settings_repo.get_unit_preference("lbs")

    # 1. Fetch 3-day Sparky nutrition summary
    nutrition_avg = get_recent_sparky_nutrition_averages(days=3)

    suggestions = []

    for ex_id in exercise_ids:
        exercise_info = get_exercise_by_id(ex_id)
        ex_name = exercise_info["name"] if exercise_info else f"Exercise {ex_id}"
        
        # 2. Fetch past sets
        past_sets = get_past_exercise_history(ex_id, limit_sessions=3)
        last_weight = past_sets[0]["weight"] if past_sets else 135.0
        last_reps = past_sets[0]["reps"] if past_sets else 10
        last_rpe = past_sets[0]["rpe"] if past_sets and past_sets[0]["rpe"] else 8.0

        # 3. Formulate Prompt for Ollama
        prompt = f"""
Analyze the athlete's progressive overload target for {ex_name}.
Units: All weights are strictly in {unit}.
Recent Nutrition (3-day average):
- Calories: {nutrition_avg['avg_calories']} kcal
- Protein: {nutrition_avg['avg_protein_g']} g
- Carbs: {nutrition_avg['avg_carbs_g']} g

Previous Performance:
- Last Weight: {last_weight} {unit}
- Last Reps: {last_reps}
- Last RPE: {last_rpe}

Return JSON with exact keys:
"suggested_weight" (number in {unit}),
"target_reps" (string e.g. "8-10"),
"suggested_sets" (integer),
"strategy" (string: "weight_increase"|"rep_increase"|"maintain"|"deload"),
"rationale" (string explaining how nutrition and past RPE drove this decision in {unit})
"""
        context_data = {
            "current_weight": last_weight,
            "target_rep_range": [8, 12],
            "last_reps": last_reps,
            "last_rpe": last_rpe,
            "nutrition": nutrition_avg,
            "unit": unit
        }

        # 4. Generate with Ollama
        ollama_response = generate_completion(
            prompt=prompt,
            model=active_model,
            base_url=ollama_url,
            context_data=context_data,
            raw_json_format=True
        )

        parsed = ollama_response.get("parsed_json") or {}
        rec_item = {
            "exercise_id": ex_id,
            "exercise_name": ex_name,
            "suggested_weight": parsed.get("suggested_weight", last_weight),
            "target_reps": parsed.get("target_reps", "8-12"),
            "suggested_sets": parsed.get("suggested_sets", 3),
            "strategy": parsed.get("strategy", "maintain"),
            "rationale": parsed.get("rationale", f"Progressive overload target in {unit}"),
            "unit": unit,
            "model_used": ollama_response.get("model"),
            "is_fallback": ollama_response.get("is_fallback", False)
        }
        suggestions.append(rec_item)

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
                ollama_response.get("content"),
                ollama_response.get("model", active_model)
            ))
            conn.commit()

    return {
        "nutrition_averages": nutrition_avg,
        "active_model": active_model,
        "unit": unit,
        "suggestions": suggestions
    }

# -----------------------------------------------------------------------------
# Coaching Feedback Endpoint (/api/coaching/feedback)
# -----------------------------------------------------------------------------

def get_weekly_volume_and_nutrition() -> Dict[str, Any]:
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    repo = SettingsRepository(DB_PATH, user_id=user_id)
    unit = repo.get_unit_preference("lbs")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(es.id) as total_sets,
                SUM(es.weight * es.reps) as total_volume_tonnage,
                AVG(es.rpe) as avg_rpe
            FROM exercise_sets es
            WHERE es.completed_at >= ? AND es.is_completed = 1
        """, (seven_days_ago,))
        row = cursor.fetchone()
        sets_count = row["total_sets"] or 0
        volume = float(row["total_volume_tonnage"] or 0.0)
        avg_rpe = float(row["avg_rpe"] or 8.0)

    nutrition = get_recent_sparky_nutrition_averages(days=7)

    return {
        "weekly_sets": sets_count,
        "total_volume": round(volume, 1),
        "unit": unit,
        "average_rpe": round(avg_rpe, 1),
        "weekly_nutrition": nutrition
    }

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

# -----------------------------------------------------------------------------
# AI Coach Chat (/api/coaching/chat)
# -----------------------------------------------------------------------------

def handle_coach_chat(data: Dict[str, Any]) -> Dict[str, Any]:
    user_id = data.get("user_id") or "default_user"
    messages = data.get("messages", [])
    
    settings_repo = SettingsRepository(DB_PATH, user_id=user_id)
    active_model = data.get("model") or settings_repo.get_selected_ollama_model("qwen3:14b")
    ollama_url = settings_repo.get_ollama_base_url()

    routines = list_routines(user_id)
    routines_context = json.dumps(routines, indent=2)
    
    gym_equipment = settings_repo.get_setting("gym_equipment", "")
    equip_constraint = f"\nCRITICAL: The athlete ONLY has access to the following equipment: {gym_equipment}\nDo NOT suggest any exercises that require equipment outside of this list." if gym_equipment else ""

    prompt = f"""
You are an expert, encouraging, and highly analytical AI strength coach. The athlete is asking for advice, routine modifications, or new routines.

Current Routines Data:
{routines_context}{equip_constraint}

Your capabilities:
You can provide a conversational response. If the user asks for new routines or modifications, you MUST provide them by returning a JSON object containing an array of 'new_routines' or 'modified_routines'. If no changes are needed, just return 'message'.

CRITICAL SCHEDULING RULE: If you are generating or modifying multiple routines, you MUST NEVER schedule them on the same day. Ensure absolutely zero overlap in the 'schedule_days' arrays across all routines (e.g. if Routine A is on Friday, Routine B cannot be on Friday).

Return ONLY valid JSON in this exact format:
{{
  "message": "Your conversational response here, formatted in markdown. Explain what you've done or answer the question.",
  "routines_to_create": [
    {{
      "title": "New Routine Name",
      "description": "...",
      "schedule_days": ["Monday", "Wednesday"],
      "exercises": [
         {{"exercise_id": "UUID-from-DB-if-known-or-leave-blank", "target_sets": 3, "min_reps": 8, "max_reps": 12, "rest_seconds": 90, "name": "Bench Press"}}
      ]
    }}
  ]
}}

To match exercises, use general names. If the user wants a new routine, generate the exercises array with common names (like "Barbell Bench Press", "Squat", "Pull Up") in the 'name' field if you don't know the ID.
"""

    # We will just pass the prompt as the system message and append user history
    # For simplicity, we just format the last message into the prompt
    last_user_message = messages[-1]["content"] if messages else ""
    full_prompt = prompt + "\n\nUser Message:\n" + last_user_message

    ollama_res = generate_completion(
        prompt=full_prompt,
        model=active_model,
        base_url=ollama_url,
        raw_json_format=True,
        timeout=90
    )

    parsed = ollama_res.get("parsed_json") or {}
    message = parsed.get("message", "I couldn't process that properly.")
    routines_to_create = parsed.get("routines_to_create", [])
    routines_to_update = parsed.get("routines_to_update", [])
    routines_to_delete = parsed.get("routines_to_delete", [])

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
                create_routine({
                    "user_id": user_id,
                    "title": rt.get("title", "AI Generated Routine"),
                    "description": rt.get("description", "Generated by AI Coach"),
                    "schedule_days": rt.get("schedule_days", []),
                    "exercises": exercises_payload
                })
                
        for rt in routines_to_update:
            rt_id = rt.get("id")
            if rt_id:
                exercises_payload = match_exercises(rt)
                if exercises_payload:
                    rt["exercises"] = exercises_payload
                    update_routine(rt_id, rt)
                    
        for rt_id in routines_to_delete:
            if rt_id:
                delete_routine(rt_id)

    return {
        "reply": message,
        "routines_created": len(routines_to_create),
        "routines_updated": len(routines_to_update),
        "routines_deleted": len(routines_to_delete),
        "model_used": ollama_res.get("model", active_model),
    }



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
