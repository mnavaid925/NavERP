"""Model unit, constraint, and invariant tests for Sub-module 11.11: Compliance & Regulatory Management.

Covers all 4 models:
- AssetComplianceFramework (ACF-YYYYMM-XXXX)
- AssetComplianceAudit (ACA-YYYYMM-XXXX)
- AssetPermitLicense (APL-YYYYMM-XXXX)
- AssetComplianceIncident (ACI-YYYYMM-XXXX)
"""
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.assets.models import (
    AssetCategory,
    AssetComplianceFramework,
    AssetComplianceAudit,
    AssetPermitLicense,
    AssetComplianceIncident,
)
from apps.core.models import Party
from apps.scm.models import Asset

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (Contract Aligned, prefixed with _compliance_*)
# ==============================================================================

def _compliance_create_framework(tenant, **kwargs):
    """Helper to provision test compliance framework with valid defaults."""
    defaults = {
        "name": "Environmental Management System Standard",
        "code": "ISO-14001-EMS",
        "framework_type": "voluntary_standard",
        "effective_date": timezone.now().date() - timezone.timedelta(days=120),
        "revision": "2024 Revision",
        "mandatory_audit_cycle_months": 12,
        "readiness_score": 90,
        "description": "Standard governing environmental impact controls.",
        "status": "active",
    }
    defaults.update(kwargs)
    return AssetComplianceFramework.objects.create(
        tenant=tenant,
        **defaults,
    )


def _compliance_create_audit(tenant, framework, **kwargs):
    """Helper to provision test compliance audit with valid defaults."""
    defaults = {
        "title": "Quarterly Environmental Discharge Audit",
        "audit_type": "internal",
        "audit_date": timezone.now().date() - timezone.timedelta(days=10),
        "scope_description": "Evaluation of wastewater and emission scrubbers.",
        "total_checkpoints": 50,
        "passed_checkpoints": 48,
        "minor_findings_count": 2,
        "major_findings_count": 0,
        "critical_findings_count": 0,
        "compliance_rating": "minor_deficiencies",
        "summary_findings": "Overall sound, two minor labeling deficiencies.",
        "status": "scheduled",
    }
    defaults.update(kwargs)
    return AssetComplianceAudit.objects.create(
        tenant=tenant,
        framework=framework,
        **defaults,
    )


def _compliance_create_permit(tenant, asset, **kwargs):
    """Helper to provision test permit/license with valid defaults."""
    defaults = {
        "permit_name": "Wastewater Discharge Permit",
        "permit_number": "NPDES-WASTE-2026",
        "permit_type": "water_discharge",
        "issue_date": timezone.now().date() - timezone.timedelta(days=90),
        "effective_date": timezone.now().date() - timezone.timedelta(days=90),
        "expiration_date": timezone.now().date() + timezone.timedelta(days=275),
        "renewal_lead_days": 60,
        "renewal_fee": Decimal("500.00"),
        "operating_conditions": "pH 6.5 - 8.5 at discharge point.",
        "status": "active",
    }
    defaults.update(kwargs)
    return AssetPermitLicense.objects.create(
        tenant=tenant,
        asset=asset,
        **defaults,
    )


def _compliance_create_incident(tenant, **kwargs):
    """Helper to provision test compliance incident with valid defaults."""
    defaults = {
        "title": "Unauthorized Effluent Release Exceedance",
        "incident_date": timezone.now() - timezone.timedelta(days=5),
        "discovery_date": timezone.now().date() - timezone.timedelta(days=4),
        "incident_type": "unpermitted_discharge",
        "severity": "serious",
        "fine_assessed": Decimal("10000.00"),
        "fine_paid": Decimal("2500.00"),
        "root_cause": "mechanical_failure",
        "root_cause_analysis": "Secondary holding pump seal ruptured.",
        "corrective_action_plan": "Replace mechanical pump seals with double-contained units.",
        "status": "open",
    }
    defaults.update(kwargs)
    return AssetComplianceIncident.objects.create(
        tenant=tenant,
        **defaults,
    )


# ==============================================================================
# Model 1: AssetComplianceFramework Tests
# ==============================================================================

def test_compliance_model_framework_auto_number_and_str(compliance_framework_a):
    """Verify ACF- auto-number generation and __str__ format."""
    assert compliance_framework_a.number.startswith("ACF-")
    assert str(compliance_framework_a) == f"{compliance_framework_a.code} — {compliance_framework_a.name} ({compliance_framework_a.number})"


