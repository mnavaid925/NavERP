"""Projects 7.3 — ResourceProfile form.

``status`` stays ON the form: active/inactive is a lens toggle on the pool register, not
verb-driven governance state (unlike the booking status on ResourceAllocation, which only the
commit/assign/substitute verbs move). ``number`` and the tenant are excluded as always; the
model's ``clean()`` carries the exactly-one-of-employee/party guard and the one-row-per-employee
pool check, so the form only re-checks the crafted-POST boundary with ``_reject_foreign``.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ResourceProfile


class ResourceProfileForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ResourceProfile
        fields = [
            "employee", "party", "resource_type", "default_role", "org_unit",
            "skill_summary", "weekly_capacity_hours", "utilization_target_pct",
            "available_from", "available_to", "status", "notes",
        ]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["employee", "party", "org_unit"])
        return cleaned
