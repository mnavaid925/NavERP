"""Projects 7.19 — ProjectLocaleSetting forms."""
import json
from decimal import Decimal

from django import forms

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models.Localization import Language, TimeZone
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSetting
from apps.projects.models.ProjectInitiation.Projects import Project


class ProjectLocaleSettingForm(TenantUniqueMixin, TenantModelForm):
    """Admin/PM form for project regional and localization settings."""

    working_days_choices = forms.MultipleChoiceField(
        choices=[
            (1, "Monday"),
            (2, "Tuesday"),
            (3, "Wednesday"),
            (4, "Thursday"),
            (5, "Friday"),
            (6, "Saturday"),
            (7, "Sunday"),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-checkbox"}),
        required=False,
        initial=[1, 2, 3, 4, 5],
        label="Active Working Days",
        help_text="Standard business delivery days for scheduling and effort calculation.",
    )

    class Meta:
        model = ProjectLocaleSetting
        fields = [
            "name",
            "code",
            "project",
            "language",
            "time_zone",
            "currency",
            "date_format",
            "time_format",
            "first_day_of_week",
            "number_format",
            "working_hours_per_day",
            "is_default",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EMEA Regional Delivery Profile"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOC-EMEA-01"}),
            "project": forms.Select(attrs={"class": "form-select"}),
            "language": forms.Select(attrs={"class": "form-select"}),
            "time_zone": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "date_format": forms.Select(attrs={"class": "form-select"}),
            "time_format": forms.Select(attrs={"class": "form-select"}),
            "first_day_of_week": forms.Select(attrs={"class": "form-select"}),
            "number_format": forms.Select(attrs={"class": "form-select"}),
            "working_hours_per_day": forms.NumberInput(attrs={"class": "form-input", "step": "0.25"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

        self.fields["language"].queryset = Language.objects.filter(is_active=True).order_by("name")
        self.fields["time_zone"].queryset = TimeZone.objects.filter(is_active=True).order_by("name")
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")

        if self.instance and self.instance.pk:
            if self.instance.working_days_pattern:
                self.initial["working_days_choices"] = [str(d) for d in self.instance.working_days_pattern]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        selected_days = self.cleaned_data.get("working_days_choices") or []
        instance.working_days_pattern = [int(d) for d in selected_days]
        if commit:
            instance.save()
        return instance
