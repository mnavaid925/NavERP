"""Model unit tests for Sub-module 13.10: Audit Trail & Reporting.

Tests the four core models:
1. DocumentAuditTrail:
   - Number sequence (DAUD- prefix), tenant isolation.
   - String representation __str__.
   - Immutable append-only invariant: updates and deletes raise ValidationError.
   - Cryptographic chain integrity: compute_chain_hash(), verify_hash(), SHA-256 calculation.
   - Genesis block handling for first record.
   - Snapshots and badge methods.

2. AuditReportDefinition:
   - Number sequence (DRPT- prefix), tenant isolation.
   - String representation, choices (REPORT_TYPE_CHOICES, STATUS_CHOICES).
   - Date range resolution (get_effective_date_range).
   - execute_query() execution and summary metric computation.
   - Badge methods.

3. DocumentSecurityAlert:
   - Number sequence (DANM- prefix), tenant isolation.
   - String representation, choices (ALERT_TYPE_CHOICES, SEVERITY_CHOICES, STATUS_CHOICES).
   - Triage action updates, risk score boundaries (1 to 100).
   - Badge methods.

4. ChainOfCustodyExport:
   - Number sequence (DCOC- prefix), tenant isolation.
   - Manifest generation (generate_manifest()), package SHA-256 seal (seal_package()).
   - Passcode verification (set_passcode(), check_passcode()).
   - Expiration property (is_expired), is_valid, revocation, status badges.
"""
from datetime import date, datetime, timedelta
import hashlib
import json
import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.documents.models.AuditReporting.AuditReportDefinitions import AuditReportDefinition
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Module-level test helpers (prefix _audit_reporting_*)
# ---------------------------------------------------------------------------

def _audit_reporting_create_audit_trail(
    tenant,
    document=None,
    version=None,
    actor=None,
    action_type="viewed",
    is_success=True,
    failure_reason="",
    details_json=None,
    ip_address=None,
    user_agent="",
    session_id="",
):
    """Helper to create a DocumentAuditTrail entry."""
    return DocumentAuditTrail.objects.create(
        tenant=tenant,
        document=document,
        version=version,
        actor=actor,
        action_type=action_type,
        is_success=is_success,
        failure_reason=failure_reason,
        details_json=details_json or {},
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
    )


def _audit_reporting_create_report_def(
    tenant,
    user=None,
    name="Standard Audit Report",
    report_type="custom_query",
    date_range_preset="last_30_days",
    custom_start_date=None,
    custom_end_date=None,
    filter_criteria_json=None,
    output_format="table_view",
    status="active",
    is_system_preset=False,
    description="Automated compliance query",
):
    """Helper to create an AuditReportDefinition."""
    return AuditReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        report_type=report_type,
        date_range_preset=date_range_preset,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
        filter_criteria_json=filter_criteria_json or {},
        output_format=output_format,
        status=status,
        is_system_preset=is_system_preset,
        description=description,
        created_by=user,
    )


def _audit_reporting_create_security_alert(
    tenant,
    target_user=None,
    document=None,
    alert_type="mass_download",
    severity="medium",
    risk_score=50,
    title="Anomalous User Activity Triggered",
    description="Heuristic threshold breached for document operations.",
    status="new",
    action_taken="logged_only",
    source_ip="192.168.1.100",
    event_count=1,
    evidence_json=None,
):
    """Helper to create a DocumentSecurityAlert."""
    return DocumentSecurityAlert.objects.create(
        tenant=tenant,
        target_user=target_user,
        target_document=document,
        alert_type=alert_type,
        severity=severity,
        risk_score=risk_score,
        title=title,
        description=description,
        status=status,
        action_taken=action_taken,
        source_ip=source_ip,
        event_count=event_count,
        evidence_json=evidence_json or {},
    )


def _audit_reporting_create_custody_export(
    tenant,
    user,
    document=None,
    folder=None,
    title="Litigation Evidence Vault",
    regulatory_framework="general_compliance",
    scope="single_document",
    auditor_name="Jane Doe",
    auditor_email="j.doe@auditorcorp.org",
    auditor_organization="Auditor Corp Global",
    expires_in_days=30,
    is_portal_active=True,
    passcode=None,
):
    """Helper to create a ChainOfCustodyExport package."""
    pkg = ChainOfCustodyExport(
        tenant=tenant,
        title=title,
        regulatory_framework=regulatory_framework,
        scope=scope,
        document=document,
        folder=folder,
        auditor_name=auditor_name,
        auditor_email=auditor_email,
        auditor_organization=auditor_organization,
        expires_at=timezone.now() + timedelta(days=expires_in_days),
        is_portal_active=is_portal_active,
        created_by=user,
    )
    if passcode:
        pkg.set_passcode(passcode)
    pkg.save()
    return pkg


