"""CRM 1.1 Core Data Management — Accounts forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    AccountProfile,
)


# Accounts & Contacts span two tables: the shared core.Party identity (name/tax_id) + the CRM
# profile. These forms are ModelForms on the *profile* with the Party fields declared inline; the
# view creates/updates the Party and links the profile.
class AccountForm(TenantModelForm):
    name = forms.CharField(max_length=255, label="Account name")
    tax_id = forms.CharField(max_length=64, required=False, label="Tax ID")
    # Explicit form field with the permanent assume_scheme API (avoids the Django 6.0 URLField
    # default-scheme deprecation warning).
    website = forms.URLField(required=False, assume_scheme="https")

    field_order = ["name", "tax_id", "industry", "website", "phone", "email", "annual_revenue",
                   "employee_count", "parent_account", "address_line", "address_city",
                   "address_state", "address_postal", "address_country", "source", "owner",
                   "description"]

    class Meta:
        model = AccountProfile
        fields = ["industry", "website", "phone", "email", "annual_revenue", "employee_count",
                  "parent_account", "address_line", "address_city", "address_state",
                  "address_postal", "address_country", "source", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            qs = Party.objects.filter(tenant=self.tenant, kind="organization")
            if self.instance and self.instance.party_id:
                qs = qs.exclude(pk=self.instance.party_id)  # an account can't be its own parent
            self.fields["parent_account"].queryset = qs.order_by("name")
