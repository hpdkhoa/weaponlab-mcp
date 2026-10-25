"""Weapon Lab over MCP: one server, seven groups of tools (spec_, gate_, probe_, rig_, motion_, gunkit_, blueprint_) and the
contract checks.
Run: weaponlab-mcp (or python -m weaponlab serve)."""
import json
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
def contract_check(kind: Annotated[str, Field(description="job, rows or parts (the probe contract); sources, blueprint or partsmap (the digitizer's)")], path: str,
                   job_path: Annotated[str | None, Field(description="for rows: the job they answer")] = None) -> dict:
    """Checks a file against its contract: a probe's job, rows or parts dump, or a digitizer file (sources,
    blueprint, partsmap)."""
    if kind in ("sources", "blueprint", "partsmap"):
        from . import contracts as DC
        bad = _err(DC.check_file, path)
    else:
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


# ------------------------------------------------------------------ Blueprint Lab: a real gun's visual copy from its sources
def _bp():
    from .blueprint import build as BB, check as BK, figures as BF, plan as BP, sources as BS, specs as BX, store as BT, trace as BR
    return BS, BX, BF, BR, BP, BK, BB, BT


@mcp.tool()
def blueprint_source_add(gun: str, file: str, source_id: str, kind: Annotated[str, Field(description="manual, patent, photo, drawing, book or web")],
                         title: str, license_basis: Annotated[str, Field(description="us-government-work, public-domain-age, public-domain-mark, us-patent, cc0, cc-by, cc-by-sa, permission or facts-only (a maker's sheet used only for its measured dimensions and shapes)")],
                         publisher: str | None = None, year: int | None = None, url: str | None = None, credit: str | None = None,
                         distribution: Annotated[str | None, Field(description="a distribution marking printed on the source, quoted")] = None,
                         gun_title: str | None = None) -> dict:
    """Step 1: registers a file (PDF or picture) as one of a gun's sources, with its license. Opens it as data only."""
    BS = _bp()[0]
    return _err(BS.add, gun, file, source_id, kind, title, license_basis, publisher, year, url, credit, distribution, None, gun_title)


@mcp.tool()
def blueprint_scan(gun: str, source_id: str) -> dict:
    """Every page of a source sorted into text, table, figure, mixed or blank, with the figure pages' captions."""
    return _err(_bp()[0].scan, gun, source_id)


@mcp.tool()
def blueprint_page(gun: str, source_id: str, pages: list[int], dpi: int = 110) -> dict:
    """Pages as pictures to read: one page at dpi, or several side by side (a contact sheet) to find the figures."""
    BS = _bp()[0]
    if len(pages) == 1:
        return {"picture": _err(BS.render, gun, source_id, pages[0], dpi)}
    return {"picture": _err(BS.sheet, gun, source_id, pages)}


@mcp.tool()
def blueprint_text(gun: str, source_id: str | None = None, page: int | None = None,
                   pattern: Annotated[str | None, Field(description="a regular expression: the lines that match, across the sources")] = None) -> dict:
    """A page's text, or the lines matching a pattern across the sources (where a part or a number is named)."""
    BS = _bp()[0]
    if pattern:
        return {"lines": _err(BS.find, gun, pattern, source_id)}
    return {"text": _err(BS.text, gun, source_id, page)}


@mcp.tool()
def blueprint_specs(gun: str, source_id: str | None = None) -> dict:
    """Step 2: candidates for each data table quantity (overall length, barrel length, weights...): the line, the
    numbers near it. Check a candidate on the page picture before adding it."""
    return _err(_bp()[1].find, gun, source_id)


@mcp.tool()
def blueprint_fact_add(gun: str, fact_id: str, value: float, unit: Annotated[str, Field(description="as printed: in, mm, cm, lb, oz, kg, count...")],
                       source_id: str, page: int, quote: Annotated[str, Field(description="the line the value was read from")]) -> dict:
    """Records a fact (kept in cm, kg, deg or count) with its page and quote."""
    return _err(_bp()[1].add, gun, fact_id, value, unit, source_id, page, quote)


