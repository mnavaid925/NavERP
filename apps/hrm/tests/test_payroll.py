"""Tests for HRM 3.14 Payroll Processing models: PayrollCycle, Payslip (recompute() calc
engine), PayslipLine."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ local helpers
def _make_structure(tenant, employee, template, ctc):
    from apps.hrm.models import EmployeeSalaryStructure
    return EmployeeSalaryStructure.objects.create(
        tenant=tenant, employee=employee, template=template,
        annual_ctc_amount=ctc, status="active",
    )


def _make_cycle(tenant, start=None, end=None, pay_date=None, **kwargs):
    from apps.hrm.models import PayrollCycle
    start = start or datetime.date(2026, 6, 1)
    end = end or datetime.date(2026, 6, 30)
    pay_date = pay_date or datetime.date(2026, 7, 1)
    return PayrollCycle.objects.create(
        tenant=tenant, period_start=start, period_end=end, pay_date=pay_date, **kwargs,
    )


def _make_payslip(tenant, cycle, employee, structure, **kwargs):
    from apps.hrm.models import Payslip
    kwargs.setdefault("days_in_period", 30)
    kwargs.setdefault("days_worked", 30)
    return Payslip.objects.create(
        tenant=tenant, cycle=cycle, employee=employee, salary_structure=structure, **kwargs,
    )


# ================================================================ PayrollCycle
class TestPayrollCycleModel:
    def test_number_auto_assigns(self, tenant_a):
        cycle = _make_cycle(tenant_a)
        assert cycle.number.startswith("PRC-")

    def test_str(self, tenant_a):
        cycle = _make_cycle(tenant_a, cycle_type="regular")
        assert str(cycle) == f"{cycle.number} · Regular · {cycle.period_start}–{cycle.period_end}"

    def test_defaults(self, tenant_a):
        cycle = _make_cycle(tenant_a)
        assert cycle.cycle_type == "regular"
        assert cycle.status == "draft"
        assert cycle.submitted_by is None
        assert cycle.approved_by is None
        assert cycle.accounting_payroll_run is None

    def test_is_locked_false_when_not_locked(self, tenant_a):
        cycle = _make_cycle(tenant_a, status="approved")
        assert cycle.is_locked is False

    def test_is_locked_true_when_locked(self, tenant_a):
        cycle = _make_cycle(tenant_a, status="locked")
        assert cycle.is_locked is True

    def test_unique_together_tenant_number(self, tenant_a):
        cycle = _make_cycle(tenant_a)
        with pytest.raises(IntegrityError):
            _make_cycle(tenant_a, number=cycle.number)

    def test_clean_period_end_before_start_raises(self, tenant_a):
        from apps.hrm.models import PayrollCycle
        cycle = PayrollCycle(
            tenant=tenant_a, period_start=datetime.date(2026, 6, 30),
            period_end=datetime.date(2026, 6, 1), pay_date=datetime.date(2026, 7, 1),
        )
        with pytest.raises(ValidationError) as exc:
            cycle.clean()
        assert "period_end" in exc.value.message_dict

    def test_clean_period_end_equal_start_passes(self, tenant_a):
        from apps.hrm.models import PayrollCycle
        cycle = PayrollCycle(
            tenant=tenant_a, period_start=datetime.date(2026, 6, 1),
            period_end=datetime.date(2026, 6, 1), pay_date=datetime.date(2026, 7, 1),
        )
        cycle.clean()  # must not raise

    def test_derived_totals_over_two_payslips(
        self, tenant_a, employee_a, employee_b, salary_template_a,
    ):
        """Build a cycle with 2 payslips and assert headcount/total_gross/total_deductions/total_net
        are derived aggregates, not stored fields."""
        from apps.hrm.models import Payslip
        cycle = _make_cycle(tenant_a)
        p1 = _make_payslip(tenant_a, cycle, employee_a, None)
        p1.gross_pay = Decimal("1000.00")
        p1.total_deductions = Decimal("100.00")
        p1.net_pay = Decimal("900.00")
        p1.save(update_fields=["gross_pay", "total_deductions", "net_pay"])

        # second payslip for a different employee in the SAME tenant (employee_b is tenant_b — use a
        # second tenant_a employee instead via a fresh EmployeeProfile).
        from apps.core.models import Party, Employment
        from apps.hrm.models import EmployeeProfile
        person2 = Party.objects.create(tenant=tenant_a, kind="person", name="Dave Lee")
        employment2 = Employment.objects.create(
            tenant=tenant_a, party=person2, job_title="QA Engineer",
            hired_on=datetime.date(2023, 1, 1), status="active",
        )
        employee2 = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person2, employment=employment2, employee_type="full_time",
        )
        p2 = _make_payslip(tenant_a, cycle, employee2, None)
        p2.gross_pay = Decimal("2000.00")
        p2.total_deductions = Decimal("300.00")
        p2.net_pay = Decimal("1700.00")
        p2.save(update_fields=["gross_pay", "total_deductions", "net_pay"])

        assert cycle.headcount == 2
        assert cycle.total_gross == Decimal("3000.00")
        assert cycle.total_deductions == Decimal("400.00")
        assert cycle.total_net == Decimal("2600.00")

    def test_derived_totals_zero_when_no_payslips(self, tenant_a):
        cycle = _make_cycle(tenant_a)
        assert cycle.headcount == 0
        assert cycle.total_gross == Decimal("0")
        assert cycle.total_deductions == Decimal("0")
        assert cycle.total_net == Decimal("0")


# ================================================================ Payslip.recompute() — the calc engine
class TestPayslipRecomputeBasics:
    def test_monthly_conversion_and_full_period_gross(self, tenant_a, employee_a, salary_template_a):
        """A fixed-amount annual CTC of 120000 over a template with a single 60000/yr basic line
        (salary_line_a-equivalent) -> monthly = 60000/12 = 5000; full days worked -> gross = 5000."""
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", component_type="earning",
            calculation_type="fixed_amount", default_amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"),
        )
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure)
        payslip.recompute()

        assert payslip.gross_pay == Decimal("5000.00")
        assert payslip.total_deductions == Decimal("0.00")
        assert payslip.net_pay == Decimal("5000.00")
        names = {(l.component_name, l.component_type) for l in payslip.lines.all()}
        assert ("Basic Pay", "earning") in names

    def test_earnings_prorated_by_days_worked(self, tenant_a, employee_a, salary_template_a):
        """days_worked=15/30 -> gross is exactly half of the full-period monthly amount."""
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"),
        )
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(
            tenant_a, cycle, employee_a, structure, days_in_period=30, days_worked=15,
        )
        payslip.recompute()
        # monthly = 5000.00; ratio 15/30 = 0.5 -> 2500.00
        assert payslip.gross_pay == Decimal("2500.00")
        assert payslip.net_pay == Decimal("2500.00")

    def test_net_equals_gross_minus_total_deductions(self, tenant_a, employee_a, salary_template_a):
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("60000"),
        )
        pf_ee = PayComponent.objects.create(
            tenant=tenant_a, name="PF Employee", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employee",
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=pf_ee, amount=Decimal("1200"),
        )
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure)
        payslip.recompute()
        # basic monthly = 5000.00, PF-EE monthly = 100.00
        assert payslip.gross_pay == Decimal("5000.00")
        assert payslip.total_deductions == Decimal("100.00")
        assert payslip.net_pay == Decimal("4900.00")

    def test_decimal_quantized_to_2dp(self, tenant_a, employee_a, salary_template_a):
        """An odd annual amount that doesn't divide evenly by 12 must round to exactly 2dp."""
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("100000"),
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("100000"),
        )
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure)
        payslip.recompute()
        # 100000 / 12 = 8333.333... -> quantized to 8333.33
        assert payslip.gross_pay == Decimal("8333.33")
        # Confirm exactly 2 decimal places stored.
        assert payslip.gross_pay.as_tuple().exponent == -2


