import re
with open("public/js/app.js", "r") as f:
    js = f.read()

# Add timer functions
timer_funcs = """
let restTimerInterval = null;

window.startRestTimer = function(seconds = 90) {
  if (restTimerInterval) clearInterval(restTimerInterval);
  let timeLeft = seconds;
  const banner = document.getElementById('restTimerBanner');
  const display = document.getElementById('restTimerDisplay');
  if (!banner || !display) return;
  
  banner.style.display = 'flex';
  
  const update = () => {
    const mins = Math.floor(timeLeft / 60).toString().padStart(2, '0');
    const secs = (timeLeft % 60).toString().padStart(2, '0');
    display.textContent = `${mins}:${secs}`;
    if (timeLeft <= 0) {
      clearInterval(restTimerInterval);
      banner.style.display = 'none';
      
      // Attempt to play a sound or just alert
      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate([200, 100, 200]);
      }
    }
    timeLeft--;
  };
  
  update();
  restTimerInterval = setInterval(update, 1000);
};

window.stopRestTimer = function() {
  if (restTimerInterval) clearInterval(restTimerInterval);
  const banner = document.getElementById('restTimerBanner');
  if (banner) banner.style.display = 'none';
};

"""
js = js + "\n" + timer_funcs

# Update logSet
old_logset = re.search(r'async function logSet\(sessionId, domPrefixId, exerciseId, setNumber, btnEl\) \{.*?\n\}\n', js, re.DOTALL).group(0)
new_logset = old_logset.replace("async function logSet(sessionId, domPrefixId, exerciseId, setNumber, btnEl) {", "async function logSet(sessionId, domPrefixId, exerciseId, setNumber, btnEl, restSeconds = 90) {")
new_logset = new_logset.replace("btnEl.style.color = 'white';", "btnEl.style.color = 'white';\n      window.startRestTimer(restSeconds);")

js = js.replace(old_logset, new_logset)

# Update renderActiveWorkout to call fetch AI suggestion and add restSeconds
old_render = re.search(r'function renderActiveWorkout\(routine, session\) \{.*?\n\}\n', js, re.DOTALL).group(0)

# Replace the onclick
new_render = old_render.replace("onclick=\"logSet('${session.id}', '${ex.id}', '${ex.exercise_id}', ${i}, this)\"", "onclick=\"logSet('${session.id}', '${ex.id}', '${ex.exercise_id}', ${i}, this, ${ex.rest_seconds || 90})\"")

# Insert fetch AI suggestion loop
fetch_ai_code = """
    routine.exercises.forEach(ex => {
      fetchAISuggestionForExercise(ex.id, ex.exercise_id);
    });
"""
new_render = new_render.replace("  } catch (err) {", fetch_ai_code + "\n  } catch (err) {")

js = js.replace(old_render, new_render)

# Add fetchAISuggestionForExercise
fetch_func = """
async function fetchAISuggestionForExercise(domPrefixId, exerciseId) {
  try {
    const res = await fetch('/api/workouts/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise_ids: [exerciseId] })
    });
    const data = await res.json();
    if (res.ok && data.target) {
      const sets = document.querySelectorAll(`input[id^="log_weight_${domPrefixId}_"]`);
      sets.forEach((wInput) => {
        if (!wInput.value && wInput.placeholder !== '...') wInput.value = data.target.weight;
      });
      const reps = document.querySelectorAll(`input[id^="log_reps_${domPrefixId}_"]`);
      reps.forEach((rInput) => {
        if (!rInput.value && rInput.placeholder !== '...') rInput.value = data.target.reps;
      });
    }
  } catch(e) {
    console.warn("Could not prepopulate", e);
  }
}
"""
js = js + "\n" + fetch_func

with open("public/js/app.js", "w") as f:
    f.write(js)
