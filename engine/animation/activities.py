"""Procedural activity clips for the humanoid rig (idle, walk, run, wave, ...).

Pure Python, no ``bpy`` import: this is the single source of truth for the motion.
The web demo plays clips sampled by ``tools/export_clips.py`` and the Blender
bake (``engine/animation/bake.py``) keys the same data onto the real armature.

Conventions (character space, same handedness as the Blender rig):
  * +X is the character's left, +Y is up, +Z is forward (Blender: -Y is forward).
  * Rotations are Euler degrees, applied as R = Rx * Ry * Rz, relative to the
    parent bone's rest pose.
  * Limb joints hang down.  Positive X swings a hanging limb *backwards*, so a
    forward arm/leg raise is negative X, a knee bend is positive X on the shin,
    an elbow bend is negative X on the forearm.  Positive Z abducts the left
    arm/leg outwards (negative for the right side).  Forward lean is positive X
    on spine/chest/head.  Jaw open and lid closure are positive X.
  * ``off`` is the hips translation in metres for the reference avatar
    (hips pivot at 1.0 m); scale it by hips height for other characters.
"""
import math

TAU = math.tau

BONES = [
    'hips', 'spine', 'chest', 'neck', 'head', 'jaw', 'lid.L', 'lid.R',
    'upper_arm.L', 'upper_arm.R', 'forearm.L', 'forearm.R', 'hand.L', 'hand.R',
    'thigh.L', 'thigh.R', 'shin.L', 'shin.R', 'foot.L', 'foot.R',
]

# Reference avatar proportions used for foot grounding.
THIGH, SHIN, HIP_DROP, ANKLE_H, HIPS_H = 0.46, 0.44, 0.02, 0.08, 1.0


def S(u, k=1, ph=0.0):
    return math.sin(TAU * (k * u + ph))


def C(u, k=1, ph=0.0):
    return math.cos(TAU * (k * u + ph))


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def bump(u, centre, width):
    """Periodic 0..1 pulse centred on ``centre`` (u is a 0..1 loop phase)."""
    d = abs(((u - centre + 0.5) % 1.0) - 0.5)
    return smooth(1 - d / width)


def keys(u, pts):
    """Smoothly interpolate ``[(u0, v0), (u1, v1), ...]`` keys at phase ``u``."""
    if u <= pts[0][0]:
        return pts[0][1]
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if u <= b:
            return va + (vb - va) * smooth((u - a) / (b - a))
    return pts[-1][1]


class Pose:
    def __init__(self):
        self.rot = {b: [0.0, 0.0, 0.0] for b in BONES}
        self.off = [0.0, 0.0, 0.0]
        self.lift = 0.0
        self.ground = 1.0     # 1 = keep the lowest foot on the floor, 0 = free
        self._leg = {'L': (0.0, 0.0), 'R': (0.0, 0.0)}
        self.add('upper_arm.L', z=7).add('upper_arm.R', z=-7)
        self.add('forearm.L', x=-8).add('forearm.R', x=-8)

    def add(self, bone, x=0.0, y=0.0, z=0.0):
        r = self.rot[bone]
        r[0] += x
        r[1] += y
        r[2] += z
        return self

    def both(self, name, x=0.0, y=0.0, z=0.0):
        """Add to ``name.L`` and ``name.R``; y and z mirror on the right side."""
        self.add(name + '.L', x, y, z)
        return self.add(name + '.R', x, -y, -z)

    def leg(self, side, fwd, knee, foot=None):
        """Thigh forward by ``fwd`` deg, knee bent by ``knee`` deg, foot kept flat."""
        self._leg[side] = (fwd, knee)
        self.add('thigh.' + side, x=-fwd)
        self.add('shin.' + side, x=knee)
        self.add('foot.' + side, x=(fwd - knee) if foot is None else foot)
        return self

    def frame(self):
        reach = max(THIGH * math.cos(math.radians(f)) + SHIN * math.cos(math.radians(f - k))
                    for f, k in self._leg.values())
        hips_y = ANKLE_H + HIP_DROP + reach
        off = list(self.off)
        off[1] += self.ground * (hips_y - HIPS_H) + self.lift
        return {b: list(v) for b, v in self.rot.items()}, off


# ---------------------------------------------------------------- activities

def idle(u):
    p = Pose()
    p.leg('L', 1.5, 3).leg('R', 0, 2)
    p.add('chest', x=-1.5 * S(u)).add('spine', x=1.0 * S(u))
    p.add('hips', z=1.2 * S(u)).add('chest', z=-1.0 * S(u))
    p.both('upper_arm', x=1.5 * S(u, 1, 0.1))
    p.add('head', x=2 * S(u, 2), y=7 * S(u))
    blink = 85 * (bump(u, 0.30, 0.03) + bump(u, 0.78, 0.03))
    p.add('lid.L', x=blink).add('lid.R', x=blink)
    return p


