"""Blueprint Lab's look at a built model, in Blender: the left and right sides square on (orthographic, at a known
cm a pixel) and a three-quarter view, each labelled as a Blueprint Lab model view (not a game view). Writes, under
out: view_left.png, view_right.png, view_three_quarter.png and render.json.

    blender -b <name>.blend -P blueprint_render.py -- <job.json>
job: {"out": folder, "cm_per_px": 0.03, "label": "..."}"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
OUT = job["out"]
S = float(job.get("cm_per_px", 0.03))
sc = bpy.context.scene
obs = [o for o in sc.objects if o.type == 'MESH']
lo = Vector((min(min((o.matrix_world @ v.co)[i] for v in o.data.vertices) for o in obs) for i in range(3)))
hi = Vector((max(max((o.matrix_world @ v.co)[i] for v in o.data.vertices) for o in obs) for i in range(3)))
mid = (lo + hi) / 2.0
size = hi - lo
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_cavity = True
sc.display.shading.show_object_outline = True
sc.render.film_transparent = False
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.color = (1.0, 1.0, 1.0)
sc.display.shading.background_type = 'WORLD'
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
out = {"views": {}}


def shoot(name, loc, look, ortho=True, pad=1.15):
    cam.location = loc
    d = (look - loc).normalized()
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam_data.type = 'ORTHO'
        w_m = max(size.y, size.x) * pad if abs(d.x) > 0.5 else max(size.y, size.z) * pad
        h_m = size.z * pad
        sc.render.resolution_x = int(w_m * 100 / S)
        sc.render.resolution_y = int(h_m * 100 / S)
        cam_data.ortho_scale = max(w_m, h_m)
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = 50
        sc.render.resolution_x, sc.render.resolution_y = 1400, 900
    sc.render.filepath = os.path.join(OUT, "%s.png" % name)
    bpy.ops.render.render(write_still=True)
    out["views"][name] = {"file": sc.render.filepath, "px": [sc.render.resolution_x, sc.render.resolution_y], "ortho": ortho,
                          "cm_per_px": S if ortho else None}


far = max(size) * 4 + 1.0
# Blender's world: gun +X (left) is +X, the muzzle toward -Y, up +Z
shoot("view_left", mid + Vector((far, 0, 0)), mid)
shoot("view_right", mid + Vector((-far, 0, 0)), mid)
shoot("view_three_quarter", mid + Vector((far * 0.45, -far * 0.35, far * 0.25)) * 0.35 + mid * 0.65, mid, ortho=False)
with open(os.path.join(OUT, "render.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
print("BLUEPRINT RENDER " + json.dumps(list(out["views"])))
