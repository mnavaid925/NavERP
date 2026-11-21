"""View tests for Sub-module 12.16: Environmental, Health & Safety (EHS)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models.EhsManagement.HazardousMaterials import HazardousMaterial
from apps.quality.models.EhsManagement.SafetyIncidents import SafetyIncident
from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLog
from apps.quality.models.EhsManagement.WasteDisposalManifests import WasteDisposalManifest


# ==============================================================================
# EHS Dashboard View Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_dashboard_view(client_a, hazardous_material_a, safety_incident_a, environmental_monitoring_log_a, waste_disposal_manifest_a):
    url = reverse("quality:ehs_dashboard")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "active_materials_count" in response.context
    assert "expiring_sds_count" in response.context
    assert "total_incidents_count" in response.context
    assert "dart_cases_count" in response.context
    assert "active_excursions_count" in response.context
    assert "pending_manifests_count" in response.context
    assert "overdue_accumulation_count" in response.context
    assert response.context["active_materials_count"] >= 1


@pytest.mark.django_db
def test_ehsmanagement_dashboard_export(client_a):
    url = reverse("quality:ehs_dashboard_export")
    response = client_a.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "ehs_dashboard_kpis_" in response["Content-Disposition"]


# ==============================================================================
# HazardousMaterial View Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_list(client_a, hazardous_material_a):
    url = reverse("quality:hazardous_material_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "hazardous_materials" in response.context
    assert len(response.context["hazardous_materials"]) >= 1

    # Filter with search and status
    response = client_a.get(url, {"q": "Isopropyl", "status": "active"})
    assert response.status_code == 200
    assert len(response.context["hazardous_materials"]) >= 1

    # Junk filter parameters (L11 resilience)
    response = client_a.get(url, {"org_unit": "invalid_alpha", "supplier": "xyz", "page": "invalid_page"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_detail(client_a, hazardous_material_a):
    url = reverse("quality:hazardous_material_detail", kwargs={"pk": hazardous_material_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["hazardous_material"] == hazardous_material_a
    assert "IPA Cleanroom Grade" in response.content.decode()


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_create(client_a, admin_user, supplier_party_a, quality_department):
    url = reverse("quality:hazardous_material_create")
    response = client_a.get(url)
    assert response.status_code == 200

    post_data = {
        "material_name": "Ethanol Anhydrous 99.5%",
        "trade_name": "Decon Ethanol",
        "cas_number": "64-17-5",
        "un_number": "UN1170",
        "physical_state": "liquid",
        "ghs_signal_word": "danger",
        "ghs_pictograms": "GHS02",
        "hazard_statements": "Highly flammable liquid and vapor.",
        "precautionary_statements": "Keep away from heat, sparks, open flames.",
        "nfpa_health": 2,
        "nfpa_flammability": 3,
        "nfpa_instability": 0,
        "nfpa_special_hazard": "none",
        "maximum_storage_quantity": "250.00",
        "quantity_uom": "L",
        "supplier": str(supplier_party_a.pk),
        "org_unit": str(quality_department.pk),
        "managed_by": str(admin_user.pk),
        "status": "active",
    }
    response = client_a.post(url, post_data)
    assert response.status_code == 302
    created = HazardousMaterial.objects.filter(material_name="Ethanol Anhydrous 99.5%").first()
    assert created is not None
    assert created.number.startswith("QHAZ-")


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_update(client_a, hazardous_material_a, admin_user, supplier_party_a, quality_department):
    url = reverse("quality:hazardous_material_update", kwargs={"pk": hazardous_material_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200

    post_data = {
        "material_name": "Isopropyl Alcohol 99% USP Revised",
        "trade_name": hazardous_material_a.trade_name,
        "cas_number": hazardous_material_a.cas_number,
        "un_number": hazardous_material_a.un_number,
        "physical_state": hazardous_material_a.physical_state,
        "ghs_signal_word": hazardous_material_a.ghs_signal_word,
        "nfpa_health": 2,
        "nfpa_flammability": 3,
        "nfpa_instability": 0,
        "nfpa_special_hazard": "none",
        "maximum_storage_quantity": "600.00",
        "quantity_uom": "L",
        "supplier": str(supplier_party_a.pk),
        "org_unit": str(quality_department.pk),
        "managed_by": str(admin_user.pk),
        "status": "active",
    }
    response = client_a.post(url, post_data)
    assert response.status_code == 302
    hazardous_material_a.refresh_from_db()
    assert hazardous_material_a.material_name == "Isopropyl Alcohol 99% USP Revised"
    assert hazardous_material_a.maximum_storage_quantity == Decimal("600.00")


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_delete(client_a, tenant_a, admin_user, supplier_party_a, quality_department):
    mat_to_delete = HazardousMaterial.objects.create(
        tenant=tenant_a,
        material_name="Temporary Chemical To Delete",
        physical_state="liquid",
        ghs_signal_word="warning",
        nfpa_health=1,
        nfpa_flammability=0,
        nfpa_instability=0,
        supplier=supplier_party_a,
        org_unit=quality_department,
        managed_by=admin_user,
        status="active",
    )
    url = reverse("quality:hazardous_material_delete", kwargs={"pk": mat_to_delete.pk})
    response = client_a.post(url)
    assert response.status_code == 302
    assert not HazardousMaterial.objects.filter(pk=mat_to_delete.pk).exists()


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_label_and_export(client_a, hazardous_material_a):
    label_url = reverse("quality:hazardous_material_label", kwargs={"pk": hazardous_material_a.pk})
    response = client_a.get(label_url)
    assert response.status_code == 200
    assert "NFPA 704" in response.content.decode()

    export_url = reverse("quality:hazardous_material_export")
    response = client_a.get(export_url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "hazardous_materials_" in response["Content-Disposition"]


# ==============================================================================
# SafetyIncident View Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_list_and_detail(client_a, safety_incident_a):
    list_url = reverse("quality:safety_incident_list")
    response = client_a.get(list_url)
    assert response.status_code == 200
    assert "safety_incidents" in response.context
    assert len(response.context["safety_incidents"]) >= 1

    detail_url = reverse("quality:safety_incident_detail", kwargs={"pk": safety_incident_a.pk})
    response = client_a.get(detail_url)
    assert response.status_code == 200
    assert response.context["safety_incident"] == safety_incident_a


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_create_and_investigate(client_a, admin_user, quality_department):
    create_url = reverse("quality:safety_incident_create")
    post_data = {
        "title": "Minor Trip Over Extension Cord In Cleanroom Airlock",
        "incident_date": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "report_date": timezone.now().date().isoformat(),
        "incident_type": "near_miss",
        "severity": "minor",
        "org_unit": str(quality_department.pk),
        "location_details": "Airlock 2 Floor",
        "reported_by": str(admin_user.pk),
        "affected_person": str(admin_user.pk),
        "affected_party_type": "employee",
        "nature_of_injury": "none",
        "body_part_affected": "none",
        "medical_treatment_level": "none",
        "is_osha_recordable": False,
        "osha_classification": "non_recordable",
        "lost_workdays_count": 0,
        "restricted_workdays_count": 0,
        "ppe_compliance_status": "compliant",
        "immediate_actions_taken": "Rerouted and taped cord to wall",
        "lead_investigator": str(admin_user.pk),
        "root_cause_category": "environmental_hazard",
    }
    response = client_a.post(create_url, post_data)
    assert response.status_code == 302
    created = SafetyIncident.objects.filter(title="Minor Trip Over Extension Cord In Cleanroom Airlock").first()
    assert created is not None
    assert created.status == "reported"

    # Test workflow transition action: investigate
    action_url = reverse("quality:safety_incident_investigate", kwargs={"pk": created.pk})
    response = client_a.post(action_url)
    assert response.status_code == 302
    created.refresh_from_db()
    assert created.status == "under_review"


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_delete_guard_on_osha_recordable(client_a, safety_incident_a):
    safety_incident_a.is_osha_recordable = True
    safety_incident_a.save()

    delete_url = reverse("quality:safety_incident_delete", kwargs={"pk": safety_incident_a.pk})
    response = client_a.post(delete_url)
    assert response.status_code == 302
    # Should NOT be deleted due to OSHA statutory preservation rule
    assert SafetyIncident.objects.filter(pk=safety_incident_a.pk).exists()


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_export(client_a):
    url = reverse("quality:safety_incident_export")
    response = client_a.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")


# ==============================================================================
# EnvironmentalMonitoringLog View Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_environmental_log_list_and_detail(client_a, environmental_monitoring_log_a):
    list_url = reverse("quality:environmental_monitoring_log_list")
    response = client_a.get(list_url)
    assert response.status_code == 200
    assert "environmental_logs" in response.context

    detail_url = reverse("quality:environmental_monitoring_log_detail", kwargs={"pk": environmental_monitoring_log_a.pk})
    response = client_a.get(detail_url)
    assert response.status_code == 200
    assert response.context["environmental_log"] == environmental_monitoring_log_a


@pytest.mark.django_db
def test_ehsmanagement_environmental_log_create_and_evaluate(client_a, admin_user, quality_department):
    create_url = reverse("quality:environmental_monitoring_log_create")
    post_data = {
        "sampling_point_id": "CR-ISO7-AIR-09",
        "sampling_timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "org_unit": str(quality_department.pk),
        "cleanroom_class": "iso_class_7",
        "operational_state": "in_operation",
        "monitoring_category": "airborne_particles_0_5um",
        "parameter_name": "Airborne Particles >= 0.5 um",
        "measured_value": "110000.000",
        "unit_of_measure": "particles_m3",
        "upper_alert_limit": "250000.000",
        "upper_action_limit": "352000.000",
        "sampled_by": str(admin_user.pk),
    }
    response = client_a.post(create_url, post_data)
    assert response.status_code == 302
    created = EnvironmentalMonitoringLog.objects.filter(sampling_point_id="CR-ISO7-AIR-09").first()
    assert created is not None

    # Test workflow evaluate action
    eval_url = reverse("quality:environmental_monitoring_log_evaluate", kwargs={"pk": created.pk})
    response = client_a.post(eval_url)
    assert response.status_code == 302
    created.refresh_from_db()
    assert created.verified_by == admin_user


@pytest.mark.django_db
def test_ehsmanagement_environmental_log_export(client_a):
    url = reverse("quality:environmental_monitoring_log_export")
    response = client_a.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")


# ==============================================================================
# WasteDisposalManifest View Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_list_and_detail(client_a, waste_disposal_manifest_a):
    list_url = reverse("quality:waste_disposal_manifest_list")
    response = client_a.get(list_url)
    assert response.status_code == 200
    assert "waste_manifests" in response.context

    detail_url = reverse("quality:waste_disposal_manifest_detail", kwargs={"pk": waste_disposal_manifest_a.pk})
    response = client_a.get(detail_url)
    assert response.status_code == 200
    assert response.context["waste_manifest"] == waste_disposal_manifest_a


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_create_and_certify(client_a, admin_user, supplier_party_a, hazardous_material_a, quality_department):
    create_url = reverse("quality:waste_disposal_manifest_create")
    post_data = {
        "manifest_title": "Bi-Weekly Flammable Liquids Consignment",
        "regulatory_manifest_id": "EPA-2026-BW-1102",
        "manifest_type": "hazardous_chemical",
        "generator_org_unit": str(quality_department.pk),
        "generator_epa_id": "MAD998877665",
        "accumulation_start_date": (timezone.now().date() - timedelta(days=5)).isoformat(),
        "waste_description": "Flammable Liquids n.o.s. (Contains Ethanol)",
        "associated_hazardous_material": str(hazardous_material_a.pk),
        "physical_state": "liquid",
        "is_ignitable": True,
        "container_type": "drum_55gal",
        "container_count": 1,
        "quantity_value": "180.00",
        "quantity_uom": "pounds",
        "transporter": str(supplier_party_a.pk),
        "tsdf_facility": str(supplier_party_a.pk),
        "shipment_date": (timezone.now().date() + timedelta(days=3)).isoformat(),
        "certifying_officer": str(admin_user.pk),
    }
    response = client_a.post(create_url, post_data)
    assert response.status_code == 302
    created = WasteDisposalManifest.objects.filter(regulatory_manifest_id="EPA-2026-BW-1102").first()
    assert created is not None

    # Test workflow certify action
    certify_url = reverse("quality:waste_disposal_manifest_certify", kwargs={"pk": created.pk})
    response = client_a.post(certify_url, {
        "certificate_of_disposal_number": "CERT-TSDF-2026-4401",
        "certificate_received_date": timezone.now().date().isoformat(),
    })
    assert response.status_code == 302
    created.refresh_from_db()
    assert created.certificate_of_disposal_number == "CERT-TSDF-2026-4401"
    assert created.has_certificate is True


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_export(client_a):
    url = reverse("quality:waste_disposal_manifest_export")
    response = client_a.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
