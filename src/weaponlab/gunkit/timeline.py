"""The timeline of one clip: an action's beats, events and poses turned into frames, for one gun's facts. Pure Python:
Blender keys the gun's parts from it (gun clips) and Pose Lab's solver poses the arms from it (hand clips).

A gun clip's frame:  {"t": 0.05, "parts": {"carrier": 0.62, "magazine": [0, 0, -4.1] | {"follow": "l"}}}
A hand clip's frame: {"t": 0.05, "parts": {...}, "gun": {"roll": 0, "pitch": 0, "yaw": 0, "move": [0, 0, 0]},
                      "hands": {"r": {"a": TARGET, "b": TARGET, "w": 0.4, "grasp": "palm"}, "l": {...}}}
TARGET is {"space": "gun", "point": [x, y, z], "name": "support"} (gun space, the parts as at that frame) or
{"space": "view", "point": [x, y, z], "name": "pouch_l"} (view space); the hand is at a, moving to b, w of the way.
The solver brings both into one space with the gun's pose at the frame, then blends."""
import math

from . import actions as A

FPS = 60


def ease(x, kind="inout"):
    x = min(max(x, 0.0), 1.0)
    if kind == "linear":
        return x
    if kind == "in":
        return x * x
    if kind == "out":
        return 1.0 - (1.0 - x) * (1.0 - x)
    if kind == "snap":
        return 1.0 if x >= 1.0 else 0.0
    if kind == "spring":                      # a spring's return: past the stop a little, then settled
        return 1.0 - math.cos(x * math.pi * 2.5) * math.exp(-5.0 * x) if x < 1.0 else 1.0
    return x * x * (3.0 - 2.0 * x)            # inout: smoothstep


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _scale(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _rot(p, pivot, axis, deg):
    """p turned by deg round axis (a unit vector) through pivot (Rodrigues)."""
    v = [p[i] - pivot[i] for i in range(3)]
    k = axis
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    kv = k[0] * v[0] + k[1] * v[1] + k[2] * v[2]
    kxv = [k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0]]
    r = [v[i] * c + kxv[i] * s + k[i] * kv * (1 - c) for i in range(3)]
    return _add(r, pivot)


def _value_track(beats, t, start=0.0):
    """A part's value at t from its beats (each from the value before it to its own)."""
    v = start
    for b in sorted(beats, key=lambda b: b["from"]):
        if t < b["from"]:
            break
        span = b["to"] - b["from"]
        x = 1.0 if span <= 0 else (t - b["from"]) / span
        v = v + (b["value"] - v) * ease(x, b.get("ease", "inout")) if t < b["to"] else b["value"]
    return v


def well(facts, d):
    """d cm out of the well along the magazine's own line (its axis, out of the gun), or "clear": its length and
    half a cm, so it is out of the grip. A magazine that sits tilted (a pistol's, along its grip) leaves along that
    line, not straight down."""
    m = facts.get("magazine") or {}
    axis = m.get("axis") or [0.0, 0.0, -1.0]
    if d == "clear":
        d = float(m.get("length_cm", 10.0)) + 0.5
    return _scale(axis, float(d))


def _beats(beats, facts):
    """Beats with any well move turned into a plain offset in gun space."""
    out = []
    for b in beats:
        if "well" in b:
            b = dict(b)
            b["offset"] = _add(well(facts, b.pop("well")), b.get("offset", [0.0, 0.0, 0.0]))
        out.append(b)
    return out


def _offset_track(beats, t):
    o = [0.0, 0.0, 0.0]
    for b in sorted(beats, key=lambda b: b["from"]):
        if t < b["from"]:
            break
        if "offset" not in b:
            continue
        span = b["to"] - b["from"]
        x = 1.0 if span <= 0 else (t - b["from"]) / span
        e = ease(x, b.get("ease", "inout")) if t < b["to"] else 1.0
        o = [o[i] + (b["offset"][i] - o[i]) * e for i in range(3)]
    return o


def frames_of(seconds, fps=FPS):
    n = max(int(round(seconds * fps)), 1)
    return [round(i / fps, 5) for i in range(n + 1)]


def carry_spans(clip):
    """Each free part's spans in a hand's grasp: [(part, hand, start, end)], end None to the clip's end."""
    spans, open_ = [], {}
    for e in sorted(clip.get("events", []), key=lambda e: e["from"]):
        if "carry" in e:
            open_[e["carry"]] = (e["hand"], e["from"])
        if "seat" in e and e["seat"] in open_:
            hand, start = open_.pop(e["seat"])
            spans.append((e["seat"], hand, start, e["to"]))
    for part, (hand, start) in open_.items():
        spans.append((part, hand, start, None))
    return spans


