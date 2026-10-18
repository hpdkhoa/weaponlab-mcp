"""A reference hold read from a pack's first-person clip (an animator-made hand on its own gun): each hand's wrist,
knuckles, thumb base and digit tips in the grip's frame (reference.py), each finger's three bends and the thumb's
two, at one frame of one clip. Writes a weaponlab-reference/1 file. The pack's numbers belong where its licence lets
them live (a Fab Standard licence: inside the game project, not a public repository).

    blender -b --factory-startup -P gunkit_pack_hold.py -- <job.json>
job: {"fbx", "clip": "<action name part>", "frame": <int or null: the clip's first>, "style", "out",
      "gun": {"magazine": [mesh names, the one nearest the frame wins], "slide": "<mesh>", "frame": "<mesh>"},
      "bones": {r|l: {"hand": name, "forearm": name (optional), "thumb"|"index"|"middle"|"ring"|"pinky": [4 names, base to tip]}},
      "keep": {r|l: [digits the style poses itself]}, "source": {...}}"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from weaponlab.gunkit import reference as REF  # noqa: E402

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=job["fbx"])
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
act = next(a for a in bpy.data.actions if job["clip"] in a.name)
arm.animation_data.action = act
frame = int(job.get("frame") if job.get("frame") is not None else act.frame_range[0])
bpy.context.scene.frame_set(frame)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()


def verts(name):
    ob = bpy.data.objects[name]
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    pts = np.array([list(ev.matrix_world @ v.co) for v in me.vertices])
    ev.to_mesh_clear()
    return pts


def axis(pts):
    c = pts.mean(0)
    _u, _s, vt = np.linalg.svd(pts - c)
    return c, vt[0]


G = job["gun"]
body = verts(G["frame"]).mean(0)
mags = sorted(G["magazine"], key=lambda n: float(np.linalg.norm(verts(n).mean(0) - body)))
mag = verts(mags[0])
slide = verts(G["slide"])
mc, up = axis(mag)
sc_, fwd = axis(slide)
if np.dot(up, sc_ - mc) < 0:
    up = -up                                          # up the magazine: toward the slide
proj = (slide - sc_) @ fwd
mag_on = float((mc - sc_) @ fwd)
if abs(proj.max() - mag_on) < abs(proj.min() - mag_on):
    fwd = -fwd                                        # forward: toward the slide's end far from the grip
lips = mag[int(np.argmax((mag - mc) @ up))]
left = np.cross(up, fwd)                              # Blender's world is right-handed: up x forward is the left
FR = REF.grip_frame(list(lips), list(up), list(fwd), list(left))
W = arm.matrix_world


def head(n):
    return list(W @ arm.pose.bones[n].head)


def grip(p):
    return [round(x * 100.0, 3) for x in REF.to_grip(p, FR)]      # metres in Blender, cm in the frame


def seg_deg(a, c):
    a, c = Vector(a).normalized(), Vector(c).normalized()
    return math.degrees(a.angle(c))


out = {"contract": REF.CONTRACT, "style": job.get("style"), "source": dict(job.get("source") or {}, clip=act.name, frame=frame),
       "frame": "grip: origin the magazine's lips, d up the magazine, f forward, l the gun's left; cm", "hands": {}}
for sd, B in job["bones"].items():
    f = {fi: [Vector(head(n)) for n in B[fi]] for fi in ("thumb", "index", "middle", "ring", "pinky")}
    wrist = Vector(head(B["hand"]))
    across = (f["index"][0] - f["pinky"][0]).normalized()
    sign = -1.0 if sd == "l" else 1.0
    w2k = f["middle"][0] - wrist
    curls = {}
    for fi in ("index", "middle", "ring", "pinky"):
        pts = [f[fi][0] - w2k, f[fi][0], f[fi][1], f[fi][2], f[fi][3]]
        c3 = []
        for i in range(3):
            a, c = (pts[i + 1] - pts[i]).normalized(), (pts[i + 2] - pts[i + 1]).normalized()
            c3.append(round(math.degrees(math.atan2(a.cross(c).dot(across) * sign, a.dot(c))), 1))
        curls[fi] = c3
    t = f["thumb"]
    elbow = Vector(head(B["forearm"])) if B.get("forearm") else None
    extra = {}
    if elbow is not None:
        # the forearm's line and the wrist's bend off it (the forearm to the wrist against the wrist to the middle
        # knuckle), as the animator posed them
        extra = {"elbow": grip(elbow), "wrist_bend_deg": round(math.degrees((wrist - elbow).angle(f["middle"][0] - wrist)), 1)}
    out["hands"][sd] = {
        "points": {"wrist": grip(wrist), "index_knuckle": grip(f["index"][0]), "knuckle": grip(f["middle"][0]),
                   "pinky_knuckle": grip(f["pinky"][0]), "thumb_cmc": grip(t[0]), "thumb_tip": grip(t[3]),
                   "index_tip": grip(f["index"][3]), "middle_tip": grip(f["middle"][3])},
        "curls": curls,
        "thumb": [round(seg_deg(t[1] - t[0], t[2] - t[1]), 1), round(seg_deg(t[2] - t[1], t[3] - t[2]), 1)],
        "keep": list((job.get("keep") or {}).get(sd, [])),
        "hand_cm": round((f["middle"][3] - wrist).length * 100.0, 2)}
    out["hands"][sd]["points"].update({k: v for k, v in extra.items() if k == "elbow"})
    if "wrist_bend_deg" in extra:
        out["hands"][sd]["wrist_bend_deg"] = extra["wrist_bend_deg"]
cam = next((o for o in bpy.data.objects if o.type == "CAMERA"), None)
if cam is not None:
    out["eye"] = grip(cam.matrix_world.translation)
out["gun"] = {"magazine": mags[0], "lips_world_cm": [round(x * 100, 2) for x in lips]}
bad = REF.check(out)
os.makedirs(os.path.dirname(job["out"]), exist_ok=True)
json.dump(out, open(job["out"], "w", encoding="utf-8"), indent=1)
print("GUNKIT " + json.dumps({"out": job["out"], "problems": bad}))
