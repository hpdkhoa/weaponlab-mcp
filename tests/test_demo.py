"""The whole loop on the demo game: measure, find the bugs, try the fixes by tune, judge them."""
from conftest import trust


def test_measure_find_try_and_judge(demo):
    from weaponlab import contract as C, gate as G, probe as P, rig as R
    trust("probe", "rig")
    run = G.run_providers(["probe", "rig"])
    assert not run["errors"], run["errors"]
    G.set_baseline(run["run"])
    v = G.verdict(run["run"], ["Demo_Rifle-support", "Demo_Knife-fist"])
    got = {c["case"]: c for c in v["cases"]}
    assert not v["pass"]
    assert got["Demo_Rifle-support"]["value"] == 3.75 and got["Demo_Knife-fist"]["value"] > 85
    assert got["Demo_Rifle-facts"]["value"] == 0      # the magazine behind and under the barrel

    # the knife's fix from Rig Lab, the rifle's from the bug's own field; both tried without writing them
    dump = sorted((G.project().work / "rig" / "dumps").glob("*"))[-1] / C.parts_name("Demo_Knife", "idle", 1.2)
    assert C.check_parts(dump) == []
    m = R.fist(dump)
    tune = {"Demo_Rifle": {"offset": [0, 0, 0]}, "Demo_Knife": {"rot": m["rot"], "offset": m["move_cm"]}}
    out = P.run(["Demo_Rifle", "Demo_Knife"], ["idle"], at={"idle": [1.2]}, tune=tune, parts=G.project().ensure("try"))
    gap = next(r["value"] for r in out["rows"] if r["weapon"] == "Demo_Rifle" and r["metric"] == "hands.l_gap_cm")
    assert gap == 0.25
    after = R.fist(G.project().work / "try" / C.parts_name("Demo_Knife", "idle", 1.2))
    assert after["offset_cm"] < 0.1 and after["angle_deg"] < 1.0
    assert any("tuned" in r.get("note", "") for r in out["rows"] if r["metric"] == "note")


def test_the_warmup_rows_are_dropped_and_the_job_follows_the_contract(demo):
    import json
    from weaponlab import contract as C, gate as G, probe as P
    rows = P.measure(["Demo_Rifle"])
    assert rows and not any("@warmup" in r["weapon"] for r in rows)
    job = json.loads(sorted((G.project().work / "probe").glob("job-*.json"))[-1].read_text())
    assert C.check_job(job) == [] and job["weapons"][0]["tag"] == "warmup"


def test_a_missing_probe_says_how_to_set_one(demo):
    import json
    import pytest
    from weaponlab import config, probe as P
    cfg = json.loads((demo / "weaponlab.json").read_text())
    cfg["probe"]["command"] = []
    (demo / "weaponlab.json").write_text(json.dumps(cfg))
    config.reset()
    with pytest.raises(RuntimeError, match="probe.command"):
        P.measure(["Demo_Rifle"])
