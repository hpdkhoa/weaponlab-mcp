"""Gun Kit's hand clips, in Blender, on Pose Lab's Lab (poselab-mcp): the shared arms holding one gun through each
hand clip of its action. Pose Lab does the arms (two-bone reach, the forearm's roll, the grip search, the clipping,
anatomy and grip checks, the FBX); this script drives it from the timeline: the gun's pose, its parts, each hand's
way from target to target, a carried part riding its hand. Writes under out: clips/<name>.fbx and .pose.json (Pose
Lab's), hands.json (each clip's checks and the carried parts' resolved tracks). Nothing else.

    blender -b --factory-startup -P gunkit_hands.py -- <job.json>
job: {"poselab": "<poselab_mcp/blender>", "arms": {"folder", "arms", "idle", "eye"}, "gun_fbx": "<SK_<name>_Rig.fbx>",
      "facts": {...}, "clips": {"reload": <timeline.hand_clip>, ...}, "tracks": {"reload": <rigplan.tracks of it>},
      "prefix": "A_<name>_Hands_", "out": folder, "grip_steps": 3,
      "style": <weaponlab-gripstyle/1 or null>, "character": <weaponlab-character/1 or null>, "glove_cm": 0.15}

A grip style lays each hand on its contact's face, poses its fingers (straight, or wrapped until they meet the gun a
glove's thickness off), puts the thumbs back in their hinge's plane, and puts the trigger finger on the trigger in
the style's trigger clips. The character's glove thickens the palm and every finger: the clearance allowed shrinks
by as much.

Spaces: gun space (facts, marks) is cm, +Y the muzzle, +Z up, +X the gun's left; the timeline's view places are cm
from the eye with +X the player's LEFT (Gun Kit's), Pose Lab's view has +X the player's right: x changes sign here."""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from weaponlab.gunkit import motion as MO  # noqa: E402
from weaponlab.gunkit import reference as REFH  # noqa: E402

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
sys.path.insert(0, job["poselab"])
import lab as PL  # noqa: E402

OUT = job["out"]
os.makedirs(OUT, exist_ok=True)
facts = job["facts"]
A = job["arms"]
rigs = {"gunkit": {"title": "Gun Kit: %s on the shared arms" % facts["name"], "folder": A["folder"], "arms": A["arms"],
                   "idle": A["idle"], "gun": job["gun_fbx"], "gun_offset": [0.0, 0.0, 0.0], "eye": A["eye"],
                   "styled": bool(job.get("character")),
                   # the clearance capsules fitted to the arms' own skin (Pose Lab measures it on the rest pose)
                   "fit_capsules": bool(job.get("fit_capsules", True)),
                   # the thumb's hinges fixed in its own ray (they roll with the metacarpal, as an opposed thumb's do)
                   "thumb_hinge": job.get("thumb_hinge", "ray")}}            # the character's colours and the gun's finishes
_be = os.path.join(A["folder"] if os.path.isabs(A["folder"]) else os.path.join(OUT, A["folder"]), "bone_edits.json")
if os.path.exists(_be):
    rigs["gunkit"]["bone_edits"] = "bone_edits.json"          # the arms copy's bone edits (Tools/blender/slim_arms.py)
rigs_file = os.path.join(OUT, "gunkit_rigs.json")
json.dump(rigs, open(rigs_file, "w", encoding="utf-8"), indent=1)
L = PL.Lab(rigs_file, OUT)
# The run's time budget (10 minutes unless the job says otherwise). Each phase gets a share and stops on time,
# keeping its best so far: the stance search a quarter, the right hand to 55%, the left to 80%, the clips, the
# checks and the render the rest. The timing file is written at every phase, so a stopped run still shows its
# time. What a budget cut short is listed in the report (budget_cut).
import time as _time
T0 = _time.time()
BUDGET = float(job.get("time_budget_s", 600))


def by(share):
    return T0 + share * BUDGET


L.steps.out_path = os.path.join(OUT, "steps.json")
L.steps.meta = {"run": "gunkit hands", "budget_s": BUDGET}
L.steps.phase("load the arms and the gun")
L.load_rig("gunkit")
RA = L.rifle_arm
report = {"gun": facts["name"], "clips": {}, "notes": []}
if hasattr(L, "_fitted_radii") and L._fitted_radii():
    report["capsules_cm"] = {k: round(v * 100.0, 2) for k, v in L._fitted_radii().items()}
STYLE = job.get("style")
CHAR = job.get("character")
GLOVE = float(job.get("glove_cm", 0.0))
# the palm's half thickness: the capsule fitted to the arms' skin when Pose Lab fits them, else 1.5 cm; the glove on it
_FIT = L._fitted_radii() if hasattr(L, "_fitted_radii") else None
PALM_CM = ((_FIT or {}).get("palm", 0.015) * 100.0) + GLOVE
FACE = {h["contact"]["mark"]: h["contact"]["face"] for h in (STYLE or {}).get("hands", {}).values()}
TOWARD = {h["contact"]["mark"]: h["contact"].get("fingers_toward") for h in (STYLE or {}).get("hands", {}).values()}
for _h in (STYLE or {}).get("hands", {}).values():
    for _m, _x in (_h.get("holds") or {}).items():
        FACE.setdefault(_m, _x["face"])               # a working hold's face (the slide's top for a rack)
        TOWARD.setdefault(_m, _x.get("fingers_toward"))
report["style"] = STYLE["id"] if STYLE else None
report["character"] = CHAR["id"] if CHAR else None
report["glove_cm"] = GLOVE
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


# --- the character's gloves: the hands' surface thickened and coloured (the checks count the glove already) --------
def put_gloves():
    cov = (CHAR or {}).get("covering") or {}
    if cov.get("kind") not in ("full_gloves", "fingerless_gloves") or not GLOVE:
        return None
    col = ((CHAR.get("finish") or {}).get("colors") or {}).get("glove", [0.23, 0.26, 0.2])
    mat = bpy.data.materials.new("M_glove_" + CHAR["id"])
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    mat.diffuse_color = (*col, 1.0)
    hand_bones = {L._n("hand", sd) for sd in ("l", "r")} | set(FINGER_BONES["l"]) | set(FINGER_BONES["r"])
    if cov["kind"] == "fingerless_gloves":
        hand_bones = {b for b in hand_bones if not b.endswith(("02_l", "03_l", "02_r", "03_r"))}
    done = 0
    for ob in L.meshes:
        groups = {vg.index: vg.name for vg in ob.vertex_groups}
        me = ob.data
        gloved = set()
        for v in me.vertices:
            w_hand = sum(gr.weight for gr in v.groups if groups.get(gr.group) in hand_bones)
            w_all = sum(gr.weight for gr in v.groups) or 1.0
            if w_hand / w_all >= 0.5:
                gloved.add(v.index)
        if not gloved:
            continue
        me.calc_normals() if hasattr(me, "calc_normals") else None
        unit = 1.0 / (ob.matrix_world.to_scale().x or 1.0)          # the glove's thickness in the mesh's own units
        for i in gloved:
            v = me.vertices[i]
            v.co = v.co + v.normal * (GLOVE / 100.0) * unit
        sleeve_col = ((CHAR.get("finish") or {}).get("colors") or {}).get("sleeve", [0.24, 0.26, 0.2])
        sleeve = bpy.data.materials.get("M_sleeve_" + CHAR["id"]) or bpy.data.materials.new("M_sleeve_" + CHAR["id"])
        sleeve.diffuse_color = (*sleeve_col, 1.0)
        me.materials.append(mat)
        k = len(me.materials) - 1
        me.materials.append(sleeve)
        ks = len(me.materials) - 1
        for poly in me.polygons:                      # the hands gloved, the rest of the arms in the character's sleeves
            poly.material_index = k if sum(1 for i in poly.vertices if i in gloved) * 2 >= len(poly.vertices) else ks
        me.update()
        done += len(gloved)
    return {"vertices": done, "thickness_cm": GLOVE, "color": col, "material": mat.name}



# --- the hold: the gun moved so the right palm meets its grip, then each hand's hold searched ---------------------
L.steps.phase("gloves, body size, style setup")
rest_parts()
L.pose_idle()
shift = palm_r() - mark_world("grip")
L.rifle_rest = Matrix.Translation(shift) @ L.rifle_rest
L._place_rifle()
FINGER_BONES = {s: [pb.name for pb in L.arm.pose.bones if any(pb.name.startswith(f + "_") and pb.name.endswith("_" + s) for f in PL.FINGERS)] for s in ("l", "r")}
if job.get("body_ranges") and hasattr(L, "body_size"):
    # the bare arms against human sizes before anything is posed on them: a bone or a part of the skin no adult has
    # fails the run (the gloves come after: a glove is not the body)
    report["body_size"] = L.body_size("both", ranges=job["body_ranges"])
    if not report["body_size"]["ok"]:
        report["notes"].append("the arms are not of human size: " + "; ".join(
            report["body_size"][sd]["bad"][0] for sd in ("l", "r") if report["body_size"].get(sd, {}).get("bad")))
report["gloves"] = put_gloves()
GRASPS = {}


_BVH = {}


def surface_normal(world_point, mark=None):
    """The gun's surface normal at a mark: the facts' own (gun space) when given, else the nearest face's, outward."""
    q = RA.matrix_world.to_quaternion()
    n = FACE.get(mark) if mark else None                         # the grip style's face for its contact marks
    n = n or ((facts.get("normals") or {}).get(mark) if mark else None)
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


def fingers_way(side):
    hn = L._n("hand", side)
    return (L._bw(L._n("finger", side, "middle", "01")).translation - L._bw(hn).translation).normalized()


def lay_palm(side, at, normal, thickness_cm=None, toward=None):
    """The palm turned to face into the surface (the least turn) and its middle set a palm's thickness off it."""
    thickness_cm = PALM_CM if thickness_cm is None else thickness_cm
    hn = L._n("hand", side)
    H = L._bw(hn).copy()
    P, facing = palm_frame(side)
    q = facing.rotation_difference(-normal)
    R = Matrix.Translation(P) @ q.to_matrix().to_4x4() @ Matrix.Translation(-P) @ H
    if toward is not None:
        # then turned about the face's normal so the fingers point the hold's way (a palm on a slide's top could
        # face its fingers anywhere; the forearm wrings past its range if they point back)
        fw = (R.to_quaternion() @ (H.to_quaternion().inverted() @ fingers_way(side))).normalized()
        want = (toward - normal * toward.dot(normal)).normalized()
        have = (fw - normal * fw.dot(normal)).normalized()
        if want.length > 1e-6 and have.length > 1e-6:
            q2 = have.rotation_difference(want)
            R = Matrix.Translation(P) @ q2.to_matrix().to_4x4() @ Matrix.Translation(-P) @ R
    goal = at + normal * (thickness_cm / 100.0)
    R = Matrix.Translation(goal - P) @ R
    short = L._put_hand(side, Matrix.LocRotScale(R.translation, R.to_quaternion(), L._unit()))
    L._mend_hand(side)
    return short


def settle(side):
    """The palm onto the surface (Pose Lab's own measure of its gap) and the fingers closed."""
    hn = L._n("hand", side)
    for _ in range(4):
        gr = L.grip(side, hold=False)[side]
        gap = gr.get("palm_gap_cm")
        if gap is None or -0.1 <= gap <= 0.4:
            break
        P, facing = palm_frame(side)
        hw = L._bw(hn)
        L._put_hand(side, Matrix.LocRotScale(hw.translation + facing * ((gap - 0.15) / 100.0), hw.to_quaternion(), L._unit()))
    L._clear_fingers(side)


# --- the grip style's fingers --------------------------------------------------------------------------------------
_FL = L._limits()[1]
_TL = L._thumb_limits()
DIGITS = ("index", "middle", "ring", "pinky")


def _curl(side, fi, j):
    return L._finger_report(side, _FL)[0]["%s_%s" % (fi, j)][0]


def set_joint(side, fi, j, target):
    """One finger joint turned about the finger's own hinge to a curl (degrees), the way that gets closer."""
    cur = _curl(side, fi, j)
    if abs(cur - target) < 0.5:
        return
    n = L._n("finger", side, fi, j)
    head = L._bw(n).translation.copy()
    M = L._bw(n)
    planes = L._finger_report(side, _FL)[2]
    for sg in (1.0, -1.0):
        L._turn_about(n, planes[fi], (target - cur) * sg, head)
        if abs(_curl(side, fi, j) - target) < abs(cur - target):
            return
        L._set_world(n, M)


def set_finger(side, fi, curls):
    for j, c in zip(("01", "02", "03"), curls):
        set_joint(side, fi, j, c)


def finger_gap(side, fi, tree):
    """The finger's skin to the gun's surface, the closest of its three segments (cm; under 0 when inside)."""
    best = None
    for name, a, b, r in L._segments(side):
        if not name.startswith(fi):
            continue
        n = max(2, int((b - a).length / 0.003))
        for i in range(n + 1):
            q, dq = tree.nearest(a.lerp(b, i / n))
            if q is None:
                continue
            gap = (dq - r) * 100.0
            best = gap if best is None else min(best, gap)
    return 99.0 if best is None else best


def wrap(side, fi, max_curl, tree):
    """The finger opened, then closed a step at a time until its skin is a glove's thickness off the gun (or at its
    most curl); a step that goes into the gun is taken back."""
    set_finger(side, fi, [4.0, 4.0, 4.0])
    prev = [4.0, 4.0, 4.0]
    for k in range(1, 21):
        c = [4.0 + (m - 4.0) * k / 20.0 for m in max_curl]
        set_finger(side, fi, c)
        gap = finger_gap(side, fi, tree)
        if gap <= GLOVE + 0.05:
            if gap < GLOVE - 0.1:
                set_finger(side, fi, prev)
            return
        prev = c


