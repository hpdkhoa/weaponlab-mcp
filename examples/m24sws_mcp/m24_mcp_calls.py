"""The M24 SWS built from nothing through MCP calls only (the owner, 2026-10-24: "check if another run mcp in another
environment can start the flow to end result"). Writes the calls as JSON for client.py. Numbers in cm come from the
calibrate and frame answers (0.054469 cm a px, the bore through (1550, 147.5) and (2040, 146), the breech at 930 px),
as another session would turn its pixel readings into gun space."""
import json
import math

G = "M24MCP"
M = r"K:\epic\ToangTown\ToangTown\Saved\Manuals\M24_SWS"
CMPX = 0.054469
O = (930.01, 149.4)                       # the breech on the bore
D = (490.0, -1.5)
L = math.hypot(*D)
D = (D[0] / L, D[1] / L)
N = (D[1], -D[0])                         # up in the image (y down)


def cm(x, y):
    dx, dy = x - O[0], y - O[1]
    return [round((dx * D[0] + dy * D[1]) * CMPX, 3), round((dx * N[0] + dy * N[1]) * CMPX, 3)]


Y = lambda x: cm(x, 147.0)[0]            # noqa: E731
Z = lambda y: cm(1500.0, y)[1]            # noqa: E731
R = lambda px: round(px * CMPX, 3)        # noqa: E731
rd = lambda note: {"figure": "usaf-right", "method": "read", "note": note}          # noqa: E731
guess = lambda why: {"guess": why}                                                  # noqa: E731
C = []


def call(tool, **args):
    C.append([tool, dict({"gun": G}, **args)])


# sources, facts, figures
call("blueprint_source_add", file=M + r"\M24_USAF.jpg", source_id="usaf-m24", kind="photo", title="M24 Rifle, right side, studio (US Air Force photo)",
     license_basis="us-government-work", credit="US Air Force, public domain (Wikimedia Commons)", gun_title="M24 Sniper Weapon System (MCP-built)")
call("blueprint_source_add", file=M + r"\FM23-10_1994.pdf", source_id="fm23-10", kind="manual", title="FM 23-10 Sniper Training (1994)",
     license_basis="us-government-work", year=1994)
call("blueprint_source_add", file=M + r"\m24_wikipedia.txt", source_id="wiki-m24", kind="web", title="M24 SWS, Wikipedia", license_basis="cc-by-sa",
     credit="Wikipedia contributors, CC BY-SA 4.0")
call("blueprint_source_add", file=M + r"\hs_specs\opplanet-h-s-precision-psl134-spec-sheet-pdf.pdf", source_id="hs-psl134", kind="web",
     title="H-S Precision PSL134 stock spec sheet (a sibling of the M24's PST-024)", license_basis="facts-only",
     credit="H-S Precision; printed widths and the forend shape measured, nothing copied")
for fid, v, u, src, q in (("overall_length", 43, "in", "usaf-m24", "Length: 43 in."), ("barrel_length", 610, "mm", "wiki-m24", "Barrel length: 610 mm (24 in)"),
                          ("eye_relief_min", 2, "in", "fm23-10", "AN AVERAGE DISTANCE OF 2 TO 3 INCHES BETWEEN THE EYE AND THE SCOPE"),
                          ("eye_relief_max", 3, "in", "fm23-10", "The average distance is 2 to 3 inches.")):
    call("blueprint_fact_add", fact_id=fid, value=v, unit=u, source_id=src, page=40 if src == "fm23-10" else 1, quote=q)
