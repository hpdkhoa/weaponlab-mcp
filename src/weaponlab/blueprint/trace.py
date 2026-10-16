"""Step 3b: outlines from a figure, in pixels and in gun space (cm).

    silhouette  the whole gun: the ink (or a photo's dark gun on a light ground) closed, its holes filled, its
                largest outline
    region      a closed area round a seed point: the paper inside the ink lines that bound one part of a drawing
    snap        a rough outline (Claude's reading of the picture) moved onto the nearest ink edges within a radius

Each writes a picture of what it found on the figure (labelled as a source figure, not a model view)."""
import json

from . import figures as Fg
from . import store


def _cv():
    import cv2
    import numpy as np
    return cv2, np


def ink(gun, f, threshold=None, invert=False):
    """The figure's ink as a mask: dark on light (Otsu's threshold unless one is given); invert for light on dark."""
    cv2, np = _cv()
    g = Fg.image(gun, f, gray=True)
    if threshold is None:
        _, m = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, m = cv2.threshold(g, threshold, 255, cv2.THRESH_BINARY_INV)
    return (255 - m) if invert else m


SMOOTH = {"window_px": 0, "corner_deg": 35.0}      # set by smoothing(); 0 keeps the raw contour


def smooth(points, window_px, corner_deg=35.0):
    """A traced contour's edge noise (a halftone's dots, a scan's grain) taken out: the corners found first (where the
    outline turns more than corner_deg over a window), then each run between two corners averaged over the window
    with its two corner ends held. Straight edges come out straight, curves even, corners sharp."""
    cv2, np = _cv()
    P = np.asarray(points, dtype=float)
    n = len(P)
    h = max(2, int(window_px // 2))
    if n < 4 * h:
        return P
    hc = 2 * h                                       # corners judged over twice the smoothing span: noise is no corner
    a = P[(np.arange(n) - hc) % n]
    b = P[(np.arange(n) + hc) % n]
    u, v = P - a, b - P
    cos = (u * v).sum(1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1) + 1e-9)
    turn = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    corners = [i for i in range(n) if turn[i] >= corner_deg and turn[i] >= turn[(i - 1) % n] and turn[i] >= turn[(i + 1) % n]]
    keep = []                                        # corners closer than the window are one corner
    for i in corners:
        if not keep or i - keep[-1] > hc:
            keep.append(i)
    if len(keep) > 1 and keep[0] + n - keep[-1] <= hc:
        keep.pop()
    out = P.copy()
    if not keep:
        k = np.ones(2 * h + 1) / (2 * h + 1)
        for d in range(2):
            ext = np.concatenate([P[-h:, d], P[:, d], P[:h, d]])
            out[:, d] = np.convolve(ext, k, mode="valid")
        return out
    for j, c0 in enumerate(keep):
        c1 = keep[(j + 1) % len(keep)]
        idx = [(c0 + t) % n for t in range(((c1 - c0) % n) + 1)]
        seg = P[idx]
        m = len(seg)
        for t in range(1, m - 1):
            w = min(h, t, m - 1 - t)                  # the window shrinks toward the corners, which stay put
            out[idx[t]] = seg[t - w:t + w + 1].mean(axis=0)
    return out


def smoothing(window_px=0, corner_deg=35.0):
    """Turns edge smoothing on for the traces that follow (window_px 0 turns it off)."""
    SMOOTH.update({"window_px": int(window_px), "corner_deg": float(corner_deg)})
    return dict(SMOOTH)


def _outline(mask, eps_px):
    cv2, np = _cv()
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        raise ValueError("nothing found")
    c = max(cs, key=cv2.contourArea)
    if SMOOTH["window_px"]:
        sm = smooth(c[:, 0, :], SMOOTH["window_px"], SMOOTH["corner_deg"])
        c = sm.astype(np.float32).reshape(-1, 1, 2)
    poly = cv2.approxPolyDP(c, eps_px, True)[:, 0, :]
    return [[float(x), float(y)] for x, y in poly], float(abs(cv2.contourArea(c)))


def _fill_holes(mask):
    cv2, np = _cv()
    h, w = mask.shape
    flood = mask.copy()
    pad = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, pad, (0, 0), 255)
    return mask | (255 - flood)


