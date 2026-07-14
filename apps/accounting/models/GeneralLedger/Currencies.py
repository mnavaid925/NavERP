"""Accounting 2.2 General Ledger — Currencies models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# =========================================================== 2.2 General Ledger
class Currency(models.Model):
    """ISO 4217 currency master. **Global** — shared across all tenants (no tenant FK), exactly
    as the intended ERD treats currencies as a shared reference master."""

    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=60)
    symbol = models.CharField(max_length=8, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "currencies"

    def __str__(self):
        return self.code
