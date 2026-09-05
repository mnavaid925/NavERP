"""Procurement 6.18 Inventory & Warehouse Integration — views sub-package init (docstring-only).

Re-exports live in ``apps/procurement/views/__init__.py`` — the app-level package is the single
re-export point (6.13/6.14/6.15/6.17 precedent). Entity/page modules: ``Policies``, ``Runs``,
``MaterialIssues`` (the three CRUD entities) plus ``StockPosition``, ``ReceiptBinMap`` and
``CountAccuracy`` (the three derived, no-model analysis pages), mirroring the urls/ package
one-for-one.
"""
