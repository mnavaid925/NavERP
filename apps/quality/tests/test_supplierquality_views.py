"""
View tests for Sub-module 12.6: Supplier & Vendor Quality Management.

Covers all views, routes, filters, search, pagination, context contracts,
form submissions (valid & invalid), status progressions, export, admin gates,
and cross-tenant isolation:
1. avl_directory (AVL Directory & Governance metrics)
2. SupplierQualificationAudit (list, detail, create, edit, delete, export, status)
3. SupplierQualityScorecard (list, detail, create, edit, delete, export, publish)
4. SupplierCorrectiveAction (list, detail, create, edit, delete, export, advance, close)
5. SupplierChangeNotification (list, detail, create, edit, delete, export, disposition)
6. Cross-tenant isolation & unauthenticated redirection
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party, PartyRole
from apps.quality.models import (
    SupplierChangeNotification,
    SupplierCorrectiveAction,
    SupplierQualificationAudit,
    SupplierQualityScorecard,
)

pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _supplierquality_*)
# =============================================================================

def _supplierquality_pk(val):
    """Return pk if val is a model instance, or val itself."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _supplierquality_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _supplierquality_audit_data(supplier, auditor=None, doc=None, **extra):
    """Build valid baseline POST dictionary for SupplierQualificationAuditForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "assessment_type": "initial_qualification",
        "criticality_tier": "critical",
        "audit_method": "on_site",
        "qualification_status": "approved",
        "scope_commodities": "Medical catheters, surgical tubing",
        "score": "95.00",
        "audit_result": "passed",
        "critical_findings": 0,
        "major_findings": 1,
        "minor_findings": 2,
        "lead_auditor": _supplierquality_pk(auditor) if auditor else "",
        "audit_date": _supplierquality_date(-10),
        "qualified_date": _supplierquality_date(-5),
        "next_audit_due_date": _supplierquality_date(355),
        "certificate_expiry_date": _supplierquality_date(720),
        "dock_to_stock_eligible": True,
        "skip_lot_approved": False,
        "requires_coa": True,
        "quality_agreement": _supplierquality_pk(doc) if doc else "",
        "notes": "Facility complies with ISO 13485 cleanroom standards.",
    }
    data.update(extra)
    return data


def _supplierquality_scorecard_data(supplier, evaluator=None, **extra):
    """Build valid baseline POST dictionary for SupplierQualityScorecardForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "cadence": "quarterly",
        "period_start": _supplierquality_date(-90),
        "period_end": _supplierquality_date(0),
        "status": "draft",
        "lot_acceptance_rate_score": "95.00",
        "defect_ppm_score": "92.00",
        "scar_responsiveness_score": "90.00",
        "audit_compliance_score": "88.00",
        "documentation_coa_score": "96.00",
        "total_lots_received": 100,
        "lots_rejected": 2,
        "total_scars_issued": 1,
        "evaluated_by": _supplierquality_pk(evaluator) if evaluator else "",
        "is_manual_override": False,
        "override_justification": "",
        "evaluation_notes": "Consistent delivery quality and fast response times.",
    }
    data.update(extra)
    return data


