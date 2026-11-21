"""Unit and functional view tests for Quality Management Sub-module 12.15 Process Validation & Verification.

Tests all views, workflows, filters, command centers, and exports:
- ValidationProtocol (list, detail, create, edit, delete, export)
- ProcessCapabilityStudy (list, detail, create, edit, delete, export)
- ComputerSystemValidation (list, detail, create, edit, delete, export)
- CleaningValidation (list, detail, create, edit, delete, export)
- ProcessValidationDashboard (dashboard overview)
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models import (
    ValidationProtocol,
    ProcessCapabilityStudy,
    ComputerSystemValidation,
    CleaningValidation,
)


@pytest.mark.django_db
class TestProcessValidationViews:
    """Test all function-based views in ProcessValidation package."""

    # --- 1. ValidationProtocol Views ---

    def test_processvalidation_protocol_list_view(self, client, admin_user, validation_protocol_a):
        """Verify validation_protocol_list returns 200 with filters and annotated counts."""
        client.force_login(admin_user)
        url = reverse("quality:validation_protocol_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "validation_protocols" in resp.context
        assert "total_count" in resp.context
        assert validation_protocol_a.title.encode() in resp.content

        # Test filter params
        resp_filtered = client.get(url, {
            "q": "Autoclave",
            "stage": "iq",
            "target_type": "equipment",
            "status": "draft",
        })
        assert resp_filtered.status_code == 200

    def test_processvalidation_protocol_detail_view(self, client, admin_user, validation_protocol_a):
        """Verify validation_protocol_detail passes expected context and returns 200."""
        client.force_login(admin_user)
        url = reverse("quality:validation_protocol_detail", kwargs={"pk": validation_protocol_a.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["validation_protocol"] == validation_protocol_a
        assert validation_protocol_a.number.encode() in resp.content

    def test_processvalidation_protocol_create_view(self, client, admin_user, tenant_a, quality_department, doc_a):
        """Verify validation_protocol_create GET returns 200 and POST redirects to detail."""
        client.force_login(admin_user)
        url = reverse("quality:validation_protocol_create")

        # GET
        resp_get = client.get(url)
        assert resp_get.status_code == 200

        # POST
        data = {
            "title": "Depyrogenation Tunnel PQ Protocol",
            "protocol_stage": "pq",
            "target_type": "equipment",
            "status": "draft",
            "revalidation_trigger": "initial",
            "equipment_tag": "EQ-DEP-01",
            "test_runs_planned": 3,
            "test_runs_completed": 0,
            "department": quality_department.pk,
            "lead_author": admin_user.pk,
            "qa_reviewer": admin_user.pk,
            "governing_document": doc_a.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        new_obj = ValidationProtocol.objects.filter(title="Depyrogenation Tunnel PQ Protocol").first()
        assert new_obj is not None
        assert new_obj.tenant == tenant_a
        assert resp_post.url == reverse("quality:validation_protocol_detail", kwargs={"pk": new_obj.pk})

    def test_processvalidation_protocol_edit_view(self, client, admin_user, validation_protocol_a):
        """Verify validation_protocol_edit GET returns 200 and POST updates object."""
        client.force_login(admin_user)
        url = reverse("quality:validation_protocol_edit", kwargs={"pk": validation_protocol_a.pk})

        resp_get = client.get(url)
        assert resp_get.status_code == 200

        data = {
            "title": "Autoclave 01 Modified Protocol",
            "protocol_stage": validation_protocol_a.protocol_stage,
            "target_type": validation_protocol_a.target_type,
            "status": "approved_for_execution",
            "revalidation_trigger": validation_protocol_a.revalidation_trigger,
            "test_runs_planned": 5,
            "lead_author": admin_user.pk,
            "qa_reviewer": admin_user.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        validation_protocol_a.refresh_from_db()
        assert validation_protocol_a.title == "Autoclave 01 Modified Protocol"
        assert validation_protocol_a.status == "approved_for_execution"
        assert validation_protocol_a.test_runs_planned == 5

    def test_processvalidation_protocol_delete_view(self, client, admin_user, validation_protocol_a):
        """Verify validation_protocol_delete removes object and redirects to list."""
        client.force_login(admin_user)
        url = reverse("quality:validation_protocol_delete", kwargs={"pk": validation_protocol_a.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert resp.url == reverse("quality:validation_protocol_list")
        assert not ValidationProtocol.objects.filter(pk=validation_protocol_a.pk).exists()

    def test_processvalidation_protocol_export_csv(self, client, admin_user, validation_protocol_a):
        """Verify validation_protocol_export returns streaming CSV with proper headers."""
        client.force_login(admin_user)
        url = reverse("quality:validation_protocol_export")
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert "attachment; filename=" in resp["Content-Disposition"]
        assert validation_protocol_a.number.encode() in resp.content

    # --- 2. ProcessCapabilityStudy Views ---

    def test_processvalidation_capability_study_list_view(self, client, admin_user, process_capability_study_a):
        """Verify process_capability_study_list returns 200 with filters."""
        client.force_login(admin_user)
        url = reverse("quality:process_capability_study_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "capability_studies" in resp.context
        assert process_capability_study_a.title.encode() in resp.content

        # Test query filter
        resp_filtered = client.get(url, {"q": "Tablet", "category": "weight_mass"})
        assert resp_filtered.status_code == 200

    def test_processvalidation_capability_study_detail_view(self, client, admin_user, process_capability_study_a):
        """Verify process_capability_study_detail passes expected context and returns 200."""
        client.force_login(admin_user)
        url = reverse("quality:process_capability_study_detail", kwargs={"pk": process_capability_study_a.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["capability_study"] == process_capability_study_a

    def test_processvalidation_capability_study_create_view(self, client, admin_user, tenant_a, validation_protocol_a):
        """Verify process_capability_study_create POST creates study and calculates indices."""
        client.force_login(admin_user)
        url = reverse("quality:process_capability_study_create")

        resp_get = client.get(url)
        assert resp_get.status_code == 200

        data = {
            "title": "Packaging Line Seal Temp Study",
            "parameter_name": "Sealing Temp",
            "parameter_category": "temperature",
            "unit_of_measure": "C",
            "upper_spec_limit": "155.0000",
            "lower_spec_limit": "145.0000",
            "target_nominal": "150.0000",
            "subgroup_size": 5,
            "number_of_subgroups": 20,
            "total_samples": 100,
            "mean_value": "150.1000",
            "within_subgroup_stdev": "0.9500",
            "overall_stdev": "1.0200",
            "is_normally_distributed": True,
            "status": "draft",
            "validation_protocol": validation_protocol_a.pk,
            "investigator": admin_user.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        new_obj = ProcessCapabilityStudy.objects.filter(title="Packaging Line Seal Temp Study").first()
        assert new_obj is not None
        assert new_obj.cp_index is not None
        assert resp_post.url == reverse("quality:process_capability_study_detail", kwargs={"pk": new_obj.pk})

    def test_processvalidation_capability_study_edit_view(self, client, admin_user, process_capability_study_a):
        """Verify process_capability_study_edit updates study data."""
        client.force_login(admin_user)
        url = reverse("quality:process_capability_study_edit", kwargs={"pk": process_capability_study_a.pk})

        resp_get = client.get(url)
        assert resp_get.status_code == 200

        data = {
            "title": "Updated Tablet Study Title",
            "parameter_name": process_capability_study_a.parameter_name,
            "parameter_category": process_capability_study_a.parameter_category,
            "unit_of_measure": process_capability_study_a.unit_of_measure,
            "upper_spec_limit": str(process_capability_study_a.upper_spec_limit),
            "lower_spec_limit": str(process_capability_study_a.lower_spec_limit),
            "subgroup_size": 5,
            "number_of_subgroups": 25,
            "total_samples": 125,
            "mean_value": "501.0000",
            "within_subgroup_stdev": "4.1500",
            "overall_stdev": "4.5000",
            "is_normally_distributed": True,
            "status": "analyzed",
            "investigator": admin_user.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        process_capability_study_a.refresh_from_db()
        assert process_capability_study_a.title == "Updated Tablet Study Title"
        assert process_capability_study_a.status == "analyzed"

    def test_processvalidation_capability_study_delete_view(self, client, admin_user, process_capability_study_a):
        """Verify capability study delete removes object."""
        client.force_login(admin_user)
        url = reverse("quality:process_capability_study_delete", kwargs={"pk": process_capability_study_a.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert not ProcessCapabilityStudy.objects.filter(pk=process_capability_study_a.pk).exists()

    def test_processvalidation_capability_study_export_csv(self, client, admin_user, process_capability_study_a):
        """Verify CSV export streams with proper filename and content."""
        client.force_login(admin_user)
        url = reverse("quality:process_capability_study_export")
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert process_capability_study_a.number.encode() in resp.content

    # --- 3. ComputerSystemValidation Views ---

    def test_processvalidation_csv_list_view(self, client, admin_user, computer_system_validation_a):
        """Verify computer_system_validation_list returns 200 with filters."""
        client.force_login(admin_user)
        url = reverse("quality:computer_system_validation_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "computer_systems" in resp.context
        assert computer_system_validation_a.system_name.encode() in resp.content

        # Test filters
        resp_filtered = client.get(url, {"q": "MasterQMS", "gamp": "cat_4_configured"})
        assert resp_filtered.status_code == 200

    def test_processvalidation_csv_detail_view(self, client, admin_user, computer_system_validation_a):
        """Verify computer_system_validation_detail returns 200."""
        client.force_login(admin_user)
        url = reverse("quality:computer_system_validation_detail", kwargs={"pk": computer_system_validation_a.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["computer_system"] == computer_system_validation_a

    def test_processvalidation_csv_create_view(self, client, admin_user, tenant_a):
        """Verify computer_system_validation_create creates new CSV entry."""
        client.force_login(admin_user)
        url = reverse("quality:computer_system_validation_create")

        resp_get = client.get(url)
        assert resp_get.status_code == 200

        data = {
            "system_name": "Agilent OpenLab CDS",
            "version_release": "v3.1.0",
            "vendor_name": "Agilent Technologies",
            "gamp_category": "cat_4_configured",
            "gxp_impact": "direct_gxp",
            "validation_approach": "traditional_csv",
            "hosting_model": "on_premises",
            "is_part_11_compliant": True,
            "requires_audit_trail": True,
            "has_disaster_recovery_plan": True,
            "traceability_status": "drafting",
            "status": "in_qualification",
            "system_owner": admin_user.pk,
            "quality_lead": admin_user.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        new_obj = ComputerSystemValidation.objects.filter(system_name="Agilent OpenLab CDS").first()
        assert new_obj is not None
        assert resp_post.url == reverse("quality:computer_system_validation_detail", kwargs={"pk": new_obj.pk})

    def test_processvalidation_csv_edit_view(self, client, admin_user, computer_system_validation_a):
        """Verify computer_system_validation_edit updates system validation."""
        client.force_login(admin_user)
        url = reverse("quality:computer_system_validation_edit", kwargs={"pk": computer_system_validation_a.pk})

        resp_get = client.get(url)
        assert resp_get.status_code == 200

        data = {
            "system_name": computer_system_validation_a.system_name,
            "version_release": "v4.2.2-patch1",
            "vendor_name": computer_system_validation_a.vendor_name,
            "gamp_category": computer_system_validation_a.gamp_category,
            "gxp_impact": computer_system_validation_a.gxp_impact,
            "validation_approach": computer_system_validation_a.validation_approach,
            "hosting_model": computer_system_validation_a.hosting_model,
            "is_part_11_compliant": True,
            "requires_audit_trail": True,
            "has_disaster_recovery_plan": True,
            "traceability_status": "matrix_verified",
            "status": "validated_live",
            "system_owner": admin_user.pk,
            "quality_lead": admin_user.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        computer_system_validation_a.refresh_from_db()
        assert computer_system_validation_a.version_release == "v4.2.2-patch1"
        assert computer_system_validation_a.status == "validated_live"

    def test_processvalidation_csv_delete_view(self, client, admin_user, computer_system_validation_a):
        """Verify computer_system_validation_delete removes system."""
        client.force_login(admin_user)
        url = reverse("quality:computer_system_validation_delete", kwargs={"pk": computer_system_validation_a.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert not ComputerSystemValidation.objects.filter(pk=computer_system_validation_a.pk).exists()

    def test_processvalidation_csv_export(self, client, admin_user, computer_system_validation_a):
        """Verify computer system validation export generates streaming CSV."""
        client.force_login(admin_user)
        url = reverse("quality:computer_system_validation_export")
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert computer_system_validation_a.number.encode() in resp.content

    # --- 4. CleaningValidation Views ---

    def test_processvalidation_cleaning_list_view(self, client, admin_user, cleaning_validation_a):
        """Verify cleaning_validation_list returns 200 with filters."""
        client.force_login(admin_user)
        url = reverse("quality:cleaning_validation_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "cleaning_validations" in resp.context
        assert cleaning_validation_a.title.encode() in resp.content

        # Test filters
        resp_filtered = client.get(url, {"q": "Granulator", "method": "hplc"})
        assert resp_filtered.status_code == 200

    def test_processvalidation_cleaning_detail_view(self, client, admin_user, cleaning_validation_a):
        """Verify cleaning_validation_detail returns 200."""
        client.force_login(admin_user)
        url = reverse("quality:cleaning_validation_detail", kwargs={"pk": cleaning_validation_a.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["cleaning_validation"] == cleaning_validation_a

    def test_processvalidation_cleaning_create_view(self, client, admin_user, tenant_a, doc_a):
        """Verify cleaning_validation_create creates new study and computes MACO."""
        client.force_login(admin_user)
        url = reverse("quality:cleaning_validation_create")

        resp_get = client.get(url)
        assert resp_get.status_code == 200

        data = {
            "title": "Coater 01 Cleaning Validation",
            "equipment_train_tag": "COAT-01",
            "target_residue": "Aspirin Active Marker",
            "cleaning_agent_used": "CIP-100 Wash + Purified Water Rinse",
            "worst_case_rationale": "hardest_to_clean",
            "calculation_basis": "ten_ppm_limit",
            "smallest_batch_size_kg": "250.000",
            "safety_factor": "1000.0",
            "total_surface_area_sqcm": "150000.00",
            "swab_sampling_area_sqcm": "25.00",
            "rinse_volume_liters": "200.00",
            "analytical_method": "toc",
            "method_recovery_percentage": "82.50",
            "dirty_hold_time_hours": "48.0",
            "clean_hold_time_hours": "72.0",
            "consecutive_successful_runs": 0,
            "is_visually_clean": True,
            "cleaning_status": "draft",
            "cleaning_sop": doc_a.pk,
            "analytical_lead": admin_user.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        new_obj = CleaningValidation.objects.filter(title="Coater 01 Cleaning Validation").first()
        assert new_obj is not None
        assert new_obj.calculated_maco_mg is not None
        assert resp_post.url == reverse("quality:cleaning_validation_detail", kwargs={"pk": new_obj.pk})

    def test_processvalidation_cleaning_edit_view(self, client, admin_user, cleaning_validation_a):
        """Verify cleaning_validation_edit updates cleaning study."""
        client.force_login(admin_user)
        url = reverse("quality:cleaning_validation_edit", kwargs={"pk": cleaning_validation_a.pk})

        resp_get = client.get(url)
        assert resp_get.status_code == 200

        data = {
            "title": cleaning_validation_a.title,
            "equipment_train_tag": cleaning_validation_a.equipment_train_tag,
            "target_residue": cleaning_validation_a.target_residue,
            "cleaning_agent_used": cleaning_validation_a.cleaning_agent_used,
            "worst_case_rationale": cleaning_validation_a.worst_case_rationale,
            "calculation_basis": cleaning_validation_a.calculation_basis,
            "smallest_batch_size_kg": str(cleaning_validation_a.smallest_batch_size_kg),
            "safety_factor": str(cleaning_validation_a.safety_factor),
            "total_surface_area_sqcm": str(cleaning_validation_a.total_surface_area_sqcm),
            "swab_sampling_area_sqcm": str(cleaning_validation_a.swab_sampling_area_sqcm),
            "rinse_volume_liters": str(cleaning_validation_a.rinse_volume_liters),
            "analytical_method": cleaning_validation_a.analytical_method,
            "method_recovery_percentage": str(cleaning_validation_a.method_recovery_percentage),
            "dirty_hold_time_hours": str(cleaning_validation_a.dirty_hold_time_hours),
            "clean_hold_time_hours": str(cleaning_validation_a.clean_hold_time_hours),
            "consecutive_successful_runs": 3,
            "is_visually_clean": True,
            "cleaning_status": "validated_pass",
            "cleaning_sop": cleaning_validation_a.cleaning_sop_id,
            "analytical_lead": admin_user.pk,
        }
        resp_post = client.post(url, data)
        assert resp_post.status_code == 302
        cleaning_validation_a.refresh_from_db()
        assert cleaning_validation_a.cleaning_status == "validated_pass"

    def test_processvalidation_cleaning_delete_view(self, client, admin_user, cleaning_validation_a):
        """Verify cleaning study delete removes object."""
        client.force_login(admin_user)
        url = reverse("quality:cleaning_validation_delete", kwargs={"pk": cleaning_validation_a.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert not CleaningValidation.objects.filter(pk=cleaning_validation_a.pk).exists()

    def test_processvalidation_cleaning_export_csv(self, client, admin_user, cleaning_validation_a):
        """Verify cleaning export produces streaming CSV."""
        client.force_login(admin_user)
        url = reverse("quality:cleaning_validation_export")
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert cleaning_validation_a.number.encode() in resp.content

    # --- 5. Dashboard View ---

    def test_processvalidation_dashboard_view(self, client, admin_user, validation_protocol_a, process_capability_study_a, computer_system_validation_a, cleaning_validation_a):
        """Verify process_validation_dashboard returns 200 with summary KPIs and recent records."""
        client.force_login(admin_user)
        url = reverse("quality:process_validation_dashboard")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "total_protocols" in resp.context
        assert "total_studies" in resp.context
        assert "total_systems" in resp.context
        assert "total_cleaning" in resp.context
        assert "recent_protocols" in resp.context
        assert "recent_studies" in resp.context
        assert "recent_systems" in resp.context
        assert "recent_cleaning" in resp.context
