"""Gun Kit: every action file is sound, and a test gun's timelines do what the action says."""
import pytest

from weaponlab.gunkit import actions as A
from weaponlab.gunkit import facts as F
from weaponlab.gunkit import timeline as T


def ar_facts():
    """A made-up AR-15's facts, enough for the timelines (the numbers are round, not measured)."""
    return {"contract": F.CONTRACT, "name": "TestAR", "action": "ar_gas",
            "bones": [{"name": "Root"}] + [{"name": n, "parent": "Root"} for n in
                      ("Carrier", "Handle", "Cover", "Catch", "Release", "Assist", "Trigger", "Magazine")],
            "parts": {"carrier": {"bone": "Carrier", "kind": "slide", "axis": [0, -1, 0], "travel_cm": 8.4},
                      "handle": {"bone": "Handle", "kind": "slide", "axis": [0, -1, 0], "travel_cm": 8.4},
                      "cover": {"bone": "Cover", "kind": "turn", "axis": [0, 1, 0], "turn_deg": 110, "pivot": [-1.3, 0, -1]},
                      "catch": {"bone": "Catch", "kind": "slide", "axis": [0, 0, 1], "travel_cm": 0.6},
                      "release": {"bone": "Release", "kind": "slide", "axis": [1, 0, 0], "travel_cm": 0.3},
                      "assist": {"bone": "Assist", "kind": "slide", "axis": [0, 1, 0], "travel_cm": 0.5},
                      "trigger": {"bone": "Trigger", "kind": "turn", "axis": [1, 0, 0], "turn_deg": 12, "pivot": [0, -6, -4]},
                      "magazine": {"bone": "Magazine", "kind": "free"}},
            "marks": {"grip": [0, -12, -8], "support": [0, 20, -2], "mag_well": [0, -1, -3], "mag_grab": [0, 2, -18],
                      "mag_lips": [0, -1, -2], "handle": [0, -15, 3], "port": [-1.6, 2, 0.5], "catch": [1.4, -4, -3],
                      "release": [-1.4, -1, -3], "assist": [-1.8, -9, 1.5], "muzzle": [0, 40, 0], "trigger": [0, -6, -6]},
            "mark_parts": {"handle": "handle", "mag_grab": "magazine", "mag_lips": "magazine"},
            "magazine": {"bone": "Magazine", "lips": [0, -1, -2]}}


@pytest.mark.parametrize("action_id", A.ids())
def test_action_is_sound(action_id):
    assert A.check(A.load(action_id)) == []


def test_ar_facts_fit_the_action():
    assert F.check(ar_facts(), A.load("ar_gas")) == []


def test_facts_name_what_is_missing():
    f = ar_facts()
    del f["parts"]["handle"]
    del f["marks"]["port"]
    bad = F.check(f, A.load("ar_gas"))
    assert any("handle" in b for b in bad) and any("port" in b for b in bad)


def test_fire_cycles_the_carrier_and_returns():
    a, f = A.load("ar_gas"), ar_facts()
    clip = T.gun_clip(a, f, "fire")
    vals = [fr["parts"]["carrier"] for fr in clip["frames"]]
    assert max(vals) == pytest.approx(1.0, abs=0.05) and vals[-1] == pytest.approx(0.0, abs=1e-6)


def test_fire_last_holds_the_carrier_on_the_catch():
    clip = T.gun_clip(A.load("ar_gas"), ar_facts(), "fire_last")
    end = clip["frames"][-1]["parts"]
    assert end["carrier"] == pytest.approx(0.905) and end["catch"] == pytest.approx(1.0)


