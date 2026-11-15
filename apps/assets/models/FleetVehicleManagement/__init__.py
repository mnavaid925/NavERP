"""Fleet & Vehicle Management models package (11.19)."""

from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleDriverAssignments import VehicleDriverAssignment
from apps.assets.models.FleetVehicleManagement.VehicleFuelLogs import VehicleFuelLog
from apps.assets.models.FleetVehicleManagement.VehicleServiceSchedules import VehicleServiceSchedule

__all__ = [
    "FleetVehicle",
    "VehicleFuelLog",
    "VehicleDriverAssignment",
    "VehicleServiceSchedule",
]
