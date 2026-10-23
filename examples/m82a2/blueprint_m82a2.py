"""Barrett M82A2 (the owner, 2026-10-24: "then make barrett m82a2"): its blueprint, a visual copy for the game.

Outlines: read off the photo (Tomketchum, Wikimedia Commons, CC BY-SA 3.0; the rifle's left side, shot from above on
a floor) with pixel rulers. Scale: the .50 BMG cartridge lying beside it on the same floor, 5.450 in long (185 px). That
scale makes the rifle 142 cm long, which agrees with the 1409 mm published for the M82A2. Bore: the barrel's middle line.
Bolt face: over the magazine's front, where a round chambers (the photo; the M82 family's 737 mm barrel would put it
at 975 px, ahead of the grip, which a bullpup does not have: that fact is kept and reported, not used). No public
manual gives the M82A2's widths: each is a guess with its reason."""
import json
import math

from weaponlab.blueprint import figures as F
from weaponlab.blueprint import plan as P
from weaponlab.blueprint import specs as S
from weaponlab.blueprint import store

G = "M82A2"
FIG = "photo"
fx = S.facts(G)
F.calibrate(G, FIG, [1441.0, 425.0], [1626.0, 420.0], fact="cartridge_length")
BORE_REAR, BORE_FRONT = (800.0, 263.6), (1800.0, 263.0)        # the barrel's middle: 252 to 275 px at x 1450 to 1800
F.frame(G, FIG, list(BORE_REAR), list(BORE_FRONT), list(BORE_REAR))
f = F.figure(G, FIG)
cmpx = f["scale"]["cm_per_px"]
g = lambda pts: [[round(a, 3), round(b, 3)] for a, b in F.to_gun(f, pts)]      # noqa: E731
pt = lambda x, y: g([(x, y)])[0]                                                 # noqa: E731
READ = {"figure": FIG, "method": "read", "note": "points read off the photo with pixel rulers (25 px grid, 1.7x zoom)"}


def guess(why):
    return {"guess": why}


P.new(G, "ak_handle", title="Barrett M82A2 (.50 BMG, bullpup)")
bp = store.load(G, "blueprint")
bp["parts"], bp["marks"], bp["mark_parts"] = {}, {}, {}
store.save(G, "blueprint", bp, strict=False)


def ext(pid, role, finish, px, w, wsrc, name, motion=None, msrc=None, bevel=0.08, holes=()):
    P.extrude(G, pid, role, finish, None, [-w / 2.0, w / 2.0] if not isinstance(w, list) else w, wsrc, outline=g(px),
              outline_source=READ, name=name, motion=motion, motion_sources=msrc, bevel_cm=bevel)
    if holes:
        b_ = store.load(G, "blueprint")
        b_["parts"][pid].setdefault("holes", []).extend(holes)
        store.save(G, "blueprint", b_, strict=False)


W_UP, W_LO = 5.6, 6.2
# the upper receiver with its barrel shroud and its two rows of oval vents (cut 0.5 cm into each side)
vents = []
for row, xs in (((235, 247), (970, 1010, 1052, 1093, 1135, 1175, 1217, 1255)), ((271, 285), (1003, 1050, 1135, 1177, 1218, 1258))):
    for cx in xs:
        for xr in ([-W_UP / 2 - 0.1, -W_UP / 2 + 0.5], [W_UP / 2 - 0.5, W_UP / 2 + 0.1]):
            vents.append({"kind": "polygon", "outline": g([(cx - 17, row[0]), (cx + 17, row[0]), (cx + 17, row[1]), (cx - 17, row[1])]),
                          "x": xr, "source": dict(READ, note="the shroud's oval vents, 34 px long, two rows; 0.5 cm deep (a guess)")})
ext("upper", "body", "parkerized", [(70, 222), (1374, 222), (1374, 300), (66, 300), (62, 240)], W_UP,
    guess("the upper receiver about 5.6 cm across: a .50 BMG bolt carrier's width and its walls (no top view public)"),
    "Upper receiver and barrel shroud", holes=vents)
ext("lower", "body", "parkerized",
    [(300, 298), (840, 298), (840, 310), (795, 330), (790, 480), (560, 487), (540, 485), (538, 380), (470, 315), (300, 313)],
    W_LO, guess("the lower and the magazine housing about 6.2 cm across, round the 10-round magazine"), "Lower receiver and buttstock")
