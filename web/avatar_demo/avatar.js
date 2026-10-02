import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const DEG = Math.PI / 180;
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const stage = document.getElementById('stage');

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = dark ? 0.8 : 1.0;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const SKY = dark ? 0x232a38 : 0xcdd6e2;
scene.background = new THREE.Color(SKY);
scene.fog = new THREE.Fog(SKY, 8, 22);
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = dark ? 0.35 : 0.55;

const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 80);
camera.position.set(1.5, 1.3, 4.3);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.88, 0);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 1.5;
controls.maxDistance = 9;

scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, dark ? 0.5 : 0.8));
const sun = new THREE.DirectionalLight(0xfff1dc, dark ? 1.6 : 2.4);
sun.position.set(3, 5.5, 4);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.radius = 4;
sun.shadow.bias = -0.0004;
Object.assign(sun.shadow.camera, { left: -2.5, right: 2.5, top: 3, bottom: -2.5, near: 1, far: 16 });
scene.add(sun);
const rim = new THREE.DirectionalLight(0xbcd6ff, 1.1);
rim.position.set(-3, 3, -4);
scene.add(rim);

// ---- street: pavement, road, buildings, lamps; scrolls backwards when walking ----------
const BLOCK = 6;
const street = new THREE.Group();
scene.add(street);
const smat = (c, r = 0.9) => new THREE.MeshStandardMaterial({ color: c, roughness: r });
function streetBlock(z0) {
  const g = new THREE.Group(); g.position.z = z0;
  const box = (w, h, d, x, y, z, m) => {
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z);
    b.castShadow = b.receiveShadow = true; g.add(b); return b;
  };
  const pave = smat(dark ? 0x454b57 : 0xbfc2c9);
  box(5.4, 0.02, BLOCK, -1.3, 0.01, 0, pave);
  for (let i = 0; i < BLOCK * 2; i++) box(5.4, 0.003, 0.01, -1.3, 0.021, -BLOCK / 2 + i * 0.5, smat(dark ? 0x3a404b : 0xaaadb5));
  box(5, 0.01, BLOCK, 4.8, 0.005, 0, smat(dark ? 0x2c3038 : 0x7b7f87));              // road
  box(0.12, 0.012, 3, 2.35, 0.012, 0, smat(0xf0eee6, 0.7));                           // lane line
  box(0.12, 0.12, BLOCK, 2.1, 0.06, 0, smat(dark ? 0x555b66 : 0xa3a6ae));            // kerb
  const cols = [0xcab8a0, 0xb9a48c, 0xd2c2ad, 0xaeb7c4];
  box(1.6, 5, 2.9, -4.2, 2.5, -1.5, smat(cols[(z0 / BLOCK + 8) % 4 | 0]));
  box(1.6, 6.5, 2.9, -4.2, 3.25, 1.5, smat(cols[(z0 / BLOCK + 9) % 4 | 0]));
  for (let j = 0; j < 4; j++) for (const zz of [-2.2, -0.8, 0.8, 2.2])
    box(0.05, 0.7, 0.5, -3.38, 1.2 + j * 1.2, zz, smat(0x39434f, 0.3));
  box(0.07, 3.2, 0.07, 2.6, 1.6, 2.2, smat(0x4a4f58, 0.5));                           // lamp
  box(0.7, 0.06, 0.06, 2.3, 3.2, 2.2, smat(0x4a4f58, 0.5));
  return g;
}
const blocks = [-1, 0, 1].map(i => { const b = streetBlock(i * BLOCK); street.add(b); return b; });
const floor = new THREE.Mesh(new THREE.CircleGeometry(40, 48).rotateX(-Math.PI / 2), smat(dark ? 0x2a303a : 0xaab0ba, 1));
floor.position.y = -0.01; floor.receiveShadow = true; scene.add(floor);

