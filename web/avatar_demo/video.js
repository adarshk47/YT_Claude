const v = document.getElementById('v'), seek = document.getElementById('seek'), play = document.getElementById('play');
const tv = document.getElementById('tv'), spd = document.getElementById('spd'), sv = document.getElementById('sv');
let scrubbing = false;
v.addEventListener('error', () => { document.getElementById('err').style.display = 'block'; }, true);
function setPlaying(on) {
  play.setAttribute('aria-pressed', String(on)); play.textContent = on ? 'Pause' : 'Play';
  if (on) v.play().catch(() => setPlaying(false)); else v.pause();
}
play.onclick = () => setPlaying(v.paused);
v.addEventListener('loadedmetadata', () => { seek.max = v.duration.toFixed(2); });
v.addEventListener('timeupdate', () => { if (!scrubbing) { seek.value = v.currentTime; tv.textContent = v.currentTime.toFixed(1) + ' s'; } });
seek.addEventListener('input', () => { scrubbing = true; v.pause(); v.currentTime = +seek.value; tv.textContent = (+seek.value).toFixed(1) + ' s'; });
seek.addEventListener('change', () => { scrubbing = false; if (play.getAttribute('aria-pressed') === 'true') v.play().catch(() => {}); });
document.querySelectorAll('button[data-t]').forEach(b => b.onclick = () => { v.currentTime = +b.dataset.t; });
spd.oninput = () => { v.playbackRate = +spd.value; sv.textContent = (+spd.value).toFixed(2).replace(/0$/, '') + '×'; };
setPlaying(true);
window.__v = v;
