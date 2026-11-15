"""Module 11.19 Fleet & Vehicle Management URLs package."""

from apps.assets.urls.FleetVehicleManagement.FleetTelematicsBoards import (
    urlpatterns as telematics_urlpatterns,
)
from apps.assets.urls.FleetVehicleManagement.FleetVehicles import (
    urlpatterns as vehicle_urlpatterns,
)
from apps.assets.urls.FleetVehicleManagement.VehicleDriverAssignments import (
    urlpatterns as driver_urlpatterns,
)
from apps.assets.urls.FleetVehicleManagement.VehicleFuelLogs import (
    urlpatterns as fuel_urlpatterns,
)
from apps.assets.urls.FleetVehicleManagement.VehicleServiceSchedules import (
    urlpatterns as service_urlpatterns,
)

urlpatterns = (
    telematics_urlpatterns
    + vehicle_urlpatterns
    + fuel_urlpatterns
    + driver_urlpatterns
    + service_urlpatterns
)
