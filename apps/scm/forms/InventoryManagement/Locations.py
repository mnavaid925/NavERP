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
        fields = ["code", "name", "location_type", "storage_condition", "parent", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and "parent" in self.fields:
            # A location can't be its own parent. parent is tenant-scoped by the base class.
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)
