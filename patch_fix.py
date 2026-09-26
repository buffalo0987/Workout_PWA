with open("public/js/app.js", "r") as f:
    js = f.read()

bad_code = "if (!rInput.value && rInput.placeholder !== '-') const repMatch = String(suggestion.target_reps).match(/\d+/); rInput.value = repMatch ? repMatch[0] : 8;"

good_code = """if (!rInput.value && rInput.placeholder !== '-') {
              const repMatch = String(suggestion.target_reps).match(/\\d+/);
              rInput.value = repMatch ? repMatch[0] : 8;
            }"""

js = js.replace(bad_code, good_code)

with open("public/js/app.js", "w") as f:
    f.write(js)
