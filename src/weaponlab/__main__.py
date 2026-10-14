"""weaponlab <command>
  serve                                   the MCP server (also: weaponlab-mcp)
  contract job|rows|parts <file> [job]    check a probe's file against the contract
  init [folder]                           a new project: weaponlab.json and empty data
  gate run <providers> [weapons]          measure and store a run
  gate verdict <run> [targets]            the verdict on a run
  gate baseline <run>                     a run becomes the baseline
  rig fist <dump.obj>                     a melee hilt against the fist
  motion profile <clip.fbx> [side]        a clip's forearm roll"""
import json
import sys
from pathlib import Path


def _csv(s):
    return [x for x in (s or "").split(",") if x]


def init(folder="."):
    root = Path(folder).resolve()
    data = root / "weaponlab" / "data"
    (root / "weaponlab" / "specs").mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    cfg = root / "weaponlab.json"
    if not cfg.exists():
        cfg.write_text(json.dumps({"probe": {"command": [], "timeout_s": 1800, "busy": []}}, indent=1) + "\n", encoding="utf-8")
    for name, empty in (("weapons.json", []), ("cases.json", []), ("metrics.json", {}), ("budgets.json", {}),
                        ("actions.json", {"*": {"idle": {"seconds": 1.6}}})):
        if not (data / name).exists():
            (data / name).write_text(json.dumps(empty, indent=1) + "\n", encoding="utf-8")
    gi = root / ".gitignore"
    line = "weaponlab/work/"
    if not gi.exists() or line not in gi.read_text(encoding="utf-8"):
        with open(gi, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return {"project": str(root), "next": "set probe.command in weaponlab.json (docs/PROBE_CONTRACT.md), list weapons in weaponlab/data/weapons.json"}


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = a[0]
    if cmd == "serve":
        from .server import main as serve
        serve()
        return 0
    if cmd == "contract":
        from . import contract as C
        bad = C.check_file(a[1], a[2], a[3] if len(a) > 3 else None)
        print(json.dumps({"ok": not bad, "problems": bad}, indent=1))
        return 0 if not bad else 1
    if cmd == "init":
        out = init(a[1] if len(a) > 1 else ".")
    elif cmd == "gate":
        from . import gate as G
        if a[1] == "run":
            out = G.run_providers(_csv(a[2]), _csv(a[3]) if len(a) > 3 else None)
        elif a[1] == "verdict":
            out = G.verdict(a[2], _csv(a[3]) if len(a) > 3 else None)
        elif a[1] == "baseline":
            out = G.set_baseline(a[2])
        else:
            raise SystemExit(__doc__)
    elif cmd == "rig" and a[1] == "fist":
        from . import rig as R
        out = R.fist(a[2])
    elif cmd == "motion" and a[1] == "profile":
        from . import motion as M
        out = M.profile(a[2], *(a[3:4] or ["r"]))
    else:
        raise SystemExit(__doc__)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
