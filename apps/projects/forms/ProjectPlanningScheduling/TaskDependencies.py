"""Projects 7.2 — TaskDependency form."""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import TaskDependency


class TaskDependencyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = TaskDependency
        fields = ["predecessor", "successor", "link_type", "lag_days", "note"]

    def clean(self):
        cleaned = super().clean()
        # Both endpoints are tenant-stamped Task rows, so the crafted-POST re-check applies.
        _reject_foreign(self, cleaned, ["predecessor", "successor"])
        return cleaned
