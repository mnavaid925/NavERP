"""Tests for HRM 3.17 Payout & Reports models: PayoutBatch (numbering/is_editable/clean/derived
_totals()), PayoutPayment (masked bank snapshot/retry_of), PayslipDistribution (for_payslip()
idempotency), BankReconciliation (recompute() matching + status derivation)."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ PayoutBatch
class TestPayoutBatchModel:
    def test_number_auto_assigns_pob_prefix(self, tenant_a, locked_cycle_a):
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch.objects.create(tenant=tenant_a, cycle=locked_cycle_a)
        assert batch.number.startswith("POB-")

    def test_default_status_is_draft(self, payout_batch_a):
        assert payout_batch_a.status == "draft"

    def test_is_editable_true_when_draft(self, payout_batch_a):
        assert payout_batch_a.is_editable is True

    def test_is_editable_false_when_approved(self, payout_batch_a):
        payout_batch_a.status = "approved"
        assert payout_batch_a.is_editable is False

    def test_clean_rejects_non_locked_cycle(self, tenant_a, draft_cycle_a):
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch(tenant=tenant_a, cycle=draft_cycle_a)
        with pytest.raises(ValidationError):
            batch.clean()

    def test_clean_accepts_locked_cycle(self, tenant_a, locked_cycle_a):
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch(tenant=tenant_a, cycle=locked_cycle_a)
        batch.clean()  # must not raise

    def test_unique_together_tenant_cycle(self, tenant_a, locked_cycle_a):
        from apps.hrm.models import PayoutBatch
        PayoutBatch.objects.create(tenant=tenant_a, cycle=locked_cycle_a)
        with pytest.raises(IntegrityError):
            PayoutBatch.objects.create(tenant=tenant_a, cycle=locked_cycle_a)

    def test_str_contains_number_and_cycle(self, payout_batch_a):
        s = str(payout_batch_a)
        assert payout_batch_a.number in s
        assert payout_batch_a.cycle.number in s

    def test_source_account_last4_accepts_masked(self, tenant_a, locked_cycle_a):
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch(tenant=tenant_a, cycle=locked_cycle_a, source_account_last4="••••4321")
        batch.full_clean()  # must not raise

    def test_source_account_last4_accepts_plain_4_digits(self, tenant_a, locked_cycle_a):
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch(tenant=tenant_a, cycle=locked_cycle_a, source_account_last4="4321")
        batch.full_clean()  # must not raise

    def test_source_account_last4_accepts_blank(self, tenant_a, locked_cycle_a):
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch(tenant=tenant_a, cycle=locked_cycle_a, source_account_last4="")
        batch.full_clean()  # must not raise

    def test_source_account_last4_rejects_full_account_number(self, tenant_a, locked_cycle_a):
        """SECURITY (security-reviewer-requested): a full account number must never be accepted
        into source_account_last4 — the RegexValidator caps it at 4 raw digits (optionally
        masked-prefixed)."""
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch(tenant=tenant_a, cycle=locked_cycle_a, source_account_last4="1234567890")
        with pytest.raises(ValidationError):
            batch.full_clean()


class TestPayoutBatchTotals:
    def test_totals_zero_when_no_payments(self, payout_batch_a):
        assert payout_batch_a.headcount == 0
        assert payout_batch_a.total_amount == Decimal("0")
        assert payout_batch_a.paid_count == 0
        assert payout_batch_a.paid_amount == Decimal("0")
        assert payout_batch_a.failed_count == 0
        assert payout_batch_a.on_hold_count == 0

    def test_totals_reflect_current_payments(self, generated_batch_a):
        batch = generated_batch_a
        assert batch.headcount == 2
        expected_total = sum((p.net_amount for p in batch.payments.all()), Decimal("0"))
        assert batch.total_amount == expected_total

    def test_totals_on_hold_snapshot(self, locked_cycle_with_hold_a, tenant_a, admin_user):
        from django.utils import timezone as tz
        from apps.hrm.models import PayoutBatch, PayoutPayment
        batch = PayoutBatch.objects.create(tenant=tenant_a, cycle=locked_cycle_with_hold_a)
        for ps in batch.cycle.payslips.select_related("employee").all():
            emp = ps.employee
            PayoutPayment.objects.create(
                tenant=tenant_a, batch=batch, payslip=ps, employee=emp,
                net_amount=ps.net_pay, bank_name_snapshot=emp.bank_name,
                bank_account_last4_snapshot=emp.masked_bank_account(),
                bank_routing_snapshot=emp.masked_bank_routing(),
                status="on_hold" if ps.on_hold else "pending",
            )
        assert batch.on_hold_count == 1
        assert batch.headcount == 2

    def test_totals_cached_per_instance(self, generated_batch_a):
        """_totals() memoizes into _totals_cache — calling it twice must not re-query (same dict id)."""
        batch = generated_batch_a
        first = batch._totals()
        second = batch._totals()
        assert first is second


# ================================================================ PayoutPayment
class TestPayoutPaymentModel:
    def test_default_status_pending(self, generated_batch_a):
        payment = generated_batch_a.payments.filter(status="pending").first()
        assert payment is not None

    def test_bank_snapshot_is_masked_not_raw(self, generated_batch_a, employee_a):
        """The snapshot must be the MASKED value, never the raw bank_account/bank_routing."""
        payment = generated_batch_a.payments.get(employee=employee_a)
        assert payment.bank_account_last4_snapshot == employee_a.masked_bank_account()
        assert payment.bank_account_last4_snapshot != employee_a.bank_account
        assert "9012" in payment.bank_account_last4_snapshot  # last 4 of 123456789012
        assert employee_a.bank_account not in payment.bank_account_last4_snapshot

    def test_net_amount_snapshots_payslip_net_pay(self, generated_batch_a, employee_a):
        payment = generated_batch_a.payments.get(employee=employee_a)
        ps = payment.payslip
        assert payment.net_amount == ps.net_pay

    def test_on_hold_payslip_yields_on_hold_payment(self, tenant_a, locked_cycle_with_hold_a):
        from apps.hrm.models import PayoutBatch, PayoutPayment
        batch = PayoutBatch.objects.create(tenant=tenant_a, cycle=locked_cycle_with_hold_a)
        held_ps = locked_cycle_with_hold_a.payslips.filter(on_hold=True).first()
        emp = held_ps.employee
        payment = PayoutPayment.objects.create(
            tenant=tenant_a, batch=batch, payslip=held_ps, employee=emp,
            net_amount=held_ps.net_pay, bank_name_snapshot=emp.bank_name,
            bank_account_last4_snapshot=emp.masked_bank_account(),
            bank_routing_snapshot=emp.masked_bank_routing(), status="on_hold",
        )
        assert payment.status == "on_hold"

    def test_str_contains_employee_and_status(self, generated_batch_a, employee_a):
        payment = generated_batch_a.payments.get(employee=employee_a)
        s = str(payment)
        assert "Pending" in s

    def test_no_unique_together_batch_payslip_allows_retry_row(self, generated_batch_a, employee_a):
        """A retry creates a SECOND row for the same (batch, payslip) — must not raise IntegrityError
        (there is deliberately no unique_together on (batch, payslip))."""
        from apps.hrm.models import PayoutPayment
        original = generated_batch_a.payments.get(employee=employee_a)
        original.status = "failed"
        original.save(update_fields=["status"])
        retry = PayoutPayment.objects.create(
            tenant=original.tenant, batch=original.batch, payslip=original.payslip,
            employee=original.employee, net_amount=original.net_amount,
            bank_name_snapshot=original.bank_name_snapshot,
            bank_account_last4_snapshot=original.bank_account_last4_snapshot,
            bank_routing_snapshot=original.bank_routing_snapshot,
            status="pending", retry_of=original,
        )
        assert retry.retry_of_id == original.pk
        assert PayoutPayment.objects.filter(batch=original.batch, payslip=original.payslip).count() == 2


# ================================================================ Retry / supersede invariant
class TestCurrentPaymentsRetryInvariant:
    def test_current_payments_excludes_superseded_original(self, generated_batch_a, employee_a):
        """_current_payments() must exclude a failed row once it has been retried (retries__isnull=True
        drops the original) so the retry is the only 'current' row for that employee."""
        from apps.hrm.models import PayoutPayment
        batch = generated_batch_a
        original = batch.payments.get(employee=employee_a)
        original.status = "failed"
        original.save(update_fields=["status"])
        retry = PayoutPayment.objects.create(
            tenant=original.tenant, batch=batch, payslip=original.payslip, employee=employee_a,
            net_amount=original.net_amount, bank_name_snapshot=original.bank_name_snapshot,
            bank_account_last4_snapshot=original.bank_account_last4_snapshot,
            bank_routing_snapshot=original.bank_routing_snapshot,
            status="pending", retry_of=original,
        )
        current_pks = set(batch._current_payments().values_list("pk", flat=True))
        assert original.pk not in current_pks
        assert retry.pk in current_pks

    def test_retried_employee_not_double_counted_in_headcount(self, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        batch = generated_batch_a
        original_headcount = batch.headcount
        original = batch.payments.get(employee=employee_a)
        original.status = "failed"
        original.save(update_fields=["status"])
        PayoutPayment.objects.create(
            tenant=original.tenant, batch=batch, payslip=original.payslip, employee=employee_a,
            net_amount=original.net_amount, bank_name_snapshot=original.bank_name_snapshot,
            bank_account_last4_snapshot=original.bank_account_last4_snapshot,
            bank_routing_snapshot=original.bank_routing_snapshot,
            status="pending", retry_of=original,
        )
        # refresh cached totals on a fresh instance
        from apps.hrm.models import PayoutBatch
        fresh = PayoutBatch.objects.get(pk=batch.pk)
        assert fresh.headcount == original_headcount  # still 2, not 3

    def test_retried_employee_not_double_counted_in_total_amount(self, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutBatch, PayoutPayment
        batch = generated_batch_a
        original_total = batch.total_amount
        original = batch.payments.get(employee=employee_a)
        original.status = "failed"
        original.save(update_fields=["status"])
        PayoutPayment.objects.create(
            tenant=original.tenant, batch=batch, payslip=original.payslip, employee=employee_a,
            net_amount=original.net_amount, bank_name_snapshot=original.bank_name_snapshot,
            bank_account_last4_snapshot=original.bank_account_last4_snapshot,
            bank_routing_snapshot=original.bank_routing_snapshot,
            status="paid", retry_of=original,
        )
        fresh = PayoutBatch.objects.get(pk=batch.pk)
        assert fresh.total_amount == original_total  # unchanged — same employee, not additive

    def test_failed_count_drops_when_only_failure_is_superseded(self, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutBatch, PayoutPayment
        batch = generated_batch_a
        original = batch.payments.get(employee=employee_a)
        original.status = "failed"
        original.save(update_fields=["status"])
        fresh = PayoutBatch.objects.get(pk=batch.pk)
        assert fresh.failed_count == 1
        PayoutPayment.objects.create(
            tenant=original.tenant, batch=batch, payslip=original.payslip, employee=employee_a,
            net_amount=original.net_amount, bank_name_snapshot=original.bank_name_snapshot,
            bank_account_last4_snapshot=original.bank_account_last4_snapshot,
            bank_routing_snapshot=original.bank_routing_snapshot,
            status="pending", retry_of=original,
        )
        fresh2 = PayoutBatch.objects.get(pk=batch.pk)
        assert fresh2.failed_count == 0


# ================================================================ PayslipDistribution
class TestPayslipDistributionModel:
    def test_for_payslip_creates_row(self, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        assert dist.payslip_id == payslip_a.pk
        assert dist.status == "pending"
        assert dist.delivery_channel == "portal"

    def test_for_payslip_idempotent(self, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist1 = PayslipDistribution.for_payslip(payslip_a)
        dist1.status = "sent"
        dist1.save(update_fields=["status"])
        dist2 = PayslipDistribution.for_payslip(payslip_a)
        assert dist1.pk == dist2.pk
        assert dist2.status == "sent"  # not reset back to pending
        assert PayslipDistribution.objects.filter(payslip=payslip_a).count() == 1

    def test_one_to_one_with_payslip(self, payslip_a):
        from apps.hrm.models import PayslipDistribution
        PayslipDistribution.objects.create(tenant=payslip_a.tenant, payslip=payslip_a)
        with pytest.raises(IntegrityError):
            PayslipDistribution.objects.create(tenant=payslip_a.tenant, payslip=payslip_a)

    def test_str_contains_status(self, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        assert "Pending" in str(dist)


# ================================================================ BankReconciliation
class TestBankReconciliationModel:
    def test_number_auto_assigns_brc_prefix(self, tenant_a, payout_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=payout_batch_a, statement_date=datetime.date(2026, 7, 2))
        assert recon.number.startswith("BRC-")

    def test_default_status_pending(self, tenant_a, payout_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=payout_batch_a, statement_date=datetime.date(2026, 7, 2))
        assert recon.status == "pending"

    def test_str_contains_number_and_batch(self, tenant_a, payout_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=payout_batch_a, statement_date=datetime.date(2026, 7, 2))
        s = str(recon)
        assert recon.number in s
        assert payout_batch_a.number in s


class TestBankReconciliationRecompute:
    """recompute() (code-reviewer-requested): matched = current PAID rows with a non-blank
    transaction_reference; unmatched = everything else; status reconciled iff unmatched==0."""

    def _disbursed_batch_with_payments(self, tenant_a, generated_batch_a):
        from apps.hrm.models import PayoutBatch
        batch = generated_batch_a
        batch.status = "disbursed"
        batch.save(update_fields=["status"])
        return PayoutBatch.objects.get(pk=batch.pk)

    def test_recompute_all_paid_with_utr_is_reconciled(self, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation
        batch = self._disbursed_batch_with_payments(tenant_a, generated_batch_a)
        for p in batch.payments.all():
            p.status = "paid"
            p.transaction_reference = f"UTR{p.pk}"
            p.save(update_fields=["status", "transaction_reference"])
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=batch, statement_date=datetime.date(2026, 7, 2))
        recon.recompute()
        assert recon.status == "reconciled"
        assert recon.unmatched_count == 0
        assert recon.matched_count == batch.payments.count()
        assert recon.matched_amount == sum((p.net_amount for p in batch.payments.all()), Decimal("0"))

    def test_recompute_paid_without_utr_is_unmatched(self, tenant_a, generated_batch_a):
        """A paid row with a BLANK transaction_reference is unmatched, not matched — UTR is the
        match key, not just status=paid."""
        from apps.hrm.models import BankReconciliation
        batch = self._disbursed_batch_with_payments(tenant_a, generated_batch_a)
        for p in batch.payments.all():
            p.status = "paid"
            p.transaction_reference = ""
            p.save(update_fields=["status", "transaction_reference"])
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=batch, statement_date=datetime.date(2026, 7, 2))
        recon.recompute()
        assert recon.matched_count == 0
        assert recon.unmatched_count == batch.payments.count()
        assert recon.status == "discrepancy"

    def test_recompute_failed_payment_is_unmatched_and_discrepancy(self, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation
        batch = self._disbursed_batch_with_payments(tenant_a, generated_batch_a)
        payments = list(batch.payments.all())
        payments[0].status = "paid"
        payments[0].transaction_reference = "UTR1"
        payments[0].save(update_fields=["status", "transaction_reference"])
        payments[1].status = "failed"
        payments[1].save(update_fields=["status"])
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=batch, statement_date=datetime.date(2026, 7, 2))
        recon.recompute()
        assert recon.matched_count == 1
        assert recon.unmatched_count == 1
        assert recon.status == "discrepancy"

    def test_recompute_excludes_superseded_originals(self, tenant_a, generated_batch_a, employee_a):
        """A superseded (retried) original must not be double-reflected in matched/unmatched — only
        the current (retry) row counts, mirroring batch._current_payments()."""
        from apps.hrm.models import BankReconciliation, PayoutPayment
        batch = self._disbursed_batch_with_payments(tenant_a, generated_batch_a)
        original = batch.payments.get(employee=employee_a)
        original.status = "failed"
        original.save(update_fields=["status"])
        retry = PayoutPayment.objects.create(
            tenant=original.tenant, batch=batch, payslip=original.payslip, employee=employee_a,
            net_amount=original.net_amount, bank_name_snapshot=original.bank_name_snapshot,
            bank_account_last4_snapshot=original.bank_account_last4_snapshot,
            bank_routing_snapshot=original.bank_routing_snapshot,
            status="paid", transaction_reference="UTR-RETRY", retry_of=original,
        )
        other = batch.payments.exclude(pk__in=[original.pk, retry.pk]).first()
        other.status = "paid"
        other.transaction_reference = "UTR-OTHER"
        other.save(update_fields=["status", "transaction_reference"])
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=batch, statement_date=datetime.date(2026, 7, 2))
        recon.recompute()
        # Only 2 CURRENT payments exist (original superseded) — both matched.
        assert recon.matched_count == 2
        assert recon.unmatched_count == 0
        assert recon.status == "reconciled"

    def test_recompute_sets_reconciled_at(self, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation
        batch = self._disbursed_batch_with_payments(tenant_a, generated_batch_a)
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=batch, statement_date=datetime.date(2026, 7, 2))
        assert recon.reconciled_at is None
        recon.recompute()
        assert recon.reconciled_at is not None
