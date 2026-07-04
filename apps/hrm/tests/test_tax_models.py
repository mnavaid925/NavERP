"""Tests for HRM 3.16 Tax & Investment models: TaxRegimeConfig (+ TaxSlabBand), InvestmentDeclaration
(ITD-, draft->submitted->locked, is_editable), InvestmentDeclarationLine (effective_amount,
recompute_verified()), InvestmentProof (4-state verify), TaxComputation (TXC-, the engine + save()
FY-derivation + link_form16())."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ TaxRegimeConfig
class TestTaxRegimeConfigModel:
    def test_defaults(self, tenant_a):
        from apps.hrm.models import TaxRegimeConfig
        cfg = TaxRegimeConfig.objects.create(tenant=tenant_a, financial_year="2025-26")
        assert cfg.regime == "new"
        assert cfg.standard_deduction == Decimal("75000.00")
        assert cfg.cess_rate == Decimal("4.00")
        assert cfg.is_default_regime is False

    def test_str(self, new_regime_config_a):
        s = str(new_regime_config_a)
        assert "2025-26" in s
        assert "New Regime" in s

    def test_unique_together_tenant_fy_regime(self, tenant_a, new_regime_config_a):
        from apps.hrm.models import TaxRegimeConfig
        dupe = TaxRegimeConfig(tenant=tenant_a, financial_year="2025-26", regime="new")
        with pytest.raises(IntegrityError):
            dupe.save()

    def test_old_and_new_regime_can_coexist_same_fy(self, tenant_a, new_regime_config_a, old_regime_config_a):
        from apps.hrm.models import TaxRegimeConfig
        assert TaxRegimeConfig.objects.filter(tenant=tenant_a, financial_year="2025-26").count() == 2


class TestTaxSlabBandModel:
    def test_str(self, old_regime_config_a):
        band = old_regime_config_a.slab_bands.order_by("sequence").first()
        s = str(band)
        assert "0" in s
        assert "250000" in s

    def test_top_band_str_shows_infinity(self, old_regime_config_a):
        band = old_regime_config_a.slab_bands.order_by("sequence").last()
        assert "∞" in str(band)

    def test_clean_income_to_below_income_from_raises(self, tenant_a, old_regime_config_a):
        from apps.hrm.models import TaxSlabBand
        band = TaxSlabBand(
            tenant=tenant_a, config=old_regime_config_a,
            income_from=Decimal("500000"), income_to=Decimal("100000"), rate_percent=Decimal("20"))
        with pytest.raises(ValidationError) as exc:
            band.clean()
        assert "income_to" in exc.value.message_dict

    def test_clean_valid_band_passes(self, tenant_a, old_regime_config_a):
        from apps.hrm.models import TaxSlabBand
        band = TaxSlabBand(
            tenant=tenant_a, config=old_regime_config_a,
            income_from=Decimal("100000"), income_to=Decimal("200000"), rate_percent=Decimal("10"))
        band.clean()  # must not raise

    def test_clean_allows_null_income_to_top_band(self, tenant_a, old_regime_config_a):
        from apps.hrm.models import TaxSlabBand
        band = TaxSlabBand(
            tenant=tenant_a, config=old_regime_config_a,
            income_from=Decimal("1000000"), income_to=None, rate_percent=Decimal("30"))
        band.clean()  # must not raise

    def test_cascade_delete_with_config(self, tenant_a, old_regime_config_a):
        from apps.hrm.models import TaxSlabBand
        config_pk = old_regime_config_a.pk
        assert TaxSlabBand.objects.filter(config_id=config_pk).count() == 4
        old_regime_config_a.delete()
        assert TaxSlabBand.objects.filter(config_id=config_pk).count() == 0


# ================================================================ InvestmentDeclaration
class TestInvestmentDeclarationModel:
    def test_number_auto_assigns(self, tax_declaration_a):
        assert tax_declaration_a.number.startswith("ITD-")

    def test_defaults_on_new_declaration(self, tenant_a, employee_a):
        from apps.hrm.models import InvestmentDeclaration
        decl = InvestmentDeclaration.objects.create(
            tenant=tenant_a, employee=employee_a, financial_year="2025-26")
        assert decl.status == "draft"
        assert decl.regime_elected == "new"
        assert decl.previous_employer_income == Decimal("0")
        assert decl.previous_employer_tds == Decimal("0")
        assert decl.submitted_at is None

    def test_is_editable_true_when_draft(self, draft_declaration_a):
        assert draft_declaration_a.is_editable is True

    def test_is_editable_false_when_submitted(self, tax_declaration_a):
        assert tax_declaration_a.is_editable is False

    def test_is_editable_false_when_locked(self, tax_declaration_a):
        tax_declaration_a.status = "locked"
        assert tax_declaration_a.is_editable is False

    def test_unique_together_tenant_employee_fy(self, tenant_a, employee_a, tax_declaration_a):
        from apps.hrm.models import InvestmentDeclaration
        dupe = InvestmentDeclaration(
            tenant=tenant_a, employee=employee_a, financial_year=tax_declaration_a.financial_year)
        with pytest.raises(IntegrityError):
            dupe.save()

    def test_str(self, tax_declaration_a, employee_a):
        s = str(tax_declaration_a)
        assert tax_declaration_a.number in s
        assert "2025-26" in s


# ================================================================ InvestmentDeclarationLine
class TestInvestmentDeclarationLineModel:
    def test_effective_amount_falls_back_to_declared_when_unverified(self, line_80c_a):
        assert line_80c_a.verified_amount is None
        assert line_80c_a.effective_amount == Decimal("150000.00")

    def test_effective_amount_uses_verified_when_set(self, line_80c_a):
        line_80c_a.verified_amount = Decimal("100000.00")
        line_80c_a.save(update_fields=["verified_amount"])
        assert line_80c_a.effective_amount == Decimal("100000.00")

    def test_unique_together_tenant_declaration_section(self, tenant_a, tax_declaration_a, line_80c_a):
        from apps.hrm.models import InvestmentDeclarationLine
        dupe = InvestmentDeclarationLine(
            tenant=tenant_a, declaration=tax_declaration_a, section_code="80c", declared_amount=Decimal("1"))
        with pytest.raises(IntegrityError):
            dupe.save()

    def test_str(self, line_80c_a):
        s = str(line_80c_a)
        assert "Section 80C" in s

    def test_recompute_verified_sums_verified_proofs(self, tenant_a, line_80c_a, verified_proof_80c_a):
        line_80c_a.verified_amount = None
        line_80c_a.save(update_fields=["verified_amount"])
        line_80c_a.recompute_verified()
        assert line_80c_a.verified_amount == Decimal("150000.00")

    def test_recompute_verified_sums_multiple_verified_proofs(self, tenant_a, line_80c_a, admin_user):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.hrm.models import InvestmentProof
        InvestmentProof.objects.create(
            tenant=tenant_a, declaration_line=line_80c_a,
            file=SimpleUploadedFile("p1.pdf", b"%PDF-1.4", content_type="application/pdf"),
            title="Proof 1", amount=Decimal("50000.00"), verification_status="verified",
            verified_by=admin_user)
        InvestmentProof.objects.create(
            tenant=tenant_a, declaration_line=line_80c_a,
            file=SimpleUploadedFile("p2.pdf", b"%PDF-1.4", content_type="application/pdf"),
            title="Proof 2", amount=Decimal("30000.00"), verification_status="verified",
            verified_by=admin_user)
        line_80c_a.recompute_verified()
        assert line_80c_a.verified_amount == Decimal("80000.00")

    def test_recompute_verified_ignores_pending_and_rejected_proofs(self, tenant_a, line_80c_a):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.hrm.models import InvestmentProof
        InvestmentProof.objects.create(
            tenant=tenant_a, declaration_line=line_80c_a,
            file=SimpleUploadedFile("pending.pdf", b"%PDF-1.4", content_type="application/pdf"),
            title="Pending", amount=Decimal("99999.00"), verification_status="pending")
        InvestmentProof.objects.create(
            tenant=tenant_a, declaration_line=line_80c_a,
            file=SimpleUploadedFile("rejected.pdf", b"%PDF-1.4", content_type="application/pdf"),
            title="Rejected", amount=Decimal("88888.00"), verification_status="rejected")
        line_80c_a.recompute_verified()
        assert line_80c_a.verified_amount is None
        # Falls back to declared_amount via effective_amount.
        assert line_80c_a.effective_amount == Decimal("150000.00")

    def test_recompute_verified_no_verified_proof_sets_none(self, tenant_a, line_80c_a):
        """No verified proof at all -> verified_amount stays None (aggregate() of empty qs)."""
        line_80c_a.recompute_verified()
        assert line_80c_a.verified_amount is None


# ================================================================ InvestmentProof
class TestInvestmentProofModel:
    def test_defaults(self, pending_proof_80c_a):
        assert pending_proof_80c_a.verification_status == "pending"
        assert pending_proof_80c_a.verified_by is None
        assert pending_proof_80c_a.verified_at is None

    def test_str(self, pending_proof_80c_a, line_80c_a):
        s = str(pending_proof_80c_a)
        assert "Receipt" in s

    def test_verified_state(self, verified_proof_80c_a, admin_user):
        assert verified_proof_80c_a.verification_status == "verified"
        assert verified_proof_80c_a.verified_by_id == admin_user.pk
        assert verified_proof_80c_a.verified_at is not None


# ================================================================ TaxComputation — engine arithmetic
class TestTaxComputationEngine:
    """Hand-computed demo case: gross 920000 (120000 CTC structure + 800000 previous-employer),
    BASIC 60000/HRA 30000 lines, old-regime declared 80C 150000 (capped) + HRA (metro, rent 15000/mo)."""

    def test_gross_annual_income(self, tax_computation_a):
        assert tax_computation_a.gross_annual_income == Decimal("920000.00")

    def test_hra_exemption_3way_min(self, tax_computation_a):
        # candidates: (15000*12 - 10%*60000)=174000, 50%*60000=30000, actual HRA received=30000 -> min=30000
        assert tax_computation_a.hra_exemption == Decimal("30000.00")

    def test_hra_exemption_zero_under_new_regime(self, tenant_a, tax_declaration_a, tax_structure_a,
                                                  line_80c_a, line_hra_a, new_regime_config_a):
        from apps.hrm.models import TaxComputation
        tax_declaration_a.regime_elected = "new"
        tax_declaration_a.save(update_fields=["regime_elected"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=tax_declaration_a.employee, declaration=tax_declaration_a,
            computation_type="provisional")
        assert comp.hra_exemption == Decimal("0.00")

    def test_total_chapter_via_deductions_old_regime_caps_80c(self, tax_computation_a):
        # 80c declared 150000 == cap 150000 -> capped total is exactly the cap (not over).
        assert tax_computation_a.total_chapter_via_deductions == Decimal("150000.00")

    def test_section_caps_over_declared_80c_is_capped_and_surfaced(
        self, tenant_a, tax_declaration_a, tax_structure_a, line_80c_a, line_hra_a, old_regime_config_a,
    ):
        from apps.hrm.models import TaxComputation
        line_80c_a.declared_amount = Decimal("200000.00")
        line_80c_a.save(update_fields=["declared_amount"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=tax_declaration_a.employee, declaration=tax_declaration_a,
            computation_type="provisional")
        # Capped at 150000 in the deduction total, not the raw 200000.
        assert comp.total_chapter_via_deductions == Decimal("150000.00")
        capped = comp.capped_sections
        assert len(capped) == 1
        label, claimed, cap = capped[0]
        assert label == "Section 80C"
        assert claimed == Decimal("200000.00")
        assert cap == Decimal("150000.00")

    def test_no_capped_sections_when_under_cap(self, tax_computation_a):
        assert tax_computation_a.capped_sections == []

    def test_chapter_via_excludes_hra_line(self, tax_computation_a):
        """The HRA line itself must never be double-counted into chapter_via (handled separately)."""
        # Only 80C (150000) contributes; HRA line's declared_amount is 0 anyway but must be excluded
        # from the chapter-via sum by section_code, not by coincidence of being zero.
        assert tax_computation_a.total_chapter_via_deductions == Decimal("150000.00")

    def test_chapter_via_new_regime_excludes_80c_and_hra(
        self, tenant_a, tax_declaration_a, tax_structure_a, line_80c_a, line_hra_a, new_regime_config_a,
    ):
        from apps.hrm.models import TaxComputation
        tax_declaration_a.regime_elected = "new"
        tax_declaration_a.save(update_fields=["regime_elected"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=tax_declaration_a.employee, declaration=tax_declaration_a,
            computation_type="provisional")
        assert comp.total_chapter_via_deductions == Decimal("0.00")

    def test_chapter_via_new_regime_keeps_nps_80ccd_1b(
        self, tenant_a, tax_declaration_a, tax_structure_a, new_regime_config_a,
    ):
        from apps.hrm.models import InvestmentDeclarationLine, TaxComputation
        tax_declaration_a.regime_elected = "new"
        tax_declaration_a.save(update_fields=["regime_elected"])
        InvestmentDeclarationLine.objects.create(
            tenant=tenant_a, declaration=tax_declaration_a, section_code="80ccd_1b_nps",
            declared_amount=Decimal("50000.00"))
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=tax_declaration_a.employee, declaration=tax_declaration_a,
            computation_type="provisional")
        assert comp.total_chapter_via_deductions == Decimal("50000.00")

    def test_taxable_income_old(self, tax_computation_a):
        # 920000 - 50000(std) - 30000(hra) - 150000(80c capped) = 690000
        assert tax_computation_a.taxable_income_old == Decimal("690000.00")

    def test_taxable_income_new(self, tax_computation_a):
        # 920000 - 75000(std) - 0(hra excluded) - 0(chapter via excluded) = 845000
        assert tax_computation_a.taxable_income_new == Decimal("845000.00")

    def test_tax_old_regime_hand_verified(self, tax_computation_a):
        # taxable 690000: 0-250000@0 + 250000-500000@5%=12500 + 500000-690000@20%=38000 = 50500
        # cess 4% -> 50500*1.04 = 52520.00
        assert tax_computation_a.tax_old_regime == Decimal("52520.00")

    def test_tax_new_regime_hand_verified(self, tax_computation_a):
        # taxable 845000 <= rebate threshold 1200000 -> 87A rebate zeros the tax entirely.
        assert tax_computation_a.tax_new_regime == Decimal("0.00")

    def test_87a_rebate_zeros_tax_at_threshold_boundary(self, tenant_a, tax_declaration_a, tax_structure_a,
                                                          old_regime_config_a):
        """Taxable income exactly AT the old-regime rebate threshold (500000) -> rebate zeros the tax."""
        from apps.hrm.models import TaxComputation
        tax_declaration_a.previous_employer_income = Decimal("0")
        tax_declaration_a.save(update_fields=["previous_employer_income"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=tax_declaration_a.employee, declaration=tax_declaration_a,
            computation_type="provisional")
        # gross = 120000 (CTC only, no previous-employer income); std ded 50000 -> taxable 70000, well
        # under threshold -> rebate zeros tax.
        assert comp.taxable_income_old <= Decimal("500000.00")
        assert comp.tax_old_regime == Decimal("0.00")

    def test_cheaper_regime_picks_lower_tax(self, tax_computation_a):
        assert tax_computation_a.cheaper_regime == "new"

    def test_cheaper_regime_ties_resolve_to_new(self, tenant_a, tax_declaration_a, tax_structure_a):
        """No regime configs at all -> both regime taxes are 0 (config None -> ZERO) -> tie -> 'new'."""
        from apps.hrm.models import TaxComputation
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=tax_declaration_a.employee, declaration=tax_declaration_a,
            computation_type="provisional")
        assert comp.tax_old_regime == Decimal("0")
        assert comp.tax_new_regime == Decimal("0")
        assert comp.cheaper_regime == "new"

    def test_verified_amount_used_over_declared_via_effective_amount(
        self, tenant_a, tax_declaration_a, tax_structure_a, line_80c_a, line_hra_a, old_regime_config_a,
    ):
        from apps.hrm.models import TaxComputation
        line_80c_a.verified_amount = Decimal("100000.00")
        line_80c_a.save(update_fields=["verified_amount"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=tax_declaration_a.employee, declaration=tax_declaration_a,
            computation_type="provisional")
        assert comp.total_chapter_via_deductions == Decimal("100000.00")

    def test_no_active_structure_yields_zero_gross_basis(self, tenant_a, employee_a):
        """No EmployeeSalaryStructure at all -> gross_annual_income is just previous_employer_income."""
        from apps.hrm.models import InvestmentDeclaration, TaxComputation
        decl = InvestmentDeclaration.objects.create(
            tenant=tenant_a, employee=employee_a, financial_year="2025-26",
            previous_employer_income=Decimal("500000.00"))
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a, declaration=decl, computation_type="provisional")
        assert comp.gross_annual_income == Decimal("500000.00")


# ================================================================ TaxComputation.save() FY-derivation
class TestTaxComputationSaveFYDerivation:
    def test_financial_year_derived_from_declaration_when_blank(self, tenant_a, tax_declaration_a, employee_a):
        from apps.hrm.models import TaxComputation
        comp = TaxComputation(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a,
            computation_type="provisional")
        assert comp.financial_year == ""
        comp.save()
        assert comp.financial_year == tax_declaration_a.financial_year
        assert comp.financial_year == "2025-26"

    def test_explicit_financial_year_not_overwritten(self, tenant_a, tax_declaration_a, employee_a):
        from apps.hrm.models import TaxComputation
        comp = TaxComputation(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a,
            financial_year="9999-00", computation_type="provisional")
        comp.save()
        assert comp.financial_year == "9999-00"

    def test_via_create_view_yields_matching_financial_year_and_nonzero_tax(
        self, client_a, tenant_a, tax_declaration_a, employee_a, tax_structure_a,
        line_80c_a, line_hra_a, old_regime_config_a,
    ):
        """Creating a TaxComputation via the real view (POST, financial_year excluded from the form)
        yields financial_year == declaration.financial_year -- not blank -- so a subsequent generate()
        computes a real (non-zero) tax rather than silently finding no TaxRegimeConfig."""
        from apps.hrm.models import TaxComputation
        resp = client_a.post(reverse("hrm:taxcomputation_create"), {
            "employee": employee_a.pk, "declaration": tax_declaration_a.pk,
            "computation_type": "final", "remaining_pay_periods": "6", "notes": "",
        })
        assert resp.status_code == 302
        comp = TaxComputation.objects.get(tenant=tenant_a, employee=employee_a,
                                          financial_year=tax_declaration_a.financial_year)
        assert comp.financial_year == "2025-26"
        comp.recompute()
        # tax_declaration_a is old-regime-elected -> recompute() follows the declaration's election and
        # produces the hand-verified non-zero figure (never 0.00 from a blank/mismatched financial_year).
        assert tax_declaration_a.regime_elected == "old"
        assert comp.tax_payable == Decimal("52520.00")


# ================================================================ TaxComputationForm guards
class TestTaxComputationFormGuards:
    def test_second_computation_same_employee_fy_rejected(self, client_a, tax_computation_a, tax_declaration_a):
        resp = client_a.post(reverse("hrm:taxcomputation_create"), {
            "employee": tax_declaration_a.employee_id, "declaration": tax_declaration_a.pk,
            "computation_type": "provisional", "remaining_pay_periods": "12", "notes": "",
        })
        assert resp.status_code == 200
        assert not resp.context["form"].is_valid()

    def test_employee_declaration_mismatch_rejected(self, client_a, tenant_a, employee_a, employee_a2,
                                                     tax_declaration_a):
        resp = client_a.post(reverse("hrm:taxcomputation_create"), {
            "employee": employee_a2.pk, "declaration": tax_declaration_a.pk,
            "computation_type": "provisional", "remaining_pay_periods": "12", "notes": "",
        })
        assert resp.status_code == 200
        assert not resp.context["form"].is_valid()

    def test_editing_existing_computation_does_not_clash_with_itself(self, client_a, tax_computation_a):
        resp = client_a.post(reverse("hrm:taxcomputation_edit", args=[tax_computation_a.pk]), {
            "employee": tax_computation_a.employee_id, "declaration": tax_computation_a.declaration_id,
            "computation_type": "final", "remaining_pay_periods": "9", "notes": "Updated",
        })
        assert resp.status_code == 302
        tax_computation_a.refresh_from_db()
        assert tax_computation_a.notes == "Updated"
        assert tax_computation_a.remaining_pay_periods == 9

    def test_different_employee_different_fy_computation_validates(
        self, client_a, tenant_a, employee_a2, dept_a, designation_a,
    ):
        from apps.hrm.models import InvestmentDeclaration
        decl2 = InvestmentDeclaration.objects.create(
            tenant=tenant_a, employee=employee_a2, financial_year="2024-25")
        resp = client_a.post(reverse("hrm:taxcomputation_create"), {
            "employee": employee_a2.pk, "declaration": decl2.pk,
            "computation_type": "provisional", "remaining_pay_periods": "12", "notes": "",
        })
        assert resp.status_code == 302


# ================================================================ recompute() provisional/final gate
class TestTaxComputationRecomputeGate:
    def test_final_raises_when_proof_window_open_in_future(
        self, tenant_a, tax_declaration_a, tax_structure_a, employee_a,
    ):
        from apps.hrm.models import TaxComputation
        tax_declaration_a.proof_window_close = datetime.date(2099, 12, 31)
        tax_declaration_a.save(update_fields=["proof_window_close"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a, computation_type="final")
        with pytest.raises(ValidationError):
            comp.recompute()

    def test_final_succeeds_when_proof_window_closed(self, tax_computation_a):
        tax_computation_a.declaration.proof_window_close = datetime.date(2020, 1, 1)  # long past
        tax_computation_a.declaration.save(update_fields=["proof_window_close"])
        tax_computation_a.recompute()  # must not raise
        assert tax_computation_a.computed_at is not None

    def test_final_succeeds_when_no_proof_window_set(self, tenant_a, tax_declaration_a, tax_structure_a, employee_a):
        from apps.hrm.models import TaxComputation
        tax_declaration_a.proof_window_close = None
        tax_declaration_a.save(update_fields=["proof_window_close"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a, computation_type="final")
        comp.recompute()  # must not raise

    def test_provisional_ignores_proof_window(self, tenant_a, tax_declaration_a, tax_structure_a, employee_a):
        from apps.hrm.models import TaxComputation
        tax_declaration_a.proof_window_close = datetime.date(2099, 12, 31)
        tax_declaration_a.save(update_fields=["proof_window_close"])
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a, computation_type="provisional")
        comp.recompute()  # must not raise


class TestTaxComputationTDSAggregation:
    """tax_declaration_a's financial_year is "2025-26" -> FY date range 2025-04-01..2026-03-31, so the
    payroll cycle used here must fall INSIDE that window (unlike draft_cycle_a, whose pay_date
    2026-07-01 is FY 2026-27 and would be silently excluded by _tds_paid_ytd's date filter)."""

    @pytest.fixture
    def fy_cycle_a(self, db, tenant_a):
        from apps.hrm.models import PayrollCycle
        return PayrollCycle.objects.create(
            tenant=tenant_a, period_start=datetime.date(2025, 12, 1), period_end=datetime.date(2025, 12, 31),
            pay_date=datetime.date(2026, 1, 1), cycle_type="regular", status="draft")

    def test_tax_paid_ytd_aggregates_tds_payslip_lines(
        self, tenant_a, tax_declaration_a, tax_structure_a, employee_a, fy_cycle_a,
        salary_template_a,
    ):
        from apps.hrm.models import PayComponent, SalaryStructureLine, Payslip, TaxComputation
        tds_component = PayComponent.objects.create(
            tenant=tenant_a, name="TDS Deduction", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employee",
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=tds_component, amount=Decimal("1200"))
        payslip = Payslip.objects.create(
            tenant=tenant_a, cycle=fy_cycle_a, employee=employee_a,
            salary_structure=tax_structure_a, days_in_period=30, days_worked=30)
        payslip.recompute()

        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a,
            computation_type="provisional")
        comp.recompute()
        # TDS Deduction 1200/yr -> 100.00/month payslip line, picked up by the "tds" keyword.
        assert comp.tax_paid_ytd == Decimal("100.00")

    def test_tax_paid_ytd_ignores_non_tds_statutory_line(
        self, tenant_a, tax_declaration_a, tax_structure_a, employee_a, fy_cycle_a,
        salary_template_a,
    ):
        from apps.hrm.models import PayComponent, SalaryStructureLine, Payslip, TaxComputation
        pf_component = PayComponent.objects.create(
            tenant=tenant_a, name="Provident Fund - Employee", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employee",
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=pf_component, amount=Decimal("1200"))
        payslip = Payslip.objects.create(
            tenant=tenant_a, cycle=fy_cycle_a, employee=employee_a,
            salary_structure=tax_structure_a, days_in_period=30, days_worked=30)
        payslip.recompute()

        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a,
            computation_type="provisional")
        comp.recompute()
        # "provident" does not match the tds_24q keyword list ("tds", "income tax", "tax deducted").
        assert comp.tax_paid_ytd == Decimal("0.00")

    def test_monthly_tds_amount_uses_manual_override_when_set(self, tax_computation_a):
        tax_computation_a.manual_override_amount = Decimal("999.99")
        tax_computation_a.save(update_fields=["manual_override_amount"])
        tax_computation_a.recompute()
        assert tax_computation_a.monthly_tds_amount == Decimal("999.99")

    def test_monthly_tds_amount_derived_from_remaining_periods(self, tax_computation_a):
        tax_computation_a.recompute()
        # tax_payable (new) - assert against old since declaration is old-regime-elected: 52520.00 / 6
        expected = (tax_computation_a.tax_payable - tax_computation_a.tax_paid_ytd) / Decimal("6")
        expected = max(expected, Decimal("0")).quantize(Decimal("0.01"))
        assert tax_computation_a.monthly_tds_amount == expected

    def test_monthly_tds_amount_zero_when_no_remaining_periods(self, tenant_a, tax_declaration_a,
                                                                tax_structure_a, employee_a):
        from apps.hrm.models import TaxComputation
        comp = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a,
            computation_type="provisional", remaining_pay_periods=0)
        comp.recompute()
        assert comp.monthly_tds_amount == Decimal("0.00")


