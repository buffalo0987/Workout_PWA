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
    const res = await fetch(`/api/settings?user_id=${API_USER}`);
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

    const goalSelect = document.getElementById('settingTrainingGoal');
    const levelSelect = document.getElementById('settingExperienceLevel');
    const daysSelect = document.getElementById('settingDaysPerWeek');
    const bodyWeightInput = document.getElementById('settingBodyWeight');
    if (goalSelect && (data.training_goal || data.settings?.training_goal)) {
      goalSelect.value = data.training_goal || data.settings?.training_goal;
    }
    if (levelSelect && (data.experience_level || data.settings?.experience_level)) {
      levelSelect.value = data.experience_level || data.settings?.experience_level;
    }
    if (daysSelect && (data.days_per_week || data.settings?.days_per_week)) {
      daysSelect.value = data.days_per_week || data.settings?.days_per_week;
    }
    if (bodyWeightInput) {
      bodyWeightInput.value = data.body_weight || data.settings?.body_weight || '145';
    }

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
      body: JSON.stringify({ user_id: API_USER, ollama_base_url: ollamaUrl })
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
      body: JSON.stringify({ user_id: API_USER, sparky_base_url: sparkyUrl, sparky_api_token: sparkyToken })
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
  const trainingGoal = document.getElementById('settingTrainingGoal')?.value;
  const expLevel = document.getElementById('settingExperienceLevel')?.value;
  const daysPerWeek = document.getElementById('settingDaysPerWeek')?.value;
  const bodyWeight = parseFloat(document.getElementById('settingBodyWeight')?.value || '145');
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
        training_goal: trainingGoal,
        experience_level: expLevel,
        days_per_week: daysPerWeek,
        body_weight: bodyWeight,
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
    if (profileChanged) {
      window.location.reload();
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
      body: JSON.stringify({ user_id: API_USER, ollama_base_url: ollamaUrl })
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
      body: JSON.stringify({ user_id: API_USER, name, category, primary_muscle, is_custom: true }),
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
      body: JSON.stringify({ user_id: API_USER, exercise_ids: [exerciseId] }),
    });
    const data = await res.json();
    const suggestion = data.suggestions?.[0];

    if (suggestion) {
      state.aiSuggestion = suggestion;
      if (badge) {
        const displayWeight = (suggestion.unit && (suggestion.unit === unitPref || (unitPref === 'lb' && suggestion.unit.startsWith('lb'))))
          ? suggestion.suggested_weight
          : (unitPref === 'lb' ? kgToLb(suggestion.suggested_weight) : suggestion.suggested_weight);
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
      body: JSON.stringify({ user_id: API_USER, }),
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
      body: JSON.stringify({ user_id: API_USER, routine_id: routineId, name: routine.title })
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
        <div style="padding: 12px 16px; background: rgba(0,0,0,0.2); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.06);">
          <div>
            <h3 id="ex_title_${ex.id}" style="font-size: 1.05rem; margin: 0; color: var(--color-primary);">${ex.exercise_name || 'Unknown Exercise'}</h3>
            <span style="font-size: 0.75rem; font-weight: 600; color: var(--color-text-muted); text-transform: uppercase;">${ex.target_sets} Sets</span>
          </div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <button class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem; border-color: rgba(255,255,255,0.2);" onclick="openPlateCalcModal(document.getElementById('log_weight_${ex.id}_1')?.value)" title="Barbell Plate Calculator">🧮 Plates</button>
            <button class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem; border-color: rgba(255,255,255,0.2);" onclick="openWarmupModal('${(ex.exercise_name || 'Exercise').replace(/'/g, "\\'")}', document.getElementById('log_weight_${ex.id}_1')?.value)" title="Automated Warmup Ramp">🌡️ Warm-Up</button>
            <button class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem; border-color: rgba(255,255,255,0.2);" onclick="openSwapModal('${ex.exercise_id}', '${ex.id}', '${(ex.exercise_name || 'Exercise').replace(/'/g, "\\'")}')" title="Swap Exercise">🔄 Swap</button>
          </div>
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
      body: JSON.stringify({ user_id: API_USER, workout_session_id: sessionId,
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
      body: JSON.stringify({ user_id: API_USER, status: 'completed', ended_at: new Date().toISOString() })
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
  loadWeeklyVolumeLandmarks();
  loadStrengthRecords();

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
// AI Coach Chat State
let chatHistory = [];

function formatCoachMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^[•\-\*]\s+(.*)$/gm, '<li style="margin-left: 14px; margin-bottom: 2px;">$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

async function sendCoachMessage() {
  const inputEl = document.getElementById('coachChatInput');
  const text = inputEl.value.trim();
  if (!text) return;
  
  inputEl.value = '';
  
  // Add user message to UI
  chatHistory.push({ role: "user", content: text });
  appendChatMessage(text, 'user');
  
  // Create streaming coach message container
  const coachMsgEl = appendChatMessage('...', 'coach');
  const chatContainer = document.getElementById('coachChatHistory');
  
  let fullCoachReply = '';
  let streamSuccess = false;

  try {
    const res = await fetch(`/api/coaching/chat/stream?user_id=${API_USER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: API_USER, messages: chatHistory })
    });

    if (res.ok && res.body) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // keep partial chunk

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            try {
              const payload = JSON.parse(trimmed.slice(6));
              if (payload.type === 'text') {
                fullCoachReply += payload.delta;
                coachMsgEl.innerHTML = formatCoachMarkdown(fullCoachReply);
                if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
                streamSuccess = true;
              } else if (payload.type === 'action') {
                const totalActions = (payload.routines_created || 0) + (payload.routines_updated || 0) + (payload.routines_deleted || 0);
                if (totalActions > 0) {
                  appendChatMessage(`🛠️ **Routines Updated:** ${payload.details || 'Check your Routines tab!'}`, 'system');
                  loadRoutines(); // Reload routines tab in background
                }
              }
            } catch (jsonErr) {
              // Ignore partial JSON parse
            }
          }
        }
      }
    }
  } catch (streamErr) {
    console.warn('Stream interrupted or failed, falling back to static endpoint:', streamErr);
  }

  // Fallback to static endpoint if stream produced nothing
  if (!streamSuccess || !fullCoachReply.trim()) {
    try {
      const res = await fetch(`/api/coaching/chat?user_id=${API_USER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: API_USER, messages: chatHistory })
      });
      const data = await res.json();
      fullCoachReply = data.reply || 'No response received from coach.';
      coachMsgEl.innerHTML = formatCoachMarkdown(fullCoachReply);
      if (data.routines_created > 0 || data.routines_updated > 0) {
        appendChatMessage(`🛠️ **Routines Updated:** ${data.details || 'Check your Routines tab!'}`, 'system');
        loadRoutines();
      }
    } catch (fallbackErr) {
      coachMsgEl.innerHTML = '<span style="color: var(--color-danger);">Unable to connect to AI Coach service.</span>';
      return;
    }
  }

  if (fullCoachReply) {
    chatHistory.push({ role: "assistant", content: fullCoachReply });
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
    msgDiv.innerHTML = formatCoachMarkdown(text);
    if (isTyping) msgDiv.style.opacity = '0.7';
  } else if (sender === 'system') {
    msgDiv.style.alignSelf = 'center';
    msgDiv.style.background = 'rgba(255,255,255,0.05)';
    msgDiv.style.border = '1px solid rgba(255,255,255,0.1)';
    msgDiv.style.borderRadius = '8px';
    msgDiv.style.color = 'var(--color-accent)';
    msgDiv.style.fontSize = '0.8rem';
    msgDiv.style.padding = '6px 12px';
    msgDiv.innerHTML = formatCoachMarkdown(text);
  }
  
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
  return msgDiv;
}



