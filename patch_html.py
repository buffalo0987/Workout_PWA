with open("public/index.html", "r") as f:
    html = f.read()

import re

old_header = re.search(r'<header class="app-header">.*?</header>', html, re.DOTALL).group(0)
new_header = """<header class="app-header">
    <div class="brand-title">
      <span>🔥 Overload</span>
      <span class="brand-badge">AI PWA</span>
    </div>
    <div style="display: flex; align-items: center; gap: 16px;">
      <div class="connection-indicator">
        <div id="statusDot" class="status-dot"></div>
        <span id="statusText">Online</span>
        <span id="offlineQueueCount" style="display:none; color: var(--color-warning); font-weight:600; margin-left: 6px;"></span>
      </div>
      <button class="hamburger-btn" onclick="document.getElementById('mobileMenu').style.display = document.getElementById('mobileMenu').style.display === 'flex' ? 'none' : 'flex'">☰</button>
    </div>
  </header>
  <nav id="mobileMenu" style="display: none; position: fixed; top: 53px; right: 0; background: var(--color-card); border-bottom-left-radius: 12px; border: 1px solid var(--color-card-border); border-top: none; z-index: 100; flex-direction: column; width: 220px; box-shadow: -4px 4px 15px rgba(0,0,0,0.5);">
    <button class="menu-item" onclick="switchView('view-workout'); document.getElementById('mobileMenu').style.display='none';">🏋️ Single Workout</button>
    <button class="menu-item" onclick="switchView('view-routines'); document.getElementById('mobileMenu').style.display='none';">📋 Routines</button>
    <button class="menu-item" onclick="switchView('view-history'); document.getElementById('mobileMenu').style.display='none';">🕒 History</button>
    <button class="menu-item" onclick="switchView('view-coach'); document.getElementById('mobileMenu').style.display='none';">🤖 AI Coach</button>
    <button class="menu-item" onclick="switchView('view-settings'); document.getElementById('mobileMenu').style.display='none';">⚙️ Settings</button>
  </nav>"""

html = html.replace(old_header, new_header)

old_nav = re.search(r'<!-- Bottom Navigation Bar with 4 Views -->\s*<nav class="bottom-nav">.*?</nav>', html, re.DOTALL).group(0)
html = html.replace(old_nav, "")

with open("public/index.html", "w") as f:
    f.write(html)
