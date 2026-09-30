"""Garment and accessory library.

An outfit is a list of item dictionaries, e.g.::

    [{"type": "shirt", "color": "#9fc3e6", "sleeve": "long", "collar": "shirt", "tucked": true},
     {"type": "trousers", "color": "#2a2d36"}, {"type": "belt"}, {"type": "shoes", "color": "#1b1714"}]

Every item is generated around the same body profile and skinned with the
same weights as the body underneath, which keeps clipping low during motion.
Add a new garment by writing a function ``def g_<type>(o, it)`` below and
registering it in ``GARMENTS``.
"""
import math
from mathutils import Vector
from ..meshkit import Part, sec, loft, tube_path, uv_sphere, smoothstep, mix_weights, to_object, dome_cap
from .body import (torso_part, torso_point, torso_weights, torso_at, arm_part, arm_path, arm_weights, leg_part,
                   leg_path, leg_weights, foot_sections)
from . import materials as M

HALF_PI = math.pi / 2


class Outfit:
    def __init__(self, spec, head, name):
        self.spec = spec
        self.head = head
        self.name = name
        self.part = Part()
        self.mats = []
        self._mi = {}
        self.flags = set()

    def mat(self, key, color, **kw):
        k = (key, str(color), tuple(sorted(kw.items())))
        if k not in self._mi:
            self.mats.append(M.material('%s_%s' % (self.name, key), color, **kw))
            self._mi[k] = len(self.mats) - 1
        return self._mi[k]

    def add(self, part, mi):
        part.set_mat(mi)
        self.part.extend(part)


# ------------------------------------------------------------------ helpers

def neck_c(spec, z):
    return Vector((0, 0.016 * spec.s, z))


def ring_band(o, z0, z1, off, mi, arc=None, n=40, leg_follow=0.55):
    spec = o.spec
    secs = []
    for z in (z0, (z0 + z1) / 2, z1):
        t = torso_at(spec, z, off)
        secs.append(sec((0, t['y'], z), t['rs'], t['rf'], t['rb'], e=t['e']))
    p = loft(secs, n=n, arc=arc, weight_fn=lambda q, w, i, a: torso_weights(spec, q, leg_follow))
    o.add(p, mi)


def collar(o, kind, mi, off=0.006, open_deg=None, zip_mi=None):
    spec = o.spec
    z = spec.z
    nb = z['neck_base']
    s = spec.s
    t = torso_at(spec, nb + 0.006, off)
    base_rs, base_rf, base_rb = t['rs'] + 0.004, t['rf'] + 0.004, t['rb'] + 0.004
    yc = t['y']
    wn = lambda q, w, i, a: torso_weights(spec, q)

    def arc_open(deg):
        d = math.radians(deg)
        return (HALF_PI + d, HALF_PI + 2 * math.pi - d)
    if kind in ('shirt', 'polo_zip', 'mandarin', 'rib', 'blazer'):
        h = {'shirt': 0.032, 'polo_zip': 0.036, 'mandarin': 0.028, 'rib': 0.034, 'blazer': 0.03}[kind] * s
        od = open_deg if open_deg is not None else {'shirt': 16, 'polo_zip': 8, 'mandarin': 5, 'rib': 16, 'blazer': 40}[kind]
        grow = 0.006 if kind == 'rib' else 0.0
        secs = []
        for i in range(4):
            tt = i / 3
            zz = nb - 0.006 * s + h * tt
            shrink = 0.004 * s * tt
            secs.append(sec((0, yc + 0.004 * s * tt, zz), base_rs - shrink + grow, base_rf - shrink + grow,
                            base_rb - shrink + grow, e=2.0))
        stand = loft(secs, n=48, arc=arc_open(od), weight_fn=wn)
        o.add(stand, mi)
        if kind in ('shirt', 'blazer'):
            # fold-down collar with points at the front
            fsecs = []
            top = nb - 0.006 * s + h + 0.003 * s
            for i in range(4):
                tt = i / 3
                zz = top - (0.042 * s) * tt
                g = 0.006 * s + 0.030 * s * tt ** 0.8
                fsecs.append(sec((0, yc + 0.006 * s * (1 - tt), zz), base_rs + g, base_rf + g, base_rb + g * 0.6, e=2.0))
            od2 = od + 6
            fall = loft(fsecs, n=48, arc=arc_open(od2), weight_fn=wn)
            # drop the collar points near the front edges
            ring = 49
            for idx in range(len(fall.v)):
                j = idx % ring
                ri = idx // ring
                a = arc_open(od2)[0] + (arc_open(od2)[1] - arc_open(od2)[0]) * j / 48
                dist = min(abs(a - arc_open(od2)[0]), abs(a - arc_open(od2)[1]))
                drop = 0.028 * s * math.exp(-(dist / 0.35) ** 2) * (ri / 3)
                fall.v[idx].z -= drop
                fall.w[idx] = torso_weights(spec, fall.v[idx])
            o.add(fall, mi)
        if kind == 'polo_zip' and zip_mi is not None:
            pts = [torso_point(spec, nb + h * 0.9 - 0.16 * s * i / 8, HALF_PI, off + 0.003) for i in range(9)]
            pts[0].z = nb - 0.006 * s + h
            p = tube_path(pts, [0.0022 * s] * len(pts), n=6, w={'chest': 1.0})
            p.w = [torso_weights(spec, v) for v in p.v]
            o.add(p, zip_mi)
            pull = uv_sphere(pts[1] + Vector((0, -0.004 * s, -0.01 * s)), (0.004 * s, 0.002 * s, 0.009 * s), 8, 6)
            pull.w = [torso_weights(spec, v) for v in pull.v]
            o.add(pull, zip_mi)
    elif kind == 'crew':
        pts = []
        for j in range(33):
            a = 2 * math.pi * j / 32
            pts.append(torso_point(spec, nb + 0.004 * s, a, off + 0.002))
        p = tube_path(pts, [0.006 * s] * len(pts), n=8, cap=False)
        p.w = [torso_weights(spec, v) for v in p.v]
        o.add(p, mi)


def buttons(o, mi, z_top, z_bot, count, off, a=HALF_PI, r=0.0055):
    spec = o.spec
    s = spec.s
    for i in range(count):
        zz = z_top + (z_bot - z_top) * (i / max(1, count - 1))
        c = torso_point(spec, zz, a, off + 0.002)
        b = uv_sphere(c, (r * s, r * 0.5 * s, r * s), 10, 6)
        b.w = [torso_weights(spec, c) for _ in b.v]
        o.add(b, mi)


