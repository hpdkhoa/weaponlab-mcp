"""Benelli M4 Super 90 (the owner, 2026-10-24: "make another model for benelli m4"): its blueprint, a visual copy for
the game.

Outlines: read off the UK MoD photo of the L128A1 (the British Benelli M4; Steve Dock, OGL v3.0), its right side on a
floor, with pixel rulers. Scale: the length with the stock retracted, 889 mm, butt to muzzle (the photo's stock is
retracted: with the 1010 mm extended length the visible barrel alone would be longer than the 470 mm barrel). Bore:
the barrel's middle line. Breech face: the 470 mm barrel back from the muzzle. Widths: guesses with their reasons.
The EOTech sight is left off (the photo's crop cuts it, and it is an accessory)."""
import json

from weaponlab.blueprint import figures as F
from weaponlab.blueprint import plan as P
from weaponlab.blueprint import specs as S
from weaponlab.blueprint import store

G = "M4Super90"
FIG = "photo"
fx = S.facts(G)
BORE_REAR, BORE_FRONT = (2600.0, 200.0), (4800.0, 200.0)       # the barrel 145 to 255 px across at x 4150 and 4700, level
F.frame(G, FIG, list(BORE_REAR), list(BORE_FRONT), list(BORE_REAR))
F.calibrate(G, FIG, [165.0, 200.0], [4815.0, 200.0], fact="length_retracted")
f = F.figure(G, FIG)
cmpx = f["scale"]["cm_per_px"]
breech_x = 4815.0 - fx["barrel_length"]["value"] / cmpx
F.frame(G, FIG, list(BORE_REAR), list(BORE_FRONT), [breech_x, 200.0])
f = F.figure(G, FIG)
g = lambda pts: [[round(a, 3), round(b, 3)] for a, b in F.to_gun(f, pts)]      # noqa: E731
pt = lambda x, y: g([(x, y)])[0]                                                 # noqa: E731
READ = {"figure": FIG, "method": "read", "note": "points read off the photo with pixel rulers (50 px grid)"}


def guess(why):
    return {"guess": why}


P.new(G, "semi_tube", title="Benelli M4 Super 90 (M1014, L128A1), 12 gauge")
bp = store.load(G, "blueprint")
bp["parts"], bp["marks"], bp["mark_parts"] = {}, {}, {}
store.save(G, "blueprint", bp, strict=False)


def ext(pid, role, finish, px, w, wsrc, name, motion=None, msrc=None, bevel=0.06, holes=(), parent=None):
    P.extrude(G, pid, role, finish, None, [-w / 2.0, w / 2.0] if not isinstance(w, list) else w, wsrc, outline=g(px),
              outline_source=READ, name=name, motion=motion, motion_sources=msrc, bevel_cm=bevel, parent=parent)
    if holes:
        b_ = store.load(G, "blueprint")
        b_["parts"][pid].setdefault("holes", []).extend(holes)
        store.save(G, "blueprint", b_, strict=False)


W_RX = 3.2
ext("receiver", "body", "aluminium", [(1395, 250), (1595, 128), (2560, 128), (2560, 400), (1395, 400)], W_RX,
    guess("the receiver about 3.2 cm across: a 12 gauge shell's rim (2.27 cm) and its walls"), "Receiver",
    holes=[{"kind": "polygon", "outline": g([(2165, 145), (2555, 145), (2555, 255), (2165, 255)]), "x": [-W_RX / 2 - 0.1, -W_RX / 2 + 0.6],
            "source": dict(READ, note="the ejection port on the right, 0.6 cm deep (the bolt shows in it)")}])
ext("rail", "body", "aluminium", [(1630, 78), (2600, 78), (2600, 130), (1630, 130)], 2.12,
    {"derived": "MIL-STD-1913: the rail 0.835 in across its top"}, "Accessory rail")
ext("rear_sight", "body", "steel", [(1640, 130), (1650, 62), (1700, 32), (1760, 40), (1772, 130)], 2.0,
    guess("the ghost ring's wings about 2 cm across"), "Rear sight (ghost ring)", holes=[
        {"kind": "circle", "at": pt(1705, 80), "r": round(16 * cmpx, 3), "source": dict(READ, note="the ghost ring's aperture")}])
ext("trigger_group", "body", "polymer",
    [(1560, 398), (2060, 398), (2000, 455), (1950, 520), (1880, 545), (1690, 560), (1620, 540), (1600, 470), (1560, 440)], 2.6,
    guess("the trigger guard about 2.6 cm across"), "Trigger group and guard",
    holes=[{"kind": "polygon", "outline": g([(1660, 440), (1830, 440), (1840, 500), (1790, 522), (1682, 526)]), "source": dict(READ, note="the guard's opening")}])
ext("grip", "body", "polymer",
    [(1150, 430), (1390, 420), (1460, 440), (1440, 520), (1390, 700), (1365, 955), (1300, 965), (1160, 935), (1150, 880), (1160, 600), (1150, 500)], 3.0,
    guess("the pistol grip about 3 cm across"), "Pistol grip")
ext("stock", "body", "polymer",
    [(165, 330), (300, 310), (430, 296), (1205, 198), (1222, 228), (1090, 330), (1150, 430), (1050, 480), (350, 660), (300, 700),
     (300, 920), (195, 925), (165, 880)], 4.5, guess("the telescoping stock about 4.5 cm across at the butt pad"), "Telescoping buttstock")
ext("forend", "body", "polymer", [(2560, 205), (3530, 205), (3545, 250), (3545, 410), (3530, 455), (2560, 455)], 5.0,
    guess("the forend about 5 cm across round the magazine tube"), "Forend")
