"""Tests for HRM 3.13 Salary Structure models: PayComponent, SalaryStructureTemplate,
SalaryStructureLine, EmployeeSalaryStructure."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ PayComponent
class TestPayComponentModel:
    def test_str(self, tenant_a):
        from apps.hrm.models import PayComponent
        pc = PayComponent.objects.create(tenant=tenant_a, name="House Rent Allowance")
        assert str(pc) == "House Rent Allowance"

    def test_unique_together_tenant_name(self, tenant_a):
        from apps.hrm.models import PayComponent
        PayComponent.objects.create(tenant=tenant_a, name="Basic Pay")
        with pytest.raises(IntegrityError):
            PayComponent.objects.create(tenant=tenant_a, name="Basic Pay")

    def test_defaults(self, tenant_a):
        from apps.hrm.models import PayComponent
        pc = PayComponent.objects.create(tenant=tenant_a, name="Basic Pay")
        assert pc.component_type == "earning"
        assert pc.calculation_type == "fixed_amount"
        assert pc.frequency == "monthly"
        assert pc.is_taxable is True
        assert pc.include_in_ctc is True
        assert pc.contribution_side == "employee"
        assert pc.is_active is True
        assert pc.display_order == 0

    def test_clean_fixed_amount_with_default_percentage_raises(self, tenant_a):
        from apps.hrm.models import PayComponent
        pc = PayComponent(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_percentage=Decimal("10"),
        )
        with pytest.raises(ValidationError) as exc:
            pc.clean()
        assert "default_percentage" in exc.value.message_dict

    def test_clean_percentage_calc_with_default_amount_raises(self, tenant_a):
        from apps.hrm.models import PayComponent
        pc = PayComponent(
            tenant=tenant_a, name="HRA", calculation_type="pct_of_basic",
            default_amount=Decimal("500"),
        )
        with pytest.raises(ValidationError) as exc:
            pc.clean()
        assert "default_amount" in exc.value.message_dict

    def test_clean_pct_of_ctc_with_default_amount_raises(self, tenant_a):
        from apps.hrm.models import PayComponent
        pc = PayComponent(
            tenant=tenant_a, name="Bonus", calculation_type="pct_of_ctc",
            default_amount=Decimal("500"),
        )
        with pytest.raises(ValidationError) as exc:
            pc.clean()
        assert "default_amount" in exc.value.message_dict

    def test_clean_consistent_fixed_amount_component_passes(self, tenant_a):
        from apps.hrm.models import PayComponent
        pc = PayComponent(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("50000"),
        )
        pc.clean()  # must not raise

    def test_clean_consistent_percentage_component_passes(self, tenant_a):
        from apps.hrm.models import PayComponent
        pc = PayComponent(
            tenant=tenant_a, name="HRA", calculation_type="pct_of_basic",
            default_percentage=Decimal("40"),
        )
        pc.clean()  # must not raise

    def test_clean_all_blank_defaults_passes(self, tenant_a):
        """A component with neither default set is valid (a line supplies the value)."""
        from apps.hrm.models import PayComponent
        pc = PayComponent(tenant=tenant_a, name="Variable Bonus", calculation_type="pct_of_ctc")
        pc.clean()  # must not raise


# ================================================================ SalaryStructureTemplate
class TestSalaryStructureTemplateModel:
    def test_number_auto_assigns(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate
        tmpl = SalaryStructureTemplate.objects.create(
            tenant=tenant_a, name="Engineering L2", annual_ctc_amount=Decimal("100000"),
        )
        assert tmpl.number.startswith("SST-")

    def test_str(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="Engineering L2")
        assert str(tmpl) == f"{tmpl.number} · Engineering L2"

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="Engineering L2")
        with pytest.raises(IntegrityError):
            SalaryStructureTemplate.objects.create(
                tenant=tenant_a, name="Duplicate Number", number=tmpl.number,
            )

    def test_computed_ctc_total_empty_template(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="Empty Template")
        assert tmpl.computed_ctc_total == Decimal("0")

    def test_computed_ctc_total_sums_lines(self, tenant_a):
        """A fixed-amount line + a pct-of-ctc line must sum to the exact derived Decimal total."""
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(
            tenant=tenant_a, name="Engineering L2", annual_ctc_amount=Decimal("120000"),
        )
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
        )
        hra = PayComponent.objects.create(
            tenant=tenant_a, name="HRA", calculation_type="pct_of_basic",
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=tmpl, pay_component=basic, amount=Decimal("60000"),
        )
        SalaryStructureLine.objects.create(
            tenant=tenant_a, template=tmpl, pay_component=hra, percentage=Decimal("40"),
        )
        # 60000 (fixed) + 120000 * 40% = 60000 + 48000 = 108000.00
        assert tmpl.computed_ctc_total == Decimal("108000.00")


# ================================================================ SalaryStructureLine.resolved_amount()
class TestSalaryStructureLineResolvedAmount:
    def test_fixed_amount_uses_line_amount(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="T1")
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("40000"),
        )
        line = SalaryStructureLine.objects.create(
            tenant=tenant_a, template=tmpl, pay_component=comp, amount=Decimal("55000"),
        )
        assert line.resolved_amount() == Decimal("55000")

    def test_fixed_amount_falls_back_to_component_default(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="T1")
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", calculation_type="fixed_amount",
            default_amount=Decimal("40000"),
        )
        line = SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)
        assert line.resolved_amount() == Decimal("40000")

    def test_fixed_amount_no_amount_no_default_returns_zero(self, tenant_a):
        """No crash — returns Decimal('0') when neither the line nor the component supplies an amount."""
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="T1")
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="Ad-hoc Allowance", calculation_type="fixed_amount",
        )
        line = SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)
        assert line.resolved_amount() == Decimal("0")

    def test_percentage_uses_line_percentage_against_template_ctc(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(
            tenant=tenant_a, name="T1", annual_ctc_amount=Decimal("100000"),
        )
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="HRA", calculation_type="pct_of_basic",
            default_percentage=Decimal("10"),
        )
        line = SalaryStructureLine.objects.create(
            tenant=tenant_a, template=tmpl, pay_component=comp, percentage=Decimal("40"),
        )
        assert line.resolved_amount() == Decimal("40000.00")

    def test_percentage_falls_back_to_component_default_percentage(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(
            tenant=tenant_a, name="T1", annual_ctc_amount=Decimal("100000"),
        )
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="HRA", calculation_type="pct_of_basic",
            default_percentage=Decimal("25"),
        )
        line = SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)
        assert line.resolved_amount() == Decimal("25000.00")

    def test_percentage_no_percentage_no_default_returns_zero(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(
            tenant=tenant_a, name="T1", annual_ctc_amount=Decimal("100000"),
        )
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="Bonus", calculation_type="pct_of_ctc",
        )
        line = SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)
        assert line.resolved_amount() == Decimal("0")

    def test_percentage_no_ctc_on_template_returns_zero(self, tenant_a):
        """Template has no annual_ctc_amount set — the pct base is Decimal('0')."""
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="T1")
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="HRA", calculation_type="pct_of_basic",
            default_percentage=Decimal("40"),
        )
        line = SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)
        assert line.resolved_amount() == Decimal("0.00")

    def test_line_calculation_type_override_beats_component(self, tenant_a):
        """Component is fixed_amount, but the line overrides calculation_type to pct_of_basic —
        the line's calc type must win."""
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(
            tenant=tenant_a, name="T1", annual_ctc_amount=Decimal("100000"),
        )
        comp = PayComponent.objects.create(
            tenant=tenant_a, name="Flexible Comp", calculation_type="fixed_amount",
            default_amount=Decimal("5000"),
        )
        line = SalaryStructureLine.objects.create(
            tenant=tenant_a, template=tmpl, pay_component=comp,
            calculation_type="pct_of_basic", percentage=Decimal("5"),
        )
        assert line.resolved_amount() == Decimal("5000.00")

    def test_str(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="T1")
        comp = PayComponent.objects.create(tenant=tenant_a, name="Basic Pay")
        line = SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)
        assert str(line) == f"{tmpl} · {comp}"

    def test_unique_together_tenant_template_pay_component(self, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate, SalaryStructureLine, PayComponent
        tmpl = SalaryStructureTemplate.objects.create(tenant=tenant_a, name="T1")
        comp = PayComponent.objects.create(tenant=tenant_a, name="Basic Pay")
        SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)
        with pytest.raises(IntegrityError):
            SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=comp)


# ================================================================ EmployeeSalaryStructure
class TestEmployeeSalaryStructureModel:
    def test_number_auto_assigns(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        ess = EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"),
        )
        assert ess.number.startswith("ESS-")

    def test_str(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        ess = EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"),
        )
        assert str(ess) == f"{ess.number} · {employee_a}"

    def test_defaults(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        ess = EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"),
        )
        assert ess.status == "active"
        assert ess.effective_to is None

    def test_unique_together_tenant_number(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        ess = EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"), status="superseded",
        )
        with pytest.raises(IntegrityError):
            EmployeeSalaryStructure.objects.create(
                tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("90000"),
                number=ess.number, status="superseded",
            )

    def test_clean_effective_to_before_from_raises(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        ess = EmployeeSalaryStructure(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"),
            effective_from=datetime.date(2026, 6, 1), effective_to=datetime.date(2026, 5, 1),
            status="superseded",
        )
        with pytest.raises(ValidationError) as exc:
            ess.clean()
        assert "effective_to" in exc.value.message_dict

    def test_clean_effective_to_equal_from_passes(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        ess = EmployeeSalaryStructure(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"),
            effective_from=datetime.date(2026, 6, 1), effective_to=datetime.date(2026, 6, 1),
            status="superseded",
        )
        ess.clean()  # must not raise

    def test_clean_second_active_for_same_employee_raises(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"), status="active",
        )
        second = EmployeeSalaryStructure(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("90000"), status="active",
        )
        with pytest.raises(ValidationError) as exc:
            second.clean()
        assert "status" in exc.value.message_dict

    def test_clean_second_superseded_for_same_employee_allowed(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeSalaryStructure
        EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"), status="active",
        )
        second = EmployeeSalaryStructure(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("70000"), status="superseded",
        )
        second.clean()  # must not raise — superseded rows don't compete for the one-active slot

    def test_clean_editing_the_existing_active_row_excludes_self(self, tenant_a, employee_a):
        """Re-saving/clean()-ing the SAME active row (pk set) must not clash with itself."""
        from apps.hrm.models import EmployeeSalaryStructure
        ess = EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"), status="active",
        )
        ess.annual_ctc_amount = Decimal("85000")
        ess.clean()  # must not raise

    def test_active_check_is_tenant_scoped(
        self, tenant_a, tenant_b, employee_a, employee_b,
    ):
        """tenant_a and tenant_b can each have their own active assignment for their own (different)
        employees — validates that the clash query filters via self.employee.tenant_id and doesn't
        leak across tenants."""
        from apps.hrm.models import EmployeeSalaryStructure
        EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"), status="active",
        )
        b_assignment = EmployeeSalaryStructure(
            tenant=tenant_b, employee=employee_b, annual_ctc_amount=Decimal("70000"), status="active",
        )
        b_assignment.clean()  # must not raise — tenant_b's employee has no clashing active row yet
        b_assignment.save()
        assert EmployeeSalaryStructure.objects.filter(tenant=tenant_b, employee=employee_b, status="active").exists()

    def test_clean_derives_tenant_from_employee_when_tenant_blank(self, tenant_a, employee_a):
        """Mirrors the ModelForm create flow (FloatingHolidayElection precedent): tenant isn't set on
        the instance yet — clean() must derive tenant scoping from employee.tenant_id."""
        from apps.hrm.models import EmployeeSalaryStructure
        EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("80000"), status="active",
        )
        second = EmployeeSalaryStructure(employee=employee_a, annual_ctc_amount=Decimal("90000"), status="active")
        with pytest.raises(ValidationError):
            second.clean()
