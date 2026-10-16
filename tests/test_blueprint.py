"""Blueprint Lab without Blender: a made-up manual (a data table page and a drawn page with a scale bar) goes through
sources, specs, figures, trace, plan and check, and the parts map the build would write follows its contract."""
import math

import pytest

pymupdf = pytest.importorskip("pymupdf")
pytest.importorskip("cv2")

from weaponlab import contracts as C  # noqa: E402
from weaponlab.blueprint import build as B  # noqa: E402
from weaponlab.blueprint import check as K  # noqa: E402
from weaponlab.blueprint import figures as F  # noqa: E402
from weaponlab.blueprint import plan as P  # noqa: E402
from weaponlab.blueprint import sources as S  # noqa: E402
from weaponlab.blueprint import specs as X  # noqa: E402
from weaponlab.blueprint import trace as T  # noqa: E402
from weaponlab.gunkit import actions as A  # noqa: E402

G = "TestPistol"
# the drawn gun, in page points (72 a inch): a slide 0.5 in tall over a grip, 8 in long, muzzle to the left
SLIDE = [(72, 144), (648, 144), (648, 180), (72, 180)]
FRAME = [(72, 180), (648, 180), (648, 200), (560, 200), (600, 330), (520, 330), (470, 200), (72, 200)]


def manual(path):
    doc = pymupdf.open()
    p = doc.new_page(width=720, height=540)
    p.insert_text((72, 100), "GENERAL DATA", fontsize=14)
    p.insert_text((72, 130), "Overall length of pistol, inches ........ 8.000", fontsize=11)
    p.insert_text((72, 150), "Weight of pistol with magazine, pounds .. 2.000", fontsize=11)
    for k in range(20):
        p.insert_text((72, 170 + 14 * k), "Table row %d ........ %d.%d %d %d" % (k, k, k, k * 3, k * 7), fontsize=10)
    q = doc.new_page(width=720, height=540)
    outline = SLIDE[:2] + [(648, 200), (560, 200), (600, 330), (520, 330), (470, 200), (72, 200)]
    q.draw_polyline(outline + [outline[0]], color=(0, 0, 0), fill=(0, 0, 0), width=1)
    # a scale bar: 0 to 5 inches, a tick each inch, under the gun
    q.draw_line((100, 450), (460, 450), color=(0, 0, 0), width=2)
    for k in range(6):
        q.draw_line((100 + 72 * k, 436), (100 + 72 * k, 450), color=(0, 0, 0), width=2)
    q.insert_text((300, 500), "FIGURE 1. Test pistol, left side.", fontsize=10)
    doc.save(str(path))


@pytest.fixture()
def gun(tmp_path, monkeypatch):
    monkeypatch.setenv("WEAPONLAB_DIGITIZE", str(tmp_path / "digitize"))
    pdf = tmp_path / "manual.pdf"
    manual(pdf)
    S.add(G, str(pdf), "tm-test", "manual", "TM Test Pistol", "us-government-work", year=1940)
    return pdf


def test_sources_scan_and_specs(gun):
    r = S.scan(G, "tm-test")
    assert r["pages"] == 2
    assert 2 in [f["page"] for f in r["figures"]]
    c = X.find(G)
    assert any(8.0 in [n["value"] for n in x["numbers"]] for x in c["overall_length"])
    f = X.add(G, "overall_length", 8.0, "in", "tm-test", 1, "Overall length of pistol, inches 8.000")
    assert f["value"] == pytest.approx(20.32) and f["unit"] == "cm"
    assert C.check_file(str(gun.parent / "digitize" / G / "sources.json")) == []


def figure(gun):
    X.add(G, "overall_length", 8.0, "in", "tm-test", 1, "Overall length of pistol, inches 8.000")
    X.add(G, "weight", 2.0, "lb", "tm-test", 1, "Weight of pistol with magazine, pounds 2.000")
    F.add(G, "side", "tm-test", 2, "side", shows="left", dpi=144)       # 2 px a point
    return F.figure(G, "side")


def test_ticks_give_the_drawn_scale(gun):
    figure(gun)
    t = T.ticks(G, "side", [180, 868, 940, 896], min_share=0.6)
    assert len(t["ticks_px"]) == 6
    assert all(abs(g - 144) <= 2 for g in t["gaps_px"])                     # an inch is 144 px at 2 px a point
    c = F.calibrate(G, "side", [t["ticks_px"][0], 890], [t["ticks_px"][-1], 890], cm=12.7)
    assert c["cm_per_px"] == pytest.approx(2.54 / 144, rel=0.01)


