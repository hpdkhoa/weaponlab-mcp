"""A skin variant of a Gun Kit gun: the same rig, the grip's surface moved out (thicker, offset_cm > 0) or in
(thinner) along its normals, below a height in gun space. Job: {"gun_fbx", "out_fbx", "offset_cm", "below_z_cm",
"part_bone" (default Root)}. Writes out_fbx and prints GUNKIT."""
import json
import sys

import bpy
from mathutils import Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=job["gun_fbx"])
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
me = next(o for o in bpy.data.objects if o.type == "MESH")
names = {g.index: g.name for g in me.vertex_groups}
Ai = arm.matrix_world.inverted()
k_ = arm.matrix_world.to_scale()[0]
off = float(job["offset_cm"]) / 100.0
below = float(job["below_z_cm"]) / 100.0
bone = job.get("part_bone", "Root")
moved = 0
mesh = me.data
for v in mesh.vertices:
    gm = max(v.groups, key=lambda x: x.weight) if v.groups else None
    if (names.get(gm.group) if gm else "Root") != bone:
        continue
    p = (Ai @ (me.matrix_world @ v.co)) * k_          # the armature's own frame, metres
    if p.z > below:
        continue
    v.co = v.co + v.normal * (off / max(1e-9, me.matrix_world.to_scale()[0]))
    moved += 1
bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
me.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.fbx(filepath=job["out_fbx"], use_selection=True, object_types={"ARMATURE", "MESH"},
                         add_leaf_bones=False, bake_anim=False)
print("GUNKIT " + json.dumps({"moved": moved, "out": job["out_fbx"]}))
