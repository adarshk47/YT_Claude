"""Stylised head and face.

The head is a loft of horizontal sections (a "profile table" like a
sculptor's reference sheet) plus a relief map for the facial features.  All
numbers are editable through the ``face`` block of the identity JSON
(assets/likeness/adarsh_identity.json), so the likeness can be improved without
touching code.  This is an approximation made from a limited set of reference
images; it is not a face scan.
"""
import math
import random
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from ..meshkit import Part, sec, loft, dome_cap, smoothstep, uv_sphere, tube_path, mix_weights, shell, vertex_normals

# z above chin, side radius, front radius, back radius, section centre y, exponent  (head height 0.24 m)
HEAD_TABLE = [
    (0.000, .011, .007, .007, -.066, 2.0),
    (0.008, .024, .012, .015, -.062, 2.2),
    (0.020, .040, .018, .032, -.053, 2.2),
    (0.035, .057, .024, .054, -.042, 2.2),
    (0.050, .067, .038, .064, -.030, 2.25),
    (0.070, .073, .060, .068, -.016, 2.3),
    (0.090, .076, .077, .071, -.004, 2.35),
    (0.110, .074, .088, .077, .004, 2.4),
    (0.130, .077, .094, .085, .008, 2.4),
    (0.150, .079, .096, .092, .010, 2.35),
    (0.170, .079, .095, .096, .012, 2.3),
    (0.190, .077, .091, .096, .012, 2.2),
    (0.205, .073, .085, .091, .012, 2.1),
    (0.220, .063, .072, .079, .012, 2.0),
    (0.232, .045, .050, .057, .012, 2.0),
    (0.2385, .020, .022, .026, .012, 2.0),
]
EYE_W = 0.1176  # eye level above chin for the reference head