ext("trigger_housing", "body", "parkerized", [(940, 298), (1100, 298), (1100, 385), (1020, 385), (1020, 345), (940, 345)], 3.0,
    guess("the trigger housing about 3 cm across"), "Trigger housing (forward of the magazine)",
    holes=[{"kind": "polygon", "outline": g([(1025, 340), (1092, 340), (1092, 378), (1025, 378)]), "source": dict(READ, note="the trigger guard's opening")}])
ext("grip", "body", "polymer",
    [(955, 312), (1035, 312), (1035, 350), (1020, 400), (1005, 460), (1000, 492), (922, 492), (918, 465), (935, 400), (950, 345)], 3.0,
    guess("the pistol grip about 3 cm across"), "Pistol grip")
ext("front_grip", "body", "polymer",
    [(1195, 300), (1265, 300), (1258, 322), (1305, 430), (1290, 446), (1238, 442), (1200, 330)], 3.0,
    guess("the forward grip about 3 cm across"), "Forward grip")
ext("grip_mount", "body", "parkerized", [(1165, 292), (1300, 292), (1300, 306), (1165, 306)], 3.4, guess("its mount a little wider"), "Forward grip mount")
ext("scope_base", "body", "parkerized", [(930, 200), (1225, 200), (1225, 223), (930, 223)], 3.0, guess("the scope base about 3 cm across"), "Scope base")
ext("carry_handle", "body", "parkerized",
    [(878, 225), (878, 180), (890, 120), (905, 60), (1092, 60), (1092, 100), (912, 100), (898, 178), (898, 225)], 2.4,
    guess("the carrying handle's bar about 2.4 cm across"), "Carrying handle")
# the barrel and the muzzle brake (its two side ports cut through)
y_front = pt(1374, 263)[0]
y_brake0, y_brake1 = pt(1845, 263)[0], pt(1963, 263)[0]
P.lathe(G, "barrel", "body", "parkerized", [[0.0, 11.5 * cmpx], [y_brake0, 11.5 * cmpx]], [0.0, 0.0],
        dict(READ, note="the barrel 252 to 275 px across ahead of the shroud"), {"derived": "on the bore, from the bolt face"},
        bore_r=0.65, name="Barrel")
ext("brake", "body", "parkerized", [(1845, 233), (1963, 236), (1963, 290), (1845, 293)], 6.0,
    guess("the two-port brake about 6 cm across"), "Muzzle brake",
    holes=[{"kind": "polygon", "outline": g([(x0, 241), (x0 + 25, 241), (x0 + 25, 285), (x0, 285)]),
            "source": dict(READ, note="the brake's side ports")} for x0 in (1860, 1897)])
# the scope: a tube turned round its own line, read off the photo
zs = pt(1100, 168)[1]
prof = [[pt(890, 168)[0], 28 * cmpx], [pt(960, 168)[0], 26 * cmpx], [pt(965, 168)[0], 18 * cmpx], [pt(1250, 168)[0], 18 * cmpx],
        [pt(1300, 168)[0], 38 * cmpx], [pt(1392, 168)[0], 38 * cmpx]]
P.lathe(G, "scope", "body", "polymer", prof, [0.0, zs], dict(READ, note="the scope: eyepiece 56 px across, tube 36, objective 76"),
        dict(READ, note="the scope's middle line at 168 px"), name="Telescopic sight")
# the moving parts (the ak_handle action's)
ACT = {"derived": "the ak_handle action's part (Gun Kit)"}
ext("carrier", "carrier", "parkerized", [(300, 240), (800, 240), (800, 290), (300, 290)], 3.0,
    guess("the bolt carrier inside the upper, over the magazine"), "Bolt carrier",
    motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": 13.0},
    msrc={"axis": ACT, "travel_cm": guess("about a .50 BMG round's length and a little more (13 cm)")}, bevel=None)
P.extrude(G, "handle", "body", "parkerized", None, [-W_UP / 2 - 2.0, -W_UP / 2],
          guess("the charging handle stands 2 cm off the upper's right side (the photo shows the left: its slot's front end, 590 px)"),
          outline=g([(575, 236), (610, 236), (610, 278), (575, 278)]), outline_source=READ, name="Charging handle (rides the carrier)",
          parent="carrier")
