"""Blueprint Lab's build step, in Blender: a blueprint (weaponlab-blueprint/1) as a model, one object a part, named
after the part, with a material a finish. An extrude is its side outline run across x; a lathe its profile turned
round its axis; holes are cut across x. Writes, under out: <name>.blend and build.json. Nothing else.

    blender -b --factory-startup -P blueprint_build.py -- <job.json>
job: {"blueprint": {...}, "out": folder, "segments": 32}

Gun space is cm, +Y to the muzzle, +Z up, +X the gun's left; Blender's world is metres with Y flipped (Model Lab's
and Gun Kit's convention): g(x, y, z) = (x, -y, z) / 100."""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
bp = job["blueprint"]
OUT = job["out"]
SEG = int(job.get("segments", 32))
os.makedirs(OUT, exist_ok=True)
for _o in list(bpy.data.objects):          # the factory scene's cube, camera and light are not the gun's
    bpy.data.objects.remove(_o)

FINISH = {"blued": ((0.05, 0.055, 0.065), 1.0, 0.35), "parkerized": ((0.11, 0.115, 0.11), 0.9, 0.7),
          "phosphate": ((0.11, 0.115, 0.11), 0.9, 0.7), "steel": ((0.45, 0.45, 0.47), 1.0, 0.3),
          "stainless": ((0.6, 0.6, 0.62), 1.0, 0.25), "nickel": ((0.65, 0.63, 0.6), 1.0, 0.2),
          "aluminium": ((0.12, 0.12, 0.13), 0.8, 0.5), "brass": ((0.7, 0.55, 0.25), 1.0, 0.3),
          "walnut": ((0.25, 0.12, 0.05), 0.0, 0.55), "wood": ((0.3, 0.17, 0.08), 0.0, 0.6),
          "plastic": ((0.18, 0.09, 0.05), 0.0, 0.45), "bakelite": ((0.16, 0.08, 0.04), 0.0, 0.4),
          "polymer": ((0.04, 0.04, 0.04), 0.0, 0.6), "rubber": ((0.03, 0.03, 0.03), 0.0, 0.85)}


def g(x, y, z):
    return Vector((x, -y, z)) / 100.0


def material(finish):
    name = "M_" + finish
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    key = next((k for k in FINISH if k in finish.lower()), "steel")
    col, metal, rough = FINISH[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*col, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*col, 1.0)                 # the colour quick renders and the viewport show
    m.metallic, m.roughness = metal, rough
    m["finish"] = finish
    return m


def ccw(outline):
    s = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(outline, outline[1:] + outline[:1]))
    return outline if s > 0 else list(reversed(outline))


