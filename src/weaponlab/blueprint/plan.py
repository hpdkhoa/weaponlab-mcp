"""Step 4: the blueprint, written part by part. A part's outline comes from a kept trace (trace.save), clipped where
a line in another figure parts it from its neighbour, or turned into a lathe profile for a round part; its width
from a fact or a guess with its reason; its motion from the action, the facts or a figure. The tools fill in each
number's source as they go; a number given by hand needs its source given with it.

Polygon helpers work in the side view's (y, z), cm."""
import json
import math

from ..gunkit import actions as A
from . import store


def new(gun, action, title=None):
    """An empty blueprint for the gun (kept when one exists and has the same action)."""
    A.load(action)
    if store.exists(gun, "blueprint"):
        bp = store.load(gun, "blueprint")
        if bp["action"] != action:
            raise ValueError("%s's blueprint is for %s; remove it to start one for %s" % (gun, bp["action"], action))
        return bp
    src = store.load(gun, "sources")
    bp = {"contract": "weaponlab-blueprint/1", "name": gun, "title": title or src.get("title", gun), "action": action,
          "sources": str((store.root() / gun / "sources.json").resolve()), "parts": {}, "marks": {}, "mark_parts": {}}
    store.save(gun, "blueprint", bp, strict=False)
    return bp


def trace(gun, name):
    p = store.folder(gun, "figures") / ("%s.trace.json" % name)
    if not p.exists():
        raise FileNotFoundError("no kept trace %s (trace.save it first)" % name)
    t = json.loads(p.read_text(encoding="utf-8"))
    if "outline_cm" not in t:
        raise ValueError("trace %s was made before its figure had a scale and a frame" % name)
    return t


def clip(outline, axis, value, keep):
    """The part of a polygon on one side of a line: axis "y" or "z", keep "above" (more than value) or "below"."""
    i = {"y": 0, "z": 1}[axis]
    inside = (lambda p: p[i] >= value) if keep == "above" else (lambda p: p[i] <= value)
    out = []
    for k, a in enumerate(outline):
        b = outline[(k + 1) % len(outline)]
        if inside(a):
            out.append(list(a))
        if inside(a) != inside(b):
            t = (value - a[i]) / (b[i] - a[i])
            out.append([round(a[0] + (b[0] - a[0]) * t, 4), round(a[1] + (b[1] - a[1]) * t, 4)])
    return out


def clip_line(outline, p, q, keep="left"):
    """The part of a polygon on one side of the line from p to q (y, z): keep "left" or "right" of it, looking
    from p to q."""
    side = lambda a: (q[0] - p[0]) * (a[1] - p[1]) - (q[1] - p[1]) * (a[0] - p[0])   # noqa: E731
    inside = (lambda a: side(a) >= 0) if keep == "left" else (lambda a: side(a) <= 0)
    out = []
    for k, a in enumerate(outline):
        b = outline[(k + 1) % len(outline)]
        if inside(a):
            out.append(list(a))
        if inside(a) != inside(b):
            sa, sb = side(a), side(b)
            t = sa / (sa - sb)
            out.append([round(a[0] + (b[0] - a[0]) * t, 4), round(a[1] + (b[1] - a[1]) * t, 4)])
    return out


def edge_line(outline, z0, z1, front=True, y_max=None):
    """A straight fit to an outline's front (or rear) edge between two heights: at each height band the outline's
    frontmost (or rearmost) point; returns two points on the line, at z0 and z1, and the fit's worst miss in cm."""
    import numpy as np
    dense = []
    for a, c in zip(outline, outline[1:] + outline[:1]):           # points along every edge, not its corners alone
        n = max(1, int(np.hypot(c[0] - a[0], c[1] - a[1]) / 0.05))
        dense += [[a[0] + (c[0] - a[0]) * k / n, a[1] + (c[1] - a[1]) * k / n] for k in range(n)]
    pts = [p for p in dense if z0 <= p[1] <= z1 and (y_max is None or p[0] <= y_max)]
    bands = {}
    for y, z in pts:
        k = round(z / 0.25)
        if k not in bands or (y > bands[k][0] if front else y < bands[k][0]):
            bands[k] = (y, z)
    if len(bands) < 3:
        raise ValueError("too few outline points between z %.2f and %.2f" % (z0, z1))
    ys = np.array([v[0] for v in bands.values()])
    zs = np.array([v[1] for v in bands.values()])
    a, b = np.polyfit(zs, ys, 1)
    miss = float(np.abs(ys - (a * zs + b)).max())
    return [[round(float(a * z0 + b), 4), float(z0)], [round(float(a * z1 + b), 4), float(z1)]], round(miss, 3)


