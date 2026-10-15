"""Gun actions (weaponlab-action/1): how one kind of gun works, as data. A gun names its action in its facts; the
action says which parts move and how far, when each part moves in each of the gun's own clips (beats), and where the
hands go in each hand clip (events), with the sources of the timings.

    {"contract": "weaponlab-action/1", "id": "ar_gas", "name": "...", "guns": ["AR-15", "M4A1"],
     "manuals": [{"title": "...", "covers": "...", "status": "to read" | "read"}],
     "parts": {"carrier": {"kind": "slide", "what": "...", "travel_cm": 8.4, "required": true}, ...},
     "marks": ["grip", "support", "port", ...],
     "gun_clips": {"fire": {"seconds": 0.12, "beats": [BEAT, ...]}, ...},
     "hand_clips": {"reload": {"seconds": 2.4, "loop": false, "gun": [POSE, ...], "events": [EVENT, ...],
                               "expect": [EXPECT, ...]}, ...},
     "sources": ["..."]}

BEAT, a part moving in the gun's own clip, from its value at `from` to `value` by `to` (seconds):
    {"part": "carrier", "from": 0.0, "to": 0.03, "value": 1.0, "ease": "out", "why": "..."}
  value is a share of the part's travel (slide) or turn (turn), 0 at rest. A free part (the magazine) takes
  "offset": [x, y, z] cm in gun space from its seat instead, or "follow": "l" / "r" (it rides that hand's grasp).

EVENT, a hand going somewhere and staying there until its next event:
    {"hand": "l", "from": 0.3, "to": 0.6, "go": TARGET, "ease": "inout", "grasp": "palm", "carry": "magazine"}
  TARGET: {"mark": "support"} a mark on the gun; {"part": "handle", "mark": "handle"} a mark riding a moving part;
  {"part": "magazine"} the magazine where it is; {"place": "pouch_l"} a place on the body (PLACES).
  carry: the named free part rides the hand from this event on, until an event puts it back ("seat": "magazine").
  At 0 the right hand holds "grip" and the left "support", unless the clip's first events say otherwise.

POSE, the gun's turn and move from its hold, in degrees and cm (absolute, eased from the pose before):
    {"from": 0.2, "to": 0.5, "roll": -35, "pitch": 10, "yaw": 0, "move": [0, -5, 6], "ease": "inout"}

EXPECT, what the clip must show, checked on the result:
    {"at": [0.9, 1.6], "visible": "port"}    the mark faces the eye and nothing hides it
    {"at": 2.4, "seated": "magazine"}        the free part back at its seat
    {"at": [0, 0.5], "on": {"r": "grip"}}     a hand on its mark"""
import json
from pathlib import Path

CONTRACT = "weaponlab-action/1"
HERE = Path(__file__).resolve().parent / "actions"
EASES = ("linear", "in", "out", "inout", "snap", "spring")
GUN_CLIPS = ("fire", "fire_last", "reload", "reload_empty", "charge", "check_chamber", "check_mag", "cycle")
HAND_CLIPS = ("idle", "walk", "run", "fire", "reload", "reload_empty", "check_mag", "check_chamber", "charge", "cycle",
              "equip", "holster")
# places on the body, in view space (cm from the eye: +Y ahead, +Z up, +X left), for a right-handed shooter
PLACES = {
    "pouch_l": [9.0, -2.0, -52.0],      # a magazine pouch on the belt, front left
    "chest_l": [7.0, 8.0, -32.0],       # a chest rig pouch, left of centre
    "dump": [14.0, -6.0, -60.0],        # a dump pouch on the left hip
    "drop": [4.0, 20.0, -140.0],        # the ground below the gun: a magazine let fall
    "eye_check": [3.0, 26.0, -8.0],     # held up before the eye to look at
    "belt_r": [-16.0, 0.0, -55.0],      # the right hip: a holster, a speed loader pouch
    "low_ready": [0.0, 30.0, -38.0],    # where a gun points while not aimed
}


def path():
    return HERE


def ids():
    """The actions a gun can name (a base, its name starting with _, only lends clips)."""
    return sorted(p.stem for p in HERE.glob("*.json") if not p.stem.startswith("_"))


def load(action_id):
    """An action, with what its base lends it ("extends": a file whose hand clips, gun clips, marks and sources it
    takes where it has none of its own)."""
    p = HERE / ("%s.json" % action_id)
    if not p.exists():
        raise ValueError("no action %r; actions: %s" % (action_id, ", ".join(ids())))
    a = json.loads(p.read_text(encoding="utf-8"))
    if a.get("extends"):
        base = load(a["extends"])
        for key in ("hand_clips", "gun_clips"):
            a[key] = {**base.get(key, {}), **a.get(key, {})}
        a["marks"] = list(dict.fromkeys(base.get("marks", []) + a.get("marks", [])))
        a["sources"] = base.get("sources", []) + a.get("sources", [])
        a["manuals"] = base.get("manuals", []) + a.get("manuals", [])
    return a


