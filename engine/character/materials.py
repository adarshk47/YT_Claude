"""Material helpers.  All materials are plain Principled BSDF set-ups so they
export cleanly to glTF (base colour, roughness, metallic, optional vertex
colour / alpha).  Colours in config files are sRGB hex strings."""
import bpy

_cache = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h, linear=True):
    if isinstance(h, (list, tuple)):
        rgb = tuple(h[:3])
        return rgb
    h = h.lstrip('#')
    rgb = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return tuple(srgb_to_linear(c) for c in rgb) if linear else rgb


def mix_hex(a, b, t):
    ca, cb = hex_rgb(a, False), hex_rgb(b, False)
    c = [x + (y - x) * t for x, y in zip(ca, cb)]
    return '#%02x%02x%02x' % tuple(int(max(0, min(1, x)) * 255) for x in c)


def _principled(nt):
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return nt.nodes.new('ShaderNodeBsdfPrincipled')


def material(name, color='#808080', rough=0.6, metal=0.0, alpha=1.0, vcol=None, emission=None,
             emission_strength=1.0, sheen=0.0, coat=0.0, spec=0.5, transmission=0.0, sss=0.0):
    key = (name, str(color), round(rough, 3), round(metal, 3), round(alpha, 3), vcol, str(emission))
    m = _cache.get(key)
    if m is not None and m.name in bpy.data.materials:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = _principled(nt)
    rgb = hex_rgb(color)
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    for nm in ('Specular IOR Level', 'Specular'):
        if nm in bsdf.inputs:
            bsdf.inputs[nm].default_value = spec
            break
    if sheen and 'Sheen Weight' in bsdf.inputs:
        bsdf.inputs['Sheen Weight'].default_value = sheen
    if coat and 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = coat
    if sss and 'Subsurface Weight' in bsdf.inputs:
        bsdf.inputs['Subsurface Weight'].default_value = sss
        if 'Subsurface Radius' in bsdf.inputs:
            bsdf.inputs['Subsurface Radius'].default_value = (0.9, 0.35, 0.2)
        if 'Subsurface Scale' in bsdf.inputs:
            bsdf.inputs['Subsurface Scale'].default_value = 0.004
    if transmission and 'Transmission Weight' in bsdf.inputs:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    if vcol:
        at = nt.nodes.new('ShaderNodeVertexColor')
        at.layer_name = vcol
        mul = nt.nodes.new('ShaderNodeMix') if hasattr(bpy.types, 'ShaderNodeMix') else None
        if mul is not None:
            mul.data_type = 'RGBA'
            mul.blend_type = 'MULTIPLY'
            mul.inputs['Factor'].default_value = 1.0
            mul.inputs[6].default_value = (*rgb, 1.0)
            nt.links.new(at.outputs['Color'], mul.inputs[7])
            nt.links.new(mul.outputs[2], bsdf.inputs['Base Color'])
        else:
            nt.links.new(at.outputs['Color'], bsdf.inputs['Base Color'])
    if emission:
        er = hex_rgb(emission)
        for nm in ('Emission Color', 'Emission'):
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = (*er, 1.0)
                break
        if 'Emission Strength' in bsdf.inputs:
            bsdf.inputs['Emission Strength'].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs['Alpha'].default_value = alpha
        for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED')):
            if hasattr(m, attr):
                try:
                    setattr(m, attr, val)
                except Exception:
                    pass
        if hasattr(m, 'use_backface_culling'):
            m.use_backface_culling = False
    m.diffuse_color = (*rgb, alpha)
    _cache[key] = m
    return m
