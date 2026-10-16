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

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
sys.path.insert(0, job["poselab"])
import lab as PL  # noqa: E402

OUT = job["out"]
os.makedirs(OUT, exist_ok=True)
facts = job["facts"]
A = job["arms"]
rigs = {"gunkit": {"title": "Gun Kit: %s on the shared arms" % facts["name"], "folder": A["folder"], "arms": A["arms"],
                   "idle": A["idle"], "gun": job["gun_fbx"], "gun_offset": [0.0, 0.0, 0.0], "eye": A["eye"],
                   "styled": bool(job.get("character"))}}            # the character's colours and the gun's finishes
rigs_file = os.path.join(OUT, "gunkit_rigs.json")
json.dump(rigs, open(rigs_file, "w", encoding="utf-8"), indent=1)
L = PL.Lab(rigs_file, OUT)
L.load_rig("gunkit")
RA = L.rifle_arm
report = {"gun": facts["name"], "clips": {}, "notes": []}
STYLE = job.get("style")
CHAR = job.get("character")
GLOVE = float(job.get("glove_cm", 0.0))
PALM_CM = 1.5 + GLOVE
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
rest_parts()
L.pose_idle()
shift = palm_r() - mark_world("grip")
L.rifle_rest = Matrix.Translation(shift) @ L.rifle_rest
L._place_rifle()
FINGER_BONES = {s: [pb.name for pb in L.arm.pose.bones if any(pb.name.startswith(f + "_") and pb.name.endswith("_" + s) for f in PL.FINGERS)] for s in ("l", "r")}
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
        else:
            wrap(side, fi, f["max_curl"], tree)
    t = fingers.get("thumb")
    if t and t["pose"] == "straight":
        set_thumb(side, t["curl"][1], t["curl"][2])
    elif t and t["pose"] == "wrap":
        thumb_wrap(side, t["max_curl"], tree)
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


def grasp(side, mark, part=None, offset=None, start=None):
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
    back = (RA.matrix_world.to_quaternion() @ g((0.0, -1.0, 0.0))).normalized()
    slid = 0.0
    if start:
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


if STYLE and STYLE.get("stance"):
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
if job.get("place_search", True) and "support" in facts["marks"]:
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
home_r = grasp("r", "grip", start=start)
home_l = grasp("l", facts.get("home_l", "support"), start=start) if "support" in facts["marks"] else None
for side, gr in (("r", home_r), ("l", home_l)):
    if gr:
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


ARC_CM = float(job.get("arc_cm", 5.5))


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


def arc(a, b, w):
    """A hand going from one hold on the gun to another goes round the gun, not through it: lifted off along both
    surfaces' facing, most at the middle of the way."""
    if not (0.0 < w < 1.0) or a == b:
        return None
    na, nb = _face_world(a), _face_world(b)
    if na is None or nb is None or (a.get("name") == b.get("name")):
        return None
    d = na + nb
    if d.length < 1e-6:
        d = na
    return d.normalized() * (ARC_CM / 100.0) * math.sin(math.pi * w)


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
            lift = arc(h["a"], h["b"], h["w"])
            if lift is not None:
                H = Matrix.Translation(lift) @ H
            L._put_hand(side, H)
            resting = h["w"] >= 1.0 and h["b"].get("space") == "gun" or (h["a"] == h["b"])
            if side in MEND_SIDES and not resting:
                # a hand on its way between holds keeps the last hold's turn while the arm moves: the wrist back
                # inside its range, turned toward the forearm's line (Pose Lab's mend keeps the hand's back out of
                # the gun)
                L._mend_hand(side, fingers=True)
                end_joints_flat(side)
            for n in FINGER_BONES[side]:
                qa = (fa or {}).get(n)
                qb = (fb or {}).get(n)
                if qa is not None and qb is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qa.slerp(qb, h["w"])
                elif qb is not None and h["w"] > 0.5 or qa is None and qb is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qb
                elif qa is not None:
                    L.arm.pose.bones[n].rotation_quaternion = qa
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
        L.record_clip("key", seconds=fr["t"])
    L.record_clip("stop")
    saved = L.save_clip(name, formats=("pose.json", "fbx"), root_name="root")
    try:
        soft = [c["segment"] + "*" for c in (STYLE or {}).get("soft_contacts", [])]
        cs = L.check_set(name, ignore=["palm*"] + soft, sides="both", clearance_max_cm=max(0.0, 0.2 - GLOVE))
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
            k += 0.1
        if isinstance(cs, dict):
            cs["soft_contacts"] = {sc["segment"]: {"worst_cm": round(worst[sc["segment"]], 2), "max_cm": sc["max_cm"],
                                                   "ok": worst[sc["segment"]] <= sc["max_cm"]} for sc in STYLE["soft_contacts"]}
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
            k += 0.1
        report.setdefault("diagnose", {})[cid] = rows
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
