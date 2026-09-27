const API_USER = localStorage.getItem('workout_user_id') || 'default_user';
/**
 * Progressive Overload & AI Coaching PWA Application Logic
 * Implements:
 * 1. Offline set logging with IndexedDB & sync queue
 * 2. Real-time Ollama progressive overload calculation
 * 3. AI Weekly coaching insights & SparkyFitness macro display
 * 4. Settings View (Ollama URL/model selection, SparkyFitness URL/API token)
 * 5. Routines & Workout Split Management (Push/Pull/Legs)
 * 6. Exercise Library Expansion & Custom Exercise Creation
 */

// Global State
const kgToLb = (kg) => (kg * 2.20462).toFixed(1);
const lbToKg = (lb) => (lb / 2.20462).toFixed(2);

const state = {
  currentSession: null,
  activeExercise: null,
  exercises: [],
  routines: [],
  settings: {},
  availableModels: [],
  activeModel: 'qwen3:14b',
  offlineQueue: [],
  online: navigator.onLine,
  aiSuggestion: null,
};

// IndexedDB Helper for Offline Resilience
const DB_NAME = 'OverloadAppDB';
const DB_VERSION = 1;

function openOfflineDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pendingSets')) {
        db.createObjectStore('pendingSets', { keyPath: 'sync_id' });
      }
      if (!db.objectStoreNames.contains('localExercises')) {
        db.createObjectStore('localExercises', { keyPath: 'id' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function savePendingSetOffline(setData) {
  const db = await openOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pendingSets', 'readwrite');
    tx.objectStore('pendingSets').put(setData);
    tx.oncomplete = () => {
      console.log('[OfflineStore] Set saved locally to IndexedDB:', setData.sync_id);
      updateOfflineCounter();
      resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}

async function getPendingSets() {
  const db = await openOfflineDB();
  return new Promise((resolve) => {
    const tx = db.transaction('pendingSets', 'readonly');
    const req = tx.objectStore('pendingSets').getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => resolve([]);
  });
}

async function removePendingSet(syncId) {
  const db = await openOfflineDB();
  return new Promise((resolve) => {
    const tx = db.transaction('pendingSets', 'readwrite');
    tx.objectStore('pendingSets').delete(syncId);
    tx.oncomplete = () => resolve();
  });
}

// Network Sync Engine
async function syncOfflineQueue() {
  if (!navigator.onLine) return;
  const pending = await getPendingSets();
  if (!pending || pending.length === 0) return;

  console.log(`[SyncEngine] Attempting to sync ${pending.length} pending sets to backend...`);
  for (const setItem of pending) {
    try {
      const res = await fetch(`/api/workouts/sets?user_id=${API_USER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(setItem),
      });
      if (res.ok) {
        await removePendingSet(setItem.sync_id);
        console.log(`[SyncEngine] Successfully synced set: ${setItem.sync_id}`);
      }
    } catch (e) {
      console.warn(`[SyncEngine] Sync failed for ${setItem.sync_id}, retaining for next attempt`);
      break;
    }
  }
  updateOfflineCounter();
}

async function updateOfflineCounter() {
  const pending = await getPendingSets();
  const badge = document.getElementById('offlineQueueCount');
  if (badge) {
    if (pending.length > 0) {
      badge.textContent = `${pending.length} pending sync`;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }
}

// View Routing
window.switchView = function(viewId) {
  document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));

  const targetView = document.getElementById(viewId);
  const targetNav = document.getElementById(`nav-${viewId}`);
  if (targetView) targetView.classList.add('active');
  if (targetNav) targetNav.classList.add('active');

  if (viewId === 'view-coach') {
    loadCoachingInsights();
  } else if (viewId === 'view-routines') {
    loadRoutines();
  } else if (viewId === 'view-settings') {
    loadSettings();
  } else if (viewId === 'view-history') {
    loadHistory();
  }
};

// =============================================================================
// Settings Manager (Ollama URL/Model & SparkyFitness URL/Token)
// =============================================================================

async function loadSettings() {
  const statusEl = document.getElementById('settingsStatus');
  if (statusEl) statusEl.textContent = 'Loading server settings...';

  try {
    const res = await fetch(`/api/settings?user_id=${targetUserId}`);
    const data = await res.json();
    state.settings = data.settings || {}; state.settings.unit_preference = data.unit_preference || "kg";
    state.availableModels = data.available_models || [];
    state.activeModel = data.active_model || 'qwen3:14b';

    const ollamaUrlInput = document.getElementById('settingOllamaUrl');
    const sparkyUrlInput = document.getElementById('settingSparkyUrl');
    const sparkyTokenInput = document.getElementById('settingSparkyToken');
    const modelSelect = document.getElementById('settingOllamaModel');
    const unitSelect = document.getElementById('settingUnitPref');
    const profileInput = document.getElementById('settingProfileName');
    if (profileInput) profileInput.value = API_USER;
    const weightLabel = document.getElementById('weightLabel');
    const gymEquipInput = document.getElementById('settingGymEquipment');

    if (ollamaUrlInput) ollamaUrlInput.value = data.ollama_base_url || 'http://localhost:11434';
    if (gymEquipInput) gymEquipInput.value = data.settings?.gym_equipment || '';
    if (sparkyUrlInput) sparkyUrlInput.value = data.sparky_base_url || 'http://localhost:8080';
    if (sparkyTokenInput) sparkyTokenInput.value = data.sparky_api_token || '';
    if (unitSelect) unitSelect.value = data.unit_preference || 'kg';
    if (weightLabel) weightLabel.textContent = `Weight (${data.unit_preference || 'kg'})`;

    if (modelSelect) {
      modelSelect.innerHTML = '';
      state.availableModels.forEach((m) => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        if (m === state.activeModel) opt.selected = true;
        modelSelect.appendChild(opt);
      });
    }

    if (statusEl) statusEl.textContent = `Connected to server settings. Active model: ${state.activeModel}`;
  } catch (err) {
    console.warn('[Settings] Failed to fetch settings:', err);
    if (statusEl) statusEl.textContent = 'Unable to reach backend settings endpoint.';
  }
}

// ------------------------------------------------------------
// Connection test helpers
// ------------------------------------------------------------
window.testOllamaConnection = async function() {
  const statusEl = document.getElementById('ollamaTestStatus');
  if (statusEl) statusEl.textContent = 'Testing Ollama connection...';
  try {
    const ollamaUrl = document.getElementById('settingOllamaUrl')?.value.trim();
    const res = await fetch(`/api/settings/test-connection?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, ollama_base_url: ollamaUrl })
    });
    const data = await res.json();
    const result = data.ollama;
    if (statusEl) {
      statusEl.innerHTML = result.status === 'success'
        ? `<span style="color: var(--color-success);">✓ ${result.message} (${result.latency_ms}ms)</span>`
        : `<span style="color: var(--color-danger);">✗ ${result.message}</span>`;
    }
  } catch (e) {
    if (statusEl) {
      statusEl.innerHTML = `<span style="color: var(--color-danger);">✗ Network error: ${e.message || e}</span>`;
    }
  }
};

window.testSparkyConnection = async function() {
  const statusEl = document.getElementById('sparkyTestStatus');
  if (statusEl) statusEl.textContent = 'Testing SparkyFitness...';
  try {
    const sparkyUrl = document.getElementById('settingSparkyUrl')?.value.trim();
    const sparkyToken = document.getElementById('settingSparkyToken')?.value.trim();
    const res = await fetch(`/api/settings/test-connection?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, sparky_base_url: sparkyUrl, sparky_api_token: sparkyToken })
    });
    const data = await res.json();
    const result = data.sparky;
    if (statusEl) {
      statusEl.innerHTML = result.status === 'success'
        ? `<span style="color: var(--color-success);">✓ ${result.message} (${result.latency_ms}ms)</span>`
        : `<span style="color: var(--color-danger);">✗ ${result.message}</span>`;
    }
  } catch (e) {
    if (statusEl) {
      statusEl.innerHTML = `<span style="color: var(--color-danger);">✗ Network error: ${e.message || e}</span>`;
    }
  }
};

window.saveSettings = async function() {
  const statusEl = document.getElementById('settingsStatus');
  const ollamaUrl = document.getElementById('settingOllamaUrl')?.value.trim();
  const sparkyUrl = document.getElementById('settingSparkyUrl')?.value.trim();
  const sparkyToken = document.getElementById('settingSparkyToken')?.value.trim();
  const selectedModel = document.getElementById('settingOllamaModel')?.value;
  const unitPref = document.getElementById('settingUnitPref')?.value;
  const gymEquip = document.getElementById('settingGymEquipment')?.value;
  const profileName = document.getElementById('settingProfileName')?.value || 'default_user';
  let profileChanged = false;
  if (profileName !== API_USER) {
    localStorage.setItem('workout_user_id', profileName);
    profileChanged = true;
  }
  
  // Use the newly typed profile name as the user_id for this save!
  const targetUserId = profileName;

  if (statusEl) statusEl.textContent = 'Saving configuration...';

  try {
    const res = await fetch(`/api/settings?user_id=${targetUserId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, ollama_base_url: ollamaUrl,
        sparky_base_url: sparkyUrl,
        sparky_api_token: sparkyToken,
        selected_ollama_model: selectedModel,
        unit_preference: unitPref,
        gym_equipment: gymEquip,
      }),
    });

    if (!res.ok) throw new Error('Settings update rejected');
    const data = await res.json();
    state.activeModel = data.active_model;
    if (data.settings) state.settings = data.settings;
    if (unitPref) state.settings.unit_preference = unitPref;

    // Refresh UI weight label and fields immediately
    const weightLabel = document.getElementById('weightLabel');
    if (weightLabel) weightLabel.textContent = `Weight (${unitPref})`;

    if (statusEl) {
      statusEl.innerHTML = '<span style="color: var(--color-accent);">✓ Settings successfully saved to database!</span>';
    }
  } catch (e) {
    console.error('[Settings] Save error:', e);
    if (statusEl) {
      statusEl.innerHTML = '<span style="color: var(--color-danger);">Error saving settings. Check server connection.</span>';
    }
  }
};