def _result(gun, f, poly_px, area_px, what, extra=None):
    cv2, np = _cv()
    out = {"figure": f["id"], "method": what, "points": len(poly_px), "outline_px": [[round(x, 1), round(y, 1)] for x, y in poly_px]}
    if SMOOTH["window_px"]:
        out["smoothed"] = {"window_px": SMOOTH["window_px"], "corner_deg": SMOOTH["corner_deg"]}
    if "scale" in f:
        out["area_cm2"] = round(area_px * f["scale"]["cm_per_px"] ** 2, 3)
    if "scale" in f and "frame" in f:
        g = Fg.to_gun(f, poly_px)
        out["outline_cm"] = [[round(y, 3), round(z, 3)] for y, z in g]
        ys, zs = [p[0] for p in g], [p[1] for p in g]
        out["bounds_cm"] = {"y": [min(ys), max(ys)], "z": [min(zs), max(zs)]}
    img = Fg.image(gun, f)
    cv2.polylines(img, [np.array(poly_px, dtype=np.int32)], True, (0, 0, 255), 2)
    label = "SOURCE FIGURE %s, %s TRACE (not a model view)" % (f["id"], what.upper())
    cv2.rectangle(img, (0, 0), (12 + 9 * len(label), 26), (255, 255, 255), -1)
    cv2.putText(img, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    pic = store.folder(gun, "figures") / ("%s_%s%s.png" % (f["id"], what, "_" + extra if extra else ""))
    cv2.imwrite(str(pic), img)
    out["picture"] = str(pic)
    return out


def silhouette(gun, fig_id, region=None, close_px=9, eps_px=2.0, threshold=None):
    """The gun's whole outline. region: [x0, y0, x1, y1] px to look in (leave out captions and labels)."""
    cv2, np = _cv()
    f = Fg.figure(gun, fig_id)
    m = ink(gun, f, threshold)
    if region:
        keep = np.zeros_like(m)
        x0, y0, x1, y1 = [int(v) for v in region]
        keep[y0:y1, x0:x1] = 255
        m &= keep
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_px, close_px))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    m = _fill_holes(m)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    poly, area = _outline(m, eps_px)
    return _result(gun, f, poly, area, "silhouette")


def region(gun, fig_id, seed, gap_px=3, eps_px=1.5, threshold=None, name=None):
    """The closed area round a seed point (px): the paper inside the ink lines round it. gap_px closes small gaps in
    the lines first (and the area grows back by as much)."""
    cv2, np = _cv()
    f = Fg.figure(gun, fig_id)
    m = ink(gun, f, threshold)
    if gap_px:
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gap_px + 1, 2 * gap_px + 1)))
    sx, sy = int(seed[0]), int(seed[1])
    if m[sy, sx]:
        raise ValueError("the seed (%d, %d) is on ink; put it inside the part's area" % (sx, sy))
    h, w = m.shape
    pad = np.zeros((h + 2, w + 2), np.uint8)
    flood = m.copy()
    cv2.floodFill(flood, pad, (sx, sy), 128)
    area = (flood == 128).astype(np.uint8) * 255
    if area[0, :].any() or area[-1, :].any() or area[:, 0].any() or area[:, -1].any():
        raise ValueError("the area round (%d, %d) runs out to the picture's edge: its lines do not close (try a larger gap_px)" % (sx, sy))
    if gap_px:
        area = cv2.dilate(area, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gap_px + 1, 2 * gap_px + 1)))
    poly, a = _outline(_fill_holes(area), eps_px)
    return _result(gun, f, poly, a, "region", name)


