"""Blueprint Lab's showcase shots, in Blender: a rigged gun (Gun Kit's clips file) turned once round, then its own
clips played (slowed where they are fast). Every frame a PNG under out; the labels go on in Python.

    blender -b <name>_clips.blend -P blueprint_showcase.py -- <job.json>
job: {"out": folder, "size": [w, h], "fps": 15, "turn_frames": 60,
      "clips": [{"action": "A_<name>_fire", "slow": 6, "view": "right", "repeat": 2}, ...]}
views: right (the gun's right side, three quarters), left, top_right."""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
OUT = job["out"]
os.makedirs(OUT, exist_ok=True)
W, H = job.get("size", [960, 600])
FPS = job.get("fps", 15)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_specular_highlight = True
sh.show_object_outline = False
sh.background_type = 'WORLD'
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.color = (0.93, 0.93, 0.95)
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.film_transparent = False
sc.view_settings.view_transform = 'Standard'
arm = next(o for o in sc.objects if o.type == 'ARMATURE')
mesh = [o for o in sc.objects if o.type == 'MESH']
for m in mesh:
    m.hide_render = False
# the gun's bounds at rest
arm.animation_data_create()
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.location = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
pts = []
for m in mesh:
    e = m.evaluated_get(dg)
    pts += [e.matrix_world @ v.co for v in e.to_mesh().vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
mid = (lo + hi) / 2.0
R = (hi - lo).length
cam_data = bpy.data.cameras.new("ShowCam")
cam_data.lens = 70
cam = bpy.data.objects.new("ShowCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
DIST = R * 2.15


def aim(az_deg, el_deg, dist=DIST, look=None):
    """The camera round the gun: azimuth 0 looks at its left side (Blender +X), 180 its right; the muzzle is -Y."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    look = look or mid
    cam.location = look + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (look - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()


VIEWS = {"right": (205, 14), "left": (-25, 14), "top_right": (215, 38), "right_close": (195, 8)}
n = 0
report = {"shots": []}


def shot(name):
    global n
    sc.render.filepath = os.path.join(OUT, "f%05d.png" % n)
    bpy.ops.render.render(write_still=True)
    report["shots"].append({"frame": n, "shot": name})
    n += 1


# 1. once round
arm.animation_data.action = None
for k in range(job.get("turn_frames", 60)):
    aim(-25 + 360.0 * k / job.get("turn_frames", 60), 14)
    shot("turn")
# 2. the clips
for c in job.get("clips", []):
    act = bpy.data.actions.get(c["action"])
    if act is None:
        print("SHOWCASE: no action %s" % c["action"])
        continue
    arm.animation_data.action = act
    if hasattr(arm.animation_data, "action_slot") and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = act.frame_range
    src_fps = c.get("fps", 60)
    secs = (f1 - f0) / src_fps
    frames = max(2, int(round(secs * c.get("slow", 1) * FPS)))
    az, el = VIEWS.get(c.get("view", "right"), VIEWS["right"])
    aim(az, el, DIST * c.get("zoom", 1.0))
    for rep in range(c.get("repeat", 1)):
        for k in range(frames + 1):
            t = f0 + (f1 - f0) * k / frames
            sc.frame_set(int(t), subframe=t - int(t))
            shot(c.get("label", c["action"]))
        for _ in range(int(FPS * c.get("hold", 0.4))):          # a short hold at the end of each play
            shot(c.get("label", c["action"]))
with open(os.path.join(OUT, "shots.json"), "w", encoding="utf-8") as f:
    json.dump(report, f)
print("SHOWCASE FRAMES %d" % n)
