import re
with open("public/js/app.js", "r") as f:
    js = f.read()

old_timer = """window.startRestTimer = function(seconds = 90) {
  if (restTimerInterval) clearInterval(restTimerInterval);
  let timeLeft = seconds;
  const banner = document.getElementById('restTimerBanner');
  const display = document.getElementById('restTimerDisplay');
  if (!banner || !display) return;
  
  banner.style.display = 'flex';
  
  const update = () => {
    const mins = Math.floor(timeLeft / 60).toString().padStart(2, '0');
    const secs = (timeLeft % 60).toString().padStart(2, '0');
    display.textContent = `${mins}:${secs}`;
    if (timeLeft <= 0) {
      clearInterval(restTimerInterval);
      banner.style.display = 'none';
      
      // Attempt to play a sound or just alert
      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate([200, 100, 200]);
      }
    }
    timeLeft--;
  };
  
  update();
  restTimerInterval = setInterval(update, 1000);
};"""

new_timer = """window.startRestTimer = function(seconds = 90) {
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
    }
  };
  
  update();
  restTimerInterval = setInterval(update, 1000);
};"""

js = js.replace(old_timer, new_timer)
with open("public/js/app.js", "w") as f:
    f.write(js)