def summary():
    out = {}
    for i in ids():
        a = load(i)
        out[i] = {"name": a["name"], "guns": a.get("guns", []), "parts": list(a["parts"]),
                  "gun_clips": list(a.get("gun_clips", {})), "hand_clips": list(a.get("hand_clips", {}))}
    return out


def _t(x):
    return isinstance(x, (int, float)) and x >= 0


def check(action):
    """Problems with an action file ([] when it is sound)."""
    bad = []
    if action.get("contract") != CONTRACT:
        bad.append("contract: want %s" % CONTRACT)
    for k in ("id", "name", "parts", "gun_clips", "hand_clips"):
        if k not in action:
            bad.append("no %s" % k)
    if bad:
        return bad
    parts = action["parts"]
    for role, p in parts.items():
        if p.get("kind") not in ("slide", "turn", "free"):
            bad.append("part %s: kind %r" % (role, p.get("kind")))
    for cid, c in action["gun_clips"].items():
        if cid not in GUN_CLIPS:
            bad.append("gun clip %s: not one of %s" % (cid, ", ".join(GUN_CLIPS)))
        secs = c.get("seconds")
        if not (isinstance(secs, (int, float)) and secs > 0):
            bad.append("gun clip %s: seconds > 0" % cid)
            continue
        for b in c.get("beats", []):
            where = "gun clip %s, beat %s" % (cid, b.get("part"))
            if b.get("part") not in parts:
                bad.append("%s: no such part" % where)
                continue
            if not (_t(b.get("from")) and _t(b.get("to")) and b["from"] <= b["to"] <= secs + 1e-6):
                bad.append("%s: from <= to <= seconds" % where)
            if b.get("ease", "inout") not in EASES:
                bad.append("%s: ease %r" % (where, b.get("ease")))
            free = parts[b["part"]]["kind"] == "free"
            if free and not ("offset" in b or "follow" in b):
                bad.append("%s: a free part takes offset or follow" % where)
            if not free and not isinstance(b.get("value"), (int, float)):
                bad.append("%s: value (a share of the travel)" % where)
            if not b.get("why"):
                bad.append("%s: why (the source or the reason)" % where)
    for cid, c in action["hand_clips"].items():
        if cid not in HAND_CLIPS:
            bad.append("hand clip %s: not one of %s" % (cid, ", ".join(HAND_CLIPS)))
        secs = c.get("seconds")
        if not (isinstance(secs, (int, float)) and secs > 0):
            bad.append("hand clip %s: seconds > 0" % cid)
            continue
        for e in c.get("events", []):
            where = "hand clip %s, %s hand at %s" % (cid, e.get("hand"), e.get("from"))
            if e.get("hand") not in ("l", "r"):
                bad.append("%s: hand l or r" % where)
            if not (_t(e.get("from")) and _t(e.get("to")) and e["from"] <= e["to"] <= secs + 1e-6):
                bad.append("%s: from <= to <= seconds" % where)
            go = e.get("go", {})
            if "place" in go and go["place"] not in PLACES:
                bad.append("%s: no place %s" % (where, go["place"]))
            if "part" in go and go["part"] not in parts:
                bad.append("%s: no part %s" % (where, go["part"]))
            if "mark" in go and go["mark"] not in action.get("marks", []) and "part" not in go:
                bad.append("%s: mark %s is not in the action's marks" % (where, go["mark"]))
            for k in ("carry", "seat"):
                if k in e and (e[k] not in parts or parts[e[k]]["kind"] != "free"):
                    bad.append("%s: %s needs a free part" % (where, k))
            if e.get("ease", "inout") not in EASES:
                bad.append("%s: ease %r" % (where, e.get("ease")))
        for g in c.get("gun", []):
            if not (_t(g.get("from")) and _t(g.get("to")) and g["from"] <= g["to"] <= secs + 1e-6):
                bad.append("hand clip %s, gun pose at %s: from <= to <= seconds" % (cid, g.get("from")))
        for x in c.get("expect", []):
            if "visible" in x and x["visible"] not in action.get("marks", []):
                bad.append("hand clip %s: expects %s visible, not a mark" % (cid, x["visible"]))
            if "seated" in x and x["seated"] not in parts:
                bad.append("hand clip %s: expects %s seated, not a part" % (cid, x["seated"]))
    return bad
