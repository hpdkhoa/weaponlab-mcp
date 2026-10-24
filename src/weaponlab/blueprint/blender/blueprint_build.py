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
PLAIN = bool(job.get("plain"))           # the collision copy: no knurl grooves, the reliefs on a coarser grid
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


def material_textured(finish, pattern, pitch_cm):
    """The finish with a surface pattern too fine for the mesh shown in its shading: stippling as a fine noise bump
    (a moulded stock's texture), knurling and checkering as a finer one; the colour and the shine kept."""
    name = "M_%s_%s_%.3f" % (finish, pattern, pitch_cm)
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = material(finish).copy()
    m.name = name
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 100.0 / max(pitch_cm, 0.02)      # one grain each pitch (the model is in metres)
    tex.inputs["Detail"].default_value = 4.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = pitch_cm / 400.0
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = min(1.0, b.inputs["Roughness"].default_value + 0.15)
    m["pattern"] = pattern
    return m


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


def rounded(outline):
    """An outline whose points may carry a corner radius (y, z, r in cm, as the drawing gives it): each such corner
    replaced by the arc tangent to both its edges, at least one point every 360/SEG degrees of turn. A radius too big
    for its edges is cut to fit (half of the shorter edge) and noted."""
    pts = [list(p) for i, p in enumerate(outline) if i == 0 or p[:2] != outline[i - 1][:2]]
    if not any(len(p) > 2 and p[2] > 0 for p in pts):
        return [p[:2] for p in pts]
    out, n = [], len(pts)
    for i, p in enumerate(pts):
        r = p[2] if len(p) > 2 else 0.0
        if r <= 0:
            out.append(p[:2])
            continue
        P, A, B = Vector((p[0], p[1])), Vector(pts[i - 1][:2]), Vector(pts[(i + 1) % n][:2])
        u, v = (A - P), (B - P)
        la, lb = u.length, v.length
        if la < 1e-9 or lb < 1e-9:
            out.append(p[:2])
            continue
        u, v = u / la, v / lb
        half = math.acos(max(-1.0, min(1.0, u.dot(v)))) / 2.0
        if half < 1e-4 or half > math.pi / 2 - 1e-4:
            out.append(p[:2])
            continue
        t = r / math.tan(half)
        tmax = 0.5 * min(la, lb)
        if t > tmax:
            ROUND_NOTES.append({"corner": [round(p[0], 3), round(p[1], 3)], "radius_cm": r, "cut_to_cm": round(tmax * math.tan(half), 4)})
            t, r = tmax, tmax * math.tan(half)
        bis = (u + v).normalized()
        C = P + bis * (r / math.sin(half))
        T1, T2 = P + u * t, P + v * t
        a1 = math.atan2(T1.y - C.y, T1.x - C.x)
        a2 = math.atan2(T2.y - C.y, T2.x - C.x)
        d = a2 - a1
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        k = max(2, int(math.ceil(abs(d) / (2 * math.pi / SEG))))
        for j in range(k + 1):
            a_ = a1 + d * j / k
            out.append([C.x + r * math.cos(a_), C.y + r * math.sin(a_)])
    return out


ROUND_NOTES = []


def prism(name, outline, x0, x1):
    """A side outline (y, z) run from x0 to x1: its two faces and its walls, closed."""
    pts = ccw(rounded(outline))
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
    pts = ccw(rounded(outline))
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


def _seg_hits(pts, P, d):
    """Where the line P + s d crosses the closed outline pts: the s values, sorted."""
    out = []
    n = len(pts)
    for i in range(n):
        A, B = Vector(pts[i]), Vector(pts[(i + 1) % n])
        e = B - A
        den = d.x * e.y - d.y * e.x
        if abs(den) < 1e-12:
            continue
        w = A - P
        s = (w.x * e.y - w.y * e.x) / den
        u = (w.x * d.y - w.y * d.x) / den
        if -1e-9 <= u <= 1.0 + 1e-9:
            out.append(s)
    return sorted(out)


