"""Blueprint Lab's showcase shots, in Blender: a rigged gun (Gun Kit's clips file) turned once round, then its own
clips played (slowed where they are fast). Every frame a PNG under out; the labels go on in Python.

    blender -b <name>_clips.blend -P blueprint_showcase.py -- <job.json>
job: {"out": folder, "size": [w, h], "fps": 15, "turn_frames": 60,
      "clips": [{"action": "A_<name>_fire", "slow": 6, "view": "right", "repeat": 2, "loaded": "always",
                 "free": {"Magazine": [[x, y, z] cm a frame]}, "free_fps": 60}, ...],
      "round": {"profile": [[y, r] cm], "case_y_cm": [0, 2.28]} | null, "slide_bone": "Slide"}
a clip's "look" (Blender metres) is the point its camera looks at, for a long gun's action seen close.
views: right (the gun's right side, three quarters), left, top_right, port (behind and above the right side, close on
the breech: the gap the slide opens). A clip's free tracks replace its free bones' keys (a gun-only view: the part the
arms would carry plays along their way); loaded shows the round in the chamber: always, when_home (the slide home),
after_home (once the slide has come home)."""
import json
import math
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

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
    look = mid if look is None else look
    cam.location = look + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (look - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()


VIEWS = {"right": (205, 14), "left": (-25, 14), "top_right": (215, 38), "right_close": (195, 8), "port": (150, 32)}
LOOK = {"port": Vector((0.0, 0.004, 0.004))}         # the breech face on the bore axis (gun origin), a little up and back


def turned(name, profile, color):
    """A profile (y, r) in gun cm turned round the bore axis, in Blender's frame (metres, y flipped)."""
    me = bpy.data.meshes.new(name)
    seg = 48
    vs, fs = [], []
    for y, r in profile:
        for k in range(seg):
            a = 2 * math.pi * k / seg
            vs.append((r * math.cos(a) / 100.0, -y / 100.0, r * math.sin(a) / 100.0))
    for i in range(len(profile) - 1):
        for k in range(seg):
            fs.append((i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k))
    fs.append(tuple(reversed(range(seg))))
    me.from_pydata(vs, [], fs)
    me.validate()
    for poly in me.polygons:
        poly.use_smooth = True
    mat = bpy.data.materials.new(name + "_mat")
    mat.diffuse_color = color
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


ROUND = []
if job.get("round"):
    rp, cy = job["round"]["profile"], job["round"]["case_y_cm"][1]
    case = [q for q in rp if q[0] <= cy + 1e-6]
    bullet = [[cy, 0.0]] + [q for q in rp if q[0] > cy + 1e-6]
    ROUND = [turned("Round_case", case, (0.80, 0.60, 0.26, 1.0)), turned("Round_bullet", bullet, (0.72, 0.42, 0.26, 1.0))]


def show_round(on):
    for o in ROUND:
        o.hide_render = not on
n = 0
report = {"shots": [], "free_clip": {}}


def body_tree():
    """The gun's fixed body (faces whose vertices all follow the root bone only), as a BVH, at rest."""
    gm = next(o for o in mesh if o.vertex_groups)
    names = {g.index: g.name for g in gm.vertex_groups}
    fixed = set()
    for v in gm.data.vertices:
        gs = [names[g.group] for g in v.groups if g.weight > 0.5]
        if gs and all(n_.lower() == "root" for n_ in gs):
            fixed.add(v.index)
    e = gm.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    vs = [gm.matrix_world @ v.co for v in e.vertices]
    fs = [tuple(p_.vertices) for p_ in e.polygons if all(i in fixed for i in p_.vertices)]
    return gm, BVHTree.FromPolygons(vs, fs)


def inside_depth(tree, co):
    """How deep co sits inside the body (metres, 0 outside): ray parity on three axes (two of three say inside), then
    the distance to the nearest face."""
    votes = 0
    for d in (Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 1, 0))):
        hits, o = 0, co.copy()
        for _ in range(64):
            loc, nrm, idx, dist = tree.ray_cast(o, d)
            if loc is None:
                break
            hits += 1
            o = loc + d * 1e-6
        votes += hits % 2
    if votes < 2:
        return 0.0
    near = tree.find_nearest(co)
    return near[3] if near[0] is not None else 0.0


