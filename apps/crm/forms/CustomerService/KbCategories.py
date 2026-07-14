"""CRM 1.4 Customer Service & Support — KbCategories forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    KbCategory,
)


class KbCategoryForm(TenantModelForm):
    class Meta:
        model = KbCategory
        fields = ["name", "description", "slug", "parent", "order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A category can't be its own parent.
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)