@mcp.tool()
def blueprint_figure_add(gun: str, figure_id: str, source_id: str, page: int,
                         kind: Annotated[str, Field(description="side, section, top, front, rear, exploded, detail or photo")],
                         shows: Annotated[str | None, Field(description="right or left: the gun's side a side view shows")] = None,
                         crop: Annotated[list[float] | None, Field(description="[x0, y0, x1, y1] as shares of the page")] = None,
                         rotate_deg: Annotated[int, Field(description="0, 90, 180 or 270 clockwise, to stand the gun upright")] = 0,
                         dpi: int = 300, caption: str | None = None) -> dict:
    """Step 3: cuts a figure from a page and stands it upright."""
    return _err(_bp()[2].add, gun, figure_id, source_id, page, kind, shows, crop, rotate_deg, dpi, None, caption)


@mcp.tool()
def blueprint_grid(gun: str, figure_id: str, step_px: int = 100, region: list[float] | None = None, zoom: float = 1.0) -> dict:
    """The figure with a labelled pixel grid (and, once framed, its bore line, origin and cm grid) to read points off."""
    return {"picture": _err(_bp()[2].grid, gun, figure_id, step_px, region, zoom)}


@mcp.tool()
def blueprint_calibrate(gun: str, figure_id: str,
                        a: Annotated[list[float] | None, Field(description="px: one end of a known length")] = None,
                        b: Annotated[list[float] | None, Field(description="px: its other end")] = None,
                        fact: Annotated[str | None, Field(description="the fact the length is (an overall length)")] = None,
                        cm: float | None = None,
                        extent_of: Annotated[str | None, Field(description="a kept trace whose full length along the bore is the fact (in place of a and b)")] = None) -> dict:
    """A figure's scale: two points a known length apart (a printed scale bar's ticks, or a fact), or a kept
    outline's length along the bore against a length fact."""
    BS, BX, BF, BR, BP, *_ = _bp()
    if extent_of:
        t = _err(BP.trace_px, gun, extent_of)
        return _err(BF.calibrate_extent, gun, figure_id, t, fact)
    return _err(BF.calibrate, gun, figure_id, a, b, fact, cm)


@mcp.tool()
def blueprint_frame(gun: str, figure_id: str, bore_rear: list[float], bore_front: list[float], origin: Annotated[list[float], Field(description="px: the bolt face")]) -> dict:
    """How a figure lies in gun space: the bore line (from the rear toward the muzzle) and the bolt face."""
    return _err(_bp()[2].frame, gun, figure_id, bore_rear, bore_front, origin)


@mcp.tool()
def blueprint_align(gun: str, figure_id: str, reference_figure: str, trace_here: Annotated[str, Field(description="a kept trace of a shared part in this figure")],
                    trace_there: Annotated[str, Field(description="the same part's kept trace in the framed reference figure")],
                    muzzle: Annotated[str, Field(description="left or right: where the muzzle points in this figure")] = "left", note: str | None = None) -> dict:
    """A figure's scale and frame matched to a framed figure on a part both show (a trigger guard's opening)."""
    BS, BX, BF, BR, BP, *_ = _bp()
    return _err(BF.align, gun, figure_id, reference_figure, BP.trace_px(gun, trace_here), BP.trace(gun, trace_there)["outline_cm"], muzzle, note)


