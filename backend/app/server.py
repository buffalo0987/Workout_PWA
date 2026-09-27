"""
Lightweight Asynchronous HTTP Server for Workout App & PWA
Implements:
1. Static File Serving (PWA UI, Service Worker, Manifest, Icons)
2. POST /api/workouts/suggest
3. POST /api/coaching/feedback
4. GET & POST /api/exercises
5. GET & POST /api/routines
6. POST /api/workouts/sessions
7. GET & POST /api/workouts/sets
8. GET & POST /api/settings
9. GET /health
"""

import sys
import os
import json
import logging
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.controllers import (
    list_exercises,
    create_exercise,
    get_exercise_by_id,
    list_routines,
    create_routine,
    delete_routine,
    create_workout_session,
    log_exercise_set,
    list_workout_sets,
    list_workout_sessions,
    update_workout_session,
    get_workout_session_details,
    suggest_workout_progression,
    generate_coaching_feedback,
    handle_coach_chat,
    get_app_settings,
    update_app_settings,
    test_service_connections
)
from src.database.init_db import init_database

PUBLIC_DIR = Path(__file__).parent.parent.parent / "public"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WorkoutServer")

class WorkoutAPIRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def _read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return {}
            body = self.rfile.read(content_length).decode("utf-8")
            return json.loads(body)
        except Exception as e:
            logger.error(f"Error parsing JSON request: {e}")
            return {}

    def _send_json(self, status, payload):
        self._set_headers(status, "application/json")
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def _serve_static_file(self, relative_path: str):
        if relative_path in ("/", ""):
            relative_path = "index.html"
        clean_path = relative_path.lstrip("/")
        file_path = (PUBLIC_DIR / clean_path).resolve()

        if not str(file_path).startswith(str(PUBLIC_DIR.resolve())):
            self._send_json(403, {"error": "Forbidden"})
            return

        if file_path.is_file():
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"
            if file_path.suffix == ".js":
                content_type = "application/javascript"
            elif file_path.suffix == ".json" or file_path.name == "manifest.json":
                content_type = "application/manifest+json"

            with open(file_path, "rb") as f:
                content = f.read()

            self._set_headers(200, content_type)
            self.wfile.write(content)
        else:
            self._send_json(404, {"error": "File Not Found", "path": relative_path})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path in ("/health", "/api/health"):
                self._send_json(200, {"status": "ok", "service": "workout-api"})
                return

            if path == "/api/exercises":
                exercises = list_exercises()
                self._send_json(200, {"data": exercises, "count": len(exercises)})
                return

            if path == "/api/routines":
                user_id = query.get("user_id", ["default_user"])[0]
                routines = list_routines(user_id)
                self._send_json(200, {"data": routines, "count": len(routines)})
                return

            if path == "/api/settings":
                user_id = query.get("user_id", ["default_user"])[0]
                settings = get_app_settings(user_id)
                self._send_json(200, settings)
                return
            if path == "/api/settings/test-connection":
                user_id = query.get("user_id", ["default_user"])[0]
                results = test_service_connections({"user_id": user_id})
                self._send_json(200, results)
                return

            if path == "/api/workouts/sets":
                workout_exercise_id = query.get("workout_exercise_id", [None])[0]
                session_id = query.get("session_id", [None])[0]
                sets = list_workout_sets(workout_exercise_id=workout_exercise_id, session_id=session_id)
                self._send_json(200, {"data": sets, "count": len(sets)})
                return

            if path == "/api/workouts/sessions":
                user_id = query.get("user_id", ["default_user"])[0]
                sessions = list_workout_sessions(user_id)
                self._send_json(200, {"data": sessions, "count": len(sessions)})
                return
                
            if path == "/api/workouts/sessions/details":
                session_id = query.get("id", [None])[0]
                if not session_id:
                    self._send_json(400, {"error": "id parameter required"})
                    return
                details = get_workout_session_details(session_id)
                self._send_json(200, details)
                return

            if path == "/api/analytics/weekly-volume":
                user_id = query.get("user_id", ["default_user"])[0]
                from backend.app.controllers import get_weekly_muscle_volume
                volume_data = get_weekly_muscle_volume(user_id)
                self._send_json(200, volume_data)
                return

            if path == "/api/analytics/strength-records":
                user_id = query.get("user_id", ["default_user"])[0]
                from backend.app.controllers import get_strength_records
                records = get_strength_records(user_id)
                self._send_json(200, {"records": records})
                return

            if not path.startswith("/api/"):
                self._serve_static_file(path)
                return

            self._send_json(404, {"error": "Not Found", "path": path})

        except Exception as e:
            logger.exception(f"Unhandled GET error: {e}")
            self._send_json(500, {"error": "Internal Server Error", "message": str(e)})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:

            if path == "/api/settings/data":
                user_id = query.get("user_id", ["default_user"])[0]
                from backend.app.controllers import delete_all_user_data
                res = delete_all_user_data(user_id)
                self._send_json(200, res)
                return

            if path == "/api/routines":
                routine_id = query.get("id", [None])[0]
                if routine_id:
                    from backend.app.controllers import delete_routine
                    res = delete_routine(routine_id)
                    self._send_json(200, res)
                    return
            self._send_json(404, {"error": "Not Found", "path": path})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()
        try:
            
            if path.startswith("/api/routines"):
                query = parse_qs(parsed.query)
                routine_id = query.get("id", [None])[0]
                if routine_id:
                    from backend.app.controllers import update_routine
                    res = update_routine(routine_id, body)
                    self._send_json(200, {"data": res, "count": len(res)})
                    return
            if path.startswith("/api/workouts/sessions/"):
                session_id = path.split("/")[-1]
                res = update_workout_session(session_id, body)
                self._send_json(200, res)
                return
            self._send_json(404, {"error": "Not Found", "path": path})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        try:
            if path == "/api/settings/test-connection":
                results = test_service_connections(body)
                self._send_json(200, results)
                return

            if path == "/api/coaching/chat":
                result = handle_coach_chat(body)
                self._send_json(200, result)
                return

            if path == "/api/workouts/suggest":
                result = suggest_workout_progression(body)
                self._send_json(200, result)
                return

            if path == "/api/coaching/feedback":
                result = generate_coaching_feedback(body)
                self._send_json(200, result)
                return

            if path == "/api/exercises":
                created = create_exercise(body)
                self._send_json(201, created)
                return

            if path == "/api/routines":
                created = create_routine(body)
                self._send_json(201, created)
                return

            if path == "/api/settings":
                updated = update_app_settings(body)
                self._send_json(200, updated)
                return

            if path == "/api/workouts/sessions":
                session = create_workout_session(body)
                self._send_json(201, session)
                return

            if path == "/api/workouts/sets":
                logged_set = log_exercise_set(body)
                self._send_json(201, logged_set)
                return

            if path == "/api/workouts/swap-exercise":
                from backend.app.controllers import swap_workout_exercise
                swapped = swap_workout_exercise(body)
                self._send_json(200, swapped)
                return

            self._send_json(404, {"error": "Not Found", "path": path})

        except ValueError as ve:
            self._send_json(400, {"error": "Bad Request", "message": str(ve)})
        except Exception as e:
            logger.exception(f"Unhandled POST error: {e}")
            self._send_json(500, {"error": "Internal Server Error", "message": str(e)})

def run_server(host="0.0.0.0", port=8000):
    init_database()
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, WorkoutAPIRequestHandler)
    logger.info(f"Serving Workout PWA & API on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping server...")
        httpd.server_close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_server(port=port)
