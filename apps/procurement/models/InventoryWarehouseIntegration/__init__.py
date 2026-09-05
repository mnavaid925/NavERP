"""Procurement 6.18 Inventory & Warehouse Integration — sub-package init (docstring-only).

Re-exports live in ``apps/procurement/models/__init__.py`` — the app-level package is the single
re-export point (6.13/6.14/6.15/6.17 precedent). Entity modules: ``Policies`` (the procurement-side
replenishment overlay on ``scm.ReorderRule``), ``Runs`` (the persisted replenishment proposal and
its suggestion lines) and ``MaterialIssues`` (the goods-issue / return-to-stock document that mints
a draft ``scm.StockAdjustment``).
"""