def _cr(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def _table_at(z, table=HEAD_TABLE):
    if z <= table[0][0]:
        return table[0][1:]
    if z >= table[-1][0]:
        return table[-1][1:]
    for i in range(len(table) - 1):
        if table[i][0] <= z <= table[i + 1][0]:
            break
    p0, p1, p2, p3 = table[max(0, i - 1)], table[i], table[i + 1], table[min(len(table) - 1, i + 2)]
    t = (z - p1[0]) / (p2[0] - p1[0])
    return tuple(_cr(p0[j], p1[j], p2[j], p3[j], t) for j in range(1, 6))


def g2(u, w, cu, cw, su, sw, pu=2.0):
    return math.exp(-(abs(u - cu) / su) ** pu - ((w - cw) / sw) ** 2)


class Head:
    """Builds head geometry and exposes surface queries for face parts."""

    def __init__(self, spec, face=None, seed=0):
        self.spec = spec
        self.k = spec.k
        self.f = dict(DEFAULT_FACE)
        self.f.update(face or {})
        self.chin_z = spec.z['chin']
        self.eye_z = spec.z['eye']
        self.rng = random.Random(seed)
        self.skin = None
        self.bvh = None

    # ------------------------------------------------------------ shape
    def section(self, zr):
        f = self.f
        rs, rf, rb, yc, e = _table_at(zr)
        jaw = 1.0 + (f['jaw_width'] - 1.0) * (1 - smoothstep(0.03, 0.11, zr))
        chin = 1.0 + (f['chin_width'] - 1.0) * (1 - smoothstep(0.0, 0.05, zr))
        rs *= f['head_width'] * jaw * chin
        rf *= f['face_depth']
        rb *= f['head_depth']
        cheek = f['cheek_full'] * math.exp(-((zr - 0.085) / 0.03) ** 2)
        rs += cheek * 0.004
        return rs, rf, rb, yc, e

    def relief(self, u, w):
        """Forward displacement (in reference metres) of the face surface at (u, w)
        where u = x / k and w = (z - eye_z) / k."""
        f = self.f
        nl, nw, npj = f['nose_length'], f['nose_width'], f['nose_projection']
        es = f['eye_spacing']
        r = 0.0
        # nose
        tip_w = -0.041 * nl
        top_w = 0.010
        base_w = tip_w - 0.009
        if base_w - 0.004 < w < top_w + 0.01:
            if w >= tip_w:
                t = min(1.0, (w - tip_w) / (top_w - tip_w))
                h = (0.021 * npj) * (1 - t) ** 0.9 + 0.0035 * t
                wd = (0.0125 * nw) * (1 - t) + 0.0072 * t
                if w > top_w:
                    h *= 1 - smoothstep(top_w, top_w + 0.01, w)
            else:
                t = min(1.0, (tip_w - w) / (tip_w - base_w))
                h = 0.021 * npj * (1 - t ** 1.6) * 0.95 + 0.001
                wd = 0.0125 * nw * (1 + 0.15 * t)
                if w < base_w:
                    h *= 1 - smoothstep(base_w, base_w - 0.004, w)
            r += h * math.exp(-(u / wd) ** 2)
        # nostril wings
        for sg in (-1, 1):
            r += 0.0072 * g2(u, w, sg * 0.0158 * nw, tip_w - 0.003, 0.0068 * nw, 0.0058)
        # eye sockets and brows
        for sg in (-1, 1):
            r -= 0.0085 * g2(u, w, sg * 0.0315 * es, 0.001, 0.0165, 0.0105)
            r += 0.0035 * f['brow_ridge'] * g2(u, w, sg * 0.031, 0.021, 0.02, 0.0065)
            r += 0.0042 * f['cheekbone'] * g2(u, w, sg * 0.047, -0.025, 0.015, 0.012)
        r += 0.0022 * g2(u, w, 0, 0.017, 0.009, 0.007)
        # mouth region
        lf = f['lip_full']
        wm = self.mouth_w(u)
        mw = f['mouth_width']
        r += 0.004 * g2(u, w, 0, wm + 0.001, 0.034 * mw, 0.016)  # muzzle
        r += 0.0042 * lf * g2(u, w, 0, wm + 0.0058, 0.019 * mw, 0.0042, 4)
        r -= 0.0011 * g2(u, w, 0, wm + 0.011, 0.0032, 0.004)
        r -= 0.0026 * g2(u, w, 0, wm, 0.0225 * mw, 0.0014, 4)
        r += 0.0044 * lf * g2(u, w, 0, wm - 0.006, 0.017 * mw, 0.0045, 4)
        r -= 0.0025 * g2(u, w, 0, wm - 0.0155, 0.015, 0.0042)
        r += 0.0046 * f['chin_projection'] * g2(u, w, 0, -0.098, 0.014, 0.011)
        return r

    def mouth_w(self, u):
        return -0.0646 * self.f['mouth_height'] + self.f['smile'] * 0.0032 * (u / 0.022) ** 2

    # ------------------------------------------------------------ build
    def build_skin(self, skin_tint=None):
        k = self.k
        c0 = self.chin_z
        zs = []
        z = 0.0
        while z < 0.2385:
            zs.append(z)
            dz = 0.0026 if 0.03 < z < 0.16 else 0.0045
            z += dz
        zs.append(0.2385)
        n = 128
        secs = []
        for zr in zs:
            rs, rf, rb, yc, e = self.section(zr)
            secs.append(sec((0, yc * k, c0 + zr * k), rs * k, rf * k, rb * k, e=e))
        part = loft(secs, n=n, cap_start=True)
        top = dome_cap(secs, end=True, steps=4, n=n, depth=0.0015 * k)
        part.extend(top)
        # relief + weights + tint
        for i, v in enumerate(part.v):
            a = 2 * math.pi * (i % n) / n if i < len(zs) * n else math.pi / 2
            front = smoothstep(0.30, 0.85, math.sin(a)) if i < len(zs) * n else 0.0
            u = v.x / k
            w = (v.z - self.eye_z) / k
            if front > 0:
                v.y -= self.relief(u, w) * k * front
            part.w[i] = self.weights(v)
            part.col[i] = self.tint(v, front)
        self.skin = part
        self.bvh = BVHTree.FromPolygons([tuple(v) for v in part.v], part.f, all_triangles=False)
        return part

    def weights(self, p):
        k = self.k
        u = p.x / k
        w = (p.z - self.eye_z) / k
        y = (p.y) / k
        wm = self.mouth_w(u)
        # jaw: below the mouth line, in front of the ear, above the neck
        j = smoothstep(wm + 0.0015, wm - 0.011, w)
        j *= 1 - smoothstep(0.050, 0.078, abs(u)) * 0.75
        j *= 1 - smoothstep(-0.005, 0.045, y)
        j *= 1 - smoothstep(-0.115, -0.14, w) * 0.5
        wt = {'head': 1 - j, 'jaw': j} if j > 1e-3 else {'head': 1.0}
        # mouth corners
        for sd, sg in (('L', 1), ('R', -1)):
            mc = self.mouth_corner(sd)
            d = (p - mc).length / k
            c = 0.55 * math.exp(-(d / 0.0085) ** 2)
            if c > 0.01:
                wt = {kk: vv * (1 - c) for kk, vv in wt.items()}
                wt['mouth_corner.' + sd] = c
        return wt

    def tint(self, p, front):
        k = self.k
        u = p.x / k
        w = (p.z - self.eye_z) / k
        f = self.f
        col = [1.0, 1.0, 1.0]
        wm = self.mouth_w(u)
        # lips
        lip = math.exp(-(abs(u) / (0.021 * f['mouth_width'])) ** 4) * math.exp(-((w - wm) / 0.0072) ** 2) * front
        col = [c * (1 - lip) + t * lip for c, t in zip(col, (0.80, 0.60, 0.58))]
        # stubble / beard shadow
        st = f['stubble']
        if st > 0:
            below_cheek = smoothstep(-0.028 - 0.1 * abs(u) * 0.0, -0.046, w - 0.12 * max(0.0, abs(u) - 0.03))
            m = below_cheek * smoothstep(-0.2, 0.2, (-(p.y / k) + 0.03) * 10) * (1 - lip)
            m *= 1 - smoothstep(-0.12, -0.145, w)  # stop under the jaw
            nose_gap = 1 - math.exp(-(abs(u) / 0.02) ** 2 - ((w + 0.045) / 0.008) ** 2)
            m *= nose_gap
            sideburn = smoothstep(0.066, 0.074, abs(u)) * smoothstep(-0.055, -0.01, w) * (1 - smoothstep(0.0, 0.02, w))
            m = max(m, sideburn * 0.8)
            m *= st
            col = [c * (1 - 0.5 * m) for c in col]
            col = [col[0] * (1 - 0.05 * m), col[1], col[2] * (1 + 0.03 * m)]
        # under-eye, nostrils, cheeks warmth
        for sg in (-1, 1):
            ue = math.exp(-((u - sg * 0.031) / 0.014) ** 2 - ((w + 0.012) / 0.006) ** 2) * front
            col = [c * (1 - 0.12 * ue) for c in col]
            ns = math.exp(-((u - sg * 0.0085) / 0.004) ** 2 - ((w + 0.047) / 0.0035) ** 2) * front
            col = [c * (1 - 0.55 * ns) for c in col]
            ch = math.exp(-((u - sg * 0.045) / 0.016) ** 2 - ((w + 0.03) / 0.015) ** 2) * front
            col = [col[0] * (1 + 0.04 * ch), col[1] * (1 - 0.02 * ch), col[2] * (1 - 0.02 * ch)]
        return (min(col[0], 1.0), min(col[1], 1.0), min(col[2], 1.0), 1.0)

    # ------------------------------------------------------------ queries
    def ray(self, origin, direction, dist=1.0):
        loc, nrm, idx, d = self.bvh.ray_cast(Vector(origin), Vector(direction).normalized(), dist)
        return loc, nrm

    def front_point(self, x, z):
        loc, nrm = self.ray((x, -0.5, z), (0, 1, 0))
        return loc, nrm

    def center(self):
        return Vector((0, 0.01 * self.k, self.chin_z + 0.13 * self.k))

    def dir_point(self, d):
        o = self.center()
        d = Vector(d).normalized()
        loc, nrm = self.ray(o + d * 0.6, -d, 1.0)
        return loc, nrm

    def eye_center(self, sd):
        k = self.k
        sg = 1 if sd == 'L' else -1
        x = sg * 0.0315 * k * self.f['eye_spacing']
        loc, _ = self.front_point(x, self.eye_z)
        r = self.eye_r()
        return Vector((x, loc.y + r - 0.0074 * k * self.f['eye_open'], self.eye_z))

    def eye_r(self):
        return 0.0133 * self.k * self.f['eye_size']

    def mouth_corner(self, sd):
        k = self.k
        sg = 1 if sd == 'L' else -1
        u = 0.0232 * self.f['mouth_width']
        z = self.eye_z + self.mouth_w(u) * k
        x = sg * u * k
        if self.bvh is None:
            return Vector((x, -0.07 * k, z))
        loc, _ = self.front_point(x, z)
        return loc

    def layout(self):
        k = self.k
        out = {}
        for sd in ('L', 'R'):
            out['eye.' + sd] = self.eye_center(sd)
            out['mouth_corner.' + sd] = self.mouth_corner(sd)
            sg = 1 if sd == 'L' else -1
            loc, _ = self.front_point(sg * 0.032 * k, self.eye_z + 0.021 * k)
            out['brow.' + sd] = loc
        out['jaw_pivot'] = Vector((0, 0.004 * k, self.eye_z - 0.030 * k))
        cl, _ = self.front_point(0, self.chin_z + 0.012 * k)
        out['chin'] = cl
        return out

    # ------------------------------------------------------------ parts
    def eyes(self, lay, mats):
        """eyeballs (mat 0 white, 1 iris, 2 pupil), lids (skin), lashes (3)."""
        k = self.k
        r = self.eye_r()
        eyes = Part()
        lids = Part()
        lashes = Part()
        for sd in ('L', 'R'):
            c = lay['eye.' + sd]
            fwd = Vector((0, -1, 0))
            ball = uv_sphere(c, (r, r, r), 24, 16, mat=0, w={'eye.' + sd: 1.0})
            eyes.extend(ball)
            # iris and pupil caps
            for rad, ang, m in ((r * 1.006, 0.64, 1), (r * 1.012, 0.26, 2)):
                cap = Part()
                rings = []
                for i in range(6):
                    th = ang * i / 5
                    ring = []
                    for j in range(20 if i else 1):
                        ph = 2 * math.pi * j / 20
                        d = Vector((math.sin(th) * math.cos(ph), -math.cos(th), math.sin(th) * math.sin(ph)))
                        ring.append(cap.vert(c + d * rad, {'eye.' + sd: 1.0}))
                    rings.append(ring)
                for i in range(5):
                    for j in range(20):
                        j2 = (j + 1) % 20
                        if i == 0:
                            cap.face((rings[0][0], rings[1][j2], rings[1][j]), m)
                        else:
                            cap.face((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]), m)
                eyes.extend(cap)
            # lids: shells rotated about the eye centre
            up_open = math.radians(self.f['lid_upper'])
            lo_open = math.radians(self.f['lid_lower'])
            for is_upper in (True, False):
                rr = r * (1.085 if is_upper else 1.07)
                lid = Part()
                rows = []
                NA, NT = 22, 10
                for i in range(NT + 1):
                    # polar angle from +Z (upper) or -Z (lower), 0..100deg
                    th = math.radians(92) * i / NT
                    row = []
                    for j in range(NA + 1):
                        ph = math.radians(-80 + 160 * j / NA)  # azimuth around vertical, 0 = forward
                        d = Vector((math.sin(th) * math.sin(ph), -math.sin(th) * math.cos(ph), math.cos(th)))
                        if not is_upper:
                            d.z = -d.z
                        # rotate about X so the edge sits at the open position
                        ang = -up_open if is_upper else lo_open
                        rot = Matrix.Rotation(ang, 3, 'X')
                        p = c + rot @ (d * rr)
                        wt = {'lid.' + sd: 1.0} if is_upper else {'head': 1.0}
                        row.append(lid.vert(p, wt, (0.93, 0.88, 0.86, 1)))
                    rows.append(row)
                for i in range(NT):
                    for j in range(NA):
                        q = (rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])
                        lid.face(q if is_upper else tuple(reversed(q)), 0)
                lids.extend(lid)
                if is_upper:
                    # lash line along the lid edge
                    pts = [lid.v[rows[-1][j]] for j in range(2, NA - 1)]
                    pts = [c + (p - c) * 1.012 for p in pts]
                    radii = [0.00045 * k + 0.0006 * k * math.sin(math.pi * j / (len(pts) - 1)) for j in range(len(pts))]
                    lashes.extend(tube_path(pts, radii, n=5, mat=0, w={'lid.' + sd: 1.0}))
        return eyes, lids, lashes

    def ears(self):
        k = self.k
        part = Part()
        for sd, sg in (('L', 1), ('R', -1)):
            ez = self.eye_z - 0.012 * k
            loc, nrm = self.ray((sg * 0.3, 0.012 * k, ez), (-sg, 0, 0))
            c = Vector((loc.x - sg * 0.001 * k, 0.014 * k, ez))
            ear = uv_sphere((0, 0, 0), (0.0075 * k, 0.0165 * k * self.f['ear_size'], 0.029 * k * self.f['ear_size']),
                            16, 12, w={'head': 1.0})
            for i, v in enumerate(ear.v):
                # bowl on the outer side, thick rim
                if v.x > 0:
                    dd = math.exp(-(v.y / (0.011 * k)) ** 2 - (v.z / (0.02 * k)) ** 2)
                    v.x -= 0.0085 * k * dd
                v.x += 0.004 * k  # push out from the head
            rot = Matrix.Rotation(math.radians(-22), 4, 'Y') @ Matrix.Rotation(math.radians(10), 4, 'X')
            if sg < 0:
                ear = ear.mirrored_x()
                rot = Matrix.Rotation(math.radians(22), 4, 'Y') @ Matrix.Rotation(math.radians(10), 4, 'X')
            ear.transform(Matrix.Translation(c) @ rot)
            for i in range(len(ear.col)):
                ear.col[i] = (0.94, 0.88, 0.86, 1)
            part.extend(ear)
        return part

    def mouth(self):
        """Mouth opening decal: closed = thin line; the jaw bone opens it."""
        k = self.k
        part = Part()
        NU, NT = 22, 8
        mw = 0.0232 * self.f['mouth_width']
        rows = []
        for i in range(NT + 1):
            t = 1 - 2 * i / NT  # 1 upper edge .. -1 lower edge
            row = []
            for j in range(NU + 1):
                u = -mw + 2 * mw * j / NU
                edge = 1 - (u / mw) ** 2
                w = self.mouth_w(u) + t * 0.0006 * edge
                x = u * k
                z = self.eye_z + w * k
                loc, nrm = self.front_point(x, z)
                p = loc + nrm * 0.0007 * k - Vector((0, 0.0002 * k, 0))
                jw = (1 - t) / 2
                wt = {'head': 1 - jw, 'jaw': jw}
                cc = 0.6 * smoothstep(0.55 * mw, mw, abs(u))
                sd = 'L' if u > 0 else 'R'
                if cc > 0:
                    wt = {kk: vv * (1 - cc) for kk, vv in wt.items()}
                    wt['mouth_corner.' + sd] = cc
                # colours: teeth band near the top, dark interior, lip-coloured rim
                if t > 0.55:
                    col = (0.86, 0.83, 0.78, 1) if edge > 0.25 else (0.16, 0.06, 0.06, 1)
                elif t < -0.6:
                    col = (0.42, 0.16, 0.15, 1)
                else:
                    col = (0.10, 0.03, 0.03, 1)
                if abs(t) > 0.99:
                    col = (0.35, 0.16, 0.14, 1)
                row.append(part.vert(p, wt, col))
            rows.append(row)
        for i in range(NT):
            for j in range(NU):
                part.face((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]), 0)
        return part

    def surface_strands(self, roots, mat=0, sides=5, col=None):
        """roots: list of (point, normal, dir, length, radius, weights)"""
        part = Part()
        for p0, nrm, d, L, r, wt in roots:
            pts, radii = [], []
            steps = 4
            dirv = Vector(d).normalized()
            p = Vector(p0) - nrm * r * 0.4
            for i in range(steps + 1):
                t = i / steps
                pts.append(p.copy())
                radii.append(r * (1 - 0.8 * t))
                # lie along the surface with a slight lift
                dirv = (dirv - nrm * dirv.dot(nrm) + nrm * 0.05).normalized()
                p = p + dirv * (L / steps)
            part.extend(tube_path(pts, radii, n=sides, mat=mat, w=wt, flat=0.45, up=tuple(nrm), col=col))
        return part

    def brows(self):
        k = self.k
        rng = random.Random(7)
        roots = []
        th = self.f['brow_thickness']
        for sd, sg in (('L', 1), ('R', -1)):
            for i in range(int(90 * th)):
                t = rng.random()
                u = 0.011 + 0.043 * t
                arch = 0.0055 * math.sin(math.pi * min(1, t * 1.25)) - 0.001 * t
                w = 0.0205 + arch + (rng.random() - 0.5) * 0.0055 * th * (1.1 - 0.5 * t)
                loc, nrm = self.front_point(sg * u * k, self.eye_z + w * k)
                if loc is None:
                    continue
                d = Vector((sg * 1.0, 0, 0.25 - 0.55 * t + (rng.random() - 0.5) * 0.3)).normalized()
                L = (0.006 + 0.003 * rng.random()) * k
                r = (0.0013 + 0.0006 * (1 - t)) * k
                roots.append((loc + nrm * 0.0008 * k, nrm, d, L, r, {'brow.' + sd: 0.75, 'head': 0.25}))
        return self.surface_strands(roots)

    def facial_hair(self, style='moustache_goatee', density=1.0, length=1.0):
        k = self.k
        rng = random.Random(11)
        roots = []
        if style in (None, 'none', 'clean'):
            return Part()
        f = self.f

        def add(u, w, d, L, r):
            loc, nrm = self.front_point(u * k, self.eye_z + w * k)
            if loc is None:
                return
            if nrm.y > 0.2:
                return
            roots.append((loc + nrm * 0.0006 * k, nrm, d, L * k * length, r * k, self.weights(loc)))

        # dense short clumps sampled over the beard mask on the skin surface
        nr = vertex_normals(self.skin)
        cand = [(i, self.beard_mask(v, style)) for i, v in enumerate(self.skin.v)]
        cand = [(i, m) for i, m in cand if m > 0.12]
        target = int((260 if style != 'moustache' else 160) * density)
        if cand:
            for n_ in range(target):
                i, m = cand[rng.randrange(len(cand))]
                if rng.random() > m:
                    continue
                v = self.skin.v[i]
                # jitter inside the neighbouring area
                nrm = nr[i]
                u = v.x / k
                wv = (v.z - self.eye_z) / k
                in_m = wv > self.mouth_w(u)
                sgn = 1 if u > 0 else -1
                if in_m:  # moustache: down and outwards
                    d = Vector((0.7 * sgn * min(1, abs(u) / 0.012), -0.15, -1.0))
                    L = 0.0055 + 0.0025 * rng.random()
                else:
                    d = Vector((0.25 * sgn * min(1, abs(u) / 0.02), -0.1, -1.0))
                    L = 0.0036 + 0.0016 * rng.random()
                p = v + (Vector((rng.random() - 0.5, rng.random() - 0.5, rng.random() - 0.5)) * 0.003 * k)
                roots.append((p + nrm * 0.0004 * k, nrm, d, L * k * length, (0.001 + 0.0004 * rng.random()) * k,
                              self.weights(v)))
        part = self.surface_strands(roots)
        part.extend(self.beard_shell(style))
        if style == 'full_long':
            # long hanging beard mass
            chin, _ = self.front_point(0, self.chin_z + 0.012 * k)
            L = 0.12 * k * length
            for i in range(60):
                u = (rng.random() * 2 - 1) * 0.035 * k
                p0 = chin + Vector((u, 0.02 * k * rng.random() + 0.01 * k, 0.012 * k * rng.random()))
                pts = []
                for s in range(6):
                    t = s / 5
                    pts.append(p0 + Vector((u * 0.2 * t, -0.012 * k * math.sin(t * 2), -L * t * (0.8 + 0.4 * rng.random()))))
                radii = [0.006 * k * (1 - 0.7 * s / 5) for s in range(6)]
                part.extend(tube_path(pts, radii, n=6, w={'jaw': 0.8, 'head': 0.2}, flat=0.7))
        return part

    def beard_mask(self, p, style):
        k = self.k
        f = self.f
        u = p.x / k
        w = (p.z - self.eye_z) / k
        y = p.y / k
        au = abs(u)
        wm = self.mouth_w(u)
        mw = f['mouth_width']
        m = 0.0
        if style in ('moustache_goatee', 'moustache', 'full_short', 'full_long', 'stubble_moustache'):
            band = smoothstep(wm + 0.0026, wm + 0.0045, w) * (1 - smoothstep(wm + 0.0115 - 0.1 * au, wm + 0.0135 - 0.1 * au, w))
            m = max(m, band * (1 - smoothstep(0.024 * mw, 0.028 * mw, au)))
        if style in ('moustache_goatee', 'full_short', 'full_long'):
            chin = (1 - smoothstep(wm - 0.0105, wm - 0.0085, w)) * (1 - smoothstep(0.019 + 0.004 * smoothstep(-0.09, -0.11, w), 0.025 + 0.004 * smoothstep(-0.09, -0.11, w), au))
            chin *= 1 - smoothstep(0.005, 0.03, y + 0.02)
            conn = (1 - smoothstep(wm + 0.004, wm + 0.006, w)) * smoothstep(wm - 0.02, wm - 0.012, w) \
                * smoothstep(0.017 * mw, 0.021 * mw, au) * (1 - smoothstep(0.027 * mw, 0.031 * mw, au))
            m = max(m, chin, conn)
        if style in ('full_short', 'full_long'):
            jaw = smoothstep(-0.03, -0.045, w - 0.1 * max(0.0, au - 0.03)) * (1 - smoothstep(0.01, 0.05, y))
            lipgap = math.exp(-(au / (0.02 * mw)) ** 4) * math.exp(-((w - wm) / 0.006) ** 2)
            m = max(m, jaw * (1 - lipgap))
        return m

    def beard_shell(self, style):
        if self.skin is None:
            return Part()
        k = self.k
        nr = vertex_normals(self.skin)
        thick = 0.0034 * k if style != 'full_long' else 0.005 * k
        return shell(self.skin, lambda i, v: self.beard_mask(v, style) - 0.3,
                     lambda i, v, m: thick * min(1.0, 0.25 + m), weights=lambda i, v: self.weights(v),
                     normals=nr)

    def glasses(self, gl):
        """Thin metal frames.  mat 0 frame, mat 1 lens."""
        k = self.k
        part = Part()
        if not gl or not gl.get('enabled', True):
            return part
        hw = gl.get('lens_half_width', 0.0235) * k
        hh = gl.get('lens_half_height', 0.0175) * k
        rim = gl.get('rim_radius', 0.0011) * k
        ex = gl.get('superellipse', 3.2)
        wt = {'head': 1.0}
        lay_l = self.eye_center('L')
        front_y = lay_l.y - self.eye_r() - gl.get('distance', 0.0125) * k
        cz = self.eye_z - 0.002 * k
        outers = {}
        for sd, sg in (('L', 1), ('R', -1)):
            cx = sg * (abs(lay_l.x) + 0.0015 * k)
            ring = []
            N = 36
            for j in range(N):
                a = 2 * math.pi * j / N
                ca, sa = math.cos(a), math.sin(a)
                x = hw * math.copysign(abs(ca) ** (2 / ex), ca)
                z = hh * math.copysign(abs(sa) ** (2 / ex), sa)
                # frames are slightly wider at the top, lens wraps a little
                if z > 0:
                    x *= 1.03
                y = front_y + 0.0025 * k * (abs(x) / hw) ** 2 * (1 if sg * x > 0 else 0.4)
                ring.append(Vector((cx + x, y, cz + z)))
            part.extend(tube_path(ring + ring[:2], [rim] * (N + 2), n=6, mat=0, w=wt, cap=False))
            # lens
            lens = Part()
            ci = lens.vert(Vector((cx, front_y - 0.0005 * k, cz)), wt)
            idx = [lens.vert(p + Vector((0, 0.0002 * k, 0)), wt) for p in ring]
            for j in range(N):
                lens.face((ci, idx[(j + 1) % N], idx[j]) if sg > 0 else (ci, idx[j], idx[(j + 1) % N]), 1)
            part.extend(lens)
            outers[sd] = Vector((cx + sg * hw * 1.02, front_y + 0.003 * k, cz + hh * 0.55))
            # nose pad
            part.extend(uv_sphere((cx - sg * hw * 0.95, front_y + 0.007 * k, cz - hh * 0.35),
                                  (0.0016 * k, 0.003 * k, 0.0042 * k), 8, 6, mat=1, w=wt))
        # bridge
        a = Vector((abs(lay_l.x) + 0.0015 * k - hw * 0.92, front_y, cz + hh * 0.45))
        pts = [Vector((a.x * (1 - 2 * t), front_y - 0.001 * k * math.sin(math.pi * t), cz + hh * 0.45 + 0.004 * k * math.sin(math.pi * t)))
               for t in [i / 8 for i in range(9)]]
        part.extend(tube_path(pts, [rim * 0.95] * len(pts), n=6, mat=0, w=wt))
        # temples: from the outer rim back to the ear
        for sd, sg in (('L', 1), ('R', -1)):
            o = outers[sd]
            loc, nrm = self.ray((sg * 0.4, o.y, o.z), (-sg, 0, 0))
            side_x = loc.x + sg * 0.0035 * k if loc else o.x
            ear_y = 0.020 * k
            pts = [o, Vector((side_x, o.y + 0.02 * k, o.z)), Vector((side_x, ear_y * 0.3, o.z - 0.002 * k)),
                   Vector((side_x - sg * 0.001 * k, ear_y + 0.012 * k, o.z - 0.006 * k)),
                   Vector((side_x - sg * 0.004 * k, ear_y + 0.026 * k, o.z - 0.022 * k))]
            part.extend(tube_path(pts, [rim * 1.1] * len(pts), n=6, mat=0, w=wt))
        return part


DEFAULT_FACE = {
    'head_width': 1.0, 'head_depth': 1.0, 'face_depth': 1.0, 'jaw_width': 0.97, 'chin_width': 1.0,
    'cheek_full': 0.4, 'cheekbone': 1.0, 'nose_length': 1.0, 'nose_width': 1.0, 'nose_projection': 1.0,
    'eye_spacing': 1.0, 'eye_size': 1.0, 'eye_open': 1.0, 'lid_upper': 14.0, 'lid_lower': 26.0,
    'brow_ridge': 1.0, 'brow_thickness': 1.0, 'lip_full': 1.0, 'mouth_width': 1.0, 'mouth_height': 1.0,
    'smile': 0.35, 'chin_projection': 1.0, 'ear_size': 1.0, 'stubble': 0.6,
}