// ---- avatar helpers ----------------------------------------------------------------------
const mat = (c, r = 0.65, o = {}) => new THREE.MeshPhysicalMaterial({ color: c, roughness: r, ...o });
const M = {
  skin: mat(0xb07650, 0.55, { sheen: 0.3, sheenRoughness: 0.5, sheenColor: new THREE.Color(0xd79a74) }),
  jacket: mat(0x1c1c20, 0.5, { sheen: 0.8, sheenRoughness: 0.4, sheenColor: new THREE.Color(0x555a66), side: THREE.DoubleSide }),
  rib: mat(0x151518, 0.9, { side: THREE.DoubleSide }),
  polo: mat(0xe2cfa9, 0.8, { sheen: 0.5, side: THREE.DoubleSide }),
  jeans: mat(0x27406b, 0.85, { sheen: 0.4, sheenColor: new THREE.Color(0x4a6aa0), side: THREE.DoubleSide }),
  cuff: mat(0x4a6a9c, 0.9, { side: THREE.DoubleSide }),
  shoe: mat(0x2552b8, 0.55), sole: mat(0xf0efe9, 0.6), lace: mat(0xe8e8e8, 0.7),
  hair: mat(0x14100e, 0.45, { sheen: 0.5, sheenColor: new THREE.Color(0x5a5f6a) }),
  stubble: new THREE.MeshStandardMaterial({ color: 0x1a1210, roughness: 1, transparent: true, opacity: 0.2, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }),
  white: mat(0xf2efe8, 0.25), iris: mat(0x3a2314, 0.25), pupil: mat(0x050404, 0.2),
  mouth: mat(0x4a1a1a, 0.6), lip: mat(0x8a4a3e, 0.5),
  frame: mat(0x17181b, 0.35, { metalness: 0.3 }),
  lens: new THREE.MeshPhysicalMaterial({ color: 0xdfeaf5, roughness: 0.05, transparent: true, opacity: 0.12, depthWrite: false }),
  strap: mat(0x141416, 0.85), pack: mat(0x18181b, 0.8),
  cupRed: mat(0xa8242a, 0.5), cupWhite: mat(0xf3f1ea, 0.5), lid: mat(0x1b1b1e, 0.5),
  cap: mat(0x6ea4da, 0.8), metal: mat(0x9096a2, 0.4, { metalness: 0.6 }),
};
const bones = {};
const put = (parent, mesh, x = 0, y = 0, z = 0) => {
  mesh.position.set(x, y, z); mesh.castShadow = true; parent.add(mesh); return mesh;
};
const joint = (name, parent, x, y, z) => {
  const g = new THREE.Group(); g.name = name; g.position.set(x, y, z);
  parent.add(g); bones[name] = g; return g;
};
const ball = (parent, r, material, x, y, z, sx = 1, sy = 1, sz = 1) => {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, 32, 20), material);
  m.scale.set(sx, sy, sz); return put(parent, m, x, y, z);
};
// Lofted surface through elliptical rings. secs: [{y, rx, rz, cx?, cz?}] ; angle 0 = +z (front).
// ``gap`` leaves an opening (radians) centred on the front (jacket zip opening).
function loft(secs, material, { seg = 36, gap = 0 } = {}) {
  const pos = [], idx = [], n = seg + 1;
  for (const s of secs) for (let j = 0; j <= seg; j++) {
    const a = gap / 2 + (2 * Math.PI - gap) * j / seg;
    pos.push((s.cx || 0) + s.rx * Math.sin(a), s.y, (s.cz || 0) + s.rz * Math.cos(a));
  }
  for (let i = 0; i < secs.length - 1; i++) for (let j = 0; j < seg; j++) {
    const a = i * n + j, b = a + 1, c = a + n, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx); g.computeVertexNormals();
  const m = new THREE.Mesh(g, material); m.castShadow = true; return m;
}
const tube = (parent, pts, material, seg = 20) => {
  const m = loft(pts.map(([y, r]) => ({ y, rx: r, rz: r })), material, { seg });
  parent.add(m); return m;
};
const scaleSecs = (secs, k, dz = 0) => secs.map(s => ({ ...s, rx: s.rx * k, rz: s.rz * k, cz: (s.cz || 0) + dz }));

// ---- avatar --------------------------------------------------------------------------------
const root = new THREE.Group();
scene.add(root);
const hips = joint('hips', root, 0, 1.0, 0);
hips.add(loft([{ y: -0.16, rx: 0.15, rz: 0.1 }, { y: -0.06, rx: 0.16, rz: 0.106 }, { y: 0.0, rx: 0.15, rz: 0.098 }, { y: 0.05, rx: 0.125, rz: 0.085 }], M.jeans, { seg: 32 }));

