"""Small compatibility layer so the engine runs on Blender 4.2 LTS ... 5.x.

Everything version-specific (render engine names, action/F-curve storage,
glTF exporter options) is isolated here.
"""
import bpy

VERSION = bpy.app.version


def eevee_engine_id():
    items = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    for cand in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        if cand in items:
            return cand
    return 'BLENDER_WORKBENCH'


def engine_id(name):
    name = (name or 'eevee').lower()
    if name == 'cycles':
        return 'CYCLES'
    if name == 'workbench':
        return 'BLENDER_WORKBENCH'
    return eevee_engine_id()


def new_action_fcurves(id_block, action_name, id_type='OBJECT'):
    """Create an action, assign it to ``id_block`` and return an object with
    ``.new(data_path, index=0, action_group='')`` for creating F-curves.
    Works with both the legacy (<=4.3) and slotted (4.4+) action systems."""
    action = bpy.data.actions.new(action_name)
    ad = id_block.animation_data or id_block.animation_data_create()
    ad.action = action
    if hasattr(action, 'slots') and not hasattr(action, 'fcurves'):
        from bpy_extras import anim_utils
        slot = ad.action_slot
        if slot is None:
            slot = action.slots.new(id_type=id_type, name=id_block.name)
            ad.action_slot = slot
        bag = anim_utils.action_ensure_channelbag_for_slot(action, slot)
        return action, bag.fcurves
    if hasattr(action, 'slots') and ad.action_slot is None and len(action.slots) == 0:
        # 4.4/4.5: legacy fcurves proxy still exists, but make sure a slot is bound
        try:
            slot = action.slots.new(id_type=id_type, name=id_block.name)
            ad.action_slot = slot
        except Exception:
            pass
    return action, action.fcurves


def write_fcurve(fcurves, data_path, index, frames, values, group=''):
    fc = fcurves.new(data_path, index=index, action_group=group) if group else fcurves.new(data_path, index=index)
    n = len(frames)
    fc.keyframe_points.add(n)
    co = [0.0] * (2 * n)
    co[0::2] = frames
    co[1::2] = values
    fc.keyframe_points.foreach_set('co', co)
    try:  # enum order: CONSTANT=0, LINEAR=1, BEZIER=2
        fc.keyframe_points.foreach_set('interpolation', [1] * n)
    except Exception:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    fc.update()
    return fc


def gltf_export(filepath, use_selection=True, animations=True, anim_mode='NLA_TRACKS'):
    op = bpy.ops.export_scene.gltf
    props = set(op.get_rna_type().properties.keys())
    kw = dict(filepath=filepath, export_format='GLB')
    wanted = {
        'use_selection': use_selection,
        'export_apply': True,
        'export_animations': animations,
        'export_animation_mode': anim_mode,
        'export_skins': True,
        'export_morph': True,
        'export_yup': True,
        'export_cameras': False,
        'export_lights': False,
        'export_vertex_color': 'ACTIVE',
        'export_all_vertex_colors': False,
        'export_colors': True,
        'export_optimize_animation_size': False,
        'export_anim_slide_to_zero': False,
        'export_force_sampling': True,
        'export_frame_range': False,
        'export_def_bones': False,
        'export_image_format': 'AUTO',
        'export_extras': True,
    }
    for k, v in wanted.items():
        if k in props:
            kw[k] = v
    return op(**kw)


def set_color_management(scene, look='AgX - Medium High Contrast'):
    vs = scene.view_settings
    try:
        vs.view_transform = 'AgX'
        try:
            vs.look = look
        except TypeError:
            pass
    except TypeError:
        vs.view_transform = 'Filmic'
