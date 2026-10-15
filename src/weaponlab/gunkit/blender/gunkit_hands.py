"""Gun Kit's hand clips, in Blender, on Pose Lab's Lab (poselab-mcp): the shared arms holding one gun through each
hand clip of its action. Pose Lab does the arms (two-bone reach, the forearm's roll, the grip search, the clipping,
anatomy and grip checks, the FBX); this script drives it from the timeline: the gun's pose, its parts, each hand's
way from target to target, a carried part riding its hand. Writes under out: clips/<name>.fbx and .pose.json (Pose
Lab's), hands.json (each clip's checks and the carried parts' resolved tracks). Nothing else.

    blender -b --factory-startup -P gunkit_hands.py -- <job.json>
job: {"poselab": "<poselab_mcp/blender>", "arms": {"folder", "arms", "idle", "eye"}, "gun_fbx": "<SK_<name>_Rig.fbx>",
      "facts": {...}, "clips": {"reload": <timeline.hand_clip>, ...}, "tracks": {"reload": <rigplan.tracks of it>},
      "prefix": "A_<name>_Hands_", "out": folder, "grip_steps": 3}

Spaces: gun space (facts, marks) is cm, +Y the muzzle, +Z up, +X the gun's left; the timeline's view places are cm
from the eye with +X the player's LEFT (Gun Kit's), Pose Lab's view has +X the player's right: x changes sign here."""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
sys.path.insert(0, job["poselab"])
import lab as PL  # noqa: E402

OUT = job["out"]
os.makedirs(OUT, exist_ok=True)
facts = job["facts"]
A = job["arms"]
rigs = {"gunkit": {"title": "Gun Kit: %s on the shared arms" % facts["name"], "folder": A["folder"], "arms": A["arms"],
                   "idle": A["idle"], "gun": job["gun_fbx"], "gun_offset": [0.0, 0.0, 0.0], "eye": A["eye"]}}
rigs_file = os.path.join(OUT, "gunkit_rigs.json")
json.dump(rigs, open(rigs_file, "w", encoding="utf-8"), indent=1)
L = PL.Lab(rigs_file, OUT)
L.load_rig("gunkit")
RA = L.rifle_arm
report = {"gun": facts["name"], "clips": {}, "notes": []}
bone_of = {r: p["bone"] for r, p in facts["parts"].items()}
role_of = {p["bone"]: r for r, p in facts["parts"].items()}


def g(v):
    return Vector((v[0], -v[1], v[2])) / 100.0


def gun_cm(v):
    return [v.x * 100.0, -v.y * 100.0, v.z * 100.0]


# --- the gun's parts: a track frame's transforms onto the rifle's bones (gunkit_clips' sums) ----------------------
def pose_parts(bones):
    for name, x in bones.items():
        pb = RA.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_mode = 'QUATERNION'
        lx, ly, lz = x["loc"]
        pb.location = Vector((lx, -ly, lz)) / 100.0
        deg, ax, ay, az = x["rot"]
        axis = Vector((ax, -ay, az))
        pb.rotation_quaternion = Quaternion(axis.normalized() if axis.length > 0 else Vector((0, 1, 0)), -math.radians(deg))
    bpy.context.view_layer.update()


def rest_parts():
    for pb in RA.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def mark_bone(mark, part=None):
    """The rifle bone a mark rides: its part's (or the last of its chain), else Root."""
    chain = part or facts.get("mark_parts", {}).get(mark)
    if isinstance(chain, list):
        chain = chain[-1] if chain else None
    return bone_of.get(chain, "Root") if chain else "Root"


def bone_world(name):
    pb = RA.pose.bones[name]
    return RA.matrix_world @ pb.matrix @ pb.bone.matrix_local.inverted()


def mark_world(mark, part=None, offset=None):
    """A mark's place in the world as the rifle's bones are posed now (it rides its bone)."""
    p = list(facts["marks"][mark])
    if offset:
        p = [p[i] + offset[i] for i in range(3)]
    return bone_world(mark_bone(mark, part)) @ g(p)


def lab_gun(world):
    return list(L._to(world, "gun"))


