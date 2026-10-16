"""The M1911A1 worked example, the detail pass: shaped parts, every visible part, surface features, the parts list.
Run after sources.py and blueprint.py. Readings are by the tools (trace, span, peaks); each guess says why."""
import json

from weaponlab.blueprint import figures as F
from weaponlab.blueprint import plan as P
from weaponlab.blueprint import sources as S
from weaponlab.blueprint import store
from weaponlab.blueprint import trace as T

G, SRC = "M1911A1", "fm23-35-1940"
T.smoothing(13, 40)                     # the detail traces (the magazine catch) lose their edge noise too
photo, side, top = F.figure(G, "photo-a1-left"), F.figure(G, "section-side"), F.figure(G, "section-top")
bp = store.load(G, "blueprint")
outline = P.trace(G, "photo_outline")["outline_cm"]
sl = bp["parts"]["slide"]["shape"]
hs = sl["x"][1]
slide_top = 1.246
z_split = min(p[1] for p in sl["outline"])
slide_w = 2 * hs
fx = {f["id"]: f for f in store.load(G, "sources")["facts"]}
BARREL = fx["barrel_length"]["value"]

# --- the parts list: the labels on the sections (pages 11 and 12), read off the figures --------------------------
L = [  # name, number, page, figure, visible, why
    ("Slide", "D1827", 12, "section-side", True, "the slide"), ("Receiver", "D35359", 12, "section-side", True, "the frame"),
    ("Barrel", "C3838", 11, "section-top", True, "at the muzzle and through the ejection port"),
    ("Bushing", "B8596", 11, "section-top", True, "round the muzzle"),
    ("Sight (front)", "A13197", 12, "section-side", True, "on the slide's front"), ("Sight (rear)", "A13196", 12, "section-side", True, "on the slide's rear"),
    ("Stop (firing pin)", "A13205", 12, "section-side", True, "the slide's rear face"),
    ("Hammer", "C3839", 12, "section-side", True, "behind the slide"), ("Safety (grip)", "D1828", 12, "section-side", True, "the back strap's top"),
    ("Housing (mainspring)", "C3841", 12, "section-side", True, "the back strap's bottom"), ("Loop (lanyard)", "A13214", 12, "section-side", True, "under the housing"),
    ("Trigger", "B8604", 12, "section-side", True, "in the trigger guard"), ("Tube (magazine)", "C6695", 12, "section-side", True, "when it is out"),
    ("Base (magazine)", "B8606", 12, "section-side", True, "under the grip"), ("Stock", "C6406", 11, "section-top", True, "both sides of the grip"),
    ("Screw (stock)", "B19023", 11, "section-top", True, "on each stock"), ("Catch (magazine)", "B8609", 11, "section-top", True, "its button on the left"),
    ("Plug (recoil spring)", "A13201", 12, "section-side", True, "under the muzzle"),
    ("Follower", "B8608", 12, "section-side", False, "inside the magazine"), ("Spring (firing pin)", "A13204", 12, "section-side", False, "inside the slide"),
    ("Pin", "B8599", 12, "section-side", False, "inside the slide"), ("Pin (hammer)", "A13206", 12, "section-side", False, "its head is under the thumb safety and the grip"),
    ("Pin (sear)", "A13207", 12, "section-side", False, "covered by the thumb safety"), ("Sear", "B8601", 12, "section-side", False, "inside the frame"),
    ("Pin", "A13211", 12, "section-side", False, "inside the frame"), ("Disconnector", "B8603", 12, "section-side", False, "inside the frame"),
    ("Spring (sear)", "B8602", 12, "section-side", False, "inside the frame"), ("Strut", "B8600", 12, "section-side", False, "inside the housing"),
    ("Cap", "A13209", 12, "section-side", False, "inside the housing"), ("Mainspring", "A13208", 12, "section-side", False, "inside the housing"),
    ("Retainer", "A13213", 12, "section-side", False, "inside the housing"), ("Pin (housing)", "A13216", 12, "section-side", False, "flush with the frame"),
    ("Spring (recoil)", "A13200", 12, "section-side", False, "inside the slide"), ("Guide", "B8597", 12, "section-side", False, "inside the slide"),
    ("Link", "A13198", 12, "section-side", False, "under the barrel"), ("Pin (link)", "A13199", 12, "section-side", False, "the slide stop's pin passes it"),
    ("Spring (magazine)", "B8607", 12, "section-side", False, "inside the magazine"), ("Extractor", "B8598", 11, "section-top", False, "inside the slide"),
    ("Bushing (stock screw)", "B19022", 11, "section-top", False, "under the stock"), ("Spring (catch)", "A13217", 11, "section-top", False, "inside the frame"),
    ("Lock (catch)", "A13218", 11, "section-top", False, "inside the frame")]