@mcp.tool()
def blueprint_trace(gun: str, figure_id: str, method: Annotated[str, Field(description="silhouette, region, follow, snap or blob")],
                    keep_as: Annotated[str, Field(description="the name the trace is kept under, for the plan")],
                    region: Annotated[list[float] | None, Field(description="silhouette: [x0, y0, x1, y1] px to look in")] = None,
                    seed: Annotated[list[float] | None, Field(description="region: a px point inside the area")] = None,
                    rough: Annotated[list[list[float]] | None, Field(description="follow or snap: a rough outline in px")] = None,
                    box: Annotated[list[float] | None, Field(description="blob: [x0, y0, x1, y1] px round the patch (with seed inside)")] = None,
                    light: bool = True,
                    close_px: int = 7, gap_px: int = 2, radius_px: int = 10, eps_px: float = 1.5,
                    smooth_px: Annotated[int, Field(description="take out edge noise (a halftone's dots): average runs between corners over this many px (0: off)")] = 0,
                    corner_deg: Annotated[float, Field(description="with smooth_px: turns this sharp or sharper stay corners")] = 40.0) -> dict:
    """An outline from a figure, kept for the plan: the whole silhouette, a closed area round a seed, a rough
    outline laid onto the figure's lines as one line (follow: OCR Lab's follower, with its fit before and after; snap:
    the older point by point snap), or a patch in a halftone. Look at the picture it writes."""
    BR = _bp()[3]
    BR.smoothing(smooth_px, corner_deg)
    if method == "silhouette":
        r = _err(BR.silhouette, gun, figure_id, region, close_px, eps_px)
    elif method == "region":
        r = _err(BR.region, gun, figure_id, seed, gap_px, eps_px, None, keep_as)
    elif method == "follow":
        r = _err(BR.follow, gun, figure_id, rough, keep_as, radius_px=radius_px)
    elif method == "snap":
        r = _err(BR.snap, gun, figure_id, rough, radius_px, 4, eps_px, None, keep_as)
    elif method == "blob":
        r = _err(BR.blob, gun, figure_id, box, seed, light, 3, eps_px, keep_as)
    else:
        raise ToolError("method: silhouette, region, follow, snap or blob")
    BR.smoothing(0)
    BR.save(gun, keep_as, r)
    return {k: v for k, v in r.items() if k not in ("outline_px", "outline_cm")} | {"kept": keep_as}


@mcp.tool()
def blueprint_measure(gun: str, figure_id: str, a: list[float], b: list[float],
                      how: Annotated[str, Field(description="distance (a to b in cm), span (where the ink starts and ends on the line a to b), ticks (a scale bar's ticks in the box a, b) or peaks (faint evenly spaced marks, serrations, in the box a, b)")] = "distance",
                      light: bool = True) -> dict:
    """Readings off a figure by the tools, not by eye: a distance, the ink's span along a line, a scale bar's ticks,
    the count and pitch of faint marks."""
    BS, BX, BF, BR, *_ = _bp()
    if how == "peaks":
        return _err(BR.peaks, gun, figure_id, [a[0], a[1], b[0], b[1]], light)
    if how == "span":
        return _err(BR.span, gun, figure_id, a, b)
    if how == "ticks":
        return _err(BR.ticks, gun, figure_id, [a[0], a[1], b[0], b[1]])
    return _err(BF.measure, gun, figure_id, a, b)


@mcp.tool()
def blueprint_new(gun: str, action: str, title: str | None = None) -> dict:
    """Step 4: starts the gun's blueprint for its action family."""
    return _err(_bp()[4].new, gun, action, title)


@mcp.tool()
def blueprint_part(gun: str, part_id: str, role: Annotated[str, Field(description="body, or the action's part role (slide, magazine...)")], finish: str,
                   kind: Annotated[str, Field(description="extrude (a side outline run across x) or lathe (a round part)")],
                   x: Annotated[list[float] | None, Field(description="extrude: [x0, x1], the gun's right to its left, cm")] = None,
                   x_source: Annotated[dict | None, Field(description="where x comes from: {figure}, {fact}, {derived: how} or {guess: why}")] = None,
                   trace: Annotated[str | None, Field(description="extrude: the kept trace its outline comes from")] = None,
                   clips: Annotated[list[list] | None, Field(description="extrude: [axis (y, z or line), value (or [[y, z], [y, z]]), keep (above, below, left, right), why]")] = None,
                   profile: Annotated[list[list[float]] | None, Field(description="lathe: [[y, r], ...]")] = None, axis: list[float] | None = None,
                   profile_source: dict | None = None, axis_source: dict | None = None, bore_r: float | None = None,
                   motion: Annotated[dict | None, Field(description="{kind: slide, axis, travel_cm} | {kind: turn, axis, turn_deg, pivot} | {kind: free}")] = None,
                   motion_sources: Annotated[dict | None, Field(description="the source of each motion number (axis, travel_cm, turn_deg, pivot)")] = None,
                   name: str | None = None, bevel_cm: float | None = None, parent: str | None = None,
                   outline_px: Annotated[list[list[float]] | None, Field(description="extrude: the side outline read by eye off a figure, in its pixels (with figure_id), instead of a kept trace")] = None,
                   figure_id: Annotated[str | None, Field(description="extrude with outline_px: the figure it was read off")] = None,
                   outline_note: Annotated[str | None, Field(description="extrude with outline_px: what was read and where (px ranges)")] = None) -> dict:
    """Sets one part of the blueprint. Every number needs its source; the check fails a part without one."""
    BP = _bp()[4]
    if kind == "extrude" and outline_px:
        if not figure_id:
            raise ToolError("outline_px needs the figure_id it was read off")
        BF = _bp()[2]
        f = _err(BF.figure, gun, figure_id)
        if "scale" not in f or "frame" not in f:
            raise ToolError("figure %s has no scale and frame yet (blueprint_calibrate, blueprint_frame)" % figure_id)
        out_cm = [[round(u, 3), round(v, 3)] for u, v in BF.to_gun(f, outline_px)]
        return _err(BP.extrude, gun, part_id, role, finish, None, x, x_source, name=name, motion=motion, motion_sources=motion_sources,
                    bevel_cm=bevel_cm, parent=parent, outline=out_cm,
                    outline_source={"figure": figure_id, "method": "read", "note": outline_note or "read off the figure with pixel rulers"})
    if kind == "extrude":
        return _err(BP.extrude, gun, part_id, role, finish, trace, x, x_source, [tuple(c) for c in (clips or [])], name, motion, motion_sources, bevel_cm, parent)
    if kind == "lathe":
        return _err(BP.lathe, gun, part_id, role, finish, profile, axis, profile_source, axis_source, bore_r, name, motion, motion_sources, parent)
    raise ToolError("kind: extrude or lathe")