def relief(name, side, x, edge_cm, axis, grid_cm=0.08):
    """A relief: the side outline (y, z) with a flat inner face at x[0], and an outer face arching across the part's
    width (square to its long axis) as one circular arc, edge_cm thick at the rim and |x[1] - x[0]| at the middle of
    each cross line, the width read where the line crosses the outline: a grip panel's crescent section. The outer face
    is a constrained triangulation of the outline and a grid of points inside it (grid_cm apart)."""
    from mathutils.geometry import delaunay_2d_cdt
    pts = ccw(rounded(side))
    x0, x1 = x
    sgn = 1.0 if x1 >= x0 else -1.0
    top = abs(x1 - x0)
    ax = Vector(axis).normalized()
    ac = Vector((-ax.y, ax.x))                          # across the width
    ys, zs = [q[0] for q in pts], [q[1] for q in pts]
    inner = []
    gy = min(ys)
    while gy <= max(ys):
        gz = min(zs)
        while gz <= max(zs):
            P = Vector((gy, gz))
            hits = _seg_hits(pts, P, Vector((1.0, 0.0)))
            if sum(1 for s in hits if s > 0) % 2 == 1:
                d_edge = min((P - (Vector(pts[i]) + (Vector(pts[(i + 1) % len(pts)]) - Vector(pts[i])) * max(0.0, min(1.0, (P - Vector(pts[i])).dot(Vector(pts[(i + 1) % len(pts)]) - Vector(pts[i])) / max(1e-12, (Vector(pts[(i + 1) % len(pts)]) - Vector(pts[i])).length_squared))))).length for i in range(len(pts)))
                if d_edge > 0.4 * grid_cm:
                    inner.append([gy, gz])
            gz += grid_cm
        gy += grid_cm
    verts2 = [Vector(q) for q in pts] + [Vector(q) for q in inner]
    nb = len(pts)
    edges = [(i, (i + 1) % nb) for i in range(nb)]
    vo, eo, fo, _ov, _oe, _of = delaunay_2d_cdt(verts2, edges, [], 2, 1e-7)    # 2: the faces inside the outline

    # the arch across the width: the thickness at a point depends on its distance d to the nearest LONG edge (an
    # outline edge within 35 degrees of the long axis): a circular arch from edge_cm at d = 0 to the full thickness at
    # d = w/2 (w the part's widest span across the long axis). The short end edges stay full thickness (their round
    # comes from the part's edge bevel), as the drawing's end views show.
    nb_ = len(pts)
    long_e = []
    for i_ in range(nb_):
        A_, B_ = Vector(pts[i_]), Vector(pts[(i_ + 1) % nb_])
        e_ = B_ - A_
        if e_.length > 1e-9 and abs(e_.normalized().dot(ax)) >= math.cos(math.radians(35.0)):
            long_e.append((A_, B_))
    across = [Vector(q).dot(ac) for q in pts]
    w_full = max(across) - min(across)
    h_ = top - edge_cm
    half_w = w_full / 2.0
    R_ = (half_w * half_w + h_ * h_) / (2.0 * h_) if h_ > 1e-9 else 1e9

    def dist_long(P):
        best = 1e9
        for A_, B_ in long_e:
            e_ = B_ - A_
            s_ = max(0.0, min(1.0, (P - A_).dot(e_) / e_.length_squared))
            best = min(best, (P - (A_ + e_ * s_)).length)
        return best

    def height(q):
        if h_ <= 1e-9 or not long_e:
            return top
        d_ = min(dist_long(Vector((q.x, q.y))), half_w)
        x_ = half_w - d_                                   # distance from the arch's middle
        return edge_cm + max(0.0, math.sqrt(max(0.0, R_ * R_ - x_ * x_)) - (R_ - h_))
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    top_v = [bm.verts.new(g(x0 + sgn * height(q), q.x, q.y)) for q in vo]
    # the flat inside face needs no grid: one face round the outline, its points shared with the walls
    bot_by = {}
    for i, q in enumerate(vo):
        key = (round(q.x, 6), round(q.y, 6))
        if any(abs(q.x - pp[0]) < 1e-6 and abs(q.y - pp[1]) < 1e-6 for pp in pts):
            bot_by[i] = bm.verts.new(g(x0, q.x, q.y))
    for f in fo:
        bm.faces.new([top_v[i] for i in f])
    # the wall round the rim: the triangulation's boundary edges (used by one face), each a quad between the faces
    use = {}
    for f in fo:
        for i in range(len(f)):
            e = (f[i], f[(i + 1) % len(f)])
            k = tuple(sorted(e))
            use.setdefault(k, []).append(e)
    rim = []
    for k, es in use.items():
        if len(es) == 1:
            a_, b_ = es[0]
            bm.faces.new([top_v[b_], top_v[a_], bot_by[a_], bot_by[b_]])
            rim.append((a_, b_))
    # the inside face: the rim's loop, in order
    nxt = {a_: b_ for a_, b_ in rim}
    loop, cur = [], rim[0][0]
    for _ in range(len(rim)):
        loop.append(cur)
        cur = nxt[cur]
    bm.faces.new([bot_by[i] for i in reversed(loop)])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _span(outline, y):
    """Where the line at y crosses a closed outline (y, v): the lowest and highest v, or None."""
    vs = []
    n = len(outline)
    for i in range(n):
        (y0, v0), (y1, v1) = outline[i][:2], outline[(i + 1) % n][:2]
        if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
            vs.append(v0 + (v1 - v0) * (y - y0) / (y1 - y0))
    return (min(vs), max(vs)) if len(vs) >= 2 else None


