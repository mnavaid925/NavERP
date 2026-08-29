"""Procurement 6.12 Goods Receipt & Inspection views — one module per entity.

Re-exported by the app-level views package so ``views.<name>`` resolves in the URLconf. A view
missing from this block is an ``AttributeError`` raised at URLconf **import** time — i.e. every
page in the app 500s, not just the one that was forgotten.

``ReceiptBoards.py`` holds the three read-only computed pages (``receiving_console``,
``tolerance_exceptions``, ``receipt_audit``) plus the console's two POST verbs — booking a DRAFT
``scm.GoodsReceiptNote`` from an ASN declaration and minting the declared lots. The stock and
ledger effects stay with SCM's admin-gated ``scm:goodsreceipt_receive``: one writer for the
ledger (L29/L36).
"""
from .ReceiptBoards import (
    receipt_audit,
    receiving_console,
    receiving_console_book,
    receiving_console_mint_lots,
    tolerance_exceptions,
)
from .ReceiptDiscrepancies import (
    discrepancy_cancel,
    discrepancy_create,
    discrepancy_delete,
    discrepancy_detail,
    discrepancy_edit,
    discrepancy_list,
    discrepancy_notify_vendor,
    discrepancy_resolve,
)
from .ReceiptTolerances import (
    tolerancepolicy_create,
    tolerancepolicy_delete,
    tolerancepolicy_detail,
    tolerancepolicy_edit,
    tolerancepolicy_list,
)
from .ReturnsToVendor import (
    rtv_authorize,
    rtv_cancel,
    rtv_close,
    rtv_create,
    rtv_delete,
    rtv_detail,
    rtv_edit,
    rtv_list,
    rtv_ship,
)

__all__ = [
    "tolerancepolicy_list",
    "tolerancepolicy_detail",
    "tolerancepolicy_create",
    "tolerancepolicy_edit",
    "tolerancepolicy_delete",
    "discrepancy_list",
    "discrepancy_detail",
    "discrepancy_create",
    "discrepancy_edit",
    "discrepancy_delete",
    "discrepancy_notify_vendor",
    "discrepancy_resolve",
    "discrepancy_cancel",
    "rtv_list",
    "rtv_detail",
    "rtv_create",
    "rtv_edit",
    "rtv_delete",
    "rtv_authorize",
    "rtv_ship",
    "rtv_close",
    "rtv_cancel",
    "receiving_console",
    "receiving_console_book",
    "receiving_console_mint_lots",
    "tolerance_exceptions",
    "receipt_audit",
]
