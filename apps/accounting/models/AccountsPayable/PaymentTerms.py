"""Accounting 2.3 Accounts Payable — PaymentTerms models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ======================================== 2.3 AP + 2.4 AR shared masters
class PaymentTerm(TenantOwned):
    """Reusable Net-N / early-discount term (e.g. "2/10 Net 30")."""

    name = models.CharField(max_length=80)
    days_due = models.PositiveSmallIntegerField(default=30)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_days = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