def set_thumb(side, b2, b3):
    """The thumb's knuckle and end joint bent (degrees) about their own hinges, then turned back into the hinges'
    plane (the arms' template thumb is bent out of it, which every hold kept)."""
    for j, target in (("02", b2), ("03", b3)):
        tr, _b, axes = L._thumb_report(side, _TL)
        if "thumb_" + j not in tr or j not in axes:
            continue
        cur = tr["thumb_" + j][0]
        n = L._n("finger", side, "thumb", j)
        head, M = L._bw(n).translation.copy(), L._bw(n)
        for sg in (1.0, -1.0):
            L._turn_about(n, axes[j], (target - cur) * sg, head)
            if abs(L._thumb_report(side, _TL)[0]["thumb_" + j][0] - target) < abs(cur - target):
                break
            L._set_world(n, M)
    for _ in range(3):
        for j in ("02", "03"):
            tr, _b, axes = L._thumb_report(side, _TL)
            if "thumb_" + j not in tr or j not in axes:
                continue
            side_deg = tr["thumb_" + j][1]
            if abs(side_deg) < 3.0:
                continue
            n = L._n("finger", side, "thumb", j)
            head = L._bw(n).translation.copy()
            tip = L._bw(L._n("finger", side, "thumb", "03")).translation if j == "02" else L._finger_tip("thumb", side)
            w = (tip - head).cross(axes[j])
            if w.length < 1e-9:
                continue
            w.normalize()
            M = L._bw(n)
            for sg in (1.0, -1.0):
                L._turn_about(n, w, -side_deg * sg, head)
                if abs(L._thumb_report(side, _TL)[0]["thumb_" + j][1]) < abs(side_deg):
                    break
                L._set_world(n, M)


def thumb_clear(side, tree, steps=16):
    """A thumb pressed into the gun lifted off it: one of its three joints turned 3 degrees at a time, the joint and
    the way that open the gap most, until its skin is a glove's thickness off the surface; a turn that breaks a thumb
    rule is not taken."""
    for _ in range(steps):
        gap = finger_gap(side, "thumb", tree)
        if gap >= GLOVE - 0.02:
            return gap
        across, k = L._hand_frame(side)
        best = None
        for j in ("01", "02", "03"):
            n = L._n("finger", side, "thumb", j)
            head = L._bw(n).translation.copy()
            tip = L._finger_tip("thumb", side)
            d = (tip - head)
            if d.length < 1e-9:
                continue
            d.normalize()
            M = L._bw(n)
            for axis in (across, d.cross(across).normalized(), d.cross(d.cross(across)).normalized()):
                for sg in (1.0, -1.0):
                    L._turn_about(n, axis, 3.0 * sg, head)
                    g2 = finger_gap(side, "thumb", tree)
                    ok = not L._thumb_report(side, _TL)[1]
                    if ok and (best is None or g2 > best[0]):
                        best = (g2, n, axis, sg, head)
                    L._set_world(n, M)
        if best is None or best[0] <= gap + 1e-4:
            return gap
        L._turn_about(best[1], best[2], 3.0 * best[3], best[4])
    return finger_gap(side, "thumb", tree)


def end_joints_flat(side):
    """Each finger's end joint turned back into its finger's plane (a wrap or a blend can twist it; Pose Lab's mend
    straightens the knuckle and the middle joint only)."""
    for _ in range(2):
        rep_, _b, planes = L._finger_report(side, _FL)
        for fi in DIGITS:
            side_deg = rep_["%s_03" % fi][1]
            lim = _FL["03"][2]
            if abs(side_deg) < lim - 3.0:
                continue
            n = L._n("finger", side, fi, "03")
            head = L._bw(n).translation.copy()
            axis = (L._finger_tip(fi, side) - head).cross(planes[fi])
            if axis.length < 1e-9:
                continue
            axis.normalize()
            M = L._bw(n)
            for sg in (1.0, -1.0):
                L._turn_about(n, axis, -side_deg * 0.8 * sg, head)
                if abs(L._finger_report(side, _FL)[0]["%s_03" % fi][1]) < abs(side_deg):
                    break
                L._set_world(n, M)


def pose_digits(side, h, trigger, tree, fingers=None):
    fingers = fingers or h["fingers"]
    for fi in DIGITS:
        f = fingers.get(fi)
        if trigger and fi == "index" and h.get("trigger"):
            f = h["trigger"]
        if not f or f["pose"] == "rest":
            continue
        if f["pose"] == "straight":
            set_finger(side, fi, f["curl"])
        elif f["pose"] == "wrap":
            wrap(side, fi, f["max_curl"], tree)
    t = fingers.get("thumb")
    if t and t["pose"] == "straight":
        set_thumb(side, t["curl"][1], t["curl"][2])
    elif t and t["pose"] == "wrap":
        thumb_wrap(side, t["max_curl"], tree)
    elif t and t["pose"] == "to":
        thumb_to(side, RA.matrix_world @ g(t["point"]), tree)
    L._mend_hand(side)                                  # the joints back in range and in their fingers' planes
    end_joints_flat(side)
    thumb_clear(side, tree)


def thumb_wrap(side, max_curl, tree):
    """The thumb's knuckle and end joint closed a step at a time (in their hinges' plane) until its skin is a
    glove's thickness off the gun, or at its most bend; a step into the gun is taken back."""
    prev = (6.0, 4.0)
    set_thumb(side, *prev)
    for k in range(1, 13):
        b = (6.0 + (max_curl[1] - 6.0) * k / 12.0, 4.0 + (max_curl[2] - 4.0) * k / 12.0)
        set_thumb(side, *b)
        gap = finger_gap(side, "thumb", tree)
        if gap <= GLOVE + 0.05:
            if gap < GLOVE - 0.1:
                set_thumb(side, *prev)
            return
        prev = b


def thumb_to(side, target, tree, rounds=12, step_deg=8.0):
    """The thumb's tip brought to a rest point: each of its joints, tip to base, turned about its head toward the
    point by at most step_deg a round (cyclic coordinate descent); a turn that breaks a thumb rule or puts the thumb
    deeper in the gun is undone. Returns the tip's distance left, cm."""
    rules0 = len(L._thumb_report(side, _TL)[1])
    for _ in range(rounds):
        moved = False
        for j in ("03", "02", "01"):
            n = L._n("finger", side, "thumb", j)
            head = L._bw(n).translation.copy()
            tip = L._finger_tip("thumb", side)
            a, b = (tip - head), (target - head)
            if a.length < 1e-6 or b.length < 1e-6:
                continue
            axis = a.cross(b)
            if axis.length < 1e-9:
                continue
            ang = min(step_deg, math.degrees(a.angle(b)))
            if ang < 0.5:
                continue
            M = L._bw(n)
            gap0 = finger_gap(side, "thumb", tree)
            L._turn_about(n, axis.normalized(), ang, head)
            if len(L._thumb_report(side, _TL)[1]) > rules0 or finger_gap(side, "thumb", tree) < min(gap0, GLOVE) - 0.05:
                L._set_world(n, M)
                continue
            moved = True
        if not moved:
            break
    return (L._finger_tip("thumb", side) - target).length * 100.0


def apply_hold(side, mark):
    """A working hold's fingers (the support hand racking the slide, seating a magazine)."""
    h = (STYLE or {}).get("hands", {}).get(side) or {}
    x = (h.get("holds") or {}).get(mark)
    if not x:
        return False
    tree = L._tree()
    pose_digits(side, h, False, tree, fingers=x["fingers"])
    L._clear_fingers(side)
    bpy.context.view_layer.update()
    return True


SOFT = {c["segment"]: c["max_cm"] for c in (STYLE or {}).get("soft_contacts", [])}


def deepest_press(side, tree):
    """The hand's deepest press into the gun that the style does not allow, and the way out of it: (excess cm, world
    direction from the gun's surface out through the body part). A soft contact counts past 80 percent of its own
    most; the thumb's middle and end are the thumb's own (thumb_clear); the forearm and the palm are left out."""
    allowed = max(0.0, 0.2 - GLOVE)
    best = None
    for name, a, b, r in L._segments(side):
        if name.startswith(("forearm", "palm", "thumb2", "thumb3")) and not any(name.startswith(k) for k in SOFT):
            continue
        lim = next((0.8 * v for k, v in SOFT.items() if name.startswith(k)), allowed)
        n = max(2, int((b - a).length / 0.003))
        for i in range(n + 1):
            pt = a.lerp(b, i / n)
            q, dq = tree.nearest(pt)
            if q is None or dq >= r:
                continue
            depth = (r - dq) * 100.0
            excess = depth - lim
            if excess > 0 and (best is None or excess > best[0]):
                out = (pt - q) if dq >= 0.0 else (q - pt)
                if out.length > 1e-9:
                    best = (excess, out.normalized(), name)
    return best


def apply_style(side, trigger=False, normal=None):
    """The style's fingers for this hand on its contact: each digit straight or wrapped; the trigger finger on the
    trigger when asked. Then the hand backed off along the contact's face while any of it (the ball of the thumb, the
    palm, a knuckle) sits deeper in the gun than the glove allows, the fingers closed again each time."""
    h = (STYLE or {}).get("hands", {}).get(side)
    if not h:
        return
    tree = L._tree()
    allowed = max(0.0, 0.2 - GLOVE)
    hn = L._n("hand", side)
    pose_digits(side, h, trigger, tree)
    if h.get("thumb_rest") and not trigger:
        tr = h["thumb_rest"]
        left = thumb_to(side, mark_world(tr["mark"], offset=tr["offset"]), tree)
        thumb_clear(side, tree)
        report.setdefault("thumb_rest_cm", {})[side] = round(left, 2)
    if normal is not None and not trigger:
        # each press the style does not allow undone along its own way out, by its excess (at most 0.8 cm), the
        # fingers closed again after each move
        # (off: moving the support hand out of a press put the back of its index into the gun; the support fingers
        # need the firing hand's fingers as something to wrap over, which Pose Lab's tests do not hold yet)
        for _ in range(3 if side in tuple(job.get("press_sides", ())) else 0):
            pr = deepest_press(side, tree)
            if pr is None:
                break
            hw = L._bw(hn)
            L._put_hand(side, Matrix.LocRotScale(hw.translation + pr[1] * (min(pr[0] + 0.03, 0.8) / 100.0), hw.to_quaternion(), L._unit()))
            bpy.context.view_layer.update()
            pose_digits(side, h, trigger, tree)
        report.setdefault("presses", {})[side] = None if deepest_press(side, tree) is None else round(deepest_press(side, tree)[0], 2)
    for _ in range(0):
        # the thumb lies on the gun's far side (a pistol's firing thumb on its left): backing the palm off moves it in,
        # so the thumbs are cleared on their own (thumb_clear)
        depth = L.clearance(parts=side, ignore=["forearm*", "thumb2*", "thumb3*"], top=1)["worst_cm"]
        if depth <= allowed:
            break
        hw = L._bw(hn)
        L._put_hand(side, Matrix.LocRotScale(hw.translation + normal * ((depth - allowed + 0.03) / 100.0), hw.to_quaternion(), L._unit()))
        bpy.context.view_layer.update()
    thumb_clear(side, tree, steps=30)
    L._clear_fingers(side)
    bpy.context.view_layer.update()


def arm_over(side):
    """How far the arm is past its limits now: the wrist's bend and side bends and the forearm's roll, degrees over."""
    Lm = L._limits()[0]
    rep_, bad = L._arm_report(side, Lm)
    over = max(0.0, rep_.get("wrist_bend_deg", 0.0) - Lm["wrist_max_deg"])
    over += max(0.0, rep_.get("wrist_radial_deg", 0.0) - Lm["wrist_radial_deg"]) + max(0.0, -rep_.get("wrist_radial_deg", 0.0) - Lm["wrist_ulnar_deg"])
    return over + 10.0 * len(bad)


def turn_search(side, at, n, toward):
    """The palm laid on the face at seven turns about its normal, 30 degrees apart round the style's finger direction
    (or the least turn): the one that leaves the arm least past its limits, then the closest to the hand's reach."""
    base = toward
    if base is None:
        base = fingers_way(side)
    base = (base - n * base.dot(n)).normalized()
    L.snapshot("save", "turn_search")
    best = None
    for k in (0, -1, 1, -2, 2, -3, 3):
        L.snapshot("load", "turn_search")
        way = Quaternion(n, math.radians(30.0 * k)) @ base
        short = lay_palm(side, at, n, toward=way)
        score = arm_over(side) + 4.0 * short
        if best is None or score < best[0] - 1e-6:
            best = (score, way, short)
    L.snapshot("load", "turn_search")
    return lay_palm(side, at, n, toward=best[1])


def contact_search(side, mark, at, n, tw):
    """Where on its contact the hand lies: the palm laid at a few places down and up the grip and forward and back,
    each scored by the presses the style does not allow (the web through a pistol's tang), the palm's gap and the
    arm's limits; the best place is kept."""
    q = RA.matrix_world.to_quaternion()
    up, fwd = (q @ g((0.0, 0.0, 1.0))).normalized(), (q @ g((0.0, 1.0, 0.0))).normalized()
    tree = L._tree()
    L.snapshot("save", "contact_search")
    best = None
    for dz in (0.0, -0.5, -1.0, -1.5, -2.0, 0.5):
        for dy in (0.0, 0.5, -0.5, 1.0):
            L.snapshot("load", "contact_search")
            p_ = at + (up * dz + fwd * dy) / 100.0
            short = turn_search(side, p_, n, tw) if STYLE else lay_palm(side, p_, n, toward=tw)
            settle(side)
            pr = deepest_press(side, tree)
            gap = L.grip(side, hold=False)[side].get("palm_gap_cm")
            gap = 3.0 if gap is None else gap
            score = (pr[0] if pr else 0.0) * 4.0 + max(0.0, gap - 0.3) * 2.0 + arm_over(side) * 0.1 + 4.0 * short
            if best is None or score < best[0] - 1e-6:
                best = (score, p_, dz, dy)
    L.snapshot("load", "contact_search")
    short = turn_search(side, best[1], n, tw) if STYLE else lay_palm(side, best[1], n, toward=tw)
    report.setdefault("contact_place", {})["%s:%s" % (side, mark)] = {"down_cm": -best[2], "forward_cm": best[3], "score": round(best[0], 3)}
    return short


