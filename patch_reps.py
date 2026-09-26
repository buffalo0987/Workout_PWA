with open("public/js/app.js", "r") as f:
    js = f.read()

import re
js = js.replace("rInput.value = suggestion.target_reps;", "const repMatch = String(suggestion.target_reps).match(/\\d+/); rInput.value = repMatch ? repMatch[0] : 8;")

with open("public/js/app.js", "w") as f:
    f.write(js)