def _supplierquality_scar_data(supplier, issued_by=None, audit=None, **extra):
    """Build valid baseline POST dictionary for SupplierCorrectiveActionForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "title": "Cannula Hub Mold Flash Defect",
        "severity": "major",
        "status": "draft",
        "defect_summary": "Flash observed around connector hub exceeding 0.1mm tolerance.",
        "affected_item_code": "HUB-CAN-002",
        "affected_item_name": "Luer-Lock Cannula Hub",
        "affected_lots": "LOT-2026-B81",
        "purchase_order": "",
        "non_conformance": "",
        "qualification_audit": _supplierquality_pk(audit) if audit else "",
        "internal_capa": "",
        "issued_date": _supplierquality_date(-2),
        "response_due_date": _supplierquality_date(12),
        "issued_by": _supplierquality_pk(issued_by) if issued_by else "",
        "containment_action": "Quarantine affected batch B81 in inspection cage.",
        "containment_due_date": _supplierquality_date(2),
        "containment_verified_at": "",
        "root_cause_summary": "Worn parting line shutoff on mold cavity #4.",
        "root_cause_category": "tooling_equipment",
        "vendor_investigation_details": "Tooling dismantled and cavity #4 insert found deformed.",
        "corrective_action_plan": "Replace cavity insert and re-measure first article samples.",
        "preventive_action_plan": "Implement preventive cavity maintenance at 25k cycles.",
        "implementation_due_date": _supplierquality_date(30),
        "implemented_at": "",
        "effectiveness_due_date": _supplierquality_date(60),
        "effectiveness_method": "Inspect next 3 consecutive shipments for zero flash.",
        "effectiveness_results": "",
        "is_effective": "",
        "verified_by": "",
    }
    data.update(extra)
    return data


def _supplierquality_scn_data(supplier, evaluator=None, audit=None, **extra):
    """Build valid baseline POST dictionary for SupplierChangeNotificationForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "title": "Polymer Resin Supplier Relocation",
        "supplier_scn_number": "PCN-2026-901",
        "change_category": "facility_location",
        "risk_level": "level_2_moderate",
        "status": "received",
        "description": "Supplier resin synthesis moving from Plant 1 to Plant 2.",
        "proposed_effective_date": _supplierquality_date(45),
        "first_affected_lot": "LOT-RES-701",
        "affected_item_code": "RES-PEEK-01",
        "affected_item_name": "Medical Grade PEEK Granules",
        "affects_form_fit_function": False,
        "requires_requalification": False,
        "requires_design_change": False,
        "requires_regulatory_filing": False,
        "requires_customer_notification": False,
        "samples_required": True,
        "impact_assessment_notes": "No formulation changes. Equivalency validation testing underway.",
        "design_project": "",
        "requalification_audit": _supplierquality_pk(audit) if audit else "",
        "evaluated_by": _supplierquality_pk(evaluator) if evaluator else "",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. AVL Directory Views
# =============================================================================

