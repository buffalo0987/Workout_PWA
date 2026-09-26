with open("public/js/app.js", "r") as f:
    js = f.read()

import re

# Remove the old fetchAISuggestionForExercise loop
old_loop = """    routine.exercises.forEach(ex => {
      fetchAISuggestionForExercise(ex.id, ex.exercise_id);
    });"""

new_loop = """    const exerciseIds = routine.exercises.map(ex => ex.exercise_id);
    fetchAISuggestionForRoutine(exerciseIds, routine.exercises);"""

js = js.replace(old_loop, new_loop)

# Replace fetchAISuggestionForExercise with fetchAISuggestionForRoutine
old_fetch = re.search(r'async function fetchAISuggestionForExercise\(domPrefixId, exerciseId\) \{.*?\n\}\n', js, re.DOTALL).group(0)

new_fetch = """async function fetchAISuggestionForRoutine(exerciseIds, exercises) {
  try {
    const res = await fetch('/api/workouts/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise_ids: exerciseIds })
    });
    const data = await res.json();
    if (res.ok && data.suggestions) {
      data.suggestions.forEach(suggestion => {
        // find corresponding domPrefixId
        const ex = exercises.find(e => e.exercise_id === suggestion.exercise_id);
        if (ex) {
          const domPrefixId = ex.id;
          const sets = document.querySelectorAll(`input[id^="log_weight_${domPrefixId}_"]`);
          sets.forEach((wInput) => {
            if (!wInput.value && wInput.placeholder !== '-') wInput.value = suggestion.suggested_weight;
          });
          const reps = document.querySelectorAll(`input[id^="log_reps_${domPrefixId}_"]`);
          reps.forEach((rInput) => {
            if (!rInput.value && rInput.placeholder !== '-') rInput.value = suggestion.target_reps;
          });
        }
      });
    }
  } catch(e) {
    console.warn("Could not prepopulate", e);
  }
}
"""

js = js.replace(old_fetch, new_fetch)

with open("public/js/app.js", "w") as f:
    f.write(js)