# --- contact rules: regions found on the gun's mesh, whichever mesh it is ------------------------------------------
_DIRS = {"left": (1, 0, 0), "right": (-1, 0, 0), "front": (0, 1, 0), "back": (0, -1, 0), "up": (0, 0, 1), "down": (0, 0, -1)}


def _facing_vec(f):
    if isinstance(f, list):
        return Vector(f).normalized()
    handed = (CHAR or {}).get("handed", "right")
    if f == "support_side":
        f = "left" if handed == "right" else "right"
    elif f == "firing_side":
        f = "right" if handed == "right" else "left"
    return None if f == "any" else Vector(_DIRS[f])


def _gun_polys():
    """Each polygon of the gun's mesh at rest in the facts' gun frame (cm): its centre, its normal and the bone that
    carries it (its vertices' heaviest group)."""
    me = L.rifle_mesh
    Ri = RA.matrix_world.inverted() @ me.matrix_world
    Rq = Ri.to_quaternion()
    names = {g.index: g.name for g in me.vertex_groups}
    vb = []
    for v in me.data.vertices:
        gm = max(v.groups, key=lambda x: x.weight) if v.groups else None
        vb.append(names.get(gm.group, "Root") if gm else "Root")
    out = []
    for p in me.data.polygons:
        c_ = Ri @ p.center
        n_ = Rq @ p.normal
        bones = [vb[i] for i in p.vertices]
        out.append((Vector((c_.x * 100, -c_.y * 100, c_.z * 100)), Vector((n_.x, -n_.y, n_.z)).normalized(),
                    max(set(bones), key=bones.count)))
    return out


_GP = []


def _bound(b, axis, part_ext):
    if isinstance(b, (int, float)):
        return float(b)
    if b.startswith("frac:"):
        lo, hi = part_ext
        return lo + (hi - lo) * float(b[5:])
    import re as _re
    m = _re.match(r"^([A-Za-z_]+)([+-][0-9.]+)?$", b)
    return facts["marks"][m.group(1)]["xyz".index(axis)] + float(m.group(2) or 0.0)


def resolve_region(spec):
    """The polygons of a region: the part's (frame: the gun's body), facing the way asked within its tolerance,
    their centres inside the window."""
    if not _GP:
        _GP.extend(_gun_polys())
    bone = "Root" if spec["part"] == "frame" else (facts["parts"][spec["part"]]["bone"])
    mine = [(i, c_, n_) for i, (c_, n_, b_) in enumerate(_GP) if b_ == bone]
    ext = {ax: (min(c_["xyz".index(ax)] for _i, c_, _n in mine), max(c_["xyz".index(ax)] for _i, c_, _n in mine)) for ax in "xyz"} if mine else {}
    fv = _facing_vec(spec["facing"])
    cos_t = math.cos(math.radians(spec.get("facing_tol_deg", 60.0)))
    win = {ax: (_bound(v[0], ax, ext.get(ax, (0, 0))), _bound(v[1], ax, ext.get(ax, (0, 0)))) for ax, v in (spec.get("window") or {}).items()}
    out = []
    for i, c_, n_ in mine:
        if fv is not None and n_.dot(fv) < cos_t:
            continue
        if any(not (min(lohi) <= c_["xyz".index(ax)] <= max(lohi)) for ax, lohi in win.items()):
            continue
        out.append(i)
    return out


RULES = {}


def hand_rules(side):
    """A hand's contact rules with their regions on this mesh (polygon indices), its wrap band and closure."""
    if side in RULES:
        return RULES[side]
    h = ((STYLE or {}).get("hands") or {}).get(side) or {}
    rules = []
    for r_ in h.get("contact_rules", []):
        x = dict(r_)
        if r_.get("on_hand"):
            x["polys"] = []                               # the region is the other hand's skin, found each time
        else:
            x["polys"] = resolve_region(r_["region"])
        rules.append(x)
    wrap = None
    if h.get("wrap"):
        wrap = {"polys": resolve_region(h["wrap"]["region"]), "min": h["wrap"]["min"],
                "sides": ["r", "l"] if h["wrap"].get("both_hands") else [side]}
    RULES[side] = (rules, wrap, h.get("closure"))
    report.setdefault("contact_regions", {})[side] = {r_["id"]: ("hand " + r_["on_hand"]["side"] if r_.get("on_hand") else len(r_["polys"])) for r_ in rules}
    return RULES[side]


def contacts_now(side):
    rules, wrap, closure = hand_rules(side)
    if not rules and not wrap and not closure:
        return None
    cn = L.contacts(side, rules, glove_cm=GLOVE, friction=(closure or {}).get("friction", 0.5), wrap=wrap,
                    closure_sides=(closure or {}).get("sides", [side]), frame="world")
    Ri = RA.matrix_world.inverted()
    for r_ in cn["rules"]:
        if r_.get("touch") is not None:
            q = Ri @ Vector(r_["touch"])
            r_["touch"] = [round(q.x * 100, 2), round(-q.y * 100, 2), round(q.z * 100, 2)]
            nv = Ri.to_quaternion() @ Vector(r_["normal"])
            r_["normal"] = [round(nv.x, 2), round(-nv.y, 2), round(nv.z, 2)]
    return cn


def summarise_contacts(rows):
    """A clip's contact checks: for each hand and rule, the frames it fails, its worst error and gap; the frames
    the wrap or the force closure fails; and the frames any required rule fails."""
    out = {}
    for t, side, cn in rows:
        o = out.setdefault(side, {"frames": 0, "fail_frames": 0, "rules": {}, "wrap_fail_frames": 0, "closure_fail_frames": 0,
                                  "closure_margin_min": None})
        o["frames"] += 1
        o["fail_frames"] += 0 if cn["ok"] else 1
        for r_ in cn["rules"]:
            x = o["rules"].setdefault(r_["id"], {"need": r_.get("need"), "fail_frames": 0, "worst_error": 0.0, "gap_cm": [], "facing_deg": []})
            if not r_["met"]:
                x["fail_frames"] += 1
            x["worst_error"] = max(x["worst_error"], r_.get("error", 0.0))
            if "gap_cm" in r_:
                x["gap_cm"].append(r_["gap_cm"])
                x["facing_deg"].append(r_["facing_deg"])
            if r_.get("touch") is not None and "first_touch" not in x:
                x["first_touch"] = r_["touch"]
        if cn.get("wrap") and not cn["wrap"]["met"]:
            o["wrap_fail_frames"] += 1
        cl = cn.get("closure") or {}
        if not cl.get("closed", True):
            o["closure_fail_frames"] += 1
        m = cl.get("margin")
        o["closure_margin_min"] = m if o["closure_margin_min"] is None else min(o["closure_margin_min"], m)
    for o in out.values():
        for x in o["rules"].values():
            g_, f_ = x.pop("gap_cm"), x.pop("facing_deg")
            if g_:
                x["gap_cm"] = [round(min(g_), 2), round(max(g_), 2)]
                x["facing_deg"] = [min(f_), max(f_)]
    return out


def style_plan(side, mark):
    """The style's finger plan for a hand on a mark: its contact's fingers, or a working hold's. A digit brought to
    a rest point gets the point in the world too (as the gun is posed now)."""
    h = (STYLE or {}).get("hands", {}).get(side) or {}
    if h.get("contact", {}).get("mark") == mark:
        plan = h["fingers"]
    else:
        x = (h.get("holds") or {}).get(mark)
        plan = x["fingers"] if x else None
    if plan is None:
        return None
    plan = {k: dict(v) for k, v in plan.items()}
    for v in plan.values():
        if v.get("point") is not None:
            v["to_world"] = list(RA.matrix_world @ g(v["point"]))
            if v.get("via"):
                v["via_world"] = list(RA.matrix_world @ g(v["via"]))
    return plan


def grasp(side, mark, part=None, offset=None, start=None):
    """The hand's hold on a mark (_grasp_solve), checked against the walls whichever way it was found: the hold is
    posed, its walls read, and a hold past any wall is recorded as failed with the walls it breaks (report
    "walls"); it never counts as found."""
    key = (side, mark, part, tuple(offset or ()))
    if key in GRASPS:
        return GRASPS[key]
    rel, fingers, found = _grasp_solve(side, mark, part, offset, start)
    L.snapshot("save", "_wall_check")
    L._put_hand(side, bone_world(mark_bone(mark, part)) @ rel)      # as every solver stored it: against the mark's bone
    for n_, q_ in fingers.items():
        L.arm.pose.bones[n_].rotation_quaternion = q_
    bpy.context.view_layer.update()
    w_ = L.wall_faults(side, other=True)
    L.snapshot("load", "_wall_check")
    if w_:
        report.setdefault("walls", {})["%s:%s" % (side, mark)] = {k: round(v, 2) for k, v in w_.items()}
    GRASPS[key] = (rel, fingers, bool(found) and not w_)
    return GRASPS[key]


def _gun_shift(d):
    """The gun moved d metres along the sight line (Step C of the direct hold, the firing hand's solve): the aim does
    not change. The gun's caches and the stance's place follow it."""
    global REST0
    if d:
        L.rifle_rest = Matrix.Translation(Vector(PL.VIEW_FWD) * d) @ L.rifle_rest
        L._place_rifle()
    _BVH.clear()
    REST0 = L.rifle_rest.copy()