def test_compliance_model_framework_defaults(tenant_a):
    """Verify default values when creating a framework with minimal parameters."""
    fw = AssetComplianceFramework.objects.create(
        tenant=tenant_a,
        name="Minimum Requirement Safety Code",
        code="MIN-SAFE-01",
    )
    assert fw.framework_type == "regulatory"
    assert fw.status == "active"
    assert fw.revision == "Current"
    assert fw.mandatory_audit_cycle_months == 12
    assert fw.readiness_score == 100
    assert fw.description == ""
    assert fw.number.startswith("ACF-")


def test_compliance_model_framework_choices():
    """Verify FRAMEWORK_TYPE_CHOICES and STATUS_CHOICES defined on framework."""
    framework_types = [c[0] for c in AssetComplianceFramework.FRAMEWORK_TYPE_CHOICES]
    assert "regulatory" in framework_types
    assert "statutory" in framework_types
    assert "voluntary_standard" in framework_types
    assert "industry_code" in framework_types
    assert "corporate_policy" in framework_types

    statuses = [s[0] for s in AssetComplianceFramework.STATUS_CHOICES]
    assert "draft" in statuses
    assert "active" in statuses
    assert "under_review" in statuses
    assert "deprecated" in statuses


def test_compliance_model_framework_badges(compliance_framework_a):
    """Verify status and framework type badge css mapping properties."""
    assert compliance_framework_a.status_badge_class == "badge-green"
    assert compliance_framework_a.framework_type_badge_class == "badge-red"

    compliance_framework_a.status = "draft"
    assert compliance_framework_a.status_badge_class == "badge-slate"
    compliance_framework_a.status = "under_review"
    assert compliance_framework_a.status_badge_class == "badge-amber"
    compliance_framework_a.status = "deprecated"
    assert compliance_framework_a.status_badge_class == "badge-muted"

    compliance_framework_a.framework_type = "voluntary_standard"
    assert compliance_framework_a.framework_type_badge_class == "badge-info"
    compliance_framework_a.framework_type = "statutory"
    assert compliance_framework_a.framework_type_badge_class == "badge-amber"
    compliance_framework_a.framework_type = "industry_code"
    assert compliance_framework_a.framework_type_badge_class == "badge-slate"
    compliance_framework_a.framework_type = "corporate_policy"
    assert compliance_framework_a.framework_type_badge_class == "badge-muted"


def test_compliance_model_framework_is_active_property(compliance_framework_a):
    """Verify is_active returns True only when status is 'active'."""
    compliance_framework_a.status = "active"
    assert compliance_framework_a.is_active is True

    compliance_framework_a.status = "draft"
    assert compliance_framework_a.is_active is False

    compliance_framework_a.status = "under_review"
    assert compliance_framework_a.is_active is False

    compliance_framework_a.status = "deprecated"
    assert compliance_framework_a.is_active is False


def test_compliance_model_framework_is_audit_due_without_audit(tenant_a):
    """Verify is_audit_due uses effective_date when no audits have been conducted."""
    today = timezone.now().date()
    # Effective date 400 days ago, 12 month cycle (360 days) -> overdue
    fw_overdue = _compliance_create_framework(
        tenant_a,
        name="Overdue Standard",
        code="ODS-01",
        effective_date=today - timezone.timedelta(days=400),
        mandatory_audit_cycle_months=12,
        status="active",
    )
    assert fw_overdue.is_audit_due is True

    # Effective date 30 days ago, 12 month cycle -> not overdue
    fw_current = _compliance_create_framework(
        tenant_a,
        name="Current Standard",
        code="CUR-01",
        effective_date=today - timezone.timedelta(days=30),
        mandatory_audit_cycle_months=12,
        status="active",
    )
    assert fw_current.is_audit_due is False


def test_compliance_model_framework_is_audit_due_with_recent_audit(tenant_a):
    """Verify is_audit_due references latest completed audit date."""
    today = timezone.now().date()
    fw = _compliance_create_framework(
        tenant_a,
        name="Audited Standard",
        code="AUD-01",
        effective_date=today - timezone.timedelta(days=500),
        mandatory_audit_cycle_months=12,
        status="active",
    )
    # Without audit, it's overdue
    assert fw.is_audit_due is True

    # Add completed audit from 15 days ago
    _compliance_create_audit(
        tenant_a,
        framework=fw,
        audit_date=today - timezone.timedelta(days=15),
        status="completed",
    )
    assert fw.is_audit_due is False