const spine = joint('spine', hips, 0, 0.05, 0);
const lowerSecs = [{ y: -0.1, rx: 0.165, rz: 0.108 }, { y: 0.0, rx: 0.158, rz: 0.104 }, { y: 0.1, rx: 0.15, rz: 0.1 }, { y: 0.2, rx: 0.155, rz: 0.104 }];
const upperSecs = [{ y: 0.0, rx: 0.155, rz: 0.104 }, { y: 0.12, rx: 0.172, rz: 0.112 }, { y: 0.22, rx: 0.176, rz: 0.104 }, { y: 0.27, rx: 0.14, rz: 0.088 }, { y: 0.31, rx: 0.065, rz: 0.06 }];
spine.add(loft(scaleSecs(lowerSecs, 0.98), M.polo));
spine.add(loft(scaleSecs(lowerSecs, 1.06), M.jacket, { gap: 0.4 }));
spine.add(loft([{ y: -0.125, rx: 0.176, rz: 0.118 }, { y: -0.085, rx: 0.176, rz: 0.118 }], M.rib, { seg: 36, gap: 0.4 }));  // ribbed hem
const chest = joint('chest', spine, 0, 0.2, 0);
chest.add(loft(scaleSecs(upperSecs, 0.98), M.polo));
chest.add(loft(scaleSecs(upperSecs, 1.03), M.jacket, { gap: 0.6 }));
// polo: placket, zip, collar
put(chest, new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.3, 0.004), M.metal), 0, 0.12, 0.101).castShadow = false;
chest.add(loft([{ y: 0.285, rx: 0.075, rz: 0.07 }, { y: 0.335, rx: 0.062, rz: 0.058 }], M.polo, { gap: 0.5 }));
// jacket collar
chest.add(loft([{ y: 0.265, rx: 0.1, rz: 0.082 }, { y: 0.31, rx: 0.088, rz: 0.075 }, { y: 0.34, rx: 0.086, rz: 0.073 }], M.rib, { seg: 36, gap: 1.0 }));
// backpack straps over the shoulders + pack body
for (const sx of [1, -1]) {
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(sx * 0.1, 0.0, 0.112), new THREE.Vector3(sx * 0.105, 0.17, 0.115),
    new THREE.Vector3(sx * 0.115, 0.285, 0.05), new THREE.Vector3(sx * 0.12, 0.27, -0.06),
    new THREE.Vector3(sx * 0.1, 0.1, -0.115),
  ]);
  const st = new THREE.Mesh(new THREE.TubeGeometry(curve, 24, 0.017, 8), M.strap);
  st.scale.set(1.4, 1, 1); put(chest, st);
}
put(chest, new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.38, 0.12), M.pack), 0, 0.08, -0.17);