def _grasp_solve(side, mark, part=None, offset=None, start=None):
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
    plan = style_plan(side, mark) if STYLE and job.get("solver", True) else None
    con = ((STYLE or {}).get("hands", {}).get(side) or {}).get("contact", {})
    pu = (PUR or {}).get(side) or {}
    if MARKS and pu.get("mark") == mark:
        # the hold found by what the hand is for (its purpose on the gun's own geometry), over the whole arm:
        # several turns about the grip tried as starts, the best one searched
        if start:
            L.snapshot("load", start)
        o_ = "l" if side == "r" else "r"
        ok_home = ((PUR or {}).get(o_) or {}).get("mark")
        if ok_home and (o_, ok_home, None, ()) in GRASPS:
            # the other hand on its own hold, as it was solved (the snapshot above has it where it started): a
            # support hand is solved against the firing hand where it really holds
            rel_o, fing_o, _ = GRASPS[(o_, ok_home, None, ())]
            if o_ in CLAV_SET:
                L.arm.pose.bones["clavicle_" + o_].rotation_quaternion = CLAV_SET[o_]
                bpy.context.view_layer.update()
            B_o = bone_world(mark_bone(ok_home))          # a home hold sits on its mark's bone
            L._put_hand(o_, B_o @ rel_o)
            for n_, q_ in fing_o.items():
                L.arm.pose.bones[n_].rotation_quaternion = q_
            bpy.context.view_layer.update()
        m = next(x for x in MARKS if x.get("role") == "hold" and x.get("hand") == side)
        oth = job.get("solver_other", True) and not (side == "r" and mark == "grip")
        if DIRECT and FACE.get(side):
            # the direct hold: the hand on its mark from the grip style's face, the body solved backward; a support
            # hand rests on the firing hand. One start, checked by the valid-start rule.
            wr_ = {fi: ("straight" if fi == "index" and m.get("index") == "extended" else "wrap") for fi in ("index", "middle", "ring", "pinky")}
            h_ = L.direct_hold(side, MARKS, palm_dir=FACE[side], glove_cm=GLOVE, other=oth, wrap=wr_,
                               rest_on_hand=(m["purpose"] == "support"),
                               gun_shift=_gun_shift if side == "r" else None)    # the firing hand is on the gun first
            g_ = L.hold_gate(MARKS, sides=(side,), glove_cm=GLOVE, skin=False, other=oth)
            ok_ = bool(g_.get(side, {}).get("pass")) and not h_.get("walls")
            r = {"method": "direct"}
            best_ = (h_, g_, ok_, None)
            L.snapshot("save", "_held_" + side)
        else:
            tries, seat, ext = purpose_starts(side, m, pu, oth)
            r = {"seeds": sorted([{"roll_deg": t_[1], "score": round(t_[0], 1), "arm_excess_deg": t_[2]} for t_ in tries],
                                 key=lambda x_: (x_["arm_excess_deg"], x_["score"]))}
            # the search from the best starts in turn (the body first, then the score), the best hold kept, stopping
            # as soon as one passes the gate; the fingers close by the skin each try, an extended index lies straight
            wr_ = {fi: ("straight" if fi == "index" and ext else "wrap") for fi in ("index", "middle", "ring", "pinky")}
            best_, r["restarts"] = None, []
            for k_, (_sc, roll, _ex) in enumerate(sorted(tries, key=lambda t_: (t_[2], t_[0]))[: int(job.get("hold_restarts", 3))]):
                if k_ > 0 and getattr(L, "_deadline", None) is not None and _time.time() > L._deadline:
                    report.setdefault("budget_cut", []).append("%s %s: %d of the starts solved" % (side, mark, k_))
                    break
                seat(roll)
                # the target solver (no chance in it), inside the walls: each purpose names where its hand part goes
                h_ = L.target_hold(side, MARKS, glove_cm=GLOVE, other=oth, wrap=wr_)
                g_ = L.hold_gate(MARKS, sides=(side,), glove_cm=GLOVE, skin=False, other=oth)
                ok_ = bool(g_.get(side, {}).get("pass"))
                ok_ = ok_ and not h_.get("walls")
                r["restarts"].append({"roll_deg": roll, "score": h_["score"], "gate": ok_, "rounds": h_.get("rounds"),
                                      "unmet": h_.get("unmet"), "walls": h_.get("walls"), "solve_s": h_.get("solve_s")})
                # the walls first (fewer broken, less past), then the gate, then the score
                rank_ = (L._walls_rank(h_.get("walls") or {}), not ok_, h_["score"])
                if best_ is None or rank_ < best_[3]:
                    best_ = (h_, g_, ok_, rank_)
                    L.snapshot("save", "_held_" + side)
                if ok_:
                    break
        L.snapshot("load", "_held_" + side)
        r["hold"], r["gate"] = best_[0], best_[1]
        r["press"] = r["hold"].get("press")        # an invalid direct start makes no hold, so no press
        report.setdefault("solved", {})["%s:%s" % (side, mark)] = r
        cn_ = "clavicle_" + side
        if cn_ in L.arm.pose.bones:
            CLAV_SET[side] = L.arm.pose.bones[cn_].rotation_quaternion.copy()
        H = L._bw(hn).copy()
        rel = bone_world(mark_bone(mark, part)).inverted() @ H
        fingers = {nm: L.arm.pose.bones[nm].rotation_quaternion.copy() for nm in FINGER_BONES[side]}
        L.snapshot("load", "before_grasp")
        GRASPS[key] = (rel, fingers, bool(r["gate"].get(side, {}).get("pass")) and not r["hold"].get("walls"))
        return GRASPS[key]
    rf = ((job.get("reference") or {}).get("hands") or {}).get(side)
    if plan is not None and con.get("mark") == mark and rf and job.get("use_reference", False):
        # the style's reference hold (an animator's hand on its own gun, carried in the grip's frame) put on the
        # hand, the digits the style poses itself (the trigger finger along the frame) set from the style, then the
        # one score adapts it to this gun in small moves
        if start:
            L.snapshot("load", start)
        FRG = REFH.facts_frame(facts)
        Q = RA.matrix_world
        W_ = lambda c: list(Q @ g(REFH.from_grip(c, FRG)))     # noqa: E731
        put = {"points": {k: W_(v) for k, v in rf["points"].items()}, "curls": rf["curls"], "thumb": rf["thumb"],
               "thumb_tip": W_(rf["points"]["thumb_tip"]) if rf["points"].get("thumb_tip") else None,
               "keep": rf.get("keep", [])}
        oth = job.get("solver_other", True) and not (side == "r" and mark == "grip")
        r = {"reference": L.put_reference(side, put, glove_cm=GLOVE, other=oth)}
        for fi in rf.get("keep", []):
            f_ = plan.get(fi) or {}
            if f_.get("pose") == "posture" and fi != "thumb":
                for j, cc in zip(("01", "02", "03"), f_["curl"]):
                    L._set_curl(side, fi, j, float(cc), _FL)
        bpy.context.view_layer.update()
        r["seed"] = L.hold_score(side, hand_rules(side)[0], GLOVE, oth, SOFT)[1]
        r["adapt"] = L.adapt_hold(side, hand_rules(side)[0], plan=plan, glove_cm=GLOVE, other=oth, soft=SOFT,
                                  span_cm=float(job.get("adapt_span_cm", 3.0)), turn_deg=float(job.get("adapt_turn_deg", 20.0)),
                                  keep_w=float(job.get("adapt_keep_w", 1.0)), generations=int(job.get("adapt_generations", 40)),
                                  pop=int(job.get("adapt_pop", 16)))
        r["fits"] = (r["adapt"]["moved_cm"] < float(job.get("adapt_span_cm", 3.0)) - 0.05
                     and r["adapt"]["turned_deg"] < float(job.get("adapt_turn_deg", 20.0)) - 0.5)
        r["press"] = r["adapt"]["press"]
        if r["adapt"]["arm_bad"] or r["press"] > 0.0:
            # still a fault the contact rules pulled it into: the one repair on the hold itself, so the hold is what
            # every frame shows (anatomy before touch)
            r["repair"] = L.repair_hand(side, glove_cm=GLOVE, other=oth, soft=SOFT, keep_w=float(job.get("repair_keep_w", 6.0)),
                                        generations=int(job.get("hold_repair_generations", 12)), pop=int(job.get("repair_pop", 8)))
            r["press"] = r["repair"]["press"]
        r["contacts"] = contacts_now(side)
        report.setdefault("solved", {})["%s:%s" % (side, mark)] = r
        H = L._bw(hn).copy()
        rel = bone_world(mark_bone(mark, part)).inverted() @ H
        fingers = {nm: L.arm.pose.bones[nm].rotation_quaternion.copy() for nm in FINGER_BONES[side]}
        L.snapshot("load", "before_grasp")
        GRASPS[key] = (rel, fingers, r["press"] <= 0.01)
        return GRASPS[key]
    if plan is not None and con.get("mark") == mark and con.get("search") == "natural" and hasattr(L, "natural_hold"):
        # the hold found over the whole arm's range, scored by the arm's ease, then the contact rules and presses;
        # nothing of the hand is set by hand
        if start:
            L.snapshot("load", start)
        Q = RA.matrix_world
        nrm_w = (Q.to_quaternion() @ g(con["face"])).normalized()
        acr = None
        if con.get("across") == "grip_axis" and (facts.get("magazine") or {}).get("axis"):
            acr = list((Q.to_quaternion() @ g([-x for x in facts["magazine"]["axis"]])).normalized())
        oth = job.get("solver_other", True) and not (side == "r" and mark == "grip")   # the firing hand closes on the gun alone
        r = L.natural_hold(side, list(at), list(nrm_w), hand_rules(side)[0], plan=plan, glove_cm=GLOVE,
                           other=oth, soft=SOFT, axis=acr,
                           dists_cm=tuple(con.get("search_dists_cm", (0.0, 1.0, 2.0))), keep=int(job.get("natural_keep", 40)),
                           refine=int(job.get("natural_refine", 40)))
        # then one search over the hand, its fingers and its thumb together, from the most natural arm found
        r["es"] = L.es_hold(side, hand_rules(side)[0], plan=plan, glove_cm=GLOVE, other=oth,
                            soft=SOFT, generations=int(job.get("es_generations", 40)), pop=int(job.get("es_pop", 16)),
                            sigma_cm=float(job.get("es_sigma_cm", 1.0)), sigma_deg=float(job.get("es_sigma_deg", 8.0)))
        r["contacts"] = contacts_now(side)
        report.setdefault("solved", {})["%s:%s" % (side, mark)] = r
        H = L._bw(hn).copy()
        rel = bone_world(mark_bone(mark, part)).inverted() @ H
        fingers = {nm: L.arm.pose.bones[nm].rotation_quaternion.copy() for nm in FINGER_BONES[side]}
        L.snapshot("load", "before_grasp")
        GRASPS[key] = (rel, fingers, r.get("press", 1.0) <= 0.01)
        return GRASPS[key]
    if plan is not None and con.get("mark") == mark and con.get("anchors"):
        # the hold as real technique sets it: the hand fitted to its anchor points on the gun (the web under the
        # tang, the middle knuckle under the guard ...), its palm facing the panel; then its digits closed by the
        # plan, and the solver refining round the anchors so nothing presses into the gun or the other hand
        if start:
            L.snapshot("load", start)
        Q = RA.matrix_world
        anc = {k: list(Q @ g(v)) for k, v in con["anchors"].items()}
        face_w = (Q.to_quaternion() @ g([-x for x in con["face"]])).normalized()
        acr = None
        if con.get("across") == "grip_axis" and (facts.get("magazine") or {}).get("axis"):
            ax_ = [-x for x in facts["magazine"]["axis"]]        # the magazine well's line, upward: the grip's axis
            acr = list((Q.to_quaternion() @ g(ax_)).normalized())
        elif isinstance(con.get("across"), list):
            acr = list((Q.to_quaternion() @ g(con["across"])).normalized())
        placed = L.place_hand(side, anc, facing=list(face_w), frame="world", across=acr)
        r = L.solve_hand(side, list(at), surface_normal(at, mark), plan=plan, toward=None, glove_cm=GLOVE, frame="world",
                         soft=SOFT, samples=int(job.get("solver_samples", 60)), refine=int(job.get("solver_refine", 30)),
                         span_cm=float(job.get("anchor_span_cm", 0.8)), turn_deg=float(job.get("anchor_turn_deg", 10.0)),
                         other=job.get("solver_other", True) and not (side == "r" and mark == "grip"),
                         from_current=True, anchors=anc, anchor_w=float(job.get("anchor_weight", 4.0)),
                         contact_rules=hand_rules(side)[0] or None, contact_w=float(job.get("contact_weight", 8.0)))
        if job.get("es_after_anchor", True) and hasattr(L, "es_hold"):
            # then the one optimiser from this hold, in small steps: the faults left are mended together, the thumb kept
            oth_ = job.get("solver_other", True) and not (side == "r" and mark == "grip")
            r["es"] = L.es_hold(side, hand_rules(side)[0], plan=plan, glove_cm=GLOVE, other=oth_, soft=SOFT,
                                generations=int(job.get("es_anchor_generations", 30)), pop=int(job.get("es_pop", 16)),
                                sigma_cm=float(job.get("es_anchor_sigma_cm", 0.6)), sigma_deg=float(job.get("es_anchor_sigma_deg", 6.0)),
                                freeze_thumb=bool((plan.get("thumb") or {}).get("via")))   # a thumb on its path stays on it
        r["placed"] = placed
        r["contacts"] = contacts_now(side)
        report.setdefault("solved", {})["%s:%s" % (side, mark)] = r
        H = L._bw(hn).copy()
        rel = bone_world(mark_bone(mark, part)).inverted() @ H
        fingers = {nm: L.arm.pose.bones[nm].rotation_quaternion.copy() for nm in FINGER_BONES[side]}
        L.snapshot("load", "before_grasp")
        GRASPS[key] = (rel, fingers, r["press"] <= 0.01 and r["rules"] == 0)
        return GRASPS[key]
    if plan is not None and job.get("solver_from_scratch", True):
        # the grasp solver (Pose Lab): the whole hand placed on the hold, its digits closed by the style's plan,
        # nothing pressing into the gun or the other hand past what is allowed, the glove counted
        if start:
            L.snapshot("load", start)
        tw = TOWARD.get(mark)
        tw = (RA.matrix_world.to_quaternion() @ g(tw)).normalized() if tw else None
        r = L.solve_hand(side, list(at), surface_normal(at, mark), plan=plan, toward=tw, glove_cm=GLOVE, frame="world",
                         soft=SOFT, samples=int(job.get("solver_samples", 120)), refine=int(job.get("solver_refine", 40)),
                         span_cm=float(job.get("solver_span_cm", 3.0)),
                         # no finger direction given: the whole turn about the face is open (swept), tilts to 25
                         turn_deg=(180.0 if tw is None else float(job.get("solver_turn_deg", 25.0)) * (1.0 if (STYLE["hands"].get(side) or {}).get("contact", {}).get("mark") == mark else 3.0)),
                         tilt_deg=25.0 if tw is None else None,
                         other=job.get("solver_other", True) and not (side == "r" and mark == "grip"),
                         contact_rules=(hand_rules(side)[0] or None) if (STYLE["hands"].get(side) or {}).get("contact", {}).get("mark") == mark else None,
                         contact_w=float(job.get("contact_weight", 8.0)))
        report.setdefault("solved", {})["%s:%s" % (side, mark)] = r
        H = L._bw(hn).copy()
        rel = bone_world(mark_bone(mark, part)).inverted() @ H
        fingers = {nm: L.arm.pose.bones[nm].rotation_quaternion.copy() for nm in FINGER_BONES[side]}
        L.snapshot("load", "before_grasp")
        GRASPS[key] = (rel, fingers, r["press"] <= 0.01 and r["rules"] == 0)
        return GRASPS[key]
    back = (RA.matrix_world.to_quaternion() @ g((0.0, -1.0, 0.0))).normalized()
    slid = 0.0
    if start == "at_use":
        L.snapshot("load", start)                 # the gun as the clip has it where the hold is used; laid below
    if start and start != "at_use":
        L.snapshot("load", start)                 # the hands as the placement search left them, already settled
        if STYLE and side == "r" and (STYLE["hands"].get(side) or {}).get("contact", {}).get("mark") == mark:
            tw0 = TOWARD.get(mark)
            contact_search(side, mark, at, surface_normal(at, mark), (RA.matrix_world.to_quaternion() @ g(tw0)).normalized() if tw0 else None)
            settle(side)
    else:
        n = surface_normal(at, mark)
        tw = TOWARD.get(mark)
        tw = (RA.matrix_world.to_quaternion() @ g(tw)).normalized() if tw else None
        own = STYLE and (STYLE["hands"].get(side) or {}).get("contact", {}).get("mark") == mark and side == "r"
        short = contact_search(side, mark, at, n, tw) if own else (turn_search(side, at, n, tw) if STYLE else lay_palm(side, at, n, toward=tw))
        while short > 0.3 and mark == "support" and slid < 14.0:      # beyond the arm's reach: slide back along the bore
            slid += 2.0
            L.snapshot("load", "before_grasp")
            short = lay_palm(side, at + back * (slid / 100.0), n)
        settle(side)
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
    if STYLE and (STYLE["hands"].get(side) or {}).get("contact", {}).get("mark") == mark:
        apply_style(side, normal=surface_normal(at, mark))   # the style's fingers on its own contact; the thumb's
                                                       # base backed out of the grip (at most 0.6 cm)
    elif STYLE:
        apply_hold(side, mark)                         # a working hold the style names
    if plan is not None and job.get("solver_refine_placed", True):
        # the grasp solver (Pose Lab) refines the hold placed above: small moves and turns of the whole hand about
        # its palm, its digits closed again by the style's plan for each, the place that presses least into the gun
        # and the other hand (the glove counted), keeps the palm on and the fingers round the gun, and the arm in
        # its limits wins
        own = (STYLE["hands"].get(side) or {}).get("contact", {}).get("mark") == mark
        r = L.solve_hand(side, list(at), surface_normal(at, mark), plan=plan, toward=None, glove_cm=GLOVE, frame="world",
                         soft=SOFT, samples=int(job.get("solver_samples", 80)), refine=int(job.get("solver_refine", 30)),
                         span_cm=float(job.get("solver_span_cm", 1.0)),
                         turn_deg=float(job.get("solver_turn_deg", 10.0)) * (1.0 if own else 2.0),
                         other=job.get("solver_other", True), from_current=True)
        report.setdefault("solved", {})["%s:%s" % (side, mark)] = r
    H = L._bw(hn).copy()
    rel = bone_world(mark_bone(mark, part)).inverted() @ H
    fingers = {nm: L.arm.pose.bones[nm].rotation_quaternion.copy() for nm in FINGER_BONES[side]}
    L.snapshot("load", "before_grasp")
    GRASPS[key] = (rel, fingers, found)
    return GRASPS[key]


