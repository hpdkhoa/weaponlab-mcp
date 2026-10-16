"""The digitizer's file contracts, as JSON Schema files beside this module, and their checks.

    weaponlab-sources/1    one gun's sources: files and licenses, pages, figures (scale, frame), facts
    weaponlab-blueprint/1  the gun's visual copy as data: each part's shape, holes, role, motion, finish, sources
    weaponlab-partsmap/1   how a model maps onto its action (the blueprint's build writes one)

check(doc) gives every problem as a sentence, empty when the document follows its contract: first the schema, then
what a schema cannot say (ids that must exist, the source of every number, the scale's own sum)."""
import json
import math
from functools import lru_cache
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
NAMES = {"weaponlab-sources/1": "sources", "weaponlab-blueprint/1": "blueprint", "weaponlab-partsmap/1": "partsmap"}


@lru_cache(maxsize=None)
def schema(name):
    """A contract's JSON Schema, by its short name (sources, blueprint, partsmap) or its full id."""
    short = NAMES.get(name, name)
    return json.loads((HERE / ("%s.schema.json" % short)).read_text(encoding="utf-8"))


def _schema_problems(doc, name):
    v = jsonschema.Draft202012Validator(schema(name))
    out = []
    for e in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in e.absolute_path) or "(top)"
        msg = e.message if len(e.message) < 300 else e.message[:300] + "..."
        out.append("%s: %s" % (where, msg))
    return out


def check_sources(doc):
    bad = _schema_problems(doc, "sources")
    if bad:
        return bad
    ids = [s["id"] for s in doc["sources"]]
    for i in {i for i in ids if ids.count(i) > 1}:
        bad.append("sources: id %s is used twice" % i)
    pages = {s["id"]: s.get("pages") for s in doc["sources"]}
    for kind in ("pages", "figures", "facts"):
        for n, x in enumerate(doc.get(kind, [])):
            if x["source"] not in pages:
                bad.append("%s/%d: source %s is not in sources" % (kind, n, x["source"]))
            elif pages[x["source"]] and x["page"] > pages[x["source"]]:
                bad.append("%s/%d: page %d is past the source's %d pages" % (kind, n, x["page"], pages[x["source"]]))
    for kind in ("figures", "facts"):
        xs = [x["id"] for x in doc.get(kind, [])]
        for i in {i for i in xs if xs.count(i) > 1}:
            bad.append("%s: id %s is used twice" % (kind, i))
    facts = {f["id"] for f in doc.get("facts", [])}
    for f in doc.get("figures", []):
        s = f.get("scale")
        if s:
            px = math.dist(s["a"], s["b"])
            if px <= 0:
                bad.append("figure %s: the scale's two points are the same" % f["id"])
            elif abs(px * s["cm_per_px"] - s["cm"]) > 0.005 * s["cm"]:
                bad.append("figure %s: %.2f px at %.5f cm a px is %.3f cm, not the %.3f cm given"
                           % (f["id"], px, s["cm_per_px"], px * s["cm_per_px"], s["cm"]))
            if s.get("fact") and s["fact"] not in facts:
                bad.append("figure %s: the scale's fact %s is not in facts" % (f["id"], s["fact"]))
        if f["kind"] in ("side", "section") and f.get("to_scale") is not False and "shows" not in f:
            bad.append("figure %s: a side view says which side it shows (right or left)" % f["id"])
    return bad


# the numbers each shape and motion kind holds, and so the keys its part's sources must have
NEEDS = {"extrude": ("outline", "x"), "lathe": ("profile", "axis"),
         "slide": ("axis", "travel_cm"), "turn": ("axis", "turn_deg", "pivot"), "free": ()}


