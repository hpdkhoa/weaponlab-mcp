"""The photo detail layer: surface maps baked from a source photo of the gun's side, so the flat plates of a visual
copy carry the pins, seams, markings and wear the photo shows (the owner, 2026-10-25: "add the baked texture layer
from the source photos").

The figure is already framed and scaled (its bore line and cm a pixel), so it is redrawn square in gun space (u along
the bore, n up) at the map's own cm a pixel. From its brightness:
    height    a band pass (fine detail kept, the photo's lighting gradient removed); dark reads as a recess
    normal    the height's slope, as a tangent-space normal map (OpenGL, +Y up)
    albedo    the tone against its surroundings (markings, panels, stains): a multiplier on the finish's colour
    rough     brighter spots read as worn, shinier metal: a multiplier on the finish's roughness
    mask      the parts' side outlines filled: outside them the maps are neutral (the background is not the gun)
A photo's shading is not a height field: every map is a derived guess of relief from brightness, and is recorded as
one. The side not photographed takes the same map mirrored, recorded as a guess too."""
import json
import math

from . import figures as F
from . import store


def _np():
    import numpy as np
    return np


def _side(p):
    sh = p["shape"]
    if sh["kind"] == "extrude":
        return sh["outline"]
    if sh["kind"] in ("views", "loft"):
        return sh["side"]
    return None


def _gauss(img, sigma_px):
    import cv2
    k = max(3, int(6 * sigma_px) | 1)
    return cv2.GaussianBlur(img, (k, k), sigma_px)


def bake(gun, fig_id, max_px=4096, fine_cm=0.08, coarse_cm=2.5, strength=1.0, mirror_other_side=True):
    """Bakes the maps from figure fig_id into model/photomap/ and records them on the blueprint (photo_detail).
    fine_cm: detail finer than this is noise (the photo's grain); coarse_cm: variation broader than this is lighting.
    strength: the normal map's slope scale (1 = the band's full range reads as about 1 mm of relief)."""
    import cv2
    np = _np()
    bp = store.load(gun, "blueprint")
    f = F.figure(gun, fig_id)
    if "scale" not in f or "frame" not in f:
        raise ValueError("figure %s needs its scale and frame first" % fig_id)
    outlines = [o for p in bp["parts"].values() for o in [_side(p)] if o]
    if not outlines:
        raise ValueError("no part with a side outline to mask the photo with")
    ys = [q[0] for o in outlines for q in o]
    zs = [q[1] for o in outlines for q in o]
    pad = 1.0
    box = [min(ys) - pad, max(ys) + pad, min(zs) - pad, max(zs) + pad]
    span = max(box[1] - box[0], box[3] - box[2])
    cmpx = max(f["scale"]["cm_per_px"], span / float(max_px))
    W = int(math.ceil((box[1] - box[0]) / cmpx))
    H = int(math.ceil((box[3] - box[2]) / cmpx))
    # the photo redrawn in gun space: map pixel (i, j) -> gun (y, z) -> photo px; an affine warp (the figure's frame
    # is a rotation and a scale)
    u, n = F.axes(f)
    o, s = f["frame"]["origin"], f["scale"]["cm_per_px"]
    # photo_px = o + (y u + z n) / s, with y = box0 + i cmpx, z = box3 - j cmpx
    a = cmpx / s
    M = np.array([[u[0] * a, -n[0] * a, o[0] + (box[0] * u[0] + box[3] * n[0]) / s],
                  [u[1] * a, -n[1] * a, o[1] + (box[0] * u[1] + box[3] * n[1]) / s]], dtype=np.float64)
    img = F.image(gun, f, gray=True)
    L = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE).astype(np.float32) / 255.0
    # the mask: the parts' side outlines, filled
    mask = np.zeros((H, W), np.uint8)
    for ol in outlines:
        pts = np.array([[(q[0] - box[0]) / cmpx, (box[3] - q[1]) / cmpx] for q in ol], np.int32)
        cv2.fillPoly(mask, [pts], 255)
    mask = cv2.erode(mask, np.ones((3, 3), np.uint8))
    m = mask > 0
    # the band pass: fine grain out, lighting out
    fine = _gauss(L, max(0.5, fine_cm / cmpx))
    coarse = _gauss(L, coarse_cm / cmpx)
    band = fine - coarse
    sd = float(band[m].std()) if m.any() else 1.0
    height = np.clip(band / (3.0 * max(sd, 1e-6)), -1.0, 1.0)          # 3 sigma of the gun's own detail = full range
    height[~m] = 0.0
    # the normal: the height's slope; one unit of height stands for about 1 mm of relief at strength 1
    relief_px = (0.1 * strength) / cmpx
    gx = cv2.Sobel(height, cv2.CV_32F, 1, 0, ksize=3) / 8.0 * relief_px
    gy = cv2.Sobel(height, cv2.CV_32F, 0, 1, ksize=3) / 8.0 * relief_px
    nx, ny, nz = -gx, gy, np.ones_like(gx)        # image y runs down: OpenGL +Y up
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.dstack([(nx / ln + 1) / 2, (ny / ln + 1) / 2, (nz / ln + 1) / 2])
    normal[~m] = (0.5, 0.5, 1.0)
    # the tone: fine against its surroundings (markings, panel steps, stains) as a multiplier about 1
    mid = _gauss(L, 0.6 / cmpx)
    tone = np.clip(mid / np.maximum(coarse, 0.02), 0.55, 1.45)
    tone[~m] = 1.0
    # worn, shinier metal shows bright: a roughness multiplier, bright spots lower
    bright = np.clip((mid - coarse) / (2.0 * max(float((mid - coarse)[m].std()), 1e-6)), -1.0, 1.0)
    rough = np.clip(1.0 - 0.35 * bright, 0.55, 1.35)
    rough[~m] = 1.0
    out = store.folder(gun, "model", "photomap")
    files = {}
    for name, arr in (("normal", (normal[..., ::-1] * 255)), ("albedo", np.dstack([tone] * 3) * 127.5), ("rough", np.dstack([rough] * 3) * 127.5),
                      ("height", np.dstack([(height + 1) / 2] * 3) * 255), ("mask", np.dstack([mask] * 3))):
        pth = out / ("%s_%s.png" % (fig_id, name))
        cv2.imwrite(str(pth), np.clip(arr, 0, 255).astype(np.uint8))
        files[name] = str(pth)
    rec = {"figure": fig_id, "shows": f.get("shows") or "right", "box_cm": [round(v, 3) for v in box], "cm_per_px": round(cmpx, 5),
           "size_px": [W, H], "fine_cm": fine_cm, "coarse_cm": coarse_cm, "strength": strength, "mirror_other_side": mirror_other_side,
           "files": files, "coverage": round(float(m.mean()), 3), "detail_sd": round(sd, 4),
           "source": {"figure": fig_id, "method": "derived",
                      "note": "surface maps baked from the photo's brightness: a band pass %.2f to %.1f cm as relief (dark reads as a recess), its slope "
                              "as the normal, the tone as a colour multiplier, bright spots as worn shinier metal; a guess of relief from shading, "
                              "masked to the parts' outlines" % (fine_cm, coarse_cm)},
           "other_side": {"guess": "the side not photographed takes the same maps mirrored"} if mirror_other_side else None}
    (out / "photomap.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    bp["photo_detail"] = rec
    store.save(gun, "blueprint", bp, strict=False)
    return rec


def remove(gun):
    bp = store.load(gun, "blueprint")
    bp.pop("photo_detail", None)
    store.save(gun, "blueprint", bp, strict=False)
    return {"removed": True}