# where the gun sits for both hands: a few places round the first one (along the bore, up and down, a little to the
# side), both palms laid at each; the place where both arms reach with the least clipping and the fewest broken rules
# wins (Pose Lab's clearance and anatomy measures)
def try_place(dv):
    L.rifle_rest = Matrix.Translation(dv) @ REST0
    L.pose_idle()
    rest_parts()
    sr = lay_palm("r", mark_world("grip"), surface_normal(mark_world("grip"), "grip"))
    sl = lay_palm("l", mark_world("support"), surface_normal(mark_world("support"), "support")) if "support" in facts["marks"] else 0.0
    settle("r")
    settle("l")
    gr = L.grip("both", hold=True)
    holding = sum(1 for sd in ("l", "r") if gr.get(sd, {}).get("holding"))
    cl = L.clearance(parts="both", ignore=["palm*"], top=1)["worst_cm"]
    an = L.anatomy("both")
    bad = len(an.get("l", {}).get("bad", [])) + len(an.get("r", {}).get("bad", []))
    # the view: the muzzle and the bolt face stay about where the arms' own hold puts a gun on the screen (low and to
    # the right at the hip); a gun dead in the middle of the view would hide the world
    view = 0.0
    for m, ref in VIEW_REF.items():
        w = RA.matrix_world @ g((0.0, 0.0, 0.0)) if m == "bolt_face" else mark_world(m)
        sc = L.screen(lab_gun(w))
        view += ((sc.get("x", 2.0) - ref[0]) ** 2 + (sc.get("y", 2.0) - ref[1]) ** 2) ** 0.5
    return (4.0 * (sr + sl) + cl + 1.5 * bad + 3.0 * (2 - holding) + 6.0 * view,
            {"short_r": round(sr, 2), "short_l": round(sl, 2), "clearance": cl, "rules": bad, "holding": holding, "view_off": round(view, 3)})


REF_EYE = (job.get("reference") or {}).get("eye") if job.get("use_reference", False) else None
if REF_EYE and STYLE:
    # the reference's own stance: the gun where the pack's camera saw it (its eye carried in the grip's frame), so
    # the hold sits on arms reaching as the animator's did. Gun cm to Pose Lab's view: x right = the gun's left,
    # y ahead and z up the other way round
    E_ = REFH.from_grip(REF_EYE, REFH.facts_frame(facts))
    vc_ = [E_[0], -E_[1], -E_[2]]
    L.rifle_rest = Matrix.LocRotScale(L._from(vc_, "view"), Quaternion(), L.rifle_rest.to_scale())
    L.pose_idle()
    report["stance_view_cm"] = [round(x, 2) for x in vc_]
    report["stance_from"] = "reference"
elif STYLE and STYLE.get("stance"):
    # the style's stance: the bolt face at its place in front of the eye, the bore straight ahead (Pose Lab's arms
    # frame looks down the gun's own axes), the arms reaching it from the idle
    L.rifle_rest = Matrix.LocRotScale(L._from(STYLE["stance"]["view_cm"], "view"), Quaternion(), L.rifle_rest.to_scale())
    L.pose_idle()
    report["stance_view_cm"] = STYLE["stance"]["view_cm"]
REST0 = L.rifle_rest.copy()
# the screen places of the muzzle and the bolt face with the gun where the arms' idle puts it (the reference the view
# term keeps the gun near)
L.pose_idle()
VIEW_REF = {}
for m in ("muzzle",):
    sc = L.screen(lab_gun(mark_world(m)))
    if sc.get("on_screen") is not None and "x" in sc:
        VIEW_REF[m] = (sc["x"], sc["y"])
_bf = L.screen(lab_gun(RA.matrix_world @ g((0.0, 0.0, 0.0))))
if "x" in _bf:
    VIEW_REF["bolt_face"] = (_bf["x"], _bf["y"])
report["view_reference"] = {k: list(v) for k, v in VIEW_REF.items()}
L.steps.phase("place search")
# v26 (2026-10-20): with purposes, the stance search below places the gun for both hands on the contact
# model; this older search (capsule checks) only fed it a start, so it is skipped then.
if job.get("place_search", True) and "support" in facts["marks"] and not REF_EYE and not (STYLE or {}).get("purposes"):
    qg = RA.matrix_world.to_quaternion()
    fwd, up_, left_ = (qg @ g((0, 1, 0))).normalized(), (qg @ g((0, 0, 1))).normalized(), (qg @ g((1, 0, 0))).normalized()
    tried = []
    for dy in (-16.0, -12.0, -8.0, -4.0, 0.0):
        for dz in (-6.0, -3.0, 0.0, 3.0):
            for dx in (0.0, 3.0):
                dv = (fwd * dy + up_ * dz + left_ * dx) / 100.0
                score, why = try_place(dv)
                tried.append((score, [dx, dy, dz], why, dv))
                if score <= min(t[0] for t in tried):
                    L.snapshot("save", "place_best")      # both hands as they hold the best place so far
    tried.sort(key=lambda t: t[0])
    best = tried[0]
    REST0 = Matrix.Translation(best[3]) @ REST0
    report["placement_search"] = {"best": {"move_cm": best[1], **best[2]}, "first": next(({"move_cm": t[1], **t[2]} for t in tried if t[1] == [0.0, 0.0, 0.0]), None),
                                  "tried": len(tried)}
L.rifle_rest = REST0
L.pose_idle()
rest_parts()
L._place_rifle()
_BVH.clear()                                       # the gun's surface, in the world, as it now sits
start = "place_best" if "placement_search" in report else None
# --- the gun read from its own geometry, the marks from its facts --------------------------------------------
L.steps.phase("the gun read, the marks")
PUR = (STYLE or {}).get("purposes") if job.get("purposes", True) else None
OBJ, MARKS = None, None
# the direct hold (Pose Lab docs/DIRECT_HOLD_PLAN.md): the hand placed from the marks, the body solved backward;
# hold_method "search" keeps the start search
DIRECT = False
FACE = {}
CLAV_SET = {}                # each home hold's shoulder girdle, as its search left it
GUN_DIRS = {"back": (0, -1, 0), "front": (0, 1, 0), "left": (1, 0, 0), "right": (-1, 0, 0), "up": (0, 0, 1), "down": (0, 0, -1)}
if PUR:
    hl_ = ((report.get("body_size") or {}).get("r") or {}).get("measures", {}).get("hand_length_cm")
    OBJ = L.read_object(parts=["Root"], hand_length_cm=hl_, inner_toward=list(g((0.0, 0.0, 0.0))))
    runs_ = (OBJ["parts"].get("Root") or {}).get("runs") or []
    report["object"] = L.object_summary()
    if not runs_:
        report["notes"].append("the frame has no run a hand can wrap: no purpose holds")
        PUR = None
if PUR:
    gl_ = g(facts["marks"]["grip"])
    ri_ = min(range(len(runs_)), key=lambda i: min((Vector(s_["centre"]) - gl_).length for s_ in runs_[i]["sections"]))
    MARKS = []
    for sd_ in ("r", "l"):
        p_ = PUR.get(sd_)
        if not p_:
            continue
        m_ = {"part": "Root", "role": "hold", "purpose": p_["purpose"], "run": ri_, "hand": sd_, "thumb": p_.get("thumb"),
              "index": p_.get("index", "wrap"), "palm_dir": list(g(GUN_DIRS[p_.get("palm", "back")]).normalized())}
        ops_ = runs_[ri_]["openings"]
        if m_["index"] == "extended":
            if ops_:
                tl_ = g(facts["marks"]["trigger"]) if "trigger" in facts["marks"] else gl_
                m_["index_line"] = min(range(len(ops_)), key=lambda i: (Vector(ops_[i]["centre"]) - tl_).length)
            else:
                m_["index"] = "wrap"
                report["notes"].append("no opening beside the grip: the index wraps")
        MARKS.append(m_)
    for part_ in PUR.get("notouch", []):
        if part_ in facts["parts"]:
            MARKS.append({"part": facts["parts"][part_]["bone"], "role": "notouch"})
    # the gun's surface labelled once by region (the contact model's object), named in the gun's own frame
    LEFT_ = list(g((1.0, 0.0, 0.0)).normalized())
    for m_ in MARKS:
        if m_.get("role") == "hold" and m_.get("purpose") == "power_wrap" and m_.get("palm_dir"):
            m_["_web"] = L.web_point(m_, m_["palm_dir"])[0]
    report["regions_cm2"] = L.object_regions(MARKS, LEFT_)
    report["marks"] = MARKS
    report["grip_run"] = ri_
    # Step 0: the hold marks, from the gun's geometry and the grip style's contact faces (FM 3-23.35 2-2, 2-3),
    # saved beside the run. The facts' support normal points down; the support palm faces the gun's side, so the
    # support face comes from the grip style.
    DIRECT = job.get("hold_method", "direct") == "direct"
    for sd_ in ("r", "l"):
        c_ = (((STYLE or {}).get("hands") or {}).get(sd_) or {}).get("contact") or {}
        if c_.get("face"):
            FACE[sd_] = list(g(c_["face"]).normalized())
    run_ = runs_[ri_]
    m_r0 = next((x for x in MARKS if x.get("role") == "hold" and x.get("hand") == "r"), {})
    op_ = run_["openings"][m_r0["index_line"]] if "index_line" in m_r0 else None
    report["hold_marks"] = {
        "gun": facts["name"], "frame": "the gun body bone's frame, m",
        "grip_axis": {"origin": run_["origin"], "axis": run_["axis"], "inner": run_["inner"], "outer": run_["outer"]},
        "web_point": m_r0.get("_web"), "guard_line": op_["edge"] if op_ else None,
        "firing_face": FACE.get("r"), "support_face": FACE.get("l"),
        "support_normal_in_facts": facts.get("normals", {}).get("support"),
        "faces_from": "the grip style's contact faces"}
    json.dump(report["hold_marks"], open(os.path.join(OUT, "hold_marks.json"), "w", encoding="utf-8"), indent=1, default=str)


def purpose_starts(side, m, pu, oth):
    """A hand's starts on its mark: the hand by the run's frame turned about the grip (a support hand's palm toward
    where the firing hand leaves the grip open), its palm settled, the index laid straight when it lies along the
    guard, the other fingers closed by the skin; each scored by the purposes and by how far past its limits the arm
    is. Returns the starts [(score, turn, arm excess)], a function that seats the hand at a turn, and whether the
    index is extended."""
    pdir, rolls = m.get("palm_dir"), [float(x) for x in job.get("seed_rolls", range(-90, 91, 15))]
    if m["purpose"] == "support":
        od_, share_ = L.open_dir("r" if side == "l" else "l", m, GLOVE)
        if od_ is not None:
            pdir, rolls = od_, [float(x) for x in range(-45, 46, 15)]
            report["support_open"] = {"dir": [round(x, 3) for x in od_], "open_share": share_}
    L.snapshot("save", "_seed_" + side)
    ext = m.get("index") == "extended"
    digits_ = tuple(fi for fi in ("index", "middle", "ring", "pinky") if not (fi == "index" and ext))
    along_ = float(pu.get("along_cm", 0.0)) if m["purpose"] != "support" else 0.0

    def seat(roll):
        L.snapshot("load", "_seed_" + side)
        sd_ = L.seed_hold(side, m, palm_dir=pdir, roll_deg=roll, along_cm=along_)
        L.settle_palm(side)
        for fi in ("index", "middle", "ring", "pinky"):
            for j, cc in zip(("01", "02", "03"), (0.0, 0.0, 3.0) if (fi == "index" and ext) else (0.0, 0.0, 0.0)):
                L._set_curl(side, fi, j, float(cc), _FL)
        bpy.context.view_layer.update()
        L.conform_digits(side, digits_, other=oth)
        return sd_

    tries = []
    for roll in rolls:
        seat(roll)
        sc_, _why = L._hold_score(side, MARKS, GLOVE, oth, SOFT, L._tree())
        tries.append((sc_, roll, L.arm_excess(side)))
    return tries, seat, ext


