"""Where a gun's digitizer files live, and loading and saving them through their contracts.

    <work>/digitize/<gun>/sources.json     weaponlab-sources/1
    <work>/digitize/<gun>/blueprint.json   weaponlab-blueprint/1
    <work>/digitize/<gun>/pages/           rendered pages
    <work>/digitize/<gun>/figures/         figures cut from pages, and their grid and trace pictures
    <work>/digitize/<gun>/check/           overlay pictures and the last check
    <work>/digitize/<gun>/model/           the built model and its parts map

The root is the project's work folder, or WEAPONLAB_DIGITIZE when it is set."""
import json
import os
import re
from pathlib import Path

from .. import contracts as C
from ..config import project

NAME = re.compile(r"^[A-Za-z0-9_]+$")


def root():
    r = os.environ.get("WEAPONLAB_DIGITIZE")
    return Path(r) if r else Path(project().work) / "digitize"


def folder(gun, *sub):
    if not NAME.match(gun or ""):
        raise ValueError("a gun's name is letters, digits and _ (it names files): %r" % gun)
    d = root().joinpath(gun, *sub)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(gun, kind):
    return folder(gun) / ("%s.json" % kind)


def exists(gun, kind):
    return (root() / gun / ("%s.json" % kind)).exists()


def load(gun, kind):
    p = _path(gun, kind)
    if not p.exists():
        raise FileNotFoundError("%s has no %s yet (%s)" % (gun, kind, p))
    return json.loads(p.read_text(encoding="utf-8"))


def save(gun, kind, doc, strict=True):
    """Writes a document after its contract check. strict: refuse it when the check finds problems (a blueprint is
    saved while it is being written, so its part checks run in check.py)."""
    bad = C.check_sources(doc) if kind == "sources" else C._schema_problems(doc, kind)
    if bad and strict:
        raise ValueError("the %s for %s does not follow its contract:\n  %s" % (kind, gun, "\n  ".join(bad[:20])))
    _path(gun, kind).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return bad


def rel(gun, path):
    """A path inside the gun's folder, as the documents store it (relative, with /)."""
    return Path(path).resolve().relative_to((root() / gun).resolve()).as_posix()


def abspath(gun, relpath):
    return root() / gun / relpath
