"""Unit tests for Quality Management Sub-module 12.15 Process Validation & Verification models.

Tests models:
- ValidationProtocol (QVAL)
- ProcessCapabilityStudy (QCPK)
- ComputerSystemValidation (QCSV)
- CleaningValidation (QCLN)
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.quality.models import (
    ValidationProtocol,
    ProcessCapabilityStudy,
    ComputerSystemValidation,
    CleaningValidation,
)


@pytest.mark.django_db
class TestProcessValidationModels:
    """Test invariants, computed properties, auto-numbering, and constraints on 12.15 models."""

    # --- 1. ValidationProtocol Tests ---

    def test_processvalidation_validation_protocol_creation(self, validation_protocol_a, tenant_a, admin_user):
        """Verify ValidationProtocol auto-numbering, properties, and string representation."""
        assert validation_protocol_a.number.startswith("QVAL-")
        assert validation_protocol_a.tenant == tenant_a
        assert str(validation_protocol_a) == f"{validation_protocol_a.number} - {validation_protocol_a.title}"
        assert validation_protocol_a.test_runs_planned == 3
        assert validation_protocol_a.test_runs_completed == 0
        assert validation_protocol_a.progress_percentage == 0
        assert validation_protocol_a.stage_css == "badge-info"
        assert validation_protocol_a.status_css == "badge-muted"

    def test_processvalidation_validation_protocol_progress_calculation(self, validation_protocol_a):
        """Verify execution progress percentage calculation and edge case handling."""
        validation_protocol_a.test_runs_planned = 4
        validation_protocol_a.test_runs_completed = 2
        assert validation_protocol_a.progress_percentage == 50

        validation_protocol_a.test_runs_completed = 4
        assert validation_protocol_a.progress_percentage == 100

        # Over-completion capped at 100%
        validation_protocol_a.test_runs_completed = 6
        assert validation_protocol_a.progress_percentage == 100

        # Zero planned runs defaults to 0% unless final_approved
        validation_protocol_a.test_runs_planned = 0
        validation_protocol_a.status = "draft"
        assert validation_protocol_a.progress_percentage == 0

        validation_protocol_a.status = "final_approved"
        assert validation_protocol_a.progress_percentage == 100

    def test_processvalidation_validation_protocol_is_revalidation_overdue(self, validation_protocol_a):
        """Verify is_revalidation_overdue respects dates and terminal statuses."""
        today = timezone.now().date()
        validation_protocol_a.revalidation_due_date = today - timedelta(days=5)
        validation_protocol_a.status = "final_approved"
        assert validation_protocol_a.is_revalidation_overdue is True

        # Future date is not overdue
        validation_protocol_a.revalidation_due_date = today + timedelta(days=10)
        assert validation_protocol_a.is_revalidation_overdue is False

        # Terminal statuses (rejected, superseded) are excluded from overdue flag
        validation_protocol_a.revalidation_due_date = today - timedelta(days=5)
        validation_protocol_a.status = "rejected"
        assert validation_protocol_a.is_revalidation_overdue is False

        validation_protocol_a.status = "superseded"
        assert validation_protocol_a.is_revalidation_overdue is False

    def test_processvalidation_validation_protocol_is_overdue(self, validation_protocol_a):
        """Verify target completion is_overdue property."""
        today = timezone.now().date()
        validation_protocol_a.target_completion_date = today - timedelta(days=3)
        validation_protocol_a.status = "in_execution"
        assert validation_protocol_a.is_overdue is True

        validation_protocol_a.status = "final_approved"
        assert validation_protocol_a.is_overdue is False

    # --- 2. ProcessCapabilityStudy Tests ---

    def test_processvalidation_process_capability_study_creation(self, process_capability_study_a, tenant_a):
        """Verify ProcessCapabilityStudy auto-numbering, fields, and string representation."""
        assert process_capability_study_a.number.startswith("QCPK-")
        assert process_capability_study_a.tenant == tenant_a
        assert str(process_capability_study_a) == f"{process_capability_study_a.number} - {process_capability_study_a.parameter_name} ({process_capability_study_a.title})"
        assert process_capability_study_a.upper_spec_limit == Decimal("525.0000")
        assert process_capability_study_a.lower_spec_limit == Decimal("475.0000")
        assert process_capability_study_a.tolerance_width == Decimal("50.0000")
        assert process_capability_study_a.determination_css == "badge-green"
        assert process_capability_study_a.status_css == "badge-muted"

    def test_processvalidation_capability_indices_calculation(self, process_capability_study_a):
        """Verify statistical indices calculation (Cp, Cpk, Pp, Ppk) and determination categorization."""
        # Mean perfectly centered at 500, sigma = 5
        # USL = 525, LSL = 475 -> Tolerance = 50
        # Cp = 50 / (6 * 5) = 1.667
        # Cpu = (525 - 500) / 15 = 1.667, Cpl = (500 - 475) / 15 = 1.667 -> Cpk = 1.667
        process_capability_study_a.mean_value = Decimal("500.0000")
        process_capability_study_a.within_subgroup_stdev = Decimal("5.0000")
        process_capability_study_a.overall_stdev = Decimal("5.0000")
        process_capability_study_a.calculate_indices()

        assert process_capability_study_a.cp_index == Decimal("1.667")
        assert process_capability_study_a.cpk_index == Decimal("1.667")
        assert process_capability_study_a.pp_index == Decimal("1.667")
        assert process_capability_study_a.ppk_index == Decimal("1.667")
        assert process_capability_study_a.capability_determination in ("capable", "highly_capable")

    def test_processvalidation_capability_indices_off_center(self, process_capability_study_a):
        """Verify off-center process reduces Cpk while Cp remains constant."""
        # USL = 525, LSL = 475, Tolerance = 50, sigma = 5 -> Cp = 1.667
        # Mean shifted to 515:
        # Cpu = (525 - 515) / 15 = 0.667
        # Cpl = (515 - 475) / 15 = 2.667 -> Cpk = 0.667 (incapable)
        process_capability_study_a.mean_value = Decimal("515.0000")
        process_capability_study_a.within_subgroup_stdev = Decimal("5.0000")
        process_capability_study_a.overall_stdev = Decimal("5.0000")
        process_capability_study_a.calculate_indices()

        assert process_capability_study_a.cp_index == Decimal("1.667")
        assert process_capability_study_a.cpk_index == Decimal("0.667")
        assert process_capability_study_a.capability_determination == "incapable"

    def test_processvalidation_capability_indices_tolerance_zero(self, process_capability_study_a):
        """Verify invalid or inverted tolerance returns early without crash."""
        process_capability_study_a.lower_spec_limit = Decimal("525.0000")
        process_capability_study_a.upper_spec_limit = Decimal("500.0000")
        process_capability_study_a.calculate_indices()
        # Returns early without updating
        assert process_capability_study_a.tolerance_width <= Decimal("0")

    # --- 3. ComputerSystemValidation Tests ---

    def test_processvalidation_csv_creation(self, computer_system_validation_a, tenant_a):
        """Verify ComputerSystemValidation auto-numbering, properties, and string representation."""
        assert computer_system_validation_a.number.startswith("QCSV-")
        assert computer_system_validation_a.tenant == tenant_a
        assert str(computer_system_validation_a) == f"{computer_system_validation_a.number} - {computer_system_validation_a.system_name} ({computer_system_validation_a.version_release})"
        assert computer_system_validation_a.status_css == "badge-slate"
        assert computer_system_validation_a.gamp_css == "badge-green"

    def test_processvalidation_csv_review_overdue(self, computer_system_validation_a):
        """Verify periodic review overdue check correctly handles past and future dates."""
        today = timezone.now().date()
        computer_system_validation_a.next_review_due = today - timedelta(days=1)
        computer_system_validation_a.status = "validated_live"
        assert computer_system_validation_a.is_review_overdue is True

        computer_system_validation_a.next_review_due = today + timedelta(days=30)
        assert computer_system_validation_a.is_review_overdue is False

        # Decommissioned systems are not considered overdue
        computer_system_validation_a.next_review_due = today - timedelta(days=1)
        computer_system_validation_a.status = "decommissioned"
        assert computer_system_validation_a.is_review_overdue is False

    # --- 4. CleaningValidation Tests ---

    def test_processvalidation_cleaning_validation_creation(self, cleaning_validation_a, tenant_a):
        """Verify CleaningValidation auto-numbering, fields, and string representation."""
        assert cleaning_validation_a.number.startswith("QCLN-")
        assert cleaning_validation_a.tenant == tenant_a
        assert str(cleaning_validation_a) == f"{cleaning_validation_a.number} - {cleaning_validation_a.target_residue} ({cleaning_validation_a.equipment_train_tag})"
        assert cleaning_validation_a.consecutive_successful_runs == 3
        assert cleaning_validation_a.status_css == "badge-slate"

    def test_processvalidation_cleaning_validation_is_revalidation_overdue(self, cleaning_validation_a):
        """Verify cleaning revalidation overdue check."""
        today = timezone.now().date()
        cleaning_validation_a.next_revalidation_date = today - timedelta(days=2)
        cleaning_validation_a.cleaning_status = "validated_pass"
        assert cleaning_validation_a.is_revalidation_overdue is True

        cleaning_validation_a.cleaning_status = "expired"
        assert cleaning_validation_a.is_revalidation_overdue is False

    def test_processvalidation_cleaning_validation_limits_ten_ppm(self, cleaning_validation_a):
        """Verify 10 ppm default calculation basis generates expected MACO and swab/rinse limits."""
        cleaning_validation_a.calculation_basis = "ten_ppm_limit"
        cleaning_validation_a.smallest_batch_size_kg = Decimal("200.000")
        cleaning_validation_a.total_surface_area_sqcm = Decimal("100000.00")
        cleaning_validation_a.swab_sampling_area_sqcm = Decimal("25.00")
        cleaning_validation_a.rinse_volume_liters = Decimal("100.00")
        cleaning_validation_a.method_recovery_percentage = Decimal("80.00")

        # 10 ppm of 200 kg = 2000 mg MACO
        # Surface area = 100,000 cm2 -> Limit per cm2 = 2000 mg / 100,000 cm2 = 0.02 mg/cm2 = 20 ug/cm2
        # Swab limit (25 cm2 coupon) = 25 * 20 ug = 500 ug * 0.8 recovery = 400 ug
        # Rinse limit (100 L) = 2000 mg / 100 L = 20 ppm
        cleaning_validation_a.calculate_limits()

        assert cleaning_validation_a.calculated_maco_mg == Decimal("2000.0000")
        assert cleaning_validation_a.calculated_swab_limit_ug == Decimal("400.000")
        assert cleaning_validation_a.calculated_rinse_limit_ppm == Decimal("20.000")

    def test_processvalidation_cleaning_validation_limits_therapeutic_dose(self, cleaning_validation_a):
        """Verify therapeutic dose calculation basis: MACO = (MinDoseA / SafetyFactor) * (SmallestBatchB / MaxDoseB)."""
        cleaning_validation_a.calculation_basis = "therapeutic_dose"
        cleaning_validation_a.min_daily_dose_active_mg = Decimal("500.0000")
        cleaning_validation_a.safety_factor = Decimal("1000.0")
        cleaning_validation_a.smallest_batch_size_kg = Decimal("100.000")  # 100,000,000 mg
        cleaning_validation_a.max_daily_dose_subsequent_mg = Decimal("20.0000")
        cleaning_validation_a.total_surface_area_sqcm = Decimal("50000.00")
        cleaning_validation_a.swab_sampling_area_sqcm = Decimal("25.00")
        cleaning_validation_a.rinse_volume_liters = Decimal("50.00")
        cleaning_validation_a.method_recovery_percentage = Decimal("100.00")

        # MACO = (500 / 1000) * (100,000,000 / 20) mg = 0.5 * 5,000,000 = 2,500,000 mg = 2500 g
        cleaning_validation_a.calculate_limits()
        assert cleaning_validation_a.calculated_maco_mg == Decimal("2500000.0000")
        # Surface limit = 2,500,000 mg / 50,000 cm2 = 50 mg/cm2 = 50,000 ug/cm2
        # Swab limit = 25 cm2 * 50,000 ug/cm2 = 1,250,000 ug
        assert cleaning_validation_a.calculated_swab_limit_ug == Decimal("1250000.000")

    def test_processvalidation_cleaning_validation_limits_toxicological_pde(self, cleaning_validation_a):
        """Verify toxicological PDE calculation: MACO = (PDE * SmallestBatchB_mg) / MaxDoseB_mg."""
        cleaning_validation_a.calculation_basis = "toxicological_pde"
        cleaning_validation_a.toxicological_pde_mg_day = Decimal("10.0000")
        cleaning_validation_a.smallest_batch_size_kg = Decimal("50.000")  # 50,000,000 mg
        cleaning_validation_a.max_daily_dose_subsequent_mg = Decimal("25.0000")
        cleaning_validation_a.total_surface_area_sqcm = Decimal("50000.00")
        cleaning_validation_a.swab_sampling_area_sqcm = Decimal("25.00")
        cleaning_validation_a.rinse_volume_liters = Decimal("100.00")
        cleaning_validation_a.method_recovery_percentage = Decimal("100.00")

        # MACO = (10 * 50,000,000) / 25 = 20,000,000 mg
        cleaning_validation_a.calculate_limits()
        assert cleaning_validation_a.calculated_maco_mg == Decimal("20000000.0000")
