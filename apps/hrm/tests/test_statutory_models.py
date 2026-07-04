"""Tests for HRM 3.15 Statutory Compliance models: StatutoryConfig (tenant singleton),
StatutoryStateRule (scheme-aware clean()), EmployeeStatutoryIdentifier (masking), StatutoryReturn
(recompute() aggregation, is_overdue/is_locked, SCR-##### numbering)."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ================================================================ StatutoryConfig
class TestStatutoryConfigModel:
    def test_for_tenant_creates_singleton(self, tenant_a):
        from apps.hrm.models import StatutoryConfig
        config = StatutoryConfig.for_tenant(tenant_a)
        assert config.pk is not None
        assert config.tenant_id == tenant_a.id

    def test_for_tenant_is_idempotent(self, tenant_a):
        from apps.hrm.models import StatutoryConfig
        config1 = StatutoryConfig.for_tenant(tenant_a)
        config2 = StatutoryConfig.for_tenant(tenant_a)
        assert config1.pk == config2.pk
        assert StatutoryConfig.objects.filter(tenant=tenant_a).count() == 1

    def test_defaults(self, tenant_a):
        from apps.hrm.models import StatutoryConfig
        config = StatutoryConfig.for_tenant(tenant_a)
        assert config.pf_wage_ceiling == Decimal("15000.00")
        assert config.pf_employee_rate == Decimal("12.00")
        assert config.pf_employer_rate == Decimal("12.00")
        assert config.esi_wage_ceiling == Decimal("21000.00")
        assert config.esi_employee_rate == Decimal("0.75")
        assert config.esi_employer_rate == Decimal("3.25")
        assert config.is_lwf_applicable is False

    def test_one_config_per_tenant_via_onetoone(self, tenant_a, statutory_config_a):
        from apps.hrm.models import StatutoryConfig
        dupe = StatutoryConfig(tenant=tenant_a)
        with pytest.raises(IntegrityError):
            dupe.save()

    def test_str(self, tenant_a):
        from apps.hrm.models import StatutoryConfig
        config = StatutoryConfig.for_tenant(tenant_a)
        assert str(config) == f"Statutory Config · {tenant_a.name}"

    def test_separate_tenants_get_separate_configs(self, tenant_a, tenant_b):
        from apps.hrm.models import StatutoryConfig
        config_a = StatutoryConfig.for_tenant(tenant_a)
        config_b = StatutoryConfig.for_tenant(tenant_b)
        assert config_a.pk != config_b.pk
        assert config_a.tenant_id == tenant_a.id
        assert config_b.tenant_id == tenant_b.id


# ================================================================ StatutoryStateRule.clean()
class TestStatutoryStateRuleClean:
    def test_pt_missing_income_from_raises(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Karnataka", scheme="pt",
            income_to=Decimal("20000"), pt_monthly_amount=Decimal("200"),
        )
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "income_from" in exc.value.message_dict

    def test_pt_missing_income_to_raises(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Karnataka", scheme="pt",
            income_from=Decimal("15000"), pt_monthly_amount=Decimal("200"),
        )
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "income_to" in exc.value.message_dict

    def test_pt_missing_pt_monthly_amount_raises(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Karnataka", scheme="pt",
            income_from=Decimal("15000"), income_to=Decimal("20000"),
        )
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "pt_monthly_amount" in exc.value.message_dict

    def test_pt_income_to_below_income_from_raises(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Karnataka", scheme="pt",
            income_from=Decimal("20000"), income_to=Decimal("15000"),
            pt_monthly_amount=Decimal("200"),
        )
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "income_to" in exc.value.message_dict

    def test_pt_valid_rule_passes_clean(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Karnataka", scheme="pt",
            income_from=Decimal("15000"), income_to=Decimal("20000"),
            pt_monthly_amount=Decimal("200"),
        )
        rule.clean()  # must not raise

    def test_lwf_missing_contributions_raises(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Maharashtra", scheme="lwf",
            lwf_periodicity="half_yearly",
        )
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "lwf_employee_contribution" in exc.value.message_dict

    def test_lwf_missing_employer_contribution_raises(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Maharashtra", scheme="lwf",
            lwf_employee_contribution=Decimal("12"), lwf_periodicity="half_yearly",
        )
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "lwf_employee_contribution" in exc.value.message_dict

    def test_lwf_missing_periodicity_raises(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Maharashtra", scheme="lwf",
            lwf_employee_contribution=Decimal("12"), lwf_employer_contribution=Decimal("36"),
        )
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "lwf_periodicity" in exc.value.message_dict

    def test_lwf_valid_rule_passes_clean(self, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        rule = StatutoryStateRule(
            tenant=tenant_a, state="Maharashtra", scheme="lwf",
            lwf_employee_contribution=Decimal("12"), lwf_employer_contribution=Decimal("36"),
            lwf_periodicity="half_yearly",
        )
        rule.clean()  # must not raise

    def test_second_active_lwf_rule_same_state_raises_on_create(self, tenant_a, lwf_rule_a):
        from apps.hrm.models import StatutoryStateRule
        # lwf_rule_a is already active for tenant_a/Maharashtra — a second active LWF row for the
        # SAME state must be rejected even though income_from is NULL on both (NULL-distinct DB
        # constraint would otherwise let it slip through).
        dupe = StatutoryStateRule(
            tenant=tenant_a, state="Maharashtra", scheme="lwf",
            lwf_employee_contribution=Decimal("15"), lwf_employer_contribution=Decimal("40"),
            lwf_periodicity="annual", is_active=True,
        )
        with pytest.raises(ValidationError):
            dupe.clean()

    def test_second_inactive_lwf_rule_same_state_passes(self, tenant_a, lwf_rule_a):
        """A new LWF row for the same state is fine as long as it is NOT active (supersede pattern)."""
        from apps.hrm.models import StatutoryStateRule
        superseding = StatutoryStateRule(
            tenant=tenant_a, state="Maharashtra", scheme="lwf",
            lwf_employee_contribution=Decimal("15"), lwf_employer_contribution=Decimal("40"),
            lwf_periodicity="annual", is_active=False,
        )
        superseding.clean()  # must not raise

    def test_lwf_rule_different_state_does_not_clash(self, tenant_a, lwf_rule_a):
        from apps.hrm.models import StatutoryStateRule
        other_state = StatutoryStateRule(
            tenant=tenant_a, state="Gujarat", scheme="lwf",
            lwf_employee_contribution=Decimal("6"), lwf_employer_contribution=Decimal("18"),
            lwf_periodicity="annual", is_active=True,
        )
        other_state.clean()  # must not raise

    def test_editing_the_same_active_lwf_rule_does_not_clash_with_itself(self, tenant_a, lwf_rule_a):
        """clean() excludes self.pk from the clash query — editing the existing active row must
        not raise against itself."""
        lwf_rule_a.lwf_employee_contribution = Decimal("14")
        lwf_rule_a.clean()  # must not raise

    def test_deactivating_then_reactivating_a_second_rule_raises(self, tenant_a, lwf_rule_a):
        """Supersede workflow: deactivate the old rule, then a new active rule for the same state
        is fine; but re-activating BOTH at once must fail."""
        from apps.hrm.models import StatutoryStateRule
        lwf_rule_a.is_active = False
        lwf_rule_a.save(update_fields=["is_active", "updated_at"])
        new_rule = StatutoryStateRule.objects.create(
            tenant=tenant_a, state="Maharashtra", scheme="lwf",
            lwf_employee_contribution=Decimal("15"), lwf_employer_contribution=Decimal("40"),
            lwf_periodicity="annual", is_active=True,
        )
        assert new_rule.pk is not None
        # Now flip the old (superseded) rule back to active — must clash with new_rule.
        lwf_rule_a.is_active = True
        with pytest.raises(ValidationError):
            lwf_rule_a.clean()

    def test_unique_together_tenant_state_scheme_income_from(self, tenant_a, pt_rule_a):
        from apps.hrm.models import StatutoryStateRule
        dupe = StatutoryStateRule(
            tenant=tenant_a, state="Karnataka", scheme="pt",
            income_from=pt_rule_a.income_from, income_to=Decimal("25000"),
            pt_monthly_amount=Decimal("250"),
        )
        with pytest.raises(IntegrityError):
            dupe.save()

    def test_str_pt_includes_income_band(self, tenant_a, pt_rule_a):
        s = str(pt_rule_a)
        assert "Karnataka" in s
        assert "Professional Tax" in s
        assert "15000" in s

    def test_str_lwf_omits_income_band(self, tenant_a, lwf_rule_a):
        s = str(lwf_rule_a)
        assert "Maharashtra" in s
        assert "Labour Welfare Fund" in s


# ================================================================ EmployeeStatutoryIdentifier
class TestEmployeeStatutoryIdentifierModel:
    def test_masked_uan_number_shows_last4(self, statutory_identifier_a):
        assert statutory_identifier_a.masked_uan_number() == "••••9012"

    def test_masked_pf_number_shows_last4(self, statutory_identifier_a):
        assert statutory_identifier_a.masked_pf_number() == "••••1234"

    def test_masked_esi_number_shows_last4(self, statutory_identifier_a):
        assert statutory_identifier_a.masked_esi_number() == "••••4567"

    def test_masked_value_never_contains_full_number(self, statutory_identifier_a):
        masked = statutory_identifier_a.masked_uan_number()
        assert statutory_identifier_a.uan_number not in masked
        assert masked != statutory_identifier_a.uan_number

    def test_masked_blank_value_returns_empty_string(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeStatutoryIdentifier
        ident = EmployeeStatutoryIdentifier.objects.create(tenant=tenant_a, employee=employee_a)
        assert ident.masked_uan_number() == ""
        assert ident.masked_pf_number() == ""
        assert ident.masked_esi_number() == ""

    def test_masked_short_value_returns_dots_only(self, tenant_a, employee_a):
        """A value shorter than 4 chars has nothing safe to reveal — mask-only, no partial leak."""
        from apps.hrm.models import EmployeeStatutoryIdentifier
        ident = EmployeeStatutoryIdentifier.objects.create(
            tenant=tenant_a, employee=employee_a, uan_number="12")
        assert ident.masked_uan_number() == "••••"

    def test_defaults(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeStatutoryIdentifier
        ident = EmployeeStatutoryIdentifier.objects.create(tenant=tenant_a, employee=employee_a)
        assert ident.is_pf_applicable is True
        assert ident.is_esi_applicable is True

    def test_one_to_one_per_employee(self, tenant_a, employee_a, statutory_identifier_a):
        from apps.hrm.models import EmployeeStatutoryIdentifier
        dupe = EmployeeStatutoryIdentifier(tenant=tenant_a, employee=employee_a)
        with pytest.raises(IntegrityError):
            dupe.save()

    def test_str(self, statutory_identifier_a, employee_a):
        assert str(statutory_identifier_a) == f"Statutory IDs · {employee_a}"


# ================================================================ StatutoryReturn
class TestStatutoryReturnModel:
    def test_number_auto_assigns(self, pending_statutory_return_a):
        assert pending_statutory_return_a.number.startswith("SCR-")

    def test_defaults(self, pending_statutory_return_a):
        assert pending_statutory_return_a.status == "pending"
        assert pending_statutory_return_a.employee_contribution_total == Decimal("0")
        assert pending_statutory_return_a.employer_contribution_total == Decimal("0")
        assert pending_statutory_return_a.headcount == 0
        assert pending_statutory_return_a.filed_on is None
        assert pending_statutory_return_a.paid_on is None

    def test_is_locked_false_when_pending(self, pending_statutory_return_a):
        assert pending_statutory_return_a.is_locked is False

    @pytest.mark.parametrize("status", ["filed", "paid", "late"])
    def test_is_locked_true_when_not_pending(self, pending_statutory_return_a, status):
        pending_statutory_return_a.status = status
        assert pending_statutory_return_a.is_locked is True

    def test_is_overdue_true_when_pending_and_past_due(self, tenant_a, draft_cycle_a):
        from apps.hrm.models import StatutoryReturn
        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            due_date=datetime.date(2020, 1, 1),  # long past
        )
        assert ret.is_overdue is True

    def test_is_overdue_false_when_no_due_date(self, pending_statutory_return_a):
        pending_statutory_return_a.due_date = None
        assert pending_statutory_return_a.is_overdue is False

    def test_is_overdue_false_when_not_pending(self, pending_statutory_return_a):
        pending_statutory_return_a.due_date = datetime.date(2020, 1, 1)
        pending_statutory_return_a.status = "filed"
        assert pending_statutory_return_a.is_overdue is False

    def test_is_overdue_false_when_due_date_in_future(self, pending_statutory_return_a):
        pending_statutory_return_a.due_date = timezone.localdate() + datetime.timedelta(days=30)
        assert pending_statutory_return_a.is_overdue is False

    def test_clean_period_end_before_start_raises(self, tenant_a):
        from apps.hrm.models import StatutoryReturn
        ret = StatutoryReturn(
            tenant=tenant_a, scheme="pf", period_start=datetime.date(2026, 6, 30),
            period_end=datetime.date(2026, 6, 1),
        )
        with pytest.raises(ValidationError) as exc:
            ret.clean()
        assert "period_end" in exc.value.message_dict

    def test_unique_together_tenant_scheme_period_employee(self, tenant_a, employee_a, draft_cycle_a):
        """The DB unique_together fires when ``employee`` is a real (non-NULL) FK — e.g. two Form 16
        returns for the SAME employee/scheme/period_start. (NULL ``employee`` is NOT covered by this
        DB constraint — MariaDB/SQLite treat NULL as distinct — that hole is closed at the form level,
        see TestStatutoryReturnFormDuplicateGuard.)"""
        from apps.hrm.models import StatutoryReturn
        StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="tds_form16", period_type="annual",
            period_start=datetime.date(2026, 4, 1), period_end=datetime.date(2027, 3, 31),
            employee=employee_a,
        )
        dupe = StatutoryReturn(
            tenant=tenant_a, scheme="tds_form16", period_type="annual",
            period_start=datetime.date(2026, 4, 1), period_end=datetime.date(2027, 3, 31),
            employee=employee_a,
        )
        with pytest.raises(IntegrityError):
            dupe.save()

    def test_unique_together_allows_null_employee_collision_at_db_level(
        self, tenant_a, pending_statutory_return_a,
    ):
        """Documents the known NULL-distinct DB-constraint gap: two org-level (employee=None) returns
        for the same (tenant, scheme, period_start) do NOT collide at the DB layer — this is exactly
        why StatutoryReturnForm.clean() enforces the guard at the form level instead."""
        from apps.hrm.models import StatutoryReturn
        dupe = StatutoryReturn(
            tenant=tenant_a, scheme=pending_statutory_return_a.scheme,
            period_start=pending_statutory_return_a.period_start,
            period_end=pending_statutory_return_a.period_end, employee=None,
        )
        dupe.save()  # does NOT raise — NULL is distinct from NULL in a unique index
        assert dupe.pk is not None

    def test_str(self, pending_statutory_return_a):
        s = str(pending_statutory_return_a)
        assert pending_statutory_return_a.number in s
        assert "Provident Fund" in s


class TestStatutoryReturnRecomputeAggregation:
    """The key domain behavior: recompute() aggregates from PayslipLine rows — never hand-typed."""

    def test_recompute_aggregates_employer_and_employee_pf_totals(
        self, tenant_a, draft_cycle_a, payslip_with_pf_a,
    ):
        from apps.hrm.models import StatutoryReturn
        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        # pf_component_lines_a: employee-side PF 1200/yr -> 100.00/mo; employer-side PF 1200/yr -> 100.00/mo.
        assert ret.employee_contribution_total == Decimal("100.00")
        assert ret.employer_contribution_total == Decimal("100.00")

    def test_recompute_headcount_is_distinct_employee_count(
        self, tenant_a, draft_cycle_a, payslip_with_pf_a,
    ):
        from apps.hrm.models import StatutoryReturn
        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        assert ret.headcount == 1

    def test_recompute_headcount_counts_distinct_employees_across_multiple_payslips(
        self, tenant_a, draft_cycle_a, employee_a, employee_a2,
        active_structure_in_window_a, pf_component_lines_a, salary_template_a,
    ):
        from apps.hrm.models import EmployeeSalaryStructure, Payslip, StatutoryReturn
        structure2 = EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a2, template=salary_template_a,
            annual_ctc_amount=Decimal("120000"), status="active",
            effective_from=datetime.date(2026, 5, 1),
        )
        payslip2 = Payslip.objects.create(
            tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a2,
            salary_structure=structure2, days_in_period=30, days_worked=30,
        )
        payslip2.recompute()
        # employee_a's payslip must also exist for a 2-employee headcount.
        payslip1 = Payslip.objects.create(
            tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a,
            salary_structure=active_structure_in_window_a, days_in_period=30, days_worked=30,
        )
        payslip1.recompute()

        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        assert ret.headcount == 2
        # Each employee contributes 100.00 employee-side + 100.00 employer-side.
        assert ret.employee_contribution_total == Decimal("200.00")
        assert ret.employer_contribution_total == Decimal("200.00")

    def test_contribution_side_both_counted_once_in_employee_bucket_not_doubled(
        self, tenant_a, draft_cycle_a, employee_a, salary_template_a, active_structure_in_window_a,
    ):
        """CRITICAL: a contribution_side="both" statutory line (e.g. ESI-both) must land in
        employee_contribution_total exactly once via the `exclude(contribution_side="employer")`
        bucket — it must NEVER be double-counted into employer_contribution_total too. Mirrors
        3.14's payrollcycle_lock roll-up bucketing exactly."""
        from apps.hrm.models import PayComponent, SalaryStructureLine, Payslip, StatutoryReturn
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", component_type="earning",
            calculation_type="fixed_amount", default_amount=Decimal("60000"),
        )
        esi_both = PayComponent.objects.create(
            tenant=tenant_a, name="ESI Both", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("600"),
            contribution_side="both",
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=esi_both, amount=Decimal("600"))
        payslip = Payslip.objects.create(
            tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a,
            salary_structure=active_structure_in_window_a, days_in_period=30, days_worked=30,
        )
        payslip.recompute()

        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="esi", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        # esi_both monthly = 600/12 = 50.00 -> counted ONCE into employee_contribution_total.
        assert ret.employee_contribution_total == Decimal("50.00")
        # It must NOT also appear in employer_contribution_total (that would be double-counting).
        assert ret.employer_contribution_total == Decimal("0.00")
        # Sanity: total aggregated (employee + employer) equals exactly one copy of the line, not two.
        assert ret.employee_contribution_total + ret.employer_contribution_total == Decimal("50.00")

    def test_recompute_scheme_keyword_matching_is_case_insensitive_substring(
        self, tenant_a, draft_cycle_a, employee_a, salary_template_a, active_structure_in_window_a,
    ):
        from apps.hrm.models import PayComponent, SalaryStructureLine, Payslip, StatutoryReturn
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", component_type="earning",
            calculation_type="fixed_amount", default_amount=Decimal("60000"),
        )
        epf = PayComponent.objects.create(
            tenant=tenant_a, name="EPF Contribution", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employee",
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=epf, amount=Decimal("1200"))
        payslip = Payslip.objects.create(
            tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a,
            salary_structure=active_structure_in_window_a, days_in_period=30, days_worked=30,
        )
        payslip.recompute()

        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        # "epf" substring-matches the "epf" keyword for scheme "pf".
        assert ret.employee_contribution_total == Decimal("100.00")

    def test_recompute_unmatched_scheme_yields_zero_not_crash(
        self, tenant_a, draft_cycle_a, payslip_with_pf_a,
    ):
        """LWF has no seeded PayComponent in this fixture set -> recompute() aggregates to zero,
        not an exception."""
        from apps.hrm.models import StatutoryReturn
        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="lwf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        assert ret.employee_contribution_total == Decimal("0")
        assert ret.employer_contribution_total == Decimal("0")
        assert ret.headcount == 0

    def test_recompute_snapshots_registration_number(
        self, tenant_a, draft_cycle_a, payslip_with_pf_a, statutory_config_a,
    ):
        from apps.hrm.models import StatutoryReturn
        statutory_config_a.pf_establishment_code = "KN/BLR/1234567"
        statutory_config_a.save(update_fields=["pf_establishment_code", "updated_at"])
        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        assert ret.registration_number_used == "KN/BLR/1234567"

    def test_recompute_raises_when_filed(self, pending_statutory_return_a):
        pending_statutory_return_a.status = "filed"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        with pytest.raises(ValidationError):
            pending_statutory_return_a.recompute()

    def test_recompute_raises_when_paid(self, pending_statutory_return_a):
        pending_statutory_return_a.status = "paid"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        with pytest.raises(ValidationError):
            pending_statutory_return_a.recompute()

    def test_recompute_raises_when_late(self, pending_statutory_return_a):
        pending_statutory_return_a.status = "late"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        with pytest.raises(ValidationError):
            pending_statutory_return_a.recompute()

    def test_recompute_does_not_mutate_totals_when_locked(self, pending_statutory_return_a):
        """The immutability guard must fire BEFORE any totals are touched."""
        pending_statutory_return_a.status = "filed"
        pending_statutory_return_a.employee_contribution_total = Decimal("999.99")
        pending_statutory_return_a.save(update_fields=[
            "status", "employee_contribution_total", "updated_at"])
        with pytest.raises(ValidationError):
            pending_statutory_return_a.recompute()
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.employee_contribution_total == Decimal("999.99")

    def test_recompute_scoped_by_cycle_excludes_other_cycles(
        self, tenant_a, draft_cycle_a, payslip_with_pf_a, employee_a, salary_template_a,
    ):
        """A return scoped to draft_cycle_a must not pick up PayslipLine rows from a different
        cycle in the same period-date range."""
        from apps.hrm.models import PayrollCycle, EmployeeSalaryStructure, Payslip, StatutoryReturn
        other_cycle = PayrollCycle.objects.create(
            tenant=tenant_a, period_start=draft_cycle_a.period_start,
            period_end=draft_cycle_a.period_end, pay_date=draft_cycle_a.pay_date,
            cycle_type="off_cycle",
        )
        structure = EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, template=salary_template_a,
            annual_ctc_amount=Decimal("120000"), status="superseded",
            effective_from=datetime.date(2025, 1, 1),
        )
        other_payslip = Payslip.objects.create(
            tenant=tenant_a, cycle=other_cycle, employee=employee_a,
            salary_structure=structure, days_in_period=30, days_worked=30,
        )
        other_payslip.recompute()

        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        ret.recompute()
        # Only draft_cycle_a's payslip (1 employee) counted, not other_cycle's.
        assert ret.headcount == 1
