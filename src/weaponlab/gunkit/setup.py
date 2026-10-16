"""The hand step's two inputs set before any hand clip is made: the grip style (how this kind of gun is held, by its
action family) and the character (who holds it: the hands' size and covering). gripstyles/<id>.json and
characters/<id>.json beside this module; a project adds its own under <data>/gunkit/gripstyles and
<data>/gunkit/characters, and names its character in weaponlab.json ("gunkit": {"character": "<id>"})."""
import json
from pathlib import Path

from .. import contracts as C
from ..config import project
from . import actions as A

HERE = Path(__file__).resolve().parent


def _dirs(kind):
    out = [HERE / kind]
    try:
        out.insert(0, Path(project().data) / "gunkit" / kind)
    except Exception:
        pass
    return out


def _load(kind, ident):
    for d in _dirs(kind):
        p = d / ("%s.json" % ident)
        if p.exists():
            doc = json.loads(p.read_text(encoding="utf-8"))
            bad = C.check(doc)
            if bad:
                raise ValueError("%s %s does not follow its contract:\n  %s" % (kind[:-1], ident, "\n  ".join(bad)))
            return doc
    raise ValueError("no %s %s (have %s)" % (kind[:-1], ident, ", ".join(ids(kind))))


def ids(kind):
    return sorted({p.stem for d in _dirs(kind) if d.exists() for p in d.glob("*.json")})


def style(ident):
    return _load("gripstyles", ident)


def style_for(action_id):
    """The grip style an action family is held by: the one that names it."""
    A.load(action_id)
    for i in ids("gripstyles"):
        s = style(i)
        if action_id in s["families"]:
            return s
    return None


def character(ident=None):
    """A character by id, or the project's (weaponlab.json gunkit.character), or None."""
    if ident is None:
        ident = ((project().config.get("gunkit") or {}).get("character"))
    return _load("characters", ident) if ident else None


def glove_cm(char):
    return float(((char or {}).get("covering") or {}).get("thickness_cm", 0.0))
