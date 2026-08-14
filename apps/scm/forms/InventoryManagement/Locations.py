"""SCM 4.3 Inventory Management — Location form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import Location


class LocationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Location
        # `storage_condition` is 4.15's temperature class. It sits on this whitelist for the same
        # reason `is_spare_part` sits on `ItemForm`'s: it is the other half of the Cold Storage
        # Inventory report's key (item class vs. location class), and the report's empty state sends
        # the admin here to "set the class on your locations". Off the whitelist there is nowhere in
        # the UI to follow that link to — the mismatch and unmonitored-zone sections could only ever
        # be populated by `seed_scm` and the Django admin.
        # `owner_client` is 4.17's reserved-space column, here for the same reason
        # `storage_condition` is: it is the SOLE selector for the Warehouse Rental Management page
        # (`scm:client_space_report`), which shows the bins actually reserved to a client beside what
        # that client committed to. Off the whitelist the reserved-bin column is permanently zero and
        # the page's own "assign this space to a client" instruction has nowhere in the UI to lead.
        fields = ["code", "name", "location_type", "storage_condition", "owner_client", "parent",
                  "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and "parent" in self.fields:
            # A location can't be its own parent. parent is tenant-scoped by the base class.
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)