doc = store.load(G, "sources")
doc["parts_list"] = [{"name": n, "number": num, "page": pg, "figure": fig, "visible": v, "why": w, "source": SRC} for n, num, pg, fig, v, w in L]
# named in the text, not labelled on the sections, and on the outside
doc["parts_list"] += [{"name": "Slide stop", "page": 10, "visible": True, "why": "its thumbpiece on the left (paragraph 3, page 10)", "source": SRC},
                      {"name": "Safety lock", "page": 10, "visible": True, "why": "the thumb safety on the left (page 10)", "source": SRC}]
store.save(G, "sources", doc)
TEXT = lambda pg, q: {"derived": "FM 23-35 (1940) page %d: %s" % (pg, q)}  # noqa: E731

# --- the slide: shaped by section A-A, its sights apart, its rear serrations ------------------------------------
aa = P.trace_px(G, "section_aa_px")
xs, ys = [p[0] for p in aa], [p[1] for p in aa]
cx = (min(xs) + max(xs)) / 2.0
k = slide_w / (max(xs) - min(xs))                       # cm a px of the section, so its width is the slide's
front = [[round((x - cx) * k, 4), round(slide_top - (y - min(ys)) * k, 4)] for x, y in aa]
P.views(G, "slide", front=[{"y": [-7.0, BARREL + 0.5], "outline": front}],
        front_source={"figure": "section-side", "method": "traced", "note": "section A-A (the slide at the barrel bushing), scaled to the slide's width, its top on the slide's top"})
# the sights: the outline above the slide's flat top, at the front and the rear
RIDE = {"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": bp["parts"]["slide"]["motion"]["travel_cm"]}
RIDE_SRC = {"axis": {"derived": "the sights are fixed to the slide and move with it"}, "travel_cm": {"derived": "the slide's travel"}}
P.extrude(G, "sight_front", "slide", "parkerized", "photo_outline", [-0.16, 0.16],
          {"derived": "section A-A's front sight stub, 20 px across at its root less the drawing's two 3 px lines, scaled as the section"},
          clips=[("z", slide_top - 0.05, "above", "above the slide's top"), ("y", 7.0, "above", "the front sight, near the muzzle")], name="Sight A13197",
          motion=RIDE, motion_sources=RIDE_SRC)
P.extrude(G, "sight_rear", "slide", "parkerized", "photo_outline", [-0.5, 0.5],
          {"guess": "the rear sight's width: about 1 cm, the same as its notch and its two shoulders (no plan view shows it)"},
          clips=[("z", slide_top - 0.05, "above", "above the slide's top"), ("y", -3.0, "below", "the rear sight, over the slide's rear"),
                 ("y", -6.45, "above", "ahead of the slide's rear face")], name="Sight A13196", motion=RIDE, motion_sources=RIDE_SRC)
bp = store.load(G, "blueprint")
sv = bp["parts"]["slide"]
sv["shape"]["side"] = P.clip(sv["shape"]["side"], "z", slide_top + 0.02, "below")
sv["sources"]["side"]["note"] += "; kept below z=%.3f (the sights are their own parts)" % (slide_top + 0.02)
store.save(G, "blueprint", bp, strict=False)
pk = T.peaks(G, "photo-a1-left", [742, 120, 870, 165], light=True, min_gap_px=4, k=0.3)
cols = pk["columns_px"]
run = max((cols[i:j + 1] for i in range(len(cols)) for j in range(i, len(cols))
           if all(abs((cols[t + 1] - cols[t]) - pk["pitch_px"]) <= 1 for t in range(i, j))), key=len)
