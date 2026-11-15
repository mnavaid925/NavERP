from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder

User = get_user_model()


class DocumentChangeOrderForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentChangeOrder
        fields = [
            "title",
            "change_type",
            "priority",
            "document",
            "target_revision",
            "reason_for_change",
            "change_description",
            "regulatory_impact",
            "training_required",
            "impact_assessment",
            "target_effective_date",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Short title for this Change Request..."}),
            "change_type": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "document": forms.Select(attrs={"class": "form-select"}),
            "target_revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2.0"}),
            "reason_for_change": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Operational, quality or audit justification..."}),
            "change_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Specific additions, removals, and modifications..."}),
            "regulatory_impact": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "training_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "impact_assessment": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Scope of equipment, processes, or validation affected..."}),
            "target_effective_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["document"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant, is_latest_revision=True
            )
        else:
            self.fields["document"].queryset = ControlledDocument.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document"])
        return cleaned_data
