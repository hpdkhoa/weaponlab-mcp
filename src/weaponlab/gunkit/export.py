"""Gun Kit's export: one gun's files made ready for a game to import, in staging only. A project's adapter decides how
its game reads them; this writes the general part:
  <build>/export/
    SK_<name>_Clips.fbx           the gun rigged, with its own clips (one take a clip)
    arms/<clip>.fbx               each hand clip on the shared arms
    import_plan.json              what goes where: the gun, its clips, the arms clips, the staging folder
    <game_id>.json                a draft of the game's data file: the base definition with Gun Kit's fields set
The game's own numbers (damage, rate, calibre) come from the base: a dump of the gun as the game has it now.

Roles of the hand clips, as the game's data file names them (ArmsClips): idle, hold, walk, run, fire, reload_fast,
reload_empty, check_mag, check_chamber, charge, equip, holster."""
import json
import shutil
from pathlib import Path

from . import actions as A

HAND_ROLE = {"idle": "idle", "walk": "walk", "run": "run", "fire": "fire", "reload": "reload_fast",
             "reload_empty": "reload_empty", "check_mag": "check_mag", "check_chamber": "check_chamber",
             "charge": "charge", "cycle": "charge", "equip": "equip", "holster": "holster"}
GUN_FIELD = {"fire": "ArmsGunFire", "fire_last": "ArmsGunFireLast", "reload": "ArmsGunReloadFast",
             "reload_empty": "ArmsGunReloadEmpty", "charge": "ArmsGunCharge", "cycle": "ArmsGunCharge",
             "check_chamber": "ArmsGunPressCheck", "check_mag": "ArmsGunCheckMag"}


def asset(folder, name):
    return "%s/%s.%s" % (folder.rstrip("/"), name, name)


def export(facts_path, game_id, base=None, game_folder="/Game/Guns", staging="/Game/Staging/Guns", rig="Shared"):
    """Stages one gun: its FBX files, the import plan and a draft data file. base: the game's current definition of
    the gun (a dict or a path to a dump), whose numbers the draft keeps."""
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    build = Path(facts_path).parent
    a = A.load(facts["action"])
    clips = json.loads((build / "clips.json").read_text(encoding="utf-8"))
    hands = json.loads((build / "hands" / "hands.json").read_text(encoding="utf-8"))
    out = build / "export"
    (out / "arms").mkdir(parents=True, exist_ok=True)
    shutil.copy2(clips["fbx"], out / Path(clips["fbx"]).name)
    arms = {}
    for cid, h in hands["clips"].items():
        fbx = next((w for w in h["written"] if w.endswith(".fbx")), None)
        if fbx:
            dst = out / "arms" / Path(fbx).name
            shutil.copy2(fbx, dst)
            arms[cid] = {"fbx": str(dst), "clip": h["clip"]}
    folder = "%s/%s" % (game_folder, game_id)
    mesh = "SK_%s" % game_id
    plan = {"gun": {"fbx": str(out / Path(clips["fbx"]).name), "name": mesh, "clips": [c["clip"] for c in clips["clips"]],
                    "rate": 60},
            "arms": [{"fbx": v["fbx"], "name": v["clip"]} for v in arms.values()],
            "staging": "%s/%s" % (staging, game_id), "dest": folder, "approved_by": None}
    (out / "import_plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    d = dict(base) if isinstance(base, dict) else (json.loads(Path(base).read_text(encoding="utf-8")) if base else {})
    d.pop("_about", None)
    d["_about"] = ("%s, drafted by Gun Kit from %s (action %s); the game's numbers from its dump. A draft: it goes to "
                   "Content/Data/Guns only after the Gate and the user" % (game_id, facts["name"], a["id"]))
    d["Id"] = game_id
    if facts.get("proxy"):
        d["DisplayName"] = "TEST MODEL (%s proxy)" % a["id"]      # a proxy never ships: its name says what it is
    d["ArmsRig"] = rig
    d["ArmsGun"] = asset(folder, mesh)
    d["ArmsGunNoIrons"] = ""
    d["ArmsGunOffset"] = dict(zip("XYZ", hands["placement"]["bolt_face_in_gun_bone_cm"]))
    d["ArmsGunRot"] = {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}
    d["ArmsGunScale"] = 1.0
    d["ArmsMuzzle"] = dict(zip("XYZ", facts["marks"].get("muzzle", [0.0, 40.0, 0.0])))
    d["ChamberAt"] = {"X": 0.0, "Y": 0.0, "Z": 0.0}
    if "port" in facts["marks"]:
        d["EjectPort"] = dict(zip("XYZ", facts["marks"]["port"]))
    if facts.get("magazine"):
        d["ArmsMagBone"] = facts["magazine"]["bone"]
        d["ArmsMagMesh"] = ""          # the magazine is the rig's own bone: its clips carry it, in the hand too
    for cid, field in GUN_FIELD.items():
        if cid in a["gun_clips"]:
            d[field] = asset(folder, "A_%s_%s" % (facts["name"], cid))
    d["ArmsClips"] = {HAND_ROLE[cid]: asset(folder, v["clip"]) for cid, v in arms.items() if cid in HAND_ROLE}
    if "idle" in arms:
        d["ArmsClips"]["hold"] = d["ArmsClips"]["idle"]
    # the chamber check's open stretch (the round shows): the action's own expectation of the port in view
    cc = a["hand_clips"].get("check_chamber", {})
    seen = next((x["at"] for x in cc.get("expect", []) if "visible" in x and isinstance(x["at"], list)), None)
    if seen:
        d["ChamberOpen"] = {"X": seen[0], "Y": seen[1]}
    charge = a["hand_clips"].get("charge") or a["hand_clips"].get("cycle")
    if charge:
        d["HandChargeSeconds"] = charge["seconds"]
    d["EmptyReloadCut"] = 0.0
    # the special paths of the old rigs do not apply to a gun with its own clips
    for k in ("ArmsChamberClip", "ArmsChargeClip", "ArmsMagHoldClip", "ArmsClipSuffix", "ArmsHandBone", "ArmsPressBone",
              "ArmsMagHandBone", "ArmsGunChargeLocked", "ArmsGunLoad", "ArmsGunLoadStart", "ArmsGunLoadEnd"):
        d.pop(k, None)
    (out / ("%s.json" % game_id)).write_text(json.dumps(d, indent=1), encoding="utf-8")
    # the same file for a trial before the import is approved: every asset in the staging folder (the game reads it
    # with -GunData=<folder>, Game Probe's trial)
    trial = json.loads(json.dumps(d).replace('"%s/' % folder, '"%s/%s/' % (staging, game_id)))
    trial["_about"] = "TRIAL of " + d["_about"]
    (out / "trial").mkdir(exist_ok=True)
    (out / "trial" / ("%s.json" % game_id)).write_text(json.dumps(trial, indent=1), encoding="utf-8")
    return {"folder": str(out), "plan": plan, "data_file": str(out / ("%s.json" % game_id)), "trial_folder": str(out / "trial"),
            "hand_checks": {c: {k: h["checks"].get(k) for k in ("clearance_worst_cm", "anatomy_break_frames", "grip_break_frames")}
                            for c, h in hands["clips"].items() if isinstance(h.get("checks"), dict)}}