def _ring(outline, n):
    """A section outline (x, z) as n points evenly spaced along it, counter-clockwise, starting at its lowest point
    nearest its middle, in its own box: u from -1 to 1 across, v from 0 to 1 up."""
    pts = [tuple(q[:2]) for q in outline]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    if area < 0:
        pts.reverse()
    xs, zs = [q[0] for q in pts], [q[1] for q in pts]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    xm = (x0 + x1) / 2.0
    k0 = min(range(len(pts)), key=lambda i: (round(pts[i][1] - z0, 4) > 0.05 * (z1 - z0), abs(pts[i][0] - xm)))
    pts = pts[k0:] + pts[:k0]
    seg = [math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    L = sum(seg)
    out, acc, i = [], 0.0, 0
    for k in range(n):
        t = L * k / n
        while acc + seg[i] < t:
            acc += seg[i]
            i += 1
        f = (t - acc) / seg[i] if seg[i] else 0.0
        a, b = pts[i], pts[(i + 1) % len(pts)]
        x, z = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        out.append(((x - xm) / ((x1 - x0) / 2.0), (z - z0) / (z1 - z0)))
    return out


def loft(name, sh):
    """A part skinned through its cross-sections: at every station along y (every step_cm) the side outline gives
    its bottom and top, the top outline its two sides, and the key sections (each in its own box) its shape, blended
    between the two nearest by a smooth step. Rings of ring_points points, joined by quads, the two ends closed."""
    n = int(sh.get("ring_points", 72))
    step = float(sh.get("step_cm", 0.3))
    keys = sorted(((float(s_["y"]), _ring(s_["outline"], n)) for s_ in sh["sections"]), key=lambda t: t[0])
    ys = [q[0] for q in sh["side"]]
    y_lo, y_hi = min(ys), max(ys)
    m = max(2, int(math.ceil((y_hi - y_lo) / step)) + 1)
    stations = [y_lo + (y_hi - y_lo) * k / (m - 1) for k in range(m)]
    stations[0] += 1e-4
    stations[-1] -= 1e-4
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for y in stations:
        zz = _span(sh["side"], y)
        xx = _span(sh["top"], y)
        if not zz or not xx:
            continue
        if y <= keys[0][0]:
            shape = keys[0][1]
        elif y >= keys[-1][0]:
            shape = keys[-1][1]
        else:
            j = max(i for i in range(len(keys)) if keys[i][0] <= y)
            (ya, A), (yb, B) = keys[j], keys[j + 1]
            t = (y - ya) / (yb - ya)
            t = t * t * (3.0 - 2.0 * t)
            shape = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for a, b in zip(A, B)]
        xm, hw = (xx[0] + xx[1]) / 2.0, (xx[1] - xx[0]) / 2.0
        rings.append([bm.verts.new(g(xm + u * hw, y, zz[0] + v * (zz[1] - zz[0]))) for u, v in shape])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def sweep_prism(name, outline, a, b, ext=0.2):
    """A prism along the side-view line a -> b (y, z), extended ext cm past both ends, its cross-section the outline in
    (u, x): u along the line's normal in the side view (the direction turned +90 degrees), x across the gun."""
    A, B = Vector((a[0], a[1])), Vector((b[0], b[1]))
    d = (B - A).normalized()
    n = Vector((-d.y, d.x))
    A, B = A - d * ext, B + d * ext
    pts = ccw([q[:2] for q in outline])
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    ra = [bm.verts.new(g(x, A.x + n.x * u, A.y + n.y * u)) for u, x in pts]
    rb = [bm.verts.new(g(x, B.x + n.x * u, B.y + n.y * u)) for u, x in pts]
    k = len(pts)
    bm.faces.new(list(reversed(ra)))
    bm.faces.new(rb)
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new([ra[i], ra[j], rb[j], rb[i]])
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
    if ft["kind"] in ("knurl", "crown"):            # shaped after the edges are rounded (see the part loop)
        return
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


