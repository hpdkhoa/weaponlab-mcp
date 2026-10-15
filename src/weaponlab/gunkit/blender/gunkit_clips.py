"""Gun Kit's clip step, in Blender: the gun's own clips keyed from their bone tracks (rigplan.tracks) on a rig the rig
step made, and written as one FBX with every clip in it (the game imports each as a clip on the rig's skeleton).
Writes, under out: SK_<name>_Clips.fbx (the rig and its clips), <name>_clips.blend, clips.json. Nothing else.

    blender -b --factory-startup -P gunkit_clips.py -- <job.json>
job: {"blend": "<name>_rig.blend", "tracks": [{"clip", "fps", "seconds", "frames": [{"t", "bones": {name: {"loc", "rot"}}}]}],
      "prefix": "A_<name>_", "out": folder}

A track's loc is cm in gun space and rot [degrees, ax, ay, az] round an axis in gun space; Blender's world is gun
space in metres with Y flipped, a mirror: a loc's Y and a turn's axis Y change sign, and so does the turn's angle."""
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
OUT = job["out"]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=job["blend"])
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
NAME = arm.name
sc = bpy.context.scene
report = []
arm.animation_data_create()
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'
for tr in job["tracks"]:
    fps = int(tr["fps"])
    sc.render.fps = fps
    act = bpy.data.actions.new(job.get("prefix", "A_%s_" % NAME) + tr["clip"])
    act.use_fake_user = True
    arm.animation_data.action = act
    for fr in tr["frames"]:
        f = int(round(fr["t"] * fps))
        for bone, x in fr["bones"].items():
            pb = arm.pose.bones.get(bone)
            if pb is None:
                continue
            lx, ly, lz = x["loc"]
            pb.location = Vector((lx, -ly, lz)) / 100.0
            deg, ax, ay, az = x["rot"]
            axis = Vector((ax, -ay, az))
            pb.rotation_quaternion = Quaternion(axis.normalized() if axis.length > 0 else Vector((0, 1, 0)), -math.radians(deg))
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_quaternion", frame=f)
    report.append({"clip": act.name, "frames": len(tr["frames"]), "seconds": tr["seconds"], "fps": fps})
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.location = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
for o in sc.objects:
    o.select_set(False)
arm.select_set(True)
mesh.select_set(True)
fbx = os.path.join(OUT, "SK_%s_Clips.fbx" % NAME)
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False,
                         bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
                         bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
                         mesh_smooth_type='FACE', colors_type='LINEAR')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "%s_clips.blend" % NAME))
json.dump({"fbx": fbx, "clips": report}, open(os.path.join(OUT, "clips.json"), "w", encoding="utf-8"), indent=1)
print("GUNKIT CLIPS: %s, %d clips, %s" % (NAME, len(report), fbx))