window.refreshAvailableModels = async function() {
  const ollamaUrl = document.getElementById('settingOllamaUrl')?.value.trim();
  const select = document.getElementById('settingOllamaModel');
  if (select) select.innerHTML = '<option>Loading...</option>';
  try {
    const res = await fetch(`/api/settings/test-connection?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, ollama_base_url: ollamaUrl })
    });
    const data = await res.json();
    if (data.ollama && data.ollama.status === 'success' && data.ollama.models) {
      if (select) {
        select.innerHTML = '';
        data.ollama.models.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m;
          opt.textContent = m;
          select.appendChild(opt);
        });
      }
    } else {
      if (select) select.innerHTML = '<option>Failed to load models</option>';
    }
  } catch(e) {
    if (select) select.innerHTML = '<option>Error</option>';
  }
};

// =============================================================================
// Exercise Management
// =============================================================================

async function fetchExercises() {
  try {
    const res = await fetch(`/api/exercises?user_id=${API_USER}`);
    const data = await res.json();
    state.exercises = data.data || [];
    renderExercisePicker();
    populateRoutineExerciseDropdown();
  } catch (e) {
    console.warn('[API] Could not fetch exercises, using defaults', e);
    state.exercises = [
      { id: 'bench-press-1', name: 'Barbell Bench Press', category: 'barbell', primary_muscle: 'chest' },
      { id: 'overhead-press-1', name: 'Overhead Press', category: 'barbell', primary_muscle: 'shoulders' },
      { id: 'incline-db-1', name: 'Incline DB Press', category: 'dumbbell', primary_muscle: 'chest' },
      { id: 'barbell-squat-1', name: 'Barbell Squat', category: 'barbell', primary_muscle: 'quadriceps' },
      { id: 'romanian-dl-1', name: 'Romanian Deadlift', category: 'barbell', primary_muscle: 'hamstrings' },
      { id: 'pull-up-1', name: 'Pull-Up', category: 'bodyweight', primary_muscle: 'lats' },
    ];
    renderExercisePicker();
    renderRoutineExerciseCheckboxes();
  }
}

function renderExercisePicker(filteredList = null) {
  const select = document.getElementById('exerciseSelect');
  if (!select) return;
  const listToRender = filteredList !== null ? filteredList : state.exercises;
  select.innerHTML = '';
  
  if (listToRender.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No matching exercises found';
    select.appendChild(opt);
    return;
  }

  listToRender.forEach((ex) => {
    const opt = document.createElement('option');
    opt.value = ex.id;
    opt.textContent = `${ex.name} (${ex.category || 'exercise'})`;
    select.appendChild(opt);
  });

  // Preserve or set active exercise
  if (!state.activeExercise || !listToRender.some(e => e.id === state.activeExercise.id)) {
    state.activeExercise = listToRender[0];
  }
  select.value = state.activeExercise.id;
  updateExerciseDetails(state.activeExercise);
  requestProgressionSuggestion();
}

window.filterExerciseList = function() {
  const searchInput = document.getElementById('exerciseSearchInput');
  const muscleSelect = document.getElementById('exerciseMuscleFilter');
  const term = (searchInput?.value || '').toLowerCase().trim();
  const muscle = (muscleSelect?.value || 'all').toLowerCase();

  const filtered = state.exercises.filter((ex) => {
    const nameMatch = !term || (ex.name && ex.name.toLowerCase().includes(term));
    let muscleMatch = true;
    if (muscle !== 'all') {
      const pm = (ex.primary_muscle || '').toLowerCase();
      if (muscle === 'arms') {
        muscleMatch = pm === 'arms' || pm === 'biceps' || pm === 'triceps';
      } else if (muscle === 'legs') {
        muscleMatch = pm === 'legs' || pm === 'quadriceps' || pm === 'hamstrings';
      } else if (muscle === 'core') {
        muscleMatch = pm === 'core' || pm === 'abs' || pm === 'abdominals';
      } else {
        muscleMatch = pm.includes(muscle);
      }
    }
    return nameMatch && muscleMatch;
  });

  renderExercisePicker(filtered);
};

window.onExerciseSelectionChanged = function() {
  const select = document.getElementById('exerciseSelect');
  if (!select || !select.value) return;
  const found = state.exercises.find((e) => e.id === select.value);
  if (found) {
    state.activeExercise = found;
    updateExerciseDetails(found);
    requestProgressionSuggestion();
  }
};

let animationTimer = null;

function updateExerciseDetails(exercise) {
  if (!exercise) return;
  const animBox = document.getElementById('exerciseAnimationBox');
  const muscleBadge = document.getElementById('exMuscleBadge');
  const equipBadge = document.getElementById('exEquipmentBadge');
  const catBadge = document.getElementById('exCategoryBadge');
  const descText = document.getElementById('exDescriptionText');

  // Clear any existing illustration loop
  if (animationTimer) {
    clearInterval(animationTimer);
    animationTimer = null;
  }

  // Parse images if stored as JSON string
  let images = [];
  if (Array.isArray(exercise.images)) {
    images = exercise.images;
  } else if (typeof exercise.images === 'string' && exercise.images) {
    try {
      images = JSON.parse(exercise.images);
    } catch (e) {
      images = [];
    }
  }

  // Parse muscle IDs
  let muscleIds = [];
  if (Array.isArray(exercise.muscle_ids)) {
    muscleIds = exercise.muscle_ids;
  } else if (typeof exercise.muscle_ids === 'string' && exercise.muscle_ids) {
    try {
      muscleIds = JSON.parse(exercise.muscle_ids);
    } catch (e) {
      muscleIds = [];
    }
  }

  if (animBox) {
    if (images && images.length > 0) {
      // GIF or Single Image Available
      animBox.style.background = '#ffffff';
      animBox.innerHTML = `
        <img src="${images[0]}" class="exercise-animation-img" alt="${exercise.name}" style="width:100%; max-height:250px; object-fit:contain; border-radius:12px;">
      `;

    } else if (exercise.animation_svg) {
      animBox.style.background = 'radial-gradient(circle at center, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)';
      animBox.innerHTML = exercise.animation_svg;
    } else {
      animBox.style.background = 'radial-gradient(circle at center, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)';
      animBox.innerHTML = `
        <div style="color:var(--color-text-muted); font-size:0.85rem; display:flex; flex-direction:column; align-items:center; gap:6px;">
          <span style="font-size:2.2rem;">🏋️</span>
          <span style="font-weight:600; color:var(--color-text);">${exercise.name}</span>
          <span style="font-size:0.75rem;">Standard execution: controlled eccentric & full contraction</span>
        </div>`;
    }
  }

  if (muscleBadge) {
    muscleBadge.textContent = `Target: ${exercise.primary_muscle || 'Full Body'}`;
  }
  if (equipBadge) {
    equipBadge.textContent = exercise.equipment || exercise.category || 'Bodyweight';
  }
  if (catBadge) {
    catBadge.textContent = exercise.category ? exercise.category.toUpperCase() : 'COMPOUND';
  }
  if (descText) {
    descText.textContent = exercise.description || 'Focus on controlled tempo and full range of motion with braced core.';
  }
}

window.addNewExercise = async function() {
  const nameInput = document.getElementById('newExerciseName');
  const catInput = document.getElementById('newExerciseCategory');
  const muscleInput = document.getElementById('newExerciseMuscle');

  const name = nameInput?.value.trim();
  const category = catInput?.value || 'barbell';
  const primary_muscle = muscleInput?.value || 'chest';

  if (!name) {
    alert('Please provide an exercise name.');
    return;
  }

  try {
    const res = await fetch(`/api/exercises?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, name, category, primary_muscle, is_custom: true }),
    });
    if (!res.ok) throw new Error('Failed to create exercise');
    const created = await res.json();
    nameInput.value = '';
    await fetchExercises();
    select.value = created.id;
    requestProgressionSuggestion();
    alert(`Added ${created.name} to exercise library!`);
  } catch (err) {
    console.error('Add exercise error:', err);
    alert('Could not save new exercise.');
  }
};

