"""Sales 8.10 — Forms for `CommissionAdjustment`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.IncentiveCompensation.CommissionAdjustments import CommissionAdjustment
from apps.sales.models.IncentiveCompensation.CommissionEarnings import CommissionEarning
from apps.sales.models.IncentiveCompensation.CommissionStatements import CommissionStatement


class CommissionAdjustmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CommissionAdjustment
        fields = [
            "statement",
            "earning",
            "payee",
            "adjustment_type",
            "amount",
            "reason",
            "effective_date",
        ]
        widgets = {
            "statement": forms.Select(attrs={"class": "form-select"}),
            "earning": forms.Select(attrs={"class": "form-select"}),
            "payee": forms.Select(attrs={"class": "form-select"}),
            "adjustment_type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Negative for clawbacks, positive for credits"}),
            "reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["statement"].queryset = CommissionStatement.objects.filter(
                tenant=self.tenant, status__in=["draft", "under_review"]
            )
            self.fields["earning"].queryset = CommissionEarning.objects.filter(tenant=self.tenant)
            self.fields["payee"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
        else:
            self.fields["statement"].queryset = CommissionStatement.objects.none()
            self.fields["earning"].queryset = CommissionEarning.objects.none()
            self.fields["payee"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["statement", "earning", "payee"])
        return cleaned


class CommissionDisputeTicketForm(forms.Form):
    earning_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    disputed_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        label="Disputed Amount",
    )
    dispute_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Explain the discrepancy in attainment, deal split, or rate calculation..."}),
        label="Dispute Justification",
    )
