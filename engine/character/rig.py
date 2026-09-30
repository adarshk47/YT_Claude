"""Humanoid armature shared by Adarsh, his role variants and background people.

Bone names are stable and documented in docs/RIG.md; animations address bones
by these names so every character can use every action."""
import bpy
from mathutils import Vector

FINGERS = ('index', 'middle', 'ring', 'pinky')
FINGER_LEN = {'index': 0.40, 'middle': 0.44, 'ring': 0.41, 'pinky': 0.33}
FINGER_OFS = {'index': 0.029, 'middle': 0.010, 'ring': -0.009, 'pinky': -0.026}
FINGER_BASE = {'index': 0.54, 'middle': 0.55, 'ring': 0.53, 'pinky': 0.49}
FINGER_SPREAD = {'index': 0.07, 'middle': 0.0, 'ring': -0.06, 'pinky': -0.13}


def hand_frame(spec, side='L'):
    """Return (wrist, down, across, normal) for a hand. ``across`` points from pinky to index
    (forwards), ``normal`` points out of the palm (towards the thigh)."""
    el = spec.pt('elbow.' + side)
    wr = spec.pt('wrist.' + side)
    dn = (wr - el).normalized()
    dn = (dn + Vector((0, 0, -0.35))).normalized()
    n = Vector((-1 if side == 'L' else 1, 0, 0))
    n = (n - dn * n.dot(dn)).normalized()
    across = n.cross(dn).normalized() if side == 'L' else dn.cross(n).normalized()
    return wr, dn, across, n


def hand_points(spec, side='L'):
    wr, dn, ac, n = hand_frame(spec, side)
    h = spec.hand
    s = spec.s
    pts = {}
    pts['hand'] = (wr, wr + dn * h * 0.52)
    for f in FINGERS:
        base = wr + dn * h * FINGER_BASE[f] + ac * FINGER_OFS[f] * s * (0.92 if spec.female else 1.0)
        d = (dn + ac * FINGER_SPREAD[f]).normalized()
        L = h * FINGER_LEN[f]
        mid = base + d * L * 0.55
        tip = base + d * L
        pts[f + '1'] = (base, mid)
        pts[f + '2'] = (mid, tip)
    tb = wr + dn * h * 0.13 + ac * 0.024 * s + n * 0.010 * s
    td = (dn * 0.55 + ac * 0.72 + n * 0.42).normalized()
    t1 = tb + td * h * 0.24
    td2 = (td + dn * 0.35).normalized()
    t2 = t1 + td2 * h * 0.2
    pts['thumb1'] = (tb, t1)
    pts['thumb2'] = (t1, t2)
    return pts


def build_armature(name, spec, face, collection):
    arm = bpy.data.armatures.new(name + '_rig')
    ob = bpy.data.objects.new(name + '_rig', arm)
    collection.objects.link(ob)
    try:
        arm.display_type = 'STICK'
    except Exception:
        pass
    ob.show_in_front = True
    view = bpy.context.view_layer
    view.objects.active = ob
    for o in view.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    z = spec.z
    front = Vector((0, -1, 0))

    def bone(nm, head, tail, parent=None, connect=False, roll_to=front, deform=True):
        b = eb.new(nm)
        b.head = Vector(head)
        b.tail = Vector(tail)
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        try:
            b.align_roll(roll_to)
        except Exception:
            pass
        b.use_deform = deform
        return b

    up = Vector((0, 0, 1))
    bone('root', (0, 0, 0), (0, 0.25 * spec.s, 0), roll_to=up, deform=False)
    bone('hips', (0, 0.0, z['hip'] + 0.02 * spec.s), (0, 0.0, z['waist']), 'root')
    bone('spine', (0, 0.0, z['waist']), (0, 0.005, z['ribs'] + 0.05 * spec.s), 'hips', True)
    bone('chest', (0, 0.005, z['ribs'] + 0.05 * spec.s), (0, 0.01, z['neck_base']), 'spine', True)
    bone('neck', (0, 0.012 * spec.s, z['neck_base']), (0, 0.016 * spec.k, z['neck_top']), 'chest', True)
    bone('head', (0, 0.016 * spec.k, z['neck_top']), (0, 0.016 * spec.k, z['crown']), 'neck', True)
    bone('jaw', face['jaw_pivot'], face['chin'], 'head', roll_to=up)
    for sd in ('L', 'R'):
        sg = 1 if sd == 'L' else -1
        ec = face['eye.' + sd]
        bone('eye.' + sd, ec, ec + Vector((0, -0.02 * spec.k, 0)), 'head', roll_to=up)
        bone('lid.' + sd, ec, ec + Vector((0, -0.018 * spec.k, 0.004)), 'head', roll_to=up)
        mc = face['mouth_corner.' + sd]
        bone('mouth_corner.' + sd, mc, mc + Vector((sg * 0.012 * spec.k, 0.0, 0)), 'head', roll_to=up)
        bone('brow.' + sd, face['brow.' + sd], face['brow.' + sd] + Vector((0, -0.012 * spec.k, 0)), 'head', roll_to=up)
        sh = spec.pt('shoulder.' + sd)
        bone('clavicle.' + sd, (sg * 0.02 * spec.s, 0.01 * spec.s, z['neck_base'] - 0.025 * spec.s), sh, 'chest')
        bone('upper_arm.' + sd, sh, spec.pt('elbow.' + sd), 'clavicle.' + sd, True)
        bone('forearm.' + sd, spec.pt('elbow.' + sd), spec.pt('wrist.' + sd), 'upper_arm.' + sd, True)
        hp = hand_points(spec, sd)
        bone('hand.' + sd, *hp['hand'], 'forearm.' + sd, True)
        for f in FINGERS + ('thumb',):
            bone(f + '1.' + sd, *hp[f + '1'], 'hand.' + sd)
            bone(f + '2.' + sd, *hp[f + '2'], f + '1.' + sd, True)
        bone('thigh.' + sd, spec.pt('hip.' + sd), spec.pt('knee.' + sd), 'hips')
        bone('shin.' + sd, spec.pt('knee.' + sd), spec.pt('ankle.' + sd), 'thigh.' + sd, True)
        bone('foot.' + sd, spec.pt('ankle.' + sd), spec.pt('ball.' + sd), 'shin.' + sd, True, roll_to=up)
        bone('toe.' + sd, spec.pt('ball.' + sd), spec.pt('toe.' + sd), 'foot.' + sd, True, roll_to=up)
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return ob
