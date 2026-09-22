"""Projects 7.18 — ProjectSyncJob forms."""
from django import forms

from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.IntegrationApiHub.SyncJobs import ProjectSyncJob


class ProjectSyncJobForm(TenantUniqueMixin, TenantModelForm):
    """Form for creating and updating ProjectSyncJob instances."""

    class Meta:
        model = ProjectSyncJob
        fields = [
            "connector",
            "name",
            "entity_scope",
            "direction",
            "trigger_mode",
            "interval_minutes",
            "schedule_note",
            "filter_expression",
            "conflict_policy",
            "batch_size",
            "is_active",
        ]
        widgets = {
            "filter_expression": forms.Textarea(
                attrs={"rows": 2, "class": "form-textarea font-mono text-sm"}
            ),
        }
        help_texts = {
            "filter_expression": "Recorded intent only — NavERP never evaluates this expression.",
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["connector"])
        return cleaned