def test_compliance_model_framework_is_audit_due_when_inactive(tenant_a):
    """Verify is_audit_due returns False if framework is not active."""
    today = timezone.now().date()
    fw_draft = _compliance_create_framework(
        tenant_a,
        name="Draft Standard",
        code="DRF-01",
        effective_date=today - timezone.timedelta(days=500),
        mandatory_audit_cycle_months=12,
        status="draft",
    )
    assert fw_draft.is_audit_due is False


def test_compliance_model_framework_foreign_keys(tenant_a, category_a, vendor_party_a):
    """Verify foreign keys for category, regulatory agency, and tenant."""
    fw = _compliance_create_framework(
        tenant_a,
        applicable_category=category_a,
        regulatory_agency=vendor_party_a,
    )
    assert fw.applicable_category == category_a
    assert fw.regulatory_agency == vendor_party_a
    assert fw.tenant == tenant_a
    assert fw in category_a.compliance_frameworks.all()
    assert fw in vendor_party_a.compliance_frameworks.all()


# ==============================================================================
# Model 2: AssetComplianceAudit Tests
# ==============================================================================

def test_compliance_model_audit_auto_number_and_str(compliance_audit_a):
    """Verify ACA- auto-number generation and __str__ representation."""
    assert compliance_audit_a.number.startswith("ACA-")
    assert str(compliance_audit_a) == f"{compliance_audit_a.title} ({compliance_audit_a.number})"


def test_compliance_model_audit_defaults(tenant_a, compliance_framework_a):
    """Verify audit creation with defaults."""
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Baseline Verification Audit",
    )
    assert audit.audit_type == "internal"
    assert audit.compliance_rating == "not_rated"
    assert audit.status == "scheduled"
    assert audit.total_checkpoints == 0
    assert audit.passed_checkpoints == 0
    assert audit.minor_findings_count == 0
    assert audit.major_findings_count == 0
    assert audit.critical_findings_count == 0
    assert audit.completed_at is None
    assert audit.number.startswith("ACA-")


def test_compliance_model_audit_choices():
    """Verify AUDIT_TYPE_CHOICES, COMPLIANCE_RATING_CHOICES, and STATUS_CHOICES."""
    types = [t[0] for t in AssetComplianceAudit.AUDIT_TYPE_CHOICES]
    assert "internal" in types
    assert "external_regulatory" in types
    assert "third_party_certification" in types
    assert "customer_qualification" in types

    ratings = [r[0] for r in AssetComplianceAudit.COMPLIANCE_RATING_CHOICES]
    assert "fully_compliant" in ratings
    assert "minor_deficiencies" in ratings
    assert "major_non_conformance" in ratings
    assert "critical_breach" in ratings
    assert "not_rated" in ratings

    statuses = [s[0] for s in AssetComplianceAudit.STATUS_CHOICES]
    assert "scheduled" in statuses
    assert "in_progress" in statuses
    assert "under_review" in statuses
    assert "completed" in statuses
    assert "cancelled" in statuses


def test_compliance_model_audit_badges(compliance_audit_a):
    """Verify badge CSS mappings for audit status, rating, and type."""
    assert compliance_audit_a.status_badge_class == "badge-green"
    assert compliance_audit_a.compliance_rating_badge_class == "badge-green"
    assert compliance_audit_a.audit_type_badge_class == "badge-info"

    compliance_audit_a.status = "scheduled"
    assert compliance_audit_a.status_badge_class == "badge-slate"
    compliance_audit_a.status = "in_progress"
    assert compliance_audit_a.status_badge_class == "badge-info"
    compliance_audit_a.status = "under_review"
    assert compliance_audit_a.status_badge_class == "badge-amber"
    compliance_audit_a.status = "cancelled"
    assert compliance_audit_a.status_badge_class == "badge-muted"

    compliance_audit_a.compliance_rating = "minor_deficiencies"
    assert compliance_audit_a.compliance_rating_badge_class == "badge-amber"
    compliance_audit_a.compliance_rating = "major_non_conformance"
    assert compliance_audit_a.compliance_rating_badge_class == "badge-red"
    compliance_audit_a.compliance_rating = "critical_breach"
    assert compliance_audit_a.compliance_rating_badge_class == "badge-red"
    compliance_audit_a.compliance_rating = "not_rated"
    assert compliance_audit_a.compliance_rating_badge_class == "badge-slate"

    compliance_audit_a.audit_type = "external_regulatory"
    assert compliance_audit_a.audit_type_badge_class == "badge-red"
    compliance_audit_a.audit_type = "third_party_certification"
    assert compliance_audit_a.audit_type_badge_class == "badge-green"
    compliance_audit_a.audit_type = "customer_qualification"
    assert compliance_audit_a.audit_type_badge_class == "badge-slate"


