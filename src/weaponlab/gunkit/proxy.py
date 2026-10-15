"""Proxy guns: one test model per action, simple shapes with the action's real moving parts at plausible places, so the
whole chain (rig, gun clips, hand clips, checks, export) runs before any real model exists. A proxy is not art and
never ships: every picture of one is labelled a test model.

proxy(action_id) gives a parts map (weaponlab-partsmap/1) and the shapes to build: the same parts map a user writes
for a model of their own, so a proxy goes through the rig step as a real model does.

weaponlab-partsmap/1 (gun space: cm, +Y to the muzzle, +Z up, +X the gun's left; origin the bolt face):
    {"contract": "weaponlab-partsmap/1", "name": "AK47", "action": "ak_handle",
     "model": "<a .blend, .fbx, .obj or .glb>", "units": "cm" | "m" | "mm", "forward": "+Y", "up": "+Z",
     "origin": [x, y, z] (the bolt face in the model's own units and axes),
     "parts": {"carrier": {"objects": ["Carrier", "Handle"], "axis": [0, -1, 0], "travel_cm": 12.0}, ...
               "dustcover": {"objects": [...], "axis": [...], "turn_deg": 110, "pivot": [x, y, z]}},
     "marks": {"grip": [x, y, z], ...}, "mark_parts": {"handle": "carrier"}, "magazine": {"lips": [x, y, z]},
     "normals": {"port": [x, y, z]}}
Marks, pivots and lips are in gun space (cm) already; axes are unit vectors in gun space. Objects not in any part
are the body (the Root bone)."""
import copy

from . import actions as A

CONTRACT = "weaponlab-partsmap/1"


def _box(name, size, at, part=None):
    return {"name": name, "shape": "box", "size": list(size), "at": list(at), "part": part}


def _cyl(name, d, length, at, part=None, along="y"):
    return {"name": name, "shape": "cyl", "size": [d, length], "at": list(at), "part": part, "along": along}


def _long_gun(barrel=40.0, mag=True):
    """A rifle's body: receiver, barrel, handguard, stock, grip; the marks every long gun has."""
    shapes = [_box("Receiver", (4.0, 24.0, 7.0), (0.0, -4.0, 0.5)),
              _cyl("Barrel", 2.0, barrel, (0.0, barrel / 2.0, 0.0)),
              _box("Handguard", (5.0, 22.0, 6.0), (0.0, 16.0, -0.5)),
              _box("Stock", (4.0, 26.0, 10.0), (0.0, -29.0, -3.0)),
              _box("Grip", (3.0, 4.0, 10.0), (0.0, -10.0, -8.0))]
    marks = {"grip": [0.0, -10.0, -8.0], "support": [0.0, 16.0, -3.5], "muzzle": [0.0, barrel, 0.0],
             "trigger": [0.0, -6.5, -5.5], "port": [-2.2, 1.0, 1.5]}
    if mag:
        shapes.append(_box("Magazine", (2.5, 6.0, 18.0), (0.0, 3.0, -11.0), "magazine"))
        marks.update({"mag_well": [0.0, 3.0, -2.0], "mag_grab": [0.0, 3.5, -17.0], "mag_lips": [0.0, 3.0, -2.2]})
    return shapes, marks


def _pistol():
    shapes = [_box("Frame", (3.0, 18.0, 3.5), (0.0, 2.0, -1.5)),
              _box("Grip", (3.0, 5.0, 11.0), (0.0, -5.0, -8.0))]
    marks = {"grip": [0.0, -5.0, -7.0], "support": [1.8, -4.5, -8.0], "muzzle": [0.0, 12.0, 0.0],
             "trigger": [0.0, -1.0, -4.0], "port": [-1.6, 1.0, 1.2],
             "mag_well": [0.0, -5.0, -2.5], "mag_grab": [0.0, -5.5, -13.5], "mag_lips": [0.0, -5.0, -2.6]}
    return shapes, marks