@mcp.tool()
def blueprint_hole(gun: str, part_id: str, trace: str | None = None, circle: dict | None = None, bore: dict | None = None,
                   source: dict | None = None, x: list[float] | None = None) -> dict:
    """A cut in a part: a kept trace's outline or a circle across x (limited to x when given), or a bore along y."""
    return _err(_bp()[4].hole, gun, part_id, trace, circle, source, x, bore)


@mcp.tool()
def blueprint_mark(gun: str, name: str, at: list[float], source: dict, normal: list[float] | None = None,
                   rides: Annotated[str | list[str] | None, Field(description="the part id (or chain) the mark moves with")] = None,
                   magazine_lips: bool = False) -> dict:
    """A mark in gun space (cm) with its source: a hand's place (with the way its surface faces) or a point a check needs."""
    BP = _bp()[4]
    if magazine_lips:
        return _err(BP.lips, gun, at, source)
    return _err(BP.mark, gun, name, at, source, normal, rides)


@mcp.tool()
def blueprint_views(gun: str, part_id: str,
                    front: Annotated[list[dict] | None, Field(description="front sections: [{y: [y0, y1], outline: [[x, z], ...]}]")] = None,
                    front_source: dict | None = None,
                    top: Annotated[list[list[float]] | None, Field(description="the top outline [[y, x], ...]")] = None,
                    top_source: dict | None = None) -> dict:
    """The detail pass: a part shaped by three views (its side outline, front sections, a top outline), each with
    its source."""
    return _err(_bp()[4].views, gun, part_id, front, front_source, top, top_source)


