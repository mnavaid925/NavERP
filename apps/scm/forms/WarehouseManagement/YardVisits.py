"""SCM 4.4 Warehouse Management — YardVisit form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import YardVisit


class YardVisitForm(TenantModelForm):
    class Meta:
        model = YardVisit
        # `status` and the arrived/docked/departed stamps EXCLUDED — they advance via the
        # arrive/dock/depart/cancel actions, so the timeline can't be back-dated by hand.
        fields = ["carrier_name", "vehicle_ref", "trailer_ref", "driver_name", "direction",
                  "dock_door", "purchase_order", "scheduled_at", "notes"]
        # dock_door (Location) and purchase_order are tenant-scoped, so the base class scopes them.
