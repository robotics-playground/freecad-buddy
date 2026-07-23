"""Independent third-party export oracles (trimesh, lib3mf) plus a from-scratch STL checker.

These wrappers read a written export file directly and return per-oracle facts; they never
import FreeCAD (they run only in the external process). ``stl_oracle`` runs trimesh over an STL;
``StdlibStlOracle`` is a second, independent STL checker that parses the facets itself and
asserts manifold edge-pairing, winding, and non-degeneracy without reusing trimesh's loader.
``mesh3mf_oracle`` runs lib3mf (container/unit/manifold layer) and a trimesh geometry layer
built from the lib3mf mesh arrays. Cross-oracle disagreement is surfaced as separate legs, not
merged, so the verdict assembler can force FAIL on any disagreement.
"""

from __future__ import annotations

import struct
from typing import Protocol

_ASCII_STL_MARKER = b"solid"


def _read_binary_stl_facets(data: bytes) -> list[tuple]:
    """Parse a binary STL blob into a list of triangles ``(normal, v0, v1, v2)``.

    The 80-byte header is skipped, then a uint32 facet count, then 50 bytes per facet (a normal
    and three vertices as little-endian floats, plus a 2-byte attribute). Raises ``ValueError``
    when the blob is too short for its declared facet count.
    """
    count = struct.unpack_from("<I", data, 80)[0]
    facets = []
    offset = 84
    for _ in range(count):
        if offset + 50 > len(data):
            raise ValueError("binary STL truncated before its declared facet count")
        values = struct.unpack_from("<12f", data, offset)
        normal = values[0:3]
        v0, v1, v2 = values[3:6], values[6:9], values[9:12]
        facets.append((normal, v0, v1, v2))
        offset += 50
    return facets


def _read_ascii_stl_facets(text: str) -> list[tuple]:
    """Parse an ASCII STL into a list of triangles ``(normal, v0, v1, v2)``.

    A facet block whose vertex count is not exactly three is a malformed (truncated) file, not a
    facet to silently drop: raise ``ValueError`` so the corruption surfaces as a verification FAIL
    rather than a silently-normalised mesh.
    """
    facets: list[tuple] = []
    normal = (0.0, 0.0, 0.0)
    verts: list[tuple] = []
    for raw in text.splitlines():
        line = raw.strip().split()
        if not line:
            continue
        if line[0] == "facet" and len(line) >= 5 and line[1] == "normal":
            normal = tuple(float(x) for x in line[2:5])
            verts = []
        elif line[0] == "vertex" and len(line) >= 4:
            verts.append(tuple(float(x) for x in line[1:4]))
        elif line[0] == "endfacet":
            if len(verts) != 3:
                raise ValueError(
                    f"malformed ASCII STL facet: expected 3 vertices, got {len(verts)}"
                )
            facets.append((normal, verts[0], verts[1], verts[2]))
    return facets


