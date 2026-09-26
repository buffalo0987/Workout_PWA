with open("backend/app/controllers.py", "r") as f:
    code = f.read()

import re

old_update = """    if "unit_preference" in data:
        repo.set_unit_preference(str(data["unit_preference"]).strip())"""

new_update = """    if "unit_preference" in data:
        repo.set_unit_preference(str(data["unit_preference"]).strip())
    if "gym_equipment" in data:
        repo.set_setting("gym_equipment", str(data["gym_equipment"]).strip(), "List of available gym equipment")"""

code = code.replace(old_update, new_update)

old_coach = """    routines = list_routines()
    routines_context = json.dumps(routines, indent=2)

    prompt = f\"\"\""""

new_coach = """    routines = list_routines()
    routines_context = json.dumps(routines, indent=2)
    
    gym_equipment = settings_repo.get_setting("gym_equipment", "")
    equip_constraint = f"\\nCRITICAL: The athlete ONLY has access to the following equipment: {gym_equipment}\\nDo NOT suggest any exercises that require equipment outside of this list." if gym_equipment else ""

    prompt = f\"\"\""""

code = code.replace(old_coach, new_coach)

old_prompt = """Current Routines Data:
{routines_context}

Your capabilities:"""

new_prompt = """Current Routines Data:
{routines_context}{equip_constraint}

Your capabilities:"""

code = code.replace(old_prompt, new_prompt)

with open("backend/app/controllers.py", "w") as f:
    f.write(code)
