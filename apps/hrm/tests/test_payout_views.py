"""Tests for HRM 3.17 Payout & Reports views: PayoutBatch CRUD + generate/approve/disburse
workflow; PayoutPayment mark_paid/mark_failed/retry actions; PayslipDistribution send/send_cycle/
mark_viewed/mark_downloaded; BankReconciliation CRUD + reconcile; payment_register/payout_exceptions
reports. Bounded-query N+1 guards on list views."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ PayoutBatch CRUD
class TestPayoutBatchListView:
    def test_list_200(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payout_batch_a.pk in pks

    def test_list_filter_by_status(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payout_batch_a.pk in pks
        resp2 = client_a.get(reverse("hrm:payoutbatch_list"), {"status": "approved"})
        pks2 = [obj.pk for obj in resp2.context["object_list"]]
        assert payout_batch_a.pk not in pks2

    def test_list_search_by_number(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_list"), {"q": payout_batch_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payout_batch_a.pk in pks

    def test_list_has_status_choices_context(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_list"))
        assert "status_choices" in resp.context
        assert "bank_file_format_choices" in resp.context
        assert "cycles" in resp.context

    def test_list_annotations_match_totals(self, client_a, generated_batch_a):
        """The list-page annotations (list_headcount/list_total/list_paid) must equal the model's
        derived _totals() values — same aggregate, computed two different ways."""
        resp = client_a.get(reverse("hrm:payoutbatch_list"))
        row = next(o for o in resp.context["object_list"] if o.pk == generated_batch_a.pk)
        assert row.list_headcount == generated_batch_a.headcount
        assert row.list_total == generated_batch_a.total_amount
        assert row.list_paid == generated_batch_a.paid_count


class TestPayoutBatchCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:payoutbatch_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, locked_cycle_a):
        from apps.hrm.models import PayoutBatch
        resp = client_a.post(reverse("hrm:payoutbatch_create"), {
            "cycle": locked_cycle_a.pk, "bank_file_format": "neft",
            "source_bank_name": "HDFC", "source_account_last4": "4321", "notes": "",
        })
        assert resp.status_code == 302
        batch = PayoutBatch.objects.filter(tenant=tenant_a, cycle=locked_cycle_a).first()
        assert batch is not None
        assert batch.tenant_id == tenant_a.pk

    def test_cycle_dropdown_excludes_draft_cycle(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payoutbatch_create"))
        form = resp.context["form"]
        pks = list(form.fields["cycle"].queryset.values_list("pk", flat=True))
        assert draft_cycle_a.pk not in pks

    def test_cycle_dropdown_excludes_already_batched_cycle(self, client_a, payout_batch_a, locked_cycle_a):
        """The create dropdown must omit a cycle that already has a batch (one batch per cycle)."""
        resp = client_a.get(reverse("hrm:payoutbatch_create"))
        form = resp.context["form"]
        pks = list(form.fields["cycle"].queryset.values_list("pk", flat=True))
        assert locked_cycle_a.pk not in pks

    def test_post_duplicate_cycle_rejected_by_form_not_500(self, client_a, payout_batch_a, locked_cycle_a):
        """A second batch for an already-batched cycle must be rejected by the form (200 + errors),
        never a 500 IntegrityError — the clean() backstop (code-reviewer-requested)."""
        resp = client_a.post(reverse("hrm:payoutbatch_create"), {
            "cycle": locked_cycle_a.pk, "bank_file_format": "neft",
            "source_bank_name": "", "source_account_last4": "", "notes": "",
        })
        assert resp.status_code == 200
        assert resp.context["form"].errors
        from apps.hrm.models import PayoutBatch
        assert PayoutBatch.objects.filter(tenant=payout_batch_a.tenant, cycle=locked_cycle_a).count() == 1


class TestPayoutBatchDetailEditDelete:
    def test_detail_200(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_detail", args=[payout_batch_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_payments_and_reconciliations(self, client_a, generated_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_detail", args=[generated_batch_a.pk]))
        assert "payments" in resp.context
        assert "reconciliations" in resp.context

    def test_edit_get_200_when_draft(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_edit", args=[payout_batch_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_not_draft(self, client_a, payout_batch_a):
        payout_batch_a.status = "approved"
        payout_batch_a.save(update_fields=["status"])
        resp = client_a.get(reverse("hrm:payoutbatch_edit", args=[payout_batch_a.pk]))
        assert resp.status_code == 302
        assert reverse("hrm:payoutbatch_detail", args=[payout_batch_a.pk]) in resp["Location"]

    def test_delete_post_removes_when_draft(self, client_a, payout_batch_a):
        from apps.hrm.models import PayoutBatch
        pk = payout_batch_a.pk
        resp = client_a.post(reverse("hrm:payoutbatch_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PayoutBatch.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_not_draft(self, client_a, payout_batch_a):
        payout_batch_a.status = "approved"
        payout_batch_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:payoutbatch_delete", args=[payout_batch_a.pk]))
        from apps.hrm.models import PayoutBatch
        assert PayoutBatch.objects.filter(pk=payout_batch_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, payout_batch_a):
        resp = client_a.get(reverse("hrm:payoutbatch_delete", args=[payout_batch_a.pk]))
        assert resp.status_code == 405


# ================================================================ Batch generate workflow
class TestPayoutBatchGenerate:
    def test_generate_creates_one_payment_per_payslip(self, client_a, payout_batch_a):
        from apps.hrm.models import PayoutPayment
        resp = client_a.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        assert resp.status_code == 302
        assert PayoutPayment.objects.filter(batch=payout_batch_a).count() == \
            payout_batch_a.cycle.payslips.count()

    def test_generate_snapshots_net_pay(self, client_a, payout_batch_a, employee_a):
        client_a.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=payout_batch_a, employee=employee_a)
        ps = payment.payslip
        assert payment.net_amount == ps.net_pay

    def test_generate_snapshots_masked_bank_never_raw(self, client_a, payout_batch_a, employee_a):
        client_a.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=payout_batch_a, employee=employee_a)
        assert payment.bank_account_last4_snapshot == employee_a.masked_bank_account()
        assert employee_a.bank_account not in payment.bank_account_last4_snapshot

    def test_generate_on_hold_payslip_yields_on_hold_status(self, client_a, tenant_a, locked_cycle_with_hold_a):
        from apps.hrm.models import PayoutBatch, PayoutPayment
        batch = PayoutBatch.objects.create(tenant=tenant_a, cycle=locked_cycle_with_hold_a)
        client_a.post(reverse("hrm:payoutbatch_generate", args=[batch.pk]))
        held_ps = locked_cycle_with_hold_a.payslips.filter(on_hold=True).first()
        payment = PayoutPayment.objects.get(batch=batch, payslip=held_ps)
        assert payment.status == "on_hold"

    def test_generate_blocked_on_non_locked_cycle(self, client_a, tenant_a, draft_cycle_a):
        """A batch can't even be created against a non-locked cycle (form/clean() guard), but if the
        cycle is unlocked AFTER batch creation, generate must still refuse."""
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch.objects.create(tenant=tenant_a, cycle=draft_cycle_a)
        resp = client_a.post(reverse("hrm:payoutbatch_generate", args=[batch.pk]))
        assert resp.status_code == 302
        assert batch.payments.count() == 0

    def test_generate_blocked_when_not_draft(self, client_a, payout_batch_a):
        payout_batch_a.status = "approved"
        payout_batch_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        assert payout_batch_a.payments.count() == 0

    def test_generate_sets_generated_by_and_at(self, client_a, payout_batch_a, admin_user):
        client_a.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        payout_batch_a.refresh_from_db()
        assert payout_batch_a.generated_by_id == admin_user.pk
        assert payout_batch_a.generated_at is not None

    def test_regenerate_deletes_old_payments(self, client_a, generated_batch_a):
        """Re-generating a draft batch deletes prior payments (draft-only) and recreates them."""
        from apps.hrm.models import PayoutPayment
        old_pks = set(generated_batch_a.payments.values_list("pk", flat=True))
        client_a.post(reverse("hrm:payoutbatch_generate", args=[generated_batch_a.pk]))
        new_pks = set(PayoutPayment.objects.filter(batch=generated_batch_a).values_list("pk", flat=True))
        assert old_pks.isdisjoint(new_pks)

    def test_generate_totals_correct(self, client_a, payout_batch_a):
        client_a.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        from apps.hrm.models import PayoutBatch
        batch = PayoutBatch.objects.get(pk=payout_batch_a.pk)
        expected_total = sum((p.net_pay for p in batch.cycle.payslips.all()), Decimal("0"))
        assert batch.headcount == batch.cycle.payslips.count()
        assert batch.total_amount == expected_total
        assert batch.paid_count == 0
        assert batch.failed_count == 0
        assert batch.on_hold_count == 0


# ================================================================ Batch status derivation
class TestPayoutBatchStatusWorkflow:
    def test_approve_draft_to_approved(self, client_a, generated_batch_a):
        resp = client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        assert resp.status_code == 302
        generated_batch_a.refresh_from_db()
        assert generated_batch_a.status == "approved"
        assert generated_batch_a.approved_by_id is not None
        assert generated_batch_a.approved_at is not None

    def test_approve_blocked_without_payments(self, client_a, payout_batch_a):
        client_a.post(reverse("hrm:payoutbatch_approve", args=[payout_batch_a.pk]))
        payout_batch_a.refresh_from_db()
        assert payout_batch_a.status == "draft"

    def test_disburse_approved_to_disbursed(self, client_a, generated_batch_a):
        client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        resp = client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        assert resp.status_code == 302
        generated_batch_a.refresh_from_db()
        assert generated_batch_a.status == "disbursed"
        assert generated_batch_a.disbursed_at is not None

    def test_disburse_pending_payments_become_processing(self, client_a, generated_batch_a):
        client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        from apps.hrm.models import PayoutPayment
        for p in PayoutPayment.objects.filter(batch=generated_batch_a).exclude(status="on_hold"):
            assert p.status == "processing"
            assert p.initiated_at is not None

    def test_disburse_blocked_when_not_approved(self, client_a, generated_batch_a):
        resp = client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        generated_batch_a.refresh_from_db()
        assert generated_batch_a.status == "draft"

    def test_mark_paid_from_processing(self, client_a, generated_batch_a, employee_a):
        client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        resp = client_a.post(reverse("hrm:payoutpayment_mark_paid", args=[payment.pk]), {
            "transaction_reference": "UTR12345",
        })
        assert resp.status_code == 302
        payment.refresh_from_db()
        assert payment.status == "paid"
        assert payment.transaction_reference == "UTR12345"
        assert payment.paid_on is not None

    def test_mark_paid_batch_stays_disbursed_when_no_failures(
        self, client_a, generated_batch_a, employee_a, employee_a2
    ):
        """mark_paid on all payments with no failures -> batch stays disbursed."""
        from apps.hrm.models import PayoutBatch, PayoutPayment
        client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        for payment in PayoutPayment.objects.filter(batch=generated_batch_a):
            client_a.post(reverse("hrm:payoutpayment_mark_paid", args=[payment.pk]), {
                "transaction_reference": f"UTR{payment.pk}",
            })
        batch = PayoutBatch.objects.get(pk=generated_batch_a.pk)
        assert batch.status == "disbursed"
        assert batch.failed_count == 0
        assert batch.paid_count == batch.headcount

    def test_mark_failed_from_processing(self, client_a, generated_batch_a, employee_a):
        client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        resp = client_a.post(reverse("hrm:payoutpayment_mark_failed", args=[payment.pk]), {
            "failure_reason": "Invalid account",
        })
        assert resp.status_code == 302
        payment.refresh_from_db()
        assert payment.status == "failed"
        assert payment.failure_reason == "Invalid account"

    def test_mark_failed_flips_batch_to_partially_disbursed(self, client_a, generated_batch_a, employee_a):
        client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        client_a.post(reverse("hrm:payoutpayment_mark_failed", args=[payment.pk]))
        generated_batch_a.refresh_from_db()
        assert generated_batch_a.status == "partially_disbursed"

    def test_mark_paid_only_from_pending_or_processing(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        client_a.post(reverse("hrm:payoutpayment_mark_paid", args=[payment.pk]))
        payment.refresh_from_db()
        assert payment.status == "failed"  # unchanged — guard held

    def test_mark_failed_only_from_pending_or_processing(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        payment.status = "paid"
        payment.save(update_fields=["status"])
        client_a.post(reverse("hrm:payoutpayment_mark_failed", args=[payment.pk]))
        payment.refresh_from_db()
        assert payment.status == "paid"  # unchanged — guard held


# ================================================================ Retry workflow
class TestPayoutPaymentRetry:
    def _get_to_failed(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        client_a.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        client_a.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        client_a.post(reverse("hrm:payoutpayment_mark_failed", args=[payment.pk]))
        payment.refresh_from_db()
        return payment

    def test_retry_creates_new_pending_row(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        original = self._get_to_failed(client_a, generated_batch_a, employee_a)
        resp = client_a.post(reverse("hrm:payoutpayment_retry", args=[original.pk]))
        assert resp.status_code == 302
        retries = PayoutPayment.objects.filter(retry_of=original)
        assert retries.count() == 1
        retry = retries.first()
        assert retry.status == "pending"

    def test_retry_only_from_failed_or_returned(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        assert payment.status == "pending"
        client_a.post(reverse("hrm:payoutpayment_retry", args=[payment.pk]))
        assert PayoutPayment.objects.filter(retry_of=payment).count() == 0

    def test_current_payments_excludes_superseded_after_retry_view(
        self, client_a, generated_batch_a, employee_a
    ):
        original = self._get_to_failed(client_a, generated_batch_a, employee_a)
        client_a.post(reverse("hrm:payoutpayment_retry", args=[original.pk]))
        from apps.hrm.models import PayoutBatch
        fresh = PayoutBatch.objects.get(pk=generated_batch_a.pk)
        current_pks = set(fresh._current_payments().values_list("pk", flat=True))
        assert original.pk not in current_pks

    def test_retry_supersedes_failure_batch_becomes_disbursed(
        self, client_a, generated_batch_a, employee_a
    ):
        """The only failure in the batch gets retried -> failed_count drops to 0 -> a follow-up
        disburse-status recompute (triggered by another workflow action) flips the batch back to
        disbursed. We trigger _recompute_batch_status indirectly via another mark_paid call."""
        original = self._get_to_failed(client_a, generated_batch_a, employee_a)
        from apps.hrm.models import PayoutBatch, PayoutPayment
        fresh = PayoutBatch.objects.get(pk=generated_batch_a.pk)
        assert fresh.status == "partially_disbursed"
        client_a.post(reverse("hrm:payoutpayment_retry", args=[original.pk]))
        fresh2 = PayoutBatch.objects.get(pk=generated_batch_a.pk)
        assert fresh2.failed_count == 0
        assert fresh2.status == "disbursed"  # _recompute_batch_status ran inside the retry view

    def test_retry_not_double_counted_in_headcount(self, client_a, generated_batch_a, employee_a):
        original = self._get_to_failed(client_a, generated_batch_a, employee_a)
        from apps.hrm.models import PayoutBatch
        before = PayoutBatch.objects.get(pk=generated_batch_a.pk).headcount
        client_a.post(reverse("hrm:payoutpayment_retry", args=[original.pk]))
        after = PayoutBatch.objects.get(pk=generated_batch_a.pk).headcount
        assert after == before

    def test_retry_resnapshots_current_bank_details(self, client_a, generated_batch_a, employee_a, tenant_a):
        original = self._get_to_failed(client_a, generated_batch_a, employee_a)
        employee_a.bank_account = "999988887777"
        employee_a.save(update_fields=["bank_account"])
        client_a.post(reverse("hrm:payoutpayment_retry", args=[original.pk]))
        from apps.hrm.models import PayoutPayment
        retry = PayoutPayment.objects.get(retry_of=original)
        assert retry.bank_account_last4_snapshot == employee_a.masked_bank_account()
        assert "7777" in retry.bank_account_last4_snapshot


# ================================================================ PayslipDistribution
class TestPayslipDistributionViews:
    def test_list_200(self, client_a, payslip_a):
        from apps.hrm.models import PayslipDistribution
        PayslipDistribution.for_payslip(payslip_a)
        resp = client_a.get(reverse("hrm:payslipdistribution_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        resp = client_a.get(reverse("hrm:payslipdistribution_detail", args=[dist.pk]))
        assert resp.status_code == 200

    def test_send_marks_sent_with_email_snapshot(self, client_a, payslip_a, employee_a):
        from apps.hrm.models import PayslipDistribution
        employee_a.personal_email = "alice@acme.test"
        employee_a.save(update_fields=["personal_email"])
        dist = PayslipDistribution.for_payslip(payslip_a)
        resp = client_a.post(reverse("hrm:payslipdistribution_send", args=[dist.pk]))
        assert resp.status_code == 302
        dist.refresh_from_db()
        assert dist.status == "sent"
        assert dist.sent_to_email == "alice@acme.test"
        assert dist.sent_by_id is not None
        assert dist.sent_at is not None

    def test_send_cycle_creates_and_sends_all(self, client_a, locked_cycle_a):
        from apps.hrm.models import PayslipDistribution
        resp = client_a.post(reverse("hrm:payslipdistribution_send_cycle"), {
            "cycle": locked_cycle_a.pk,
        })
        assert resp.status_code == 302
        dists = PayslipDistribution.objects.filter(payslip__cycle=locked_cycle_a)
        assert dists.count() == locked_cycle_a.payslips.count()
        assert all(d.status == "sent" for d in dists)

    def test_mark_viewed_advances_from_sent(self, client_a, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        dist.status = "sent"
        dist.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:payslipdistribution_mark_viewed", args=[dist.pk]))
        assert resp.status_code == 302
        dist.refresh_from_db()
        assert dist.status == "viewed"
        assert dist.viewed_at is not None

    def test_mark_viewed_does_not_regress_from_downloaded(self, client_a, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        dist.status = "downloaded"
        dist.save(update_fields=["status"])
        client_a.post(reverse("hrm:payslipdistribution_mark_viewed", args=[dist.pk]))
        dist.refresh_from_db()
        assert dist.status == "downloaded"  # only pending/sent -> viewed

    def test_mark_downloaded_always_advances(self, client_a, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        resp = client_a.post(reverse("hrm:payslipdistribution_mark_downloaded", args=[dist.pk]))
        assert resp.status_code == 302
        dist.refresh_from_db()
        assert dist.status == "downloaded"
        assert dist.downloaded_at is not None


# ================================================================ BankReconciliation
class TestBankReconciliationViews:
    def test_list_200(self, client_a, tenant_a, payout_batch_a):
        from apps.hrm.models import BankReconciliation
        BankReconciliation.objects.create(
            tenant=tenant_a, batch=payout_batch_a, statement_date=datetime.date(2026, 7, 2))
        resp = client_a.get(reverse("hrm:bankreconciliation_list"))
        assert resp.status_code == 200

    def test_create_post(self, client_a, tenant_a, payout_batch_a):
        from apps.hrm.models import BankReconciliation
        resp = client_a.post(reverse("hrm:bankreconciliation_create"), {
            "batch": payout_batch_a.pk, "statement_date": "2026-07-02",
            "statement_reference": "STMT-001", "notes": "",
        })
        assert resp.status_code == 302
        assert BankReconciliation.objects.filter(tenant=tenant_a, batch=payout_batch_a).exists()

    def test_detail_200_with_exceptions_context(self, client_a, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=generated_batch_a, statement_date=datetime.date(2026, 7, 2))
        resp = client_a.get(reverse("hrm:bankreconciliation_detail", args=[recon.pk]))
        assert resp.status_code == 200
        assert "exceptions" in resp.context

    def test_reconcile_full_match_flips_batch_to_reconciled(self, client_a, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation, PayoutBatch, PayoutPayment
        generated_batch_a.status = "disbursed"
        generated_batch_a.save(update_fields=["status"])
        for p in generated_batch_a.payments.all():
            p.status = "paid"
            p.transaction_reference = f"UTR{p.pk}"
            p.save(update_fields=["status", "transaction_reference"])
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=generated_batch_a, statement_date=datetime.date(2026, 7, 2))
        resp = client_a.post(reverse("hrm:bankreconciliation_reconcile", args=[recon.pk]))
        assert resp.status_code == 302
        recon.refresh_from_db()
        assert recon.status == "reconciled"
        assert recon.reconciled_by_id is not None
        batch = PayoutBatch.objects.get(pk=generated_batch_a.pk)
        assert batch.status == "reconciled"

    def test_reconcile_partial_match_stays_discrepancy_batch_unchanged(
        self, client_a, tenant_a, generated_batch_a
    ):
        from apps.hrm.models import BankReconciliation, PayoutBatch
        generated_batch_a.status = "disbursed"
        generated_batch_a.save(update_fields=["status"])
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=generated_batch_a, statement_date=datetime.date(2026, 7, 2))
        client_a.post(reverse("hrm:bankreconciliation_reconcile", args=[recon.pk]))
        recon.refresh_from_db()
        assert recon.status == "discrepancy"
        batch = PayoutBatch.objects.get(pk=generated_batch_a.pk)
        assert batch.status == "disbursed"  # not flipped — no full match

    def test_edit_blocked_when_reconciled(self, client_a, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=generated_batch_a, statement_date=datetime.date(2026, 7, 2),
            status="reconciled",
        )
        resp = client_a.get(reverse("hrm:bankreconciliation_edit", args=[recon.pk]))
        assert resp.status_code == 302

    def test_delete_blocked_when_reconciled(self, client_a, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=generated_batch_a, statement_date=datetime.date(2026, 7, 2),
            status="reconciled",
        )
        resp = client_a.post(reverse("hrm:bankreconciliation_delete", args=[recon.pk]))
        assert BankReconciliation.objects.filter(pk=recon.pk).exists()
        assert resp.status_code == 302


# ================================================================ Reports
class TestPaymentRegisterReport:
    def test_200_with_by_status_and_by_method(self, client_a, generated_batch_a):
        resp = client_a.get(reverse("hrm:payment_register", args=[generated_batch_a.pk]))
        assert resp.status_code == 200
        assert "by_status" in resp.context
        assert "by_method" in resp.context
        assert "payments" in resp.context

    def test_excludes_superseded_originals(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        original = generated_batch_a.payments.get(employee=employee_a)
        original.status = "failed"
        original.save(update_fields=["status"])
        retry = PayoutPayment.objects.create(
            tenant=original.tenant, batch=original.batch, payslip=original.payslip,
            employee=employee_a, net_amount=original.net_amount,
            bank_name_snapshot=original.bank_name_snapshot,
            bank_account_last4_snapshot=original.bank_account_last4_snapshot,
            bank_routing_snapshot=original.bank_routing_snapshot,
            status="pending", retry_of=original,
        )
        resp = client_a.get(reverse("hrm:payment_register", args=[generated_batch_a.pk]))
        pks = [p.pk for p in resp.context["payments"]]
        assert original.pk not in pks
        assert retry.pk in pks


class TestPayoutExceptionsReport:
    def test_200_lists_failed_not_yet_retried(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        resp = client_a.get(reverse("hrm:payout_exceptions"))
        assert resp.status_code == 200
        pks = [p.pk for p in resp.context["payments"]]
        assert payment.pk in pks

    def test_excludes_retried_failures(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        PayoutPayment.objects.create(
            tenant=payment.tenant, batch=payment.batch, payslip=payment.payslip,
            employee=employee_a, net_amount=payment.net_amount,
            bank_name_snapshot=payment.bank_name_snapshot,
            bank_account_last4_snapshot=payment.bank_account_last4_snapshot,
            bank_routing_snapshot=payment.bank_routing_snapshot,
            status="pending", retry_of=payment,
        )
        resp = client_a.get(reverse("hrm:payout_exceptions"))
        pks = [p.pk for p in resp.context["payments"]]
        assert payment.pk not in pks  # superseded original excluded

    def test_filter_by_batch(self, client_a, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        resp = client_a.get(reverse("hrm:payout_exceptions"), {"batch": generated_batch_a.pk})
        assert resp.status_code == 200
        pks = [p.pk for p in resp.context["payments"]]
        assert payment.pk in pks


# ================================================================ Bounded queries (N+1 guard)
class TestPayoutQueryCount:
    def test_payoutbatch_list_bounded_queries_flat(
        self, client_a, tenant_a, django_assert_max_num_queries
    ):
        """The list must not grow per-batch-row — create several distinct locked cycles + batches
        with payments and assert the query count stays flat (performance-reviewer-requested)."""
        from apps.hrm.models import EmployeeSalaryStructure, PayrollCycle, Payslip, PayoutBatch, \
            PayoutPayment
        from apps.core.models import Party, Employment, OrgUnit
        for i in range(5):
            party = Party.objects.create(tenant=tenant_a, kind="person", name=f"Emp {i}")
            employment = Employment.objects.create(
                tenant=tenant_a, party=party, job_title="Staff",
                hired_on=datetime.date(2023, 1, 1), status="active")
            from apps.hrm.models import EmployeeProfile
            emp = EmployeeProfile.objects.create(
                tenant=tenant_a, party=party, employment=employment, employee_type="full_time",
                bank_account=f"11112222{i}{i}{i}{i}",
            )
            cycle = PayrollCycle.objects.create(
                tenant=tenant_a, period_start=datetime.date(2026, 1, 1),
                period_end=datetime.date(2026, 1, 31), pay_date=datetime.date(2026, 2, 1),
                status="draft")
            ps = Payslip.objects.create(tenant=tenant_a, cycle=cycle, employee=emp,
                                        days_in_period=30, days_worked=30)
            ps.recompute()
            cycle.status = "locked"
            cycle.save(update_fields=["status"])
            batch = PayoutBatch.objects.create(tenant=tenant_a, cycle=cycle)
            PayoutPayment.objects.create(
                tenant=tenant_a, batch=batch, payslip=ps, employee=emp, net_amount=ps.net_pay,
                bank_account_last4_snapshot=emp.masked_bank_account(), status="paid")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:payoutbatch_list"))

    def test_payment_register_bounded_queries(self, client_a, generated_batch_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:payment_register", args=[generated_batch_a.pk]))
