"""Accounting 2.14 Audit & Controls — InternalControls forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    InternalControl,
)


class InternalControlForm(TenantModelForm):
    class Meta:
        model = InternalControl
        fields = ["code", "name", "control_type", "frequency", "risk_level", "owner",
                  "last_tested_date", "last_result", "status", "description"]