def test_compliance_model_audit_mark_in_progress(tenant_a, compliance_framework_a):
    """Verify mark_in_progress transitions scheduled -> in_progress."""
    audit = _compliance_create_audit(
        tenant_a,
        framework=compliance_framework_a,
        status="scheduled",
    )
    audit.mark_in_progress()
    audit.refresh_from_db()
    assert audit.status == "in_progress"

    # Calling it when already in_progress does not break or alter status
    audit.mark_in_progress()
    audit.refresh_from_db()
    assert audit.status == "in_progress"


def test_compliance_model_audit_complete_audit(tenant_a, compliance_framework_a):
    """Verify complete_audit transitions to completed and records timestamp."""
    audit = _compliance_create_audit(
        tenant_a,
        framework=compliance_framework_a,
        status="in_progress",
    )
    assert audit.completed_at is None
    audit.complete_audit()
    audit.refresh_from_db()
    assert audit.status == "completed"
    assert audit.completed_at is not None


def test_compliance_model_audit_is_breached_rating(tenant_a, compliance_framework_a):
    """Verify is_breached property evaluates compliance_rating correctly."""
    audit = _compliance_create_audit(
        tenant_a,
        framework=compliance_framework_a,
        compliance_rating="fully_compliant",
        critical_findings_count=0,
    )
    assert audit.is_breached is False

    audit.compliance_rating = "major_non_conformance"
    assert audit.is_breached is True

    audit.compliance_rating = "critical_breach"
    assert audit.is_breached is True

    audit.compliance_rating = "minor_deficiencies"
    assert audit.is_breached is False


def test_compliance_model_audit_is_breached_critical_findings(tenant_a, compliance_framework_a):
    """Verify is_breached is True if critical_findings_count > 0 even with non-breach rating."""
    audit = _compliance_create_audit(
        tenant_a,
        framework=compliance_framework_a,
        compliance_rating="minor_deficiencies",
        critical_findings_count=1,
    )
    assert audit.is_breached is True


def test_compliance_model_audit_checkpoint_calculation(compliance_audit_a):
    """Verify checkpoint attributes and pass rate invariant."""
    assert compliance_audit_a.passed_checkpoints <= compliance_audit_a.total_checkpoints
    pass_rate = (compliance_audit_a.passed_checkpoints / compliance_audit_a.total_checkpoints) * 100
    assert pass_rate == 100.0


def test_compliance_model_audit_framework_protected(tenant_a, compliance_framework_a):
    """Verify Framework has on_delete=PROTECT and cannot be deleted while audits exist."""
    _compliance_create_audit(tenant_a, framework=compliance_framework_a)
    with pytest.raises(ProtectedError):
        compliance_framework_a.delete()


# ==============================================================================
# Model 3: AssetPermitLicense Tests
# ==============================================================================

def test_compliance_model_permit_auto_number_and_str(permit_license_a):
    """Verify APL- auto-number generation and __str__ representation."""
    assert permit_license_a.number.startswith("APL-")
    assert str(permit_license_a) == f"{permit_license_a.permit_name} ({permit_license_a.permit_number})"


def test_compliance_model_permit_defaults(tenant_a, operational_asset_a):
    """Verify permit creation with defaults."""
    today = timezone.now().date()
    permit = AssetPermitLicense.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        permit_name="Standard Factory Operating Permit",
        permit_number="STD-PERMIT-001",
        expiration_date=today + timezone.timedelta(days=180),
    )
    assert permit.permit_type == "safety_operating"
    assert permit.status == "active"
    assert permit.renewal_lead_days == 60
    assert permit.renewal_fee == Decimal("0.00")
    assert permit.number.startswith("APL-")


