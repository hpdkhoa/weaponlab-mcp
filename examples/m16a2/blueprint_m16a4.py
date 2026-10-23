"""M16A4: the M16A2 without its carry handle (the owner, 2026-10-24: "finish M16A2 then make another without the
carrying handle"). The flat-top upper carries a MIL-STD-1913 rail where the handle sat; everything else is the
M16A2's blueprint (TM 9-1005-319-23&P, 1991), and the M16A4 is the flat-top M16A2 (TC 3-22.9, 2016, table 2-1:
the M16A4 a 20 in barrel, a full buttstock).

Rail: MIL-STD-1913 (Dimensioning of accessory mounting rail for small arms weapons, 1995): slots 0.206 in wide at
0.394 in centres, the rail 0.835 in across its top. Those three numbers are from the standard by name (it is not
on this disk); the rail's height over the receiver is a guess."""
import copy
import json

from weaponlab.blueprint import plan as P
from weaponlab.blueprint import store

SRC, G = "M16A2", "M16A4"
bp = copy.deepcopy(store.load(SRC, "blueprint"))
bp["name"] = G
bp["title"] = "Rifle, 5.56 mm, M16A4 (the M16A2 with a flat-top upper)"
bp["sources"] = str(store.folder(SRC, "model").parent / "sources.json")
del bp["parts"]["carry_handle"]
up = bp["parts"]["upper"]["shape"]["outline"]
top = max(p[1] for p in up)
y0 = min(p[0] for p in up if p[1] > top - 0.6)
y1 = max(p[0] for p in up if p[1] > top - 0.6)
IN = 2.54
W = 0.835 * IN
H = 0.95                                              # guess: the rail's top 0.95 cm over the receiver's top
rail = [[y0, top - 0.05], [y1, top - 0.05], [y1, top + H], [y0, top + H]]
MIL = {"derived": "MIL-STD-1913: the rail 0.835 in across its top; slots 0.206 in wide at 0.394 in centres"}
bp["parts"]["rail"] = {"role": "body", "finish": "aluminium", "name": "Flat-top rail (MIL-STD-1913)",
                       "shape": {"kind": "extrude", "outline": rail, "x": [-W / 2, W / 2]},
                       "sources": {"outline": {"guess": "the rail along the upper's flat top, front to back, 0.95 cm high"}, "x": MIL,
                                   "bevel_cm": {"guess": "a small round on the rail's edges, as machined parts have"}},
                       "bevel_cm": 0.03,
                       "features": [{"kind": "grooves", "face": "top", "y": [y0 + 0.4, y1 - 0.4],
                                     "count": max(1, int((y1 - y0 - 0.8) / (0.394 * IN))), "width_cm": round(0.206 * IN, 3),
                                     "depth_cm": 0.3, "source": MIL}]}
# the sight line: the A2's rear aperture height kept (a back-up rear sight on the rail co-witnesses the front post)
rs = bp["marks"]["rear_sight"]
rs["source"] = {"guess": "a back-up rear sight on the rail's rear at the A2 aperture's height, so the front post's line stays"}
store.save(G, "blueprint", bp, strict=False)
print(json.dumps({"parts": list(bp["parts"]), "rail_y": [round(y0, 2), round(y1, 2)], "rail_slots": bp["parts"]["rail"]["features"][0]["count"]}))