def patch(o, mi, z0, z1, a0, a1, off, nz=4, na=5, outline_mi=None, flap=False):
    """Rectangular panel on the torso surface (pockets, flaps, name strips)."""
    spec = o.spec
    p = Part()
    rows = []
    for i in range(nz + 1):
        row = []
        for j in range(na + 1):
            zz = z0 + (z1 - z0) * i / nz
            aa = a0 + (a1 - a0) * j / na
            v = torso_point(spec, zz, aa, off + 0.0025 + (0.002 if flap and i == nz else 0))
            row.append(p.vert(v, torso_weights(spec, v)))
        rows.append(row)
    for i in range(nz):
        for j in range(na):
            p.face((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    o.add(p, mi)
    if outline_mi is not None:
        border = [p.v[rows[0][j]] for j in range(na + 1)] + [p.v[rows[i][na]] for i in range(1, nz + 1)] + \
                 [p.v[rows[nz][j]] for j in range(na - 1, -1, -1)] + [p.v[rows[i][0]] for i in range(nz - 1, 0, -1)]
        t = tube_path(border + border[:2], [0.0012 * spec.s] * (len(border) + 2), n=5, cap=False)
        t.w = [torso_weights(spec, v) for v in t.v]
        o.add(t, outline_mi)


def sleeves(o, it, off, mi, cuff_mi=None, kind='long', loose=0.0):
    spec = o.spec
    t1 = {'long': 1.965, 'short': 0.48, 'rolled': 1.36, 'three_quarter': 1.55, 'cap': 0.18}.get(kind, 1.965)
    if kind == 'none':
        return
    for sd in ('L', 'R'):
        extra = (lambda t: loose * smoothstep(0.6, 2.0, t)) if loose else None
        p = arm_part(spec, sd, -0.12, t1, off, n=22, extra=extra)
        o.add(p, mi)
        cm = cuff_mi if cuff_mi is not None else mi
        if kind == 'long' and it.get('cuff', True):
            o.add(arm_part(spec, sd, 1.88, 1.968, off + 0.003 + (loose if loose else 0), n=22), cm)
        elif kind == 'rolled':
            o.add(arm_part(spec, sd, 1.28, 1.38, off + 0.008, n=22), cm)
        elif kind == 'short':
            o.add(arm_part(spec, sd, 0.42, 0.49, off + 0.003, n=22), cm)


def ribbon(o, pts, widths, mi, thick=0.0035, normals=None, n=8, weights=None):
    """Flat band following ``pts`` (scarves, ties, straps)."""
    spec = o.spec
    secs = []
    for i, p in enumerate(pts):
        nrm = normals[i] if normals else Vector((0, -1, 0))
        secs.append(sec(p, widths[i], thick, e=3.0, front=tuple(nrm)))
    part = loft(secs, n=n, cap_start=True, cap_end=True)
    part.w = [weights(v) if weights else torso_weights(spec, v) for v in part.v]
    o.add(part, mi)
    return part


def outward(spec, p):
    t = torso_at(spec, min(p.z, spec.z['neck_base']), 0)
    d = Vector((p.x, p.y - t['y'], 0))
    if d.length < 1e-6:
        return Vector((0, -1, 0))
    return d.normalized()


# ------------------------------------------------------------------ tops

def g_shirt(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.006)
    mi = o.mat(it.get('key', 'shirt'), it.get('color', '#dfe6ee'), rough=0.75)
    tucked = it.get('tucked', True)
    hem = z['hip'] - 0.03 * s if tucked else z['crotch'] - 0.035 * s
    arc_fn = None
    if it.get('open'):
        d = math.radians(it.get('open_deg', 7))
        arc_fn = lambda zz: (HALF_PI + d, HALF_PI + 2 * math.pi - d)
    part = torso_part(spec, hem, z['neck_base'] + 0.006, off, n=44, levels=18, arc_fn=arc_fn)
    o.add(part, mi)
    sleeves(o, it, off + 0.001, mi, kind=it.get('sleeve', 'long'))
    pattern = it.get('pattern')
    if pattern == 'check':
        lm = o.mat(it.get('key', 'shirt') + '_check', it.get('pattern_color', '#5b6f8e'), rough=0.8)
        for zz in [hem + (z['neck_base'] - hem) * i / 7 for i in range(1, 7)]:
            pts = [torso_point(spec, zz, 2 * math.pi * j / 48, off + 0.0012) for j in range(49)]
            t = tube_path(pts, [0.0022 * s] * 49, n=4, cap=False, flat=0.3, up=(0, 0, 1))
            t.w = [torso_weights(spec, v) for v in t.v]
            o.add(t, lm)
    coll = it.get('collar', 'shirt')
    zip_mi = o.mat('zip', '#b9b9b9', rough=0.3, metal=0.9)
    collar(o, coll, mi, off, zip_mi=zip_mi)
    if it.get('buttons', coll in ('shirt',)) and not it.get('open'):
        bm = o.mat('button', it.get('button_color', '#efefe8'), rough=0.4)
        buttons(o, bm, z['neck_base'] - 0.04 * s, hem + 0.05 * s, 6, off)
        # placket line
        pts = [torso_point(spec, z['neck_base'] - 0.01 * s - (z['neck_base'] - hem) * i / 10, HALF_PI, off + 0.0012)
               for i in range(11)]
        t = tube_path(pts, [0.0014 * s] * 11, n=4)
        t.w = [torso_weights(spec, v) for v in t.v]
        o.add(t, mi)
    if it.get('pocket'):
        patch(o, mi, z['chest'] + 0.005 * s, z['chest'] + 0.07 * s, HALF_PI - 0.62, HALF_PI - 0.26, off,
              outline_mi=o.mat(it.get('key', 'shirt') + '_seam', M.mix_hex(it.get('color', '#dfe6ee'), '#000000', 0.25)))
    o.flags.add('top')


def g_tshirt(o, it):
    it = dict(it)
    it.setdefault('collar', 'crew')
    it.setdefault('sleeve', 'short')
    it.setdefault('tucked', False)
    it.setdefault('buttons', False)
    it.setdefault('key', 'tshirt')
    g_shirt(o, it)


def g_polo(o, it):
    it = dict(it)
    it.setdefault('collar', 'polo_zip')
    it.setdefault('tucked', False)
    it.setdefault('buttons', False)
    it.setdefault('key', 'polo')
    g_shirt(o, it)


def _jacket_body(o, it, off, hem, mi, opening, lapel=False, leg_follow=0.55, flare=None, lapel_mi=None):
    spec = o.spec
    z = spec.z
    s = spec.s
    part = torso_part(spec, hem, z['neck_base'] + 0.008, off, n=48, levels=22, arc_fn=opening,
                      leg_follow=leg_follow, flare=flare)
    o.add(part, mi)
    # thickness strip along both open edges
    for side in (0, 1):
        pts = []
        levels = 22
        for i in range(levels + 1):
            zz = hem + (z['neck_base'] + 0.008 - hem) * i / levels
            a0, a1 = opening(zz)
            aa = a0 if side == 0 else a1
            pts.append(torso_point(spec, zz, aa, off + 0.001))
        t = tube_path(pts, [0.0035 * s] * len(pts), n=6, flat=0.8)
        t.w = [torso_weights(spec, v, leg_follow) for v in t.v]
        o.add(t, lapel_mi if lapel_mi is not None else mi)
    if lapel:
        zb = lapel
        for side in (0, 1):
            secs = []
            levels = 10
            for i in range(levels + 1):
                zz = zb + (z['neck_base'] - 0.005 * s - zb) * i / levels
                a0, a1 = opening(zz)
                u = i / levels
                lw = 0.05 + 0.33 * math.sin(min(1.0, u * 1.15) * math.pi * 0.62)
                if u > 0.88:
                    lw *= 0.55  # notch
                arc = (a0, a0 + lw) if side == 0 else (a1 - lw, a1)
                t = torso_at(spec, zz, off + 0.006 + 0.004 * u)
                secs.append(sec((0, t['y'], zz), t['rs'], t['rf'], t['rb'], e=t['e'], arc=arc))
            p = loft(secs, n=10, arc=(0, 1), weight_fn=lambda q, w, i, a: torso_weights(spec, q))
            o.add(p, lapel_mi if lapel_mi is not None else mi)


def g_jacket(o, it):
    """Bomber-style jacket (default Adarsh look)."""
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.022)
    mi = o.mat(it.get('key', 'jacket'), it.get('color', '#1d1b1f'), rough=0.55)
    rib = o.mat('jacket_rib', it.get('rib_color', M.mix_hex(it.get('color', '#1d1b1f'), '#000000', 0.3)), rough=0.85)
    zipm = o.mat('zip', '#b9b9b9', rough=0.3, metal=0.9)
    hem = z['hip'] + 0.0 * s
    d = math.radians(it.get('open_deg', 9)) if it.get('open', True) else 0.004
    opening = lambda zz: (HALF_PI + d, HALF_PI + 2 * math.pi - d)
    _jacket_body(o, it, off, hem, mi, opening, lapel_mi=zipm)
    ring_band(o, hem - 0.035 * s, hem + 0.008 * s, off + 0.004, rib, arc=opening(hem))
    # sleeves with gathered look + rib cuffs
    for sd in ('L', 'R'):
        o.add(arm_part(spec, sd, -0.12, 1.86, off - 0.002, n=24, extra=lambda t: 0.006 * math.sin(t * 3.0) ** 2), mi)
        o.add(arm_part(spec, sd, 1.84, 1.97, off - 0.004, n=24), rib)
    collar(o, 'rib', rib, off - 0.004, open_deg=math.degrees(d) + 8)
    # slanted welt pockets
    for sg in (1, -1):
        a = HALF_PI - sg * 0.95
        pts = [torso_point(spec, z['waist'] - 0.02 * s + 0.08 * s * i / 5, a + sg * 0.12 * i / 5, off + 0.002) for i in range(6)]
        t = tube_path(pts, [0.003 * s] * 6, n=5, flat=0.5)
        t.w = [torso_weights(spec, v) for v in t.v]
        o.add(t, rib)
    o.flags.add('top')


def g_blazer(o, it, long=False):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.022 if not long else 0.026)
    mi = o.mat(it.get('key', 'blazer'), it.get('color', '#2b2f3a'), rough=0.7)
    lm = o.mat(it.get('key', 'blazer') + '_lapel', it.get('lapel_color', M.mix_hex(it.get('color', '#2b2f3a'), '#000000', 0.12)),
               rough=0.6)
    zb = z['waist'] + 0.02 * s if not long else z['waist'] - 0.01 * s
    hem = (z['crotch'] - 0.06 * s) if not long else (z['knee'] + 0.14 * s)
    top = z['neck_base']

    def opening(zz):
        if zz > zb:
            u = smoothstep(zb, top, zz)
            d = 0.035 + 0.55 * u ** 1.1
        else:
            d = 0.035 + 0.14 * smoothstep(zb, hem, zz)
        if it.get('open') and zz < zb:
            d += 0.12
        return (HALF_PI + d, HALF_PI + 2 * math.pi - d)
    flare = (lambda zz: 0.03 * smoothstep(z['crotch'], hem, zz) if zz < z['crotch'] else 0.0) if long else None
    _jacket_body(o, it, off, hem, mi, opening, lapel=zb, leg_follow=0.8 if long else 0.55, flare=flare, lapel_mi=lm)
    sleeves(o, it, off - 0.002, mi, kind=it.get('sleeve', 'long'), loose=0.004)
    collar(o, 'blazer', lm, off - 0.004, open_deg=48)
    bm = o.mat('blazer_button', it.get('button_color', '#1a1a1a'), rough=0.3)
    if not it.get('open'):
        c = torso_point(spec, zb - 0.01 * s, opening(zb)[0] - 0.08, off + 0.004)
        b = uv_sphere(c, (0.007 * s, 0.003 * s, 0.007 * s), 10, 6)
        b.w = [torso_weights(spec, c) for _ in b.v]
        o.add(b, bm)
    # pockets
    for sg in (1, -1):
        a0 = HALF_PI - sg * 0.55
        a1 = HALF_PI - sg * 1.05
        zp = z['hip'] - 0.01 * s if not long else z['crotch'] - 0.02 * s
        patch(o, lm if long else mi, zp, zp + (0.022 if not long else 0.14) * s, min(a0, a1), max(a0, a1), off, flap=True,
              outline_mi=lm)
    patch(o, lm, z['chest'] + 0.02 * s, z['chest'] + 0.032 * s, HALF_PI - 0.75, HALF_PI - 0.45, off)
    if it.get('pen'):
        pm = o.mat('pen', '#1f4fa8', rough=0.3)
        c = torso_point(spec, z['chest'] + 0.05 * s, HALF_PI - 0.62, off + 0.006)
        p = tube_path([c, c + Vector((0, 0, 0.045 * s))], [0.0035 * s] * 2, n=6)
        p.w = [torso_weights(spec, c) for _ in p.v]
        o.add(p, pm)
    o.flags.add('top')


