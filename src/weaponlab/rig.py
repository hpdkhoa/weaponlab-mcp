"""Rig Lab: reads a weapon as the game poses it, from the probe's parts dumps (docs/PROBE_CONTRACT.md). Plain Python
and numpy; Blender only renders (blender/render_parts.py).

- pieces: each group split into its connected pieces, each described (triangles, centre, bounds, principal extents).
- facts: the spec's real-world facts (order along the barrel, side, below, in) on the spec's anchors.
- align: a magazine's line into its well over a reload's moments.
- part_line: a sliding part's path against its axis.
- fist: a melee hilt against the closed fist's grip channel, and the hold that lays it in.
- measure: the Gate's rows from fresh dumps (the provider "rig")."""
import math
from pathlib import Path

import numpy as np

from . import contract as C
from . import spec as S
from .config import project


# ------------------------------------------------------------------ pieces
def _tris(group):
    v = np.array(group["verts"], dtype=float)
    return [(v[a], v[b], v[c]) for a, b, c in group["tris"]]


def split(tris, weld=0.02):
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
    pts = np.array([p for t in tris for p in t])
    c = pts.mean(0)
    area = sum(float(np.linalg.norm(np.cross(t[1] - t[0], t[2] - t[0]))) / 2.0 for t in tris)
    a = pts - c
    w, v = np.linalg.eigh(np.cov(a.T)) if len(a) > 3 else (np.zeros(3), np.eye(3))
    proj = a @ v
    ext = sorted((proj.max(0) - proj.min(0)).tolist(), reverse=True)
    return {"triangles": len(tris), "center": [round(float(x), 2) for x in c], "min": [round(float(x), 2) for x in pts.min(0)],
            "max": [round(float(x), 2) for x in pts.max(0)], "area_cm2": round(area, 1), "extents": [round(x, 2) for x in ext],
            "long_axis": [round(float(x), 3) for x in v[:, int(np.argmax(w))]]}


def pieces(obj):
    """Every piece of a parts dump, with its role, component, asset and bone, and the twins (the same shape drawn
    twice: a magazine copied)."""
    d = C.read_parts(obj)
    out = []
    for (role, comp, asset, bone), g in d["groups"].items():
        if role == "arms":
            continue
        for p in split(_tris(g)):
            out.append(dict(describe(p), role=role, component=comp, asset=asset, bone=bone))
    return {"pieces": out, "eye": d["eye"], "header": d["header"], "twins": twins(out)}


def twins(items, tol=0.06):
    groups = []
    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            b = items[j]
            if a["triangles"] == b["triangles"] and a["triangles"] > 20 and all(abs(x - y) <= tol * max(x, y, 0.5) for x, y in zip(a["extents"], b["extents"])):
                groups.append([i, j])
    return groups


# ------------------------------------------------------------------ facts
def find_all(pcs, anchor):
    out = []
    for p in pcs:
        if anchor.get("component") and p["component"] != anchor["component"]:
            continue
        if anchor.get("role") and p["role"] != anchor["role"]:
            continue
        if p["triangles"] != anchor["triangles"]:
            continue
        if all(abs(a - b) <= 0.06 * max(a, b, 0.5) for a, b in zip(p["extents"], anchor["extents"])):
            out.append(p)
    return out


def find_piece(pcs, anchor):
    hits = find_all(pcs, anchor)
    return hits[0] if hits else None


def facts(weapon, obj):
    """The spec's facts on one dump: rows facts.false and parts.duplicates, and each fact's result."""
    sp = S.read_spec(weapon)
    anchors = sp.get("anchors", {})
    pcs = pieces(obj)["pieces"]
    found = {k: find_piece(pcs, a) for k, a in anchors.items()}
    false, notes = 0, []
    for f in sp.get("facts", []):
        c = f.get("check", {})
        kind = c.get("kind")
        if kind == "order":
            a, b = found.get(c["ahead"]), found.get(c["behind"])
            ok = a is not None and b is not None and a["center"][1] > b["center"][1]
        elif kind == "side":
            a = found.get(c["anchor"])
            ok = a is not None and (a["center"][0] > 0.2 if c["side"] == "left" else a["center"][0] < -0.2)
        elif kind == "below":
            a, b = found.get(c["anchor"]), found.get(c["under"])
            ok = a is not None and b is not None and a["max"][2] <= b["min"][2] + c.get("overlap_cm", 1.0)
        elif kind == "in":
            a, b = found.get(c["anchor"]), found.get(c["into"])
            ok = a is not None and b is not None and all(b["min"][i] - 1.0 <= a["max"][i] and a["min"][i] <= b["max"][i] + 1.0 for i in range(3))
        else:
            continue
        if not ok:
            false += 1
        notes.append("%s: %s" % (f["id"], "holds" if ok else "FALSE"))
    dup = sum(max(0, len(find_all(pcs, a)) - 1) for a in anchors.values() if a.get("unique"))
    return {"facts.false": false, "parts.duplicates": dup, "notes": notes}


