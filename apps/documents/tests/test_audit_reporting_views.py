"""View integration tests for Sub-module 13.10: Audit Trail & Reporting.

Covers all 16 views across the 5 controller modules:
1. DocumentAuditTrails:
   - audit_trail_list: 200, context keys, search q, date/action/success/doc filters, chain status, pagination.
   - audit_trail_detail: 200, context keys, prev/next navigation, verify_hash check, cross-tenant 404.
   - audit_trail_export_csv: 200, CSV response, Content-Disposition, formula injection escaping (_csv_safe).
   - audit_trail_verify_chain: POST-only, tenant_admin_required, validates hash chain across entries (intact & tampered).
2. AuditReportDefinitions:
   - audit_report_list: 200, context keys, filters by q, report_type, status, tenant isolation.
   - audit_report_create: GET/POST, context keys, form validation, successful redirect to detail.
   - audit_report_detail: 200, context keys, execution counter update, summary metrics and KPIs.
   - audit_report_edit: GET/POST, update custom report, system preset edit protection.
   - audit_report_run: GET/POST, downloadable CSV and JSON exports, report type filtering.
   - audit_report_delete: POST-only, admin/creator permission check, system preset protection.
3. DocumentSecurityAlerts:
   - security_alert_list: 200, context keys, filters by q, severity, status, alert_type, open/critical counts.
   - security_alert_detail: 200, context keys, target user stats, correlated audit logs.
   - security_alert_triage: POST-only, tenant_admin_required, triage status, resolved_at/by transition.
   - security_alert_scan: POST-only, tenant_admin_required, triggers heuristic UBA scan.
4. ChainOfCustodyExports:
   - custody_export_list: 200, context keys, search, framework filter, active passes count.
   - custody_export_create: GET/POST, seals manifest, passcode protection, redirects to detail.
   - custody_export_detail: 200, context keys, manifest inspection, package hash verification.
   - custody_export_certificate: 200, printable Certificate of Authenticity.
   - custody_export_revoke: POST-only, tenant_admin_required, revokes auditor portal pass.
   - auditor_portal_view & auditor_portal_verify: public view with token, passcode verification,
     revoked 403, expired 410, locked 5 failed attempts, audit logging.
5. AuditReportingDashboard:
   - audit_dashboard: 200, context keys (stats, recent_audit_logs, recent_alerts, active_custody_passes).
   - document_lifecycle_dashboard: 200, context keys (lifecycle_kpis, status_distribution, bottlenecks, churn).
"""
import csv
from datetime import timedelta
import io
import json
import pytest

from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.documents.models.AuditReporting.AuditReportDefinitions import AuditReportDefinition
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert
from apps.documents.models.ApprovalWorkflow.DocumentApprovalRequests import DocumentApprovalRequest
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion

pytestmark = pytest.mark.django_db


# ============================================================================
# Module-level helpers (prefix _audit_reporting_*)
# ============================================================================

def _audit_reporting_create_audit_entry(
    tenant,
    document=None,
    version=None,
    actor=None,
    action_type="viewed",
    is_success=True,
    failure_reason="",
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0 TestBrowser",
    details_json=None,
    timestamp=None,
):
    """Helper to create an immutable DocumentAuditTrail entry."""
    entry = DocumentAuditTrail(
        tenant=tenant,
        document=document,
        version=version,
        actor=actor,
        actor_email_snapshot=actor.email if actor else "guest@example.com",
        action_type=action_type,
        document_number_snapshot=document.number if document else "DOC-GEN",
        document_title_snapshot=document.title if document else "General Title",
        is_success=is_success,
        failure_reason=failure_reason,
        ip_address=ip_address,
        user_agent=user_agent,
        details_json=details_json or {"info": "test entry"},
    )
    if timestamp:
        entry.event_timestamp = timestamp
    entry.save()
    return entry


def _audit_reporting_create_report_def(
    tenant,
    created_by,
    name="Test Compliance Audit",
    report_type="confidential_access",
    date_range_preset="last_30_days",
    output_format="table_view",
    is_system_preset=False,
    status="active",
):
    """Helper to create an AuditReportDefinition."""
    return AuditReportDefinition.objects.create(
        tenant=tenant,
        created_by=created_by,
        name=name,
        report_type=report_type,
        date_range_preset=date_range_preset,
        output_format=output_format,
        is_system_preset=is_system_preset,
        status=status,
        description=f"Description for {name}",
    )


def _audit_reporting_create_alert(
    tenant,
    target_user,
    target_document=None,
    title="Anomalous Bulk Download",
    alert_type="mass_download",
    severity="high",
    status="investigating",
    risk_score=82,
):
    """Helper to create a DocumentSecurityAlert."""
    return DocumentSecurityAlert.objects.create(
        tenant=tenant,
        target_user=target_user,
        target_document=target_document,
        title=title,
        alert_type=alert_type,
        severity=severity,
        status=status,
        risk_score=risk_score,
        description=f"Detailed description for {title}",
        evidence_json={"downloads": 30, "window_minutes": 5},
    )