def g_coat(o, it):
    it = dict(it)
    it.setdefault('color', '#f4f5f2')
    it.setdefault('key', 'coat')
    it.setdefault('pen', True)
    g_blazer(o, it, long=True)


def g_vest(o, it):
    """Sleeveless vest: 'nehru' (mandarin collar, closed) or 'waistcoat' (V neck)."""
    spec = o.spec
    z = spec.z
    s = spec.s
    style = it.get('style', 'nehru')
    off = it.get('off', 0.02)
    mi = o.mat(it.get('key', 'vest'), it.get('color', '#3a2f28'), rough=0.7)
    hem = z['hip'] - 0.035 * s if style == 'nehru' else z['hip'] + 0.01 * s
    top = z['neck_base'] + 0.006

    def opening(zz):
        if style == 'waistcoat':
            d = 0.02 + 0.5 * smoothstep(z['chest'] - 0.03 * s, top, zz)
        else:
            d = 0.012
        return (HALF_PI + d, HALF_PI + 2 * math.pi - d)
    # sleeveless: shoulders narrower -> shrink radius near armholes
    extra = lambda zz: {'rs': -0.028 * s * smoothstep(z['chest'] + 0.01 * s, z['shoulder'] - 0.01 * s, zz)}
    part = torso_part(spec, hem, top, off, n=48, levels=20, arc_fn=opening, extra=extra)
    o.add(part, mi)
    if style == 'nehru':
        collar(o, 'mandarin', mi, off, open_deg=5)
        buttons(o, o.mat('vest_button', it.get('button_color', '#c8a45a'), rough=0.3, metal=0.6),
                z['neck_base'] - 0.02 * s, hem + 0.04 * s, 6, off, a=HALF_PI)
    else:
        buttons(o, o.mat('vest_button', it.get('button_color', '#2a2320'), rough=0.3),
                z['chest'] - 0.05 * s, hem + 0.03 * s, 4, off, a=HALF_PI)
    patch(o, mi, z['chest'] + 0.0 * s, z['chest'] + 0.012 * s, HALF_PI - 0.8, HALF_PI - 0.45, off, flap=True)
    o.flags.add('top')


