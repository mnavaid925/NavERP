"""HRM 3.15 Statutory Compliance — Statutoryconfig forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    StatutoryConfig,
)


# ----------------------------------------------------------------------- 3.15 Statutory Compliance
class StatutoryConfigForm(TenantModelForm):
    # tenant is set via StatutoryConfig.for_tenant() (one row per tenant) — never a form field.
    class Meta:
        model = StatutoryConfig
        fields = ["pf_establishment_code", "pf_wage_ceiling", "pf_employee_rate", "pf_employer_rate",
                  "esi_employer_code", "esi_wage_ceiling", "esi_employee_rate", "esi_employer_rate",
                  "pt_default_state", "tan_number", "tds_circle_address", "pan_of_deductor",
                  "is_lwf_applicable"]
        widgets = {
            "tds_circle_address": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }
