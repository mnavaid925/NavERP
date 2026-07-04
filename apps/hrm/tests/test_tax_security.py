"""Security tests for HRM 3.16 Tax & Investment: cross-tenant IDOR (TaxRegimeConfig/TaxSlabBand/
InvestmentDeclaration/InvestmentDeclarationLine/InvestmentProof/TaxComputation), list isolation,
anonymous-blocked, tenant-admin-only actions, CSRF enforcement on the delete/submit/lock/verify/
reject/on_hold/generate/link_form16/upload/inline POST routes."""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ TaxRegimeConfig / TaxSlabBand IDOR
class TestTaxRegimeConfigIDOR:
    def test_detail_cross_tenant_404(self, client_a, regime_config_b):
        resp = client_a.get(reverse("hrm:taxregimeconfig_detail", args=[regime_config_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, regime_config_b):
        resp = client_a.get(reverse("hrm:taxregimeconfig_edit", args=[regime_config_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, regime_config_b):
        resp = client_a.post(reverse("hrm:taxregimeconfig_edit", args=[regime_config_b.pk]), {
            "financial_year": "2025-26", "regime": "new",
            "standard_deduction": "1.00", "cess_rate": "4.00",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, regime_config_b):
        resp = client_a.post(reverse("hrm:taxregimeconfig_delete", args=[regime_config_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_configs(self, client_a, old_regime_config_a, regime_config_b):
        resp = client_a.get(reverse("hrm:taxregimeconfig_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert old_regime_config_a.pk in pks
        assert regime_config_b.pk not in pks


class TestTaxSlabBandIDOR:
    def test_create_cross_tenant_config_404(self, client_a, regime_config_b):
        resp = client_a.post(reverse("hrm:taxslabband_create", args=[regime_config_b.pk]), {
            "income_from": "0", "income_to": "100000", "rate_percent": "0", "sequence": "1",
        })
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, regime_config_b, slab_band_b):
        resp = client_a.get(reverse("hrm:taxslabband_edit", args=[regime_config_b.pk, slab_band_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, regime_config_b, slab_band_b):
        resp = client_a.post(
            reverse("hrm:taxslabband_edit", args=[regime_config_b.pk, slab_band_b.pk]), {
                "income_from": "0", "income_to": "999999", "rate_percent": "99", "sequence": "1",
            })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, regime_config_b, slab_band_b):
        resp = client_a.post(reverse("hrm:taxslabband_delete", args=[regime_config_b.pk, slab_band_b.pk]))
        assert resp.status_code == 404

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, regime_config_b, slab_band_b):
        original_rate = slab_band_b.rate_percent
        client_a.post(reverse("hrm:taxslabband_edit", args=[regime_config_b.pk, slab_band_b.pk]), {
            "income_from": "0", "income_to": "999999", "rate_percent": "99", "sequence": "1",
        })
        slab_band_b.refresh_from_db()
        assert slab_band_b.rate_percent == original_rate

    def test_edit_own_config_but_foreign_band_404(self, client_a, old_regime_config_a, slab_band_b):
        """Even when config_pk belongs to A, a band pk belonging to B must still 404 (band is
        additionally scoped by tenant, not just by config_pk)."""
        resp = client_a.get(reverse("hrm:taxslabband_edit", args=[old_regime_config_a.pk, slab_band_b.pk]))
        assert resp.status_code == 404


# ================================================================ InvestmentDeclaration IDOR
class TestInvestmentDeclarationIDOR:
    def test_detail_cross_tenant_404(self, client_a, declaration_b):
        resp = client_a.get(reverse("hrm:investmentdeclaration_detail", args=[declaration_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, declaration_b):
        resp = client_a.get(reverse("hrm:investmentdeclaration_edit", args=[declaration_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, declaration_b):
        resp = client_a.post(reverse("hrm:investmentdeclaration_edit", args=[declaration_b.pk]), {
            "employee": declaration_b.employee_id, "financial_year": "2025-26", "regime_elected": "old",
            "previous_employer_income": "999999", "previous_employer_tds": "0", "notes": "hacked",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, declaration_b):
        resp = client_a.post(reverse("hrm:investmentdeclaration_delete", args=[declaration_b.pk]))
        assert resp.status_code == 404

    def test_submit_cross_tenant_404(self, client_a, declaration_b):
        resp = client_a.post(reverse("hrm:investmentdeclaration_submit", args=[declaration_b.pk]))
        assert resp.status_code == 404

    def test_lock_cross_tenant_404(self, client_a, declaration_b):
        resp = client_a.post(reverse("hrm:investmentdeclaration_lock", args=[declaration_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_declarations(self, client_a, tax_declaration_a, declaration_b):
        resp = client_a.get(reverse("hrm:investmentdeclaration_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tax_declaration_a.pk in pks
        assert declaration_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, declaration_b):
        original_status = declaration_b.status
        client_a.post(reverse("hrm:investmentdeclaration_submit", args=[declaration_b.pk]))
        client_a.post(reverse("hrm:investmentdeclaration_lock", args=[declaration_b.pk]))
        declaration_b.refresh_from_db()
        assert declaration_b.status == original_status


class TestInvestmentDeclarationLineIDOR:
    def test_create_cross_tenant_declaration_404(self, client_a, declaration_b):
        resp = client_a.post(reverse("hrm:investmentdeclarationline_create", args=[declaration_b.pk]), {
            "section_code": "80c", "declared_amount": "1000",
        })
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, declaration_b, line_b):
        resp = client_a.get(
            reverse("hrm:investmentdeclarationline_edit", args=[declaration_b.pk, line_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, declaration_b, line_b):
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_edit", args=[declaration_b.pk, line_b.pk]), {
                "section_code": "80c", "declared_amount": "999999",
            })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, declaration_b, line_b):
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_delete", args=[declaration_b.pk, line_b.pk]))
        assert resp.status_code == 404

    def test_own_declaration_but_foreign_line_404(self, client_a, draft_declaration_a, line_b):
        """Own declaration_pk (A) but a line pk belonging to B must still 404 (line additionally
        scoped by tenant + declaration, not just declaration_pk)."""
        resp = client_a.get(
            reverse("hrm:investmentdeclarationline_edit", args=[draft_declaration_a.pk, line_b.pk]))
        assert resp.status_code == 404

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, declaration_b, line_b):
        original_amount = line_b.declared_amount
        client_a.post(
            reverse("hrm:investmentdeclarationline_edit", args=[declaration_b.pk, line_b.pk]), {
                "section_code": "80c", "declared_amount": "999999",
            })
        line_b.refresh_from_db()
        assert line_b.declared_amount == original_amount


# ================================================================ InvestmentProof IDOR
class TestInvestmentProofIDOR:
    def test_upload_cross_tenant_line_404(self, client_a, line_b):
        f = SimpleUploadedFile("hack.pdf", b"%PDF-1.4", content_type="application/pdf")
        resp = client_a.post(reverse("hrm:investmentproof_upload", args=[line_b.pk]), {
            "file": f, "title": "Hack", "amount": "1", "notes": "",
        })
        assert resp.status_code == 404

    def test_detail_cross_tenant_404(self, client_a, proof_b):
        resp = client_a.get(reverse("hrm:investmentproof_detail", args=[proof_b.pk]))
        assert resp.status_code == 404

    def test_verify_cross_tenant_404(self, client_a, proof_b):
        resp = client_a.post(reverse("hrm:investmentproof_verify", args=[proof_b.pk]))
        assert resp.status_code == 404

    def test_reject_cross_tenant_404(self, client_a, proof_b):
        resp = client_a.post(reverse("hrm:investmentproof_reject", args=[proof_b.pk]))
        assert resp.status_code == 404

    def test_on_hold_cross_tenant_404(self, client_a, proof_b):
        resp = client_a.post(reverse("hrm:investmentproof_on_hold", args=[proof_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_proofs(self, client_a, pending_proof_80c_a, proof_b):
        resp = client_a.get(reverse("hrm:investmentproof_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_proof_80c_a.pk in pks
        assert proof_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, proof_b):
        original_status = proof_b.verification_status
        client_a.post(reverse("hrm:investmentproof_verify", args=[proof_b.pk]))
        proof_b.refresh_from_db()
        assert proof_b.verification_status == original_status


# ================================================================ TaxComputation IDOR
class TestTaxComputationIDOR:
    def test_detail_cross_tenant_404(self, client_a, computation_b):
        resp = client_a.get(reverse("hrm:taxcomputation_detail", args=[computation_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, computation_b):
        resp = client_a.get(reverse("hrm:taxcomputation_edit", args=[computation_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, computation_b):
        resp = client_a.post(reverse("hrm:taxcomputation_edit", args=[computation_b.pk]), {
            "employee": computation_b.employee_id, "declaration": computation_b.declaration_id,
            "computation_type": "final", "remaining_pay_periods": "1", "notes": "hacked",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, computation_b):
        resp = client_a.post(reverse("hrm:taxcomputation_delete", args=[computation_b.pk]))
        assert resp.status_code == 404

    def test_generate_cross_tenant_404(self, client_a, computation_b):
        resp = client_a.post(reverse("hrm:taxcomputation_generate", args=[computation_b.pk]))
        assert resp.status_code == 404

    def test_link_form16_cross_tenant_404(self, client_a, computation_b):
        resp = client_a.post(reverse("hrm:taxcomputation_link_form16", args=[computation_b.pk]))
        assert resp.status_code == 404

    def test_form16_partb_cross_tenant_404(self, client_a, computation_b):
        resp = client_a.get(reverse("hrm:form16_partb", args=[computation_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_computations(self, client_a, tax_computation_a, computation_b):
        resp = client_a.get(reverse("hrm:taxcomputation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tax_computation_a.pk in pks
        assert computation_b.pk not in pks

    def test_tax_regime_comparison_cannot_read_b_computation(self, client_a, computation_b):
        """Passing a foreign pk via ?computation= must not leak tenant_b's data — the view scopes its
        own filter by request.tenant, so comp resolves to None rather than 404 (GET, no pk in the URL
        path) but the breakdown must never be built from tenant_b's row."""
        resp = client_a.get(reverse("hrm:tax_regime_comparison"), {"computation": computation_b.pk})
        assert resp.status_code == 200
        assert resp.context["comp"] is None
        assert "breakdown" not in resp.context

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, computation_b):
        original_payable = computation_b.tax_payable
        client_a.post(reverse("hrm:taxcomputation_generate", args=[computation_b.pk]))
        client_a.post(reverse("hrm:taxcomputation_link_form16", args=[computation_b.pk]))
        computation_b.refresh_from_db()
        assert computation_b.tax_payable == original_payable
        assert computation_b.statutory_return_id is None


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:taxregimeconfig_list", []),
        ("hrm:investmentdeclaration_list", []),
        ("hrm:investmentproof_list", []),
        ("hrm:taxcomputation_list", []),
        ("hrm:tax_regime_comparison", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_pages(
        self, client, old_regime_config_a, tax_declaration_a, pending_proof_80c_a, tax_computation_a,
    ):
        for url_name, pk in [
            ("hrm:taxregimeconfig_detail", old_regime_config_a.pk),
            ("hrm:investmentdeclaration_detail", tax_declaration_a.pk),
            ("hrm:investmentproof_detail", pending_proof_80c_a.pk),
            ("hrm:taxcomputation_detail", tax_computation_a.pk),
            ("hrm:form16_partb", tax_computation_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_actions(
        self, client, tax_declaration_a, pending_proof_80c_a, tax_computation_a,
    ):
        for url_name, pk in [
            ("hrm:investmentdeclaration_submit", tax_declaration_a.pk),
            ("hrm:investmentdeclaration_lock", tax_declaration_a.pk),
            ("hrm:investmentproof_verify", pending_proof_80c_a.pk),
            ("hrm:investmentproof_reject", pending_proof_80c_a.pk),
            ("hrm:investmentproof_on_hold", pending_proof_80c_a.pk),
            ("hrm:taxcomputation_generate", tax_computation_a.pk),
            ("hrm:taxcomputation_link_form16", tax_computation_a.pk),
            ("hrm:taxcomputation_delete", tax_computation_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_upload(self, client, line_80c_a):
        f = SimpleUploadedFile("anon.pdf", b"%PDF-1.4", content_type="application/pdf")
        resp = client.post(reverse("hrm:investmentproof_upload", args=[line_80c_a.pk]), {
            "file": f, "title": "Anon Upload", "amount": "1", "notes": "",
        })
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ AuthZ — tenant-admin-only actions
class TestTaxAdminOnlyActions:
    """@tenant_admin_required gates the InvestmentDeclaration lock, InvestmentProof verify/reject/
    on_hold, and TaxComputation generate/link_form16 actions — a plain (non-admin) tenant member must
    get 403 and the underlying row must remain unchanged."""

    def test_non_admin_403_on_investmentdeclaration_lock(self, member_client, tax_declaration_a):
        resp = member_client.post(reverse("hrm:investmentdeclaration_lock", args=[tax_declaration_a.pk]))
        assert resp.status_code == 403
        tax_declaration_a.refresh_from_db()
        assert tax_declaration_a.status == "submitted"

    def test_non_admin_403_on_investmentproof_verify(self, member_client, pending_proof_80c_a):
        resp = member_client.post(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403
        pending_proof_80c_a.refresh_from_db()
        assert pending_proof_80c_a.verification_status == "pending"

    def test_non_admin_403_on_investmentproof_reject(self, member_client, pending_proof_80c_a):
        resp = member_client.post(reverse("hrm:investmentproof_reject", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_investmentproof_on_hold(self, member_client, pending_proof_80c_a):
        resp = member_client.post(reverse("hrm:investmentproof_on_hold", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_taxcomputation_generate(self, member_client, tax_computation_a):
        resp = member_client.post(reverse("hrm:taxcomputation_generate", args=[tax_computation_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_taxcomputation_link_form16(self, member_client, tax_computation_a):
        resp = member_client.post(reverse("hrm:taxcomputation_link_form16", args=[tax_computation_a.pk]))
        assert resp.status_code == 403
        tax_computation_a.refresh_from_db()
        assert tax_computation_a.statutory_return_id is None

    def test_non_admin_can_still_view_lists(self, member_client, tax_declaration_a, tax_computation_a):
        """Plain @login_required reads (list/detail) stay open to non-admin tenant members."""
        resp = member_client.get(reverse("hrm:investmentdeclaration_list"))
        assert resp.status_code == 200
        resp = member_client.get(reverse("hrm:taxcomputation_list"))
        assert resp.status_code == 200

    def test_non_admin_can_still_submit_own_declaration(self, member_client, tenant_a, employee_a):
        """Submit is plain @login_required (not admin-gated) — any tenant member can submit their own
        draft declaration; only LOCK is admin-only."""
        from apps.hrm.models import InvestmentDeclaration
        decl = InvestmentDeclaration.objects.create(
            tenant=tenant_a, employee=employee_a, financial_year="2023-24", status="draft")
        resp = member_client.post(reverse("hrm:investmentdeclaration_submit", args=[decl.pk]))
        assert resp.status_code == 302
        decl.refresh_from_db()
        assert decl.status == "submitted"


# ================================================================ CSRF enforcement
class TestTaxCSRFEnforcement:
    def test_taxregimeconfig_delete_enforces_csrf(self, admin_user, old_regime_config_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:taxregimeconfig_delete", args=[old_regime_config_a.pk]))
        assert resp.status_code == 403

    def test_taxslabband_create_enforces_csrf(self, admin_user, old_regime_config_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:taxslabband_create", args=[old_regime_config_a.pk]), {
            "income_from": "0", "income_to": "100000", "rate_percent": "0", "sequence": "1",
        })
        assert resp.status_code == 403

    def test_taxslabband_delete_enforces_csrf(self, admin_user, old_regime_config_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        band = old_regime_config_a.slab_bands.first()
        resp = c.post(reverse("hrm:taxslabband_delete", args=[old_regime_config_a.pk, band.pk]))
        assert resp.status_code == 403

    def test_investmentdeclaration_delete_enforces_csrf(self, admin_user, draft_declaration_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:investmentdeclaration_delete", args=[draft_declaration_a.pk]))
        assert resp.status_code == 403

    def test_investmentdeclaration_submit_enforces_csrf(self, admin_user, draft_declaration_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:investmentdeclaration_submit", args=[draft_declaration_a.pk]))
        assert resp.status_code == 403

    def test_investmentdeclaration_lock_enforces_csrf(self, admin_user, tax_declaration_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:investmentdeclaration_lock", args=[tax_declaration_a.pk]))
        assert resp.status_code == 403

    def test_investmentdeclarationline_create_enforces_csrf(self, admin_user, draft_declaration_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:investmentdeclarationline_create", args=[draft_declaration_a.pk]), {
                "section_code": "80c", "declared_amount": "1000",
            })
        assert resp.status_code == 403

    def test_investmentdeclarationline_delete_enforces_csrf(self, admin_user, draft_declaration_a, tenant_a):
        from apps.hrm.models import InvestmentDeclarationLine
        line = InvestmentDeclarationLine.objects.create(
            tenant=tenant_a, declaration=draft_declaration_a, section_code="80c",
            declared_amount=Decimal("1000"))
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:investmentdeclarationline_delete", args=[draft_declaration_a.pk, line.pk]))
        assert resp.status_code == 403

    def test_investmentproof_upload_enforces_csrf(self, admin_user, line_80c_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        f = SimpleUploadedFile("csrf.pdf", b"%PDF-1.4", content_type="application/pdf")
        resp = c.post(reverse("hrm:investmentproof_upload", args=[line_80c_a.pk]), {
            "file": f, "title": "CSRF Test", "amount": "1", "notes": "",
        })
        assert resp.status_code == 403

    def test_investmentproof_verify_enforces_csrf(self, admin_user, pending_proof_80c_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403

    def test_investmentproof_reject_enforces_csrf(self, admin_user, pending_proof_80c_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:investmentproof_reject", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403

    def test_investmentproof_on_hold_enforces_csrf(self, admin_user, pending_proof_80c_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:investmentproof_on_hold", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403

    def test_taxcomputation_delete_enforces_csrf(self, admin_user, tax_computation_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:taxcomputation_delete", args=[tax_computation_a.pk]))
        assert resp.status_code == 403

    def test_taxcomputation_generate_enforces_csrf(self, admin_user, tax_computation_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:taxcomputation_generate", args=[tax_computation_a.pk]))
        assert resp.status_code == 403

    def test_taxcomputation_link_form16_enforces_csrf(self, admin_user, tax_computation_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:taxcomputation_link_form16", args=[tax_computation_a.pk]))
        assert resp.status_code == 403