def g_kurta(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.013)
    mi = o.mat(it.get('key', 'kurta'), it.get('color', '#f1ead8'), rough=0.85)
    L = it.get('length', 'knee')
    hem = {'knee': z['knee'] + 0.06 * s, 'long': z['knee'] - 0.06 * s, 'short': z['crotch'] - 0.12 * s,
           'ankle': z['ankle'] + 0.07 * s}[L]
    flare = lambda zz: 0.045 * s * smoothstep(z['hip'], hem, zz) if zz < z['hip'] else 0.0
    part = torso_part(spec, hem, z['neck_base'] + 0.006, off, n=48, levels=26, flare=flare, leg_follow=0.85)
    o.add(part, mi)
    sleeves(o, it, off + 0.002, mi, kind=it.get('sleeve', 'long'), loose=0.012)
    collar(o, it.get('collar', 'mandarin'), mi, off, open_deg=6)
    if it.get('buttons', True) and it.get('collar', 'mandarin') != 'none':
        buttons(o, o.mat('kurta_button', it.get('button_color', '#c9b27a'), rough=0.35, metal=0.4),
                z['neck_base'] - 0.015 * s, z['chest'] - 0.02 * s, 3, off)
    if it.get('border'):
        bm = o.mat('kurta_border', it['border'], rough=0.5, metal=0.3)
        ring_band(o, hem, hem + 0.02 * s, off + flare(hem) + 0.002, bm, leg_follow=0.85)
    o.flags.add('top')


def g_robe(o, it):
    it = dict(it)
    it.setdefault('length', 'ankle')
    it.setdefault('collar', 'crew')
    it.setdefault('sleeve', 'three_quarter')
    it.setdefault('buttons', False)
    it.setdefault('key', 'robe')
    it.setdefault('color', '#d9731f')
    g_kurta(o, it)
    o.flags.add('robe')


def g_safety_vest(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.03)
    mi = o.mat('safety_vest', it.get('color', '#c8e62a'), rough=0.6)
    strip = o.mat('reflective', '#d9d9d6', rough=0.2, metal=0.3)
    hem = z['hip'] - 0.02 * s
    d = 0.06
    opening = lambda zz: (HALF_PI + d + 0.35 * smoothstep(z['chest'], z['neck_base'], zz),
                          HALF_PI + 2 * math.pi - d - 0.35 * smoothstep(z['chest'], z['neck_base'], zz))
    extra = lambda zz: {'rs': -0.03 * s * smoothstep(z['chest'], z['shoulder'], zz)}
    part = torso_part(spec, hem, z['neck_base'] + 0.004, off, n=48, levels=16, arc_fn=opening, extra=extra)
    o.add(part, mi)
    for zz in (z['waist'] - 0.02 * s, z['chest'] - 0.03 * s):
        a0, a1 = opening(zz)
        pts = [torso_point(spec, zz, a0 + (a1 - a0) * j / 40, off + 0.002) for j in range(41)]
        t = tube_path(pts, [0.012 * s] * 41, n=4, flat=0.15, cap=False, up=(0, 0, 1))
        t.w = [torso_weights(spec, v) for v in t.v]
        o.add(t, strip)
    o.flags.add('top')