let restTimerInterval = null;
let wakeLock = null;
let isRestTimerMuted = localStorage.getItem('workout_timer_mute') === 'true';

window.toggleRestTimerMute = function() {
  isRestTimerMuted = !isRestTimerMuted;
  localStorage.setItem('workout_timer_mute', isRestTimerMuted ? 'true' : 'false');
  const btn = document.getElementById('restTimerMuteBtn');
  if (btn) btn.textContent = isRestTimerMuted ? '🔕' : '🔔';
};

function playRestTimerChime() {
  if (isRestTimerMuted) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;
    
    // Tone 1: 587.33 Hz (D5) - warm bell attack
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, now);
    gain1.gain.setValueAtTime(0.25, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.35);

    // Tone 2: 880 Hz (A5) - bright confirmation chime
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(880.0, now + 0.14);
    gain2.gain.setValueAtTime(0.35, now + 0.14);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.65);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.14);
    osc2.stop(now + 0.65);
  } catch (err) {
    console.warn('[Timer] Web Audio chime unavailable:', err);
  }
}

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
  const muteBtn = document.getElementById('restTimerMuteBtn');
  if (muteBtn) muteBtn.textContent = isRestTimerMuted ? '🔕' : '🔔';
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
      
      playRestTimerChime();
      
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
      body: JSON.stringify({ user_id: API_USER, exercise_ids: exerciseIds })
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