FACE_DIR = {"left": Vector((1.0, 0.0, 0.0)), "right": Vector((-1.0, 0.0, 0.0)), "top": Vector((0.0, 0.0, 1.0)),
            "front": Vector((0.0, -1.0, 0.0)), "rear": Vector((0.0, 1.0, 0.0))}          # Blender frame (y flipped)


def knurl(ob, ft):
    """V grooves (90 degrees included) pressed into the faces of ob that face ft["face"] (within 50 degrees), inside its
    y/z region and its border: the faces refined to a quarter pitch, each vertex moved in along its normal by the
    groove depth there. Diamond: two line families at +- angle_deg to the face's long direction; straight: one family.
    The face's own 2D coordinates: across x and up z for front/rear, y and z for left/right, y and x for top."""
    faces = ["left", "right"] if ft["face"] == "both" else [ft["face"]]
    pitch, depth = ft["pitch_cm"] / 100.0, ft["depth_cm"] / 100.0
    border = ft.get("border_cm", 0.0) / 100.0
    ang = math.radians(ft.get("angle_deg", 45.0 if ft["pattern"] == "diamond" else 0.0))
    yr = [v / 100.0 for v in ft["y"]] if ft.get("y") else None
    zr = [v / 100.0 for v in ft["z"]] if ft.get("z") else None
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    cosl = math.cos(math.radians(50.0))

    def in_region(co):
        gy = -co.y
        if yr and not (yr[0] + border <= gy <= yr[1] - border):
            return False
        if zr and not (zr[0] + border <= co.z <= zr[1] - border):
            return False
        return True
    for face in faces:
        fd = FACE_DIR[face]
        sel = [f for f in bm.faces if f.normal.dot(fd) >= cosl and in_region(f.calc_center_median())]
        if not sel:
            continue
        # refine: split the selected faces' edges until none is longer than a quarter pitch
        for _ in range(8):
            edges = {e for f in sel for e in f.edges if e.calc_length() > pitch / 2.8}   # a quarter-pitch grid's diagonals pass
            if not edges:
                break
            res = bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=1, use_grid_fill=True)
            bm.normal_update()
            sel = [f for f in bm.faces if f.normal.dot(fd) >= cosl and in_region(f.calc_center_median())]
        verts = {v for f in sel for v in f.verts if in_region(v.co)}
        if border > 0:
            # the plain band: no groove within border of the knurled face's own edge (its edges used by one face of it)
            from mathutils.kdtree import KDTree
            sel_set = set(sel)
            rim = {v for f in sel for e in f.edges if sum(1 for lf in e.link_faces if lf in sel_set) == 1 for v in e.verts}
            if rim:
                kd = KDTree(len(rim))
                for i_, v in enumerate(rim):
                    kd.insert(v.co, i_)
                kd.balance()
                verts = {v for v in verts if kd.find(v.co)[2] >= border}
        skips = [(q[0] / 100.0, q[1] / 100.0, q[2] / 100.0) for q in ft.get("skip", [])]
        if skips:
            verts = {v for v in verts if all((-v.co.y - sy) ** 2 + (v.co.z - sz) ** 2 >= sr * sr for sy, sz, sr in skips)}
        rot = math.radians(ft.get("rotate_deg", 0.0))
        dirs = [(math.cos(rot + ang), math.sin(rot + ang))]
        if ft["pattern"] == "diamond":
            dirs.append((math.cos(rot - ang), math.sin(rot - ang)))
        for v in verts:
            if face in ("front", "rear"):
                a_, b_ = v.co.x, v.co.z
            elif face == "top":
                a_, b_ = -v.co.y, v.co.x
            else:
                a_, b_ = -v.co.y, v.co.z
            cut = 0.0
            for cx, cy in dirs:
                s_ = -a_ * cy + b_ * cx                    # distance across the line family
                fr = (s_ / pitch) % 1.0
                dist = min(fr, 1.0 - fr) * pitch           # to the nearest groove's centre line
                cut = max(cut, depth - dist)               # a 90 degree V: one deeper for one nearer
            if cut > 0:
                nrm = v.normal if v.normal.length > 1e-9 else fd
                v.co -= nrm.normalized() * cut
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def crown(ob, ft):
    """The faces of ob facing ft["face"] (within 50 degrees), inside its y/z region, curved across the part's width to
    the radius r_cm: the faces refined to 0.05 cm across x, each point moved in along the face's direction by
    r - sqrt(r^2 - (x - x_mid)^2), x_mid the faces' middle across."""
    r = ft["r_cm"] / 100.0
    fd = FACE_DIR[ft["face"]]
    yr = [v / 100.0 for v in ft["y"]] if ft.get("y") else None
    zr = [v / 100.0 for v in ft["z"]] if ft.get("z") else None
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    cosl = math.cos(math.radians(50.0))

    def ok(co):
        if yr and not (yr[0] <= -co.y <= yr[1]):
            return False
        return not (zr and not (zr[0] <= co.z <= zr[1]))
    sel = [f for f in bm.faces if f.normal.dot(fd) >= cosl and ok(f.calc_center_median())]
    for _ in range(8):
        edges = {e for f in sel for e in f.edges if abs(e.verts[0].co.x - e.verts[1].co.x) > 0.0005}
        if not edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=1, use_grid_fill=True)
        bm.normal_update()
        sel = [f for f in bm.faces if f.normal.dot(fd) >= cosl and ok(f.calc_center_median())]
    verts = {v for f in sel for v in f.verts}
    if verts:
        xs = [v.co.x for v in verts]
        xm = (min(xs) + max(xs)) / 2.0
        for v in verts:
            dx = min(abs(v.co.x - xm), r)
            v.co -= fd * (r - math.sqrt(max(0.0, r * r - dx * dx)))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def union(ob, other):
    mod = ob.modifiers.new("add", 'BOOLEAN')
    mod.operation = 'UNION'
    mod.solver = 'EXACT'
    mod.use_self = True              # operands may overlap themselves (joined sections, crossing grooves)
    mod.use_hole_tolerant = True
    mod.object = other
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(other)