def g_shawl(o, it):
    """Stole / angavastram / dupatta over both shoulders, ends hanging in front."""
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.034)
    mi = o.mat(it.get('key', 'shawl'), it.get('color', '#e0892b'), rough=0.8)
    width = it.get('width', 0.045) * s
    drop = it.get('drop', z['waist'] - 0.06 * s)
    style = it.get('style', 'both')
    pts, nrms = [], []

    def front_pts(sg, reverse=False):
        seq = []
        for i in range(8):
            zz = drop + (z['shoulder'] - 0.02 * s - drop) * i / 7
            a = HALF_PI - sg * (0.62 - 0.14 * i / 7)
            p = torso_point(spec, zz, a, off)
            seq.append((p, outward(spec, p)))
        return list(reversed(seq)) if reverse else seq

    left = front_pts(1)
    for p, n in left:
        pts.append(p)
        nrms.append(n)
    # over the left shoulder and around the back of the neck
    over = []
    for i in range(1, 8):
        u = i / 8
        ang = HALF_PI - (0.5 + 2.14 * u)  # sweep from front-left over to back
        r = 0.105 * s + off
        zz = z['shoulder'] + 0.025 * s + 0.01 * s * math.sin(u * math.pi)
        c = neck_c(spec, zz)
        p = Vector((math.cos(ang) * r * 1.0, c.y - math.sin(ang) * r * 0.85, zz))
        over.append((p, (Vector((p.x, p.y - c.y, 0)).normalized() * 0.5 + Vector((0, 0, 1)) * 0.5).normalized()))
    for p, n in over:
        pts.append(p)
        nrms.append(n)
    back_mid = Vector((0, neck_c(spec, 0).y + 0.10 * s + off * 0.8, z['shoulder'] + 0.02 * s))
    pts.append(back_mid)
    nrms.append(Vector((0, 1, 0.4)).normalized())
    for p, n in reversed(over):
        pts.append(Vector((-p.x, p.y, p.z)))
        nrms.append(Vector((-n.x, n.y, n.z)))
    if style == 'both':
        for p, n in reversed(left):
            pts.append(Vector((-p.x, p.y, p.z)))
            nrms.append(Vector((-n.x, n.y, n.z)))
    else:  # one end falls behind the right shoulder
        for i in range(1, 6):
            zz = z['shoulder'] - 0.05 * s * i
            p = torso_point(spec, zz, -HALF_PI - 0.4, off)
            pts.append(p)
            nrms.append(outward(spec, p))
    widths = [width] * len(pts)
    ribbon(o, pts, widths, mi, thick=0.004 * s, normals=nrms, n=10)
    if it.get('border'):
        bm = o.mat(it.get('key', 'shawl') + '_border', it['border'], rough=0.45, metal=0.5)
        for sgn in (1, -1):
            ep = []
            for i, (p, n) in enumerate(zip(pts, nrms)):
                if i == 0 or i == len(pts) - 1:
                    tng = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
                else:
                    tng = (pts[i + 1] - pts[i - 1]).normalized()
                side = tng.cross(n).normalized()
                ep.append(p + side * width * 0.92 * sgn + n * 0.001)
            t = tube_path(ep, [0.004 * s] * len(ep), n=5, flat=0.5)
            t.w = [torso_weights(spec, v) for v in t.v]
            o.add(t, bm)
    o.flags.add('shawl')


# ------------------------------------------------------------------ bottoms

def _pelvis(o, off, mi, z_top=None, z_bot=None, leg_follow=0.55):
    spec = o.spec
    z = spec.z
    s = spec.s
    zt = z_top if z_top is not None else z['waist'] + 0.02 * s
    zb = z_bot if z_bot is not None else z['crotch'] - 0.015 * s
    part = torso_part(spec, zb, zt, off, n=40, levels=10, leg_follow=leg_follow)
    o.add(part, mi)


def g_trousers(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.013)
    fit = it.get('fit', 'straight')
    color = it.get('color', '#2c2f38')
    rough = 0.85 if fit != 'jeans' else 0.9
    mi = o.mat(it.get('key', 'trousers'), color, rough=rough)
    _pelvis(o, off, mi)
    t1 = {'straight': 1.965, 'jeans': 1.965, 'cargo': 1.72, 'shorts': 0.52, 'churidar': 1.97, 'pyjama': 1.965}.get(fit, 1.965)
    flare = None
    if fit in ('straight', 'pyjama'):
        flare = lambda t: 0.008 * smoothstep(1.0, 2.0, t) * s
    elif fit == 'cargo':
        flare = lambda t: 0.012 * s
    elif fit == 'shorts':
        flare = lambda t: 0.018 * s * smoothstep(0.1, 0.5, t)
    elif fit == 'jeans':
        flare = lambda t: 0.004 * smoothstep(1.0, 2.0, t) * s
    for sd in ('L', 'R'):
        o.add(leg_part(spec, sd, -0.12, t1, off, n=24, flare=flare), mi)
    # waistband
    wb = o.mat(it.get('key', 'trousers') + '_band', M.mix_hex(color, '#000000', 0.12), rough=rough)
    ring_band(o, z['waist'] - 0.012 * s, z['waist'] + 0.022 * s, off + 0.003, wb)
    if fit == 'jeans':
        seam = o.mat('jeans_seam', it.get('seam_color', '#c7913f'), rough=0.8)
        # back pockets and fly
        for sg in (1, -1):
            a0 = -HALF_PI + sg * 0.25
            a1 = -HALF_PI + sg * 0.85
            patch(o, mi, z['crotch'] + 0.05 * s, z['hip'] + 0.02 * s, min(a0, a1), max(a0, a1), off, outline_mi=seam)
        pts = [torso_point(spec, z['waist'] - 0.01 * s - 0.13 * s * i / 6, HALF_PI - 0.12 * math.sin(i / 6 * 1.4), off + 0.001)
               for i in range(7)]
        t = tube_path(pts, [0.0012 * s] * 7, n=4)
        t.w = [torso_weights(spec, v) for v in t.v]
        o.add(t, seam)
    if fit == 'cargo':
        for sd, sg in (('L', 1), ('R', -1)):
            c = leg_path(spec, sd, 0.5) + Vector((sg * (0.072 * s + off), 0.0, 0))
            box = uv_sphere(c, (0.018 * s, 0.05 * s, 0.07 * s), 10, 8, w={'thigh.' + sd: 1.0})
            for v in box.v:
                v.x = c.x + (v.x - c.x) * 0.9
            o.add(box, mi)
    o.flags.add('legs')


def g_dhoti(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.018)
    mi = o.mat(it.get('key', 'dhoti'), it.get('color', '#f4efe1'), rough=0.9)
    _pelvis(o, off, mi, leg_follow=0.7)
    t1 = it.get('end', 1.86)
    flare = lambda t: s * (0.018 + 0.05 * smoothstep(0.2, 1.7, t))
    for sd in ('L', 'R'):
        o.add(leg_part(spec, sd, -0.12, t1, off, n=26, flare=flare), mi)
    # front pleats hanging between the legs
    pts = []
    for i in range(9):
        u = i / 8
        zz = z['waist'] - (z['waist'] - z['knee'] - 0.05 * s) * u
        p = torso_point(spec, min(zz, z['hip']), HALF_PI, off + 0.012) if zz > z['crotch'] else \
            Vector((0, -(0.13 * s + off) - 0.02 * s * u, zz))
        pts.append(p)
    part = tube_path(pts, [0.028 * s * (1 + 0.4 * i / 8) for i in range(9)], n=8, flat=0.25, up=(0, -1, 0))
    part.w = [torso_weights(spec, v, 0.5) if v.z > z['crotch'] else {'hips': 0.3, 'thigh.L': 0.35, 'thigh.R': 0.35}
              for v in part.v]
    o.add(part, mi)
    if it.get('border'):
        bm = o.mat('dhoti_border', it['border'], rough=0.5, metal=0.3)
        for sd in ('L', 'R'):
            o.add(leg_part(spec, sd, t1 - 0.05, t1, off + 0.002, n=26, flare=flare), bm)
    o.flags.add('legs')


