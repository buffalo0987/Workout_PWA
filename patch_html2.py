with open("public/index.html", "r") as f:
    html = f.read()

import re

# Hamburger on the left
old_header = re.search(r'<header class="app-header">.*?</header>', html, re.DOTALL).group(0)
new_header = """<header class="app-header" style="justify-content: flex-start; gap: 16px;">
    <button class="hamburger-btn" onclick="document.getElementById('mobileMenu').style.display = document.getElementById('mobileMenu').style.display === 'flex' ? 'none' : 'flex'">☰</button>
    <div class="brand-title" style="flex-grow: 1;">
      <span>🔥 Overload</span>
      <span class="brand-badge">AI PWA</span>
    </div>
    <div class="connection-indicator">
      <div id="statusDot" class="status-dot"></div>
      <span id="statusText">Online</span>
      <span id="offlineQueueCount" style="display:none; color: var(--color-warning); font-weight:600; margin-left: 6px;"></span>
    </div>
  </header>"""

html = html.replace(old_header, new_header)

# Mobile menu style update (left side)
old_menu = re.search(r'<nav id="mobileMenu" style=".*?</nav>', html, re.DOTALL).group(0)
new_menu = old_menu.replace("right: 0;", "left: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 12px;").replace("box-shadow: -4px 4px 15px rgba(0,0,0,0.5);", "box-shadow: 4px 4px 15px rgba(0,0,0,0.5);")
html = html.replace(old_menu, new_menu)

# Rest timer banner
timer_html = """  <!-- Floating Rest Timer -->
  <div id="restTimerBanner" style="display: none; position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); background: var(--color-primary); color: white; padding: 12px 24px; border-radius: 30px; font-weight: bold; box-shadow: 0 4px 15px rgba(0,0,0,0.5); z-index: 1000; align-items: center; gap: 12px; font-size: 1.1rem;">
    ⏳ Rest: <span id="restTimerDisplay" style="font-family: monospace; font-size: 1.2rem;">01:30</span>
    <button onclick="stopRestTimer()" style="background: rgba(0,0,0,0.3); border: none; color: white; border-radius: 50%; width: 28px; height: 28px; line-height: 1; cursor: pointer;">✕</button>
  </div>
"""

# Insert before </main>
html = html.replace("  </main>", timer_html + "\n  </main>")

with open("public/index.html", "w") as f:
    f.write(html)