def fit_along(outline, line, inset_cm, bottom_z, front=True):
    """A part's outline turned so its long axis runs along a line (two points, y z), moved so its front (or rear)
    side lies inset_cm inside that line and its lowest point at bottom_z: a magazine set in a grip drawn in another
    figure."""
    import numpy as np
    P = np.array(outline, dtype=float)
    c = P.mean(axis=0)
    w, v = np.linalg.eigh(np.cov((P - c).T))
    d = v[:, int(np.argmax(w))]
    if d[1] < 0:
        d = -d
    t = np.array(line[1], dtype=float) - np.array(line[0], dtype=float)
    t = t / np.linalg.norm(t)
    if t[1] < 0:
        t = -t
    ang = np.arctan2(t[1], t[0]) - np.arctan2(d[1], d[0])
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    Q = (P - c) @ R.T + c
    n = np.array([t[1], -t[0]])                       # square to the line, toward +y (the front) for a line going up
    if n[0] < 0:
        n = -n
    l0 = np.array(line[0], dtype=float)
    off = (Q - l0) @ n
    target = -inset_cm if front else inset_cm
    # one move a*n + b*z that sets both: the side on its inset and the lowest point at bottom_z
    side = target - (off.max() if front else off.min())
    drop = bottom_z - Q[:, 1].min()
    a, b = np.linalg.solve(np.array([[1.0, n[1]], [n[1], 1.0]]), np.array([side, drop]))
    Q = Q + a * n + np.array([0.0, b])
    return [[round(float(y), 4), round(float(z), 4)] for y, z in Q], round(float(np.degrees(ang)), 2)


def box(outline):
    ys, zs = [p[0] for p in outline], [p[1] for p in outline]
    return {"y": [min(ys), max(ys)], "z": [min(zs), max(zs)]}


def area(outline):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(outline, outline[1:] + outline[:1]))) / 2.0


def lathe_profile(outline, axis_z, step_cm=0.25):
    """A round part's profile (y, r) from its side outline: at each y, r is the outline's greatest distance from
    the axis line (z = axis_z)."""
    b = box(outline)
    n = max(2, int((b["y"][1] - b["y"][0]) / step_cm) + 1)
    prof = []
    for k in range(n):
        y = b["y"][0] + (b["y"][1] - b["y"][0]) * k / (n - 1)
        zs = []
        for a, c in zip(outline, outline[1:] + outline[:1]):
            if (a[0] - y) * (c[0] - y) <= 0 and a[0] != c[0]:
                t = (y - a[0]) / (c[0] - a[0])
                zs.append(a[1] + (c[1] - a[1]) * t)
        if zs:
            prof.append([round(y, 4), round(max(abs(z - axis_z) for z in zs), 4)])
    return prof


def _save(gun, bp):
    store.save(gun, "blueprint", bp, strict=False)
    return bp


def part(gun, part_id, role, finish, shape, sources, name=None, motion=None, bevel_cm=None, parent=None, holes=None):
    """Sets one part. shape and sources as the contract has them (plan.extrude and plan.lathe build them from traces)."""
    bp = store.load(gun, "blueprint")
    p = {"role": role, "shape": shape, "finish": finish, "sources": sources}
    for k, v in (("name", name), ("motion", motion), ("bevel_cm", bevel_cm), ("parent", parent), ("holes", holes)):
        if v is not None:
            p[k] = v
    bp["parts"][part_id] = p
    return _save(gun, bp)["parts"][part_id]


