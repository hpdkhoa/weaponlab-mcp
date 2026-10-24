"""The detail pass's helpers (the owner, 2026-10-24: "the requirement is no low poly guns"; "I want the default of lab
mcp end result is the full detail pass"): a part's outline followed onto its figure's lines, shaped across, its
corners rounded, its edges softened. Each writes the blueprint and says where its numbers come from."""
import math

from . import figures as F
from . import plan as P
from . import store
from . import trace as T


def rr(x0, x1, z0, z1, r, steps=8):
    """A front section (x, z): a box with all four corners rounded by r (cm)."""
    r = max(0.0, min(r, (x1 - x0) / 2.0 - 1e-4, (z1 - z0) / 2.0 - 1e-4))
    out = []
    for cx, cz, a0 in ((x1 - r, z0 + r, -90.0), (x1 - r, z1 - r, 0.0), (x0 + r, z1 - r, 90.0), (x0 + r, z0 + r, 180.0)):
        for k in range(steps + 1):
            a = math.radians(a0 + 90.0 * k / steps)
            out.append([round(cx + r * math.cos(a), 4), round(cz + r * math.sin(a), 4)])
    return out


def oval(x0, x1, z0, z1, n=40):
    """A front section (x, z): an ellipse filling the box (a grip's, a magazine's round)."""
    cx, cz, ax, az = (x0 + x1) / 2.0, (z0 + z1) / 2.0, (x1 - x0) / 2.0, (z1 - z0) / 2.0
    return [[round(cx + ax * math.cos(2 * math.pi * k / n), 4), round(cz + az * math.sin(2 * math.pi * k / n), 4)] for k in range(n)]


def side_of(p):
    sh = p["shape"]
    return sh["outline"] if sh["kind"] == "extrude" else sh["side"]


def _key(p):
    return "outline" if p["shape"]["kind"] == "extrude" else "side"


def follow(gun, fig_id, pid, radius_px=16, step_px=2, eps_px=0.5, smooth=0.6, max_area_change=0.12, **kw):
    """A part's side outline laid onto the figure's lines as one line (OCR Lab's follower: each point along its
    normal, all moves chosen together). Kept as it was when following does not bring it closer to the lines, or
    changes its area by more than max_area_change (it collapsed onto an inner line or ran off). Returns the fit
    before and after (95th percentile miss, px)."""
    bp = store.load(gun, "blueprint")
    p = bp["parts"][pid]
    f = F.figure(gun, fig_id)
    res = T.follow(gun, fig_id, F.to_px(f, side_of(p)), radius_px=radius_px, step_px=step_px, eps_px=eps_px, smooth=smooth,
                   name="detail_" + pid, **kw)
    fb, fa = res["fit_before"], res["fit_after"]
    out = {"part": pid, "fit_before": fb, "fit_after": fa, "area_change": res["area_change"], "picture": res["picture"]}
    if fa["p95_px"] >= fb["p95_px"] or len(res["outline_cm"]) < 4 or abs(res["area_change"] or 0) > max_area_change:
        return dict(out, kept=True)
    note = "followed onto the source's lines (OCR Lab line_follow, %d px search): %d points, p95 miss %.1f px (was %.1f), %.0f%% on a line" % (
        radius_px, len(res["outline_cm"]), fa["p95_px"], fb["p95_px"], 100 * fa["on_share"])
    bp = store.load(gun, "blueprint")
    p = bp["parts"][pid]
    key = _key(p)
    p["shape"][key] = res["outline_cm"]
    src = p["sources"].get(key, {})
    p["sources"][key] = dict(src, method="traced", note=(src.get("note", "") + "; " + note).strip("; "))
    store.save(gun, "blueprint", bp, strict=False)
    return dict(out, points=len(res["outline_cm"]))


def soft(gun, pid, r, source, section="rr", steps=8):
    """A part shaped across: three views, its side kept, its front a rounded box (rr, corner radius r cm) or an
    ellipse (oval) over its full height and width."""
    bp = store.load(gun, "blueprint")
    p = bp["parts"][pid]
    sd = side_of(p)
    x0, x1 = p["shape"]["x"]
    z0, z1 = min(q[1] for q in sd) - 0.01, max(q[1] for q in sd) + 0.01
    y0, y1 = min(q[0] for q in sd) - 0.5, max(q[0] for q in sd) + 0.5
    front = rr(x0, x1, z0, z1, r, steps) if section == "rr" else oval(x0, x1, z0, z1)
    return P.views(gun, pid, front=[{"y": [y0, y1], "outline": front}], front_source=source)


def bevel(gun, pid, cm, source):
    """A part's edges rounded to cm."""
    bp = store.load(gun, "blueprint")
    bp["parts"][pid]["bevel_cm"] = cm
    bp["parts"][pid]["sources"]["bevel_cm"] = source
    store.save(gun, "blueprint", bp, strict=False)
    return {"part": pid, "bevel_cm": cm}


def round_outline(pts, r_cm, steps=6, min_turn_deg=20.0):
    """An outline with every corner (a turn of min_turn_deg or more) replaced by an arc of radius r_cm, tangent to
    both edges; a point where the outline turns straight back (a spike) is dropped."""
    n = len(pts)
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        u = (a[0] - b[0], a[1] - b[1])
        v = (c[0] - b[0], c[1] - b[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-6 or lv < 1e-6:
            continue
        u, v = (u[0] / lu, u[1] / lu), (v[0] / lv, v[1] / lv)
        ang = math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))
        if ang < 1e-3:
            continue
        if math.degrees(math.pi - ang) < min_turn_deg:
            out.append([b[0], b[1]])
            continue
        t = min(r_cm / math.tan(ang / 2.0), 0.45 * lu, 0.45 * lv)
        r = t * math.tan(ang / 2.0)
        p0 = (b[0] + u[0] * t, b[1] + u[1] * t)
        p1 = (b[0] + v[0] * t, b[1] + v[1] * t)
        bis = (u[0] + v[0], u[1] + v[1])
        lb = math.hypot(*bis)
        cen = (b[0] + bis[0] / lb * r / math.sin(ang / 2.0), b[1] + bis[1] / lb * r / math.sin(ang / 2.0))
        a0 = math.atan2(p0[1] - cen[1], p0[0] - cen[0])
        a1 = math.atan2(p1[1] - cen[1], p1[0] - cen[0])
        d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(steps + 1):
            q = a0 + d * k / steps
            out.append([round(cen[0] + r * math.cos(q), 4), round(cen[1] + r * math.sin(q), 4)])
    return out


def round_corners(gun, pid, r_cm, source, steps=6, min_turn_deg=20.0):
    """A part's side outline with its corners rounded (machined and moulded parts have radiused corners, not knife
    ones). Returns the number of points."""
    bp = store.load(gun, "blueprint")
    p = bp["parts"][pid]
    key = _key(p)
    p["shape"][key] = round_outline(p["shape"][key], r_cm, steps, min_turn_deg)
    src = p["sources"].get(key, {})
    p["sources"][key] = dict(src, note=(src.get("note", "") + "; corners rounded %.2f cm" % r_cm).strip("; "))
    p["sources"]["corner_r_cm"] = source
    store.save(gun, "blueprint", bp, strict=False)
    return len(p["shape"][key])


def polys(build_report):
    """Faces per part and in all, from a build's report."""
    parts = build_report.get("parts", {})
    per = {k: v.get("faces") for k, v in parts.items()}
    return {"total_faces": sum(v or 0 for v in per.values()), "per_part": per}