y_b0, y_mz = pt(2560, 200)[0], pt(4815, 200)[0]
P.lathe(G, "barrel", "body", "parkerized", [[0.0, 55.0 * cmpx], [y_mz, 55.0 * cmpx]], [0.0, 0.0],
        dict(READ, note="the barrel 145 to 255 px across (x 4150, 4700)"), {"derived": "on the bore, from the breech face"}, bore_r=0.92, name="Barrel")
z_tube = pt(4000, 345)[1]
P.lathe(G, "mag_tube", "body", "parkerized", [[pt(3530, 345)[0], 60 * cmpx], [pt(4600, 345)[0], 60 * cmpx]], [0.0, z_tube],
        dict(READ, note="the magazine tube 285 to 405 px across (x 4150)"), dict(READ, note="its middle line at 345 px"), name="Magazine tube")
P.lathe(G, "mag_cap", "body", "polymer", [[pt(4600, 345)[0], 82 * cmpx], [pt(4790, 345)[0], 82 * cmpx], [pt(4830, 345)[0], 62 * cmpx]],
        [0.0, z_tube], dict(READ, note="the knurled magazine cap 265 to 430 px across (x 4700)"), dict(READ, note="on the tube's line"), name="Magazine cap")
ext("barrel_band", "body", "parkerized", [(3615, 145), (3700, 145), (3700, 500), (3615, 500)], 3.6,
    guess("the barrel band about 3.6 cm across"), "Barrel band with sling loop")
ext("front_sight", "body", "steel", [(4560, 145), (4580, 60), (4625, 35), (4675, 60), (4690, 145)], 1.6,
    guess("the front sight's wings about 1.6 cm across"), "Front sight")
# the moving parts (the semi_tube action's)
ACT = {"derived": "the semi_tube action's part (Gun Kit)"}
ext("bolt", "bolt", "steel", [(2170, 150), (2550, 150), (2550, 250), (2170, 250)], 2.2,
    guess("the bolt inside the receiver, seen in the port"), "Bolt", motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": 9.5},
    msrc={"axis": ACT, "travel_cm": guess("a 12 gauge shell's 7 cm and its clearance: 9.5 cm")}, bevel=None)
P.extrude(G, "bolt_handle", "body", "steel", None, [-W_RX / 2 - 2.2, -W_RX / 2], guess("the bolt handle stands 2.2 cm off the right"),
          outline=g([(2420, 198), (2470, 198), (2470, 248), (2420, 248)]), outline_source=dict(READ, note="the bolt handle's knob"),
          name="Bolt handle (rides the bolt)", parent="bolt")
ext("release", "release", "steel", [(2425, 252), (2458, 252), (2458, 282), (2425, 282)], [-W_RX / 2 - 0.3, -W_RX / 2],
    guess("the bolt release button on the receiver's right"), "Bolt release",
    motion={"kind": "slide", "axis": [1.0, 0.0, 0.0], "travel_cm": 0.25}, msrc={"axis": ACT, "travel_cm": ACT}, bevel=None)
ext("trigger", "trigger", "steel", [(1705, 430), (1722, 430), (1745, 515), (1728, 518)], 0.6, guess("the trigger 0.6 cm across"),
    "Trigger", motion={"kind": "turn", "axis": [1.0, 0.0, 0.0], "turn_deg": 12.0, "pivot": [0.0] + pt(1712, 430)},
    msrc={"kind": ACT, "axis": guess("its pin across the group"), "pivot": dict(READ, note="the trigger's top"), "turn_deg": guess("about 12 degrees")}, bevel=None)
# marks
P.mark(G, "muzzle", [0.0, round(y_mz, 3), 0.0], {"fact": "length_retracted", "note": "the barrel's front on the bore"})
gy, gz = pt(1300, 700)
P.mark(G, "grip", [-1.5, gy, gz], dict(READ, note="the pistol grip's right face at its middle"), normal=[-1.0, 0.0, 0.0])
sy, sz = pt(3050, 455)
P.mark(G, "support", [0.0, sy, sz], dict(READ, note="under the forend, midway along it"), normal=[0.0, 0.0, -1.0])
ty, tz = pt(1730, 470)
P.mark(G, "trigger", [0.0, ty, tz], dict(READ, note="the trigger's face"))
hy, hz = pt(2445, 222)
P.mark(G, "handle", [-W_RX / 2 - 2.2, hy, hz], dict(READ, note="the bolt handle's knob"), rides="bolt")
py, pz = pt(2360, 200)
P.mark(G, "port", [-W_RX / 2, py, pz], dict(READ, note="the ejection port's middle"), normal=[-1.0, 0.0, 0.0])
ly, lz = pt(2300, 400)
P.mark(G, "load_port", [0.0, ly, lz], dict(READ, note="the loading port under the receiver, ahead of the guard"), normal=[0.0, 0.0, -1.0])
ry, rz = pt(2441, 267)
P.mark(G, "release", [-W_RX / 2 - 0.3, ry, rz], dict(READ, note="the bolt release button"), normal=[-1.0, 0.0, 0.0], rides="release")
ay, az = pt(1705, 80)
P.mark(G, "rear_sight", [0.0, ay, az], dict(READ, note="the ghost ring's aperture"))
fy, fz = pt(4625, 40)
P.mark(G, "front_sight", [0.0, fy, fz], dict(READ, note="the front sight post's tip"))
bp = store.load(G, "blueprint")
print(json.dumps({"parts": list(bp["parts"]), "cm_per_px": round(cmpx, 5), "breech_px": round(breech_x, 1),
                  "length_cm": round(y_mz - pt(165, 600)[0], 2)}))
