<h1 align="center">Weapon Lab</h1>

<!-- mcp-name: io.github.hpdkhoa/weaponlab-mcp -->

<p align="center"><strong>First-person weapon bugs fixed once per kind, then for every weapon, behind a gate.</strong></p>

<p align="center">
  <a href="LICENSE"><img alt="license: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
  <a href="pyproject.toml"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white"></a>
  <a href="https://pypi.org/project/weaponlab-mcp/"><img alt="PyPI: weaponlab-mcp" src="https://img.shields.io/pypi/v/weaponlab-mcp?label=PyPI&logo=pypi&logoColor=white&color=3775a9"></a>
  <a href="https://registry.modelcontextprotocol.io/v0/servers?search=weaponlab-mcp"><img alt="MCP Registry: weaponlab-mcp" src="https://img.shields.io/badge/MCP%20Registry-weaponlab--mcp-6f42c1"></a>
  <a href="https://www.blender.org/download/"><img alt="Blender: 4.4+ (Motion Lab)" src="https://img.shields.io/badge/Blender-4.4%2B%20(Motion%20Lab)-e87d0d?logo=blender&logoColor=white"></a>
  <a href="#what-it-does"><img alt="tools: 41" src="https://img.shields.io/badge/tools-41-orange"></a>
  <a href="docs/PROBE_CONTRACT.md"><img alt="probe contract: v1" src="https://img.shields.io/badge/probe%20contract-v1-orange"></a>
</p>

An MCP server that finds and fixes first-person weapon bugs behind a gate: hands off the gun, a magazine crooked in
its well, a blade held wrong, arms covering the screen.

Each bug becomes a **case**: a metric, a weapon, an action and a pass rule. Your game's own **probe** measures the
weapons. The **Gate** passes a change only when its target cases pass and nothing else got worse. Fix each kind of
bug once, then check every weapon with it.

Weapon Lab never runs your game itself. You write a small probe for your engine that follows the
[probe contract](docs/PROBE_CONTRACT.md): a job file in, a rows file out. Everything else works on what the probe
writes back.

## What it does

| Group | Tools | What for |
|---|---|---|
| Gate | `gate_run`, `gate_verdict`, `gate_propose`, `gate_approve`, `gate_set_baseline`, `gate_cases`, ... | Keeps the bugs as cases, measures, compares against a baseline, judges a change, records a person's approval. |
| Probe | `probe_run`, `probe_plan`, `probe_status` | Starts your game's probe. Tries a fix before it is written: tuned fields, staged assets, screenshots, parts dumps. |
| Rig Lab | `rig_pieces`, `rig_facts`, `rig_align`, `rig_part_line`, `rig_fist` | Reads the posed weapon from a parts dump: its pieces, real-world facts (the magazine behind the barrel), a magazine's line into its well, a hilt in the fist. |
| Motion Lab | `motion_roll`, `motion_roll_profile`, `motion_roll_set`, `motion_track`, `motion_render` | Rebuilds clips in Blender: turns a hand about its forearm inside the forearm's range, puts a sliding part back on its axis. |
| Specs | `spec_list`, `spec_read`, `spec_validate`, `spec_write` | One file a weapon: marks (grip, support), anchors (pieces to find), facts, limits. |
| Contract | `contract_check` | Checks a probe's job, rows or parts dump. |
| Gun Kit | `gunkit_inspect`, `gunkit_draft`, `gunkit_from_modellab`, `gunkit_proxy`, `gunkit_rig`, `gunkit_build`, `gunkit_verify`, `gunkit_export`, `gunkit_cases`, `gunkit_actions`, `gunkit_action` | Takes any gun model to the game: rigs it for one of 18 actions, makes its own clips and the hand clips on one shared pair of arms, checks them, stages the files. See [docs/GUNKIT.md](docs/GUNKIT.md). |

## Try it on the demo

The demo is a toy game with two planted bugs and a probe in about 150 lines. It needs no engine.

```bash
pip install -e .
cd examples/demo
weaponlab gate run probe,rig
```

(`python -m weaponlab` works the same when pip's scripts folder is not on your PATH.)

The rifle's left hand misses its handguard by 3.75 cm. The knife's hilt lies 90 degrees across the fist.
`tests/test_demo.py` walks the whole loop: measure, find the fix, try it by tune, judge it.

## Use it in your game

1. `weaponlab init` in your project. It writes `weaponlab.json` and empty data files.
2. Write your probe from [the contract](docs/PROBE_CONTRACT.md), starting from `examples/demo/probe/demo_probe.py`.
   Set its command in `weaponlab.json`.
3. List your weapons in `weaponlab/data/weapons.json` and their actions in `actions.json`.
4. Add a case for each bug you know. Measure everything once and set the baseline.
5. Fix through the loop: try by tune or staging, look at the screenshots, propose, approve, import.

Check your probe on its own with `weaponlab contract job|rows|parts <file>`.

## Add it to an MCP client

```json
{"mcpServers": {"weaponlab": {"command": "weaponlab-mcp", "env": {"WEAPONLAB_PROJECT": "C:/path/to/your/game"}}}}
```

| Setting | Meaning |
|---|---|
| `WEAPONLAB_PROJECT` | The project folder with `weaponlab.json`. The current folder by default. |
| `WEAPONLAB_BLENDER` | Blender, for Motion Lab. Found on the PATH or in the usual install folders otherwise. |

## Requirements

- Python 3.10 or later.
- Blender 4.4 or later for Motion Lab and renders. Nothing else needs it.
- Hand bones named as Unreal's mannequin names them (`hand_r`, `index_01_r`, `lowerarm_r`) for the fist measure and
  the forearm roll.

## Where it came from

Weapon Lab is the general part of the tools built for ToangTown, an Unreal 5.8 game with 46 weapons. Its first probe
is ToangTown's. The [contract's lessons](docs/PROBE_CONTRACT.md#lessons-from-the-first-probe) come from that probe.
Pose Lab ([poselab-mcp](https://github.com/hpdkhoa/poselab-mcp)) answers the body's side: clipping, the view, a grip
solver. The Gate can use it as a provider.

## License

MIT
