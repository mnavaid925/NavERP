"""HRM 3.13 Salary Structure — Paycomponent forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PayComponent,
)


# ----------------------------------------------------------------------- 3.13 Salary Structure
class PayComponentForm(TenantModelForm):
    class Meta:
        model = PayComponent
        fields = ["name", "code", "component_type", "variable_subtype", "calculation_type",
                  "default_amount", "default_percentage", "frequency", "is_taxable", "include_in_ctc",
                  "contribution_side", "annual_cap_amount", "requires_bill", "is_active",
                  "display_order", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }
