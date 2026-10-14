"""Weapon Spec: one JSON file a weapon in the project's specs folder, the source every other part reads.

Frame: the gun's space of the probe contract (cm, +Y along the barrel, +Z up, +X the gun's left).

A spec holds:
  id, name, family, real_model, support ("two_hand" or "one_hand")
  assets   {gun, arms_rig?, idle?, clips?{action: path}, arms_from? (the rig whose clips it borrows)}
  marks    {name: {at [x,y,z], axis? [x,y,z], travel_cm?, status "measured"|"proposed", source}}
  actions  {name: {beats [{name, mark?, hand? "l"|"r", t?}], gun_clip?, arms_clip?}}
  anchors  {name: {component?, role?, triangles, extents [a,b,c], unique?}}: a piece of the model, found in a parts dump
  align    {bone, axis [x,y,z], well_depth_cm}: the magazine's line into its well
  facts    [{id, claim, check {kind, ...}, source}]   (rig.py checks order, side, below and in on the anchors)
  limits   {wrist_deg, elbow_under_shoulder_cm, elbow_bend [min,max], clearance_cm, contacts [segment wildcards],
            view_budget {lower_left, bottom_middle, total} (shares of the screen the arms may cover at rest)}
"""
import copy
import json
from pathlib import Path

from .config import project

SUPPORT = ("two_hand", "one_hand")
STATUS = ("measured", "proposed")
FACT_KINDS = ("side", "travel", "count", "two_hand", "edge_leads", "bone", "order", "below", "in")
DEFAULT_LIMITS = {"wrist_deg": 30.0, "elbow_under_shoulder_cm": 2.0, "elbow_bend": [5.0, 150.0], "clearance_cm": 0.2,
                  "contacts": [], "view_budget": None}


def path_of(weapon_id):
    return project().specs / (weapon_id + ".json")


def list_specs():
    folder = project().specs
    out = []
    for p in sorted(folder.glob("*.json")) if folder.exists() else []:
        try:
            s = json.loads(p.read_text(encoding="utf-8-sig"))
            out.append({"id": s.get("id", p.stem), "name": s.get("name"), "family": s.get("family"),
                        "marks": len(s.get("marks", {})), "actions": sorted(s.get("actions", {})),
                        "proposed_marks": sorted(k for k, m in s.get("marks", {}).items() if m.get("status") != "measured")})
        except ValueError as e:
            out.append({"id": p.stem, "error": "not JSON: %s" % e})
    return out


def read_spec(weapon_id):
    p = path_of(weapon_id)
    if not p.exists():
        raise FileNotFoundError("no spec for %s (%s)" % (weapon_id, p))
    s = json.loads(p.read_text(encoding="utf-8-sig"))
    lim = copy.deepcopy(DEFAULT_LIMITS)
    lim.update(s.get("limits", {}))
    s["limits"] = lim
    return s


def _vec(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)


def validate(spec):
    """Every problem with a spec, as sentences; an empty list means it is whole."""
    bad = []
    for key in ("id", "name", "family", "real_model", "support", "assets", "marks", "actions", "facts"):
        if key not in spec:
            bad.append("missing '%s'" % key)
    if spec.get("support") not in SUPPORT:
        bad.append("support must be one of %s" % (SUPPORT,))
    assets = spec.get("assets", {})
    if not assets.get("gun"):
        bad.append("assets.gun is empty: the weapon's model")
    marks = spec.get("marks", {})
    for name, m in marks.items():
        if not _vec(m.get("at")):
            bad.append("mark %s: 'at' must be [x, y, z] in cm" % name)
        if "axis" in m and not _vec(m["axis"]):
            bad.append("mark %s: 'axis' must be [x, y, z]" % name)
        if m.get("status") not in STATUS:
            bad.append("mark %s: status must be measured or proposed" % name)
        if not m.get("source"):
            bad.append("mark %s: no source (where the number comes from)" % name)
    if spec.get("support") == "two_hand" and "support_l" not in marks:
        bad.append("a two-hand weapon needs a support_l mark for the left hand")
    if "grip_r" not in marks:
        bad.append("no grip_r mark for the right hand")
    for aname, a in spec.get("actions", {}).items():
        beats = a.get("beats", [])
        if not beats:
            bad.append("action %s has no beats" % aname)
        for b in beats:
            if "name" not in b:
                bad.append("action %s: a beat without a name" % aname)
            if b.get("mark") and b["mark"] not in marks:
                bad.append("action %s, beat %s: mark %s is not in marks" % (aname, b.get("name"), b["mark"]))
            if b.get("hand") not in (None, "l", "r"):
                bad.append("action %s, beat %s: hand must be l or r" % (aname, b.get("name")))
    for f in spec.get("facts", []):
        if not f.get("id") or not f.get("claim"):
            bad.append("a fact needs an id and a claim")
        if not f.get("source"):
            bad.append("fact %s: no source" % f.get("id"))
        kind = f.get("check", {}).get("kind")
        if kind not in FACT_KINDS:
            bad.append("fact %s: check kind must be one of %s" % (f.get("id"), FACT_KINDS))
        m = f.get("check", {}).get("mark")
        if m and m not in marks:
            bad.append("fact %s: mark %s is not in marks" % (f.get("id"), m))
    vb = spec.get("limits", {}).get("view_budget")
    if vb is not None and not all(isinstance(vb.get(k), (int, float)) for k in ("lower_left", "bottom_middle", "total")):
        bad.append("limits.view_budget needs lower_left, bottom_middle and total (shares 0..1)")
    return bad


def diff(a, b, path=""):
    """What changed between two specs, key by key."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = "%s.%s" % (path, k) if path else k
            if k not in a:
                out.append({"path": p, "added": b[k]})
            elif k not in b:
                out.append({"path": p, "removed": a[k]})
            else:
                out += diff(a[k], b[k], p)
    elif a != b:
        out.append({"path": path, "was": a, "now": b})
    return out


def write_spec(spec):
    bad = validate(spec)
    if bad:
        raise ValueError("the spec is not whole: " + "; ".join(bad))
    p = path_of(spec["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    before = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    p.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return diff(before, spec)
