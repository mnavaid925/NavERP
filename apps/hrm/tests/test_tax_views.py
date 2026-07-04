"""Tests for HRM 3.16 Tax & Investment views: TaxRegimeConfig (+ inline TaxSlabBand) CRUD +
tax_regime_comparison; InvestmentDeclaration CRUD + submit/lock workflow + inline lines
(gated by is_editable); InvestmentProof upload (proof-window-gated) + verify/reject/on_hold;
TaxComputation CRUD + generate/link_form16/form16_partb. Bounded-query N+1 guards."""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ TaxRegimeConfig CRUD
class TestTaxRegimeConfigListView:
    def test_list_200(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert old_regime_config_a.pk in pks

    def test_list_filter_by_regime(self, client_a, old_regime_config_a, new_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_list"), {"regime": "old"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert old_regime_config_a.pk in pks
        assert new_regime_config_a.pk not in pks

    def test_list_search_by_financial_year(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_list"), {"q": "2025-26"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert old_regime_config_a.pk in pks

    def test_list_has_regime_choices(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_list"))
        assert "regime_choices" in resp.context


class TestTaxRegimeConfigCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import TaxRegimeConfig
        resp = client_a.post(reverse("hrm:taxregimeconfig_create"), {
            "financial_year": "2026-27", "regime": "new",
            "standard_deduction": "75000.00", "cess_rate": "4.00",
            "rebate_income_threshold": "1200000.00", "rebate_max_tax": "60000.00",
            "tax_law_reference": "",
        })
        assert resp.status_code == 302
        cfg = TaxRegimeConfig.objects.filter(tenant=tenant_a, financial_year="2026-27").first()
        assert cfg is not None
        assert cfg.tenant_id == tenant_a.pk


class TestTaxRegimeConfigDetailEditDelete:
    def test_detail_200(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_detail", args=[old_regime_config_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_slab_bands_and_band_form(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_detail", args=[old_regime_config_a.pk]))
        assert "slab_bands" in resp.context
        assert "band_form" in resp.context
        assert resp.context["slab_bands"].count() == 4

    def test_edit_get_200(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_edit", args=[old_regime_config_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, old_regime_config_a):
        resp = client_a.post(reverse("hrm:taxregimeconfig_edit", args=[old_regime_config_a.pk]), {
            "financial_year": "2025-26", "regime": "old",
            "standard_deduction": "55000.00", "cess_rate": "4.00",
            "rebate_income_threshold": "500000.00", "rebate_max_tax": "12500.00",
            "tax_law_reference": "",
        })
        assert resp.status_code == 302
        old_regime_config_a.refresh_from_db()
        assert old_regime_config_a.standard_deduction == Decimal("55000.00")

    def test_delete_post_removes(self, client_a, old_regime_config_a):
        from apps.hrm.models import TaxRegimeConfig
        pk = old_regime_config_a.pk
        resp = client_a.post(reverse("hrm:taxregimeconfig_delete", args=[pk]))
        assert resp.status_code == 302
        assert not TaxRegimeConfig.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxregimeconfig_delete", args=[old_regime_config_a.pk]))
        assert resp.status_code == 405


# ================================================================ TaxSlabBand inline management
class TestTaxSlabBandInline:
    def test_create_adds_band(self, client_a, old_regime_config_a, tenant_a):
        from apps.hrm.models import TaxSlabBand
        resp = client_a.post(
            reverse("hrm:taxslabband_create", args=[old_regime_config_a.pk]), {
                "income_from": "2000000", "income_to": "", "rate_percent": "35", "sequence": "5",
            })
        assert resp.status_code == 302
        assert TaxSlabBand.objects.filter(tenant=tenant_a, config=old_regime_config_a,
                                          rate_percent=Decimal("35")).exists()

    def test_create_get_not_allowed(self, client_a, old_regime_config_a):
        resp = client_a.get(reverse("hrm:taxslabband_create", args=[old_regime_config_a.pk]))
        assert resp.status_code == 405

    def test_edit_get_200(self, client_a, old_regime_config_a):
        band = old_regime_config_a.slab_bands.first()
        resp = client_a.get(reverse("hrm:taxslabband_edit", args=[old_regime_config_a.pk, band.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, old_regime_config_a):
        band = old_regime_config_a.slab_bands.first()
        resp = client_a.post(
            reverse("hrm:taxslabband_edit", args=[old_regime_config_a.pk, band.pk]), {
                "income_from": "0", "income_to": "300000", "rate_percent": "0", "sequence": "1",
            })
        assert resp.status_code == 302
        band.refresh_from_db()
        assert band.income_to == Decimal("300000.00")

    def test_delete_post_removes(self, client_a, old_regime_config_a):
        from apps.hrm.models import TaxSlabBand
        band = old_regime_config_a.slab_bands.first()
        pk = band.pk
        resp = client_a.post(reverse("hrm:taxslabband_delete", args=[old_regime_config_a.pk, pk]))
        assert resp.status_code == 302
        assert not TaxSlabBand.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, old_regime_config_a):
        band = old_regime_config_a.slab_bands.first()
        resp = client_a.get(reverse("hrm:taxslabband_delete", args=[old_regime_config_a.pk, band.pk]))
        assert resp.status_code == 405


# ================================================================ tax_regime_comparison
class TestTaxRegimeComparisonView:
    def test_no_computation_selected_200(self, client_a):
        resp = client_a.get(reverse("hrm:tax_regime_comparison"))
        assert resp.status_code == 200
        assert resp.context["comp"] is None

    def test_with_computation_selected_has_breakdown(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:tax_regime_comparison"), {"computation": tax_computation_a.pk})
        assert resp.status_code == 200
        assert resp.context["comp"].pk == tax_computation_a.pk
        assert resp.context["breakdown"]["tax_old"] == Decimal("52520.00")
        assert resp.context["breakdown"]["tax_new"] == Decimal("0.00")

    def test_non_digit_computation_param_ignored_not_500(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:tax_regime_comparison"), {"computation": "abc"})
        assert resp.status_code == 200
        assert resp.context["comp"] is None


# ================================================================ InvestmentDeclaration CRUD
class TestInvestmentDeclarationListView:
    def test_list_200(self, client_a, tax_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, tax_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tax_declaration_a.pk in pks

    def test_list_filter_by_status(self, client_a, tax_declaration_a, draft_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_declaration_a.pk in pks
        assert tax_declaration_a.pk not in pks

    def test_list_filter_by_regime(self, client_a, tax_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_list"), {"regime_elected": "old"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tax_declaration_a.pk in pks

    def test_list_has_choices_context(self, client_a, tax_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_list"))
        assert "status_choices" in resp.context
        assert "regime_choices" in resp.context
        assert "employees" in resp.context


class TestInvestmentDeclarationCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import InvestmentDeclaration
        resp = client_a.post(reverse("hrm:investmentdeclaration_create"), {
            "employee": employee_a.pk, "financial_year": "2024-25", "regime_elected": "new",
            "declaration_window_open": "", "declaration_window_close": "",
            "proof_window_open": "", "proof_window_close": "",
            "previous_employer_income": "0", "previous_employer_tds": "0", "notes": "",
        })
        assert resp.status_code == 302
        decl = InvestmentDeclaration.objects.filter(tenant=tenant_a, financial_year="2024-25").first()
        assert decl is not None
        assert decl.tenant_id == tenant_a.pk
        assert decl.number.startswith("ITD-")

    def test_post_missing_employee_rejected(self, client_a, tenant_a):
        resp = client_a.post(reverse("hrm:investmentdeclaration_create"), {
            "financial_year": "2024-25", "regime_elected": "new",
            "previous_employer_income": "0", "previous_employer_tds": "0", "notes": "",
        })
        assert resp.status_code == 200  # re-rendered with form errors


class TestInvestmentDeclarationDetailEditDelete:
    def test_detail_200(self, client_a, tax_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_detail", args=[tax_declaration_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_lines_proofs_line_form(self, client_a, tax_declaration_a, line_80c_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_detail", args=[tax_declaration_a.pk]))
        assert "lines" in resp.context
        assert "proofs" in resp.context
        assert "line_form" in resp.context

    def test_edit_get_200_when_draft(self, client_a, draft_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_edit", args=[draft_declaration_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_blocked_when_submitted(self, client_a, tax_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_edit", args=[tax_declaration_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:investmentdeclaration_detail", args=[tax_declaration_a.pk])

    def test_edit_post_updates_when_draft(self, client_a, draft_declaration_a):
        resp = client_a.post(
            reverse("hrm:investmentdeclaration_edit", args=[draft_declaration_a.pk]), {
                "employee": draft_declaration_a.employee_id, "financial_year": "2025-26",
                "regime_elected": "old", "declaration_window_open": "", "declaration_window_close": "",
                "proof_window_open": "", "proof_window_close": "",
                "previous_employer_income": "100000", "previous_employer_tds": "0", "notes": "Updated",
            })
        assert resp.status_code == 302
        draft_declaration_a.refresh_from_db()
        assert draft_declaration_a.previous_employer_income == Decimal("100000.00")

    def test_delete_post_removes_when_draft(self, client_a, draft_declaration_a):
        from apps.hrm.models import InvestmentDeclaration
        pk = draft_declaration_a.pk
        resp = client_a.post(reverse("hrm:investmentdeclaration_delete", args=[pk]))
        assert resp.status_code == 302
        assert not InvestmentDeclaration.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_submitted(self, client_a, tax_declaration_a):
        from apps.hrm.models import InvestmentDeclaration
        resp = client_a.post(reverse("hrm:investmentdeclaration_delete", args=[tax_declaration_a.pk]))
        assert resp.status_code == 302
        assert InvestmentDeclaration.objects.filter(pk=tax_declaration_a.pk).exists()

    def test_delete_blocked_when_tax_computation_linked(self, client_a, tax_declaration_a, tax_computation_a):
        """PROTECT pre-check (code-reviewer-requested): a friendly redirect+message, never a 500."""
        from apps.hrm.models import InvestmentDeclaration
        # Force to draft to isolate the PROTECT guard from the is_editable guard.
        tax_declaration_a.status = "draft"
        tax_declaration_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:investmentdeclaration_delete", args=[tax_declaration_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:investmentdeclaration_detail", args=[tax_declaration_a.pk])
        assert InvestmentDeclaration.objects.filter(pk=tax_declaration_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, draft_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_delete", args=[draft_declaration_a.pk]))
        assert resp.status_code == 405


# ================================================================ InvestmentDeclaration workflow
class TestInvestmentDeclarationSubmitLock:
    def test_submit_draft_to_submitted(self, client_a, draft_declaration_a):
        resp = client_a.post(reverse("hrm:investmentdeclaration_submit", args=[draft_declaration_a.pk]))
        assert resp.status_code == 302
        draft_declaration_a.refresh_from_db()
        assert draft_declaration_a.status == "submitted"
        assert draft_declaration_a.submitted_at is not None

    def test_submit_noop_when_already_submitted(self, client_a, tax_declaration_a):
        resp = client_a.post(reverse("hrm:investmentdeclaration_submit", args=[tax_declaration_a.pk]))
        assert resp.status_code == 302
        tax_declaration_a.refresh_from_db()
        assert tax_declaration_a.status == "submitted"

    def test_submit_get_not_allowed(self, client_a, draft_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_submit", args=[draft_declaration_a.pk]))
        assert resp.status_code == 405

    def test_lock_submitted_to_locked_by_admin(self, client_a, tax_declaration_a):
        resp = client_a.post(reverse("hrm:investmentdeclaration_lock", args=[tax_declaration_a.pk]))
        assert resp.status_code == 302
        tax_declaration_a.refresh_from_db()
        assert tax_declaration_a.status == "locked"

    def test_lock_noop_when_draft(self, client_a, draft_declaration_a):
        resp = client_a.post(reverse("hrm:investmentdeclaration_lock", args=[draft_declaration_a.pk]))
        assert resp.status_code == 302
        draft_declaration_a.refresh_from_db()
        assert draft_declaration_a.status == "draft"

    def test_lock_403_for_non_admin(self, member_client, tax_declaration_a):
        resp = member_client.post(reverse("hrm:investmentdeclaration_lock", args=[tax_declaration_a.pk]))
        assert resp.status_code == 403
        tax_declaration_a.refresh_from_db()
        assert tax_declaration_a.status == "submitted"

    def test_lock_get_not_allowed(self, client_a, tax_declaration_a):
        resp = client_a.get(reverse("hrm:investmentdeclaration_lock", args=[tax_declaration_a.pk]))
        assert resp.status_code == 405

    def test_locked_declaration_lines_are_immutable(self, client_a, tax_declaration_a, line_80c_a):
        tax_declaration_a.status = "locked"
        tax_declaration_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_edit", args=[tax_declaration_a.pk, line_80c_a.pk]), {
                "section_code": "80c", "declared_amount": "999999.00",
            })
        assert resp.status_code == 302
        line_80c_a.refresh_from_db()
        assert line_80c_a.declared_amount == Decimal("150000.00")

    def test_locked_declaration_line_create_blocked(self, client_a, tax_declaration_a):
        from apps.hrm.models import InvestmentDeclarationLine
        tax_declaration_a.status = "locked"
        tax_declaration_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_create", args=[tax_declaration_a.pk]), {
                "section_code": "lta", "declared_amount": "5000",
            })
        assert resp.status_code == 302
        assert not InvestmentDeclarationLine.objects.filter(
            declaration=tax_declaration_a, section_code="lta").exists()

    def test_locked_declaration_line_delete_blocked(self, client_a, tax_declaration_a, line_80c_a):
        from apps.hrm.models import InvestmentDeclarationLine
        tax_declaration_a.status = "locked"
        tax_declaration_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_delete", args=[tax_declaration_a.pk, line_80c_a.pk]))
        assert resp.status_code == 302
        assert InvestmentDeclarationLine.objects.filter(pk=line_80c_a.pk).exists()


# ================================================================ InvestmentDeclarationLine inline
class TestInvestmentDeclarationLineInline:
    def test_create_adds_line_when_draft(self, client_a, draft_declaration_a, tenant_a):
        from apps.hrm.models import InvestmentDeclarationLine
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_create", args=[draft_declaration_a.pk]), {
                "section_code": "lta", "declared_amount": "5000",
            })
        assert resp.status_code == 302
        assert InvestmentDeclarationLine.objects.filter(
            tenant=tenant_a, declaration=draft_declaration_a, section_code="lta").exists()

    def test_create_duplicate_section_shows_friendly_message_not_500(
        self, client_a, draft_declaration_a, tenant_a,
    ):
        """A duplicate (tenant, declaration, section_code) POST redirects back with a friendly message,
        not a 500/400. ``investmentdeclarationline_create`` wraps ``form.save()`` in its own
        ``transaction.atomic()`` savepoint, so the duplicate-section IntegrityError rolls back only that
        insert instead of poisoning the whole request transaction (which previously broke the
        end-of-request session save → 400). No second row is created."""
        from apps.hrm.models import InvestmentDeclarationLine
        InvestmentDeclarationLine.objects.create(
            tenant=tenant_a, declaration=draft_declaration_a, section_code="80c",
            declared_amount=Decimal("10000"))
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_create", args=[draft_declaration_a.pk]), {
                "section_code": "80c", "declared_amount": "20000",
            })
        assert resp.status_code == 302  # friendly redirect back to the declaration detail
        # The duplicate was rejected — still exactly one 80C line, with the original amount.
        lines = InvestmentDeclarationLine.objects.filter(
            tenant=tenant_a, declaration=draft_declaration_a, section_code="80c")
        assert lines.count() == 1
        assert lines.first().declared_amount == Decimal("10000")

    def test_edit_get_200(self, client_a, draft_declaration_a):
        from apps.hrm.models import InvestmentDeclarationLine
        line = InvestmentDeclarationLine.objects.create(
            tenant=draft_declaration_a.tenant, declaration=draft_declaration_a, section_code="80c",
            declared_amount=Decimal("10000"))
        resp = client_a.get(
            reverse("hrm:investmentdeclarationline_edit", args=[draft_declaration_a.pk, line.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_when_draft(self, client_a, draft_declaration_a):
        from apps.hrm.models import InvestmentDeclarationLine
        line = InvestmentDeclarationLine.objects.create(
            tenant=draft_declaration_a.tenant, declaration=draft_declaration_a, section_code="80c",
            declared_amount=Decimal("10000"))
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_edit", args=[draft_declaration_a.pk, line.pk]), {
                "section_code": "80c", "declared_amount": "25000",
            })
        assert resp.status_code == 302
        line.refresh_from_db()
        assert line.declared_amount == Decimal("25000.00")

    def test_delete_post_removes_when_draft(self, client_a, draft_declaration_a):
        from apps.hrm.models import InvestmentDeclarationLine
        line = InvestmentDeclarationLine.objects.create(
            tenant=draft_declaration_a.tenant, declaration=draft_declaration_a, section_code="80c",
            declared_amount=Decimal("10000"))
        pk = line.pk
        resp = client_a.post(
            reverse("hrm:investmentdeclarationline_delete", args=[draft_declaration_a.pk, pk]))
        assert resp.status_code == 302
        assert not InvestmentDeclarationLine.objects.filter(pk=pk).exists()


# ================================================================ InvestmentProof upload + workflow
class TestInvestmentProofUpload:
    def test_upload_get_200_when_window_open(self, client_a, tax_declaration_a, line_80c_a):
        resp = client_a.get(reverse("hrm:investmentproof_upload", args=[line_80c_a.pk]))
        assert resp.status_code == 200

    def test_upload_post_creates_when_window_open(self, client_a, tax_declaration_a, line_80c_a, tenant_a):
        from apps.hrm.models import InvestmentProof
        f = SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        resp = client_a.post(reverse("hrm:investmentproof_upload", args=[line_80c_a.pk]), {
            "file": f, "title": "Insurance Receipt", "amount": "150000", "notes": "",
        })
        assert resp.status_code == 302
        assert InvestmentProof.objects.filter(tenant=tenant_a, declaration_line=line_80c_a,
                                              title="Insurance Receipt").exists()

    def test_upload_blocked_before_window_open(self, client_a, tax_declaration_a, line_80c_a):
        tax_declaration_a.proof_window_open = datetime.date(2099, 1, 1)
        tax_declaration_a.proof_window_close = datetime.date(2099, 12, 31)
        tax_declaration_a.save(update_fields=["proof_window_open", "proof_window_close"])
        resp = client_a.get(reverse("hrm:investmentproof_upload", args=[line_80c_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:investmentdeclaration_detail", args=[tax_declaration_a.pk])

    def test_upload_blocked_after_window_close(self, client_a, tax_declaration_a, line_80c_a):
        tax_declaration_a.proof_window_open = datetime.date(2020, 1, 1)
        tax_declaration_a.proof_window_close = datetime.date(2020, 1, 31)
        tax_declaration_a.save(update_fields=["proof_window_open", "proof_window_close"])
        f = SimpleUploadedFile("late.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        resp = client_a.post(reverse("hrm:investmentproof_upload", args=[line_80c_a.pk]), {
            "file": f, "title": "Late Upload", "amount": "1000", "notes": "",
        })
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:investmentdeclaration_detail", args=[tax_declaration_a.pk])
        from apps.hrm.models import InvestmentProof
        assert not InvestmentProof.objects.filter(title="Late Upload").exists()

    def test_upload_allowed_with_no_window_configured(self, client_a, tenant_a, employee_a):
        """No proof window set at all -> upload allowed by default (open)."""
        from apps.hrm.models import InvestmentDeclaration, InvestmentDeclarationLine, InvestmentProof
        decl = InvestmentDeclaration.objects.create(
            tenant=tenant_a, employee=employee_a, financial_year="2027-28")
        line = InvestmentDeclarationLine.objects.create(
            tenant=tenant_a, declaration=decl, section_code="80c", declared_amount=Decimal("1000"))
        f = SimpleUploadedFile("open.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        resp = client_a.post(reverse("hrm:investmentproof_upload", args=[line.pk]), {
            "file": f, "title": "Open Window Upload", "amount": "1000", "notes": "",
        })
        assert resp.status_code == 302
        assert InvestmentProof.objects.filter(declaration_line=line, title="Open Window Upload").exists()


class TestInvestmentProofListDetail:
    def test_list_200(self, client_a, pending_proof_80c_a):
        resp = client_a.get(reverse("hrm:investmentproof_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, pending_proof_80c_a):
        resp = client_a.get(reverse("hrm:investmentproof_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_proof_80c_a.pk in pks

    def test_list_filter_by_status(self, client_a, pending_proof_80c_a, verified_proof_80c_a):
        resp = client_a.get(reverse("hrm:investmentproof_list"), {"verification_status": "verified"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert verified_proof_80c_a.pk in pks
        assert pending_proof_80c_a.pk not in pks

    def test_list_has_status_choices(self, client_a, pending_proof_80c_a):
        resp = client_a.get(reverse("hrm:investmentproof_list"))
        assert "verification_status_choices" in resp.context

    def test_detail_200(self, client_a, pending_proof_80c_a):
        resp = client_a.get(reverse("hrm:investmentproof_detail", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 200


class TestInvestmentProofVerifyRejectOnHold:
    def test_verify_by_admin(self, client_a, pending_proof_80c_a, line_80c_a):
        resp = client_a.post(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 302
        pending_proof_80c_a.refresh_from_db()
        assert pending_proof_80c_a.verification_status == "verified"
        assert pending_proof_80c_a.verified_by_id is not None
        assert pending_proof_80c_a.verified_at is not None

    def test_verify_rolls_up_line_verified_amount(self, client_a, pending_proof_80c_a, line_80c_a):
        assert line_80c_a.verified_amount is None
        client_a.post(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        line_80c_a.refresh_from_db()
        assert line_80c_a.verified_amount == Decimal("150000.00")

    def test_reject_by_admin_with_reason(self, client_a, pending_proof_80c_a):
        resp = client_a.post(reverse("hrm:investmentproof_reject", args=[pending_proof_80c_a.pk]),
                             {"rejection_reason": "Illegible scan"})
        assert resp.status_code == 302
        pending_proof_80c_a.refresh_from_db()
        assert pending_proof_80c_a.verification_status == "rejected"
        assert pending_proof_80c_a.rejection_reason == "Illegible scan"

    def test_on_hold_by_admin(self, client_a, pending_proof_80c_a):
        resp = client_a.post(reverse("hrm:investmentproof_on_hold", args=[pending_proof_80c_a.pk]),
                             {"rejection_reason": "Need clarification"})
        assert resp.status_code == 302
        pending_proof_80c_a.refresh_from_db()
        assert pending_proof_80c_a.verification_status == "on_hold"

    def test_on_hold_can_later_be_verified(self, client_a, pending_proof_80c_a):
        client_a.post(reverse("hrm:investmentproof_on_hold", args=[pending_proof_80c_a.pk]))
        resp = client_a.post(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 302
        pending_proof_80c_a.refresh_from_db()
        assert pending_proof_80c_a.verification_status == "verified"

    def test_terminal_state_guard_blocks_re_verify_of_verified(self, client_a, verified_proof_80c_a):
        original_verified_at = verified_proof_80c_a.verified_at
        resp = client_a.post(reverse("hrm:investmentproof_reject", args=[verified_proof_80c_a.pk]),
                             {"rejection_reason": "Trying to flip it"})
        assert resp.status_code == 302
        verified_proof_80c_a.refresh_from_db()
        assert verified_proof_80c_a.verification_status == "verified"
        assert verified_proof_80c_a.verified_at == original_verified_at

    def test_terminal_state_guard_blocks_re_decide_of_rejected(self, client_a, pending_proof_80c_a):
        client_a.post(reverse("hrm:investmentproof_reject", args=[pending_proof_80c_a.pk]))
        resp = client_a.post(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 302
        pending_proof_80c_a.refresh_from_db()
        assert pending_proof_80c_a.verification_status == "rejected"

    def test_verify_403_for_non_admin(self, member_client, pending_proof_80c_a):
        resp = member_client.post(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403
        pending_proof_80c_a.refresh_from_db()
        assert pending_proof_80c_a.verification_status == "pending"

    def test_reject_403_for_non_admin(self, member_client, pending_proof_80c_a):
        resp = member_client.post(reverse("hrm:investmentproof_reject", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403

    def test_on_hold_403_for_non_admin(self, member_client, pending_proof_80c_a):
        resp = member_client.post(reverse("hrm:investmentproof_on_hold", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 403

    def test_verify_get_not_allowed(self, client_a, pending_proof_80c_a):
        resp = client_a.get(reverse("hrm:investmentproof_verify", args=[pending_proof_80c_a.pk]))
        assert resp.status_code == 405


# ================================================================ TaxComputation CRUD
class TestTaxComputationListView:
    def test_list_200(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tax_computation_a.pk in pks

    def test_list_filter_by_type(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_list"), {"computation_type": "final"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tax_computation_a.pk in pks

    def test_list_has_choices_context(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_list"))
        assert "computation_type_choices" in resp.context
        assert "employees" in resp.context


class TestTaxComputationCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:taxcomputation_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a, tax_declaration_a):
        from apps.hrm.models import TaxComputation
        resp = client_a.post(reverse("hrm:taxcomputation_create"), {
            "employee": employee_a.pk, "declaration": tax_declaration_a.pk,
            "computation_type": "provisional", "remaining_pay_periods": "12", "notes": "",
        })
        assert resp.status_code == 302
        comp = TaxComputation.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert comp is not None
        assert comp.number.startswith("TXC-")
        assert comp.tenant_id == tenant_a.pk


class TestTaxComputationDetailEditDelete:
    def test_detail_200(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_detail", args=[tax_computation_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_breakdown_and_lines(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_detail", args=[tax_computation_a.pk]))
        assert "breakdown" in resp.context
        assert "lines" in resp.context
        assert resp.context["breakdown"]["tax_old"] == Decimal("52520.00")

    def test_edit_get_200(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_edit", args=[tax_computation_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, tax_computation_a):
        resp = client_a.post(reverse("hrm:taxcomputation_edit", args=[tax_computation_a.pk]), {
            "employee": tax_computation_a.employee_id, "declaration": tax_computation_a.declaration_id,
            "computation_type": "final", "remaining_pay_periods": "3", "notes": "Edited",
        })
        assert resp.status_code == 302
        tax_computation_a.refresh_from_db()
        assert tax_computation_a.remaining_pay_periods == 3

    def test_delete_post_removes(self, client_a, tax_computation_a):
        from apps.hrm.models import TaxComputation
        pk = tax_computation_a.pk
        resp = client_a.post(reverse("hrm:taxcomputation_delete", args=[pk]))
        assert resp.status_code == 302
        assert not TaxComputation.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_delete", args=[tax_computation_a.pk]))
        assert resp.status_code == 405


# ================================================================ TaxComputation generate / link_form16
class TestTaxComputationGenerate:
    def test_generate_recomputes(self, client_a, tax_computation_a):
        tax_computation_a.tax_payable = Decimal("0")
        tax_computation_a.save(update_fields=["tax_payable"])
        resp = client_a.post(reverse("hrm:taxcomputation_generate", args=[tax_computation_a.pk]))
        assert resp.status_code == 302
        tax_computation_a.refresh_from_db()
        assert tax_computation_a.tax_payable == Decimal("52520.00")

    def test_generate_final_blocked_when_proof_window_open(
        self, client_a, tax_declaration_a, tax_computation_a,
    ):
        tax_declaration_a.proof_window_close = datetime.date(2099, 12, 31)
        tax_declaration_a.save(update_fields=["proof_window_close"])
        resp = client_a.post(reverse("hrm:taxcomputation_generate", args=[tax_computation_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:taxcomputation_detail", args=[tax_computation_a.pk])

    def test_generate_403_for_non_admin(self, member_client, tax_computation_a):
        resp = member_client.post(reverse("hrm:taxcomputation_generate", args=[tax_computation_a.pk]))
        assert resp.status_code == 403

    def test_generate_get_not_allowed(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_generate", args=[tax_computation_a.pk]))
        assert resp.status_code == 405


class TestTaxComputationLinkForm16View:
    def test_link_form16_creates_and_links(self, client_a, tax_computation_a):
        from apps.hrm.models import StatutoryReturn
        resp = client_a.post(reverse("hrm:taxcomputation_link_form16", args=[tax_computation_a.pk]))
        assert resp.status_code == 302
        tax_computation_a.refresh_from_db()
        assert tax_computation_a.statutory_return_id is not None
        assert StatutoryReturn.objects.filter(pk=tax_computation_a.statutory_return_id,
                                              scheme="tds_form16").exists()

    def test_link_form16_403_for_non_admin(self, member_client, tax_computation_a):
        resp = member_client.post(reverse("hrm:taxcomputation_link_form16", args=[tax_computation_a.pk]))
        assert resp.status_code == 403

    def test_link_form16_get_not_allowed(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:taxcomputation_link_form16", args=[tax_computation_a.pk]))
        assert resp.status_code == 405


class TestForm16PartBView:
    def test_form16_partb_200(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:form16_partb", args=[tax_computation_a.pk]))
        assert resp.status_code == 200

    def test_form16_partb_context(self, client_a, tax_computation_a):
        resp = client_a.get(reverse("hrm:form16_partb", args=[tax_computation_a.pk]))
        assert "breakdown" in resp.context
        assert "lines" in resp.context
        assert "config" in resp.context

    def test_form16_partb_accessible_by_non_admin(self, member_client, tax_computation_a):
        """Plain @login_required read — no admin gate on the report itself."""
        resp = member_client.get(reverse("hrm:form16_partb", args=[tax_computation_a.pk]))
        assert resp.status_code == 200


# ================================================================ Bounded queries (N+1 guard)
class TestTaxQueryCount:
    """The engine was memoized from ~60 to single-digit queries per breakdown call
    (TaxComputation._engine_cache) — these pin a generous-but-real ceiling (measured: detail=15,
    form16_partb=17, regime_comparison=16, incl. session/auth/tenant-resolution overhead) so a future
    N+1 regression (e.g. re-adding an unmemoized per-property query) still trips the guard."""

    def test_taxcomputation_detail_bounded_queries(
        self, client_a, tax_computation_a, django_assert_max_num_queries,
    ):
        with django_assert_max_num_queries(18):
            client_a.get(reverse("hrm:taxcomputation_detail", args=[tax_computation_a.pk]))

    def test_form16_partb_bounded_queries(
        self, client_a, tax_computation_a, django_assert_max_num_queries,
    ):
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:form16_partb", args=[tax_computation_a.pk]))

    def test_tax_regime_comparison_bounded_queries(
        self, client_a, tax_computation_a, django_assert_max_num_queries,
    ):
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:tax_regime_comparison"), {"computation": tax_computation_a.pk})

    def test_computation_breakdown_helper_bounded_queries(self, tax_computation_a):
        """Direct unit test of the memoized engine's query count (performance-reviewer-requested) —
        the per-instance _engine_cache means calling all 9 breakdown properties fires a small, bounded
        number of DB queries, not one fresh query per property access."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        from apps.hrm.views import _computation_breakdown
        with CaptureQueriesContext(connection) as ctx:
            _computation_breakdown(tax_computation_a)
        assert len(ctx.captured_queries) <= 10

    def test_taxregimeconfig_list_bounded_queries(
        self, client_a, tenant_a, django_assert_max_num_queries,
    ):
        from apps.hrm.models import TaxRegimeConfig
        for i in range(5):
            TaxRegimeConfig.objects.create(
                tenant=tenant_a, financial_year=f"202{i}-2{i+1}", regime="new" if i % 2 else "old")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:taxregimeconfig_list"))

    def test_investmentdeclaration_list_bounded_queries(
        self, client_a, tenant_a, employee_a, django_assert_max_num_queries,
    ):
        from apps.hrm.models import InvestmentDeclaration
        for i in range(5):
            InvestmentDeclaration.objects.create(
                tenant=tenant_a, employee=employee_a, financial_year=f"20{10+i}-{11+i}")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:investmentdeclaration_list"))

    def test_taxcomputation_list_bounded_queries(
        self, client_a, tenant_a, employee_a, django_assert_max_num_queries,
    ):
        from apps.hrm.models import InvestmentDeclaration, TaxComputation
        for i in range(5):
            decl = InvestmentDeclaration.objects.create(
                tenant=tenant_a, employee=employee_a, financial_year=f"20{20+i}-{21+i}")
            TaxComputation.objects.create(
                tenant=tenant_a, employee=employee_a, declaration=decl, computation_type="provisional")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:taxcomputation_list"))
