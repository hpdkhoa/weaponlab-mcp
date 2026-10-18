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
    # what was keyed, by clip, with which clips the hand step resolved (verify checks those against their keys)
    (out / "keyed_tracks.json").write_text(json.dumps({"resolved": sorted(resolved or {}), "tracks": {t["clip"]: t for t in tracks}}),
                                           encoding="utf-8")
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


def expected_keyed(facts, track, t):
    """Where each bone's head and its three side points should be at t, from the tracks keyed (a resolved clip): a
    bone turns round its head, then moves by its loc, then rides its parent (Blender's pose, in gun space)."""
    fr = min(track["frames"], key=lambda f: abs(f["t"] - t))
    byname = {b["name"]: b for b in facts["bones"]}

    def move(bone, pt):
        x = fr["bones"].get(bone)
        if x:
            head = byname[bone]["head"]
            deg, ax, ay, az = x["rot"]
            n = (ax * ax + ay * ay + az * az) ** 0.5
            if deg and n:
                pt = T._rot(pt, head, [ax / n, ay / n, az / n], deg)
            pt = [pt[i] + x["loc"][i] for i in range(3)]
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
    kp = out / "keyed_tracks.json"
    keyed = json.loads(kp.read_text(encoding="utf-8")) if kp.exists() else {"resolved": [], "tracks": {}}
    report = {}
    for cid in a["gun_clips"]:
        name = "A_%s_%s" % (facts["name"], cid)
        clip = T.gun_clip(a, facts, cid)
        res = cid in keyed["resolved"] and cid in keyed["tracks"]
        worst = 0.0
        for t in plan[name]:
            want = expected_keyed(facts, keyed["tracks"][cid], t) if res else expected(facts, clip, t)
            for bone, pts in want.items():
                for k, w in pts.items():
                    g = got[name][str(t)][bone][k]
                    worst = max(worst, max(abs(g[i] - w[i]) for i in range(3)))
        report[cid] = {"worst_cm": round(worst, 4), "ok": worst <= tol_cm, "against": "keyed (hand step)" if res else "timeline"}
    (out / "readback_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def arms():
    """The shared arms the hand clips are made on: weaponlab.json "gunkit": {"arms": {"folder", "arms", "idle", "eye"}}
    (the folder holds the arms' FBX and an idle clip of the same skeleton; the eye in the arms' space, cm)."""
    a = (project().config.get("gunkit") or {}).get("arms")
    if not a:
        raise RuntimeError('weaponlab.json has no "gunkit": {"arms": {"folder", "arms", "idle", "eye"}}: the shared arms')
    a = dict(a)
    f = Path(a["folder"])
    a["folder"] = str(f if f.is_absolute() else Path(project().root) / f)
    return a


def _body_ranges(ch):
    """The human size ranges for the character's sex (Pose Lab's human_sizes), or None when Pose Lab has none."""
    try:
        from poselab_mcp.sizes import ranges
    except ImportError:
        return None
    return ranges((ch or {}).get("sex", "male"))


def hands(facts_path, clips=None, grip_steps=3, render=False, style=None, character=None, diagnose=(), options=None):
    """The hand clips on the shared arms (Pose Lab's Lab in Blender): each written as FBX and bone data, with Pose
    Lab's clipping, anatomy and grip checks, the expected sights (a port in view) and the carried parts' tracks.
    style: a grip style id (default the action family's); character: a character id (default the project's). The
    character's glove is counted in the palm's place, the fingers' closure and the clearance allowed."""
    import poselab_mcp
    from . import setup as SU
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    a = A.load(facts["action"])
    st = SU.style(style) if style else SU.style_for(facts["action"])
    ch = SU.character(character)
    out = Path(facts_path).parent / "hands"
    out.mkdir(exist_ok=True)
    want = clips or list(a["hand_clips"])
    tl = {cid: T.hand_clip(a, facts, cid) for cid in want}
    tracks = {cid: R.tracks(facts, c) for cid, c in tl.items()}
    job = {"poselab": str(Path(poselab_mcp.__file__).resolve().parent / "blender"), "arms": arms(),
           "gun_fbx": facts["model"]["file"], "facts": facts, "clips": tl, "tracks": tracks,
           "prefix": "A_%s_Hands_" % facts["name"], "out": str(out), "grip_steps": grip_steps, "render": render,
           "style": st, "character": ch, "glove_cm": SU.glove_cm(ch), "diagnose": list(diagnose),
           # no bone and no part of the skin of a size no adult has (Pose Lab's body_size, ANSUR II ranges)
           "body_ranges": _body_ranges(ch),
           # the grip style's reference hold (a pack's hand, in the grip's frame), kept beside the guns' folders
           "reference": reference_for(facts_path, st)}
    job.update(options or {})          # the hand step's own switches (solver_*, regrip, arc_cm ...), for trials
    _blender("gunkit_hands.py", job, out, timeout=7200)
    return json.loads((out / "hands.json").read_text(encoding="utf-8"))


def references_dir(facts_path):
    """Where reference holds live: beside the guns' folders (work/gunkit/references), in the project, never in a
    package (a pack's numbers keep its licence)."""
    return Path(facts_path).resolve().parent.parent / "references"


def reference_for(facts_path, style):
    """The grip style's reference hold (references/<style id>.json), or None when it has none yet."""
    from . import reference as REF
    if not style:
        return None
    f = references_dir(facts_path) / ("%s.json" % style["id"])
    if not f.exists():
        return None
    ref = json.loads(f.read_text(encoding="utf-8"))
    bad = REF.check(ref)
    if bad:
        raise ValueError("%s: %s" % (f, "; ".join(bad)))
    return ref


def pack_hold(fbx, style, clip, gun, bones, out, frame=None, keep=None, source=None):
    """A reference hold read from a pack's first-person clip at one frame (gunkit_pack_hold.py): each hand's points
    in the grip's frame, its digits' bends. out: the reference file to write (references/<style>.json). Returns its
    path and any faults."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = _blender("gunkit_pack_hold.py", {"fbx": str(fbx), "clip": clip, "frame": frame, "style": style, "gun": gun,
                                             "bones": bones, "keep": keep or {}, "source": source or {}, "out": str(out)},
                     out.parent, timeout=600)
    return json.loads(lines[-1][len("GUNKIT "):])


def skin_variant(facts_path, name, offset_cm, below_z_cm=None):
    """A test skin of the gun: its grip (the body below below_z_cm, default 1.5 cm under the trigger) moved out by
    offset_cm along its normals (thicker; negative thinner), the rig kept. Returns the variant's FBX path."""
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    out = Path(facts_path).parent / "skins"
    out.mkdir(exist_ok=True)
    fbx = out / ("SK_%s_Rig_%s.fbx" % (facts["name"], name))
    bz = below_z_cm if below_z_cm is not None else facts["marks"]["trigger"][2] - 1.5
    job = {"gun_fbx": facts["model"]["file"], "out_fbx": str(fbx), "offset_cm": offset_cm, "below_z_cm": bz}
    _blender("gunkit_skin.py", job, out)
    return str(fbx)


def skin_check(facts_path, gun_fbx, name=None, style=None, character=None):
    """The hand clips as made, replayed on another skin of the same gun (gun_fbx, the same rig): every frame's
    clearance, the firing hand's hold and each hand's contact rules, measured; no hand is moved. A thicker skin
    shows as presses, a thinner one as gaps. Writes hands/skin_<name>/skin_check.json and returns it."""
    import poselab_mcp
    from . import setup as SU
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    a = A.load(facts["action"])
    st = SU.style(style) if style else SU.style_for(facts["action"])
    ch = SU.character(character)
    hands_dir = Path(facts_path).parent / "hands"
    name = name or Path(gun_fbx).stem
    out = hands_dir / ("skin_" + name)
    out.mkdir(parents=True, exist_ok=True)
    want = list(a["hand_clips"])
    tl = {cid: T.hand_clip(a, facts, cid) for cid in want}
    tracks = {cid: R.tracks(facts, cc) for cid, cc in tl.items()}
    job = {"poselab": str(Path(poselab_mcp.__file__).resolve().parent / "blender"), "arms": arms(),
           "gun_fbx": str(gun_fbx), "facts": facts, "clips": tl, "tracks": tracks,
           "prefix": "A_%s_Hands_" % facts["name"], "out": str(out), "grip_steps": 3, "render": False,
           "style": st, "character": ch, "glove_cm": SU.glove_cm(ch), "body_ranges": None,
           "skin_check": {"name": name, "clips_dir": str(hands_dir / "clips")}}
    _blender("gunkit_hands.py", job, out, timeout=7200)
    return json.loads((out / "skin_check.json").read_text(encoding="utf-8"))


def build_all(facts_path, grip_steps=3, style=None, character=None):
    """Every clip of one gun: the hand clips first (they settle where a carried part goes), then the gun's own clips
    with those parts' tracks. Returns both reports."""
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    a = A.load(facts["action"])
    h = hands(facts_path, grip_steps=grip_steps, style=style, character=character)
    resolved = {}
    for cid, v in h["clips"].items():
        if cid in a["gun_clips"] and any(isinstance(x, dict) and "at" in x for fr in v["resolved"]["frames"] for x in fr["parts"].values()):
            resolved[cid] = v["resolved"]
    c = gun_clips(facts_path, resolved=resolved)
    return {"hands": {k: v["checks"] for k, v in h["clips"].items()}, "holds": h.get("holds"), "clips": c, "resolved": list(resolved)}


def inspect(model):
    """What a model holds as Blender shows it after import: its objects, vertex groups, bounds, the longest axis and a
    units guess, to write its parts map from (and draft_partsmap's starting point)."""
    out = folder("inspect_" + Path(model).stem.replace(" ", "_"))
    _blender("gunkit_inspect.py", {"model": str(model), "out": str(out)}, out)
    return json.loads((out / "inspect.json").read_text(encoding="utf-8"))
