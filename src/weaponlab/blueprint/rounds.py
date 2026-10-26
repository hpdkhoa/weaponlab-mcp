"""The round a gun chambers, as a turned profile in gun cm (y forward from the breech face, r off the bore), from
the cartridge's published dimensions (SAAMI and CIP drawings, inches and millimetres as printed). The chamber check
and the showcase draw it; Gun Kit's rig carries it as a mesh the game can show or hide (the owner, 2026-10-26: "two
variants: with bullet and without bullet").

Each cartridge: the rim's diameter and thickness, the base and shoulder diameters, the shoulder's and the neck's
place, the neck's diameter, the case length, the overall length and the bullet's diameter. The profile runs from the
rim at y 0 to the bullet's tip; the case ends at case_length."""
import json
import math

from . import store

IN = 2.54
# dimensions in mm (SAAMI drawings, as printed; the shotshell from the SAAMI shotshell drawing, a crimped 2 3/4 in hull)
CARTRIDGES = {
    "45acp": {"name": ".45 ACP ball", "rim_d": 12.19, "rim_t": 1.24, "base_d": 12.09, "shoulder_y": None, "neck_d": 12.01, "case_l": 22.81,
              "bullet_d": 11.48, "oal": 32.39, "source": "SAAMI Z299.3, .45 Automatic: rim .480 in, base .476, neck .473, case .898, OAL 1.275"},
    "5.56x45": {"name": "5.56x45 mm NATO ball", "rim_d": 9.60, "rim_t": 1.14, "base_d": 9.58, "shoulder_d": 9.00, "shoulder_y": 36.52, "neck_d": 6.43,
                "case_l": 44.70, "bullet_d": 5.70, "oal": 57.40, "source": "SAAMI Z299.4, 223 Remington / 5.56 NATO (STANAG 4172): rim .378 in, base .377, shoulder .354 at 1.438, neck .253, case 1.760, OAL 2.260"},
    "7.62x51": {"name": "7.62x51 mm NATO ball", "rim_d": 12.01, "rim_t": 1.37, "base_d": 11.96, "shoulder_d": 11.53, "shoulder_y": 39.62, "neck_d": 8.74,
                "case_l": 51.18, "bullet_d": 7.82, "oal": 71.12, "source": "SAAMI Z299.4, 308 Winchester / 7.62 NATO: rim .473 in, base .471, shoulder .454 at 1.560, neck .344, case 2.015, OAL 2.800"},
    "50bmg": {"name": ".50 BMG ball", "rim_d": 20.42, "rim_t": 2.11, "base_d": 20.42, "shoulder_d": 18.08, "shoulder_y": 79.25, "neck_d": 14.22,
              "case_l": 99.31, "bullet_d": 12.95, "oal": 138.43, "source": "SAAMI Z299.4, 50 Browning: rim .804 in, base .804, shoulder .712 at 3.120, neck .560, case 3.910, OAL 5.450"},
    "12ga": {"name": "12 gauge 2 3/4 in shotshell (crimped)", "rim_d": 22.10, "rim_t": 1.50, "base_d": 20.30, "shoulder_y": None, "neck_d": 19.70,
             "case_l": 58.00, "bullet_d": 0.0, "oal": 58.00, "source": "SAAMI shotshell drawing, 12 gauge: rim .870 in, body .800 at the head, .775 at the mouth, hull 2 3/4 in fired, about 2 5/16 in crimped"},
}


def profile(cart):
    """The turned profile [[y cm, r cm], ...] of a cartridge from its dimensions: the rim, a step to the base, the
    body to the shoulder (a straight taper), the shoulder to the neck, the neck to the case mouth, the bullet's ogive
    (a tangent ogive to the tip) or, for a shotshell, the crimped mouth."""
    d = cart
    p = [[0.0, d["rim_d"] / 2], [d["rim_t"], d["rim_d"] / 2], [d["rim_t"] + 0.1, d["base_d"] / 2]]
    if d.get("shoulder_y"):
        p += [[d["shoulder_y"], d["shoulder_d"] / 2], [d["shoulder_y"] + (d["shoulder_d"] - d["neck_d"]) / 2 / math.tan(math.radians(25.0)), d["neck_d"] / 2]]
    p += [[d["case_l"], d["neck_d"] / 2]]
    if d["bullet_d"] > 0:
        rb = d["bullet_d"] / 2
        p += [[d["case_l"] + 0.1, rb]]
        y0 = d["case_l"] + 0.1
        L = d["oal"] - y0
        for k in range(1, 13):
            t = k / 12.0
            p.append([y0 + L * t, rb * math.sqrt(max(0.0, 1.0 - t * t)) if k < 12 else 0.0])
    else:
        p += [[d["case_l"], 0.0]]
    return [[round(y / 10.0, 4), round(r / 10.0, 4)] for y, r in p]


def round_for(cartridge):
    c = CARTRIDGES[cartridge]
    return {"name": c["name"], "cartridge": cartridge, "units": "cm, gun space: y forward from the breech face, on the bore axis",
            "profile": profile(c), "case_y_cm": [0.0, round(c["case_l"] / 10.0, 4)], "dims_mm": {k: v for k, v in c.items() if k not in ("name", "source")},
            "source": c["source"]}


def write(gun, cartridge):
    """Writes <gun>/round.json from the cartridge table and records the cartridge on the blueprint (when it has one)."""
    r = round_for(cartridge)
    path = store.root() / gun / "round.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(r, indent=1), encoding="utf-8")
    try:
        bp = store.load(gun, "blueprint")
        bp["cartridge"] = {"id": cartridge, "source": r["source"]}
        store.save(gun, "blueprint", bp, strict=False)
    except Exception:
        pass
    return {"file": str(path), "cartridge": cartridge, "overall_cm": r["profile"][-1][0], "case_cm": r["case_y_cm"][1]}
