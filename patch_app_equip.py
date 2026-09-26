with open("public/js/app.js", "r") as f:
    js = f.read()

import re

# Patch loadSettings
old_load = """    const unitSelect = document.getElementById('settingUnitPref');
    const weightLabel = document.getElementById('weightLabel');

    if (ollamaUrlInput) ollamaUrlInput.value = data.ollama_base_url || 'http://localhost:11434';"""

new_load = """    const unitSelect = document.getElementById('settingUnitPref');
    const weightLabel = document.getElementById('weightLabel');
    const gymEquipInput = document.getElementById('settingGymEquipment');

    if (ollamaUrlInput) ollamaUrlInput.value = data.ollama_base_url || 'http://localhost:11434';
    if (gymEquipInput) gymEquipInput.value = data.settings?.gym_equipment || '';"""

js = js.replace(old_load, new_load)

# Patch saveSettings
old_save = """  const selectedModel = document.getElementById('settingOllamaModel')?.value;
  const unitPref = document.getElementById('settingUnitPref')?.value;

  if (statusEl) statusEl.textContent = 'Saving configuration...';"""

new_save = """  const selectedModel = document.getElementById('settingOllamaModel')?.value;
  const unitPref = document.getElementById('settingUnitPref')?.value;
  const gymEquip = document.getElementById('settingGymEquipment')?.value;

  if (statusEl) statusEl.textContent = 'Saving configuration...';"""

js = js.replace(old_save, new_save)

old_save_body = """      body: JSON.stringify({
        ollama_base_url: ollamaUrl,
        sparky_base_url: sparkyUrl,
        sparky_api_token: sparkyToken,
        selected_ollama_model: selectedModel,
        unit_preference: unitPref,
      }),"""

new_save_body = """      body: JSON.stringify({
        ollama_base_url: ollamaUrl,
        sparky_base_url: sparkyUrl,
        sparky_api_token: sparkyToken,
        selected_ollama_model: selectedModel,
        unit_preference: unitPref,
        gym_equipment: gymEquip,
      }),"""

js = js.replace(old_save_body, new_save_body)

with open("public/js/app.js", "w") as f:
    f.write(js)
