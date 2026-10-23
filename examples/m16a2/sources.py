"""M16A2 (the owner's "AR-15", 2026-10-24: "M16A2/A4 rifle style"): its public sources, registered with their
licences. A visual copy for the game only: no receiver machining drawings are used."""
import os
from weaponlab.blueprint import sources as S

M = r"K:\epic\ToangTown\ToangTown\Saved\Manuals"
G = "M16A2"
T = "Rifle, 5.56 mm, M16A2 (M16A4 as a flat-top variant)"
A = "DISTRIBUTION STATEMENT A. Approved for public release; distribution is unlimited."
S.add(G, os.path.join(M, "TM_9-1005-319-23P_M16A2_1991", "Army M16A2 and M4 manual.pdf"), "tm9-1005-319-23p-1991", "manual",
      "TM 9-1005-319-23&P: Unit Maintenance Manual (Including Repair Parts and Special Tools List) for Rifle, 5.56 mm, "
      "M16A2, Carbine M4 and M4A1", "us-government-work", publisher="Department of the Army", year=1991,
      url="https://archive.org/details/a2-m4-m4a1-technical", distribution="Approved for public release; distribution is unlimited.",
      gun_title=T)
S.add(G, os.path.join(M, "MIL-R-63997B_M16A2_1997", "MIL-R-63997B_(AR).pdf"), "mil-r-63997b", "manual",
      "MIL-R-63997B(AR) Military Specification, Rifle, 5.56 mm: M16A2 (12 Dec 1986, amendments to 1997)",
      "us-government-work", publisher="U.S. Army Armament, Munitions and Chemical Command", year=1986,
      url="https://archive.org/details/mil-r-63997-b-ar", distribution=A)
S.add(G, os.path.join(M, "DTIC_ADA168577_M16A2_1986", "DTIC_ADA168577.pdf"), "dtic-ada168577", "book",
      "DTIC ADA168577: Analysis of M16A2 Rifle Characteristics and Recommended Improvements (Feb 1986)",
      "us-government-work", publisher="U.S. Army Research Institute", year=1986,
      url="https://archive.org/details/DTIC_ADA168577", distribution="Approved for public release; distribution unlimited.")
S.add(G, os.path.join(M, "TC_3-22.9_2016", "TC 3-22.9 Rifle And Carbine  2016.pdf"), "tc3-22.9-2016", "manual",
      "TC 3-22.9 Rifle and Carbine (May 2016)", "us-government-work", publisher="Department of the Army", year=2016,
      url="https://archive.org/details/tc-3-22.9-rifle-and-carbine-2016")
S.add(G, os.path.join(M, "TM_9-1005-249-10_M16A1", "tm_9-1005-249-10_-_operators_manual_for_m16_m16a1.pdf"),
      "tm9-1005-249-10", "manual", "TM 9-1005-249-10 Operator's Manual, M16 and M16A1 Rifle", "us-government-work",
      publisher="Department of the Army", url="https://archive.org/details/milmanual-tm-9-1005-249-10---operators-manual-for-m16-m16a1")
for s in ("tm9-1005-319-23p-1991", "mil-r-63997b", "dtic-ada168577"):
    r = S.scan(G, s)
    print(s, {k: (len(v) if isinstance(v, list) else v) for k, v in r.items()} if isinstance(r, dict) else r)
