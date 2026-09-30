"""Procedural mesh toolkit used by the character and scene builders.

Geometry is assembled as lightweight ``Part`` objects (vertices, faces, per-
vertex bone weights, per-face material index, optional UVs and vertex colours)
and converted into Blender objects at the end.  Keeping geometry in plain
Python makes the builders deterministic and easy to extend.
"""
import math
import bpy
from mathutils import Vector, Matrix


def smoothstep(e0, e1, x):
    if e0 == e1:
        return 1.0 if x >= e1 else 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def mix_weights(a, b, t):
    out = {}
    for k, v in a.items():
        out[k] = out.get(k, 0) + v * (1 - t)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v * t
    return {k: v for k, v in out.items() if v > 1e-4}


class Part:
    def __init__(self):
        self.v = []      # Vector
        self.f = []      # tuple of indices
        self.w = []      # dict bone->weight per vertex
        self.fm = []     # material index per face
        self.uv = []     # per-face list of (u,v) tuples or None
        self.col = []    # per-vertex RGBA or None

    def vert(self, p, w=None, col=None):
        self.v.append(Vector(p))
        self.w.append(dict(w) if w else {})
        self.col.append(col)
        return len(self.v) - 1

    def face(self, idx, mat=0, uv=None):
        self.f.append(tuple(idx))
        self.fm.append(mat)
        self.uv.append(uv)

    def extend(self, other, mat_offset=0):
        base = len(self.v)
        self.v.extend(v.copy() for v in other.v)
        self.w.extend(dict(w) for w in other.w)
        self.col.extend(other.col)
        for f, m, uv in zip(other.f, other.fm, other.uv):
            self.f.append(tuple(i + base for i in f))
            self.fm.append(m + mat_offset)
            self.uv.append(uv)
        return self

    def set_mat(self, m):
        self.fm = [m] * len(self.f)
        return self

    def set_weights(self, w):
        self.w = [dict(w) for _ in self.v]
        return self

    def transform(self, mat):
        for i, v in enumerate(self.v):
            self.v[i] = mat @ v
        return self

    def mirrored_x(self):
        m = Part()
        for v, w, c in zip(self.v, self.w, self.col):
            m.vert((-v.x, v.y, v.z), {swap_side(k): x for k, x in w.items()}, c)
        for f, mi, uv in zip(self.f, self.fm, self.uv):
            m.face(tuple(reversed(f)), mi, list(reversed(uv)) if uv else None)
        return m

    def displace(self, fn):
        for i, v in enumerate(self.v):
            self.v[i] = fn(v)
        return self


def swap_side(name):
    if name.endswith('.L'):
        return name[:-2] + '.R'
    if name.endswith('.R'):
        return name[:-2] + '.L'
    return name


# ---------------------------------------------------------------- lofting

def _frame(t, front):
    t = t.normalized()
    f = Vector(front)
    f = f - t * f.dot(t)
    if f.length < 1e-5:
        f = Vector((0, 0, 1)) - t * t.z
        if f.length < 1e-5:
            f = Vector((1, 0, 0))
    f.normalize()
    s = t.cross(f)
    return s, f


def sec(c, rs, rf, rb=None, e=2.0, w=None, twist=0.0, front=None, dx=0.0, arc=None):
    """Cross-section description for :func:`loft`.
    rs: side radius, rf: front radius, rb: back radius, e: superellipse exponent,
    arc: optional (a0, a1) partial ring for this section (open garments)."""
    return dict(c=Vector(c), rs=rs, rf=rf, rb=rf if rb is None else rb, e=e, w=w or {}, twist=twist,
                front=front, dx=dx, arc=arc)


def ring_point(s, a):
    cs, sn = math.cos(a + s['twist']), math.sin(a + s['twist'])
    ex = 2.0 / s['e']
    x = s['rs'] * math.copysign(abs(cs) ** ex, cs) + s['dx']
    r = s['rf'] if sn >= 0 else s['rb']
    y = r * math.copysign(abs(sn) ** ex, sn)
    return x, y