# ---------------------------------------------------------------------------
# 1. DocumentAuditTrail Model Tests
# ---------------------------------------------------------------------------

def test_audit_reporting_audit_trail_autonumber_and_defaults(tenant_a, admin_user, document):
    """Test auto-number sequence (DAUD- prefix), defaults, and initial chain generation."""
    entry = _audit_reporting_create_audit_trail(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        action_type="viewed",
    )
    assert entry.number.startswith("DAUD-")
    assert len(entry.number) > 5
    assert entry.action_type == "viewed"
    assert entry.is_success is True
    assert entry.failure_reason == ""
    assert entry.prev_hash != ""
    assert len(entry.chain_hash) == 64
    assert entry.event_timestamp is not None
    assert entry.document_number_snapshot == document.number
    assert entry.document_title_snapshot == document.title
    assert entry.actor_email_snapshot == admin_user.email


def test_audit_reporting_audit_trail_tenant_isolation(tenant_a, tenant_b, admin_user):
    """Test tenant isolation: records are strictly segregated across tenants."""
    entry_a = _audit_reporting_create_audit_trail(tenant=tenant_a, actor=admin_user, action_type="created")
    entry_b = _audit_reporting_create_audit_trail(tenant=tenant_b, actor=admin_user, action_type="created")

    assert entry_a.tenant == tenant_a
    assert entry_b.tenant == tenant_b
    assert entry_a.pk != entry_b.pk

    # Queryset segregation
    qs_a = DocumentAuditTrail.objects.filter(tenant=tenant_a)
    qs_b = DocumentAuditTrail.objects.filter(tenant=tenant_b)
    assert entry_a in qs_a
    assert entry_a not in qs_b
    assert entry_b in qs_b
    assert entry_b not in qs_a


def test_audit_reporting_audit_trail_string_representation(tenant_a, admin_user, document):
    """Test __str__ representation formatting with snapshots and fallback."""
    entry = _audit_reporting_create_audit_trail(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        action_type="downloaded",
    )
    expected = f"[{entry.number}] Document Downloaded on {document.number} by {admin_user.email}"
    assert str(entry) == expected

    # Test fallback representation when document and actor are absent
    system_entry = DocumentAuditTrail.objects.create(
        tenant=tenant_a,
        action_type="purged",
    )
    expected_sys = f"[{system_entry.number}] Document Purged on General by System/Guest"
    assert str(system_entry) == expected_sys


def test_audit_reporting_audit_trail_immutable_update_raises(document_audit_trail):
    """Test that modifying and saving an existing DocumentAuditTrail raises ValidationError."""
    document_audit_trail.action_type = "edited"
    with pytest.raises(ValidationError) as exc_info:
        document_audit_trail.save()

    assert "Audit records are strictly immutable and cannot be updated." in str(exc_info.value)

    # Verify database record remains untouched
    reloaded = DocumentAuditTrail.objects.get(pk=document_audit_trail.pk)
    assert reloaded.action_type == "viewed"


