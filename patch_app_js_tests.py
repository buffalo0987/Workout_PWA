with open("public/js/app.js", "r") as f:
    js = f.read()

import re

old_ollama = re.search(r'window\.testOllamaConnection = async function\(\) \{.*?\n\};\n', js, re.DOTALL).group(0)
new_ollama = """window.testOllamaConnection = async function() {
  const statusEl = document.getElementById('ollamaTestStatus');
  if (statusEl) statusEl.textContent = 'Testing Ollama connection...';
  try {
    const ollamaUrl = document.getElementById('settingOllamaUrl')?.value.trim();
    const res = await fetch('/api/settings/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ollama_base_url: ollamaUrl })
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
"""
js = js.replace(old_ollama, new_ollama)

old_sparky = re.search(r'window\.testSparkyConnection = async function\(\) \{.*?\n\};\n', js, re.DOTALL).group(0)
new_sparky = """window.testSparkyConnection = async function() {
  const statusEl = document.getElementById('sparkyTestStatus');
  if (statusEl) statusEl.textContent = 'Testing SparkyFitness...';
  try {
    const sparkyUrl = document.getElementById('settingSparkyUrl')?.value.trim();
    const sparkyToken = document.getElementById('settingSparkyToken')?.value.trim();
    const res = await fetch('/api/settings/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sparky_base_url: sparkyUrl, sparky_api_token: sparkyToken })
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
"""
js = js.replace(old_sparky, new_sparky)

with open("public/js/app.js", "w") as f:
    f.write(js)