L.steps.wrap_dict(globals(), ["purpose_starts", "grasp", "_grasp_solve", "gun_pose", "contacts_now", "try_place"])
L.steps.phase("stance search")
if MARKS and DIRECT and FACE.get("r") and not (job.get("contact_view") or job.get("skin_check") or job.get("object_only")):
    # Step B: the gun's distance along the view's forward line, from the reach that gives the preferred elbow
    # flexion: D*^2 = l1^2 + l2^2 + 2 l1 l2 cos(f_pref); |W(d) - S| grows with d, so bisection finds it.
    import directmath as DM
    base_ = L.rifle_rest.copy()
    m_r = next(x for x in MARKS if x.get("role") == "hold" and x.get("hand") == "r")
    L.snapshot("save", "_stance0")
    fpref = float(((STYLE or {}).get("stance") or {}).get("elbow_flexion_pref_deg", 20.0))

    def _at(d_):
        L.snapshot("load", "_stance0")
        L.rifle_rest = Matrix.Translation(Vector(PL.VIEW_FWD) * d_) @ base_
        L.pose_idle()
        rest_parts()
        L._place_rifle()
        _BVH.clear()
        L.seed_hold("r", m_r, palm_dir=FACE["r"], roll_deg=0.0)
        return L.reach_now("r")
    l1_, l2_, _d0 = _at(0.0)
    Dstar = DM.reach_for_elbow(l1_, l2_, fpref)
    d_, got_, n_ = DM.bisect(lambda x_: _at(x_)[2], Dstar, -0.15, 0.15, tol=0.001)
    _at(d_)
    L.snapshot("load", "_stance0")
    L.rifle_rest = Matrix.Translation(Vector(PL.VIEW_FWD) * d_) @ base_
    REST0 = L.rifle_rest.copy()
    L.pose_idle()
    rest_parts()
    L._place_rifle()
    _BVH.clear()
    L.snapshot("save", "place_best")
    start = "place_best"
    report["stance_search"] = {"method": "direct", "best": {
        "ahead_cm": round(d_ * 100.0, 2), "elbow_pref_deg": fpref, "l1_cm": round(l1_ * 100.0, 2),
        "l2_cm": round(l2_ * 100.0, 2), "reach_target_cm": round(Dstar * 100.0, 2), "reach_got_cm": round(got_ * 100.0, 2),
        "elbow_got_deg": round(DM.elbow_for_reach(l1_, l2_, got_) or -1.0, 1), "bisect_steps": n_,
        "hit_range_end": abs(abs(d_) - 0.15) < 1e-9}}
elif MARKS and job.get("stance_search", True) and not (job.get("contact_view") or job.get("skin_check") or job.get("object_only")):
    # where the gun sits for both hands: a grid of places about the style's stance (ahead and back, up and down in
    # the view), each judged by the two hands' best starts on it (how far past its limits each arm is first, then
    # the purposes' score): the body decides the stance, as it decides each hold
    base_ = L.rifle_rest.copy()
    m_r = next(x for x in MARKS if x.get("role") == "hold" and x.get("hand") == "r")
    m_l = next((x for x in MARKS if x.get("role") == "hold" and x.get("hand") == "l"), None)
    L.snapshot("save", "_stance0")
    rows_ = []
    # The stance depends only on the gun, the arms, the style and the solver's code: the same inputs give the
    # same place, so it is kept on disk and the 20 place grid (400 seated starts) runs only when one changes.
    import hashlib
    _h = hashlib.sha1()
    _fold = A["folder"] if os.path.isabs(A["folder"]) else os.path.join(OUT, A["folder"])
    _files = [job["gun_fbx"], os.path.join(_fold, A["arms"]), os.path.join(_fold, A["idle"]), _be]
    _files += [os.path.join(job["poselab"], f) for f in sorted(os.listdir(job["poselab"])) if f.endswith(".py")]
    for _f in _files:
        if os.path.exists(_f):
            _h.update(open(_f, "rb").read())
    _h.update(json.dumps([STYLE.get("stance") if STYLE else None, PUR, MARKS, list(job.get("stance_ahead_cm", [])),
                          list(job.get("stance_up_cm", [])), list(job.get("seed_rolls", [])), GLOVE],
                         sort_keys=True, default=str).encode())
    _skey = _h.hexdigest()[:16]
    _scache = os.path.join(OUT, "stance_cache.json")
    _cached = json.load(open(_scache, encoding="utf-8")).get(_skey) if os.path.exists(_scache) else None
    if not job.get("stance_cache", True):
        _cached = None
    # the places nearest the style's stance first, so a budget stop keeps the likeliest ones
    _grid = sorted(((float(a_), float(b_)) for a_ in job.get("stance_ahead_cm", (-6.0, -3.0, 0.0, 3.0))
                    for b_ in job.get("stance_up_cm", (-8.0, -6.0, -4.0, -2.0, 0.0))), key=lambda p_: (abs(p_[0]) + abs(p_[1]), p_))
    for dy, dz in ([] if _cached else _grid):
        if rows_ and _time.time() > by(0.25):
            report.setdefault("budget_cut", []).append("stance search: %d of %d places" % (len(rows_), len(_grid)))
            break
        if True:
            L.snapshot("load", "_stance0")
            L.rifle_rest = Matrix.Translation(Vector(PL.VIEW_FWD) * (dy / 100.0) + Vector(PL.VIEW_UP) * (dz / 100.0)) @ base_
            L.pose_idle()
            rest_parts()
            L._place_rifle()
            _BVH.clear()
            tr_r, seat_r, _e = purpose_starts("r", m_r, PUR["r"], False)
            b_r = min(tr_r, key=lambda t_: (t_[2], t_[0]))
            tot = (10.0 * b_r[2] + b_r[0], b_r[2], b_r[0])
            if m_l is not None:
                seat_r(b_r[1])
                tr_l, _seat_l, _e2 = purpose_starts("l", m_l, PUR["l"], True)
                b_l = min(tr_l, key=lambda t_: (t_[2], t_[0]))
                tot = (tot[0] + 10.0 * b_l[2] + b_l[0], tot[1] + b_l[2], tot[2] + b_l[0])
            rows_.append({"ahead_cm": dy, "up_cm": dz, "value": round(tot[0], 1), "arm_excess_deg": tot[1], "score": round(tot[2], 1)})
    if _cached:
        best_s = _cached["best"]
        rows_ = _cached["tried"]
    else:
        best_s = min(rows_, key=lambda r_: r_["value"])
    if not _cached and len(rows_) == len(_grid):    # only a full search is kept: a budget-cut one is a partial answer
        _all = json.load(open(_scache, encoding="utf-8")) if os.path.exists(_scache) else {}
        _all[_skey] = {"best": best_s, "tried": sorted(rows_, key=lambda r_: r_["value"])[:6]}
        json.dump(_all, open(_scache, "w", encoding="utf-8"), indent=1)
    L.snapshot("load", "_stance0")
    L.rifle_rest = Matrix.Translation(Vector(PL.VIEW_FWD) * (best_s["ahead_cm"] / 100.0) + Vector(PL.VIEW_UP) * (best_s["up_cm"] / 100.0)) @ base_
    REST0 = L.rifle_rest.copy()
    L.pose_idle()
    rest_parts()
    L._place_rifle()
    _BVH.clear()
    L.snapshot("save", "place_best")
    start = "place_best"
    report["stance_search"] = {"best": best_s, "tried": sorted(rows_, key=lambda r_: r_["value"])[:6],
                               "from_cache": bool(_cached), "key": _skey}
if job.get("object_only"):
    # the gun as read, and nothing else of the hand step
    json.dump(report, open(os.path.join(OUT, "hands.json"), "w", encoding="utf-8"), indent=1, default=str)
    print("GUNKIT object read")
    sys.exit(0)
if job.get("contact_view"):
    # the contact model on a saved clip's frame: the gun's regions from its marks, the hands' labelled skin, every
    # contact pair and press, and the pictures (object, hand, heat, contact); no hand is moved
    cv = job["contact_view"]
    cid = cv.get("clip", "idle")
    path = os.path.join(OUT, "clips", job.get("prefix", "A_%s_Hands_" % facts["name"]) + cid + ".pose.json")
    L.load_clip("cv_" + cid, path)
    frames, fps = L._frames("cv_" + cid)
    k_ = max(0, min(len(frames) - 1, int(round(float(cv.get("t", 0.0)) * fps))))
    L._apply(frames[k_])
    rest_parts()
    tr_ = job["tracks"].get(cid)
    if tr_:
        tf_ = {round(f["t"], 5): f["bones"] for f in tr_["frames"]}.get(round(k_ / fps, 5))
        if tf_:
            pose_parts(tf_)
    bpy.context.view_layer.update()
    left_ = list(g((1.0, 0.0, 0.0)).normalized())
    for m_ in MARKS or []:
        if m_.get("role") == "hold" and m_.get("purpose") == "power_wrap" and m_.get("palm_dir") and "_web" not in m_:
            m_["_web"] = L.web_point(m_, m_["palm_dir"])[0]        # the tang: the run's palm side up to the web
    report["contact_view"] = {"clip": cid, "frame": k_, "regions_cm2": L.object_regions(MARKS, left_),
                              "palm_check": {sd: L.palm_check(sd) for sd in ("r", "l")}}
    report["contact_view"]["map"] = L.contact_map(("r", "l"), band_cm=float(cv.get("band_cm", 0.2)), marks=MARKS, left_dir=left_)
    report["contact_view"]["pictures"] = L.contact_pictures(os.path.join(OUT, "contact"), centre=list(mark_world("grip")),
                                                            frame_part="Root")
    json.dump(report, open(os.path.join(OUT, "hands.json"), "w", encoding="utf-8"), indent=1, default=str)
    print("GUNKIT contact view done")
    sys.exit(0)
if job.get("skin_check"):
    # the hand clips as made, replayed on this skin (the gun's mesh in gun_fbx): no hand is moved; each frame's
    # clearance, the firing hand's hold and each hand's contact rules on its own contact are measured, so a skin
    # thicker than the one the clips were made on shows as presses, a thinner one as gaps
    sk = job["skin_check"]
    soft = [c_["segment"] + "*" for c_ in (STYLE or {}).get("soft_contacts", [])]
    allow = max(0.0, 0.2 - GLOVE)

    def _mark(tg):
        if tg["space"] != "gun" or tg["point"] is None:
            return None
        n_ = tg["name"]
        return n_ if n_ in facts["marks"] else ("mag_grab" if n_ in facts["parts"] and "mag_grab" in facts["marks"] else None)

    res = {"skin": sk.get("name"), "gun_fbx": job["gun_fbx"], "clips": {}}
    for cid, clip in job["clips"].items():
        path = os.path.join(sk["clips_dir"], job.get("prefix", "A_%s_Hands_" % facts["name"]) + cid + ".pose.json")
        if not os.path.exists(path):
            res["clips"][cid] = {"missing": path}
            continue
        nm = "skin_" + cid
        L.load_clip(nm, path)
        frames, fps = L._frames(nm)
        tr = job["tracks"].get(cid)
        tframes = {round(f["t"], 5): f["bones"] for f in (tr["frames"] if tr else [])}
        tl = {round(f["t"], 3): f for f in clip["frames"]}
        rows = []
        over, worst, not_hold = 0, 0.0, 0
        crow = []
        for i, fr in enumerate(frames):
            t = round(i / fps, 5)
            L._apply(fr)
            rest_parts()
            if t in tframes:
                pose_parts(tframes[t])
            cl = L.clearance(parts="both", ignore=["palm*"] + soft, top=1)
            w_ = cl["worst_cm"]
            worst = max(worst, w_)
            over += 1 if w_ > allow else 0
            g_ = L.grip("both", hold=False)
            held = g_["r"]["holding"] and (g_["r"]["grasping"] or len([d for d in g_["r"].get("digits_touching", []) if d != "thumb"]) >= 2)
            not_hold += 0 if held else 1
            tf = tl.get(round(t, 3))
            if tf is not None:
                for side in ("r", "l"):
                    h = tf["hands"][side]
                    on = _mark(h["b"]) if h["w"] >= 0.999 or h["a"] == h["b"] else (_mark(h["a"]) if h["w"] <= 0.001 else None)
                    cm_ = (((STYLE.get("hands") or {}).get(side) or {}).get("contact") or {}).get("mark")
                    if on and on == cm_:
                        cn = contacts_now(side)
                        if cn:
                            crow.append((t, side, cn))
            rows.append({"t": round(t, 3), "clearance_cm": w_, "holding_r": held,
                         "deepest": (cl.get("contacts") or [{}])[0].get("segment") if w_ > allow else None})
        res["clips"][cid] = {"frames": len(frames), "clearance_worst_cm": round(worst, 2), "clearance_over_frames": over,
                             "not_holding_r_frames": not_hold, "contacts": summarise_contacts(crow) if crow else None,
                             "per_frame": rows}
    json.dump(res, open(os.path.join(OUT, "skin_check.json"), "w", encoding="utf-8"), indent=1, default=str)
    print("GUNKIT skin check done")
    sys.exit(0)
REF = None
if job.get("reference_pose"):
    # a reference hold (a pack clip retargeted to these arms): each hand against the gun's body bone, every finger
    # joint's turn; taken as the home holds instead of solving them
    REF = json.load(open(job["reference_pose"], encoding="utf-8"))
    for sd, mk in (("r", "grip"), ("l", facts.get("home_l", "support"))):
        h_ = REF["hands"].get(sd)
        if not h_:
            continue
        rel_ = Matrix([h_["rel_to_root"][i * 4:(i + 1) * 4] for i in range(4)])
        GRASPS[(sd, mk, None, ())] = (bone_world(mark_bone(mk)).inverted() @ (bone_world("Root") @ rel_),
                                      {n: Quaternion(q) for n, q in h_["fingers"].items()}, True)
    report["reference_pose"] = job["reference_pose"]
