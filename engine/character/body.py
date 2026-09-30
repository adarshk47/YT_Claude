"""Body skin geometry (torso, neck, arms, hands, legs, feet) and the shared
torso profile used by garments so clothes follow the same shape and weights."""
import math
from mathutils import Vector
from ..meshkit import Part, sec, loft, dome_cap, smoothstep, mix_weights, uv_sphere
from .rig import hand_points, hand_frame, FINGERS

# fraction of chin height, side radius, front radius, back radius, exponent, y offset
TORSO_M = [
    (0.556, .148, .088, .106, 2.2, .006),
    (0.605, .164, .098, .116, 2.3, .008),
    (0.645, .156, .099, .104, 2.3, .004),
    (0.695, .144, .096, .094, 2.4, .002),
    (0.765, .150, .104, .096, 2.5, .000),
    (0.830, .163, .112, .098, 2.6, .000),
    (0.885, .178, .101, .094, 2.6, .002),
    (0.912, .190, .090, .088, 2.3, .004),
    (0.930, .168, .076, .078, 2.1, .006),
    (0.946, .120, .066, .068, 2.0, .008),
    (0.962, .072, .058, .060, 2.0, .012),
]
TORSO_F = [
    (0.556, .158, .090, .112, 2.2, .006),
    (0.605, .176, .100, .124, 2.3, .008),
    (0.645, .160, .096, .108, 2.3, .004),
    (0.695, .132, .090, .090, 2.4, .002),
    (0.765, .140, .104, .092, 2.5, .000),
    (0.830, .150, .124, .094, 2.6, .000),
    (0.885, .158, .104, .090, 2.6, .002),
    (0.912, .168, .086, .086, 2.3, .004),
    (0.930, .150, .072, .076, 2.1, .006),
    (0.946, .108, .062, .066, 2.0, .008),
    (0.962, .066, .054, .056, 2.0, .012),
]