// =============================================================================
// Barbell Plate Calculator Modal Logic
// =============================================================================
window.openPlateCalcModal = function(initialWeight) {
  const modal = document.getElementById('modalPlateCalc');
  const input = document.getElementById('plateCalcTargetWeight');
  const barSelect = document.getElementById('plateCalcBarWeight');
  if (!modal || !input) return;
  
  const unit = state.settings?.unit_preference || 'lb';
  if (barSelect) {
    barSelect.value = (unit === 'kg') ? '20' : '45';
  }
  const parsed = parseFloat(initialWeight);
  input.value = (!isNaN(parsed) && parsed > 0) ? parsed : (unit === 'kg' ? 60 : 135);
  modal.style.display = 'flex';
  calculatePlates();
};

window.closePlateCalcModal = function() {
  const modal = document.getElementById('modalPlateCalc');
  if (modal) modal.style.display = 'none';
};

window.calculatePlates = function() {
  const targetWeight = parseFloat(document.getElementById('plateCalcTargetWeight')?.value) || 0;
  const barWeight = parseFloat(document.getElementById('plateCalcBarWeight')?.value) || 45;
  const resultsContainer = document.getElementById('plateCalcResults');
  if (!resultsContainer) return;

  const isKg = (barWeight === 20 || barWeight === 15);
  const unitLabel = isKg ? 'kg' : 'lb';
  
  if (targetWeight <= barWeight) {
    resultsContainer.innerHTML = `
      <div style="font-weight: bold; color: var(--color-primary); font-size: 1.1rem; margin-bottom: 4px;">Empty Bar Only</div>
      <div style="color: var(--color-text-muted); font-size: 0.85rem;">Just the ${barWeight} ${unitLabel} barbell. No plates needed.</div>
    `;
    return;
  }

  const weightPerSide = (targetWeight - barWeight) / 2.0;
  const availablePlates = isKg 
    ? [25, 20, 15, 10, 5, 2.5, 1.25] 
    : [45, 35, 25, 10, 5, 2.5];

  let remaining = weightPerSide;
  const platesPerSide = [];

  for (const plate of availablePlates) {
    const count = Math.floor(remaining / plate);
    if (count > 0) {
      platesPerSide.push({ plate, count });
      remaining = Math.round((remaining - (count * plate)) * 100) / 100;
    }
  }

  const plateColors = {
    45: '#ef4444',
    35: '#3b82f6',
    25: '#eab308',
    10: '#22c55e',
    5: '#94a3b8',
    2.5: '#1e293b',
    20: '#3b82f6',
    15: '#eab308',
    1.25: '#94a3b8'
  };

  let visualSleeveHtml = '<div style="display: flex; align-items: center; justify-content: center; gap: 4px; padding: 14px 4px; overflow-x: auto;">';
  visualSleeveHtml += '<div style="width: 24px; height: 16px; background: #64748b; border-radius: 4px 0 0 4px;" title="Barbell Collar"></div>';
  visualSleeveHtml += '<div style="width: 10px; height: 32px; background: #94a3b8; border-radius: 2px;" title="Collar Ring"></div>';

  platesPerSide.forEach(item => {
    for (let c = 0; c < item.count; c++) {
      const height = Math.min(68, Math.max(28, 24 + item.plate * 0.9));
      const bg = plateColors[item.plate] || '#3b82f6';
      visualSleeveHtml += `
        <div style="height: ${height}px; width: 14px; background: ${bg}; border-radius: 3px; display: flex; align-items: center; justify-content: center; border: 1px solid rgba(0,0,0,0.4); box-shadow: 1px 1px 4px rgba(0,0,0,0.3);" title="${item.plate} ${unitLabel}">
        </div>
      `;
    }
  });

  visualSleeveHtml += '<div style="width: 28px; height: 12px; background: #475569; border-radius: 0 4px 4px 0;" title="Sleeve tip"></div>';
  visualSleeveHtml += '</div>';

  const breakdownList = platesPerSide.map(p => `<strong>${p.count}×</strong> ${p.plate} ${unitLabel}`).join(', ');

  resultsContainer.innerHTML = `
    <div style="font-size: 1.2rem; font-weight: bold; color: var(--color-primary); margin-bottom: 2px;">
      ${weightPerSide} ${unitLabel} <span style="font-size: 0.85rem; font-weight: normal; color: var(--color-text-muted);">per side</span>
    </div>
    ${visualSleeveHtml}
    <div style="font-size: 0.9rem; color: white; margin-top: 6px;">
      ${breakdownList || 'Exact match with available plates'}
    </div>
    ${remaining > 0 ? `<div style="font-size: 0.75rem; color: var(--color-warning); margin-top: 4px;">(${remaining} ${unitLabel} difference from nearest plate)</div>` : ''}
  `;
};