call("blueprint_figure_add", figure_id="usaf-right", source_id="usaf-m24", page=1, kind="photo", shows="right")
call("blueprint_figure_add", figure_id="hs-forend", source_id="hs-psl134", page=1, kind="section", shows="right", crop=[0.52, 0.56, 0.735, 0.675])
call("blueprint_frame", figure_id="usaf-right", bore_rear=[1550, 147.5], bore_front=[2040, 146], origin=[930, 147])
call("blueprint_calibrate", figure_id="usaf-right", a=[50, 290], b=[2050, 146], fact="overall_length")
call("blueprint_new", action="bolt_stripper", title="M24 SWS (built through MCP only)")
# the stock: a loft through the H-S forend shape (traced by the follower), an oval wrist and a rounded-box butt
call("blueprint_trace", figure_id="hs-forend", method="follow", keep_as="forend_shape", radius_px=10,
     rough=[[112, 35], [145, 35], [150, 55], [165, 85], [190, 110], [220, 128], [245, 132], [270, 128], [300, 112], [325, 90], [340, 60], [348, 35],
            [382, 35], [388, 60], [398, 100], [420, 150], [445, 190], [452, 240], [440, 285], [410, 320], [360, 343], [300, 353], [245, 355],
            [190, 352], [130, 342], [85, 322], [55, 290], [42, 240], [50, 190], [75, 150], [98, 100], [106, 60]])
STOCK = [[175, 180], [180, 177], [490, 177], [503, 183], [518, 195], [552, 197], [600, 182], [650, 165], [705, 157], [950, 154], [1000, 145], [1520, 145],
         [1532, 152], [1537, 170], [1537, 200], [1530, 214], [1515, 220], [1000, 230], [930, 233], [750, 246], [645, 251], [605, 262], [580, 290],
         [565, 320], [553, 346], [540, 349], [510, 342], [480, 331], [450, 322], [300, 351], [186, 381], [178, 377], [175, 360]]
IN = 2.54
PLAN = [(175, 1.98), (490, 1.98), (545, 1.78), (600, 1.59), (650, 1.59), (720, 2.16), (1030, 2.27), (1500, 2.0), (1525, 1.8), (1537, 1.1)]
top = [[Y(x), round(w * IN / 2, 3)] for x, w in PLAN] + [[Y(x), -round(w * IN / 2, 3)] for x, w in reversed(PLAN)]
OVAL = [[round(math.cos(2 * math.pi * k / 48), 4), round(math.sin(2 * math.pi * k / 48), 4)] for k in range(48)]
BOX = []
for cx, cz, a0 in ((0.45, -0.45, -90), (0.45, 0.45, 0), (-0.45, 0.45, 90), (-0.45, -0.45, 180)):
    BOX += [[round(cx + 0.55 * math.cos(math.radians(a0 + 90 * k / 8)), 4), round(cz + 0.55 * math.sin(math.radians(a0 + 90 * k / 8)), 4)] for k in range(9)]
call("blueprint_loft", part_id="stock", role="body", finish="polymer", side_px=STOCK, figure_id="usaf-right", top=top,
     sections=[{"y": Y(300), "outline": BOX}, {"y": Y(470), "outline": BOX}, {"y": Y(600), "outline": OVAL}, {"y": Y(760), "trace": "forend_shape"},
               {"y": Y(1500), "trace": "forend_shape"}],
     top_source={"derived": "the H-S Precision PSL134 sheet: body 1.98 in, grip 1.59 in, forend 2.27 in widest and 2 in at the tip"},
     sections_source={"derived": "the PSL134 sheet's forend shape (kept trace forend_shape); the wrist an oval and the butt a rounded box (guesses)"},
     name="Stock (H-S Precision PST-024)")
call("blueprint_round_corners", part_id="stock", radius_cm=0.5, source=guess("a moulded composite stock's corners about 0.5 cm round"))
call("blueprint_feature", part_id="stock", feature={"kind": "texture", "pattern": "stippling", "face": "all", "pitch_cm": 0.1,
                                                     "source": rd("the stock's textured finish, its grain about 1 mm")})
# the butt plate
call("blueprint_part", part_id="butt_plate", role="body", finish="rubber", kind="extrude", x=[-2.3, 2.3], x_source=guess("the butt plate 4.6 cm across"),
     outline_px=[[52, 196], [58, 185], [70, 182], [92, 182], [100, 188], [102, 200], [102, 383], [98, 394], [88, 398], [66, 398], [56, 392], [51, 380], [50, 214]],
     figure_id="usaf-right", outline_note="the butt plate (50 to 102 px)", name="Butt plate")