def palm_r():
    return L._bw(L._n("hand", "r")).translation.lerp(L._bw(L._n("finger", "r", "middle", "01")).translation, 0.5)


# --- the hold: the gun moved so the right palm meets its grip, then each hand's hold searched ---------------------
rest_parts()
L.pose_idle()
shift = palm_r() - mark_world("grip")
L.rifle_rest = Matrix.Translation(shift) @ L.rifle_rest
L._place_rifle()
FINGER_BONES = {s: [pb.name for pb in L.arm.pose.bones if any(pb.name.startswith(f + "_") and pb.name.endswith("_" + s) for f in PL.FINGERS)] for s in ("l", "r")}
GRASPS = {}


_BVH = {}


def surface_normal(world_point, mark=None):
    """The gun's surface normal at a mark: the facts' own (gun space) when given, else the nearest face's, outward."""
    q = RA.matrix_world.to_quaternion()
    n = (facts.get("normals") or {}).get(mark) if mark else None
    if n:
        return (q @ g(n)).normalized()
    if "tree" not in _BVH:
        from mathutils.bvhtree import BVHTree
        dg = bpy.context.evaluated_depsgraph_get()
        ev = L.rifle_mesh.evaluated_get(dg)
        me = ev.to_mesh()
        M = L.rifle_mesh.matrix_world
        _BVH["tree"] = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
    loc, nrm, idx, dist = _BVH["tree"].find_nearest(world_point)
    return nrm.normalized() if nrm is not None else Vector((0.0, 0.0, 1.0))


def palm_frame(side):
    """The palm's middle and the way it faces (toward what the fingers close on)."""
    hn = L._n("hand", side)
    w = L._bw(hn).translation
    mid = L._bw(L._n("finger", side, "middle", "01")).translation
    across, k = L._hand_frame(side)
    return w.lerp(mid, 0.5), (across.cross((mid - w).normalized()) * k).normalized()


def lay_palm(side, at, normal, thickness_cm=1.5):
    """The palm turned to face into the surface (the least turn) and its middle set a palm's thickness off it."""
    hn = L._n("hand", side)
    H = L._bw(hn).copy()
    P, facing = palm_frame(side)
    q = facing.rotation_difference(-normal)
    R = Matrix.Translation(P) @ q.to_matrix().to_4x4() @ Matrix.Translation(-P) @ H
    goal = at + normal * (thickness_cm / 100.0)
    R = Matrix.Translation(goal - P) @ R
    short = L._put_hand(side, Matrix.LocRotScale(R.translation, R.to_quaternion(), L._unit()))
    L._mend_hand(side)
    return short


def grasp(side, mark, part=None, offset=None):
    """The hand's hold on a mark, solved once with the parts as they are now: (the hand against the mark's bone, the
    fingers' turns, whether a hold passed). The palm is first laid on the surface facing into it (the support hand
    slid back along the bore while the arm cannot reach), then Pose Lab's grip search runs from there; its hold is
    kept when one passes, else the laid palm, settled and with its fingers closed."""
    key = (side, mark, part, tuple(offset or ()))
    if key in GRASPS:
        return GRASPS[key]
    L.snapshot("save", "before_grasp")
    hn = L._n("hand", side)
    at = mark_world(mark, part, offset)
    n = surface_normal(at, mark)
    back = (RA.matrix_world.to_quaternion() @ g((0.0, -1.0, 0.0))).normalized()
    short, slid = lay_palm(side, at, n), 0.0
    while short > 0.3 and mark == "support" and slid < 14.0:      # beyond the arm's reach: slide back along the bore
        slid += 2.0
        L.snapshot("load", "before_grasp")
        short = lay_palm(side, at + back * (slid / 100.0), n)
    # settle onto the surface (Pose Lab's own measure of the palm's gap) and close the fingers
    for _ in range(4):
        gr = L.grip(side, hold=False)[side]
        gap = gr.get("palm_gap_cm")
        if gap is None or -0.1 <= gap <= 0.4:
            break
        P, facing = palm_frame(side)
        hw = L._bw(hn)
        L._put_hand(side, Matrix.LocRotScale(hw.translation + facing * ((gap - 0.15) / 100.0), hw.to_quaternion(), L._unit()))
    L._clear_fingers(side)
    L.snapshot("save", "laid")
    found = False
    try:
        target = lab_gun(at + back * (slid / 100.0))
        span = (-8.0, 2.0) if mark == "support" else (-2.0, 2.0)
        r = L.solve_grip(side, target, along=span, steps=int(job.get("grip_steps", 3)), rolls=(0.0, -20.0, 20.0))
        found = r["found"]
    except Exception as e:                          # a part too small or too odd for the grip search
        report["notes"].append("grip %s on %s: %s" % (side, mark, str(e)[:160]))
    if not found:
        L.snapshot("load", "laid")
        report["notes"].append("no hold passed for the %s hand on %s: the palm laid on the surface%s"
                               % (side, mark, (", slid back %.0f cm" % slid) if slid else ""))
    H = L._bw(hn).copy()
    rel = bone_world(mark_bone(mark, part)).inverted() @ H
    fingers = {nm: L.arm.pose.bones[nm].rotation_quaternion.copy() for nm in FINGER_BONES[side]}
    L.snapshot("load", "before_grasp")
    GRASPS[key] = (rel, fingers, found)
    return GRASPS[key]


