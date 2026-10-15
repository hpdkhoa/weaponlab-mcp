"""Gun facts (weaponlab-gunfacts/1): one gun made ready for its action, whatever drew it (Model Lab, or a model the
user brings and a parts map). Gun Kit's later steps read only this: the gun clips, the hand clips, the checks, the
game file.

Gun space, in cm: +Y toward the muzzle, +Z up, +X the gun's left; the origin is the bolt face at rest (the chamber).

    {"contract": "weaponlab-gunfacts/1",
     "name": "AK47", "action": "ak_handle",
     "model": {"source": "modellab" | "import", "file": "<the rigged FBX>", "blend": "<the .blend>", "triangles": n},
     "bones": [{"name": "Root"}, {"name": "Carrier", "parent": "Root", "head": [x, y, z]}, ...],
     "parts": {"carrier": {"bone": "Carrier", "kind": "slide", "axis": [0, -1, 0], "travel_cm": 13.0}, ...},
     "marks": {"muzzle": [x, y, z], "port": [...], "grip": [...], "support": [...], "mag_well": [...], ...},
     "normals": {"port": [x, y, z]},
     "magazine": {"bone": "Magazine", "lips": [x, y, z]},
     "slots": [{"name": "Receiver", "parts": ["Upper", "Lower"]}],
     "sources": ["where each number comes from"]}

A part's kind: "slide" moves along its axis by travel_cm; "turn" turns round its axis through its pivot by turn_deg;
"free" (the magazine) goes where the clip puts it."""
import json
import math
from pathlib import Path

CONTRACT = "weaponlab-gunfacts/1"
KINDS = ("slide", "turn", "free")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _vec(v, n=3):
    return isinstance(v, (list, tuple)) and len(v) == n and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)


def check(facts, action=None):
    """Problems with a gun's facts, against its action when given ([] when it is ready)."""
    bad = []
    if facts.get("contract") != CONTRACT:
        bad.append("contract: want %s, got %r" % (CONTRACT, facts.get("contract")))
    for key in ("name", "action", "bones", "parts", "marks"):
        if key not in facts:
            bad.append("no %s" % key)
    if bad:
        return bad
    names = {b.get("name") for b in facts["bones"]}
    for b in facts["bones"]:
        if b.get("parent") and b["parent"] not in names:
            bad.append("bone %s: no parent %s" % (b.get("name"), b["parent"]))
    for role, p in facts["parts"].items():
        if p.get("bone") not in names:
            bad.append("part %s: no bone %r" % (role, p.get("bone")))
        if p.get("kind") not in KINDS:
            bad.append("part %s: kind %r, want one of %s" % (role, p.get("kind"), ", ".join(KINDS)))
        if p.get("kind") in ("slide", "turn"):
            ax = p.get("axis")
            if not _vec(ax) or abs(math.sqrt(sum(a * a for a in ax)) - 1.0) > 1e-3:
                bad.append("part %s: axis must be a unit vector" % role)
        if p.get("kind") == "slide" and not (isinstance(p.get("travel_cm"), (int, float)) and p["travel_cm"] > 0):
            bad.append("part %s: travel_cm > 0" % role)
        if p.get("kind") == "turn":
            if not (isinstance(p.get("turn_deg"), (int, float)) and p["turn_deg"] != 0):
                bad.append("part %s: turn_deg not 0" % role)
            if not _vec(p.get("pivot")):
                bad.append("part %s: a turn needs its pivot" % role)
    for m, v in facts["marks"].items():
        if not _vec(v):
            bad.append("mark %s: [x, y, z] in cm" % m)
    if action:
        if facts["action"] != action["id"]:
            bad.append("action: the facts say %s, checked against %s" % (facts["action"], action["id"]))
        for role, want in action["parts"].items():
            if want.get("required", True) and role not in facts["parts"]:
                bad.append("the %s action needs the part %s (%s)" % (action["id"], role, want.get("what", "")))
            elif role in facts["parts"] and facts["parts"][role]["kind"] != want["kind"]:
                bad.append("part %s: the action moves it as %s, the facts say %s" % (role, want["kind"], facts["parts"][role]["kind"]))
        for m in action.get("marks", []):
            if m not in facts["marks"]:
                bad.append("the %s action needs the mark %s" % (action["id"], m))
        if "magazine" in action["parts"] and not facts.get("magazine"):
            bad.append("the %s action moves a magazine: facts.magazine {bone, lips}" % action["id"])
    return bad