def _catmull(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def torso_table(spec):
    tab = TORSO_F if spec.female else TORSO_M
    g = spec.girth
    s = spec.s
    rows = []
    for zf, rs, rf, rb, e, yo in tab:
        z = zf * spec.B
        gf = g
        rf2 = rf
        if spec.child:
            rs, rf, rb = rs * 0.97, rf * 0.97, rb * 0.97
        # belly / girth only widen the lower torso
        bel = spec.belly * math.exp(-((zf - 0.67) / 0.07) ** 2)
        rows.append((z, rs * s * gf, (rf2 * gf + bel * 0.06) * s, rb * s * gf, e, yo * s))
    return rows


def torso_at(spec, z, off=0.0, table=None):
    """Interpolated torso section at height ``z`` with outward offset ``off``."""
    rows = table or torso_table(spec)
    if z <= rows[0][0]:
        r = rows[0]
        vals = r[1:]
    elif z >= rows[-1][0]:
        vals = rows[-1][1:]
    else:
        for i in range(len(rows) - 1):
            if rows[i][0] <= z <= rows[i + 1][0]:
                break
        p0 = rows[max(i - 1, 0)]
        p1, p2 = rows[i], rows[i + 1]
        p3 = rows[min(i + 2, len(rows) - 1)]
        t = (z - p1[0]) / (p2[0] - p1[0])
        vals = tuple(_catmull(p0[j], p1[j], p2[j], p3[j], t) for j in range(1, 6))
    rs, rf, rb, e, yo = vals
    return dict(z=z, rs=rs + off, rf=rf + off, rb=rb + off, e=e, y=yo)


def torso_point(spec, z, a, off=0.0):
    """Point on the (offset) torso surface at height z and angle a (a=pi/2 front)."""
    t = torso_at(spec, z, off)
    ex = 2.0 / t['e']
    cs, sn = math.cos(a), math.sin(a)
    x = t['rs'] * math.copysign(abs(cs) ** ex, cs)
    r = t['rf'] if sn >= 0 else t['rb']
    y = r * math.copysign(abs(sn) ** ex, sn)
    return Vector((x, t['y'] - y, z))


def torso_weights(spec, p, leg_follow=0.55):
    """Skinning weights for any point on/around the torso (body or garment)."""
    z = spec.z
    x, zz = p.x, p.z
    side = 'L' if x >= 0 else 'R'
    ax = abs(x)
    w_h = 1 - smoothstep(z['belly'], z['ribs'] - 0.01, zz)
    w_c = smoothstep(z['ribs'], z['chest'] + 0.03, zz)
    w_s = max(0.0, 1 - w_h - w_c)
    w = {'hips': w_h, 'spine': w_s, 'chest': w_c}
    # neck
    wn = smoothstep(z['shoulder'] + 0.005, z['neck_base'] + 0.03, zz) * (1 - smoothstep(0.05, 0.11, ax))
    if wn > 0:
        w = {k: v * (1 - wn) for k, v in w.items()}
        w['neck'] = wn
    # shoulders / arms
    shx = spec.shoulder_x
    wa = smoothstep(0.55 * shx, 1.02 * shx, ax) * smoothstep(z['chest'] - 0.03, z['shoulder'] + 0.01, zz)
    wcl = smoothstep(0.25 * shx, 0.8 * shx, ax) * smoothstep(z['chest'], z['shoulder'], zz) * 0.45
    if wa > 0 or wcl > 0:
        tot = min(0.9, wa * 0.6 + wcl)
        w = {k: v * (1 - tot) for k, v in w.items()}
        w['upper_arm.' + side] = w.get('upper_arm.' + side, 0) + wa * 0.6
        w['clavicle.' + side] = w.get('clavicle.' + side, 0) + max(0.0, tot - wa * 0.6)
    # legs
    wl = smoothstep(z['hip'] + 0.02, z['crotch'] - 0.02 * spec.s, zz) * smoothstep(0.0, 0.08 * spec.s, ax) * leg_follow
    if wl > 0:
        w = {k: v * (1 - wl) for k, v in w.items()}
        w['thigh.' + side] = w.get('thigh.' + side, 0) + wl
    return {k: v for k, v in w.items() if v > 1e-4}


def torso_part(spec, z0, z1, off=0.0, n=40, mat=0, levels=None, flare=None, weight_fn=None, cap_bottom=False,
               col=None, arc=None, leg_follow=0.55, extra=None, arc_fn=None):
    """Loft the torso between heights z0 (bottom) and z1 (top).  ``flare(z)`` adds extra
    radius (for skirts/coats), ``extra(z)`` returns dict of radius deltas."""
    levels = levels or 16
    secs = []
    for i in range(levels + 1):
        zz = z0 + (z1 - z0) * i / levels
        t = torso_at(spec, min(max(zz, spec.z['crotch'] - 0.2), 10), off)
        rs, rf, rb = t['rs'], t['rf'], t['rb']
        e = t['e']
        yo = t['y']
        if zz < spec.z['crotch']:
            # below the crotch the "torso" becomes a skirt around both legs
            d = spec.z['crotch'] - zz
            rs = max(rs, spec.hip_x + 0.075 * spec.s + off + d * 0.08)
            rf = max(rf, 0.085 * spec.s + off + d * 0.05)
            rb = max(rb, 0.095 * spec.s + off + d * 0.05)
        if flare:
            fl = flare(zz)
            rs += fl
            rf += fl * 0.8
            rb += fl * 0.8
        if extra:
            ex = extra(zz) or {}
            rs += ex.get('rs', 0)
            rf += ex.get('rf', 0)
            rb += ex.get('rb', 0)
            yo += ex.get('y', 0)
        secs.append(sec((0, yo, zz), rs, rf, rb, e=e, arc=arc_fn(zz) if arc_fn else None))
    wf = weight_fn or (lambda p, w, i, a: torso_weights(spec, p, leg_follow))
    if arc_fn and arc is None:
        arc = arc_fn(z0)
    return loft(secs, n=n, mat=mat, weight_fn=wf, cap_start=cap_bottom, col=col, arc=arc)


# ------------------------------------------------------------------ limbs

ARM_R = [  # t along upper arm (0..1) then forearm (1..2): (t, rs, rf)
    (-0.12, .050, .050), (0.0, .052, .052), (0.18, .050, .049), (0.45, .044, .044), (0.8, .039, .040),
    (1.0, .036, .038), (1.18, .039, .040), (1.5, .034, .033), (1.85, .027, .022), (2.0, .023, .019)]
LEG_R = [
    (-0.10, .086, .086), (0.0, .088, .088), (0.25, .080, .080), (0.55, .069, .069), (0.85, .055, .055),
    (1.0, .050, .052), (1.12, .053, .054), (1.32, .057, .058), (1.65, .044, .044), (1.92, .034, .034),
    (2.0, .032, .032)]


def arm_path(spec, side, t):
    sh, el, wr = spec.pt('shoulder.' + side), spec.pt('elbow.' + side), spec.pt('wrist.' + side)
    if t <= 1:
        if t < 0:
            # continue inwards (towards the chest) rather than up, so the arm top stays under the shoulder slope
            return sh + Vector((0.35 * t * spec.upper_arm * (1 if side == 'L' else -1), 0, 0.05 * t * spec.upper_arm))
        return sh.lerp(el, t)
    return el.lerp(wr, t - 1)


def arm_weights(side, t):
    if t < 0.12:
        return mix_weights({'clavicle.' + side: 0.35, 'upper_arm.' + side: 0.65}, {'upper_arm.' + side: 1.0},
                           smoothstep(-0.12, 0.12, t))
    if t < 0.88:
        return {'upper_arm.' + side: 1.0}
    if t < 1.12:
        return mix_weights({'upper_arm.' + side: 1.0}, {'forearm.' + side: 1.0}, smoothstep(0.88, 1.12, t))
    if t < 1.9:
        return {'forearm.' + side: 1.0}
    return mix_weights({'forearm.' + side: 1.0}, {'forearm.' + side: 0.5, 'hand.' + side: 0.5}, smoothstep(1.9, 2.0, t))


def arm_part(spec, side, t0=-0.12, t1=2.0, off=0.0, mat=0, n=20, rscale=1.0, table=None, col=None,
             cap_end=False, extra=None):
    table = table or ARM_R
    s = spec.s * spec.girth ** 0.7
    secs = []
    ts = sorted(set([t0, t1] + [r[0] for r in table if t0 < r[0] < t1]))
    # subdivide for smoother bending
    dense = []
    for a, b in zip(ts[:-1], ts[1:]):
        steps = max(1, int(math.ceil((b - a) / 0.12)))
        dense += [a + (b - a) * i / steps for i in range(steps)]
    dense.append(t1)
    for t in dense:
        rs = _interp_table(table, t, 1) * s * rscale + off
        rf = _interp_table(table, t, 2) * s * rscale + off
        if extra:
            e = extra(t)
            rs += e
            rf += e
        w = arm_weights(side, t)
        secs.append(sec(arm_path(spec, side, t), rs, rf, w=w, e=2.1))
    return loft(secs, n=n, mat=mat, col=col, cap_end=cap_end)


def _interp_table(table, t, j):
    if t <= table[0][0]:
        return table[0][j]
    for a, b in zip(table[:-1], table[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / (b[0] - a[0])
            return a[j] + (b[j] - a[j]) * u
    return table[-1][j]


def leg_path(spec, side, t):
    hp, kn, an = spec.pt('hip.' + side), spec.pt('knee.' + side), spec.pt('ankle.' + side)
    if t <= 1:
        if t < 0:
            return hp + Vector((0, 0, -t * 0.5 * spec.s * 0.12))
        return hp.lerp(kn, t)
    return kn.lerp(an, t - 1)


def leg_weights(side, t):
    if t < 0.0:
        return {'thigh.' + side: 0.6, 'hips': 0.4}
    if t < 0.1:
        return mix_weights({'thigh.' + side: 0.6, 'hips': 0.4}, {'thigh.' + side: 1.0}, t / 0.1)
    if t < 0.9:
        return {'thigh.' + side: 1.0}
    if t < 1.1:
        return mix_weights({'thigh.' + side: 1.0}, {'shin.' + side: 1.0}, smoothstep(0.9, 1.1, t))
    if t < 1.93:
        return {'shin.' + side: 1.0}
    return mix_weights({'shin.' + side: 1.0}, {'shin.' + side: 0.5, 'foot.' + side: 0.5}, smoothstep(1.93, 2.0, t))


def leg_part(spec, side, t0=-0.10, t1=2.0, off=0.0, mat=0, n=22, rscale=1.0, table=None, col=None, flare=None,
             weight_mix=None):
    table = table or LEG_R
    s = spec.s * spec.girth ** 0.8
    ts = sorted(set([t0, t1] + [r[0] for r in table if t0 < r[0] < t1]))
    dense = []
    for a, b in zip(ts[:-1], ts[1:]):
        steps = max(1, int(math.ceil((b - a) / 0.1)))
        dense += [a + (b - a) * i / steps for i in range(steps)]
    dense.append(t1)
    secs = []
    for t in dense:
        rs = _interp_table(table, t, 1) * s * rscale + off
        rf = _interp_table(table, t, 2) * s * rscale + off
        if flare:
            f = flare(t)
            rs += f
            rf += f
        w = leg_weights(side, t)
        secs.append(sec(leg_path(spec, side, t), rs, rf, w=w, e=2.05))
    return loft(secs, n=n, mat=mat, col=col)


def foot_sections(spec, side, off=0.0, sole=0.0, toe_len=1.0, height=1.0, width=1.0):
    s = spec.s
    an = spec.pt('ankle.' + side)
    ball = spec.pt('ball.' + side)
    toe = spec.pt('toe.' + side)
    fl = spec.foot_len
    x0 = an.x
    heel_y = an.y + 0.045 * s
    rows = [  # y, z_center, rs(width), up, down
        (heel_y + 0.012 * s, 0.040 * s, 0.024, 0.020, 0.028),
        (heel_y, 0.045 * s, 0.031, 0.032, 0.040),
        (an.y, 0.050 * s, 0.035, 0.040, 0.046),
        (an.y - fl * 0.30, 0.042 * s, 0.040, 0.034, 0.036),
        (ball.y, 0.030 * s, 0.046, 0.024, 0.024),
        (ball.y - (toe.y - ball.y) * -0.5 * toe_len, 0.024 * s, 0.043, 0.018, 0.019),
        (toe.y - 0.02 * s * toe_len, 0.020 * s, 0.032, 0.013, 0.015),
    ]
    secs = []
    for i, (y, zc, rs, up, dn) in enumerate(rows):
        x = x0 + (ball.x - x0) * max(0, min(1, (an.y - y) / max(1e-4, (an.y - ball.y))))
        t = i / (len(rows) - 1)
        if i <= 2:
            w = {'foot.' + side: 0.85, 'shin.' + side: 0.15} if i == 2 else {'foot.' + side: 1.0}
        elif i == 3:
            w = {'foot.' + side: 1.0}
        elif i == 4:
            w = {'foot.' + side: 0.5, 'toe.' + side: 0.5}
        else:
            w = {'toe.' + side: 1.0}
        secs.append(sec((x, y, zc * height + (dn * s - (dn * s)) + sole * 0.5), rs * s * width + off,
                        up * s * height + off, dn * s + off + sole * 0.5, e=2.4, w=w, front=(0, 0, 1)))
    return secs


def foot_part(spec, side, mat=0, col=None):
    secs = foot_sections(spec, side)
    p = loft(secs, n=18, mat=mat, col=col, cap_start=True)
    p.extend(dome_cap(secs, end=True, steps=3, n=18, mat=mat, front=(0, 0, 1), depth=0.012 * spec.s, col=col))
    return p


# ------------------------------------------------------------------ hands

def finger_part(spec, side, f, mat=0, col=None, r_scale=1.0):
    hp = hand_points(spec, side)
    b1, m = hp[f + '1']
    _, tip = hp[f + '2']
    s = spec.s * r_scale * (0.9 if spec.female else 1.0)
    base_r = {'index': .0098, 'middle': .0102, 'ring': .0094, 'pinky': .0082, 'thumb': .0118}[f] * s
    wr, dn, ac, n = hand_frame(spec, side)
    d = (tip - b1).normalized()
    start = b1 - d * 0.012 * s
    secs = []
    pts = [(start, base_r * 1.05, {'hand.' + side: 1.0}),
           (b1, base_r, {'hand.' + side: 0.4, f + '1.' + side: 0.6}),
           (b1.lerp(m, 0.5), base_r * 0.93, {f + '1.' + side: 1.0}),
           (m, base_r * 0.86, {f + '1.' + side: 0.5, f + '2.' + side: 0.5}),
           (m.lerp(tip, 0.55), base_r * 0.8, {f + '2.' + side: 1.0}),
           (tip - d * 0.004 * s, base_r * 0.74, {f + '2.' + side: 1.0})]
    for p, r, w in pts:
        secs.append(sec(p, r, r * 0.86, w=w, e=2.0, front=tuple(-n)))
    part = loft(secs, n=12, mat=mat, col=col)
    part.extend(dome_cap(secs, end=True, steps=3, n=12, mat=mat, front=tuple(-n), depth=base_r * 0.8, col=col))
    return part


def hand_part(spec, side, mat=0, col=None):
    hp = hand_points(spec, side)
    wr, dn, ac, n = hand_frame(spec, side)
    s = spec.s * (0.9 if spec.female else 1.0)
    h = spec.hand
    rows = [(-0.02, .019, .024), (0.0, .018, .026), (0.18, .018, .036), (0.38, .016, .041), (0.52, .013, .040)]
    secs = []
    for t, th, wd in rows:
        c = wr + dn * h * t + ac * 0.002 * s
        w = {'hand.' + side: 1.0} if t > 0.05 else {'hand.' + side: 0.6, 'forearm.' + side: 0.4}
        secs.append(sec(c, th * s, wd * s, e=2.8, w=w, front=tuple(ac)))
    part = loft(secs, n=20, mat=mat, col=col, cap_start=False)
    part.extend(dome_cap(secs, end=True, steps=2, n=20, mat=mat, front=tuple(ac), depth=0.008 * s, col=col))
    # thenar (thumb base) pad
    tb, t1 = hp['thumb1']
    c = wr + dn * h * 0.22 + ac * 0.018 * s + n * 0.006 * s
    pad = uv_sphere(c, (0.017 * s, 0.017 * s, 0.028 * s), 12, 8, mat=mat, w={'hand.' + side: 0.7, 'thumb1.' + side: 0.3}, col=col)
    part.extend(pad)
    for f in FINGERS + ('thumb',):
        part.extend(finger_part(spec, side, f, mat, col))
    return part


def neck_part(spec, mat=0, col=None, off=0.0, top=None, bottom=None):
    z = spec.z
    k = spec.k
    s = spec.s
    z0 = bottom if bottom is not None else z['neck_base'] - 0.05 * s
    z1 = top if top is not None else z['neck_top'] + 0.035 * k
    secs = []
    N = 6
    for i in range(N + 1):
        t = i / N
        zz = z0 + (z1 - z0) * t
        y = 0.012 * s + (0.016 * k - 0.012 * s) * t
        r = (0.060 * s * (1 - t) + 0.054 * k * t) * (1.08 if t < 0.2 else 1.0) * spec.girth ** 0.5 + off
        if t < 0.25:
            w = mix_weights({'chest': 1.0}, {'neck': 1.0}, t / 0.25)
        elif t < 0.75:
            w = {'neck': 1.0}
        else:
            w = mix_weights({'neck': 1.0}, {'head': 1.0}, (t - 0.75) / 0.25)
        secs.append(sec((0, y + 0.004 * s, zz), r * 1.02, r * 0.95, r * 1.0, e=2.0, w=w))
    return loft(secs, n=24, mat=mat, col=col)


def body_part(spec, skin_col=None, include=('torso', 'arms', 'hands', 'legs', 'feet', 'neck')):
    p = Part()
    z = spec.z
    if 'torso' in include:
        p.extend(torso_part(spec, z['crotch'] - 0.01, z['neck_base'] + 0.01, 0.0, n=36, col=skin_col,
                            cap_bottom=True, levels=18))
    if 'neck' in include:
        p.extend(neck_part(spec, col=skin_col))
    for sd in ('L', 'R'):
        if 'arms' in include:
            p.extend(arm_part(spec, sd, col=skin_col))
        if 'hands' in include:
            p.extend(hand_part(spec, sd, col=skin_col))
        if 'legs' in include:
            p.extend(leg_part(spec, sd, col=skin_col))
        if 'feet' in include:
            p.extend(foot_part(spec, sd, col=skin_col))
    return p
