"""Accounting 2.2 General Ledger — ExchangeRates forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    ExchangeRate,
)


class ExchangeRateForm(TenantModelForm):
    class Meta:
        model = ExchangeRate
        fields = ["currency", "rate_date", "rate", "source"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
