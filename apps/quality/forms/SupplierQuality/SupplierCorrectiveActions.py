from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveAction,
)
from apps.quality.models.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAudit,
)
from apps.scm.models import NonConformance, PurchaseOrder

User = get_user_model()


class SupplierCorrectiveActionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SupplierCorrectiveAction
        fields = [
            "supplier",
            "title",
            "severity",
            "status",
            "defect_summary",
            "affected_item_code",
            "affected_item_name",
            "affected_lots",
            "purchase_order",
            "non_conformance",
            "qualification_audit",
            "internal_capa",
            "issued_date",
            "response_due_date",
            "issued_by",
            "containment_action",
            "containment_due_date",
            "containment_verified_at",
            "root_cause_summary",
            "root_cause_category",
            "vendor_investigation_details",
            "corrective_action_plan",
            "preventive_action_plan",
            "implementation_due_date",
            "implemented_at",
            "effectiveness_due_date",
            "effectiveness_method",
            "effectiveness_results",
            "is_effective",
            "verified_by",
        ]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "defect_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "affected_item_code": forms.TextInput(attrs={"class": "form-input"}),
            "affected_item_name": forms.TextInput(attrs={"class": "form-input"}),
            "affected_lots": forms.TextInput(attrs={"class": "form-input"}),
            "purchase_order": forms.Select(attrs={"class": "form-select"}),
            "non_conformance": forms.Select(attrs={"class": "form-select"}),
            "qualification_audit": forms.Select(attrs={"class": "form-select"}),
            "internal_capa": forms.Select(attrs={"class": "form-select"}),
            "issued_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "response_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "issued_by": forms.Select(attrs={"class": "form-select"}),
            "containment_action": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "containment_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "containment_verified_at": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "root_cause_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "root_cause_category": forms.Select(attrs={"class": "form-select"}),
            "vendor_investigation_details": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "corrective_action_plan": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "preventive_action_plan": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "implementation_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "implemented_at": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effectiveness_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effectiveness_method": forms.TextInput(attrs={"class": "form-input"}),
            "effectiveness_results": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "is_effective": forms.NullBooleanSelect(attrs={"class": "form-select"}),
            "verified_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not (self.instance and self.instance.pk and self.instance.status == "closed"):
            self.fields["status"].choices = [
                c for c in SupplierCorrectiveAction.STATUS_CHOICES if c[0] != "closed"
            ]
        if self.tenant:
            suppliers = Party.objects.filter(
                tenant=self.tenant, roles__role__in=("supplier", "vendor")
            ).distinct().order_by("name")
            if not suppliers.exists():
                suppliers = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["supplier"].queryset = suppliers
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(
                tenant=self.tenant
            ).order_by("-id")
            self.fields["non_conformance"].queryset = NonConformance.objects.filter(
                tenant=self.tenant
            ).order_by("-id")
            self.fields["qualification_audit"].queryset = SupplierQualificationAudit.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["internal_capa"].queryset = CapaInvestigation.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            users = User.objects.filter(tenant=self.tenant).order_by("first_name", "last_name", "email")
            self.fields["issued_by"].queryset = users
            self.fields["verified_by"].queryset = users

    def clean_status(self):
        status = self.cleaned_data.get("status")
        if status == "closed" and not (self.instance and self.instance.pk and self.instance.status == "closed"):
            raise forms.ValidationError("SCARs must be closed via the official Status update action.")
        return status

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "supplier",
                "purchase_order",
                "non_conformance",
                "qualification_audit",
                "internal_capa",
                "issued_by",
                "verified_by",
            ],
        )
        return cleaned_data
