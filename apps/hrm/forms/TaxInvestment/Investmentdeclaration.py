"""HRM 3.16 Tax & Investment — Investmentdeclaration forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    InvestmentDeclaration,
    InvestmentDeclarationLine,
)


class InvestmentDeclarationForm(TenantModelForm):
    # number / status / submitted_at are workflow-owned (submit/lock actions), never form fields.
    class Meta:
        model = InvestmentDeclaration
        fields = ["employee", "financial_year", "regime_elected", "declaration_window_open",
                  "declaration_window_close", "proof_window_open", "proof_window_close",
                  "previous_employer_income", "previous_employer_tds", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "employee" in self.fields:
            self.fields["employee"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))


class InvestmentDeclarationLineForm(TenantModelForm):
    # declaration is set from the parent in the inline view; verified_amount is proof-derived.
    class Meta:
        model = InvestmentDeclarationLine
        fields = ["section_code", "declared_amount", "monthly_rent_amount", "is_metro_city",
                  "landlord_pan", "lender_name", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }
