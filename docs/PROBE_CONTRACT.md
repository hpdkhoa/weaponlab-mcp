# The probe contract (weaponlab-probe/1)

Weapon Lab never runs your game itself. A **probe** does: a program you write for your game, in any language or
engine. Weapon Lab writes a **job file** and starts your probe with its path. The probe plays each weapon's actions,
measures them and writes a **rows file**. It may also write screenshots and **parts dumps**. Weapon Lab checks what
comes back, and the Gate judges the rows.

`weaponlab contract job|rows|parts <file>` checks a file against this contract, so you can test a probe on its own.
`examples/demo/probe/demo_probe.py` is a complete probe in about 200 lines. It measures a toy game.

## How Weapon Lab starts the probe

The project's `weaponlab.json` names the command. `{job}` becomes the job file's path:

```json
{"probe": {"command": ["MyGame.exe", "-probe={job}", "-log={work}/probe/game-{stamp}.log"],
           "timeout_s": 1800, "refuse": ["MyGame.exe"], "busy": ["UnrealEditor.exe"], "wait_s": 3600,
           "job_extra": {"quit": true}, "low_priority": true}}
```

- `{job}` is the job file, `{work}` the project's work folder, `{stamp}` the run's time stamp.
- The probe reads the job, runs, writes the rows file at the job's `out`, and exits.
- Exit code 0 means it finished. Weapon Lab still checks the rows file. A missing or broken file is an error.
- Weapon Lab waits up to `timeout_s`, or longer when the job's own length needs it, scaled by `1 / slomo`.
- `refuse` lists processes Weapon Lab never runs beside, such as the player's own copy of the game. It stops at once.
- `busy` lists other heavy jobs, such as an editor or Blender. Weapon Lab waits up to `wait_s` for them to end.
- `job_extra` adds keys to every job for the probe's own use.
- `low_priority` starts the probe below normal priority, so the machine stays usable.

## The gun's space

Every position in a job, a rows file or a parts dump is in the gun's space, in centimetres:

- +Y runs along the barrel, toward the muzzle.
- +Z is up.
- +X is the gun's left.
- The origin is the probe's choice, but it must stay the same for one weapon across runs. A spec's marks use it.

## The job file

```json
{
  "contract": "weaponlab-probe/1",
  "out": "C:/proj/weaponlab/work/probe/rows-20261014-120000.json",
  "weapons": [
    {
      "id": "Rifle_M4",
      "tag": "fix1",
      "actions": [
        {"name": "idle", "seconds": 1.6, "at": [1.2]},
        {"name": "reload", "run": "reload", "seconds": 3.0, "at": [0.6, 1.2]}
      ],
      "bones": {"bolt": "Bolt_j"},
      "support_l": [0.0, 25.0, 1.0],
      "tune": {"ArmsGunOffset": {"X": 0, "Y": 18.5, "Z": -1.4}}
    }
  ],
  "overrides": {"/Game/Anims/A_Idle": "/Game/Staging/S1/A_Idle"},
  "shots": "C:/proj/weaponlab/work/shots/fix1",
  "parts": "C:/proj/weaponlab/work/parts/fix1",
  "slomo": 0.2,
  "view": true
}
```

| Field | Required | Meaning |
|---|---|---|
| `contract` | no (default `weaponlab-probe/1`) | The contract version. A probe refuses a version it does not know. |
| `out` | yes | Where the probe writes the rows file. |
| `weapons[].id` | yes | The weapon, by the game's own id. |
| `weapons[].tag` | no | A label for this entry. Its rows report the weapon as `<id>@<tag>`. One job can run the same weapon twice, for example before and after a tune. |
| `weapons[].actions[].name` | yes | The action: `idle`, `fire`, `reload` or any name the probe knows. |
| `weapons[].actions[].seconds` | no | How long to watch it. |
| `weapons[].actions[].run` | no | The probe's own command for the action. Weapon Lab passes it through from `actions.json`. |
| `weapons[].actions[].at` | no | Moments, in seconds from the action's start, for screenshots and parts dumps. |
| `weapons[].actions[]` other keys | no | Passed through from `actions.json` for the probe's own use. |
| `weapons[].bones` | no | A spec mark's name to a bone. The probe reports how far each travels (`events.<mark>_travel_cm`). |
| `weapons[].support_l` | no | The spec's support mark. The probe reports the left palm's distance to it. |
| `weapons[].tune` | no | Fields of the weapon's definition, set before the weapon is drawn and put back after the entry. This is how a fix is tried before it is written. |
| `overrides` | no | Assets the probe loads in place of others: staged clips or models, tried without replacing anything. |
| `shots` | no | A folder for screenshots. Empty or missing means none. |
| `parts` | no | A folder for parts dumps. Empty or missing means none. |
| `slomo` | no | A time scale in (0, 1]. Dumps are slow, so the game runs slower while they are taken. |
| `view` | no | Measure the screen cover (`view.*` metrics). |

A probe ignores keys it does not know. A probe that cannot do something it was asked (`tune`, `overrides`) says so
in `notes` and does not fail.

## The rows file

```json
{
  "rows": [
    {"weapon": "Rifle_M4@fix1", "action": "idle", "metric": "hands.l_gap_cm", "value": 0.22},
    {"weapon": "Rifle_M4@fix1", "action": "idle", "metric": "view.hand_l_shown", "value": 0.27},
    {"weapon": "Rifle_M4@fix1", "action": "reload", "metric": "hands.l_to_support_cm", "value": null, "note": "no support mark"}
  ],
  "notes": ["Rifle_M4@fix1: ArmsGunOffset tuned"]
}
```

- One row per weapon, action and metric.
- `value` is a finite number, or `null` when the probe could not measure it. The Gate skips a null.
- `note` is optional text for a person.
- A metric name has a group and a name: `hands.l_gap_cm`. The standard metrics are below. A project adds its own in
  its `metrics.json`.
- `notes` holds text about the run as a whole.

## Screenshots and parts dumps

- A screenshot at a moment: `<shots>/<weapon>_<action>_<t>.png`, with `t` to two decimals (`Rifle_M4_idle_1.20.png`).
- A screenshot of the idle view without a moment: `<shots>/<weapon>_idle.png`.
- A parts dump at a moment: `<parts>/<weapon>_<action>_<t>.obj`.

A parts dump is a Wavefront OBJ of every drawn part as posed at that moment, in the gun's space:

```
# eye 22.0 -31.1 36.2
# hold rig AKS offset 0.0 18.5 -1.4
g arms|Arms|/Game/Arms/SK_Arms|hand_l
v 1.0 2.0 3.0
...
f 1 2 3
g gun|Gun|/Game/Guns/M4/SK_M4|root
g part|Mag|/Game/Guns/M4/SM_Mag|Mag1
```

- A group name has four fields: `role|component|asset|bone`.
- `role` is `arms`, `gun` (the weapon's own model), `part` (a separate piece of it, such as a magazine) or `item`
  (something carried in a hand).
- `bone` is the bone the triangles follow. Use `-` for a static mesh.
- `# eye x y z` is the camera in the gun's space.
- Any other `# key ...` line is free for the probe's own facts. Weapon Lab keeps them as a header.
- Every group needs triangles. A dump needs a `gun` group or, when the weapon is drawn only as pieces (a melee
  model swapped into another weapon's hands), a `part` group.

Hand bones follow Unreal's mannequin names (`hand_l`, `index_01_r`, `pinky_01_r`, `middle_01_r`, `thumb_03_r`,
`lowerarm_r`). The fist measure and the forearm roll read those names.

## The standard metrics

| Metric | Unit | Better | Meaning |
|---|---|---|---|
| `hands.arms_shown` | 0/1 | higher | The weapon is held by visible arms. |
| `hands.l_gap_cm` | cm | lower | The left palm's distance to the gun's surface, the worst over the action. |
| `hands.r_gap_cm` | cm | lower | The right palm's distance to the gun's surface. |
| `hands.r_handle_gap_cm` | cm | lower | The right palm's distance to the grip. |
| `hands.l_drift_cm` | cm | lower | How far the left hand moves in the gun's space during the action. |
| `hands.l_to_support_cm` | cm | lower | The left palm's distance to the spec's support mark. |
| `hands.r_hold_drift_cm` | cm | lower | How far a held melee weapon moves in the right hand. |
| `hands.l_ride_<mark>_cm` | cm | lower | The left hand's distance to a moving part it rides, such as a pump. |
| `view.cover_total` | share | lower | The share of the screen the arms and weapon cover. |
| `view.cover_lower_left` | share | lower | The share of the lower left third they cover. |
| `view.cover_bottom_middle` | share | lower | The share of the bottom middle third they cover. |
| `view.hand_l_shown` | share | higher | The share of the left hand the player sees. |
| `view.hand_r_shown` | share | higher | The share of the right hand the player sees. |
| `view.item_shown` | share | higher | The share of a carried item the player sees. |
| `parts.copies_magazine` | count | none | Magazines drawn at once. |
| `events.played` | 0/1 | higher | The action's clip played. |
| `events.item_in_hand` | 0/1 | none | An item was in the hand during the action. |
| `events.<mark>_travel_cm` | cm | higher | How far a spec's moving bone travels. |
| `swing.edge_lead` | cos | higher | How well a blade's edge leads its cut: 1 is the edge, 0 the flat. |

"Better: none" means the Gate never calls a change in it a regression. Only a case's rule judges it.

## Lessons from the first probe

ToangTown's probe (Unreal 5.8, C++) found these. A new probe should handle them too.

- **The first action of a run can read wrong.** One read the hands 44 cm off the gun. Weapon Lab adds a warm-up entry
  and drops its rows.
- **Actions depend on the state the last one left.** Start fire and chamber actions from a full magazine.
- **Melee swing rows vary between runs.** Run an unchanged weapon twice before you trust a small change.
- **A dump stalls the game for a moment.** Take dumps in slow motion.
- **Set tuned fields before the weapon is drawn.** Some fields are read only when it is equipped.