def test_compliance_model_permit_choices():
    """Verify PERMIT_TYPE_CHOICES and STATUS_CHOICES defined on permit."""
    types = [t[0] for t in AssetPermitLicense.PERMIT_TYPE_CHOICES]
    assert "environmental_emissions" in types
    assert "safety_operating" in types
    assert "hazardous_material" in types
    assert "water_discharge" in types
    assert "pressure_vessel" in types
    assert "radiation_device" in types
    assert "municipal_zoning" in types
    assert "transportation" in types

    statuses = [s[0] for s in AssetPermitLicense.STATUS_CHOICES]
    assert "active" in statuses
    assert "pending_renewal" in statuses
    assert "under_review" in statuses
    assert "expired" in statuses
    assert "suspended" in statuses
    assert "revoked" in statuses


def test_compliance_model_permit_badges(permit_license_a):
    """Verify badge CSS mappings for permit status and type."""
    assert permit_license_a.status_badge_class == "badge-green"
    assert permit_license_a.permit_type_badge_class == "badge-slate"

    permit_license_a.status = "pending_renewal"
    assert permit_license_a.status_badge_class == "badge-amber"
    permit_license_a.status = "under_review"
    assert permit_license_a.status_badge_class == "badge-info"
    permit_license_a.status = "expired"
    assert permit_license_a.status_badge_class == "badge-red"
    permit_license_a.status = "suspended"
    assert permit_license_a.status_badge_class == "badge-red"
    permit_license_a.status = "revoked"
    assert permit_license_a.status_badge_class == "badge-muted"

    permit_license_a.permit_type = "environmental_emissions"
    assert permit_license_a.permit_type_badge_class == "badge-amber"
    permit_license_a.permit_type = "safety_operating"
    assert permit_license_a.permit_type_badge_class == "badge-green"
    permit_license_a.permit_type = "hazardous_material"
    assert permit_license_a.permit_type_badge_class == "badge-red"
    permit_license_a.permit_type = "water_discharge"
    assert permit_license_a.permit_type_badge_class == "badge-info"
    permit_license_a.permit_type = "radiation_device"
    assert permit_license_a.permit_type_badge_class == "badge-red"
    permit_license_a.permit_type = "transportation"
    assert permit_license_a.permit_type_badge_class == "badge-info"


def test_compliance_model_permit_days_to_expiration(tenant_a, operational_asset_a):
    """Verify days_to_expiration calculation based on expiration date."""
    today = timezone.now().date()
    permit = _compliance_create_permit(
        tenant_a,
        asset=operational_asset_a,
        expiration_date=today + timezone.timedelta(days=45),
    )
    assert permit.days_to_expiration == 45


def test_compliance_model_permit_is_expiring_soon(tenant_a, operational_asset_a):
    """Verify is_expiring_soon returns True within renewal lead window."""
    today = timezone.now().date()
    # Within lead days (lead = 60, exp = 30) -> True
    permit_soon = _compliance_create_permit(
        tenant_a,
        asset=operational_asset_a,
        expiration_date=today + timezone.timedelta(days=30),
        renewal_lead_days=60,
        status="active",
    )
    assert permit_soon.is_expiring_soon is True

    # Beyond lead days (lead = 60, exp = 120) -> False
    permit_far = _compliance_create_permit(
        tenant_a,
        asset=operational_asset_a,
        expiration_date=today + timezone.timedelta(days=120),
        renewal_lead_days=60,
        status="active",
    )
    assert permit_far.is_expiring_soon is False

    # Within lead days but status not active -> False
    permit_inactive = _compliance_create_permit(
        tenant_a,
        asset=operational_asset_a,
        expiration_date=today + timezone.timedelta(days=30),
        renewal_lead_days=60,
        status="suspended",
    )
    assert permit_inactive.is_expiring_soon is False


def test_compliance_model_permit_is_expired_by_date(tenant_a, operational_asset_a):
    """Verify is_expired returns True when expiration date has passed."""
    today = timezone.now().date()
    permit = _compliance_create_permit(
        tenant_a,
        asset=operational_asset_a,
        expiration_date=today - timezone.timedelta(days=5),
        status="active",
    )
    assert permit.is_expired is True


