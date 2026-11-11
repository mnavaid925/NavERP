"""Unit and tenant-isolation tests for Sub-module 11.11 compliance forms.

Covers:
1. AssetComplianceFrameworkForm:
   - Valid data creation and edit
   - Tenant scoping of foreign keys (applicable_category, regulatory_agency)
   - reject_foreign cross-tenant rejection
   - Required fields (name, code, framework_type, status)
   - Number and tenant excluded from Meta.fields
2. AssetComplianceAuditForm:
   - Valid data creation and edit
   - Tenant scoping of FKs (framework, asset, auditor_party, lead_auditor_user)
   - reject_foreign cross-tenant rejection (including lead_auditor_user - C2)
   - Checkpoint validation: passed_checkpoints <= total_checkpoints (M4)
   - Status restrictions: cannot set terminal status='completed' directly in form (I7)
3. AssetPermitLicenseForm:
   - Valid data creation and edit
   - Tenant scoping of FKs (asset, issuing_authority)
   - reject_foreign cross-tenant rejection
   - Date validation: expiration_date >= effective_date (M4)
   - Required fields
4. AssetComplianceIncidentForm:
   - Valid data creation and edit
   - Tenant scoping of FKs (asset, permit, audit, enforcement_agency, assigned_investigator)
   - reject_foreign cross-tenant rejection (including assigned_investigator - C2)
   - Fine amounts validation: fine_paid <= fine_assessed (M4)
   - Default fine amounts handling (M8)
   - Status restrictions: cannot set resolved or closed directly in form (I7)
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.assets.forms.AssetCompliance import (
    AssetComplianceAuditForm,
    AssetComplianceFrameworkForm,
    AssetComplianceIncidentForm,
    AssetPermitLicenseForm,
)
from apps.assets.models import (
    AssetCategory,
    AssetComplianceAudit,
    AssetComplianceFramework,
    AssetComplianceIncident,
    AssetPermitLicense,
)
from apps.core.models import Party
from apps.scm.models import Asset

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helpers (Contract Aligned, prefixed with _compliance_*)
# ==============================================================================

def _compliance_framework_payload(**overrides):
    """Build a valid payload for AssetComplianceFrameworkForm."""
    today = timezone.now().date()
    data = {
        "name": "OSHA 1910.119 Process Safety Management",
        "code": "OSHA-1910-PSM",
        "framework_type": "regulatory",
        "effective_date": today.isoformat(),
        "revision": "2024 Edition",
        "mandatory_audit_cycle_months": "12",
        "readiness_score": "95",
        "description": "Standard for managing hazards associated with highly hazardous chemicals.",
        "status": "active",
    }
    data.update(overrides)
    return data


def _compliance_audit_payload(framework, **overrides):
    """Build a valid payload for AssetComplianceAuditForm."""
    today = timezone.now().date()
    data = {
        "title": "Annual Machine Guarding Safety Audit",
        "framework": str(framework.pk),
        "audit_type": "internal",
        "audit_date": today.isoformat(),
        "scope_description": "Evaluation of physical interlocks and emergency stop systems.",
        "total_checkpoints": "30",
        "passed_checkpoints": "28",
        "minor_findings_count": "2",
        "major_findings_count": "0",
        "critical_findings_count": "0",
        "compliance_rating": "minor_deficiencies",
        "summary_findings": "Two labeling tags replaced on bay 4 disconnect panels.",
        "status": "scheduled",
    }
    data.update(overrides)
    return data


def _compliance_permit_payload(asset, issuing_authority=None, **overrides):
    """Build a valid payload for AssetPermitLicenseForm."""
    today = timezone.now().date()
    data = {
        "permit_name": "Stationary Source Air Emissions Operating Permit",
        "permit_number": "EPA-AIR-2026-9042",
        "permit_type": "environmental_emissions",
        "asset": str(asset.pk),
        "issue_date": (today - timezone.timedelta(days=30)).isoformat(),
        "effective_date": (today - timezone.timedelta(days=30)).isoformat(),
        "expiration_date": (today + timezone.timedelta(days=335)).isoformat(),
        "renewal_lead_days": "60",
        "renewal_fee": "1250.00",
        "operating_conditions": "Continuous monitoring of particulate exhaust.",
        "status": "active",
    }
    if issuing_authority is not None:
        data["issuing_authority"] = str(issuing_authority.pk)
    data.update(overrides)
    return data


def _compliance_incident_payload(**overrides):
    """Build a valid payload for AssetComplianceIncidentForm."""
    today = timezone.now().date()
    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")
    data = {
        "title": "Temporary Coolant Sump Overflow",
        "incident_date": now_dt,
        "discovery_date": today.isoformat(),
        "incident_type": "unpermitted_discharge",
        "severity": "other_than_serious",
        "citation_reference": "EPA-NOV-2026-004",
        "fine_assessed": "2500.00",
        "fine_paid": "2500.00",
        "fine_payment_date": today.isoformat(),
        "root_cause": "mechanical_failure",
        "root_cause_analysis": "Float sensor failed to actuate valve closure.",
        "corrective_action_plan": "Replaced float sensor with redundant ultrasonic monitor.",
        "target_resolution_date": (today + timezone.timedelta(days=14)).isoformat(),
        "status": "under_investigation",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. AssetComplianceFrameworkForm Tests
# ==============================================================================

def test_compliance_form_framework_valid_create(tenant_a, category_a, vendor_party_a):
    """Form validates and persists a new compliance framework with foreign keys."""
    data = _compliance_framework_payload(
        applicable_category=str(category_a.pk),
        regulatory_agency=str(vendor_party_a.pk),
    )
    form = AssetComplianceFrameworkForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    framework = form.save(commit=False)
    framework.tenant = tenant_a
    framework.save()

    assert framework.pk is not None
    assert framework.name == "OSHA 1910.119 Process Safety Management"
    assert framework.code == "OSHA-1910-PSM"
    assert framework.framework_type == "regulatory"
    assert framework.number.startswith("ACF-")
    assert framework.applicable_category == category_a
    assert framework.regulatory_agency == vendor_party_a


def test_compliance_form_framework_valid_minimal(tenant_a):
    """Form validates with only required fields (FKs omitted)."""
    today = timezone.now().date()
    data = {
        "name": "Corporate Electrical Safety Code",
        "code": "EHS-ELEC-01",
        "framework_type": "corporate_policy",
        "effective_date": today.isoformat(),
        "revision": "1.0",
        "mandatory_audit_cycle_months": "12",
        "readiness_score": "80",
        "status": "draft",
    }
    form = AssetComplianceFrameworkForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    framework = form.save(commit=False)
    framework.tenant = tenant_a
    framework.save()

    assert framework.pk is not None
    assert framework.applicable_category is None
    assert framework.regulatory_agency is None
    assert framework.status == "draft"


def test_compliance_form_framework_valid_edit(tenant_a, compliance_framework_a):
    """Form successfully updates an existing framework instance."""
    data = _compliance_framework_payload(
        name="OSHA 1910.119 Revised PSM Standard",
        revision="2025 Revised Edition",
        readiness_score="99",
        description="Updated comprehensive refinery audit guidelines.",
        status="active",
    )
    form = AssetComplianceFrameworkForm(instance=compliance_framework_a, data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == compliance_framework_a.pk
    assert updated.name == "OSHA 1910.119 Revised PSM Standard"
    assert updated.revision == "2025 Revised Edition"
    assert updated.readiness_score == 99
    assert updated.description == "Updated comprehensive refinery audit guidelines."


def test_compliance_form_framework_required_fields(tenant_a):
    """Form requires name, code, framework_type, and status."""
    form = AssetComplianceFrameworkForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "code" in form.errors
    assert "framework_type" in form.errors
    assert "status" in form.errors


def test_compliance_form_framework_meta_exclusions(tenant_a):
    """Form excludes system-assigned fields (tenant, number) from Meta.fields."""
    form = AssetComplianceFrameworkForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "created_at" not in form.fields
    assert "updated_at" not in form.fields

    # Attempt injecting tenant and number via POST
    data = _compliance_framework_payload(
        number="ACF-MALICIOUS-9999",
        tenant="9999",
    )
    form_post = AssetComplianceFrameworkForm(data=data, tenant=tenant_a)
    assert form_post.is_valid(), form_post.errors
    instance = form_post.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.number != "ACF-MALICIOUS-9999"
    assert instance.number.startswith("ACF-")


def test_compliance_form_framework_fk_scoping(tenant_a, category_a, category_b, vendor_party_a, vendor_party_b):
    """Foreign key dropdown querysets only contain tenant_a records."""
    form = AssetComplianceFrameworkForm(tenant=tenant_a)
    assert category_a in form.fields["applicable_category"].queryset
    assert category_b not in form.fields["applicable_category"].queryset
    assert vendor_party_a in form.fields["regulatory_agency"].queryset
    assert vendor_party_b not in form.fields["regulatory_agency"].queryset


def test_compliance_form_framework_reject_foreign_applicable_category(tenant_a, category_b):
    """Cross-tenant applicable_category is blocked by choice validation and reject_foreign."""
    data = _compliance_framework_payload(applicable_category=str(category_b.pk))

    # 1. Scoped queryset blocks it
    form = AssetComplianceFrameworkForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "applicable_category" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetComplianceFrameworkForm(data=data, tenant=tenant_a)
    form_wide.fields["applicable_category"].queryset = AssetCategory.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["applicable_category"]


def test_compliance_form_framework_reject_foreign_regulatory_agency(tenant_a, vendor_party_b):
    """Cross-tenant regulatory_agency is blocked by choice validation and reject_foreign."""
    data = _compliance_framework_payload(regulatory_agency=str(vendor_party_b.pk))

    # 1. Scoped queryset blocks it
    form = AssetComplianceFrameworkForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "regulatory_agency" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetComplianceFrameworkForm(data=data, tenant=tenant_a)
    form_wide.fields["regulatory_agency"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["regulatory_agency"]


# ==============================================================================
# 2. AssetComplianceAuditForm Tests
# ==============================================================================

def test_compliance_form_audit_valid_create(
    tenant_a,
    compliance_framework_a,
    operational_asset_a,
    vendor_party_a,
    admin_user,
):
    """Form validates and persists a new compliance audit with all valid foreign keys."""
    data = _compliance_audit_payload(
        compliance_framework_a,
        asset=str(operational_asset_a.pk),
        auditor_party=str(vendor_party_a.pk),
        lead_auditor_user=str(admin_user.pk),
    )
    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    audit = form.save(commit=False)
    audit.tenant = tenant_a
    audit.save()

    assert audit.pk is not None
    assert audit.title == "Annual Machine Guarding Safety Audit"
    assert audit.framework == compliance_framework_a
    assert audit.asset == operational_asset_a
    assert audit.auditor_party == vendor_party_a
    assert audit.lead_auditor_user == admin_user
    assert audit.number.startswith("ACA-")
    assert audit.passed_checkpoints == 28


def test_compliance_form_audit_valid_edit(tenant_a, compliance_audit_a, compliance_framework_a):
    """Form successfully edits an existing audit instance."""
    data = _compliance_audit_payload(
        compliance_framework_a,
        title="Updated Verification Audit Scope",
        total_checkpoints="50",
        passed_checkpoints="49",
        minor_findings_count="1",
        compliance_rating="minor_deficiencies",
        summary_findings="One additional warning placard needed on motor cabinet.",
        status="in_progress",
    )
    form = AssetComplianceAuditForm(instance=compliance_audit_a, data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == compliance_audit_a.pk
    assert updated.title == "Updated Verification Audit Scope"
    assert updated.total_checkpoints == 50
    assert updated.passed_checkpoints == 49
    assert updated.summary_findings == "One additional warning placard needed on motor cabinet."


def test_compliance_form_audit_required_fields(tenant_a):
    """Form requires title, framework, audit_type, and audit_date."""
    form = AssetComplianceAuditForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "framework" in form.errors
    assert "audit_type" in form.errors
    assert "audit_date" in form.errors


def test_compliance_form_audit_meta_exclusions(tenant_a):
    """Form excludes system and terminal timestamp fields (tenant, number, completed_at)."""
    form = AssetComplianceAuditForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "completed_at" not in form.fields


def test_compliance_form_audit_fk_scoping(
    tenant_a,
    compliance_framework_a,
    compliance_framework_b,
    operational_asset_a,
    operational_asset_b,
    vendor_party_a,
    vendor_party_b,
    admin_user,
    admin_b,
):
    """Audit dropdown querysets only contain tenant_a records, including lead_auditor_user."""
    form = AssetComplianceAuditForm(tenant=tenant_a)
    assert compliance_framework_a in form.fields["framework"].queryset
    assert compliance_framework_b not in form.fields["framework"].queryset
    assert operational_asset_a in form.fields["asset"].queryset
    assert operational_asset_b not in form.fields["asset"].queryset
    assert vendor_party_a in form.fields["auditor_party"].queryset
    assert vendor_party_b not in form.fields["auditor_party"].queryset
    assert admin_user in form.fields["lead_auditor_user"].queryset
    assert admin_b not in form.fields["lead_auditor_user"].queryset


def test_compliance_form_audit_reject_foreign_framework(tenant_a, compliance_framework_b):
    """Cross-tenant framework is rejected by reject_foreign."""
    data = _compliance_audit_payload(compliance_framework_b)

    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "framework" in form.errors

    form_wide = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    form_wide.fields["framework"].queryset = AssetComplianceFramework.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["framework"]


def test_compliance_form_audit_reject_foreign_asset(tenant_a, compliance_framework_a, operational_asset_b):
    """Cross-tenant asset is rejected by reject_foreign."""
    data = _compliance_audit_payload(
        compliance_framework_a,
        asset=str(operational_asset_b.pk),
    )
    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    form_wide = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    form_wide.fields["asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset"]


def test_compliance_form_audit_reject_foreign_auditor_party(tenant_a, compliance_framework_a, vendor_party_b):
    """Cross-tenant auditor_party is rejected by reject_foreign."""
    data = _compliance_audit_payload(
        compliance_framework_a,
        auditor_party=str(vendor_party_b.pk),
    )
    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "auditor_party" in form.errors

    form_wide = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    form_wide.fields["auditor_party"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["auditor_party"]


def test_compliance_form_audit_reject_foreign_lead_auditor_user(tenant_a, compliance_framework_a, admin_b):
    """Cross-tenant lead_auditor_user is rejected by reject_foreign (Finding C2)."""
    data = _compliance_audit_payload(
        compliance_framework_a,
        lead_auditor_user=str(admin_b.pk),
    )
    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lead_auditor_user" in form.errors

    form_wide = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    form_wide.fields["lead_auditor_user"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["lead_auditor_user"]


def test_compliance_form_audit_checkpoint_validation_passed_exceeds_total(tenant_a, compliance_framework_a):
    """Form adds error when passed_checkpoints > total_checkpoints (Finding M4)."""
    data = _compliance_audit_payload(
        compliance_framework_a,
        total_checkpoints="15",
        passed_checkpoints="20",
    )
    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "passed_checkpoints" in form.errors
    assert "Passed checkpoints cannot exceed total checkpoints." in form.errors["passed_checkpoints"]


def test_compliance_form_audit_checkpoint_validation_passed_equal_or_less(tenant_a, compliance_framework_a):
    """Form allows passed_checkpoints equal to or less than total_checkpoints."""
    # Equal
    data_equal = _compliance_audit_payload(
        compliance_framework_a,
        total_checkpoints="25",
        passed_checkpoints="25",
    )
    form_equal = AssetComplianceAuditForm(data=data_equal, tenant=tenant_a)
    assert form_equal.is_valid(), form_equal.errors

    # Less
    data_less = _compliance_audit_payload(
        compliance_framework_a,
        total_checkpoints="25",
        passed_checkpoints="12",
    )
    form_less = AssetComplianceAuditForm(data=data_less, tenant=tenant_a)
    assert form_less.is_valid(), form_less.errors


def test_compliance_form_audit_status_restrictions_choices(tenant_a):
    """Status choices in form exclude terminal 'completed' status (Finding I7)."""
    form = AssetComplianceAuditForm(tenant=tenant_a)
    status_choices = dict(form.fields["status"].choices)
    assert "completed" not in status_choices
    assert "scheduled" in status_choices
    assert "in_progress" in status_choices


def test_compliance_form_audit_status_restrictions_clean_completed(tenant_a, compliance_framework_a):
    """clean_status rejects direct assignment of status='completed' (Finding I7)."""
    data = _compliance_audit_payload(
        compliance_framework_a,
        status="completed",
    )
    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert any("completed is not one of the available choices" in err or "Status cannot be set" in err for err in form.errors["status"])


# ==============================================================================
# 3. AssetPermitLicenseForm Tests
# ==============================================================================

def test_compliance_form_permit_valid_create(tenant_a, operational_asset_a, vendor_party_a):
    """Form validates and creates a new permit license with valid dates and FKs."""
    data = _compliance_permit_payload(
        operational_asset_a,
        issuing_authority=vendor_party_a,
    )
    form = AssetPermitLicenseForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    permit = form.save(commit=False)
    permit.tenant = tenant_a
    permit.save()

    assert permit.pk is not None
    assert permit.permit_number == "EPA-AIR-2026-9042"
    assert permit.number.startswith("APL-")
    assert permit.asset == operational_asset_a
    assert permit.issuing_authority == vendor_party_a
    assert permit.renewal_fee == Decimal("1250.00")


def test_compliance_form_permit_valid_edit(tenant_a, permit_license_a, operational_asset_a):
    """Form successfully edits an existing permit license instance."""
    data = _compliance_permit_payload(
        operational_asset_a,
        permit_name="Amended Title V Air Emissions Permit",
        renewal_fee="1500.00",
        operating_conditions="Amended NOx and SO2 hourly limit conditions.",
    )
    form = AssetPermitLicenseForm(instance=permit_license_a, data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == permit_license_a.pk
    assert updated.permit_name == "Amended Title V Air Emissions Permit"
    assert updated.renewal_fee == Decimal("1500.00")
    assert updated.operating_conditions == "Amended NOx and SO2 hourly limit conditions."


def test_compliance_form_permit_required_fields(tenant_a):
    """Form requires permit_name, permit_number, permit_type, asset, expiration_date, and status."""
    form = AssetPermitLicenseForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "permit_name" in form.errors
    assert "permit_number" in form.errors
    assert "permit_type" in form.errors
    assert "asset" in form.errors
    assert "expiration_date" in form.errors
    assert "status" in form.errors


def test_compliance_form_permit_meta_exclusions(tenant_a):
    """Form excludes system-assigned fields (tenant, number)."""
    form = AssetPermitLicenseForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields


def test_compliance_form_permit_fk_scoping(
    tenant_a,
    operational_asset_a,
    operational_asset_b,
    vendor_party_a,
    vendor_party_b,
):
    """Permit dropdown querysets only contain tenant_a records."""
    form = AssetPermitLicenseForm(tenant=tenant_a)
    assert operational_asset_a in form.fields["asset"].queryset
    assert operational_asset_b not in form.fields["asset"].queryset
    assert vendor_party_a in form.fields["issuing_authority"].queryset
    assert vendor_party_b not in form.fields["issuing_authority"].queryset


def test_compliance_form_permit_reject_foreign_asset(tenant_a, operational_asset_b):
    """Cross-tenant asset is rejected by reject_foreign."""
    data = _compliance_permit_payload(operational_asset_b)

    form = AssetPermitLicenseForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    form_wide = AssetPermitLicenseForm(data=data, tenant=tenant_a)
    form_wide.fields["asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset"]


def test_compliance_form_permit_reject_foreign_issuing_authority(tenant_a, operational_asset_a, vendor_party_b):
    """Cross-tenant issuing_authority is rejected by reject_foreign."""
    data = _compliance_permit_payload(
        operational_asset_a,
        issuing_authority=vendor_party_b,
    )
    form = AssetPermitLicenseForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "issuing_authority" in form.errors

    form_wide = AssetPermitLicenseForm(data=data, tenant=tenant_a)
    form_wide.fields["issuing_authority"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["issuing_authority"]


def test_compliance_form_permit_date_validation_expiration_before_effective(tenant_a, operational_asset_a):
    """Form adds error when expiration_date < effective_date (Finding M4)."""
    today = timezone.now().date()
    data = _compliance_permit_payload(
        operational_asset_a,
        effective_date=today.isoformat(),
        expiration_date=(today - timezone.timedelta(days=1)).isoformat(),
    )
    form = AssetPermitLicenseForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "expiration_date" in form.errors
    assert "Expiration date cannot be earlier than effective date." in form.errors["expiration_date"]


def test_compliance_form_permit_date_validation_expiration_equal_or_after_effective(tenant_a, operational_asset_a):
    """Form allows expiration_date on or after effective_date."""
    today = timezone.now().date()

    # Same day
    data_same = _compliance_permit_payload(
        operational_asset_a,
        effective_date=today.isoformat(),
        expiration_date=today.isoformat(),
    )
    form_same = AssetPermitLicenseForm(data=data_same, tenant=tenant_a)
    assert form_same.is_valid(), form_same.errors

    # Later date
    data_later = _compliance_permit_payload(
        operational_asset_a,
        effective_date=today.isoformat(),
        expiration_date=(today + timezone.timedelta(days=180)).isoformat(),
    )
    form_later = AssetPermitLicenseForm(data=data_later, tenant=tenant_a)
    assert form_later.is_valid(), form_later.errors


# ==============================================================================
# 4. AssetComplianceIncidentForm Tests
# ==============================================================================

def test_compliance_form_incident_valid_create(
    tenant_a,
    operational_asset_a,
    permit_license_a,
    compliance_audit_a,
    vendor_party_a,
    admin_user,
):
    """Form validates and persists a new incident with all valid foreign keys."""
    data = _compliance_incident_payload(
        asset=str(operational_asset_a.pk),
        permit=str(permit_license_a.pk),
        audit=str(compliance_audit_a.pk),
        enforcement_agency=str(vendor_party_a.pk),
        assigned_investigator=str(admin_user.pk),
    )
    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    incident = form.save(commit=False)
    incident.tenant = tenant_a
    incident.save()

    assert incident.pk is not None
    assert incident.title == "Temporary Coolant Sump Overflow"
    assert incident.number.startswith("ACI-")
    assert incident.asset == operational_asset_a
    assert incident.permit == permit_license_a
    assert incident.audit == compliance_audit_a
    assert incident.enforcement_agency == vendor_party_a
    assert incident.assigned_investigator == admin_user
    assert incident.fine_assessed == Decimal("2500.00")
    assert incident.fine_paid == Decimal("2500.00")


def test_compliance_form_incident_valid_edit(tenant_a, compliance_incident_b):
    """Form successfully edits an existing incident instance."""
    data = _compliance_incident_payload(
        title="Updated Root Cause Sump Investigation",
        root_cause="inadequate_procedure",
        root_cause_analysis="Checklist missed during shift turnover.",
        corrective_action_plan="Added mandatory shift turnover EHS checklist item.",
        status="capa_in_progress",
    )
    form = AssetComplianceIncidentForm(instance=compliance_incident_b, data=data, tenant=compliance_incident_b.tenant)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == compliance_incident_b.pk
    assert updated.root_cause == "inadequate_procedure"
    assert updated.root_cause_analysis == "Checklist missed during shift turnover."
    assert updated.corrective_action_plan == "Added mandatory shift turnover EHS checklist item."


def test_compliance_form_incident_required_fields(tenant_a):
    """Form requires title, incident_date, discovery_date, incident_type, severity, and status."""
    form = AssetComplianceIncidentForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "incident_date" in form.errors
    assert "discovery_date" in form.errors
    assert "incident_type" in form.errors
    assert "severity" in form.errors
    assert "status" in form.errors


def test_compliance_form_incident_meta_exclusions(tenant_a):
    """Form excludes system and workflow resolution fields (tenant, number, actual_resolution_date)."""
    form = AssetComplianceIncidentForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "actual_resolution_date" not in form.fields


def test_compliance_form_incident_fk_scoping(
    tenant_a,
    operational_asset_a,
    operational_asset_b,
    permit_license_a,
    permit_license_b,
    compliance_audit_a,
    compliance_audit_b,
    vendor_party_a,
    vendor_party_b,
    admin_user,
    admin_b,
):
    """Incident dropdown querysets only contain tenant_a records, including assigned_investigator."""
    form = AssetComplianceIncidentForm(tenant=tenant_a)
    assert operational_asset_a in form.fields["asset"].queryset
    assert operational_asset_b not in form.fields["asset"].queryset
    assert permit_license_a in form.fields["permit"].queryset
    assert permit_license_b not in form.fields["permit"].queryset
    assert compliance_audit_a in form.fields["audit"].queryset
    assert compliance_audit_b not in form.fields["audit"].queryset
    assert vendor_party_a in form.fields["enforcement_agency"].queryset
    assert vendor_party_b not in form.fields["enforcement_agency"].queryset
    assert admin_user in form.fields["assigned_investigator"].queryset
    assert admin_b not in form.fields["assigned_investigator"].queryset


def test_compliance_form_incident_reject_foreign_asset(tenant_a, operational_asset_b):
    """Cross-tenant asset is rejected by reject_foreign."""
    data = _compliance_incident_payload(asset=str(operational_asset_b.pk))

    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    form_wide = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    form_wide.fields["asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset"]


def test_compliance_form_incident_reject_foreign_permit(tenant_a, permit_license_b):
    """Cross-tenant permit is rejected by reject_foreign."""
    data = _compliance_incident_payload(permit=str(permit_license_b.pk))

    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "permit" in form.errors

    form_wide = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    form_wide.fields["permit"].queryset = AssetPermitLicense.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["permit"]


def test_compliance_form_incident_reject_foreign_audit(tenant_a, compliance_audit_b):
    """Cross-tenant audit is rejected by reject_foreign."""
    data = _compliance_incident_payload(audit=str(compliance_audit_b.pk))

    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "audit" in form.errors

    form_wide = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    form_wide.fields["audit"].queryset = AssetComplianceAudit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["audit"]


def test_compliance_form_incident_reject_foreign_enforcement_agency(tenant_a, vendor_party_b):
    """Cross-tenant enforcement_agency is rejected by reject_foreign."""
    data = _compliance_incident_payload(enforcement_agency=str(vendor_party_b.pk))

    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "enforcement_agency" in form.errors

    form_wide = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    form_wide.fields["enforcement_agency"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["enforcement_agency"]


def test_compliance_form_incident_reject_foreign_assigned_investigator(tenant_a, admin_b):
    """Cross-tenant assigned_investigator is rejected by reject_foreign (Finding C2)."""
    data = _compliance_incident_payload(assigned_investigator=str(admin_b.pk))

    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "assigned_investigator" in form.errors

    form_wide = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    form_wide.fields["assigned_investigator"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["assigned_investigator"]


def test_compliance_form_incident_fine_amounts_paid_exceeds_assessed(tenant_a):
    """Form adds error when fine_paid > fine_assessed (Finding M4)."""
    data = _compliance_incident_payload(
        fine_assessed="500.00",
        fine_paid="1000.00",
    )
    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fine_paid" in form.errors
    assert "Fine paid cannot exceed fine assessed." in form.errors["fine_paid"]


def test_compliance_form_incident_fine_amounts_paid_equal_or_less(tenant_a):
    """Form allows fine_paid equal to or less than fine_assessed."""
    # Equal
    data_equal = _compliance_incident_payload(
        fine_assessed="1000.00",
        fine_paid="1000.00",
    )
    form_equal = AssetComplianceIncidentForm(data=data_equal, tenant=tenant_a)
    assert form_equal.is_valid(), form_equal.errors

    # Less
    data_less = _compliance_incident_payload(
        fine_assessed="1000.00",
        fine_paid="250.00",
    )
    form_less = AssetComplianceIncidentForm(data=data_less, tenant=tenant_a)
    assert form_less.is_valid(), form_less.errors

    # Zero
    data_zero = _compliance_incident_payload(
        fine_assessed="0.00",
        fine_paid="0.00",
    )
    form_zero = AssetComplianceIncidentForm(data=data_zero, tenant=tenant_a)
    assert form_zero.is_valid(), form_zero.errors


def test_compliance_form_incident_fine_amounts_defaults_handling(tenant_a):
    """Empty fine amounts are coerced to Decimal('0.00') by clean() (Finding M8)."""
    data = _compliance_incident_payload(
        fine_assessed="",
        fine_paid="",
    )
    form = AssetComplianceIncidentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["fine_assessed"] == Decimal("0.00")
    assert form.cleaned_data["fine_paid"] == Decimal("0.00")


def test_compliance_form_incident_status_restrictions_choices(tenant_a):
    """Status choices in form exclude terminal 'resolved' and 'closed' statuses (Finding I7)."""
    form = AssetComplianceIncidentForm(tenant=tenant_a)
    status_choices = dict(form.fields["status"].choices)
    assert "resolved" not in status_choices
    assert "closed" not in status_choices
    assert "open" in status_choices
    assert "under_investigation" in status_choices
    assert "capa_in_progress" in status_choices


def test_compliance_form_incident_status_restrictions_clean_resolved_closed(tenant_a):
    """clean_status rejects direct assignment of status='resolved' or 'closed' (Finding I7)."""
    # Attempt resolved
    data_resolved = _compliance_incident_payload(status="resolved")
    form_resolved = AssetComplianceIncidentForm(data=data_resolved, tenant=tenant_a)
    assert not form_resolved.is_valid()
    assert "status" in form_resolved.errors
    assert any("resolved is not one of the available choices" in err or "Status cannot be set" in err for err in form_resolved.errors["status"])

    # Attempt closed
    data_closed = _compliance_incident_payload(status="closed")
    form_closed = AssetComplianceIncidentForm(data=data_closed, tenant=tenant_a)
    assert not form_closed.is_valid()
    assert "status" in form_closed.errors
    assert any("closed is not one of the available choices" in err or "Status cannot be set" in err for err in form_closed.errors["status"])
