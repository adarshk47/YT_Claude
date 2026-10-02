import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const DEG = Math.PI / 180;
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const stage = document.getElementById('stage');

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(dark ? 0x151a22 : 0xeef1f5);
scene.fog = new THREE.Fog(scene.background, 9, 22);
const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 60);
camera.position.set(2.1, 1.4, 3.1);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.78, 0);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 1.5;
controls.maxDistance = 9;

scene.add(new THREE.HemisphereLight(0xffffff, dark ? 0x222a38 : 0x9aa4b4, dark ? 1.1 : 1.5));
const sun = new THREE.DirectionalLight(0xffffff, dark ? 2.0 : 2.6);
sun.position.set(3, 5, 4);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 1, far: 15 });
scene.add(sun);

// ---- floor: shadow catcher + scrolling grid (walk/run scroll it backwards)
const floor = new THREE.Mesh(new THREE.CircleGeometry(30, 64).rotateX(-Math.PI / 2),
  new THREE.MeshStandardMaterial({ color: dark ? 0x1b212b : 0xdfe4ec, roughness: 1 }));
floor.receiveShadow = true;
scene.add(floor);
const CELL = 0.5;
const grid = new THREE.GridHelper(24, 48, dark ? 0x3a4556 : 0xb9c2cf, dark ? 0x2a3342 : 0xc9d0db);
grid.position.y = 0.002;
scene.add(grid);

// ---- avatar --------------------------------------------------------------
const mat = (c, r = 0.65) => new THREE.MeshStandardMaterial({ color: c, roughness: r });
const M = {
  skin: mat(0xc58a65, 0.55), shirt: mat(0x3d6fb0), pants: mat(0x343a4a), shoe: mat(0x1f2229, 0.5),
  hair: mat(0x2a1d16, 0.5), white: mat(0xf4f1ea, 0.3), dark: mat(0x111111, 0.3), mouth: mat(0x5a1d1d, 0.6),
  lip: mat(0x8a3b35, 0.6), wood: mat(0xa9855d, 0.7), metal: mat(0x8c939e, 0.4), seat: mat(0x4b5565),
};
const bones = {};
const add = (parent, mesh, x = 0, y = 0, z = 0) => {
  mesh.position.set(x, y, z); mesh.castShadow = true; parent.add(mesh); return mesh;
};
const joint = (name, parent, x, y, z) => {
  const g = new THREE.Group(); g.name = name; g.position.set(x, y, z); g.rotation.order = 'XYZ';
  parent.add(g); bones[name] = g; return g;
};
// capsule hanging down from its joint
const limb = (parent, r, len, material, sx = 1, sz = 1) => {
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, len - 2 * r, 8, 16), material);
  m.scale.set(sx, 1, sz);
  return add(parent, m, 0, -len / 2, 0);
};
const ball = (parent, r, material, x, y, z, sx = 1, sy = 1, sz = 1) => {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, 24, 16), material);
  m.scale.set(sx, sy, sz);
  return add(parent, m, x, y, z);
};

