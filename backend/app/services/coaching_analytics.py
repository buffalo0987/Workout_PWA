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
    Calculates weekly sets per muscle group, upper-body push:pull ratio,
    and week-over-week volume tonnage delta (0-7d vs 7-14d).
    """
    now = datetime.now(timezone.utc)
    cutoff_cur = (now - timedelta(days=days)).isoformat()
    cutoff_prev = (now - timedelta(days=days * 2)).isoformat()

    cursor = conn.cursor()
    # 1. Current Window (0-7 days)
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
    """, (user_id, cutoff_cur))
    rows_cur = cursor.fetchall()

    muscle_sets = {r["muscle"]: r["set_count"] for r in rows_cur}
    current_tonnage = sum(float(r["tonnage"] or 0.0) for r in rows_cur)

    # 2. Previous Window (7-14 days)
    cursor.execute("""
        SELECT 
            COUNT(es.id) as prev_sets,
            ROUND(SUM(es.weight * es.reps), 1) as prev_tonnage
        FROM exercise_sets es
        JOIN workout_exercises we ON es.workout_exercise_id = we.id
        JOIN exercises e ON we.exercise_id = e.id
        JOIN workout_sessions ws ON we.workout_session_id = ws.id
        WHERE ws.user_id = ? AND es.completed_at >= ? AND es.completed_at < ? AND es.is_completed = 1
    """, (user_id, cutoff_prev, cutoff_cur))
    prev_row = cursor.fetchone()
    prev_sets = prev_row["prev_sets"] if prev_row and prev_row["prev_sets"] else 0
    prev_tonnage = float(prev_row["prev_tonnage"] or 0.0) if prev_row and prev_row["prev_tonnage"] else 0.0

    tonnage_delta = round(current_tonnage - prev_tonnage, 1)
    if prev_tonnage > 0:
        tonnage_pct_change = round(((current_tonnage - prev_tonnage) / prev_tonnage) * 100.0, 1)
    else:
        tonnage_pct_change = None

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
        "landmarks": landmarks[:6],
        "current_tonnage": round(current_tonnage, 1),
        "prev_tonnage": round(prev_tonnage, 1),
        "tonnage_delta": tonnage_delta,
        "tonnage_pct_change": tonnage_pct_change,
        "prev_sets": prev_sets,
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

