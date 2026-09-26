with open("public/js/app.js", "r") as f:
    content = f.read()

import re

old_create = re.search(r'window\.createNewRoutine = async function\(\) \{.*?\n\};\n', content, re.DOTALL).group(0)

new_create = """window.editingRoutineId = null;

window.editRoutine = function(id) {
  const routine = state.routines.find(r => r.id === id);
  if (!routine) return;
  
  window.editingRoutineId = id;
  document.getElementById('newRoutineTitle').value = routine.title || '';
  document.getElementById('newRoutineDesc').value = routine.description || '';
  
  document.querySelectorAll('input[name="routineDay"]').forEach(el => el.checked = false);
  if (routine.schedule_days) {
    routine.schedule_days.forEach(day => {
      const cb = document.querySelector(`input[name="routineDay"][value="${day}"]`);
      if (cb) cb.checked = true;
    });
  }
  
  window.routineBuilderExercises = routine.exercises.map(ex => ({
    tempId: 'rex_' + Date.now() + Math.random(),
    exercise_id: ex.exercise_id,
    name: ex.exercise_name || state.exercises.find(e => e.id === ex.exercise_id)?.name || 'Unknown',
    target_sets: ex.target_sets,
    min_reps: ex.min_reps,
    max_reps: ex.max_reps
  }));
  
  renderRoutineBuilderExercises();
  
  document.getElementById('newRoutineTitle').scrollIntoView({ behavior: 'smooth' });
  const saveBtn = document.querySelector('button[onclick="createNewRoutine()"]');
  if (saveBtn) saveBtn.textContent = "💾 Update Routine Split";
};

window.createNewRoutine = async function() {
  const titleInput = document.getElementById('newRoutineTitle');
  const descInput = document.getElementById('newRoutineDesc');
  const title = titleInput?.value.trim();
  const description = descInput?.value.trim();

  if (!title) {
    alert('Please provide a routine title.');
    return;
  }

  const checkedDays = Array.from(document.querySelectorAll('input[name="routineDay"]:checked')).map((el) => el.value);

  const exercises = window.routineBuilderExercises.map(item => {
    return {
      exercise_id: item.exercise_id,
      target_sets: parseInt(document.getElementById(`rb_sets_${item.tempId}`).value) || 3,
      min_reps: parseInt(document.getElementById(`rb_min_${item.tempId}`).value) || 8,
      max_reps: parseInt(document.getElementById(`rb_max_${item.tempId}`).value) || 12,
    };
  });

  const payload = {
    title,
    description,
    schedule_days: checkedDays,
    exercises,
  };

  try {
    const url = window.editingRoutineId ? `/api/routines?id=${window.editingRoutineId}` : '/api/routines';
    const method = window.editingRoutineId ? 'PUT' : 'POST';
    
    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to save routine');
    
    titleInput.value = '';
    descInput.value = '';
    document.querySelectorAll('input[name="routineDay"]').forEach((el) => (el.checked = false));
    window.routineBuilderExercises = [];
    window.editingRoutineId = null;
    
    const saveBtn = document.querySelector('button[onclick="createNewRoutine()"]');
    if (saveBtn) saveBtn.textContent = "💾 Save Routine Split";
    
    renderRoutineBuilderExercises();
    await loadRoutines();
  } catch (err) {
    console.error('Create/Update routine error:', err);
  }
};
"""

content = content.replace(old_create, new_create)

with open("public/js/app.js", "w") as f:
    f.write(content)
