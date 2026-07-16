"""HRM 3.16 Tax & Investment — Taxcomputation forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    InvestmentDeclaration,
    TaxComputation,
)


class TaxComputationForm(TenantModelForm):
    # number + all derived (tax_payable/tax_paid_ytd/monthly_tds_amount) + statutory_return/computed_at
    # are set by recompute()/link_form16(), never form-typed.
    class Meta:
        model = TaxComputation
        fields = ["employee", "declaration", "computation_type", "manual_override_amount",
                  "override_reason", "remaining_pay_periods", "notes"]
        widgets = {
            "override_reason": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "declaration" in self.fields:
                self.fields["declaration"].queryset = (
                    InvestmentDeclaration.objects.filter(tenant=self.tenant)
                    .select_related("employee__party").order_by("-financial_year"))

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get("employee")
        declaration = cleaned.get("declaration")
        if employee and declaration:
            # The employee must own the chosen declaration (the engine mixes self.employee for TDS/salary
            # with self.declaration for the deduction lines — a mismatch would compute the wrong person).
            if declaration.employee_id != employee.pk:
                raise forms.ValidationError("The selected employee must match the declaration's employee.")
            # Denormalize financial_year FROM the declaration (the field is excluded from the form) — a
            # blank FY would silently compute zero tax (no matching TaxRegimeConfig).
            self.instance.financial_year = declaration.financial_year
            # One computation per (tenant, employee, FY) — enforced here since the excluded tenant/FY
            # fields keep ModelForm.validate_unique() from catching it (else it would 500 at the DB).
            if self.tenant is not None:
                dup = TaxComputation.objects.filter(
                    tenant=self.tenant, employee=employee, financial_year=declaration.financial_year)
                if self.instance.pk:
                    dup = dup.exclude(pk=self.instance.pk)
                if dup.exists():
                    raise forms.ValidationError(
                        "A tax computation for this employee and financial year already exists.")
        return cleaned
