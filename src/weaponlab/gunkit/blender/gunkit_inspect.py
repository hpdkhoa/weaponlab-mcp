"""Gun Kit's look at a model before its parts map is written, in Blender: what the model holds as Blender shows it
after import. Writes inspect.json under out: every mesh object (its vertices, its bounds in Blender's world, its
materials, its vertex groups with their vertex counts and bounds), the whole model's bounds, the longest axis (most
likely the barrel), and a scale guess from the length (a long gun is 60 to 130 cm, a pistol 15 to 30). Nothing else.

    blender -b --factory-startup -P gunkit_inspect.py -- <job.json>
job: {"model": "<.blend, .fbx, .obj or .glb>", "out": folder}"""
import json
import os
import sys

import bpy
from mathutils import Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
path = job["model"]
ext = os.path.splitext(path)[1].lower()
bpy.ops.wm.read_factory_settings(use_empty=True)
if ext == ".blend":
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    for ob in dst.objects:
        if ob is not None:
            bpy.context.scene.collection.objects.link(ob)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=path)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=path)
elif ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=path)
else:
    raise SystemExit("GUNKIT INSPECT: cannot read %s" % path)
bpy.context.view_layer.update()


def bounds(pts):
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


objects, every = [], []
for ob in bpy.context.scene.objects:
    if ob.type != 'MESH':
        continue
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    if not pts:
        continue
    every += pts
    lo, hi = bounds(pts)
    groups = []
    for vg in ob.vertex_groups:
        gp = [ob.matrix_world @ v.co for v in ob.data.vertices if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
        if gp:
            glo, ghi = bounds(gp)
            groups.append({"name": vg.name, "vertices": len(gp), "min": list(glo), "max": list(ghi)})
    objects.append({"name": ob.name, "vertices": len(pts), "min": list(lo), "max": list(hi), "centre": list((lo + hi) / 2),
                    "materials": [m.name for m in ob.data.materials if m], "vertex_groups": groups,
                    "parent": ob.parent.name if ob.parent else None})
lo, hi = bounds(every)
size = hi - lo
axes = sorted((("X", size.x), ("Y", size.y), ("Z", size.z)), key=lambda a: -a[1])
longest = axes[0]
# units: the length in Blender units against a gun's length in cm
guess = "m" if longest[1] < 3.0 else "cm" if longest[1] < 300 else "mm"
report = {"model": path, "objects": objects, "min": list(lo), "max": list(hi), "size": list(size),
          "longest_axis": longest[0], "length_units": longest[1], "units_guess": guess,
          "armatures": [o.name for o in bpy.context.scene.objects if o.type == 'ARMATURE'],
          "hint": "forward is along the longest axis: look at which end the muzzle is (the thin end), then write forward "
                  "as +%s or -%s; up is usually +Z" % (longest[0], longest[0])}
os.makedirs(job["out"], exist_ok=True)
json.dump(report, open(os.path.join(job["out"], "inspect.json"), "w", encoding="utf-8"), indent=1)
print("GUNKIT INSPECT: %d meshes, longest %s %.3f, units %s" % (len(objects), longest[0], longest[1], guess))