def part_values(action, clip, t, kind="gun"):
    """Every part's value at t: a share for a slide or a turn, an offset or a follow for a free part."""
    beats = clip.get("beats", [])
    out = {}
    for role, p in action["parts"].items():
        mine = [b for b in beats if b["part"] == role]
        if p["kind"] == "free":
            follow = next((b["follow"] for b in mine if "follow" in b and b["from"] <= t <= b["to"]), None)
            out[role] = {"follow": follow} if follow else _offset_track(mine, t)
        else:
            out[role] = _value_track(mine, t)
    if kind == "hand":
        for part, hand, start, end in carry_spans(clip):
            if t >= start and (end is None or t < end):
                out[part] = {"follow": hand}
            elif end is not None and t >= end:
                out[part] = [0.0, 0.0, 0.0]
    return out


def point(facts, values, mark, part=None):
    """A mark's place in gun space with the parts as they are: it rides its part (slide or turn), or its parts in order
    (a bolt knob: the bolt's lift turns it, then the bolt's draw slides it), when it has them."""
    roles = facts.get("mark_parts", {}).get(mark) if part is None else part
    roles = [roles] if isinstance(roles, str) else list(roles or [])
    if part is not None and isinstance(part, str):
        # a target that names one part rides the mark's own chain when that part is in it
        own = facts.get("mark_parts", {}).get(mark)
        own = [own] if isinstance(own, str) else list(own or [])
        if part in own:
            roles = own
    at = list(facts["marks"][mark])
    for role in roles:
        if role not in facts["parts"]:
            continue
        p, v = facts["parts"][role], values.get(role, 0.0)
        if p["kind"] == "slide":
            at = _add(at, _scale(p["axis"], p["travel_cm"] * v))
        elif p["kind"] == "turn":
            at = _rot(at, p["pivot"], p["axis"], p["turn_deg"] * v)
        elif isinstance(v, list):
            at = _add(at, v)
    return at


def _resolve(facts, values, go):
    """A target's place now. go may add "offset" [x, y, z] (in its own space) and "value" (the part as at that share,
    not as it is now: a hand that lets go of a handle stays where the handle was)."""
    r = _resolve_base(facts, dict(values, **({go["part"]: go["value"]} if "value" in go and "part" in go else {})), go)
    if go.get("offset") and r["point"] is not None:
        r["point"] = _add(r["point"], go["offset"])
    if "well" in go and r["point"] is not None:                    # cm out along the magazine's line, in gun space
        r["point"] = _add(r["point"], well(facts, go["well"]))
    return r


def _resolve_base(facts, values, go):
    if "place" in go:
        return {"space": "view", "point": list(A.PLACES[go["place"]]), "name": go["place"]}
    if "part" in go and facts["parts"].get(go["part"], {}).get("kind") == "free":
        mark = go.get("mark") or ("mag_grab" if "mag_grab" in facts["marks"] else None)
        rest = facts["marks"][mark] if mark else _add(facts["magazine"]["lips"], [0.0, 0.0, -10.0])
        off = values.get(go["part"])
        if isinstance(off, list):
            return {"space": "gun", "point": _add(rest, off), "name": go["part"]}
        return {"space": "hand", "point": None, "name": go["part"]}       # it rides a hand: the hand stays where it is
    mark = go.get("mark")
    return {"space": "gun", "point": point(facts, values, mark, go.get("part")), "name": mark}


def _pose(clip, t):
    pose = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "move": [0.0, 0.0, 0.0]}
    for g in sorted(clip.get("gun", []), key=lambda g: g["from"]):
        if t < g["from"]:
            break
        span = g["to"] - g["from"]
        x = 1.0 if span <= 0 else (t - g["from"]) / span
        e = ease(x, g.get("ease", "inout")) if t < g["to"] else 1.0
        for k in ("roll", "pitch", "yaw"):
            pose[k] += (g.get(k, 0.0) - pose[k]) * e
        mv = g.get("move", [0.0, 0.0, 0.0])
        pose["move"] = [pose["move"][i] + (mv[i] - pose["move"][i]) * e for i in range(3)]
    return pose


def gun_clip(action, facts, clip_id, fps=FPS):
    clip = dict(action["gun_clips"][clip_id])
    clip["beats"] = _beats(clip.get("beats", []), facts)
    return {"clip": clip_id, "seconds": clip["seconds"], "fps": fps,
            "frames": [{"t": t, "parts": part_values(action, clip, t)} for t in frames_of(clip["seconds"], fps)]}


