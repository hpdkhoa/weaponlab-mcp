"""M16A2 step 3: the blueprint (the owner, 2026-10-24: "finish M16A2"). A visual copy for the game.

Outlines: read off the right-side figure (TM 9-1005-319-23&P, 1991, page 1-0) with pixel rulers, in the figure's px.
Scale: the printed overall length with the compensator (39.63 in) from the butt's rearmost point to the compensator's
tip, along the bore. Bore: the barrel's and the compensator's middle lines in the figure. Breech face: the printed
barrel with compensator (21 in) back from the muzzle. Widths across: the manuals print none and no top view exists in
them; each is a guess with its reason. The figure is an illustration: its proportions are what the copy keeps.

Run: python blueprint_m16a2.py (WEAPONLAB_DIGITIZE set)."""
import json
import math

from weaponlab.blueprint import figures as F
from weaponlab.blueprint import plan as P
from weaponlab.blueprint import specs as S
from weaponlab.blueprint import store

G = "M16A2"
FIG = "tm-right-clean"
fx = S.facts(G)

# --- frame and scale ------------------------------------------------------------------------------------------------
BORE_REAR, BORE_FRONT = (934.0, 259.1), (1890.0, 247.2)      # the barrel's middle at x 1700 (236 to 263) and the
                                                            # compensator's at x 1860 (227 to 268), carried back
F.frame(G, FIG, list(BORE_REAR), list(BORE_FRONT), list(BORE_REAR))
cal = F.calibrate_extent(G, FIG, [[83.0, 330.0], [1892.0, 247.0]], "overall_length")
f = F.figure(G, FIG)
cmpx = f["scale"]["cm_per_px"]
ux, uy = BORE_FRONT[0] - BORE_REAR[0], BORE_FRONT[1] - BORE_REAR[1]
n = math.hypot(ux, uy)
ux, uy = ux / n, uy / n
muzzle_px = (1892.0, BORE_REAR[1] + (1892.0 - BORE_REAR[0]) * uy / ux)
L_COMP = fx["barrel_with_compensator"]["value"]
breech_px = (muzzle_px[0] - ux * L_COMP / cmpx, muzzle_px[1] - uy * L_COMP / cmpx)
F.frame(G, FIG, list(BORE_REAR), list(BORE_FRONT), list(breech_px))
f = F.figure(G, FIG)
g = lambda pts: [[round(a, 3), round(b, 3)] for a, b in F.to_gun(f, pts)]      # noqa: E731
print("scale cm/px", round(cmpx, 5), "breech px", [round(v, 1) for v in breech_px])

READ = {"figure": FIG, "method": "read", "note": "points read off the figure with pixel rulers (25 px grid, 2x zoom)"}


def guess(why):
    return {"guess": why}


P.new(G, "ar_gas", title="Rifle, 5.56 mm, M16A2")
bp = store.load(G, "blueprint")
bp["parts"], bp["marks"], bp["mark_parts"] = {}, {}, {}
store.save(G, "blueprint", bp, strict=False)


def ext(pid, role, finish, px, x, xsrc, name, motion=None, msrc=None, bevel=0.05, holes_px=()):
    P.extrude(G, pid, role, finish, None, x, xsrc, outline=g(px), outline_source=READ, name=name, motion=motion,
              motion_sources=msrc, bevel_cm=bevel)
    for h in holes_px:
        bp_ = store.load(G, "blueprint")
        bp_["parts"][pid].setdefault("holes", []).append({"kind": "polygon", "outline": g(h), "source": READ})
        store.save(G, "blueprint", bp_, strict=False)


W_UP = 2.3
W_SRC = guess("the receivers' width: about the magazine well's outside (a 5.56 mm double-stack magazine and its walls); no top view in the sources")
# --- the receivers, the handle, the stock, the grip -------------------------------------------------------------------
ext("upper", "body", "aluminium", [(578, 258), (940, 252), (946, 262), (946, 323), (592, 325), (580, 305)],
    [-W_UP / 2, W_UP / 2], W_SRC, "Upper receiver")
ext("carry_handle", "body", "aluminium",
    [(600, 256), (600, 236), (616, 214), (632, 198), (632, 150), (645, 141), (690, 143), (700, 149), (905, 160), (930, 176),
     (943, 200), (946, 254)],
    [-0.8, 0.8], guess("the carry handle narrower than the receiver: about two thirds of it"), "Carry handle with rear sight",
    holes_px=[[(705, 184), (905, 181), (918, 200), (915, 226), (705, 227), (699, 205)]])
