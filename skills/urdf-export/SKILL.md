---
name: urdf-export
track: R
description: >-
  Use when exporting a FreeCAD parametric assembly to URDF: mapping bodies to
  links, joints between them, inertials from mass properties, collision/visual
  meshes, and verifying the result by re-parse rather than trusting the written
  file. Trigger phrases: "export URDF", "make a robot description", "links and
  joints", "URDF from this assembly", "inertials for the robot", "ROS robot file".
  Do NOT use for SDF/simulator files (see sdf-export) or MoveIt planning semantics
  (SRDF — not yet supported).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Export a parametric FreeCAD assembly to a valid URDF and prove it. This skill owns
the assembly→URDF mapping: bodies to links, assembly joints to URDF joints,
inertials computed from FreeCAD's native mass properties, mesh references, and the
verify-first done rule. It does not own SDF (sdf-export) or MoveIt planning
semantics (SRDF, which derives from a URDF and isn't supported yet). It assumes an
assembly already exists — building the assembly is upstream.

This skill drives FreeCAD through the **freecad-buddy MCP server** (the `export_urdf`,
`verify_export_urdf`, `query_mass_properties`, and `query_placement` tools named
below). These are Phase-5 capabilities — if they aren't available in your session,
the robot-description export tools aren't installed yet; install and connect the
freecad-buddy MCP (open FreeCAD with the add-on, which auto-starts the server, then
point your MCP client at it) and confirm the Phase-5 tool set is present.

## Decision Rules

- Treat the written `.urdf` as **unverified until `verify_export_urdf` re-parses
  it**, because "the file was written" is never proof — a URDF that serializes fine
  can still have a cyclic tree, a wrong-frame axis, or an unresolved mesh. Export is
  done only when the re-parse leg passes.
- Convert units at an **explicit, pinned boundary**: FreeCAD is millimetres and
  degrees, URDF is **metres, kilograms, and radians**. Never let an ambient default
  do this — a silent mm-as-m error scales the robot 1000×, and degrees-as-radians is
  the classic joint-limit bug.
- Compute each link's `<inertial>` from FreeCAD's **native mass properties**
  (`query_mass_properties` gives mass, center of mass, and the inertia tensor), not
  from a guessed primitive, because the whole point of exporting from CAD is that the
  inertials are real; record the method if any value is approximated.
- Record the **reference frame** every origin is expressed in: a joint `<origin>` is
  parent-link-frame → joint-frame, the child link frame coincides with the joint
  frame, and `<axis>` is in the joint frame — not the world, not the mesh frame.
  A number without its frame is the most common silent robot-description error.
- Verify the kinematic tree is **a single root, connected, and acyclic** with one
  parent per child, because a URDF is a tree — a cycle or a second root won't load
  in any consumer, and this is exactly what the re-parse leg checks.
- Make every joint `<axis>` a **finite, non-zero, normalized** vector in the joint
  frame, and document the positive-motion direction, because an un-normalized or
  zero axis is invalid and a flipped sign is a silent motion-direction bug — fix the
  frame, never patch it with a compensating visual offset.
- Keep **visual and collision geometry distinct**: visual can be the full mesh,
  collision should be simplified for contact/planning; do not silently copy the
  visual origin onto the collision or inertial origin — document when they
  legitimately coincide and when they differ.
- Ensure every **mesh reference resolves** from the URDF's location (a relative path
  that exists, or a `package://` URI the consumer resolves), and that the mesh's
  export units match the URDF metre scale, because an unresolved or mis-scaled mesh
  is a load failure or a wrong-size robot.
- Do not infer spatial values from appearance — derive link poses, joint axes, and
  frames from the **assembly's actual transforms** (`query_placement`) and stated
  data, because spatial reasoning from a render is where silent handedness and
  axis-sign errors enter.

## Worked Examples

Input: "Export this 2-link arm assembly to URDF."

Reasoning → export:
1. Map: base body → `base_link`, upper body → `link_1`; the assembly's revolute
   joint between them → a URDF `<joint type="revolute">`.
2. Inertials: `query_mass_properties` on each body → mass, COM, inertia tensor →
   `<inertial>` in kg and metres (convert from FreeCAD mm/g-equivalents at the pinned
   boundary).
3. Joint: `<origin>` from the assembly transform (`query_placement`) expressed in the
   parent-link frame; `<axis>` normalized in the joint frame; limits in radians.
4. Meshes: export each body's visual mesh; collision = a simplified box/cylinder;
   relative paths beside the `.urdf`.
5. `export_urdf` then `verify_export_urdf` → re-parse: schema-valid, one acyclic
   tree, axes normalized, inertials positive, meshes resolve. Only now is it done.

Input: "The exported robot is 1000× too big in RViz."

Reasoning: a unit boundary was missed — millimetres written as metres. Fix the
mm→m conversion at the export boundary and re-run `verify_export_urdf`; the re-parse
plus a bbox sanity check catches the scale.

## Anti-Patterns

- **File written = done.** Symptom: a broken URDF shipped. Why: no re-parse. Fix:
  `verify_export_urdf` before calling it done.
- **Ambient unit conversion.** Symptom: a 1000× robot or wrong joint limits. Why:
  mm/deg leaked into a metre/radian file. Fix: pin the conversion explicitly.
- **Guessed inertials.** Symptom: unstable or implausible dynamics. Why: a primitive
  approximation replaced the real mass properties. Fix: compute from
  `query_mass_properties`; document any approximation.
- **Axis sign fixed with a visual offset.** Symptom: motion is right but the frames
  are wrong. Why: a flipped joint axis was masked instead of corrected. Fix: fix the
  joint frame; visual is derivative.
- **Copying visual origin to collision/inertial.** Symptom: wrong contact or
  dynamics. Why: distinct frames were conflated. Fix: keep them separate; document
  coincidence.
- **Unresolved or mis-scaled mesh.** Symptom: the model won't load or is the wrong
  size. Why: a bad mesh path or unit. Fix: relative-path-resolves + mesh units match
  the metre scale.