yg = F.to_gun(photo, [[run[0], 140.0], [run[-1], 140.0]])
zg = F.to_gun(photo, [[800.0, 120.0], [800.0, 165.0]])
pitch = pk["pitch_cm"]
P.feature(G, "slide", {"kind": "grooves", "face": "both", "count": len(run), "y": [round(min(yg[0][0], yg[1][0]) - pitch / 2, 3), round(max(yg[0][0], yg[1][0]) + pitch / 2, 3)],
                       "z": [round(zg[1][1], 3), round(zg[0][1], 3)], "width_cm": round(pitch * 0.5, 3), "depth_cm": 0.05,
                       "source": {"figure": "photo-a1-left", "method": "read", "note": "%d light lines %.1f px apart (peaks on the photo, rows 120 to 165 px); width half the pitch and depth 0.05 cm are guesses" % (len(run), pk["pitch_px"])}})
P.numbers(G, "slide", ["D1827", "A13205"])
P.numbers(G, "sight_front", ["A13197"])
P.numbers(G, "sight_rear", ["A13196"])

# the slide's lower front round the recoil spring plug (section A-A), ahead of the frame's dust cover
y_dc = round(BARREL - 1.3, 3)
DC = "the frame's dust cover ends 1.3 cm behind the muzzle, where the slide's lower lobe round the plug (section A-A) begins: a guess at the plug's and the bushing's length together"
P.extrude(G, "slide_front", "slide", "parkerized", "photo_outline", [-hs, hs], {"derived": "the slide's width"},
          clips=[("z", z_split, "below", "under the slide's lower edge"), ("y", y_dc, "above", DC)], name="Slide D1827 (front lobe)",
          motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": store.load(G, "blueprint")["parts"]["slide"]["motion"]["travel_cm"]},
          motion_sources={"axis": {"derived": "it is the slide's"}, "travel_cm": {"derived": "it is the slide's"}}, bevel_cm=0.08)
P.views(G, "slide_front", front=[{"y": [y_dc - 0.5, BARREL + 0.5], "outline": front}],
        front_source={"figure": "section-side", "method": "traced", "note": "section A-A, as the slide's"})
bp = store.load(G, "blueprint")
q = bp["parts"]["frame"]
q["shape"]["outline"] = P.clip(q["shape"]["outline"], "y", y_dc, "below")
q["sources"]["outline"]["note"] += "; behind y=%.3f (%s)" % (y_dc, DC)
bp.setdefault("mark_parts", {})
store.save(G, "blueprint", bp, strict=False)
P.numbers(G, "slide_front", ["D1827"])

# --- the hammer, the grip safety, the mainspring housing and the lanyard loop ---------------------------------
bp = store.load(G, "blueprint")
fr = bp["parts"].pop("frame_rear")
store.save(G, "blueprint", bp, strict=False)
hy = [p[0] for p in fr["shape"]["outline"]]
pivot_y = round(max(hy) - 0.35, 3)
P.part(G, "hammer", "hammer", "blued", fr["shape"], {"outline": fr["sources"]["outline"], "x": {"guess": "the hammer is about 0.8 cm thick at its spur (narrower than the frame)"},
       "axis": {"derived": "the hammer turns about the gun's x axis, on its pin"},
       "turn_deg": {"derived": "from cocked (as both figures draw it) forward to rest on the firing pin stop: about 50 degrees"},
       "pivot": {"derived": "the hammer's lower front, 0.35 cm behind the slide's rear face at the slide's lower edge, where the photo's outline shows it meets the frame"}},
       name="Hammer C3839", motion={"kind": "turn", "axis": [1.0, 0.0, 0.0], "turn_deg": -50.0, "pivot": [0.0, pivot_y, z_split + 0.25]})