def _load_stl_facets(path: str) -> list[tuple]:
    """Return the STL triangles at ``path``, auto-detecting ASCII vs binary.

    FreeCAD writes binary STL with a non-``solid`` 80-byte header, so the binary path is the
    default; a leading ``solid`` token with no binary-consistent size is treated as ASCII.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) >= 84 and data[:5] != _ASCII_STL_MARKER:
        return _read_binary_stl_facets(data)
    # A "solid"-prefixed file may still be binary; trust the size when it matches.
    if len(data) >= 84:
        declared = struct.unpack_from("<I", data, 80)[0]
        if 84 + declared * 50 == len(data):
            return _read_binary_stl_facets(data)
    return _read_ascii_stl_facets(data.decode("ascii", errors="ignore"))


class SecondStlOracle(Protocol):
    """A second, independent STL checker: returns ``{checks, ok}`` for a written STL file."""

    def check(self, path: str) -> dict: ...


class StdlibStlOracle:
    """From-scratch STL checker independent of trimesh's loader.

    Parses the facets itself, quantizes vertices to fuse coincident corners, and asserts:
    every edge is shared by exactly two facets (manifold), no shared edge is traversed in the
    SAME direction by two facets (locally consistent winding — a same-direction directed edge
    means one of the two neighbours is flipped relative to the other), and no facet is degenerate
    (zero area). A UNIFORM reversal of every facet is deliberately NOT flagged here — it leaves
    winding locally consistent — so that flipped-normals detection comes from the disagreement
    with trimesh (which does test global orientation). Any failure marks the leg ``ok=False``;
    the individual checks are returned so a disagreement with trimesh is visible.
    """

    def __init__(self, quantum: float = 1e-6) -> None:
        self._q = quantum

    def _key(self, vertex: tuple) -> tuple:
        return tuple(round(float(c) / self._q) for c in vertex)

    @staticmethod
    def _degenerate(v0: tuple, v1: tuple, v2: tuple) -> bool:
        ax, ay, az = (v1[i] - v0[i] for i in range(3))
        bx, by, bz = (v2[i] - v0[i] for i in range(3))
        cx = ay * bz - az * by
        cy = az * bx - ax * bz
        cz = ax * by - ay * bx
        return (cx * cx + cy * cy + cz * cz) <= 0.0

    def check(self, path: str) -> dict:
        """Return ``{checks: [...], ok: bool}`` for the STL at ``path``."""
        facets = _load_stl_facets(path)
        edge_count: dict[tuple, int] = {}
        directed: set[tuple] = set()
        winding_ok = True
        degenerate = 0

        for _normal, v0, v1, v2 in facets:
            k0, k1, k2 = self._key(v0), self._key(v1), self._key(v2)
            if self._degenerate(v0, v1, v2):
                degenerate += 1
            for a, b in ((k0, k1), (k1, k2), (k2, k0)):
                undirected = (a, b) if a <= b else (b, a)
                edge_count[undirected] = edge_count.get(undirected, 0) + 1
                if (a, b) in directed:
                    winding_ok = False
                directed.add((a, b))

        non_paired = [e for e, n in edge_count.items() if n != 2]
        manifold_ok = len(non_paired) == 0 and len(facets) > 0

        checks = [
            {"id": "stl2.facets", "measured": len(facets), "passed": len(facets) > 0},
            {
                "id": "stl2.manifold_edge_pairing",
                "measured": len(non_paired),
                "passed": manifold_ok,
            },
            {"id": "stl2.local_winding", "measured": winding_ok, "passed": winding_ok},
            {"id": "stl2.non_degenerate", "measured": degenerate, "passed": degenerate == 0},
        ]
        return {"oracle": "stdlib_stl", "checks": checks, "ok": all(c["passed"] for c in checks)}


def safe_oracle(name: str, fn) -> dict:
    """Run an oracle callable, turning any failure into a failed leg rather than raising.

    A missing/corrupt export file or an unreadable mesh is a verification FAIL, not a caller
    error: the oracle leg reports ``ok=False`` with a ``<name>.readable`` check so the merged
    verdict fails closed instead of surfacing the exception as ``INVALID_INPUT``/a crash.
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - an oracle that cannot read the file is a failed leg
        return {
            "oracle": name,
            "checks": [{"id": f"{name}.readable", "measured": str(exc), "passed": False}],
            "ok": False,
        }


def stl_oracle(path: str, expected_volume: float, volume_band: float) -> dict:
    """Run trimesh over an STL file; return ``{oracle, checks, ok}``.

    Checks ``is_watertight``, ``is_winding_consistent``, ``is_volume``, ``mesh.volume`` within
    the deflection-derived ``volume_band`` (never ±0.1 %), and an even Euler characteristic.
    """
    import trimesh

    # process=True welds the per-facet duplicated vertices FreeCAD's binary STL emits, so a
    # sound mesh reads back watertight; a real hole or non-manifold edge still fails to weld.
    mesh = trimesh.load(path, file_type="stl", process=True)
    return _trimesh_checks(mesh, expected_volume, volume_band, oracle="trimesh_stl")


def _trimesh_checks(mesh, expected_volume: float, volume_band: float, oracle: str) -> dict:
    """Return the trimesh geometry checks for ``mesh`` against the expected volume/band."""
    watertight = bool(mesh.is_watertight)
    winding = bool(mesh.is_winding_consistent)
    is_volume = bool(mesh.is_volume)
    volume = abs(float(mesh.volume))
    volume_ok = abs(volume - abs(float(expected_volume))) <= float(volume_band)
    euler = int(mesh.euler_number)
    # A closed orientable surface has even Euler characteristic (sum of 2-2g over its bodies), so
    # an odd value signals a non-closed/non-manifold mesh. A specific value is NOT required: a
    # through-hole part (genus 1, chi 0) and a two-body compound (chi 4) are both valid exports.
    euler_ok = euler % 2 == 0

    checks = [
        {"id": f"{oracle}.watertight", "measured": watertight, "passed": watertight},
        {"id": f"{oracle}.winding_consistent", "measured": winding, "passed": winding},
        {"id": f"{oracle}.is_volume", "measured": is_volume, "passed": is_volume},
        {
            "id": f"{oracle}.volume_band",
            "measured": volume,
            "expected": abs(float(expected_volume)),
            "tolerance": {"abs": float(volume_band)},
            "passed": volume_ok,
        },
        {"id": f"{oracle}.euler", "measured": euler, "passed": euler_ok},
    ]
    return {"oracle": oracle, "checks": checks, "ok": all(c["passed"] for c in checks)}