home_r = grasp("r", "grip")
home_l = grasp("l", facts.get("home_l", "support")) if "support" in facts["marks"] else None
for side, gr in (("r", home_r), ("l", home_l)):
    if gr:
        L._put_hand(side, bone_world("Root") @ gr[0])
        for n, q in gr[1].items():
            L.arm.pose.bones[n].rotation_quaternion = q
bpy.context.view_layer.update()
L.snapshot("save", "hold")
GUN_BONE = L.names["gun"]
G_HOLD = L._bw(GUN_BONE).copy()
RA_HOLD = RA.matrix_world.copy()
PIVOT = mark_world("grip")
report["hold"] = {"right": "found" if home_r[2] else "laid", "left": ("found" if home_l[2] else "laid") if home_l else "none"}
# where the gun hangs on the arms' gun bone: the bolt face (the gun's origin) in that bone's frame at the hold, cm
# (the game's ArmsGunOffset: the gun mesh is attached to the gun bone at that offset)
report["placement"] = {"bolt_face_in_gun_bone_cm": [round(x, 3) for x in lab_gun(RA.matrix_world @ g((0.0, 0.0, 0.0)))],
                       "gun_bone": GUN_BONE}
if job.get("render"):
    report["hold_pictures"] = L.render(views=("eye", "right", "left", "top"), size=(640, 360))
    report["hold_grip"] = L.grip("both", hold=True)
    report["hold_clearance"] = L.clearance(parts="both", top=4)
    report["hold_anatomy"] = L.anatomy("both")
    report["hold_marks_lab"] = {m: [round(x, 2) for x in lab_gun(mark_world(m))] for m in ("grip", "support", "muzzle")}
    report["hold_palm_r_lab"] = [round(x, 2) for x in lab_gun(palm_r())]


def gun_pose(p):
    """The gun bone placed by a timeline pose: turned about the grip (roll about the bore, pitch about the gun's left,
    yaw about its up), moved in the view (Gun Kit's view: +X left)."""
    # the gun's own axes in the world at the hold (the gun bone's axes are the arms rig's, not the gun's)
    q0 = RA_HOLD.to_quaternion()
    ax = lambda v: (q0 @ g(v)).normalized()        # noqa: E731
    # Blender's world is gun space mirrored: a turn's angle changes sign
    q = (Quaternion(ax((0, 0, 1)), math.radians(p.get("yaw", 0.0))) @ Quaternion(ax((1, 0, 0)), -math.radians(p.get("pitch", 0.0)))
         @ Quaternion(ax((0, 1, 0)), -math.radians(p.get("roll", 0.0))))
    mv = p.get("move", [0.0, 0.0, 0.0])
    move = (PL.VIEW_RIGHT * -mv[0] + PL.VIEW_FWD * mv[1] + PL.VIEW_UP * mv[2]) / 100.0
    M = Matrix.Translation(move) @ Matrix.Translation(PIVOT) @ q.to_matrix().to_4x4() @ Matrix.Translation(-PIVOT) @ G_HOLD
    L._set_world(GUN_BONE, Matrix.LocRotScale(M.translation, M.to_quaternion(), L._unit()))
    L._place_rifle()


