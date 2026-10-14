"""The first real probe (ToangTown, Unreal 5.8) against the contract, and the port against the original tools.
Runs only where that project is (TOANGTOWN_PROJECT, default K:/epic/ToangTown/ToangTown); skipped elsewhere."""
import glob
import json
import os
import sys
from pathlib import Path

import pytest

from weaponlab import contract as C, rig as R

TT = Path(os.environ.get("TOANGTOWN_PROJECT", "K:/epic/ToangTown/ToangTown"))
pytestmark = pytest.mark.skipif(not (TT / "ToangTown.uproject").exists(), reason="the ToangTown project is not here")


def test_every_job_follows_the_contract():
    jobs = sorted(glob.glob(str(TT / "Saved/Gate/probe/job-*.json")))
    assert jobs
    for j in jobs:
        assert C.check_job(json.loads(Path(j).read_text(encoding="utf-8-sig"))) == [], j


def test_rows_since_the_tagged_view_fix_follow_their_jobs():
    # rows written before 2026-10-14 14:40 carry the tagged-view bug this check found; newer ones must be clean
    jobs = [j for j in sorted(glob.glob(str(TT / "Saved/Gate/probe/job-*.json"))) if Path(j).stem[4:] >= "20261014-144000"]
    for j in jobs:
        r = Path(j.replace("job-", "rows-"))
        if r.exists():
            assert C.check_rows(json.loads(r.read_text(encoding="utf-8-sig")), json.loads(Path(j).read_text(encoding="utf-8-sig"))) == [], j


FIXED = __import__("datetime").datetime(2026, 10, 14, 15, 6).timestamp()   # the probe build that labels a built-in gun


def test_dumps_follow_the_contract():
    # dumps from before that build label the M4's gun as arms (found by this check); newer ones must be clean
    dumps = [d for d in sorted(glob.glob(str(TT / "Saved/Gate/riglab/parts/*/*.obj"))) if os.path.getmtime(d) >= FIXED][:200]
    assert dumps
    for d in dumps:
        assert C.check_parts(d) == [], d


def test_the_fist_measure_matches_the_original():
    sys.path.insert(0, str(TT / "Tools" / "servers"))
    from ttools import fist as F
    for w in ("LaserSword", "VibroKnife", "Knife"):
        obj = TT / "Saved/Gate/riglab/parts/fist0" / ("%s_idle_1.20.obj" % w)
        if not obj.exists():
            continue
        a, b = F.measure(str(obj)), R.fist(obj)
        assert (a["offset_cm"], a["angle_deg"]) == (b["offset_cm"], b["angle_deg"]), w
        fx = F.fix(str(obj))
        t0 = F.measure(str(obj))["hold"]["offset"]
        assert [round(x - y, 2) for x, y in zip(fx["ArmsGunOffset"], t0)] == pytest.approx(b["move_cm"], abs=0.02), w
        assert fx["ArmsGunRot"] == pytest.approx(b["rotator"], abs=0.01), w
