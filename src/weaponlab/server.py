"""Weapon Lab over MCP: one server, six groups of tools (spec_, gate_, probe_, rig_, motion_, gunkit_) and the contract checks.
Run: weaponlab-mcp (or python -m weaponlab serve)."""
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from . import __version__, contract as C, gate as G, motion as M, probe as P, rig as R, spec as S
from .config import project

mcp = MCPServer("weaponlab", title="Weapon Lab", version=__version__, instructions=(
    "Weapon Lab finds and fixes first-person weapon bugs (hands off the gun, a magazine crooked in its well, a blade "
    "held wrong, arms covering the screen) once per kind of bug, then for every weapon, behind a gate. The game's own "
    "probe measures each weapon's actions (docs/PROBE_CONTRACT.md); the Gate keeps each bug as a case with a pass rule "
    "and passes a change only when its target cases pass and nothing else gets worse. Try a fix with probe_run (tune "
    "or staged assets, with screenshots) before writing it; look at the screenshots, since a passing number can hide a "
    "wrong picture; then gate_propose, and import only after a person approves."))


def _err(f, *a, **k):
    try:
        return f(*a, **k)
    except (P.Busy, RuntimeError, ValueError, FileNotFoundError, KeyError) as e:
        raise ToolError(str(e))


# ------------------------------------------------------------------ project and contract
@mcp.tool()
def project_info() -> dict:
    """The project in use: its folder, data, specs and work folders, the probe command, Blender."""
    pr = project()
    try:
        blender = str(pr.blender())
    except FileNotFoundError as e:
        blender = str(e)
    return {"root": str(pr.root), "configured": pr.has_config, "data": str(pr.data), "specs": str(pr.specs), "work": str(pr.work),
            "probe": pr.probe, "providers": sorted(pr.providers), "blender": blender}


@mcp.tool()
def contract_check(kind: Annotated[str, Field(description="job, rows or parts")], path: str,
                   job_path: Annotated[str | None, Field(description="for rows: the job they answer")] = None) -> dict:
    """Checks a file a probe reads or writes against the probe contract."""
    bad = _err(C.check_file, kind, path, job_path)
    return {"ok": not bad, "problems": bad}


# ------------------------------------------------------------------ specs
@mcp.tool()
def spec_list() -> list:
    """Every weapon spec: marks, actions, marks still proposed."""
    return S.list_specs()


@mcp.tool()
def spec_read(weapon: str) -> dict:
    """One weapon's spec, with the default limits filled in."""
    return _err(S.read_spec, weapon)


@mcp.tool()
def spec_validate(spec: Annotated[dict | None, Field(description="a spec to check; or name a saved one")] = None, weapon: str | None = None) -> list:
    """Every problem with a spec, as sentences (empty: whole)."""
    return S.validate(spec if spec is not None else _err(S.read_spec, weapon))


@mcp.tool()
def spec_write(spec: dict) -> list:
    """Saves a whole spec and returns what changed."""
    return _err(S.write_spec, spec)


# ------------------------------------------------------------------ the Gate
@mcp.tool()
def gate_cases(weapon: str | None = None, status: str | None = None) -> list:
    """The cases (each a known bug as a metric, a weapon, an action and a pass rule)."""
    return [c for c in G.cases() if (not weapon or c["weapon"] == weapon) and (not status or c.get("status") == status)]


@mcp.tool()
def gate_metrics() -> dict:
    """Every metric: provider, unit, which way is better, tolerance."""
    return G.metrics()


@mcp.tool()
def gate_weapons() -> list:
    """The project's weapons."""
    return G.weapons()


@mcp.tool()
def gate_add_case(case: Annotated[dict, Field(description="{id, weapon, action, metric, rule {op, value}, about, source}")]) -> dict:
    """Adds or replaces a case."""
    return _err(G.add_case, case)


@mcp.tool()
def gate_run(providers: list[str], weapons: list[str] | None = None, actions: list[str] | None = None, staging: str | None = None) -> dict:
    """Measures the weapons with the providers (probe, rig, or the project's own) and stores the run."""
    return _err(G.run_providers, providers, weapons, actions, staging)


@mcp.tool()
def gate_verdict(run_id: str, targets: list[str] | None = None) -> dict:
    """Pass only if the target cases pass, nothing else got worse past its tolerance and the checks are trusted."""
    return _err(G.verdict, run_id, targets)


@mcp.tool()
def gate_set_baseline(run_id: str) -> dict:
    """A run's rows become the baseline (merged over the old)."""
    return _err(G.set_baseline, run_id)


