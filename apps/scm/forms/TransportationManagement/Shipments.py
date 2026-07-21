"""SCM 4.6 Transportation Management System — Shipment form + tracking-event form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import Shipment, TrackingEvent


class ShipmentForm(TenantModelForm):
    """The shipment header.

    EXCLUDES `number` (auto), `status` (advanced only by the book/dispatch/deliver/cancel actions and
    the tracking-event projection), the `actual_*` timestamps, and every field derived from the latest
    tracking event (`current_status_text`, `last_known_location`, `eta`, POD). All FK fields
    (carrier/load/sales_order/purchase_order/addresses) auto-scope to this tenant because their target
    models carry their own tenant.
    """

    class Meta:
        model = Shipment
        fields = ["direction", "carrier", "load", "sales_order", "purchase_order",
                  "ship_from_address", "ship_to_address", "origin_text", "destination_text", "mode",
                  "planned_pickup_date", "planned_delivery_date", "weight_kg", "volume_cbm",
                  "package_count", "carrier_tracking_number", "freight_cost_estimate", "notes"]


class TrackingEventForm(TenantModelForm):
    """One append-only tracking milestone. `recorded_by` is stamped from the request in the view, so
    it is not a form field. Appending an event projects onto the shipment via
    `Shipment.apply_tracking_event()` — this form only captures the raw event."""

    class Meta:
        model = TrackingEvent
        fields = ["event_type", "event_at", "location_text", "latitude", "longitude", "source", "notes"]