L.steps.phase("home holds (both hands)")
L._deadline = by(0.55)
home_r = grasp("r", "grip", start=start)
L._deadline = by(0.80)
if home_r and STYLE and "support" in facts["marks"]:
    # the firing hand closes on the gun first; the support hand then wraps over it, against the gun and the
    # firing hand where it now is (a real two-hand grip is built in that order)
    if "r" in CLAV_SET:
        L.arm.pose.bones["clavicle_r"].rotation_quaternion = CLAV_SET["r"]
        bpy.context.view_layer.update()
    L._put_hand("r", bone_world("Root") @ home_r[0])
    for _n, _q in home_r[1].items():
        L.arm.pose.bones[_n].rotation_quaternion = _q
    bpy.context.view_layer.update()
home_l = grasp("l", facts.get("home_l", "support"), start=start) if "support" in facts["marks"] else None
if home_l and job.get("solver_two_pass", False) and STYLE and style_plan("r", "grip") is not None:
    # the firing hand solved again with the support hand on: the two hands meet (thumbs stacked, fingers wrapped)
    L._put_hand("l", bone_world("Root") @ home_l[0])
    for _n, _q in home_l[1].items():
        L.arm.pose.bones[_n].rotation_quaternion = _q
    bpy.context.view_layer.update()
    L.snapshot("save", "with_support")
    GRASPS.pop(("r", "grip", None, ()), None)
    home_r = grasp("r", "grip", start="with_support")
    # and the support hand once more on the firing hand where it now is
    L._put_hand("r", bone_world("Root") @ home_r[0])
    for _n, _q in home_r[1].items():
        L.arm.pose.bones[_n].rotation_quaternion = _q
    bpy.context.view_layer.update()
    L.snapshot("save", "with_firing")
    GRASPS.pop(("l", facts.get("home_l", "support"), None, ()), None)
    home_l = grasp("l", facts.get("home_l", "support"), start="with_firing")
for side, gr in (("r", home_r), ("l", home_l)):
    if gr:
        if side in CLAV_SET:
            L.arm.pose.bones["clavicle_" + side].rotation_quaternion = CLAV_SET[side]
            bpy.context.view_layer.update()
        L._put_hand(side, bone_world("Root") @ gr[0])
        for n, q in gr[1].items():
            L.arm.pose.bones[n].rotation_quaternion = q
bpy.context.view_layer.update()
MEND_SIDES = tuple(job.get("mend_sides", ("l",)))
TRIGGER = {}
if STYLE and STYLE.get("trigger_clips") and (STYLE["hands"].get("r") or {}).get("trigger"):
    L.snapshot("save", "before_trigger")
    apply_style("r", trigger=True)
    TRIGGER = {n: L.arm.pose.bones[n].rotation_quaternion.copy() for n in FINGER_BONES["r"] if n.startswith("index")}
    L.snapshot("load", "before_trigger")
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
def hold_geometry():
    """Each hand's hold in gun space (cm; +x the gun's left, +y forward, +z up): where its wrist, middle knuckle,
    web (between the thumb's base and the index knuckle), middle fingertip and thumb tip are, and which way its
    fingers point (wrist to middle knuckle, a unit vector)."""
    out = {}
    for sd in ("r", "l"):
        w = L._bw(L._n("hand", sd)).translation
        k = L._bw(L._n("finger", sd, "middle", "01")).translation
        web = L._bw(L._n("finger", sd, "thumb", "01")).translation.lerp(L._bw(L._n("finger", sd, "index", "01")).translation, 0.5)
        Ri = RA.matrix_world.inverted()
        fk = lambda v: Vector(((Ri @ v)[0] * 100.0, -(Ri @ v)[1] * 100.0, (Ri @ v)[2] * 100.0))   # noqa: E731  the facts' frame
        gp = lambda v: [round(x, 1) for x in fk(v)]      # noqa: E731
        d = fk(k) - fk(w)
        out[sd] = {"wrist": gp(w), "knuckle": gp(k), "web": gp(web), "middle_tip": gp(L._finger_tip("middle", sd)),
                   "thumb_tip": gp(L._finger_tip("thumb", sd)), "fingers_point": [round(x, 2) for x in d.normalized()],
                   "thumb_rules": L._thumb_report(sd, L._thumb_limits())[1],
                   "thumb_joints": {j: gp(L._bw(L._n("finger", sd, "thumb", j)).translation) for j in ("01", "02", "03")},
                   "thumb_via": getattr(L, "_last_via", None),
                   "thumb_clearance": [(c_["segment"], c_["depth_cm"]) for c_ in L.clearance(parts={"r": "right", "l": "left"}[sd], top=6)["contacts"] if c_["segment"].startswith("thumb")]}
    return out


report["hold_geometry"] = hold_geometry()
report["hold_contacts"] = {sd: contacts_now(sd) for sd in ("r", "l")} if STYLE else None
L.steps.phase("render the home hold")
L._deadline = by(0.95)
if job.get("render") and T0 + BUDGET - _time.time() < 45:
    report.setdefault("budget_cut", []).append("home hold render skipped: under 45 s left")
if job.get("render") and T0 + BUDGET - _time.time() >= 45:
    report["hold_pictures"] = L.render(views=("eye", "right", "left", "top"), size=(640, 360),
                                       ortho_cm=job.get("render_ortho_cm", 30.0), centre=list(mark_world("grip")))
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


ARC_CM = float(job.get("arc_cm", 5.5))
REGRIP = float(job.get("regrip", 0.2))      # the share of a hold-to-hold move spent letting go, and taking hold
OPEN = {sd: {n: Quaternion() for n in FINGER_BONES[sd]} for sd in ("l", "r")}   # the digits at rest: an open hand


def _face_world(tgt):
    """The gun surface's facing at a gun-space target's mark (the style's face, else the facts' normal), in the world."""
    if tgt.get("space") != "gun" or tgt.get("point") is None:
        return None
    name = tgt.get("name")
    mark = name if name in facts["marks"] else ("mag_grab" if name in facts["parts"] and "mag_grab" in facts["marks"] else None)
    n = FACE.get(mark) or (facts.get("normals") or {}).get(mark)
    if not n:
        return None
    return (RA.matrix_world.to_quaternion() @ g(n)).normalized()


def press_now(side, tree):
    """What a moving hand still does wrong: its presses past the allowance (kept 0.05 cm inside it, as the clearance
    check samples finer) and the grip's rules (the back of the hand toward the gun)."""
    pen = L.hand_presses(side, tree, GLOVE, allow_cm=0.15, palm_allow_cm=0.35, other=True, soft=SOFT)[0]
    return pen + 5.0 * len(L.grip(side, hold=False).get(side, {}).get("bad", []))


def arc(a, b, w):
    """A hand going from one hold on the gun to another goes round the gun, not through it: lifted off along both
    surfaces' facing, most at the middle of the way. A hand coming to a hold from off the gun (a pouch, the chest), or
    leaving for one, comes in and goes out along that hold's facing the same way."""
    if not (0.0 < w < 1.0) or a == b:
        return None
    na, nb = _face_world(a), _face_world(b)
    if na is None and nb is None or (a.get("name") == b.get("name")):
        return None
    if na is None or nb is None:
        return (na or nb).normalized() * (ARC_CM / 100.0) * math.sin(math.pi * w)
    d = na + nb
    if d.length < 1e-6:
        d = na
    return d.normalized() * (ARC_CM / 100.0) * math.sin(math.pi * w)


CLAV = {}                    # the clavicles' turns in the hold: each frame starts from them
ARM_HOLD = {}                # the arm bones' turns in the hold


def arm_from_hold(side):
    names = [L._n("upperarm", side), L._n("lowerarm", side), L._n("hand", side)] + [n for _, n in L._twist_bones(side)]
    if side not in ARM_HOLD:
        ARM_HOLD[side] = {n: L.arm.pose.bones[n].rotation_quaternion.copy() for n in names}
    for n, q in ARM_HOLD[side].items():
        L.arm.pose.bones[n].rotation_quaternion = q
    bpy.context.view_layer.update()


def elbow_bend(side):
    return L._arm_report(side, L._limits()[0])[0].get("elbow_bend_deg", 90.0)


def shoulder_reach(side, H):
    """An arm at full stretch reaches with the shoulder too, as a shooter's does: the clavicle turned toward the hand,
    2 degrees at a time up to 16 (about 4 cm at the shoulder), until the elbow keeps 5 degrees past its locked limit.
    Each frame starts from the hold's clavicle, so a reach lasts only while the arm needs it. Returns the degrees."""
    cn = "clavicle_" + side
    if cn not in L.arm.pose.bones:
        return 0.0
    pb = L.arm.pose.bones[cn]
    if side not in CLAV:
        CLAV[side] = pb.rotation_quaternion.copy()
    if pb.rotation_quaternion != CLAV[side]:
        pb.rotation_quaternion = CLAV[side]
        bpy.context.view_layer.update()
        L._put_hand(side, H)
    need = L._limits()[0]["elbow_bend_min_deg"] + 5.0
    if elbow_bend(side) >= need:
        return 0.0
    C = L._bw(cn).translation
    S = L._bw(L._n("upperarm", side)).translation
    axis = (S - C).cross(H.translation - C)
    if axis.length < 1e-9:
        return 0.0
    axis.normalize()
    deg = 0.0
    while deg < 16.0 and elbow_bend(side) < need:
        deg += 2.0
        pb.rotation_quaternion = CLAV[side]
        bpy.context.view_layer.update()
        L._turn_about(cn, axis, deg, C)
        bpy.context.view_layer.update()
        L._put_hand(side, H)
        bpy.context.view_layer.update()
    return deg


def repair(side):
    """A frame's hand that presses into the gun or the other hand, or whose arm is past its limits, mended by the one
    score (Pose Lab's repair_hand: the hand moved and turned, the elbow swung, drawn back to where the motion put
    it). Returns the repair's parts, or None when the frame needed none."""
    if MARKS and hasattr(L, "repair_frame"):
        # on the contact ruler (the drawn skin, past its give; the arm's excess), as the holds were judged
        rr_ = L.repair_frame(side, glove_cm=GLOVE, other=True, keep_w=float(job.get("repair_keep_w", 6.0)),
                             generations=int(job.get("repair_generations", 6)), pop=int(job.get("repair_pop", 8)))
        if rr_ is None:
            return None
        return {"press": rr_["after"]["press_cm2"] + rr_["after"]["hand_press_cm2"],
                "arm_bad": [] if rr_["after"]["arm_excess_deg"] <= 0 else ["arm %.0f deg past its limits" % rr_["after"]["arm_excess_deg"]],
                "moved_cm": rr_["moved_cm"]}
    # only a real fault: a press past its allowance, or an arm rule broken (a grip rule a hand on its way breaks
    # is the motion's, not the repair's)
    if L.hand_presses(side, None, GLOVE, other=True, soft=SOFT)[0] <= 0.0 and not L._arm_report(side, L._limits()[0])[1]:
        return None
    return L.repair_hand(side, glove_cm=GLOVE, other=True, soft=SOFT, keep_w=float(job.get("repair_keep_w", 6.0)),
                         span_cm=float(job.get("repair_span_cm", 10.0)), generations=int(job.get("repair_generations", 6)),
                         pop=int(job.get("repair_pop", 8)))


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
L.steps.phase("the holds the clips need")
L.steps.wrap_dict(globals(), ["repair", "target_matrix", "arm_from_hold", "shoulder_reach", "end_joints_flat"])
# each where the clips first use it: the gun posed as on the first frame the hand arrives (a working hold is taken
# with the gun pulled in, where the arm reaches it), the other hand on its own hold then, so the solver keeps clear
# of it
def mark_of(tg):
    if tg["space"] != "gun" or tg["point"] is None:
        return None
    n = tg["name"]
    return n if n in facts["marks"] else ("mag_grab" if n in facts["parts"] and "mag_grab" in facts["marks"] else None)


