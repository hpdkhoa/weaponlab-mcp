"""A Model Lab build (modellab-mcp) as a Gun Kit parts map: Model Lab draws the gun, Gun Kit takes it from there. The
build's facts give the moving parts (bones with their travel, hinges, presses), the marks and every shape's bounds;
its .blend holds one mesh whose vertex groups are its bones. Model Lab's Blender world is Gun Kit's (metres, Y
flipped), so the parts map's forward is -Y, up +Z, units metres, origin the bolt face at 0.

A hand's mark goes where its palm meets the surface (Gun Kit's convention): the grip's right face for the right palm,
the magazine's left face for the left hand, a button's outer face; the rest are Model Lab's own marks."""
import json
from pathlib import Path

from . import proxy as X

PLATFORM_ACTION = {"ar15": "ar_gas"}


def _box(sb, *names):
    """The bounds of shapes taken together: [[x0, y0, z0], [x1, y1, z1]] (gun cm)."""
    got = [sb[n] for n in names if n in sb]
    if not got:
        return None
    return [[min(b[0][i] for b in got) for i in range(3)], [max(b[1][i] for b in got) for i in range(3)]]


def _mid(b, i):
    return round((b[0][i] + b[1][i]) / 2.0, 3)


def partsmap(build_folder):
    """The parts map of a Model Lab build (its folder under Model Lab's builds)."""
    folder = Path(build_folder)
    f = json.loads((folder / "facts.json").read_text(encoding="utf-8"))
    action = PLATFORM_ACTION.get(f.get("platform"))
    if not action:
        raise ValueError("Gun Kit knows Model Lab's platforms %s; this build is %s" % (", ".join(PLATFORM_ACTION), f.get("platform")))
    mv, mk, sb = f["moving"], f["marks"], f["shape_bounds"]
    at = lambda name: [round(v, 3) for v in mk[name]["at"]]       # noqa: E731
    parts = {
        "carrier": {"vertex_groups": ["Bolt"], "axis": mv["Bolt"]["axis"], "travel_cm": mv["Bolt"]["travel_cm"]},
        "handle": {"vertex_groups": ["ChargingHandle"], "axis": mv["ChargingHandle"]["axis"], "travel_cm": mv["ChargingHandle"]["travel_cm"]},
        "magazine": {"vertex_groups": ["Magazine", "MagRound"]},
    }
    if "DustCover" in mv:
        parts["cover"] = {"vertex_groups": ["DustCover"], "axis": mv["DustCover"]["axis"], "turn_deg": mv["DustCover"]["open_deg"],
                          "pivot": [round(v, 3) for v in mv["DustCover"]["hinge"]]}
    if "BoltCatch" in mv:
        parts["catch"] = {"vertex_groups": ["BoltCatch"], "axis": [0, 0, 1], "travel_cm": mv["BoltCatch"]["lift_cm"]}
    if "MagRelease" in mv:
        parts["release"] = {"vertex_groups": ["MagRelease"], "axis": mv["MagRelease"]["axis"], "travel_cm": mv["MagRelease"]["press_cm"]}
    if "ForwardAssist" in mv:
        parts["assist"] = {"vertex_groups": ["ForwardAssist"], "axis": mv["ForwardAssist"]["axis"], "travel_cm": mv["ForwardAssist"]["press_cm"]}
    tb = _box(sb, "Trigger")
    if "Trigger" in mv and tb:
        parts["trigger"] = {"vertex_groups": ["Trigger"], "axis": [1, 0, 0], "turn_deg": mv["Trigger"]["pull_deg"],
                            "pivot": [0.0, _mid(tb, 1), round(tb[1][2], 3)]}
    grip = _box(sb, "Grip")
    mag = _box(sb, "Magazine_Body")
    wing = _box(sb, "Charging_Wing", "Charging_Latch")
    marks = {"muzzle": at("muzzle"), "trigger": at("trigger"), "support": at("support_l"),
             "port": at("eject_port"), "mag_well": at("magwell"), "mag_lips": at("mag_lips"),
             "grip": [round(grip[0][0], 3), _mid(grip, 1), _mid(grip, 2)] if grip else at("grip_r"),
             "mag_grab": [round(mag[1][0], 3), _mid(mag, 1), round(mag[0][2] + (mag[1][2] - mag[0][2]) * 0.3, 3)] if mag else at("mag_lips"),
             "handle": [round(wing[1][0], 3), _mid(wing, 1), _mid(wing, 2)] if wing else at("charging_handle")}
    for name, shape, side in (("catch", "BoltCatch", 1), ("release", "MagRelease", 0), ("assist", "ForwardAssist", 0)):
        b = _box(sb, shape)
        if b:
            marks[name] = [round(b[side][0], 3), _mid(b, 1), _mid(b, 2)]
    return {"contract": X.CONTRACT, "name": "ML_" + f["name"], "action": action, "model": str(folder / ("%s.blend" % f["name"])),
            "units": "m", "forward": "-Y", "up": "+Z", "origin": [0.0, 0.0, 0.0], "parts": parts, "marks": marks,
            "mark_parts": {"handle": "handle", "mag_grab": "magazine", "mag_lips": "magazine"},
            # which way each hand mark's surface faces (a palm is laid facing into it): the grip's right face, under
            # the handguard, the magazine's left face, the handle's left wing, the catch on the left, buttons on the right
            "normals": {"port": mk["eject_port"].get("normal", [-1.0, 0.0, 0.0]), "grip": [-1.0, 0.0, 0.0],
                        "support": [0.0, 0.0, -1.0], "mag_grab": [1.0, 0.0, 0.0], "handle": [1.0, 0.0, 0.0],
                        "catch": [1.0, 0.0, 0.0], "release": [-1.0, 0.0, 0.0], "assist": [-1.0, 0.0, 0.0]},
            "magazine": {"lips": at("mag_lips")},
            "sources": ["Model Lab build %s (%s, %s)" % (folder.name, f.get("platform"), f.get("params", {}).get("barrel_in", "?"))]}
