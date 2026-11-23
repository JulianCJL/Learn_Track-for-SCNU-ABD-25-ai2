"""Compatibility shim: the persistence layer was renamed json_storage.py.

The existing test suite and verify_bug_fixes.py still import
``json_storage_fixed``; this module re-exports its public API from
``json_storage`` so both import paths keep working.
"""

from json_storage import (  # noqa: F401
    PersistentTaskManager,
    create_manager,
    load_tasks,
    save_tasks,
)
