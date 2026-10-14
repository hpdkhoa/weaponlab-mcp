"""A complete probe for a toy game, written to the probe contract (docs/PROBE_CONTRACT.md). It is the template for
your own: read the job, play each action, measure, write the rows and the dumps.

The toy game has two weapons, each with a bug that shows in the numbers:
- Demo_Rifle: its model sits 4 cm too high on the arms (game.json "Demo_Rifle.offset"), so the left palm misses the
  handguard by 4 cm. Tuning "offset" to [0, 0, 0] fixes it.
- Demo_Knife: its hilt runs forward out of the fist (+Y) instead of along the fist's channel (+X). Rig Lab's fist
  measure finds the turn ("rot") and the move ("offset") that lay it in; tune them to try the fix.

    python demo_probe.py <job.json>"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = json.loads((HERE / "game.json").read_text(encoding="utf-8"))


def box(c, size):
    """A box's 12 triangles around centre c (cm)."""
    (x, y, z), (a, b, h) = c, (s / 2.0 for s in size)
    v = [(x + i * a, y + j * b, z + k * h) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [(v[a], v[b], v[c]) for a, b, c, d in q] + [(v[a], v[c], v[d]) for a, b, c, d in q]


def turn(m, p):
    return tuple(sum(m[i][k] * p[k] for k in range(3)) for i in range(3))


def model(wid, d):
    """The weapon's pieces in gun space: [(role, component, bone, triangles)], after its definition's offset and turn."""
    off, rot = d.get("offset", [0, 0, 0]), d.get("rot", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    move = lambda tris: [tuple(tuple(a + o for a, o in zip(turn(rot, p), off)) for p in t) for t in tris]
    if wid == "Demo_Rifle":
        return [("gun", "Rifle", "-", move(box((0, 10, 0), (4, 40, 6)))),        # receiver and handguard
                ("gun", "Rifle", "-", move(box((0, 40, 1), (1.5, 20, 1.5)))),    # barrel
                ("part", "Mag", "Mag", move(box((0, 4, -9), (2.4, 6, 12))))]     # magazine under the well
    # the knife: hilt from the pommel at y -6 to y 5, blade to y 25, along +Y before its turn
    return [("gun", "Knife", "-", move(box((0, -0.5, 0), (2.2, 11, 2.6)) + box((0, 15, 0), (0.5, 20, 3))))]


def arms():
    """The hands in gun space: the left palm under the handguard, the right fist's channel along +X at the origin."""
    out = [("hand_l", box((0, 25, -4), (7, 9, 2.5)))]
    out += [("hand_r", box((0, 0, -2.5), (8, 9, 2))), ("middle_01_r", box((0, 0, 3), (2, 2, 2))),
            ("middle_02_r", box((0, 0, 4.5), (2, 2, 2))), ("middle_03_r", box((0, 0, 2), (2, 2, 2))),
            ("index_01_r", box((3.5, 0, 0), (2, 2, 2))), ("pinky_01_r", box((-3.5, 0, 0), (2, 2, 2))),
            ("thumb_03_r", box((3, -2.5, 2), (1.5, 1.5, 1.5)))]
    return out


def dump(path, wid, d):
    lines = ["# demo probe parts: gun space, cm", "# eye 0.0 -20.0 12.0"]
    n = 1
    groups = [("arms", "Arms", "/Demo/Arms", b, t) for b, t in arms()] + [(r, c, "/Demo/" + wid, b, t) for r, c, b, t in model(wid, d)]
    for role, comp, asset, bone, tris in groups:
        lines.append("g %s|%s|%s|%s" % (role, comp, asset, bone))
        for t in tris:
            lines += ["v %.3f %.3f %.3f" % p for p in t]
        for _ in tris:
            lines.append("f %d %d %d" % (n, n + 1, n + 2))
            n += 3
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    if job.get("contract", "weaponlab-probe/1") != "weaponlab-probe/1":
        raise SystemExit("unknown contract %s" % job.get("contract"))
    rows, notes = [], []
    if job.get("overrides"):
        notes.append("the demo game has no assets: overrides ignored")
    if job.get("shots"):
        notes.append("the demo game draws nothing: no screenshots")
    for w in job["weapons"]:
        wid = w["id"] + ("@" + w["tag"] if w.get("tag") else "")
        d = dict(GAME.get(w["id"], {}))
        for k, v in (w.get("tune") or {}).items():
            if k in d:
                d[k] = v
                notes.append("%s: %s tuned" % (wid, k))
            else:
                notes.append("%s: no field %s" % (wid, k))
        pieces = model(w["id"], d)
        tris = [t for _, _, _, ts in pieces for t in ts]
        hands = dict(arms())
        for a in w["actions"]:
            row = lambda m, v, note=None: rows.append(dict({"weapon": wid, "action": a["name"], "metric": m, "value": v}, **({"note": note} if note else {})))
            row("hands.arms_shown", 1)
            row("events.played", 1)
            if w["id"] == "Demo_Rifle":
                # the palm's top against the handguard's underside, where the palm is (in or out of it, both wrong)
                palm_top = max(p[2] for t in hands["hand_l"] for p in t)
                under = min(p[2] for t in tris for p in t if 20.0 <= p[1] <= 30.0)
                row("hands.l_gap_cm", round(abs(under - palm_top), 3))
                low = -min(p[2] for t in tris for p in t)
                if job.get("view", True) and a["name"] == "idle":
                    row("view.cover_lower_left", round(min(1.0, 0.05 + 0.01 * low), 3))
                    row("view.hand_l_shown", round(max(0.0, 0.3 - 0.02 * max(0.0, low - 15)), 3))
            for t in a.get("at", []):
                if job.get("parts"):
                    dump(Path(job["parts"]) / ("%s_%s_%.2f.obj" % (wid, a["name"], t)), w["id"], d)
    Path(job["out"]).write_text(json.dumps({"rows": rows, "notes": notes}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