def _audit_reporting_create_custody_pkg(
    tenant,
    created_by,
    document,
    title="FDA 21 CFR Part 11 Evidence",
    regulatory_framework="fda_21cfr11",
    auditor_name="Dr. Jane Smith",
    auditor_email="j.smith@fda.gov",
    passcode="VerifyPass2026!",
    is_portal_active=True,
    expires_in_days=30,
):
    """Helper to create and seal a ChainOfCustodyExport."""
    pkg = ChainOfCustodyExport(
        tenant=tenant,
        created_by=created_by,
        document=document,
        scope="single_document",
        title=title,
        regulatory_framework=regulatory_framework,
        auditor_name=auditor_name,
        auditor_email=auditor_email,
        auditor_organization="Food and Drug Administration",
        expires_at=timezone.now() + timedelta(days=expires_in_days),
        is_portal_active=is_portal_active,
    )
    if passcode:
        pkg.set_passcode(passcode)
    pkg.save()
    return pkg


# ============================================================================
# 1. DocumentAuditTrails View Tests
# ============================================================================

def test_audit_reporting_audit_trail_list_get_success(client_a, tenant_a, document, admin_user):
    """Test audit_trail_list GET returns 200 with required context keys."""
    entry = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)
    url = reverse("documents:audit_trail_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "page_obj" in response.context
    assert "filter_form" in response.context
    assert "action_type_choices" in response.context
    assert "total_count" in response.context
    assert "chain_status" in response.context
    assert response.context["total_count"] >= 1
    assert entry in response.context["page_obj"]


def test_audit_reporting_audit_trail_list_anonymous_redirect(client):
    """Test unauthenticated user is redirected to login for audit_trail_list."""
    url = reverse("documents:audit_trail_list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url or "login" in response.url


def test_audit_reporting_audit_trail_list_search_filter(client_a, tenant_a, document, admin_user):
    """Test audit_trail_list filtering by search query 'q' across snapshots and IP."""
    e1 = _audit_reporting_create_audit_entry(
        tenant_a,
        document=document,
        actor=admin_user,
        action_type="downloaded",
        ip_address="10.20.30.40",
    )
    e2 = _audit_reporting_create_audit_entry(
        tenant_a,
        document=document,
        actor=admin_user,
        action_type="viewed",
        ip_address="172.16.0.5",
    )

    url = reverse("documents:audit_trail_list")

    # Search by IP
    res_ip = client_a.get(url, {"q": "10.20.30.40"})
    assert res_ip.status_code == 200
    assert e1 in res_ip.context["page_obj"]
    assert e2 not in res_ip.context["page_obj"]

    # Search by action_type in query
    res_act = client_a.get(url, {"q": "downloaded"})
    assert res_act.status_code == 200
    assert e1 in res_act.context["page_obj"]


def test_audit_reporting_audit_trail_list_filters(client_a, tenant_a, document, admin_user):
    """Test audit_trail_list filters for action_type, is_success, date range, and doc_id."""
    now = timezone.now()
    e_success = _audit_reporting_create_audit_entry(
        tenant_a,
        document=document,
        actor=admin_user,
        action_type="viewed",
        is_success=True,
        timestamp=now - timedelta(days=2),
    )
    e_failed = _audit_reporting_create_audit_entry(
        tenant_a,
        document=document,
        actor=admin_user,
        action_type="dlp_violation",
        is_success=False,
        failure_reason="Restricted keyword detected",
        timestamp=now,
    )

    url = reverse("documents:audit_trail_list")

    # Filter action_type
    res_at = client_a.get(url, {"action_type": "dlp_violation"})
    assert res_at.status_code == 200
    assert e_failed in res_at.context["page_obj"]
    assert e_success not in res_at.context["page_obj"]

    # Filter is_success
    res_succ = client_a.get(url, {"is_success": "1"})
    assert res_succ.status_code == 200
    assert e_success in res_succ.context["page_obj"]
    assert e_failed not in res_succ.context["page_obj"]

    res_fail = client_a.get(url, {"is_success": "0"})
    assert res_fail.status_code == 200
    assert e_failed in res_fail.context["page_obj"]
    assert e_success not in res_fail.context["page_obj"]

    # Filter doc_id
    res_doc = client_a.get(url, {"doc_id": str(document.pk)})
    assert res_doc.status_code == 200
    assert e_success in res_doc.context["page_obj"]

    # Filter date_from / date_to
    date_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    res_date = client_a.get(url, {"date_from": date_str})
    assert res_date.status_code == 200
    assert e_failed in res_date.context["page_obj"]
    assert e_success not in res_date.context["page_obj"]


def test_audit_reporting_audit_trail_list_pagination(client_a, tenant_a, document, admin_user):
    """Test audit_trail_list pagination splits cleanly across pages."""
    for i in range(18):
        _audit_reporting_create_audit_entry(
            tenant_a,
            document=document,
            actor=admin_user,
            action_type="viewed",
        )

    url = reverse("documents:audit_trail_list")
    res_p1 = client_a.get(url, {"page": 1})
    assert res_p1.status_code == 200
    assert len(res_p1.context["page_obj"]) == 15
    assert res_p1.context["page_obj"].has_next()

    res_p2 = client_a.get(url, {"page": 2})
    assert res_p2.status_code == 200
    assert len(res_p2.context["page_obj"]) >= 3


def test_audit_reporting_audit_trail_list_tenant_isolation(client_a, client_b, tenant_a, tenant_b, admin_user, admin_b):
    """Test tenant isolation: tenant_b audit records never leak into tenant_a list."""
    e_a = _audit_reporting_create_audit_entry(tenant_a, actor=admin_user)
    e_b = _audit_reporting_create_audit_entry(tenant_b, actor=admin_b)

    url = reverse("documents:audit_trail_list")
    res_a = client_a.get(url)
    assert res_a.status_code == 200
    assert e_a in res_a.context["page_obj"]
    assert e_b not in res_a.context["page_obj"]

    res_b = client_b.get(url)
    assert res_b.status_code == 200
    assert e_b in res_b.context["page_obj"]
    assert e_a not in res_b.context["page_obj"]


def test_audit_reporting_audit_trail_detail_get_success(client_a, tenant_a, document, admin_user):
    """Test audit_trail_detail returns 200 with required context keys and navigation."""
    e1 = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)
    e2 = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)
    e3 = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)

    url = reverse("documents:audit_trail_detail", kwargs={"pk": e2.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "audit_entry" in response.context
    assert response.context["audit_entry"] == e2
    assert "chain_valid" in response.context
    assert response.context["chain_valid"] is True
    assert response.context["prev_entry"].id == e1.id
    assert response.context["next_entry"].id == e3.id


def test_audit_reporting_audit_trail_detail_cross_tenant_404(client_a, tenant_b, admin_b):
    """Test accessing an audit trail entry belonging to another tenant returns 404."""
    e_b = _audit_reporting_create_audit_entry(tenant_b, actor=admin_b)
    url = reverse("documents:audit_trail_detail", kwargs={"pk": e_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_audit_reporting_audit_trail_export_csv_success(client_a, tenant_a, document, admin_user):
    """Test audit_trail_export_csv returns valid CSV attachment with headers and data."""
    entry = _audit_reporting_create_audit_entry(
        tenant_a,
        document=document,
        actor=admin_user,
        action_type="downloaded",
        is_success=True,
    )

    url = reverse("documents:audit_trail_export_csv")
    response = client_a.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert "attachment; filename=\"audit_trail_" in response["Content-Disposition"]

    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    assert len(rows) >= 2  # header + at least 1 record
    header = rows[0]
    assert "Entry #" in header
    assert "Action Type" in header
    assert "Chain Hash" in header

    # Verify our entry is present in rows
    matched = any(entry.number in row for row in rows[1:])
    assert matched


def test_audit_reporting_audit_trail_export_csv_formula_injection(client_a, tenant_a, admin_user):
    """Test audit_trail_export_csv mitigates formula injection via _csv_safe escaping."""
    doc_formula = Document.objects.create(
        tenant=tenant_a,
        owner=admin_user,
        title="=cmd|' /C calc'!A0",
        number="+DOC-DANGEROUS",
    )
    _audit_reporting_create_audit_entry(
        tenant_a,
        document=doc_formula,
        actor=admin_user,
        action_type="viewed",
    )

    url = reverse("documents:audit_trail_export_csv")
    response = client_a.get(url)
    assert response.status_code == 200

    content = response.content.decode("utf-8")
    # Formula prefixes (=, +, -, @) must be escaped with single quote
    assert "'=cmd|' /C calc'!A0" in content
    assert "'+DOC-DANGEROUS" in content


def test_audit_reporting_audit_trail_export_csv_filters(client_a, tenant_a, document, admin_user):
    """Test audit_trail_export_csv respects filter parameters."""
    e_dl = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user, action_type="downloaded")
    e_vw = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user, action_type="viewed")

    url = reverse("documents:audit_trail_export_csv")
    response = client_a.get(url, {"action_type": "downloaded"})
    assert response.status_code == 200

    content = response.content.decode("utf-8")
    assert e_dl.number in content
    assert e_vw.number not in content


def test_audit_reporting_audit_trail_verify_chain_get_method_not_allowed(client_a):
    """Test audit_trail_verify_chain rejects GET with 405 Method Not Allowed."""
    url = reverse("documents:audit_trail_verify_chain")
    response = client_a.get(url)
    assert response.status_code == 405


def test_audit_reporting_audit_trail_verify_chain_permission_denied(member_client):
    """Test audit_trail_verify_chain requires tenant administrator permission."""
    url = reverse("documents:audit_trail_verify_chain")
    response = member_client.post(url)
    assert response.status_code == 403


def test_audit_reporting_audit_trail_verify_chain_intact_success(client_a, tenant_a, document, admin_user):
    """Test audit_trail_verify_chain succeeds and redirects when chain is unbroken."""
    _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)
    _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)

    url = reverse("documents:audit_trail_verify_chain")
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("documents:audit_trail_list")


