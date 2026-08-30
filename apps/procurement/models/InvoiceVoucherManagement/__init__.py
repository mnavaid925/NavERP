"""6.13 Invoice & Voucher Management models.

Deliberately NO re-export block here: ``SupplierInvoices.py`` imports its sibling entity
modules (MatchVariances, SupplierInvoiceLines) at module level, and ``apps/procurement/
models/__init__.py`` imports THIS sub-package's entity modules directly — a re-export
``__init__`` would be a star-import cycle at URLconf import time. The app-level
``models/__init__.py`` re-exports all four models; that is the contract.
"""
