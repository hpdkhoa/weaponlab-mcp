"""Step 2: the facts in a gun's data tables. find() lists candidates: each known quantity's label found in the
text, with the numbers near it and their units, as the page prints them. add() records one fact, converted to cm,
kg or degrees, with its page and the quote it came from. Old tables often print a column of numbers apart from its
labels (the text layer reads them in a different order), so a candidate is checked on the page picture before it is
added."""
import re

from . import sources as S
from . import store

# quantity id: (label pattern, the unit when the line gives none)
LABELS = {
    "overall_length": (r"over\s*-?\s*all\s+length|length\s*,?\s*over\s*-?\s*all|total\s+length|length of (the )?(pistol|rifle|weapon|gun|carbine)", "in"),
    "barrel_length": (r"length of (the )?barrel|barrel\s+length", "in"),
    "height": (r"\bheight\b(?! of (the )?(front )?sight)", "in"),
    "width": (r"\bwidth\b|\bthickness\b", "in"),
    "sight_height": (r"height of (the )?front sight", "in"),
    "sight_radius": (r"sight\s+radius|distance between sights", "in"),
    "bore": (r"caliber of bore|\bbore\b.*diameter|\bcaliber\b", "in"),
    "weight": (r"weight of (the )?(pistol|rifle|weapon|gun|carbine)|\bweight\b.*(empty|unloaded|without)", "lb"),
    "weight_loaded_magazine": (r"weight of (the )?loaded magazine", "lb"),
    "weight_empty_magazine": (r"weight of (the )?empty magazine", "lb"),
    "magazine_capacity": (r"magazine capacity|capacity of (the )?magazine|\bcartridges?\b.*magazine holds|holds \d+ (rounds|cartridges)", "count"),
    "trigger_pull": (r"trigger pull", "lb"),
    "rate_of_fire": (r"(cyclic )?rate of fire", "rpm"),
    "muzzle_velocity": (r"muzzle velocity", "fps"),
}
UNITS = {"in": ("cm", 2.54), "inch": ("cm", 2.54), "inches": ("cm", 2.54), "mm": ("cm", 0.1), "cm": ("cm", 1.0),
         "m": ("cm", 100.0), "ft": ("cm", 30.48), "feet": ("cm", 30.48),
         "lb": ("kg", 0.45359237), "lbs": ("kg", 0.45359237), "pounds": ("kg", 0.45359237), "pound": ("kg", 0.45359237),
         "oz": ("kg", 0.028349523), "ounces": ("kg", 0.028349523), "kg": ("kg", 1.0), "g": ("kg", 0.001),
         "count": ("count", 1.0), "rpm": ("rpm", 1.0), "fps": ("m_s", 0.3048), "m_s": ("m_s", 1.0), "deg": ("deg", 1.0)}
NUM = re.compile(r"(?<![\w.])(\d{1,4}(?:\.\d+)?|\.\d+)\s*(inches|inch|in\b|mm\b|cm\b|ft\b|feet|lbs?\b|pounds?|oz\b|ounces|kg\b|g\b|m\b)?", re.I)


def find(gun, source_id=None, quantities=None):
    """Candidates for each quantity: the page, the label line, and the numbers on it and the two lines after it."""
    doc = store.load(gun, "sources")
    out = {}
    for s in doc["sources"]:
        if source_id and s["id"] != source_id or not s["file"].lower().endswith(".pdf"):
            continue
        pdf = S._pdf().open(s["file"])
        for i, page in enumerate(pdf):
            lines = [l.strip() for l in page.get_text().splitlines()]
            for q, (pat, unit) in LABELS.items():
                if quantities and q not in quantities:
                    continue
                rx = re.compile(pat, re.I)
                for n, line in enumerate(lines):
                    if not rx.search(line):
                        continue
                    near = " ".join(lines[n:n + 3])
                    nums = [{"value": float(m.group(1)), "unit": (m.group(2) or "").lower() or None} for m in NUM.finditer(near)]
                    out.setdefault(q, []).append({"source": s["id"], "page": i + 1, "line": line[:140], "near": near[:220],
                                                  "numbers": nums[:8], "default_unit": unit})
    return out


def add(gun, fact_id, value, unit, source_id, page, quote, about=None):
    """Records a fact. unit as printed (in, mm, lb, oz, count...): the fact is kept in cm, kg, deg, count, rpm or
    m_s, with the printed value in raw."""
    u = UNITS.get(unit.lower())
    if not u:
        raise ValueError("unit %s: one of %s" % (unit, ", ".join(UNITS)))
    doc = store.load(gun, "sources")
    S._source(doc, source_id)
    fact = {"id": fact_id, "value": round(float(value) * u[1], 6), "unit": u[0], "raw": "%s %s" % (value, unit),
            "source": source_id, "page": int(page), "quote": quote}
    if about:
        fact["about"] = about
    doc["facts"] = [f for f in doc.get("facts", []) if f["id"] != fact_id] + [fact]
    store.save(gun, "sources", doc)
    return fact


def facts(gun):
    return {f["id"]: f for f in store.load(gun, "sources").get("facts", [])}