ext("lower", "body", "aluminium",
    [(592, 325), (946, 325), (946, 408), (925, 412), (800, 416), (796, 427), (690, 421), (690, 396), (602, 386), (588, 350)],
    [-W_UP / 2, W_UP / 2], W_SRC, "Lower receiver", holes_px=[[(706, 393), (786, 393), (791, 412), (706, 410)]])
ext("grip", "body", "polymer",
    [(600, 384), (690, 390), (688, 420), (672, 455), (646, 520), (636, 552), (625, 558), (545, 552), (528, 535), (560, 470)],
    [-1.4, 1.4], guess("the pistol grip about 2.8 cm across, a hand's grip size"), "Pistol grip")
ext("stock", "body", "polymer",
    [(86, 262), (578, 258), (578, 352), (560, 355), (122, 513), (104, 508), (90, 450), (83, 330)],
    [-2.0, 2.0], guess("the A2 buttstock about 4 cm across at the butt"), "Buttstock")
# --- the barrel, the handguard, the front sight ---------------------------------------------------------------------
y_of = lambda xpx: F.to_gun(f, [[xpx, BORE_REAR[1] + (xpx - BORE_REAR[0]) * uy / ux]])[0][0]     # noqa: E731
r_px = lambda top, bot: (bot - top) / 2.0 * cmpx                                                 # noqa: E731
y_ring0, y_ring1, y_hg1, y_fs0, y_fs1, y_comp = y_of(940), y_of(990), y_of(1520), y_of(1520), y_of(1625), y_of(1820)
y_muz = y_of(1892)
HG_R = r_px(205, 332)
P.lathe(G, "delta_ring", "body", "aluminium", [[y_ring0, r_px(195, 330)], [y_ring1, r_px(195, 330)]], [0.0, 0.0],
        dict(READ, note="the slip ring's height 195 to 330 px at x 940 to 990"), {"derived": "on the bore"}, name="Slip ring")
P.lathe(G, "handguard", "body", "polymer", [[y_ring1, HG_R], [y_hg1, HG_R * 0.94]], [0.0, 0.0],
        dict(READ, note="the handguard's height 205 to 332 px behind, 210 to 330 px at its front cap"), {"derived": "on the bore"},
        name="Handguards (round, ribbed)")
P.lathe(G, "barrel", "body", "parkerized", [[0.0, r_px(236, 263)], [y_comp, r_px(236, 263)]], [0.0, 0.0],
        dict(READ, note="the barrel 236 to 263 px across at x 1650 to 1800"), {"derived": "on the bore, from the breech face"},
        bore_r=0.28, name="Barrel")
P.lathe(G, "compensator", "body", "parkerized", [[y_comp, r_px(227, 268)], [y_muz, r_px(227, 268)]], [0.0, 0.0],
        dict(READ, note="the compensator 227 to 268 px across at x 1820 to 1892"), {"derived": "on the bore"}, bore_r=0.3,
        name="Compensator")
ext("front_sight", "body", "parkerized",
    [(1520, 252), (1526, 205), (1586, 141), (1608, 141), (1612, 236), (1626, 240), (1626, 300), (1590, 306), (1520, 300)],
    [-0.8, 0.8], guess("the front sight tower about 1.6 cm across"), "Front sight assembly",
    holes_px=[[(1556, 178), (1590, 160), (1592, 205), (1556, 210)]])
