"""Inventory 5.7 Stock Movement & Transfers — url package."""
from .ApprovalRules import urlpatterns as _tr_approvalrules
from .TransferRoutes import urlpatterns as _tr_routes
from .Transfers import urlpatterns as _tr_board

urlpatterns = [
    *_tr_board,           # Transfers/Transfers — board, queue, panel + governance verbs
    *_tr_routes,          # Transfers/TransferRoutes — routing catalog
    *_tr_approvalrules,   # Transfers/ApprovalRules — approval policy catalog
]
