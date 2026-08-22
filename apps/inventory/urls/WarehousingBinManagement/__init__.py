"""Inventory 5.5 Warehousing & Bin Management — URLconf sub-package."""
from .BinCapacities import urlpatterns as _bincapacities
from .CrossDockOrders import urlpatterns as _crossdockorders
from .WarehouseMap import urlpatterns as _warehousemap

urlpatterns = [*_bincapacities, *_crossdockorders, *_warehousemap]
