"""SCM 4.6 Transportation Management System — Load form + stop formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import Load, LoadStop


class LoadForm(TenantModelForm):
    """The load header.

    EXCLUDES `number` (auto), `status` (advanced only by the dispatch/deliver/cancel actions) and the
    two `actual_*` timestamps (stamped by those actions). `carrier` auto-scopes to this tenant because
    `Carrier` carries its own tenant.
    """

    class Meta:
        model = Load
        fields = ["carrier", "mode", "equipment_type", "origin_text", "destination_text",
                  "planned_departure", "planned_arrival", "distance_km", "estimated_fuel_cost",
                  "freight_cost_estimate", "equipment_capacity_weight_kg", "equipment_capacity_volume_cbm",
                  "driver_name", "vehicle_ref", "notes"]


class LoadStopForm(TenantModelForm):
    """One route stop. `address` auto-scopes to this tenant (core.Address carries its own tenant);
    `actual_arrival` is excluded — it is stamped as the trip progresses, not typed."""

    class Meta:
        model = LoadStop
        fields = ["sequence", "stop_type", "address", "address_text", "planned_arrival", "status", "notes"]


LoadStopFormSet = inlineformset_factory(
    Load, LoadStop, form=LoadStopForm, extra=2, can_delete=True,
)
