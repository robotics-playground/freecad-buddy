"""Phase 4 service host: the supervisor, its worker pool, and the job lifecycle.

Nothing in this package may import FreeCAD except ``worker.py``, which runs on the far side of
the process boundary. ``scripts/check_imports.py`` enforces that split — the supervisor's flat
RSS is what makes the G4 soak leak measurement interpretable, and it holds only if FreeCAD is
never loaded into this process (AD-18).
"""
