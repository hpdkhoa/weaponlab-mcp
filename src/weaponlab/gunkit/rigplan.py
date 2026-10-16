"""The rig plan: a parts map (proxy.py's or the user's) and where each part sits, turned into the gun facts. Pure
Python, so Blender's own Python runs it (gunkit_rig.py) and the tests run it without Blender.

One bone a part, named after its role (carrier -> Carrier, bolt_lift -> BoltLift), under Root. A bone points along +Y
with no roll, so its own axes are gun space's: a slide moves the bone's location along the part's axis, a turn turns
it round its head. A turning part's head is its pivot; a sliding part's head is its centre; a free part's head is
its feed lips when it has them (the magazine: the game puts the magazine's own mesh in that frame), else its
centre. A part with a parent (a revolver's cylinder on its crane) hangs from that part's bone and moves with it: its
axis is its rest axis, turned along with the parent."""
from . import actions as A
from . import facts as F


def bone_name(role):
    return "".join(w.title() for w in role.split("_"))


def plan(partsmap, centres, model=None):
    """The gun facts from a parts map and each part's centre in gun space (cm), {role: [x, y, z]}."""
    a = A.load(partsmap["action"])
    bones = [{"name": "Root", "head": [0.0, 0.0, 0.0]}]
    parts = {}
    for role, p in partsmap["parts"].items():
        want = a["parts"].get(role)
        if not want:
            raise ValueError("the %s action has no part %s; its parts: %s" % (a["id"], role, ", ".join(a["parts"])))
        kind = p.get("kind") or want["kind"]          # a gun may pick another kind its action allows
        if kind not in want.get("kinds", [want["kind"]]):
            raise ValueError("part %s: %s moves it as %s, not %s" % (role, a["id"], " or ".join(want.get("kinds", [want["kind"]])), kind))
        name = bone_name(role)
        if kind == "turn":
            head = list(p["pivot"])
            parts[role] = {"bone": name, "kind": "turn", "axis": list(p["axis"]), "turn_deg": float(p["turn_deg"]), "pivot": head}
        elif kind == "slide":
            head = list(centres.get(role, [0.0, 0.0, 0.0]))
            parts[role] = {"bone": name, "kind": "slide", "axis": list(p.get("axis", [0, -1, 0])),
                           "travel_cm": float(p.get("travel_cm", want.get("travel_cm", 1.0)))}
        else:
            lips = (partsmap.get("magazine") or {}).get("lips") if role in ("magazine", "cell") else None
            head = list(lips) if lips else list(centres.get(role, [0.0, 0.0, 0.0]))
            parts[role] = {"bone": name, "kind": "free"}
        parent = bone_name(p["parent"]) if p.get("parent") else "Root"     # a part that rides another (a revolver's
        bones.append({"name": name, "parent": parent, "head": [round(v, 4) for v in head],   # cylinder on its crane)
                      "objects": list(p.get("objects", []))})
        if p.get("parent"):
            parts[role]["parent"] = p["parent"]
    free = next((r for r, p in parts.items() if p["kind"] == "free" and r in ("magazine", "cell")), None)
    facts = {"contract": F.CONTRACT, "name": partsmap["name"], "action": a["id"],
             "model": model or {"source": "proxy" if partsmap.get("proxy") else "import"},
             "bones": bones, "parts": parts, "marks": {k: list(v) for k, v in partsmap["marks"].items()},
             "mark_parts": dict(partsmap.get("mark_parts", {})), "normals": dict(partsmap.get("normals", {})),
             "magazine": (dict({"bone": parts[free]["bone"], "lips": list(partsmap["magazine"]["lips"])},
                               **{k: partsmap["magazine"][k] for k in ("axis", "length_cm") if k in partsmap["magazine"]})
                          if free and (partsmap.get("magazine") or {}).get("lips") else None),
             "proxy": bool(partsmap.get("proxy")),
             "sources": list(partsmap.get("sources", []))}
    if facts["magazine"] is None:
        facts.pop("magazine")
    return facts


def tracks(facts, clip):
    """A clip's bone transforms by frame for Blender to key: {"fps", "seconds", "frames": [{"t", "bones": {name:
    {"loc": [x, y, z] cm, "rot": [deg, ax, ay, az]}}}]} from a timeline clip (timeline.gun_clip or hand_clip, its
    free parts resolved to offsets: a part still marked follow holds its last offset)."""
    out, last = [], {}
    for fr in clip["frames"]:
        bones = {}
        for role, p in facts["parts"].items():
            v = fr["parts"].get(role, 0.0)
            if p["kind"] == "slide":
                bones[p["bone"]] = {"loc": [a * p["travel_cm"] * v for a in p["axis"]], "rot": [0.0, 1.0, 0.0, 0.0]}
            elif p["kind"] == "turn":
                bones[p["bone"]] = {"loc": [0.0, 0.0, 0.0], "rot": [p["turn_deg"] * v] + list(p["axis"])}
            else:
                if isinstance(v, list):
                    last[role] = v
                elif isinstance(v, dict) and "at" in v:          # a hand step's resolved place for a carried part
                    last[role] = v["at"]
                    if "rot" in v:
                        bones[p["bone"]] = {"loc": list(v["at"]), "rot": list(v["rot"])}
                        continue
                bones[p["bone"]] = {"loc": list(last.get(role, [0.0, 0.0, 0.0])), "rot": [0.0, 1.0, 0.0, 0.0]}
        out.append({"t": fr["t"], "bones": bones})
    return {"clip": clip["clip"], "fps": clip["fps"], "seconds": clip["seconds"], "frames": out}