def intersect(ob, other):
    before = len(ob.data.vertices)
    mod = ob.modifiers.new("keep", 'BOOLEAN')
    mod.operation = 'INTERSECT'
    mod.solver = 'EXACT'
    mod.use_self = True              # operands may overlap themselves (joined sections, crossing grooves)
    mod.use_hole_tolerant = True
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
    mod.use_self = True              # operands may overlap themselves (joined sections, crossing grooves)
    mod.use_hole_tolerant = True
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
            elif h["kind"] == "sweep":
                cut = sweep_prism("%s_hole%d" % (pid, k), h["outline"], h["from"], h["to"])
            elif h["kind"] == "polygon":
                cut = prism("%s_hole%d" % (pid, k), h["outline"], hx[0], hx[1])
            else:
                (y, z), r = h["at"], h["r"]
                cut = prism("%s_hole%d" % (pid, k), [[y + r * math.cos(2 * math.pi * t / SEG), z + r * math.sin(2 * math.pi * t / SEG)] for t in range(SEG)], hx[0], hx[1])
            boolean(ob, cut)
    elif sh["kind"] == "loft":
        ob = loft(pid, sh)
        x0, x1 = sorted(sh["x"])
        print("BLUEPRINT STEP %s (loft): %d vertices, %d faces" % (pid, len(ob.data.vertices), len(ob.data.polygons)))
        for k, h in enumerate(p.get("holes", [])):
            hx = h.get("x") or [x0 - 1.0, x1 + 1.0]
            if h["kind"] == "polygon":
                cut = prism("%s_hole%d" % (pid, k), h["outline"], hx[0], hx[1])
            elif h["kind"] == "bore":
                cut = lathe("%s_hole%d" % (pid, k), [[h["y"][0], h["r"]], [h["y"][1], h["r"]]], h["at"][0], h["at"][1])
            else:
                (y, z), r = h["at"], h["r"]
                cut = prism("%s_hole%d" % (pid, k), [[y + r * math.cos(2 * math.pi * t_ / SEG), z + r * math.sin(2 * math.pi * t_ / SEG)] for t_ in range(SEG)], hx[0], hx[1])
            boolean(ob, cut)
    elif sh["kind"] == "relief":
        grid_ = max(sh.get("grid_cm", 0.08), 0.08) if PLAIN else sh.get("grid_cm", 0.08)
        ob = relief(pid, sh["side"], sh["x"], sh["edge_cm"], sh["axis"], grid_)
        x0, x1 = sorted(sh["x"])
        if sh.get("both"):
            ob2 = relief(pid + "_mirror", sh["side"], [-sh["x"][0], -sh["x"][1]], sh["edge_cm"], sh["axis"], grid_)
            ob = join([ob, ob2], pid)
            x0, x1 = -x1, x1
        print("BLUEPRINT STEP %s (relief): %d vertices, %d faces" % (pid, len(ob.data.vertices), len(ob.data.polygons)))
        for k, h in enumerate(p.get("holes", [])):
            hx = h.get("x") or [x0 - 1.0, x1 + 1.0]
            if h["kind"] == "polygon":
                cut = prism("%s_hole%d" % (pid, k), h["outline"], hx[0], hx[1])
            else:
                (y, z), r = h["at"], h["r"]
                cut = prism("%s_hole%d" % (pid, k), [[y + r * math.cos(2 * math.pi * t_ / SEG), z + r * math.sin(2 * math.pi * t_ / SEG)] for t_ in range(SEG)], hx[0], hx[1])
            boolean(ob, cut)
    else:
        ob = lathe(pid, sh["profile"], sh["axis"][0], sh["axis"][1], sh.get("bore_r"))
        for k, h in enumerate(p.get("holes", [])):          # a turned part takes bores only (a chamber, a counterbore)
            if h["kind"] != "bore":
                raise SystemExit("BLUEPRINT BUILD FAILED: %s is turned (lathe): its holes must be bores, not %s" % (pid, h["kind"]))
            boolean(ob, lathe("%s_hole%d" % (pid, k), [[h["y"][0], h["r"]], [h["y"][1], h["r"]]], h["at"][0], h["at"][1]))
    for k, ft in enumerate(p.get("features", [])):
        feature(ob, pid, k, ft, report["textures"])
    if p.get("bevel_cm"):
        # the edges rounded to the drawing's (or the source's) radius: a round arc (profile 0.5), one segment for
        # every 0.02 cm of radius, at least 3, so the round reads as a curve, not a chamfer
        mod = ob.modifiers.new("bevel", 'BEVEL')
        mod.width = p["bevel_cm"] / 100.0
        mod.segments = max(3, int(math.ceil(p["bevel_cm"] / 0.02)))
        mod.profile = 0.5
        mod.limit_method = 'ANGLE'
        mod.harden_normals = True
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for ft in p.get("features", []):                # crowns first: a knurl then follows the curved face
        if ft["kind"] == "crown":
            crown(ob, ft)
    for ft in p.get("features", []):
        if ft["kind"] == "knurl" and not PLAIN:
            knurl(ob, ft)
            report["textures"].append({"part": pid, "pattern": ft["pattern"], "face": ft["face"], "pitch_cm": ft["pitch_cm"], "geometry": True})
    # smooth shading on the curved faces, flat faces kept crisp (faces meeting under 30 degrees shade as one)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    try:
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.shade_auto_smooth(angle=math.radians(30.0))
        ob.select_set(False)
    except Exception as e_:                       # an older Blender without the operator: smooth shading only
        print("BLUEPRINT NOTE auto smooth: %s" % e_)
    ob.data.materials.clear()                     # the cuts bring their cutters' empty slots: one finish a part
    tx = next((ft for ft in p.get("features", []) if ft["kind"] == "texture" and ft["pattern"] in ("stippling", "knurling", "checkering")), None)
    ob.data.materials.append(material_textured(p["finish"], tx["pattern"], float(tx.get("pitch_cm") or 0.08)) if tx and not PLAIN else material(p["finish"]))
    for poly in ob.data.polygons:
        poly.material_index = 0
    ob["role"] = p["role"]
    ob["finish"] = p["finish"]
    ob.data.validate()
    lo = Vector((min(v.co.x for v in ob.data.vertices), min(v.co.y for v in ob.data.vertices), min(v.co.z for v in ob.data.vertices)))
    hi = Vector((max(v.co.x for v in ob.data.vertices), max(v.co.y for v in ob.data.vertices), max(v.co.z for v in ob.data.vertices)))
    _bm = bmesh.new()
    _bm.from_mesh(ob.data)
    _health = {"nonmanifold_edges": sum(1 for e in _bm.edges if not e.is_manifold),
               "signed_volume_cm3": round(_bm.calc_volume(signed=True) * 1e6, 3)}
    _bm.free()
    # a sound solid: every edge on two faces, its faces turned out (a positive volume)
    _health["sound"] = _health["nonmanifold_edges"] == 0 and _health["signed_volume_cm3"] > 0
    report["parts"][pid] = {"role": p["role"], "vertices": len(ob.data.vertices), "faces": len(ob.data.polygons), "mesh": _health,
                            "bounds_cm": {"x": [round(lo.x * 100, 3), round(hi.x * 100, 3)], "y": [round(-hi.y * 100, 3), round(-lo.y * 100, 3)],
                                          "z": [round(lo.z * 100, 3), round(hi.z * 100, 3)]}}
blend = os.path.join(OUT, "%s%s.blend" % (bp["name"], "_plain" if PLAIN else ""))
bpy.ops.wm.save_as_mainfile(filepath=blend)
report["blend"] = blend
report["rounds_cut_to_fit"] = ROUND_NOTES
with open(os.path.join(OUT, "build_plain.json" if PLAIN else "build.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)
print("BLUEPRINT BUILD " + json.dumps({"parts": len(report["parts"]), "blend": blend}))
