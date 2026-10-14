"""The probe contract (weaponlab-probe/1): what Weapon Lab hands a game's probe and what it takes back. A probe is any
program that runs the game, plays each weapon's actions and measures them. It reads a job file and writes a rows
file; it may also write screenshots and parts dumps. docs/PROBE_CONTRACT.md explains each field; this module checks
them, so a probe can be tested on its own (`weaponlab contract job|rows|parts <file>`).

Frame for every position: the gun's space, in cm. +Y runs along the barrel toward the muzzle, +Z is up, +X is the
gun's left. A probe that works in another frame converts before it writes."""
import json
import math
from pathlib import Path

CONTRACT = "weaponlab-probe/1"
ROLES = ("arms", "gun", "part", "item")

# The metrics a probe may report, by name. A probe reports the ones it can measure; the Gate judges only the rows it
# gets. A project adds its own in its metrics.json (any name with a dot works).
STANDARD_METRICS = {
    "hands.arms_shown": ("0/1", "higher", "the weapon is held by visible arms"),
    "hands.l_gap_cm": ("cm", "lower", "the left palm's distance to the gun's surface, the worst over the action"),
    "hands.r_gap_cm": ("cm", "lower", "the right palm's distance to the gun's surface, the worst over the action"),
    "hands.r_handle_gap_cm": ("cm", "lower", "the right palm's distance to the grip, the worst over the action"),
    "hands.l_drift_cm": ("cm", "lower", "how far the left hand moves in the gun's space during the action"),
    "hands.l_to_support_cm": ("cm", "lower", "the left palm's distance to the spec's support mark"),
    "hands.r_hold_drift_cm": ("cm", "lower", "how far a held melee weapon moves in the right hand during the action"),
    "view.cover_total": ("share", "lower", "the share of the screen the arms and weapon cover"),
    "view.cover_lower_left": ("share", "lower", "the share of the screen's lower left third they cover"),
    "view.cover_bottom_middle": ("share", "lower", "the share of the screen's bottom middle third they cover"),
    "view.hand_l_shown": ("share", "higher", "the share of the left hand the player sees"),
    "view.hand_r_shown": ("share", "higher", "the share of the right hand the player sees"),
    "view.item_shown": ("share", "higher", "the share of a carried item (a magazine, a shell) the player sees"),
    "parts.copies_magazine": ("count", "none", "magazines drawn at once (one in the well, one in the hand at most)"),
    "events.played": ("0/1", "higher", "the action's clip played"),
    "events.item_in_hand": ("0/1", "none", "an item was in the hand during the action"),
    "swing.edge_lead": ("cos", "higher", "how well a melee blade's edge leads its cut (1: the edge, 0: the flat)"),
}
# families a probe may report with its own suffix: events.<bone>_travel_cm, hands.l_ride_<bone>_cm
STANDARD_FAMILIES = {
    "events.*_travel_cm": ("cm", "higher", "how far a spec's moving bone travels during the action"),
    "hands.l_ride_*_cm": ("cm", "lower", "the left hand's distance to a moving part it rides (a pump), the worst but one sample"),
}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(_num(x) for x in v)


def check_job(job):
    """Every problem with a job, as sentences; empty when it follows the contract."""
    bad = []
    if not isinstance(job, dict):
        return ["a job is a JSON object"]
    if job.get("contract", CONTRACT) != CONTRACT:
        bad.append("contract is %r; this core speaks %s" % (job.get("contract"), CONTRACT))
    if not isinstance(job.get("out"), str) or not job.get("out"):
        bad.append("out: the rows file's path is required")
    ws = job.get("weapons")
    if not isinstance(ws, list):
        bad.append("weapons: a list is required")
        ws = []
    for i, w in enumerate(ws):
        where = "weapons[%d]" % i
        if not isinstance(w, dict) or not isinstance(w.get("id"), str) or not w.get("id"):
            bad.append("%s: id is required" % where)
            continue
        where = "weapon %s" % w["id"]
        acts = w.get("actions")
        if not isinstance(acts, list) or not acts:
            bad.append("%s: actions must be a non-empty list" % where)
            acts = []
        for a in acts:
            if not isinstance(a, dict) or not isinstance(a.get("name"), str) or not a.get("name"):
                bad.append("%s: every action needs a name" % where)
                continue
            if "seconds" in a and not (_num(a["seconds"]) and a["seconds"] > 0):
                bad.append("%s, %s: seconds must be a positive number" % (where, a["name"]))
            if "at" in a and not (isinstance(a["at"], list) and all(_num(t) and t >= 0 for t in a["at"])):
                bad.append("%s, %s: at must be a list of seconds" % (where, a["name"]))
            if "run" in a and not isinstance(a["run"], str):
                bad.append("%s, %s: run must be a string (the probe's own command for the action)" % (where, a["name"]))
        if "tag" in w and not isinstance(w["tag"], str):
            bad.append("%s: tag must be a string" % where)
        if "support_l" in w and not _vec3(w["support_l"]):
            bad.append("%s: support_l must be [x, y, z] in cm, gun space" % where)
        if "bones" in w and not (isinstance(w["bones"], dict) and all(isinstance(v, str) for v in w["bones"].values())):
            bad.append("%s: bones maps a mark's name to a bone name" % where)
        if "tune" in w and not isinstance(w["tune"], dict):
            bad.append("%s: tune maps a field to its value" % where)
    if "overrides" in job and not (isinstance(job["overrides"], dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in job["overrides"].items())):
        bad.append("overrides maps an asset to the staged asset that stands in for it")
    for k in ("shots", "parts"):
        if k in job and not isinstance(job[k], str):
            bad.append("%s must be a folder path (empty for none)" % k)
    if "slomo" in job and not (_num(job["slomo"]) and 0 < job["slomo"] <= 1):
        bad.append("slomo must be in (0, 1]")
    for k in ("quit", "view", "trace", "bones"):
        if k in job and not isinstance(job[k], bool) and k != "bones":
            bad.append("%s must be true or false" % k)
    return bad


