"""The probe client: builds a job (docs/PROBE_CONTRACT.md), starts the project's probe on it, waits, and takes back
rows that follow the contract. The probe itself is the game's own program; Weapon Lab never runs the game directly.

Actions come from the project's actions.json: {"*": {action: {seconds, run?, ...}}, "<weapon kind>": {...},
"spec": {action: {...}}}. A weapon gets its kind's table (or "*"); an action its spec lists gets the "spec" entry."""
import json
import subprocess
import sys
import time
from pathlib import Path

from . import contract as C
from . import spec as S
from .config import project

DEFAULT_ACTIONS = {"*": {"idle": {"run": "", "seconds": 1.6}}}


class Busy(RuntimeError):
    pass


def running(names=None):
    """Which of the named processes run now (the project's probe.busy list by default)."""
    names = set(names if names is not None else project().probe.get("busy", []))
    if not names:
        return []
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout
        seen = {line.split(",")[0].strip('"') for line in out.splitlines() if line}
    else:
        out = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True).stdout
        seen = {Path(line.strip()).name for line in out.splitlines() if line.strip()}
    return sorted(seen & names)


def guard(wait_s=None, allow=False):
    """Fails at once while a "refuse" process runs (the player's own game) unless allow; waits up to wait_s (the
    project's probe.wait_s by default) while a "busy" one runs (another heavy job), then raises Busy."""
    cfg = project().probe
    refuse = set(cfg.get("refuse", []))
    wait_s = cfg.get("wait_s", 0) if wait_s is None else wait_s
    end = time.time() + wait_s
    while True:
        now = running(set(cfg.get("busy", [])) | refuse)
        playing = [n for n in now if n in refuse]
        if playing and not allow:
            raise Busy("%s running: the probe does not run beside it" % ", ".join(playing))
        busy = [n for n in now if n not in refuse]
        if not busy:
            return
        if time.time() >= end:
            raise Busy("%s running: one heavy job at a time" % ", ".join(busy))
        time.sleep(15)


def actions_table():
    t = json.loads((project().data / "actions.json").read_text(encoding="utf-8-sig")) if (project().data / "actions.json").exists() else {}
    return {**DEFAULT_ACTIONS, **t}


def job_for(weapon_ids, actions=None, at=None, tune=None):
    """The job's weapons: each weapon's actions (its kind's table, its spec's own actions), its spec's moving bones
    and support mark, moments for shots and dumps, and tuned fields."""
    from . import gate as G
    arsenal = {w["id"]: w for w in G.weapons()}
    table = actions_table()
    specs = {s["id"] for s in S.list_specs()}
    out = []
    for wid in weapon_ids:
        w = arsenal.get(wid, {"id": wid})
        acts = dict(table.get(w.get("kind"), table["*"]))
        bones, support = {}, None
        if wid in specs:
            sp = S.read_spec(wid)
            for name in sp.get("actions", {}):
                if name in table.get("spec", {}):
                    acts[name] = table["spec"][name]
            for mname, m in sp.get("marks", {}).items():
                if m.get("bone"):
                    bones[mname] = m["bone"]
            if "support_l" in sp.get("marks", {}):
                support = sp["marks"]["support_l"]["at"]
        names = actions or list(acts)
        item = {"id": wid, "actions": [dict(name=n, **acts[n]) for n in names if n in acts]}
        if not item["actions"]:
            continue
        for a in item["actions"]:
            if at and a["name"] in at:
                a["at"] = list(at[a["name"]])
        if bones:
            item["bones"] = bones
        if support:
            item["support_l"] = support
        if tune and wid in tune:
            item["tune"] = tune[wid]
        out.append(item)
    return out


