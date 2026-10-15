"""A first parts map for a model of the user's own, from what inspect found (run.inspect) and the gun's action: each
part guessed from the objects' and vertex groups' names, the marks a hand needs guessed from the parts' shapes, the
model's forward, units and bolt face guessed from its bounds. Every guess goes on the draft's "check" list: the user
(or a person with the model open) confirms or corrects them before the rig step. Nothing here is measured."""
import re

from . import actions as A
from . import proxy as X

# names a part goes by in models (lower case, matched as words or parts of names)
WORDS = {
    "carrier": r"carrier|bcg|bolt.?carrier|op.?rod|operating",
    "bolt": r"\bbolt\b|bolt(?!.?(carrier|catch|release|knob|handle|stop))",
    "bolt_lift": r"bolt.?(knob|handle)|knob",
    "handle": r"charg|cocking|\bhandle\b",
    "magazine": r"\bmag\b|magazine|\bclip\b(?!.?(strip|charger))",
    "cell": r"cell|battery|power",
    "trigger": r"trigger",
    "cover": r"dust|ejection.?(port.?)?cover|feed.?cover|top.?cover",
    "catch": r"bolt.?(catch|release)|slide.?(stop|release)",
    "stop": r"slide.?stop",
    "release": r"mag.?(release|catch|button)|paddle",
    "assist": r"forward.?assist",
    "slide": r"\bslide\b(?!.?stop)",
    "hammer": r"hammer",
    "pump": r"pump|fore.?end|forend",
    "lever": r"\blever\b|loop",
    "crane": r"crane|yoke",
    "cylinder": r"cylinder",
    "ejector": r"ejector",
    "barrel": r"barrel",
    "latch": r"latch",
    "string": r"string",
    "safety": r"safety|selector",
}
AXES = {"X": 0, "Y": 1, "Z": 2}


def _match(name, role):
    pat = WORDS.get(role)
    return bool(pat and re.search(pat, name.lower()))


def draft(inspect, action_id, model, name=None):
    """A parts map to start from: {"partsmap": {...}, "check": [what to confirm]}."""
    a = A.load(action_id)
    check = []
    ax = inspect["longest_axis"]
    i = AXES[ax]
    lo, hi = inspect["min"], inspect["max"]
    # the muzzle: the end of the longest axis nearer the barrel's object, else the end with less of the model in it
    barrel = next((o for o in inspect["objects"] if re.search(r"barrel|muzzle", o["name"].lower())), None)
    if barrel:
        sign = "+" if barrel["centre"][i] > (lo[i] + hi[i]) / 2 else "-"
    else:
        ahead = sum(o["vertices"] for o in inspect["objects"] if o["centre"][i] > (lo[i] + hi[i]) / 2)
        behind = sum(o["vertices"] for o in inspect["objects"] if o["centre"][i] <= (lo[i] + hi[i]) / 2)
        sign = "+" if ahead < behind else "-"
        check.append("forward: guessed %s%s from where the model is thinner; confirm the muzzle is that way" % (sign, ax))
    forward = sign + ax
    up = "+Z" if ax != "Z" else "+Y"
    check.append("up: guessed %s; confirm the sights are on top that way" % up)
    units = inspect["units_guess"]
    check.append("units: guessed %s from a length of %.3f Blender units" % (units, inspect["length_units"]))
    # each part: the objects (or vertex groups) whose names say it
    parts = {}
    for role, want in a["parts"].items():
        objs = [o["name"] for o in inspect["objects"] if _match(o["name"], role)]
        groups = sorted({g["name"] for o in inspect["objects"] for g in o["vertex_groups"] if _match(g["name"], role)})
        if role == "carrier" and not objs and not groups:
            # many models call the carrier group the bolt (it holds the bolt): taken when nothing else is the bolt
            if "bolt" not in a["parts"]:
                objs = [o["name"] for o in inspect["objects"] if _match(o["name"], "bolt")]
                groups = sorted({g["name"] for o in inspect["objects"] for g in o["vertex_groups"] if _match(g["name"], "bolt")})
                if objs or groups:
                    check.append("part carrier: taken from what the model calls the bolt; confirm it is the carrier group")
        if not objs and not groups:
            if want.get("required", True):
                check.append("part %s (%s): no object or group named for it; name the objects that move as it" % (role, want.get("what", "")))
            continue
        p = {"objects": objs} if objs else {"vertex_groups": groups}
        if want["kind"] == "slide":
            p["axis"] = [0.0, -1.0, 0.0]
            p["travel_cm"] = want.get("travel_cm", 1.0)
            check.append("part %s: slides back along the bore %.1f cm (the action's typical travel); measure it on the model" % (role, p["travel_cm"]))
        elif want["kind"] == "turn":
            p["axis"] = [1.0, 0.0, 0.0]
            p["turn_deg"] = 30.0
            p["pivot"] = [0.0, 0.0, 0.0]
            check.append("part %s: turns; give its axis, its angle and its pivot (gun space, cm)" % role)
        parts[role] = p
    # where the gun's origin goes (the bolt face): the top of the magazine where there is one, else the model's middle
    mag = next((o for o in inspect["objects"] if _match(o["name"], "magazine")), None)
    scale = {"m": 100.0, "cm": 1.0, "mm": 0.1}[units]
    if mag:
        origin = list(mag["centre"])
        origin[2] = mag["max"][2]
        check.append("origin: the bolt face guessed at the top of the magazine; move it to the bolt face's centre")
    else:
        origin = [(lo[k] + hi[k]) / 2 for k in range(3)]
        check.append("origin: the bolt face guessed at the model's middle; move it to the bolt face's centre")
    # marks the action's hands need, guessed: the proxy's layout scaled to the model's length (a starting point only)
    length_cm = inspect["length_units"] * scale
    px = X.proxy(action_id)["partsmap"]
    proxy_len = 100.0 if action_id not in ("pistol_slide", "revolver_swing", "energy_cell_pistol") else 25.0
    k = length_cm / proxy_len
    marks = {m: [round(v * k, 2) for v in px["marks"][m]] for m in a.get("marks", []) if m in px["marks"]}
    check.append("marks: every mark is the proxy's place scaled to this model's length (%.0f cm): set each where the hand "
                 "meets the surface (grip: the right palm on the grip's right side; support: the left palm under the "
                 "handguard; the rest as the action names them)" % length_cm)
    pm = {"contract": X.CONTRACT, "name": name or re.sub(r"\W+", "_", inspect["model"].replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]),
          "action": action_id, "model": model, "units": units, "forward": forward, "up": up, "origin": [round(v, 4) for v in origin],
          "parts": parts, "marks": marks, "mark_parts": dict(px.get("mark_parts", {})), "normals": dict(px.get("normals", {})),
          "magazine": {"lips": marks.get("mag_lips")} if marks.get("mag_lips") else None}
    return {"partsmap": pm, "check": check}