@mcp.tool()
def blueprint_loft(gun: str, part_id: str, role: Annotated[str, Field(description="body, or a part role of the action")], finish: str,
                   top: Annotated[list[list[float]], Field(description="the top outline [[y, x], ...] in cm: the part's width along its length")],
                   sections: Annotated[list[dict], Field(description="key cross-sections [{y, outline: [[x, z], ...]}] or [{y, trace: a kept trace of a section drawing}]: each is fitted to the box the side and top outlines give at its station, and blended between stations")],
                   top_source: dict, sections_source: dict,
                   side: Annotated[list[list[float]] | None, Field(description="the side outline [[y, z], ...] in cm (or side_px with figure_id, or side_trace)")] = None,
                   side_px: Annotated[list[list[float]] | None, Field(description="the side outline read off a figure, in its pixels")] = None,
                   figure_id: str | None = None, side_trace: Annotated[str | None, Field(description="a kept trace for the side outline")] = None,
                   side_source: dict | None = None, name: str | None = None, motion: dict | None = None, motion_sources: dict | None = None,
                   parent: str | None = None, step_cm: float | None = None, ring_points: int | None = None) -> dict:
    """The detail pass: a part skinned through its cross-sections (a stock that is oval at the butt, round at the
    wrist and U-shaped at the forend). Its side follows the side outline exactly, its width the top outline, its
    shape the key sections, blended smoothly. Every view needs its source."""
    BF, BP = _bp()[2], _bp()[4]
    if side is None and side_px is not None:
        if not figure_id:
            raise ToolError("side_px needs the figure_id it was read off")
        f = _err(BF.figure, gun, figure_id)
        side = [[round(u, 3), round(v, 3)] for u, v in BF.to_gun(f, side_px)]
        side_source = side_source or {"figure": figure_id, "method": "read", "note": "read off the figure with pixel rulers"}
    elif side is None and side_trace:
        t = _err(BP.trace, gun, side_trace)
        side = t["outline_cm"]
        side_source = side_source or {"figure": t.get("figure"), "method": "traced", "note": "kept trace %s" % side_trace}
    if side is None or not side_source:
        raise ToolError("a loft needs its side outline (side, side_px with figure_id, or side_trace) and its source")
    secs = []
    for sec in sections:
        if "trace" in sec:            # a section traced off a section drawing: its pixels, image y down, as (x, z); no scale needed
            tp = _bp()[7].folder(gun, "figures") / ("%s.trace.json" % sec["trace"])
            if not tp.exists():
                raise ToolError("no kept trace %s (blueprint_trace with keep_as)" % sec["trace"])
            t = json.loads(tp.read_text(encoding="utf-8"))
            secs.append({"y": float(sec["y"]), "outline": [[u, -v] for u, v in t["outline_px"]]})
        else:
            secs.append({"y": float(sec["y"]), "outline": sec["outline"]})
    sections = secs
    return _err(BP.loft, gun, part_id, role, finish, side, top, sections, side_source, top_source, sections_source, name=name,
                motion=motion, motion_sources=motion_sources, parent=parent, step_cm=step_cm, ring_points=ring_points)


@mcp.tool()
def blueprint_follow_part(gun: str, part_id: str, figure_id: str,
                          radius_px: Annotated[int, Field(description="how far a point may move: small (6) for a careful reading, larger (16) for a rough one")] = 16,
                          max_area_change: Annotated[float, Field(description="refuse a follow that changes the part's area by more than this share")] = 0.12) -> dict:
    """The detail pass: a part's side outline laid onto the figure's lines as one line (OCR Lab's follower). Kept
    as it was when following does not bring it closer, or changes its area too much (it collapsed or ran off). Gives
    the fit before and after and a picture."""
    from .blueprint import detail as D
    return _err(D.follow, gun, figure_id, part_id, radius_px=radius_px, max_area_change=max_area_change)


@mcp.tool()
def blueprint_shape_across(gun: str, part_id: str, section: Annotated[str, Field(description="rr (a box with rounded corners) or oval")],
                           source: dict, radius_cm: Annotated[float, Field(description="rr: the corner radius across, cm")] = 0.3) -> dict:
    """The detail pass: a part shaped across its width: its side kept, its front a rounded box or an ellipse over
    its full height and width (three views)."""
    from .blueprint import detail as D
    return _err(D.soft, gun, part_id, radius_cm, source, section=section)


@mcp.tool()
def blueprint_round_corners(gun: str, part_id: str, radius_cm: float, source: dict) -> dict:
    """The detail pass: a part's side outline with its corners rounded to radius_cm (machined and moulded parts have
    radiused corners)."""
    from .blueprint import detail as D
    return {"part": part_id, "points": _err(D.round_corners, gun, part_id, radius_cm, source)}


@mcp.tool()
def blueprint_bevel(gun: str, part_id: str, bevel_cm: float, source: dict) -> dict:
    """The detail pass: a part's edges rounded to bevel_cm."""
    from .blueprint import detail as D
    return _err(D.bevel, gun, part_id, bevel_cm, source)


@mcp.tool()
def blueprint_feature(gun: str, part_id: str,
                      feature: Annotated[dict, Field(description="{kind: grooves, face, count, width_cm, depth_cm, y?, z?, slant_deg?, source} | {kind: screw, face, at, r, head_cm, slot?, source} | {kind: texture, pattern (checkering, knurling, stippling, marking), face, source}")]) -> dict:
    """The detail pass: a surface feature on a part (grooves and screws in the mesh, patterns as the finish's texture)."""
    return _err(_bp()[4].feature, gun, part_id, feature)


