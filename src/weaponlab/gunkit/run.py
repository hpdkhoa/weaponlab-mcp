"""Gun Kit's steps that need Blender, run headless one at a time (the probe's guard waits for other heavy jobs). Every
step writes under the project's work folder, gunkit/<name>/: nothing reaches a game until the export step stages it
and the project imports it."""
import json
import subprocess
import time
from pathlib import Path

from .. import probe as P
from ..config import project
from . import actions as A
from . import facts as F
from . import proxy as X
from . import rigplan as R
from . import timeline as T

SCRIPTS = Path(__file__).resolve().parent / "blender"
PKG = Path(__file__).resolve().parents[2]          # the folder that holds the weaponlab package (src)


def folder(name):
    d = Path(project().work) / "gunkit" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _blender(script, job, out, timeout=1800, tag="GUNKIT"):
    P.guard()
    jf = Path(out) / ("%s.job.json" % Path(script).stem)
    jf.write_text(json.dumps(job, indent=1), encoding="utf-8")
    p = subprocess.run([str(project().blender()), "-b", "--factory-startup", "-P", str(SCRIPTS / script), "--", str(jf)],
                       capture_output=True, text=True, timeout=timeout)
    (Path(out) / ("%s.log" % Path(script).stem)).write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8", errors="replace")
    lines = [l for l in (p.stdout or "").splitlines() if l.startswith(tag)]
    if p.returncode != 0 or not lines:
        tail = [l for l in ((p.stdout or "") + (p.stderr or "")).splitlines() if l.strip()][-15:]
        raise RuntimeError("%s failed (see %s):\n%s" % (script, Path(out) / ("%s.log" % Path(script).stem), "\n".join(tail)))
    return lines


def rig(partsmap, shapes=None, name=None):
    """A gun rigged for its action from a parts map (a dict or a path). Returns its facts, checked against its action."""
    pm = partsmap if isinstance(partsmap, dict) else json.loads(Path(partsmap).read_text(encoding="utf-8"))
    out = folder(name or pm["name"])
    _blender("gunkit_rig.py", {"partsmap": pm, "shapes": shapes, "out": str(out), "pkg": str(PKG)}, out)
    facts = json.loads((out / "gunfacts.json").read_text(encoding="utf-8"))
    bad = F.check(facts, A.load(facts["action"]))
    return {"folder": str(out), "facts": str(out / "gunfacts.json"), "problems": bad, "model": facts["model"]}


def build_proxy(action_id):
    """An action's proxy gun, built and rigged (a test model: label every picture of it)."""
    px = X.proxy(action_id)
    return rig(px["partsmap"], px["shapes"])


def gun_clips(facts_path, clips=None, resolved=None):
    """The gun's own clips keyed on its rig and written as one FBX. resolved: {clip: [frames]} from the hand step,
    where a carried part's place comes from the hand (it replaces that clip's own timeline)."""
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    a = A.load(facts["action"])
    out = Path(facts_path).parent
    tracks = []
    for cid in clips or list(a["gun_clips"]):
        clip = (resolved or {}).get(cid) or T.gun_clip(a, facts, cid)
        tracks.append(R.tracks(facts, clip))
    blend = facts["model"]["blend"]
    _blender("gunkit_clips.py", {"blend": blend, "tracks": tracks, "prefix": "A_%s_" % facts["name"], "out": str(out)}, out)
    return json.loads((out / "clips.json").read_text(encoding="utf-8"))


def expected(facts, clip, t):
    """Where each bone's head and its three side points should be at t, from the timeline's sums (gun cm)."""
    fr = min(clip["frames"], key=lambda f: abs(f["t"] - t))
    byname = {b["name"]: b for b in facts["bones"]}
    role_of = {p["bone"]: r for r, p in facts["parts"].items()}

    def move(bone, pt):
        """pt carried by the bone's own move, then by its parent's (a child rides its parent)."""
        role = role_of.get(bone)
        if role:
            p = facts["parts"][role]
            v = fr["parts"].get(role, 0.0)
            head = byname[bone]["head"]
            if p["kind"] == "slide":
                pt = [pt[i] + p["axis"][i] * p["travel_cm"] * v for i in range(3)]
            elif p["kind"] == "turn":
                pt = T._rot(pt, head, p["axis"], p["turn_deg"] * v)
            elif isinstance(v, list):
                pt = [pt[i] + v[i] for i in range(3)]
        parent = byname[bone].get("parent")
        return move(parent, pt) if parent and parent != "Root" else pt

    out = {}
    for b in facts["bones"]:
        h = b["head"]
        pts = {"head": h, "x": [h[0] + 3, h[1], h[2]], "y": [h[0], h[1] + 3, h[2]], "z": [h[0], h[1], h[2] + 3]}
        out[b["name"]] = {k: move(b["name"], v) for k, v in pts.items()}
    return out


def verify(facts_path, times=(0.0, 0.25, 0.5, 0.75, 1.0), tol_cm=0.05):
    """The keyed clips read back from Blender against the timeline's sums: the worst gap a clip, in cm."""
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    a = A.load(facts["action"])
    out = Path(facts_path).parent
    plan = {}
    for cid in a["gun_clips"]:
        secs = a["gun_clips"][cid]["seconds"]
        plan["A_%s_%s" % (facts["name"], cid)] = sorted({round(round(secs * x * T.FPS) / T.FPS, 5) for x in times})   # on frames
    _blender("gunkit_readback.py", {"blend": str(out / ("%s_clips.blend" % facts["name"])), "clips": plan, "out": str(out)}, out)
    got = json.loads((out / "readback.json").read_text(encoding="utf-8"))
    report = {}
    for cid in a["gun_clips"]:
        name = "A_%s_%s" % (facts["name"], cid)
        clip = T.gun_clip(a, facts, cid)
        worst = 0.0
        for t in plan[name]:
            want = expected(facts, clip, t)
            for bone, pts in want.items():
                for k, w in pts.items():
                    g = got[name][str(t)][bone][k]
                    worst = max(worst, max(abs(g[i] - w[i]) for i in range(3)))
        report[cid] = {"worst_cm": round(worst, 4), "ok": worst <= tol_cm}
    return report