def run_job(weapons, overrides=None, shots=None, parts=None, slomo=None, view=True, timeout_s=None, extra=None):
    """One probe run: writes the job, starts the probe, checks the rows. A warm-up entry (the first weapon at idle)
    goes first and its rows are dropped: a first action can read wrong (docs/PROBE_CONTRACT.md, lessons)."""
    cfg = project().probe
    if not cfg.get("command"):
        raise RuntimeError("no probe: set probe.command in weaponlab.json (docs/PROBE_CONTRACT.md)")
    if weapons and cfg.get("warmup", True):
        idle = next((a for a in weapons[0]["actions"] if a["name"] == "idle"), {"name": "idle", "seconds": 1.0})
        weapons = [{"id": weapons[0]["id"], "tag": "warmup", "actions": [dict(idle, seconds=1.0)]}] + list(weapons)
    d = project().ensure("probe")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out, jobf = d / ("rows-%s.json" % stamp), d / ("job-%s.json" % stamp)
    job = {"contract": C.CONTRACT, "out": str(out).replace("\\", "/"), "weapons": weapons, "view": bool(view)}
    job.update(cfg.get("job_extra") or {})
    job.update(extra or {})
    if overrides:
        job["overrides"] = overrides
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        job["shots"] = str(shots).replace("\\", "/")
    if parts:
        Path(parts).mkdir(parents=True, exist_ok=True)
        job["parts"] = str(parts).replace("\\", "/")
    if slomo:
        job["slomo"] = slomo
    bad = C.check_job(job)
    if bad:
        raise ValueError("the job breaks the contract: " + "; ".join(bad))
    jobf.write_text(json.dumps(job, indent=1), encoding="utf-8")
    sub = {"{job}": str(jobf).replace("\\", "/"), "{work}": str(project().work).replace("\\", "/"), "{stamp}": stamp}
    cmd = []
    for c in cfg["command"]:
        for k, v in sub.items():
            c = c.replace(k, v)
        cmd.append(c)
    seconds = sum(sum(a.get("seconds", 2.0) + 3.0 for a in w["actions"]) for w in weapons) / (slomo or 1.0) + 90
    log = d / ("probe-%s.log" % stamp)
    with open(log, "w", encoding="utf-8") as lf:
        low = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) if cfg.get("low_priority") else 0
        p = subprocess.Popen(cmd, cwd=str(project().root), stdout=lf, stderr=subprocess.STDOUT, creationflags=low)
        try:
            p.wait(timeout=timeout_s or max(seconds, cfg.get("timeout_s", 0)))
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(60)
            raise RuntimeError("the probe ran past its time (%s); its log: %s" % (cmd[0], log))
    if not out.exists():
        raise RuntimeError("the probe wrote no rows (exit %s); its log: %s" % (p.returncode, log))
    data = json.loads(out.read_text(encoding="utf-8-sig"))
    bad = C.check_rows(data, job)
    if bad:
        raise ValueError("the probe's rows break the contract: " + "; ".join(bad[:8]))
    rows = [r for r in data["rows"] if r.get("value") is not None and not r["weapon"].endswith("@warmup")]
    rows += [{"weapon": "_probe", "action": "-", "metric": "note", "value": None, "note": n} for n in data.get("notes", [])]
    return rows


def measure(weapon_ids, actions=None, staging=None, allow_while_busy=False):
    """The Gate's probe rows for the weapons (staging: a folder whose stage.json overrides assets)."""
    guard(allow=allow_while_busy)
    return run_job(job_for(weapon_ids, actions), overrides=staged_overrides(staging) if staging else None)


def run(weapons, actions=None, at=None, tune=None, staging=None, shots=None, parts=None, slomo=None, allow_while_busy=False):
    """One run with everything a fix needs to be tried before it is written: tuned fields, staged assets, screenshots
    and parts dumps at moments. Parts dumps run slowed (0.2) unless slomo says otherwise."""
    guard(allow=allow_while_busy)
    rows = run_job(job_for(weapons, actions, at, tune), staged_overrides(staging) if staging else None, shots, parts,
                   slomo or (0.2 if parts else None))
    return {"rows": rows, "shots": str(shots) if shots else None, "parts": str(parts) if parts else None}


def staged_overrides(folder):
    """A staging folder's stage.json: {"overrides": {asset: staged asset}}. Getting staged files into the game (an
    import into a scratch folder) is the project's own step; it writes the overrides here when done."""
    spec = json.loads((Path(folder) / "stage.json").read_text(encoding="utf-8-sig"))
    if not spec.get("overrides"):
        raise ValueError("%s/stage.json has no overrides: stage the assets into the game first" % folder)
    return spec["overrides"]
