"""Projects 7.3 — ResourceTimeEntry form.

Status and the approval stamps are excluded — they are verb-driven (submit / approve / reject
are the only writers, all POST-only and audited); the form can never rewind an approval because
it cannot touch the stamps at all. The model carries no clean() beyond the base — ``hours > 0``
is the validator — so the form only re-checks the crafted-POST boundary.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ResourceTimeEntry


class ResourceTimeEntryForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ResourceTimeEntry
        fields = [
            "resource", "project", "project_task", "entry_date", "hours",
            "task_description", "notes",
        ]
        help_texts = {
            "hours": "Hours logged this day — positive only.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ResourceProfile.name walks employee → party — select_related it so the resource
        # dropdown's option labels do not pay two queries per pool row.
        self.fields["resource"].queryset = (self.fields["resource"].queryset
                                            .select_related("employee__party", "party"))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["resource", "project", "project_task"])
        return cleaned
