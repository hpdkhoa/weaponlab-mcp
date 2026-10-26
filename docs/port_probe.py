"""Is the round visible at the port? The rig blend with its Round shown, the running part drawn back, a camera close
on the port from the right. blender -b <gun>_rig.blend -P port_probe.py -- <gunfacts.json> <out.png> <draw_cm>"""
import json
import math
import sys

import bpy
from mathutils import Vector

facts_p, out, draw = sys.argv[sys.argv.index("--") + 1:][:3]
facts = json.load(open(facts_p, encoding="utf-8"))
sc = bpy.context.scene
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
rnd = bpy.data.objects.get("Round")
if rnd is not None:
    rnd.hide_render = False
    rnd.hide_viewport = False
    rnd.hide_set(False)
# the running part drawn back along the bore (gun +y forward = Blender -y)
bone = (facts.get("round") or {}).get("bone", "Root")
pb = arm.pose.bones.get(bone)
if pb is not None and bone != "Root":
    pb.location = pb.location + (arm.matrix_world.inverted().to_3x3() @ Vector((0.0, float(draw) / 100.0, 0.0)))
bpy.context.view_layer.update()
port = Vector(facts["marks"]["port"])
pw = arm.matrix_world @ Vector((port[0] / 100.0, -port[1] / 100.0, port[2] / 100.0))
cam_d = bpy.data.cameras.new("C")
cam_d.lens = 50
cam = bpy.data.objects.new("C", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
look = pw
cam.location = look + Vector((-0.22, 0.05, 0.08))      # from the right (-x), a little back and up
cam.rotation_euler = (look - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'MATERIAL'
sc.render.resolution_x, sc.render.resolution_y = 800, 500
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("PORT_PROBE", out, "round", rnd is not None, "bone", bone, "verts", len(rnd.data.vertices) if rnd else 0,
      "round_at", [round(v * 100, 1) for v in (rnd.matrix_world @ rnd.data.vertices[0].co)] if rnd else None, "port", list(port))