# --- the moving parts (the ar_gas action's) --------------------------------------------------------------------------
ACT = {"derived": "the ar_gas action's part (Gun Kit): its axis and travel"}
ext("handle", "handle", "aluminium", [(574, 238), (612, 238), (612, 257), (574, 257)], [-1.6, 1.6],
    guess("the T charging handle's wings, wider than the receiver"), "Charging handle",
    motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": 8.4}, msrc={"axis": ACT, "travel_cm": ACT})
ext("carrier", "carrier", "parkerized", [(700, 263), (935, 263), (935, 300), (700, 300)], [-0.9, 0.9],
    guess("the bolt carrier inside the upper: the ejection port's height, narrower than the receiver"), "Bolt carrier",
    motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": 8.4}, msrc={"axis": ACT, "travel_cm": ACT}, bevel=None)
ext("cover", "cover", "parkerized", [(800, 266), (918, 266), (918, 301), (800, 301)], [-W_UP / 2 - 0.12, -W_UP / 2],
    guess("the dust cover, a thin plate on the upper's right over the ejection port"), "Ejection port cover",
    motion={"kind": "turn", "axis": [0.0, 1.0, 0.0], "turn_deg": -100.0,
            "pivot": [-W_UP / 2 - 0.06] + g([(860, 301)])[0]},
    msrc={"kind": ACT, "turn_deg": guess("the cover swings down about 100 degrees on its hinge along the port's lower edge"),
          "axis": guess("the cover's hinge runs along the bore"), "pivot": dict(READ, note="the port's lower edge (860, 301 px) on the upper's right face")}, bevel=None)
ext("assist", "assist", "parkerized", [(736, 242), (790, 242), (795, 294), (736, 294)], [-W_UP / 2 - 0.9, -W_UP / 2],
    guess("the forward assist's plunger standing off the upper's right"), "Forward assist",
    motion={"kind": "slide", "axis": [0.0, 1.0, 0.0], "travel_cm": 0.5}, msrc={"axis": ACT, "travel_cm": ACT}, bevel=None)
ext("catch", "catch", "parkerized", [(728, 326), (762, 326), (762, 346), (728, 346)], [W_UP / 2, W_UP / 2 + 0.25],
    guess("the bolt catch on the lower's left, over the magazine well's rear"), "Bolt catch",
    motion={"kind": "slide", "axis": [0.0, 0.0, 1.0], "travel_cm": 0.6}, msrc={"axis": ACT, "travel_cm": ACT}, bevel=None)
ext("release", "release", "parkerized", [(774, 334), (800, 334), (800, 356), (774, 356)], [-W_UP / 2 - 0.3, -W_UP / 2],
    guess("the magazine release button on the lower's right, behind the well"), "Magazine release",
    motion={"kind": "slide", "axis": [1.0, 0.0, 0.0], "travel_cm": 0.3}, msrc={"axis": ACT, "travel_cm": ACT}, bevel=None)
ext("trigger", "trigger", "parkerized", [(700, 380), (713, 380), (720, 418), (706, 420)], [-0.3, 0.3],
    guess("the trigger in the guard, 0.6 cm across"), "Trigger",
    motion={"kind": "turn", "axis": [1.0, 0.0, 0.0], "turn_deg": 12.0, "pivot": [0.0] + g([(708, 382)])[0]},
    msrc={"kind": ACT, "turn_deg": guess("about 12 degrees of trigger travel about its pin at its top"),
          "axis": guess("the trigger pin runs across the lower"), "pivot": dict(READ, note="the trigger's top at the lower (708, 382 px)")}, bevel=None)
ext("magazine", "magazine", "parkerized",
    [(806, 336), (928, 336), (928, 410), (935, 450), (955, 600), (948, 612), (830, 617), (820, 600), (800, 450), (800, 412)],
    [-1.2, 1.2], guess("a 30-round magazine about 2.4 cm across"), "Magazine, 30 rounds",
    motion={"kind": "free"}, msrc={"kind": {"derived": "the magazine: in the well at rest, else where the hand or gravity takes it"}})
# --- detail: the handguard's vents, the grip's checkering, the rear sight's knobs --------------------------------
bp = store.load(G, "blueprint")
hg = bp["parts"]["handguard"]
# the round handguard as three views (a lathe takes no cuts across it): its side, its round front section
circ = [[round(HG_R * math.cos(2 * math.pi * k / 32), 4), round(HG_R * math.sin(2 * math.pi * k / 32), 4)] for k in range(32)]
hg["shape"] = {"kind": "views", "side": [[y_ring1, -HG_R], [y_hg1, -HG_R * 0.94], [y_hg1, HG_R * 0.94], [y_ring1, HG_R]],
               "x": [-HG_R, HG_R], "front": [{"y": [y_ring1, y_hg1], "outline": circ}]}
hg["sources"] = {"side": hg["sources"]["profile"], "x": hg["sources"]["profile"], "front": {"derived": "round about the bore, the side's radius"}}
slots = []
for row_top, row_bot in ((219, 257), (283, 320)):            # the two rows of vents, read off the figure
    for k in range(22):
        cx = 1004 + k * 23.6                                 # 22 vents from x 1004 to 1500 px
        for xr in ([-HG_R - 0.1, -HG_R + 0.6], [HG_R - 0.6, HG_R + 0.1]):     # each side's shell, not through
            slots.append({"kind": "polygon", "outline": g([(cx - 5.5, row_top), (cx + 5.5, row_top), (cx + 5.5, row_bot), (cx - 5.5, row_bot)]),
                          "x": xr, "source": dict(READ, note="the handguard's vents: two rows of 22, 11 px wide, at 23.6 px steps (x 1004 to 1500); 0.6 cm deep into each side (a guess at the shell)")})
hg["holes"] = slots
gr = bp["parts"]["grip"]
gy0, gz0 = g([(545, 545)])[0]
gy1, gz1 = g([(680, 400)])[0]
gr["features"] = [{"kind": "knurl", "face": "both", "pattern": "diamond", "pitch_cm": 0.25, "depth_cm": 0.04,
                   "y": [min(gy0, gy1), max(gy0, gy1)], "z": [min(gz0, gz1) + 0.6, max(gz0, gz1) - 0.6],
                   "source": dict(READ, note="the grip's checkered panel (x 545 to 680 px); its pitch and depth a guess")}]
ch = bp["parts"]["carry_handle"]
wy, wz = g([(660, 175)])[0]
ey, ez = g([(660, 220)])[0]
ch["features"] = [{"kind": "screw", "face": "both", "at": [wy, wz], "r": round(19 * cmpx, 3), "head_cm": 0.35, "slot": False,
                   "source": dict(READ, note="the windage knob's round (660, 175 px, 38 px across)")},
                  {"kind": "screw", "face": "right", "at": [ey, ez], "r": round(17 * cmpx, 3), "head_cm": 0.5, "slot": False,
                   "source": dict(READ, note="the elevation knob (660, 220 px, 34 px across)")}]
store.save(G, "blueprint", bp, strict=False)
# --- marks ---------------------------------------------------------------------------------------------------------
pt = lambda x, y: g([(x, y)])[0]          # noqa: E731
P.mark(G, "muzzle", [0.0, round(y_muz, 3), 0.0], {"fact": "overall_length", "note": "the compensator's tip on the bore"})
gy, gz = pt(612, 470)
P.mark(G, "grip", [-1.4, gy, gz], dict(READ, note="the pistol grip's right face at its middle (612, 470 px)"), normal=[-1.0, 0.0, 0.0])
sy, _sz = pt(1250, 330)
P.mark(G, "support", [0.0, sy, -round(HG_R, 3)], dict(READ, note="under the handguard, midway along it (x 1250 px)"), normal=[0.0, 0.0, -1.0])
ty, tz = pt(712, 402)
P.mark(G, "trigger", [0.0, ty, tz], dict(READ, note="the trigger's face in the guard"))
py, pz = pt(860, 283)
P.mark(G, "port", [-W_UP / 2, py, pz], dict(READ, note="the ejection port's middle under the cover"), normal=[-1.0, 0.0, 0.0])
hy, hz = pt(592, 246)
P.mark(G, "handle", [0.0, hy, hz], dict(READ, note="the charging handle's T"), rides="handle")
wy, wz = pt(865, 330)
P.mark(G, "mag_well", [0.0, wy, wz], dict(READ, note="the magazine well's mouth under the upper"))
ly, lz = pt(865, 338)
P.lips(G, [0.0, ly, lz], dict(READ, note="the magazine's top inside the well"))
P.mark(G, "mag_lips", [0.0, ly, lz], dict(READ, note="the magazine's top inside the well"), rides="magazine")
my, mz = pt(890, 590)
P.mark(G, "mag_grab", [1.2, my, mz], dict(READ, note="the magazine's left face near its base"), normal=[1.0, 0.0, 0.0], rides="magazine")
cy, cz = pt(745, 336)
P.mark(G, "catch", [W_UP / 2 + 0.25, cy, cz], dict(READ, note="the bolt catch's paddle"), normal=[1.0, 0.0, 0.0], rides="catch")
ry, rz = pt(787, 345)
P.mark(G, "release", [-W_UP / 2 - 0.3, ry, rz], dict(READ, note="the magazine release button"), normal=[-1.0, 0.0, 0.0], rides="release")
ay, az = pt(765, 268)
P.mark(G, "assist", [-W_UP / 2 - 0.9, ay, az], dict(READ, note="the forward assist's button"), normal=[-1.0, 0.0, 0.0], rides="assist")
rsy, rsz = pt(657, 160)
P.mark(G, "rear_sight", [0.0, rsy, rsz], dict(READ, note="the rear sight's aperture in the carry handle's rear housing (657, 160 px)"))
fsy, fsz = pt(1597, 143)
P.mark(G, "front_sight", [0.0, fsy, fsz], dict(READ, note="the front sight post's tip (1597, 143 px)"))
bp = store.load(G, "blueprint")
print(json.dumps({"parts": list(bp["parts"]), "marks": list(bp["marks"]), "length_cm": round(y_muz - g([(83, 330)])[0][0], 2)}))
