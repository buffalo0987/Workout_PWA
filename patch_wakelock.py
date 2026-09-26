import re
with open("public/js/app.js", "r") as f:
    js = f.read()

# Add wake lock variable at the top of the timer section
timer_decl = "let restTimerInterval = null;"
js = js.replace(timer_decl, "let restTimerInterval = null;\nlet wakeLock = null;")

# In startRestTimer, request wake lock
old_start = "window.startRestTimer = function(seconds = 90) {"
new_start = """window.startRestTimer = async function(seconds = 90) {
  try {
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      console.log('Screen Wake Lock active');
    }
  } catch (err) {
    console.log('Wake Lock error:', err);
  }"""
js = js.replace(old_start, new_start)

# Release wake lock when timer finishes
old_finish = """      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate([200, 100, 200]);
      }"""
new_finish = """      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate([200, 100, 200]);
      }
      if (wakeLock !== null) {
        wakeLock.release().then(() => { wakeLock = null; });
      }"""
js = js.replace(old_finish, new_finish)

# Release wake lock in stopRestTimer
old_stop = """window.stopRestTimer = function() {
  if (restTimerInterval) clearInterval(restTimerInterval);"""
new_stop = """window.stopRestTimer = function() {
  if (restTimerInterval) clearInterval(restTimerInterval);
  if (wakeLock !== null) {
    wakeLock.release().then(() => { wakeLock = null; });
  }"""
js = js.replace(old_stop, new_stop)

with open("public/js/app.js", "w") as f:
    f.write(js)