def free_path(action, facts, clip_id, fps=FPS):
    """A free part's place in a gun-only view (no arms drawn), frame by frame: {part: [[x, y, z] cm from its seat, one
    a frame]}. Where the gun clip moves it (a drop), that; while the hand clip's hand carries it, the hand's own way
    between its targets, the part held at the grasp mark; once the hand has seated it, at its seat. A hand's target off
    the gun (a pouch, in view space) stands for "away": 50 cm out along the well's line, out of sight, so a fresh
    magazine comes up that line into the well (a hand lines it up before it goes in)."""
    if clip_id not in action.get("hand_clips", {}) or clip_id not in action.get("gun_clips", {}):
        return {}
    g = gun_clip(action, facts, clip_id, fps)
    h = hand_clip(action, facts, clip_id, fps)
    out = {}
    for role, p in action["parts"].items():
        if p["kind"] != "free":
            continue
        if not (role in facts.get("parts", {}) or (role in ("magazine", "cell") and facts.get("magazine"))):
            continue                      # a free part this gun does not carry (a stripper clip, a loose shell)
        grasp = facts["marks"].get("mag_grab") or _add(facts["magazine"]["lips"], [0.0, 0.0, -10.0])
        away = _add(well(facts, "clear"), well(facts, 50.0))
        track, last, carried = [], [0.0, 0.0, 0.0], False
        for fg, fh in zip(g["frames"], h["frames"]):
            v = fh["parts"].get(role)
            if isinstance(v, dict) and "follow" in v:
                carried = True
                hd = fh["hands"][v["follow"]]

                def at(tg, last=last):
                    if tg["space"] == "view":
                        return away
                    if tg["space"] == "gun" and tg["point"] is not None:
                        return [tg["point"][i] - grasp[i] for i in range(3)]
                    return last
                a, b = at(hd["a"]), at(hd["b"])
                last = [a[i] + (b[i] - a[i]) * hd["w"] for i in range(3)]
            elif carried:
                last = v if isinstance(v, list) else [0.0, 0.0, 0.0]
            else:
                gv = fg["parts"].get(role)
                last = gv if isinstance(gv, list) else [0.0, 0.0, 0.0]
            track.append(list(last))
        out[role] = [[round(x, 4) for x in q] for q in well_bound(_smooth(track, fps), facts)]
    return out


def _smooth(track, fps, sigma_s=0.05):
    """The way smoothed in time (a Gaussian of sigma_s seconds, ends held): the joins between a hand's moves (each its
    own ease) run on without a corner. A held place stays held; a monotone move stays monotone."""
    sig = sigma_s * fps
    rad = int(math.ceil(3 * sig))
    w = [math.exp(-0.5 * (k / sig) ** 2) for k in range(-rad, rad + 1)]
    n, out = len(track), []
    for i in range(n):
        acc, tot = [0.0, 0.0, 0.0], 0.0
        for k, wk in zip(range(-rad, rad + 1), w):
            q = track[min(max(i + k, 0), n - 1)]
            acc = [acc[j] + wk * q[j] for j in range(3)]
            tot += wk
        out.append([a / tot for a in acc])
    return out


def well_bound(track, facts, ramp_cm=2.0):
    """A magazine is boxed in by its well: while any of it is still in the grip it moves only along the well's line.
    Each place split into d, the way out along the line, and the rest (sideways); the sideways part kept only as the
    magazine's top clears the grip: none until d reaches the magazine's length, all of it ramp_cm further out."""
    m = facts.get("magazine") or {}
    ax = m.get("axis") or [0.0, 0.0, -1.0]
    n = math.sqrt(sum(a * a for a in ax))
    ax = [a / n for a in ax]
    length = float(m.get("length_cm", 10.0))
    out = []
    for q in track:
        d = sum(q[i] * ax[i] for i in range(3))
        side = [q[i] - d * ax[i] for i in range(3)]
        k = min(max((d - length) / ramp_cm, 0.0), 1.0)
        k = k * k * (3.0 - 2.0 * k)
        out.append([max(d, 0.0) * ax[i] + side[i] * k for i in range(3)])
    return out


def hand_clip(action, facts, clip_id, fps=FPS):
    """The hand clip's frames: the parts (the gun clip of the same name moves them, or they rest), the gun's pose and
    each hand's way from one target to the next."""
    clip = action["hand_clips"][clip_id]
    gun = action["gun_clips"].get(clip_id, {"seconds": clip["seconds"], "beats": []})
    merged = {"beats": _beats(gun.get("beats", []), facts), "events": clip.get("events", [])}
    events = {h: sorted([e for e in clip.get("events", []) if e["hand"] == h], key=lambda e: e["from"]) for h in ("r", "l")}
    # where each hand rests: the right on the grip, the left on the support, unless the action says (a bow: the left
    # on its grip, the right on the string)
    home = {h: dict(v) for h, v in action.get("home", {"r": {"mark": "grip"}, "l": {"mark": "support"}}).items()}
    out = []
    for t in frames_of(clip["seconds"], fps):
        values = part_values(action, merged, t, kind="hand")
        hands = {}
        for h in ("r", "l"):
            prev, cur, w, grasp = home[h], None, 1.0, "palm"
            for e in events[h]:
                if t < e["from"]:
                    break
                span = e["to"] - e["from"]
                x = 1.0 if span <= 0 else (t - e["from"]) / span
                if t < e["to"]:
                    cur, w = e["go"], ease(x, e.get("ease", "inout"))
                    grasp = e.get("grasp", grasp)
                    break
                prev, grasp = e["go"], e.get("grasp", grasp)
            a = _resolve(facts, values, prev)
            b = _resolve(facts, values, cur) if cur else a
            hands[h] = {"a": a, "b": b, "w": round(w if cur else 1.0, 4), "grasp": grasp}
        out.append({"t": t, "parts": values, "gun": _pose(clip, t), "hands": hands})
    return {"clip": clip_id, "seconds": clip["seconds"], "fps": fps, "loop": bool(clip.get("loop")), "frames": out,
            "expect": clip.get("expect", [])}