bp = store.load(G, "blueprint")
bp["parts"]["hammer"]["shape"]["x"] = [-0.4, 0.4]
store.save(G, "blueprint", bp, strict=False)
P.numbers(G, "hammer", ["C3839"])
zmin = min(p[1] for p in outline)
back, miss = P.edge_line(outline, zmin + 1.0, -3.0, front=False)
inner = [[back[0][0] + 0.9, back[0][1]], [back[1][0] + 0.9, back[1][1]]]
z_joint = -6.2
side_of = lambda q: (inner[1][0] - inner[0][0]) * (q[1] - inner[0][1]) - (inner[1][1] - inner[0][1]) * (q[0] - inner[0][0])   # noqa: E731
zb = min(q[1] for q in P.dense(outline) if side_of(q) > 0)       # the lowest point behind the line: the loop's bottom
WHY_IN = "0.9 cm inside the grip's back strap (a straight fit to the photo's rear outline, worst miss %.2f cm; the depth is a guess at the parts' thickness)" % miss
P.extrude(G, "grip_safety", "body", "parkerized", "photo_outline", [-hs * 0.85, hs * 0.85],
          {"guess": "the grip safety is a little narrower than the frame (0.85 of it), as it sits between the stocks"},
          clips=[("line", inner, "left", "behind the line " + WHY_IN), ("z", z_split, "below", "under the slide's lower edge"),
                 ("z", z_joint, "above", "over its joint with the mainspring housing (guess: the grip's middle, where the section shows the housing begin)")],
          name="Safety D1828")
P.extrude(G, "housing", "body", "parkerized", "photo_outline", [-hs * 0.85, hs * 0.85],
          {"guess": "the mainspring housing as wide as the grip safety"},
          clips=[("line", inner, "left", "behind the line " + WHY_IN), ("z", z_joint, "below", "under its joint with the grip safety"),
                 ("z", zb + 0.35, "above", "over the lanyard loop")], name="Housing C3841")
P.feature(G, "housing", {"kind": "texture", "pattern": "knurling", "face": "rear", "source": TEXT(6, "curve to fit the palm of the hand and is knurled")})
P.extrude(G, "loop", "body", "parkerized", "photo_outline", [-0.25, 0.25], {"guess": "the lanyard loop is a ring of 0.5 cm wire"},
          clips=[("line", inner, "left", "under the housing"), ("z", zb + 0.35, "below", "the bottom 0.35 cm of the outline behind the back strap line")], name="Loop A13214")
P.numbers(G, "grip_safety", ["D1828"])
P.numbers(G, "housing", ["C3841"])
P.numbers(G, "loop", ["A13214"])
# the frame and the stocks stop at the line
bp = store.load(G, "blueprint")
for pid in ("frame", "stocks"):
    q = bp["parts"][pid]
    q["shape"]["outline"] = P.clip_line(q["shape"]["outline"], inner[0], inner[1], "right")
    q["sources"]["outline"]["note"] = q["sources"]["outline"].get("note", "") + "; ahead of the line " + WHY_IN
store.save(G, "blueprint", bp, strict=False)
P.numbers(G, "frame", ["D35359"])

# --- the stocks: shaped by the plan view, checkered, with their screws ---------------------------------------------
up = {780: 728, 790: 722, 800: 717, 810: 713, 820: 710, 840: 708, 850: 708, 860: 707, 880: 706, 890: 707, 900: 708, 910: 707, 920: 707,
      930: 707, 940: 707, 950: 706, 960: 707, 970: 706, 980: 707, 990: 706, 1000: 704, 1010: 705, 1020: 707, 1030: 709, 1040: 712,
      1050: 715, 1060: 719, 1070: 723, 1080: 730}
dn = {780: 865, 790: 865, 800: 868, 860: 877, 870: 878, 880: 876, 890: 875, 900: 874, 910: 874, 920: 874, 930: 874, 940: 876, 950: 879,
      960: 879, 970: 877, 980: 873, 990: 873, 1000: 875, 1010: 875, 1020: 873, 1040: 869, 1050: 866, 1060: 862, 1070: 856, 1080: 848}