call("blueprint_round_corners", part_id="butt_plate", radius_cm=0.6, source=guess("a rubber pad's corners about 0.6 cm round"))
call("blueprint_shape_across", part_id="butt_plate", section="rr", radius_cm=1.0, source=guess("the pad rounded across"))
for pid, (ya, yb) in (("lop_rod_top", (202, 220)), ("lop_rod_bottom", (312, 330))):
    call("blueprint_part", part_id=pid, role="body", finish="steel", kind="lathe", profile=[[Y(100), R((yb - ya) / 2)], [Y(178), R((yb - ya) / 2)]],
         axis=[0.0, Z((ya + yb) / 2)], profile_source=rd("a length-of-pull rod (%d to %d px)" % (ya, yb)), axis_source=rd("its middle line"), name="Length-of-pull rod")
call("blueprint_part", part_id="lop_wheel", role="body", finish="parkerized", kind="lathe", profile=[[Y(143), R(30)], [Y(146), R(42.5)], [Y(169), R(42.5)], [Y(172), R(30)]],
     axis=[0.0, Z(267.5)], profile_source=rd("the thumbwheel (143 to 172 px, 225 to 310 px)"), axis_source=rd("its middle line"), name="Length-of-pull wheel")
# the action
RSIDE = [[722, 121], [725, 118], [729, 117], [1025, 117], [1029, 118.5], [1030, 121], [1030, 173], [1029, 175.5], [1025, 177], [729, 177], [725, 176], [722, 173]]
rtop = [[cm(x, y)[0], -(cm(x, y)[1] - Z(147))] for x, y in RSIDE]
call("blueprint_loft", part_id="receiver", role="body", finish="blued", side_px=RSIDE, figure_id="usaf-right", top=rtop,
     sections=[{"y": Y(705), "outline": OVAL}, {"y": Y(1030), "outline": OVAL}], top_source={"derived": "round: its plan the same as its side"},
     sections_source={"derived": "a Remington 700 receiver is round"}, name="Receiver (Remington 700 long action)")
call("blueprint_trace", figure_id="usaf-right", method="follow", keep_as="port", rough=[[787, 132], [935, 132], [935, 157], [787, 157]], radius_px=3)
call("blueprint_hole", part_id="receiver", trace="port", x=[-R(30) - 0.1, -0.2], source=rd("the ejection port on the right (787 to 935 px)"))
call("blueprint_part", part_id="bolt", role="bolt", finish="steel", kind="extrude", x=[-0.9, 0.9], x_source=guess("a Remington 700 bolt 0.697 in across"),
     outline_px=[[650, 137], [656, 133], [705, 133], [705, 131], [933, 131], [933, 163], [705, 163], [705, 157], [656, 157], [650, 153]],
     figure_id="usaf-right", outline_note="the bolt shroud (650 to 705 px) and body to the breech", name="Bolt",
     motion={"kind": "slide", "axis": [0.0, -1.0, 0.0], "travel_cm": 11.0},
     motion_sources={"axis": {"derived": "drawn back along the bore"}, "travel_cm": guess("11 cm, a long action's bolt throw")})
call("blueprint_shape_across", part_id="bolt", section="oval", source=guess("a bolt is round"))
TURN = {"kind": "turn", "axis": [0.0, 1.0, 0.0], "turn_deg": 60.0, "pivot": [0.0, Y(711), 0.0]}
TSRC = {"axis": {"derived": "the bolt turns round the bore"}, "pivot": {"derived": "on the bore at the handle's root"},
        "turn_deg": guess("about 60 degrees on a Remington 700")}
