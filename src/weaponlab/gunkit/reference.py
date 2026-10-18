"""Reference holds: a known good hold (a pack's animator-made hand, a dataset's grasp) carried from its own gun to
another gun of the same grip style. A hold is kept in the grip's frame: its origin the magazine's lips (the top of
the grip), d up the magazine's line, f forward square to it, l to the gun's left square to both, all in cm. Two
pistols differ in grip angle and bore height; the hand round the grip follows the grip, so the grip's frame carries it.

A reference file (weaponlab-reference/1): {"contract", "style", "source": {pack, license, clip, frame}, "frame",
"hands": {r|l: {"points": {name: [l, f, d]}, "curls": {finger: [3 deg]}, "thumb": [2 deg]}}}. Reference files hold
numbers measured from a pack; the pack's licence decides where they may live (a Fab Standard licence: inside the
game project, never in a public repository)."""

import math

CONTRACT = "weaponlab-reference/1"


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _scale(a, k):
    return [x * k for x in a]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    if n < 1e-12:
        raise ValueError("a zero direction")
    return [x / n for x in a]


def grip_frame(lips, up, forward, left):
    """The grip's frame: (origin, l, f, d), each a unit vector, square to one another. up: the magazine's line toward
    its lips; forward and left: rough directions (the bore, the gun's left), squared up against up in that order."""
    d = _unit(up)
    f = _unit(_sub(forward, _scale(d, _dot(forward, d))))
    lv = _sub(_sub(left, _scale(d, _dot(left, d))), _scale(f, _dot(left, f)))
    return (list(lips), _unit(lv), f, d)


def to_grip(p, frame):
    o, l, f, d = frame
    q = _sub(p, o)
    return [_dot(q, l), _dot(q, f), _dot(q, d)]


def from_grip(c, frame):
    o, l, f, d = frame
    return [o[i] + l[i] * c[0] + f[i] * c[1] + d[i] * c[2] for i in range(3)]


def facts_frame(facts):
    """A gun's grip frame from its facts (Gun Kit's gun cm: x left, y forward, z up): the magazine's lips and line."""
    mag = facts.get("magazine") or {}
    if not mag.get("lips") or not mag.get("axis"):
        raise ValueError("%s: no magazine lips and axis in its facts" % facts.get("name"))
    up = [-x for x in mag["axis"]]                   # the facts' axis runs down the magazine, out of the well
    return grip_frame(mag["lips"], up, [0.0, 1.0, 0.0], [1.0, 0.0, 0.0])


def check(ref):
    """A reference file's faults (empty when it is good)."""
    bad = []
    if ref.get("contract") != CONTRACT:
        bad.append("contract is not %s" % CONTRACT)
    for side, h in (ref.get("hands") or {}).items():
        if side not in ("r", "l"):
            bad.append("hand %r is not r or l" % side)
            continue
        for k in ("wrist", "index_knuckle", "knuckle", "pinky_knuckle", "thumb_cmc"):
            if len((h.get("points") or {}).get(k) or []) != 3:
                bad.append("%s: no point %s" % (side, k))
        for fi in ("index", "middle", "ring", "pinky"):
            if len((h.get("curls") or {}).get(fi) or []) != 3:
                bad.append("%s: no curls for %s" % (side, fi))
        if len(h.get("thumb") or []) != 2:
            bad.append("%s: no thumb bends" % side)
    if not ref.get("hands"):
        bad.append("no hands")
    return bad
