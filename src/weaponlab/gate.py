"""The Gate: the cases, the metric table, the baseline, the evals of the checks and the verdict.

A change passes only if its target cases pass and no other row, on any weapon, gets worse past its tolerance. A check
counts only while its eval passes: it caught every known fault and passed every known good case.

In the project's data folder (in git): weapons.json (the arsenal: [{id, name, kind, ...}]), metrics.json (each
metric: provider, unit, which way is better, the tolerance), cases.json (each bug as a check with a pass rule; a fixed
case stays for good), budgets.json (named limits a rule can use, measured from the weapons that look right).
In the work folder: runs/<id>.json, baseline.json, evals.json, proposals/<id>/ (proposal.json, verdict.json, report.md).
"""
import datetime as _dt
import json
import re
import subprocess
from pathlib import Path

from . import contract as C
from .config import project


def _now():
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _load(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else default


def _save(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(p)


def _runs():
    return project().ensure("runs")


def _proposals():
    return project().ensure("proposals")


# ------------------------------------------------------------------ the project's tables
def weapons():
    return _load(project().data / "weapons.json", [])


RIG_METRICS = {
    "facts.false": ("count", "lower", 0.0, "the spec's facts the dump breaks (a magazine behind its well, a stock forward)"),
    "parts.duplicates": ("count", "none", 0.0, "a piece the gun has once, drawn more often"),
    "fist.offset_cm": ("cm", "lower", 0.5, "a melee hilt's grip centre off the fist's grip channel"),
    "fist.angle_deg": ("deg", "lower", 5.0, "a melee hilt's angle to the fist's grip channel"),
}


def metrics():
    """The project's metrics over the built-in ones: the contract's standard metrics (provider probe) and Rig Lab's
    (provider rig), tolerance 0 unless the project says otherwise."""
    std = {k: {"provider": "probe", "unit": u, "better": b, "tolerance": 0.0, "about": a} for k, (u, b, a) in C.STANDARD_METRICS.items()}
    std.update({k: {"provider": "rig", "unit": u, "better": b, "tolerance": t, "about": a} for k, (u, b, t, a) in RIG_METRICS.items()})
    from .gunkit.gaterows import METRICS as GK
    std.update({k: {"provider": "gunkit", "unit": u, "better": b, "tolerance": t, "about": a} for k, (u, b, t, rule, a) in GK.items()})
    std.update(_load(project().data / "metrics.json", {}))
    return std


def _metric(name):
    m = metrics()
    if name in m:
        return m[name]
    for pat, (u, b, a) in C.STANDARD_FAMILIES.items():
        if re.fullmatch(re.escape(pat).replace(r"\*", r"[A-Za-z0-9_]+"), name):
            return {"provider": "probe", "unit": u, "better": b, "tolerance": 0.0, "about": a}
    return {}


def cases():
    return _load(project().data / "cases.json", [])


def save_cases(cs):
    return _save(project().data / "cases.json", cs)


def add_case(case):
    for key in ("id", "weapon", "action", "metric", "rule", "source"):
        if key not in case:
            raise ValueError("a case needs %s" % key)
    if not _metric(case["metric"]):
        raise ValueError("unknown metric %s (add it to metrics.json)" % case["metric"])
    if case["rule"].get("op") not in OPS:
        raise ValueError("rule op must be one of %s" % sorted(OPS))
    cs = [c for c in cases() if c["id"] != case["id"]]
    case.setdefault("status", "open")
    cs.append(case)
    save_cases(sorted(cs, key=lambda c: c["id"]))
    return case


# ------------------------------------------------------------------ rules
OPS = {"<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b, "==": lambda a, b: a == b, "<": lambda a, b: a < b, ">": lambda a, b: a > b}


def rule_value(rule):
    v = rule["value"]
    if isinstance(v, str):          # a named budget (budgets.json)
        budgets = _load(project().data / "budgets.json", {})
        if v not in budgets:
            return None
        v = budgets[v]
    return v


def holds(rule, value):
    v = rule_value(rule)
    if v is None or value is None:
        return None
    return bool(OPS[rule["op"]](value, v))


# ------------------------------------------------------------------ runs and the baseline
def key(row):
    return "%s|%s|%s" % (row["weapon"], row["action"], row["metric"])


def _builtin(name):
    """The providers inside Weapon Lab: probe (the game's probe), rig (parts dumps against the specs) and gunkit (a Gun
    Kit build's own checks: its facts, its clips read back, its hand clips' Pose Lab checks)."""
    if name == "probe":
        from . import probe
        return lambda ws, acts, staging: probe.measure(ws, acts, staging)
    if name == "rig":
        from . import rig
        return lambda ws, acts, staging: rig.measure(ws, acts, staging)
    if name == "gunkit":
        from .gunkit import gaterows
        return lambda ws, acts, staging: [r for w in (ws or list(gaterows.registry())) for r in gaterows.rows(w)
                                          if not acts or r["action"] in acts]
    return None


def run_providers(providers, weapon_ids=None, actions=None, staging=None, timeout=7200):
    """Runs the providers' checks over the weapons (all when none named); stores and returns the run. A provider is
    built in (probe, rig) or a command in weaponlab.json "providers" that prints rows as JSON, given
    --weapons a,b [--actions x,y] [--staging folder]."""
    weapon_ids = weapon_ids or [w["id"] for w in weapons()]
    rows, errors = [], []
    for name in providers:
        try:
            fn = None if name in project().providers else _builtin(name)
            if fn:
                got = fn(weapon_ids, actions, staging)
            else:
                cmd = list(project().providers.get(name) or [])
                if not cmd:
                    raise ValueError("no provider %s (built in: probe, rig; others go in weaponlab.json providers)" % name)
                cmd += ["--weapons", ",".join(weapon_ids)]
                if actions:
                    cmd += ["--actions", ",".join(actions)]
                if staging:
                    cmd += ["--staging", str(staging)]
                p = subprocess.run(cmd, cwd=str(project().root), capture_output=True, text=True, timeout=timeout)
                if p.returncode != 0:
                    raise RuntimeError((p.stderr or p.stdout)[-2000:])
                got = json.loads(p.stdout)
            bad = C.check_rows(got)
            if bad:
                raise ValueError("rows break the contract: " + "; ".join(bad[:5]))
            got = got["rows"] if isinstance(got, dict) else got
        except Exception as e:  # one provider's failure is recorded; the verdict fails on it
            errors.append({"provider": name, "error": str(e)[-2000:]})
            continue
        for r in got:
            r["provider"] = name
        rows += [r for r in got if r.get("metric") != "note"]
    run_id = _now()
    _save(_runs() / (run_id + ".json"), {"id": run_id, "providers": providers, "weapons": weapon_ids, "actions": actions,
                                         "staging": str(staging) if staging else None, "rows": rows, "errors": errors})
    return {"run": run_id, "rows": len(rows), "errors": errors}


def save_run(rows, providers=("manual",), note=None):
    """Stores rows measured elsewhere as a run (they must follow the contract)."""
    bad = C.check_rows(rows)
    if bad:
        raise ValueError("rows break the contract: " + "; ".join(bad[:5]))
    rows = rows["rows"] if isinstance(rows, dict) else rows
    run_id = _now()
    _save(_runs() / (run_id + ".json"), {"id": run_id, "providers": list(providers), "weapons": sorted({r["weapon"] for r in rows}),
                                         "actions": None, "staging": None, "rows": rows, "errors": [], "note": note})
    return {"run": run_id, "rows": len(rows)}


def load_run(run_id):
    return _load(_runs() / (run_id + ".json"), None)


def set_baseline(run_id):
    """The rows of a run become the baseline (merged over the old one: a row not measured again keeps its value)."""
    run = load_run(run_id)
    if run is None:
        raise ValueError("no run %s" % run_id)
    base = baseline()
    for r in run["rows"]:
        base["rows"][key(r)] = r
    base["runs"].append(run_id)
    _save(project().work / "baseline.json", base)
    return {"baseline_rows": len(base["rows"]), "from_runs": base["runs"]}


def baseline():
    return _load(project().work / "baseline.json", {"rows": {}, "runs": []})


# ------------------------------------------------------------------ evals of the checks
def evals():
    return _load(project().work / "evals.json", {})


def record_eval(provider, result):
    """result: {suite, caught, faults, passed_good, good, details}; the provider's checks are trusted only when it caught
    every fault and passed every good case."""
    ev = evals()
    result["trusted"] = result["caught"] == result["faults"] and result["passed_good"] == result["good"]
    result["when"] = _now()
    ev[provider] = result
    _save(project().work / "evals.json", ev)
    return result


def trusted(provider):
    e = evals().get(provider)
    return bool(e and e.get("trusted"))


# ------------------------------------------------------------------ the verdict
def verdict(run_id, targets=None, proposal=None):
    """Target cases must pass; no other row may get worse past its tolerance; every row a target case needs must come
    from a trusted check."""
    run = load_run(run_id)
    if run is None:
        raise ValueError("no run %s" % run_id)
    base = baseline()["rows"]
    now = {key(r): r for r in run["rows"]}
    target_ids = set(targets or [])
    case_results, regressions, improved, untrusted = [], [], [], set()
    for c in cases():
        k = "%s|%s|%s" % (c["weapon"], c["action"], c["metric"])
        if k not in now or c.get("status") == "excluded":
            continue
        v = now[k]["value"]
        ok = holds(c["rule"], v)
        prov = _metric(c["metric"]).get("provider")
        if not trusted(prov):
            untrusted.add(prov)
        case_results.append({"case": c["id"], "target": c["id"] in target_ids, "value": v, "rule": c["rule"], "pass": ok,
                             "was": base.get(k, {}).get("value"), "trusted": trusted(prov)})
    for k, r in now.items():
        b = base.get(k)
        md = _metric(r["metric"])
        if b is None or not isinstance(r["value"], (int, float)) or not isinstance(b["value"], (int, float)):
            continue
        tol, better = md.get("tolerance", 0.0), md.get("better", "lower")
        if better == "none":            # a count only its cases judge
            continue
        delta = r["value"] - b["value"]
        worse = delta > tol if better == "lower" else -delta > tol
        better_now = -delta > tol if better == "lower" else delta > tol
        item = {"row": k, "was": b["value"], "now": r["value"], "unit": md.get("unit")}
        if worse:
            regressions.append(item)
        elif better_now:
            improved.append(item)
    targets_ok = all(cr["pass"] and cr["trusted"] for cr in case_results if cr["target"]) if target_ids else None
    missing = sorted(target_ids - {cr["case"] for cr in case_results})
    passed = bool(target_ids) and bool(targets_ok) and not regressions and not missing and not run["errors"]
    v = {"run": run_id, "pass": passed, "targets_pass": targets_ok, "targets_not_measured": missing,
         "regressions": regressions, "improved": improved, "cases": case_results,
         "untrusted_providers": sorted(p for p in untrusted if p), "provider_errors": run["errors"]}
    if proposal:
        d = _proposals() / proposal
        _save(d / "verdict.json", v)
        (d / "report.md").write_text(report_md(v), encoding="utf-8")
        v["report"] = str(d / "report.md")
    return v


def report_md(v):
    lines = ["# Gate verdict: %s" % ("PASS" if v["pass"] else "FAIL"), "", "Run %s." % v["run"], ""]
    if v["targets_not_measured"]:
        lines += ["Target cases not measured: " + ", ".join(v["targets_not_measured"]) + ".", ""]
    lines += ["## Cases", "", "| Case | Target | Was | Now | Rule | Pass | Trusted |", "|---|---|---|---|---|---|---|"]
    for c in v["cases"]:
        lines.append("| %s | %s | %s | %s | %s %s | %s | %s |" % (c["case"], "yes" if c["target"] else "", c["was"], c["value"], c["rule"]["op"], c["rule"]["value"],
                                                          {True: "yes", False: "NO", None: "?"}[c["pass"]], "yes" if c["trusted"] else "NO"))
    lines += ["", "## Worse than the baseline (%d)" % len(v["regressions"]), ""]
    lines += ["- %s: %s to %s %s" % (r["row"], r["was"], r["now"], r["unit"] or "") for r in v["regressions"]] or ["- none"]
    lines += ["", "## Better than the baseline (%d)" % len(v["improved"]), ""]
    lines += ["- %s: %s to %s %s" % (r["row"], r["was"], r["now"], r["unit"] or "") for r in v["improved"]] or ["- none"]
    if v["untrusted_providers"]:
        lines += ["", "Checks not trusted yet (their eval has not passed): " + ", ".join(v["untrusted_providers"]) + "."]
    if v["provider_errors"]:
        lines += ["", "Provider errors: " + "; ".join("%s: %s" % (e["provider"], e["error"][:200]) for e in v["provider_errors"])]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ proposals and approval
def propose(name, staging, targets, providers, weapon_ids=None, actions=None):
    """A change staged in staging: run the providers over every weapon it touches, then the verdict."""
    run = run_providers(providers, weapon_ids, actions, staging)
    pid = "%s-%s" % (_now(), re.sub(r"[^A-Za-z0-9_-]", "_", name))
    _save(_proposals() / pid / "proposal.json", {"name": name, "staging": str(staging) if staging else None, "targets": targets,
                                                 "providers": providers, "weapons": weapon_ids, "actions": actions, "run": run["run"], "approved": False})
    v = verdict(run["run"], targets, pid)
    return {"proposal": pid, "verdict": v}


def approve(pid, approved_by):
    """Marks a passed proposal approved: a person's word. Nothing is imported here; the project's own tooling does
    that after."""
    p = _load(_proposals() / pid / "proposal.json", None)
    v = _load(_proposals() / pid / "verdict.json", None)
    if not p or not v:
        raise ValueError("no proposal %s" % pid)
    if not v["pass"]:
        raise ValueError("proposal %s did not pass the gate: it cannot be approved" % pid)
    p["approved"] = True
    p["approved_by"] = approved_by
    p["approved_at"] = _now()
    _save(_proposals() / pid / "proposal.json", p)
    return p


def proposals():
    out = []
    d0 = project().work / "proposals"
    for d in sorted(d0.glob("*")) if d0.exists() else []:
        p = _load(d / "proposal.json", {})
        v = _load(d / "verdict.json", {})
        out.append({"proposal": d.name, "name": p.get("name"), "pass": v.get("pass"), "approved": p.get("approved")})
    return out
