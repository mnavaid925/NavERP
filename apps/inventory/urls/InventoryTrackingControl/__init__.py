"""Inventory 5.6 Inventory Tracking & Control — url re-exports."""
from .InventoryReservations import urlpatterns as _tc_reservations
from .StockLevels import urlpatterns as _tc_stocklevels
from .StockStatuses import urlpatterns as _tc_stockstatuses

urlpatterns = [
    *_tc_stocklevels,    # StockLevels (computed page)
    *_tc_stockstatuses,  # StockStatuses (CRUD)
    *_tc_reservations,   # InventoryReservations (CRUD + lifecycle verbs)
]
