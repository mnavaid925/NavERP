"""Projects 7.7 — ScopeRequirements models sub-package (one module per entity).

This package holds the per-entity modules; their public surface is re-exported from the
top-level ``apps/projects/models/__init__.py``. Adding a model here WITHOUT extending that
re-export block is an ImportError at runtime — keep the two in step.
"""
