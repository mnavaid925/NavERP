"""CRM 1.1 Core Data Management — Contacts forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    ContactProfile,
)


class ContactForm(TenantModelForm):
    name = forms.CharField(max_length=255, label="Contact name")
    linkedin = forms.URLField(required=False, assume_scheme="https")

    field_order = ["name", "job_title", "department", "email", "phone", "mobile", "account",
                   "address_line", "address_city", "address_state", "address_postal",
                   "address_country", "linkedin", "source", "owner", "description"]

    class Meta:
        model = ContactProfile
        fields = ["job_title", "department", "email", "phone", "mobile", "account",
                  "address_line", "address_city", "address_state", "address_postal",
                  "address_country", "linkedin", "source", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["account"].queryset = Party.objects.filter(
                tenant=self.tenant, kind="organization").order_by("name")