class TestPayslipRecomputeEmployerStatutory:
    def _build_template_with_sides(self, tenant, template):
        """A basic earning + an employee-side statutory deduction + an employer-side statutory
        contribution, all fixed_amount so the math is exact."""
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant, name="Basic Pay", component_type="earning",
            calculation_type="fixed_amount", default_amount=Decimal("60000"),
        )
        pf_ee = PayComponent.objects.create(
            tenant=tenant, name="PF Employee", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employee",
        )
        pf_er = PayComponent.objects.create(
            tenant=tenant, name="PF Employer", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employer",
        )
        SalaryStructureLine.objects.create(tenant=tenant, template=template, pay_component=basic, amount=Decimal("60000"))
        SalaryStructureLine.objects.create(tenant=tenant, template=template, pay_component=pf_ee, amount=Decimal("1200"))
        SalaryStructureLine.objects.create(tenant=tenant, template=template, pay_component=pf_er, amount=Decimal("1200"))
        return basic, pf_ee, pf_er

    def test_employer_side_excluded_from_net_but_present_as_line(
        self, tenant_a, employee_a, salary_template_a,
    ):
        self._build_template_with_sides(tenant_a, salary_template_a)
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure)
        payslip.recompute()

        # basic monthly 5000.00; only the employee-side PF (100.00/mo) reduces net.
        assert payslip.gross_pay == Decimal("5000.00")
        assert payslip.total_deductions == Decimal("100.00")
        assert payslip.net_pay == Decimal("4900.00")

        lines = list(payslip.lines.all())
        employer_lines = [l for l in lines if l.contribution_side == "employer"]
        assert len(employer_lines) == 1
        assert employer_lines[0].component_name == "PF Employer"
        assert employer_lines[0].amount == Decimal("100.00")
        # The employer line exists but did not reduce total_deductions/net.
        employee_side_total = sum(
            (l.amount for l in lines if l.component_type == "statutory_deduction" and l.contribution_side != "employer"),
            Decimal("0"),
        )
        assert employee_side_total == payslip.total_deductions

    def test_contribution_side_both_reduces_net(self, tenant_a, employee_a, salary_template_a):
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("60000"),
        )
        esi_both = PayComponent.objects.create(
            tenant=tenant_a, name="ESI Both", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("600"),
            contribution_side="both",
        )
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=esi_both, amount=Decimal("600"))
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure)
        payslip.recompute()
        # basic monthly 5000.00, esi_both monthly 50.00 (both side reduces net, not treated as employer)
        assert payslip.gross_pay == Decimal("5000.00")
        assert payslip.total_deductions == Decimal("50.00")
        assert payslip.net_pay == Decimal("4950.00")


class TestPayslipRecomputeLOP:
    def test_lop_amount_and_gross_reduction(self, tenant_a, employee_a, salary_template_a):
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(
            tenant_a, cycle, employee_a, structure, days_in_period=30, days_worked=30,
            lop_days=Decimal("3"),
        )
        payslip.recompute()
        # period_gross = 5000.00 (full days worked, ratio 1); lop_amount = (5000/30)*3 = 500.00
        assert payslip.lop_amount == Decimal("500.00")
        assert payslip.gross_pay == Decimal("4500.00")
        lop_lines = [l for l in payslip.lines.all() if l.component_type == "lop"]
        assert len(lop_lines) == 1
        assert lop_lines[0].amount == Decimal("500.00")

    def test_zero_lop_produces_no_lop_line(self, tenant_a, employee_a, salary_template_a):
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure, lop_days=Decimal("0"))
        payslip.recompute()
        assert payslip.lop_amount == Decimal("0.00")
        assert not payslip.lines.filter(component_type="lop").exists()


class TestPayslipRecomputeArrearsBonus:
    def test_arrears_and_bonus_add_to_gross_and_produce_lines(
        self, tenant_a, employee_a, salary_template_a,
    ):
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(
            tenant_a, cycle, employee_a, structure,
            arrears_amount=Decimal("200"), bonus_amount=Decimal("300"),
        )
        payslip.recompute()
        # 5000.00 (basic) + 200 (arrears) + 300 (bonus) = 5500.00
        assert payslip.gross_pay == Decimal("5500.00")
        assert payslip.net_pay == Decimal("5500.00")
        types = {l.component_type: l.amount for l in payslip.lines.all()}
        assert types["arrears"] == Decimal("200.00") or types["arrears"] == Decimal("200")
        assert types["bonus"] == Decimal("300.00") or types["bonus"] == Decimal("300")

    def test_zero_arrears_and_bonus_produce_no_lines(self, tenant_a, employee_a, salary_template_a):
        from apps.hrm.models import PayComponent, SalaryStructureLine
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure)
        payslip.recompute()
        types = {l.component_type for l in payslip.lines.all()}
        assert "arrears" not in types
        assert "bonus" not in types


class TestPayslipRecomputeCTCScaling:
    def test_same_template_different_employee_ctc_yields_different_pct_amounts(
        self, tenant_a, employee_a, employee_a2, salary_template_a,
    ):
        """The CTC-scaling fix: a pct_of_ctc line resolves against the EMPLOYEE's assigned CTC (via
        EmployeeSalaryStructure.annual_ctc_amount), not the template's own annual_ctc_amount."""
        from apps.hrm.models import PayComponent, SalaryStructureLine
        hra = PayComponent.objects.create(
            tenant=tenant_a, name="HRA", component_type="earning",
            calculation_type="pct_of_ctc", default_percentage=Decimal("10"),
        )
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=hra)

        structure_1 = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        structure_2 = _make_structure(tenant_a, employee_a2, salary_template_a, Decimal("240000"))

        cycle = _make_cycle(tenant_a)
        payslip_1 = _make_payslip(tenant_a, cycle, employee_a, structure_1)
        payslip_1.recompute()
        payslip_2 = _make_payslip(tenant_a, cycle, employee_a2, structure_2)
        payslip_2.recompute()

        # employee_a: 10% of 120000 / 12 = 1000.00/mo; employee_a2: 10% of 240000 / 12 = 2000.00/mo
        assert payslip_1.gross_pay == Decimal("1000.00")
        assert payslip_2.gross_pay == Decimal("2000.00")
        assert payslip_1.gross_pay != payslip_2.gross_pay