def test_supplierquality_avl_directory_get(client, admin_user, audit_a):
    """Verify AVL directory GET returns 200 with required context metrics and table."""
    client.force_login(admin_user)
    url = reverse("quality:avl_directory")
    resp = client.get(url)
    assert resp.status_code == 200

    # Context assertions
    expected_keys = [
        "qualifications",
        "active_count",
        "critical_count",
        "dock_to_stock_count",
        "pending_audits_count",
        "status_choices",
        "tier_choices",
        "search_query",
        "current_status",
        "current_tier",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Key '{key}' missing from avl_directory context"

    assert resp.context["active_count"] >= 1
    assert resp.context["critical_count"] >= 1
    assert resp.context["dock_to_stock_count"] >= 1
    assert audit_a.number in resp.content.decode()


def test_supplierquality_avl_directory_filters(client, admin_user, audit_a):
    """Verify AVL directory filters by search, qualification status, and tier."""
    client.force_login(admin_user)
    url = reverse("quality:avl_directory")

    # Filter matching
    resp_match = client.get(url, {"q": audit_a.number, "status": "approved", "tier": "critical"})
    assert resp_match.status_code == 200
    assert audit_a in resp_match.context["qualifications"]

    # Filter mismatch
    resp_nomatch = client.get(url, {"status": "disqualified"})
    assert resp_nomatch.status_code == 200
    assert audit_a not in resp_nomatch.context["qualifications"]


def test_supplierquality_avl_directory_pagination_and_junk(client, admin_user, tenant_a, supplier_party_a, audit_a):
    """Verify AVL directory handles pagination and gracefully absorbs junk parameters."""
    client.force_login(admin_user)
    url = reverse("quality:avl_directory")

    # Junk parameter handling
    resp_junk = client.get(url, {"status": "bogus_status", "tier": "xyz", "page": "invalid_page"})
    assert resp_junk.status_code == 200
    assert resp_junk.context["qualifications"].number == 1


# =============================================================================
# 2. SupplierQualificationAudit Views
# =============================================================================

def test_supplierquality_audit_list_get_and_context(client, admin_user, audit_a):
    """Verify audit list GET returns 200 with all context keys and records."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "audits",
        "status_choices",
        "tier_choices",
        "result_choices",
        "suppliers",
        "search_query",
        "current_status",
        "current_tier",
        "current_result",
        "current_supplier",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from audit list context"

    assert audit_a.number in resp.content.decode()


def test_supplierquality_audit_list_filters(client, admin_user, audit_a, supplier_party_a):
    """Verify audit list filters by query, status, tier, audit_type, result, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_list")

    resp = client.get(url, {
        "q": audit_a.number,
        "status": "approved",
        "tier": "critical",
        "result": "passed",
        "audit_type": "initial_qualification",
        "supplier": str(supplier_party_a.pk),
    })
    assert resp.status_code == 200
    assert audit_a in resp.context["audits"]

    # Junk parameter test
    resp_junk = client.get(url, {"page": "invalid", "supplier": "non_numeric"})
    assert resp_junk.status_code == 200


def test_supplierquality_audit_detail_view(client, admin_user, audit_a, scar_a, scn_a):
    """Verify audit detail GET returns 200 with audit, triggered SCARs, and related SCNs."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["audit"] == audit_a
    assert "scars" in resp.context
    assert "scns" in resp.context
    assert scar_a in resp.context["scars"]
    assert scn_a in resp.context["scns"]
    assert audit_a.number in resp.content.decode()
    assert audit_a.supplier.name in resp.content.decode()


def test_supplierquality_audit_create_get(client, admin_user):
    """Verify audit create GET renders form with is_edit=False and audit=None."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["audit"] is None


def test_supplierquality_audit_create_post_valid(client, admin_user, tenant_a, supplier_party_a, doc_a):
    """Verify valid POST to audit create redirects to detail and records AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_create")
    post_data = _supplierquality_audit_data(
        supplier=supplier_party_a,
        auditor=admin_user,
        doc=doc_a,
        scope_commodities="Precision machined cannula fittings",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_audit = SupplierQualificationAudit.objects.filter(
        tenant=tenant_a, scope_commodities="Precision machined cannula fittings"
    ).first()
    assert created_audit is not None
    assert resp.url == reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": created_audit.pk})

    # Verify AuditLog written
    content_type = ContentType.objects.get_for_model(SupplierQualificationAudit)
    log_entry = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=content_type,
        object_id=created_audit.pk,
        action="create",
    ).first()
    assert log_entry is not None
    assert log_entry.user == admin_user


def test_supplierquality_audit_create_post_invalid(client, admin_user, supplier_party_a):
    """Verify invalid POST to audit create redisplays form with errors."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_create")
    # Score out of bounds (> 100)
    post_data = _supplierquality_audit_data(
        supplier=supplier_party_a,
        score="150.00",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "score" in resp.context["form"].errors


def test_supplierquality_audit_edit_get_and_post(client, admin_user, audit_a):
    """Verify audit edit GET and valid POST update record and redirect to detail."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["audit"] == audit_a

    post_data = _supplierquality_audit_data(
        supplier=audit_a.supplier,
        auditor=audit_a.lead_auditor,
        scope_commodities="Updated scope for surgical cannulas",
        score="98.50",
    )
    resp_post = client.post(url, post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit_a.pk})

    audit_a.refresh_from_db()
    assert audit_a.scope_commodities == "Updated scope for surgical cannulas"
    assert audit_a.score == Decimal("98.50")


def test_supplierquality_audit_delete_post_and_admin_gate(client, admin_user, member_user, tenant_a, supplier_party_a):
    """Verify audit delete requires POST and admin privileges, deleting record on success."""
    audit_to_delete = SupplierQualificationAudit.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        assessment_type="desktop_assessment",
        criticality_tier="minor",
        audit_method="desktop_survey",
        qualification_status="draft",
        audit_result="pending",
        scope_commodities="Disposable swabs",
    )
    url = reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_to_delete.pk})

    # Require POST
    client.force_login(admin_user)
    resp_get = client.get(url)
    assert resp_get.status_code == 405

    # Member user blocked (403)
    client.force_login(member_user)
    resp_perm = client.post(url)
    assert resp_perm.status_code == 403

    # Admin user succeeds
    client.force_login(admin_user)
    resp_post = client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:supplier_qualification_audit_list")
    assert not SupplierQualificationAudit.objects.filter(pk=audit_to_delete.pk).exists()


def test_supplierquality_audit_export_csv(client, admin_user, audit_a):
    """Verify audit CSV export returns attachment text/csv with headers and rows."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_qualification_audit_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment; filename=\"supplier_qualification_audits.csv\"" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "Audit Number" in header
    assert "Supplier" in header
    assert "Score" in header

    rows = list(reader)
    assert any(audit_a.number in row[0] for row in rows)


def test_supplierquality_audit_status_post_and_admin_gate(client, admin_user, member_user, audit_a):
    """Verify audit status transition endpoint requires POST and admin privileges."""
    url = reverse("quality:supplier_qualification_audit_status", kwargs={"pk": audit_a.pk})

    # GET rejected with 405
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Member user blocked (403)
    client.force_login(member_user)
    assert client.post(url, {"status": "conditional"}).status_code == 403

    # Admin user valid status transition
    client.force_login(admin_user)
    resp_valid = client.post(url, {"status": "conditional"})
    assert resp_valid.status_code == 302
    audit_a.refresh_from_db()
    assert audit_a.qualification_status == "conditional"

    # Admin user invalid status
    resp_invalid = client.post(url, {"status": "invalid_status"})
    assert resp_invalid.status_code == 302
    audit_a.refresh_from_db()
    assert audit_a.qualification_status == "conditional"


# =============================================================================
# 3. SupplierQualityScorecard Views
# =============================================================================

def test_supplierquality_scorecard_list_get_and_context(client, admin_user, scorecard_a):
    """Verify scorecard list GET returns 200 with context dropdown choices and scorecards."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "scorecards",
        "cadence_choices",
        "grade_choices",
        "status_choices",
        "suppliers",
        "search_query",
        "current_status",
        "current_grade",
        "current_cadence",
        "current_supplier",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from scorecard list context"

    assert scorecard_a.number in resp.content.decode()


def test_supplierquality_scorecard_list_filters(client, admin_user, scorecard_a, supplier_party_a):
    """Verify scorecard list filters by query, status, grade, cadence, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_list")

    resp = client.get(url, {
        "q": scorecard_a.number,
        "status": "published",
        "grade": scorecard_a.grade,
        "cadence": "quarterly",
        "supplier": str(supplier_party_a.pk),
    })
    assert resp.status_code == 200
    assert scorecard_a in resp.context["scorecards"]

    # Junk parameter handling
    resp_junk = client.get(url, {"page": "invalid", "grade": "invalid_grade"})
    assert resp_junk.status_code == 200


def test_supplierquality_scorecard_detail_view(client, admin_user, scorecard_a):
    """Verify scorecard detail GET returns 200 with scorecard context and metrics."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["scorecard"] == scorecard_a
    assert scorecard_a.number in resp.content.decode()


def test_supplierquality_scorecard_create_get(client, admin_user):
    """Verify scorecard create GET renders form with is_edit=False."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["scorecard"] is None


def test_supplierquality_scorecard_create_post_valid_and_score_calc(client, admin_user, tenant_a, supplier_party_a):
    """Verify valid POST to scorecard create computes composite score and saves record."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_create")
    post_data = _supplierquality_scorecard_data(
        supplier=supplier_party_a,
        evaluator=admin_user,
        evaluation_notes="Q4 Performance Review - automated composite score calculation test",
        lot_acceptance_rate_score="100.00",  # 30% = 30.00
        defect_ppm_score="100.00",          # 25% = 25.00
        scar_responsiveness_score="100.00", # 20% = 20.00
        audit_compliance_score="100.00",    # 15% = 15.00
        documentation_coa_score="100.00",   # 10% = 10.00
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_scorecard = SupplierQualityScorecard.objects.filter(
        tenant=tenant_a,
        evaluation_notes="Q4 Performance Review - automated composite score calculation test",
    ).first()
    assert created_scorecard is not None
    assert resp.url == reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": created_scorecard.pk})

    # Composite score computation check (100 -> Grade A)
    assert created_scorecard.overall_score == Decimal("100.00")
    assert created_scorecard.grade == "grade_a"


def test_supplierquality_scorecard_create_post_invalid(client, admin_user, supplier_party_a):
    """Verify invalid POST (status=published directly from create) is blocked."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_create")
    post_data = _supplierquality_scorecard_data(
        supplier=supplier_party_a,
        status="published",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "status" in resp.context["form"].errors


def test_supplierquality_scorecard_edit_get_and_post(client, admin_user, scorecard_a):
    """Verify scorecard edit GET and valid POST update record."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": scorecard_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["scorecard"] == scorecard_a

    post_data = _supplierquality_scorecard_data(
        supplier=scorecard_a.supplier,
        evaluator=scorecard_a.evaluated_by,
        evaluation_notes="Updated notes on supplier reliability.",
        lot_acceptance_rate_score="90.00",
    )
    resp_post = client.post(url, post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_a.pk})

    scorecard_a.refresh_from_db()
    assert scorecard_a.evaluation_notes == "Updated notes on supplier reliability."


def test_supplierquality_scorecard_delete_post_and_admin_gate(client, admin_user, member_user, tenant_a, supplier_party_a):
    """Verify scorecard delete requires POST and admin privileges."""
    scorecard_to_delete = SupplierQualityScorecard.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="monthly",
        period_start=timezone.now().date() - timedelta(days=30),
        period_end=timezone.now().date(),
        status="draft",
        lot_acceptance_rate_score=Decimal("80.00"),
        defect_ppm_score=Decimal("80.00"),
        scar_responsiveness_score=Decimal("80.00"),
        audit_compliance_score=Decimal("80.00"),
        documentation_coa_score=Decimal("80.00"),
    )
    url = reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": scorecard_to_delete.pk})

    # Require POST
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin blocked
    client.force_login(member_user)
    assert client.post(url).status_code == 403

    # Admin delete
    client.force_login(admin_user)
    resp_del = client.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("quality:supplier_quality_scorecard_list")
    assert not SupplierQualityScorecard.objects.filter(pk=scorecard_to_delete.pk).exists()


def test_supplierquality_scorecard_export_csv(client, admin_user, scorecard_a):
    """Verify scorecard CSV export returns text/csv with formatted rows."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_quality_scorecard_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment; filename=\"supplier_quality_scorecards.csv\"" in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "Scorecard #" in header
    assert "Overall Score" in header
    rows = list(reader)
    assert any(scorecard_a.number in row[0] for row in rows)


def test_supplierquality_scorecard_publish_post_and_admin_gate(client, admin_user, member_user, tenant_a, supplier_party_a):
    """Verify scorecard publish transitions draft to published under admin gate."""
    scorecard_draft = SupplierQualityScorecard.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="quarterly",
        period_start=timezone.now().date() - timedelta(days=90),
        period_end=timezone.now().date(),
        status="under_review",
        lot_acceptance_rate_score=Decimal("88.00"),
        defect_ppm_score=Decimal("85.00"),
        scar_responsiveness_score=Decimal("80.00"),
        audit_compliance_score=Decimal("85.00"),
        documentation_coa_score=Decimal("90.00"),
    )
    url = reverse("quality:supplier_quality_scorecard_publish", kwargs={"pk": scorecard_draft.pk})

    # Require POST
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Member user blocked (403)
    client.force_login(member_user)
    assert client.post(url).status_code == 403

    # Admin publishes
    client.force_login(admin_user)
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_draft.pk})

    scorecard_draft.refresh_from_db()
    assert scorecard_draft.status == "published"

    # Already published scorecard
    resp_again = client.post(url)
    assert resp_again.status_code == 302


