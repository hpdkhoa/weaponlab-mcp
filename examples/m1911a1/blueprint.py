"""The M1911A1 worked example, step 4: its blueprint from the figures, traces and facts sources.py kept (FM 23-35,
1940). Every number comes from a tool reading (trace, span, align) or a fact; each guess says why. Then:

    python -c "from weaponlab.blueprint import check, build; print(check.run('M1911A1', 'photo_outline', ['photo_guard']))"
    python -c "from weaponlab.blueprint import build; build.build('M1911A1'); build.render('M1911A1'); build.to_gunkit('M1911A1')"
"""
import json

from weaponlab.blueprint import figures as F
from weaponlab.blueprint import plan as P
from weaponlab.blueprint import specs as S
from weaponlab.blueprint import store
from weaponlab.blueprint import trace as T

G = "M1911A1"
fx = S.facts(G)
photo = F.figure(G, "photo-a1-left")
side = F.figure(G, "section-side")
outline = P.trace(G, "photo_outline")["outline_cm"]
BARREL = fx["barrel_length"]["value"]

# --- readings ------------------------------------------------------------------------------------------------------
top = sorted(p[1] for p in outline if 2 < p[0] < 10 and p[1] > 0.5)
slide_top = top[len(top) // 2]                                     # the slide's flat top above the bore (photo)
# the section, as px rows at the slide's middle (x 760 to 900): slide top 168, barrel 201 to 259, lower wall to 296.5
SEC = {"slide_top": 168.0, "barrel_top": 201.0, "barrel_bottom": 259.0, "slide_bottom": 296.5}
centre = (SEC["barrel_top"] + SEC["barrel_bottom"]) / 2.0
ratio = (SEC["slide_bottom"] - centre) / (centre - SEC["slide_top"])
z_split = -ratio * slide_top                                         # the slide's lower edge
slide_h = slide_top - z_split
y_rear = -6.45                                                       # the notch between the slide's rear face and the hammer
open_rear = F.to_gun(side, [[1568.0, 200.0]])[0][0]                  # the slide's rear face, drawn locked back
travel = round(y_rear - open_rear, 3)
# the plan section: slide 733 to 858 px across, stocks 707 to 876 (columns 520 and 940); the barrel reads 2.6 % wider
# there than in the side section, so its widths are taken back by that much before the ratio to the side section
w_ratio = (125.0 / 129.5) / 1.026
slide_w = round(w_ratio * slide_h, 3)
grip_w = round(slide_w * (169.0 / 125.0), 3)
barrel_od = round(75.0 / (SEC["slide_bottom"] - SEC["slide_top"]) * slide_h, 3)   # the barrel's outside, 194 to 269 px at px x 470 to 500
bore_r = round(fx["bore"]["value"] / 2.0, 4)
print(json.dumps({"slide_top": slide_top, "z_split": round(z_split, 3), "ratio": round(ratio, 4), "travel": travel,
                  "slide_w": slide_w, "grip_w": grip_w, "barrel_od": barrel_od}))

PH = {"figure": "photo-a1-left", "method": "traced"}
SIDE = "the section (figure section-side, slide rows at px x 760 to 900: top 168, barrel 201 to 259, lower wall 296.5)"
split_ref = {"derived": "the slide's lower wall in %s: %.3f times as far under the bore as its top is above it; applied to the photo's slide top (%.3f cm)" % (SIDE, ratio, slide_top)}
rear_ref = {"derived": "the notch between the slide's rear face and the hammer on the photo's outline (photo-a1-left)"}
w_ref = {"derived": "the plan section (figure section-top, column 520 px: 733 to 858) against the side section's slide height, 2.6 percent taken off for the two scans' barrel widths; times the photo's slide height %.3f cm" % slide_h}
grip_ref = {"derived": "the stocks in the plan section (figure section-top, column 940 px: 707 to 876) against the slide there (733 to 858), times the slide's width"}

P.new(G, "pistol_slide", title="Pistol, Automatic, Caliber .45, M1911A1")
bp = store.load(G, "blueprint")
bp["parts"], bp["marks"], bp["mark_parts"] = {}, {}, {}
store.save(G, "blueprint", bp, strict=False)

hs = slide_w / 2.0
# the slide: the photo's outline above its lower edge and ahead of its rear face
P.extrude(G, "slide", "slide", "parkerized", "photo_outline", [-hs, hs], w_ref,
          clips=[("z", z_split, "above", "the slide's lower edge: " + split_ref["derived"]), ("y", y_rear, "above", "the slide's rear face: " + rear_ref["derived"])],
          name="Slide D1827", motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": travel},
          motion_sources={"axis": {"derived": "the slide runs back along the bore"},
                          "travel_cm": {"derived": "the slide's rear face drawn locked back in the section (px 1568, y %.3f cm once the section is matched to the photo on the trigger guard) to its place closed in the photo (y %.3f)" % (open_rear, y_rear)}},
          bevel_cm=0.08)
# the frame: the photo's outline under the slide's lower edge; behind the slide, the hammer and the grip safety
P.extrude(G, "frame", "body", "parkerized", "photo_outline", [-hs, hs], {"derived": "the frame's sides run flush with the slide's: " + w_ref["derived"]},
          clips=[("z", z_split, "below", "under the slide's lower edge: " + split_ref["derived"])], name="Receiver D35359", bevel_cm=0.08)
P.hole(G, "frame", trace_name="photo_guard")
P.extrude(G, "frame_rear", "body", "parkerized", "photo_outline", [-hs * 0.8, hs * 0.8],
          {"guess": "the hammer and the grip safety are narrower than the frame: 0.8 of its width (no plan view shows them)"},
          clips=[("z", z_split, "above", "above the slide's lower edge"), ("y", y_rear, "below", "behind the slide's rear face")], name="Hammer C3839 and safety D1828")
# the stocks: the grip's sides, under the slide stop and over the magazine's base
zmin = min(p[1] for p in outline)
strap, strap_miss = P.edge_line(outline, zmin + 1.0, -6.0, front=True, y_max=-0.5)       # the grip's front strap (photo)
print("front strap", strap, "worst miss", strap_miss)
behind = [[strap[0][0] - 0.3, strap[0][1]], [strap[1][0] - 0.3, strap[1][1]]]
stock_top, stock_bottom = z_split - 1.2, zmin + 1.0
P.extrude(G, "stocks", "body", "plastic", "photo_outline", [-grip_w / 2.0, grip_w / 2.0], grip_ref,
          clips=[("z", stock_top, "below", "the stocks start under the frame's top (guess 1.2 cm under the slide's edge, as the photo shows the checkering)"),
                 ("z", stock_bottom, "above", "over the magazine's base (guess 1 cm over the grip's bottom)"),
                 ("line", behind, "left", "0.3 cm behind the grip's front strap (a straight fit to the photo's outline; guess at the strap's wall)")],
          name="Stock C6406")
# the barrel, round, inside the slide, from the breech face to the muzzle; the slide's front has its bore cut
P.lathe(G, "barrel", "body", "blued", [[0.0, barrel_od / 2.0], [BARREL, barrel_od / 2.0]], [0.0, 0.0],
        {"derived": "the barrel's length (fact barrel_length) and its outside: 75 px across where it stands clear of the slide in the section (px x 470 to 500), against the slide's height there (128.5 px), times the photo's slide height"},
        {"derived": "on the bore line, from the breech face (the origin)"}, bore_r=bore_r, name="Barrel C3838")
P.hole(G, "slide", bore={"at": [0.0, 0.0], "r": round(barrel_od / 2.0 + 0.02, 4), "y": [BARREL - 3.0, BARREL + 0.5]},
       source={"derived": "the barrel bushing's opening round the barrel's muzzle: the barrel's outside and 0.2 mm"})
# the ejection port: a cut on the slide's right side over the chamber
bp = store.load(G, "blueprint")
bp["parts"]["slide"].setdefault("holes", []).append({"kind": "polygon", "outline": [[0.2, -0.5], [3.4, -0.5], [3.4, slide_top - 0.25], [0.2, slide_top - 0.25]],
    "x": [-hs - 0.5, -0.1], "source": {"guess": "the ejection port over the chamber on the right side: from the breech face forward about one .45 ACP cartridge's length (3.2 cm), from under the slide's top to under the bore"}})
store.save(G, "blueprint", bp, strict=False)
# the magazine: the tube in the section, matched to the photo
mag_sec = P.trace(G, "section_magazine")["outline_cm"]
mag, turned = P.fit_along(mag_sec, strap, 0.3, zmin, front=True)
print("magazine turned", turned, "deg")
P.extrude(G, "magazine", "magazine", "blued", None, [-0.75, 0.75],
          {"guess": "a single-stack .45 ACP magazine: the cartridge's rim (1.2 cm) and its walls, about 1.5 cm across"},
          clips=[("z", z_split - 0.1, "below", "the magazine stops under the slide")],
          outline=mag, outline_source={"derived": "the magazine tube traced in the section (section_magazine), turned %.2f degrees to run along the photo's front strap, its front 0.3 cm inside the strap (a guess at the strap's wall) and its base at the photo's bottom" % turned},
          name="Magazine tube C6695", motion={"kind": "free"})
mag = store.load(G, "blueprint")["parts"]["magazine"]["shape"]["outline"]
mtop = max(p[1] for p in mag)
lips = [round(sum(p[0] for p in mag if p[1] > mtop - 0.6) / max(1, len([p for p in mag if p[1] > mtop - 0.6])), 3), round(mtop - 0.2, 3)]
mbot = min(p[1] for p in mag)
mbot_y = round(sum(p[0] for p in mag if p[1] < mbot + 0.6) / max(1, len([p for p in mag if p[1] < mbot + 0.6])), 3)
MAGSRC = {"derived": "the magazine part's outline (the section's tube set along the photo's front strap)"}
P.lips(G, [0.0, lips[0], lips[1]], MAGSRC)

# --- marks -----------------------------------------------------------------------------------------------------------
gy = [p[0] for p in outline if -10.5 < p[1] < -4.0]
grip_mid_y = round(sum(gy) / len(gy), 3) if gy else -5.0
P.mark(G, "muzzle", [0.0, BARREL, 0.0], {"fact": "barrel_length", "note": "the muzzle a barrel's length ahead of the breech face, on the bore"})
P.mark(G, "grip", [-grip_w / 2.0, grip_mid_y, -6.5], {"derived": "the right stock's face (half the grip's width) at the middle of the grip's outline in the photo"}, normal=[-1.0, 0.0, 0.0])
P.mark(G, "support", [grip_w / 2.0, grip_mid_y + 0.4, -7.5], {"derived": "the left stock's face, where a support hand wraps the grip (the proxy's place, on this grip)"}, normal=[0.0, 0.0, -1.0])
P.mark(G, "trigger", [0.0, 1.0, -3.4], {"derived": "inside the trigger guard's opening (photo_guard), toward its rear"})
P.mark(G, "port", [-hs, 1.8, slide_top * 0.4], {"derived": "the middle of the ejection port's cut on the slide's right side"}, normal=[-1.0, 0.0, 0.0])
P.mark(G, "slide_rear", [0.0, y_rear + 0.8, slide_top], {"derived": "the slide's top just ahead of its rear face (the rear serrations)"}, rides="slide")
P.mark(G, "slide_front", [0.0, BARREL - 2.0, slide_top], {"derived": "the slide's top 2 cm behind the muzzle"}, rides="slide")
P.mark(G, "mag_well", [0.0, lips[0], z_split - 0.6], {"derived": "the magazine well's top over the magazine's lips, under the slide"})
P.mark(G, "mag_lips", [0.0, lips[0], lips[1]], MAGSRC, rides="magazine")
P.mark(G, "mag_grab", [0.0, mbot_y, mbot + 0.2], MAGSRC, normal=[1.0, 0.0, 0.0], rides="magazine")
P.mark(G, "release", [hs, -0.6, -3.0], {"guess": "the magazine catch on the frame's left behind the trigger guard, where the right thumb presses it (its place in the photo, which shows the left side)"}, normal=[1.0, 0.0, 0.0])
P.mark(G, "stop", [hs, 2.5, z_split - 0.3], {"guess": "the slide stop on the frame's left over the trigger, at the slide's lower edge"}, normal=[1.0, 0.0, 0.0])
print("parts:", ", ".join(store.load(G, "blueprint")["parts"]))