@mcp.tool()
def gate_propose(name: str, targets: list[str], providers: list[str], staging: str | None = None,
                 weapons: list[str] | None = None, actions: list[str] | None = None) -> dict:
    """A staged change measured and judged; the proposal waits for a person's approval."""
    return _err(G.propose, name, staging, targets, providers, weapons, actions)


@mcp.tool()
def gate_approve(proposal: str, approved_by: Annotated[str, Field(description="who approved, in their words")]) -> dict:
    """Marks a passed proposal approved. Only on a person's word."""
    return _err(G.approve, proposal, approved_by)


@mcp.tool()
def gate_proposals() -> list:
    """Every proposal: passed, approved."""
    return G.proposals()


@mcp.tool()
def gate_evals() -> dict:
    """Each provider's eval: faults caught, good cases passed, trusted."""
    return G.evals()


# ------------------------------------------------------------------ the probe
@mcp.tool()
def probe_status() -> dict:
    """The processes that must not run with the probe, running now."""
    return {"busy": P.running()}


@mcp.tool()
def probe_plan(weapons: list[str] | None = None, actions: list[str] | None = None) -> list:
    """The job's weapons the probe would get."""
    return _err(P.job_for, weapons or [w["id"] for w in G.weapons()], actions)


@mcp.tool()
def probe_run(weapons: list[str], actions: list[str] | None = None,
              at: Annotated[dict | None, Field(description="{action: [seconds]} for screenshots and dumps")] = None,
              tune: Annotated[dict | None, Field(description="{weapon: {field: value}}: a fix tried without writing it")] = None,
              staging: Annotated[str | None, Field(description="a folder whose stage.json overrides assets")] = None,
              shots: str | None = None, parts: str | None = None, slomo: float | None = None) -> dict:
    """One probe run: rows, and screenshots and parts dumps at the moments."""
    return _err(P.run, weapons, actions, at, tune, staging, shots, parts, slomo)


# ------------------------------------------------------------------ Rig Lab
@mcp.tool()
def rig_pieces(obj: str) -> dict:
    """A parts dump's pieces (triangles, centre, bounds, extents) and twins (a piece drawn twice)."""
    return _err(R.pieces, obj)


@mcp.tool()
def rig_facts(weapon: str, obj: str) -> dict:
    """The weapon spec's facts (order, side, below, in) on a dump."""
    return _err(R.facts, weapon, obj)


@mcp.tool()
def rig_align(seated_obj: str, moment_objs: list[str], bone: str, well_depth_cm: float = 4.0, axis: list[float] | None = None) -> dict:
    """A magazine's line into its well over a reload's moments: worst offset and tilt while in the well."""
    return _err(R.align, seated_obj, moment_objs, bone, well_depth_cm, axis)


@mcp.tool()
def rig_part_line(seated_obj: str, moment_objs: list[str], bone: str, axis: list[float]) -> dict:
    """A sliding part's path against its axis: line_cm and seat_cm."""
    return _err(R.part_line, seated_obj, moment_objs, bone, axis)


@mcp.tool()
def rig_fist(obj: str, side: str = "r") -> dict:
    """A melee hilt against the fist's grip channel, and the turn and move that lay it in (try them with probe_run's
    tune; a palm-down fist can hold the hilt right and still point the blade sideways: look at the screenshot)."""
    m = _err(R.fist, obj, side)
    if not m:
        raise ToolError("no hand bones (hand, index_01, pinky_01, middle_01..03) in %s" % obj)
    return m


# ------------------------------------------------------------------ Motion Lab
@mcp.tool()
def motion_roll_profile(fbx: str, side: str = "r") -> dict:
    """The hand's roll about its forearm through a clip (0 thumb up; past 80 degrees breaks the forearm's range)."""
    return _err(M.profile, fbx, side)


@mcp.tool()
def motion_roll(src_fbx: str, out_fbx: str, side: str = "r",
                degrees: Annotated[str, Field(description="a number, or auto: the clip starts thumb up")] = "auto") -> dict:
    """One clip's hand turned about its forearm, the twist bones sharing it."""
    return _err(M.roll, src_fbx, out_fbx, side, degrees)


@mcp.tool()
def motion_roll_set(fbx_files: list[str], out_folder: str, suffix: str, side: str = "r", degrees: str = "auto") -> dict:
    """A set of clips rolled, each from its own start, saved under new names (<name>_<suffix>)."""
    return _err(M.roll_set, fbx_files, out_folder, suffix, side, degrees)


