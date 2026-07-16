"""HRM 3.16 Tax & Investment — Taxregimeconfig forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TaxRegimeConfig,
)


# ----------------------------------------------------------------------- 3.16 Tax & Investment
class TaxRegimeConfigForm(TenantModelForm):
    class Meta:
        model = TaxRegimeConfig
        fields = ["financial_year", "regime", "standard_deduction", "cess_rate",
                  "rebate_income_threshold", "rebate_max_tax", "is_default_regime", "tax_law_reference"]
