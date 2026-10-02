"""Build a character, bake every activity and export a GLB.

    blender -b -P engine/animation/demo.py -- [--role default] [--out work/avatar_activities.glb]
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from engine import bl_compat  # noqa: E402
from engine.character import catalog  # noqa: E402
from engine.character.build import build_character  # noqa: E402
from engine.animation.bake import bake_all  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--role', default='default')
    ap.add_argument('--out', default=os.path.join(ROOT, 'work', 'avatar_activities.glb'))
    args = ap.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = build_character(catalog.adarsh_definition(args.role))
    arm = result['armature']
    bake_all(arm, hips_scale=result['spec'].z['hip'])
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(False)
    arm.select_set(True)
    for o in result['objects']:
        o.select_set(True)
    bl_compat.gltf_export(args.out, use_selection=True, animations=True, anim_mode='NLA_TRACKS')
    print('exported', args.out)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