@mcp.tool()
def blueprint_parts_list(gun: str, entries: Annotated[list[dict], Field(description="[{name, number?, page, figure?, visible, why?, source}]: the parts as the source names them")],
                         replace: bool = False) -> dict:
    """The detail pass: the source's parts list, each part visible or hidden; the check holds every visible one to a
    blueprint part (by number, or by name when the source gives none)."""
    return _err(_bp()[0].parts_list, gun, entries, replace)


@mcp.tool()
def blueprint_numbers(gun: str, part_id: str, numbers: list[str]) -> dict:
    """The source's part numbers a blueprint part stands for."""
    return _err(_bp()[4].numbers, gun, part_id, numbers)


@mcp.tool()
def blueprint_read(gun: str, what: Annotated[str, Field(description="blueprint or sources")] = "blueprint") -> dict:
    """The gun's blueprint or sources document as it stands."""
    return _err(_bp()[7].load, gun, what)


@mcp.tool()
def blueprint_check(gun: str, reference: Annotated[str | None, Field(description="a kept silhouette trace the side outline is held to")] = None,
                    reference_holes: list[str] | None = None) -> dict:
    """Step 5: the blueprint against its contract, its reference outline (overlap, edge gaps), its length and
    weight facts; and overlay pictures on every framed figure. Look at the overlays."""
    return _err(_bp()[5].run, gun, reference, tuple(reference_holes or ()))


@mcp.tool()
def blueprint_build(gun: str, render: bool = True, segments: Annotated[int, Field(description="points round a turned part")] = 64) -> dict:
    """Step 6 in Blender: the model (one object a part, each with its mesh health) and its parts map for Gun Kit;
    with render, labelled pictures of it from both sides and three quarters."""
    BB = _bp()[6]
    out = _err(BB.build, gun, segments)
    if render:
        out["views"] = _err(BB.render, gun)
    return out


@mcp.tool()
def blueprint_render(gun: str, look: Annotated[str, Field(description="workbench (flat studio shading) or material (EEVEE with the finishes' shine and textures, to hold beside a photo)")] = "material") -> dict:
    """Pictures of the built model from both sides and three quarters, labelled as model views (not game views)."""
    return _err(_bp()[6].render, gun, look=look)


@mcp.tool()
def blueprint_photomap(gun: str, figure: Annotated[str, Field(description="a framed and scaled side photo of the gun")],
                       strength: Annotated[float, Field(description="the relief the photo's detail stands for: 1 = about 1 mm")] = 1.0,
                       fine_cm: float = 0.08, coarse_cm: float = 2.5) -> dict:
    """The photo detail layer: surface maps (normal, albedo and roughness multipliers, mask) baked from the photo's
    brightness and projected onto the parts' sides at the next build, so flat plates carry the pins, seams, markings
    and wear the photo shows. A derived guess of relief from shading, recorded as one; the other side takes the maps
    mirrored. Build and render again to see it."""
    from .blueprint import photomap as PM
    return _err(PM.bake, gun, figure, strength=strength, fine_cm=fine_cm, coarse_cm=coarse_cm)


@mcp.tool()
def blueprint_showcase(gun: str, title: str | None = None, source_note: str | None = None,
                       compare_figure: Annotated[str | None, Field(description="a source figure shown beside the copy")] = None) -> dict:
    """A showcase of a built gun that has been through Gun Kit (minutes in Blender): a title card, the source beside
    the copy, a turn round it, its clips (fire slowed, the reloads, the checks); as a GIF and an MP4, every frame
    labelled as a Blueprint Lab model view."""
    from .blueprint import showcase as SC
    return _err(SC.make, gun, title, source_note, compare_figure=compare_figure)


@mcp.tool()
def blueprint_to_gunkit(gun: str, grip_steps: int = 3) -> dict:
    """Step 7: the built model through Gun Kit (several minutes in Blender): rig, hand clips, gun clips, read-back."""
    r = _err(_bp()[6].to_gunkit, gun, grip_steps)
    if "built" in r:
        r["built"] = {"hands": r["built"]["hands"], "holds": r["built"]["holds"]}
    return r


def main():
    mcp.run()
