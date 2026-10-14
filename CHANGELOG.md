# Changelog

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