mid, kw = (733 + 858) / 2.0, slide_w / 125.0              # the slide's middle and its 125 px across in the plan view
st = store.load(G, "blueprint")["parts"]["stocks"]["shape"]["outline"]
sy0, sy1 = max(p[0] for p in st), min(p[0] for p in st)    # the stocks' front and rear (y) in the side view
cols = sorted(set(up) & set(dn))
raw = [kw * ((mid - up[c]) + (dn[c] - mid)) / 2.0 for c in cols]
sm = [sum(raw[max(0, i - 2):i + 3]) / len(raw[max(0, i - 2):i + 3]) for i in range(len(raw))]   # five-column mean: the scan's 1 px jitter out
pick = list(range(0, len(cols), 3)) + ([len(cols) - 1] if (len(cols) - 1) % 3 else [])
prof = [(sy0 + (sy1 - sy0) * (cols[i] - cols[0]) / (cols[-1] - cols[0]), sm[i]) for i in pick]
topv = [[round(y, 4), round(-w, 4)] for y, w in prof] + [[round(y, 4), round(w, 4)] for y, w in reversed(prof)]
P.views(G, "stocks", top=topv, top_source={"figure": "section-top", "method": "read",
        "note": "the stocks' outer edges in the plan view, column by column (spans 780 to 1080 px, leader lines left out), half-widths about the slide's middle (795.5 px) at its 125 px for the slide's width, a five-column mean, every third column; run over the stocks' length in the side view"})
P.feature(G, "stocks", {"kind": "texture", "pattern": "checkering", "face": "both", "source": {"figure": "photo-a1-left", "method": "read", "note": "the photo shows the stocks checkered"}})
bp = store.load(G, "blueprint")
sty = (sy0 + sy1) / 2.0
stz = [p[1] for p in st]
for zz in (max(stz) - 1.0, min(stz) + 1.0):
    bp["parts"]["stocks"].setdefault("features", []).append({"kind": "screw", "face": "both", "at": [round(sty, 3), round(zz, 3)], "r": 0.3, "head_cm": 0.08, "slot": True,
        "source": {"guess": "two screws a stock, at its middle 1 cm from its top and its bottom (the plan view shows one, SCREW B19023); head 0.6 cm across"}})
store.save(G, "blueprint", bp, strict=False)
P.numbers(G, "stocks", ["C6406", "B19023"])