class TestPayslipRecomputeLockGuard:
    def test_recompute_raises_when_cycle_locked(self, tenant_a, employee_a, salary_template_a):
        structure = _make_structure(tenant_a, employee_a, salary_template_a, Decimal("120000"))
        cycle = _make_cycle(tenant_a, status="locked")
        payslip = _make_payslip(tenant_a, cycle, employee_a, structure)
        with pytest.raises(ValidationError):
            payslip.recompute()

    def test_recompute_with_no_salary_structure_yields_zero(self, tenant_a, employee_a):
        """No salary_structure attached -> gross/net all zero, no crash."""
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, None)
        payslip.recompute()
        assert payslip.gross_pay == Decimal("0.00")
        assert payslip.total_deductions == Decimal("0.00")
        assert payslip.net_pay == Decimal("0.00")


# ================================================================ Payslip.clean()
class TestPayslipClean:
    def test_days_worked_exceeds_days_in_period_raises(self, tenant_a, employee_a):
        from apps.hrm.models import Payslip
        cycle = _make_cycle(tenant_a)
        payslip = Payslip(
            tenant=tenant_a, cycle=cycle, employee=employee_a,
            days_in_period=30, days_worked=31,
        )
        with pytest.raises(ValidationError) as exc:
            payslip.clean()
        assert "days_worked" in exc.value.message_dict

    def test_lop_days_exceeds_days_in_period_raises(self, tenant_a, employee_a):
        from apps.hrm.models import Payslip
        cycle = _make_cycle(tenant_a)
        payslip = Payslip(
            tenant=tenant_a, cycle=cycle, employee=employee_a,
            days_in_period=30, days_worked=30, lop_days=Decimal("31"),
        )
        with pytest.raises(ValidationError) as exc:
            payslip.clean()
        assert "lop_days" in exc.value.message_dict

    @pytest.mark.parametrize("field", ["arrears_amount", "bonus_amount", "lop_days"])
    def test_negative_values_raise(self, tenant_a, employee_a, field):
        from apps.hrm.models import Payslip
        cycle = _make_cycle(tenant_a)
        kwargs = {"tenant": tenant_a, "cycle": cycle, "employee": employee_a,
                  "days_in_period": 30, "days_worked": 30, field: Decimal("-1")}
        payslip = Payslip(**kwargs)
        with pytest.raises(ValidationError) as exc:
            payslip.clean()
        assert field in exc.value.message_dict

    def test_valid_payslip_passes_clean(self, tenant_a, employee_a):
        from apps.hrm.models import Payslip
        cycle = _make_cycle(tenant_a)
        payslip = Payslip(
            tenant=tenant_a, cycle=cycle, employee=employee_a,
            days_in_period=30, days_worked=28, lop_days=Decimal("2"),
        )
        payslip.clean()  # must not raise

    def test_number_auto_assigns(self, tenant_a, employee_a):
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, None)
        assert payslip.number.startswith("PSL-")

    def test_unique_together_tenant_cycle_employee(self, tenant_a, employee_a):
        cycle = _make_cycle(tenant_a)
        _make_payslip(tenant_a, cycle, employee_a, None)
        with pytest.raises(IntegrityError):
            _make_payslip(tenant_a, cycle, employee_a, None)

    def test_str(self, tenant_a, employee_a):
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, None)
        assert str(payslip) == f"{payslip.number} · {employee_a} · {cycle.number}"

    def test_is_locked_mirrors_cycle(self, tenant_a, employee_a):
        cycle = _make_cycle(tenant_a, status="locked")
        payslip = _make_payslip(tenant_a, cycle, employee_a, None)
        assert payslip.is_locked is True


# ================================================================ PayslipLine
class TestPayslipLineModel:
    def test_component_type_choices_include_synthetic_types(self, tenant_a, employee_a):
        from apps.hrm.models import PayslipLine
        choice_values = {c[0] for c in PayslipLine.COMPONENT_TYPE_CHOICES}
        assert {"arrears", "bonus", "lop"}.issubset(choice_values)
        # Plus the base PayComponent types.
        assert {"earning", "statutory_deduction", "voluntary_deduction", "reimbursement", "variable"}.issubset(
            choice_values)

    def test_str(self, tenant_a, employee_a):
        from apps.hrm.models import PayslipLine
        cycle = _make_cycle(tenant_a)
        payslip = _make_payslip(tenant_a, cycle, employee_a, None)
        line = PayslipLine.objects.create(
            tenant=tenant_a, payslip=payslip, component_name="Basic Pay",
            component_type="earning", amount=Decimal("5000.00"),
        )
        assert str(line)  # just needs to not crash and return something sensible
