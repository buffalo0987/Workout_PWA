import re
with open("public/js/app.js", "r") as f:
    js = f.read()

# Update logSet definition to take isLastSet
old_logset = re.search(r'async function logSet\(sessionId, domPrefixId, exerciseId, setNumber, btnEl, restSeconds = 90\) \{.*?\n\}\n', js, re.DOTALL).group(0)

new_logset = old_logset.replace("async function logSet(sessionId, domPrefixId, exerciseId, setNumber, btnEl, restSeconds = 90) {", "async function logSet(sessionId, domPrefixId, exerciseId, setNumber, btnEl, restSeconds = 90, isLastSet = false) {")

# Add the prompt logic inside logSet, right before try {
rpe_logic = """
  let rpeToLog = null;
  if (isLastSet) {
    const rpeInput = prompt("Great job finishing that exercise! What was your RPE (Rate of Perceived Exertion) on that final set? (1-10)\\n\\n10 = Absolute failure, couldn't do another rep.\\n8 = Hard, but had 2 reps left in the tank.\\n6 = Warmup weight, moved fast.");
    if (rpeInput !== null && rpeInput.trim() !== '') {
      rpeToLog = parseFloat(rpeInput);
    }
  }
"""
new_logset = new_logset.replace("  try {", rpe_logic + "\n  try {")

# Replace rpe: null with rpe: rpeToLog
new_logset = new_logset.replace("rpe: null", "rpe: rpeToLog")

js = js.replace(old_logset, new_logset)

# Update renderActiveWorkout onclick
old_render = re.search(r'function renderActiveWorkout\(routine, session\) \{.*?\n\}\n', js, re.DOTALL).group(0)
new_render = old_render.replace("onclick=\"logSet('${session.id}', '${ex.id}', '${ex.exercise_id}', ${i}, this, ${ex.rest_seconds || 90})\"", "onclick=\"logSet('${session.id}', '${ex.id}', '${ex.exercise_id}', ${i}, this, ${ex.rest_seconds || 90}, ${i === ex.target_sets})\"")

js = js.replace(old_render, new_render)

with open("public/js/app.js", "w") as f:
    f.write(js)