// =============================================================================
// Routines & Schedule Management (e.g. Push Pull Legs)
// =============================================================================

async function loadRoutines() {
  const listEl = document.getElementById('routinesList');
  if (listEl) listEl.innerHTML = '<p style="color:var(--color-text-muted);">Loading routines...</p>';

  try {
    const res = await fetch(`/api/routines?user_id=${API_USER}`);
    const data = await res.json();
    state.routines = data.data || [];
    renderRoutines();
  } catch (e) {
    console.warn('[Routines] Fetch failed:', e);
  }
}

function renderRoutines() {
  const listEl = document.getElementById('routinesList');
  if (!listEl) return;

  if (state.routines.length === 0) {
    listEl.innerHTML = `
      <div style="text-align: center; color: var(--color-text-muted); padding: 16px;">
        <div style="margin-bottom: 12px;">No routines created yet. You can build a custom split below, or let the AI Coach generate a tailored program for your goals!</div>
        <button class="btn btn-outline" style="color: var(--color-primary); border-color: var(--color-primary);" onclick="switchView('view-coach')">🤖 Talk to AI Coach</button>
      </div>
    `;
    return;
  }

  listEl.innerHTML = '';
  state.routines.forEach((routine) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.borderColor = 'rgba(59, 130, 246, 0.25)';

    const daysHtml = (routine.schedule_days || [])
      .map((d) => `<span class="routine-badge">${d}</span>`)
      .join('');

    const exercisesHtml = (routine.exercises || [])
      .map((e) => `<span class="exercise-pill">🏋️ ${e.exercise_name} (${e.target_sets} sets)</span>`)
      .join('');

    card.innerHTML = `
      <div class="card-header" style="align-items: flex-start;">
        <div style="flex-grow: 1;">
          <h3 class="card-title">${routine.title}</h3>
          <p class="card-subtitle">${routine.description || 'Custom workout split'}</p>
          <div style="margin-top: 6px;">${daysHtml}</div>
        </div>
        <div style="display: flex; gap: 6px; flex-shrink: 0;">
          <button class="btn btn-outline" style="color: var(--color-text-muted); border-color: var(--color-card-border); padding: 6px 10px;" onclick="editRoutine('${routine.id}')">✎</button>
          <button class="btn btn-outline" style="color: #ef4444; border-color: #ef4444; padding: 6px 10px;" onclick="deleteRoutine('${routine.id}')">🗑</button>
          <button class="btn btn-primary" onclick="startRoutineWorkout('${routine.id}')">▶ Start</button>
        </div>
      </div>
      <div style="margin-top: 10px;">
        ${exercisesHtml || '<span style="color:var(--color-text-muted); font-size:0.8rem;">No exercises linked.</span>'}
      </div>
    `;
    listEl.appendChild(card);
  });
}