# =============================================================================
# 4. SupplierCorrectiveAction Views
# =============================================================================

def test_supplierquality_scar_list_get_and_context(client, admin_user, scar_a):
    """Verify SCAR list GET returns 200 with filter choices and records."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "scars",
        "severity_choices",
        "status_choices",
        "category_choices",
        "suppliers",
        "search_query",
        "current_status",
        "current_severity",
        "current_category",
        "current_supplier",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from SCAR list context"

    assert scar_a.number in resp.content.decode()


def test_supplierquality_scar_list_filters(client, admin_user, scar_a, supplier_party_a):
    """Verify SCAR list filters by query, status, severity, category, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_list")

    resp = client.get(url, {
        "q": scar_a.number,
        "status": scar_a.status,
        "severity": scar_a.severity,
        "supplier": str(supplier_party_a.pk),
    })
    assert resp.status_code == 200
    assert scar_a in resp.context["scars"]

    # Junk parameter handling
    resp_junk = client.get(url, {"page": "invalid", "status": "bogus_status"})
    assert resp_junk.status_code == 200


def test_supplierquality_scar_detail_view(client, admin_user, scar_a):
    """Verify SCAR detail GET returns 200 with scar context."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["scar"] == scar_a
    assert scar_a.number in resp.content.decode()


def test_supplierquality_scar_create_get(client, admin_user):
    """Verify SCAR create GET renders form with is_edit=False."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["scar"] is None