// =============================================================================
// Automated Compound Warm-Up Ramp Generator
// =============================================================================
window.openWarmupModal = function(exerciseName, targetWeight) {
  const modal = document.getElementById('modalWarmupRamp');
  const content = document.getElementById('warmupModalContent');
  const title = document.getElementById('warmupModalTitle');
  if (!modal || !content) return;

  const unit = state.settings?.unit_preference || 'lb';
  const parsed = parseFloat(targetWeight);
  const weight = (!isNaN(parsed) && parsed > 0) ? parsed : (unit === 'kg' ? 60 : 135);
  const barWeight = (unit === 'kg') ? 20 : 45;

  if (title) title.textContent = `🌡️ Warm-Up: ${exerciseName}`;

  const roundIncrement = (unit === 'kg') ? 2.5 : 5;
  const roundWeight = (w) => Math.max(barWeight, Math.round(w / roundIncrement) * roundIncrement);

  const rampSets = [
    { name: '1. Bar Groove', pct: 'Empty Bar', weight: barWeight, reps: 10, rest: '45s', note: 'Groove movement pattern & lubricate joints' },
    { name: '2. Light Primer', pct: '50%', weight: roundWeight(weight * 0.5), reps: 5, rest: '60s', note: 'Move the bar smoothly with speed' },
    { name: '3. Neural Prep', pct: '75%', weight: roundWeight(weight * 0.75), reps: 3, rest: '90s', note: 'Match your working set setup & breathing' },
    { name: '4. Potentiation', pct: '90%', weight: roundWeight(weight * 0.9), reps: 1, rest: '120s', note: 'Heavy confidence single. Zero fatigue' }
  ];

  let tableHtml = `
    <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left; margin-top: 10px;">
      <thead>
        <tr style="color: var(--color-text-muted); font-size: 0.7rem; text-transform: uppercase; border-bottom: 1px solid var(--color-card-border);">
          <th style="padding: 8px 4px;">Set</th>
          <th style="padding: 8px 4px;">Weight (${unit})</th>
          <th style="padding: 8px 4px;">Reps</th>
          <th style="padding: 8px 4px;">Rest</th>
        </tr>
      </thead>
      <tbody>
  `;

  rampSets.forEach((s) => {
    tableHtml += `
      <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
        <td style="padding: 10px 4px;">
          <div style="font-weight: 600; color: white;">${s.name}</div>
          <div style="font-size: 0.7rem; color: var(--color-text-muted);">${s.note}</div>
        </td>
        <td style="padding: 10px 4px; font-weight: bold; color: var(--color-primary); font-size: 1rem;">
          ${s.weight} <span style="font-size: 0.75rem; font-weight: normal; color: var(--color-text-muted);">${s.pct}</span>
        </td>
        <td style="padding: 10px 4px; font-weight: bold;">${s.reps}</td>
        <td style="padding: 10px 4px; color: var(--color-text-muted);">${s.rest}</td>
      </tr>
    `;
  });

  tableHtml += `
      </tbody>
    </table>
    <div style="margin-top: 14px; font-size: 0.8rem; color: var(--color-text-muted); background: rgba(0,0,0,0.25); padding: 10px; border-radius: 6px; line-height: 1.4;">
      💡 <strong>Pro Coach Tip:</strong> Warm-up sets do not count towards working volume landmarks. Take 2–3 minutes of rest after your potentiation single before beginning Set 1!
    </div>
  `;

  content.innerHTML = tableHtml;
  modal.style.display = 'flex';
};

window.closeWarmupModal = function() {
  const modal = document.getElementById('modalWarmupRamp');
  if (modal) modal.style.display = 'none';
};

// =============================================================================
// Exercise Swap Modal Logic
// =============================================================================
let activeSwapContext = null;