const selectedRoutineExerciseIds = new Set();

function renderRoutineExerciseCheckboxes(filterTerm = '') {
  const container = document.getElementById('routineExerciseCheckboxes');
  if (!container) return;

  // Track existing selections before re-rendering
  container.querySelectorAll('input[name="routineExercise"]:checked').forEach(cb => {
    selectedRoutineExerciseIds.add(cb.value);
  });

  const term = filterTerm.toLowerCase().trim();
  const matched = term
    ? state.exercises.filter(e => e.name.toLowerCase().includes(term) || (e.primary_muscle && e.primary_muscle.toLowerCase().includes(term)))
    : state.exercises.slice(0, 100); // Default to first 100 or checked ones for snappy rendering

  container.innerHTML = '';

  // Always show previously selected items at the top
  const selectedExercises = state.exercises.filter(e => selectedRoutineExerciseIds.has(e.id));
  const combinedList = Array.from(new Set([...selectedExercises, ...matched]));

  if (combinedList.length === 0) {
    container.innerHTML = '<div style="color:var(--color-text-muted); font-size:0.8rem; padding:4px;">No matching exercises found.</div>';
    return;
  }

  combinedList.forEach((ex) => {
    const isChecked = selectedRoutineExerciseIds.has(ex.id);
    const label = document.createElement('label');
    label.style.display = 'flex';
    label.style.alignItems = 'center';
    label.style.gap = '8px';
    label.style.fontSize = '0.85rem';
    label.style.margin = '4px 0';
    label.innerHTML = `
      <input type="checkbox" name="routineExercise" value="${ex.id}" ${isChecked ? 'checked' : ''} onchange="toggleRoutineExerciseSelection('${ex.id}', this.checked)">
      <span>${ex.name} <small style="color:var(--color-text-muted);">(${ex.equipment || ex.category})</small></span>
    `;
    container.appendChild(label);
  });
}

window.toggleRoutineExerciseSelection = function(exerciseId, isChecked) {
  if (isChecked) {
    selectedRoutineExerciseIds.add(exerciseId);
  } else {
    selectedRoutineExerciseIds.delete(exerciseId);
  }
};

window.populateRoutineExerciseDropdown = function() {
  const select = document.getElementById('routineExerciseSelector');
  if (!select) return;
  
  let html = '<option value="">+ Add Exercise to Routine</option>';
  state.exercises.forEach(ex => {
    html += `<option value="${ex.id}">${ex.name} (${ex.primary_muscle})</option>`;
  });
  select.innerHTML = html;
};

window.routineBuilderExercises = [];

window.addSelectedExerciseToRoutineUI = function(selectEl) {
  const exId = selectEl.value;
  if (!exId) return;
  
  const ex = state.exercises.find(e => e.id === exId);
  if (!ex) return;
  
  const tempId = 'rex_' + Date.now();
  window.routineBuilderExercises.push({
    tempId,
    exercise_id: exId,
    name: ex.name
  });
  
  renderRoutineBuilderExercises();
  selectEl.value = ''; // Reset
};

window.removeRoutineBuilderExercise = function(tempId) {
  window.routineBuilderExercises = window.routineBuilderExercises.filter(e => e.tempId !== tempId);
  renderRoutineBuilderExercises();
};

