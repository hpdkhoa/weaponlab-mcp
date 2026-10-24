"""Gun Kit's rig step, in Blender: a gun rigged for its action from a parts map, whoever drew it. A proxy's shapes are
built here; a user's model (.blend, .fbx, .obj, .glb) is imported and turned into gun space. Every part's objects go
on its bone, the rest on Root; the whole is one mesh on one armature, as Model Lab's rigs are. Writes, under out:
SK_<name>_Rig.fbx, <name>_rig.blend, gunfacts.json. Nothing else.

    blender -b --factory-startup -P gunkit_rig.py -- <job.json>
job: {"partsmap": {...} | "<path>", "shapes": [...] (a proxy's, else null), "out": folder, "pkg": "<weaponlab's src>"}

Spaces: gun space is cm, +Y to the muzzle, +Z up, +X the gun's left (facts, marks, pivots). Blender's world is metres
with Y flipped, as Model Lab's (the FBX importer flips it back): g(x, y, z) = (x, -y, z) / 100. A bone points along
Blender +Y (back along the gun) with no roll, so its axes are the world's.

A user's model: partsmap "forward" and "up" name the model's axes as Blender shows it after import ("+X", "-Y", ...),
"origin" the bolt face in Blender's world after import, "units" what one Blender unit is in the model ("m", "cm", "mm")."""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
sys.path.append(job["pkg"])   # last: Blender's own numpy first (an installed package sits in a site-packages built for another Python)
from weaponlab.gunkit import rigplan as R  # noqa: E402

pm = job["partsmap"] if isinstance(job["partsmap"], dict) else json.load(open(job["partsmap"], encoding="utf-8"))
OUT = job["out"]
os.makedirs(OUT, exist_ok=True)
NAME = pm["name"]


def g(x, y, z):
    return Vector((x, -y, z)) / 100.0


def gun(v):
    return [round(v.x * 100.0, 4), round(-v.y * 100.0, 4), round(v.z * 100.0, 4)]


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.scale_length = 1.0

# --- the meshes: a proxy's shapes, or the user's model turned into gun space -----------------------------------------
COLOURS = {None: (0.18, 0.18, 0.2, 1.0)}


def material(role):
    if role not in COLOURS:
        h = (abs(hash(role)) % 360) / 360.0
        import colorsys
        r, gg, b = colorsys.hsv_to_rgb(h, 0.55, 0.8)
        COLOURS[role] = (r, gg, b, 1.0)
    name = "M_" + (R.bone_name(role) if role else "Body")
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = COLOURS[role]
    return m


