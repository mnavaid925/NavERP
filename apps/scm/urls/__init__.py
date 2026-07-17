"""SCM URLconf package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets ``app_name = "scm"`` once and
concatenates them, so every ``scm:<name>`` reverse and ``include("apps.scm.urls")`` resolves.

Django is first-match-wins, so ORDER IS BEHAVIOUR. Keep literal routes before ``<int:pk>`` ones
within a module, and when you ADD a route with a greedy converter check it against this whole
concatenated list, not just its own module.
"""
from .ProcurementManagement.Overview import urlpatterns as _procurement_overview
from .ProcurementManagement.PurchaseRequisitions import urlpatterns as _procurement_purchaserequisitions
from .ProcurementManagement.Rfqs import urlpatterns as _procurement_rfqs
from .ProcurementManagement.PurchaseOrders import urlpatterns as _procurement_purchaseorders
from .ProcurementManagement.GoodsReceiptNotes import urlpatterns as _procurement_goodsreceiptnotes


app_name = "scm"

urlpatterns = [
    *_procurement_overview,              # ProcurementManagement/Overview — "" (module landing)
    *_procurement_purchaserequisitions,  # ProcurementManagement/PurchaseRequisitions
    *_procurement_rfqs,                  # ProcurementManagement/Rfqs (incl. quotes)
    *_procurement_purchaseorders,        # ProcurementManagement/PurchaseOrders
    *_procurement_goodsreceiptnotes,     # ProcurementManagement/GoodsReceiptNotes
]