def g_skirt(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.016)
    mi = o.mat(it.get('key', 'skirt'), it.get('color', '#23305a'), rough=0.85)
    hem = z['knee'] + it.get('above_knee', 0.02) * s
    flare = lambda zz: 0.05 * s * smoothstep(z['hip'], hem, zz) if zz < z['hip'] else 0.0
    part = torso_part(spec, hem, z['waist'] + 0.02 * s, off, n=40, levels=12, flare=flare, leg_follow=0.9)
    o.add(part, mi)
    o.flags.add('legs')


# ------------------------------------------------------------------ footwear

def _shoe(o, it, sd, upper_mi, sole_mi, kind):
    spec = o.spec
    s = spec.s
    uo = {'sneakers': 0.011, 'shoes': 0.008, 'boots': 0.011}[kind]
    secs = foot_sections(spec, sd, off=uo * s, height=1.02, width=1.02)
    for sc in secs:
        sc['c'] = sc['c'] + Vector((0, 0, 0.012 * s))
    up = loft(secs, n=20, cap_start=True)
    up.extend(dome_cap(secs, end=True, steps=3, n=20, front=(0, 0, 1), depth=0.02 * s))
    o.add(up, upper_mi)
    # sole
    ss = foot_sections(spec, sd, off=(uo + 0.005) * s, height=1.0, width=1.03)
    sole_secs = []
    for sc in ss:
        c = Vector((sc['c'].x, sc['c'].y, 0.012 * s))
        sole_secs.append(sec(c, sc['rs'], 0.012 * s, 0.012 * s, e=5.0, w=sc['w'], front=(0, 0, 1)))
    sole = loft(sole_secs, n=20, cap_start=True)
    sole.extend(dome_cap(sole_secs, end=True, steps=2, n=20, front=(0, 0, 1), depth=0.018 * s))
    o.add(sole, sole_mi)
    if kind == 'sneakers':
        lm = o.mat('laces', it.get('lace_color', '#f2f2f2'), rough=0.7)
        an = spec.pt('ankle.' + sd)
        for i in range(4):
            y = an.y - 0.035 * s - 0.022 * s * i
            zc = 0.075 * s - 0.009 * s * i
            p0 = Vector((an.x - 0.017 * s, y, zc))
            p1 = Vector((an.x + 0.017 * s, y - 0.004 * s, zc))
            t = tube_path([p0, (p0 + p1) / 2 + Vector((0, -0.002 * s, 0.003 * s)), p1], [0.0022 * s] * 3, n=5)
            t.w = [{'foot.' + sd: 1.0} for _ in t.v]
            o.add(t, lm)
    if kind == 'boots':
        o.add(leg_part(spec, sd, 1.58, 1.985, 0.016 * s, n=22), upper_mi)


def g_sneakers(o, it):
    um = o.mat('sneaker', it.get('color', '#1f4fb4'), rough=0.6)
    sm = o.mat('sneaker_sole', it.get('sole_color', '#f1f1ee'), rough=0.7)
    for sd in ('L', 'R'):
        _shoe(o, it, sd, um, sm, 'sneakers')


def g_shoes(o, it):
    um = o.mat('shoe', it.get('color', '#1a1512'), rough=0.3, coat=0.3)
    sm = o.mat('shoe_sole', it.get('sole_color', '#0f0d0c'), rough=0.6)
    for sd in ('L', 'R'):
        _shoe(o, it, sd, um, sm, 'shoes')


def g_boots(o, it):
    um = o.mat('boot', it.get('color', '#2a241d'), rough=0.55)
    sm = o.mat('boot_sole', '#141210', rough=0.8)
    for sd in ('L', 'R'):
        _shoe(o, it, sd, um, sm, 'boots')


def g_sandals(o, it):
    spec = o.spec
    s = spec.s
    sm = o.mat('sandal', it.get('color', '#6b4125'), rough=0.6)
    for sd in ('L', 'R'):
        ss = foot_sections(spec, sd, off=0.006 * s)
        sole_secs = [sec(Vector((sc['c'].x, sc['c'].y, 0.005 * s)), sc['rs'], 0.005 * s, 0.005 * s, e=5.0, w=sc['w'],
                         front=(0, 0, 1)) for sc in ss]
        sole = loft(sole_secs, n=18, cap_start=True)
        sole.extend(dome_cap(sole_secs, end=True, steps=2, n=18, front=(0, 0, 1), depth=0.016 * s))
        o.add(sole, sm)
        # straps: toe ring and instep band
        fs = foot_sections(spec, sd, off=0.003 * s)
        for idx in (2, 4):
            sc = fs[idx]
            ring = []
            for j in range(17):
                a = math.pi * j / 16
                x = sc['rs'] * math.cos(a)
                zz = sc['c'].z + sc['rf'] * math.sin(a)
                ring.append(Vector((sc['c'].x + x, sc['c'].y, zz)))
            t = tube_path(ring, [0.005 * s] * 17, n=5, flat=0.4, up=(0, -1, 0))
            t.w = [sc['w'] for _ in t.v]
            o.add(t, sm)


def g_socks(o, it):
    spec = o.spec
    mi = o.mat('socks', it.get('color', '#f2f2f2'), rough=0.9)
    for sd in ('L', 'R'):
        o.add(leg_part(spec, sd, 1.62, 1.99, 0.004 * spec.s, n=20), mi)


# ------------------------------------------------------------------ accessories

def g_belt(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.018)
    mi = o.mat('belt', it.get('color', '#2a1f18'), rough=0.45)
    ring_band(o, z['waist'] - 0.008 * s, z['waist'] + 0.02 * s, off, mi)
    bm = o.mat('buckle', it.get('buckle_color', '#b8b8b0'), rough=0.25, metal=0.9)
    c = torso_point(spec, z['waist'] + 0.006 * s, HALF_PI, off + 0.004)
    b = uv_sphere(c, (0.022 * s, 0.004 * s, 0.016 * s), 10, 6)
    for v in b.v:
        v.x = c.x + max(-0.022 * s, min(0.022 * s, (v.x - c.x) * 1.4))
    b.w = [torso_weights(spec, c) for _ in b.v]
    o.add(b, bm)


