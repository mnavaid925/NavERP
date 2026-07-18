"""SCM 4.5 Order Management System — SalesOrderAllocation form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import Location, SalesOrderAllocation


class SalesOrderAllocationForm(TenantModelForm):
    """Reserve a quantity of one order line at one location.

    `sales_order_line` is NOT a field — the view assigns it from the `line_pk` URL kwarg, so the
    reservation can only ever attach to the line the user navigated from. Mirrors `RFQQuote.rfq`
    being taken from `rfq_pk` rather than offered as a dropdown; a user-choosable parent here would
    be both a usability trap and a cross-order tampering surface.

    `status` is excluded — it moves via the release/cancel actions.
    """

    class Meta:
        model = SalesOrderAllocation
        fields = ["location", "quantity", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            # Only pickable locations: reserving fulfillment stock into a logical non-pickable
            # location (transit, quarantine) promises the customer something nobody can pick.
            self.fields["location"].queryset = Location.objects.filter(
                tenant=self.tenant, is_active=True, is_pickable=True).order_by("code")