call("blueprint_part", part_id="bolt_handle", role="bolt_lift", finish="blued", kind="extrude", x=[-6.2, -1.0], x_source=guess("the handle stands out to its knob"),
     outline_px=[[700, 128], [722, 132], [714, 175], [706, 200], [692, 200], [697, 140]], figure_id="usaf-right",
     outline_note="the bolt handle (692 to 722 px, 128 to 200 px)", name="Bolt handle", motion=TURN, motion_sources=TSRC, parent="bolt", bevel_cm=0.1)
call("blueprint_views", part_id="bolt_handle", front=[{"y": [Y(660), Y(725)], "outline": [[-0.977, -0.125], [-5.337, -2.773], [-4.922, -3.456], [-0.562, -0.809]]}],
     front_source=guess("seen from the front the handle sweeps out and down to its knob"))
KNOB = [[686 + 17 * math.cos(2 * math.pi * k / 40), 210 + 17 * math.sin(2 * math.pi * k / 40)] for k in range(40)]
KR, ky, kz = R(17), Y(686), Z(210)
call("blueprint_part", part_id="bolt_knob", role="bolt_lift", finish="blued", kind="extrude", x=[round(-5.6 - KR, 3), round(-5.6 + KR, 3)],
     x_source=guess("the knob a ball"), outline_px=KNOB, figure_id="usaf-right", outline_note="the knob, a circle 34 px across round (686, 210 px)",
     name="Bolt knob", motion=TURN, motion_sources={"axis": {"derived": "the handle's"}, "pivot": {"derived": "the handle's"}, "turn_deg": {"derived": "the handle's"}},
     parent="bolt")
call("blueprint_views", part_id="bolt_knob",
     front=[{"y": [ky - KR - 0.1, ky + KR + 0.1], "outline": [[round(-5.6 + KR * math.cos(2 * math.pi * k / 40), 4), round(kz + KR * math.sin(2 * math.pi * k / 40), 4)] for k in range(40)]}],
     front_source=guess("a ball seen from the front is a circle"),
     top=[[round(ky + KR * math.cos(2 * math.pi * k / 40), 4), round(-5.6 + KR * math.sin(2 * math.pi * k / 40), 4)] for k in range(40)],
     top_source=guess("a ball seen from above is a circle"))
call("blueprint_part", part_id="bottom_metal", role="body", finish="aluminium", kind="extrude", x=[-0.5, 0.5], x_source=guess("the guard's bow 1 cm across"),
     outline_px=[[640, 243], [752, 243], [752, 262], [745, 285], [728, 298], [690, 302], [660, 297], [648, 285], [643, 262]], figure_id="usaf-right",
     outline_note="the trigger guard (640 to 752 px)", name="Trigger guard")
call("blueprint_trace", figure_id="usaf-right", method="follow", keep_as="guard_hole", rough=[[658, 255], [735, 255], [735, 272], [722, 288], [690, 292], [668, 287], [660, 275]], radius_px=3)
call("blueprint_hole", part_id="bottom_metal", trace="guard_hole", source=rd("the guard's opening"))
call("blueprint_round_corners", part_id="bottom_metal", radius_cm=0.3, source=guess("a machined guard's corners about 0.3 cm round"))
call("blueprint_shape_across", part_id="bottom_metal", section="rr", radius_cm=0.5, source=guess("the guard's bow rounded across"))
call("blueprint_part", part_id="trigger", role="trigger", finish="steel", kind="extrude", x=[-0.3, 0.3], x_source=guess("the trigger 0.6 cm across"),
     outline_px=[[668, 255], [678, 255], [690, 296], [683, 299], [671, 280]], figure_id="usaf-right", outline_note="the trigger", name="Trigger",
     motion={"kind": "turn", "axis": [1.0, 0.0, 0.0], "turn_deg": 10.0, "pivot": [0.0] + cm(672, 252)},
     motion_sources={"axis": {"derived": "its pin across"}, "pivot": rd("the trigger's top"), "turn_deg": guess("about 10 degrees")})
