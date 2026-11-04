from .DataMarts import urlpatterns as mart_urlpatterns
from .LakehouseZones import urlpatterns as zone_urlpatterns
from .WarehouseOverview import urlpatterns as overview_urlpatterns
from .WarehouseStoragePolicies import urlpatterns as policy_urlpatterns
from .WarehouseTables import urlpatterns as table_urlpatterns

urlpatterns = (
    overview_urlpatterns
    + mart_urlpatterns
    + zone_urlpatterns
    + policy_urlpatterns
    + table_urlpatterns
)

__all__ = ["urlpatterns"]
