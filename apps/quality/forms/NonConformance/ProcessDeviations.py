from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation

User = get_user_model()


class ProcessDeviationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProcessDeviation
        fields = [
            "title",
            "deviation_type",
            "category",
            "ncr",
            "controlled_document",
            "department",
            "requested_by",
            "approved_by",
            "risk_impact_level",
            "quality_impact_assessment",
            "affected_lots_summary",
            "customer_notification_required",
            "customer_concession_obtained",
            "regulatory_reporting_required",
            "regulatory_authority_notified",
            "valid_from",
            "valid_until",
            "max_batches_permitted",
            "batches_produced_count",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Temporary Reflow Profile Adjustment for Line 2 Thermal Drift"}),
            "deviation_type": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "ncr": forms.Select(attrs={"class": "form-select"}),
            "controlled_document": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "requested_by": forms.Select(attrs={"class": "form-select"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "risk_impact_level": forms.Select(attrs={"class": "form-select"}),
            "quality_impact_assessment": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Assessment of impact on safety, efficacy, validation, and stability..."}),
            "affected_lots_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Impacted lot numbers, batch runs, or equipment serials..."}),
            "customer_notification_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "customer_concession_obtained": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "regulatory_reporting_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "regulatory_authority_notified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "valid_from": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "valid_until": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "max_batches_permitted": forms.NumberInput(attrs={"class": "form-input"}),
            "batches_produced_count": forms.NumberInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["ncr"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["controlled_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["requested_by"].queryset = user_qs
            self.fields["approved_by"].queryset = user_qs
        else:
            self.fields["ncr"].queryset = NonConformanceReport.objects.none()
            self.fields["controlled_document"].queryset = ControlledDocument.objects.none()
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["requested_by"].queryset = User.objects.none()
            self.fields["approved_by"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["ncr", "controlled_document", "department", "requested_by", "approved_by"])
        return cleaned
