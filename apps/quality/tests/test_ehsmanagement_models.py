"""Unit tests for Sub-module 12.16: Environmental, Health & Safety (EHS) Models."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.quality.models.EhsManagement.HazardousMaterials import HazardousMaterial
from apps.quality.models.EhsManagement.SafetyIncidents import SafetyIncident
from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLog
from apps.quality.models.EhsManagement.WasteDisposalManifests import WasteDisposalManifest


# ==============================================================================
# HazardousMaterial Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_creation_and_autonumber(tenant_a, admin_user, supplier_party_a, quality_department):
    material = HazardousMaterial.objects.create(
        tenant=tenant_a,
        material_name="Sulfuric Acid 96%",
        cas_number="7664-93-9",
        physical_state="liquid",
        ghs_signal_word="danger",
        ghs_pictograms="GHS05",
        nfpa_health=3,
        nfpa_flammability=0,
        nfpa_instability=2,
        nfpa_special_hazard="w_slash",
        storage_location_code="ACID-CAB-01",
        maximum_storage_quantity=Decimal("100.00"),
        quantity_uom="L",
        supplier=supplier_party_a,
        org_unit=quality_department,
        managed_by=admin_user,
        status="active",
    )
    assert material.pk is not None
    assert material.number.startswith("QHAZ-")
    assert str(material) == f"{material.number} \u2014 Sulfuric Acid 96%"
    assert material.status == "active"
    assert material.status_css == "badge-green"
    assert material.signal_word_css == "badge-red"
    assert material.pictograms_list == ["GHS05"]


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_sds_properties(hazardous_material_a):
    today = timezone.now().date()
    # Initially has valid expiry 730 days ahead
    assert hazardous_material_a.is_sds_expired is False
    assert hazardous_material_a.sds_status_css == "badge-green"

    # SDS expiring within 90 days
    hazardous_material_a.sds_expiry_date = today + timedelta(days=60)
    assert hazardous_material_a.is_sds_expired is False
    assert hazardous_material_a.sds_status_css == "badge-amber"

    # Expired SDS
    hazardous_material_a.sds_expiry_date = today - timedelta(days=10)
    assert hazardous_material_a.is_sds_expired is True
    assert hazardous_material_a.sds_status_css == "badge-red"

    # No SDS expiry date configured
    hazardous_material_a.sds_expiry_date = None
    assert hazardous_material_a.is_sds_expired is False
    assert hazardous_material_a.sds_status_css == "badge-slate"


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_nfpa_validation(hazardous_material_a):
    hazardous_material_a.nfpa_health = 5
    with pytest.raises(ValidationError):
        hazardous_material_a.full_clean()

    hazardous_material_a.nfpa_health = 4
    hazardous_material_a.full_clean()  # Should not raise


# ==============================================================================
# SafetyIncident Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_creation_and_autonumber(safety_incident_a):
    assert safety_incident_a.pk is not None
    assert safety_incident_a.number.startswith("QSIR-")
    assert str(safety_incident_a) == f"{safety_incident_a.number} \u2014 {safety_incident_a.title}"
    assert safety_incident_a.status == "reported"
    assert safety_incident_a.status_css == "badge-info"
    assert safety_incident_a.severity_css == "badge-slate"
    assert safety_incident_a.osha_css == "badge-slate"
    assert safety_incident_a.is_dart_incident is False
    assert safety_incident_a.total_lost_and_restricted_days == 0


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_dart_and_lost_days(safety_incident_a):
    safety_incident_a.is_osha_recordable = True
    safety_incident_a.lost_workdays_count = 5
    safety_incident_a.restricted_workdays_count = 3
    safety_incident_a.severity = "severe"
    safety_incident_a.status = "investigating"
    safety_incident_a.save()

    assert safety_incident_a.is_dart_incident is True
    assert safety_incident_a.total_lost_and_restricted_days == 8
    assert safety_incident_a.osha_css == "badge-red"
    assert safety_incident_a.severity_css == "badge-amber"
    assert safety_incident_a.status_css == "badge-amber"


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_affected_person_display(tenant_a, admin_user):
    # Test affected company employee
    incident_emp = SafetyIncident(
        tenant=tenant_a,
        title="Test Employee Incident",
        incident_date=timezone.now(),
        reported_by=admin_user,
        affected_person=admin_user,
    )
    assert incident_emp.affected_person_display == (admin_user.get_full_name() or admin_user.username)

    # Test contractor / non-employee party
    incident_ext = SafetyIncident(
        tenant=tenant_a,
        title="Test Contractor Incident",
        incident_date=timezone.now(),
        reported_by=admin_user,
        affected_person=None,
        affected_party_name="John Contractor",
        affected_party_type="contractor",
    )
    assert "John Contractor" in incident_ext.affected_person_display
    assert "Contractor" in incident_ext.affected_person_display

    # Test unspecified
    incident_none = SafetyIncident(
        tenant=tenant_a,
        title="Test Near Miss Unspecified",
        incident_date=timezone.now(),
        reported_by=admin_user,
        affected_person=None,
        affected_party_name="",
    )
    assert incident_none.affected_person_display == "Not specified"


# ==============================================================================
# EnvironmentalMonitoringLog Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_environmental_log_autonumber_and_str(environmental_monitoring_log_a):
    assert environmental_monitoring_log_a.pk is not None
    assert environmental_monitoring_log_a.number.startswith("QENV-")
    assert str(environmental_monitoring_log_a) == f"{environmental_monitoring_log_a.number} \u2014 CR-ISO7-ZONE-B4 (Airborne Particles >= 0.5 um)"
    assert environmental_monitoring_log_a.evaluation_status == "normal"
    assert environmental_monitoring_log_a.evaluation_status_css == "badge-green"
    assert environmental_monitoring_log_a.is_excursion is False
    assert "ISO Class 7" in environmental_monitoring_log_a.cleanroom_display


@pytest.mark.django_db
def test_ehsmanagement_environmental_log_auto_evaluation(tenant_a, admin_user, quality_department):
    # Value exceeding upper alert limit (250,000) but below action limit (352,000)
    log_alert = EnvironmentalMonitoringLog.objects.create(
        tenant=tenant_a,
        sampling_point_id="CR-ISO7-ZONE-C1",
        sampling_timestamp=timezone.now(),
        org_unit=quality_department,
        cleanroom_class="iso_class_7",
        parameter_name="Airborne Particles >= 0.5 um",
        measured_value=Decimal("280000.000"),
        unit_of_measure="particles_m3",
        upper_alert_limit=Decimal("250000.000"),
        upper_action_limit=Decimal("352000.000"),
        sampled_by=admin_user,
    )
    assert log_alert.evaluation_status == "alert_exceeded"
    assert log_alert.is_excursion is True
    assert log_alert.evaluation_status_css == "badge-amber"

    # Value exceeding upper action limit (352,000)
    log_action = EnvironmentalMonitoringLog.objects.create(
        tenant=tenant_a,
        sampling_point_id="CR-ISO7-ZONE-C2",
        sampling_timestamp=timezone.now(),
        org_unit=quality_department,
        cleanroom_class="iso_class_7",
        parameter_name="Airborne Particles >= 0.5 um",
        measured_value=Decimal("360000.000"),
        unit_of_measure="particles_m3",
        upper_alert_limit=Decimal("250000.000"),
        upper_action_limit=Decimal("352000.000"),
        sampled_by=admin_user,
    )
    assert log_action.evaluation_status == "action_exceeded"
    assert log_action.is_excursion is True
    assert log_action.evaluation_status_css == "badge-red"

    # Invalid sample should preserve its status without being recalculated
    log_invalid = EnvironmentalMonitoringLog.objects.create(
        tenant=tenant_a,
        sampling_point_id="CR-ISO7-ZONE-C3",
        sampling_timestamp=timezone.now(),
        org_unit=quality_department,
        cleanroom_class="iso_class_7",
        parameter_name="Airborne Particles >= 0.5 um",
        measured_value=Decimal("999999.000"),
        evaluation_status="invalid_sample",
        sampled_by=admin_user,
    )
    assert log_invalid.evaluation_status == "invalid_sample"
    assert log_invalid.is_excursion is False


# ==============================================================================
# WasteDisposalManifest Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_autonumber_and_str(waste_disposal_manifest_a):
    assert waste_disposal_manifest_a.pk is not None
    assert waste_disposal_manifest_a.number.startswith("QWST-")
    assert str(waste_disposal_manifest_a) == f"{waste_disposal_manifest_a.number} \u2014 EPA-009182371-JJK (Q4 Spent Solvent and Debris)"
    assert waste_disposal_manifest_a.status == "draft"
    assert waste_disposal_manifest_a.status_css == "badge-slate"
    assert waste_disposal_manifest_a.manifest_type_css == "badge-red"
    assert waste_disposal_manifest_a.has_certificate is False


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_accumulation_and_overdue(waste_disposal_manifest_a):
    today = timezone.now().date()
    # 20 days ago start, shipment date is 7 days ahead: accumulation_days is days until shipment = 27 days
    assert waste_disposal_manifest_a.accumulation_days == 27
    assert waste_disposal_manifest_a.is_accumulation_overdue is False

    # Overdue accumulation (> 90 days in draft)
    waste_disposal_manifest_a.accumulation_start_date = today - timedelta(days=95)
    waste_disposal_manifest_a.shipment_date = None
    assert waste_disposal_manifest_a.accumulation_days >= 95
    assert waste_disposal_manifest_a.is_accumulation_overdue is True

    # Overdue is cleared once manifest is shipped
    waste_disposal_manifest_a.status = "in_transit"
    assert waste_disposal_manifest_a.is_accumulation_overdue is False


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_certificate_property(waste_disposal_manifest_a):
    assert waste_disposal_manifest_a.has_certificate is False

    waste_disposal_manifest_a.certificate_of_disposal_number = "CERT-CH-2026-9901"
    assert waste_disposal_manifest_a.has_certificate is True

    waste_disposal_manifest_a.certificate_of_disposal_number = ""
    waste_disposal_manifest_a.certificate_received_date = timezone.now().date()
    assert waste_disposal_manifest_a.has_certificate is True