def test_compliance_model_permit_is_expired_by_status(tenant_a, operational_asset_a):
    """Verify is_expired returns True when status is explicitly 'expired'."""
    today = timezone.now().date()
    permit = _compliance_create_permit(
        tenant_a,
        asset=operational_asset_a,
        expiration_date=today + timezone.timedelta(days=60),
        status="expired",
    )
    assert permit.is_expired is True


def test_compliance_model_permit_foreign_keys(permit_license_a, operational_asset_a, vendor_party_a):
    """Verify foreign keys for asset and issuing authority."""
    assert permit_license_a.asset == operational_asset_a
    assert permit_license_a.issuing_authority == vendor_party_a
    assert permit_license_a in operational_asset_a.permits_licenses.all()


# ==============================================================================
# Model 4: AssetComplianceIncident Tests
# ==============================================================================

def test_compliance_model_incident_auto_number_and_str(compliance_incident_a):
    """Verify ACI- auto-number generation and __str__ representation."""
    assert compliance_incident_a.number.startswith("ACI-")
    assert str(compliance_incident_a) == f"{compliance_incident_a.title} ({compliance_incident_a.number})"


def test_compliance_model_incident_defaults(tenant_a):
    """Verify compliance incident creation with minimal defaults."""
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        title="Unscheduled Flare Pit Combustion",
    )
    assert incident.incident_type == "safety_infraction"
    assert incident.severity == "serious"
    assert incident.root_cause == "mechanical_failure"
    assert incident.status == "open"
    assert incident.fine_assessed == Decimal("0.00")
    assert incident.fine_paid == Decimal("0.00")
    assert incident.citation_reference == ""
    assert incident.number.startswith("ACI-")


def test_compliance_model_incident_choices():
    """Verify INCIDENT_TYPE_CHOICES, SEVERITY_CHOICES, ROOT_CAUSE_CHOICES, STATUS_CHOICES."""
    types = [t[0] for t in AssetComplianceIncident.INCIDENT_TYPE_CHOICES]
    assert "notice_of_violation" in types
    assert "regulatory_citation" in types
    assert "emissions_exceedance" in types
    assert "unpermitted_discharge" in types
    assert "safety_infraction" in types
    assert "failed_inspection" in types
    assert "internal_audit_breach" in types

    severities = [s[0] for s in AssetComplianceIncident.SEVERITY_CHOICES]
    assert "de_minimis" in severities
    assert "other_than_serious" in severities
    assert "serious" in severities
    assert "repeat" in severities
    assert "willful" in severities
    assert "imminent_danger" in severities

    causes = [c[0] for c in AssetComplianceIncident.ROOT_CAUSE_CHOICES]
    assert "mechanical_failure" in causes
    assert "human_error" in causes
    assert "inadequate_procedure" in causes
    assert "lack_of_maintenance" in causes
    assert "measurement_error" in causes
    assert "external_factor" in causes

    statuses = [s[0] for s in AssetComplianceIncident.STATUS_CHOICES]
    assert "open" in statuses
    assert "under_investigation" in statuses
    assert "capa_in_progress" in statuses
    assert "under_agency_review" in statuses
    assert "appealed" in statuses
    assert "resolved" in statuses
    assert "closed" in statuses


def test_compliance_model_incident_badges(compliance_incident_a):
    """Verify badge CSS mappings for incident fields."""
    assert compliance_incident_a.status_badge_class == "badge-green"
    assert compliance_incident_a.severity_badge_class == "badge-amber"
    assert compliance_incident_a.incident_type_badge_class == "badge-amber"
    assert compliance_incident_a.root_cause_badge_class == "badge-amber"

    compliance_incident_a.status = "open"
    assert compliance_incident_a.status_badge_class == "badge-red"
    compliance_incident_a.status = "under_investigation"
    assert compliance_incident_a.status_badge_class == "badge-amber"
    compliance_incident_a.status = "capa_in_progress"
    assert compliance_incident_a.status_badge_class == "badge-info"
    compliance_incident_a.status = "closed"
    assert compliance_incident_a.status_badge_class == "badge-muted"

    compliance_incident_a.severity = "de_minimis"
    assert compliance_incident_a.severity_badge_class == "badge-slate"
    compliance_incident_a.severity = "other_than_serious"
    assert compliance_incident_a.severity_badge_class == "badge-info"
    compliance_incident_a.severity = "repeat"
    assert compliance_incident_a.severity_badge_class == "badge-red"
    compliance_incident_a.severity = "imminent_danger"
    assert compliance_incident_a.severity_badge_class == "badge-red"

    compliance_incident_a.root_cause = "human_error"
    assert compliance_incident_a.root_cause_badge_class == "badge-slate"
    compliance_incident_a.root_cause = "inadequate_procedure"
    assert compliance_incident_a.root_cause_badge_class == "badge-info"
    compliance_incident_a.root_cause = "lack_of_maintenance"
    assert compliance_incident_a.root_cause_badge_class == "badge-red"


