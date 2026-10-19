# Changelog

## Unreleased

Since 0.1.0 (2026-10-15 to 19): Gun Kit, Blueprint Lab and the hands.

* **Gun Kit:** a gun's facts (`weaponlab-gunfacts/1`), actions as data (18 actions with a pistol and a long-gun base),
  the timeline of a clip, parts maps and proxy guns for every action, the rig plan and bone tracks; in Blender: rig any
  gun from its parts map, key its clips, read them back (within 0.0005 cm); hand clips on the shared arms through Pose
  Lab; the export with a draft data file; a magazine along its own well's line; 11 `gunkit_` MCP tools and
  docs/GUNKIT.md.
* **Blueprint Lab:** a real gun's visual copy from its sources (sources, specs, figures, trace, plan, check, build,
  render), the detail pass (three-view parts, grooves, screws, textures, the parts list), edge smoothing, a showcase
  (GIF and MP4); the M1911A1 worked example from FM 23-35 (1940). A page with no text layer is read by OCR Lab
  (`ocrlab-mcp`) when it is installed.
* **Contracts:** `weaponlab-sources/1`, `weaponlab-blueprint/1`, `weaponlab-partsmap/1`, `weaponlab-gripstyle/1`,
  `weaponlab-character/1`, `weaponlab-reference/1` as JSON Schema with checks.
* **Hands by grip style and character:** the pistol two-hand style; the character's gloves drawn on the arms; the
  arms' size checked against ANSUR II; contact rules and the skin check (clips replayed on a thicker or thinner skin).
* **Hands by purpose (2026-10-18 and 19):** the grip style names each hand's purpose (power wrap with the thumb in line
  and the index along the guard; support) and its no-touch parts; marks come from the rig's facts and the gun's own
  geometry (Pose Lab's object reader: the grip's run nearest the grip mark, the opening nearest the trigger); each home
  hold is found by Pose Lab's whole-arm search with restarts and judged by its contact gate; the support hand is solved
  against the firing hand where it holds; a hand resting on its home hold is not repaired per frame. `contact_view`
  draws the contact map of a saved clip frame. Verify reads the drawn skin, the eye's view (sights, cover) and the
  motion (`motion.py`: pops, jerks, finger jumps).
* **Holds by Pose Lab's target solver, inside the walls** (2026-10-19): each home hold is solved toward its purposes'
  targets with no chance in it; starts ranked walls first. Every hold, whichever path found it, is checked against
  the walls (report "walls"); a hold past one never counts as found. A clip with any frame past a wall is not
  written, only reported ("blocked"). The random search option is removed. Not yet run.
* **Reference holds** (`reference.py`, `run.pack_hold`): a pack's hand read through a bone map into the grip's frame,
  kept inside the project (a pack's numbers keep its licence); a comparison only, not a rule.
* Removed: the hold chain, the thumb search and probe, the hand-posing scene, the four per-frame repair passes.

## 0.1.0

The general core of the tools built for ToangTown's weapons (2026-10-13 and 14), split out so any game can use them.

* The probe contract (`weaponlab-probe/1`, docs/PROBE_CONTRACT.md): a job file in, a rows file out, screenshots and
  parts dumps at moments. `weaponlab contract job|rows|parts` checks a probe's files. Run against ToangTown's probe
  (149 jobs, 1,021 dumps), it found two real bugs there: a tagged entry's view rows under the plain weapon id, and a
  gun built into an arms mesh dumped as arms.
* The Gate: cases, metrics (the contract's standard ones built in), named budgets, runs, the baseline, check evals,
  the verdict, proposals and approval. Rows that break the contract are refused.
* Rig Lab without Blender: pieces and twins, the spec's facts, a magazine's line into its well, a sliding part's
  line, a melee hilt against the fist's grip channel and the turn and move that lay it in.
* Motion Lab in Blender: a forearm's roll (auto per clip, every frame checked against the forearm's range), a part's
  track on its axis, dev renders.
* One MCP server (`weaponlab-mcp`, 30 tools) and a command line (`weaponlab`).
* A demo game with two planted bugs and a 150-line probe; tests walk the whole loop on it.