def check_rows(data, job=None):
    """Every problem with a rows file; empty when it follows the contract. With the job, also every row's weapon and
    action must be one the job asked for (a tagged entry reports as "<id>@<tag>")."""
    bad = []
    if isinstance(data, list):
        data = {"rows": data}
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return ["a rows file is an object with a 'rows' list"]
    asked = None
    if job:
        asked = set()
        for w in job.get("weapons", []):
            wid = w["id"] + ("@" + w["tag"] if w.get("tag") else "")
            for a in w.get("actions", []):
                asked.add((wid, a["name"]))
    seen = set()
    for i, r in enumerate(data["rows"]):
        where = "rows[%d]" % i
        if not isinstance(r, dict):
            bad.append("%s: a row is an object" % where)
            continue
        for k in ("weapon", "action", "metric"):
            if not isinstance(r.get(k), str) or not r.get(k):
                bad.append("%s: %s is required (a string)" % (where, k))
        if "value" not in r:
            bad.append("%s: value is required (a number, or null when it could not be measured)" % where)
        elif r["value"] is not None and not _num(r["value"]):
            bad.append("%s: value must be a finite number or null" % where)
        if "note" in r and not isinstance(r["note"], str):
            bad.append("%s: note must be a string" % where)
        if isinstance(r.get("metric"), str) and r["metric"] != "note" and "." not in r["metric"]:
            bad.append("%s: metric %r: metric names are <group>.<name>" % (where, r["metric"]))
        k = (r.get("weapon"), r.get("action"), r.get("metric"))
        if r.get("metric") != "note":
            if k in seen:
                bad.append("%s: %s|%s|%s reported twice" % ((where,) + k))
            seen.add(k)
        if asked is not None and r.get("weapon") != "_probe" and (r.get("weapon"), r.get("action")) not in asked:
            bad.append("%s: %s|%s was not in the job" % (where, r.get("weapon"), r.get("action")))
    if "notes" in data and not (isinstance(data["notes"], list) and all(isinstance(n, str) for n in data["notes"])):
        bad.append("notes must be a list of strings")
    return bad


def read_parts(path):
    """A parts dump: {"groups": {(role, component, asset, bone): {"verts": [[x,y,z]], "tris": [[i,j,k]]}},
    "eye": [x,y,z] or None, "header": {key: [words]} from '# key ...' lines}. Triangle indices are into the group's
    own verts."""
    groups, header, eye, cur, verts, owner = {}, {}, None, None, [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("# "):
                t = line[2:].split()
                if t and t[0] == "eye" and len(t) >= 4:
                    eye = [float(x) for x in t[1:4]]
                elif t:
                    header[t[0]] = t[1:]
            elif line.startswith("g "):
                parts = line[2:].strip().split("|")
                cur = tuple((parts + ["-"] * 4)[:4])
                groups.setdefault(cur, {"verts": [], "tris": [], "_map": {}})
            elif line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
                owner.append(cur)
                if cur is not None:
                    g = groups[cur]
                    g["_map"][len(verts)] = len(g["verts"])
                    g["verts"].append(verts[-1])
            elif line.startswith("f ") and cur is not None:
                idx = [int(x.split("/")[0]) for x in line.split()[1:4]]
                g = groups[cur]
                if all(i in g["_map"] for i in idx):
                    g["tris"].append([g["_map"][i] for i in idx])
    for g in groups.values():
        g.pop("_map")
    return {"groups": groups, "eye": eye, "header": header}


def check_parts(path):
    """Every problem with a parts dump; empty when it follows the contract."""
    bad = []
    try:
        d = read_parts(path)
    except (OSError, ValueError) as e:
        return ["unreadable: %s" % e]
    if not d["groups"]:
        bad.append("no groups ('g <role>|<component>|<asset>|<bone>')")
    for key, g in d["groups"].items():
        if key[0] not in ROLES:
            bad.append("group %s: role must be one of %s" % ("|".join(key), ROLES))
        if not g["verts"]:
            bad.append("group %s: no vertices" % "|".join(key))
        if len(g["tris"]) * 3 < len(g["verts"]) and not g["tris"]:
            bad.append("group %s: no triangles" % "|".join(key))
    if not any(k[0] in ("gun", "part") for k in d["groups"]):
        bad.append("no 'gun' or 'part' group: the weapon's own model must be in the dump")
    return bad


def check_file(kind, path, job_path=None):
    """The checks above on a file: kind is job, rows or parts."""
    if kind == "parts":
        return check_parts(path)
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if kind == "job":
        return check_job(data)
    job = json.loads(Path(job_path).read_text(encoding="utf-8-sig")) if job_path else None
    return check_rows(data, job)


def shot_name(weapon, action, t=None):
    """The file name a probe gives a screenshot (and, with .obj, a parts dump) at a moment."""
    return "%s_%s.png" % (weapon, action) if t is None else "%s_%s_%.2f.png" % (weapon, action, t)


def parts_name(weapon, action, t):
    return "%s_%s_%.2f.obj" % (weapon, action, t)