def free_clipping(gm, tree, bones):
    """The free parts' vertices inside the body now: (count, deepest in cm)."""
    names = {g.index: g.name for g in gm.vertex_groups}
    e = gm.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    n_in, deep = 0, 0.0
    for v in e.vertices:
        if any(names[g.group] in bones and g.weight > 0.5 for g in gm.data.vertices[v.index].groups):
            dd = inside_depth(tree, gm.matrix_world @ v.co)
            if dd > 1e-4:                                 # deeper than 0.01 cm: a touch on a shared wall is not a clip
                n_in += 1
                deep = max(deep, dd * 100.0)
    return n_in, round(deep, 4)


def shot(name):
    global n
    sc.render.filepath = os.path.join(OUT, "f%05d.png" % n)
    bpy.ops.render.render(write_still=True)
    report["shots"].append({"frame": n, "shot": name})
    n += 1


# 1. once round (loaded)
show_round(True)
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
    if c.get("free"):
        # the free parts' gun-only way replaces their keys, on a copy (the clips file keeps the game's clip)
        act = act.copy()
        act.name = c["action"] + "_showcase"
    arm.animation_data.action = act
    if hasattr(arm.animation_data, "action_slot") and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    for bone, track in (c.get("free") or {}).items():
        pb = arm.pose.bones.get(bone)
        if pb is None:
            continue
        step = sc.render.fps / float(c.get("free_fps", 60))
        for i, (x, y, z) in enumerate(track):
            pb.location = Vector((x, -y, z)) / 100.0
            pb.keyframe_insert("location", frame=i * step)
    f0, f1 = act.frame_range
    src_fps = c.get("fps", 60)
    secs = (f1 - f0) / src_fps
    frames = max(2, int(round(secs * c.get("slow", 1) * FPS)))
    az, el = VIEWS.get(c.get("view", "right"), VIEWS["right"])
    aim(az, el, DIST * c.get("zoom", 1.0), Vector(c["look"]) if c.get("look") else LOOK.get(c.get("view")))
    slide = arm.pose.bones.get(job.get("slide_bone") or "Slide")
    for rep in range(c.get("repeat", 1)):
        was_away = False
        for k in range(frames + 1):
            t = f0 + (f1 - f0) * k / frames
            sc.frame_set(int(t), subframe=t - int(t))
            home = slide is None or slide.location.length < 1e-4
            was_away = was_away or not home
            rule = c.get("loaded", "always")
            show_round(rule == "always" or (rule == "when_home" and home) or (rule == "after_home" and home and was_away))
            if c.get("free"):
                if "_tree" not in globals():
                    arm.animation_data.action, keep = None, arm.animation_data.action
                    for pb_ in arm.pose.bones:
                        pb_.location, pb_.rotation_quaternion = (0, 0, 0), (1, 0, 0, 0)
                    bpy.context.view_layer.update()
                    globals()["_tree"] = body_tree()
                    arm.animation_data.action = keep
                    if hasattr(arm.animation_data, "action_slot") and keep.slots:
                        arm.animation_data.action_slot = keep.slots[0]
                    sc.frame_set(int(t), subframe=t - int(t))
                cnt, deep = free_clipping(_tree[0], _tree[1], set(c["free"]))
                rc = report["free_clip"].setdefault(c["action"], {"frames": 0, "frames_clipping": 0, "worst_cm": 0.0, "worst_vertices": 0})
                rc["frames"] += 1
                rc.setdefault("per_frame", []).append([round(t, 2), cnt, deep])
                if cnt:
                    rc["frames_clipping"] += 1
                    rc["worst_cm"] = max(rc["worst_cm"], deep)
                    rc["worst_vertices"] = max(rc["worst_vertices"], cnt)
            shot(c.get("label", c["action"]))
        for _ in range(int(FPS * c.get("hold", 0.4))):          # a short hold at the end of each play
            shot(c.get("label", c["action"]))
with open(os.path.join(OUT, "shots.json"), "w", encoding="utf-8") as f:
    json.dump(report, f)
print("SHOWCASE FRAMES %d" % n)
print("SHOWCASE FREE CLIP " + json.dumps(report["free_clip"]))
