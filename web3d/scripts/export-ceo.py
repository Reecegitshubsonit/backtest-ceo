"""Export Blender Studio's CC0 realistic male as the first CEO review asset.

blender -b --factory-startup --python scripts/export-ceo.py -- bundle.blend output.glb
"""
import bpy
import math
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
source, output = args
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
names = ['GEO-body_male_realistic', 'GEO-body_male_realistic.eye.L', 'GEO-body_male_realistic.eye.R']
with bpy.data.libraries.load(source) as (data_from, data_to):
    data_to.objects = names
objects = [o for o in data_to.objects if o]
body = next(o for o in objects if o.name == "GEO-body_male_realistic")
origin = body.location.copy()
for obj in objects:
    bpy.context.collection.objects.link(obj)
    obj.hide_set(False)
bpy.context.view_layer.update()
world_matrices = {obj: obj.matrix_world.copy() for obj in objects}
for obj in objects:
    obj.parent = None
    obj.hide_set(False)
    obj.hide_viewport = False
    obj.hide_render = False
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    for mod in list(obj.modifiers):
        if mod.type == 'MULTIRES':
            mod.levels = 1
            mod.render_levels = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    # Bake the collection placement and eye rotations into each mesh.
    matrix = world_matrices[obj]
    for v in obj.data.vertices:
        v.co = matrix @ v.co - origin
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj.data.materials.clear()
    obj.select_set(False)

height = max(v.co.z for v in body.data.vertices) - min(v.co.z for v in body.data.vertices)
bottom = min(v.co.z for v in body.data.vertices)

def smoothstep(a, b, x):
    t = min(1, max(0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

for obj in objects:
    for v in obj.data.vertices:
        x, y, z = v.co / height
        z -= bottom / height
        # Relax the existing sculpted A-pose arms, blending at the shoulders.
        if obj == body:
            weight = smoothstep(0.085, 0.145, abs(x)) if z > 0.35 else 0
            if weight:
                sign = 1 if x > 0 else -1
                angle = math.radians(8) * sign * weight
                dx, dz = x - sign * 0.115, z - 0.82
                x = sign * 0.115 + dx * math.cos(angle) + dz * math.sin(angle)
                z = 0.82 - dx * math.sin(angle) + dz * math.cos(angle)
        # The picture projects a long torso and arms over dissolving legs.
        if z < 0.55:
            z = z * 0.34 / 0.55
        elif z < 0.78:
            z = 0.34 + (z - 0.55) * 0.39 / 0.23
        elif z < 0.89:
            z = 0.73 + (z - 0.78) * 0.12 / 0.11
        else:
            z = 0.85 + (z - 0.89) * 0.15 / 0.11
        head_width = 1 + 0.15 * smoothstep(0.81, 0.87, z)
        v.co = (x * 1.18 * head_width, y, z)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.name = 'CEO body' if obj == body else 'CEO eye'
    obj.select_set(True)

bpy.context.view_layer.objects.active = body
bpy.ops.export_scene.gltf(filepath=output, export_format='GLB', use_selection=True,
    export_materials='NONE', export_animations=False, export_yup=True)
print('CEO_ASSET', {'vertices': sum(len(o.data.vertices) for o in objects), 'source': source, 'output': output})
