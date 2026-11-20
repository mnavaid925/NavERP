from django import forms

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint


class CustomerComplaintForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerComplaint
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "status",
            "customer_letter_date",
            "triaged_by",
            "triaged_at",
            "closed_by",
            "closed_at",
        ]
        widgets = {
            "date_received": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "date_of_occurrence": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "sample_received_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "problem_description": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
            "non_reportable_justification": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "triage_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "no_investigation_rationale": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "resolution_summary": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            if "customer" in self.fields:
                from apps.core.models import Party
                self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)
            if "sales_order" in self.fields:
                from apps.scm.models import SalesOrder
                self.fields["sales_order"].queryset = SalesOrder.objects.filter(tenant=self.tenant)
            if "return_authorization" in self.fields:
                from apps.scm.models import ReturnAuthorization
                self.fields["return_authorization"].queryset = ReturnAuthorization.objects.filter(tenant=self.tenant)
            if "assigned_to" in self.fields:
                from django.contrib.auth import get_user_model
                self.fields["assigned_to"].queryset = get_user_model().objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["customer", "sales_order", "return_authorization", "assigned_to"])

        reportability = cleaned_data.get("reportability")
        justification = cleaned_data.get("non_reportable_justification")
        if reportability == "non_reportable" and not (justification and justification.strip()):
            self.add_error(
                "non_reportable_justification",
                "A detailed regulatory justification is required when determined non-reportable (21 CFR 820.198(a)(3)).",
            )

        investigation_required = cleaned_data.get("investigation_required")
        no_inv_rationale = cleaned_data.get("no_investigation_rationale")
        if investigation_required is False and not (no_inv_rationale and no_inv_rationale.strip()):
            self.add_error(
                "no_investigation_rationale",
                "Regulatory rationale is required when formal investigation is bypassed.",
            )

        return cleaned_data


class ComplaintTriageForm(forms.ModelForm):
    class Meta:
        model = CustomerComplaint
        fields = [
            "validity",
            "severity",
            "reportability",
            "non_reportable_justification",
            "complaint_category",
            "investigation_required",
            "no_investigation_rationale",
            "assigned_to",
            "triage_notes",
        ]
        widgets = {
            "non_reportable_justification": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "no_investigation_rationale": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "triage_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "assigned_to" in self.fields:
            from django.contrib.auth import get_user_model
            self.fields["assigned_to"].queryset = get_user_model().objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned_data, ["assigned_to"])

        reportability = cleaned_data.get("reportability")
        justification = cleaned_data.get("non_reportable_justification")
        if reportability == "non_reportable" and not (justification and justification.strip()):
            self.add_error(
                "non_reportable_justification",
                "A detailed regulatory justification is required when determined non-reportable (21 CFR 820.198(a)(3)).",
            )

        investigation_required = cleaned_data.get("investigation_required")
        no_inv_rationale = cleaned_data.get("no_investigation_rationale")
        if investigation_required is False and not (no_inv_rationale and no_inv_rationale.strip()):
            self.add_error(
                "no_investigation_rationale",
                "Regulatory rationale is required when formal investigation is bypassed.",
            )

        return cleaned_data