def walk(u):
    w = TAU * u
    p = Pose()
    for side, ph in (('L', 0.0), ('R', math.pi)):
        s, c = math.sin(w + ph), math.cos(w + ph)
        p.leg(side, 24 * s, 8 + 48 * max(0.0, c) ** 1.5)
        sgn = 1 if side == 'L' else -1
        p.add('upper_arm.' + side, x=sgn * 20 * math.sin(w))
        p.add('forearm.' + side, x=-(14 + 16 * max(0.0, -s)))
    p.add('hips', y=-5 * math.sin(w)).add('chest', y=8 * math.sin(w), x=3)
    p.add('head', y=-3 * math.sin(w))
    p.add('hips', z=2.5 * math.cos(w))
    return p


def run(u):
    w = TAU * u
    p = Pose()
    p.ground = 0.5
    for side, ph in (('L', 0.0), ('R', math.pi)):
        s, c = math.sin(w + ph), math.cos(w + ph)
        p.leg(side, 36 * s + 4, 14 + 95 * max(0.0, c) ** 1.3)
        sgn = 1 if side == 'L' else -1
        p.add('upper_arm.' + side, x=sgn * 42 * math.sin(w), z=sgn * 6)
        p.add('forearm.' + side, x=-(75 + 15 * max(0.0, -s)))
    p.add('hips', y=-8 * math.sin(w)).add('chest', y=12 * math.sin(w), x=10)
    p.add('spine', x=6).add('head', x=-6, y=-4 * math.sin(w))
    p.lift = 0.05 * abs(math.cos(w)) + 0.02
    return p


def wave(u):
    p = idle(u)
    p.rot['upper_arm.R'] = [-22, 0, -102]
    p.rot['forearm.R'] = [-8, 0, -80 + 24 * S(u, 4)]
    p.rot['hand.R'] = [0, 0, 14 * S(u, 4, 0.2)]
    p.add('upper_arm.L', z=2)
    p.add('head', z=-6, y=-6 * S(u)).add('chest', y=6)
    p.add('jaw', x=10 * bump(u, 0.25, 0.12))
    return p


def talk(u):
    p = idle(u)
    p.rot['upper_arm.R'] = [-34 + 10 * S(u, 2), 8 * S(u, 3), -16 + 5 * S(u, 3, 0.3)]
    p.rot['forearm.R'] = [-72 + 24 * S(u, 3, 0.1), 0, 0]
    p.rot['hand.R'] = [-8 * S(u, 3, 0.4), 0, 10 * S(u, 2)]
    p.rot['upper_arm.L'] = [-28 + 8 * S(u, 2, 0.3), -6 * S(u, 3, 0.7), 16 + 4 * S(u, 3)]
    p.rot['forearm.L'] = [-66 + 20 * S(u, 3, 0.55), 0, 0]
    p.rot['hand.L'] = [-6 * S(u, 3, 0.8), 0, -10 * S(u, 2, 0.3)]
    p.add('jaw', x=11 * (0.5 + 0.5 * S(u, 7)) * (0.5 + 0.5 * S(u, 13, 0.2)))
    p.add('head', x=4 * S(u, 3), y=6 * S(u, 1, 0.2), z=3 * S(u, 2))
    p.add('chest', y=5 * S(u, 2, 0.25))
    return p


def _seated(p, lean=0.0):
    p.ground = 0.0
    p.off[1] = -0.46
    p.off[2] = -0.2
    for side in 'LR':
        p.leg(side, 90, 90, foot=0)
    p.add('thigh.L', z=3).add('thigh.R', z=-3)
    p.add('spine', x=lean)
    return p


def sit(u):
    p = Pose()
    _seated(p, 2)
    p.add('chest', x=-1.5 * S(u))
    p.rot['upper_arm.L'] = [-14, 0, 12]
    p.rot['upper_arm.R'] = [-14, 0, -12]
    p.both('forearm', x=-58)
    p.both('hand', x=-6)
    p.add('head', x=2 * S(u, 2), y=9 * S(u))
    blink = 85 * bump(u, 0.55, 0.03)
    p.add('lid.L', x=blink).add('lid.R', x=blink)
    return p