def extrude(gun, part_id, role, finish, trace_name, x, x_source, clips=(), name=None, motion=None, motion_sources=None,
            bevel_cm=None, parent=None, outline=None, outline_source=None):
    """A part cut from a side outline and run across x = [x0, x1] (the gun's right to its left). clips: (axis, value,
    keep, why) lines that part it from its neighbours; each one's why goes into the outline's source."""
    t = trace(gun, trace_name) if trace_name else {"figure": None, "method": "traced", "outline_cm": outline}
    out = outline if outline is not None else t["outline_cm"]
    notes = []
    for axis, value, keep, why in clips:
        if axis == "line":
            out = clip_line(out, value[0], value[1], keep)
            notes.append("kept %s of the line %s to %s (%s)" % (keep, value[0], value[1], why))
        else:
            out = clip(out, axis, value, keep)
            notes.append("kept %s %s=%.3f (%s)" % (keep, axis, value, why))
    if len(out) < 3:
        raise ValueError("the clips leave nothing of trace %s" % trace_name)
    if outline_source is not None:
        ref = dict(outline_source)
        if notes:
            key = "note" if ("figure" in ref or "fact" in ref) else next(iter(ref))
            ref[key] = (ref.get(key, "") + "; " if ref.get(key) else "") + "; ".join(notes)
    else:
        ref = {"figure": t["figure"], "method": t["method"] if t["method"] in ("traced", "snapped", "read") else ("snapped" if t["method"] == "snap" else "traced")}
        if notes:
            ref["note"] = "; ".join(notes)
    sources = {"outline": ref, "x": x_source}
    sources.update(motion_sources or {})
    if bevel_cm:
        sources.setdefault("bevel_cm", {"guess": "a small round on the edges, as machined parts have"})
    return part(gun, part_id, role, finish, {"kind": "extrude", "outline": out, "x": [float(x[0]), float(x[1])]}, sources,
                name=name, motion=motion, bevel_cm=bevel_cm, parent=parent)


def lathe(gun, part_id, role, finish, profile, axis_xz, profile_source, axis_source, bore_r=None, name=None,
          motion=None, motion_sources=None, parent=None):
    """A round part: profile (y, r) turned round the line at (x, z) = axis_xz, parallel to the bore."""
    shape = {"kind": "lathe", "profile": profile, "axis": [float(axis_xz[0]), float(axis_xz[1])]}
    if bore_r:
        shape["bore_r"] = float(bore_r)
    sources = {"profile": profile_source, "axis": axis_source}
    sources.update(motion_sources or {})
    return part(gun, part_id, role, finish, shape, sources, name=name, motion=motion, parent=parent)


def hole(gun, part_id, trace_name=None, circle=None, source=None, x=None, bore=None):
    """A cut across the part: a kept trace's outline (a trigger guard's opening) or a circle {"at": [y, z], "r": cm};
    or a bore along y: {"at": [x, z], "r": cm, "y": [y0, y1]}."""
    bp = store.load(gun, "blueprint")
    if part_id not in bp["parts"]:
        raise ValueError("no part %s" % part_id)
    if bore:
        if not source:
            raise ValueError("a bore needs its source")
        h = {"kind": "bore", "at": bore["at"], "r": bore["r"], "y": bore["y"], "source": source}
    elif trace_name:
        t = trace(gun, trace_name)
        h = {"kind": "polygon", "outline": t["outline_cm"], "source": source or {"figure": t["figure"], "method": "traced"}}
    else:
        if not source:
            raise ValueError("a circle hole needs its source")
        h = {"kind": "circle", "at": circle["at"], "r": circle["r"], "source": source}
    if x:
        h["x"] = [float(x[0]), float(x[1])]
    bp["parts"][part_id].setdefault("holes", []).append(h)
    return _save(gun, bp)["parts"][part_id]["holes"][-1]


def mark(gun, name, at, source, normal=None, rides=None):
    """A mark in gun space (cm). rides: the part id (or chain of ids) it moves with."""
    bp = store.load(gun, "blueprint")
    m = {"at": [round(float(v), 4) for v in at], "source": source}
    if normal:
        m["normal"] = [float(v) for v in normal]
    bp["marks"][name] = m
    if rides:
        bp.setdefault("mark_parts", {})[name] = rides
    return _save(gun, bp)["marks"][name]