def test_compliance_model_incident_outstanding_fine_and_penalty(tenant_a):
    """Verify outstanding_fine and outstanding_penalty property calculation."""
    incident = _compliance_create_incident(
        tenant_a,
        fine_assessed=Decimal("15000.00"),
        fine_paid=Decimal("5000.00"),
    )
    assert incident.outstanding_fine == Decimal("10000.00")
    assert incident.outstanding_penalty == Decimal("10000.00")

    # If paid in full
    incident.fine_paid = Decimal("15000.00")
    assert incident.outstanding_fine == Decimal("0.00")
    assert incident.outstanding_penalty == Decimal("0.00")


def test_compliance_model_incident_has_outstanding_fine(tenant_a):
    """Verify has_outstanding_fine returns True if fine remains unpaid."""
    incident = _compliance_create_incident(
        tenant_a,
        fine_assessed=Decimal("5000.00"),
        fine_paid=Decimal("0.00"),
    )
    assert incident.has_outstanding_fine is True

    incident.fine_paid = Decimal("5000.00")
    assert incident.has_outstanding_fine is False


def test_compliance_model_incident_is_resolved(compliance_incident_a):
    """Verify is_resolved property for resolved and closed states."""
    compliance_incident_a.status = "resolved"
    assert compliance_incident_a.is_resolved is True

    compliance_incident_a.status = "closed"
    assert compliance_incident_a.is_resolved is True

    compliance_incident_a.status = "open"
    assert compliance_incident_a.is_resolved is False

    compliance_incident_a.status = "under_investigation"
    assert compliance_incident_a.is_resolved is False


def test_compliance_model_incident_foreign_keys(
    compliance_incident_a,
    operational_asset_a,
    permit_license_a,
    compliance_audit_a,
    vendor_party_a,
    admin_user,
):
    """Verify related object linkage for incident."""
    assert compliance_incident_a.asset == operational_asset_a
    assert compliance_incident_a.permit == permit_license_a
    assert compliance_incident_a.audit == compliance_audit_a
    assert compliance_incident_a.enforcement_agency == vendor_party_a
    assert compliance_incident_a.assigned_investigator == admin_user
    assert compliance_incident_a in operational_asset_a.compliance_incidents.all()
    assert compliance_incident_a in permit_license_a.incidents.all()
    assert compliance_incident_a in compliance_audit_a.incidents.all()


# ==============================================================================
# Model 5: Multi-Tenancy & Cross-Cutting Invariants
# ==============================================================================

def test_compliance_model_tenant_isolation_framework(
    tenant_a,
    tenant_b,
    compliance_framework_a,
    compliance_framework_b,
):
    """Verify tenant isolation on AssetComplianceFramework."""
    frameworks_a = AssetComplianceFramework.objects.filter(tenant=tenant_a)
    assert compliance_framework_a in frameworks_a
    assert compliance_framework_b not in frameworks_a

    frameworks_b = AssetComplianceFramework.objects.filter(tenant=tenant_b)
    assert compliance_framework_b in frameworks_b
    assert compliance_framework_a not in frameworks_b


def test_compliance_model_tenant_isolation_audit(
    tenant_a,
    tenant_b,
    compliance_audit_a,
    compliance_audit_b,
):
    """Verify tenant isolation on AssetComplianceAudit."""
    audits_a = AssetComplianceAudit.objects.filter(tenant=tenant_a)
    assert compliance_audit_a in audits_a
    assert compliance_audit_b not in audits_a

    audits_b = AssetComplianceAudit.objects.filter(tenant=tenant_b)
    assert compliance_audit_b in audits_b
    assert compliance_audit_a not in audits_b