def test_silhouette_scale_frame_and_round_trip(gun):
    figure(gun)
    s = T.silhouette(G, "side", region=[100, 250, 1340, 700], close_px=3, eps_px=1.0)
    c = F.calibrate_extent(G, "side", s["outline_px"], "overall_length")
    assert c["cm_per_px"] == pytest.approx(2.54 / 144, rel=0.01)           # the outline is the 8 in drawn
    xs = [p[0] for p in s["outline_px"]]
    F.frame(G, "side", [max(xs), 324], [min(xs), 324], [min(xs) + 400, 324])
    f = F.figure(G, "side")
    pts = [[300.0, 300.0], [900.0, 500.0]]
    back = F.to_px(f, F.to_gun(f, pts))
    assert all(math.dist(a, b) < 0.01 for a, b in zip(pts, back))          # cm keep 4 decimals
    y, z = F.to_gun(f, [[min(xs), 324.0]])[0]
    assert y > 0 and abs(z) < 1e-6                                          # the muzzle (left) is +y, on the bore
    s = T.silhouette(G, "side", region=[100, 250, 1340, 700], close_px=3, eps_px=1.0)
    T.save(G, "outline", s)
    assert s["bounds_cm"]["y"][1] - s["bounds_cm"]["y"][0] == pytest.approx(20.32, rel=0.01)


def test_plan_check_and_parts_map(gun):
    test_silhouette_scale_frame_and_round_trip(gun)
    a = A.load("pistol_slide")
    P.new(G, "pistol_slide")
    out = P.trace(G, "outline")["outline_cm"]
    z_top = max(p[1] for p in out)
    split = z_top - 36 * 2.54 / 72                                          # the slide is 36 points tall
    guess = {"guess": "the test pistol is 2.4 cm wide"}
    P.extrude(G, "slide", "slide", "blued", "outline", [-1.2, 1.2], guess, clips=[("z", split, "above", "the slide's edge")],
              motion={"kind": "slide", "axis": [0, -1, 0], "travel_cm": 4.0},
              motion_sources={"axis": {"derived": "along the bore, back"}, "travel_cm": {"guess": "a service pistol's slide opens about 4 cm"}})
    P.extrude(G, "frame", "body", "blued", "outline", [-1.2, 1.2], guess, clips=[("z", split, "below", "under the slide")])
    P.extrude(G, "magazine", "magazine", "blued", "outline", [-0.7, 0.7], {"guess": "a single stack magazine, 1.4 cm"},
              clips=[("z", split - 1.0, "below", "in the grip"), ("y", -10.0, "below", "in the grip")], motion={"kind": "free"})
    for m in a["marks"]:
        P.mark(G, m, [0.0, 0.0, 0.0], {"derived": "a test mark at the origin"}, rides="magazine" if m.startswith("mag_") else None)
    r = K.run(G, reference="outline")
    assert r["contract"] == []
    assert r["outline"]["iou"] > 0.98 and r["outline"]["ok"]
    assert r["length"]["ok"]
    assert r["overlays"]
    bp = P.store.load(G, "blueprint")
    pm = B.partsmap(bp, "model.blend")
    assert C.check_partsmap(pm) == []
    assert pm["parts"]["slide"]["kind"] == "slide" and pm["parts"]["magazine"]["objects"] == ["magazine"]


def test_a_number_without_its_source_fails_the_check(gun):
    test_plan_check_and_parts_map(gun)
    bp = P.store.load(G, "blueprint")
    del bp["parts"]["slide"]["sources"]["travel_cm"]
    assert "part slide: no source for its travel_cm" in C.check_blueprint(bp)


def test_polygon_helpers():
    sq = [[0, 0], [4, 0], [4, 4], [0, 4]]
    assert P.area(P.clip(sq, "z", 1.0, "above")) == pytest.approx(12.0)
    assert P.area(P.clip_line(sq, [0, 0], [4, 4], "left")) == pytest.approx(8.0)
    prof = P.lathe_profile([[0, -1], [10, -1], [10, 1], [0, 1]], 0.0, step_cm=1.0)
    assert all(r == pytest.approx(1.0) for _, r in prof)
    tilted = [[0, -5], [1, -5], [3, 0], [2, 0]]
    line, miss = P.edge_line([[0, -6], [10, -6], [10, 1], [2.4, 1], [0, -5]], -4.5, 0.5, front=False)
    assert miss < 0.05
    fit, turned = P.fit_along(tilted, [[0, -5], [2, 0]], 0.3, -6.0)
    assert min(p[1] for p in fit) == pytest.approx(-6.0)
