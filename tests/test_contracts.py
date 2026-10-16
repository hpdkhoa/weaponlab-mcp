"""The digitizer's three contracts: a good document passes, and each kind of fault gives its sentence."""
import copy

import pytest

from weaponlab import contracts as C
from weaponlab.gunkit import actions as A
from weaponlab.gunkit import proxy as X


def sources():
    return {"contract": "weaponlab-sources/1", "gun": "M1911A1", "title": "Pistol, Automatic, Cal. .45, M1911A1",
            "sources": [{"id": "fm23-35-1940", "kind": "manual", "title": "FM 23-35 Automatic Pistol M1911 and M1911A1",
                         "publisher": "War Department", "year": 1940, "file": "fm.pdf", "pages": 102, "text_layer": True,
                         "license": {"basis": "us-government-work"}}],
            "pages": [{"source": "fm23-35-1940", "page": 8, "kind": "table", "text_chars": 1500, "images": 1}],
            "figures": [{"id": "section-bore", "source": "fm23-35-1940", "page": 11, "kind": "section", "shows": "right",
                         "to_scale": True, "image": "fig.png", "rotate_deg": 90, "dpi": 300,
                         "scale": {"cm_per_px": 0.02, "a": [0, 0], "b": [1000, 0], "cm": 20.0, "fact": "overall_length"},
                         "frame": {"bore": [[0, 100], [1000, 100]], "origin": [300, 100]}}],
            "facts": [{"id": "overall_length", "value": 21.826, "unit": "cm", "raw": "8.593 inches", "source": "fm23-35-1940",
                       "page": 8, "quote": "Overall length of pistol inches 8.593"}]}


def blueprint():
    a = A.load("pistol_slide")
    fig = {"figure": "section-bore", "method": "traced"}
    box = [[-8.0, -2.0], [12.0, -2.0], [12.0, 1.5], [-8.0, 1.5]]
    parts = {"frame": {"role": "body", "shape": {"kind": "extrude", "outline": box, "x": [-1.2, 1.2]}, "finish": "parkerized",
                       "sources": {"outline": fig, "x": {"guess": "a typical service pistol frame, 2.4 cm wide"}}},
             "slide": {"role": "slide", "shape": {"kind": "extrude", "outline": box, "x": [-1.2, 1.2]}, "finish": "parkerized",
                       "motion": {"kind": "slide", "axis": [0, -1, 0], "travel_cm": 3.0},
                       "sources": {"outline": fig, "x": {"fact": "overall_length", "note": "test"}, "axis": {"derived": "along the bore, rearward"},
                                   "travel_cm": {"guess": "the slide opens about 3 cm"}}},
             "magazine": {"role": "magazine", "shape": {"kind": "extrude", "outline": box, "x": [-0.8, 0.8]}, "finish": "blued",
                          "motion": {"kind": "free"}, "sources": {"outline": fig, "x": {"guess": "a single stack magazine, 1.6 cm"}}}}
    marks = {m: {"at": [0.0, 0.0, 0.0], "source": {"derived": "test mark at the origin"}} for m in a["marks"]}
    return {"contract": "weaponlab-blueprint/1", "name": "M1911A1", "action": "pistol_slide", "sources": "missing.json",
            "parts": parts, "marks": marks, "mark_parts": {"mag_grab": "magazine", "slide_rear": "slide"}}


def test_the_samples_pass():
    assert C.check(sources()) == []
    assert C.check(blueprint(), sources=sources()) == []


def test_every_proxy_parts_map_passes():
    for a in A.ids():
        assert C.check(X.proxy(a)["partsmap"]) == [], a


def test_an_unknown_contract_is_named():
    assert "contract" in C.check({"contract": "nope"})[0]


def test_sources_catch_missing_ids_and_a_wrong_scale():
    s = sources()
    s["facts"][0]["source"] = "other"
    s["figures"][0]["scale"]["cm"] = 25.0
    bad = C.check(s)
    assert any("source other is not in sources" in b for b in bad)
    assert any("not the 25.000 cm given" in b for b in bad)


def test_a_side_view_says_its_side():
    s = sources()
    del s["figures"][0]["shows"]
    assert any("which side" in b for b in C.check(s))


def test_a_number_without_a_source_fails():
    b = blueprint()
    del b["parts"]["slide"]["sources"]["travel_cm"]
    assert "part slide: no source for its travel_cm" in C.check(b, sources=sources())


def test_a_ref_must_name_a_known_figure_or_fact():
    b = blueprint()
    b["parts"]["frame"]["sources"]["outline"] = {"figure": "nowhere"}
    assert any("figure nowhere is not in the sources" in x for x in C.check(b, sources=sources()))


def test_a_guess_says_why():
    b = blueprint()
    b["parts"]["frame"]["sources"]["x"] = {"guess": "?"}
    assert C.check(b, sources=sources())          # a guess shorter than a reason fails the schema


def test_roles_and_required_parts_follow_the_action():
    b = blueprint()
    b["parts"]["slide"]["role"] = "bolt"
    bad = C.check(b, sources=sources())
    assert any("role bolt is not body or a part of pistol_slide" in x for x in bad)
    assert any("needs a part with role slide" in x for x in bad)


def test_a_moving_part_needs_its_motion_and_x_runs_right_to_left():
    b = blueprint()
    del b["parts"]["slide"]["motion"]
    b["parts"]["frame"]["shape"]["x"] = [1.2, -1.2]
    bad = C.check(b, sources=sources())
    assert "part slide: a moving part (slide) needs its motion" in bad
    assert any("x0 < x1" in x for x in bad)


def test_a_partsmap_without_a_model_must_be_a_proxy():
    pm = copy.deepcopy(X.proxy("pistol_slide")["partsmap"])
    pm["proxy"] = False
    assert "model: only a proxy has no model file" in C.check(pm)


@pytest.mark.parametrize("kind", ["sources", "blueprint", "partsmap"])
def test_each_schema_loads(kind):
    assert C.schema(kind)["$id"] == "weaponlab-%s/1" % kind
