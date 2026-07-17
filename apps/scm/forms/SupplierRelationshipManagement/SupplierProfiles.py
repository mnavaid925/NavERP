"""SCM 4.2 SRM — SupplierProfile form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _supplier_parties
from apps.scm.models import SupplierProfile


class SupplierProfileForm(TenantModelForm):
    class Meta:
        model = SupplierProfile
        # `onboarding_status` EXCLUDED — advances via the approve/reject/suspend actions.
        # `approved_by/at`, `decision_note` are system-set. `party` is scoped to supplier Parties.
        fields = [
            "party", "tier", "category", "legal_name", "tax_registration", "website",
            "primary_contact_name", "primary_contact_email", "primary_contact_phone", "country",
            "year_established",
            "dd_financials_verified", "dd_compliance_verified", "dd_insurance_verified",
            "dd_quality_cert_verified", "dd_references_checked", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)