const root = new THREE.Group();
scene.add(root);
const hips = joint('hips', root, 0, 1.0, 0);
add(hips, new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 0.06, 8, 16).rotateZ(Math.PI / 2), M.pants), 0, 0.03, 0);
const spine = joint('spine', hips, 0, 0.05, 0);
limb(spine, 0.12, 0.3, M.shirt, 1.1, 0.8).position.y = 0.1;
const chest = joint('chest', spine, 0, 0.2, 0);
add(chest, new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.1, 8, 16), M.shirt), 0, 0.13, 0).scale.set(1.15, 1, 0.78);
const neck = joint('neck', chest, 0, 0.3, 0);
add(neck, new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.05, 0.1, 16), M.skin), 0, 0.03, 0);
const head = joint('head', neck, 0, 0.08, 0);
ball(head, 0.105, M.skin, 0, 0.115, 0, 0.92, 1.08, 1);
ball(head, 0.03, M.skin, -0.098, 0.105, 0, 0.5, 1, 0.8);
ball(head, 0.03, M.skin, 0.098, 0.105, 0, 0.5, 1, 0.8);
ball(head, 0.014, M.skin, 0, 0.1, 0.108, 1, 1.1, 1.2);
// hair: top cap + back
const cap = new THREE.Mesh(new THREE.SphereGeometry(0.113, 32, 16, 0, TAU(), 0, 1.45), M.hair);
cap.scale.set(0.93, 1.1, 1.02);
add(head, cap, 0, 0.117, -0.004);
const back = new THREE.Mesh(new THREE.SphereGeometry(0.113, 32, 16, Math.PI, Math.PI, 0, 2.05), M.hair);
back.scale.set(0.93, 1.1, 1.02);
add(head, back, 0, 0.117, -0.004);
function TAU() { return Math.PI * 2; }
// face
const eyes = {};
for (const [side, sx] of [['L', 1], ['R', -1]]) {
  const lid = joint('lid.' + side, head, sx * 0.037, 0.13, 0.093);
  const eye = ball(lid, 0.016, M.white, 0, 0, 0, 1, 1, 0.6);
  ball(lid, 0.009, M.dark, 0, 0, 0.007, 1, 1, 0.5);
  eyes[side] = lid;
  const brow = new THREE.Mesh(new THREE.CapsuleGeometry(0.004, 0.03, 4, 8).rotateZ(Math.PI / 2), M.hair);
  add(head, brow, sx * 0.037, 0.158, 0.096).rotation.z = sx * -0.12;
}
const jaw = joint('jaw', head, 0, 0.07, 0.09);
const mouthOpen = ball(jaw, 0.026, M.mouth, 0, 0, 0.002, 1, 0.1, 0.4);
const smile = new THREE.Mesh(new THREE.TorusGeometry(0.026, 0.004, 6, 16, Math.PI), M.lip);
smile.rotation.z = Math.PI; smile.position.set(0, 0.012, 0.004); jaw.add(smile);
// arms
for (const [s, sx] of [['L', 1], ['R', -1]]) {
  const ua = joint('upper_arm.' + s, chest, sx * 0.195, 0.24, 0);
  ball(ua, 0.058, M.shirt, 0, 0, 0);
  limb(ua, 0.05, 0.31, M.shirt);
  const fa = joint('forearm.' + s, ua, 0, -0.3, 0);
  limb(fa, 0.043, 0.27, M.skin);
  const hd = joint('hand.' + s, fa, 0, -0.27, 0);
  ball(hd, 0.045, M.skin, 0, -0.05, 0, 0.8, 1.3, 0.6);
  ball(hd, 0.014, M.skin, sx * 0.04, -0.03, 0.02, 0.9, 1.6, 0.9);
}
// legs
for (const [s, sx] of [['L', 1], ['R', -1]]) {
  const th = joint('thigh.' + s, hips, sx * 0.09, -0.02, 0);
  limb(th, 0.076, 0.48, M.pants);
  const sh = joint('shin.' + s, th, 0, -0.46, 0);
  limb(sh, 0.058, 0.46, M.pants);
  const ft = joint('foot.' + s, sh, 0, -0.44, 0);
  const shoe = new THREE.Mesh(new THREE.CapsuleGeometry(0.045, 0.14, 8, 12).rotateX(Math.PI / 2), M.shoe);
  shoe.scale.set(1, 0.75, 1);
  add(ft, shoe, 0, -0.035, 0.05);
}

// ---- props ---------------------------------------------------------------
const props = { chair: new THREE.Group(), desk: new THREE.Group() };
{
  const c = props.chair;
  add(c, new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.05, 0.44), M.seat), 0, 0.41, -0.2);
  add(c, new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.4, 0.04), M.seat), 0, 0.66, -0.43);
  for (const [x, z] of [[-0.19, -0.02], [0.19, -0.02], [-0.19, -0.38], [0.19, -0.38]])
    add(c, new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.39, 8), M.metal), x, 0.195, z);
  const d = props.desk;
  add(d, new THREE.Mesh(new THREE.BoxGeometry(1.3, 0.04, 0.7), M.wood), 0, 0.74, 0.5);
  for (const [x, z] of [[-0.6, 0.2], [0.6, 0.2], [-0.6, 0.8], [0.6, 0.8]])
    add(d, new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.72, 0.05), M.metal), x, 0.36, z);
  add(d, new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.012, 0.23), M.metal), 0, 0.766, 0.36);
  const scr = add(d, new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.22, 0.01), M.metal), 0, 0.88, 0.48);
  scr.rotation.x = -0.15;
  add(d, new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.17, 0.004), new THREE.MeshBasicMaterial({ color: 0x8fc2ff })), 0, 0.88, 0.4735).rotation.x = -0.15;
}
for (const p of Object.values(props)) { p.visible = false; scene.add(p); }