const neck = joint('neck', chest, 0, 0.3, 0);
put(neck, new THREE.Mesh(new THREE.CylinderGeometry(0.046, 0.052, 0.12, 20), M.skin), 0, 0.03, 0);
const head = joint('head', neck, 0, 0.08, 0);
// skull, face, jaw, chin
ball(head, 0.105, M.skin, 0, 0.125, -0.006, 0.93, 1.04, 1.0);
ball(head, 0.09, M.skin, 0, 0.078, 0.012, 0.96, 1.0, 0.98);
ball(head, 0.042, M.skin, 0, 0.032, 0.052, 1.0, 0.82, 0.85);
ball(head, 0.03, M.skin, -0.097, 0.1, -0.004, 0.35, 1, 0.7);
ball(head, 0.03, M.skin, 0.097, 0.1, -0.004, 0.35, 1, 0.7);
// nose
ball(head, 0.013, M.skin, 0, 0.104, 0.096, 0.8, 1.5, 1.0);
ball(head, 0.012, M.skin, 0, 0.087, 0.103, 1, 0.85, 0.95);
ball(head, 0.008, M.skin, -0.011, 0.085, 0.098, 1, 0.8, 1);
ball(head, 0.008, M.skin, 0.011, 0.085, 0.098, 1, 0.8, 1);
// eyes and brows
for (const [side, sx] of [['L', 1], ['R', -1]]) {
  const lid = joint('lid.' + side, head, sx * 0.037, 0.128, 0.088);
  ball(lid, 0.0155, M.white, 0, 0, 0, 1, 0.9, 0.6);
  ball(lid, 0.0085, M.iris, 0, 0, 0.007, 1, 1, 0.5);
  ball(lid, 0.004, M.pupil, 0, 0, 0.0105, 1, 1, 0.5);
  const brow = new THREE.Mesh(new THREE.CapsuleGeometry(0.0055, 0.034, 4, 8).rotateZ(Math.PI / 2), M.hair);
  put(head, brow, sx * 0.04, 0.155, 0.092).rotation.z = sx * -0.1;
}
// glasses
function frameGeo(w, h, r, t) {
  const rr = (s, w, h, r) => { s.moveTo(-w / 2 + r, -h / 2); s.lineTo(w / 2 - r, -h / 2); s.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r); s.lineTo(w / 2, h / 2 - r); s.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2); s.lineTo(-w / 2 + r, h / 2); s.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r); s.lineTo(-w / 2, -h / 2 + r); s.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2); return s; };
  const outer = rr(new THREE.Shape(), w, h, r);
  outer.holes.push(rr(new THREE.Path(), w - 2 * t, h - 2 * t, Math.max(0.001, r - t)));
  return new THREE.ExtrudeGeometry(outer, { depth: 0.006, bevelEnabled: false });
}
const glasses = new THREE.Group(); head.add(glasses);
for (const sx of [1, -1]) {
  put(glasses, new THREE.Mesh(frameGeo(0.058, 0.04, 0.009, 0.0045), M.frame), sx * 0.037, 0.128, 0.098);
  put(glasses, new THREE.Mesh(new THREE.PlaneGeometry(0.054, 0.036), M.lens), sx * 0.037, 0.128, 0.102).castShadow = false;
  put(glasses, new THREE.Mesh(new THREE.BoxGeometry(0.003, 0.004, 0.12), M.frame), sx * 0.069, 0.132, 0.04);
}
put(glasses, new THREE.Mesh(new THREE.BoxGeometry(0.016, 0.004, 0.005), M.frame), 0, 0.136, 0.1);
// mouth, moustache, goatee, stubble
const jaw = joint('jaw', head, 0, 0.058, 0.098);
const mouthOpen = ball(jaw, 0.024, M.mouth, 0, 0, -0.004, 1, 0.1, 0.4);
const smile = new THREE.Mesh(new THREE.TorusGeometry(0.026, 0.0038, 6, 20, Math.PI * 0.75), M.lip);
smile.rotation.z = Math.PI * 1.125; smile.position.set(0, 0.014, -0.003); jaw.add(smile);
for (const sx of [1, -1]) {
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(0.0068, 0.024, 4, 8).rotateZ(Math.PI / 2), M.hair);
  put(head, m, sx * 0.014, 0.077, 0.1).rotation.z = sx * -0.28;
}
ball(head, 0.019, M.hair, 0, 0.024, 0.083, 1, 1.2, 0.5);
const stub = new THREE.Mesh(new THREE.SphereGeometry(0.0925, 32, 16, 0, Math.PI, 1.72, 0.9), M.stubble);
stub.scale.set(0.965, 1.0, 0.985); stub.position.set(0, 0.078, 0.012); head.add(stub);
// hair: back + sides, top shell, quiff, sideburns; cap toggle swaps the top for a cap
const hairBack = new THREE.Mesh(new THREE.SphereGeometry(0.113, 32, 16, Math.PI, Math.PI, 0, 1.95), M.hair);
hairBack.scale.set(0.95, 1.06, 1.03); put(head, hairBack, 0, 0.125, -0.003);
const hairTop = new THREE.Group(); head.add(hairTop);
const topShell = new THREE.Mesh(new THREE.SphereGeometry(0.113, 32, 16, 0, Math.PI, 0, 1.2), M.hair);
topShell.scale.set(0.95, 1.06, 1.03); put(hairTop, topShell, 0, 0.125, -0.003);
ball(hairTop, 0.062, M.hair, 0, 0.205, 0.02, 1.3, 0.55, 1.6).rotation.x = -0.2;
ball(hairTop, 0.045, M.hair, 0, 0.2, 0.07, 1.4, 0.6, 1.0).rotation.x = -0.35;
ball(hairTop, 0.04, M.hair, 0.045, 0.215, 0.0, 1.0, 0.6, 1.5);
for (const sx of [1, -1]) put(head, new THREE.Mesh(new THREE.BoxGeometry(0.008, 0.032, 0.018), M.hair), sx * 0.085, 0.125, 0.04);
const capGroup = new THREE.Group(); head.add(capGroup);
{
  const dome = new THREE.Mesh(new THREE.SphereGeometry(0.113, 32, 16, 0, Math.PI * 2, 0, 1.42), M.cap);
  dome.scale.set(1.0, 1.05, 1.08); put(capGroup, dome, 0, 0.133, -0.012).rotation.x = -0.12;
  const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.085, 0.085, 0.006, 32, 1, false, -Math.PI / 2 - 0.1, Math.PI + 0.2), M.cap);
  brim.scale.z = 1.3; put(capGroup, brim, 0, 0.162, 0.095).rotation.x = 0.1;
}
capGroup.visible = false;

