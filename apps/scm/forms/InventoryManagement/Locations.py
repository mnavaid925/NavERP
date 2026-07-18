"""SCM 4.3 Inventory Management — Location form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import Location


class LocationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Location
        fields = ["code", "name", "location_type", "parent", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and "parent" in self.fields:
            # A location can't be its own parent. parent is tenant-scoped by the base class.
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)