def prism(name, outline, x0, x1):
    """A side outline (y, z) run from x0 to x1: its two faces and its walls, closed."""
    pts = ccw([p for i, p in enumerate(outline) if i == 0 or p != outline[i - 1]])
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(g(x0, y, z)) for y, z in pts]
    b = [bm.verts.new(g(x1, y, z)) for y, z in pts]
    n = len(pts)
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def lathe(name, profile, ax, az, bore_r=None):
    """A profile (y, r) turned round the line x = ax, z = az along the bore; a bore hole cut along it."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for y, r in profile:
        rings.append([bm.verts.new(g(ax + r * math.cos(2 * math.pi * k / SEG), y, az + r * math.sin(2 * math.pi * k / SEG))) for k in range(SEG)])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(SEG):
            q = [ra[k], ra[(k + 1) % SEG], rb[(k + 1) % SEG], rb[k]]
            if len(set(q)) == 4:
                bm.faces.new(q)
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if bore_r:
        y0, y1 = profile[0][0] - 1.0, profile[-1][0] + 1.0
        cut = lathe(name + "_bore", [[y0, bore_r], [y1, bore_r]], ax, az)
        boolean(ob, cut)
    return ob


def prism_along(name, outline, axis, lo, hi):
    """An outline run along y (a front section, its points (x, z)) or along z (a top outline, its points (y, x))."""
    pts = ccw([p for i, p in enumerate(outline) if i == 0 or p != outline[i - 1]])
    if axis == "y":
        put = lambda a, b, t: g(a, t, b)        # noqa: E731
    else:
        put = lambda a, b, t: g(b, a, t)        # noqa: E731
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(put(u, v, lo)) for u, v in pts]
    b = [bm.verts.new(put(u, v, hi)) for u, v in pts]
    n = len(pts)
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def join(obs, name):
    """Several cutters as one object (their union, for an intersect)."""
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def bounds_cm(ob):
    vs = [v.co for v in ob.data.vertices]
    return {"x": (min(v.x for v in vs) * 100, max(v.x for v in vs) * 100), "y": (min(-v.y for v in vs) * 100, max(-v.y for v in vs) * 100),
            "z": (min(v.z for v in vs) * 100, max(v.z for v in vs) * 100)}


def feature(ob, pid, k, ft, textures):
    """A surface feature: grooves cut, a screw head added, a texture noted for the finish."""
    b = bounds_cm(ob)
    if ft["kind"] == "texture":
        textures.append({"part": pid, "pattern": ft["pattern"], "face": ft["face"], "pitch_cm": ft.get("pitch_cm"), "text": ft.get("text")})
        return
    faces = ["left", "right"] if ft["face"] == "both" else [ft["face"]]
    for face in faces:
        if ft["kind"] == "grooves":
            y0, y1 = ft.get("y") or b["y"]
            z0, z1 = ft.get("z") or b["z"]
            n, w, d = ft["count"], ft["width_cm"], ft["depth_cm"]
            pitch = (y1 - y0) / n
            slant = math.tan(math.radians(ft.get("slant_deg", 0.0)))
            zm = (z0 + z1) / 2.0
            for i in range(n):
                yc = y0 + pitch * (i + 0.5)
                if face in ("left", "right"):
                    out = [[yc - w / 2 + slant * (z0 - zm), z0], [yc + w / 2 + slant * (z0 - zm), z0], [yc + w / 2 + slant * (z1 - zm), z1], [yc - w / 2 + slant * (z1 - zm), z1]]
                    xa, xb = (b["x"][1] - d, b["x"][1] + 1.0) if face == "left" else (b["x"][0] - 1.0, b["x"][0] + d)
                    cut = prism("%s_f%d_%d" % (pid, k, i), out, xa, xb)
                else:                                   # top: across x, cut down from the top
                    xs = ft.get("x") or b["x"]
                    out = [[yc - w / 2, b["z"][1] - d], [yc + w / 2, b["z"][1] - d], [yc + w / 2, b["z"][1] + 1.0], [yc - w / 2, b["z"][1] + 1.0]]
                    cut = prism("%s_f%d_%d" % (pid, k, i), out, xs[0], xs[1])
                boolean(ob, cut)
        elif ft["kind"] == "screw":
            (y, z), r, h = ft["at"], ft["r"], ft["head_cm"]
            circ = [[y + r * math.cos(2 * math.pi * t / SEG), z + r * math.sin(2 * math.pi * t / SEG)] for t in range(SEG)]
            xa, xb = (b["x"][1] - 0.05, b["x"][1] + h) if face == "left" else (b["x"][0] - h, b["x"][0] + 0.05)
            head = prism("%s_screw%d" % (pid, k), circ, xa, xb)
            if ft.get("slot", True):
                sx = (xb - 0.6 * h, xb + 1.0) if face == "left" else (xa - 1.0, xa + 0.6 * h)
                boolean(head, prism("%s_slot%d" % (pid, k), [[y - r, z - r * 0.12], [y + r, z - r * 0.12], [y + r, z + r * 0.12], [y - r, z + r * 0.12]], sx[0], sx[1]))
            union(ob, head)


def union(ob, other):
    mod = ob.modifiers.new("add", 'BOOLEAN')
    mod.operation = 'UNION'
    mod.solver = 'EXACT'
    mod.object = other
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(other)


def intersect(ob, other):
    before = len(ob.data.vertices)
    mod = ob.modifiers.new("keep", 'BOOLEAN')
    mod.operation = 'INTERSECT'
    mod.solver = 'EXACT'
    mod.object = other
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    print("BLUEPRINT STEP shape %s with %s: %d to %d vertices" % (ob.name, other.name, before, len(ob.data.vertices)))
    bpy.data.objects.remove(other)
    if not ob.data.vertices:
        raise SystemExit("BLUEPRINT BUILD FAILED: %s and its other view share nothing (check the view's outline and its place)" % ob.name)


def boolean(ob, cutter):
    before = len(ob.data.vertices)
    mod = ob.modifiers.new("cut", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    what = (ob.name, cutter.name)
    print("BLUEPRINT STEP cut %s with %s: %d to %d vertices" % (what + (before, len(ob.data.vertices))))
    bpy.data.objects.remove(cutter)
    if not ob.data.vertices:
        raise SystemExit("BLUEPRINT BUILD FAILED: cutting %s with %s left nothing (a cut that covers the part, or a broken outline)" % what)


report = {"parts": {}, "textures": []}
for pid, p in bp["parts"].items():
    sh = p["shape"]
    if sh["kind"] in ("extrude", "views"):
        x0, x1 = sh["x"]
        ob = prism(pid, sh["outline"] if sh["kind"] == "extrude" else sh["side"], x0, x1)
        if sh["kind"] == "views":
            zs = [q[1] for q in sh["side"]]
            if sh.get("front"):
                intersect(ob, join([prism_along("%s_front%d" % (pid, k), f["outline"], "y", f["y"][0], f["y"][1]) for k, f in enumerate(sh["front"])], pid + "_front"))
            if sh.get("top"):
                intersect(ob, prism_along(pid + "_top", sh["top"], "z", min(zs) - 1.0, max(zs) + 1.0))
        print("BLUEPRINT STEP %s: %d vertices, %d faces" % (pid, len(ob.data.vertices), len(ob.data.polygons)))
        for k, h in enumerate(p.get("holes", [])):
            hx = h.get("x") or [x0 - 1.0, x1 + 1.0]
            if h["kind"] == "bore":
                cut = lathe("%s_hole%d" % (pid, k), [[h["y"][0], h["r"]], [h["y"][1], h["r"]]], h["at"][0], h["at"][1])
            elif h["kind"] == "polygon":
                cut = prism("%s_hole%d" % (pid, k), h["outline"], hx[0], hx[1])
            else:
                (y, z), r = h["at"], h["r"]
                cut = prism("%s_hole%d" % (pid, k), [[y + r * math.cos(2 * math.pi * t / SEG), z + r * math.sin(2 * math.pi * t / SEG)] for t in range(SEG)], hx[0], hx[1])
            boolean(ob, cut)
    else:
        ob = lathe(pid, sh["profile"], sh["axis"][0], sh["axis"][1], sh.get("bore_r"))
    for k, ft in enumerate(p.get("features", [])):
        feature(ob, pid, k, ft, report["textures"])
    if p.get("bevel_cm"):
        mod = ob.modifiers.new("bevel", 'BEVEL')
        mod.width = p["bevel_cm"] / 100.0
        mod.segments = 2
        mod.limit_method = 'ANGLE'
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.data.materials.clear()                     # the cuts bring their cutters' empty slots: one finish a part
    ob.data.materials.append(material(p["finish"]))
    for poly in ob.data.polygons:
        poly.material_index = 0
    ob["role"] = p["role"]
    ob["finish"] = p["finish"]
    ob.data.validate()
    lo = Vector((min(v.co.x for v in ob.data.vertices), min(v.co.y for v in ob.data.vertices), min(v.co.z for v in ob.data.vertices)))
    hi = Vector((max(v.co.x for v in ob.data.vertices), max(v.co.y for v in ob.data.vertices), max(v.co.z for v in ob.data.vertices)))
    report["parts"][pid] = {"role": p["role"], "vertices": len(ob.data.vertices), "faces": len(ob.data.polygons),
                            "bounds_cm": {"x": [round(lo.x * 100, 3), round(hi.x * 100, 3)], "y": [round(-hi.y * 100, 3), round(-lo.y * 100, 3)],
                                          "z": [round(lo.z * 100, 3), round(hi.z * 100, 3)]}}
blend = os.path.join(OUT, "%s.blend" % bp["name"])
bpy.ops.wm.save_as_mainfile(filepath=blend)
report["blend"] = blend
with open(os.path.join(OUT, "build.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)
print("BLUEPRINT BUILD " + json.dumps({"parts": len(report["parts"]), "blend": blend}))