def test_supplierquality_scar_create_post_valid(client, admin_user, tenant_a, supplier_party_a, audit_a):
    """Verify valid POST to SCAR create creates record and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_create")
    post_data = _supplierquality_scar_data(
        supplier=supplier_party_a,
        issued_by=admin_user,
        audit=audit_a,
        title="Excessive Particulate In Delivery Bags",
        defect_summary="Foreign particulate counts violate cleanroom packaging spec.",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_scar = SupplierCorrectiveAction.objects.filter(
        tenant=tenant_a, title="Excessive Particulate In Delivery Bags"
    ).first()
    assert created_scar is not None
    assert resp.url == reverse("quality:supplier_corrective_action_detail", kwargs={"pk": created_scar.pk})


def test_supplierquality_scar_create_post_invalid(client, admin_user, supplier_party_a):
    """Verify invalid POST (status=closed directly from form) is rejected."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_create")
    post_data = _supplierquality_scar_data(
        supplier=supplier_party_a,
        status="closed",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "status" in resp.context["form"].errors


def test_supplierquality_scar_edit_get_and_post(client, admin_user, scar_a):
    """Verify SCAR edit GET and valid POST update record."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["scar"] == scar_a

    post_data = _supplierquality_scar_data(
        supplier=scar_a.supplier,
        issued_by=scar_a.issued_by,
        audit=scar_a.qualification_audit,
        title="Updated Defect Investigation Title",
        defect_summary=scar_a.defect_summary,
    )
    resp_post = client.post(url, post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_a.pk})

    scar_a.refresh_from_db()
    assert scar_a.title == "Updated Defect Investigation Title"


def test_supplierquality_scar_delete_post_and_admin_gate(client, admin_user, member_user, tenant_a, supplier_party_a):
    """Verify SCAR delete requires POST and admin privileges."""
    scar_to_delete = SupplierCorrectiveAction.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title="Draft SCAR for Cancellation",
        defect_summary="Scratch on raw casing",
        severity="minor",
        status="draft",
        issued_date=timezone.now().date(),
    )
    url = reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_to_delete.pk})

    # Require POST
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin blocked
    client.force_login(member_user)
    assert client.post(url).status_code == 403

    # Admin delete
    client.force_login(admin_user)
    resp_del = client.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("quality:supplier_corrective_action_list")
    assert not SupplierCorrectiveAction.objects.filter(pk=scar_to_delete.pk).exists()


def test_supplierquality_scar_export_csv(client, admin_user, scar_a):
    """Verify SCAR CSV export returns text/csv with formatted rows."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment; filename=\"supplier_corrective_actions.csv\"" in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "SCAR #" in header
    assert "Severity" in header
    rows = list(reader)
    assert any(scar_a.number in row[0] for row in rows)


def test_supplierquality_scar_advance_status(client, admin_user, scar_a):
    """Verify SCAR status advance endpoint transitions workflow status."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar_a.pk})

    resp = client.post(url, {"status": "rca_submitted"})
    assert resp.status_code == 302
    assert resp.url == reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_a.pk})

    scar_a.refresh_from_db()
    assert scar_a.status == "rca_submitted"


def test_supplierquality_scar_close_status_and_admin_gate(client, admin_user, member_user, scar_a):
    """Verify closing SCAR sets closed_at date and requires admin authorization."""
    url = reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar_a.pk})

    # Require POST
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin user blocked (403)
    client.force_login(member_user)
    assert client.post(url, {"status": "closed"}).status_code == 403

    # Admin user closes SCAR
    client.force_login(admin_user)
    resp = client.post(url, {"status": "closed"})
    assert resp.status_code == 302

    scar_a.refresh_from_db()
    assert scar_a.status == "closed"
    assert scar_a.closed_at == timezone.now().date()


# =============================================================================
# 5. SupplierChangeNotification Views
# =============================================================================

def test_supplierquality_scn_list_get_and_context(client, admin_user, scn_a):
    """Verify SCN list GET returns 200 with filter choices and records."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "scns",
        "category_choices",
        "risk_choices",
        "status_choices",
        "disposition_choices",
        "suppliers",
        "search_query",
        "current_status",
        "current_category",
        "current_risk",
        "current_disposition",
        "current_supplier",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from SCN list context"

    assert scn_a.number in resp.content.decode()


def test_supplierquality_scn_list_filters(client, admin_user, scn_a, supplier_party_a):
    """Verify SCN list filters by query, status, category, risk, disposition, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_list")

    resp = client.get(url, {
        "q": scn_a.number,
        "status": scn_a.status,
        "category": scn_a.change_category,
        "risk": scn_a.risk_level,
        "supplier": str(supplier_party_a.pk),
    })
    assert resp.status_code == 200
    assert scn_a in resp.context["scns"]

    # Junk parameter handling
    resp_junk = client.get(url, {"page": "invalid", "risk": "bogus_risk"})
    assert resp_junk.status_code == 200


def test_supplierquality_scn_detail_view(client, admin_user, scn_a):
    """Verify SCN detail GET returns 200 with scn context."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["scn"] == scn_a
    assert scn_a.number in resp.content.decode()


def test_supplierquality_scn_create_get(client, admin_user):
    """Verify SCN create GET renders form with is_edit=False."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["scn"] is None


def test_supplierquality_scn_create_post_valid(client, admin_user, tenant_a, supplier_party_a, audit_a):
    """Verify valid POST to SCN create logs record and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_create")
    post_data = _supplierquality_scn_data(
        supplier=supplier_party_a,
        evaluator=admin_user,
        audit=audit_a,
        title="Secondary Packaging Box Geometry Modification",
        description="Outer corrugated shipping box depth enlarged by 10mm.",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_scn = SupplierChangeNotification.objects.filter(
        tenant=tenant_a, title="Secondary Packaging Box Geometry Modification"
    ).first()
    assert created_scn is not None
    assert resp.url == reverse("quality:supplier_change_notification_detail", kwargs={"pk": created_scn.pk})


def test_supplierquality_scn_create_post_invalid(client, admin_user, supplier_party_a):
    """Verify invalid POST (affects_form_fit_function=True without notes) is rejected."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_create")
    post_data = _supplierquality_scn_data(
        supplier=supplier_party_a,
        affects_form_fit_function=True,
        impact_assessment_notes="",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "impact_assessment_notes" in resp.context["form"].errors


def test_supplierquality_scn_edit_get_and_post(client, admin_user, scn_a):
    """Verify SCN edit GET and valid POST update record."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["scn"] == scn_a

    post_data = _supplierquality_scn_data(
        supplier=scn_a.supplier,
        evaluator=scn_a.evaluated_by,
        audit=scn_a.requalification_audit,
        title="Updated Ultrasonic Bath Description",
        description="Detailed testing protocol for 68kHz cleaning verification.",
    )
    resp_post = client.post(url, post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_a.pk})

    scn_a.refresh_from_db()
    assert scn_a.title == "Updated Ultrasonic Bath Description"


def test_supplierquality_scn_delete_post_and_admin_gate(client, admin_user, member_user, tenant_a, supplier_party_a):
    """Verify SCN delete requires POST and admin privileges."""
    scn_to_delete = SupplierChangeNotification.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title="Draft SCN for Deletion",
        change_category="labeling_packaging",
        risk_level="level_1_minor",
        status="received",
        description="Minor label font adjustment",
    )
    url = reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_to_delete.pk})

    # Require POST
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin blocked
    client.force_login(member_user)
    assert client.post(url).status_code == 403

    # Admin delete
    client.force_login(admin_user)
    resp_del = client.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("quality:supplier_change_notification_list")
    assert not SupplierChangeNotification.objects.filter(pk=scn_to_delete.pk).exists()


