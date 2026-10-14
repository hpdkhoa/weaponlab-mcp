"""Motion Lab: a forearm's roll. Turns a hand about its forearm's line through a whole clip, the hand's place kept,
the roll shared out the way a real forearm shares it: the twist bones take a third and two thirds, the hand all of it
(the radius turns about the ulna along the whole forearm, not at the wrist). A palm-down fist turned a quarter turn
stands thumb up, so a hilt in it rises the way a sword's does. Bones as Unreal's mannequin names them (lowerarm_r,
lowerarm_twist_01_r, lowerarm_twist_02_r, hand_r, index_01_r, pinky_01_r).

    blender -b --factory-startup -P roll.py -- <in.fbx> <out.fbx> <side l|r> <degrees | auto | measure>

auto: the turn that stands the knuckle line (index to little finger) most nearly upright at the clip's first frame
(each clip from its own start: a backhand cut can start palm up while the others start palm down).
measure: writes nothing; prints MOTIONLAB PROFILE, the knuckle line's angle about the forearm every few frames
(0: thumb up; past 80 either way breaks the forearm's range).
Prints MOTIONLAB ROLL <degrees>."""
import math
import sys

import bpy
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
src, out, side, want = args[:4]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
act = arm.animation_data.action
sc = bpy.context.scene
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
P = arm.pose.bones
lower, hand = P["lowerarm_" + side], P["hand_" + side]
twists = [(P[n], k) for n, k in (("lowerarm_twist_01_" + side, 1 / 3), ("lowerarm_twist_02_" + side, 2 / 3)) if n in P]
for b, _ in twists:
    assert b.parent == lower, "%s is not the forearm's child" % b.name
assert hand.parent == lower, "the hand is not the forearm's child"
W = arm.matrix_world


def axis_now():
    a = (W @ hand.head) - (W @ lower.head)
    return a.normalized()


def turned(pb, ang, axis):
    """pb's armature-space matrix turned by ang about the forearm's line (through pb's head)."""
    ax = W.to_3x3().inverted() @ axis
    head = pb.matrix.translation.copy()
    return Matrix.Translation(head) @ Matrix.Rotation(ang, 4, ax.normalized()) @ Matrix.Translation(-head) @ pb.matrix


def profile():
    out = []
    for f in range(f0, f1 + 1, max(1, (f1 - f0) // 12)):
        sc.frame_set(f)
        ax = axis_now()
        k = (W @ P["index_01_" + side].head) - (W @ P["pinky_01_" + side].head)
        k = (k - ax * k.dot(ax)).normalized()
        up = Vector((0, 0, 1))
        up = (up - ax * up.dot(ax)).normalized()
        out.append((f, round(math.degrees(math.atan2(k.dot(ax.cross(up)), k.dot(up))))))
    return out


if want == "measure":
    pr = profile()
    print("MOTIONLAB PROFILE %s" % " ".join("%d:%d" % fa for fa in pr))
    print("MOTIONLAB PROFILE WORST %d" % max(abs(a) for _, a in pr))
    sys.exit(0)
sc.frame_set(f0)
if want == "auto":
    axis = axis_now()
    across = (W @ P["index_01_" + side].head) - (W @ P["pinky_01_" + side].head)
    best = max(range(-180, 181), key=lambda d: (Matrix.Rotation(math.radians(d), 3, axis) @ across).normalized().z)
    deg = float(best)
else:
    deg = float(want)
print("MOTIONLAB ROLL %.1f" % deg)
frames = {}
for f in range(f0, f1 + 1):
    sc.frame_set(f)
    axis = axis_now()
    frames[f] = [(pb, turned(pb, math.radians(deg) * k, axis)) for pb, k in twists + [(hand, 1.0)]]
for f, mats in frames.items():
    sc.frame_set(f)
    for pb, m in mats:
        pb.rotation_mode = 'QUATERNION'
        pb.matrix = m
        bpy.context.view_layer.update()
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion", frame=f)
# check: the hand's place kept, the knuckle line turned
sc.frame_set(f0)
print("MOTIONLAB ROLL CHECK knuckles up %.2f" % ((W @ P["index_01_" + side].head) - (W @ P["pinky_01_" + side].head)).normalized().z)
sc.frame_start, sc.frame_end = f0, f1
for o in bpy.context.scene.objects:
    o.select_set(o == arm)
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={'ARMATURE'}, add_leaf_bones=False, bake_anim=True,
                         bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
                         bake_anim_simplify_factor=0.0)
print("MOTIONLAB ROLL DONE", out, "armature", arm.name, "frames", f0, f1)