def free_mark(mark):
    """True when the mark rides a free part (a magazine): its place comes from the timeline, not from the bone, which
    may be riding the very hand that reaches for it."""
    chain = facts.get("mark_parts", {}).get(mark)
    chain = chain[-1] if isinstance(chain, list) and chain else chain
    return bool(chain) and facts["parts"].get(chain, {}).get("kind") == "free"


def target_matrix(side, tgt, current):
    """A timeline target as the hand's world matrix (and the finger turns, or None to keep them)."""
    if tgt["space"] == "view":
        v = tgt["point"]
        at = L._from([-v[0], v[1], v[2]], "view")
        return Matrix.LocRotScale(at, current.to_quaternion(), current.to_scale()), None
    if tgt["space"] == "hand" or tgt["point"] is None:
        return current.copy(), None
    name = tgt["name"]
    mark = name if name in facts["marks"] else ("mag_grab" if name in facts["parts"] and "mag_grab" in facts["marks"] else None)
    if mark is None:
        return Matrix.LocRotScale(RA.matrix_world @ g(tgt["point"]), current.to_quaternion(), current.to_scale()), None
    rel, fingers, _ = grasp(side, mark)
    # the mark's frame: its bone as posed, or the gun at rest for a free part's mark (its place is the timeline's)
    B = RA.matrix_world if free_mark(mark) else bone_world(mark_bone(mark))
    H = B @ rel
    # the target moved off the mark (an offset, a free part out of its seat): the same hold moved with it
    d = (RA.matrix_world @ g(tgt["point"])) - (B @ g(facts["marks"][mark]))
    return Matrix.Translation(d) @ H, fingers


def blend(Ma, Mb, w):
    loc = Ma.translation.lerp(Mb.translation, w)
    rot = Ma.to_quaternion().slerp(Mb.to_quaternion(), w)
    return Matrix.LocRotScale(loc, rot, L._unit())


if job.get("render"):
    def dirs():
        q = RA.matrix_world.to_quaternion()
        return {"forward": [round(c, 3) for c in (q @ g((0, 1, 0))).normalized()], "right": [round(c, 3) for c in (q @ g((-1, 0, 0))).normalized()]}
    report["axes_hold"] = dirs()
    gun_pose({"roll": 30.0})
    report["axes_roll30"] = dirs()
    gun_pose({"pitch": 30.0})
    report["axes_pitch30"] = dirs()
    gun_pose({"yaw": 30.0})
    report["axes_yaw30"] = dirs()
    gun_pose({})
    report["view_axes"] = {"right": list(PL.VIEW_RIGHT), "forward": list(PL.VIEW_FWD), "up": list(PL.VIEW_UP)}

# --- every hold the clips need, solved once with the parts at rest ----------------------------------------------
need = set()
for clip in job["clips"].values():
    for fr in clip["frames"]:
        for side, h in fr["hands"].items():
            for k in ("a", "b"):
                tg = h[k]
                if tg["space"] != "gun" or tg["point"] is None:
                    continue
                n = tg["name"]
                mk = n if n in facts["marks"] else ("mag_grab" if n in facts["parts"] and "mag_grab" in facts["marks"] else None)
                if mk:
                    need.add((side, mk))
L.snapshot("load", "hold")
rest_parts()
for side, mk in sorted(need):
    grasp(side, mk)
L.snapshot("load", "hold")
report["holds"] = {"%s:%s" % (k[0], k[1]): ("found" if v[2] else "laid") for k, v in GRASPS.items()}

