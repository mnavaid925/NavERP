from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.SupplierQuality.SupplierChangeNotifications import (
    SupplierChangeNotification,
)
from apps.quality.models.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAudit,
)

User = get_user_model()


class SupplierChangeNotificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SupplierChangeNotification
        fields = [
            "supplier",
            "title",
            "supplier_scn_number",
            "change_category",
            "risk_level",
            "status",
            "description",
            "proposed_effective_date",
            "first_affected_lot",
            "affected_item_code",
            "affected_item_name",
            "affects_form_fit_function",
            "requires_requalification",
            "requires_design_change",
            "requires_regulatory_filing",
            "requires_customer_notification",
            "samples_required",
            "impact_assessment_notes",
            "design_project",
            "requalification_audit",
            "disposition",
            "disposition_notes",
            "approved_by",
            "evaluated_by",
        ]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "supplier_scn_number": forms.TextInput(attrs={"class": "form-input"}),
            "change_category": forms.Select(attrs={"class": "form-select"}),
            "risk_level": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "proposed_effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "first_affected_lot": forms.TextInput(attrs={"class": "form-input"}),
            "affected_item_code": forms.TextInput(attrs={"class": "form-input"}),
            "affected_item_name": forms.TextInput(attrs={"class": "form-input"}),
            "affects_form_fit_function": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_requalification": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_design_change": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_regulatory_filing": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_customer_notification": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "samples_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "impact_assessment_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "design_project": forms.Select(attrs={"class": "form-select"}),
            "requalification_audit": forms.Select(attrs={"class": "form-select"}),
            "disposition": forms.Select(attrs={"class": "form-select"}),
            "disposition_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "evaluated_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            suppliers = Party.objects.filter(
                tenant=self.tenant, roles__role__in=("supplier", "vendor")
            ).distinct().order_by("name")
            if not suppliers.exists():
                suppliers = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["supplier"].queryset = suppliers
            self.fields["design_project"].queryset = DesignProject.objects.filter(
                tenant=self.tenant
            ).order_by("title")
            self.fields["requalification_audit"].queryset = SupplierQualificationAudit.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            users = User.objects.filter(tenant=self.tenant).order_by("first_name", "last_name", "email")
            self.fields["approved_by"].queryset = users
            self.fields["evaluated_by"].queryset = users

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["supplier", "design_project", "requalification_audit", "approved_by", "evaluated_by"],
        )
        return cleaned_data
