"""The motion check: a clip's hands move as a person's do, with no pops and no jerks. A pop is a frame where a hand
jumps much further than it moves on the frames round it; a jerk is a sudden change of speed the frames round it do
not have; a finger jump is a joint turning further in one frame than a hand turns it. Measured on the hand's place
as the player sees it (the eye's frame, cm) and on the digits' bends (degrees)."""

import math


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return 0.0
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def pops(points, rel=3.0, floor_cm=1.5):
    """Frames (index of the frame arrived at) where the step from the last frame is over rel times the clip's middle
    step and over floor_cm: [(i, step cm)]."""
    steps = [_dist(points[i - 1], points[i]) for i in range(1, len(points))]
    m = _median(steps)
    return [(i + 1, round(s, 2)) for i, s in enumerate(steps) if s > max(rel * m, floor_cm)]


def jerks(points, rel=4.0, floor_cm=0.8):
    """Frames where the change of velocity (the second difference, cm a frame a frame) is over rel times its middle
    and over floor_cm: [(i, cm)]."""
    acc = []
    for i in range(1, len(points) - 1):
        a = [points[i + 1][k] - 2.0 * points[i][k] + points[i - 1][k] for k in range(3)]
        acc.append(math.sqrt(sum(x * x for x in a)))
    m = _median(acc)
    return [(i + 1, round(a, 2)) for i, a in enumerate(acc) if a > max(rel * m, floor_cm)]


def finger_jumps(bends, max_deg=25.0):
    """Frames where a digit's joint turns more than max_deg in one frame: [(i, joint, deg)]. bends: per frame
    {joint: degrees}."""
    out = []
    for i in range(1, len(bends)):
        for k, v in bends[i].items():
            if k in bends[i - 1] and abs(v - bends[i - 1][k]) > max_deg:
                out.append((i, k, round(abs(v - bends[i - 1][k]), 1)))
    return out


def check(frames):
    """A clip's motion faults. frames: [{"t", "hands": {side: {"at": [x, y, z] cm in the eye's frame, "bends":
    {joint: deg}}}}]. Returns {side: {pops, jerks, finger_jumps}, ok}."""
    out, ok = {}, True
    sides = sorted({s for f in frames for s in f["hands"]})
    for s in sides:
        seq = [f for f in frames if s in f["hands"]]
        pts = [f["hands"][s]["at"] for f in seq]
        ts = [f["t"] for f in seq]
        p = [(ts[i], c) for i, c in pops(pts)]
        j = [(ts[i], c) for i, c in jerks(pts)]
        fj = [(ts[i], k, c) for i, k, c in finger_jumps([f["hands"][s].get("bends", {}) for f in seq])]
        out[s] = {"pops": p, "jerks": j, "finger_jumps": fj}
        ok = ok and not (p or j or fj)
    out["ok"] = ok
    return out
