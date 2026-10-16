"""The M1911A1 worked example, steps 1 to 3: its source, facts, figures and traces, as they were done on 2026-10-16.

    python examples/m1911a1/sources.py <path to FM 23-35 (1940).pdf>

The manual is FM 23-35, Basic Field Manual: Automatic Pistol, Caliber .45, M1911 and M1911A1 (War Department,
1940), a US government work: https://archive.org/details/fm-23-35-automatic-pistol-caliber-.-45-m-1911-and-m-1911-a-1-1940
Pixel numbers below were read off the tools' grid pictures and then measured by the tools (span, ticks, snap)."""
import sys

from weaponlab.blueprint import figures as F
from weaponlab.blueprint import plan as P
from weaponlab.blueprint import sources as S
from weaponlab.blueprint import specs as X
from weaponlab.blueprint import trace as T

G, SRC = "M1911A1", "fm23-35-1940"

S.add(G, sys.argv[1], SRC, "manual", "FM 23-35 Basic Field Manual: Automatic Pistol, Caliber .45, M1911 and M1911A1",
      "us-government-work", publisher="War Department", year=1940,
      url="https://archive.org/details/fm-23-35-automatic-pistol-caliber-.-45-m-1911-and-m-1911-a-1-1940",
      gun_title="Pistol, Automatic, Caliber .45, M1911A1")
print(S.scan(G, SRC)["kinds"])

# step 2: the general data table, page 8 (the barrel's length prints in the table's column at the page's top)
for fid, v, u, page, q in [
        ("overall_length", 8.593, "in", 8, "Overall length of pistol inches 8.593"),
        ("sight_height", 0.5597, "in", 8, "Height of front sight above axis of bore do 0.5597"),
        ("barrel_length", 5.03, "in", 8, "Length of barrel do 5.03"),
        ("bore", 0.45, "in", 8, "Caliber of bore inches 0.45"),
        ("weight", 2.437, "lb", 8, "Weight of pistol with magazine pounds 2.437"),
        ("weight_loaded_magazine", 0.481, "lb", 8, "Weight of loaded magazine, 7 rounds (approximate) do 0.481"),
        ("weight_empty_magazine", 0.156, "lb", 8, "Weight of empty magazine do 0.156"),
        ("magazine_capacity", 7, "count", 7, "making seven more shots available")]:
    X.add(G, fid, v, u, SRC, page, q)
fx = X.facts(G)

# step 3a: the photo (Figure 2, page 7, left side), scaled by the overall length, framed by the front sight's height
F.add(G, "photo-a1-left", SRC, 7, "photo", shows="left", crop=[0.08, 0.2, 0.88, 0.97], rotate_deg=90, dpi=200,
      caption="Figure 2. Automatic pistol, caliber .45, M1911A1")
s = T.silhouette(G, "photo-a1-left", region=[235, 70, 1008, 545], close_px=7, eps_px=1.5)
px = s["outline_px"]
c = F.calibrate_extent(G, "photo-a1-left", px, "overall_length", direction=(1, 0))
xmin, xmax = min(p[0] for p in px), max(p[0] for p in px)
sight = min((p for p in px if p[0] < xmin + 0.1 * (xmax - xmin)), key=lambda p: p[1])     # the front sight's top
yb = sight[1] + fx["sight_height"]["value"] / c["cm_per_px"]
F.frame(G, "photo-a1-left", [xmax, yb], [xmin, yb], [xmin + fx["barrel_length"]["value"] / c["cm_per_px"], yb])
T.save(G, "photo_outline", T.silhouette(G, "photo-a1-left", region=[235, 70, 1008, 545], close_px=7, eps_px=1.5))
T.save(G, "photo_guard", T.region(G, "photo-a1-left", [640, 265], gap_px=2, name="guard"))

# step 3b: the sectional side view (Figure 3, page 12) and the plan section (its top, page 11)
F.add(G, "section-side", SRC, 12, "section", shows="left", dpi=300, rotate_deg=90,
      caption="Figure 3. Automatic pistol, caliber .45, M1911A1, sectional views")
F.add(G, "section-top", SRC, 11, "top", dpi=300, rotate_deg=90,
      caption="Section on center lines of barrel, firing pin, and extractor (top of Fig. 3)")
ticks = T.ticks(G, "section-side", [640, 978, 1330, 992], min_share=0.6)["ticks_px"]       # its 0 to 5 inch bar
F.calibrate(G, "section-top", [0, 0], [ticks[-1] - ticks[0], 0], cm=12.7)                  # the same plate's bar
# the section is matched to the photo on the trigger guard (its printed bar reads 5 to 10 percent off the photo)
g = T.region(G, "section-side", [950, 440], gap_px=2, name="guard")
T.save(G, "section_guard_px", g)
F.align(G, "section-side", "photo-a1-left", g["outline_px"], P.trace(G, "photo_guard")["outline_cm"], muzzle="left",
        note="the slide is drawn locked back; its y readings here are of the open slide; the printed inches bar reads about 5 to 10 percent off the photo")
T.save(G, "section_magazine", T.snap(G, "section-side", [[1090, 310], [1265, 300], [1400, 805], [1205, 815]],
                                     radius_px=10, step_px=6, eps_px=2.0, name="magazine"))
print("sources done; next: examples/m1911a1/blueprint.py")