# --- the trigger, the magazine catch, the slide stop, the thumb safety ------------------------------------------
gd = P.trace(G, "photo_guard")["outline_cm"]
gb = P.box(gd)
trig = [[gb["y"][0] + 0.05, gb["z"][1]], [gb["y"][0] + 0.55, gb["z"][1]], [gb["y"][0] + 0.75, gb["z"][0] + 0.9], [gb["y"][0] + 0.45, gb["z"][0] + 0.75], [gb["y"][0] + 0.05, gb["z"][0] + 0.9]]
P.part(G, "trigger", "trigger", "blued", {"kind": "extrude", "outline": trig, "x": [-0.3, 0.3]},
       {"outline": {"guess": "the trigger blade at the rear of the guard's opening (photo_guard), 0.5 to 0.7 cm long; the photo shows it black on black"},
        "x": {"guess": "a 0.6 cm wide trigger"}, "axis": {"derived": "the M1911's trigger slides straight back (FM 23-35 page 6: its face is cut back)"},
        "travel_cm": {"guess": "a short straight pull, 0.25 cm"}},
       name="Trigger B8604", motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": 0.25})
P.feature(G, "trigger", {"kind": "texture", "pattern": "knurling", "face": "front", "source": TEXT(6, "The face of the trigger is cut back and knurled")})
P.numbers(G, "trigger", ["B8604"])
cat = T.blob(G, "photo-a1-left", [708, 222, 758, 288], [730, 255], light=True, blur_px=2, name="catch")
T.save(G, "photo_catch", cat)
P.extrude(G, "catch", "release", "blued", "photo_catch", [hs - 0.4, hs + 0.15],
          {"guess": "the catch button stands 0.15 cm proud of the frame's left side"},
          motion={"kind": "slide", "axis": [-1.0, 0.0, 0.0], "travel_cm": 0.4},
          motion_sources={"axis": {"derived": "pressed in from the left (FM 23-35 page 7: 'the magazine catch is then depressed')"},
                          "travel_cm": {"guess": "the pistol action's typical 0.4 cm press"}}, name="Catch B8609")
P.feature(G, "catch", {"kind": "texture", "pattern": "checkering", "face": "left", "source": TEXT(13, "checkered left end must be pressed inward")})
P.numbers(G, "catch", ["B8609"])
stop = [[3.1, z_split - 0.05], [0.6, z_split - 0.05], [0.2, z_split - 0.55], [0.6, z_split - 1.05], [1.4, z_split - 0.6], [3.1, z_split - 0.45]]
P.part(G, "slide_stop", "stop", "parkerized", {"kind": "extrude", "outline": stop, "x": [hs, hs + 0.2]},
       {"outline": {"guess": "the slide stop on the frame's left over the trigger guard: its body along the slide's lower edge and its thumbpiece down and back (FM 23-35 page 10 names its thumbpiece); the photo shows it black on black"},
        "x": {"guess": "0.2 cm proud of the frame"}, "axis": {"derived": "it turns about its pin, across the gun"},
        "turn_deg": {"guess": "up 8 degrees to hold the slide open"}, "pivot": {"derived": "its pin at the front of its body"}},
       name="Slide stop", motion={"kind": "turn", "axis": [1.0, 0.0, 0.0], "turn_deg": 8.0, "pivot": [hs, 2.7, z_split - 0.25]})
safe = [[-5.2, z_split - 0.15], [-6.6, z_split - 0.15], [-6.8, z_split - 0.75], [-5.9, z_split - 0.9], [-5.0, z_split - 0.55]]
P.part(G, "thumb_safety", "body", "parkerized", {"kind": "extrude", "outline": safe, "x": [hs, hs + 0.2]},
       {"outline": {"guess": "the safety lock on the frame's left under the slide's rear, its thumbpiece forward (FM 23-35 page 10 names it); the photo shows it black on black"},
        "x": {"guess": "0.2 cm proud of the frame"}}, name="Safety lock")

# --- the bushing and the recoil spring plug at the muzzle --------------------------------------------------------
od = store.load(G, "blueprint")["parts"]["barrel"]["shape"]["profile"][0][1]
travel = store.load(G, "blueprint")["parts"]["slide"]["motion"]["travel_cm"]
RIDES = {"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": travel}
RIDES_SRC = {"axis": {"derived": "it sits in the slide's front and moves with it"}, "travel_cm": {"derived": "the slide's travel"}}
P.lathe(G, "bushing", "slide", "blued", [[BARREL - 1.0, od + 0.18], [BARREL + 0.02, od + 0.18]], [0.0, 0.0],
        {"derived": "section A-A's bushing ring round the barrel: about 0.18 cm thick in the section; its front flush with the muzzle"},
        {"derived": "on the bore"}, bore_r=od + 0.01, name="Bushing B8596", motion=RIDES, motion_sources=RIDES_SRC)
plug_z = round(-(330 - 245) * k, 3)
P.lathe(G, "plug", "slide", "blued", [[BARREL - 0.6, 0.42], [BARREL - 0.05, 0.42]], [0.0, plug_z],
        {"derived": "section A-A's lower circle (the recoil spring plug), about 0.84 cm across at the section's scale"},
        {"derived": "section A-A: its centre 85 px under the barrel's, at the section's scale"}, name="Plug A13201", motion=RIDES, motion_sources=RIDES_SRC)
P.numbers(G, "bushing", ["B8596"])
P.numbers(G, "plug", ["A13201"])
P.numbers(G, "barrel", ["C3838"])
P.numbers(G, "magazine", ["C6695", "B8606"])
print("parts:", ", ".join(store.load(G, "blueprint")["parts"]))