def g_tie(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.011)
    mi = o.mat('tie', it.get('color', '#7a1f2b'), rough=0.45)
    top = z['neck_base'] + 0.012 * s
    bot = z['waist'] + (0.0 if not spec.child else 0.04) * s
    pts, widths, nrms = [], [], []
    N = 14
    for i in range(N + 1):
        u = i / N
        zz = top - (top - bot) * u
        p = torso_point(spec, zz, HALF_PI, off + (0.006 if u < 0.08 else 0.0))
        pts.append(p)
        wv = 0.011 * s if u < 0.08 else (0.016 + 0.024 * (u - 0.08) / 0.92) * s
        if u > 0.93:
            wv *= 1 - (u - 0.93) / 0.07 * 0.8
        widths.append(wv)
        nrms.append(Vector((0, -1, 0)))
    ribbon(o, pts, widths, mi, thick=0.003 * s, normals=nrms, n=8)
    if it.get('stripes'):
        sm = o.mat('tie_stripe', it['stripes'], rough=0.45)
        for i in range(3, N - 1, 2):
            p = pts[i] + Vector((0, -0.0033 * s, 0))
            t = tube_path([p + Vector((-widths[i] * 0.95, 0, 0.006 * s)), p + Vector((widths[i] * 0.95, 0, -0.006 * s))],
                          [0.0022 * s] * 2, n=4, flat=0.3)
            t.w = [torso_weights(spec, p) for _ in t.v]
            o.add(t, sm)


def g_watch(o, it):
    spec = o.spec
    s = spec.s
    sd = it.get('side', 'L')
    mi = o.mat('watch_strap', it.get('color', '#2a2320'), rough=0.5)
    fm = o.mat('watch_face', it.get('face', '#c9c9c4'), rough=0.2, metal=0.8)
    o.add(arm_part(spec, sd, 1.9, 1.95, 0.004 * s, n=16), mi)
    c = arm_path(spec, sd, 1.925)
    out = Vector((1 if sd == 'L' else -1, 0, 0))
    disc = uv_sphere(c + out * 0.024 * s, (0.004 * s, 0.013 * s, 0.013 * s), 12, 8)
    disc.w = [{'forearm.' + sd: 1.0} for _ in disc.v]
    o.add(disc, fm)


def g_stethoscope(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.03)
    tm = o.mat('stetho_tube', it.get('color', '#222428'), rough=0.35)
    mm = o.mat('stetho_metal', '#c3c6ca', rough=0.2, metal=0.95)
    nb = z['neck_base']
    pts = []
    for i in range(7):
        pts.append(torso_point(spec, z['chest'] + 0.02 * s + (nb - z['chest']) * i / 6 * 0.95, HALF_PI - 0.62 + 0.1 * i / 6, off))
    c = neck_c(spec, nb + 0.012 * s)
    for i in range(1, 12):
        a = HALF_PI - 0.9 - (math.pi * 2 - 1.8) * i / 11 * 0.5 * 2 / 2
        a = (HALF_PI - 0.9) - (2 * math.pi - 1.8) * i / 12
        r = 0.078 * s + off * 0.6
        pts.append(Vector((math.cos(a) * r, c.y - math.sin(a) * r * 0.9, c.z)))
    for i in range(7):
        pts.append(torso_point(spec, nb - (nb - z['chest'] + 0.04 * s) * i / 6, HALF_PI + 0.62 - 0.05 * i / 6, off))
    t = tube_path(pts, [0.0045 * s] * len(pts), n=6)
    t.w = [torso_weights(spec, v) for v in t.v]
    o.add(t, tm)
    end = pts[-1]
    d = uv_sphere(end + Vector((0, -0.006 * s, -0.012 * s)), (0.016 * s, 0.007 * s, 0.016 * s), 12, 8)
    d.w = [torso_weights(spec, end) for _ in d.v]
    o.add(d, mm)


def g_lanyard(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.012)
    mi = o.mat('lanyard', it.get('color', '#1f5aa8'), rough=0.6)
    cm = o.mat('id_card', it.get('card', '#f2f2ee'), rough=0.4)
    nb = z['neck_base']
    card_z = z['chest'] - 0.05 * s
    pts = []
    for i in range(6):
        pts.append(torso_point(spec, card_z + 0.03 * s + (nb - card_z) * i / 5, HALF_PI - 0.25 * i / 5, off))
    c = neck_c(spec, nb + 0.008 * s)
    for i in range(1, 10):
        a = (HALF_PI - 0.5) - (2 * math.pi - 1.0) * i / 10
        r = 0.074 * s + off
        pts.append(Vector((math.cos(a) * r, c.y - math.sin(a) * r * 0.9, c.z)))
    for i in range(6):
        pts.append(torso_point(spec, nb - (nb - card_z - 0.03 * s) * i / 5, HALF_PI + 0.25 - 0.25 * i / 5, off))
    t = tube_path(pts, [0.004 * s] * len(pts), n=4, flat=0.3, up=(0, -1, 0))
    t.w = [torso_weights(spec, v) for v in t.v]
    o.add(t, mi)
    cc = torso_point(spec, card_z, HALF_PI, off + 0.004)
    b = uv_sphere(cc, (0.028 * s, 0.002 * s, 0.04 * s), 8, 6)
    for v in b.v:
        v.x = cc.x + max(-0.027 * s, min(0.027 * s, (v.x - cc.x) * 2.5))
        v.z = cc.z + max(-0.038 * s, min(0.038 * s, (v.z - cc.z) * 2.5))
    b.w = [torso_weights(spec, cc) for _ in b.v]
    o.add(b, cm)


def g_mala(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.03)
    mi = o.mat('mala', it.get('color', '#5a2e1a'), rough=0.6)
    nb = z['neck_base']
    low = z['chest'] - it.get('drop', 0.06) * s
    c = neck_c(spec, nb + 0.01 * s)
    path = []
    for i in range(10):
        u = i / 9
        path.append(torso_point(spec, low + (nb - low) * u ** 1.3, HALF_PI - 0.8 * u ** 0.8, off))
    for i in range(1, 9):
        a = (HALF_PI - 0.8) - (2 * math.pi - 1.6) * i / 9
        r = 0.08 * s + off * 0.5
        path.append(Vector((math.cos(a) * r, c.y - math.sin(a) * r * 0.9, c.z)))
    for i in range(10):
        u = 1 - i / 9
        path.append(torso_point(spec, low + (nb - low) * u ** 1.3, HALF_PI + 0.8 * u ** 0.8, off))
    # beads along the path
    total = 0
    for a, b in zip(path[:-1], path[1:]):
        L = (b - a).length
        nb_ = max(1, int(L / (0.012 * s)))
        for j in range(nb_):
            p = a.lerp(b, j / nb_)
            bead = uv_sphere(p, (0.0055 * s,) * 3, 8, 6)
            bead.w = [torso_weights(spec, p) for _ in bead.v]
            o.add(bead, mi)
            total += 1


