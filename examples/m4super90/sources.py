"""Benelli M4 (the owner, 2026-10-24: "make another model for benelli m4"): its public sources."""
import os
from weaponlab.blueprint import sources as S
M = r"K:\epic\ToangTown\ToangTown\Saved\Manuals"
G = "M4Super90"
S.add(G, os.path.join(M, "Benelli_M4_L128A1_photo_MoD", "L128A1_R004D172.jpg"), "mod-l128a1", "photo",
      "L128A1 Combat Shotgun (Benelli M4), right side, studio floor (UK MoD Defence Imagery R004D172)", "permission",
      credit="Steve Dock / UK Ministry of Defence, Open Government Licence v3.0 (Wikimedia Commons)",
      url="https://commons.wikimedia.org/wiki/File:L128A1_Combat_Shotgun_(Benelli_M4)_R004D172.jpg",
      gun_title="Benelli M4 Super 90 (M1014, L128A1), 12 gauge")
# (the USMC operator manual TM 10698A-10/1 was downloaded, found marked "distribution limited to U.S. Government agencies
# only / for official use only", and deleted unread: not a source)
from weaponlab.blueprint import specs as F
from weaponlab.blueprint import figures as FG
W = os.path.join(M, "Benelli_M4_L128A1_photo_MoD", "benelli_m4_wikipedia.txt")
open(W, "w", encoding="utf-8").write("Benelli M4 (Wikipedia infobox, read 2026-10-24): Length 889 mm (35.0 in) (stock retracted); 1,010 mm (40 in) (stock extended). Barrel length 470 mm (18.5 in). Mass 3.82 kg (8.42 lb). Feed: 5+1 (civilian) or 7+1 (Military, LE) tubular magazine.\n")
S.add(G, W, "wiki-benelli-m4", "web", "Benelli M4, Wikipedia (infobox)", "cc-by-sa", credit="Wikipedia contributors, CC BY-SA 4.0",
      url="https://en.wikipedia.org/wiki/Benelli_M4")
F.add(G, "length_retracted", 889, "mm", "wiki-benelli-m4", 1, "Length 889 mm (35.0 in) (stock retracted)", about="the photo shows the stock retracted")
F.add(G, "barrel_length", 470, "mm", "wiki-benelli-m4", 1, "Barrel length 470 mm (18.5 in)")
F.add(G, "weight_empty", 3.82, "kg", "wiki-benelli-m4", 1, "Mass 3.82 kg (8.42 lb)")
r = FG.add(G, "photo", "mod-l128a1", 1, "photo", shows="right", crop=[0.0, 0.25, 1.0, 0.80], dpi=300,
           caption="L128A1 (Benelli M4), right side (UK MoD, OGL v3.0)")
print(r["size_px"], r["image"])
