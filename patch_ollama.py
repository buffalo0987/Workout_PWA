with open("backend/app/services/ollama_client.py", "r") as f:
    content = f.read()

import re

old_try = """                try:
                    parsed = json.loads(raw_response)
                except json.JSONDecodeError:
                    parsed = None"""

new_try = """                try:
                    import re
                    clean_res = re.sub(r"^```(?:json)?|```$", "", raw_response.strip(), flags=re.MULTILINE).strip()
                    parsed = json.loads(clean_res)
                except json.JSONDecodeError:
                    print(f"Failed to decode JSON: {raw_response}")
                    parsed = None"""

content = content.replace(old_try, new_try)

with open("backend/app/services/ollama_client.py", "w") as f:
    f.write(content)
