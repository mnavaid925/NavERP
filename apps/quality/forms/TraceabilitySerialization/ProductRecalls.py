from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.TraceabilitySerialization.ProductRecalls import ProductRecall

User = get_user_model()


class ProductRecallForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProductRecall
        fields = [
            "title",
            "recall_class",
            "status",
            "is_mock_recall",
            "mock_drill_hours",
            "item_code",
            "item_name",
            "affected_lot_numbers",
            "affected_serial_range",
            "hazard_summary",
            "root_cause",
            "customer_complaint",
            "capa_investigation",
            "total_distributed_qty",
            "total_quarantined_qty",
            "total_recovered_qty",
            "total_destroyed_qty",
            "regulatory_agency_notified",
            "regulatory_notification_date",
            "coordinator",
            "closure_approved_by",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "recall_class": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_mock_recall": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "mock_drill_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.1"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "affected_lot_numbers": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "affected_serial_range": forms.TextInput(attrs={"class": "form-input"}),
            "hazard_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "root_cause": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "customer_complaint": forms.Select(attrs={"class": "form-select"}),
            "capa_investigation": forms.Select(attrs={"class": "form-select"}),
            "total_distributed_qty": forms.NumberInput(attrs={"class": "form-input"}),
            "total_quarantined_qty": forms.NumberInput(attrs={"class": "form-input"}),
            "total_recovered_qty": forms.NumberInput(attrs={"class": "form-input"}),
            "total_destroyed_qty": forms.NumberInput(attrs={"class": "form-input"}),
            "regulatory_agency_notified": forms.TextInput(attrs={"class": "form-input"}),
            "regulatory_notification_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "coordinator": forms.Select(attrs={"class": "form-select"}),
            "closure_approved_by": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["coordinator"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["closure_approved_by"].queryset = User.objects.filter(tenant=self.tenant)

            CustomerComplaint = apps.get_model("quality", "CustomerComplaint")
            self.fields["customer_complaint"].queryset = CustomerComplaint.objects.filter(tenant=self.tenant)

            CapaInvestigation = apps.get_model("quality", "CapaInvestigation")
            self.fields["capa_investigation"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "coordinator",
                "closure_approved_by",
                "customer_complaint",
                "capa_investigation",
            ],
        )
        return cleaned_data
