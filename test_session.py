import urllib.request
import json
req = urllib.request.Request(
    'http://localhost:8000/api/workouts/sessions',
    data=json.dumps({"routine_id": "a6487b87-565b-4916-a9af-84b0b1aa0c54", "name": "Push Day"}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(req)
print(res.read().decode('utf-8'))