# ------------------------------------------------------------------ lines
def read_group(obj, bone):
    """The vertices of one bone's groups in a dump, in the order written (the same mesh gives the same order)."""
    d = C.read_parts(obj)
    return [v for k, g in d["groups"].items() if k[3] == bone for v in g["verts"]]


def align(seated_obj, moment_objs, bone, well_depth_cm=4.0, axis=None, column_cm=3.0):
    """The magazine against its seat: each moment's magazine fitted rigidly onto the seated one. While its top is in
    the well (within well_depth_cm down and column_cm across), its sideways offset (cm) and tilt (deg) from the seated
    line should be nil. Returns the worst of each and each moment's numbers."""
    A = np.array(read_group(seated_obj, bone))
    if len(A) < 4:
        return None
    ca = A.mean(0)
    w, v = np.linalg.eigh(np.cov((A - ca).T))
    ax = v[:, int(np.argmax(w))]
    if ax[2] < 0:
        ax = -ax
    h = (A - ca) @ ax
    hi = h.max()
    upper, lower = A[h > hi - 1.0], A[(h < hi - 4.0) & (h > hi - 6.0)]
    if len(upper) >= 3 and len(lower) >= 3:          # a curved magazine: its straight top's line
        ax = upper.mean(0) - lower.mean(0)
        ax /= np.linalg.norm(ax)
    if axis is not None:                             # the well's own axis (the spec's)
        ax = np.array(axis, dtype=float)
        ax /= np.linalg.norm(ax)
    top = ca + ax * ((A - ca) @ ax).max()
    rows, worst_off, worst_ang = [], 0.0, 0.0
    for obj in moment_objs:
        B = np.array(read_group(obj, bone))
        if len(B) != len(A):
            rows.append({"moment": Path(obj).stem, "note": "not drawn"})
            continue
        cb = B.mean(0)
        U, _s, Vt = np.linalg.svd((A - ca).T @ (B - cb))
        d = np.sign(np.linalg.det(Vt.T @ U.T))
        R = Vt.T @ np.diag([1, 1, d]) @ U.T
        disp = R @ (top - ca) + cb - top
        down = -float(disp @ ax)
        lateral = float(np.linalg.norm(disp + ax * down))
        ang = float(np.degrees(np.arccos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))))
        inside = down < well_depth_cm and lateral < column_cm
        rows.append({"moment": Path(obj).stem, "down_cm": round(down, 2), "sideways_cm": round(lateral, 2), "tilt_deg": round(ang, 2), "in_well": inside})
        if inside:
            worst_off, worst_ang = max(worst_off, lateral), max(worst_ang, ang)
    return {"offset_cm": round(worst_off, 2), "angle_deg": round(worst_ang, 2), "moments": rows}


def part_line(seated_obj, moment_objs, bone, axis):
    """A sliding part's path against its axis. line_cm: the most any moment strays from the path's middle offset;
    seat_cm: that middle offset against the seat's (a jump off the seat as the action starts)."""
    a = np.array(axis, dtype=float)
    a /= np.linalg.norm(a)

    def across(obj):
        pts = read_group(obj, bone)
        if len(pts) < 3:
            return None
        c = np.array(pts).mean(0)
        return c - a * (c @ a)
    seat = across(seated_obj)
    offs = [x for x in (across(o) for o in moment_objs) if x is not None]
    if seat is None or not offs:
        return None
    mid = np.median(np.array(offs), axis=0)
    return {"line_cm": round(max(float(np.linalg.norm(o - mid)) for o in offs), 2), "seat_cm": round(float(np.linalg.norm(mid - seat)), 2)}


# ------------------------------------------------------------------ the fist
GRIP_CM = 5.5


def _rot_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else -np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k * (1.0 / (1.0 + c))