def check_blueprint(doc, sources=None, action=None):
    """sources: the gun's sources document (checks every figure and fact a ref names); action: its action file
    (checks the roles). Both load from the blueprint when not given and they can be found."""
    bad = _schema_problems(doc, "blueprint")
    if bad:
        return bad
    if sources is None:
        p = Path(doc["sources"])
        if p.exists():
            sources = json.loads(p.read_text(encoding="utf-8"))
    if action is None:
        try:
            from ..gunkit import actions as A
            action = A.load(doc["action"])
        except Exception as e:                     # an unknown action is itself a problem
            bad.append("action %s: %s" % (doc["action"], e))
    figs = {f["id"] for f in (sources or {}).get("figures", [])}
    facts = {f["id"] for f in (sources or {}).get("facts", [])}

    def ref_ok(where, r):
        if sources is None:
            return
        if "figure" in r and r["figure"] not in figs:
            bad.append("%s: figure %s is not in the sources" % (where, r["figure"]))
        if "fact" in r and r["fact"] not in facts:
            bad.append("%s: fact %s is not in the sources" % (where, r["fact"]))

    roles = set((action or {}).get("parts", {}))
    for pid, p in doc["parts"].items():
        sh, mo = p["shape"], p.get("motion")
        for key in NEEDS[sh["kind"]] + (NEEDS[mo["kind"]] if mo else ()) + (("bevel_cm",) if p.get("bevel_cm") else ()):
            if key not in p["sources"]:
                bad.append("part %s: no source for its %s" % (pid, key))
        for key, r in p["sources"].items():
            ref_ok("part %s %s" % (pid, key), r)
        for n, h in enumerate(p.get("holes", [])):
            ref_ok("part %s hole %d" % (pid, n), h["source"])
        if sh["kind"] == "extrude" and sh["x"][0] >= sh["x"][1]:
            bad.append("part %s: its x runs from the right (x0) to the left (x1); x0 < x1" % pid)
        if sh["kind"] == "lathe" and any(r < 0 for _, r in sh["profile"]):
            bad.append("part %s: a lathe profile's radius is never below 0" % pid)
        if action is not None and p["role"] != "body" and p["role"] not in roles:
            bad.append("part %s: role %s is not body or a part of %s (%s)" % (pid, p["role"], doc["action"], ", ".join(sorted(roles))))
        if p.get("parent") and p["parent"] not in doc["parts"]:
            bad.append("part %s: parent %s is not a part" % (pid, p["parent"]))
        if p["role"] != "body" and not mo:
            bad.append("part %s: a moving part (%s) needs its motion" % (pid, p["role"]))
    if action is not None:
        have = {p["role"] for p in doc["parts"].values()}
        for role, want in action["parts"].items():
            if want.get("required", True) and role not in have:
                bad.append("the action %s needs a part with role %s (%s)" % (doc["action"], role, want.get("what", "")))
        for m in action.get("marks", []):
            if m not in doc["marks"]:
                bad.append("the action %s needs the mark %s" % (doc["action"], m))
    for m, x in doc["marks"].items():
        ref_ok("mark %s" % m, x["source"])
    for m, chain in doc.get("mark_parts", {}).items():
        if m not in doc["marks"]:
            bad.append("mark_parts: %s is not a mark" % m)
        for pid in [chain] if isinstance(chain, str) else chain:
            if pid not in doc["parts"]:
                bad.append("mark_parts: %s rides %s, which is not a part" % (m, pid))
    return bad


def check_partsmap(doc, action=None):
    bad = _schema_problems(doc, "partsmap")
    if bad:
        return bad
    if action is None:
        try:
            from ..gunkit import actions as A
            action = A.load(doc["action"])
        except Exception as e:
            return ["action %s: %s" % (doc["action"], e)]
    for role, p in doc["parts"].items():
        if role not in action["parts"]:
            bad.append("part %s is not a part of %s (%s)" % (role, doc["action"], ", ".join(action["parts"])))
        if p.get("parent") and p["parent"] not in doc["parts"]:
            bad.append("part %s: parent %s is not a part" % (role, p["parent"]))
    for m, chain in doc.get("mark_parts", {}).items():
        if m not in doc["marks"]:
            bad.append("mark_parts: %s is not a mark" % m)
        for role in [chain] if isinstance(chain, str) else chain:
            if role not in doc["parts"]:
                bad.append("mark_parts: %s rides %s, which is not a part" % (m, role))
    if doc["model"] is None and not doc.get("proxy"):
        bad.append("model: only a proxy has no model file")
    if doc["forward"].strip("+-") == doc["up"].strip("+-"):
        bad.append("forward and up lie on one axis")
    return bad


def check(doc, **kw):
    """Every problem with a document, by its contract field."""
    name = NAMES.get(doc.get("contract") if isinstance(doc, dict) else None)
    if not name:
        return ["contract: one of %s, got %r" % (", ".join(NAMES), doc.get("contract") if isinstance(doc, dict) else doc)]
    return {"sources": check_sources, "blueprint": check_blueprint, "partsmap": check_partsmap}[name](doc, **kw)


def check_file(path, **kw):
    return check(json.loads(Path(path).read_text(encoding="utf-8")), **kw)
