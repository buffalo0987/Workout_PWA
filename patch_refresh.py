with open("public/js/app.js", "r") as f:
    js = f.read()

import re

old_refresh = re.search(r'window\.refreshAvailableModels = async function\(\) \{.*?\n\};\n', js, re.DOTALL).group(0)
new_refresh = """window.refreshAvailableModels = async function() {
  const ollamaUrl = document.getElementById('settingOllamaUrl')?.value.trim();
  const select = document.getElementById('settingOllamaModel');
  if (select) select.innerHTML = '<option>Loading...</option>';
  try {
    const res = await fetch('/api/settings/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ollama_base_url: ollamaUrl })
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
"""
js = js.replace(old_refresh, new_refresh)

with open("public/js/app.js", "w") as f:
    f.write(js)