window.openSwapModal = async function(currentExerciseId, domPrefixId, currentExerciseName) {
  const modal = document.getElementById('modalSwapExercise');
  const listEl = document.getElementById('swapAlternativesList');
  const subtitle = document.getElementById('swapModalSubtitle');
  if (!modal || !listEl) return;

  activeSwapContext = { currentExerciseId, domPrefixId, currentExerciseName };
  if (subtitle) subtitle.textContent = `Finding alternatives for: ${currentExerciseName}`;
  listEl.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--color-text-muted);">Finding biomechanically matched exercises...</div>';
  modal.style.display = 'flex';

  try {
    const exRes = await fetch(`/api/exercises?user_id=${API_USER}`);
    const exData = await exRes.json();
    const allExercises = exData.data || [];
    
    const curr = allExercises.find(e => e.id === currentExerciseId);
    const targetMuscle = curr ? curr.primary_muscle : '';

    let matches = allExercises.filter(e => e.id !== currentExerciseId && (!targetMuscle || e.primary_muscle === targetMuscle));
    
    if (matches.length === 0) {
      matches = allExercises.filter(e => e.id !== currentExerciseId).slice(0, 10);
    }

    const topPicks = matches.slice(0, 3);
    const remainingPicks = matches.slice(3, 25);

    let html = `
      <div style="font-size: 0.75rem; font-weight: bold; color: var(--color-text-muted); text-transform: uppercase; margin-bottom: 6px;">
        Recommended Substitutes (${targetMuscle ? targetMuscle.toUpperCase() : 'TARGET MUSCLE'}):
      </div>
    `;

    topPicks.forEach(ex => {
      const safeName = ex.name.replace(/'/g, "\\'");
      html += `
        <div style="background: rgba(255,255,255,0.04); border: 1px solid var(--color-card-border); border-radius: 8px; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
          <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            <div style="font-weight: 600; color: white; font-size: 0.9rem;">${ex.name}</div>
            <div style="font-size: 0.75rem; color: var(--color-text-muted);">${ex.equipment || 'Alternative'} &bull; ${ex.category || 'Movement'}</div>
          </div>
          <button class="btn btn-primary" style="padding: 6px 12px; font-size: 0.8rem; flex-shrink: 0;" onclick="applyExerciseSwap('${ex.id}', '${safeName}')">
            Swap In
          </button>
        </div>
      `;
    });

    if (remainingPicks.length > 0) {
      html += `
        <div style="margin-top: 10px;">
          <label style="font-size: 0.75rem; color: var(--color-text-muted); display: block; margin-bottom: 4px;">Or choose any other matching movement:</label>
          <select id="swapSelectOther" class="form-input" style="margin: 0; font-size: 0.85rem;" onchange="if(this.value) { const opt = this.options[this.selectedIndex]; applyExerciseSwap(this.value, opt.text); }">
            <option value="">-- Browse all options --</option>
            ${remainingPicks.map(e => `<option value="${e.id}">${e.name} (${e.equipment || 'Equipment'})</option>`).join('')}
          </select>
        </div>
      `;
    }

    listEl.innerHTML = html;

  } catch(e) {
    console.error('Swap modal error:', e);
    listEl.innerHTML = '<div style="color: var(--color-danger); padding: 16px;">Failed to load exercise alternatives.</div>';
  }
};

window.closeSwapModal = function() {
  const modal = document.getElementById('modalSwapExercise');
  if (modal) modal.style.display = 'none';
  activeSwapContext = null;
};

window.applyExerciseSwap = async function(newExerciseId, newExerciseName) {
  if (!activeSwapContext) return;
  const { currentExerciseId, domPrefixId } = activeSwapContext;

  try {
    await fetch('/api/workouts/swap-exercise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workout_session_id: state.activeWorkoutSession?.id,
        old_exercise_id: currentExerciseId,
        new_exercise_id: newExerciseId
      })
    });

    if (state.activeRoutine && state.activeRoutine.exercises) {
      const targetEx = state.activeRoutine.exercises.find(e => e.id === domPrefixId || e.exercise_id === currentExerciseId);
      if (targetEx) {
        targetEx.exercise_id = newExerciseId;
        targetEx.exercise_name = newExerciseName;
      }
    }

    const titleEl = document.getElementById(`ex_title_${domPrefixId}`);
    if (titleEl) {
      titleEl.textContent = newExerciseName;
    }

    closeSwapModal();

  } catch (err) {
    console.error('Failed to swap exercise:', err);
    alert('Failed to swap exercise on server.');
  }
};

