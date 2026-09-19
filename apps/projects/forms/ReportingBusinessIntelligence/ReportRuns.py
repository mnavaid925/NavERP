"""Projects 7.16 Reporting & Business Intelligence — ProjectReportRun forms.

A frozen run has NO builder form on purpose: no field for ``report``, ``title``, the window, ``summary``
or ``data``, because editing a frozen answer in place would destroy the one property that justifies the
table. These two forms cover the only human-authored late writes — the commentary and the issued document.
"""
from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import Document
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.ReportingBusinessIntelligence.ReportRuns import ProjectReportRun


class ProjectReportNarrativeForm(TenantUniqueMixin, TenantModelForm):
    """The commentary on a draft run — the only free text in 7.16 that reaches a colleague's page, so it
    renders auto-escaped through ``{{ }}`` like every other string (no ``|safe`` anywhere)."""

    class Meta:
        model = ProjectReportRun
        fields = ["narrative"]
        widgets = {
            "narrative": forms.Textarea(attrs={
                "rows": 8, "placeholder": "Commentary for the steering pack…",
            }),
        }

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and not self.instance.is_draft:
            raise ValidationError({"narrative": (
                "An issued or archived run cannot be edited — freeze a new run."
            )})
        return cleaned


class ProjectReportIssueForm(TenantUniqueMixin, TenantModelForm):
    """Attach an EXISTING document to the run being issued. No upload field: minting files is 7.10's job."""

    class Meta:
        model = ProjectReportRun
        fields = ["document"]
        widgets = {"document": forms.Select()}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is not None:
            self.fields["document"].queryset = Document.objects.filter(
                tenant=tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["document"])
        if self.instance.pk and not self.instance.is_draft:
            raise ValidationError({"document": (
                "Only a draft run can be issued — freeze a new run."
            )})
        return cleaned