def loft(sections, n=24, cap_start=False, cap_end=False, mat=0, front=(0, -1, 0), weight_fn=None,
         col=None, uv=False, closed=True, arc=None):
    """Build a tube through ``sections``.  ``weight_fn(p, ring_w, ring_index, angle)`` may
    override vertex weights.  ``arc`` = (a0, a1) builds an open partial tube."""
    p = Part()
    m = len(sections)
    rings = []
    for i, s in enumerate(sections):
        c = s['c']
        if m == 1:
            t = Vector((0, 0, 1))
        elif i == 0:
            t = sections[1]['c'] - c
        elif i == m - 1:
            t = c - sections[i - 1]['c']
        else:
            t = sections[i + 1]['c'] - sections[i - 1]['c']
        S, F = _frame(t, s['front'] or front)
        ring = []
        cnt = n if (closed and arc is None) else n + 1
        for j in range(cnt):
            sa = s.get('arc') or arc
            if sa is None:
                a = 2 * math.pi * j / n
            else:
                a = sa[0] + (sa[1] - sa[0]) * j / n
            x, y = ring_point(s, a)
            pos = c + S * x + F * y
            w = s['w']
            if weight_fn:
                w = weight_fn(pos, w, i, a)
            ring.append(p.vert(pos, w, col))
        rings.append(ring)
    cnt = len(rings[0])
    seg = cnt if (closed and arc is None) else cnt - 1
    for i in range(m - 1):
        for j in range(seg):
            j2 = (j + 1) % cnt
            quad = (rings[i][j], rings[i + 1][j], rings[i + 1][j2], rings[i][j2])
            u0, u1 = j / seg, (j + 1) / seg
            v0, v1 = i / (m - 1), (i + 1) / (m - 1)
            p.face(quad, mat, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)] if uv else None)
    if cap_start:
        s = sections[0]
        ci = p.vert(s['c'], s['w'], col)
        for j in range(seg):
            p.face((ci, rings[0][(j + 1) % cnt], rings[0][j]), mat)
    if cap_end:
        s = sections[-1]
        ci = p.vert(s['c'], s['w'], col)
        for j in range(seg):
            p.face((ci, rings[-1][j], rings[-1][(j + 1) % cnt]), mat)
    return p


def dome_cap(sections, end=True, steps=3, n=24, mat=0, front=(0, -1, 0), depth=None, col=None):
    """Rounded cap (hemisphere-ish) at the start or end of a loft."""
    s = sections[-1] if end else sections[0]
    other = sections[-2] if end else sections[1]
    t = (s['c'] - other['c']).normalized()
    r = max(s['rs'], s['rf'])
    depth = depth if depth is not None else r
    secs = []
    for k in range(steps + 1):
        a = (k / steps) * (math.pi / 2)
        sc = math.cos(a)
        secs.append(sec(s['c'] + t * depth * math.sin(a), max(s['rs'] * sc, 1e-4), max(s['rf'] * sc, 1e-4),
                        max(s['rb'] * sc, 1e-4), s['e'], s['w'], s['twist'], s['front'], s['dx'] * sc))
    part = loft(secs if end else list(reversed(secs)), n=n, mat=mat, front=front, col=col,
                cap_end=end, cap_start=not end)
    return part


def tube_path(points, radii, n=6, mat=0, flat=1.0, front=(0, -1, 0), w=None, cap=True, col=None, up=None):
    """Tapered tube along a polyline (hair clumps, cables, rods)."""
    secs = []
    for i, (pt, r) in enumerate(zip(points, radii)):
        secs.append(sec(pt, r, r * flat, w=w, front=up))
    part = loft(secs, n=n, mat=mat, front=front, cap_start=cap, cap_end=cap, col=col)
    return part


# ---------------------------------------------------------------- primitives

def uv_sphere(center, radii, nu=24, nv=16, mat=0, w=None, deform=None, col=None, uv=False):
    p = Part()
    cx, cy, cz = center
    rx, ry, rz = radii
    rows = []
    for j in range(nv + 1):
        th = math.pi * j / nv
        row = []
        for i in range(nu):
            ph = 2 * math.pi * i / nu
            d = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
            pos = Vector((cx + rx * d.x, cy + ry * d.y, cz + rz * d.z))
            if deform:
                pos = deform(pos, d)
            row.append(p.vert(pos, w, col))
            if j == 0 or j == nv:
                break
        rows.append(row)
    for j in range(nv):
        for i in range(nu):
            i2 = (i + 1) % nu
            u0, u1, v0, v1 = i / nu, (i + 1) / nu, 1 - j / nv, 1 - (j + 1) / nv
            if j == 0:
                p.face((rows[0][0], rows[1][i], rows[1][i2]), mat, [(u0, v0), (u0, v1), (u1, v1)] if uv else None)
            elif j == nv - 1:
                p.face((rows[j][i], rows[j + 1][0], rows[j][i2]), mat, [(u0, v0), (u0, v1), (u1, v0)] if uv else None)
            else:
                p.face((rows[j][i], rows[j + 1][i], rows[j + 1][i2], rows[j][i2]), mat,
                       [(u0, v0), (u0, v1), (u1, v1), (u1, v0)] if uv else None)
    return p


def box(center, size, mat=0, w=None, bevel=0.0, col=None):
    """Axis aligned box; ``bevel`` > 0 gives a chamfered box (cheap rounded look)."""
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    p = Part()
    if bevel <= 0:
        pts = [(cx + x * sx, cy + y * sy, cz + z * sz) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
        idx = [p.vert(q, w, col) for q in pts]
        for fc in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            p.face([idx[i] for i in fc], mat)
        return p
    b = min(bevel, sx * 0.9, sy * 0.9, sz * 0.9)
    # rounded box as a loft of superellipse rings
    secs = []
    for z, s_in in ((-sz, b * 0.3), (-sz + b, 0), (sz - b, 0), (sz, b * 0.3)):
        secs.append(sec((cx, cy, cz + z), sx - s_in, sy - s_in, e=10.0, front=(0, -1, 0)))
    return loft(secs, n=24, mat=mat, cap_start=True, cap_end=True, front=(0, -1, 0), col=col).set_weights(w or {})


def cylinder(p0, p1, r, n=16, mat=0, w=None, r1=None, cap=True, col=None, front=(0, -1, 0)):
    r1 = r if r1 is None else r1
    return loft([sec(p0, r, r, w=w), sec(p1, r1, r1, w=w)], n=n, mat=mat, cap_start=cap, cap_end=cap,
                front=front, col=col)


def torus_path(points, r, n=8, mat=0, w=None, closed=True, col=None):
    """Tube following a closed (or open) polyline - glasses rims, rings, garlands."""
    pts = list(points)
    if closed:
        pts = pts + [pts[0], pts[1]]
    part = tube_path(pts, [r] * len(pts), n=n, mat=mat, w=w, cap=not closed, col=col)
    return part


def plane(center, size, mat=0, normal='Z', col=None, uv=True):
    cx, cy, cz = center
    sx, sy = size[0] / 2, size[1] / 2
    p = Part()
    if normal == 'Z':
        pts = [(cx - sx, cy - sy, cz), (cx + sx, cy - sy, cz), (cx + sx, cy + sy, cz), (cx - sx, cy + sy, cz)]
    elif normal == '-Y':  # vertical, facing -Y (towards default camera)
        pts = [(cx - sx, cy, cz - sy), (cx + sx, cy, cz - sy), (cx + sx, cy, cz + sy), (cx - sx, cy, cz + sy)]
    elif normal == 'Y':
        pts = [(cx + sx, cy, cz - sy), (cx - sx, cy, cz - sy), (cx - sx, cy, cz + sy), (cx + sx, cy, cz + sy)]
    elif normal == 'X':
        pts = [(cx, cy + sx, cz - sy), (cx, cy - sx, cz - sy), (cx, cy - sx, cz + sy), (cx, cy + sx, cz + sy)]
    else:  # -X
        pts = [(cx, cy - sx, cz - sy), (cx, cy + sx, cz - sy), (cx, cy + sx, cz + sy), (cx, cy - sx, cz + sy)]
    idx = [p.vert(q, None, col) for q in pts]
    p.face(idx, mat, [(0, 0), (1, 0), (1, 1), (0, 1)] if uv else None)
    return p


# ---------------------------------------------------------------- Blender objects

def to_object(part, name, materials, collection=None, armature=None, smooth=True, subsurf=0,
              uv_name='UVMap', color_name=None, auto_smooth=None, render_subsurf=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in part.v], [], part.f)
    me.update(calc_edges=True)
    for m in materials:
        me.materials.append(m)
    if part.fm:
        me.polygons.foreach_set('material_index', part.fm)
    me.polygons.foreach_set('use_smooth', [smooth] * len(me.polygons))
    if any(u is not None for u in part.uv):
        uvl = me.uv_layers.new(name=uv_name)
        data = []
        for poly, uv in zip(me.polygons, part.uv):
            if uv is None:
                uv = [(0.5, 0.5)] * poly.loop_total
            for k in range(poly.loop_total):
                data.extend(uv[k])
        uvl.data.foreach_set('uv', data)
    if color_name and any(c is not None for c in part.col):
        attr = me.color_attributes.new(name=color_name, type='BYTE_COLOR', domain='POINT')
        flat = []
        for c in part.col:
            c = c or (1, 1, 1, 1)
            flat.extend(c if len(c) == 4 else (*c, 1))
        attr.data.foreach_set('color', flat)
        try:
            me.color_attributes.active_color = attr
            me.color_attributes.render_color_index = me.color_attributes.find(color_name)
        except Exception:
            pass
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if armature is not None:
        groups = {}
        for i, w in enumerate(part.w):
            tot = sum(w.values())
            if tot <= 0:
                continue
            # keep the 4 strongest influences (glTF limit) and normalise
            items = sorted(w.items(), key=lambda kv: -kv[1])[:4]
            tot = sum(x for _, x in items)
            for b, x in items:
                groups.setdefault(b, {}).setdefault(round(x / tot, 4), []).append(i)
        for b, by_w in groups.items():
            vg = ob.vertex_groups.new(name=b)
            for wv, idx in by_w.items():
                vg.add(idx, wv, 'REPLACE')
        ob.parent = armature
        mod = ob.modifiers.new('Armature', 'ARMATURE')
        mod.object = armature
    if subsurf:
        sm = ob.modifiers.new('Subdivision', 'SUBSURF')
        sm.levels = subsurf
        sm.render_levels = render_subsurf if render_subsurf is not None else subsurf
        # subdivision after the armature is fine; keep armature first in the stack
    return ob