# the barrel, the scope, its rings and bases
call("blueprint_part", part_id="barrel", role="body", finish="blued", kind="lathe",
     profile=[[0.0, 1.35], [Y(1030), 1.55], [Y(1100), 1.5], [Y(1550), R(22.5)], [Y(2040), R(19.0)], [Y(2050), R(17.5)]], axis=[0.0, 0.0], bore_r=0.381,
     profile_source=rd("the barrel 45 px across at 1550 px and 38 px at 2040 px; its shank a guess"), axis_source={"derived": "on the bore"}, name="Barrel")
SC = [[590, 43], [594, 45], [632, 45], [650, 37], [700, 30], [720, 25], [1000, 25], [1050, 30], [1100, 37], [1160, 43], [1165, 46.5], [1218, 46.5], [1220, 44]]
call("blueprint_part", part_id="scope", role="body", finish="parkerized", kind="lathe", profile=[[Y(x), R(r)] for x, r in SC], axis=[0.0, Z(75)],
     profile_source=rd("the scope: eyepiece, a 30 mm tube, the 42 mm objective's bell"), axis_source=rd("its middle line at 75 px"), name="Scope (Leupold Ultra M3A)")
call("blueprint_hole", part_id="scope", bore={"at": [0.0, Z(75)], "r": R(40), "y": [Y(1212), Y(1225)]}, source=rd("the objective lens set back in its bell"))
for pid, (xa, xb) in (("ring_rear", (757, 790)), ("ring_front", (967, 995))):
    call("blueprint_part", part_id=pid, role="body", finish="steel", kind="lathe", profile=[[Y(xa), R(30)], [Y(xb), R(30)]], axis=[0.0, Z(75)],
         profile_source=rd("a scope ring (%d to %d px)" % (xa, xb)), axis_source=rd("on the scope's line"), name="Scope ring")
for pid, (xa, xb) in (("base_rear", (724, 790)), ("base_front", (938, 1030))):
    call("blueprint_part", part_id=pid, role="body", finish="blued", kind="extrude", x=[-0.7, 0.7], x_source=guess("a base 1.4 cm across"),
         outline_px=[[xa, 104], [xb, 104], [xb, 122], [xa, 122]], figure_id="usaf-right", outline_note="a scope base (%d to %d px)" % (xa, xb), name="Scope base")
    call("blueprint_round_corners", part_id=pid, radius_cm=0.15, source=guess("a machined base's corners about 0.15 cm round"))
    call("blueprint_bevel", part_id=pid, bevel_cm=0.12, source=guess("a machined part's edges broken about 0.12 cm"))
# the marks the bolt action needs
for name, x, y, sx, note, normal, rides in (("grip", -1.5, None, (598, 275), "the pistol grip's right face", [-1.0, 0.0, 0.0], None),
                                            ("support", 0.0, None, (1300, 226), "under the forend", [0.0, 0.0, -1.0], None),
                                            ("muzzle", 0.0, None, (2050, 147), "the muzzle", None, None),
                                            ("trigger", 0.0, None, (680, 270), "the trigger's face", None, None),
                                            ("port", -R(30), None, (861, 145), "the ejection port's middle", [-1.0, 0.0, 0.0], None),
                                            ("knob", -5.6, None, (686, 210), "the bolt knob", [-1.0, 0.0, 0.0], ["bolt_knob", "bolt"]),
                                            ("charger", -0.6, None, (861, 132), "the open port's top, where rounds go down (FM 23-10)", [0.0, 0.0, 1.0], None),
                                            ("rear_sight", 0.0, None, (590, 75), "the scope's eyepiece", None, None),
                                            ("front_sight", 0.0, None, (1218, 75), "the scope's objective", None, None)):
    yy, zz = cm(*sx)
    if name == "muzzle":
        zz = 0.0
    args = {"name": name, "at": [x, yy, zz], "source": rd(note + " (%d, %d px)" % sx)}
    if normal:
        args["normal"] = normal
    if rides:
        args["rides"] = rides
    call("blueprint_mark", **args)
call("blueprint_check")
call("blueprint_build", render=True, segments=64)
call("blueprint_render", look="material")
call("blueprint_to_gunkit")
print(json.dumps(C))
