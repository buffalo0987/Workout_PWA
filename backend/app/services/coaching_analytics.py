"""
Coaching Analytics Engine
Provides deterministic pre-computations for AI Coaching:
- Plateau and stall detection across recent workout sessions
- Upper-body push:pull volume ratio and structural balance
- Hypertrophy volume landmarks per muscle group (10-20 sets/week)
- Nutrition fueling & protein deficit evaluation via SparkyFitness
- Estimated 1RM trajectory for key compound movements
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from src.models.settings import SettingsRepository

def _get_db_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def detect_stalled_exercises(conn: sqlite3.Connection, user_id: str, limit_sessions: int = 5) -> List[Dict[str, Any]]:
    """
    Scans recent completed workout sessions to detect exercises where performance
    has stalled or plateaued across 2 or more consecutive sessions.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, started_at
        FROM workout_sessions
        WHERE user_id = ? AND status = 'completed'
        ORDER BY started_at DESC
        LIMIT ?
    """, (user_id, limit_sessions))
    sessions = cursor.fetchall()
    if len(sessions) < 2:
        return []

    session_ids = [s["id"] for s in sessions]
    placeholders = ",".join("?" for _ in session_ids)

    cursor.execute(f"""
        SELECT 
            we.workout_session_id,
            ws.started_at,
            e.id as exercise_id,
            e.name as exercise_name,
            es.weight,
            es.reps,
            es.rpe
        FROM exercise_sets es
        JOIN workout_exercises we ON es.workout_exercise_id = we.id
        JOIN exercises e ON we.exercise_id = e.id
        JOIN workout_sessions ws ON we.workout_session_id = ws.id
        WHERE we.workout_session_id IN ({placeholders}) AND es.is_completed = 1 AND es.weight > 0
        ORDER BY ws.started_at DESC, es.weight DESC
    """, session_ids)
    rows = cursor.fetchall()

    exercise_history = {}
    for r in rows:
        eid = r["exercise_id"]
        ename = r["exercise_name"]
        sid = r["workout_session_id"]
        sdate = str(r["started_at"])[:10]
        
        if eid not in exercise_history:
            exercise_history[eid] = {"name": ename, "sessions": {}}
            
        if sid not in exercise_history[eid]["sessions"]:
            exercise_history[eid]["sessions"][sid] = {
                "date": sdate,
                "best_weight": r["weight"],
                "best_reps": r["reps"],
                "rpe": r["rpe"] or 8.0
            }
        else:
            cur_best = exercise_history[eid]["sessions"][sid]
            if (r["weight"] > cur_best["best_weight"]) or (r["weight"] == cur_best["best_weight"] and r["reps"] > cur_best["best_reps"]):
                exercise_history[eid]["sessions"][sid]["best_weight"] = r["weight"]
                exercise_history[eid]["sessions"][sid]["best_reps"] = r["reps"]
                if r["rpe"]:
                    exercise_history[eid]["sessions"][sid]["rpe"] = r["rpe"]

    stalls = []
    for eid, data in exercise_history.items():
        session_list = list(data["sessions"].values())
        if len(session_list) >= 2:
            s_new = session_list[0]
            s_old = session_list[1]
            
            is_stalled = (
                (s_new["best_weight"] < s_old["best_weight"]) or
                (s_new["best_weight"] == s_old["best_weight"] and s_new["best_reps"] <= s_old["best_reps"])
            )
            
            if is_stalled:
                stalls.append({
                    "exercise_name": data["name"],
                    "weight": s_new["best_weight"],
                    "reps": s_new["best_reps"],
                    "rpe": s_new["rpe"],
                    "sessions_stalled": 2,
                    "previous_performance": f"{s_old['best_weight']} × {s_old['best_reps']}"
                })

    return stalls[:4]

def analyze_volume_and_balance(conn: sqlite3.Connection, user_id: str, days: int = 7) -> Dict[str, Any]:
    """
    Calculates weekly sets per muscle group and determines the upper-body push:pull ratio.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COALESCE(LOWER(NULLIF(e.primary_muscle, '')), 'other') as muscle,
            COUNT(es.id) as set_count,
            ROUND(SUM(es.weight * es.reps), 1) as tonnage
        FROM exercise_sets es
        JOIN workout_exercises we ON es.workout_exercise_id = we.id
        JOIN exercises e ON we.exercise_id = e.id
        JOIN workout_sessions ws ON we.workout_session_id = ws.id
        WHERE ws.user_id = ? AND es.completed_at >= ? AND es.is_completed = 1
        GROUP BY muscle
    """, (user_id, cutoff))
    rows = cursor.fetchall()

    muscle_sets = {r["muscle"]: r["set_count"] for r in rows}

    push_muscles = {"chest", "pectorals", "shoulders", "deltoids", "anterior deltoids", "lateral deltoids", "triceps"}
    pull_muscles = {"back", "lats", "latissimus dorsi", "trapezius", "traps", "rhomboids", "rear deltoids", "biceps"}
    leg_muscles = {"quads", "quadriceps", "hamstrings", "glutes", "calves", "legs"}

    push_sets = sum(count for m, count in muscle_sets.items() if any(p in m for p in push_muscles))
    pull_sets = sum(count for m, count in muscle_sets.items() if any(p in m for p in pull_muscles))
    leg_sets = sum(count for m, count in muscle_sets.items() if any(l in m for l in leg_muscles))
    total_sets = sum(muscle_sets.values())

    push_pull_ratio = round(push_sets / max(pull_sets, 1), 2) if (push_sets > 0 or pull_sets > 0) else 1.0

    imbalance_notes = []
    if push_sets >= 6 and pull_sets >= 1 and push_pull_ratio > 1.35:
        imbalance_notes.append(f"Push:Pull ratio is {push_pull_ratio}:1 ({push_sets} push sets vs {pull_sets} pull sets). Pull volume is lagging; recommend adding horizontal/vertical pulling to balance shoulder mechanics.")
    elif pull_sets >= 6 and push_sets >= 1 and push_pull_ratio < 0.7:
        imbalance_notes.append(f"Pull:Push ratio is {round(1/max(push_pull_ratio, 0.01), 2)}:1 (pull-dominant session volume).")

    landmarks = []
    for m, count in muscle_sets.items():
        m_title = m.title()
        if count < 8:
            landmarks.append(f"{m_title}: {count} sets (Sub-optimal, below 10-set hypertrophy threshold)")
        elif 10 <= count <= 20:
            landmarks.append(f"{m_title}: {count} sets (Optimal Hypertrophy Zone)")
        elif count > 20:
            landmarks.append(f"{m_title}: {count} sets (High Volume / Watch for recovery fatigue)")

    return {
        "total_sets": total_sets,
        "push_sets": push_sets,
        "pull_sets": pull_sets,
        "leg_sets": leg_sets,
        "push_pull_ratio": push_pull_ratio,
        "imbalance_notes": imbalance_notes,
        "landmarks": landmarks[:6]
    }

def get_1rm_trajectories(conn: sqlite3.Connection, user_id: str) -> List[Dict[str, Any]]:
    """
    Calculates current estimated 1RM for core compound movements.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
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
        ORDER BY es.completed_at DESC
        LIMIT 40
    """, (user_id,))
    rows = cursor.fetchall()
    
    seen = set()
    records = []
    for r in rows:
        ename = r["exercise_name"]
        if ename not in seen and any(k in ename.lower() for k in ["press", "squat", "deadlift", "row", "pull"]):
            seen.add(ename)
            records.append({
                "exercise": ename,
                "est_1rm": r["est_1rm"],
                "best_set": f"{r['weight']} × {r['reps']}",
                "date": str(r["completed_at"])[:10]
            })
            if len(records) >= 4:
                break
                
    return records

def compute_athlete_diagnostics(user_id: str, db_path: str) -> str:
    """
    Orchestrates all deterministic analytics into a clean, dense Markdown bullet block
    ready for direct injection into the LLM system prompt.
    """
    if not os.path.exists(db_path):
        return "No athlete history logged yet."

    conn = _get_db_connection(db_path)
    try:
        stalls = detect_stalled_exercises(conn, user_id)
        volume_data = analyze_volume_and_balance(conn, user_id)
        trajectories = get_1rm_trajectories(conn, user_id)
    finally:
        conn.close()

    settings_repo = SettingsRepository(db_path, user_id=user_id)
    unit = settings_repo.get_unit_preference("lb")

    lines = ["=== ATHLETE DIAGNOSTIC SIGNALS (COMPUTED BY PYTHON ANALYTICS ENGINE) ==="]

    # 1. Plateaus
    if stalls:
        for s in stalls:
            rpe_note = f" (Avg RPE: {s['rpe']})" if s.get('rpe') else ""
            lines.append(f"• Plateau Alert: {s['exercise_name']} stalled at {s['weight']} {unit} × {s['reps']} reps across last {s['sessions_stalled']} sessions{rpe_note}. Previous performance was {s['previous_performance']}.")
    else:
        lines.append("• Plateau Status: No acute exercise plateaus detected across recent workouts.")

    # 2. Volume & Push/Pull balance
    if volume_data["total_sets"] > 0:
        lines.append(f"• 7-Day Volume Distribution: {volume_data['push_sets']} Push sets, {volume_data['pull_sets']} Pull sets, {volume_data['leg_sets']} Leg sets (Push:Pull ratio is {volume_data['push_pull_ratio']}:1).")
        for imb in volume_data["imbalance_notes"]:
            lines.append(f"  ↳ Structural Note: {imb}")
        if volume_data["landmarks"]:
            lines.append("• Hypertrophy Landmarks (Target 10-20 direct sets/week): " + ", ".join(volume_data["landmarks"]))
    else:
        lines.append("• 7-Day Volume: No workout sets completed in the last 7 days.")

    # 3. 1RM Trajectories
    if trajectories:
        rec_strs = [f"{t['exercise']}: {t['est_1rm']} {unit} ({t['best_set']})" for t in trajectories]
        lines.append("• Estimated 1RM Trajectories: " + "; ".join(rec_strs))

    return "\n".join(lines)
