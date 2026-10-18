# Gun Kit

Gun Kit takes any gun from its model to the game. It rigs the gun for its kind of action and makes the gun's own
clips. It makes the hand clips on one shared pair of arms and checks every clip. Then it stages the files for the game
to import. A gun goes through the same chain whatever drew it: Model Lab, or a model of the user's own.

## The chain

| Step | Tool | In | Out |
|---|---|---|---|
| Look at the model | `gunkit_inspect` | a .blend, .fbx, .obj or .glb | its objects, vertex groups, bounds, a units guess |
| Draft its parts map | `gunkit_draft` | the inspection and the gun's action | a parts map and a list of guesses to confirm |
| (or) take a Model Lab build | `gunkit_from_modellab` | a build folder | its parts map |
| Rig it | `gunkit_rig` | the parts map | the rigged gun and its facts (`gunfacts.json`) |
| Make every clip | `gunkit_build` | the facts | the hand clips on the shared arms, then the gun's own clips |
| Read the clips back | `gunkit_verify` | the facts | each gun clip against the timeline, cm |
| Stage it | `gunkit_export` | the facts, the game id, the game's dump of the gun | the FBX files, an import plan, a draft data file, a trial copy |
| Gate it | `gunkit_cases`, the provider `gunkit` | the gun | its cases and rows |

`gunkit_proxy` builds an action's proxy gun: simple shapes with the action's real moving parts. The whole chain runs on
it before a real model exists. A proxy is a test model, and every picture of it says so.

## Contracts

- **Gun space:** cm, +Y to the muzzle, +Z up, +X the gun's left, origin the bolt face at rest. It is left-handed, as
  Unreal is.
- **Action** (`weaponlab-action/1`, `gunkit/actions/*.json`): the parts that move and how far, the beats of each gun
  clip, the hand events of each hand clip, the gun's pose through a clip and what each clip must show. Every beat and
  event says why. Each action lists the manuals its timings come from, marked "to read" or "to find".
- **Parts map** (`weaponlab-partsmap/1`): a model's objects or vertex groups for each part, its forward, up, units and
  bolt face, the marks, the turning parts' pivots.
- **Gun facts** (`weaponlab-gunfacts/1`): the rigged gun, as every later step reads it.

## Marks

A hand's mark is where its palm (or a pinch's fingertips) meets the surface, with the way that surface faces:

- `grip`: the right palm on the grip's right side
- `support`: the left palm under the handguard
- `mag_grab`: the left hand on the magazine's left face
- `handle`, `knob`, `slide_rear`: where the fingers take a moving part

The other marks are places on the gun, such as `port`, `muzzle`, `mag_well` and `mag_lips`. A mark rides its part
(`mark_parts`): a handle's mark moves with the handle.

## Hand clips

The hand step runs on Pose Lab (poselab-mcp) in Blender:

1. It searches where the gun sits for both hands and the view.
2. It solves every hold once. A grip style with a reference hold starts from it: Pose Lab puts the reference on the
   hand (`put_reference`) and adapts it to this gun in small moves (`adapt_hold`). The one score (`hold_score`)
   judges every hold and every repair.
3. For each frame it poses the gun and its parts, and moves each hand from target to target. A hand on a moving part
   rides it, and a carried magazine rides its hand. A frame that presses or breaks an arm rule gets one repair by
   the same score (`repair_hand`).
4. Pose Lab checks every clip for clipping, the arm and finger rules and the grip rules. It also checks each sight the
   action expects, such as the port in view during a press check.
5. Verify adds three checks: the drawn skin against the gun and the other hand (`skin_presses`), what the eye sees
   (`view_report`: the sights, the arms' cover, the hands shown) and the motion (`motion.py`: pops, jerks, finger
   jumps).

### Reference holds

A reference hold is a known good hold in the grip's frame (`reference.py`: origin the magazine's lips, up the
magazine's line). `run.pack_hold` reads one from a pack's first-person clip (`gunkit_pack_hold.py`) through a bone
map. It is written to `<work>/gunkit/references/<style id>.json`, inside the project. A pack's numbers keep its
licence: a Fab Standard licence lets them ship in the game, never in a public repository, so no reference file is
part of this package.

The shared arms come from the project's `weaponlab.json`: `"gunkit": {"arms": {"folder", "arms", "idle", "eye"}}`.
