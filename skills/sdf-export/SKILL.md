---
name: sdf-export
track: R
description: >-
  Use when exporting a FreeCAD parametric assembly to SDF for a simulator: model
  vs world scope, links/joints/frames, inertials from mass properties, collision
  geometry for stable physics, and verifying by re-parse. Trigger phrases: "export
  SDF", "Gazebo model", "simulator description", "SDF from this assembly", "make a
  simulation model", "world file". Do NOT use for URDF/ROS robot structure (see
  urdf-export) or MoveIt planning (SRDF — not yet supported).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Export a parametric FreeCAD assembly to a valid SDF and prove it. This skill owns
the assembly→SDF mapping: choosing model-level vs world-level scope, links/joints/
frames, inertials from native mass properties, collision geometry chosen for stable
physics, and the verify-first done rule. It does not own URDF (urdf-export, the
ROS-structure sibling) or simulator plugin authoring beyond declaring what's needed.
It assumes an assembly already exists. Much of the frame and inertial discipline
mirrors urdf-export; where they differ, SDF's scope model and physics framing are
the reason.

This skill drives FreeCAD through the **freecad-buddy MCP server** (the `export_sdf`,
`verify_export_sdf`, `query_mass_properties`, and `query_placement` tools named
below). These are Phase-5 capabilities — if they aren't available in your session,
the robot-description export tools aren't installed yet; install and connect the
freecad-buddy MCP (open FreeCAD with the add-on, which auto-starts the server, then
point your MCP client at it) and confirm the Phase-5 tool set is present.

## Decision Rules

- Treat the written `.sdf` as **unverified until `verify_export_sdf` re-parses it**,
  because a serializable SDF can still carry a bad frame, an unstable collision
  shape, or an unresolved mesh — the bundled re-parse and schema check is the pass
  signal, not the successful write.
- Decide **model-level vs world-level scope first**: export a reusable robot/object
  as a **model** SDF; use a **world** SDF only when the task genuinely needs physics
  settings, lights, ground plane, or multiple placements. Prefer model-level for
  anything meant to be included into a world, because a model buried in a world
  can't be reused.
- Convert units at an **explicit, pinned boundary**: FreeCAD is millimetres and
  degrees, SDF is **SI — metres, kilograms, radians**. Never rely on an ambient
  default; a silent unit error scales or mis-limits the model.
- Express every pose with an explicit `relative_to` **frame**, because SDF pose
  defaults are easy to misread — stating the frame each pose is expressed in is what
  keeps a link, joint, or sensor where you meant it. Record the frame for every
  origin.
- Compute inertials from FreeCAD's **native mass properties**
  (`query_mass_properties`), because a dynamic model's inertials are
  simulation-critical; do not copy a visual origin into the inertial origin unless
  it's physically justified, and record the method if a value is approximated.
- Choose **collision geometry for stable, fast physics**, not visual fidelity — a
  primitive or simplified shape where possible — because a heavy or self-intersecting
  collision mesh is the usual cause of an unstable or slow simulation.
- Make every joint `<axis>` **finite, non-zero, normalized** in the joint frame with
  a documented positive direction, and keep the kinematic references valid (`parent`/
  `child` exist, `world` allowed as a parent but never a child), because these are
  exactly what the re-parse leg checks and what a simulator rejects at load.
- **Do not invent plugin or sensor parameters** — plugin filenames, topics, update
  rates, and frames must come from the target simulator's docs or explicit user
  data, because incorrect plugin XML passes lightweight validation and fails at
  simulator load. Declare what's assumed.
- Ensure every **mesh URI resolves** in the deployment environment (relative,
  `model://`, or `package://` as the consumer expects) and matches the metre scale,
  because an unresolved or mis-scaled mesh is a load failure or a wrong-size model.

## Worked Examples

Input: "Export this gripper assembly as a Gazebo model."

Reasoning → export:
1. Scope: a reusable gripper → **model-level** SDF (to be included into a world
   later), not a world file.
2. Links/joints: bodies → links; the assembly's prismatic finger joint → an SDF
   `<joint type="prismatic">` with an explicit `<pose relative_to="...">` and a
   normalized axis in the joint frame.
3. Inertials: `query_mass_properties` per link → SI inertials; collision = simplified
   primitives for stable contact, visual = the full mesh.
4. `export_sdf` then `verify_export_sdf` → re-parse: schema-valid, frames resolve,
   axes normalized, inertials positive, meshes resolve. Done only then.

Input: "The simulation is unstable at the finger contact."

Reasoning: likely a heavy or self-intersecting collision mesh. Swap the finger's
collision geometry to a simplified primitive, re-export, and re-verify — the physics
stabilizes without changing the visual mesh.

## Anti-Patterns

- **File written = done.** Symptom: a broken SDF loaded into the simulator. Why: no
  re-parse. Fix: `verify_export_sdf` before done.
- **World scope for a reusable model.** Symptom: the model can't be included
  elsewhere. Why: it was buried in a world file. Fix: export model-level unless the
  task needs world context.
- **Ambient unit conversion.** Symptom: a mis-scaled or mis-limited model. Why:
  mm/deg leaked into an SI file. Fix: pin the conversion explicitly.
- **Implicit pose frames.** Symptom: a link or sensor lands in the wrong place. Why:
  `relative_to` was omitted and the default misread. Fix: state the frame for every
  pose.
- **Visual mesh as collision.** Symptom: unstable or slow physics. Why: a heavy
  collision shape. Fix: simplified/primitive collision geometry.
- **Invented plugin parameters.** Symptom: the model loads in a viewer but fails in
  the simulator. Why: guessed plugin XML. Fix: source plugin params from the
  simulator docs; declare assumptions.