function renderRoutineBuilderExercises() {
  const container = document.getElementById('routineSelectedExercises');
  if (!container) return;
  
  container.innerHTML = '';
  window.routineBuilderExercises.forEach(item => {
    const div = document.createElement('div');
    div.style = "background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; display: flex; flex-direction: column; gap: 6px;";
    div.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.9rem; font-weight: bold;">${item.name}</span>
        <button class="btn btn-outline" style="color: var(--color-danger); border-color: var(--color-danger); padding: 2px 6px;" onclick="removeRoutineBuilderExercise('${item.tempId}')">✕</button>
      </div>
      <div style="display: flex; gap: 8px; align-items: center;">
        <div style="flex: 1;">
          <label style="font-size: 0.7rem; color: var(--color-text-muted);">Sets</label>
          <input type="number" id="rb_sets_${item.tempId}" class="form-input" value="${item.target_sets || 3}" min="1" style="margin: 0; padding: 4px;">
        </div>
        <div style="flex: 1;">
          <label style="font-size: 0.7rem; color: var(--color-text-muted);">Min Reps</label>
          <input type="number" id="rb_min_${item.tempId}" class="form-input" value="${item.min_reps || 8}" min="1" style="margin: 0; padding: 4px;">
        </div>
        <div style="flex: 1;">
          <label style="font-size: 0.7rem; color: var(--color-text-muted);">Max Reps</label>
          <input type="number" id="rb_max_${item.tempId}" class="form-input" value="${item.max_reps || 12}" min="1" style="margin: 0; padding: 4px;">
        </div>
      </div>
    `;
    container.appendChild(div);
  });
}

window.editingRoutineId = null;

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


// =============================================================================
// Progressive Overload Suggestion & Active Workout
// =============================================================================

window.requestProgressionSuggestion = async function() {
  const select = document.getElementById('exerciseSelect');
  const exerciseId = select ? select.value : state.activeExercise?.id;
  if (!exerciseId) return;

  const badge = document.getElementById('aiTargetBadge');
  const rationaleBox = document.getElementById('aiRationale');
  const targetWeightInput = document.getElementById('targetWeight');
  const targetRepsInput = document.getElementById('targetReps');

  if (badge) badge.textContent = 'Analyzing overload...';

  try {
    const res = await fetch(`/api/workouts/suggest?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, exercise_ids: [exerciseId] }),
    });
    const data = await res.json();
    const suggestion = data.suggestions?.[0];

    if (suggestion) {
      state.aiSuggestion = suggestion;
      if (badge) {
        const unitPref = state.settings.unit_preference || 'kg';
const displayWeight = unitPref === 'lb' ? kgToLb(suggestion.suggested_weight) : suggestion.suggested_weight;
badge.innerHTML = `⚡ Target: <strong>${displayWeight}${unitPref}</strong> &times; <strong>${suggestion.target_reps}</strong> reps (${suggestion.strategy})`;
      }
      if (rationaleBox) {
        rationaleBox.textContent = `AI Coach (${suggestion.model_used}): ${suggestion.rationale}`;
      }
      if (targetWeightInput) targetWeightInput.value = displayWeight;
      if (targetRepsInput) {
        const repVal = String(suggestion.target_reps).split('-')[0];
        targetRepsInput.value = repVal || 8;
      }
    }
  } catch (err) {
    console.warn('[API] Suggestion request failed', err);
    const unitPref = state.settings.unit_preference || 'kg';
    const fallbackWt = unitPref === 'lb' ? '176.4' : '80.0';
    if (badge) badge.textContent = `Target: ${fallbackWt}${unitPref} × 8-10 reps (Local Target)`;
    if (rationaleBox) rationaleBox.textContent = 'Heuristic: Consolidate reps before adding load.';
  }
};

