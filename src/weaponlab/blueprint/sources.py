"""Step 1: a gun's sources. Each file is registered with its license; its pages are scanned (text, pictures, how
much of each page is drawn, the captions); a page renders to a picture for Claude to read.

A file is data only: it is opened to read its text and draw its pages, nothing in it runs."""
import hashlib
import re
from pathlib import Path

from . import store

CAPTION = re.compile(r"^\s*((fig(ure)?|section|plate|view)\.?\s*[0-9ivxlc]+[^\n]{0,80}|section\s+[a-z]-[a-z][^\n]{0,60})", re.I | re.M)
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp")


def _pdf():
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    return pymupdf


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def new(gun, title=None):
    """An empty sources document for a gun (kept when one exists)."""
    if store.exists(gun, "sources"):
        return store.load(gun, "sources")
    return {"contract": "weaponlab-sources/1", "gun": gun, "title": title or gun, "sources": [], "pages": [], "figures": [], "facts": []}


def add(gun, file, source_id, kind, title, license_basis, publisher=None, year=None, url=None, credit=None,
        distribution=None, note=None, gun_title=None):
    """Registers a file as a source of the gun. license_basis: us-government-work, public-domain-age,
    public-domain-mark, us-patent, cc0, cc-by, cc-by-sa or permission."""
    path = Path(file)
    if not path.exists():
        raise FileNotFoundError(file)
    doc = new(gun, gun_title)
    if gun_title:
        doc["title"] = gun_title
    src = {"id": source_id, "kind": kind, "title": title, "file": str(path.resolve()), "sha256": _sha(path),
           "license": {"basis": license_basis}}
    for k, v in (("publisher", publisher), ("year", year), ("url", url), ("distribution", distribution)):
        if v is not None:
            src[k] = v
    if credit:
        src["license"]["credit"] = credit
    if note:
        src["license"]["note"] = note
    if path.suffix.lower() == ".pdf":
        d = _pdf().open(str(path))
        src["pages"] = d.page_count
        src["text_layer"] = sum(len(p.get_text()) for p in d) > 200 * min(d.page_count, 5)
    else:
        src["pages"] = 1
        src["text_layer"] = False
    doc["sources"] = [s for s in doc["sources"] if s["id"] != source_id] + [src]
    store.save(gun, "sources", doc)
    return src


def _source(doc, source_id):
    for s in doc["sources"]:
        if s["id"] == source_id:
            return s
    raise ValueError("no source %s (have %s)" % (source_id, ", ".join(s["id"] for s in doc["sources"])))


def scan(gun, source_id):
    """Every page of a source: its text, pictures, the share of it that is drawn (ink outside the words) and its
    captions. The kind follows: table (a page of numbers), figure (mostly drawn), text, mixed or blank."""
    import numpy as np
    doc = store.load(gun, "sources")
    src = _source(doc, source_id)
    out = []
    if not src["file"].lower().endswith(".pdf"):
        out.append({"source": source_id, "page": 1, "kind": "figure", "text_chars": 0, "images": 1, "drawn": 1.0, "captions": []})
    else:
        pdf = _pdf().open(src["file"])
        for i, page in enumerate(pdf):
            text = page.get_text()
            words = page.get_text("words")
            pix = page.get_pixmap(dpi=40, colorspace=_pdf().csGRAY)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            ink = img < 128
            sx, sy = pix.width / page.rect.width, pix.height / page.rect.height
            for w in words:                         # the words' own boxes are text, not drawing
                ink[int(w[1] * sy):int(w[3] * sy) + 1, int(w[0] * sx):int(w[2] * sx) + 1] = False
            drawn = float(ink.mean())
            digits = sum(c.isdigit() for c in text)
            caps = [m.group(0).strip()[:100] for m in CAPTION.finditer(text)][:6]
            if len(text.strip()) < 20 and drawn < 0.005:
                kind = "blank"
            elif (drawn > 0.04 and (len(text) < 900 or caps)) or (drawn > 0.015 and len(text) < 600):
                kind = "figure"
            elif digits > 0.08 * max(len(text), 1) and len(text) > 200:
                kind = "table"
            elif drawn > 0.02:
                kind = "mixed"
            else:
                kind = "text"
            out.append({"source": source_id, "page": i + 1, "kind": kind, "text_chars": len(text),
                        "images": len(page.get_images()), "drawn": round(drawn, 4), "captions": caps})
    doc["pages"] = [p for p in doc.get("pages", []) if p["source"] != source_id] + out
    store.save(gun, "sources", doc)
    counts = {}
    for p in out:
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
    return {"source": source_id, "pages": len(out), "kinds": counts,
            "figures": [{"page": p["page"], "drawn": p["drawn"], "captions": p["captions"]} for p in out if p["kind"] == "figure"],
            "tables": [p["page"] for p in out if p["kind"] == "table"]}


def _page_text(file, pdf, page):
    """A page's text: its own layer (a scan's hidden OCR layer, when it has one), else OCR Lab's read of the page
    (Tesseract), when ocrlab-mcp is installed."""
    t = pdf[page - 1].get_text()
    if len(re.sub(r"\s", "", t)) >= 20:
        return t
    try:
        from ocrlab import read as OCR
    except ImportError:
        return t
    try:
        return OCR.page(file, page)["text"]
    except (FileNotFoundError, ValueError):
        return t


def text(gun, source_id, page):
    """A page's text, as the source holds it (a scan's hidden OCR layer, when it has one), else read by OCR."""
    src = _source(store.load(gun, "sources"), source_id)
    pdf = _pdf().open(src["file"])
    return _page_text(src["file"], pdf, page)


def find(gun, pattern, source_id=None, limit=40):
    """Lines matching a pattern (a regular expression, any case) across the sources' text: where a part or a fact
    is named."""
    doc = store.load(gun, "sources")
    rx = re.compile(pattern, re.I)
    hits = []
    for s in doc["sources"]:
        if source_id and s["id"] != source_id or not s["file"].lower().endswith(".pdf"):
            continue
        pdf = _pdf().open(s["file"])
        for i, page in enumerate(pdf):
            for line in _page_text(s["file"], pdf, i + 1).splitlines():
                if rx.search(line):
                    hits.append({"source": s["id"], "page": i + 1, "line": line.strip()[:160]})
                    if len(hits) >= limit:
                        return hits
    return hits


def render(gun, source_id, page, dpi=110):
    """A page as a picture (pages/<source>_p<NNN>.png) for Claude to read. Higher dpi for detail."""
    doc = store.load(gun, "sources")
    src = _source(doc, source_id)
    out = store.folder(gun, "pages") / ("%s_p%03d_%d.png" % (source_id, page, dpi))
    if src["file"].lower().endswith(".pdf"):
        pdf = _pdf().open(src["file"])
        if not 1 <= page <= pdf.page_count:
            raise ValueError("page %d: %s has %d pages" % (page, source_id, pdf.page_count))
        pdf[page - 1].get_pixmap(dpi=dpi).save(str(out))
    else:
        import cv2
        img = cv2.imread(src["file"])
        cv2.imwrite(str(out), img)
    for p in doc.get("pages", []):
        if p["source"] == source_id and p["page"] == page:
            p["render"] = store.rel(gun, out)
    store.save(gun, "sources", doc)
    return str(out)


def sheet(gun, source_id, pages, dpi=40, cols=6):
    """Several pages side by side in one picture, each with its page number: a quick look for the figure pages."""
    import cv2
    import numpy as np
    src = _source(store.load(gun, "sources"), source_id)
    pdf = _pdf().open(src["file"])
    tiles = []
    for n in pages:
        pix = pdf[n - 1].get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()
        img = cv2.resize(img, (int(img.shape[1] * 360 / img.shape[0]), 360))
        cv2.rectangle(img, (0, 0), (70, 26), (255, 255, 255), -1)
        cv2.putText(img, "p%d" % n, (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 0, 0), 2)
        tiles.append(img)
    w = max(t.shape[1] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 2, 2, 2, w - t.shape[1] + 2, cv2.BORDER_CONSTANT, value=(200, 200, 200)) for t in tiles]
    rows = [np.hstack(tiles[i:i + cols] + [np.full_like(tiles[0], 255)] * (cols - len(tiles[i:i + cols]))) for i in range(0, len(tiles), cols)]
    out = store.folder(gun, "pages") / ("%s_sheet_%d-%d.png" % (source_id, pages[0], pages[-1]))
    cv2.imwrite(str(out), np.ascontiguousarray(np.vstack(rows)[:, :, ::-1]))   # RGB to the BGR cv2 writes
    return str(out)


def parts_list(gun, entries, replace=False):
    """The gun's parts as its sources name them: [{"name", "number"?, "page", "figure"?, "visible", "why"?,
    "source"}]. Added to the list (an entry with the same name and number is replaced), or replacing it."""
    doc = store.load(gun, "sources")
    have = [] if replace else doc.get("parts_list", [])
    key = lambda e: (e["name"], e.get("number"))   # noqa: E731
    new = {key(e) for e in entries}
    doc["parts_list"] = [e for e in have if key(e) not in new] + list(entries)
    store.save(gun, "sources", doc)
    return {"listed": len(doc["parts_list"]), "visible": sum(1 for e in doc["parts_list"] if e["visible"])}
