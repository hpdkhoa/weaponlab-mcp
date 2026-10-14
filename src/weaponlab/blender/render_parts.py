"""Rig Lab's renders: reads the probe's parts dumps (OBJ in the gun's space, cm, one
group a component and bone: "<role>|<component>|<asset>|<bone>"), splits each group into its pieces (connected
triangles), lists them, finds pieces drawn twice, and renders dev views from outside the gun. Writes JSON and PNG
only under the folder given.

    blender -b --factory-startup -P render_parts.py -- <job.json>

job: {"out": folder, "dumps": [obj paths], "render": true, "views": ["right", "left", "top", "bottom"]}"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

COLORS = {"arms": (0.75, 0.72, 0.68, 1), "gun": (0.12, 0.12, 0.14, 1), "part": (0.15, 0.3, 0.75, 1), "item": (0.95, 0.5, 0.1, 1)}


def read_obj(path):
    """The groups of a parts dump: {group: [triangles of three (x, y, z) in cm]}, and the eye."""
    groups, verts, cur, eye = {}, [], None, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("v "):
                verts.append(tuple(float(x) for x in line.split()[1:4]))
            elif line.startswith("g "):
                cur = line[2:].strip()
                groups.setdefault(cur, [])
            elif line.startswith("f "):
                i = [int(x) - 1 for x in line.split()[1:4]]
                groups[cur].append((verts[i[0]], verts[i[1]], verts[i[2]]))
            elif line.startswith("# eye"):
                eye = tuple(float(x) for x in line.split()[2:5])
    return groups, eye


def pieces(tris, weld=0.02):
    """Connected pieces of a triangle soup (vertices within weld cm count as one)."""
    key = lambda p: (round(p[0] / weld), round(p[1] / weld), round(p[2] / weld))
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for t in tris:
        ks = [key(p) for p in t]
        for k in ks:
            parent.setdefault(k, k)
        for k in ks[1:]:
            ra, rb = find(ks[0]), find(k)
            if ra != rb:
                parent[rb] = ra
    out = {}
    for t in tris:
        out.setdefault(find(key(t[0])), []).append(t)
    return list(out.values())


def describe(tris):
    pts = [Vector(p) for t in tris for p in t]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = sum(pts, Vector()) / len(pts)
    area = sum(((Vector(t[1]) - Vector(t[0])).cross(Vector(t[2]) - Vector(t[0]))).length / 2.0 for t in tris)
    # the shape's own size, whatever its turn: its three principal extents (a signature for twins)
    import numpy as np
    a = np.array([[p.x, p.y, p.z] for p in pts])
    a = a - a.mean(axis=0)
    w, v = np.linalg.eigh(np.cov(a.T)) if len(a) > 3 else (np.zeros(3), np.eye(3))
    proj = a @ v
    ext = sorted((proj.max(axis=0) - proj.min(axis=0)).tolist(), reverse=True)
    axis = v[:, int(np.argmax(w))].tolist()
    return {"triangles": len(tris), "center": [round(x, 2) for x in c], "min": [round(x, 2) for x in lo], "max": [round(x, 2) for x in hi],
            "area_cm2": round(area, 1), "extents": [round(x, 2) for x in ext], "long_axis": [round(x, 3) for x in axis]}


def twins(items, tol=0.06):
    """Pieces drawn twice: the same triangle count and the same three extents (within tol of the size), anywhere."""
    found = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a["triangles"] < 12 or a["triangles"] != b["triangles"]:
                continue
            if all(abs(x - y) <= tol * max(x, y, 0.5) for x, y in zip(a["extents"], b["extents"])):
                found.append({"a": a["id"], "b": b["id"], "apart_cm": round((Vector(a["center"]) - Vector(b["center"])).length, 2)})
    return found


def scene(groups):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for g, tris in groups.items():
        if not tris:
            continue
        me = bpy.data.meshes.new("m")
        bm = bmesh.new()
        for t in tris:
            vs = [bm.verts.new(Vector(p) / 100.0) for p in t]
            try:
                bm.faces.new(vs)
            except ValueError:
                pass
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(g[:60], me)
        ob.color = COLORS.get(g.split("|")[0], (0.5, 0.5, 0.5, 1))
        bpy.context.scene.collection.objects.link(ob)


def render(out, tag, views):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.color_type = 'OBJECT'
    sc.display.shading.light = 'STUDIO'
    sc.render.resolution_x, sc.render.resolution_y = 960, 600
    sc.render.film_transparent = False
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.93, 0.93, 0.9)
    pts = [o.matrix_world @ Vector(c) for o in sc.objects if o.type == 'MESH' for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    mid, size = (lo + hi) / 2, max((hi - lo).length, 0.1)
    cam_data = bpy.data.cameras.new("c")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = size * 1.05
    cam = bpy.data.objects.new("c", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    # gun space: +Y along the barrel, +Z up, +X the gun's left (Pose Lab's gun frame)
    dirs = {"right": Vector((-1, 0, 0)), "left": Vector((1, 0, 0)), "top": Vector((0, 0, 1)), "bottom": Vector((0, 0, -1)), "front": Vector((0, 1, 0))}
    made = []
    for v in views:
        d = dirs[v]
        cam.location = mid + d * size * 2
        up = Vector((0, 1, 0)) if v in ("top", "bottom") else Vector((0, 0, 1))
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y' if v not in ("top", "bottom") else 'Y').to_euler()
        if v in ("top", "bottom"):
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, "%s_%s.png" % (tag, v))
        bpy.ops.render.render(write_still=True)
        made.append(sc.render.filepath)
    return made


def main():
    job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    out = job["out"]
    os.makedirs(out, exist_ok=True)
    result = {}
    for path in job["dumps"]:
        tag = os.path.splitext(os.path.basename(path))[0]
        groups, eye = read_obj(path)
        items = []
        for g, tris in groups.items():
            role, comp, asset, bone = (g.split("|") + ["", "", "", ""])[:4]
            if role == "arms":
                continue
            for k, pc in enumerate(sorted(pieces(tris), key=len, reverse=True)):
                d = describe(pc)
                d.update({"id": "%s|%s#%d" % (comp, bone, k), "role": role, "component": comp, "asset": asset, "bone": bone})
                items.append(d)
        result[tag] = {"eye": eye, "pieces": items, "twins": twins(items)}
        if job.get("render"):
            scene(groups)
            result[tag]["renders"] = render(out, tag, job.get("views", ["right", "left", "top", "bottom"]))
    json.dump(result, open(os.path.join(out, "riglab.json"), "w", encoding="utf-8"), indent=1)
    print("RIGLAB DONE %d dumps" % len(result))


main()
