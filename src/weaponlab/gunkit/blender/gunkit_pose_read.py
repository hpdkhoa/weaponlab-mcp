"""Reads a hold a person posed in a Gun Kit reference scene: for each hand, its hand bone against the gun's body
bone (Root), and every finger joint's turn. Job: {"blend", "out"}. Writes out (JSON) and prints GUNKIT."""
import json
import sys

import bpy

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=job["blend"])
arms = next(o for o in bpy.data.objects if o.type == "ARMATURE" and "hand_r" in o.data.bones)
gun = next(o for o in bpy.data.objects if o.type == "ARMATURE" and "Root" in o.data.bones and o != arms)
bpy.context.view_layer.update()
root = gun.matrix_world @ gun.pose.bones["Root"].matrix @ gun.pose.bones["Root"].bone.matrix_local.inverted()
out = {"blend": job["blend"], "hands": {}}
for sd in ("r", "l"):
    hb = arms.pose.bones["hand_" + sd]
    Hw = arms.matrix_world @ hb.matrix
    rel = root.inverted() @ Hw
    fingers = {pb.name: list(pb.rotation_quaternion) for pb in arms.pose.bones
               if pb.name.endswith("_" + sd) and pb.name.split("_")[0] in ("thumb", "index", "middle", "ring", "pinky")
               and pb.name.split("_")[1] in ("01", "02", "03")}
    out["hands"][sd] = {"rel_to_root": [x for row in rel for x in row], "fingers": fingers}
json.dump(out, open(job["out"], "w", encoding="utf-8"), indent=1)
print("GUNKIT " + json.dumps({"out": job["out"]}))
