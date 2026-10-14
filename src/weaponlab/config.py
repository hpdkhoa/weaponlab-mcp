"""A Weapon Lab project: one folder with a weaponlab.json. WEAPONLAB_PROJECT names it; otherwise the current folder.

weaponlab.json (every key optional):
  {"data": "weaponlab/data",      weapons.json, metrics.json, cases.json, budgets.json, actions.json (in git)
   "specs": "weaponlab/specs",    one <weapon>.json a weapon (in git)
   "work": "weaponlab/work",      runs, baseline, evals, proposals, dumps, shots (not in git)
   "probe": {"command": ["MyGame.exe", "-probe={job}", "-log={work}/probe/game-{stamp}.log"],
             "timeout_s": 1800,
             "busy": ["UnrealEditor.exe"],     wait while one runs (another job), up to wait_s
             "refuse": ["MyGame.exe"],         fail at once while one runs (the player's own game)
             "wait_s": 0, "warmup": true, "low_priority": false,
             "job_extra": {"quit": true}},    keys added to every job, for the probe's own use
   "providers": {"poselab": ["python", "-m", "my_poselab_rows"]},   row sources the Gate may run (a name here
                                                                     replaces the built-in probe or rig)
   "blender": "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"}

Relative paths are from the project folder. Nothing else in Weapon Lab knows where a project lives."""
import glob
import json
import os
import shutil
import sys
from pathlib import Path

DEFAULTS = {"data": "weaponlab/data", "specs": "weaponlab/specs", "work": "weaponlab/work",
            "probe": {"command": [], "timeout_s": 1800, "busy": [], "refuse": [], "wait_s": 0, "warmup": True,
                      "low_priority": False, "job_extra": {}},
            "providers": {}, "blender": None}


class Project:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("WEAPONLAB_PROJECT") or os.getcwd()).resolve()
        cfg = self.root / "weaponlab.json"
        raw = json.loads(cfg.read_text(encoding="utf-8-sig")) if cfg.exists() else {}
        self.config = {**DEFAULTS, **raw, "probe": {**DEFAULTS["probe"], **raw.get("probe", {})}}
        self.has_config = cfg.exists()

    def _dir(self, key):
        p = Path(self.config[key])
        return p if p.is_absolute() else self.root / p

    @property
    def data(self):
        return self._dir("data")

    @property
    def specs(self):
        return self._dir("specs")

    @property
    def work(self):
        return self._dir("work")

    def ensure(self, *parts):
        p = self.work.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def probe(self):
        return self.config["probe"]

    @property
    def providers(self):
        return self.config.get("providers") or {}

    def blender(self):
        """Blender: WEAPONLAB_BLENDER, the project's setting, the PATH, then the usual install folders."""
        for cand in (os.environ.get("WEAPONLAB_BLENDER"), self.config.get("blender"), shutil.which("blender")):
            if cand and Path(cand).exists():
                return Path(cand)
        pats = []
        if sys.platform == "win32":
            for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"D:\Blender", r"C:\Blender"):
                pats += [os.path.join(base, "Blender Foundation", "Blender*", "blender.exe"), os.path.join(base, "blender.exe")]
        elif sys.platform == "darwin":
            pats += ["/Applications/Blender.app/Contents/MacOS/Blender"]
        else:
            pats += ["/usr/bin/blender", "/snap/bin/blender", os.path.expanduser("~/blender*/blender")]
        for pat in pats:
            hits = sorted(glob.glob(pat), reverse=True)
            if hits:
                return Path(hits[0])
        raise FileNotFoundError("Blender not found: set WEAPONLAB_BLENDER or \"blender\" in weaponlab.json")


_current = None


def project():
    """The project in use (read once; reset() after changing WEAPONLAB_PROJECT)."""
    global _current
    if _current is None:
        _current = Project()
    return _current


def reset(root=None):
    global _current
    _current = Project(root) if root else None
    return _current
