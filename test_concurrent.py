import threading
import time
import urllib.request
import json

def request_ai():
    t0 = time.time()
    try:
        req = urllib.request.Request("http://localhost:8000/api/workouts/suggest", method="POST", data=json.dumps({"exercise_ids": ["bench-press-1"]}).encode("utf-8"), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=90)
        print(f"AI returned in {time.time() - t0:.2f}s")
    except Exception as e:
        print(f"AI failed: {e}")

def request_routines():
    t0 = time.time()
    try:
        urllib.request.urlopen("http://localhost:8000/api/routines", timeout=5)
        print(f"Routines returned in {time.time() - t0:.2f}s")
    except Exception as e:
        print(f"Routines failed: {e}")

t1 = threading.Thread(target=request_ai)
t1.start()
time.sleep(1) # wait for AI to start
t2 = threading.Thread(target=request_routines)
t2.start()

t1.join()
t2.join()