@mcp.tool()
def motion_track(src_fbx: str, out_fbx: str, bone: str, root: str, axis: list[float] | None = None, seat: list[float] | None = None) -> dict:
    """A sliding part's track rebuilt on its axis from its seat."""
    return _err(M.track, src_fbx, out_fbx, bone, root, axis, seat)


@mcp.tool()
def motion_render(objs: list[str], out_folder: str) -> dict:
    """Dev views of parts dumps (not the game's view)."""
    return _err(M.render, objs, out_folder)


# ------------------------------------------------------------------ Gun Kit: any gun, from its model to the game
@mcp.tool()
def gunkit_actions() -> dict:
    """The kinds of gun action Gun Kit knows (AR gas, AK handle, bolt, lever, pump, pistol slide, open bolt, revolver,
    belt fed, launchers, bow, crossbow, flamethrower, fictional energy guns): each one's guns, parts and clips."""
    from .gunkit import actions as GA
    return GA.summary()


@mcp.tool()
def gunkit_action(action: str) -> dict:
    """One action in full: its parts, marks, the beats of its gun clips and the hand events of its hand clips, with
    the reason or source of each, and the manuals to read or find."""
    from .gunkit import actions as GA
    return _err(GA.load, action)


@mcp.tool()
def gunkit_inspect(model: str) -> dict:
    """What a model holds as Blender shows it after import (objects, vertex groups, bounds, the longest axis, a units
    guess): the starting point of its parts map."""
    from .gunkit import run as GR
    return _err(GR.inspect, model)


@mcp.tool()
def gunkit_draft(model: str, action: str, name: str | None = None) -> dict:
    """A first parts map for a model of the user's own and the list of every guess in it to confirm (forward, units,
    the bolt face, each part, each mark). Write the confirmed map to a file for gunkit_rig."""
    from .gunkit import draft as GD, run as GR
    return _err(lambda: GD.draft(GR.inspect(model), action, model, name))


@mcp.tool()
def gunkit_from_modellab(build_folder: str) -> dict:
    """A Model Lab build's parts map (its moving parts, travel, hinges and hand marks), ready for gunkit_rig."""
    from .gunkit import modellab as GM
    return _err(GM.partsmap, build_folder)


@mcp.tool()
def gunkit_proxy(action: str) -> dict:
    """An action's proxy gun (simple shapes with its real moving parts) built and rigged: the whole chain runs on it
    before a real model exists. A test model: label every picture of it."""
    from .gunkit import run as GR
    return _err(GR.build_proxy, action)


@mcp.tool()
def gunkit_rig(partsmap: Annotated[str, Field(description="a parts map file (weaponlab-partsmap/1)")]) -> dict:
    """A gun rigged for its action from its parts map: one bone a moving part, the gun facts checked against the action."""
    from .gunkit import run as GR
    return _err(GR.rig, partsmap)


@mcp.tool()
def gunkit_build(facts: Annotated[str, Field(description="the rigged gun's gunfacts.json")], grip_steps: int = 3) -> dict:
    """Every clip of one gun: the hand clips on the shared arms (Pose Lab: the hold searched for both hands and the
    view, each clip's clearance, anatomy and grip checks, the expected sights), then the gun's own clips with the
    carried parts' tracks. Minutes per gun."""
    from .gunkit import run as GR
    return _err(GR.build_all, facts, grip_steps)


@mcp.tool()
def gunkit_verify(facts: str) -> dict:
    """The gun's own clips read back from Blender against the timeline's sums: the worst gap a clip, cm."""
    from .gunkit import run as GR
    return _err(GR.verify, facts)


@mcp.tool()
def gunkit_export(facts: str, game_id: str, base: Annotated[str | None, Field(description="the game's current definition of the gun (a data file), for its numbers")] = None) -> dict:
    """The gun's files staged for a game: its FBX with its clips, the hand clips, an import plan, a draft data file and
    a trial copy pointing at staging. Registers the build for the Gate's gunkit provider."""
    from .gunkit import export as GX
    return _err(GX.export, facts, game_id, base)


@mcp.tool()
def gunkit_cases(weapon: str, action: str, add: bool = False) -> list:
    """The Gate cases every gun of an action gets (its facts, each clip's read-back, each hand clip's checks and
    sights); add writes them into the Gate."""
    from .gunkit import gaterows as GG
    cs = GG.cases(weapon, action)
    if add:
        for c in cs:
            _err(G.add_case, c)
    return cs


def main():
    mcp.run()
