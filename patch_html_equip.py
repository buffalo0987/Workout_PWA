with open("public/index.html", "r") as f:
    html = f.read()

equip_ui = """      <div class="card">
        <h3>Gym Equipment (AI Context)</h3>
        <p style="font-size:0.875rem; color:var(--color-text-muted); margin-bottom: 12px; line-height: 1.4;">List the equipment you have available. The AI Coach will strictly only suggest exercises you can perform.</p>
        <textarea id="settingGymEquipment" class="input-text" style="min-height: 80px;" placeholder="e.g. Dumbbells up to 50lbs, adjustable bench, pull-up bar, no machines."></textarea>
      </div>
"""

# Insert before the last card in view-settings
html = html.replace("""      <div class="card">
        <button class="btn btn-primary btn-full" onclick="saveSettings()">💾 Save Settings & Update Server</button>""", equip_ui + """      <div class="card">
        <button class="btn btn-primary btn-full" onclick="saveSettings()">💾 Save Settings & Update Server</button>""")

with open("public/index.html", "w") as f:
    f.write(html)
