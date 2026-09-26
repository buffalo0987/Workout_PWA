import json
import sqlite3
import os
import shutil
import uuid

DATA_JSON = "/tmp/exercises-dataset/data/exercises.json"
VIDEOS_DIR = "/tmp/exercises-dataset/videos"
DEST_VIDEOS_DIR = "/home/michael/Documents/Workout App/public/media/exercises"
DB_PATH = "/home/michael/Documents/Workout App/workout_app.db"

os.makedirs(DEST_VIDEOS_DIR, exist_ok=True)

with open(DATA_JSON, 'r') as f:
    exercises = json.load(f)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Clear non-custom exercises
cursor.execute("DELETE FROM exercises WHERE is_custom = 0")

for ex in exercises:
    ex_id = str(uuid.uuid4())
    name = ex.get('name', '').title()
    category = ex.get('equipment', 'body weight')
    primary_muscle = ex.get('target', '')
    secondary = ex.get('secondary_muscles', [])
    desc_val = ex.get('instructions', {}).get('en', '')
    if isinstance(desc_val, list):
        description = "\n".join(desc_val)
    else:
        description = str(desc_val)
    equipment = ex.get('equipment', '')
    
    # Handle GIF copying
    gif_url = ex.get('gif_url')
    images_json = "[]"
    if gif_url:
        src_gif = os.path.join("/tmp/exercises-dataset", gif_url)
        if os.path.exists(src_gif):
            dest_gif_name = f"{ex['id']}.gif"
            shutil.copy2(src_gif, os.path.join(DEST_VIDEOS_DIR, dest_gif_name))
            images_json = json.dumps([f"/media/exercises/{dest_gif_name}"])
            
    cursor.execute("""
        INSERT INTO exercises 
        (id, user_id, name, category, primary_muscle, secondary_muscles, is_custom, description, equipment, images)
        VALUES (?, 'system', ?, ?, ?, ?, 0, ?, ?, ?)
    """, (ex_id, name, category, primary_muscle, json.dumps(secondary), description, equipment, images_json))

conn.commit()
conn.close()
print(f"Inserted {len(exercises)} exercises.")
