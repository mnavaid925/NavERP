"""Procurement 6.12 Goods Receipt & Inspection forms — one module per entity.

Re-exported by the app-level forms package. Three ModelForm families (tolerance policy,
discrepancy, RTV header + line formset) plus the small ``forms.Form`` verbs that carry a note or a
reference into a status transition, and ``ReceivingConsoleBookForm`` — the console's only write,
a plain ``Form`` rather than a ModelForm over ``scm.GoodsReceiptNote`` because the GRN is SCM's
document and already has an editor there (L36).

``ALLOWED_DOC_EXTENSIONS`` / ``MAX_UPLOAD_BYTES`` are deliberately **NOT** re-exported here: this
app already carries a different local ``MAX_UPLOAD_BYTES`` (2 MB) in
``forms/CatalogManagement/UploadBatches.py``, and a package-level re-export would make which cap
applies depend on import order. The discrepancy evidence field imports the 20 MB core constants
locally instead.
"""
from .ReceiptBoards import ReceivingConsoleBookForm
from .ReceiptDiscrepancies import (
    DiscrepancyCancelForm,
    DiscrepancyNotifyForm,
    DiscrepancyResolveForm,
    ReceiptDiscrepancyForm,
)
from .ReceiptTolerances import ReceiptTolerancePolicyForm
from .ReturnsToVendor import (
    ReturnToVendorForm,
    ReturnToVendorLineForm,
    ReturnToVendorLineFormSet,
    RtvCancelForm,
    RtvCloseForm,
    RtvShipForm,
)

__all__ = [
    "ReceiptTolerancePolicyForm",
    "ReceiptDiscrepancyForm",
    "DiscrepancyNotifyForm",
    "DiscrepancyResolveForm",
    "DiscrepancyCancelForm",
    "ReturnToVendorForm",
    "ReturnToVendorLineForm",
    "ReturnToVendorLineFormSet",
    "RtvShipForm",
    "RtvCloseForm",
    "RtvCancelForm",
    "ReceivingConsoleBookForm",
]
