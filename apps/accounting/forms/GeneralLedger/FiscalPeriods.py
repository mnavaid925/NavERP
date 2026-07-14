"""Accounting 2.2 General Ledger — FiscalPeriods forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    FiscalPeriod,
)


class FiscalPeriodForm(TenantModelForm):
    class Meta:
        model = FiscalPeriod
        # `status` is intentionally EXCLUDED — a period is opened on create (model default) and
        # only ever transitions to closed via the @tenant_admin_required `fiscal_period_close`
        # action. Leaving it on this @login_required edit form would let any member close/lock a
        # period and bypass the admin gate (code-review finding).
        fields = ["name", "period_type", "start_date", "end_date"]
