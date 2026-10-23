"""Barrett M82A2 (the owner, 2026-10-24: "then make barrett m82a2"): its public sources."""
import os
from weaponlab.blueprint import sources as S
from weaponlab.blueprint import specs as F

M = r"K:\epic\ToangTown\ToangTown\Saved\Manuals"
G = "M82A2"
S.add(G, os.path.join(M, "Barrett_M82A2_photo_Commons", "M82A2.JPG"), "commons-m82a2", "photo",
      "One of ten M82A2s in civilian hands (photo, right side)", "cc-by-sa", credit="Tomketchum, Wikimedia Commons, CC BY-SA 3.0",
      url="https://commons.wikimedia.org/wiki/File:M82A2.JPG", gun_title="Barrett M82A2 (.50 BMG, bullpup)")
S.add(G, os.path.join(M, "US4677897_Barrett_1987", "US4677897.pdf"), "us4677897", "patent",
      "US 4,677,897 Anti-armor gun (R. G. Barrett, filed 1983, granted 1987): the M82's recoiling barrel and bolt carrier",
      "us-patent", year=1987, url="https://patents.google.com/patent/US4677897A/en")
# web references for scale (no Army manual for the M82A2 is public)
WIKI50 = os.path.join(M, "Barrett_M82A2_photo_Commons", "50BMG_wikipedia.txt")
open(WIKI50, "w", encoding="utf-8").write(".50 BMG (Wikipedia infobox, read 2026-10-24): case length 3.910 in (99.31 mm); overall length 5.450 in (138.43 mm); bullet diameter 0.511 in; rim diameter 0.804 in.\n")
S.add(G, WIKI50, "wiki-50bmg", "web", ".50 BMG, Wikipedia (infobox dimensions)", "cc-by-sa",
      credit="Wikipedia contributors, CC BY-SA 4.0", url="https://en.wikipedia.org/wiki/.50_BMG")
MF = os.path.join(M, "Barrett_M82A2_photo_Commons", "modernfirearms_m82.txt")
open(MF, "w", encoding="utf-8").write("Barrett M82 (modernfirearms.net, read 2026-10-24), specifications table: Overall Length 1448 mm; Barrel Length 737 mm. "
                                       "Text: 'The M82A2 differed from M82A1 mostly in that the pistol grip along with trigger had been placed ahead of the magazine'.\n")
S.add(G, MF, "modernfirearms-m82", "web", "Barrett M82, Modern Firearms (M. Popenker)", "permission",
      credit="modernfirearms.net (quoted facts only)", url="https://modernfirearms.net/en/sniper-rifles/large-caliber-rifles/u-s-a-large-caliber-rifles/barrett-m82-eng/")
F.add(G, "cartridge_length", 5.450, "in", "wiki-50bmg", 1, "Overall length 5.450 in (138.43 mm)", about="the .50 BMG cartridge lying beside the rifle in the photo")
F.add(G, "barrel_length", 737, "mm", "modernfirearms-m82", 1, "Barrel Length: 737 mm", about="the M82 family's barrel; a check on the photo's scale")
from weaponlab.blueprint import figures as FG
r = FG.add(G, "photo", "commons-m82a2", 1, "photo", shows="left", crop=[0.0, 0.33, 1.0, 0.72], dpi=300,
           caption="Barrett M82A2, left side, with a .50 BMG cartridge on the floor (Tomketchum, CC BY-SA 3.0)")
print(r["size_px"], r["image"])
