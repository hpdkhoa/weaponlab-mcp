"""Known answers for the hand trim's pure parts: the grip frame that carries a reference hold from one gun to another,
and the motion check."""

import math

from weaponlab.gunkit import motion, reference

M1911 = {"name": "M1911A1", "magazine": {"lips": [0.0, -2.351, -1.66], "axis": [0.0, -0.32039, -0.94729]}}


def close(a, b, tol=1e-6):
    return all(abs(a[i] - b[i]) <= tol for i in range(len(a)))


def test_grip_frame_is_square():
    o, l, f, d = reference.facts_frame(M1911)
    for u in (l, f, d):
        assert abs(math.sqrt(sum(x * x for x in u)) - 1.0) < 1e-9
    for a, b in ((l, f), (l, d), (f, d)):
        assert abs(sum(a[i] * b[i] for i in range(3))) < 1e-9
    assert close(o, [0.0, -2.351, -1.66])
    assert d[2] > 0.9 and d[1] > 0.3                 # up the magazine: up and forward (the grip leans back)
    assert close(l, [1.0, 0.0, 0.0])


def test_round_trip():
    fr = reference.facts_frame(M1911)
    for p in ([1.0, 2.0, 3.0], [-1.67, -3.57, -6.5], [0.0, 0.0, 0.0]):
        assert close(reference.from_grip(reference.to_grip(p, fr), fr), p)


def test_lips_and_grip_line():
    fr = reference.facts_frame(M1911)
    assert close(reference.to_grip([0.0, -2.351, -1.66], fr), [0.0, 0.0, 0.0])
    down = [0.0, -2.351 + -0.32039 * 5.0, -1.66 + -0.94729 * 5.0]      # 5 cm down the magazine
    c = reference.to_grip(down, fr)
    assert close(c, [0.0, 0.0, -5.0], 1e-4)


def test_carry_between_grip_angles():
    # the same point 4 cm down the grip and 2 cm behind it lands at the same place on a grip leaning 22 degrees
    # as on one leaning 18 degrees, in each gun's grip frame
    def gun(deg):
        a = math.radians(deg)
        return {"name": "g", "magazine": {"lips": [0.0, 0.0, 0.0], "axis": [0.0, -math.sin(a), -math.cos(a)]}}
    f18, f22 = reference.facts_frame(gun(18.0)), reference.facts_frame(gun(22.0))
    c = [0.5, -2.0, -4.0]
    p22 = reference.from_grip(c, f22)
    assert close(reference.to_grip(p22, f22), c)
    assert not close(reference.from_grip(c, f18), p22, 1e-3)    # it moves with the grip, not with the bore


def test_reference_check():
    ok = {"contract": reference.CONTRACT, "hands": {"r": {
        "points": {k: [0, 0, 0] for k in ("wrist", "index_knuckle", "knuckle", "pinky_knuckle", "thumb_cmc")},
        "curls": {fi: [1, 2, 3] for fi in ("index", "middle", "ring", "pinky")}, "thumb": [5, 6]}}}
    assert reference.check(ok) == []
    bad = {"contract": "x", "hands": {"r": {"points": {}, "curls": {}, "thumb": []}}}
    assert len(reference.check(bad)) >= 5


def test_smooth_motion_passes():
    pts = [[10.0 * math.sin(i / 10.0), 2.0 * i / 30.0, 0.0] for i in range(60)]
    assert motion.pops(pts) == []
    assert motion.jerks(pts) == []


def test_pop_is_found():
    pts = [[0.1 * i, 0.0, 0.0] for i in range(30)]
    for i in range(15, 30):
        pts[i][1] += 4.0                              # the hand jumps 4 cm on frame 15
    assert [i for i, _ in motion.pops(pts)] == [15]
    assert 15 in [i for i, _ in motion.jerks(pts)] or 14 in [i for i, _ in motion.jerks(pts)]


def test_finger_jump_and_check():
    bends = [{"index_02": 10.0}, {"index_02": 12.0}, {"index_02": 60.0}]
    assert motion.finger_jumps(bends) == [(2, "index_02", 48.0)]
    frames = [{"t": i / 30.0, "hands": {"r": {"at": [0.1 * i, 0.0, 0.0], "bends": {"index_02": 10.0}}}} for i in range(20)]
    assert motion.check(frames)["ok"]
    frames[10]["hands"]["r"]["bends"]["index_02"] = 70.0
    assert not motion.check(frames)["ok"]