# --- the clips -------------------------------------------------------------------------------------------------
for cid, clip in job["clips"].items():
    tr = job["tracks"].get(cid)
    tframes = {round(f["t"], 5): f["bones"] for f in (tr["frames"] if tr else [])}
    name = job.get("prefix", "A_%s_Hands_" % facts["name"]) + cid
    L.snapshot("load", "hold")
    L.record_clip("start", name, fps=clip["fps"])
    carrying = {}            # part -> (hand, the part's bone against the hand)
    resolved = []
    for fr in clip["frames"]:
        t = round(fr["t"], 5)
        gun_pose(fr["gun"])
        rest_parts()
        if t in tframes:
            pose_parts(tframes[t])
        hands_now = {}
        for side in ("r", "l"):
            h = fr["hands"][side]
            hn = L._n("hand", side)
            cur = L._bw(hn).copy()
            Ma, fa = target_matrix(side, h["a"], cur)
            Mb, fb = target_matrix(side, h["b"], cur)
            H = blend(Ma, Mb, h["w"])
            L._put_hand(side, H)
            for n in FINGER_BONES[side]:
                qa = (fa or {}).get(n)
                qb = (fb or {}).get(n)
                if qa is not None and qb is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qa.slerp(qb, h["w"])
                elif qb is not None and h["w"] > 0.5 or qa is None and qb is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qb
                elif qa is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qa
            bpy.context.view_layer.update()
            hands_now[side] = L._bw(hn).copy()
        # carried parts ride their hand: taken where they are when the carry starts
        frame_parts = {}
        for role, v in fr["parts"].items():
            if isinstance(v, dict) and v.get("follow"):
                side = v["follow"]
                bone = bone_of[role]
                pb = RA.pose.bones[bone]
                if role not in carrying:
                    carrying[role] = (side, hands_now[side].inverted() @ (RA.matrix_world @ pb.matrix))
                side_, rel = carrying[role]
                Wp = hands_now[side_] @ rel
                pb.matrix = RA.matrix_world.inverted() @ Wp
                bpy.context.view_layer.update()
                basis = pb.matrix_basis
                q = basis.to_quaternion()
                axis, ang = q.to_axis_angle()
                frame_parts[role] = {"at": gun_cm(basis.translation), "rot": [-math.degrees(ang), axis.x, -axis.y, axis.z]}
            else:
                carrying.pop(role, None)
                frame_parts[role] = v
        resolved.append({"t": fr["t"], "parts": frame_parts})
        L.record_clip("key", seconds=fr["t"])
    L.record_clip("stop")
    saved = L.save_clip(name, formats=("pose.json", "fbx"), root_name="root")
    try:
        cs = L.check_set(name, ignore=["palm*"], sides="both")
    except Exception as e:
        cs = {"error": str(e)[:300]}
    expects = []
    for x in clip.get("expect", []):
        if "visible" in x:
            ts = x["at"] if isinstance(x["at"], list) else [x["at"], x["at"]]
            t = (ts[0] + ts[1]) / 2.0
            L.pose_clip(name, t)
            fr = min(clip["frames"], key=lambda f: abs(f["t"] - t))
            gun_pose(fr["gun"])
            rest_parts()
            if round(fr["t"], 5) in tframes:
                pose_parts(tframes[round(fr["t"], 5)])
            vis = L.visible(lab_gun(mark_world(x["visible"])))
            fe = L.faces_eye(lab_gun(mark_world(x["visible"])), normal=[g for g in facts.get("normals", {}).get(x["visible"], [-1.0, 0.0, 0.0])])
            expects.append({"expect": x, "visible": vis, "faces_eye": fe})
            if job.get("render"):
                expects[-1]["pictures"] = L.render(views=("eye", "right"), size=(640, 360))
    report["clips"][cid] = {"clip": name, "written": saved["written"], "frames": saved["frames"], "checks": cs,
                            "expect": expects, "resolved": {"clip": cid, "seconds": clip["seconds"], "fps": clip["fps"], "frames": resolved}}
json.dump(report, open(os.path.join(OUT, "hands.json"), "w", encoding="utf-8"), indent=1, default=str)
print("GUNKIT HANDS: %s, %d clips, hold %s" % (facts["name"], len(report["clips"]), report["hold"]))
