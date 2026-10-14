"""Motion Lab: clips rebuilt in headless Blender, written as FBX for the project to stage and the Gate to judge.
- roll: a hand turned about its forearm through a clip (the twist bones share it); profile checks every frame stays
  inside the forearm's range (80 degrees each way from thumb up).
- track: a sliding part's track rebuilt on its axis from its seat (a carrier, a bolt, a pump).
- render: dev views of a parts dump (pictures that are not the game's view; label them so)."""
import json
import subprocess
from pathlib import Path

from . import probe as P
from .config import project

SCRIPTS = Path(__file__).resolve().parent / "blender"
ROLL_LIMIT_DEG = 80.0


def _blender(script, args, timeout=900, tag="MOTIONLAB"):
    P.guard()
    p = subprocess.run([str(project().blender()), "-b", "--factory-startup", "-P", str(SCRIPTS / script), "--"] + [str(a) for a in args],
                       capture_output=True, text=True, timeout=timeout)
    lines = [l for l in (p.stdout or "").splitlines() if l.startswith(tag)]
    if p.returncode != 0 or not lines:
        raise RuntimeError("%s failed: %s" % (script, ((p.stderr or "") + (p.stdout or ""))[-1500:]))
    return lines


def profile(fbx, side="r"):
    """The hand's roll about its forearm every few frames (0 thumb up); within_range false past 80 degrees."""
    lines = _blender("roll.py", [fbx, "-", side, "measure"])
    frames = next(l for l in lines if l.startswith("MOTIONLAB PROFILE ") and "WORST" not in l).split()[2:]
    worst = int(next(l for l in lines if "WORST" in l).split()[-1])
    return {"frames": {int(f): int(a) for f, a in (x.split(":") for x in frames)}, "worst_deg": worst, "within_range": worst <= ROLL_LIMIT_DEG}


def roll(src_fbx, out_fbx, side="r", degrees="auto"):
    """One clip's hand turned about its forearm (auto: the clip starts thumb up); the result's profile with it."""
    lines = _blender("roll.py", [src_fbx, out_fbx, side, degrees])
    deg = float(next(l for l in lines if l.startswith("MOTIONLAB ROLL ") and "CHECK" not in l and "DONE" not in l).split()[2])
    return {"out": str(out_fbx), "degrees": deg, "profile": profile(out_fbx, side)}


def roll_set(fbx_files, out_folder, suffix, side="r", degrees="auto"):
    """A set of clips rolled, each from its own start, written as <name>_<suffix>.fbx; each one's turn and worst
    roll. New names, not the old ones: other weapons may still play the originals."""
    out = Path(out_folder)
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    for f in fbx_files:
        dst = out / ("%s_%s.fbx" % (Path(f).stem, suffix))
        r = roll(f, dst, side, degrees)
        res[Path(f).stem] = {"out": str(dst), "degrees": r["degrees"], "worst_deg": r["profile"]["worst_deg"], "within_range": r["profile"]["within_range"]}
    return res


def track(src_fbx, out_fbx, bone, root, axis=None, seat=None):
    """A part's track rebuilt on its axis from its seat (blender/track.py)."""
    args = [src_fbx, out_fbx, bone, root]
    if axis:
        args.append(",".join(str(x) for x in axis))
        if seat:
            args.append(",".join(str(x) for x in seat))
    return {"out": str(out_fbx), "log": _blender("track.py", args)}


def render(objs, out_folder, views=("right", "left", "top", "bottom")):
    """Dev views of parts dumps (not the game's view): PNGs and the pieces' list in out_folder."""
    out = Path(out_folder)
    out.mkdir(parents=True, exist_ok=True)
    job = out / "job.json"
    job.write_text(json.dumps({"out": str(out), "dumps": [str(o) for o in objs], "render": True, "views": list(views)}), encoding="utf-8")
    _blender("render_parts.py", [job], timeout=3600, tag="RIGLAB")
    return json.loads((out / "riglab.json").read_text(encoding="utf-8"))