def compute_energy_and_macro_targets(user_id: str, db_path: str) -> Dict[str, Any]:
    """
    Computes exact athlete TDEE, lean bulking caloric surplus target, and protein target
    in Python. Compares against recent SparkyFitness 3-day averages to determine
    exact surplus/deficit status.
    """
    settings_repo = SettingsRepository(db_path, user_id=user_id)
    unit = settings_repo.get_unit_preference("lb")
    
    # Bodyweight setting or default (145 lb / 66 kg)
    try:
        raw_bw = settings_repo.get_setting("body_weight", "145" if unit == "lb" else "66")
        body_weight = float(raw_bw) if raw_bw else (145.0 if unit == "lb" else 66.0)
    except (ValueError, TypeError):
        body_weight = 145.0 if unit == "lb" else 66.0

    weight_lbs = body_weight if unit == "lb" else round(body_weight * 2.20462, 1)
    weight_kg = round(weight_lbs / 2.20462, 1)

    # Deterministic physiological formulas:
    # 1. Maintenance Calories (TDEE Baseline): 15 kcal per lb
    maintenance_cals = round(weight_lbs * 15.0)
    # 2. Hypertrophy Lean Bulking Target: Maintenance + 300 kcal surplus
    bulking_target_cals = maintenance_cals + 300
    # 3. Protein Target: 0.9g per lb of bodyweight (range 0.8 - 1.0 g/lb)
    protein_target_g = round(weight_lbs * 0.9)
    # 4. Carb & Fat fueling targets: 50% carbs, 25% fats
    carb_target_g = round((bulking_target_cals * 0.50) / 4.0)
    fat_target_g = round((bulking_target_cals * 0.25) / 9.0)

    # Ingest SparkyFitness 3-day nutrition averages
    from backend.app.services.sparky_client import get_daily_summary
    sparky_url = settings_repo.get_sparky_base_url()
    sparky_token = settings_repo.get_sparky_api_token()

    avg_cals = 0.0
    avg_protein = 0.0
    days_found = 0
    now = datetime.now(timezone.utc)

    if sparky_url and sparky_token:
        try:
            total_c = 0.0
            total_p = 0.0
            for i in range(3):
                target_d = now - timedelta(days=i)
                summ = get_daily_summary(target_d, base_url=sparky_url, api_token=sparky_token)
                if not summ.get("is_fallback") or summ.get("calories", 0) > 0:
                    total_c += summ.get("calories", 0)
                    total_p += summ.get("protein_grams", 0)
                    days_found += 1
            if days_found > 0:
                avg_cals = round(total_c / days_found, 1)
                avg_protein = round(total_p / days_found, 1)
        except Exception:
            pass

    has_nutrition = (days_found > 0 and avg_cals > 0)
    caloric_delta = round(avg_cals - bulking_target_cals, 0) if has_nutrition else 0
    protein_delta = round(avg_protein - protein_target_g, 0) if has_nutrition else 0

    if not has_nutrition:
        diagnostic_text = (
            f"Athlete Profile: {body_weight:g} {unit}. "
            f"Targets: Maintenance = {maintenance_cals:,} kcal, "
            f"Lean Bulk Target = {bulking_target_cals:,} kcal (+300 kcal surplus), "
            f"Protein Target = {protein_target_g}g ({round(protein_target_g/weight_lbs, 2)}g/lb). "
            f"No active SparkyFitness logs found for the last 3 days."
        )
    elif caloric_delta < -150:
        diagnostic_text = (
            f"SparkyFitness 3-Day Avg: {int(avg_cals):,} kcal, {int(avg_protein)}g protein. "
            f"CALORIC DEFICIT DETECTED: {int(caloric_delta)} kcal below the {bulking_target_cals:,} kcal bulking target "
            f"({int(maintenance_cals):,} kcal maintenance). Protein is {int(avg_protein)}g vs {protein_target_g}g target "
            f"({int(protein_delta)}g delta). Energy deficit blunts hypertrophy recovery and progressive overload capacity."
        )
    elif -150 <= caloric_delta <= 200:
        diagnostic_text = (
            f"SparkyFitness 3-Day Avg: {int(avg_cals):,} kcal, {int(avg_protein)}g protein. "
            f"OPTIMAL SURPLUS: Intake is {int(avg_cals):,} kcal ({int(caloric_delta):+d} kcal vs {bulking_target_cals:,} kcal target). "
            f"Protein target ({protein_target_g}g) is {'achieved' if protein_delta >= 0 else f'near target ({int(protein_delta)}g)'}. "
            f"Energy and substrate availability are primed for progressive overload."
        )
    else:
        diagnostic_text = (
            f"SparkyFitness 3-Day Avg: {int(avg_cals):,} kcal, {int(avg_protein)}g protein. "
            f"HIGH SURPLUS: Intake is {int(avg_cals):,} kcal (+{int(caloric_delta)} kcal over {bulking_target_cals:,} kcal target). "
            f"Protein is {int(avg_protein)}g (Target: {protein_target_g}g). Recommend trimming surplus toward +300 kcal to maximize lean mass ratio."
        )

    return {
        "body_weight": body_weight,
        "unit": unit,
        "maintenance_cals": maintenance_cals,
        "bulking_target_cals": bulking_target_cals,
        "protein_target_g": protein_target_g,
        "carb_target_g": carb_target_g,
        "fat_target_g": fat_target_g,
        "avg_cals": avg_cals,
        "avg_protein": avg_protein,
        "caloric_delta": caloric_delta,
        "protein_delta": protein_delta,
        "days_found": days_found,
        "diagnostic_text": diagnostic_text
    }

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
    macro_data = compute_energy_and_macro_targets(user_id, db_path)

    lines = ["=== ATHLETE DIAGNOSTIC SIGNALS (COMPUTED BY PYTHON ANALYTICS ENGINE) ==="]

    # 1. Fueling & Energy Diagnostics
    lines.append(f"• Fueling & Energy Status: {macro_data['diagnostic_text']}")

    # 2. Plateaus
    if stalls:
        for s in stalls:
            rpe_note = f" (Avg RPE: {s['rpe']})" if s.get('rpe') else ""
            lines.append(f"• Plateau Alert: {s['exercise_name']} stalled at {s['weight']} {unit} × {s['reps']} reps across last {s['sessions_stalled']} sessions{rpe_note}. Previous performance was {s['previous_performance']}.")
    else:
        lines.append("• Plateau Status: No acute exercise plateaus detected across recent workouts.")

    # 3. Volume & Push/Pull balance + Week-over-Week Tonnage Delta
    if volume_data["total_sets"] > 0:
        delta_str = ""
        if volume_data["tonnage_pct_change"] is not None:
            delta_str = f" ({volume_data['tonnage_pct_change']:+g}% vs previous 7-day window)"
        elif volume_data["prev_tonnage"] == 0:
            delta_str = " (baseline week)"
        lines.append(f"• Weekly Volume Load: {int(volume_data['current_tonnage']):,} {unit} total tonnage{delta_str}, {volume_data['total_sets']} completed sets.")
        lines.append(f"• 7-Day Balance: {volume_data['push_sets']} Push sets, {volume_data['pull_sets']} Pull sets, {volume_data['leg_sets']} Leg sets (Push:Pull ratio is {volume_data['push_pull_ratio']}:1).")
        for imb in volume_data["imbalance_notes"]:
            lines.append(f"  ↳ Structural Note: {imb}")
        if volume_data["landmarks"]:
            lines.append("• Hypertrophy Landmarks (Target 10-20 direct sets/week): " + ", ".join(volume_data["landmarks"]))
    else:
        lines.append("• 7-Day Volume: No workout sets completed in the last 7 days.")

    # 4. 1RM Trajectories
    if trajectories:
        rec_strs = [f"{t['exercise']}: {t['est_1rm']} {unit} ({t['best_set']})" for t in trajectories]
        lines.append("• Estimated 1RM Trajectories: " + "; ".join(rec_strs))

    return "\n".join(lines)

