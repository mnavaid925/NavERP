"""Unit tests for Quality Management Sub-module 12.15 Process Validation & Verification forms.

Tests forms:
- ValidationProtocolForm
- ProcessCapabilityStudyForm
- ComputerSystemValidationForm
- CleaningValidationForm
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from apps.quality.forms import (
    ValidationProtocolForm,
    ProcessCapabilityStudyForm,
    ComputerSystemValidationForm,
    CleaningValidationForm,
)


@pytest.mark.django_db
class TestProcessValidationForms:
    """Test validation logic, tenant scoping, reject_foreign, and security exclusions."""

    # --- 1. ValidationProtocolForm Tests ---

    def test_processvalidation_protocol_form_valid(self, tenant_a, admin_user, quality_department, doc_a):
        """Verify ValidationProtocolForm validates correct input and tenant scopes user FKs."""
        data = {
            "title": "Autoclave 02 Sterilizer Qualification",
            "description": "Comprehensive steam sterilization protocol.",
            "protocol_stage": "iq",
            "target_type": "equipment",
            "status": "draft",
            "revalidation_trigger": "initial",
            "equipment_tag": "EQ-AC-02",
            "process_name": "Moist Heat Sterilization",
            "facility_area": "Suite A",
            "item_code": "PART-001",
            "target_completion_date": date(2026, 12, 1),
            "test_runs_planned": 3,
            "test_runs_completed": 0,
            "acceptance_criteria": "Temperature >= 121 C for 15 min.",
            "department": quality_department.pk,
            "lead_author": admin_user.pk,
            "qa_reviewer": admin_user.pk,
            "governing_document": doc_a.pk,
        }
        form = ValidationProtocolForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_processvalidation_protocol_form_security_exclusions(self):
        """Verify system fields (tenant, number, timestamps) are strictly excluded from form."""
        form = ValidationProtocolForm()
        excluded = ["tenant", "number", "created_at", "updated_at"]
        for field in excluded:
            assert field not in form.fields, f"{field} should be excluded from ValidationProtocolForm"

    def test_processvalidation_protocol_form_reject_foreign(self, tenant_a, admin_user, doc_b):
        """Verify foreign tenant FK (doc_b) is rejected by reject_foreign."""
        data = {
            "title": "Autoclave 02 Sterilizer Qualification",
            "protocol_stage": "iq",
            "target_type": "equipment",
            "status": "draft",
            "revalidation_trigger": "initial",
            "test_runs_planned": 3,
            "lead_author": admin_user.pk,
            "qa_reviewer": admin_user.pk,
            "governing_document": doc_b.pk,  # Tenant B document injected!
        }
        form = ValidationProtocolForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "governing_document" in form.errors

    # --- 2. ProcessCapabilityStudyForm Tests ---

    def test_processvalidation_capability_study_form_valid(self, tenant_a, admin_user, validation_protocol_a):
        """Verify ProcessCapabilityStudyForm validates correct input."""
        data = {
            "title": "Vial Capping Torque Study",
            "parameter_name": "Removal Torque",
            "parameter_category": "torque",
            "unit_of_measure": "in-lbs",
            "upper_spec_limit": "15.0000",
            "lower_spec_limit": "5.0000",
            "target_nominal": "10.0000",
            "subgroup_size": 5,
            "number_of_subgroups": 20,
            "total_samples": 100,
            "mean_value": "10.0500",
            "within_subgroup_stdev": "0.8500",
            "overall_stdev": "0.9000",
            "is_normally_distributed": True,
            "status": "draft",
            "validation_protocol": validation_protocol_a.pk,
            "investigator": admin_user.pk,
        }
        form = ProcessCapabilityStudyForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_processvalidation_capability_study_form_spec_limit_validation(self, tenant_a, admin_user):
        """Verify USL <= LSL triggers validation error."""
        data = {
            "title": "Invalid Limit Study",
            "parameter_name": "Diameter",
            "parameter_category": "dimensional_thickness",
            "unit_of_measure": "mm",
            "upper_spec_limit": "5.0000",
            "lower_spec_limit": "10.0000",  # USL < LSL!
            "mean_value": "8.0000",
            "overall_stdev": "1.0000",
            "status": "draft",
            "investigator": admin_user.pk,
        }
        form = ProcessCapabilityStudyForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "upper_spec_limit" in form.errors

    def test_processvalidation_capability_study_form_security_exclusions(self):
        """Verify system fields are excluded from ProcessCapabilityStudyForm."""
        form = ProcessCapabilityStudyForm()
        excluded = [
            "tenant", "number", "created_at", "updated_at",
            "cp_index", "cpk_index", "pp_index", "ppk_index",
            "expected_ppm", "capability_determination",
        ]
        for field in excluded:
            assert field not in form.fields, f"{field} should be excluded from ProcessCapabilityStudyForm"

    # --- 3. ComputerSystemValidationForm Tests ---

    def test_processvalidation_csv_form_valid(self, tenant_a, admin_user, validation_protocol_a, doc_a):
        """Verify ComputerSystemValidationForm validates proper system registration."""
        data = {
            "system_name": "TrackWise Electronic QMS",
            "version_release": "v10.1.2",
            "vendor_name": "Sparta Systems",
            "gamp_category": "cat_4_configured",
            "gxp_impact": "direct_gxp",
            "validation_approach": "csa_risk_based",
            "hosting_model": "cloud_saas",
            "is_part_11_compliant": True,
            "requires_audit_trail": True,
            "has_disaster_recovery_plan": True,
            "traceability_status": "matrix_verified",
            "status": "planning",
            "system_owner": admin_user.pk,
            "quality_lead": admin_user.pk,
            "validation_protocol": validation_protocol_a.pk,
            "urs_document": doc_a.pk,
        }
        form = ComputerSystemValidationForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_processvalidation_csv_form_reject_foreign(self, tenant_a, admin_user, validation_protocol_b):
        """Verify cross-tenant validation_protocol injection is rejected."""
        data = {
            "system_name": "Injected CSV",
            "version_release": "v1.0",
            "vendor_name": "Vendor",
            "gamp_category": "cat_4_configured",
            "gxp_impact": "direct_gxp",
            "validation_approach": "csa_risk_based",
            "hosting_model": "cloud_saas",
            "system_owner": admin_user.pk,
            "quality_lead": admin_user.pk,
            "validation_protocol": validation_protocol_b.pk,  # Tenant B protocol!
        }
        form = ComputerSystemValidationForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "validation_protocol" in form.errors

    # --- 4. CleaningValidationForm Tests ---

    def test_processvalidation_cleaning_form_valid(self, tenant_a, admin_user, doc_a):
        """Verify CleaningValidationForm validates standard 10 ppm limit data."""
        data = {
            "title": "Fluid Bed Dryer Cleaning Study",
            "equipment_train_tag": "FBD-02",
            "target_residue": "Aspirin Active Ingredient",
            "cleaning_agent_used": "CIP-100 Alkaline Wash",
            "worst_case_rationale": "highest_potency",
            "calculation_basis": "ten_ppm_limit",
            "smallest_batch_size_kg": "120.000",
            "safety_factor": "1000.0",
            "total_surface_area_sqcm": "80000.00",
            "swab_sampling_area_sqcm": "25.00",
            "rinse_volume_liters": "150.00",
            "analytical_method": "toc",
            "method_recovery_percentage": "85.00",
            "dirty_hold_time_hours": "24.0",
            "clean_hold_time_hours": "48.0",
            "consecutive_successful_runs": 0,
            "is_visually_clean": True,
            "cleaning_status": "draft",
            "cleaning_sop": doc_a.pk,
            "analytical_lead": admin_user.pk,
        }
        form = CleaningValidationForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_processvalidation_cleaning_form_therapeutic_dose_requires_dose_fields(self, tenant_a, admin_user, doc_a):
        """Verify therapeutic_dose calculation basis requires min_daily_dose_active_mg and max_daily_dose_subsequent_mg."""
        data = {
            "title": "Dose Basis Cleaning Study",
            "equipment_train_tag": "MIX-01",
            "target_residue": "API-A",
            "cleaning_agent_used": "WFI",
            "worst_case_rationale": "highest_potency",
            "calculation_basis": "therapeutic_dose",
            "smallest_batch_size_kg": "100.000",
            "total_surface_area_sqcm": "50000.00",
            "dirty_hold_time_hours": "24.0",
            "clean_hold_time_hours": "48.0",
            "cleaning_status": "draft",
            "cleaning_sop": doc_a.pk,
            "analytical_lead": admin_user.pk,
            # Missing min_daily_dose_active_mg and max_daily_dose_subsequent_mg!
        }
        form = CleaningValidationForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "min_daily_dose_active_mg" in form.errors
        assert "max_daily_dose_subsequent_mg" in form.errors

    def test_processvalidation_cleaning_form_toxicological_pde_requires_pde(self, tenant_a, admin_user, doc_a):
        """Verify toxicological_pde calculation basis requires toxicological_pde_mg_day."""
        data = {
            "title": "PDE Basis Cleaning Study",
            "equipment_train_tag": "MIX-01",
            "target_residue": "API-Tox",
            "cleaning_agent_used": "WFI",
            "worst_case_rationale": "highest_toxicity_pde",
            "calculation_basis": "toxicological_pde",
            "smallest_batch_size_kg": "100.000",
            "total_surface_area_sqcm": "50000.00",
            "dirty_hold_time_hours": "24.0",
            "clean_hold_time_hours": "48.0",
            "cleaning_status": "draft",
            "cleaning_sop": doc_a.pk,
            "analytical_lead": admin_user.pk,
            # Missing toxicological_pde_mg_day and max_daily_dose_subsequent_mg!
        }
        form = CleaningValidationForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "toxicological_pde_mg_day" in form.errors
        assert "max_daily_dose_subsequent_mg" in form.errors

    def test_processvalidation_cleaning_form_security_exclusions(self):
        """Verify calculated limit fields are excluded from form fields."""
        form = CleaningValidationForm()
        excluded = [
            "tenant", "number", "created_at", "updated_at",
            "calculated_maco_mg", "calculated_swab_limit_ug", "calculated_rinse_limit_ppm",
        ]
        for field in excluded:
            assert field not in form.fields, f"{field} should be excluded from CleaningValidationForm"
