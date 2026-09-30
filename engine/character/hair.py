"""Clump-based hair generator.

A style is a small dictionary (see config/hairstyles.json) that controls
lengths per scalp region, lift (volume), flow direction, waves and extras such
as a choti, bun, ponytail or braids.  Strands are grown over the scalp, pushed
outside the head and converted into tapered, slightly flattened tubes."""
import math
import random
from mathutils import Vector
from ..meshkit import Part, tube_path, uv_sphere, smoothstep, torus_path, chaikin


def _interp(pts, x):
    if x <= pts[0][0]:
        return pts[0][1]
    for (a, va), (b, vb) in zip(pts[:-1], pts[1:]):
        if a <= x <= b:
            t = (x - a) / (b - a)
            return va + (vb - va) * t
    return pts[-1][1]


class HairBuilder:
    def __init__(self, head, style, color_mode=None, seed=3):
        self.h = head
        self.k = head.k
        self.st = style
        self.rng = random.Random(seed + sum(ord(c) for c in style.get('name', '')))
        k = self.k
        self.o = Vector((0, 0.012 * k, head.chin_z + 0.12 * k))
        self.r = Vector((0.080 * k * head.f['head_width'], 0.097 * k, 0.118 * k))
        self.grey = color_mode or 0.0

    # --------------------------------------------------------- scalp
    def hairline(self, az):
        """minimum (z - eye_z)/k for hair at azimuth (deg, 0=front)"""
        st = self.st
        a = abs(az)
        rec = st.get('temple_recess', 0.0)
        raise_ = st.get('hairline_raise', 0.0)
        sb = st.get('sideburn', 0.03)
        pts = [(0, 0.070 + raise_), (22, 0.068 + raise_ + rec * 0.4), (38, 0.062 + rec + raise_ * 0.7),
               (55, 0.040 + rec * 0.5), (70, 0.018), (78, -sb), (88, -sb), (96, 0.030), (112, 0.030),
               (125, 0.0), (145, -0.05), (165, -0.072), (180, -0.076)]
        return _interp(pts, a)

    def in_scalp(self, p, margin=0.0):
        d = p - self.o
        az = math.degrees(math.atan2(d.x, -d.y))
        w = (p.z - self.h.eye_z) / self.k
        return w > self.hairline(az) + margin, az, w

    def ell_normal(self, p):
        loc, nrm, idx, dist = self.h.bvh.find_nearest(p)
        if loc is None:
            q = p - self.o
            return Vector((q.x / self.r.x ** 2, q.y / self.r.y ** 2, q.z / self.r.z ** 2)).normalized()
        d = p - loc
        if d.length > 1e-5 and d.normalized().dot(nrm) > 0.3:
            return (d.normalized() * 0.5 + nrm * 0.5).normalized()
        return nrm

    def push_out(self, p, off):
        loc, nrm, idx, dist = self.h.bvh.find_nearest(p)
        if loc is None:
            return p
        s = (p - loc).dot(nrm)
        if s < off:
            return p + nrm * (off - s)
        return p

    def roots(self, count):
        pts = []
        N = 6000
        ga = math.pi * (3 - math.sqrt(5))
        cands = []
        for i in range(N):
            z = 1 - 2 * (i + 0.5) / N
            rr = math.sqrt(1 - z * z)
            th = ga * i
            d = Vector((rr * math.cos(th), rr * math.sin(th), z))
            if d.z < -0.55:
                continue
            loc, nrm = self.h.dir_point(d)
            if loc is None:
                continue
            ok, az, w = self.in_scalp(loc, 0.0)
            if ok:
                cands.append((loc, nrm, az, w))
        self.rng.shuffle(cands)
        chosen = cands[:count]
        # dedicated roots along the hairline so the edge is not jagged
        k = self.k
        for i in range(int(self.st.get('hairline_roots', 110))):
            az = -150 + 300 * (i + self.rng.random() * 0.5) / self.st.get('hairline_roots', 110)
            wz = self.hairline(az) + 0.004 + 0.004 * self.rng.random()
            a = math.radians(az)
            z = self.h.eye_z + wz * k
            dh = Vector((math.sin(a), -math.cos(a), 0))
            loc, nrm = self.h.ray(Vector((0, 0.012 * k, z)) + dh * 0.4, -dh, 1.0)
            if loc is not None:
                chosen.append((loc, nrm, az, wz))
        return chosen, cands

    # --------------------------------------------------------- cap
    def cap(self, skin, off=0.0025):
        k = self.k
        part = Part()
        keep = []
        vol = self.st.get('volume', 0.01)
        for i, v in enumerate(skin.v):
            ok, az, w = self.in_scalp(v, 0.004)
            keep.append(ok)
        remap = {}
        for fi, f in enumerate(skin.f):
            if all(keep[i] for i in f):
                idx = []
                for i in f:
                    if i not in remap:
                        v = skin.v[i]
                        n = self.ell_normal(v)
                        ok, az, w = self.in_scalp(v)
                        # thicker on top
                        top = smoothstep(0.2, 0.9, n.z)
                        edge = smoothstep(0.0, 0.012, w - self.hairline(az))
                        o = (off + vol * 0.25 * top * edge) * k
                        remap[i] = part.vert(v + n * o, {'head': 1.0}, self._col(0.8))
                    idx.append(remap[i])
                part.face(idx, 0)
        return part

    def _col(self, shade):
        g = self.grey
        if g > 0 and self.rng.random() < g:
            return (1.0, 1.0, 1.0, 1)  # grey strand (base colour is grey for older)
        if g > 0:
            s = 0.16 + 0.05 * self.rng.random()
            return (s, s, s, 1)
        s = min(1.0, shade)
        return (s, s * 0.98, s * 0.97, 1)

    # --------------------------------------------------------- strands
    def region_len(self, n, az):
        L = self.st.get('length', {})
        top = smoothstep(0.30, 0.80, n.z)
        c = math.cos(math.radians(az))
        front = smoothstep(0.35, 0.95, c)
        back = smoothstep(0.2, 0.9, -c)
        side = 1 - max(front, back)
        low = (L.get('front', 0.08) * front + L.get('side', 0.05) * side + L.get('back', 0.06) * back)
        return L.get('top', 0.09) * top + low * (1 - top), top, front, back, side

    def flow_dir(self, p, n, az, root_x, info):
        st = self.st
        flow = st.get('flow', 'back')
        top, front, back, side = info
        sweep = st.get('sweep', 0.0)
        if flow == 'back':
            up = max(top, front)
            ft = Vector((sweep, 1.0, 0.25))
            fs = Vector((sweep * 0.3, 0.55, -1.0))
            f = ft * up + fs * (1 - up)
        elif flow == 'side_part':
            px = st.get('part_x', 0.028) * self.k
            sgn = 1 if root_x > px else -1
            ft = Vector((sgn * 1.0, 0.35 if sgn > 0 else 0.15, -0.15))
            if sgn < 0:
                ft = Vector((-0.8, 0.25 - 0.4 * front, -0.2))
            fs = Vector((0, 0.35, -1.0))
            f = ft * top + fs * (1 - top)
        elif flow == 'forward':
            ft = Vector((sweep, -1.0, -0.35))
            fs = Vector((0, 0.1, -1.0))
            f = ft * top * (1 - back * 0.7) + fs * (1 - top) + Vector((0, 0.3, -1)) * back * top * 0.7
        elif flow == 'messy':
            j = Vector((self.rng.uniform(-1, 1), self.rng.uniform(-0.8, 1), self.rng.uniform(-0.3, 0.6)))
            f = Vector((sweep, -0.4 + 0.8 * back, 0.3)) * top + Vector((0, 0.3, -1)) * (1 - top) + j * 0.8
        elif flow in ('to_point', 'bun', 'ponytail', 'braids'):
            anchors = self.anchors()
            a = min(anchors, key=lambda q: (q - p).length)
            f = a - p
        else:
            f = Vector((0, 0.3, -1.0))
        return f.normalized()

    def anchors(self):
        k = self.k
        st = self.st
        ex = st.get('extra', '')
        if ex == 'bun':
            return [self.o + Vector((0, 0.045 * k, 0.118 * k))]
        if ex == 'low_bun':
            return [self.o + Vector((0, 0.10 * k, -0.02 * k))]
        if ex == 'ponytail':
            return [self.o + Vector((0, 0.100 * k, 0.02 * k))]
        if ex == 'braids':
            return [self.o + Vector((0.055 * k, 0.07 * k, -0.045 * k)), self.o + Vector((-0.055 * k, 0.07 * k, -0.045 * k))]
        return [self.o + Vector((0, 0.1 * k, -0.05 * k))]

    def tangent(self, v, n):
        return (v - n * v.dot(n))

    def grow(self, root, nrm, az, w):
        st = self.st
        k = self.k
        L, top, front, back, side = self.region_len(nrm, az)
        L *= (0.85 + 0.3 * self.rng.random()) * k
        if L < 0.002 * k:
            return None
        info = (top, front, back, side)
        lift = st.get('lift', {})
        lf = lift.get('top', 0.3) * top + lift.get('front', 0.5) * front * top + lift.get('side', 0.05) * (1 - top)
        lf = min(0.9, lf)
        vol = st.get('volume', 0.01) * k
        vol_here = vol * (0.25 + 0.75 * top) * (1 + 0.6 * front * top * st.get('quiff', 0.0))
        steps = 9 if L > 0.03 * k else 5
        seg = L / steps
        p = root - nrm * 0.0015 * k
        f = self.flow_dir(p, nrm, az, root.x, info)
        d = (nrm * lf + self.tangent(f, nrm).normalized() * (1 - lf)).normalized()
        pts = [p.copy()]
        grav = st.get('gravity', 0.35)
        anchors_mode = st.get('flow') in ('to_point', 'bun', 'ponytail', 'braids')
        bend = st.get('bend', 0.38)
        for i in range(1, steps + 1):
            t = i / steps
            n = self.ell_normal(p)
            f = self.flow_dir(p, n, az, root.x, info)
            want = self.tangent(f, n)
            if want.length < 1e-6:
                want = f
            want = want.normalized()
            if not anchors_mode:
                want.z -= grav * t * (1 - 0.5 * top)
                want = want.normalized()
            d = (d * (1 - bend) + want * bend).normalized()
            p = p + d * seg
            if anchors_mode:
                layer = 0.0025 * k
            else:
                layer = 0.002 * k + vol_here * (1 - 0.35 * t)
            p = self.push_out(p, layer)
            pts.append(p.copy())
            if anchors_mode:
                a = min(self.anchors(), key=lambda q: (q - p).length)
                if (a - p).length < 0.012 * k:
                    break
        # waves
        amp = st.get('wave', 0.0) * k
        if amp > 0 and len(pts) > 3:
            ph = self.rng.random() * 6.28
            fr = st.get('wave_freq', 1.6)
            out = [pts[0]]
            for i in range(1, len(pts)):
                t = i / (len(pts) - 1)
                dd = (pts[i] - pts[i - 1]).normalized()
                n = self.ell_normal(pts[i])
                sv = dd.cross(n).normalized()
                off = sv * amp * math.sin(ph + t * fr * 6.28) * t
                out.append(pts[i] + off)
            pts = out
        return chaikin(pts, 1)

    def build(self):
        st = self.st
        k = self.k
        density = st.get('density', 380)
        roots, allc = self.roots(density)
        part = Part()
        cr = st.get('clump_r', 0.009) * k
        for (loc, nrm, az, w) in roots:
            pts = self.grow(loc, nrm, az, w)
            if not pts or len(pts) < 2:
                continue
            L = sum(((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)))
            r0 = cr * (0.8 + 0.4 * self.rng.random()) * min(1.0, 0.5 + L / (0.04 * k))
            m = len(pts) - 1
            radii = [r0 * (1 - 0.72 * (i / m) ** 1.5) for i in range(len(pts))]
            nrm0 = self.ell_normal(pts[len(pts) // 2])
            col = self._col(0.75 + 0.35 * self.rng.random())
            part.extend(tube_path(pts, radii, n=st.get('sides', 5), mat=0, w={'head': 1.0}, flat=st.get('flat', 0.38),
                                  up=tuple(nrm0), col=col))
        part.extend(self.extras())
        return part

    # --------------------------------------------------------- extras
    def extras(self):
        st = self.st
        k = self.k
        ex = st.get('extra', '')
        part = Part()
        w = {'head': 1.0}
        if ex == 'choti':
            base_loc, bn = self.h.dir_point(Vector((0, 0.62, 0.78)))
            knot = base_loc + bn * 0.006 * k
            part.extend(uv_sphere(knot, (0.011 * k, 0.012 * k, 0.010 * k), 12, 8, w=w, col=self._col(0.8)))
            pts = [knot]
            p = knot.copy()
            for i in range(1, 9):
                t = i / 8
                p = p + Vector((0.002 * k * math.sin(t * 5), 0.012 * k * (1 - t), -0.016 * k))
                p = self.push_out(p, 0.004 * k + 0.004 * k * t)
                pts.append(p.copy())
            radii = [0.0075 * k * (1 - 0.6 * i / 8) for i in range(len(pts))]
            part.extend(tube_path(pts, radii, n=7, w=w, flat=0.8, col=self._col(0.85)))
            part.extend(uv_sphere(pts[-1] + Vector((0, 0, -0.004 * k)), (0.004 * k,) * 3, 8, 6, w=w, col=self._col(0.8)))
        elif ex in ('bun', 'low_bun'):
            a = self.anchors()[0]
            n = (a - self.o).normalized()
            part.extend(uv_sphere(a + n * 0.012 * k, (0.036 * k, 0.034 * k, 0.03 * k), 16, 12, w=w, col=self._col(0.75)))
            for i in range(9):
                ang0 = self.rng.random() * 6.28
                rr = (0.022 + 0.013 * self.rng.random()) * k
                h = (self.rng.random() - 0.5) * 0.03 * k
                pts = []
                for j in range(14):
                    ang = ang0 + j * 0.42
                    pts.append(a + n * (0.012 * k + h) + Vector((math.cos(ang) * rr, math.sin(ang) * rr * 0.95, 0)) * 1.0
                               + n * 0.006 * k * math.sin(j * 0.5))
                part.extend(tube_path(pts, [0.009 * k] * 14, n=6, w=w, flat=0.6, col=self._col(0.9)))
        elif ex == 'ponytail':
            a = self.anchors()[0]
            part.extend(torus_path([a + Vector((math.cos(t) * 0.012 * k, 0.004 * k, math.sin(t) * 0.012 * k))
                                    for t in [i * 0.52 for i in range(12)]], 0.0035 * k, w=w, mat=1))
            for i in range(14):
                off = Vector(((self.rng.random() - 0.5) * 0.02 * k, (self.rng.random()) * 0.01 * k, (self.rng.random() - 0.5) * 0.02 * k))
                pts = []
                p = a + off
                L = (0.20 + 0.06 * self.rng.random()) * k
                for j in range(8):
                    t = j / 7
                    pts.append(p + Vector((0.01 * k * math.sin(t * 3 + i), 0.035 * k * math.sin(t * 1.6), -L * t)))
                part.extend(tube_path(pts, [0.009 * k * (1 - 0.7 * t) for t in [j / 7 for j in range(8)]], n=6, w=w,
                                      col=self._col(0.8 + 0.3 * self.rng.random())))
        elif ex == 'braids':
            for a in self.anchors():
                sg = 1 if a.x > 0 else -1
                p = a + Vector((0.004 * k * sg, 0.006 * k, 0))
                segs = 11
                for j in range(segs):
                    t = j / segs
                    c = p + Vector((sg * 0.004 * k * t, 0.012 * k * t, -0.024 * k * j))
                    rr = 0.0105 * k * (1 - 0.35 * t)
                    tilt = 0.006 * k * (1 if j % 2 else -1)
                    part.extend(uv_sphere(c + Vector((tilt, 0, 0)), (rr, rr * 0.85, 0.016 * k), 10, 8, w=w,
                                          col=self._col(0.85)))
                end = p + Vector((sg * 0.004 * k, 0.012 * k, -0.024 * k * segs))
                # ribbon bow
                for bs in (-1, 1):
                    part.extend(uv_sphere(end + Vector((bs * 0.013 * k, 0.004 * k, 0.004 * k)),
                                          (0.012 * k, 0.005 * k, 0.008 * k), 10, 6, mat=1, w=w))
                part.extend(uv_sphere(end + Vector((0, 0.004 * k, 0.004 * k)), (0.005 * k,) * 3, 8, 6, mat=1, w=w))
        elif ex == 'long_back':
            for i in range(40):
                a = (i / 39 - 0.5) * 2.2
                start = self.o + Vector((math.sin(a) * 0.075 * k, math.cos(a) * 0.09 * k, -0.02 * k))
                pts = []
                L = (0.22 + 0.06 * self.rng.random()) * k
                for j in range(8):
                    t = j / 7
                    pp = start + Vector((0, 0.02 * k * t, -L * t))
                    pts.append(pp)
                part.extend(tube_path(pts, [0.011 * k * (1 - 0.6 * t) for t in [j / 7 for j in range(8)]], n=6, w=w,
                                      flat=0.6, col=self._col(0.85)))
        return part
