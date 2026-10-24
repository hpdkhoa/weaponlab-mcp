"""Step 6: the blueprint as a model (Blender: one object a part) and the parts map Gun Kit rigs it from. The parts
map is written from the blueprint, so Gun Kit needs no draft: every moving part's objects, its motion, the marks and
which part each rides.

Then step 7 is Gun Kit's: run.rig(partsmap) and run.build_all(facts)."""
import json
import subprocess
from pathlib import Path

from .. import contracts as C
from ..config import project
from . import store

SCRIPT = Path(__file__).resolve().parent / "blender" / "blueprint_build.py"


def magazine_line(outline, axis=None):
    """A magazine's own line from its side outline: the direction of its longest straight side (a magazine's front
    and back run along its well; the points' spread would lean toward a slanted outline's diagonal), pointing down,
    out of the well; and its length along it. axis (gun space [x, y, z]): the well's own line where the blueprint gives
    it (the well guides the magazine), used instead of the side."""
    import math
    import numpy as np
    P = np.array([q[:2] for q in outline], dtype=float)
    segs = [b - a for a, b in zip(P, np.roll(P, -1, axis=0)) if np.linalg.norm(b - a) > 1e-9]
    # a traced side is many short segments: neighbours running the same way (within 8 degrees of the run's start) are
    # one straight run; the longest run is the magazine's front or back
    runs, cur = [], None
    for v in segs + segs[:1]:
        u = v / np.linalg.norm(v)
        if cur is not None and float(u @ cur[1]) >= math.cos(math.radians(8.0)):
            cur[0] += v
        else:
            if cur is not None:
                runs.append(cur[0])
            cur = [v.copy(), u]
    runs.append(cur[0])
    d = max(runs, key=lambda r: float(np.linalg.norm(r))) if axis is None else np.array(axis[1:3], dtype=float)
    d = d / np.linalg.norm(d)
    if d[1] > 0:
        d = -d
    proj = (P - P.mean(axis=0)) @ d
    return {"axis": [0.0, round(float(d[0]), 5), round(float(d[1]), 5)], "length_cm": round(float(proj.max() - proj.min()), 3)}


def partsmap(bp, blend):
    """The parts map for a built blueprint: Blender's world (metres, Y flipped), forward -Y, up +Z, origin 0."""
    parts = {}
    for pid, p in bp["parts"].items():
        if p["role"] == "body":
            continue
        q = parts.setdefault(p["role"], {"objects": []})
        q["objects"].append(pid)
        mo = p["motion"]
        if mo["kind"] in ("slide", "turn"):
            q["kind"] = mo["kind"]
            q["axis"] = mo["axis"]
        if mo["kind"] == "slide":
            q["travel_cm"] = mo["travel_cm"]
        elif mo["kind"] == "turn":
            q["turn_deg"] = mo["turn_deg"]
            q["pivot"] = mo["pivot"]
        if p.get("parent"):
            q["parent"] = bp["parts"][p["parent"]]["role"]
    role = {pid: p["role"] for pid, p in bp["parts"].items()}
    mark_parts = {}
    for m, chain in bp.get("mark_parts", {}).items():
        roles = [role[c] for c in ([chain] if isinstance(chain, str) else chain) if role[c] != "body"]
        if roles:
            mark_parts[m] = roles[0] if len(roles) == 1 else roles
    pm = {"contract": "weaponlab-partsmap/1", "name": bp["name"], "action": bp["action"], "model": str(blend),
          "units": "m", "forward": "-Y", "up": "+Z", "origin": [0.0, 0.0, 0.0], "parts": parts,
          "marks": {m: x["at"] for m, x in bp["marks"].items()}, "mark_parts": mark_parts,
          "normals": {m: x["normal"] for m, x in bp["marks"].items() if "normal" in x},
          "blueprint": str(Path(store.root() / bp["name"] / "blueprint.json").resolve())}
    if bp.get("magazine_lips"):
        pm["magazine"] = {"lips": bp["magazine_lips"]["at"]}
        mag = next((p for p in bp["parts"].values() if p["role"] in ("magazine", "cell")), None)
        if mag and mag["shape"]["kind"] in ("extrude", "views"):
            pm["magazine"].update(magazine_line(mag["shape"]["outline"] if mag["shape"]["kind"] == "extrude" else mag["shape"]["side"],
                                                (bp.get("magazine_line") or {}).get("axis")))
    src = json.loads(Path(bp["sources"]).read_text(encoding="utf-8")) if Path(bp["sources"]).exists() else {"sources": []}
    pm["sources"] = ["%s (%s)" % (s["title"], s.get("year", "")) for s in src["sources"]]
    return pm


