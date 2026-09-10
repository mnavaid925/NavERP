"""Projects 7.3 — ResourceAllocation form.

``booking_status`` and ``substitute_of`` are excluded — they are verb-driven state (assign /
substitute / commit / complete / cancel are the only writers, all POST-only and audited), and
leaving them on the form would let any member firm-up or cancel a booking through the ungated
edit view (the mst_achieve precedent). ``requested_by`` is provenance, stamped by ``ral_create``.
The model's ``clean()`` carries the attach-to-work guard, the window check and the
one-magnitude-matching-the-unit rule; the form only re-checks the crafted-POST boundary.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ResourceAllocation


class ResourceAllocationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ResourceAllocation
        fields = [
            "project", "project_request", "project_task", "resource", "role_name",
            "skill_requirements", "allocation_unit", "hours_per_week", "pct_capacity",
            "total_hours", "start_date", "end_date", "notes",
        ]
        help_texts = {
            "allocation_unit": "Set only the magnitude matching the allocation unit — the "
                               "others stay blank.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ResourceProfile.name walks employee → party — select_related it so the resource
        # dropdown's option labels do not pay two queries per pool row.
        self.fields["resource"].queryset = (self.fields["resource"].queryset
                                            .select_related("employee__party", "party"))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["project", "project_request", "project_task", "resource"])
        return cleaned