def proxy(action_id):
    """The proxy gun of an action: its parts map (model left empty: the build writes it) and its shapes."""
    a = A.load(action_id)
    parts, mark_parts, normals = {}, {}, {"port": [-1.0, 0.0, 0.0]}
    lips = None
    if action_id in ("pistol_slide", "revolver_swing", "energy_cell_pistol"):
        shapes, marks = _pistol()
    elif action_id == "bow":
        shapes = [_box("Riser", (3.0, 4.0, 40.0), (0.0, 0.0, 0.0)),
                  _box("LimbTop", (2.0, 3.0, 45.0), (0.0, 2.0, 42.0), "limb_top"),
                  _box("LimbBottom", (2.0, 3.0, 45.0), (0.0, 2.0, -42.0), "limb_bottom"),
                  _cyl("String", 0.3, 120.0, (0.0, -1.0, 0.0), "string", along="z"),
                  _cyl("Arrow", 0.8, 70.0, (0.0, 33.0, 2.0), "arrow")]
        marks = {"grip": [0.0, 0.0, -2.0], "nock": [0.0, -1.0, 2.0], "rest": [0.5, 1.0, 2.0], "muzzle": [0.0, 40.0, 2.0]}
        mark_parts["nock"] = "string"
    elif action_id == "flamethrower":
        shapes = [_cyl("Tube", 4.0, 70.0, (0.0, 20.0, 0.0)), _box("RearGrip", (3.0, 4.0, 10.0), (0.0, -12.0, -7.0)),
                  _box("FrontGrip", (3.0, 4.0, 10.0), (0.0, 25.0, -7.0)), _box("Valve", (1.0, 3.0, 2.0), (0.0, -10.0, -3.0), "valve"),
                  _box("Igniter", (1.0, 3.0, 2.0), (0.0, 27.0, -3.0), "igniter")]
        marks = {"grip": [0.0, -12.0, -7.0], "support": [0.0, 25.0, -7.0], "nozzle": [0.0, 55.0, 0.0], "muzzle": [0.0, 55.0, 0.0],
                 "trigger": [0.0, -10.0, -3.0]}
    else:
        shapes, marks = _long_gun(mag=action_id not in ("bolt_stripper", "lever_tube", "pump_tube", "semi_tube", "belt_open_bolt",
                                                       "break_open", "muzzle_loaded", "crossbow"))
    # each action's own parts, with shapes where the part is
    def part(role, name, shape, **motion):
        shapes.append(dict(shape, name=name, part=role))
        parts[role] = dict(motion, objects=[name])

    S = lambda size, at: _box("", size, at)        # noqa: E731
    if action_id == "ar_gas":
        part("carrier", "Carrier", S((2.0, 9.0, 2.0), (0.0, -4.5, 1.0)), axis=[0, -1, 0], travel_cm=8.4)
        part("handle", "ChargingHandle", S((4.0, 2.0, 1.0), (0.0, -15.0, 3.2)), axis=[0, -1, 0], travel_cm=8.4)
        part("cover", "DustCover", S((0.3, 8.0, 2.0), (-2.2, 1.0, 1.0)), axis=[0, 1, 0], turn_deg=110.0, pivot=[-2.2, 1.0, 0.0])
        part("catch", "BoltCatch", S((0.5, 1.5, 1.0), (2.2, -4.0, -2.5)), axis=[0, 0, 1], travel_cm=0.6)
        part("release", "MagRelease", S((0.6, 1.0, 1.0), (-2.2, -1.0, -2.5)), axis=[1, 0, 0], travel_cm=0.3)
        part("assist", "ForwardAssist", S((1.0, 2.0, 1.0), (-2.4, -9.0, 1.5)), axis=[0, 1, 0], travel_cm=0.5)
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        marks.update({"handle": [0.0, -15.0, 3.2], "catch": [2.2, -4.0, -2.5], "release": [-2.2, -1.0, -2.5], "assist": [-2.4, -9.0, 1.5]})
        mark_parts.update({"handle": "handle"})
    elif action_id == "ak_handle":
        part("carrier", "Carrier", S((2.0, 14.0, 2.5), (0.0, -2.0, 2.5)), axis=[0, -1, 0], travel_cm=12.0)
        shapes.append(_box("ChargingHandle", (2.5, 1.5, 1.2), (-3.2, 3.0, 2.5), "carrier"))
        parts["carrier"]["objects"].append("ChargingHandle")
        part("release", "Paddle", S((1.5, 1.0, 2.0), (0.0, 6.5, -2.5)), axis=[1, 0, 0], turn_deg=15.0, pivot=[0.0, 6.5, -1.5])
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        marks.update({"handle": [-3.6, 3.0, 2.5], "release": [0.0, 6.5, -2.5]})
        mark_parts.update({"handle": "carrier"})
    elif action_id in ("bolt_box", "bolt_stripper"):
        part("bolt", "Bolt", S((2.0, 12.0, 2.0), (0.0, -6.0, 1.0)), axis=[0, -1, 0], travel_cm=11.0 if action_id == "bolt_box" else 10.0)
        shapes.append(_cyl("BoltKnob", 1.6, 5.0, (-3.0, -9.0, 0.5), "bolt_lift", along="x"))
        parts["bolt_lift"] = {"objects": ["BoltKnob"], "axis": [0, 1, 0], "turn_deg": -60.0 if action_id == "bolt_box" else -90.0, "pivot": [0.0, -9.0, 1.0]}
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=10.0, pivot=[0.0, -6.5, -4.5])
        marks.update({"knob": [-5.5, -9.0, 0.5]})
        mark_parts.update({"knob": ["bolt_lift", "bolt"]})
        if action_id == "bolt_box":
            part("release", "MagRelease", S((1.0, 1.0, 0.6), (0.0, 7.0, -3.0)), axis=[0, 0, 1], travel_cm=0.4)
            marks.update({"release": [0.0, 7.0, -3.0]})
        else:
            shapes.append(_box("Clip", (1.5, 4.5, 6.0), (0.0, -2.0, 6.0), "clip"))
            parts["clip"] = {"objects": ["Clip"]}
            marks.update({"charger": [0.0, -2.0, 4.5]})
    elif action_id == "lever_tube":
        part("lever", "Lever", S((1.0, 9.0, 3.0), (0.0, -8.0, -7.0)), axis=[1, 0, 0], turn_deg=-55.0, pivot=[0.0, -3.0, -4.0])
        part("bolt", "Bolt", S((2.0, 9.0, 2.0), (0.0, -4.5, 1.0)), axis=[0, -1, 0], travel_cm=8.0)
        part("hammer", "Hammer", S((0.8, 1.5, 3.0), (0.0, -11.0, 2.5)), axis=[1, 0, 0], turn_deg=-40.0, pivot=[0.0, -10.0, 1.0])
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -7.0, -5.0)), axis=[1, 0, 0], turn_deg=10.0, pivot=[0.0, -7.0, -4.0])
        shapes.append(_cyl("Round", 1.2, 6.0, (-2.4, 0.0, -2.0), "round"))
        parts["round"] = {"objects": ["Round"]}
        marks.update({"lever_loop": [0.0, -10.0, -9.5], "gate": [-2.2, 1.0, -2.0], "hammer": [0.0, -11.5, 4.0]})
        mark_parts.update({"lever_loop": "lever"})
    elif action_id in ("pump_tube", "semi_tube"):
        if action_id == "pump_tube":
            shapes[:] = [s for s in shapes if s["name"] != "Handguard"]
            part("pump", "Pump", S((5.0, 14.0, 5.0), (0.0, 17.0, -3.0)), axis=[0, -1, 0], travel_cm=9.0)
            mark_parts.update({"support": "pump"})
            marks["support"] = [0.0, 17.0, -5.5]
            part("carrier", "Lifter", S((2.0, 5.0, 0.6), (0.0, 1.0, -2.5)), axis=[1, 0, 0], turn_deg=-15.0, pivot=[0.0, -1.5, -2.5])
        else:
            part("release", "BoltRelease", S((0.6, 1.2, 1.0), (-2.2, 3.0, -2.0)), axis=[1, 0, 0], travel_cm=0.3)
            marks.update({"release": [-2.2, 3.0, -2.0], "handle": [-3.5, 0.0, 1.0]})
            mark_parts.update({"handle": "bolt"})
        part("bolt", "Bolt", S((2.0, 10.0, 2.5), (0.0, -5.0, 1.0)), axis=[0, -1, 0], travel_cm=9.0)
        if action_id == "semi_tube":
            shapes.append(_box("BoltHandle", (2.5, 1.2, 1.2), (-3.4, 0.0, 1.0), "bolt"))
            parts["bolt"]["objects"].append("BoltHandle")
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        shapes.append(_cyl("Shell", 2.0, 6.5, (0.0, 4.0, -4.5), "shell"))
        parts["shell"] = {"objects": ["Shell"]}
        marks.update({"load_port": [0.0, 3.0, -3.5]})
    elif action_id in ("pistol_slide", "energy_cell_pistol"):
        if action_id == "pistol_slide":
            part("slide", "Slide", S((2.8, 19.0, 3.0), (0.0, 2.5, 1.5)), axis=[0, -1, 0], travel_cm=6.0)
            part("stop", "SlideStop", S((0.4, 2.0, 0.8), (1.6, 1.0, -0.5)), axis=[0, 1, 0], turn_deg=-8.0, pivot=[1.6, 2.5, -0.5])
            part("release", "MagRelease", S((0.6, 1.0, 1.0), (-1.6, -1.5, -2.0)), axis=[1, 0, 0], travel_cm=0.4)
            part("hammer", "Hammer", S((0.8, 1.2, 2.0), (0.0, -7.5, 2.0)), axis=[1, 0, 0], turn_deg=-45.0, pivot=[0.0, -7.0, 0.8])
            marks.update({"slide_rear": [0.0, -6.0, 2.2], "slide_front": [0.0, 9.0, 1.8], "release": [-1.6, -1.5, -2.0], "stop": [1.6, 1.0, -0.5]})
            mark_parts.update({"slide_rear": "slide", "slide_front": "slide"})
        else:
            part("latch", "CellLatch", S((0.6, 1.0, 1.0), (-1.6, -1.5, -2.0)), axis=[1, 0, 0], travel_cm=0.4)
            part("vent", "Vent", S((2.4, 6.0, 0.4), (0.0, 4.0, 0.5)), axis=[1, 0, 0], turn_deg=-25.0, pivot=[0.0, 1.0, 0.5])
            marks.update({"indicator": [-1.6, -2.0, 0.0], "latch": [-1.6, -1.5, -2.0]})
        part("trigger", "Trigger", S((0.5, 0.6, 1.6), (0.0, -1.0, -4.0)), axis=[1, 0, 0], turn_deg=15.0, pivot=[0.0, -1.0, -3.0])
        role = "magazine" if action_id == "pistol_slide" else "cell"
        shapes.append(_box("Magazine", (2.2, 3.4, 11.0), (0.0, -5.0, -8.0), role))
        parts[role] = {"objects": ["Magazine"]}
    elif action_id == "open_bolt":
        part("bolt", "Bolt", S((2.0, 11.0, 2.5), (0.0, -5.5, 1.0)), axis=[0, -1, 0], travel_cm=11.0)
        shapes.append(_box("CockingHandle", (2.5, 1.2, 1.2), (2.8, -2.0, 1.0), "bolt"))
        parts["bolt"]["objects"].append("CockingHandle")
        part("release", "MagCatch", S((1.0, 1.0, 0.6), (-2.0, 3.0, -2.5)), axis=[1, 0, 0], travel_cm=0.4)
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        marks.update({"handle": [3.4, -2.0, 1.0], "release": [-2.0, 3.0, -2.5]})
        mark_parts.update({"handle": "bolt"})
    elif action_id == "revolver_swing":
        part("crane", "Crane", S((1.0, 4.5, 1.0), (1.8, 1.0, -1.5)), axis=[0, 1, 0], turn_deg=75.0, pivot=[2.0, 1.0, -1.5])
        part("cylinder", "Cylinder", S((4.0, 4.0, 4.0), (0.0, 1.0, 0.5)), axis=[0, 1, 0], turn_deg=60.0, pivot=[0.0, 1.0, 0.5])
        parts["cylinder"]["parent"] = "crane"
        part("latch", "Latch", S((0.4, 1.2, 0.8), (1.6, -2.5, 0.5)), axis=[0, 1, 0], travel_cm=0.5)
        part("trigger", "Trigger", S((0.5, 0.6, 1.6), (0.0, -1.5, -4.0)), axis=[1, 0, 0], turn_deg=20.0, pivot=[0.0, -1.5, -3.0])
        part("hammer", "Hammer", S((0.8, 1.2, 2.0), (0.0, -3.5, 2.0)), axis=[1, 0, 0], turn_deg=-50.0, pivot=[0.0, -3.0, 0.5])
        shapes.append(_cyl("Ejector", 0.6, 4.0, (0.0, 5.0, -0.5), "crane"))
        parts["crane"]["objects"].append("Ejector")
        shapes.append(_box("SpeedLoader", (4.0, 2.0, 4.0), (0.0, -2.0, 0.5), "loader"))
        parts["loader"] = {"objects": ["SpeedLoader"]}
        marks.update({"latch": [1.6, -2.5, 0.5], "cylinder_face": [0.0, -1.0, 0.5], "ejector": [0.0, 7.0, -0.5], "port": [0.0, -1.0, 0.5]})
        mark_parts.update({"cylinder_face": "crane", "ejector": "crane"})
        for m in ("mag_well", "mag_grab", "mag_lips"):
            marks.pop(m, None)
        shapes[:] = [s for s in shapes if s["name"] != "Magazine"]
    elif action_id == "belt_open_bolt":
        part("bolt", "Bolt", S((2.0, 13.0, 2.5), (0.0, -6.5, 1.0)), axis=[0, -1, 0], travel_cm=13.0)
        part("handle", "ChargingHandle", S((3.0, 1.5, 1.2), (-3.5, 2.0, 0.5)), axis=[0, -1, 0], travel_cm=13.0)
        part("cover", "FeedCover", S((5.0, 14.0, 1.0), (0.0, 2.0, 4.5)), axis=[1, 0, 0], turn_deg=80.0, pivot=[0.0, -5.0, 4.5])
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        shapes.append(_box("Belt", (8.0, 3.0, 1.5), (3.5, 2.0, 2.5), "belt"))
        parts["belt"] = {"objects": ["Belt"]}
        marks.update({"handle": [-4.5, 2.0, 0.5], "cover_latch": [0.0, -4.0, 5.2], "tray": [0.0, 2.0, 3.0]})
        mark_parts.update({"handle": "handle", "cover_latch": "cover"})
    elif action_id == "break_open":
        part("barrel", "LauncherBarrel", S((5.0, 32.0, 5.0), (0.0, 16.0, 0.0)), axis=[1, 0, 0], turn_deg=-45.0, pivot=[0.0, 1.0, -3.0])
        part("latch", "BarrelLatch", S((1.5, 2.0, 1.0), (0.0, -2.0, 3.0)), axis=[0, 0, 1], turn_deg=30.0, pivot=[0.0, -2.0, 2.5])
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        shapes.append(_cyl("Round", 4.0, 10.0, (0.0, 5.0, 0.0), "round"))
        parts["round"] = {"objects": ["Round"]}
        shapes[:] = [s for s in shapes if s["name"] not in ("Barrel", "Handguard")]
        marks.update({"latch": [0.0, -2.0, 3.0], "breech": [0.0, 0.5, 0.0], "support": [0.0, 16.0, -3.0]})
        mark_parts.update({"breech": "barrel", "support": "barrel"})
        normals["port"] = [0.0, -1.0, 0.0]
    elif action_id == "muzzle_loaded":
        part("hammer", "Hammer", S((0.8, 1.5, 2.0), (0.0, -6.0, -2.0)), axis=[1, 0, 0], turn_deg=-40.0, pivot=[0.0, -5.5, -3.0])
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        shapes.append(_cyl("Rocket", 8.0, 40.0, (0.0, 55.0, 0.0), "rocket"))
        parts["rocket"] = {"objects": ["Rocket"]}
        marks.update({"hammer": [0.0, -6.5, -1.0]})
    elif action_id == "crossbow":
        part("string", "String", S((50.0, 0.5, 0.5), (0.0, 20.0, 1.5)), axis=[0, -1, 0], travel_cm=30.0)
        part("limb_l", "LimbL", S((26.0, 3.0, 1.5), (13.0, 22.0, 0.5)), axis=[0, 0, 1], turn_deg=-12.0, pivot=[1.0, 22.0, 0.5])
        part("limb_r", "LimbR", S((26.0, 3.0, 1.5), (-13.0, 22.0, 0.5)), axis=[0, 0, 1], turn_deg=12.0, pivot=[-1.0, 22.0, 0.5])
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        shapes.append(_cyl("Bolt", 1.0, 40.0, (0.0, 10.0, 2.0), "bolt"))
        parts["bolt"] = {"objects": ["Bolt"]}
        marks.update({"string": [0.0, 20.0, 1.5], "stirrup": [0.0, 40.0, -2.0], "groove": [0.0, 4.0, 2.0]})
        mark_parts.update({"string": "string"})
    elif action_id == "energy_cell":
        part("latch", "CellLatch", S((0.6, 1.0, 1.0), (-2.2, -1.0, -2.5)), axis=[1, 0, 0], travel_cm=0.5)
        part("vent", "Vent", S((4.0, 8.0, 0.4), (0.0, 10.0, 3.5)), axis=[1, 0, 0], turn_deg=-25.0, pivot=[0.0, 6.0, 3.5])
        part("trigger", "Trigger", S((0.6, 0.8, 2.0), (0.0, -6.5, -5.5)), axis=[1, 0, 0], turn_deg=12.0, pivot=[0.0, -6.5, -4.5])
        for s in shapes:
            if s["name"] == "Magazine":
                s["part"] = "cell"
        parts["cell"] = {"objects": ["Magazine"]}
        parts.pop("magazine", None)
        marks.update({"indicator": [-2.2, -6.0, 2.5], "latch": [-2.2, -1.0, -2.5]})
    elif action_id == "bow":
        parts.update({"string": {"objects": ["String"], "axis": [0, -1, 0], "travel_cm": 65.0},
                      "limb_top": {"objects": ["LimbTop"], "axis": [1, 0, 0], "turn_deg": 15.0, "pivot": [0.0, 1.0, 19.0]},
                      "limb_bottom": {"objects": ["LimbBottom"], "axis": [1, 0, 0], "turn_deg": -15.0, "pivot": [0.0, 1.0, -19.0]},
                      "arrow": {"objects": ["Arrow"]}})
    elif action_id == "flamethrower":
        parts.update({"valve": {"objects": ["Valve"], "axis": [1, 0, 0], "turn_deg": 20.0, "pivot": [0.0, -10.0, -2.0]},
                      "igniter": {"objects": ["Igniter"], "axis": [1, 0, 0], "turn_deg": 20.0, "pivot": [0.0, 27.0, -2.0]}})
    # the magazine, where the action has one
    if "magazine" in a["parts"] and "magazine" not in parts and any(s["name"] == "Magazine" for s in shapes):
        parts["magazine"] = {"objects": ["Magazine"]}
    if any(p == "magazine" or a["parts"].get(p, {}).get("kind") == "free" for p in parts) and "mag_lips" in marks:
        lips = marks["mag_lips"]
    for m in ("mag_grab", "mag_lips"):
        if m in marks:
            free = next((r for r in parts if a["parts"].get(r, {}).get("kind") == "free" and r in ("magazine", "cell")), None)
            if free:
                mark_parts[m] = free
    # every mark the action needs exists, at least as a point on the body
    for m in a.get("marks", []):
        marks.setdefault(m, [0.0, 0.0, 0.0])
    pm = {"contract": CONTRACT, "name": "Proxy_" + "".join(w.title() for w in action_id.split("_")), "action": action_id,
          "model": None, "units": "cm", "forward": "+Y", "up": "+Z", "origin": [0.0, 0.0, 0.0], "proxy": True,
          "parts": parts, "marks": marks, "mark_parts": mark_parts, "normals": normals,
          "magazine": {"lips": lips} if lips else None}
    return {"partsmap": pm, "shapes": copy.deepcopy(shapes)}
