from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.ManagementReview.ManagementReviewActions import ManagementReviewAction
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview

User = get_user_model()


class ManagementReviewActionForm(TenantModelForm):
    class Meta:
        model = ManagementReviewAction
        fields = [
            "management_review",
            "title",
            "action_type",
            "priority",
            "assignee",
            "due_date",
            "budget_allocated",
            "description",
            "spawned_capa",
            "spawned_change_order",
            "notes",
        ]
        widgets = {
            "management_review": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Implement automated vision inspection on Packaging Line 2"}),
            "action_type": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "assignee": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "budget_allocated": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Detailed specification of improvement or resource requirement"}),
            "spawned_capa": forms.Select(attrs={"class": "form-select"}),
            "spawned_change_order": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["management_review"].queryset = ManagementReview.objects.filter(
                tenant=self.tenant
            ).order_by("-scheduled_date", "-created_at")
            self.fields["assignee"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["spawned_capa"].queryset = CapaInvestigation.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["spawned_change_order"].queryset = DocumentChangeOrder.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["management_review", "assignee", "spawned_capa", "spawned_change_order"],
        )
        return cleaned_data


class ManagementReviewActionCompleteForm(forms.Form):
    resolution_summary = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Provide objective evidence and implementation narrative..."}),
        label="Implementation Resolution Summary",
    )


class ManagementReviewActionVerifyForm(forms.Form):
    verification_notes = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Independent verification evidence confirming action was effective..."}),
        label="QA Verification & Effectiveness Evidence",
    )