def rotator(m):
    """A rotation matrix as Unreal's FRotator [pitch, yaw, roll] (FQuat's own conversion)."""
    w = math.sqrt(max(0.0, 1.0 + m[0, 0] + m[1, 1] + m[2, 2])) / 2.0
    x = (m[2, 1] - m[1, 2]) / (4 * w)
    y = (m[0, 2] - m[2, 0]) / (4 * w)
    z = (m[1, 0] - m[0, 1]) / (4 * w)
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, 2 * (z * x - w * y)))))
    yaw = math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
    roll = math.degrees(math.atan2(-2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
    return [round(pitch, 3), round(yaw, 3), round(roll, 3)]


def fist(obj, side="r"):
    """A one-hand weapon's hilt against the closed fist. The grip channel runs between the palm and the curled middle
    finger, along the knuckles (little finger to index); a hilt held right lies in it, the blade out on the index
    side. Returns offset_cm and angle_deg (0 and 0 when it lies in), and the turn and offset in gun space that would
    lay it in: rot (3x3, and as an Unreal rotator) and move_cm (add it to the model's offset on the hand)."""
    d = C.read_parts(obj)
    bone = lambda b: next((np.array(g["verts"]) for k, g in d["groups"].items() if k[0] == "arms" and k[3] == b), None)
    parts = [b + "_" + side for b in ("hand", "middle_01", "middle_02", "middle_03")]
    if any(bone(b) is None for b in parts + ["index_01_" + side, "pinky_01_" + side]):
        return None
    channel = np.mean([bone(b).mean(0) for b in parts], axis=0)
    across = bone("index_01_" + side).mean(0) - bone("pinky_01_" + side).mean(0)
    across /= np.linalg.norm(across)
    model = np.vstack([np.array(g["verts"]) for k, g in d["groups"].items() if k[0] in ("gun", "part")])
    c = model.mean(0)
    w, vec = np.linalg.eigh(np.cov((model - c).T))
    axis = vec[:, int(np.argmax(w))]
    h = (model - c) @ axis
    ends = [c + axis * h.min(), c + axis * h.max()]
    pommel = min(ends, key=lambda e: np.linalg.norm(e - channel))
    out_dir = axis if (ends[1] - pommel) @ axis > 0 else -axis
    grip = pommel + out_dir * GRIP_CM
    dv = grip - channel
    off = float(np.linalg.norm(dv - across * (dv @ across)))
    ang = math.degrees(math.acos(min(1.0, abs(float(out_dir @ across)))))
    # a short knife's two ends both lie by the palm and its blade end can read reversed: under 20 degrees only moves
    R = _rot_between(out_dir, across) if ang > 20.0 else np.eye(3)
    move = channel - R @ grip          # the hand stays; the model turns by R and moves by this
    return {"offset_cm": round(off, 2), "angle_deg": round(ang, 1), "rot": R.round(5).tolist(), "rotator": rotator(R),
            "move_cm": move.round(2).tolist(), "channel": channel.round(2).tolist(), "grip": grip.round(2).tolist()}


# ------------------------------------------------------------------ the Gate's provider
def measure(weapon_ids, actions=None, staging=None):
    """Rows from fresh idle dumps: facts.false and parts.duplicates for each weapon with anchors in its spec,
    fist.offset_cm and fist.angle_deg for each melee weapon held by hands, align.* for each spec with align."""
    from . import gate as G
    from . import probe as P
    kinds = {w["id"]: w.get("kind") for w in G.weapons()}
    want = [w for w in weapon_ids if kinds.get(w) == "Melee" or S.path_of(w).exists()]
    if not want:
        return []
    folder = project().ensure("rig", "dumps", __import__("time").strftime("%Y%m%d-%H%M%S"))
    P.run(want, ["idle"], at={"idle": [1.2]}, staging=staging, parts=folder)
    rows = []
    for w in want:
        obj = folder / C.parts_name(w, "idle", 1.2)
        if not obj.exists():
            continue
        if S.path_of(w).exists() and S.read_spec(w).get("anchors"):
            f = facts(w, obj)
            rows += [{"weapon": w, "action": "idle", "metric": "facts.false", "value": f["facts.false"], "note": "; ".join(f["notes"])},
                     {"weapon": w, "action": "idle", "metric": "parts.duplicates", "value": f["parts.duplicates"]}]
        if kinds.get(w) == "Melee":
            m = fist(obj)
            if m:
                rows += [{"weapon": w, "action": "idle", "metric": "fist.offset_cm", "value": m["offset_cm"]},
                         {"weapon": w, "action": "idle", "metric": "fist.angle_deg", "value": m["angle_deg"]}]
    return rows