def snap(gun, fig_id, rough_px, radius_px=12, step_px=4, eps_px=1.5, threshold=None, name=None):
    """A rough outline (px) moved onto the ink: each point, after the outline is cut into steps, goes to the nearest
    ink edge within the radius; a point with none stays. Gives how far points moved and how many found no edge."""
    cv2, np = _cv()
    f = Fg.figure(gun, fig_id)
    m = ink(gun, f, threshold)
    edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    h, w = edge.shape
    dense = []
    pts = [tuple(p) for p in rough_px]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n = max(1, int(np.hypot(b[0] - a[0], b[1] - a[1]) / step_px))
        for k in range(n):
            dense.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    out, moved, missed = [], [], 0
    r = int(radius_px)
    for x, y in dense:
        xi, yi = int(round(x)), int(round(y))
        x0, x1, y0, y1 = max(0, xi - r), min(w, xi + r + 1), max(0, yi - r), min(h, yi + r + 1)
        ys, xs = np.nonzero(edge[y0:y1, x0:x1])
        if len(xs) == 0:
            out.append((x, y))
            missed += 1
            continue
        d = (xs + x0 - x) ** 2 + (ys + y0 - y) ** 2
        j = int(np.argmin(d))
        if d[j] > r * r:
            out.append((x, y))
            missed += 1
            continue
        out.append((float(xs[j] + x0), float(ys[j] + y0)))
        moved.append(float(np.sqrt(d[j])))
    c = np.array(out, dtype=np.float32).reshape(-1, 1, 2)
    poly = cv2.approxPolyDP(c, eps_px, True)[:, 0, :]
    res = _result(gun, f, [[float(x), float(y)] for x, y in poly], float(abs(cv2.contourArea(c))), "snap", name)
    res.update({"moved_px_mean": round(float(np.mean(moved)), 2) if moved else None,
                "moved_px_max": round(float(np.max(moved)), 2) if moved else None,
                "no_edge_share": round(missed / max(1, len(dense)), 3)})
    return res


def save(gun, name, result):
    """Keeps a trace (figures/<name>.trace.json) for the plan to use."""
    p = store.folder(gun, "figures") / ("%s.trace.json" % name)
    p.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return str(p)


def ticks(gun, fig_id, region, min_share=0.5, threshold=None, invert=False):
    """The tick marks of a printed scale bar in region [x0, y0, x1, y1] px (ticks square to a level bar): the
    centre column of each run of columns whose ink fills at least min_share of the region's height. For a bar
    that stands upright, give a region that is taller than wide: rows are read instead."""
    cv2, np = _cv()
    f = Fg.figure(gun, fig_id)
    m = ink(gun, f, threshold, invert) > 0           # invert: light marks on a dark ground (serrations in a photo)
    x0, y0, x1, y1 = [int(v) for v in region]
    sub = m[y0:y1, x0:x1]
    upright = (y1 - y0) > (x1 - x0)
    prof = sub.mean(axis=1 if upright else 0)
    on = prof >= min_share
    runs, start = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start + i - 1) / 2.0)
            start = None
    at = [round(r + (y0 if upright else x0), 2) for r in runs]
    gaps = [round(b - a, 2) for a, b in zip(at, at[1:])]
    return {"figure": fig_id, "along": "y" if upright else "x", "ticks_px": at, "gaps_px": gaps}


def span(gun, fig_id, a, b, threshold=None, gap_px=0):
    """Where the ink starts and ends along a line from a to b (px): the first and last ink pixel, their distance in
    cm (when the figure has a scale) and every run of ink along it. gap_px: runs closer than this join."""
    cv2, np = _cv()
    f = Fg.figure(gun, fig_id)
    m = ink(gun, f, threshold) > 0
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
    xs = np.linspace(a[0], b[0], n).round().astype(int)
    ys = np.linspace(a[1], b[1], n).round().astype(int)
    on = m[ys.clip(0, m.shape[0] - 1), xs.clip(0, m.shape[1] - 1)]
    runs, start = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if runs and start - runs[-1][1] <= gap_px:
                runs[-1][1] = i - 1
            else:
                runs.append([start, i - 1])
            start = None
    if not runs:
        return {"figure": fig_id, "ink": False}
    first, last = runs[0][0], runs[-1][1]
    pt = lambda i: [float(xs[i]), float(ys[i])]   # noqa: E731
    out = {"figure": fig_id, "ink": True, "first_px": pt(first), "last_px": pt(last), "runs": [[pt(r[0]), pt(r[1])] for r in runs]}
    if "scale" in f:
        step = float(np.hypot(b[0] - a[0], b[1] - a[1])) / max(1, n - 1)
        out["cm"] = round((last - first) * step * f["scale"]["cm_per_px"], 4)
    return out


