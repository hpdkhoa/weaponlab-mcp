"""Gun Kit's read-back, in Blender: where each bone of a clip blend really is at given frames, in gun space (cm), so the
keyed clips can be checked against the timeline's own sums. Two points a bone: its head, and a point 3 cm along gun
+X, +Y and +Z from it (a turn moves those). Writes readback.json under out.

    blender -b --factory-startup -P gunkit_readback.py -- <job.json>
job: {"blend": "<name>_clips.blend", "clips": {"A_<name>_charge": [0.0, 0.7]}, "out": folder}"""
import json
import os
import sys

import bpy
from mathutils import Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=job["blend"])
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
sc = bpy.context.scene


def gun(v):
    return [round(v.x * 100.0, 3), round(-v.y * 100.0, 3), round(v.z * 100.0, 3)]


out = {}
for clip, times in job["clips"].items():
    act = bpy.data.actions.get(clip)
    if act is None:
        continue
    arm.animation_data.action = act
    out[clip] = {}
    for t in times:
        f = int(round(t * sc.render.fps))
        sc.frame_set(f)
        bpy.context.view_layer.update()
        frame = {}
        for pb in arm.pose.bones:
            m = arm.matrix_world @ pb.matrix
            rest = arm.matrix_world @ pb.bone.matrix_local
            pts = {}
            for k, d in (("head", Vector((0, 0, 0))), ("x", Vector((0.03, 0, 0))), ("y", Vector((0, -0.03, 0))), ("z", Vector((0, 0, 0.03)))):
                # a point fixed to the bone: its rest place in the world, carried by the bone's pose
                p_rest = rest.translation + d
                p = m @ (rest.inverted() @ p_rest)
                pts[k] = gun(p)
            frame[pb.name] = pts
        out[clip][str(t)] = frame
json.dump(out, open(os.path.join(job["out"], "readback.json"), "w", encoding="utf-8"), indent=1)
print("GUNKIT READBACK: %d clips" % len(out))