def test_supplierquality_scn_export_csv(client, admin_user, scn_a):
    """Verify SCN CSV export returns text/csv with formatted rows."""
    client.force_login(admin_user)
    url = reverse("quality:supplier_change_notification_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment; filename=\"supplier_change_notifications.csv\"" in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "SCN #" in header
    assert "Risk Level" in header
    rows = list(reader)
    assert any(scn_a.number in row[0] for row in rows)


def test_supplierquality_scn_disposition_post_and_admin_gate(client, admin_user, member_user, scn_a):
    """Verify recording disposition sets approval details, date, and user under admin gate."""
    url = reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn_a.pk})

    # Require POST
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin user blocked (403)
    client.force_login(member_user)
    assert client.post(url, {"disposition": "approved"}).status_code == 403

    # Admin user records disposition
    client.force_login(admin_user)
    resp = client.post(url, {
        "disposition": "approved",
        "disposition_notes": "Validation runs successfully proved cleanliness equivalency.",
    })
    assert resp.status_code == 302
    assert resp.url == reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_a.pk})

    scn_a.refresh_from_db()
    assert scn_a.disposition == "approved"
    assert scn_a.status == "approved"
    assert scn_a.approved_by == admin_user
    assert scn_a.disposition_date == timezone.now().date()
    assert scn_a.disposition_notes == "Validation runs successfully proved cleanliness equivalency."


