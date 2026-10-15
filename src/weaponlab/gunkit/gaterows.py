"""Gun Kit for the Gate: a built gun's checks as rows (provider "gunkit") and the cases every gun of an action gets.

The rows come from the build's own files: its facts (checked against its action), the gun clips read back from
Blender against the timeline (verify), and the hand clips' Pose Lab checks and expected sights (hands.json). The
export step registers each game id's build in <work>/gunkit/registry.json, so the provider finds it by weapon."""
import json
from pathlib import Path

from ..config import project
from . import actions as A
from . import facts as F

# metric: (unit, which way is better, tolerance, rule (op, value), about)
METRICS = {
    "gunkit.facts_problems": ("count", "lower", 0, ("==", 0), "the gun's facts against its action: every part and mark it needs"),
    "gunkit.readback_cm": ("cm", "lower", 0.01, ("<=", 0.05), "the gun's own clip as keyed in Blender against the timeline's sums"),
    "gunkit.clearance_cm": ("cm", "lower", 0.1, ("<=", 0.2), "the deepest a hand or forearm sits inside the gun over a hand clip (Pose Lab)"),
    "gunkit.anatomy_frames": ("frames", "lower", 0, ("==", 0), "frames of a hand clip that break an arm or finger rule (Pose Lab)"),
    "gunkit.grip_frames": ("frames", "lower", 0, ("==", 0), "frames of a hand clip that break a grip rule (Pose Lab)"),
    "gunkit.visible": ("share", "higher", 0.05, (">=", 0.5), "the share of a mark the eye sees where the action expects it in view (a port in a press check)"),
}


def registry():
    p = Path(project().work) / "gunkit" / "registry.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def register(game_id, build_folder):
    p = Path(project().work) / "gunkit" / "registry.json"
    reg = registry()
    reg[game_id] = str(build_folder)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reg, indent=1), encoding="utf-8")


def rows(weapon, build_folder=None, readback=None):
    """A weapon's rows from its build (the registry's, or the folder given). readback: verify()'s report when it was
    just run (else the build's last one, readback_report.json)."""
    folder = Path(build_folder or registry().get(weapon) or "")
    if not (folder / "gunfacts.json").exists():
        return [{"weapon": weapon, "action": "-", "metric": "note", "value": None, "note": "no Gun Kit build for %s" % weapon}]
    facts = json.loads((folder / "gunfacts.json").read_text(encoding="utf-8"))
    a = A.load(facts["action"])
    out = [{"weapon": weapon, "action": "build", "metric": "gunkit.facts_problems", "value": len(F.check(facts, a))}]
    rb = readback
    if rb is None and (folder / "readback_report.json").exists():
        rb = json.loads((folder / "readback_report.json").read_text(encoding="utf-8"))
    for clip, r in (rb or {}).items():
        out.append({"weapon": weapon, "action": "gun_" + clip, "metric": "gunkit.readback_cm", "value": r["worst_cm"]})
    hp = folder / "hands" / "hands.json"
    if hp.exists():
        h = json.loads(hp.read_text(encoding="utf-8"))
        for clip, v in h["clips"].items():
            cs = v.get("checks") or {}
            if isinstance(cs, dict) and "clearance_worst_cm" in cs:
                out += [{"weapon": weapon, "action": "hands_" + clip, "metric": "gunkit.clearance_cm", "value": cs["clearance_worst_cm"]},
                        {"weapon": weapon, "action": "hands_" + clip, "metric": "gunkit.anatomy_frames", "value": cs.get("anatomy_break_frames", 0)},
                        {"weapon": weapon, "action": "hands_" + clip, "metric": "gunkit.grip_frames", "value": cs.get("grip_break_frames", 0)}]
            for e in v.get("expect", []):
                if "visible" in e:
                    out.append({"weapon": weapon, "action": "hands_" + clip, "metric": "gunkit.visible", "value": e["visible"]["visible"]})
    return out


def cases(weapon, action_id, source="Gun Kit (weaponlab.gunkit), the action's template"):
    """Every case a gun of this action gets: the facts, each gun clip's read-back, each hand clip's checks and sights."""
    a = A.load(action_id)
    out = []

    def case(action, metric, about):
        op, value = METRICS[metric][3]
        out.append({"id": "%s-gk-%s-%s" % (weapon, action, metric.split(".")[1]), "weapon": weapon, "action": action, "metric": metric,
                    "rule": {"op": op, "value": value}, "about": about, "source": source})
    case("build", "gunkit.facts_problems", METRICS["gunkit.facts_problems"][4])
    for clip in a["gun_clips"]:
        case("gun_" + clip, "gunkit.readback_cm", "the %s clip keys what the action says" % clip)
    for clip, c in a["hand_clips"].items():
        for m in ("gunkit.clearance_cm", "gunkit.anatomy_frames", "gunkit.grip_frames"):
            case("hands_" + clip, m, "%s: %s" % (clip, METRICS[m][4]))
        if any("visible" in x for x in c.get("expect", [])):
            case("hands_" + clip, "gunkit.visible", "%s: %s" % (clip, METRICS["gunkit.visible"][4]))
    return out
