"""The Gate's rules on the demo project, with rows saved by hand (no probe run)."""
import pytest

from conftest import trust


def row(w, a, m, v):
    return {"weapon": w, "action": a, "metric": m, "value": v}


@pytest.fixture
def G(demo):
    from weaponlab import gate
    trust("probe")
    base = [row("Demo_Rifle", "idle", "hands.l_gap_cm", 3.75), row("Demo_Rifle", "idle", "view.cover_lower_left", 0.16),
            row("Demo_Knife", "idle", "hands.l_drift_cm", 0.4)]
    gate.set_baseline(gate.save_run(base)["run"])
    return gate


def test_a_fix_that_breaks_nothing_passes(G):
    run = G.save_run([row("Demo_Rifle", "idle", "hands.l_gap_cm", 0.25), row("Demo_Rifle", "idle", "view.cover_lower_left", 0.16),
                      row("Demo_Knife", "idle", "hands.l_drift_cm", 0.4)])["run"]
    v = G.verdict(run, ["Demo_Rifle-support"])
    assert v["pass"] and len(v["improved"]) == 1 and not v["regressions"]


def test_a_regression_elsewhere_blocks_it(G):
    run = G.save_run([row("Demo_Rifle", "idle", "hands.l_gap_cm", 0.25), row("Demo_Knife", "idle", "hands.l_drift_cm", 2.0)])["run"]
    v = G.verdict(run, ["Demo_Rifle-support"])
    assert not v["pass"] and v["regressions"][0]["row"] == "Demo_Knife|idle|hands.l_drift_cm"


def test_a_change_inside_the_tolerance_is_not_a_regression(G):
    run = G.save_run([row("Demo_Rifle", "idle", "hands.l_gap_cm", 0.25), row("Demo_Rifle", "idle", "view.cover_lower_left", 0.16)])["run"]
    G.set_baseline(run)
    run2 = G.save_run([row("Demo_Rifle", "idle", "hands.l_gap_cm", 0.7), row("Demo_Rifle", "idle", "view.cover_lower_left", 0.16)])["run"]
    v = G.verdict(run2, ["Demo_Rifle-support"])
    assert v["pass"] and not v["regressions"]          # 0.45 worse, tolerance 0.5 (metrics.json)


def test_an_untrusted_check_cannot_pass_a_target(demo):
    from weaponlab import gate
    run = gate.save_run([row("Demo_Rifle", "idle", "hands.l_gap_cm", 0.25)])["run"]
    v = gate.verdict(run, ["Demo_Rifle-support"])
    assert not v["pass"] and v["untrusted_providers"] == ["probe"]


def test_a_target_not_measured_fails(G):
    run = G.save_run([row("Demo_Rifle", "idle", "hands.l_gap_cm", 0.25)])["run"]
    v = G.verdict(run, ["Demo_Rifle-support", "Demo_Knife-fist"])
    assert not v["pass"] and v["targets_not_measured"] == ["Demo_Knife-fist"]


def test_a_named_budget_is_a_rule(G):
    run = G.save_run([row("Demo_Rifle", "idle", "view.cover_lower_left", 0.3)])["run"]
    c = next(c for c in G.verdict(run)["cases"] if c["case"] == "Demo_Rifle-view")
    assert c["pass"] is False                           # budget view_lower_left 0.2


def test_approval_refuses_a_failed_verdict(G):
    import json
    pid = "p1"
    d = G._proposals() / pid
    d.mkdir(parents=True)
    (d / "proposal.json").write_text(json.dumps({"name": "x"}))
    (d / "verdict.json").write_text(json.dumps({"pass": False}))
    with pytest.raises(ValueError):
        G.approve(pid, "someone")


def test_rows_that_break_the_contract_are_refused(G):
    with pytest.raises(ValueError):
        G.save_run([{"weapon": "A", "action": "idle", "metric": "nodot", "value": 1}])