def test_compliance_model_tenant_isolation_permit(
    tenant_a,
    tenant_b,
    permit_license_a,
    permit_license_b,
):
    """Verify tenant isolation on AssetPermitLicense."""
    permits_a = AssetPermitLicense.objects.filter(tenant=tenant_a)
    assert permit_license_a in permits_a
    assert permit_license_b not in permits_a

    permits_b = AssetPermitLicense.objects.filter(tenant=tenant_b)
    assert permit_license_b in permits_b
    assert permit_license_a not in permits_b


def test_compliance_model_tenant_isolation_incident(
    tenant_a,
    tenant_b,
    compliance_incident_a,
    compliance_incident_b,
):
    """Verify tenant isolation on AssetComplianceIncident."""
    incidents_a = AssetComplianceIncident.objects.filter(tenant=tenant_a)
    assert compliance_incident_a in incidents_a
    assert compliance_incident_b not in incidents_a

    incidents_b = AssetComplianceIncident.objects.filter(tenant=tenant_b)
    assert compliance_incident_b in incidents_b
    assert compliance_incident_a not in incidents_b


def test_compliance_model_unique_number_same_tenant_raises_error(
    tenant_a,
    compliance_framework_a,
    compliance_audit_a,
    permit_license_a,
    compliance_incident_a,
):
    """Verify UniqueConstraint raises IntegrityError for duplicate number within same tenant."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _compliance_create_framework(tenant_a, number=compliance_framework_a.number)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _compliance_create_audit(
                tenant_a,
                framework=compliance_framework_a,
                number=compliance_audit_a.number,
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _compliance_create_permit(
                tenant_a,
                asset=permit_license_a.asset,
                number=permit_license_a.number,
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _compliance_create_incident(
                tenant_a,
                number=compliance_incident_a.number,
            )


def test_compliance_model_cross_tenant_same_number_allowed(
    tenant_a,
    tenant_b,
    operational_asset_b,
):
    """Verify composite unique (tenant, number) allows same number in different tenants."""
    shared_fw_num = "ACF-SHARED-0001"
    fw_a = _compliance_create_framework(tenant_a, number=shared_fw_num)
    fw_b = _compliance_create_framework(tenant_b, number=shared_fw_num)
    assert fw_a.number == shared_fw_num
    assert fw_b.number == shared_fw_num
    assert fw_a.tenant != fw_b.tenant

    shared_perm_num = "APL-SHARED-0001"
    perm_a = _compliance_create_permit(tenant_a, asset=operational_asset_b, number=shared_perm_num)
    perm_b = _compliance_create_permit(tenant_b, asset=operational_asset_b, number=shared_perm_num)
    assert perm_a.number == shared_perm_num
    assert perm_b.number == shared_perm_num


def test_compliance_model_auto_numbering_sequential(tenant_a, compliance_framework_a, operational_asset_a):
    """Verify sequential number allocation produces distinct auto numbers with valid prefixes."""
    fw1 = _compliance_create_framework(tenant_a, name="Seq FW 1", code="SEQ-01")
    fw2 = _compliance_create_framework(tenant_a, name="Seq FW 2", code="SEQ-02")
    assert fw1.number.startswith("ACF-")
    assert fw2.number.startswith("ACF-")
    assert fw1.number != fw2.number

    audit1 = _compliance_create_audit(tenant_a, framework=compliance_framework_a, title="Seq Audit 1")
    audit2 = _compliance_create_audit(tenant_a, framework=compliance_framework_a, title="Seq Audit 2")
    assert audit1.number.startswith("ACA-")
    assert audit2.number.startswith("ACA-")
    assert audit1.number != audit2.number

    perm1 = _compliance_create_permit(tenant_a, asset=operational_asset_a, permit_name="Seq Permit 1", permit_number="P1")
    perm2 = _compliance_create_permit(tenant_a, asset=operational_asset_a, permit_name="Seq Permit 2", permit_number="P2")
    assert perm1.number.startswith("APL-")
    assert perm2.number.startswith("APL-")
    assert perm1.number != perm2.number

    inc1 = _compliance_create_incident(tenant_a, title="Seq Incident 1")
    inc2 = _compliance_create_incident(tenant_a, title="Seq Incident 2")
    assert inc1.number.startswith("ACI-")
    assert inc2.number.startswith("ACI-")
    assert inc1.number != inc2.number
