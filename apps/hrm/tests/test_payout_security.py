"""Security tests for HRM 3.17 Payout & Reports: cross-tenant IDOR (PayoutBatch/PayoutPayment/
PayslipDistribution/BankReconciliation), list isolation, anonymous-blocked, tenant-admin-only
workflow actions, CSRF enforcement on the delete/generate/approve/disburse/mark_*/retry/send/
send_cycle/reconcile POSTs."""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ PayoutBatch IDOR
class TestPayoutBatchIDOR:
    def test_detail_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.get(reverse("hrm:payoutbatch_detail", args=[batch_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.get(reverse("hrm:payoutbatch_edit", args=[batch_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.post(reverse("hrm:payoutbatch_edit", args=[batch_b.pk]), {
            "cycle": batch_b.cycle_id, "bank_file_format": "neft",
            "source_bank_name": "hacked", "source_account_last4": "", "notes": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.post(reverse("hrm:payoutbatch_delete", args=[batch_b.pk]))
        assert resp.status_code == 404

    def test_generate_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.post(reverse("hrm:payoutbatch_generate", args=[batch_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.post(reverse("hrm:payoutbatch_approve", args=[batch_b.pk]))
        assert resp.status_code == 404

    def test_disburse_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.post(reverse("hrm:payoutbatch_disburse", args=[batch_b.pk]))
        assert resp.status_code == 404

    def test_payment_register_cross_tenant_404(self, client_a, batch_b):
        resp = client_a.get(reverse("hrm:payment_register", args=[batch_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_batches(self, client_a, payout_batch_a, batch_b):
        resp = client_a.get(reverse("hrm:payoutbatch_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payout_batch_a.pk in pks
        assert batch_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, batch_b):
        original_status = batch_b.status
        client_a.post(reverse("hrm:payoutbatch_generate", args=[batch_b.pk]))
        client_a.post(reverse("hrm:payoutbatch_approve", args=[batch_b.pk]))
        client_a.post(reverse("hrm:payoutbatch_disburse", args=[batch_b.pk]))
        batch_b.refresh_from_db()
        assert batch_b.status == original_status
        assert batch_b.payments.count() == 0


# ================================================================ PayoutPayment IDOR
class TestPayoutPaymentIDOR:
    def test_mark_paid_cross_tenant_404(self, client_a, payment_b):
        resp = client_a.post(reverse("hrm:payoutpayment_mark_paid", args=[payment_b.pk]))
        assert resp.status_code == 404

    def test_mark_failed_cross_tenant_404(self, client_a, payment_b):
        resp = client_a.post(reverse("hrm:payoutpayment_mark_failed", args=[payment_b.pk]))
        assert resp.status_code == 404

    def test_retry_cross_tenant_404(self, client_a, payment_b):
        resp = client_a.post(reverse("hrm:payoutpayment_retry", args=[payment_b.pk]))
        assert resp.status_code == 404

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, payment_b):
        from apps.hrm.models import PayoutPayment
        original_status = payment_b.status
        client_a.post(reverse("hrm:payoutpayment_mark_paid", args=[payment_b.pk]))
        client_a.post(reverse("hrm:payoutpayment_mark_failed", args=[payment_b.pk]))
        client_a.post(reverse("hrm:payoutpayment_retry", args=[payment_b.pk]))
        payment_b.refresh_from_db()
        assert payment_b.status == original_status
        assert PayoutPayment.objects.filter(retry_of=payment_b).count() == 0


# ================================================================ PayslipDistribution IDOR
class TestPayslipDistributionIDOR:
    def test_detail_cross_tenant_404(self, client_a, distribution_b):
        resp = client_a.get(reverse("hrm:payslipdistribution_detail", args=[distribution_b.pk]))
        assert resp.status_code == 404

    def test_send_cross_tenant_404(self, client_a, distribution_b):
        resp = client_a.post(reverse("hrm:payslipdistribution_send", args=[distribution_b.pk]))
        assert resp.status_code == 404

    def test_mark_viewed_cross_tenant_404(self, client_a, distribution_b):
        resp = client_a.post(reverse("hrm:payslipdistribution_mark_viewed", args=[distribution_b.pk]))
        assert resp.status_code == 404

    def test_mark_downloaded_cross_tenant_404(self, client_a, distribution_b):
        resp = client_a.post(reverse("hrm:payslipdistribution_mark_downloaded", args=[distribution_b.pk]))
        assert resp.status_code == 404

    def test_send_cycle_cross_tenant_cycle_creates_nothing(self, client_a, cycle_b_locked, tenant_a):
        """Posting a foreign (tenant_b) cycle pk to send_cycle must not distribute tenant_b's payslips
        — the view scopes the cycle lookup by request.tenant, so a foreign pk 404s."""
        resp = client_a.post(reverse("hrm:payslipdistribution_send_cycle"), {
            "cycle": cycle_b_locked.pk,
        })
        assert resp.status_code == 404
        from apps.hrm.models import PayslipDistribution
        assert not PayslipDistribution.objects.filter(payslip__cycle=cycle_b_locked).exists()

    def test_list_excludes_b_distributions(self, client_a, payslip_a, distribution_b):
        from apps.hrm.models import PayslipDistribution
        own = PayslipDistribution.for_payslip(payslip_a)
        resp = client_a.get(reverse("hrm:payslipdistribution_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert own.pk in pks
        assert distribution_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, distribution_b):
        original_status = distribution_b.status
        client_a.post(reverse("hrm:payslipdistribution_send", args=[distribution_b.pk]))
        client_a.post(reverse("hrm:payslipdistribution_mark_viewed", args=[distribution_b.pk]))
        client_a.post(reverse("hrm:payslipdistribution_mark_downloaded", args=[distribution_b.pk]))
        distribution_b.refresh_from_db()
        assert distribution_b.status == original_status


# ================================================================ BankReconciliation IDOR
class TestBankReconciliationIDOR:
    def test_detail_cross_tenant_404(self, client_a, reconciliation_b):
        resp = client_a.get(reverse("hrm:bankreconciliation_detail", args=[reconciliation_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, reconciliation_b):
        resp = client_a.get(reverse("hrm:bankreconciliation_edit", args=[reconciliation_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, reconciliation_b):
        resp = client_a.post(reverse("hrm:bankreconciliation_edit", args=[reconciliation_b.pk]), {
            "batch": reconciliation_b.batch_id, "statement_date": "2026-07-02",
            "statement_reference": "hacked", "notes": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, reconciliation_b):
        resp = client_a.post(reverse("hrm:bankreconciliation_delete", args=[reconciliation_b.pk]))
        assert resp.status_code == 404

    def test_reconcile_cross_tenant_404(self, client_a, reconciliation_b):
        resp = client_a.post(reverse("hrm:bankreconciliation_reconcile", args=[reconciliation_b.pk]))
        assert resp.status_code == 404

    def test_create_cross_tenant_batch_rejected(self, client_a, batch_b):
        """Posting a foreign batch pk to bankreconciliation_create must not create a row — the form's
        batch queryset is scoped to request.tenant so the foreign pk fails form validation."""
        from apps.hrm.models import BankReconciliation
        resp = client_a.post(reverse("hrm:bankreconciliation_create"), {
            "batch": batch_b.pk, "statement_date": "2026-07-02",
            "statement_reference": "", "notes": "",
        })
        assert resp.status_code == 200  # re-rendered form with errors, not a 500/302
        assert not BankReconciliation.objects.filter(batch=batch_b).exists()

    def test_list_excludes_b_reconciliations(self, client_a, tenant_a, payout_batch_a, reconciliation_b):
        from apps.hrm.models import BankReconciliation
        own = BankReconciliation.objects.create(
            tenant=tenant_a, batch=payout_batch_a, statement_date=datetime.date(2026, 7, 2))
        resp = client_a.get(reverse("hrm:bankreconciliation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert own.pk in pks
        assert reconciliation_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, reconciliation_b):
        original_status = reconciliation_b.status
        client_a.post(reverse("hrm:bankreconciliation_reconcile", args=[reconciliation_b.pk]))
        reconciliation_b.refresh_from_db()
        assert reconciliation_b.status == original_status


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:payoutbatch_list", []),
        ("hrm:payslipdistribution_list", []),
        ("hrm:bankreconciliation_list", []),
        ("hrm:payout_exceptions", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_pages(
        self, client, payout_batch_a, generated_batch_a, payslip_a,
    ):
        from apps.hrm.models import PayslipDistribution, BankReconciliation
        dist = PayslipDistribution.for_payslip(payslip_a)
        recon = BankReconciliation.objects.create(
            tenant=payout_batch_a.tenant, batch=payout_batch_a,
            statement_date=datetime.date(2026, 7, 2))
        for url_name, pk in [
            ("hrm:payoutbatch_detail", payout_batch_a.pk),
            ("hrm:payslipdistribution_detail", dist.pk),
            ("hrm:bankreconciliation_detail", recon.pk),
            ("hrm:payment_register", generated_batch_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_actions(self, client, payout_batch_a, generated_batch_a):
        for url_name, pk in [
            ("hrm:payoutbatch_delete", payout_batch_a.pk),
            ("hrm:payoutbatch_generate", payout_batch_a.pk),
            ("hrm:payoutbatch_approve", payout_batch_a.pk),
            ("hrm:payoutbatch_disburse", payout_batch_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ================================================================ AuthZ — tenant-admin-only actions
class TestPayoutAdminOnlyActions:
    """@tenant_admin_required gates generate/approve/disburse/mark_paid/mark_failed/retry/send/
    send_cycle/reconcile — a plain (non-admin) tenant member must get 403 and the row must remain
    unchanged."""

    def test_non_admin_403_on_generate(self, member_client, payout_batch_a):
        resp = member_client.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        assert resp.status_code == 403
        assert payout_batch_a.payments.count() == 0

    def test_non_admin_403_on_approve(self, member_client, generated_batch_a):
        resp = member_client.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        assert resp.status_code == 403
        generated_batch_a.refresh_from_db()
        assert generated_batch_a.status == "draft"

    def test_non_admin_403_on_disburse(self, member_client, generated_batch_a):
        generated_batch_a.status = "approved"
        generated_batch_a.save(update_fields=["status"])
        resp = member_client.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        assert resp.status_code == 403
        generated_batch_a.refresh_from_db()
        assert generated_batch_a.status == "approved"

    def test_non_admin_403_on_mark_paid(self, member_client, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        resp = member_client.post(reverse("hrm:payoutpayment_mark_paid", args=[payment.pk]))
        assert resp.status_code == 403
        payment.refresh_from_db()
        assert payment.status == "pending"

    def test_non_admin_403_on_mark_failed(self, member_client, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        resp = member_client.post(reverse("hrm:payoutpayment_mark_failed", args=[payment.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_retry(self, member_client, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        resp = member_client.post(reverse("hrm:payoutpayment_retry", args=[payment.pk]))
        assert resp.status_code == 403
        assert PayoutPayment.objects.filter(retry_of=payment).count() == 0

    def test_non_admin_403_on_send(self, member_client, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        resp = member_client.post(reverse("hrm:payslipdistribution_send", args=[dist.pk]))
        assert resp.status_code == 403
        dist.refresh_from_db()
        assert dist.status == "pending"

    def test_non_admin_403_on_send_cycle(self, member_client, locked_cycle_a):
        resp = member_client.post(reverse("hrm:payslipdistribution_send_cycle"), {
            "cycle": locked_cycle_a.pk,
        })
        assert resp.status_code == 403
        from apps.hrm.models import PayslipDistribution
        assert not PayslipDistribution.objects.filter(payslip__cycle=locked_cycle_a).exists()

    def test_non_admin_403_on_reconcile(self, member_client, tenant_a, generated_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=generated_batch_a, statement_date=datetime.date(2026, 7, 2))
        resp = member_client.post(reverse("hrm:bankreconciliation_reconcile", args=[recon.pk]))
        assert resp.status_code == 403
        recon.refresh_from_db()
        assert recon.status == "pending"

    def test_non_admin_can_still_view_lists(self, member_client, payout_batch_a):
        """Plain @login_required reads (list/detail) stay open to non-admin tenant members."""
        resp = member_client.get(reverse("hrm:payoutbatch_list"))
        assert resp.status_code == 200
        resp = member_client.get(reverse("hrm:payoutbatch_detail", args=[payout_batch_a.pk]))
        assert resp.status_code == 200

    def test_non_admin_can_mark_viewed_downloaded(self, member_client, payslip_a):
        """mark_viewed/mark_downloaded are plain @login_required — not admin-gated (documented
        product decision: no data disclosure, only bumps a status/timestamp)."""
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        resp = member_client.post(reverse("hrm:payslipdistribution_mark_viewed", args=[dist.pk]))
        assert resp.status_code == 302
        dist.refresh_from_db()
        assert dist.status == "viewed"


# ================================================================ CSRF enforcement
class TestPayoutCSRFEnforcement:
    def test_payoutbatch_delete_enforces_csrf(self, admin_user, payout_batch_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payoutbatch_delete", args=[payout_batch_a.pk]))
        assert resp.status_code == 403

    def test_payoutbatch_generate_enforces_csrf(self, admin_user, payout_batch_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payoutbatch_generate", args=[payout_batch_a.pk]))
        assert resp.status_code == 403

    def test_payoutbatch_approve_enforces_csrf(self, admin_user, generated_batch_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payoutbatch_approve", args=[generated_batch_a.pk]))
        assert resp.status_code == 403

    def test_payoutbatch_disburse_enforces_csrf(self, admin_user, generated_batch_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payoutbatch_disburse", args=[generated_batch_a.pk]))
        assert resp.status_code == 403

    def test_payoutpayment_mark_paid_enforces_csrf(self, admin_user, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payoutpayment_mark_paid", args=[payment.pk]))
        assert resp.status_code == 403

    def test_payoutpayment_mark_failed_enforces_csrf(self, admin_user, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payoutpayment_mark_failed", args=[payment.pk]))
        assert resp.status_code == 403

    def test_payoutpayment_retry_enforces_csrf(self, admin_user, generated_batch_a, employee_a):
        from apps.hrm.models import PayoutPayment
        payment = PayoutPayment.objects.get(batch=generated_batch_a, employee=employee_a)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payoutpayment_retry", args=[payment.pk]))
        assert resp.status_code == 403

    def test_payslipdistribution_send_enforces_csrf(self, admin_user, payslip_a):
        from apps.hrm.models import PayslipDistribution
        dist = PayslipDistribution.for_payslip(payslip_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payslipdistribution_send", args=[dist.pk]))
        assert resp.status_code == 403

    def test_payslipdistribution_send_cycle_enforces_csrf(self, admin_user, locked_cycle_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payslipdistribution_send_cycle"), {"cycle": locked_cycle_a.pk})
        assert resp.status_code == 403

    def test_bankreconciliation_delete_enforces_csrf(self, admin_user, tenant_a, payout_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=payout_batch_a, statement_date=datetime.date(2026, 7, 2))
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:bankreconciliation_delete", args=[recon.pk]))
        assert resp.status_code == 403

    def test_bankreconciliation_reconcile_enforces_csrf(self, admin_user, tenant_a, payout_batch_a):
        from apps.hrm.models import BankReconciliation
        recon = BankReconciliation.objects.create(
            tenant=tenant_a, batch=payout_batch_a, statement_date=datetime.date(2026, 7, 2))
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:bankreconciliation_reconcile", args=[recon.pk]))
        assert resp.status_code == 403
