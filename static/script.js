const todayLabel = document.getElementById('today-label');
if (todayLabel) todayLabel.textContent = new Date().toLocaleDateString(undefined, {weekday:'short', month:'short', day:'numeric'});

// Focus timer: 25 minutes by default. It does not need any external library.
(() => {
  const display = document.getElementById('timer-display');
  if (!display) return;
  const startBtn = document.getElementById('timer-start');
  const resetBtn = document.getElementById('timer-reset');
  const status = document.getElementById('timer-status');
  let remaining = 25 * 60;
  let interval = null;
  const render = () => { display.textContent = `${String(Math.floor(remaining/60)).padStart(2,'0')}:${String(remaining%60).padStart(2,'0')}`; };
  startBtn.addEventListener('click', () => {
    if (interval) { clearInterval(interval); interval = null; startBtn.textContent = 'Resume focus'; status.textContent = 'Timer paused'; return; }
    startBtn.textContent = 'Pause timer'; status.textContent = 'You are doing great. Keep going!';
    interval = setInterval(() => {
      remaining -= 1; render();
      if (remaining <= 0) { clearInterval(interval); interval = null; startBtn.textContent = 'Start again'; status.textContent = 'Focus session complete! Take a short break.'; alert('Focus session complete! Take a short break.'); remaining = 25*60; render(); }
    }, 1000);
  });
  resetBtn.addEventListener('click', () => { clearInterval(interval); interval = null; remaining = 25*60; render(); startBtn.textContent = 'Start focus'; status.textContent = '25-minute focus session'; });
  render();
})();