need = {}
for cid_, clip in job["clips"].items():
    stays = {}
    for fr in clip["frames"]:
        for side, h in fr["hands"].items():
            for k in ("a", "b"):
                mk = mark_of(h[k])
                if not mk:
                    continue
                if (side, mk) not in need:
                    need[(side, mk)] = (fr, None, False)
                on = k == "b" and h["w"] >= 0.999 or k == "a" and h["w"] <= 0.001
                if on:
                    stays.setdefault((side, mk), []).append(fr)
    for sk, frs in stays.items():
        if not need[sk][2]:
            need[sk] = (frs[len(frs) // 2], cid_, True)       # the middle of the first clip's stay on the hold
for (side, mk), (fr, cid_, _) in sorted(need.items()):
    key = (side, mk, None, ())
    if key in GRASPS:
        continue
    L.snapshot("load", "hold")
    rest_parts()
    if job.get("solve_at_use", True):
        gun_pose(fr["gun"])
        tr_ = job["tracks"].get(cid_) if cid_ else None
        if tr_ and not free_mark(mk):
            at_t = {round(f["t"], 5): f["bones"] for f in tr_["frames"]}.get(round(fr["t"], 5))
            if at_t:
                pose_parts(at_t)                          # the slide back on a press check, as the hand holds it
        o = "l" if side == "r" else "r"
        ho = fr["hands"][o]
        omk = mark_of(ho["b"] if ho["w"] >= 0.5 else ho["a"])
        if omk and (o, omk, None, ()) in GRASPS:
            rel, fingers, _ = GRASPS[(o, omk, None, ())]
            B = RA.matrix_world if free_mark(omk) else bone_world(mark_bone(omk))
            L._put_hand(o, B @ rel)
            for n, q in fingers.items():
                L.arm.pose.bones[n].rotation_quaternion = q
        bpy.context.view_layer.update()
    L.snapshot("save", "at_use")
    grasp(side, mk, start="at_use")
L.snapshot("load", "hold")
report["holds"] = {"%s:%s" % (k[0], k[1]): ("found" if v[2] else "laid") for k, v in GRASPS.items()}

# --- the clips -------------------------------------------------------------------------------------------------
L.steps.phase("clips")
for cid, clip in job["clips"].items():
    L.steps.phase("clip " + cid, level=1)
    L.steps.phase("key the frames (hands placed, repaired, walls read)", level=2)
    tr = job["tracks"].get(cid)
    tframes = {round(f["t"], 5): f["bones"] for f in (tr["frames"] if tr else [])}
    name = job.get("prefix", "A_%s_Hands_" % facts["name"]) + cid
    L.snapshot("load", "hold")
    L.record_clip("start", name, fps=clip["fps"])
    carrying = {}            # part -> (hand, the part's bone against the hand)
    clip_contacts = []       # (t, side, contacts) on frames a hand is on its own contact
    resolved = []
    repairs = []             # the frames the one repair mended
    moves = []               # each frame's hands as the player sees them, for the motion check
    walled = []              # frames where a hand is past a wall (the clip is then not written)
    for fr in clip["frames"]:
        L._cnt("frames")
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
            # between two holds on the gun the hand lets go first (its fingers open where they are), moves open,
            # and closes on the new hold once there: wrapped fingers never drag through the gun
            regrip = REGRIP > 0.0 and mark_of(h["a"]) and mark_of(h["b"]) and mark_of(h["a"]) != mark_of(h["b"]) and 0.0 < h["w"] < 1.0
            wm = min(1.0, max(0.0, (h["w"] - REGRIP) / (1.0 - 2.0 * REGRIP))) if regrip else h["w"]
            H = blend(Ma, Mb, wm)
            lift = arc(h["a"], h["b"], wm)
            if lift is not None:
                H = Matrix.Translation(lift) @ H
            if job.get("arm_from_hold", True):
                # each frame's arm starts from the hold's, as the solver's does: the forearm's roll is the hand's
                # turn from there, not the sum of every frame's change (that wound the forearm the long way round)
                arm_from_hold(side)
            L._put_hand(side, H)
            if STYLE and job.get("shoulder_reach", True):
                shoulder_reach(side, H)                   # an arm at full stretch: the shoulder reaches too
            on_gun = h["b"].get("space") == "gun"
            resting = on_gun and (h["w"] >= 1.0 or h["a"] == h["b"])   # a hand waiting off the gun is mended too
            mb = mark_of(h["b"])
            carrying_out = (on_gun and mb and free_mark(mb) and h["b"].get("point") is not None
                            and (Vector(h["b"]["point"]) - Vector(facts["marks"][mb])).length > 1.5)
            if side in MEND_SIDES and (not resting or carrying_out):
                # a hand on its way between holds keeps the last hold's turn while the arm moves: the wrist back
                # inside its range, turned toward the forearm's line (Pose Lab's mend keeps the hand's back out of
                # the gun)
                L._mend_hand(side, fingers=True)
                end_joints_flat(side)
            fw = h["w"]
            if h["a"].get("space") == "gun" and not on_gun:
                fw = min(1.0, fw / 0.3)                   # a hand letting go opens first, then lifts off
            if regrip and fa and fb:
                # the four fingers open and close; the thumb, lying along the gun, goes from one hold's turn to the
                # next with the hand (opened to rest, it would swing into the frame)
                op = {k: (fb[k] if k.startswith("thumb") else OPEN[side][k]) for k in fb}
                st = {k: (fa[k].slerp(fb[k], wm) if k.startswith("thumb") and k in fa else None) for k in fb}
                if h["w"] < REGRIP:
                    fa, fb, fw = fa, {k: st[k] or op[k] for k in op}, h["w"] / REGRIP
                elif h["w"] > 1.0 - REGRIP:
                    fa, fb, fw = {k: st[k] or op[k] for k in op}, fb, (h["w"] - 1.0 + REGRIP) / REGRIP
                else:
                    fa, fb, fw = {k: st[k] or op[k] for k in op}, None, 0.0
            for n in FINGER_BONES[side]:
                qa = (fa or {}).get(n)
                qb = (fb or {}).get(n)
                if qa is not None and qb is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qa.slerp(qb, fw)
                elif qb is not None and fw > 0.5 or qa is None and qb is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qb
                elif qa is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qa
            on_home = bool(MARKS) and resting and mark_of(h["b"]) == ((PUR or {}).get(side) or {}).get("mark")
            if STYLE and job.get("repair", True) and not on_home:
                # one repair, only where the frame needs it; a hand resting on its home hold is that hold (searched
                # and gated on the contact model), so it is left as it is
                rr_ = repair(side)
                if rr_ is not None:
                    repairs.append({"t": t, "side": side, "press": rr_["press"], "arm_bad": rr_["arm_bad"],
                                    "moved_cm": rr_["moved_cm"]})
            if TRIGGER and side == "r" and cid in STYLE.get("trigger_clips", []):
                for n, q in TRIGGER.items():              # the trigger finger on the trigger for the shot
                    L.arm.pose.bones[n].rotation_quaternion = q
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
        mv = {}
        for sd in ("r", "l"):
            fr_b = L._finger_report(sd, _FL)[0]
            th_b = L._thumb_report(sd, _TL)[0]
            bends = {k: v[0] for k, v in fr_b.items()}
            bends.update({k: v[0] for k, v in th_b.items() if k.startswith("thumb_")})
            mv[sd] = {"at": list(L._to(hands_now[sd].translation, "view")), "bends": bends}
        moves.append({"t": fr["t"], "hands": mv})
        # the contact rules of each hand on its own contact hold, measured on this frame
        if STYLE and job.get("contact_checks", True):
            for side in ("r", "l"):
                h = fr["hands"][side]
                on = mark_of(h["b"]) if h["w"] >= 0.999 or h["a"] == h["b"] else (mark_of(h["a"]) if h["w"] <= 0.001 else None)
                cm_ = (((STYLE.get("hands") or {}).get(side) or {}).get("contact") or {}).get("mark")
                if on and on == cm_:
                    cn = contacts_now(side)
                    if cn:
                        clip_contacts.append((fr["t"], side, cn))
        for sd in ("r", "l"):
            w_ = L.wall_faults(sd, other=True)
            if w_:
                walled.append({"t": round(fr["t"], 3), "side": sd, "walls": {k: round(v, 2) for k, v in w_.items()}})
        L.record_clip("key", seconds=fr["t"])
    L.record_clip("stop")
    if walled:
        # the walls are a real body's limits and physics: a clip with any frame past one is not written, only reported
        report["clips"][cid] = {"clip": name, "written": [], "blocked": "frames past the walls: %d" % len(walled),
                                "walls": walled[:12]}
        print("GUNKIT HANDS: %s not written, %d frames past the walls" % (cid, len(walled)))
        continue
    L.steps.phase("save the clip", level=2)
    saved = L.save_clip(name, formats=("pose.json", "fbx"), root_name="root")
    L.steps.phase("check set", level=2)
    try:
        soft = [c["segment"] + "*" for c in (STYLE or {}).get("soft_contacts", [])]
        # the firing hand holds the gun on every frame of every clip: its palm on the grip, its thumb opposing its fingers
        firing = ("r" if (CHAR or {}).get("handed", "right") == "right" else "l",) if STYLE else ()
        cs = L.check_set(name, ignore=["palm*"] + soft, sides="both", clearance_max_cm=max(0.0, 0.2 - GLOVE),
                         hold_sides=firing)
    except Exception as e:
        cs = {"error": str(e)[:300]}
    if (STYLE or {}).get("soft_contacts"):
        # the style's soft contacts, every 0.1 s: each one's deepest press against its own most
        worst = {c["segment"]: 0.0 for c in STYLE["soft_contacts"]}
        k = 0.0
        while k <= clip["seconds"] + 1e-6:
            L.pose_clip(name, k)
            for c in L.clearance(parts="both", top=40)["contacts"]:
                for sc in STYLE["soft_contacts"]:
                    if c["segment"].startswith(sc["segment"]):
                        worst[sc["segment"]] = max(worst[sc["segment"]], c["depth_cm"])
            k += job.get("diagnose_step", 0.05)
        if isinstance(cs, dict):
            cs["soft_contacts"] = {sc["segment"]: {"worst_cm": round(worst[sc["segment"]], 2), "max_cm": sc["max_cm"],
                                                   "ok": worst[sc["segment"]] <= sc["max_cm"]} for sc in STYLE["soft_contacts"]}
    if clip_contacts and isinstance(cs, dict):
        cs["contacts"] = summarise_contacts(clip_contacts)
    L.steps.phase("verify: skin, view, motion, hold gate", level=2)
    if isinstance(cs, dict) and job.get("verify", True):
        # the drawn skin, every verify_step s (the capsules test a body slightly thinner than the picture's)
        skin_rows, k = [], 0.0
        while k <= clip["seconds"] + 1e-6:
            L.pose_clip(name, k)
            sp_ = L.skin_presses("both", glove_cm=GLOVE, other=True)
            if not sp_["ok"]:
                skin_rows.append({"t": round(k, 2), "r": sp_["r"], "l": sp_["l"]})
            k += float(job.get("verify_step", 0.1))
        worst_ = {sd: max([0.0] + [max(x[sd]["gun_cm"], x[sd]["hand_cm"]) for x in skin_rows]) for sd in ("r", "l")}
        cs["skin"] = {"frames_bad": len(skin_rows), "worst_cm": worst_, "first": skin_rows[:3], "ok": not skin_rows}
        # the eye at the clip's middle: the sights over the hands, the arms' share of the view, the hands shown
        tm = clip["seconds"] / 2.0
        L.pose_clip(name, tm)
        frm = min(clip["frames"], key=lambda f: abs(f["t"] - tm))
        gun_pose(frm["gun"])
        rest_parts()
        sights = [lab_gun(mark_world(m)) for m in ("slide_rear", "slide_front") if m in facts["marks"]]
        vr = L.view_report(sights=sights)
        vr["ok"] = all(v >= float(job.get("sight_min", 0.8)) for v in vr["sights"]) and vr["lower_left"] <= float(job.get("lower_left_max", 0.6))
        cs["view"] = vr
        cs["motion"] = MO.check(moves)
        if MARKS:
            # the hold gate: the purposes of each hand on its home hold, every verify_step s (the trigger is no
            # touch except in the clips the finger is on it)
            mk_ = [m for m in MARKS if not (m.get("role") == "notouch" and cid in (STYLE or {}).get("trigger_clips", [])
                                              and m["part"] == facts["parts"].get("trigger", {}).get("bone"))]
            rows_, k = [], 0.0
            while k <= clip["seconds"] + 1e-6:
                L.pose_clip(name, k)
                fr_ = min(clip["frames"], key=lambda f: abs(f["t"] - k))
                gun_pose(fr_["gun"])
                rest_parts()
                on_ = tuple(sd for sd in ("r", "l") if mark_of(fr_["hands"][sd]["b"] if fr_["hands"][sd]["w"] >= 0.5 else fr_["hands"][sd]["a"])
                            == ((PUR or {}).get(sd) or {}).get("mark"))
                if on_:
                    hg_ = L.hold_gate(mk_, sides=on_, glove_cm=GLOVE, skin=False)
                    if not hg_["pass"]:
                        rows_.append({"t": round(k, 2), **{sd: [p_["purpose"] for p_ in hg_[sd]["purposes"] if not p_["met"]]
                                                          + (["body"] if hg_[sd]["body_rules"] else []) + (["press"] if hg_[sd]["press"] > 0 else [])
                                                          for sd in on_ if sd in hg_}})
                k += float(job.get("verify_step", 0.1))
            cs["hold_gate"] = {"frames_failed": len(rows_), "first": rows_[:4], "pass": not rows_}
        cs["repairs"] = {"frames": len(repairs), "first": repairs[:4]}
    if cid in job.get("diagnose", []):
        # which rule breaks when, every 0.1 s: the clip posed, each hand's anatomy and grip rules and the deepest
        # contact, with what each hand is doing then (its targets)
        rows = []
        k = 0.0
        while k <= clip["seconds"] + 1e-6:
            L.pose_clip(name, k)
            fr = min(clip["frames"], key=lambda f: abs(f["t"] - k))
            an, gr = L.anatomy("both"), L.grip("both", hold=False)
            cl = L.clearance(parts="both", ignore=["palm*"], top=2)
            rows.append({"t": round(k, 2), "l_doing": [fr["hands"]["l"]["a"].get("name"), fr["hands"]["l"]["b"].get("name"), round(fr["hands"]["l"]["w"], 2)],
                         "anatomy": {sd: an.get(sd, {}).get("bad", []) for sd in ("l", "r")},
                         "grip": {sd: gr.get(sd, {}).get("bad", []) for sd in ("l", "r")}, "clearance": cl["contacts"]})
            k += job.get("diagnose_step", 0.05)
        report.setdefault("diagnose", {})[cid] = rows
    L.steps.phase("expectations (visible, faces the eye)", level=2)
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
L.steps.end_all()
report["steps"] = L.steps.write(os.path.join(OUT, "steps.json"), {"run": "gunkit hands", "gun": facts["name"],
                                                                   "clips": list(job["clips"])})["wall_s"]
json.dump(report, open(os.path.join(OUT, "hands.json"), "w", encoding="utf-8"), indent=1, default=str)
print("GUNKIT HANDS: %s, %d clips, hold %s" % (facts["name"], len(report["clips"]), report["hold"]))
