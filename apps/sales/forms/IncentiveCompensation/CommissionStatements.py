"""Sales 8.10 — Forms for `CommissionStatement`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.IncentiveCompensation.CommissionPlans import CommissionPlan
from apps.sales.models.IncentiveCompensation.CommissionStatements import CommissionStatement


class CommissionStatementForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CommissionStatement
        fields = [
            "statement_number",
            "payee",
            "plan",
            "period_start",
            "period_end",
            "draw_advance_paid",
            "notes",
        ]
        widgets = {
            "statement_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. STMT-2026-M10-REP"}),
            "payee": forms.Select(attrs={"class": "form-select"}),
            "plan": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "draw_advance_paid": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["payee"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["plan"].queryset = CommissionPlan.objects.filter(tenant=self.tenant, status="active")
        else:
            self.fields["payee"].queryset = User.objects.none()
            self.fields["plan"].queryset = CommissionPlan.objects.none()

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["payee", "plan"])
        return cleaned
