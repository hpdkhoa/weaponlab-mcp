"""Motion Lab: a sliding part's track on its axis. A gun clip (the editor's FBX) whose part
(a carrier, a bolt, a pump) leaves its line as it travels gets its track rebuilt: its seat is the bind pose (the
model as built, the part in its rails), it travels only along its axis, by the clip's own travel along that axis,
frame by frame, and it does not turn. Writes the clip as FBX for the editor.

    blender -b --factory-startup -P track.py -- <in.fbx> <out.fbx> <bone> <root bone name> [x,y,z] [seat x,y,z]

The seat: where the part rests, in its own space (pose location); the bind pose if left out. A part can rest away
from its bind pose (a carrier 1.5 cm off it in one rifle): take the seat from the idle clip then.

The axis: x,y,z in the model's space as Blender reads the FBX (the bore: Rig Lab's barrel piece), turned into the
part's own space; without it, the clip's own stroke (which keeps a slanted path slanted)."""
import sys

import bpy
from mathutils import Quaternion, Vector

args = sys.argv[sys.argv.index("--") + 1:]
src, out, bone, root = args[:4]
given = Vector([float(x) for x in args[4].split(",")]) if len(args) > 4 else None
seat = Vector([float(x) for x in args[5].split(",")]) if len(args) > 5 else Vector((0, 0, 0))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
act = arm.animation_data.action
sc = bpy.context.scene
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
pb = arm.pose.bones[bone]
pb.rotation_mode = 'QUATERNION'
locs = {}
for f in range(f0, f1 + 1):
    sc.frame_set(f)
    locs[f] = pb.location.copy()
first = locs[f0]
far = max(locs, key=lambda f: (locs[f] - first).length)
axis = (locs[far] - first)
stroke = axis.length
axis = axis.normalized() if stroke > 1e-6 else Vector((0, 0, 1))
if given is not None:
    # the model's axis in the bone's rest frame (pose locations are in it), signed as the stroke goes
    g = (arm.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()).inverted() @ given
    g.normalize()
    axis = g if g.dot(axis) >= 0 else -g
# the clip's own travel along that axis (its off-axis part, and the offset it starts from, dropped)
travel = {f: (locs[f] - first).dot(axis) for f in locs}
off = max(((locs[f] - first) - axis * travel[f]).length for f in locs)
print("MOTIONLAB TRACK %s: frames %d-%d, stroke %.3f along %s (local), started %s off its bind seat, most off-axis %.3f"
      % (bone, f0, f1, stroke, tuple(round(x, 3) for x in axis), tuple(round(x, 3) for x in first), off))
# rebuild the track: drop the old keys of this bone, key the new ones
try:                                   # Blender 4.4+: an action's curves live in its slot's channel bag
    from bpy_extras import anim_utils
    curves = anim_utils.action_get_channelbag_for_slot(act, arm.animation_data.action_slot).fcurves
except (ImportError, AttributeError):
    curves = act.fcurves
for fc in [fc for fc in curves if fc.data_path.startswith('pose.bones["%s"]' % bone)]:
    curves.remove(fc)
for f in range(f0, f1 + 1):
    pb.location = seat + axis * travel[f]
    pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
    pb.scale = Vector((1, 1, 1))
    pb.keyframe_insert("location", frame=f)
    pb.keyframe_insert("rotation_quaternion", frame=f)
    pb.keyframe_insert("scale", frame=f)
sc.frame_start, sc.frame_end = f0, f1        # the bake writes the scene's range: the clip's own
for o in bpy.context.scene.objects:
    o.select_set(o == arm)
clash = bpy.data.objects.get(root)
if clash and clash != arm:
    clash.name = clash.name + "_kept"
arm.name = root
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={'ARMATURE'}, add_leaf_bones=False, bake_anim=True,
                         bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
                         bake_anim_simplify_factor=0.0)
print("MOTIONLAB TRACK DONE", out)