window.logCompletedSet = async function() {
  const select = document.getElementById('exerciseSelect');
  const exerciseId = select ? select.value : state.activeExercise?.id;
  const rawWeightInput = parseFloat(document.getElementById('targetWeight')?.value || '0');
  const reps = parseInt(document.getElementById('targetReps')?.value || '0', 10);
  const rpe = parseFloat(document.getElementById('targetRpe')?.value || '8.0');
  
  // Convert to kilograms if UI is displaying pounds for persistence
  const unitPref = state.settings.unit_preference || 'kg';
  const weightKg = unitPref === 'lb' ? parseFloat(lbToKg(rawWeightInput)) : rawWeightInput;

  if (!state.currentSession) {
    state.currentSession = {
      id: 'session-' + Date.now(),
      name: 'Today Workout',
    };
  }

  const syncId = 'set-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
  const setPayload = {
    workout_session_id: state.currentSession.id,
    exercise_id: exerciseId,
    set_number: document.querySelectorAll('#completedSetsList tr').length + 1,
    weight: weightKg,
    reps,
    rpe,
    is_completed: true,
    completed_at: new Date().toISOString(),
    sync_id: syncId,
    source: 'mobile_pwa',
  };

  appendSetToUI(setPayload, rawWeightInput, unitPref);

  try {
    const res = await fetch(`/api/workouts/sets?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(setPayload),
    });
    if (!res.ok) throw new Error('API rejection');
    console.log('[API] Set successfully committed to server:', syncId);
  } catch (err) {
    console.warn('[Network] Offline or server timeout. Saving set to IndexedDB queue:', err);
    await savePendingSetOffline(setPayload);
  }

  triggerDynamicMidWorkoutAdjustment(setPayload);
};

function appendSetToUI(setData, displayWeight, unit) {
  const tbody = document.getElementById('completedSetsList');
  if (!tbody) return;

  const row = document.createElement('tr');
  const unitLabel = unit || state.settings.unit_preference || 'kg';
  const wt = displayWeight !== undefined ? displayWeight : (unitLabel === 'lb' ? kgToLb(setData.weight) : setData.weight);
  row.innerHTML = `
    <td><strong>#${setData.set_number}</strong></td>
    <td>${wt} ${unitLabel}</td>
    <td>${setData.reps}</td>
    <td>RPE ${setData.rpe}</td>
    <td><span style="color: var(--color-accent); font-weight:600;">✓ Done</span></td>
  `;
  tbody.appendChild(row);
}

function triggerDynamicMidWorkoutAdjustment(lastSet) {
  const rationaleBox = document.getElementById('aiRationale');
  const weightInput = document.getElementById('targetWeight');

  if (lastSet.rpe >= 9.5) {
    if (rationaleBox) rationaleBox.textContent = `⚡ Mid-workout Adaptation: High exertion (RPE ${lastSet.rpe}) logged. Lowering next set load by 5% to prevent fatigue failure.`;
    if (weightInput) weightInput.value = (lastSet.weight * 0.95).toFixed(1);
  } else if (lastSet.rpe <= 7.0 && lastSet.reps >= 10) {
    if (rationaleBox) rationaleBox.textContent = `⚡ Mid-workout Adaptation: High bar speed (RPE ${lastSet.rpe}). Adding 2.5kg for next set.`;
    if (weightInput) weightInput.value = (lastSet.weight + 2.5).toFixed(1);
  } else {
    if (rationaleBox) rationaleBox.textContent = `⚡ Set #${lastSet.set_number} confirmed. Maintain load and target clean rep execution.`;
  }
}

// =============================================================================
// AI Coaching & Nutrition Insights
// =============================================================================

async function loadCoachingInsights() {
  const container = document.getElementById('coachingInsightsList');
  const calsEl = document.getElementById('macroCalories');
  const proteinEl = document.getElementById('macroProtein');
  const carbsEl = document.getElementById('macroCarbs');
  const fatEl = document.getElementById('macroFat');

  if (container) container.innerHTML = '<p style="color:var(--color-text-muted);">Consulting Ollama coach and Sparky macros...</p>';

  try {
    const res = await fetch(`/api/coaching/feedback?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, }),
    });
    const data = await res.json();
    const insights = data.insights || [];
    const nutrition = data.weekly_metrics?.weekly_nutrition || {};

    if (calsEl) calsEl.textContent = `${nutrition.avg_calories || 0} kcal`;
    if (proteinEl) proteinEl.textContent = `${nutrition.avg_protein_g || 0}g`;
    if (carbsEl) carbsEl.textContent = `${nutrition.avg_carbs_g || 0}g`;
    if (fatEl) fatEl.textContent = `${nutrition.avg_fat_g || 0}g`;

    if (container) {
      container.innerHTML = '';
      const icons = ['training', 'nutrition', 'recovery'];
      const glyphs = ['🏋️', '🥩', '💤'];

      insights.forEach((bullet, idx) => {
        const item = document.createElement('div');
        item.className = 'insight-item';
        item.innerHTML = `
          <div class="insight-icon ${icons[idx % 3]}">${glyphs[idx % 3]}</div>
          <div class="insight-text">${bullet}</div>
        `;
        container.appendChild(item);
      });
    }
  } catch (e) {
    console.warn('[API] Coaching fetch failed, showing fallback guidance', e);
  }
}

// =============================================================================
// Connectivity & Boot
// =============================================================================

window.addEventListener('online', () => {
  const dot = document.getElementById('statusDot');
  const txt = document.getElementById('statusText');
  if (dot) dot.className = 'status-dot';
  if (txt) txt.textContent = 'Online';
  syncOfflineQueue();
});

window.addEventListener('offline', () => {
  const dot = document.getElementById('statusDot');
  const txt = document.getElementById('statusText');
  if (dot) dot.className = 'status-dot offline';
  if (txt) txt.textContent = 'Offline Mode';
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((reg) => console.log('[ServiceWorker] Registered with scope:', reg.scope))
      .catch((err) => console.warn('[ServiceWorker] Registration error:', err));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  fetchExercises();
  loadSettings();
  updateOfflineCounter();
  syncOfflineQueue();
});

// =============================================================================
// Active Workout, History, and AI Coach Chat
// =============================================================================

async function deleteRoutine(id) {
  // removed confirm
  try {
    const res = await fetch(`/api/routines?id=${id}&user_id=${API_USER}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete routine');
    await loadRoutines();
  } catch (err) {
    console.error(err);
    // removed alert
  }
}

let workoutTimerInterval = null;

async function startRoutineWorkout(routineId) {
  const routine = state.routines.find(r => r.id === routineId);
  if (!routine) return;
  
  try {
    const res = await fetch(`/api/workouts/sessions?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, routine_id: routineId, name: routine.title })
    });
    const session = await res.json();
    state.activeSessionId = session.id;
    state.activeSessionStart = Date.now();
    
    // Render the active workout UI
    renderActiveWorkout(routine, session);
    switchView('view-active-workout');
    
    if (workoutTimerInterval) clearInterval(workoutTimerInterval);
    stopRestTimer();
    workoutTimerInterval = setInterval(() => {
      const el = document.getElementById('activeWorkoutTimer');
      if (!el) return;
      const elapsed = Math.floor((Date.now() - state.activeSessionStart) / 1000);
      const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
      const secs = String(elapsed % 60).padStart(2, '0');
      el.textContent = `${mins}:${secs}`;
    }, 1000);
    
  } catch(e) {
    console.error(e);
    alert('Could not start workout.');
  }
}

function renderActiveWorkout(routine, session) {
  try {
    document.getElementById('activeWorkoutTitle').textContent = session.name;
    const container = document.getElementById('activeWorkoutExercises');
    
    if (!container) return;
    container.innerHTML = '';
    
    if (!routine.exercises || routine.exercises.length === 0) {
      container.innerHTML = '<div style="padding: 16px; color: var(--color-warning);">No exercises found in this routine.</div>';
      return;
    }
    
    routine.exercises.forEach((ex, index) => {
      const exCard = document.createElement('div');
      exCard.style.cssText = "background: rgba(255,255,255,0.03); border: 1px solid var(--color-card-border); border-radius: 12px; overflow: hidden; margin-bottom: 16px;";
      
      let setsHtml = '';
      for (let i = 1; i <= ex.target_sets; i++) {
        setsHtml += `
          <tr style="border-top: 1px solid rgba(255,255,255,0.05);">
            <td style="padding: 8px 4px; font-weight: 600; color: var(--color-text-muted);">${i}</td>
            <td style="padding: 8px 4px;">
              <input type="number" id="log_weight_${ex.id}_${i}" style="width: 70px; text-align: center; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: white; padding: 8px; font-size: 1rem;" placeholder="...">
            </td>
            <td style="padding: 8px 4px;">
              <input type="number" id="log_reps_${ex.id}_${i}" style="width: 70px; text-align: center; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: white; padding: 8px; font-size: 1rem;" placeholder="...">
            </td>
            <td style="padding: 8px 4px;">
              <button class="btn" style="background: var(--color-card-border); color: var(--color-text); border: none; padding: 8px 16px; border-radius: 6px; font-size: 1rem;" onclick="logSet('${session.id}', '${ex.id}', '${ex.exercise_id}', ${i}, this, ${ex.rest_seconds || 90}, ${i === ex.target_sets})">✓</button>
            </td>
          </tr>
        `;
      }
      
      exCard.innerHTML = `
        <div style="padding: 12px 16px; background: rgba(0,0,0,0.15); display: flex; justify-content: space-between; align-items: center;">
          <h3 style="font-size: 1.05rem; margin: 0; color: var(--color-primary);">${ex.exercise_name || 'Unknown Exercise'}</h3>
          <span style="font-size: 0.75rem; font-weight: 600; color: var(--color-text-muted); text-transform: uppercase;">${ex.target_sets} Sets</span>
        </div>
        <table style="width: 100%; text-align: center; border-collapse: collapse; font-size: 0.85rem;">
          <thead>
            <tr style="color: var(--color-text-muted); font-size: 0.7rem; text-transform: uppercase;">
              <th style="padding: 10px 4px; font-weight: 600;">Set</th>
              <th style="padding: 10px 4px; font-weight: 600;">${state.settings?.unit_preference || "kg"}</th>
              <th style="padding: 10px 4px; font-weight: 600;">Reps</th>
              <th style="padding: 10px 4px;"><span style="visibility: hidden;">Done</span></th>
            </tr>
          </thead>
          <tbody>
            ${setsHtml}
          </tbody>
        </table>
      `;
      container.appendChild(exCard);
    });

    const exerciseIds = routine.exercises.map(ex => ex.exercise_id);
    fetchAISuggestionForRoutine(exerciseIds, routine.exercises);

  } catch (err) {
    console.error("renderActiveWorkout error:", err);
    alert("Error rendering workout: " + err.message);
  }
}

async function logSet(sessionId, domPrefixId, exerciseId, setNumber, btnEl, restSeconds = 90, isLastSet = false) {
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
  

  let rpeToLog = null;
  if (isLastSet) {
    const rpeInput = prompt("Great job finishing that exercise! What was your RPE (Rate of Perceived Exertion) on that final set? (1-10)\n\n10 = Absolute failure, couldn't do another rep.\n8 = Hard, but had 2 reps left in the tank.\n6 = Warmup weight, moved fast.");
    if (rpeInput !== null && rpeInput.trim() !== '') {
      rpeToLog = parseFloat(rpeInput);
    }
  }

  try {
    const res = await fetch(`/api/workouts/sets?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, workout_session_id: sessionId,
        exercise_id: exerciseId,
        set_number: setNumber,
        weight: parseFloat(weight),
        reps: parseInt(reps),
        rpe: rpeToLog
      })
    });
    
    if (res.ok) {
      btnEl.textContent = '✓';
      btnEl.style.background = 'var(--color-success)';
      btnEl.style.color = 'white';
      window.startRestTimer(restSeconds);
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

async function finishWorkout() {
  if (!state.activeSessionId) return;
  if (!confirm("Are you ready to finish this workout?")) return;
  
  try {
    const res = await fetch(`/api/workouts/sessions/${state.activeSessionId}?user_id=${API_USER}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, status: 'completed', ended_at: new Date().toISOString() })
    });
    
    if (workoutTimerInterval) clearInterval(workoutTimerInterval);
    stopRestTimer();
    state.activeSessionId = null;
    alert("Workout completed successfully! Great job.");
    loadHistory();
    switchView('view-history');
  } catch(e) {
    console.error(e);
    alert("Failed to finish workout");
  }
}

async function loadHistory() {
  const container = document.getElementById('historyList');
  container.innerHTML = '<div style="text-align: center; padding: 20px;">Loading history...</div>';
  try {
    const res = await fetch(`/api/workouts/sessions?user_id=${API_USER}`);
    const data = await res.json();
    
    if (data.data.length === 0) {
      container.innerHTML = '<div style="text-align: center; color: var(--color-text-muted); padding: 16px;">No workouts logged yet.</div>';
      return;
    }
    
    container.innerHTML = '';
    data.data.forEach(session => {
      const card = document.createElement('div');
      card.className = 'card';
      const dateStr = new Date(session.started_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
      card.innerHTML = `
        <div class="card-header" style="cursor: pointer;" onclick="toggleHistoryDetails('${session.id}')">
          <div>
            <h3 class="card-title">${session.name}</h3>
            <p class="card-subtitle">${dateStr} &bull; ${session.status}</p>
          </div>
          <span style="color:var(--color-primary);">▼</span>
        </div>
        <div id="history_details_${session.id}" style="display: none; margin-top: 10px; border-top: 1px solid var(--color-card-border); padding-top: 10px;">
          <div style="text-align: center; color: var(--color-text-muted); font-size: 0.8rem;">Loading...</div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch(e) {
    console.error(e);
    container.innerHTML = '<div style="color: var(--color-danger); padding: 16px;">Error loading history.</div>';
  }
}

async function toggleHistoryDetails(sessionId) {
  const detailsEl = document.getElementById(`history_details_${sessionId}`);
  if (detailsEl.style.display === 'block') {
    detailsEl.style.display = 'none';
    return;
  }
  detailsEl.style.display = 'block';
  
  try {
    const res = await fetch(`/api/workouts/sessions/details?id=${sessionId}&user_id=${API_USER}`);
    const data = await res.json();
    
    if (!data.exercises || data.exercises.length === 0) {
      detailsEl.innerHTML = '<div style="color: var(--color-text-muted); font-size: 0.8rem;">No sets logged.</div>';
      return;
    }
    
    let html = '';
    data.exercises.forEach(ex => {
      let setsStr = ex.sets.map(s => `<span class="routine-badge">${s.weight}x${s.reps}</span>`).join(' ');
      html += `
        <div style="margin-bottom: 8px;">
          <div style="font-weight: 600; font-size: 0.85rem; margin-bottom: 4px;">${ex.name}</div>
          <div>${setsStr || '<span style="color:var(--color-text-muted); font-size:0.75rem;">Skipped</span>'}</div>
        </div>
      `;
    });
    detailsEl.innerHTML = html;
  } catch(e) {
    console.error(e);
    detailsEl.innerHTML = '<div style="color: var(--color-danger); font-size: 0.8rem;">Error loading details.</div>';
  }
}

// AI Coach Chat State
let chatHistory = [];

async function sendCoachMessage() {
  const inputEl = document.getElementById('coachChatInput');
  const text = inputEl.value.trim();
  if (!text) return;
  
  inputEl.value = '';
  
  // Add user message to UI
  chatHistory.push({ role: "user", content: text });
  appendChatMessage(text, 'user');
  
  // Show typing indicator
  const typingId = appendChatMessage('Coach is thinking...', 'coach', true);
  
  try {
    const res = await fetch(`/api/coaching/chat?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, messages: chatHistory })
    });
    const data = await res.json();
    
    // Remove typing indicator
    document.getElementById(typingId)?.remove();
    
    // Add coach reply to UI
    chatHistory.push({ role: "assistant", content: data.reply });
    appendChatMessage(data.reply, 'coach');
    
    if (data.routines_created > 0) {
      appendChatMessage(`*I have updated your routines! Check the Routines tab.*`, 'system');
      loadRoutines(); // reload routines in background
    }
    
  } catch (err) {
    console.error(err);
    document.getElementById(typingId)?.remove();
    appendChatMessage('Sorry, I encountered an error connecting to Ollama.', 'system');
  }
}

function appendChatMessage(text, sender, isTyping = false) {
  const container = document.getElementById('coachChatHistory');
  const msgDiv = document.createElement('div');
  const msgId = 'msg_' + Date.now();
  msgDiv.id = msgId;
  msgDiv.style.padding = '8px 12px';
  msgDiv.style.borderRadius = '12px';
  msgDiv.style.maxWidth = '85%';
  msgDiv.style.fontSize = '0.9rem';
  msgDiv.style.lineHeight = '1.4';
  
  if (sender === 'user') {
    msgDiv.style.alignSelf = 'flex-end';
    msgDiv.style.background = 'var(--color-primary)';
    msgDiv.style.color = '#fff';
    msgDiv.textContent = text;
  } else if (sender === 'coach') {
    msgDiv.style.alignSelf = 'flex-start';
    msgDiv.style.background = 'var(--color-card-border)';
    msgDiv.style.color = 'var(--color-text)';
    msgDiv.innerHTML = text.replace(/\n/g, '<br>');
    if (isTyping) msgDiv.style.opacity = '0.7';
  } else if (sender === 'system') {
    msgDiv.style.alignSelf = 'center';
    msgDiv.style.background = 'transparent';
    msgDiv.style.color = 'var(--color-accent)';
    msgDiv.style.fontStyle = 'italic';
    msgDiv.style.fontSize = '0.8rem';
    msgDiv.innerHTML = text;
  }
  
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
  return msgId;
}



let restTimerInterval = null;
let wakeLock = null;

window.startRestTimer = async function(seconds = 90) {
  try {
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      console.log('Screen Wake Lock active');
    }
  } catch (err) {
    console.log('Wake Lock error:', err);
  }
  if (restTimerInterval) clearInterval(restTimerInterval);
  const targetTime = Date.now() + (seconds * 1000);
  const banner = document.getElementById('restTimerBanner');
  const display = document.getElementById('restTimerDisplay');
  if (!banner || !display) return;
  
  banner.style.display = 'flex';
  
  const update = () => {
    let timeLeft = Math.max(0, Math.round((targetTime - Date.now()) / 1000));
    const mins = Math.floor(timeLeft / 60).toString().padStart(2, '0');
    const secs = (timeLeft % 60).toString().padStart(2, '0');
    display.textContent = `${mins}:${secs}`;
    if (timeLeft <= 0) {
      clearInterval(restTimerInterval);
      banner.style.display = 'none';
      
      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate([200, 100, 200]);
      }
      if (wakeLock !== null) {
        wakeLock.release().then(() => { wakeLock = null; });
      }
    }
  };
  
  update();
  restTimerInterval = setInterval(update, 1000);
};

window.stopRestTimer = function() {
  if (restTimerInterval) clearInterval(restTimerInterval);
  if (wakeLock !== null) {
    wakeLock.release().then(() => { wakeLock = null; });
  }
  const banner = document.getElementById('restTimerBanner');
  if (banner) banner.style.display = 'none';
};



async function fetchAISuggestionForRoutine(exerciseIds, exercises) {
  try {
    const res = await fetch(`/api/workouts/suggest?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: targetUserId, exercise_ids: exerciseIds })
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
            if (!rInput.value && rInput.placeholder !== '-') {
              const repMatch = String(suggestion.target_reps).match(/\d+/);
              rInput.value = repMatch ? repMatch[0] : 8;
            }
          });
        }
      });
    }
  } catch(e) {
    console.warn("Could not prepopulate", e);
  }
}

window.deleteAllUserData = async function() {
  if (confirm("Are you ABSOLUTELY sure you want to permanently delete ALL of your routines, workouts, and settings?\n\nThis action cannot be undone.")) {
    try {
      const res = await fetch(`/api/settings/data?user_id=${API_USER}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        alert("All your data has been successfully deleted.");
        window.location.reload();
      } else {
        alert("Failed to delete data. Server returned an error.");
      }
    } catch(e) {
      alert("Network error while trying to delete data.");
    }
  }
};
