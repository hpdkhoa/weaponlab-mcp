"""Step 5: the blueprint checked.

    contract    the blueprint against weaponlab-blueprint/1 and its sources (every number has a source)
    outline     the blueprint's side silhouette (every part laid flat) against a reference trace: overlap (IoU)
                and the mean and worst gap between their edges, in cm
    length      the silhouette's length along the bore against the overall length fact
    weight      every part's volume times its finish's density against the weight fact (a visual copy is solid
                where the gun is hollow, so this one only warns)
    overlays    each framed figure with the blueprint's outlines drawn on it, labelled as a source figure

The results go into the blueprint's checks and check/check.json."""
import json
import math

from .. import contracts as C
from . import figures as Fg
from . import plan as Pl
from . import specs as Sp
from . import store

DENSITY = {"steel": 7.85, "blued": 7.85, "parkerized": 7.85, "phosphate": 7.85, "stainless": 8.0, "nickel": 8.4,
           "aluminium": 2.7, "aluminum": 2.7, "anodized": 2.7, "brass": 8.5, "walnut": 0.65, "wood": 0.65,
           "plastic": 1.3, "bakelite": 1.3, "polymer": 1.2, "rubber": 1.1}
PASS = {"iou": 0.95, "gap_mean_cm": 0.15, "length_share": 0.01}


def silhouette(bp, include=None):
    """Every part's side outline as polygons in (y, z) cm: an extrude's outline, a lathe's profile mirrored about
    its axis."""
    polys = []
    for pid, p in bp["parts"].items():
        if include and pid not in include:
            continue
        sh = p["shape"]
        if sh["kind"] == "extrude":
            polys.append(sh["outline"])
        elif sh["kind"] in ("views", "relief"):
            polys.append(sh["side"])
        else:
            z0 = sh["axis"][1]
            top = [[y, z0 + r] for y, r in sh["profile"]]
            bot = [[y, z0 - r] for y, r in reversed(sh["profile"])]
            polys.append(top + bot)
    return polys


def _raster(polys, holes, bounds, res):
    import cv2
    import numpy as np
    (y0, y1), (z0, z1) = bounds
    w, h = int((y1 - y0) / res) + 3, int((z1 - z0) / res) + 3
    m = np.zeros((h, w), np.uint8)
    to = lambda poly: np.array([[(y - y0) / res + 1, (z1 - z) / res + 1] for y, z, *_ in poly], dtype=np.int32)   # noqa: E731
    for p in polys:
        cv2.fillPoly(m, [to(p)], 255)
    for p in holes:
        cv2.fillPoly(m, [to(p)], 0)
    return m


def _holes(bp):
    out = []
    for p in bp["parts"].values():
        for h in p.get("holes", []):
            if h.get("x") or h["kind"] in ("bore", "sweep"):
                continue                   # a cut that stops inside the part, runs along the bore, or shapes an edge, still shows its outside
            if h["kind"] == "polygon":
                out.append(h["outline"])
            else:
                (y, z), r = h["at"], h["r"]
                out.append([[y + r * math.cos(t * math.pi / 12), z + r * math.sin(t * math.pi / 12)] for t in range(24)])
    return out


