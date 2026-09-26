with open("public/js/app.js", "r") as f:
    js = f.read()

import re

# Patch renderActiveWorkout button
js = js.replace("onclick=\"logSet('${session.id}', '${ex.exercise_id}', ${i}, this)\"", "onclick=\"logSet('${session.id}', '${ex.id}', '${ex.exercise_id}', ${i}, this)\"")

# Patch logSet function definition
old_logset = re.search(r'async function logSet\(sessionId, exerciseId, setNumber, btnEl\) \{.*?\n\}\n', js, re.DOTALL).group(0)

new_logset = """async function logSet(sessionId, domPrefixId, exerciseId, setNumber, btnEl) {
  const weightInput = document.getElementById(`log_weight_${domPrefixId}_${setNumber}`);
  const repsInput = document.getElementById(`log_reps_${domPrefixId}_${setNumber}`);
  
  if (!weightInput || !repsInput) return;
  const weight = weightInput.value;
  const reps = repsInput.value;
  
  if (!reps || !weight) {
    alert("Please enter weight and reps");
    return;
  }
  
  btnEl.textContent = '...';
  btnEl.disabled = true;
  
  try {
    const res = await fetch('/api/workouts/sets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workout_session_id: sessionId,
        exercise_id: exerciseId,
        set_number: setNumber,
        weight: parseFloat(weight),
        reps: parseInt(reps),
        rpe: null
      })
    });
    
    if (res.ok) {
      btnEl.textContent = '✓';
      btnEl.style.background = 'var(--color-success)';
      btnEl.style.color = 'white';
    } else {
      throw new Error("Failed to save set");
    }
  } catch (err) {
    console.error(err);
    alert('Failed to log set');
    btnEl.textContent = '✓';
    btnEl.disabled = false;
  }
}
"""

js = js.replace(old_logset, new_logset)

with open("public/js/app.js", "w") as f:
    f.write(js)