def g_tilak(o, it):
    """Forehead mark projected on the skin (vertical, tripundra or dot)."""
    head = o.head
    k = head.k
    mi = o.mat('tilak_' + it.get('style', 'vertical'), it.get('color', '#c8261e'), rough=0.6)
    style = it.get('style', 'vertical')

    def strip(u0, u1, w0, w1, nu=6, nw=4, mat=mi):
        p = Part()
        rows = []
        for i in range(nw + 1):
            row = []
            for j in range(nu + 1):
                u = u0 + (u1 - u0) * j / nu
                w = w0 + (w1 - w0) * i / nw
                loc, nrm = head.front_point(u * k, head.eye_z + w * k)
                row.append(p.vert(loc + nrm * 0.0006 * k, {'head': 1.0}))
            rows.append(row)
        for i in range(nw):
            for j in range(nu):
                p.face((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
        o.add(p, mat)
    if style == 'vertical':
        strip(-0.0035, 0.0035, 0.026, 0.058)
    elif style == 'tripundra':
        wm = o.mat('tilak_ash', it.get('ash', '#e8e2d6'), rough=0.9)
        for w in (0.034, 0.042, 0.050):
            strip(-0.03, 0.03, w, w + 0.0035, nu=12, nw=1, mat=wm)
        strip(-0.004, 0.004, 0.036, 0.047)
    else:
        strip(-0.004, 0.004, 0.028, 0.036)


def g_hard_hat(o, it):
    head = o.head
    k = head.k
    mi = o.mat('hard_hat', it.get('color', '#f2c318'), rough=0.35)
    c = Vector((0, 0.012 * k, head.eye_z + 0.055 * k))
    dome = uv_sphere(c, (0.108 * k, 0.126 * k, 0.1 * k), 24, 12, w={'head': 1.0})
    keep = Part()
    idx = {}
    for f in dome.f:
        if all(dome.v[i].z >= c.z - 0.002 for i in f):
            nf = []
            for i in f:
                if i not in idx:
                    idx[i] = keep.vert(dome.v[i], {'head': 1.0})
                nf.append(idx[i])
            keep.face(nf)
    o.add(keep, mi)
    brim = loft([sec(c + Vector((0, -0.01 * k, -0.002)), 0.12 * k, 0.15 * k, 0.13 * k, e=2.2, w={'head': 1.0}),
                 sec(c + Vector((0, -0.01 * k, 0.006)), 0.108 * k, 0.128 * k, 0.126 * k, e=2.2, w={'head': 1.0})], n=32)
    o.add(brim, mi)
    ridge = tube_path([c + Vector((0, -0.12 * k * math.cos(t), 0.1 * k * math.sin(t))) for t in [i * math.pi / 12 for i in range(13)]],
                      [0.008 * k] * 13, n=6, w={'head': 1.0})
    o.add(ridge, mi)
    o.flags.add('hat')


def g_epaulettes(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    mi = o.mat(it.get('key', 'uniform') + '_strap', it.get('color', '#46503a'), rough=0.8)
    for sg in (1, -1):
        pts = [Vector((sg * (0.06 + 0.1 * i / 4) * s, 0.0, z['shoulder'] + (0.03 - 0.012 * i / 4) * s + 0.022)) for i in range(5)]
        t = tube_path(pts, [0.016 * s] * 5, n=6, flat=0.25, up=(0, 0, 1))
        t.w = [torso_weights(spec, v) for v in t.v]
        o.add(t, mi)


def g_chest_pockets(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    off = it.get('off', 0.007)
    mi = o.mat(it.get('key', 'uniform') + '_pocket', it.get('color', '#4a553d'), rough=0.85)
    seam = o.mat(it.get('key', 'uniform') + '_seam', M.mix_hex(it.get('color', '#4a553d'), '#000000', 0.3), rough=0.85)
    for sg in (1, -1):
        a0, a1 = HALF_PI - sg * 0.3, HALF_PI - sg * 0.75
        patch(o, mi, z['chest'] - 0.03 * s, z['chest'] + 0.06 * s, min(a0, a1), max(a0, a1), off, outline_mi=seam)
        patch(o, mi, z['chest'] + 0.045 * s, z['chest'] + 0.07 * s, min(a0, a1) - 0.02, max(a0, a1) + 0.02, off + 0.003,
              flap=True, outline_mi=seam)


def g_lapel_mic(o, it):
    spec = o.spec
    z = spec.z
    s = spec.s
    mi = o.mat('mic', '#111111', rough=0.5)
    c = torso_point(spec, z['chest'] + 0.07 * s, HALF_PI - 0.5, it.get('off', 0.03))
    m = uv_sphere(c, (0.006 * s, 0.006 * s, 0.01 * s), 8, 6)
    m.w = [torso_weights(spec, c) for _ in m.v]
    o.add(m, mi)


def g_wristband(o, it):
    spec = o.spec
    mi = o.mat('kalava', it.get('color', '#c0281f'), rough=0.7)
    sd = it.get('side', 'R')
    o.add(arm_part(spec, sd, 1.92, 1.95, 0.003 * spec.s, n=14), mi)


GARMENTS = {
    'shirt': g_shirt, 'tshirt': g_tshirt, 'polo': g_polo, 'jacket': g_jacket, 'blazer': g_blazer, 'coat': g_coat,
    'vest': g_vest, 'kurta': g_kurta, 'robe': g_robe, 'safety_vest': g_safety_vest, 'shawl': g_shawl,
    'trousers': g_trousers, 'dhoti': g_dhoti, 'skirt': g_skirt,
    'sneakers': g_sneakers, 'shoes': g_shoes, 'boots': g_boots, 'sandals': g_sandals, 'socks': g_socks,
    'belt': g_belt, 'tie': g_tie, 'watch': g_watch, 'stethoscope': g_stethoscope, 'lanyard': g_lanyard,
    'mala': g_mala, 'tilak': g_tilak, 'hard_hat': g_hard_hat, 'epaulettes': g_epaulettes,
    'chest_pockets': g_chest_pockets, 'lapel_mic': g_lapel_mic, 'wristband': g_wristband,
}


def covered_regions(outfit):
    return set(it.get('type') for it in outfit)


def build_outfit(outfit, spec, head, name, collection, arm):
    if not outfit:
        return []
    o = Outfit(spec, head, name)
    for it in outfit:
        fn = GARMENTS.get(it.get('type'))
        if fn is None:
            print('WARNING: unknown garment type', it.get('type'))
            continue
        fn(o, it)
    ob = to_object(o.part, name + '_outfit', o.mats, collection, arm, subsurf=1)
    ob.modifiers['Subdivision'].levels = 0      # light viewport/glTF mesh
    ob.modifiers['Subdivision'].render_levels = 1
    return [ob]