objects = {}
if job.get("shapes"):
    for s in job["shapes"]:
        if s["shape"] == "box":
            bpy.ops.mesh.primitive_cube_add(size=1.0)
            ob = bpy.context.object
            ob.scale = (s["size"][0] / 100.0, s["size"][1] / 100.0, s["size"][2] / 100.0)
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.5, depth=1.0)
            ob = bpy.context.object
            d, length = s["size"]
            along = s.get("along", "y")
            if along == "y":
                ob.rotation_euler = (math.radians(90), 0, 0)
                ob.scale = (d / 100.0, d / 100.0, length / 100.0)
            elif along == "x":
                ob.rotation_euler = (0, math.radians(90), 0)
                ob.scale = (d / 100.0, d / 100.0, length / 100.0)
            else:
                ob.scale = (d / 100.0, d / 100.0, length / 100.0)
        ob.location = g(*s["at"])
        ob.name = s["name"]
        ob.data.materials.append(material(s.get("part")))
        bpy.context.view_layer.update()
        ob.data.transform(ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
        objects[s["name"]] = ob
else:
    path = pm["model"]
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext == ".blend":
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [n for n in src.objects]
        for ob in dst.objects:
            if ob is not None:
                bpy.context.scene.collection.objects.link(ob)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise SystemExit("GUNKIT RIG: cannot read %s" % path)
    new = [o for o in bpy.data.objects if o not in before]
    for ob in new:
        if ob.type != 'MESH':
            continue
        ob.data = ob.data.copy()
        ob.data.transform(ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
        ob.parent = None
        objects[ob.name] = ob
    for ob in new:
        if ob.type != 'MESH':
            bpy.data.objects.remove(ob)
    # the model's axes and units into gun space, then into Blender's (g)
    axes = {"+X": Vector((1, 0, 0)), "-X": Vector((-1, 0, 0)), "+Y": Vector((0, 1, 0)), "-Y": Vector((0, -1, 0)),
            "+Z": Vector((0, 0, 1)), "-Z": Vector((0, 0, -1))}
    f, u = axes[pm.get("forward", "+Y")], axes[pm.get("up", "+Z")]
    # Blender's world is right-handed, gun space left-handed (+X the gun's left, as Unreal's): the gun's left is up x
    # forward here (forward x up is its right)
    left = u.cross(f)
    unit_cm = {"m": 100.0, "cm": 1.0, "mm": 0.1}[pm.get("units", "m")]
    o = Vector(pm.get("origin", [0, 0, 0]))
    to_gun = Matrix(((*left, 0.0), (*f, 0.0), (*u, 0.0), (0.0, 0.0, 0.0, 1.0)))   # rows: gun x, y, z of a model vector
    to_gun = Matrix.Scale(unit_cm, 4) @ to_gun @ Matrix.Translation(-o)
    flip = Matrix.Diagonal((0.01, -0.01, 0.01, 1.0))                          # gun cm to Blender m, Y flipped
    for ob in objects.values():
        ob.data.transform(flip @ to_gun)
        if (flip @ to_gun).determinant() < 0:
            ob.data.flip_normals()

# a part named by vertex groups (a joined mesh, a Model Lab build): its vertices split off into an object of its own,
# named after the part, so every later step sees objects
for role, p in pm["parts"].items():
    groups = p.get("vertex_groups") or []
    if not groups:
        continue
    made = []
    for src in list(objects.values()):
        idx = {vg.index for vg in src.vertex_groups if vg.name in groups}
        if not idx:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = src
        src.select_set(True)
        bpy.context.tool_settings.mesh_select_mode = (True, False, False)     # vertices: their faces follow
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        picked = 0
        for v in src.data.vertices:
            v.select = any(g.group in idx and g.weight > 0.5 for g in v.groups)
            picked += v.select
        if not picked:
            continue
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='VERT')
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        new = [o for o in bpy.context.selected_objects if o is not src]
        for o in new:
            o.name = "%s_%s" % (R.bone_name(role), src.name)
            objects[o.name] = o
            made.append(o.name)
    p["objects"] = list(p.get("objects", [])) + made
    p.pop("vertex_groups", None)
for ob in objects.values():                      # the old skin's groups mean nothing on the new rig
    ob.vertex_groups.clear()

missing = [n for p in pm["parts"].values() for n in p.get("objects", []) if n not in objects]
if missing:
    raise SystemExit("GUNKIT RIG: the parts map names objects the model does not have: %s; it has: %s"
                     % (", ".join(missing), ", ".join(sorted(objects))))

# --- each part's centre, then the facts (rigplan) --------------------------------------------------------------------
centres = {}
for role, p in pm["parts"].items():
    pts = [Vector(c) for n in p.get("objects", []) for c in [v.co for v in objects[n].data.vertices]]
    if pts:
        lo = Vector((min(v.x for v in pts), min(v.y for v in pts), min(v.z for v in pts)))
        hi = Vector((max(v.x for v in pts), max(v.y for v in pts), max(v.z for v in pts)))
        centres[role] = gun((lo + hi) / 2.0)
tri = sum(len(ob.data.polygons) for ob in objects.values())
facts = R.plan(pm, centres, model={"source": "proxy" if job.get("shapes") else "import", "from": pm.get("model"),
                                   "triangles": tri})

# --- one mesh on one armature ------------------------------------------------------------------------------------------
owner = {n: R.bone_name(role) for role, p in pm["parts"].items() for n in p.get("objects", [])}
for name, ob in objects.items():
    vg = ob.vertex_groups.new(name=owner.get(name, "Root"))
    vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
for o in bpy.context.scene.objects:
    o.select_set(False)
every = list(objects.values())
for ob in every:
    ob.select_set(True)
bpy.context.view_layer.objects.active = every[0]
bpy.ops.object.join()
mesh = bpy.context.object
mesh.name = NAME + "_Mesh"
arm_data = bpy.data.armatures.new("SKEL_" + NAME)
arm = bpy.data.objects.new(NAME, arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for b in facts["bones"]:
    eb = arm_data.edit_bones.new(b["name"])
    eb.head = g(*b["head"])
    eb.tail = eb.head + Vector((0, 0.02, 0))
    eb.roll = 0.0
for b in facts["bones"]:
    if b.get("parent"):
        arm_data.edit_bones[b["name"]].parent = arm_data.edit_bones[b["parent"]]
bpy.ops.object.mode_set(mode='OBJECT')
mesh.parent = arm
mesh.modifiers.new("Armature", 'ARMATURE').object = arm

blend = os.path.join(OUT, "%s_rig.blend" % NAME)
fbx = os.path.join(OUT, "SK_%s_Rig.fbx" % NAME)
for o in bpy.context.scene.objects:
    o.select_set(False)
arm.select_set(True)
mesh.select_set(True)
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False,
                         bake_anim=False, mesh_smooth_type='FACE', colors_type='LINEAR')
bpy.ops.wm.save_as_mainfile(filepath=blend)
facts["model"].update({"blend": blend, "file": fbx, "armature": NAME, "mesh": mesh.name})
json.dump(facts, open(os.path.join(OUT, "gunfacts.json"), "w", encoding="utf-8"), indent=1)
print("GUNKIT RIG: %s, %d bones, %d triangles, %s" % (NAME, len(facts["bones"]), tri, OUT))