// =============================================================================
// Analytics: Weekly Volume Landmarks & Estimated 1RM Trackers
// =============================================================================
async function loadWeeklyVolumeLandmarks() {
  const container = document.getElementById('historyWeeklyVolume');
  if (!container) return;

  try {
    const res = await fetch(`/api/analytics/weekly-volume?user_id=${API_USER}`);
    const data = await res.json();
    const muscles = data.muscles || [];

    if (muscles.length === 0) {
      container.innerHTML = `
        <div class="card" style="background: rgba(255,255,255,0.02); border: 1px dashed var(--color-card-border); text-align: center; padding: 14px;">
          <div style="font-weight: 600; font-size: 0.9rem; color: var(--color-primary); margin-bottom: 4px;">📊 Weekly Hypertrophy Volume Tracker</div>
          <div style="font-size: 0.75rem; color: var(--color-text-muted);">Complete workout sets this week to track your volume against the 10–20 set science benchmark.</div>
        </div>
      `;
      return;
    }

    let itemsHtml = '';
    muscles.forEach(m => {
      const pct = Math.min(100, Math.round((m.sets / 20) * 100));
      itemsHtml += `
        <div style="margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <span style="font-weight: 600; font-size: 0.85rem; color: white;">${m.muscle}</span>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 0.85rem; font-weight: bold; color: var(--color-primary);">${m.sets} sets</span>
              <span style="font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); color: ${m.color}; font-weight: bold;">${m.badge}</span>
            </div>
          </div>
          <div style="width: 100%; height: 8px; background: rgba(0,0,0,0.4); border-radius: 4px; overflow: hidden; position: relative;">
            <div style="width: ${pct}%; height: 100%; background: ${m.color}; border-radius: 4px; transition: width 0.4s ease;"></div>
          </div>
        </div>
      `;
    });

    container.innerHTML = `
      <div class="card" style="border: 1px solid var(--color-card-border);">
        <div class="card-header" style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h3 class="card-title" style="font-size: 1.05rem;">📊 Weekly Hypertrophy Volume Landmarks</h3>
            <p class="card-subtitle" style="font-size: 0.75rem;">Optimal hypertrophy growth target: 10 to 20 direct sets / week</p>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 0.95rem; font-weight: bold; color: var(--color-primary);">${data.total_weekly_sets} Sets</div>
            <div style="font-size: 0.7rem; color: var(--color-text-muted);">${(data.total_weekly_volume || 0).toLocaleString()} ${data.unit} total</div>
          </div>
        </div>
        ${itemsHtml}
      </div>
    `;

  } catch (err) {
    console.warn('Failed to load weekly volume landmarks:', err);
  }
}

async function loadStrengthRecords() {
  const container = document.getElementById('historyStrengthRecords');
  if (!container) return;

  try {
    const res = await fetch(`/api/analytics/strength-records?user_id=${API_USER}`);
    const data = await res.json();
    const records = data.records || [];

    if (records.length === 0) {
      container.innerHTML = '';
      return;
    }

    let cardsHtml = '';
    records.forEach(r => {
      cardsHtml += `
        <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--color-card-border); border-radius: 8px; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center;">
          <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px;">
            <div style="font-weight: 600; font-size: 0.85rem; color: white;">${r.exercise_name}</div>
            <div style="font-size: 0.7rem; color: var(--color-text-muted);">Best: ${r.best_weight} ${r.unit} × ${r.best_reps} reps ${r.date ? `(${r.date})` : ''}</div>
          </div>
          <div style="text-align: right; flex-shrink: 0;">
            <div style="font-weight: bold; color: var(--color-primary); font-size: 0.95rem;">${r.est_1rm} <span style="font-size: 0.7rem; font-weight: normal; color: var(--color-text-muted);">${r.unit}</span></div>
            <div style="font-size: 0.65rem; color: var(--color-accent); font-weight: bold;">EST. 1RM</div>
          </div>
        </div>
      `;
    });

    container.innerHTML = `
      <div class="card" style="border: 1px solid var(--color-card-border);">
        <div class="card-header" style="margin-bottom: 10px;">
          <div>
            <h3 class="card-title" style="font-size: 1.05rem;">🏆 Estimated 1-Rep Max (1RM) Records</h3>
            <p class="card-subtitle" style="font-size: 0.75rem;">Calculated via Brzycki formula from your top completed sets</p>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px;">
          ${cardsHtml}
        </div>
      </div>
    `;

  } catch (err) {
    console.warn('Failed to load strength records:', err);
  }
}
