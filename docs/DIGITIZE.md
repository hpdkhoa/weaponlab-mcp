# Gun digitizer: plan

Drafted 2026-10-16. The goal is a general workflow that takes any real gun from its public sources and makes its
digital copy without a person drawing it. No game and no arsenal sets the goal. A game reads the result through its
own adapter.

## Version 1: a visual copy

Version 1 makes a visual copy:

- **Outside:** the gun's outside shape, at the sizes its sources give.
- **Moving parts:** each part a player or a viewer sees move (bolt, slide, handle, magazine, cylinder, lever),
  rigged, with its travel.
- **Clips:** the clips of its action and the hand clips on a shared pair of arms, checked.
- **Finish slots:** the finish names its sources give (blued, parkerized, wood).
- **Blueprint:** a record that names the source of every number.

Version 1 leaves out every internal part that never shows, and all tolerances and fire-control geometry. It is not
a design anyone could make parts from.

## The chain

| Step | Tool | In | Out |
|---|---|---|---|
| 1. Sources | Blueprint Lab `sources` | manuals, patents, photos of one gun | pages, text, figures; each with its file, page and license |
| 2. Facts | Blueprint Lab `specs` | the data tables | lengths, heights, weights, travel, each with its page |
| 3. Figures | Blueprint Lab `figures`, `calibrate`, `trace` | a side view or section, scaled by a known length | each part's outline in cm |
| 4. Blueprint | Blueprint Lab `blueprint` | outlines, facts, parts list, the action family | `weaponlab-blueprint/1` |
| 5. Check | Blueprint Lab `check` | the blueprint, its figures and facts | outline overlap, length and weight sums, a labelled overlay picture |
| 6. Model | Blueprint Lab `build` | the blueprint | the model: one object a part, named for its role, and its parts map |
| 7. Motion | Gun Kit | the model and its action family | rig, gun clips, hand clips, read-back, checks |
| 8. Export | Gun Kit `export` | everything above | FBX files, a data file, the blueprint; one adapter a game |

Steps 1 to 6 are Blueprint Lab (docs/BLUEPRINT.md). The general builder lives there, beside the blueprint it reads;
Model Lab's AR-15 platform, written by hand, stays as its test. Steps 7 and 8 are Gun Kit (docs/GUNKIT.md).

## Sources

| Kind | What it gives | Rule |
|---|---|---|
| Manuals (field and technical manuals) | data tables, sections with named parts, operation steps | US government works are public domain; a "limited distribution" mark is noted |
| Patent drawings | the mechanism, parts in place, often to scale | US patents are public domain |
| Photos | a side view for the outline check | only public domain or with a license that allows it, credited |
| Maker manuals | none | copyrighted; not used |

Every number in a blueprint names its source: file, page, figure. A number without one is marked as a guess.

## The detail pass

Steps 1 to 6 make the gun's silhouette: each part is one side outline pushed straight across its width. The detail
pass makes the copy look like the gun, from the same sources. It runs between the check (step 5) and the build:

1. **Three views a part.** A part is the shape its side outline, its front sections and its top outline share (the
   three views of a drawing, intersected). The plan section gives the top outlines, a front section the rounded
   slide top, and a part without one keeps a guess with its reason.
2. **Every visible part.** The source's parts list (the labels on its sections, read off the figure) goes into the
   sources with each part marked visible or hidden, and why. Each visible part gets its own blueprint part, traced
   on its figure.
3. **Surface features.** Grooves (serrations), screw heads and knurling or checkering, with their counts and
   spacing measured on the figure or given by the text. Grooves and screws are cut into the mesh; knurling and
   checkering go to the finish as a texture, since they are too fine for the mesh.
4. **The detail check.** Every visible part in the parts list has a blueprint part, and each feature names its
   source. A missing visible part fails the check.

## The action families

A gun's action family decides its moving parts and its clips. There are 18 families in `gunkit/actions/`:

- AR gas, reciprocating handle, bolt (box magazine), bolt (stripper clip)
- lever, pump, semi-automatic tube
- pistol slide, open bolt, swing-out revolver, belt-fed open bolt
- break-open, muzzle-loaded
- flamethrower, crossbow, bow
- energy cell (rifle and pistol, for invented guns)

A new family is a new action file. No code changes.

## Who does what

- **Claude:** reads the pages, picks the figures, names the parts on them, chooses the action family.
- **The tools:** every number: scale, tracing, sums, the build, the clips, the checks.
- **A person:** approves at the end, on labelled pictures of the copy beside its source figures.