def test_audit_reporting_audit_trail_verify_chain_json_response(client_a, tenant_a, document, admin_user):
    """Test audit_trail_verify_chain returns JSON payload when requested with format=json."""
    _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)

    url = reverse("documents:audit_trail_verify_chain") + "?format=json"
    response = client_a.post(url)

    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["verified_count"] >= 1
    assert data["tampered_id"] is None
    assert len(data["latest_hash"]) == 64


def test_audit_reporting_audit_trail_verify_chain_detects_tamper(client_a, tenant_a, document, admin_user):
    """Test audit_trail_verify_chain detects cryptographic tampering and flags compromised ID."""
    e1 = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)
    e2 = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user)

    # Tamper with e2 chain_hash via queryset update (bypassing save ValidationError)
    DocumentAuditTrail.objects.filter(pk=e2.pk).update(chain_hash="deadbeef" * 8)

    url = reverse("documents:audit_trail_verify_chain") + "?format=json"
    response = client_a.post(url)

    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert data["tampered_id"] == e2.id


# ============================================================================
# 2. AuditReportDefinitions View Tests
# ============================================================================

def test_audit_reporting_audit_report_list_get_success(client_a, tenant_a, admin_user):
    """Test audit_report_list GET returns 200 with required context keys."""
    rep_sys = _audit_reporting_create_report_def(tenant_a, admin_user, name="System Preset Access", is_system_preset=True)
    rep_cust = _audit_reporting_create_report_def(tenant_a, admin_user, name="Custom Audit Q1", is_system_preset=False)

    url = reverse("documents:audit_report_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "system_reports" in response.context
    assert "custom_reports" in response.context
    assert "total_reports" in response.context
    assert "report_type_choices" in response.context
    assert "status_choices" in response.context
    assert rep_sys in response.context["system_reports"]
    assert rep_cust in response.context["custom_reports"]


def test_audit_reporting_audit_report_list_filters(client_a, tenant_a, admin_user):
    """Test audit_report_list search 'q', report_type, and status filters."""
    r1 = _audit_reporting_create_report_def(
        tenant_a, admin_user, name="SOC2 Security Incident Log", report_type="security_exceptions", status="active"
    )
    r2 = _audit_reporting_create_report_def(
        tenant_a, admin_user, name="GDPR Confidential Access", report_type="confidential_access", status="draft"
    )

    url = reverse("documents:audit_report_list")

    # Search q
    res_q = client_a.get(url, {"q": "SOC2"})
    assert res_q.status_code == 200
    assert r1 in res_q.context["custom_reports"]
    assert r2 not in res_q.context["custom_reports"]

    # Filter report_type
    res_type = client_a.get(url, {"report_type": "security_exceptions"})
    assert res_type.status_code == 200
    assert r1 in res_type.context["custom_reports"]
    assert r2 not in res_type.context["custom_reports"]

    # Filter status
    res_st = client_a.get(url, {"status": "draft"})
    assert res_st.status_code == 200
    assert r2 in res_st.context["custom_reports"]
    assert r1 not in res_st.context["custom_reports"]


def test_audit_reporting_audit_report_create_get(client_a):
    """Test audit_report_create GET renders form with is_edit=False."""
    url = reverse("documents:audit_report_create")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["report_def"] is None


def test_audit_reporting_audit_report_create_post_success(client_a, tenant_a):
    """Test audit_report_create valid POST creates report definition and redirects to detail."""
    url = reverse("documents:audit_report_create")
    payload = {
        "name": "Q3 Executive Access Review",
        "description": "Quarterly review of elevated document access",
        "report_type": "confidential_access",
        "date_range_preset": "last_90_days",
        "output_format": "table_view",
        "status": "active",
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    created = AuditReportDefinition.objects.filter(tenant=tenant_a, name="Q3 Executive Access Review").first()
    assert created is not None
    assert created.is_system_preset is False
    assert response.url == reverse("documents:audit_report_detail", kwargs={"pk": created.pk})


def test_audit_reporting_audit_report_create_post_invalid(client_a):
    """Test audit_report_create POST with custom preset without dates returns form error."""
    url = reverse("documents:audit_report_create")
    payload = {
        "name": "Invalid Custom Report",
        "report_type": "confidential_access",
        "date_range_preset": "custom",  # Missing start/end dates
        "output_format": "table_view",
        "status": "active",
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert response.context["form"].errors


def test_audit_reporting_audit_report_detail_get_success(client_a, tenant_a, admin_user, document):
    """Test audit_report_detail runs report, updates metrics and run counter."""
    rep = _audit_reporting_create_report_def(
        tenant_a, admin_user, name="Live Audit Run", report_type="confidential_access", date_range_preset="last_30_days"
    )
    _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user, action_type="viewed")

    url = reverse("documents:audit_report_detail", kwargs={"pk": rep.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "report_def" in response.context
    assert "summary_kpis" in response.context
    assert "report_data" in response.context
    assert "total_events" in response.context
    assert response.context["total_events"] >= 1

    rep.refresh_from_db()
    assert rep.total_runs == 1
    assert rep.last_run_at is not None
    assert rep.last_run_by == admin_user


def test_audit_reporting_audit_report_detail_cross_tenant_404(client_a, tenant_b, admin_b):
    """Test audit_report_detail returns 404 for report owned by another tenant."""
    rep_b = _audit_reporting_create_report_def(tenant_b, admin_b, name="Tenant B Secret Report")
    url = reverse("documents:audit_report_detail", kwargs={"pk": rep_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_audit_reporting_audit_report_edit_get(client_a, tenant_a, admin_user):
    """Test audit_report_edit GET renders edit form with is_edit=True."""
    rep = _audit_reporting_create_report_def(tenant_a, admin_user, name="Editable Report")
    url = reverse("documents:audit_report_edit", kwargs={"pk": rep.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["report_def"] == rep


def test_audit_reporting_audit_report_edit_post_success(client_a, tenant_a, admin_user):
    """Test audit_report_edit valid POST updates custom report definition."""
    rep = _audit_reporting_create_report_def(tenant_a, admin_user, name="Old Report Name")
    url = reverse("documents:audit_report_edit", kwargs={"pk": rep.pk})
    payload = {
        "name": "Updated Report Name",
        "description": "Updated scope and objectives",
        "report_type": "security_exceptions",
        "date_range_preset": "last_30_days",
        "output_format": "csv",
        "status": "archived",
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("documents:audit_report_detail", kwargs={"pk": rep.pk})
    rep.refresh_from_db()
    assert rep.name == "Updated Report Name"
    assert rep.report_type == "security_exceptions"
    assert rep.status == "archived"


def test_audit_reporting_audit_report_edit_system_preset_blocked(client_a, tenant_a, admin_user):
    """Test editing a system preset report definition is rejected with an error redirect."""
    rep_sys = _audit_reporting_create_report_def(tenant_a, admin_user, name="Preset Core Report", is_system_preset=True)
    url = reverse("documents:audit_report_edit", kwargs={"pk": rep_sys.pk})
    response = client_a.get(url)

    assert response.status_code == 302
    assert response.url == reverse("documents:audit_report_detail", kwargs={"pk": rep_sys.pk})


def test_audit_reporting_audit_report_delete_post_success(client_a, tenant_a, admin_user):
    """Test creator or tenant admin can delete custom report definition via POST."""
    rep = _audit_reporting_create_report_def(tenant_a, admin_user, name="Report To Delete")
    url = reverse("documents:audit_report_delete", kwargs={"pk": rep.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("documents:audit_report_list")
    assert not AuditReportDefinition.objects.filter(pk=rep.pk).exists()


def test_audit_reporting_audit_report_delete_system_preset_blocked(client_a, tenant_a, admin_user):
    """Test system preset reports cannot be deleted."""
    rep_sys = _audit_reporting_create_report_def(tenant_a, admin_user, name="Immutable Preset", is_system_preset=True)
    url = reverse("documents:audit_report_delete", kwargs={"pk": rep_sys.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("documents:audit_report_list")
    assert AuditReportDefinition.objects.filter(pk=rep_sys.pk).exists()


def test_audit_reporting_audit_report_delete_permission_denied(member_client, tenant_a, admin_user):
    """Test non-creator non-admin member is forbidden from deleting custom report."""
    rep = _audit_reporting_create_report_def(tenant_a, admin_user, name="Admin Owned Report")
    url = reverse("documents:audit_report_delete", kwargs={"pk": rep.pk})
    response = member_client.post(url)
    assert response.status_code == 403


def test_audit_reporting_audit_report_run_csv_export(client_a, tenant_a, admin_user, document):
    """Test audit_report_run returns downloadable CSV attachment."""
    rep = _audit_reporting_create_report_def(tenant_a, admin_user, report_type="confidential_access")
    entry = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user, action_type="viewed")

    url = reverse("documents:audit_report_run", kwargs={"pk": rep.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert f'filename="report_{rep.number}.csv"' in response["Content-Disposition"]
    content = response.content.decode("utf-8")
    assert entry.number in content


def test_audit_reporting_audit_report_run_json_export(client_a, tenant_a, admin_user, document):
    """Test audit_report_run with format=json returns downloadable JSON attachment."""
    rep = _audit_reporting_create_report_def(tenant_a, admin_user, report_type="confidential_access")
    entry = _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user, action_type="viewed")

    url = reverse("documents:audit_report_run", kwargs={"pk": rep.pk}) + "?format=json"
    response = client_a.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert f'filename="report_{rep.number}.json"' in response["Content-Disposition"]
    data = json.loads(response.content.decode("utf-8"))
    assert isinstance(data, list)
    assert any(item["number"] == entry.number for item in data)


# ============================================================================
# 3. DocumentSecurityAlerts View Tests
# ============================================================================

def test_audit_reporting_security_alert_list_get_success(client_a, tenant_a, member_user):
    """Test security_alert_list GET returns 200 with required context keys."""
    alert = _audit_reporting_create_alert(tenant_a, member_user, severity="high", status="investigating")

    url = reverse("documents:security_alert_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "alerts" in response.context
    assert "page_obj" in response.context
    assert "filter_form" in response.context
    assert "open_count" in response.context
    assert "critical_count" in response.context
    assert "severity_choices" in response.context
    assert "status_choices" in response.context
    assert "alert_type_choices" in response.context
    assert alert in response.context["alerts"]


def test_audit_reporting_security_alert_list_filters(client_a, tenant_a, member_user):
    """Test security_alert_list filters for q, severity, status, and alert_type."""
    a1 = _audit_reporting_create_alert(
        tenant_a, member_user, title="Mass Download Threat", severity="critical", status="new", alert_type="mass_download"
    )
    a2 = _audit_reporting_create_alert(
        tenant_a, member_user, title="After Hours Access Log", severity="low", status="resolved", alert_type="after_hours_access"
    )

    url = reverse("documents:security_alert_list")

    # Filter severity
    res_sev = client_a.get(url, {"severity": "critical"})
    assert res_sev.status_code == 200
    assert a1 in res_sev.context["alerts"]
    assert a2 not in res_sev.context["alerts"]

    # Filter status
    res_st = client_a.get(url, {"status": "resolved"})
    assert res_st.status_code == 200
    assert a2 in res_st.context["alerts"]
    assert a1 not in res_st.context["alerts"]

    # Filter alert_type
    res_type = client_a.get(url, {"alert_type": "mass_download"})
    assert res_type.status_code == 200
    assert a1 in res_type.context["alerts"]
    assert a2 not in res_type.context["alerts"]


def test_audit_reporting_security_alert_list_tenant_isolation(client_a, client_b, tenant_a, tenant_b, member_user, admin_b):
    """Test tenant isolation: tenant_b alerts never appear in tenant_a alert list."""
    a_a = _audit_reporting_create_alert(tenant_a, member_user, title="Tenant A Alert")
    a_b = _audit_reporting_create_alert(tenant_b, admin_b, title="Tenant B Alert")

    url = reverse("documents:security_alert_list")
    res_a = client_a.get(url)
    assert a_a in res_a.context["alerts"]
    assert a_b not in res_a.context["alerts"]


def test_audit_reporting_security_alert_detail_get_success(client_a, tenant_a, member_user, document):
    """Test security_alert_detail GET returns 200 with correlated audit logs and target user stats."""
    alert = _audit_reporting_create_alert(tenant_a, member_user, target_document=document)
    # Correlated activity by target_user
    _audit_reporting_create_audit_entry(tenant_a, document=document, actor=member_user, action_type="downloaded")
    _audit_reporting_create_audit_entry(tenant_a, document=document, actor=member_user, action_type="dlp_violation", is_success=False)

    url = reverse("documents:security_alert_detail", kwargs={"pk": alert.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "alert" in response.context
    assert "triage_form" in response.context
    assert "correlated_audit_logs" in response.context
    assert "target_user_stats" in response.context
    assert response.context["target_user_stats"]["total_events"] >= 2
    assert response.context["target_user_stats"]["download_count"] >= 1
    assert response.context["target_user_stats"]["denied_count"] >= 1


def test_audit_reporting_security_alert_detail_cross_tenant_404(client_a, tenant_b, admin_b):
    """Test security_alert_detail returns 404 for alert belonging to another tenant."""
    alert_b = _audit_reporting_create_alert(tenant_b, admin_b)
    url = reverse("documents:security_alert_detail", kwargs={"pk": alert_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_audit_reporting_security_alert_triage_permission_denied(member_client, tenant_a, member_user):
    """Test non-admin member cannot triage security alert."""
    alert = _audit_reporting_create_alert(tenant_a, member_user)
    url = reverse("documents:security_alert_triage", kwargs={"pk": alert.pk})
    response = member_client.post(url, {"status": "resolved", "severity": "medium", "action_taken": "user_warned"})
    assert response.status_code == 403


def test_audit_reporting_security_alert_triage_resolved_transition(client_a, tenant_a, member_user, admin_user):
    """Test triaging alert to resolved sets resolved_at and resolved_by timestamp snapshot."""
    alert = _audit_reporting_create_alert(tenant_a, member_user, status="investigating")
    url = reverse("documents:security_alert_triage", kwargs={"pk": alert.pk})
    payload = {
        "status": "resolved",
        "severity": "medium",
        "action_taken": "user_warned",
        "triage_notes": "Employee notified of bulk download policy.",
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("documents:security_alert_detail", kwargs={"pk": alert.pk})
    alert.refresh_from_db()
    assert alert.status == "resolved"
    assert alert.resolved_at is not None
    assert alert.resolved_by == admin_user
    assert alert.action_taken == "user_warned"


def test_audit_reporting_security_alert_triage_reopen_clears_resolved(client_a, tenant_a, member_user, admin_user):
    """Test reopening a resolved alert clears resolved_at and resolved_by."""
    alert = _audit_reporting_create_alert(tenant_a, member_user, status="resolved")
    alert.resolved_at = timezone.now()
    alert.resolved_by = admin_user
    alert.save()

    url = reverse("documents:security_alert_triage", kwargs={"pk": alert.pk})
    payload = {
        "status": "investigating",
        "severity": "high",
        "action_taken": "downloads_blocked",
        "triage_notes": "Reopening investigation due to new forensic evidence.",
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    alert.refresh_from_db()
    assert alert.status == "investigating"
    assert alert.resolved_at is None
    assert alert.resolved_by is None


def test_audit_reporting_security_alert_scan_permission_denied(member_client):
    """Test security_alert_scan requires tenant administrator permission."""
    url = reverse("documents:security_alert_scan")
    response = member_client.post(url)
    assert response.status_code == 403


def test_audit_reporting_security_alert_scan_success(client_a):
    """Test security_alert_scan triggers heuristic scan and redirects to list."""
    url = reverse("documents:security_alert_scan")
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("documents:security_alert_list")


# ============================================================================
# 4. ChainOfCustodyExports View Tests
# ============================================================================

def test_audit_reporting_custody_export_list_get_success(client_a, tenant_a, admin_user, document):
    """Test custody_export_list GET returns 200 with required context keys."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document)

    url = reverse("documents:custody_export_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "exports" in response.context
    assert "page_obj" in response.context
    assert "active_passes_count" in response.context
    assert "framework_choices" in response.context
    assert response.context["active_passes_count"] >= 1
    assert pkg in response.context["exports"]


def test_audit_reporting_custody_export_list_filters(client_a, tenant_a, admin_user, document):
    """Test custody_export_list filters for q and regulatory framework."""
    p1 = _audit_reporting_create_custody_pkg(
        tenant_a, admin_user, document, title="FDA Compliance Pack", regulatory_framework="fda_21cfr11"
    )
    p2 = _audit_reporting_create_custody_pkg(
        tenant_a, admin_user, document, title="SOC 2 Evidence Vault", regulatory_framework="soc2_type2"
    )

    url = reverse("documents:custody_export_list")

    # Search q
    res_q = client_a.get(url, {"q": "Evidence Vault"})
    assert res_q.status_code == 200
    assert p2 in res_q.context["exports"]
    assert p1 not in res_q.context["exports"]

    # Filter framework
    res_fw = client_a.get(url, {"framework": "fda_21cfr11"})
    assert res_fw.status_code == 200
    assert p1 in res_fw.context["exports"]
    assert p2 not in res_fw.context["exports"]


def test_audit_reporting_custody_export_create_get(client_a):
    """Test custody_export_create GET returns form."""
    url = reverse("documents:custody_export_create")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context


def test_audit_reporting_custody_export_create_post_success(client_a, tenant_a, document):
    """Test custody_export_create valid POST creates sealed package and redirects to detail."""
    url = reverse("documents:custody_export_create")
    payload = {
        "title": "ISO 27001 Auditor Review Pack",
        "regulatory_framework": "iso_27001",
        "scope": "single_document",
        "document": str(document.pk),
        "auditor_name": "Marcus Vance",
        "auditor_email": "m.vance@auditfirm.com",
        "auditor_organization": "Ernst & Young LLP",
        "portal_passcode": "SecretPass2026!",
        "expires_at": (timezone.now() + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M"),
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    pkg = ChainOfCustodyExport.objects.filter(tenant=tenant_a, title="ISO 27001 Auditor Review Pack").first()
    assert pkg is not None
    assert pkg.package_hash is not None
    assert pkg.check_passcode("SecretPass2026!") is True
    assert response.url == reverse("documents:custody_export_detail", kwargs={"pk": pkg.pk})


def test_audit_reporting_custody_export_create_post_invalid(client_a):
    """Test custody_export_create POST with scope=single_document but no document fails validation."""
    url = reverse("documents:custody_export_create")
    payload = {
        "title": "Broken Package",
        "regulatory_framework": "soc2_type2",
        "scope": "single_document",
        # missing document
        "auditor_name": "Auditor Name",
        "auditor_email": "auditor@agency.gov",
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "document" in response.context["form"].errors


def test_audit_reporting_custody_export_detail_get_success(client_a, tenant_a, admin_user, document):
    """Test custody_export_detail GET returns 200 with manifest data and verified package hash."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document)
    url = reverse("documents:custody_export_detail", kwargs={"pk": pkg.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "export_pkg" in response.context
    assert "portal_url" in response.context
    assert "manifest_data" in response.context
    assert "is_hash_valid" in response.context
    assert response.context["is_hash_valid"] is True


def test_audit_reporting_custody_export_detail_cross_tenant_404(client_a, tenant_b, admin_b):
    """Test custody_export_detail returns 404 for evidence package of another tenant."""
    doc_b = Document.objects.create(tenant=tenant_b, owner=admin_b, title="Globex Secret", number="DOC-GLO-1")
    pkg_b = _audit_reporting_create_custody_pkg(tenant_b, admin_b, doc_b)

    url = reverse("documents:custody_export_detail", kwargs={"pk": pkg_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_audit_reporting_custody_export_certificate_get_success(client_a, tenant_a, admin_user, document):
    """Test custody_export_certificate GET renders printable official Certificate of Authenticity."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document)
    url = reverse("documents:custody_export_certificate", kwargs={"pk": pkg.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "export_pkg" in response.context
    assert "manifest_data" in response.context
    assert "tenant" in response.context


def test_audit_reporting_custody_export_revoke_permission_denied(member_client, tenant_a, admin_user, document):
    """Test non-admin member cannot revoke auditor custody pass."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document)
    url = reverse("documents:custody_export_revoke", kwargs={"pk": pkg.pk})
    response = member_client.post(url)
    assert response.status_code == 403


def test_audit_reporting_custody_export_revoke_success(client_a, tenant_a, admin_user, document):
    """Test tenant administrator can revoke active auditor pass via POST."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, is_portal_active=True)
    url = reverse("documents:custody_export_revoke", kwargs={"pk": pkg.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("documents:custody_export_detail", kwargs={"pk": pkg.pk})
    pkg.refresh_from_db()
    assert pkg.is_portal_active is False
    assert pkg.revoked_at is not None
    assert pkg.revoked_by == admin_user


def test_audit_reporting_auditor_portal_view_invalid_token(client):
    """Test auditor_portal_view returns 404 for non-existent token."""
    url = reverse("documents:auditor_portal_view", kwargs={"token": "non_existent_token_123456789"})
    response = client.get(url)
    assert response.status_code == 404


def test_audit_reporting_auditor_portal_view_revoked_403(client, tenant_a, admin_user, document):
    """Test auditor_portal_view returns 403 Forbidden when package is revoked."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, is_portal_active=False)
    url = reverse("documents:auditor_portal_view", kwargs={"token": pkg.access_token})
    response = client.get(url)

    assert response.status_code == 403
    assert "Access Revoked" in response.content.decode("utf-8")


def test_audit_reporting_auditor_portal_view_expired_410(client, tenant_a, admin_user, document):
    """Test auditor_portal_view returns 410 Gone when package has expired."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, expires_in_days=-2)
    url = reverse("documents:auditor_portal_view", kwargs={"token": pkg.access_token})
    response = client.get(url)

    assert response.status_code == 410
    assert "Pass Expired" in response.content.decode("utf-8")


def test_audit_reporting_auditor_portal_view_passcode_gate(client, tenant_a, admin_user, document):
    """Test auditor_portal_view renders passcode gate when passcode protection is set."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, passcode="AuditPass2026!")
    url = reverse("documents:auditor_portal_view", kwargs={"token": pkg.access_token})
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["passcode_required"] is True
    assert "passcode_form" in response.context


def test_audit_reporting_auditor_portal_verify_invalid_passcode(client, tenant_a, admin_user, document):
    """Test auditor_portal_verify logs failure and rejects invalid passcode."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, passcode="SecretPass123!")
    url = reverse("documents:auditor_portal_verify", kwargs={"token": pkg.access_token})
    response = client.post(url, {"passcode": "WrongPassword"})

    assert response.status_code == 302
    assert response.url == reverse("documents:auditor_portal_view", kwargs={"token": pkg.access_token})

    # Verify audit trail logs failed access attempt
    failed_log = DocumentAuditTrail.objects.filter(
        tenant=tenant_a,
        action_type="auditor_portal_accessed",
        is_success=False,
    ).first()
    assert failed_log is not None
    assert "Invalid passcode attempt" in failed_log.failure_reason


def test_audit_reporting_auditor_portal_verify_correct_passcode_unlocks(client, tenant_a, admin_user, document):
    """Test auditor_portal_verify with correct passcode authenticates session and unlocks portal."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, passcode="CorrectPass777!")
    verify_url = reverse("documents:auditor_portal_verify", kwargs={"token": pkg.access_token})
    response = client.post(verify_url, {"passcode": "CorrectPass777!"})

    assert response.status_code == 302
    assert response.url == reverse("documents:auditor_portal_view", kwargs={"token": pkg.access_token})

    # Subsequent view visit is unlocked
    portal_url = reverse("documents:auditor_portal_view", kwargs={"token": pkg.access_token})
    portal_res = client.get(portal_url)

    assert portal_res.status_code == 200
    assert portal_res.context["passcode_required"] is False
    assert "document" in portal_res.context
    assert "versions" in portal_res.context
    assert "audit_trail" in portal_res.context


def test_audit_reporting_auditor_portal_verify_lockout_after_5_failures(client, tenant_a, admin_user, document):
    """Test auditor_portal_verify locks out after 5 consecutive failed passcode submissions."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, passcode="Pass12345!")
    verify_url = reverse("documents:auditor_portal_verify", kwargs={"token": pkg.access_token})

    for _ in range(5):
        client.post(verify_url, {"passcode": "WrongPassword"})

    # 6th attempt is blocked
    res_6 = client.post(verify_url, {"passcode": "Pass12345!"})
    assert res_6.status_code == 302
    # Verify session auth not granted
    session = client.session
    assert not session.get(f"auditor_auth_{pkg.access_token}", False)


def test_audit_reporting_auditor_portal_view_no_passcode_direct_access(client, tenant_a, admin_user, document):
    """Test auditor_portal_view without passcode grants direct access and logs audit trail."""
    pkg = _audit_reporting_create_custody_pkg(tenant_a, admin_user, document, passcode="")
    url = reverse("documents:auditor_portal_view", kwargs={"token": pkg.access_token})
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["passcode_required"] is False
    assert response.context["document"] == document

    pkg.refresh_from_db()
    assert pkg.access_count == 1
    assert pkg.last_accessed_at is not None


# ============================================================================
# 5. AuditReportingDashboard View Tests
# ============================================================================

def test_audit_reporting_dashboard_get_success(client_a, tenant_a, admin_user, document):
    """Test audit_dashboard command center returns 200 with stats, alerts, and custody passes."""
    _audit_reporting_create_audit_entry(tenant_a, document=document, actor=admin_user, action_type="downloaded")
    _audit_reporting_create_alert(tenant_a, admin_user, status="new")
    _audit_reporting_create_custody_pkg(tenant_a, admin_user, document)

    url = reverse("documents:audit_dashboard")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "stats" in response.context
    assert "recent_audit_logs" in response.context
    assert "recent_alerts" in response.context
    assert "active_custody_passes" in response.context

    stats = response.context["stats"]
    assert stats["total_events_24h"] >= 1
    assert stats["downloads_24h"] >= 1
    assert stats["security_threats"] >= 1
    assert stats["chain_status"] == "intact"


def test_audit_reporting_dashboard_tenant_isolation(client_a, client_b, tenant_a, tenant_b, admin_user, admin_b):
    """Test audit_dashboard KPIs isolate tenant data completely."""
    _audit_reporting_create_audit_entry(tenant_a, actor=admin_user, action_type="downloaded")
    _audit_reporting_create_audit_entry(tenant_b, actor=admin_b, action_type="downloaded")

    url = reverse("documents:audit_dashboard")
    res_a = client_a.get(url)
    res_b = client_b.get(url)

    assert res_a.context["stats"]["downloads_24h"] == 1
    assert res_b.context["stats"]["downloads_24h"] == 1


def test_audit_reporting_document_lifecycle_dashboard_get_success(client_a, tenant_a, admin_user, document):
    """Test document_lifecycle_dashboard returns 200 with lifecycle KPIs and status distribution."""
    # Create multiple versions on document for churn analysis
    DocumentVersion.objects.create(
        tenant=tenant_a,
        document=document,
        version_label="1.1.0",
        major_number=1,
        minor_number=1,
        patch_number=0,
        author=admin_user,
        file_hash="1111111111111111111111111111111111111111111111111111111111111111",
    )
    DocumentVersion.objects.create(
        tenant=tenant_a,
        document=document,
        version_label="1.2.0",
        major_number=1,
        minor_number=2,
        patch_number=0,
        author=admin_user,
        file_hash="2222222222222222222222222222222222222222222222222222222222222222",
    )

    url = reverse("documents:document_lifecycle_dashboard")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "lifecycle_kpis" in response.context
    kpis = response.context["lifecycle_kpis"]
    assert "status_distribution" in kpis
    assert "high_churn_docs" in kpis
    assert "bottleneck_stages" in kpis
    assert "avg_approval_hours" in kpis
    assert "total_managed_docs" in kpis
    assert kpis["total_managed_docs"] >= 1
