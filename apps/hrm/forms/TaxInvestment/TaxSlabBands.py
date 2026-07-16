"""HRM 3.16 Tax & Investment — TaxSlabBands forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TaxSlabBand,
)


class TaxSlabBandForm(TenantModelForm):
    # config is set from the parent config in the inline-management view, never a free-choice dropdown.
    class Meta:
        model = TaxSlabBand
        fields = ["income_from", "income_to", "rate_percent", "sequence"]
