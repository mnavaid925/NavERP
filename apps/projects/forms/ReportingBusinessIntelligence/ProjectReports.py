"""Projects 7.16 Reporting & Business Intelligence — ProjectReportForm, the guided builder.

Every axis is a dropdown or a checkbox set, never a text box: the vocabulary is frozen in
``_choices.py`` and ``ProjectReport.clean()`` re-checks it, so a crafted POST cannot invent an axis.
``tenant=`` narrows the four scope querysets for UX; ``_reject_foreign`` is the authorization boundary.
"""
from django import forms

from apps.core.models import OrgUnit, Party
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ReportingBusinessIntelligence.ProjectReports import ProjectReport
from apps.projects.models.ReportingBusinessIntelligence._choices import MEASURE_CHOICES


class ProjectReportForm(TenantUniqueMixin, TenantModelForm):
    """The report definition editor. ``number``, ``owner``, ``is_favorite`` and ``last_run_at`` are
    deliberately absent — they are stamped by the view or moved by a verb, never typed."""

    #: The one field whose FORM type differs from its COLUMN type: a JSON list asked as a checkbox set.
    #: ``MultipleChoiceField`` already hands the model a ``list``, and ``ProjectReport.clean()`` owns the
    #: 1–3 and known-key rules, so no ``clean_measures`` here — a second copy would only drift.
    measures = forms.MultipleChoiceField(
        choices=MEASURE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check"}),
        help_text="Pick 1–3. The first measure feeds the chart series, the sort and the RAG rating.",
    )
    #: Not ``choices=`` on the model: a sort key must be one of THIS report's measures, which the model
    #: validates. The blank option is the "sort by the first measure" default.
    sort_by = forms.ChoiceField(
        choices=[("", "— first measure —")] + list(MEASURE_CHOICES), required=False,
    )

    class Meta:
        model = ProjectReport
        fields = [
            "name", "description", "report_type", "subject", "measures", "dimension_1",
            "dimension_2", "date_range", "date_from", "date_to", "as_of",
            "project", "portfolio", "client", "org_unit",
            "chart_type", "top_n", "sort_by", "notes", "is_shared",
        ]
        # What Django does not give by itself: the two row counts, and top_n's browser max — its min comes
        # from the model's validators, its max does not. Classes and type="date" are the base class's job.
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "top_n": forms.NumberInput(attrs={"max": "100"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=tenant).order_by("name")
            self.fields["portfolio"].queryset = Portfolio.objects.filter(
                tenant=tenant).order_by("name")
            self.fields["client"].queryset = Party.objects.filter(
                tenant=tenant).order_by("name")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "portfolio", "client", "org_unit"])
        return cleaned
