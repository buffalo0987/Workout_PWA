import re

with open("backend/app/controllers.py", "r") as f:
    content = f.read()

update_routine_func = """
def update_routine(routine_id: str, data: dict) -> list:
    title = data.get("title")
    description = data.get("description", "")
    import json
    schedule_days = json.dumps(data.get("schedule_days", []))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(\"\"\"
            UPDATE routines 
            SET title = ?, description = ?, schedule_days = ?
            WHERE id = ?
        \"\"\", (title, description, schedule_days, routine_id))
        
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
            cursor.execute(\"\"\"
                INSERT INTO routine_exercises (id, routine_id, exercise_id, order_index, target_sets, min_reps, max_reps, rest_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            \"\"\", (re_id, routine_id, ex_id, idx, target_sets, min_reps, max_reps, rest_seconds))
            
        conn.commit()
    return list_routines()
"""

if "def update_routine" not in content:
    content = content.replace("def create_routine", update_routine_func + "\ndef create_routine")
    with open("backend/app/controllers.py", "w") as f:
        f.write(content)

with open("backend/app/server.py", "r") as f:
    server_content = f.read()

if "path.startswith(\"/api/routines\"):" not in server_content:
    put_logic = """
            if path.startswith("/api/routines"):
                query = parse_qs(parsed.query)
                routine_id = query.get("id", [None])[0]
                if routine_id:
                    from backend.app.controllers import update_routine
                    res = update_routine(routine_id, body)
                    self._send_json(200, {"data": res, "count": len(res)})
                    return
"""
    server_content = server_content.replace('if path.startswith("/api/workouts/sessions/"):', put_logic + '            if path.startswith("/api/workouts/sessions/"):')
    with open("backend/app/server.py", "w") as f:
        f.write(server_content)