ext("trigger", "trigger", "parkerized", [(1036, 336), (1050, 336), (1052, 372), (1040, 372)], 0.6, guess("the trigger 0.6 cm across"),
    "Trigger", motion={"kind": "turn", "axis": [1.0, 0.0, 0.0], "turn_deg": 12.0, "pivot": [0.0] + pt(1043, 336)},
    msrc={"kind": ACT, "axis": guess("its pin across the housing"), "pivot": dict(READ, note="the trigger's top"),
          "turn_deg": guess("about 12 degrees of travel")}, bevel=None)
ext("release", "release", "parkerized", [(540, 388), (600, 388), (600, 410), (540, 410)], [W_LO / 2, W_LO / 2 + 0.4],
    guess("the magazine release paddle on the lower's left, behind the magazine"), "Magazine release",
    motion={"kind": "turn", "axis": [0.0, 0.0, 1.0], "turn_deg": 10.0, "pivot": [W_LO / 2] + pt(540, 399)},
    msrc={"kind": ACT, "axis": guess("it swings out about its rear edge"), "pivot": dict(READ, note="its rear edge"),
          "turn_deg": guess("about 10 degrees")}, bevel=None)
ext("magazine", "magazine", "parkerized", [(600, 318), (788, 318), (785, 478), (600, 480)], 4.0,
    guess("the 10-round .50 BMG magazine about 4 cm across"), "Magazine, 10 rounds",
    motion={"kind": "free"}, msrc={"kind": {"derived": "the magazine: in the well at rest, else where the hand or gravity takes it"}})
# marks
y_muz = pt(1963, 263)[0]
P.mark(G, "muzzle", [0.0, round(y_muz, 3), 0.0], dict(READ, note="the brake's front on the bore"))
gy, gz = pt(975, 410)
P.mark(G, "grip", [-1.5, gy, gz], dict(READ, note="the pistol grip's right face at its middle"), normal=[-1.0, 0.0, 0.0])
sy, sz = pt(1255, 380)
P.mark(G, "support", [-1.5, sy, sz], dict(READ, note="the forward grip's right face at its middle"), normal=[-1.0, 0.0, 0.0])
ty, tz = pt(1045, 352)
P.mark(G, "trigger", [0.0, ty, tz], dict(READ, note="the trigger's face"))
py, pz = pt(700, 268)
P.mark(G, "port", [-W_UP / 2, py, pz], dict(READ, note="over the magazine, where a case leaves (the right side)"), normal=[-1.0, 0.0, 0.0])
hy, hz = pt(592, 257)
P.mark(G, "handle", [-W_UP / 2 - 2.0, hy, hz], dict(READ, note="the charging handle's knob"), rides="carrier")
wy, wz = pt(700, 318)
P.mark(G, "mag_well", [0.0, wy, wz], dict(READ, note="the well's mouth over the magazine"))
P.lips(G, [0.0, wy, wz - 0.3], dict(READ, note="the magazine's top"))
P.mark(G, "mag_lips", [0.0, wy, wz - 0.3], dict(READ, note="the magazine's top"), rides="magazine")
my, mz = pt(690, 465)
P.mark(G, "mag_grab", [2.0, my, mz], dict(READ, note="the magazine's left face near its base"), normal=[1.0, 0.0, 0.0], rides="magazine")
ry, rz = pt(570, 399)
P.mark(G, "release", [W_LO / 2 + 0.4, ry, rz], dict(READ, note="the release paddle"), normal=[1.0, 0.0, 0.0], rides="release")
ey, ez = pt(890, 168)
P.mark(G, "rear_sight", [0.0, ey, ez], dict(READ, note="the scope's eyepiece on its middle line"))
oy, oz = pt(1392, 168)
P.mark(G, "front_sight", [0.0, oy, oz], dict(READ, note="the scope's objective on its middle line"))
bp = store.load(G, "blueprint")
print(json.dumps({"parts": list(bp["parts"]), "length_cm": round(y_muz - pt(62, 260)[0], 2), "cm_per_px": round(cmpx, 5),
                  "barrel_fact_cm": fx["barrel_length"]["value"], "barrel_in_photo_cm": round(y_brake0, 2)}))
