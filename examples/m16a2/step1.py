"""M16A2 step 1: the printed facts and the side-view figure (TM 9-1005-319-23&P, 1991)."""
import json
from weaponlab.blueprint import figures as F
from weaponlab.blueprint import specs as S
from weaponlab.blueprint import trace as T

G = "M16A2"
TM = "tm9-1005-319-23p-1991"
Q = "1-10. EQUIPMENT DATA."
S.add(G, "overall_length", 39.63, "in", TM, 27, Q + " Length: Rifle with compensator ... 39.63 in 100.66 cm", about="tip to tip along the bore, with the compensator")
S.add(G, "barrel_length", 20.0, "in", TM, 27, Q + " Barrel (Rifle) ... 20 in 50.8 cm")
S.add(G, "barrel_with_compensator", 21.0, "in", TM, 27, Q + " Barrel with compensator (Rifle) ... 21 in 53.34 cm")
S.add(G, "weight_empty", 7.5, "lb", TM, 27, Q + " Rifle, M16A2 without magazine and sling ... 7 lb 8 oz 3.40 kg")
S.add(G, "magazine_empty_weight", 4.0, "oz", TM, 27, Q + " Empty magazine ... 4 oz 0.11 kg")
S.add(G, "magazine_loaded_weight", 17.0, "oz", TM, 27, Q + " Loaded magazine ... 1 lb 1 oz 0.48 kg")
r = F.add(G, "tm-right", TM, 20, "side", shows="right", crop=[0.22, 0.17, 0.80, 0.42], dpi=400,
          caption="EXTERNAL VIEW OF 5.56 MM RIFLE M16A2, RIGHT SIDE (page 1-0)")
print(json.dumps(r["size_px"]), r["image"])
r = F.add(G, "tm-left", TM, 20, "side", shows="left", crop=[0.06, 0.55, 0.80, 0.80], dpi=400,
          caption="EXTERNAL VIEW OF 5.56 MM RIFLE M16A2, LEFT SIDE (page 1-0)")
print(json.dumps(r["size_px"]), r["image"])