def lips(gun, at, source):
    bp = store.load(gun, "blueprint")
    bp["magazine_lips"] = {"at": [float(v) for v in at], "source": source}
    return _save(gun, bp)["magazine_lips"]


def action_default(action_id, role):
    """The action file's typical numbers for a role (a starting guess with its reason)."""
    a = A.load(action_id)
    want = a["parts"].get(role) or {}
    out = {}
    if "travel_cm" in want:
        out["travel_cm"] = (want["travel_cm"], {"guess": "the %s action's typical travel for its %s (%s)" % (action_id, role, want.get("what", role))})
    return out


def remove(gun, part_id=None, mark_name=None):
    bp = store.load(gun, "blueprint")
    if part_id:
        bp["parts"].pop(part_id, None)
        bp["mark_parts"] = {k: v for k, v in bp.get("mark_parts", {}).items() if v != part_id}
    if mark_name:
        bp["marks"].pop(mark_name, None)
        bp.get("mark_parts", {}).pop(mark_name, None)
    return _save(gun, bp)


def trace_px(gun, name):
    """A kept trace's outline in its figure's pixels."""
    p = store.folder(gun, "figures") / ("%s.trace.json" % name)
    if not p.exists():
        raise FileNotFoundError("no kept trace %s" % name)
    return json.loads(p.read_text(encoding="utf-8"))["outline_px"]


def views(gun, part_id, front=None, front_source=None, top=None, top_source=None):
    """Turns a part into three views: its side outline (kept) shared with front sections [{"y": [y0, y1],
    "outline": [[x, z], ...]}] and a top outline [[y, x], ...]. Each view given needs its source."""
    bp = store.load(gun, "blueprint")
    p = bp["parts"].get(part_id)
    if not p:
        raise ValueError("no part %s" % part_id)
    sh = p["shape"]
    if sh["kind"] == "lathe":
        raise ValueError("part %s is round (a lathe); it has its shape" % part_id)
    if sh["kind"] == "extrude":
        p["shape"] = sh = {"kind": "views", "side": sh["outline"], "x": sh["x"]}
        p["sources"]["side"] = p["sources"].pop("outline")
    if front is not None:
        if not front_source:
            raise ValueError("a front section needs its source")
        sh["front"] = front
        p["sources"]["front"] = front_source
    if top is not None:
        if not top_source:
            raise ValueError("a top outline needs its source")
        sh["top"] = top
        p["sources"]["top"] = top_source
    return _save(gun, bp)["parts"][part_id]


def feature(gun, part_id, ft):
    """Adds a surface feature (grooves, screw, texture) with its source to a part."""
    bp = store.load(gun, "blueprint")
    if part_id not in bp["parts"]:
        raise ValueError("no part %s" % part_id)
    if "source" not in ft:
        raise ValueError("a feature needs its source")
    bp["parts"][part_id].setdefault("features", []).append(ft)
    return _save(gun, bp)["parts"][part_id]["features"][-1]


def numbers(gun, part_id, nums):
    """The source's drawing or part numbers a blueprint part stands for (the detail check matches them)."""
    bp = store.load(gun, "blueprint")
    bp["parts"][part_id]["numbers"] = sorted(set(bp["parts"][part_id].get("numbers", [])) | set(nums))
    return _save(gun, bp)["parts"][part_id]


def rounded(x0, x1, z0, z1, r, steps=4):
    """A front section (x, z): a box from x0 to x1 and z0 to z1 with its top corners rounded by r."""
    out = [[x0, z0], [x1, z0]]
    for cx, a0 in ((x1 - r, 0.0), (x0 + r, 90.0)):
        for k in range(steps + 1):
            a = math.radians(a0 + 90.0 * k / steps)
            out.append([round(cx + r * math.cos(a), 4), round(z1 - r + r * math.sin(a), 4)])
    return out