// arms: jacket sleeves with ribbed cuffs, skin hands
for (const [s, sx] of [['L', 1], ['R', -1]]) {
  const ua = joint('upper_arm.' + s, chest, sx * 0.195, 0.24, 0);
  ball(ua, 0.062, M.jacket, 0, 0, 0);
  tube(ua, [[0, 0.058], [-0.16, 0.054], [-0.3, 0.05]], M.jacket);
  const fa = joint('forearm.' + s, ua, 0, -0.3, 0);
  tube(fa, [[0, 0.05], [-0.12, 0.047], [-0.215, 0.05]], M.jacket);
  tube(fa, [[-0.205, 0.046], [-0.27, 0.042]], M.rib);
  const hd = joint('hand.' + s, fa, 0, -0.27, 0);
  ball(hd, 0.043, M.skin, 0, -0.055, 0, 0.8, 1.3, 0.55);
  for (let f = 0; f < 4; f++) ball(hd, 0.011, M.skin, sx * (-0.022 + f * 0.0135), -0.125 - (f === 1 || f === 2 ? 0.006 : 0), 0.004, 0.9, 2.5, 0.9);
  ball(hd, 0.013, M.skin, sx * 0.04, -0.06, 0.02, 0.9, 1.9, 0.9);
  hd.rotation.order = 'XYZ';
}
// cup (right hand) – kept upright while the forearm is bent ~130 deg
const cup = new THREE.Group();
cup.add(Object.assign(new THREE.Mesh(new THREE.CylinderGeometry(0.036, 0.027, 0.1, 24), M.cupRed), { castShadow: true }));
put(cup, new THREE.Mesh(new THREE.CylinderGeometry(0.0375, 0.0365, 0.022, 24), M.cupWhite), 0, 0.0, 0).castShadow = true;
put(cup, new THREE.Mesh(new THREE.CylinderGeometry(0.039, 0.037, 0.016, 24), M.lid), 0, 0.057, 0);
cup.position.set(0.0, -0.055, 0.035); cup.rotation.x = 128 * DEG;
bones['hand.R'].add(cup); cup.visible = false;
// legs: tapered jeans with turned cuffs, sneakers
for (const [s, sx] of [['L', 1], ['R', -1]]) {
  const th = joint('thigh.' + s, hips, sx * 0.09, -0.02, 0);
  tube(th, [[0.02, 0.082], [-0.1, 0.082], [-0.3, 0.068], [-0.46, 0.058]], M.jeans);
  const sh = joint('shin.' + s, th, 0, -0.46, 0);
  ball(sh, 0.058, M.jeans, 0, 0, 0);
  tube(sh, [[0, 0.058], [-0.2, 0.052], [-0.38, 0.047], [-0.46, 0.046]], M.jeans);
  tube(sh, [[-0.37, 0.05], [-0.372, 0.052], [-0.43, 0.052], [-0.432, 0.05]], M.cuff);
  const ft = joint('foot.' + s, sh, 0, -0.44, 0);
  const shoe = new THREE.Mesh(new THREE.CapsuleGeometry(0.043, 0.14, 8, 14).rotateX(Math.PI / 2), M.shoe);
  shoe.scale.set(1, 0.72, 1); put(ft, shoe, 0, -0.035, 0.055);
  const sole = new THREE.Mesh(new THREE.CapsuleGeometry(0.046, 0.15, 6, 14).rotateX(Math.PI / 2), M.sole);
  sole.scale.set(1.0, 0.22, 1.02); put(ft, sole, 0, -0.07, 0.057);
  const toe = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 10), M.sole);
  toe.scale.set(1.1, 0.6, 0.8); put(ft, toe, 0, -0.045, 0.14);
  put(ft, new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.004, 0.06), M.lace), 0, -0.012, 0.075);
}

