"""Key the procedural activity clips (``activities.py``) onto a character armature.

Each activity becomes one Action, pushed onto its own NLA track so the exported
GLB carries every clip by name.  Rotations are authored in character space
(+X left, +Y up, +Z forward) and converted to each bone's local rest frame here.
"""
import math
import bpy
from mathutils import Euler, Matrix, Vector
from ..bl_compat import new_action_fcurves, write_fcurve
from . import activities as A

# character space (x left, y up, z forward) -> Blender (x left, z up, -y forward); det = +1
TO_BLENDER = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def _local_quat(pb, rot_deg):
    """Character-space joint rotation -> pose-bone ``rotation_quaternion``.

    For a bone with rest orientation Rr (armature space), basis = Rr^-1 * Q * Rr where Q is the
    rotation expressed in armature space; this keeps parent-chain composition correct."""
    # three.js 'XYZ' (R = Rx*Ry*Rz) is Blender 'ZYX'
    q_char = Euler([math.radians(a) for a in rot_deg], 'ZYX').to_matrix()
    q_arm = TO_BLENDER @ q_char @ TO_BLENDER.inverted()
    rr = pb.bone.matrix_local.to_3x3()
    return (rr.inverted() @ q_arm @ rr).to_quaternion()


def _local_loc(pb, vec, scale):
    rr = pb.bone.matrix_local.to_3x3()
    return rr.inverted() @ (TO_BLENDER @ (scale * Vector(vec)))


def bake_activity(arm, name, fps=30, hips_scale=1.0):
    """Create the Action for activity ``name`` on armature object ``arm`` and return it."""
    scene = bpy.context.scene
    frames = A.sample(name, fps)
    action, fcurves = new_action_fcurves(arm, 'Adarsh_' + name)
    action.use_fake_user = True
    xs = [float(i + 1) for i in range(len(frames) + 1)]       # loop: repeat first frame at the end
    data = {}
    for bone in A.BONES:
        pb = arm.pose.bones.get(bone)
        if pb is None:
            continue
        qs = [_local_quat(pb, rot[bone]) for rot, _ in frames]
        qs.append(qs[0])
        for i in range(4):
            data[(pb.name, 'rotation_quaternion', i)] = [q[i] for q in qs]
    hips = arm.pose.bones['hips']
    locs = [_local_loc(hips, off, hips_scale) for _, off in frames]
    locs.append(locs[0])
    for i in range(3):
        data[('hips', 'location', i)] = [v[i] for v in locs]
    for (bname, prop, idx), vals in data.items():
        write_fcurve(fcurves, 'pose.bones["%s"].%s' % (bname, prop), idx, xs, vals, group=bname)
    action.frame_range = (1, len(frames) + 1)
    action.use_frame_range = True
    action.use_cyclic = True
    scene.render.fps = fps
    return action


def bake_all(arm, fps=30, hips_scale=1.0):
    """Bake every activity into NLA tracks (one track per clip)."""
    ad = arm.animation_data or arm.animation_data_create()
    actions = {}
    for name in A.CLIPS:
        action = bake_activity(arm, name, fps, hips_scale)
        ad.action = None
        track = ad.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 1, action)
        strip.action_frame_end = action.frame_range[1]
        actions[name] = action
    return actions