def vertex_normals(part):
    ns = [Vector((0, 0, 0)) for _ in part.v]
    for f in part.f:
        if len(f) < 3:
            continue
        a, b, c = part.v[f[0]], part.v[f[1]], part.v[f[2]]
        n = (b - a).cross(c - a)
        if len(f) == 4:
            n += (c - a).cross(part.v[f[3]] - a)
        for i in f:
            ns[i] += n
    return [n.normalized() if n.length > 1e-12 else Vector((0, 0, 1)) for n in ns]


def chaikin(pts, iterations=1):
    for _ in range(iterations):
        if len(pts) < 3:
            return pts
        out = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            out.append(a.lerp(b, 0.25))
            out.append(a.lerp(b, 0.75))
        out.append(pts[-1])
        pts = out
    return pts


def shell(part, mask_fn, thickness_fn, mat=0, weights=None, col=None, normals=None):
    """Offset copy of the faces of ``part`` whose vertices all pass ``mask_fn(i, v) > 0``."""
    normals = normals or vertex_normals(part)
    out = Part()
    m = [mask_fn(i, v) for i, v in enumerate(part.v)]
    remap = {}
    for f in part.f:
        if all(m[i] > 0 for i in f):
            idx = []
            for i in f:
                if i not in remap:
                    v = part.v[i] + normals[i] * thickness_fn(i, part.v[i], m[i])
                    remap[i] = out.vert(v, weights(i, v) if weights else part.w[i], col(i, m[i]) if col else None)
                idx.append(remap[i])
            out.face(idx, mat)
    return out
