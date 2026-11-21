"""Unit tests for Sub-module 12.16: Environmental, Health & Safety (EHS) Forms."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.quality.forms.EhsManagement.HazardousMaterials import HazardousMaterialForm
from apps.quality.forms.EhsManagement.SafetyIncidents import SafetyIncidentForm
from apps.quality.forms.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLogForm
from apps.quality.forms.EhsManagement.WasteDisposalManifests import WasteDisposalManifestForm


# ==============================================================================
# HazardousMaterialForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_form_valid(tenant_a, admin_user, supplier_party_a, quality_department, doc_a):
    form_data = {
        "material_name": "Hydrochloric Acid 37%",
        "trade_name": "Muriatic Acid Clean Grade",
        "cas_number": "7647-01-0",
        "un_number": "UN1789",
        "chemical_formula": "HCl",
        "physical_state": "liquid",
        "ghs_signal_word": "danger",
        "ghs_pictograms": "GHS05",
        "hazard_statements": "Causes severe skin burns and eye damage.",
        "precautionary_statements": "Wear protective gloves/protective clothing/eye protection.",
        "nfpa_health": 3,
        "nfpa_flammability": 0,
        "nfpa_instability": 1,
        "nfpa_special_hazard": "cor",
        "sds_revision": "Rev 2.0",
        "sds_issue_date": (timezone.now().date() - timedelta(days=30)).isoformat(),
        "sds_expiry_date": (timezone.now().date() + timedelta(days=700)).isoformat(),
        "sds_document": str(doc_a.pk),
        "osha_pel": "5 ppm Ceiling",
        "acgih_tlv": "2 ppm Ceiling",
        "exposure_uom": "ppm",
        "ppe_requirements": "Acid-resistant gloves, apron, full face shield",
        "incompatible_materials": "Strong bases, strong oxidizing agents, metals",
        "spill_cleanup_procedure": "Neutralize with lime or sodium bicarbonate",
        "org_unit": str(quality_department.pk),
        "storage_location_code": "ACID-CAB-02",
        "maximum_storage_quantity": "50.00",
        "quantity_uom": "L",
        "supplier": str(supplier_party_a.pk),
        "status": "active",
        "managed_by": str(admin_user.pk),
        "notes": "Used for surface activation etching",
    }
    form = HazardousMaterialForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.material_name == "Hydrochloric Acid 37%"
    assert instance.tenant == tenant_a


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_form_reject_foreign(tenant_a, admin_user, supplier_party_b, quality_department):
    form_data = {
        "material_name": "Test Material Foreign Supplier",
        "physical_state": "liquid",
        "ghs_signal_word": "warning",
        "nfpa_health": 1,
        "nfpa_flammability": 1,
        "nfpa_instability": 0,
        "nfpa_special_hazard": "none",
        "org_unit": str(quality_department.pk),
        "supplier": str(supplier_party_b.pk),  # Belongs to tenant_b
        "status": "active",
        "managed_by": str(admin_user.pk),
    }
    form = HazardousMaterialForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier" in form.errors


@pytest.mark.django_db
def test_ehsmanagement_hazardous_material_form_nfpa_bounds(tenant_a, admin_user, quality_department):
    form_data = {
        "material_name": "Invalid NFPA Material",
        "physical_state": "liquid",
        "ghs_signal_word": "warning",
        "nfpa_health": 5,  # Exceeds 4
        "nfpa_flammability": 1,
        "nfpa_instability": 0,
        "nfpa_special_hazard": "none",
        "org_unit": str(quality_department.pk),
        "status": "active",
        "managed_by": str(admin_user.pk),
    }
    form = HazardousMaterialForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "nfpa_health" in form.errors


# ==============================================================================
# SafetyIncidentForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_form_valid(tenant_a, admin_user, quality_department):
    form_data = {
        "title": "Ergonomic Hand Strain at Packaging Cell 1",
        "incident_date": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "report_date": timezone.now().date().isoformat(),
        "incident_type": "injury_illness",
        "severity": "minor",
        "org_unit": str(quality_department.pk),
        "location_details": "Packaging Conveyor Line 1",
        "reported_by": str(admin_user.pk),
        "affected_person": str(admin_user.pk),
        "affected_party_type": "employee",
        "nature_of_injury": "strain_sprain",
        "body_part_affected": "hands_fingers",
        "medical_treatment_level": "first_aid_only",
        "is_osha_recordable": False,
        "osha_classification": "first_aid",
        "lost_workdays_count": 0,
        "restricted_workdays_count": 0,
        "ppe_compliance_status": "compliant",
        "immediate_actions_taken": "Rotated operator to secondary assembly station",
        "lead_investigator": str(admin_user.pk),
        "root_cause_category": "ergonomic_strain",
        "investigation_findings": "High repetitive wrist torque required by manual capping tool",
    }
    form = SafetyIncidentForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.title == "Ergonomic Hand Strain at Packaging Cell 1"
    assert instance.status == "reported"  # Default workflow status preserved


@pytest.mark.django_db
def test_ehsmanagement_safety_incident_form_reject_foreign(tenant_a, admin_user, quality_department_b):
    form_data = {
        "title": "Cross Tenant Incident",
        "incident_date": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "report_date": timezone.now().date().isoformat(),
        "incident_type": "near_miss",
        "severity": "minor",
        "org_unit": str(quality_department_b.pk),  # Belongs to tenant_b
        "reported_by": str(admin_user.pk),
    }
    form = SafetyIncidentForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors


# ==============================================================================
# EnvironmentalMonitoringLogForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_environmental_log_form_valid(tenant_a, admin_user, quality_department):
    form_data = {
        "sampling_point_id": "CR-ISO6-ZONE-D2",
        "sampling_timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "org_unit": str(quality_department.pk),
        "cleanroom_class": "iso_class_6",
        "operational_state": "at_rest",
        "monitoring_category": "airborne_particles_0_5um",
        "parameter_name": "Airborne Particles >= 0.5 um",
        "measured_value": "12000.000",
        "unit_of_measure": "particles_m3",
        "target_nominal_value": "5000.000",
        "lower_alert_limit": "",
        "upper_alert_limit": "25000.000",
        "lower_action_limit": "",
        "upper_action_limit": "35200.000",
        "sampled_by": str(admin_user.pk),
    }
    form = EnvironmentalMonitoringLogForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.cleanroom_class == "iso_class_6"
    assert instance.evaluation_status == "normal"


@pytest.mark.django_db
def test_ehsmanagement_environmental_log_form_limit_validation(tenant_a, admin_user, quality_department):
    # Test lower alert limit exceeding upper alert limit
    form_data = {
        "sampling_point_id": "CR-ISO7-LIMIT-ERR",
        "sampling_timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "org_unit": str(quality_department.pk),
        "cleanroom_class": "iso_class_7",
        "operational_state": "in_operation",
        "monitoring_category": "temperature_humidity",
        "parameter_name": "Relative Humidity %",
        "measured_value": "45.000",
        "unit_of_measure": "percent_rh",
        "lower_alert_limit": "55.000",
        "upper_alert_limit": "40.000",  # lower > upper
        "sampled_by": str(admin_user.pk),
    }
    form = EnvironmentalMonitoringLogForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lower_alert_limit" in form.errors


# ==============================================================================
# WasteDisposalManifestForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_form_valid(tenant_a, admin_user, supplier_party_a, hazardous_material_a, quality_department):
    form_data = {
        "manifest_title": "Monthly Spent Solvent Drums Consignment",
        "regulatory_manifest_id": "EPA-2026-MAN-7789",
        "manifest_type": "hazardous_chemical",
        "generator_org_unit": str(quality_department.pk),
        "generator_epa_id": "MAD998877665",
        "accumulation_start_date": (timezone.now().date() - timedelta(days=10)).isoformat(),
        "waste_description": "Hazardous Waste Liquid, Flammable (Acetone, IPA)",
        "epa_waste_codes": "D001, F003",
        "associated_hazardous_material": str(hazardous_material_a.pk),
        "physical_state": "liquid",
        "is_ignitable": True,
        "is_corrosive": False,
        "is_reactive": False,
        "is_toxic": False,
        "container_type": "drum_55gal",
        "container_count": 2,
        "quantity_value": "350.00",
        "quantity_uom": "pounds",
        "transporter": str(supplier_party_a.pk),
        "transporter_epa_id": "MAD039322250",
        "tsdf_facility": str(supplier_party_a.pk),
        "tsdf_epa_id": "MAD053452637",
        "shipment_date": (timezone.now().date() + timedelta(days=5)).isoformat(),
        "certifying_officer": str(admin_user.pk),
    }
    form = WasteDisposalManifestForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.status == "draft"  # Excluded from form, defaults to draft
    assert instance.regulatory_manifest_id == "EPA-2026-MAN-7789"


@pytest.mark.django_db
def test_ehsmanagement_waste_manifest_form_reject_foreign(tenant_a, admin_user, supplier_party_b, quality_department):
    form_data = {
        "manifest_title": "Foreign TSDF Manifest",
        "regulatory_manifest_id": "EPA-ERR-001",
        "manifest_type": "hazardous_chemical",
        "generator_org_unit": str(quality_department.pk),
        "transporter": str(supplier_party_b.pk),  # Belongs to tenant_b
        "tsdf_facility": str(supplier_party_b.pk),  # Belongs to tenant_b
        "certifying_officer": str(admin_user.pk),
        "quantity_value": "100.00",
        "waste_description": "Test waste",
    }
    form = WasteDisposalManifestForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "transporter" in form.errors
    assert "tsdf_facility" in form.errors
