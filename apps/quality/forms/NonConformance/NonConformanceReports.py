from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit, Party
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport

User = get_user_model()


class NonConformanceReportForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = NonConformanceReport
        fields = [
            "title",
            "description",
            "source_type",
            "category",
            "severity",
            "status",
            "defect_code",
            "department",
            "initiator",
            "owner",
            "supplier_party",
            "affected_item_code",
            "affected_item_name",
            "lot_serial_numbers",
            "quantity_inspected",
            "quantity_nonconforming",
            "unit_of_measure",
            "estimated_financial_loss",
            "immediate_containment_required",
            "capa_required",
            "capa_investigation",
            "target_resolution_date",
            "closure_notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PCB Solder Bridging in Sub-Assembly Stage"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe defect details, failure mode, immediate observations, and detection context..."}),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "defect_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. DIM-OOS, CONTAM, PKG-FAIL"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "initiator": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "supplier_party": forms.Select(attrs={"class": "form-select"}),
            "affected_item_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CMP-CAP-0402"}),
            "affected_item_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Surface Mount Ceramic Capacitor"}),
            "lot_serial_numbers": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOT-2026-X14, LOT-2026-X15"}),
            "quantity_inspected": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "quantity_nonconforming": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input", "placeholder": "EA, KG, M"}),
            "estimated_financial_loss": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "immediate_containment_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "capa_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "capa_investigation": forms.Select(attrs={"class": "form-select"}),
            "target_resolution_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "closure_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Formal closure rationale and verification notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["supplier_party"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["capa_investigation"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["initiator"].queryset = user_qs
            self.fields["owner"].queryset = user_qs
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["supplier_party"].queryset = Party.objects.none()
            self.fields["capa_investigation"].queryset = CapaInvestigation.objects.none()
            self.fields["initiator"].queryset = User.objects.none()
            self.fields["owner"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["department", "supplier_party", "capa_investigation", "initiator", "owner"])
        return cleaned