// ---- clips & playback ------------------------------------------------------
const clipData = await (await fetch('clips.json')).json();
const names = Object.keys(clipData.clips);
const NB = clipData.bones.length;
const FRAME = NB * 3 + 3;
const cur = new Float32Array(FRAME);       // pose currently applied
const from = new Float32Array(FRAME);      // pose at the moment of switching
const target = new Float32Array(FRAME);
let active = 'idle', time = 0, blend = 1, speed = 1, paused = false;

function sampleClip(clip, t, out) {
  const n = clip.frames.length, f = ((t / clip.duration) % 1 + 1) % 1 * n;
  const i = Math.floor(f) % n, j = (i + 1) % n, k = f - Math.floor(f);
  const a = clip.frames[i], b = clip.frames[j];
  for (let q = 0; q < FRAME; q++) out[q] = a[q] + (b[q] - a[q]) * k;
}
function setActivity(name) {
  if (name === active && blend >= 1) return;
  from.set(cur); active = name; time = 0; blend = 0;
  const clip = clipData.clips[name];
  for (const [k, p] of Object.entries(props)) p.visible = clip.props.includes(k);
  document.querySelectorAll('#acts button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.name === name)));
}

const actsEl = document.getElementById('acts');
names.forEach((n, i) => {
  const b = document.createElement('button');
  b.textContent = clipData.clips[n].label; b.dataset.name = n; b.title = 'Key ' + ((i + 1) % 10);
  b.onclick = () => setActivity(n);
  actsEl.appendChild(b);
});
addEventListener('keydown', e => {
  const i = e.key === '0' ? 9 : parseInt(e.key, 10) - 1;
  if (i >= 0 && i < names.length) setActivity(names[i]);
});
const speedEl = document.getElementById('speed');
speedEl.oninput = () => { speed = +speedEl.value; document.getElementById('speedv').textContent = speed.toFixed(2).replace(/0$/, '') + '×'; };
document.getElementById('orbit').onchange = e => { controls.autoRotate = e.target.checked; controls.autoRotateSpeed = 2.5; };
document.getElementById('pause').onchange = e => { paused = e.target.checked; };

function applyPose(p) {
  clipData.bones.forEach((name, i) => {
    const b = bones[name]; if (!b) return;
    if (name.startsWith('lid.')) {                 // lid closure squashes the eye
      b.scale.y = Math.max(0.08, 1 - p[i * 3] / 90 * 0.92); return;
    }
    if (name === 'jaw') {
      b.rotation.set(p[i * 3] * DEG, 0, 0);
      mouthOpen.scale.y = 0.1 + p[i * 3] * 0.035; smile.visible = p[i * 3] < 3; return;
    }
    b.rotation.set(p[i * 3] * DEG, p[i * 3 + 1] * DEG, p[i * 3 + 2] * DEG);
  });
  bones.hips.position.set(p[NB * 3], 1.0 + p[NB * 3 + 1], p[NB * 3 + 2]);
}

function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
  if (w < 600) camera.position.setLength(Math.max(camera.position.length(), 5.2));
}
addEventListener('resize', resize); resize();

let last = performance.now();
renderer.setAnimationLoop(now => {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  const clip = clipData.clips[active];
  if (!paused) {
    time += dt * speed;
    blend = Math.min(1, blend + dt / 0.35);
    if (clip.travel) {
      const dz = clip.travel * speed * dt;
      grid.position.z = ((grid.position.z - dz) % CELL + CELL) % CELL;
    }
  }
  sampleClip(clip, time, target);
  const w = blend * blend * (3 - 2 * blend);
  for (let q = 0; q < FRAME; q++) cur[q] = from[q] + (target[q] - from[q]) * w;
  applyPose(cur);
  controls.update();
  renderer.render(scene, camera);
});

setActivity('idle');
cur.set(target);
window.__avatar = { setActivity, names };