## Contracts

The schemas are in `src/weaponlab/contracts/` (`<name>.schema.json`). `contracts.check()` checks a file against its
schema and against what a schema cannot say: ids that must exist, the source of every number, the scale's sum. The
`contract_check` tool takes `sources`, `blueprint` or `partsmap`.

| Contract | Holds |
|---|---|
| `weaponlab-sources/1` | a gun's sources: files, pages, figures, licenses |
| `weaponlab-blueprint/1` | each part: its outline, width or cross-section, holes, role, finish, and the source of every number |
| `weaponlab-partsmap/1` | a model's parts and marks (the blueprint writes it) |
| `weaponlab-gunfacts/1` | the rigged gun |
| `weaponlab-action/1` | an action family |

## Order

1. Blueprint Lab steps 1 to 5 on the gun with the best sources: the M1911 (a 1940 field manual with a data table and
   sections along the bore).
2. The general builder, then that gun through Gun Kit.
3. The detail pass on that gun: three views a part, every visible part, surface features.
4. The AR-15 from its blueprint, checked against Model Lab's hand-built AR-15 (within 1 cm).
5. One gun for each action family, picked by how good its sources are.

## Limits of version 1

1. **The sources are flat.** Side views and sections give the outline. Widths and round shapes (stocks, grips) come
   from a top view where there is one, else from the data or a typical value, marked as a guess.
2. **Old drawings are scans.** They have skew, thick lines, and some are not to scale. Exploded views are never to
   scale: they name parts only. A good section gives about 1 to 3 mm on large parts, less on small ones.
3. **Scans without text need OCR.** No OCR engine is installed yet.
4. **Claude's reading of a picture is not a measurement.** Every number comes from a tool.
5. **Some guns have no clean source.** Patent drawings fill some gaps. An invented gun uses rules: sizes from a real
   gun of its class.
6. **Manuals give steps, not seconds.** Clip timings are estimates from the drills.
7. **The only check is against the same sources.** There is no 3D truth. A photo gives a second check.
8. **One heavy job at a time.** A gun takes minutes in Blender.
9. **The hand clips fail their checks today** (docs/GUNKIT.md). That must be fixed before a copy passes.

## Built (2026-10-16)

- **Contracts:** the three schemas and their checks (`src/weaponlab/contracts/`).
- **Blueprint Lab:** steps 1 to 6 as code and as 21 `blueprint_` MCP tools (docs/BLUEPRINT.md).
- **The M1911A1 through the whole chain**, from FM 23-35 (1940) to Gun Kit (`examples/m1911a1/`):
  - outline IoU 0.997 against the source photo
  - every gun clip read back within 0.0005 cm

Not done yet:

1. **The detail pass** (above), on the M1911A1 first.
2. **The hand clips fail their anatomy and grip checks** on every gun, the M1911A1 as well. This is limit 9 above,
   and it comes after the detail pass: the hands grip the real shapes.
3. **The AR-15 from its blueprint**, checked against Model Lab's AR-15 (order step 4).
4. **One gun for each action family** (order step 5). Each needs its manual's figures read the way the M1911A1's
   were.
5. **OCR** for the scanned manuals without text.

## Later: digital design for any object

The later goal is wider than guns. It is a general system that designs any object digitally from its sources. The
gun is one sample milestone on the way, not the goal.

What it adds to the visual copy:

- **Every part as a solid with its own geometry,** inside parts too, joined in an assembly with its joints and
  limits.
- **Motion from the assembly:** a mechanism moves because its joints let it, not because a clip says so.
- **Materials with density:** each part's mass, the centre of mass, the balance.
- **Views made from the assembly:** sections, exploded views, cutaways.
- **Contracts that know no domain:** parts, joints, materials, sources. The gun's action families become one library
  of mechanisms among others: hinges, slides, gears, latches, springs.

Milestones:

1. Any object with moving parts from its sources (a door latch, a hand tool, a mechanical clock): the same chain as
   version 1, with no gun terms.
2. The assembly model: parts, joints, limits, materials.
3. Motion from joints, checked against the source's operation steps.
4. The gun as a sample: a version 1 gun rebuilt as an assembly and checked against its visual copy.

For guns, one rule holds in every version: the design is for viewing, motion and simulation. It holds no
manufacturing data, so no tolerances, no machining or print files, nothing that makes a working part.