def _lib3mf_meshes(model) -> list:
    """Return every mesh object in a lib3mf model (a multi-mesh container yields more than one)."""
    meshes = []
    iterator = model.GetMeshObjects()
    while iterator.MoveNext():
        meshes.append(iterator.GetCurrentMeshObject())
    return meshes


def _trimesh_from_lib3mf(mesh_obj):
    """Build a ``trimesh.Trimesh`` from a lib3mf mesh object's vertex/triangle arrays.

    The 3MF geometry layer reuses trimesh's assertions without invoking its 3MF scene loader,
    so no extra scene-graph dependency is pulled in.
    """
    import numpy
    import trimesh

    vertices = numpy.array([v.Coordinates for v in mesh_obj.GetVertices()], dtype=float)
    faces = numpy.array([t.Indices for t in mesh_obj.GetTriangleIndices()], dtype=int)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def mesh3mf_oracle(
    path: str, source_is_mm: bool, expected_volume: float, volume_band: float
) -> dict:
    """Run the lib3mf container layer and a trimesh geometry layer over a 3MF file.

    lib3mf asserts: the file parses, the declared unit is millimetre AND the source document was
    mm (unit-lie guard), and ``IsManifoldAndOriented()`` holds for EVERY mesh object in the
    container (an open surface written as a model object, or a defect in any 2nd+ mesh, fails).
    The metadata count is reported as a non-verdict fact — missing metadata is not a declared 3MF
    fault, so it never drives FAIL. trimesh asserts the same geometry checks as the STL oracle,
    built from the first lib3mf mesh's arrays. Returns ``{oracle, checks, ok}`` with both layers
    combined; a parse failure or missing mesh yields a single failed check.
    """
    import lib3mf

    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    try:
        reader = model.QueryReader("3mf")
        reader.ReadFromFile(path)
    except Exception as exc:  # noqa: BLE001 - a container that will not parse is a failed oracle
        return {
            "oracle": "lib3mf",
            "checks": [{"id": "lib3mf.parses", "measured": str(exc), "passed": False}],
            "ok": False,
        }

    unit = int(model.GetUnit())
    unit_ok = unit == int(lib3mf.ModelUnit.MilliMeter) and bool(source_is_mm)

    meshes = _lib3mf_meshes(model)
    if not meshes:
        return {
            "oracle": "lib3mf",
            "checks": [
                {"id": "lib3mf.parses", "measured": True, "passed": True},
                {"id": "lib3mf.has_mesh", "measured": False, "passed": False},
            ],
            "ok": False,
        }

    # Manifold-check EVERY mesh object: a defect in the 2nd+ mesh of a multi-mesh container must
    # fail, not pass on the first mesh's soundness alone.
    non_manifold = sum(1 for mesh_obj in meshes if not bool(mesh_obj.IsManifoldAndOriented()))
    manifold = non_manifold == 0
    metadata_count = int(model.GetMetaDataGroup().GetMetaDataCount())

    checks = [
        {"id": "lib3mf.parses", "measured": True, "passed": True},
        {
            "id": "lib3mf.unit_millimeter",
            "measured": {"unit": unit, "source_is_mm": bool(source_is_mm)},
            "passed": unit_ok,
        },
        {
            "id": "lib3mf.manifold_and_oriented",
            "measured": {"meshes": len(meshes), "non_manifold": non_manifold},
            "passed": manifold,
        },
        {"id": "lib3mf.metadata_present", "measured": metadata_count, "passed": True},
    ]

    trimesh_leg = _trimesh_checks(
        _trimesh_from_lib3mf(meshes[0]), expected_volume, volume_band, oracle="trimesh_3mf"
    )
    checks.extend(trimesh_leg["checks"])
    return {"oracle": "lib3mf", "checks": checks, "ok": all(c["passed"] for c in checks)}