def test_reload_carries_the_magazine_and_seats_it():
    a, f = A.load("ar_gas"), ar_facts()
    clip = T.hand_clip(a, f, "reload")
    by_t = {fr["t"]: fr for fr in clip["frames"]}
    assert by_t[0.0]["parts"]["magazine"] == [0.0, 0.0, 0.0]
    assert by_t[0.6]["parts"]["magazine"] == {"follow": "l"}            # in the hand on its way to the pouch
    assert by_t[2.4]["parts"]["magazine"] == [0.0, 0.0, 0.0]            # seated
    assert by_t[0.0]["hands"]["l"]["b"]["name"] == "support"
    mid = by_t[0.6]["hands"]["l"]
    assert mid["b"]["space"] == "view" and mid["b"]["name"] == "pouch_l"


def test_a_hand_rides_the_handle_it_holds():
    a, f = A.load("ar_gas"), ar_facts()
    clip = T.hand_clip(a, f, "charge")
    by_t = {fr["t"]: fr for fr in clip["frames"]}
    rest = by_t[0.4]["hands"]["l"]["b"]["point"][1]
    back = by_t[0.7]["hands"]["l"]["b"]["point"][1]
    assert back == pytest.approx(rest - 8.4, abs=0.05)                  # the handle's full travel, the hand on it
    let_go = by_t[0.9]["hands"]["l"]["a"]["point"][1]
    assert let_go == pytest.approx(rest - 8.4, abs=0.05)                # it let go at the rear; the handle went home


def test_the_check_rolls_the_port_up_and_back():
    clip = T.hand_clip(A.load("ar_gas"), ar_facts(), "check_chamber")
    by_t = {fr["t"]: fr for fr in clip["frames"]}
    assert by_t[1.0]["gun"]["roll"] == pytest.approx(60.0) and by_t[2.0]["gun"]["roll"] == pytest.approx(0.0)
    assert by_t[1.0]["parts"]["handle"] == pytest.approx(0.238)


def test_every_hand_clip_of_every_action_runs_on_a_fitting_gun():
    """Each action's clips run through the timeline on facts made to fit it (each part and mark present)."""
    for aid in A.ids():
        a = A.load(aid)
        f = {"contract": F.CONTRACT, "name": "Fit", "action": aid, "bones": [{"name": "Root"}], "parts": {}, "marks": {},
             "mark_parts": {}, "magazine": {"bone": "Magazine", "lips": [0, 0, -2]}}
        for role, p in a["parts"].items():
            f["bones"].append({"name": role.title(), "parent": "Root"})
            f["parts"][role] = ({"bone": role.title(), "kind": "slide", "axis": [0, -1, 0], "travel_cm": 5.0} if p["kind"] == "slide" else
                                {"bone": role.title(), "kind": "turn", "axis": [1, 0, 0], "turn_deg": 30, "pivot": [0, 0, 0]} if p["kind"] == "turn" else
                                {"bone": role.title(), "kind": "free"})
        for m in a.get("marks", []):
            f["marks"][m] = [0.0, 0.0, 0.0]
        assert F.check(f, a) == [], aid
        for cid in a["gun_clips"]:
            assert T.gun_clip(a, f, cid)["frames"], (aid, cid)
        for cid in a["hand_clips"]:
            assert T.hand_clip(a, f, cid)["frames"], (aid, cid)


@pytest.mark.parametrize("action_id", A.ids())
def test_every_proxy_rigs_into_facts_its_action_takes(action_id):
    """Each action's proxy gun, planned into facts (its parts at their shapes' centres), fits its action, and every clip
    turns into bone tracks."""
    from weaponlab.gunkit import proxy as P
    from weaponlab.gunkit import rigplan as R
    px = P.proxy(action_id)
    centres = {}
    for s in px["shapes"]:
        if s["part"]:
            centres.setdefault(s["part"], s["at"])
    facts = R.plan(px["partsmap"], centres)
    a = A.load(action_id)
    assert F.check(facts, a) == [], action_id
    for cid in a["gun_clips"]:
        tr = R.tracks(facts, T.gun_clip(a, facts, cid))
        assert tr["frames"] and all(b in {x["name"] for x in facts["bones"]} for b in tr["frames"][0]["bones"])
    for cid in a["hand_clips"]:
        assert R.tracks(facts, T.hand_clip(a, facts, cid))["frames"]