def build(gun, segments=64, timeout=900):
    """Builds the model and writes model/<gun>.blend, model/build.json and model/partsmap.json. Refuses a blueprint
    that fails its contract."""
    bp = store.load(gun, "blueprint")
    bad = C.check_blueprint(bp)
    if bad:
        raise ValueError("the blueprint fails its contract (run the check):\n  " + "\n  ".join(bad[:20]))
    out = store.folder(gun, "model")
    jf = out / "build.job.json"
    jf.write_text(json.dumps({"blueprint": bp, "out": str(out), "segments": segments}), encoding="utf-8")
    p = subprocess.run([str(project().blender()), "-b", "--factory-startup", "-P", str(SCRIPT), "--", str(jf)],
                       capture_output=True, text=True, timeout=timeout)
    (out / "build.log").write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8", errors="replace")
    if p.returncode != 0 or "BLUEPRINT BUILD" not in (p.stdout or ""):
        tail = [l for l in ((p.stdout or "") + (p.stderr or "")).splitlines() if l.strip()][-15:]
        raise RuntimeError("the build failed (see %s):\n%s" % (out / "build.log", "\n".join(tail)))
    rep = json.loads((out / "build.json").read_text(encoding="utf-8"))
    pm = partsmap(bp, rep["blend"])
    # a gun with real knurling also gets a plain copy (no grooves, coarser reliefs) for the hand step's collision: the
    # grooves are finer than the skin's give and would only slow the distance grids
    if any(f.get("kind") == "knurl" for p_ in bp["parts"].values() for f in p_.get("features", [])):
        jp = out / "build_plain.job.json"
        jp.write_text(json.dumps({"blueprint": bp, "out": str(out), "segments": segments, "plain": True}), encoding="utf-8")
        q = subprocess.run([str(project().blender()), "-b", "--factory-startup", "-P", str(SCRIPT), "--", str(jp)],
                           capture_output=True, text=True, timeout=timeout)
        (out / "build_plain.log").write_text((q.stdout or "") + "\n" + (q.stderr or ""), encoding="utf-8", errors="replace")
        if q.returncode == 0 and "BLUEPRINT BUILD" in (q.stdout or ""):
            pm["collision_model"] = json.loads((out / "build_plain.json").read_text(encoding="utf-8"))["blend"]
    bad = C.check_partsmap(pm)
    (out / "partsmap.json").write_text(json.dumps(pm, indent=1), encoding="utf-8")
    return {"blend": rep["blend"], "parts": rep["parts"], "partsmap": str(out / "partsmap.json"), "partsmap_problems": bad}


def to_gunkit(gun, grip_steps=3):
    """Step 7: the built model through Gun Kit: rig, hand and gun clips, read-back."""
    from ..gunkit import run as R
    pm = store.folder(gun, "model") / "partsmap.json"
    if not pm.exists():
        raise FileNotFoundError("build the model first")
    from . import check as Ck
    fin = Ck.finish(store.load(gun, "blueprint"))
    if not fin["ok"]:
        # the full detail pass is the end result (the owner, 2026-10-24): a low poly gun does not go on to the game
        return {"stopped": "the detail pass is not done", "finish": fin}
    rep = store.folder(gun, "model") / "build.json"
    parts = (json.loads(rep.read_text(encoding="utf-8")).get("parts") or {}) if rep.exists() else {}
    broken = {k: v["mesh"] for k, v in parts.items() if v.get("mesh") and not v["mesh"].get("sound")}
    if broken:
        # a broken solid (an open edge, faces turned in) shades wrong and cannot be cut or checked: not done
        return {"stopped": "parts with broken meshes", "broken": broken}
    rigged = R.rig(str(pm))
    if rigged["problems"]:
        return {"rigged": rigged, "stopped": "the facts do not fit the action"}
    built = R.build_all(rigged["facts"], grip_steps=grip_steps)
    return {"facts": rigged["facts"], "built": built, "verify": R.verify(rigged["facts"])}


RENDER = Path(__file__).resolve().parent / "blender" / "blueprint_render.py"


def render(gun, cm_per_px=0.03, timeout=600):
    """The built model seen from its left and right sides square on (at cm_per_px) and from three quarters; each
    picture labelled as a Blueprint Lab model view, not a game view."""
    import cv2
    out = store.folder(gun, "model", "views")
    blend = store.folder(gun, "model") / ("%s.blend" % gun)
    if not blend.exists():
        raise FileNotFoundError("build the model first")
    jf = out / "render.job.json"
    jf.write_text(json.dumps({"out": str(out), "cm_per_px": cm_per_px}), encoding="utf-8")
    p = subprocess.run([str(project().blender()), "-b", str(blend), "-P", str(RENDER), "--", str(jf)],
                       capture_output=True, text=True, timeout=timeout)
    (out / "render.log").write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8", errors="replace")
    if p.returncode != 0 or "BLUEPRINT RENDER" not in (p.stdout or ""):
        tail = [l for l in ((p.stdout or "") + (p.stderr or "")).splitlines() if l.strip()][-15:]
        raise RuntimeError("the render failed (see %s):\n%s" % (out / "render.log", "\n".join(tail)))
    rep = json.loads((out / "render.json").read_text(encoding="utf-8"))
    for name, v in rep["views"].items():
        img = cv2.imread(v["file"])
        label = "BLUEPRINT LAB MODEL %s, %s (not a game view)" % (gun, name.replace("view_", "").replace("_", " "))
        cv2.rectangle(img, (0, 0), (min(img.shape[1], 12 + 9 * len(label)), 26), (255, 255, 255), -1)
        cv2.putText(img, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.imwrite(v["file"], img)
    return {k: v["file"] for k, v in rep["views"].items()}