def type_(u):
    p = Pose()
    _seated(p, 7)
    p.add('chest', x=3 - 1.0 * S(u, 2))
    p.rot['upper_arm.L'] = [-30, 0, 8]
    p.rot['upper_arm.R'] = [-30, 0, -8]
    p.both('forearm', x=-62)
    p.add('hand.L', x=-10 + 7 * S(u, 5), z=-4 * S(u, 3))
    p.add('hand.R', x=-10 + 7 * S(u, 6, 0.3), z=4 * S(u, 4))
    p.add('forearm.L', x=1.5 * S(u, 5, 0.2)).add('forearm.R', x=1.5 * S(u, 6, 0.5))
    p.add('head', x=14 + 2 * S(u, 2), y=3 * S(u))
    blink = 85 * bump(u, 0.7, 0.04)
    p.add('lid.L', x=blink).add('lid.R', x=blink)
    return p


def jump(u):
    if u < 0.2:
        c, air = smooth(u / 0.2), 0.0
    elif u < 0.3:
        c, air = 1 - smooth((u - 0.2) / 0.1), 0.0
    elif u < 0.7:
        q = (u - 0.3) / 0.4
        c, air = 0.0, 4 * q * (1 - q)
    elif u < 0.78:
        c, air = smooth((u - 0.7) / 0.08), 0.0
    else:
        c, air = 1 - smooth((u - 0.78) / 0.22), 0.0
    tuck = smooth(air * 6)
    p = Pose()
    p.ground = 1 - min(1.0, air * 20)
    p.lift = 0.35 * air
    p.off[2] = -0.07 * c
    for side in 'LR':
        p.leg(side, 45 * c + 25 * tuck, 80 * c + 50 * tuck)
    swing = keys(u, [(0, 5), (0.2, 45), (0.3, -150), (0.5, -150), (0.7, -40), (0.78, 30), (1, 5)])
    p.both('upper_arm', x=swing, z=8)
    p.both('forearm', x=-12 - 20 * c)
    p.add('spine', x=18 * c).add('head', x=-8 * c)
    p.add('jaw', x=14 * smooth(air * 4))
    return p


def dance(u):
    p = Pose()
    bob = 0.5 + 0.5 * S(u, 4, 0.25)
    knee = 12 + 22 * bob
    p.leg('L', 10 + 6 * S(u, 2), knee).leg('R', 10 - 6 * S(u, 2), knee)
    p.add('hips', y=14 * S(u, 2), z=6 * S(u, 2, 0.25))
    p.add('chest', y=-10 * S(u, 2), z=-4 * S(u, 2, 0.25), x=4 * bob)
    for side, sgn, ph in (('L', 1, 0.0), ('R', -1, 0.5)):
        up = 0.5 + 0.5 * S(u, 2, ph)
        p.rot['upper_arm.' + side] = [-25 * up, 0, sgn * (35 + 95 * up)]
        p.rot['forearm.' + side] = [-30 - 40 * (1 - up), 0, sgn * -25 * up]
        p.rot['hand.' + side] = [0, 0, sgn * 18 * S(u, 4)]
    p.add('head', x=8 * S(u, 4, 0.1), y=10 * S(u, 2, 0.5), z=5 * S(u, 2))
    p.add('jaw', x=6 * bump(u, 0.5, 0.2))
    return p


def stretch(u):
    e = math.sin(math.pi * u) ** 2
    p = Pose()
    p.leg('L', 1.5, 3).leg('R', 0, 2)
    p.rot['upper_arm.L'] = [-6 * e, 0, 7 + 160 * e]
    p.rot['upper_arm.R'] = [-6 * e, 0, -7 - 160 * e]
    p.both('forearm', x=-8 * (1 - e) - 4 * e)
    p.add('chest', x=-8 * e, z=8 * S(u, 1) * e).add('spine', z=4 * S(u, 1) * e)
    p.add('head', x=-10 * e)
    p.add('jaw', x=16 * bump(u, 0.5, 0.25))
    p.off[1] += 0.015 * e
    return p


# name -> (function, seconds per loop, travel m/s, props shown, label)
CLIPS = {
    'idle': (idle, 4.0, 0.0, [], 'Idle'),
    'walk': (walk, 1.2, 1.2, [], 'Walk'),
    'run': (run, 0.72, 3.2, [], 'Run'),
    'wave': (wave, 2.0, 0.0, [], 'Wave'),
    'talk': (talk, 4.0, 0.0, [], 'Talk'),
    'sit': (sit, 4.0, 0.0, ['chair'], 'Sit'),
    'type': (type_, 2.0, 0.0, ['chair', 'desk'], 'Type'),
    'jump': (jump, 1.6, 0.0, [], 'Jump'),
    'dance': (dance, 2.0, 0.0, [], 'Dance'),
    'stretch': (stretch, 5.0, 0.0, [], 'Stretch'),
}


def sample(name, fps=30):
    """Return ``[(rot_dict, off), ...]`` for one loop of ``name`` (last frame excluded)."""
    fn, dur, _, _, _ = CLIPS[name]
    n = max(1, round(dur * fps))
    return [fn(i / n).frame() for i in range(n)]
