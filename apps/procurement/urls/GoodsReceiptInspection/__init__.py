"""Procurement 6.12 Goods Receipt & Inspection URL patterns — one module per entity.

Six NEW first segments, all distinct whole components against the inventory in
``apps/procurement/urls/__init__.py``: ``receipt-tolerances/``, ``receipt-discrepancies/``,
``returns-to-vendor/``, ``receiving-console/``, ``tolerance-exceptions/`` and ``receipt-audit/``.
The app still registers no greedy ``<str:…>`` converter, so there is no cross-module shadowing
surface to reason about.

Django resolves first-match-wins, and within each module the literal routes (``add/``, ``book/``)
are declared before the ``<int:pk>/`` ones. Ordering here is behaviour, not tidiness.
"""
from .ReceiptBoards import urlpatterns as _gri_boards
from .ReceiptDiscrepancies import urlpatterns as _gri_discrepancies
from .ReceiptTolerances import urlpatterns as _gri_tolerances
from .ReturnsToVendor import urlpatterns as _gri_rtv

urlpatterns = [
    *_gri_tolerances,      # 6.12 receipt tolerance policies (rule master CRUD)
    *_gri_discrepancies,   # 6.12 discrepancy register + notify-vendor/resolve/cancel verbs
    *_gri_rtv,             # 6.12 return-to-vendor register + authorize/ship/close/cancel verbs
    *_gri_boards,          # 6.12 computed pages: receiving console (+ book / mint-lots),
                           #      tolerance exceptions board, receipt audit trail
]