def peaks(gun, fig_id, region, light=True, min_gap_px=3, k=0.5):
    """Evenly spaced marks too faint or dotted for ink runs (serrations in a halftone photo): the columns of region
    [x0, y0, x1, y1] px whose mean brightness (light marks) or darkness peaks above the profile's mean plus k times
    its spread, at least min_gap_px apart. Gives their columns, their mean pitch in px and in cm."""
    cv2, np = _cv()
    f = Fg.figure(gun, fig_id)
    g = Fg.image(gun, f, gray=True).astype(float)
    x0, y0, x1, y1 = [int(v) for v in region]
    prof = g[y0:y1, x0:x1].mean(axis=0)
    if not light:
        prof = 255.0 - prof
    prof = np.convolve(prof, np.ones(3) / 3.0, mode="same")
    cut = prof.mean() + k * prof.std()
    at = []
    for i in range(1, len(prof) - 1):
        if prof[i] >= cut and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]:
            if at and i - at[-1] < min_gap_px:
                if prof[i] > prof[at[-1]]:
                    at[-1] = i
                continue
            at.append(i)
    cols = [x0 + i for i in at]
    gaps = [b - a for a, b in zip(cols, cols[1:])]
    out = {"figure": fig_id, "columns_px": cols, "count": len(cols), "gaps_px": gaps,
           "pitch_px": round(float(np.median(gaps)), 2) if gaps else None}
    if gaps and "scale" in f:
        out["pitch_cm"] = round(out["pitch_px"] * f["scale"]["cm_per_px"], 4)
        out["span_cm"] = round((cols[-1] - cols[0]) * f["scale"]["cm_per_px"], 3)
    return out


def blob(gun, fig_id, box, seed, light=True, blur_px=5, eps_px=1.0, name=None):
    """A light (or dark) patch round a seed in a halftone picture, where single dots break a region's lines: the
    box [x0, y0, x1, y1] px blurred, cut at its own Otsu threshold, and the connected patch holding the seed."""
    cv2, np = _cv()
    f = Fg.figure(gun, fig_id)
    g = Fg.image(gun, f, gray=True)
    x0, y0, x1, y1 = [int(v) for v in box]
    sub = cv2.GaussianBlur(g[y0:y1, x0:x1], (2 * blur_px + 1, 2 * blur_px + 1), 0)
    _, m = cv2.threshold(sub, 0, 255, (cv2.THRESH_BINARY if light else cv2.THRESH_BINARY_INV) + cv2.THRESH_OTSU)
    n, lab = cv2.connectedComponents(m)
    sx, sy = int(seed[0]) - x0, int(seed[1]) - y0
    if not lab[sy, sx]:
        raise ValueError("the seed (%d, %d) is not on a %s patch" % (seed[0], seed[1], "light" if light else "dark"))
    patch = (lab == lab[sy, sx]).astype(np.uint8) * 255
    if patch[0, :].any() or patch[-1, :].any() or patch[:, 0].any() or patch[:, -1].any():
        raise ValueError("the patch runs to the box's edge: give a larger box")
    full = np.zeros_like(g)
    full[y0:y1, x0:x1] = patch
    poly, a = _outline(full, eps_px)
    return _result(gun, f, poly, a, "blob", name)
