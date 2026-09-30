"""Turn the JSON configuration (identity, roles, ages, hairstyles, extras) into
character build definitions.  Pure Python - usable inside and outside Blender."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'config'
LIKENESS = ROOT / 'assets' / 'likeness' / 'adarsh_identity.json'


def load(name):
    p = CONFIG / (name if name.endswith('.json') else name + '.json')
    with open(p, encoding='utf-8') as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith('_')}


def identity():
    with open(LIKENESS, encoding='utf-8') as f:
        return json.load(f)


def _mix(a, b, t):
    a, b = a.lstrip('#'), b.lstrip('#')
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return '#%02x%02x%02x' % tuple(int(x + (y - x) * t) for x, y in zip(ca, cb))


def apply_age(defn, age, hs):
    ages = load('ages')
    a = ages.get(age, {})
    body = defn['body']
    body['girth'] = body.get('girth', 1.0) + a.get('girth_add', 0.0)
    body['belly'] = body.get('belly', 0.0) + a.get('belly', 0.0)
    body['posture'] = max(body.get('posture', 0.0), a.get('posture', 0.0))
    defn['identity']['face'].update(a.get('face', {}))
    hs['volume'] = hs.get('volume', 0.01) * a.get('hair_volume_mul', 1.0)
    hs['density'] = int(hs.get('density', 400) * a.get('hair_density_mul', 1.0))
    hs['hairline_raise'] = hs.get('hairline_raise', 0.0) + a.get('hairline_raise', 0.0)
    hs['temple_recess'] = hs.get('temple_recess', 0.0) + a.get('temple_recess', 0.0)
    g = a.get('grey', 0.0)
    if g > 0:
        defn['grey'] = g
        defn['hair_color'] = '#908b85'
        base = defn['identity'].get('hair', '#1a1310')
        defn['brow_color'] = _mix(base, '#8d8882', min(1.0, g * 0.8))
        defn['beard_color'] = '#a7a29b' if a.get('beard_grey') else _mix(base, '#8d8882', g * 0.6)
    fh = defn.get('facial_hair') or {}
    fh['density'] = fh.get('density', 1.0) * a.get('facial_hair_density_mul', 1.0)
    defn['facial_hair'] = fh
    if age == 'older':
        defn['identity']['skin'] = _mix(defn['identity']['skin'], '#7d5a45', 0.25)
    defn['age'] = age
    return defn


def adarsh_definition(role='default', age='young', variants=()):
    ident = identity()
    roles = load('roles')
    hstyles = load('hairstyles')
    if role not in roles:
        raise KeyError('Unknown role %r (known: %s)' % (role, ', '.join(roles)))
    r = roles[role]
    hs = copy.deepcopy(hstyles[r.get('hair', ident.get('default_hair', 'adarsh_wavy'))])
    hs['name'] = r.get('hair')
    defn = {
        'name': 'Adarsh_%s_%s' % (role, age),
        'kind': 'adarsh', 'role': role,
        'seed': 0,
        'identity': {'skin': ident['skin'], 'hair': ident['hair'], 'eyes': ident.get('eyes', '#2c1a10'),
                     'face': copy.deepcopy(ident.get('face', {}))},
        'body': copy.deepcopy(ident.get('body', {})),
        'hair_style': hs,
        'facial_hair': {'style': r.get('facial_hair', ident.get('facial_hair', {}).get('style', 'moustache_goatee')),
                        'density': ident.get('facial_hair', {}).get('density', 1.0),
                        'length': ident.get('facial_hair', {}).get('length', 1.0)},
        'glasses': copy.deepcopy(ident.get('glasses', {'enabled': True})),
        'outfit': copy.deepcopy(r.get('outfit', [])),
    }
    for v in variants:
        defn['outfit'] += copy.deepcopy(r.get('variants', {}).get(v, []))
    apply_age(defn, age, hs)
    return defn


def extra_definition(eid):
    extras = load('extras')
    e = extras[eid]
    hstyles = load('hairstyles')
    hs = copy.deepcopy(hstyles[e['hair']])
    hs['name'] = e['hair']
    face = {'stubble': 0.0}
    face.update(e.get('face', {}))
    defn = {
        'name': 'Extra_' + eid, 'kind': 'extra', 'extra': eid, 'group': e.get('group'),
        'seed': e.get('seed', 0),
        'identity': {'skin': e.get('skin', '#8f5c3d'), 'hair': e.get('hair_color', '#15100d'),
                     'eyes': e.get('eyes', '#2a180e'), 'face': face},
        'body': copy.deepcopy(e.get('body', {})),
        'hair_style': hs,
        'hair_color': e.get('hair_color'),
        'facial_hair': copy.deepcopy(e.get('facial_hair', {'style': 'none'})),
        'glasses': copy.deepcopy(e.get('glasses', {'enabled': False})),
        'outfit': copy.deepcopy(e.get('outfit', [])),
    }
    for k in ('grey', 'beard_color', 'brow_color'):
        if k in e:
            defn[k] = e[k]
    return defn


def role_ids():
    return list(load('roles').keys())


def extra_ids():
    return list(load('extras').keys())