def outline(bp, ref_outline, res=0.01, ref_holes=()):
    """IoU and edge gaps between the blueprint's silhouette and a reference outline (y, z cm)."""
    import cv2
    import numpy as np
    polys = silhouette(bp)
    pts = [p for poly in polys + [ref_outline] for p in poly]
    bounds = ((min(p[0] for p in pts) - 0.5, max(p[0] for p in pts) + 0.5), (min(p[1] for p in pts) - 0.5, max(p[1] for p in pts) + 0.5))
    a = _raster(polys, _holes(bp), bounds, res) > 0
    b = _raster([ref_outline], list(ref_holes), bounds, res) > 0
    iou = float((a & b).sum()) / max(1, float((a | b).sum()))
    ea = cv2.morphologyEx(a.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    eb = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    da = cv2.distanceTransform((~ea).astype(np.uint8), cv2.DIST_L2, 5)
    gaps = da[eb] * res
    return {"iou": round(iou, 4), "gap_mean_cm": round(float(gaps.mean()), 3), "gap_worst_cm": round(float(gaps.max()), 3),
            "gap_p95_cm": round(float(np.percentile(gaps, 95)), 3)}


def detail(bp, src):
    """The detail check: every visible part of the source's parts list has a blueprint part (by its number), and
    the shapes the parts take (a slab is a side outline alone; a shaped part has front or top views too)."""
    have = {n for p in bp["parts"].values() for n in p.get("numbers", [])}
    names = {p.get("name", "").strip().lower() for p in bp["parts"].values()}
    listed = src.get("parts_list", [])
    visible = [lp for lp in listed if lp["visible"]]
    # a listed part with a number matches by its number; one the text names without one, by its name
    found = lambda lp: lp["number"] in have if lp.get("number") else lp["name"].strip().lower() in names   # noqa: E731
    missing = [{"name": lp["name"], "number": lp.get("number"), "page": lp["page"]} for lp in visible if not found(lp)]
    kinds = {}
    for pid, p in bp["parts"].items():
        sh = p["shape"]
        k = "lathe" if sh["kind"] == "lathe" else ("shaped" if (sh["kind"] == "views" and ("front" in sh or "top" in sh)) or sh["kind"] == "relief" else "slab")
        kinds.setdefault(k, []).append(pid)
    feats = [f["kind"] for p in bp["parts"].values() for f in p.get("features", [])]
    return {"listed": len(listed), "visible": len(visible), "missing": missing,
            "covered_share": round(1 - len(missing) / len(visible), 3) if visible else None,
            "shapes": kinds, "features": {k: feats.count(k) for k in sorted(set(feats))},
            "ok": bool(listed) and not missing}


def volume_cm3(p):
    sh = p["shape"]
    if sh["kind"] == "relief":                      # no larger than its side times its thickness (a pair: twice)
        return Pl.area(sh["side"]) * abs(sh["x"][1] - sh["x"][0]) * (2 if sh.get("both") else 1)
    if sh["kind"] in ("extrude", "views"):          # a shaped part is no larger than its side times its width
        v = Pl.area(sh["outline"] if sh["kind"] == "extrude" else sh["side"]) * (sh["x"][1] - sh["x"][0])
        for h in p.get("holes", []):
            if h["kind"] == "bore":
                v -= math.pi * h["r"] ** 2 * abs(h["y"][1] - h["y"][0])
                continue
            if h["kind"] == "sweep":                # a shaping cut along an edge: small, left out of the bound
                continue
            w = (h["x"][1] - h["x"][0]) if h.get("x") else (sh["x"][1] - sh["x"][0])
            v -= (Pl.area(h["outline"]) if h["kind"] == "polygon" else math.pi * h["r"] ** 2) * w
        return max(v, 0.0)
    prof = sh["profile"]
    v = sum(math.pi * (a[1] ** 2 + a[1] * b[1] + b[1] ** 2) / 3.0 * abs(b[0] - a[0]) for a, b in zip(prof, prof[1:]))
    if sh.get("bore_r"):
        v -= math.pi * sh["bore_r"] ** 2 * abs(prof[-1][0] - prof[0][0])
    return max(v, 0.0)


def density(finish):
    f = finish.lower()
    for k, d in DENSITY.items():
        if k in f:
            return d
    return 7.85


def overlay(gun, bp, fig):
    import cv2
    import numpy as np
    img = Fg.image(gun, fig)
    colors = [(0, 0, 255), (0, 160, 0), (255, 0, 0), (0, 160, 255), (200, 0, 200), (160, 160, 0), (0, 0, 120), (90, 60, 200)]
    for k, (pid, p) in enumerate(bp["parts"].items()):
        col = colors[k % len(colors)]
        for poly in silhouette(bp, include=[pid]):
            px = np.array(Fg.to_px(fig, poly), dtype=np.int32)
            cv2.polylines(img, [px], True, col, 2)
            c = px.mean(axis=0).astype(int)
            cv2.putText(img, pid, (int(c[0]) - 20, int(c[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
        for h in p.get("holes", []):
            if h["kind"] == "polygon":
                cv2.polylines(img, [np.array(Fg.to_px(fig, h["outline"]), dtype=np.int32)], True, col, 1)
    for m, x in bp["marks"].items():
        px = Fg.to_px(fig, [[x["at"][1], x["at"][2]]])[0]
        cv2.drawMarker(img, (int(px[0]), int(px[1])), (0, 0, 0), cv2.MARKER_CROSS, 10, 1)
    label = "SOURCE FIGURE %s WITH THE BLUEPRINT DRAWN ON IT (not a model view)" % fig["id"]
    cv2.rectangle(img, (0, 0), (12 + 9 * len(label), 26), (255, 255, 255), -1)
    cv2.putText(img, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    out = store.folder(gun, "check") / ("overlay_%s.png" % fig["id"])
    cv2.imwrite(str(out), img)
    return str(out)


def run(gun, reference=None, reference_holes=(), length_fact="overall_length", weight_fact="weight"):
    """Every check. reference: the name of a kept silhouette trace the side outline is held to; reference_holes:
    kept traces of its openings (a trigger guard)."""
    bp = store.load(gun, "blueprint")
    src = store.load(gun, "sources")
    out = {"contract": C.check_blueprint(bp, sources=src)}
    polys = silhouette(bp)
    facts = Sp.facts(gun)
    if polys:
        ys = [p[0] for poly in polys for p in poly]
        zs = [p[1] for poly in polys for p in poly]
        out["bounds_cm"] = {"y": [round(min(ys), 3), round(max(ys), 3)], "z": [round(min(zs), 3), round(max(zs), 3)]}
        if length_fact in facts:
            L, want = max(ys) - min(ys), facts[length_fact]["value"]
            out["length"] = {"cm": round(L, 3), "fact_cm": want, "share_off": round(abs(L - want) / want, 4),
                             "ok": abs(L - want) / want <= PASS["length_share"]}
    if reference:
        t = Pl.trace(gun, reference)
        holes = [Pl.trace(gun, h)["outline_cm"] for h in reference_holes]
        o = outline(bp, t["outline_cm"], ref_holes=holes)
        o["reference"] = reference
        o["ok"] = o["iou"] >= PASS["iou"] and o["gap_mean_cm"] <= PASS["gap_mean_cm"]
        out["outline"] = o
    out["detail"] = detail(bp, src)
    kg = sum(volume_cm3(p) * density(p["finish"]) for p in bp["parts"].values()) / 1000.0
    out["weight"] = {"kg": round(kg, 3)}
    if weight_fact in facts:
        out["weight"].update({"fact_kg": facts[weight_fact]["value"], "ratio": round(kg / facts[weight_fact]["value"], 3),
                              "note": "warning only: the copy is solid where the gun is hollow"})
    out["overlays"] = [overlay(gun, bp, f) for f in src.get("figures", []) if "scale" in f and "frame" in f]
    out["ok"] = not out["contract"] and all(out[k].get("ok", True) for k in ("length", "outline", "detail") if k in out)
    bp["checks"] = {k: v for k, v in out.items() if k != "overlays"}
    store.save(gun, "blueprint", bp, strict=False)
    (store.folder(gun, "check") / "check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
