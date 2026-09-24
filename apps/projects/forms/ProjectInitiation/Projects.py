"""Projects 7.1 — Project (charter) form.

Excludes the verb-driven and stamped fields: ``request`` (set by the convert verb only),
``charter_status`` + its approval stamps, and ``status``. There are no money columns on the model,
so there is nothing here for 7.4 to collide with.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign
from apps.projects.forms.MasterDataConfiguration.CustomFieldMixin import ProjectCustomFieldFormMixin
from apps.projects.models import Project


class ProjectForm(ProjectCustomFieldFormMixin, TenantUniqueMixin, TenantModelForm):
    custom_field_target = "project"
    class Meta:
        model = Project
        exclude = [
            "tenant", "number",                 # auto
            "request",                          # provenance, set by the convert verb
            "charter_status",                   # verb-driven
            "charter_approved_by", "charter_approved_at",   # stamps
            "status",                           # verb-driven
            "created_by",                       # set in the view
        ]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["org_unit", "client", "charter_document"])
        return cleaned
