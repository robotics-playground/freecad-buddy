"""Force the post-abort rollback proof to fail once, the state FreeCAD #6031 leaves behind.

Abort restores every pattern these tests drive on FreeCAD 1.1.x, so the escalation to the snapshot
restore is planted: the first digest comparison and the first mass-property comparison
``run_mutation`` makes after the abort both report a mismatch. Every later comparison, the proof
of the restored document included, is real.
"""

import contextlib

from freecad_buddy.usecases import transaction


@contextlib.contextmanager
def abort_proof_mismatch():
    real = {
        "fingerprints_equal": transaction.fingerprints_equal,
        "massprops_equal": transaction.massprops_equal,
    }
    calls = {name: 0 for name in real}

    def once_unequal(name):
        def compare(left, right):
            calls[name] += 1
            return False if calls[name] == 1 else real[name](left, right)

        return compare

    for name in real:
        setattr(transaction, name, once_unequal(name))
    try:
        yield
    finally:
        for name, function in real.items():
            setattr(transaction, name, function)
