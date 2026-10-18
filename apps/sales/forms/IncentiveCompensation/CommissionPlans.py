"""Sales 8.10 — Forms for `CommissionPlan`."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.crm.models import SalesQuota
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.IncentiveCompensation.CommissionPlans import CommissionPlan


class CommissionPlanForm(TenantUniqueMixin, TenantModelForm):
    tiers_json = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-xs", "placeholder": '[{"min_pct": 0, "max_pct": 100, "rate_pct": 8.0}, {"min_pct": 100, "max_pct": 150, "rate_pct": 15.0}]'}),
        required=False,
        label="Tier Brackets JSON",
        help_text="Format: [{\"min_pct\": 0, \"max_pct\": 100, \"rate_pct\": 8.0}, ...]",
    )
    spif_json = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs", "placeholder": '[{"name": "Q4 New Logo Push", "bonus_amount": 500.0, "criteria": "new_logo"}]'}),
        required=False,
        label="SPIF Campaigns JSON",
        help_text="Format: [{\"name\": \"Campaign\", \"bonus_amount\": 500.0, \"criteria\": \"notes\"}, ...]",
    )

    class Meta:
        model = CommissionPlan
        fields = [
            "name",
            "code",
            "description",
            "plan_type",
            "tier_mode",
            "status",
            "payout_frequency",
            "effective_start",
            "effective_end",
            "currency",
            "target_region",
            "base_rate_pct",
            "draw_amount",
            "is_draw_recoverable",
            "clawback_window_days",
            "tax_withholding_pct",
            "sales_quota",
            "owner",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Enterprise Tiered Quota 2026"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ent-quota-2026"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "plan_type": forms.Select(attrs={"class": "form-select"}),
            "tier_mode": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "payout_frequency": forms.Select(attrs={"class": "form-select"}),
            "effective_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "target_region": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Americas, Global"}),
            "base_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "draw_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "clawback_window_days": forms.NumberInput(attrs={"class": "form-input"}),
            "tax_withholding_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "sales_quota": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["sales_quota"].queryset = SalesQuota.objects.filter(tenant=self.tenant)
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
        else:
            self.fields["sales_quota"].queryset = SalesQuota.objects.none()
            self.fields["owner"].queryset = User.objects.none()
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)

        if self.instance and self.instance.pk:
            if self.instance.tiers_config:
                self.fields["tiers_json"].initial = json.dumps(self.instance.tiers_config, indent=2)
            if self.instance.spif_config:
                self.fields["spif_json"].initial = json.dumps(self.instance.spif_config, indent=2)

    def clean_tiers_json(self):
        data = self.cleaned_data.get("tiers_json", "").strip()
        if not data:
            return []
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, list):
                raise ValidationError("Tiers configuration must be a JSON array of objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON format: {exc}")

    def clean_spif_json(self):
        data = self.cleaned_data.get("spif_json", "").strip()
        if not data:
            return []
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, list):
                raise ValidationError("SPIF configuration must be a JSON array of objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON format: {exc}")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["sales_quota", "owner"])
        tiers = cleaned.get("tiers_json")
        spifs = cleaned.get("spif_json")
        if tiers is not None:
            self.instance.tiers_config = tiers
        if spifs is not None:
            self.instance.spif_config = spifs
        return cleaned

    def _post_clean(self):
        opts = self._meta
        exclude = self._get_validation_exclusions()

        for name, field in self.fields.items():
            if isinstance(field, forms.models.InlineForeignKeyField):
                exclude.append(name)

        try:
            self.instance = forms.models.construct_instance(self, self.instance, opts.fields, opts.exclude)
        except ValidationError as e:
            self._update_errors(e)

        try:
            self.instance.full_clean(exclude=exclude, validate_unique=False)
        except ValidationError as e:
            if hasattr(e, "error_dict"):
                err_dict = dict(e.error_dict)
                if "tiers_config" in err_dict:
                    err_dict["tiers_json"] = err_dict.pop("tiers_config")
                if "spif_config" in err_dict:
                    err_dict["spif_json"] = err_dict.pop("spif_config")
                e = ValidationError(err_dict)
            self._update_errors(e)

        if self._validate_unique:
            self.validate_unique()
