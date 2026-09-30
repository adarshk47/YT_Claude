"""Body landmarks.  Every mesh and bone position is derived from a small set of
parameters (height, head ratio, widths, girth) so the same generator makes
Adarsh, his age variants and the background people (children, adults)."""
from mathutils import Vector


class BodySpec:
    def __init__(self, height=1.78, head_ratio=0.141, shoulder=0.168, hip=0.092, girth=1.0,
                 female=False, child=False, posture=0.0, belly=0.0, arm_out=9.0):
        self.H = height
        self.head_h = height * head_ratio
        self.female = female
        self.child = child
        self.girth = girth
        self.posture = posture          # 0 upright .. 1 stooped (older)
        self.belly = belly
        B = height - self.head_h        # chin height
        self.B = B
        s = B / 1.54                    # scale relative to the adult reference
        self.s = s
        self.k = self.head_h / 0.24     # head scale
        z = {}
        z['crown'] = height
        z['chin'] = B
        z['eye'] = B + 0.49 * self.head_h
        z['head_c'] = B + 0.52 * self.head_h
        z['neck_top'] = B + 0.12 * self.head_h
        z['neck_base'] = B * 0.952
        z['shoulder'] = B * 0.918
        z['chest'] = B * 0.83
        z['ribs'] = B * 0.765
        z['waist'] = B * 0.695
        z['belly'] = B * 0.645
        z['hip'] = B * 0.605
        z['crotch'] = B * 0.558
        z['knee'] = B * 0.33
        z['ankle'] = B * 0.047
        self.z = z
        self.shoulder_x = shoulder * s * (0.9 if female else 1.0)
        self.hip_x = hip * s * (1.08 if female else 1.0)
        self.upper_arm = B * 0.19
        self.forearm = B * 0.165
        self.hand = B * 0.118
        self.arm_out = arm_out
        import math
        a = math.radians(arm_out)
        sh = Vector((self.shoulder_x, 0.0, z['shoulder']))
        self.p = p = {}
        p['shoulder.L'] = sh
        p['elbow.L'] = sh + Vector((math.sin(a), 0.03, -math.cos(a))).normalized() * self.upper_arm
        fdir = Vector((math.sin(a * 0.6), -0.16, -1.0)).normalized()
        p['wrist.L'] = p['elbow.L'] + fdir * self.forearm
        p['hip.L'] = Vector((self.hip_x, 0.0, z['hip']))
        p['knee.L'] = Vector((self.hip_x * 1.02, -0.012 * s, z['knee']))
        p['ankle.L'] = Vector((self.hip_x * 1.06, 0.02 * s, z['ankle']))
        foot_len = height * 0.15 * (0.95 if female else 1.0)
        self.foot_len = foot_len
        p['ball.L'] = Vector((self.hip_x * 1.12, 0.02 * s - foot_len * 0.62, 0.018 * s))
        p['toe.L'] = Vector((self.hip_x * 1.15, 0.02 * s - foot_len * 0.86, 0.014 * s))
        # head
        k = self.k
        self.head_c = Vector((0.0, 0.012 * k, z['head_c']))
        self.head_r = (0.079 * k, 0.098 * k, 0.114 * k)

    def mirror(self, name):
        v = self.p[name]
        return Vector((-v.x, v.y, v.z))

    def pt(self, name):
        if name.endswith('.R'):
            return self.mirror(name[:-2] + '.L')
        return self.p[name]


def spec_from(params):
    """Build a BodySpec from a dict (identity json / role / extra definitions)."""
    keys = ('height', 'head_ratio', 'shoulder', 'hip', 'girth', 'female', 'child', 'posture', 'belly', 'arm_out')
    kw = {k: params[k] for k in keys if k in params}
    return BodySpec(**kw)