# =============================================================================
# 6. Cross-Tenant Isolation & Authentication Guards
# =============================================================================

def test_supplierquality_cross_tenant_isolation_detail(client, admin_user, audit_b, scorecard_b, scar_b, scn_b):
    """Verify tenant_a users receive 404 when requesting tenant_b objects."""
    client.force_login(admin_user)

    # Detail 404
    assert client.get(reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit_b.pk})).status_code == 404
    assert client.get(reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_b.pk})).status_code == 404
    assert client.get(reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_b.pk})).status_code == 404
    assert client.get(reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_b.pk})).status_code == 404

    # Edit 404
    assert client.get(reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit_b.pk})).status_code == 404
    assert client.get(reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": scorecard_b.pk})).status_code == 404
    assert client.get(reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar_b.pk})).status_code == 404
    assert client.get(reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn_b.pk})).status_code == 404

    # Delete 404
    assert client.post(reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_b.pk})).status_code == 404
    assert client.post(reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": scorecard_b.pk})).status_code == 404
    assert client.post(reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_b.pk})).status_code == 404
    assert client.post(reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_b.pk})).status_code == 404


def test_supplierquality_cross_tenant_isolation_list(client, admin_user, audit_b, scorecard_b, scar_b, scn_b):
    """Verify list and AVL views do not leak tenant_b records."""
    client.force_login(admin_user)

    avl_resp = client.get(reverse("quality:avl_directory"))
    assert audit_b.number not in avl_resp.content.decode()

    audit_resp = client.get(reverse("quality:supplier_qualification_audit_list"))
    assert audit_b.number not in audit_resp.content.decode()

    scorecard_resp = client.get(reverse("quality:supplier_quality_scorecard_list"))
    assert scorecard_b.number not in scorecard_resp.content.decode()

    scar_resp = client.get(reverse("quality:supplier_corrective_action_list"))
    assert scar_b.number not in scar_resp.content.decode()

    scn_resp = client.get(reverse("quality:supplier_change_notification_list"))
    assert scn_b.number not in scn_resp.content.decode()


def test_supplierquality_unauthenticated_redirect(client, audit_a, scorecard_a, scar_a, scn_a):
    """Verify unauthenticated requests redirect to login."""
    urls = [
        reverse("quality:avl_directory"),
        reverse("quality:supplier_qualification_audit_list"),
        reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit_a.pk}),
        reverse("quality:supplier_quality_scorecard_list"),
        reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_a.pk}),
        reverse("quality:supplier_corrective_action_list"),
        reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_a.pk}),
        reverse("quality:supplier_change_notification_list"),
        reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_a.pk}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url
