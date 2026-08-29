"""Procurement 6.12 Goods Receipt & Inspection models — one module per entity.

``ReceiptTolerances.py`` = ``ReceiptTolerancePolicy`` (a rule master with **no** number prefix —
the ``QcRoutingRule`` / ``ApprovalRoutingRule`` / ``EscalationPolicy`` precedent) plus the three
module-level functions that make it useful: ``resolve_receipt_tolerance`` (which rule governs
this line), ``evaluate_receipt_tolerance`` (what that rule says about these quantities/dates) and
``resolve_line_item`` (the free-text ``sku_hint`` → ``scm.Item`` bridge, mirroring
``apps/scm/views/_helpers.py:_resolve_grn_item`` rather than importing a private cross-app
symbol). Selection and judgement are deliberately two functions: they are independently testable,
and the exceptions board needs the verdict for lines whose rule was already resolved.

``ReceiptDiscrepancies.py`` = ``ReceiptDiscrepancy`` [RDS-], the commercial finding anchored to a
``scm.GoodsReceiptNote`` (optionally to one of its lines).

``ReturnsToVendor.py`` = ``ReturnToVendor`` [RTV-] + its tenant-less ``ReturnToVendorLine`` child
(the ``AsnLine`` / ``PurchaseOrderChangeLine`` precedent — the child is scoped through its header).

Six of this sub-module's ten NavERP bullets add **no model at all**: quality checklists, the
quarantine hold, lot/serial capture, barcode labels and inventory posting already live in
inventory 5.14/5.15 and scm 4.1/4.3/4.9, and 6.12 maps to them rather than opening a second
register (L36). The three remaining computed pages — the receiving console, the tolerance
exceptions board and the receipt audit trail — are views over these rows joined to the SCM spine,
which is why there is no ``ReceiptBoards.py`` here.
"""
from .ReceiptDiscrepancies import ReceiptDiscrepancy
from .ReceiptTolerances import (
    ReceiptTolerancePolicy,
    evaluate_receipt_tolerance,
    resolve_line_item,
    resolve_receipt_tolerance,
)
from .ReturnsToVendor import ReturnToVendor, ReturnToVendorLine

__all__ = [
    "ReceiptTolerancePolicy",
    "resolve_receipt_tolerance",
    "evaluate_receipt_tolerance",
    "resolve_line_item",
    "ReceiptDiscrepancy",
    "ReturnToVendor",
    "ReturnToVendorLine",
]