// ---- desk props (sit / type) -----------------------------------------------------------------
const props = { chair: new THREE.Group(), desk: new THREE.Group(), cup: cup };
{
  const wood = smat(0xa9855d, 0.7), metal = smat(0x8c939e, 0.4), seat = smat(0x4b5565);
  const c = props.chair;
  put(c, new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.05, 0.44), seat), 0, 0.41, -0.2);
  put(c, new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.4, 0.04), seat), 0, 0.66, -0.43);
  for (const [x, z] of [[-0.19, -0.02], [0.19, -0.02], [-0.19, -0.38], [0.19, -0.38]])
    put(c, new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.39, 8), metal), x, 0.195, z);
  const d = props.desk;
  put(d, new THREE.Mesh(new THREE.BoxGeometry(1.3, 0.04, 0.7), wood), 0, 0.74, 0.5);
  for (const [x, z] of [[-0.6, 0.2], [0.6, 0.2], [-0.6, 0.8], [0.6, 0.8]])
    put(d, new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.72, 0.05), metal), x, 0.36, z);
  put(d, new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.012, 0.23), metal), 0, 0.766, 0.36);
  put(d, new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.22, 0.01), metal), 0, 0.88, 0.48).rotation.x = -0.15;
}
for (const [k, p] of Object.entries(props)) { if (k !== 'cup') { p.visible = false; scene.add(p); } }

// ---- clips & playback ----------------------------------------------------------------------------
const clipData = await (await fetch('clips.json')).json();
const names = Object.keys(clipData.clips);
const NB = clipData.bones.length;
const FRAME = NB * 3 + 3;
const cur = new Float32Array(FRAME), from = new Float32Array(FRAME), target = new Float32Array(FRAME);
const START = 'walk_cup';
let active = START, time = 0, blend = 1, speed = 1, paused = false;

function sampleClip(clip, t, out) {
  const n = clip.frames.length, f = ((t / clip.duration) % 1 + 1) % 1 * n;
  const i = Math.floor(f) % n, j = (i + 1) % n, k = f - Math.floor(f);
  const a = clip.frames[i], b = clip.frames[j];
  for (let q = 0; q < FRAME; q++) out[q] = a[q] + (b[q] - a[q]) * k;
}
function setActivity(name) {
  if (name === active && blend >= 1 && time > 0) return;
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
document.getElementById('cap').onchange = e => { capGroup.visible = e.target.checked; hairTop.visible = !e.target.checked; };

function applyPose(p) {
  clipData.bones.forEach((name, i) => {
    const b = bones[name]; if (!b) return;
    if (name.startsWith('lid.')) { b.scale.y = Math.max(0.08, 1 - p[i * 3] / 90 * 0.92); return; }
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
  if (w < 600) camera.position.setLength(Math.max(camera.position.length(), 6));
}
addEventListener('resize', resize); resize();

let last = performance.now();
renderer.setAnimationLoop(now => {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  const clip = clipData.clips[active];
  if (!paused) {
    time += dt * speed;
    blend = Math.min(1, blend + dt / 0.35);
    if (clip.travel) street.position.z = ((street.position.z - clip.travel * speed * dt) % BLOCK + BLOCK) % BLOCK - BLOCK;
  }
  sampleClip(clip, time, target);
  const w = blend * blend * (3 - 2 * blend);
  for (let q = 0; q < FRAME; q++) cur[q] = from[q] + (target[q] - from[q]) * w;
  applyPose(cur);
  controls.update();
  renderer.render(scene, camera);
});

setActivity(START);
cur.set(target);
window.__avatar = {
  setActivity, names,
  freeze(t) { time = t; blend = 1; paused = true; },
  cap(on) { document.getElementById('cap').checked = on; document.getElementById('cap').onchange({ target: { checked: on } }); },
  view(x, y, z, ty = 0.88) { camera.position.set(x, y, z); controls.target.set(0, ty, 0); },
};
