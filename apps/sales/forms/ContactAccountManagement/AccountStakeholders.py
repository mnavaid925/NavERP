from django import forms

from apps.core.models import Party
from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.sales.models.ContactAccountManagement.AccountStakeholders import AccountStakeholder


class AccountStakeholderForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AccountStakeholder
        fields = [
            "account", "contact", "role", "influence", "attitude",
            "relationship_strength", "status", "valid_from", "valid_to", "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is None:
            self.fields["account"].queryset = Party.objects.none()
            self.fields["contact"].queryset = Party.objects.none()
        else:
            account_ids = list(Party.objects.filter(
                tenant=tenant, kind="organization"
            ).order_by("name").values_list("pk", flat=True)[:500])
            contact_ids = list(Party.objects.filter(
                tenant=tenant, kind="person"
            ).order_by("name").values_list("pk", flat=True)[:500])
            self.fields["account"].queryset = Party.objects.filter(pk__in=account_ids)
            self.fields["contact"].queryset = Party.objects.filter(pk__in=contact_ids)
        if self.instance.pk:
            self.fields["account"].disabled = True
            self.fields["contact"].disabled = True

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["account", "contact"])
        account = cleaned.get("account")
        contact = cleaned.get("contact")
        if account and contact and account.pk == contact.pk:
            self.add_error("contact", "An account and contact must be different Parties.")
        valid_from = cleaned.get("valid_from")
        valid_to = cleaned.get("valid_to")
        if valid_from and valid_to and valid_to < valid_from:
            self.add_error("valid_to", "The end date cannot precede the start date.")
        return cleaned
