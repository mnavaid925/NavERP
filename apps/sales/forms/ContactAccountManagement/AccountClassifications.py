from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import Party
from apps.sales.forms._common import TenantModelForm, _reject_foreign
from apps.sales.models.ContactAccountManagement.AccountClassifications import AccountClassification


class AccountClassificationForm(TenantModelForm):
    class Meta:
        model = AccountClassification
        fields = [
            "account", "tier", "lifecycle_stage", "strategic_priority",
            "revenue_potential", "wallet_category", "rationale", "effective_on", "review_due_on",
        ]
        widgets = {
            "rationale": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is None:
            self.fields["account"].queryset = Party.objects.none()
        else:
            account_ids = list(Party.objects.filter(
                tenant=tenant, kind="organization"
            ).order_by("name").values_list("pk", flat=True)[:500])
            self.fields["account"].queryset = Party.objects.filter(pk__in=account_ids)
        if self.instance.pk:
            self.fields["account"].disabled = True

    def validate_unique(self):
        if self.instance.pk:
            return super().validate_unique()
        exclude = set(self._get_validation_exclusions())
        exclude.update({"tenant", "account"})
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as exc:
            self._update_errors(exc)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["account"])
        account = cleaned.get("account")
        if account is not None and account.kind != "organization":
            self.add_error("account", "Choose a same-tenant organization account.")
        if cleaned.get("tier") in {"strategic", "key"} and not cleaned.get("review_due_on"):
            self.add_error("review_due_on", "Strategic and key accounts require a review date.")
        effective_on = cleaned.get("effective_on")
        review_due_on = cleaned.get("review_due_on")
        if effective_on and review_due_on and review_due_on < effective_on:
            self.add_error("review_due_on", "The review date cannot precede the effective date.")
        if not (cleaned.get("rationale") or "").strip():
            self.add_error("rationale", "A rationale is required for every classification.")
        return cleaned
