"""Blueprint Lab's detail helpers and the loft part: corners rounded tangent to their edges, sections in their box,
a loft that the contract accepts."""
import math

from weaponlab.blueprint import detail as D
from weaponlab import contracts as C


def test_round_outline_keeps_the_box_and_rounds_its_corners():
    box = [[0, 0], [10, 0], [10, 4], [0, 4]]
    out = D.round_outline(box, 1.0)
    assert len(out) == 4 * 7
    xs, zs = [p[0] for p in out], [p[1] for p in out]
    assert min(xs) >= -1e-6 and max(xs) <= 10 + 1e-6 and min(zs) >= -1e-6 and max(zs) <= 4 + 1e-6
    assert not any(abs(p[0]) < 1e-6 and abs(p[1]) < 1e-6 for p in out)          # the knife corner is gone


def test_round_outline_drops_a_spike():
    spiky = [[0, 0], [10, 0], [10, 4], [5, 4], [5, 8], [5, 4.0001], [0, 4]]
    out = D.round_outline(spiky, 0.5)
    assert all(p[1] <= 8 for p in out)


def test_sections_fill_their_box():
    rr = D.rr(-2, 2, -1, 1, 0.5)
    ov = D.oval(-2, 2, -1, 1)
    for sec in (rr, ov):
        xs, zs = [p[0] for p in sec], [p[1] for p in sec]
        assert math.isclose(min(xs), -2, abs_tol=1e-3) and math.isclose(max(xs), 2, abs_tol=1e-3)
        assert math.isclose(min(zs), -1, abs_tol=1e-3) and math.isclose(max(zs), 1, abs_tol=1e-3)


def test_a_loft_part_passes_the_schema():
    side = [[0, -2], [20, -2], [20, 2], [0, 2]]
    top = [[0, -1.5], [20, -1.5], [20, 1.5], [0, 1.5]]
    part = {"role": "body", "finish": "polymer", "motion": {"kind": "fixed"},
            "shape": {"kind": "loft", "side": side, "x": [-1.5, 1.5], "top": top,
                      "sections": [{"y": 0.0, "outline": D.oval(-1, 1, -1, 1)}, {"y": 20.0, "outline": D.rr(-1, 1, -1, 1, 0.3)}]},
            "sources": {"side": {"guess": "a test outline, a box"}, "top": {"guess": "a test outline, a box"},
                        "sections": {"guess": "a test: an oval then a rounded box"}}}
    bad = C._schema_problems({"contract": "weaponlab-blueprint/1", "name": "T", "action": "bolt_stripper", "sources": "x",
                              "parts": {"stock": part}, "marks": {}}, "blueprint")
    assert not [b for b in bad if "stock" in b and "shape" in b], bad
