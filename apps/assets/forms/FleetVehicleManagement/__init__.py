"""Fleet & Vehicle Management forms package (11.19)."""

from apps.assets.forms.FleetVehicleManagement.FleetVehicles import FleetVehicleForm
from apps.assets.forms.FleetVehicleManagement.VehicleDriverAssignments import VehicleDriverAssignmentForm
from apps.assets.forms.FleetVehicleManagement.VehicleFuelLogs import VehicleFuelLogForm
from apps.assets.forms.FleetVehicleManagement.VehicleServiceSchedules import VehicleServiceScheduleForm

__all__ = [
    "FleetVehicleForm",
    "VehicleFuelLogForm",
    "VehicleDriverAssignmentForm",
    "VehicleServiceScheduleForm",
]
