"""M16A2 step 2: the right-side figure cleaned of its sling and label arrows (white painted over them, along
lines and regions read off the figure with pixel rulers), then its silhouette traced, scaled by the overall length
and framed on the bore."""
import json
import cv2
from weaponlab.blueprint import figures as F
from weaponlab.blueprint import trace as T
from weaponlab.blueprint import store

G = "M16A2"
TM = "tm9-1005-319-23p-1991"
r = F.add(G, "tm-right-clean", TM, 20, "side", shows="right", crop=[0.22, 0.17, 0.80, 0.42], dpi=400,
          caption="EXTERNAL VIEW OF 5.56 MM RIFLE M16A2, RIGHT SIDE (page 1-0), the sling and the label arrows painted out",
          note="painted out: below the buttstock's lower line (x < 520 px), under the magazine and grip (y > 640 px, "
               "x 520-950), under the handguard (y > 350 px, x 950-1500), under the front sight and barrel (y > 303 px, "
               "x > 1500); the three label arrows along their own lines")
img = cv2.imread(r["image"])
W = (255, 255, 255)
import numpy as np
for poly in ([(0, 525), (125, 520), (520, 375), (520, 1100), (0, 1100)],
             [(520, 640), (950, 640), (950, 1100), (520, 1100)],
             [(950, 350), (1500, 350), (1500, 1100), (950, 1100)],
             [(1500, 303), (1972, 303), (1972, 1100), (1500, 1100)]):
    cv2.fillPoly(img, [np.array(poly, dtype=np.int32)], W)
for a, b in (((520, 0), (640, 128)), ((1440, 0), (1238, 192)), ((500, 945), (722, 465))):
    cv2.line(img, a, b, W, 11)
cv2.imwrite(r["image"], img)
res = T.silhouette(G, "tm-right-clean", close_px=7, eps_px=1.5)
print(res["points"], res["picture"])
T.save(G, "right_outline", res)
