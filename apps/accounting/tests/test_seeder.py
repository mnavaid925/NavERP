"""Seeder idempotency test for seed_accounting management command.

Covers:
- Running seed_accounting twice leaves row counts unchanged.
- After seeding, the per-tenant posted GL ledger is balanced (Σdebit == Σcredit).
"""
from decimal import Decimal

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


class TestSeedAccountingIdempotency:
    def _seed(self):
        """Run the seed command, suppressing output."""
        import io
        from django.core.management import call_command
        call_command("seed_accounting", stdout=io.StringIO(), stderr=io.StringIO())

    def test_double_seed_leaves_counts_unchanged(self, tenant_a, admin_user):
        """Running seed_accounting twice must not duplicate rows."""
        from apps.accounting.models import GLAccount, FiscalPeriod, JournalEntry

        self._seed()
        gl_count_1 = GLAccount.objects.filter(tenant=tenant_a).count()
        period_count_1 = FiscalPeriod.objects.filter(tenant=tenant_a).count()
        je_count_1 = JournalEntry.objects.filter(tenant=tenant_a).count()

        self._seed()
        gl_count_2 = GLAccount.objects.filter(tenant=tenant_a).count()
        period_count_2 = FiscalPeriod.objects.filter(tenant=tenant_a).count()
        je_count_2 = JournalEntry.objects.filter(tenant=tenant_a).count()

        assert gl_count_1 == gl_count_2, "GLAccount count changed on second seed"
        assert period_count_1 == period_count_2, "FiscalPeriod count changed on second seed"
        assert je_count_1 == je_count_2, "JournalEntry count changed on second seed"

    def test_seeded_ledger_is_balanced(self, tenant_a, admin_user):
        """After seeding, Σdebit == Σcredit over all posted journal lines for the tenant."""
        from django.db.models import Sum
        from apps.accounting.models import JournalLine

        self._seed()

        agg = JournalLine.objects.filter(
            entry__tenant=tenant_a,
            entry__status="posted",
        ).aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))

        total_debit = agg["total_debit"] or Decimal("0")
        total_credit = agg["total_credit"] or Decimal("0")

        assert total_debit == total_credit, (
            f"Ledger not balanced after seed: debit={total_debit}, credit={total_credit}"
        )
