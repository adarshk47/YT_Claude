"""Assemble a complete rigged character from a definition dictionary.

A definition combines: identity (face + colours), body parameters, hair style,
facial hair, glasses and an outfit (list of garments/accessories).  See
``engine/character/catalog.py`` for how roles, ages and extras are turned into
definitions."""
import bpy
from mathutils import Vector
from ..meshkit import Part, to_object
from .spec import spec_from
from .head import Head
from .hair import HairBuilder
from .body import body_part
from .rig import build_armature
from . import materials as M
from . import clothes as C


def build_character(defn, collection=None, name=None):
    name = name or defn.get('name', 'Character')
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    spec = spec_from(defn.get('body', {}))
    ident = defn.get('identity', {})
    head = Head(spec, ident.get('face', {}), seed=defn.get('seed', 0))
    skin_part = head.build_skin()
    lay = head.layout()
    arm = build_armature(name, spec, lay, collection)
    arm['adarshpov_character'] = name
    arm['adarshpov_height'] = spec.H

    skin_hex = ident.get('skin', '#a8745a')
    hair_hex = defn.get('hair_color') or ident.get('hair', '#17110e')
    skin = M.material(name + '_skin', skin_hex, rough=0.5, vcol='tint', spec=0.35, sss=0.12)
    objs = []

    covered = C.covered_regions(defn.get('outfit', []))
    include = ['neck', 'hands']
    for part_name in ('torso', 'arms', 'legs', 'feet'):
        include.append(part_name)  # keep full body; clothes cover it (cheap and avoids holes)
    body = body_part(spec, skin_col=(1, 1, 1, 1), include=include)
    ob = to_object(body, name + '_body', [skin], collection, arm, subsurf=1, color_name='tint')
    objs.append(ob)
    ob = to_object(skin_part, name + '_head', [skin], collection, arm, subsurf=1, color_name='tint')
    objs.append(ob)
    ears = head.ears()
    objs.append(to_object(ears, name + '_ears', [skin], collection, arm, subsurf=1, color_name='tint'))

    eye_white = M.material('eye_white', '#e9e4dc', rough=0.18, spec=0.6)
    iris = M.material(name + '_iris', ident.get('eyes', '#3b2416'), rough=0.2, spec=0.6)
    pupil = M.material('pupil', '#050404', rough=0.15)
    eyes, lids, lashes = head.eyes(lay, None)
    objs.append(to_object(eyes, name + '_eyes', [eye_white, iris, pupil], collection, arm))
    objs.append(to_object(lids, name + '_lids', [skin], collection, arm, color_name='tint'))
    hair_mat = M.material(name + '_hair', hair_hex, rough=0.5, vcol='tint', spec=0.35)
    objs.append(to_object(lashes, name + '_lashes', [M.material('lash', '#0b0807', rough=0.6)], collection, arm))
    mouth = head.mouth()
    objs.append(to_object(mouth, name + '_mouth', [M.material('mouth', '#ffffff', rough=0.5, vcol='tint')],
                          collection, arm, color_name='tint'))
    brow_hex = defn.get('brow_color') or hair_hex
    brows = head.brows()
    objs.append(to_object(brows, name + '_brows', [M.material(name + '_brow', brow_hex, rough=0.6)], collection, arm))
    fh = defn.get('facial_hair', {})
    if fh and fh.get('style', 'none') != 'none':
        beard = head.facial_hair(fh.get('style'), fh.get('density', 1.0), fh.get('length', 1.0))
        fh_hex = defn.get('beard_color') or hair_hex
        objs.append(to_object(beard, name + '_facial_hair', [M.material(name + '_beard', fh_hex, rough=0.55)],
                              collection, arm))
    hs = defn.get('hair_style')
    if hs:
        hb = HairBuilder(head, hs, color_mode=defn.get('grey', 0.0), seed=defn.get('seed', 0) + 3)
        cap = hb.cap(skin_part)
        acc = M.material(name + '_hair_accessory', hs.get('accessory_color', '#c0282d'), rough=0.5)
        hair = hb.build()
        hair.extend(cap)
        objs.append(to_object(hair, name + '_hair', [hair_mat, acc], collection, arm, color_name='tint'))
    gl = defn.get('glasses')
    if gl and gl.get('enabled', True):
        fr = M.material('glasses_frame_' + gl.get('frame', '#7d7f86'), gl.get('frame', '#7d7f86'), rough=0.25, metal=0.9)
        lens = M.material('glasses_lens', '#e6eef2', rough=0.05, alpha=0.08, spec=0.3)
        objs.append(to_object(head.glasses(gl), name + '_glasses', [fr, lens], collection, arm))
    # clothes and accessories
    for ob in C.build_outfit(defn.get('outfit', []), spec, head, name, collection, arm):
        objs.append(ob)
    for o in objs:
        o['adarshpov_part'] = True
    return dict(armature=arm, objects=objs, spec=spec, head=head, layout=lay, collection=collection)