def test_audit_reporting_audit_trail_immutable_delete_raises(document_audit_trail):
    """Test that deleting a DocumentAuditTrail raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        document_audit_trail.delete()

    assert "Audit records cannot be deleted." in str(exc_info.value)
    assert DocumentAuditTrail.objects.filter(pk=document_audit_trail.pk).exists()


def test_audit_reporting_audit_trail_cryptographic_chain_integrity(tenant_a, admin_user, document):
    """Test compute_chain_hash() formula and verify_hash() tamper verification."""
    entry = _audit_reporting_create_audit_trail(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        action_type="checked_in",
        details_json={"version": "1.1", "size": 1024},
    )

    # Hash should verify successfully initially
    assert entry.verify_hash() is True

    # Manually recompute expected SHA-256
    raw_payload = (
        f"{entry.prev_hash}|{entry.tenant_id}|{entry.action_type}|"
        f"{entry.event_timestamp.isoformat()}|{entry.actor_email_snapshot}|"
        f"{entry.document_number_snapshot}|{json.dumps(entry.details_json, sort_keys=True)}"
    )
    expected_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    assert entry.chain_hash == expected_hash

    # Tampering with an in-memory field causes verify_hash to return False
    entry.action_type = "deleted"
    assert entry.verify_hash() is False


def test_audit_reporting_audit_trail_genesis_block_and_chaining(tenant_b, admin_user):
    """Test that the first record uses the GENESIS_BLOCK and subsequent records link hashes."""
    # First record in tenant_b must link to the genesis block
    first = _audit_reporting_create_audit_trail(tenant=tenant_b, actor=admin_user, action_type="created")
    assert first.prev_hash == "GENESIS_BLOCK_000000000000000000000000000000000000000000000000000000"
    assert first.verify_hash() is True

    # Second record in tenant_b must link to the first record's chain_hash
    second = _audit_reporting_create_audit_trail(tenant=tenant_b, actor=admin_user, action_type="viewed")
    assert second.prev_hash == first.chain_hash
    assert second.verify_hash() is True

    # Third record in tenant_b must link to the second record's chain_hash
    third = _audit_reporting_create_audit_trail(tenant=tenant_b, actor=admin_user, action_type="downloaded")
    assert third.prev_hash == second.chain_hash
    assert third.verify_hash() is True


def test_audit_reporting_audit_trail_snapshot_population(tenant_a, admin_user, document):
    """Test auto-population of document and actor snapshots before hash computation."""
    entry = DocumentAuditTrail(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        action_type="signed",
    )
    # Snapshots are initially empty on unsaved model instance
    assert entry.document_number_snapshot == ""
    assert entry.document_title_snapshot == ""
    assert entry.actor_email_snapshot == ""

    entry.save()

    # After save, snapshots are filled and hash is computed using them
    assert entry.document_number_snapshot == document.number
    assert entry.document_title_snapshot == document.title
    assert entry.actor_email_snapshot == admin_user.email
    assert entry.verify_hash() is True


def test_audit_reporting_audit_trail_badges_and_choices(tenant_a, admin_user):
    """Test CSS badge mappings for various action types and boolean results."""
    success_entry = _audit_reporting_create_audit_trail(
        tenant=tenant_a, actor=admin_user, action_type="downloaded", is_success=True
    )
    assert success_entry.get_action_type_badge() == "badge-green"
    assert success_entry.get_result_badge() == "badge-green"

    denied_entry = _audit_reporting_create_audit_trail(
        tenant=tenant_a, actor=admin_user, action_type="dlp_violation", is_success=False
    )
    assert denied_entry.get_action_type_badge() == "badge-red"
    assert denied_entry.get_result_badge() == "badge-red"

    view_entry = _audit_reporting_create_audit_trail(
        tenant=tenant_a, actor=admin_user, action_type="viewed", is_success=True
    )
    assert view_entry.get_action_type_badge() == "badge-slate"


# ---------------------------------------------------------------------------
# 2. AuditReportDefinition Model Tests
# ---------------------------------------------------------------------------

def test_audit_reporting_report_def_autonumber_and_defaults(tenant_a, admin_user):
    """Test auto-number sequence (DRPT- prefix) and model default field values."""
    rpt = _audit_reporting_create_report_def(tenant=tenant_a, user=admin_user, name="Monthly Security Audit")
    assert rpt.number.startswith("DRPT-")
    assert len(rpt.number) > 5
    assert rpt.name == "Monthly Security Audit"
    assert rpt.report_type == "custom_query"
    assert rpt.date_range_preset == "last_30_days"
    assert rpt.output_format == "table_view"
    assert rpt.status == "active"
    assert rpt.is_system_preset is False
    assert rpt.total_runs == 0
    assert rpt.last_run_at is None
    assert rpt.last_run_by is None


def test_audit_reporting_report_def_tenant_isolation(tenant_a, tenant_b, admin_user):
    """Test report definitions are isolated per tenant."""
    rpt_a = _audit_reporting_create_report_def(tenant=tenant_a, user=admin_user, name="Tenant A Access Log")
    rpt_b = _audit_reporting_create_report_def(tenant=tenant_b, user=admin_user, name="Tenant B Access Log")

    assert rpt_a.tenant == tenant_a
    assert rpt_b.tenant == tenant_b
    assert rpt_a in AuditReportDefinition.objects.filter(tenant=tenant_a)
    assert rpt_a not in AuditReportDefinition.objects.filter(tenant=tenant_b)


def test_audit_reporting_report_def_string_representation(tenant_a, admin_user):
    """Test __str__ formatting for custom definitions and system presets."""
    custom_rpt = _audit_reporting_create_report_def(
        tenant=tenant_a, user=admin_user, name="Vendor Access Log", is_system_preset=False
    )
    assert str(custom_rpt) == f"Vendor Access Log ({custom_rpt.number})"

    preset_rpt = _audit_reporting_create_report_def(
        tenant=tenant_a, user=admin_user, name="HIPAA Audit Preset", is_system_preset=True
    )
    assert str(preset_rpt) == f"HIPAA Audit Preset ({preset_rpt.number}) [Preset]"


def test_audit_reporting_report_def_choices_and_badges(tenant_a, admin_user):
    """Test report type choices, status choices, and corresponding badge methods."""
    types_to_css = {
        "document_history": "badge-info",
        "user_activity": "badge-slate",
        "confidential_access": "badge-amber",
        "permission_audit": "badge-info",
        "security_exceptions": "badge-red",
        "external_sharing": "badge-amber",
        "deletion_purge": "badge-red",
        "lifecycle_bottlenecks": "badge-amber",
        "version_churn": "badge-slate",
        "custom_query": "badge-green",
    }
    for rtype, expected_badge in types_to_css.items():
        rpt = _audit_reporting_create_report_def(
            tenant=tenant_a, user=admin_user, name=f"Report {rtype}", report_type=rtype
        )
        assert rpt.get_report_type_badge() == expected_badge

    # Test status badges
    active_rpt = _audit_reporting_create_report_def(tenant=tenant_a, user=admin_user, status="active")
    assert active_rpt.get_status_badge() == "badge-green"

    archived_rpt = _audit_reporting_create_report_def(tenant=tenant_a, user=admin_user, status="archived")
    assert archived_rpt.get_status_badge() == "badge-muted"


def test_audit_reporting_report_def_effective_date_range(tenant_a, admin_user):
    """Test get_effective_date_range() calculation across presets and custom dates."""
    now = timezone.now()

    # Preset: today
    rpt_today = _audit_reporting_create_report_def(
        tenant=tenant_a, user=admin_user, date_range_preset="today"
    )
    start, end = rpt_today.get_effective_date_range()
    assert start.date() == now.date()
    assert start.hour == 0 and start.minute == 0
    assert end >= start

    # Preset: last_7_days
    rpt_7 = _audit_reporting_create_report_def(
        tenant=tenant_a, user=admin_user, date_range_preset="last_7_days"
    )
    start_7, end_7 = rpt_7.get_effective_date_range()
    assert (end_7 - start_7).days in (7, 8)

    # Preset: last_30_days
    rpt_30 = _audit_reporting_create_report_def(
        tenant=tenant_a, user=admin_user, date_range_preset="last_30_days"
    )
    start_30, end_30 = rpt_30.get_effective_date_range()
    assert (end_30 - start_30).days in (30, 31)

    # Preset: custom date range
    d_start = date(2026, 1, 1)
    d_end = date(2026, 1, 31)
    rpt_custom = _audit_reporting_create_report_def(
        tenant=tenant_a,
        user=admin_user,
        date_range_preset="custom",
        custom_start_date=d_start,
        custom_end_date=d_end,
    )
    start_c, end_c = rpt_custom.get_effective_date_range()
    assert start_c.date() == d_start
    assert end_c.date() == d_end


def test_audit_reporting_report_def_execute_query_and_metrics(tenant_a, admin_user, member_user, document):
    """Test execute_query() filters events, calculates summary KPI metrics, and updates run stats."""
    # Seed audit entries in tenant_a
    _audit_reporting_create_audit_trail(
        tenant=tenant_a, document=document, actor=admin_user, action_type="viewed", is_success=True
    )
    _audit_reporting_create_audit_trail(
        tenant=tenant_a, document=document, actor=member_user, action_type="downloaded", is_success=True
    )
    _audit_reporting_create_audit_trail(
        tenant=tenant_a, document=document, actor=member_user, action_type="dlp_violation", is_success=False
    )

    # 1. Custom query report (matches all recent events in date range)
    custom_rpt = _audit_reporting_create_report_def(
        tenant=tenant_a,
        user=admin_user,
        name="All Activity",
        report_type="custom_query",
        date_range_preset="last_7_days",
    )
    events_qs, kpis = custom_rpt.execute_query(user=admin_user)

    assert events_qs.count() == 3
    assert kpis["total_events"] == 3
    assert kpis["success_events"] == 2
    assert kpis["failed_events"] == 1
    assert kpis["unique_actors"] == 2
    assert kpis["success_rate"] == 66.7

    # Run stats updated
    custom_rpt.refresh_from_db()
    assert custom_rpt.total_runs == 1
    assert custom_rpt.last_run_by == admin_user
    assert custom_rpt.last_run_at is not None

    # 2. Security exceptions report (only failed / DLP violation events)
    sec_rpt = _audit_reporting_create_report_def(
        tenant=tenant_a,
        user=admin_user,
        name="Security Violations",
        report_type="security_exceptions",
        date_range_preset="last_7_days",
    )
    sec_events, sec_kpis = sec_rpt.execute_query()
    assert sec_events.count() == 1
    assert sec_kpis["failed_events"] == 1


# ---------------------------------------------------------------------------
# 3. DocumentSecurityAlert Model Tests
# ---------------------------------------------------------------------------

def test_audit_reporting_security_alert_autonumber_and_defaults(tenant_a, member_user):
    """Test auto-number sequence (DANM- prefix) and default values of DocumentSecurityAlert."""
    alert = _audit_reporting_create_security_alert(
        tenant=tenant_a,
        target_user=member_user,
        alert_type="mass_download",
    )
    assert alert.number.startswith("DANM-")
    assert len(alert.number) > 5
    assert alert.severity == "medium"
    assert alert.risk_score == 50
    assert alert.status == "new"
    assert alert.action_taken == "logged_only"
    assert alert.event_count == 1
    assert alert.assigned_to is None
    assert alert.resolved_at is None
    assert alert.resolved_by is None


def test_audit_reporting_security_alert_tenant_isolation(tenant_a, tenant_b, member_user):
    """Test security alert tenant boundaries."""
    alert_a = _audit_reporting_create_security_alert(tenant=tenant_a, target_user=member_user, title="Threat Alpha")
    alert_b = _audit_reporting_create_security_alert(tenant=tenant_b, target_user=member_user, title="Threat Beta")

    assert alert_a.tenant == tenant_a
    assert alert_b.tenant == tenant_b
    assert alert_a in DocumentSecurityAlert.objects.filter(tenant=tenant_a)
    assert alert_a not in DocumentSecurityAlert.objects.filter(tenant=tenant_b)


def test_audit_reporting_security_alert_string_representation(tenant_a, member_user):
    """Test __str__ formatting with number, severity display, and headline."""
    alert = _audit_reporting_create_security_alert(
        tenant=tenant_a,
        target_user=member_user,
        severity="critical",
        title="Excessive Credential Abuse",
    )
    expected = f"[{alert.number}] (Critical Threat (Risk 90-100)) Excessive Credential Abuse"
    assert str(alert) == expected


def test_audit_reporting_security_alert_choices_and_badges(tenant_a, member_user):
    """Test badge mappings for alert types, severities, and triage statuses."""
    alert = _audit_reporting_create_security_alert(
        tenant=tenant_a,
        target_user=member_user,
        alert_type="mass_download",
        severity="high",
        status="investigating",
    )
    assert alert.get_alert_type_badge() == "badge-red"
    assert alert.get_severity_badge() == "badge-amber"
    assert alert.get_status_badge() == "badge-amber"

    alert.severity = "critical"
    alert.status = "confirmed_threat"
    assert alert.get_severity_badge() == "badge-red"
    assert alert.get_status_badge() == "badge-red"

    alert.status = "resolved"
    assert alert.get_status_badge() == "badge-green"

    alert.status = "dismissed"
    assert alert.get_status_badge() == "badge-muted"


def test_audit_reporting_security_alert_risk_score_boundaries(tenant_a, member_user):
    """Test risk score storage across boundary range (1 to 100)."""
    min_alert = _audit_reporting_create_security_alert(
        tenant=tenant_a, target_user=member_user, risk_score=1, severity="low"
    )
    assert min_alert.risk_score == 1

    max_alert = _audit_reporting_create_security_alert(
        tenant=tenant_a, target_user=member_user, risk_score=100, severity="critical"
    )
    assert max_alert.risk_score == 100

    mid_alert = _audit_reporting_create_security_alert(
        tenant=tenant_a, target_user=member_user, risk_score=75, severity="high"
    )
    assert mid_alert.risk_score == 75


def test_audit_reporting_security_alert_triage_updates(tenant_a, admin_user, member_user):
    """Test triage workflow: assigning investigator, notes, mitigating action, and resolution."""
    alert = _audit_reporting_create_security_alert(tenant=tenant_a, target_user=member_user, status="new")

    # Step 1: Assign and triage
    alert.status = "investigating"
    alert.assigned_to = admin_user
    alert.action_taken = "user_warned"
    alert.triage_notes = "Contacted employee to verify whether bulk download was approved."
    alert.save()

    reloaded = DocumentSecurityAlert.objects.get(pk=alert.pk)
    assert reloaded.status == "investigating"
    assert reloaded.assigned_to == admin_user
    assert reloaded.action_taken == "user_warned"
    assert "Contacted employee" in reloaded.triage_notes

    # Step 2: Mitigate and resolve
    reloaded.status = "resolved"
    reloaded.action_taken = "downloads_blocked"
    reloaded.resolved_at = timezone.now()
    reloaded.resolved_by = admin_user
    reloaded.save()

    final = DocumentSecurityAlert.objects.get(pk=alert.pk)
    assert final.status == "resolved"
    assert final.action_taken == "downloads_blocked"
    assert final.resolved_at is not None
    assert final.resolved_by == admin_user


# ---------------------------------------------------------------------------
# 4. ChainOfCustodyExport Model Tests
# ---------------------------------------------------------------------------

def test_audit_reporting_custody_export_autonumber_and_defaults(tenant_a, admin_user, document):
    """Test auto-number sequence (DCOC- prefix), generated token, and defaults."""
    pkg = _audit_reporting_create_custody_export(
        tenant=tenant_a,
        user=admin_user,
        document=document,
        title="FDA Audit Evidence Pack",
        regulatory_framework="fda_21cfr11",
    )
    assert pkg.number.startswith("DCOC-")
    assert len(pkg.number) > 5
    assert len(pkg.access_token) > 20
    assert pkg.scope == "single_document"
    assert pkg.is_sealed is True
    assert pkg.sealed_at is not None
    assert pkg.is_portal_active is True
    assert pkg.access_count == 0
    assert pkg.last_accessed_at is None
    assert pkg.package_hash != ""
    assert len(pkg.package_hash) == 64


def test_audit_reporting_custody_export_tenant_isolation(tenant_a, tenant_b, admin_user):
    """Test chain-of-custody export packages remain isolated per tenant."""
    pkg_a = _audit_reporting_create_custody_export(tenant=tenant_a, user=admin_user, title="Tenant A Package")
    pkg_b = _audit_reporting_create_custody_export(tenant=tenant_b, user=admin_user, title="Tenant B Package")

    assert pkg_a.tenant == tenant_a
    assert pkg_b.tenant == tenant_b
    assert pkg_a in ChainOfCustodyExport.objects.filter(tenant=tenant_a)
    assert pkg_a not in ChainOfCustodyExport.objects.filter(tenant=tenant_b)


def test_audit_reporting_custody_export_string_representation(tenant_a, admin_user):
    """Test __str__ formatting with number, title, and framework display."""
    pkg = _audit_reporting_create_custody_export(
        tenant=tenant_a,
        user=admin_user,
        title="SOC2 Type II Package",
        regulatory_framework="soc2_type2",
    )
    expected = f"[{pkg.number}] SOC2 Type II Package (SOC 2 Type II Security & Confidentiality)"
    assert str(pkg) == expected


def test_audit_reporting_custody_export_manifest_generation(tenant_a, admin_user, document):
    """Test generate_manifest() creates structured payload and SHA-256 package hash."""
    pkg = _audit_reporting_create_custody_export(
        tenant=tenant_a,
        user=admin_user,
        document=document,
        title="ISO Audit Trail Bundle",
        regulatory_framework="iso_27001",
    )
    manifest = pkg.manifest_json
    assert manifest["package_number"] == pkg.number
    assert manifest["title"] == "ISO Audit Trail Bundle"
    assert manifest["regulatory_framework"] == "iso_27001"
    assert manifest["auditor"]["name"] == "Jane Doe"
    assert manifest["document"]["number"] == document.number
    assert manifest["document"]["title"] == document.title

    # Verify mathematical seal matches manifest JSON
    raw = json.dumps(manifest, sort_keys=True)
    expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert pkg.package_hash == expected_hash


def test_audit_reporting_custody_export_seal_package(tenant_a, admin_user, document):
    """Test seal_package() updates timestamps and generates verifiable package seal."""
    pkg = _audit_reporting_create_custody_export(
        tenant=tenant_a,
        user=admin_user,
        document=document,
        title="Annual Regulatory Inspection",
    )
    old_sealed_at = pkg.sealed_at
    digest = pkg.seal_package()

    pkg.refresh_from_db()
    assert pkg.is_sealed is True
    assert pkg.package_hash == digest
    assert len(digest) == 64
    assert pkg.sealed_at >= old_sealed_at


def test_audit_reporting_custody_export_passcode_verification(tenant_a, admin_user):
    """Test set_passcode() hashing and check_passcode() verification."""
    pkg = _audit_reporting_create_custody_export(
        tenant=tenant_a,
        user=admin_user,
        passcode="StrictInspectorPass2026!",
    )
    assert pkg.passcode_hash != ""
    assert pkg.passcode_hash != "StrictInspectorPass2026!"
    assert pkg.check_passcode("StrictInspectorPass2026!") is True
    assert pkg.check_passcode("WrongPassword") is False
    assert pkg.check_passcode("") is False

    # Empty passcode means no password required
    pkg.set_passcode("")
    assert pkg.passcode_hash == ""
    assert pkg.check_passcode("anything") is True


def test_audit_reporting_custody_export_expiration_and_validity(tenant_a, admin_user):
    """Test is_expired, is_valid, and status_key properties."""
    # Active package expiring in future
    active_pkg = _audit_reporting_create_custody_export(
        tenant=tenant_a, user=admin_user, expires_in_days=10, is_portal_active=True
    )
    assert active_pkg.is_expired is False
    assert active_pkg.is_valid is True
    assert active_pkg.status_key == "active"
    assert active_pkg.get_status_badge() == "badge-green"

    # Expired package
    expired_pkg = ChainOfCustodyExport(
        tenant=tenant_a,
        title="Old Evidence Package",
        expires_at=timezone.now() - timedelta(days=2),
        is_portal_active=True,
        created_by=admin_user,
        auditor_name="Auditor X",
        auditor_email="x@auditor.com",
    )
    expired_pkg.save()
    assert expired_pkg.is_expired is True
    assert expired_pkg.is_valid is False
    assert expired_pkg.status_key == "expired"
    assert expired_pkg.get_status_badge() == "badge-amber"


def test_audit_reporting_custody_export_revocation(tenant_a, admin_user, member_user):
    """Test revoke() deactivates external auditor portal access immediately."""
    pkg = _audit_reporting_create_custody_export(tenant=tenant_a, user=admin_user, is_portal_active=True)
    assert pkg.is_valid is True

    pkg.revoke(user=admin_user)

    pkg.refresh_from_db()
    assert pkg.is_portal_active is False
    assert pkg.revoked_at is not None
    assert pkg.revoked_by == admin_user
    assert pkg.is_valid is False
    assert pkg.status_key == "revoked"
    assert pkg.get_status_badge() == "badge-red"


def test_audit_reporting_custody_export_choices_and_badges(tenant_a, admin_user):
    """Test regulatory framework choices and badge CSS class resolution."""
    frameworks_to_css = {
        "general_compliance": "badge-slate",
        "iso_27001": "badge-info",
        "soc2_type2": "badge-green",
        "fda_21cfr11": "badge-amber",
        "hipaa": "badge-info",
        "gdpr_article30": "badge-slate",
        "legal_hold": "badge-red",
    }
    for fmwk, expected_css in frameworks_to_css.items():
        pkg = _audit_reporting_create_custody_export(
            tenant=tenant_a,
            user=admin_user,
            title=f"Package for {fmwk}",
            regulatory_framework=fmwk,
        )
        assert pkg.get_regulatory_framework_badge() == expected_css
