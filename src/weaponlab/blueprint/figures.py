"""Step 3a: figures. A figure is cut from a page, turned upright (muzzle level, sights up), drawn at a known dpi;
then scaled by two points a known length apart (a fact: the overall length tip to tip) and framed in gun space by
the bore line and the bolt face. Pixel positions are in the figure's own picture.

Gun space from a figure: y runs along the bore toward the muzzle; z is square to it, up on the picture; x (across
the gun) does not show in a side view. grid() draws the picture with a pixel grid, and once framed a cm grid, so
points can be read off it."""
import math

from . import sources as S
from . import store


def _fig(doc, fig_id):
    for f in doc.get("figures", []):
        if f["id"] == fig_id:
            return f
    raise ValueError("no figure %s (have %s)" % (fig_id, ", ".join(f["id"] for f in doc.get("figures", []))))


def add(gun, fig_id, source_id, page, kind, shows=None, crop=None, rotate_deg=0, dpi=300, to_scale=None,
        caption=None, note=None):
    """Cuts a figure from a page. crop: [x0, y0, x1, y1] as shares of the page before turning (default the whole
    page); rotate_deg: 0, 90, 180 or 270, clockwise, to bring the gun upright; kind: side, section, top, front,
    rear, exploded, detail or photo; shows: right or left (the side a side view shows)."""
    import cv2
    import numpy as np
    doc = store.load(gun, "sources")
    src = S._source(doc, source_id)
    if src["file"].lower().endswith(".pdf"):
        pdf = S._pdf().open(src["file"])
        pg = pdf[page - 1]
        clip = None
        if crop:
            r = pg.rect
            clip = S._pdf().Rect(r.x0 + crop[0] * r.width, r.y0 + crop[1] * r.height, r.x0 + crop[2] * r.width, r.y0 + crop[3] * r.height)
        pix = pg.get_pixmap(dpi=dpi, clip=clip)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3][:, :, ::-1].copy()
    else:
        img = cv2.imread(src["file"])
        if crop:
            h, w = img.shape[:2]
            img = img[int(crop[1] * h):int(crop[3] * h), int(crop[0] * w):int(crop[2] * w)].copy()
    turn = {0: None, 90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[rotate_deg]
    if turn is not None:
        img = cv2.rotate(img, turn)
    out = store.folder(gun, "figures") / ("%s.png" % fig_id)
    cv2.imwrite(str(out), img)
    fig = {"id": fig_id, "source": source_id, "page": int(page), "kind": kind, "image": store.rel(gun, out),
           "rotate_deg": rotate_deg, "dpi": dpi}
    if crop:
        fig["crop"] = [round(c, 4) for c in crop]
    if shows:
        fig["shows"] = shows
    fig["to_scale"] = (kind != "exploded") if to_scale is None else bool(to_scale)
    for k, v in (("caption", caption), ("note", note)):
        if v:
            fig[k] = v
    doc["figures"] = [f for f in doc.get("figures", []) if f["id"] != fig_id] + [fig]
    store.save(gun, "sources", doc)
    return {"figure": fig, "image": str(out), "size_px": [img.shape[1], img.shape[0]]}


def calibrate(gun, fig_id, a, b, fact=None, cm=None):
    """The figure's scale from two points (px) a known length apart: a fact's value, or cm given."""
    doc = store.load(gun, "sources")
    f = _fig(doc, fig_id)
    if fact:
        fs = {x["id"]: x for x in doc.get("facts", [])}
        if fact not in fs:
            raise ValueError("no fact %s (have %s)" % (fact, ", ".join(fs)))
        if fs[fact]["unit"] != "cm":
            raise ValueError("fact %s is in %s, not a length" % (fact, fs[fact]["unit"]))
        cm = fs[fact]["value"]
    if not cm:
        raise ValueError("a fact or a length in cm")
    px = math.dist(a, b)
    f["scale"] = {"cm_per_px": round(cm / px, 7), "a": [round(v, 2) for v in a], "b": [round(v, 2) for v in b], "cm": round(cm, 4)}
    if fact:
        f["scale"]["fact"] = fact
    f["scale"]["cm_per_px"] = f["scale"]["cm"] / math.dist(f["scale"]["a"], f["scale"]["b"])
    store.save(gun, "sources", doc)
    return {"cm_per_px": f["scale"]["cm_per_px"], "px": round(px, 2), "cm": cm}


def frame(gun, fig_id, bore_rear, bore_front, origin):
    """How the figure lies in gun space: the bore line from bore_rear toward the muzzle at bore_front, and the bolt
    face (the origin). The origin is moved onto the bore line."""
    doc = store.load(gun, "sources")
    f = _fig(doc, fig_id)
    u = _unit(bore_rear, bore_front)
    t = (origin[0] - bore_rear[0]) * u[0] + (origin[1] - bore_rear[1]) * u[1]
    on = [bore_rear[0] + u[0] * t, bore_rear[1] + u[1] * t]
    f["frame"] = {"bore": [[round(v, 2) for v in bore_rear], [round(v, 2) for v in bore_front]], "origin": [round(v, 2) for v in on]}
    store.save(gun, "sources", doc)
    return {"origin_on_bore": f["frame"]["origin"], "moved_px": round(math.dist(origin, on), 2)}


def _unit(a, b):
    d = math.dist(a, b)
    if d == 0:
        raise ValueError("the bore's two points are the same")
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def axes(f):
    """The figure's gun axes in px: u along the bore toward the muzzle, n square to it and up on the picture."""
    u = _unit(*f["frame"]["bore"])
    n = (u[1], -u[0])
    if n[1] > 0:
        n = (-n[0], -n[1])
    return u, n


def to_gun(f, pts):
    """Pixel points to gun space (y, z) in cm."""
    if "scale" not in f or "frame" not in f:
        raise ValueError("figure %s needs its scale and frame first" % f["id"])
    u, n = axes(f)
    o, s = f["frame"]["origin"], f["scale"]["cm_per_px"]
    return [[round(((p[0] - o[0]) * u[0] + (p[1] - o[1]) * u[1]) * s, 4), round(((p[0] - o[0]) * n[0] + (p[1] - o[1]) * n[1]) * s, 4)] for p in pts]


def to_px(f, pts):
    """Gun space (y, z) in cm to pixel points."""
    u, n = axes(f)
    o, s = f["frame"]["origin"], f["scale"]["cm_per_px"]
    return [[o[0] + (y * u[0] + z * n[0]) / s, o[1] + (y * u[1] + z * n[1]) / s] for y, z, *_ in pts]


def figure(gun, fig_id):
    return _fig(store.load(gun, "sources"), fig_id)


def image(gun, f, gray=False):
    import cv2
    img = cv2.imread(str(store.abspath(gun, f["image"])), cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f["image"])
    return img


def measure(gun, fig_id, a, b):
    """The length between two pixel points, in cm, and each in gun space."""
    f = figure(gun, fig_id)
    if "scale" not in f:
        raise ValueError("figure %s has no scale yet" % fig_id)
    out = {"cm": round(math.dist(a, b) * f["scale"]["cm_per_px"], 3)}
    if "frame" in f:
        out["a_gun"], out["b_gun"] = to_gun(f, [a, b])
    return out


def grid(gun, fig_id, step_px=100, region=None, zoom=1.0):
    """The figure with a labelled pixel grid (and, once framed, the bore line, the origin and a cm grid along it),
    for reading points off it. region: [x0, y0, x1, y1] px to look closer; zoom scales the picture."""
    import cv2
    f = figure(gun, fig_id)
    img = image(gun, f)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in (region or [0, 0, w, h])]
    view = img.copy()
    if "frame" in f and "scale" in f:
        u, n = axes(f)
        s = f["scale"]["cm_per_px"]
        o = f["frame"]["origin"]
        for k in range(-60, 61):
            for d, col in ((u, (0, 160, 0)), (n, (160, 120, 0))):
                c = (o[0] + d[0] * k / s, o[1] + d[1] * k / s)
                perp = (d[1], -d[0])
                p1 = (int(c[0] - perp[0] * 4000), int(c[1] - perp[1] * 4000))
                p2 = (int(c[0] + perp[0] * 4000), int(c[1] + perp[1] * 4000))
                cv2.line(view, p1, p2, col, 1 if k % 5 else 2)
        b0, b1 = f["frame"]["bore"]
        cv2.line(view, (int(b0[0]), int(b0[1])), (int(b1[0]), int(b1[1])), (0, 0, 255), 2)
        cv2.circle(view, (int(o[0]), int(o[1])), 8, (0, 0, 255), 2)
    for x in range(0, w, step_px):
        cv2.line(view, (x, 0), (x, h), (255, 0, 255), 1)
        cv2.putText(view, str(x), (x + 2, max(y0 + 16, 16)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
    for y in range(0, h, step_px):
        cv2.line(view, (0, y), (w, y), (255, 0, 255), 1)
        cv2.putText(view, str(y), (max(x0 + 2, 2), y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
    view = view[y0:y1, x0:x1]
    if zoom != 1.0:
        view = cv2.resize(view, (int(view.shape[1] * zoom), int(view.shape[0] * zoom)), interpolation=cv2.INTER_AREA if zoom < 1 else cv2.INTER_CUBIC)
    label = "SOURCE FIGURE %s WITH A MEASURING GRID (not a model view)" % fig_id
    cv2.rectangle(view, (0, view.shape[0] - 24), (min(view.shape[1], 12 + 9 * len(label)), view.shape[0]), (255, 255, 255), -1)
    cv2.putText(view, label, (6, view.shape[0] - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    out = store.folder(gun, "figures") / ("%s_grid%s.png" % (fig_id, "" if not region else "_%d_%d" % (x0, y0)))
    cv2.imwrite(str(out), view)
    return str(out)


def calibrate_extent(gun, fig_id, outline_px, fact, direction=None):
    """The figure's scale from an outline's full length along a direction (default the frame's bore, else level),
    against a length fact (an overall length is the gun tip to tip along the bore). The scale's two points are the
    outline's end points carried onto one line along the direction."""
    doc = store.load(gun, "sources")
    f = _fig(doc, fig_id)
    if direction is None:
        direction = axes(f)[0] if "frame" in f else (1.0, 0.0)
    d = math.hypot(*direction)
    u = (direction[0] / d, direction[1] / d)
    proj = [p[0] * u[0] + p[1] * u[1] for p in outline_px]
    lo, hi = min(proj), max(proj)
    a = outline_px[proj.index(lo)]
    b = [a[0] + u[0] * (hi - lo), a[1] + u[1] * (hi - lo)]
    r = calibrate(gun, fig_id, a, b, fact=fact)
    r.update({"a": a, "b": b, "length_px": round(hi - lo, 2)})
    return r


def align(gun, fig_id, ref_fig_id, fig_outline_px, ref_outline_cm, muzzle="left", note=None):
    """A figure's scale and frame from a part both figures show (a trigger guard's opening): its outline here in px
    and in the framed reference figure in gun cm. The two outlines' boxes are matched (their centres, and the mean of
    the two sides' ratios for the scale); both figures must stand upright with the bore level. muzzle: the side of
    this picture the muzzle points to."""
    doc = store.load(gun, "sources")
    f = _fig(doc, fig_id)
    _fig(doc, ref_fig_id)
    xs, ys = [p[0] for p in fig_outline_px], [p[1] for p in fig_outline_px]
    gy, gz = [p[0] for p in ref_outline_cm], [p[1] for p in ref_outline_cm]
    sw, sh = (max(gy) - min(gy)) / (max(xs) - min(xs)), (max(gz) - min(gz)) / (max(ys) - min(ys))
    s = (sw + sh) / 2.0
    cx, cy = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
    yc, zc = (max(gy) + min(gy)) / 2.0, (max(gz) + min(gz)) / 2.0
    sign = -1.0 if muzzle == "left" else 1.0
    ox, oy = cx - sign * yc / s, cy + zc / s                 # the origin: the centre less its gun offset
    a, b = [min(xs), cy], [max(xs), cy]
    f["scale"] = {"cm_per_px": s, "a": a, "b": b, "cm": round(math.dist(a, b) * s, 4)}
    f["frame"] = {"bore": [[ox - sign * 100.0, oy], [ox + sign * 100.0, oy]], "origin": [round(ox, 2), round(oy, 2)]}
    f["note"] = (note + "; " if note else "") + "scale and frame matched to figure %s on a shared part (sides %.3f and %.3f cm a px)" % (ref_fig_id, sw, sh)
    store.save(gun, "sources", doc)
    return {"cm_per_px": round(s, 6), "side_ratios": [round(sw, 6), round(sh, 6)], "spread": round(abs(sw - sh) / s, 4), "origin_px": [round(ox, 2), round(oy, 2)]}
