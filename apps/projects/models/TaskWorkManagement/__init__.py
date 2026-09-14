"""Projects 7.8 — TaskWorkManagement models sub-package (one module per entity).

Intentionally EMPTY by convention: the package's public surface is the top-level
``apps/projects/models/__init__.py`` re-export block (the 7.8 classes are re-exported there
now that the Integrate step has landed). Every sub-package in this app keeps its own
``__init__.py`` empty, which is what makes the "missing re-export is an ImportError" rule
visible.
"""