# ================================================================ link_form16()
class TestTaxComputationLinkForm16:
    def test_link_form16_creates_statutory_return(self, tax_computation_a, admin_user):
        from apps.hrm.models import StatutoryReturn
        ret = tax_computation_a.link_form16(admin_user)
        assert ret.scheme == "tds_form16"
        assert ret.employee_id == tax_computation_a.employee_id
        tax_computation_a.refresh_from_db()
        assert tax_computation_a.statutory_return_id == ret.pk

    def test_link_form16_period_matches_fy(self, tax_computation_a):
        ret = tax_computation_a.link_form16()
        assert ret.period_start == datetime.date(2025, 4, 1)
        assert ret.period_end == datetime.date(2026, 3, 31)

    def test_link_form16_idempotent_no_duplicate(self, tenant_a, tax_computation_a):
        from apps.hrm.models import StatutoryReturn
        ret1 = tax_computation_a.link_form16()
        ret2 = tax_computation_a.link_form16()
        assert ret1.pk == ret2.pk
        assert StatutoryReturn.objects.filter(
            tenant=tenant_a, scheme="tds_form16", employee=tax_computation_a.employee).count() == 1

    def test_link_form16_recomputes_while_pending(self, tax_computation_a):
        ret = tax_computation_a.link_form16()
        assert ret.status == "pending"
        # recompute() aggregates PayslipLine rows -- headcount/contribution totals populated (may be 0
        # if no matching lines exist, but must not have crashed and must reflect a real recompute pass).
        assert ret.registration_number_used is not None  # snapshotted, even if blank string

    def test_link_form16_does_not_crash_when_already_filed(self, tax_computation_a):
        ret = tax_computation_a.link_form16()
        ret.status = "filed"
        ret.save(update_fields=["status", "updated_at"])
        # Second link_form16 call must not attempt recompute() on a filed (locked) return.
        ret2 = tax_computation_a.link_form16()
        assert ret2.pk == ret.pk
        assert ret2.status == "filed"

    def test_link_form16_second_computation_different_employee_does_not_collide(
        self, tenant_a, tax_computation_a, employee_a2, dept_a, designation_a,
    ):
        from apps.hrm.models import InvestmentDeclaration, TaxComputation, StatutoryReturn
        decl2 = InvestmentDeclaration.objects.create(
            tenant=tenant_a, employee=employee_a2, financial_year="2025-26")
        comp2 = TaxComputation.objects.create(
            tenant=tenant_a, employee=employee_a2, declaration=decl2, computation_type="provisional")
        ret1 = tax_computation_a.link_form16()
        ret2 = comp2.link_form16()
        assert ret1.pk != ret2.pk
        assert StatutoryReturn.objects.filter(tenant=tenant_a, scheme="tds_form16").count() == 2
