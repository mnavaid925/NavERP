"""
Security, Multi-Tenant Data Isolation, Role Authorization, and Adversarial Tests
for Sub-module 12.6: Supplier & Vendor Quality Management.

Test coverage requirements:
1. Multi-Tenant Data Isolation & Cross-Tenant IDOR:
   - Exhaustive IDOR sweeps: accessing Tenant B objects as Tenant A returns HTTP 404
     across detail, edit, delete, status/publish/advance/close/disposition endpoints.
   - Symmetric IDOR: Client B accessing Tenant A resources returns HTTP 404.
   - List views and AVL directory never leak Tenant B records or aggregate metrics.
   - Cross-Tenant Foreign Key Injection: forging form submissions with Foreign Keys
     belonging to Tenant B (supplier, lead_auditor, quality_agreement, qualification_audit,
     internal_capa, non_conformance, design_project, evaluated_by, issued_by, verified_by)
     is strictly rejected by reject_foreign.
2. Authentication & Role Enforcement:
   - Unauthenticated GET and POST requests across all 29 endpoints redirect to login (HTTP 302).
   - Non-admin tenant users (e.g. user_a with is_tenant_admin=False) cannot access
     @tenant_admin_required endpoints (delete, audit status transition, scorecard publish,
     SCAR close/status, SCN disposition) -> HTTP 403 Forbidden.
   - State-changing endpoints reject GET requests -> HTTP 405 Method Not Allowed.
3. Mass Assignment Prevention:
   - Crafting POST data with tenant, number, created_at, updated_at does not overwrite those fields.
   - SCN form cannot mass-assign disposition, approved_by, disposition_date.
   - Scorecard form cannot mass-assign status="published", overall_score, grade.
   - SCAR form cannot mass-assign status="closed", closed_at.
4. Injection Sanitization & Defense-in-Depth:
   - CSV exports neutralize formula injection (including with leading whitespace: ' =cmd|...')
     via _csv_safe across all 4 export endpoints.
   - X-Content-Type-Options: nosniff header enforced on exports.
   - Template rendering escapes HTML/XSS payloads (<script>alert(1)</script>).
5. Audit Logging & Compliance (21 CFR Part 11 / GxP):
   - Verify AuditLog records are created with correct tenant, user, action verb (<= 10 chars).
   - On deletion of audits, scorecards, SCARs, and SCNs, AuditLog.object_id is preserved.
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, OrgUnit, Party, PartyRole, Tenant
from apps.quality.forms.SupplierQuality.SupplierChangeNotifications import (
    SupplierChangeNotificationForm,
)
from apps.quality.forms.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveActionForm,
)
from apps.quality.forms.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAuditForm,
)
from apps.quality.forms.SupplierQuality.SupplierQualityScorecards import (
    SupplierQualityScorecardForm,
)
from apps.quality.models import (
    CapaInvestigation,
    ControlledDocument,
    DesignProject,
    NonConformanceReport,
    SupplierChangeNotification,
    SupplierCorrectiveAction,
    SupplierQualificationAudit,
    SupplierQualityScorecard,
)
from apps.quality.views.SupplierQuality.SupplierQualificationAudits import _csv_safe

pytestmark = pytest.mark.django_db


# =============================================================================
# Fixtures and Helpers (Prefix: _supplierquality_*)
# =============================================================================

@pytest.fixture
def _supplierquality_user_a(member_user):
    """Tenant A standard non-admin member user."""
    return member_user


@pytest.fixture
def _supplierquality_user_b(db, tenant_b):
    """Tenant B standard non-admin member user."""
    return User.objects.create_user(
        email="member_b@globex.com",
        username="member_globex",
        password="TestPass123!",
        tenant=tenant_b,
        is_tenant_admin=False,
    )


user_a = _supplierquality_user_a
user_b = _supplierquality_user_b


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


def _supplierquality_audit_logs(obj_or_model, object_id=None, action=None, tenant=None):
    """Retrieve audit log rows written for obj or model."""
    if isinstance(obj_or_model, type):
        ct = ContentType.objects.get_for_model(obj_or_model)
        qs = AuditLog.objects.filter(content_type=ct)
        if object_id is not None:
            qs = qs.filter(object_id=object_id)
    else:
        ct = ContentType.objects.get_for_model(obj_or_model.__class__)
        qs = AuditLog.objects.filter(content_type=ct, object_id=obj_or_model.pk)
    if action:
        qs = qs.filter(action=action)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs


def _supplierquality_parse_csv(response):
    """Parse CSV response into list of rows."""
    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    return list(reader)


# =============================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR Sweeps
# =============================================================================

def test_supplierquality_audit_detail_cross_tenant_idor_404(client_a, client_b, audit_a, audit_b):
    """Accessing foreign SupplierQualificationAudit detail returns 404 symmetrically."""
    url_b = reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit_b.pk})
    assert client_a.get(url_b).status_code == 404

    url_a = reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit_a.pk})
    assert client_b.get(url_a).status_code == 404


def test_supplierquality_audit_edit_cross_tenant_idor_404(client_a, client_b, audit_a, audit_b):
    """GET and POST to edit foreign SupplierQualificationAudit returns 404; database remains untouched."""
    url_b = reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit_b.pk})
    assert client_a.get(url_b).status_code == 404
    assert client_a.post(url_b, {"notes": "Tampered Audit Notes"}).status_code == 404
    audit_b.refresh_from_db()
    assert "Tampered" not in (audit_b.notes or "")

    url_a = reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit_a.pk})
    assert client_b.get(url_a).status_code == 404
    assert client_b.post(url_a, {"notes": "Tampered Audit Notes"}).status_code == 404
    audit_a.refresh_from_db()
    assert "Tampered" not in (audit_a.notes or "")


def test_supplierquality_audit_delete_cross_tenant_idor_404(client_a, client_b, audit_a, audit_b):
    """POST to delete foreign SupplierQualificationAudit returns 404; record is preserved."""
    url_b = reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_b.pk})
    assert client_a.post(url_b).status_code == 404
    assert SupplierQualificationAudit.objects.filter(pk=audit_b.pk).exists()

    url_a = reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_a.pk})
    assert client_b.post(url_a).status_code == 404
    assert SupplierQualificationAudit.objects.filter(pk=audit_a.pk).exists()


def test_supplierquality_audit_status_cross_tenant_idor_404(client_a, client_b, audit_a, audit_b):
    """POST to update status of foreign audit returns 404; status remains untouched."""
    url_b = reverse("quality:supplier_qualification_audit_status", kwargs={"pk": audit_b.pk})
    assert client_a.post(url_b, {"status": "conditional"}).status_code == 404
    audit_b.refresh_from_db()
    assert audit_b.qualification_status != "conditional"

    url_a = reverse("quality:supplier_qualification_audit_status", kwargs={"pk": audit_a.pk})
    assert client_b.post(url_a, {"status": "conditional"}).status_code == 404
    audit_a.refresh_from_db()
    assert audit_a.qualification_status != "conditional"


def test_supplierquality_scorecard_detail_cross_tenant_idor_404(client_a, client_b, scorecard_a, scorecard_b):
    """Accessing foreign SupplierQualityScorecard detail returns 404 symmetrically."""
    url_b = reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_b.pk})
    assert client_a.get(url_b).status_code == 404

    url_a = reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_a.pk})
    assert client_b.get(url_a).status_code == 404


def test_supplierquality_scorecard_edit_cross_tenant_idor_404(client_a, client_b, scorecard_a, scorecard_b):
    """GET and POST to edit foreign SupplierQualityScorecard returns 404; database remains untouched."""
    url_b = reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": scorecard_b.pk})
    assert client_a.get(url_b).status_code == 404
    assert client_a.post(url_b, {"evaluation_notes": "Tampered Evaluation"}).status_code == 404
    scorecard_b.refresh_from_db()
    assert "Tampered" not in (scorecard_b.evaluation_notes or "")

    url_a = reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": scorecard_a.pk})
    assert client_b.get(url_a).status_code == 404
    assert client_b.post(url_a, {"evaluation_notes": "Tampered Evaluation"}).status_code == 404
    scorecard_a.refresh_from_db()
    assert "Tampered" not in (scorecard_a.evaluation_notes or "")


def test_supplierquality_scorecard_delete_cross_tenant_idor_404(client_a, client_b, scorecard_a, scorecard_b):
    """POST to delete foreign SupplierQualityScorecard returns 404; record is preserved."""
    url_b = reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": scorecard_b.pk})
    assert client_a.post(url_b).status_code == 404
    assert SupplierQualityScorecard.objects.filter(pk=scorecard_b.pk).exists()

    url_a = reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": scorecard_a.pk})
    assert client_b.post(url_a).status_code == 404
    assert SupplierQualityScorecard.objects.filter(pk=scorecard_a.pk).exists()


def test_supplierquality_scorecard_publish_cross_tenant_idor_404(client_a, client_b, scorecard_a, scorecard_b):
    """POST to publish foreign scorecard returns 404; status remains draft."""
    assert scorecard_b.status == "draft"
    url_b = reverse("quality:supplier_quality_scorecard_publish", kwargs={"pk": scorecard_b.pk})
    assert client_a.post(url_b).status_code == 404
    scorecard_b.refresh_from_db()
    assert scorecard_b.status == "draft"

    url_a = reverse("quality:supplier_quality_scorecard_publish", kwargs={"pk": scorecard_a.pk})
    assert client_b.post(url_a).status_code == 404


def test_supplierquality_scar_detail_cross_tenant_idor_404(client_a, client_b, scar_a, scar_b):
    """Accessing foreign SupplierCorrectiveAction detail returns 404 symmetrically."""
    url_b = reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_b.pk})
    assert client_a.get(url_b).status_code == 404

    url_a = reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_a.pk})
    assert client_b.get(url_a).status_code == 404


def test_supplierquality_scar_edit_cross_tenant_idor_404(client_a, client_b, scar_a, scar_b):
    """GET and POST to edit foreign SupplierCorrectiveAction returns 404; database remains untouched."""
    url_b = reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar_b.pk})
    assert client_a.get(url_b).status_code == 404
    assert client_a.post(url_b, {"title": "Tampered Title"}).status_code == 404
    scar_b.refresh_from_db()
    assert scar_b.title != "Tampered Title"

    url_a = reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar_a.pk})
    assert client_b.get(url_a).status_code == 404
    assert client_b.post(url_a, {"title": "Tampered Title"}).status_code == 404
    scar_a.refresh_from_db()
    assert scar_a.title != "Tampered Title"


def test_supplierquality_scar_delete_cross_tenant_idor_404(client_a, client_b, scar_a, scar_b):
    """POST to delete foreign SupplierCorrectiveAction returns 404; record is preserved."""
    url_b = reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_b.pk})
    assert client_a.post(url_b).status_code == 404
    assert SupplierCorrectiveAction.objects.filter(pk=scar_b.pk).exists()

    url_a = reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_a.pk})
    assert client_b.post(url_a).status_code == 404
    assert SupplierCorrectiveAction.objects.filter(pk=scar_a.pk).exists()


def test_supplierquality_scar_status_cross_tenant_idor_404(client_a, client_b, scar_a, scar_b):
    """POST to advance or close foreign SCAR returns 404; status remains untouched."""
    url_b = reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar_b.pk})
    assert client_a.post(url_b, {"status": "closed"}).status_code == 404
    scar_b.refresh_from_db()
    assert scar_b.status != "closed"

    url_a = reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar_a.pk})
    assert client_b.post(url_a, {"status": "closed"}).status_code == 404
    scar_a.refresh_from_db()
    assert scar_a.status != "closed"


def test_supplierquality_scn_detail_cross_tenant_idor_404(client_a, client_b, scn_a, scn_b):
    """Accessing foreign SupplierChangeNotification detail returns 404 symmetrically."""
    url_b = reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_b.pk})
    assert client_a.get(url_b).status_code == 404

    url_a = reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_a.pk})
    assert client_b.get(url_a).status_code == 404


def test_supplierquality_scn_edit_cross_tenant_idor_404(client_a, client_b, scn_a, scn_b):
    """GET and POST to edit foreign SupplierChangeNotification returns 404; database remains untouched."""
    url_b = reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn_b.pk})
    assert client_a.get(url_b).status_code == 404
    assert client_a.post(url_b, {"title": "Tampered Title"}).status_code == 404
    scn_b.refresh_from_db()
    assert scn_b.title != "Tampered Title"

    url_a = reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn_a.pk})
    assert client_b.get(url_a).status_code == 404
    assert client_b.post(url_a, {"title": "Tampered Title"}).status_code == 404
    scn_a.refresh_from_db()
    assert scn_a.title != "Tampered Title"


def test_supplierquality_scn_delete_cross_tenant_idor_404(client_a, client_b, scn_a, scn_b):
    """POST to delete foreign SupplierChangeNotification returns 404; record is preserved."""
    url_b = reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_b.pk})
    assert client_a.post(url_b).status_code == 404
    assert SupplierChangeNotification.objects.filter(pk=scn_b.pk).exists()

    url_a = reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_a.pk})
    assert client_b.post(url_a).status_code == 404
    assert SupplierChangeNotification.objects.filter(pk=scn_a.pk).exists()


def test_supplierquality_scn_disposition_cross_tenant_idor_404(client_a, client_b, scn_a, scn_b):
    """POST to set disposition on foreign SCN returns 404; disposition remains untouched."""
    url_b = reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn_b.pk})
    assert client_a.post(url_b, {"disposition": "approved"}).status_code == 404
    scn_b.refresh_from_db()
    assert scn_b.disposition != "approved"

    url_a = reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn_a.pk})
    assert client_b.post(url_a, {"disposition": "rejected"}).status_code == 404
    scn_a.refresh_from_db()
    assert scn_a.disposition != "rejected"


# =============================================================================
# 2. List Views & AVL Directory Isolation
# =============================================================================

def test_supplierquality_avl_directory_cross_tenant_isolation(client_a, client_b, audit_a, audit_b):
    """Verify AVL directory never leaks foreign supplier audits or foreign metrics."""
    res_a = client_a.get(reverse("quality:avl_directory"))
    assert res_a.status_code == 200
    content_a = res_a.content.decode("utf-8")
    assert audit_a.supplier.name in content_a
    assert audit_b.supplier.name not in content_a
    qual_pks_a = [q.pk for q in res_a.context["qualifications"]]
    assert audit_a.pk in qual_pks_a
    assert audit_b.pk not in qual_pks_a

    res_b = client_b.get(reverse("quality:avl_directory"))
    assert res_b.status_code == 200
    content_b = res_b.content.decode("utf-8")
    assert audit_b.supplier.name in content_b
    assert audit_a.supplier.name not in content_b
    qual_pks_b = [q.pk for q in res_b.context["qualifications"]]
    assert audit_b.pk in qual_pks_b
    assert audit_a.pk not in qual_pks_b


def test_supplierquality_audit_list_cross_tenant_isolation(client_a, client_b, audit_a, audit_b):
    """Verify audit list strictly isolates tenant records."""
    url = reverse("quality:supplier_qualification_audit_list")
    res_a = client_a.get(url)
    assert res_a.status_code == 200
    assert audit_a.supplier.name in res_a.content.decode("utf-8")
    assert audit_b.supplier.name not in res_a.content.decode("utf-8")
    audits_a = [a.pk for a in res_a.context["audits"]]
    assert audit_a.pk in audits_a
    assert audit_b.pk not in audits_a

    res_b = client_b.get(url)
    assert res_b.status_code == 200
    assert audit_b.supplier.name in res_b.content.decode("utf-8")
    assert audit_a.supplier.name not in res_b.content.decode("utf-8")
    audits_b = [a.pk for a in res_b.context["audits"]]
    assert audit_b.pk in audits_b
    assert audit_a.pk not in audits_b


def test_supplierquality_scorecard_list_cross_tenant_isolation(client_a, client_b, scorecard_a, scorecard_b):
    """Verify scorecard list strictly isolates tenant records."""
    url = reverse("quality:supplier_quality_scorecard_list")
    res_a = client_a.get(url)
    assert res_a.status_code == 200
    assert scorecard_a.supplier.name in res_a.content.decode("utf-8")
    assert scorecard_b.supplier.name not in res_a.content.decode("utf-8")
    scs_a = [s.pk for s in res_a.context["scorecards"]]
    assert scorecard_a.pk in scs_a
    assert scorecard_b.pk not in scs_a

    res_b = client_b.get(url)
    assert res_b.status_code == 200
    assert scorecard_b.supplier.name in res_b.content.decode("utf-8")
    assert scorecard_a.supplier.name not in res_b.content.decode("utf-8")
    scs_b = [s.pk for s in res_b.context["scorecards"]]
    assert scorecard_b.pk in scs_b
    assert scorecard_a.pk not in scs_b


def test_supplierquality_scar_list_cross_tenant_isolation(client_a, client_b, scar_a, scar_b):
    """Verify SCAR list strictly isolates tenant records."""
    url = reverse("quality:supplier_corrective_action_list")
    res_a = client_a.get(url)
    assert res_a.status_code == 200
    assert scar_a.title in res_a.content.decode("utf-8")
    assert scar_b.title not in res_a.content.decode("utf-8")
    scars_a = [s.pk for s in res_a.context["scars"]]
    assert scar_a.pk in scars_a
    assert scar_b.pk not in scars_a

    res_b = client_b.get(url)
    assert res_b.status_code == 200
    assert scar_b.title in res_b.content.decode("utf-8")
    assert scar_a.title not in res_b.content.decode("utf-8")
    scars_b = [s.pk for s in res_b.context["scars"]]
    assert scar_b.pk in scars_b
    assert scar_a.pk not in scars_b


def test_supplierquality_scn_list_cross_tenant_isolation(client_a, client_b, scn_a, scn_b):
    """Verify SCN list strictly isolates tenant records."""
    url = reverse("quality:supplier_change_notification_list")
    res_a = client_a.get(url)
    assert res_a.status_code == 200
    assert scn_a.title in res_a.content.decode("utf-8")
    assert scn_b.title not in res_a.content.decode("utf-8")
    scns_a = [s.pk for s in res_a.context["scns"]]
    assert scn_a.pk in scns_a
    assert scn_b.pk not in scns_a

    res_b = client_b.get(url)
    assert res_b.status_code == 200
    assert scn_b.title in res_b.content.decode("utf-8")
    assert scn_a.title not in res_b.content.decode("utf-8")
    scns_b = [s.pk for s in res_b.context["scns"]]
    assert scn_b.pk in scns_b
    assert scn_a.pk not in scns_b


def test_supplierquality_csv_exports_cross_tenant_isolation(
    client_a, client_b, audit_a, audit_b, scorecard_a, scorecard_b, scar_a, scar_b, scn_a, scn_b
):
    """Verify all 4 CSV export endpoints strictly filter by tenant without row leakage."""
    export_specs = [
        ("quality:supplier_qualification_audit_export", audit_a.supplier.name, audit_b.supplier.name),
        ("quality:supplier_quality_scorecard_export", scorecard_a.supplier.name, scorecard_b.supplier.name),
        ("quality:supplier_corrective_action_export", scar_a.title, scar_b.title),
        ("quality:supplier_change_notification_export", scn_a.title, scn_b.title),
    ]

    for url_name, expected_a, expected_b in export_specs:
        res_a = client_a.get(reverse(url_name))
        assert res_a.status_code == 200
        text_a = res_a.content.decode("utf-8")
        assert expected_a in text_a, f"Expected {expected_a} in Tenant A export {url_name}"
        assert expected_b not in text_a, f"Leaked {expected_b} into Tenant A export {url_name}"

        res_b = client_b.get(reverse(url_name))
        assert res_b.status_code == 200
        text_b = res_b.content.decode("utf-8")
        assert expected_b in text_b, f"Expected {expected_b} in Tenant B export {url_name}"
        assert expected_a not in text_b, f"Leaked {expected_a} into Tenant B export {url_name}"


# =============================================================================
# 3. Cross-Tenant Foreign Key Injection (reject_foreign)
# =============================================================================

def test_supplierquality_audit_form_foreign_key_injection_rejected(
    tenant_a, supplier_party_a, supplier_party_b, admin_user, admin_b, doc_a, quality_doc_b
):
    """Verify SupplierQualificationAuditForm rejects foreign tenant supplier, auditor, or quality agreement."""
    # 1. Foreign supplier
    bad_supplier = _supplierquality_audit_data(supplier_party_b, auditor=admin_user, doc=doc_a)
    form1 = SupplierQualificationAuditForm(data=bad_supplier, tenant=tenant_a)
    assert not form1.is_valid()
    assert "supplier" in form1.errors

    # 2. Foreign lead auditor
    bad_auditor = _supplierquality_audit_data(supplier_party_a, auditor=admin_b, doc=doc_a)
    form2 = SupplierQualificationAuditForm(data=bad_auditor, tenant=tenant_a)
    assert not form2.is_valid()
    assert "lead_auditor" in form2.errors

    # 3. Foreign quality agreement
    bad_doc = _supplierquality_audit_data(supplier_party_a, auditor=admin_user, doc=quality_doc_b)
    form3 = SupplierQualificationAuditForm(data=bad_doc, tenant=tenant_a)
    assert not form3.is_valid()
    assert "quality_agreement" in form3.errors


def test_supplierquality_scorecard_form_foreign_key_injection_rejected(
    tenant_a, supplier_party_a, supplier_party_b, admin_user, admin_b
):
    """Verify SupplierQualityScorecardForm rejects foreign supplier or evaluator."""
    # 1. Foreign supplier
    bad_supplier = _supplierquality_scorecard_data(supplier_party_b, evaluator=admin_user)
    form1 = SupplierQualityScorecardForm(data=bad_supplier, tenant=tenant_a)
    assert not form1.is_valid()
    assert "supplier" in form1.errors

    # 2. Foreign evaluator
    bad_evaluator = _supplierquality_scorecard_data(supplier_party_a, evaluator=admin_b)
    form2 = SupplierQualityScorecardForm(data=bad_evaluator, tenant=tenant_a)
    assert not form2.is_valid()
    assert "evaluated_by" in form2.errors


def test_supplierquality_scar_form_foreign_key_injection_rejected(
    tenant_a, supplier_party_a, supplier_party_b, admin_user, admin_b, audit_a, audit_b, capa_investigation_b
):
    """Verify SupplierCorrectiveActionForm rejects foreign supplier, audit, capa, or users."""
    # 1. Foreign supplier
    bad_supp = _supplierquality_scar_data(supplier_party_b, issued_by=admin_user, audit=audit_a)
    form1 = SupplierCorrectiveActionForm(data=bad_supp, tenant=tenant_a)
    assert not form1.is_valid()
    assert "supplier" in form1.errors

    # 2. Foreign qualification audit
    bad_audit = _supplierquality_scar_data(supplier_party_a, issued_by=admin_user, audit=audit_b)
    form2 = SupplierCorrectiveActionForm(data=bad_audit, tenant=tenant_a)
    assert not form2.is_valid()
    assert "qualification_audit" in form2.errors

    # 3. Foreign internal CAPA
    bad_capa = _supplierquality_scar_data(supplier_party_a, issued_by=admin_user, internal_capa=capa_investigation_b.pk)
    form3 = SupplierCorrectiveActionForm(data=bad_capa, tenant=tenant_a)
    assert not form3.is_valid()
    assert "internal_capa" in form3.errors

    # 4. Foreign issued_by user
    bad_user = _supplierquality_scar_data(supplier_party_a, issued_by=admin_b)
    form4 = SupplierCorrectiveActionForm(data=bad_user, tenant=tenant_a)
    assert not form4.is_valid()
    assert "issued_by" in form4.errors

    # 5. Foreign verified_by user
    bad_ver = _supplierquality_scar_data(supplier_party_a, issued_by=admin_user, verified_by=admin_b.pk)
    form5 = SupplierCorrectiveActionForm(data=bad_ver, tenant=tenant_a)
    assert not form5.is_valid()
    assert "verified_by" in form5.errors


def test_supplierquality_scn_form_foreign_key_injection_rejected(
    tenant_a, supplier_party_a, supplier_party_b, admin_user, admin_b, design_project_b, audit_b
):
    """Verify SupplierChangeNotificationForm rejects foreign supplier, design project, audit, or evaluator."""
    # 1. Foreign supplier
    bad_supp = _supplierquality_scn_data(supplier_party_b, evaluator=admin_user)
    form1 = SupplierChangeNotificationForm(data=bad_supp, tenant=tenant_a)
    assert not form1.is_valid()
    assert "supplier" in form1.errors

    # 2. Foreign design project
    bad_proj = _supplierquality_scn_data(supplier_party_a, evaluator=admin_user, design_project=design_project_b.pk)
    form2 = SupplierChangeNotificationForm(data=bad_proj, tenant=tenant_a)
    assert not form2.is_valid()
    assert "design_project" in form2.errors

    # 3. Foreign requalification audit
    bad_audit = _supplierquality_scn_data(supplier_party_a, evaluator=admin_user, audit=audit_b)
    form3 = SupplierChangeNotificationForm(data=bad_audit, tenant=tenant_a)
    assert not form3.is_valid()
    assert "requalification_audit" in form3.errors

    # 4. Foreign evaluator
    bad_eval = _supplierquality_scn_data(supplier_party_a, evaluator=admin_b)
    form4 = SupplierChangeNotificationForm(data=bad_eval, tenant=tenant_a)
    assert not form4.is_valid()
    assert "evaluated_by" in form4.errors


def test_supplierquality_views_cross_tenant_foreign_key_post_rejected(
    client_a, tenant_a, supplier_party_b, audit_b, admin_b
):
    """Submitting foreign Foreign Keys via POST to creation endpoints is rejected without creating records."""
    initial_audits = SupplierQualificationAudit.objects.filter(tenant=tenant_a).count()
    initial_scorecards = SupplierQualityScorecard.objects.filter(tenant=tenant_a).count()
    initial_scars = SupplierCorrectiveAction.objects.filter(tenant=tenant_a).count()
    initial_scns = SupplierChangeNotification.objects.filter(tenant=tenant_a).count()

    # 1. Create audit with foreign supplier
    bad_audit = _supplierquality_audit_data(supplier_party_b)
    res1 = client_a.post(reverse("quality:supplier_qualification_audit_create"), bad_audit)
    assert res1.status_code == 200
    assert SupplierQualificationAudit.objects.filter(tenant=tenant_a).count() == initial_audits

    # 2. Create scorecard with foreign supplier
    bad_scorecard = _supplierquality_scorecard_data(supplier_party_b)
    res2 = client_a.post(reverse("quality:supplier_quality_scorecard_create"), bad_scorecard)
    assert res2.status_code == 200
    assert SupplierQualityScorecard.objects.filter(tenant=tenant_a).count() == initial_scorecards

    # 3. Create SCAR with foreign supplier
    bad_scar = _supplierquality_scar_data(supplier_party_b)
    res3 = client_a.post(reverse("quality:supplier_corrective_action_create"), bad_scar)
    assert res3.status_code == 200
    assert SupplierCorrectiveAction.objects.filter(tenant=tenant_a).count() == initial_scars

    # 4. Create SCN with foreign supplier
    bad_scn = _supplierquality_scn_data(supplier_party_b)
    res4 = client_a.post(reverse("quality:supplier_change_notification_create"), bad_scn)
    assert res4.status_code == 200
    assert SupplierChangeNotification.objects.filter(tenant=tenant_a).count() == initial_scns


# =============================================================================
# 4. Authentication & Role Enforcement
# =============================================================================

def test_supplierquality_unauthenticated_requests_redirect_to_login(
    client, audit_a, scorecard_a, scar_a, scn_a
):
    """Unauthenticated requests across all 29 endpoints redirect to login (HTTP 302)."""
    endpoints = [
        # AVL Directory
        ("get", reverse("quality:avl_directory")),
        # Audits
        ("get", reverse("quality:supplier_qualification_audit_list")),
        ("get", reverse("quality:supplier_qualification_audit_create")),
        ("post", reverse("quality:supplier_qualification_audit_create")),
        ("get", reverse("quality:supplier_qualification_audit_export")),
        ("get", reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit_a.pk})),
        ("get", reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit_a.pk})),
        ("post", reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit_a.pk})),
        ("post", reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_a.pk})),
        ("post", reverse("quality:supplier_qualification_audit_status", kwargs={"pk": audit_a.pk})),
        # Scorecards
        ("get", reverse("quality:supplier_quality_scorecard_list")),
        ("get", reverse("quality:supplier_quality_scorecard_create")),
        ("post", reverse("quality:supplier_quality_scorecard_create")),
        ("get", reverse("quality:supplier_quality_scorecard_export")),
        ("get", reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard_a.pk})),
        ("get", reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": scorecard_a.pk})),
        ("post", reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": scorecard_a.pk})),
        ("post", reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": scorecard_a.pk})),
        ("post", reverse("quality:supplier_quality_scorecard_publish", kwargs={"pk": scorecard_a.pk})),
        # SCARs
        ("get", reverse("quality:supplier_corrective_action_list")),
        ("get", reverse("quality:supplier_corrective_action_create")),
        ("post", reverse("quality:supplier_corrective_action_create")),
        ("get", reverse("quality:supplier_corrective_action_export")),
        ("get", reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar_a.pk})),
        ("get", reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar_a.pk})),
        ("post", reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar_a.pk})),
        ("post", reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_a.pk})),
        ("post", reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar_a.pk})),
        # SCNs
        ("get", reverse("quality:supplier_change_notification_list")),
        ("get", reverse("quality:supplier_change_notification_create")),
        ("post", reverse("quality:supplier_change_notification_create")),
        ("get", reverse("quality:supplier_change_notification_export")),
        ("get", reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn_a.pk})),
        ("get", reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn_a.pk})),
        ("post", reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn_a.pk})),
        ("post", reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_a.pk})),
        ("post", reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn_a.pk})),
    ]

    login_url_prefix = reverse(settings.LOGIN_URL)
    for method, url in endpoints:
        resp = client.get(url) if method == "get" else client.post(url)
        assert resp.status_code == 302, f"Endpoint {method.upper()} {url} did not redirect (status {resp.status_code})"
        assert resp.url.startswith(login_url_prefix), f"Endpoint {method.upper()} {url} redirected to {resp.url} instead of {login_url_prefix}"


def test_supplierquality_non_admin_cannot_access_tenant_admin_endpoints(
    client, user_a, audit_a, scorecard_a, scar_a, scn_a
):
    """Non-admin user (is_tenant_admin=False) receives 403 Forbidden on @tenant_admin_required endpoints."""
    client.force_login(user_a)

    privileged_endpoints = [
        # 1. Audit delete
        (reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_a.pk}), {}),
        # 2. Audit status transition
        (reverse("quality:supplier_qualification_audit_status", kwargs={"pk": audit_a.pk}), {"status": "conditional"}),
        # 3. Scorecard delete
        (reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": scorecard_a.pk}), {}),
        # 4. Scorecard publish
        (reverse("quality:supplier_quality_scorecard_publish", kwargs={"pk": scorecard_a.pk}), {}),
        # 5. SCAR delete
        (reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_a.pk}), {}),
        # 6. SCAR status update / close
        (reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar_a.pk}), {"status": "closed"}),
        # 7. SCN delete
        (reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_a.pk}), {}),
        # 8. SCN disposition
        (reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn_a.pk}), {"disposition": "approved"}),
    ]

    for url, payload in privileged_endpoints:
        resp = client.post(url, payload)
        assert resp.status_code == 403, f"Non-admin user accessed privileged endpoint {url} (status {resp.status_code})"

    # Assert database states were NOT modified by non-admin attempts
    assert SupplierQualificationAudit.objects.filter(pk=audit_a.pk).exists()
    audit_a.refresh_from_db()
    assert audit_a.qualification_status != "conditional"

    assert SupplierQualityScorecard.objects.filter(pk=scorecard_a.pk).exists()
    assert SupplierCorrectiveAction.objects.filter(pk=scar_a.pk).exists()
    scar_a.refresh_from_db()
    assert scar_a.status != "closed"

    assert SupplierChangeNotification.objects.filter(pk=scn_a.pk).exists()
    scn_a.refresh_from_db()
    assert scn_a.disposition != "approved"


def test_supplierquality_state_changing_endpoints_reject_get(client_a, audit_a, scorecard_a, scar_a, scn_a):
    """State-changing POST-only endpoints reject GET with 405 Method Not Allowed."""
    post_only_endpoints = [
        reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_a.pk}),
        reverse("quality:supplier_qualification_audit_status", kwargs={"pk": audit_a.pk}),
        reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": scorecard_a.pk}),
        reverse("quality:supplier_quality_scorecard_publish", kwargs={"pk": scorecard_a.pk}),
        reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_a.pk}),
        reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar_a.pk}),
        reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_a.pk}),
        reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn_a.pk}),
    ]

    for url in post_only_endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Endpoint {url} accepted GET (status {resp.status_code})"


# =============================================================================
# 5. Mass Assignment Prevention
# =============================================================================

def test_supplierquality_audit_mass_assignment_prevented(client_a, tenant_a, tenant_b, audit_a):
    """Crafted POST data cannot overwrite tenant, number, created_at, or updated_at on audit."""
    orig_tenant = audit_a.tenant
    orig_number = audit_a.number
    orig_created = audit_a.created_at

    url = reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit_a.pk})
    tamper_data = _supplierquality_audit_data(
        audit_a.supplier,
        auditor=audit_a.lead_auditor,
        tenant=tenant_b.pk,
        number="HACKED-AUDIT-9999",
        created_at="2020-01-01T00:00:00Z",
    )
    res = client_a.post(url, tamper_data)
    assert res.status_code == 302

    audit_a.refresh_from_db()
    assert audit_a.tenant == orig_tenant
    assert audit_a.number == orig_number
    assert audit_a.created_at == orig_created


def test_supplierquality_scorecard_mass_assignment_prevented(client_a, tenant_a, tenant_b, scorecard_a):
    """Scorecard form rejects status='published' and prevents mass-assigning overall_score or grade."""
    # 1. Form level: clean_status rejects published on draft instance
    draft_scorecard = SupplierQualityScorecard.objects.create(
        tenant=tenant_a,
        supplier=scorecard_a.supplier,
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
    tamper_status = _supplierquality_scorecard_data(scorecard_a.supplier, status="published")
    form = SupplierQualityScorecardForm(data=tamper_status, instance=draft_scorecard, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors

    # 2. View level: forged overall_score and grade in POST are ignored / overwritten by calculation
    url = reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": draft_scorecard.pk})
    tamper_post = _supplierquality_scorecard_data(
        scorecard_a.supplier,
        status="under_review",
        lot_acceptance_rate_score="90.00",
        defect_ppm_score="90.00",
        scar_responsiveness_score="90.00",
        audit_compliance_score="90.00",
        documentation_coa_score="90.00",
        overall_score="50.00",
        grade="grade_d",
        tenant=tenant_b.pk,
        number="FORGED-SCR-999",
    )
    res = client_a.post(url, tamper_post)
    assert res.status_code == 302

    draft_scorecard.refresh_from_db()
    assert draft_scorecard.tenant == tenant_a
    assert draft_scorecard.number != "FORGED-SCR-999"
    # overall_score must be computed from components: 90.00 -> grade_a, not 50.00
    assert draft_scorecard.overall_score == Decimal("90.00")
    assert draft_scorecard.grade == "grade_a"


def test_supplierquality_scar_mass_assignment_prevented(client_a, tenant_a, tenant_b, scar_a):
    """SCAR form rejects status='closed' and ignores closed_at or forged tenant."""
    # 1. Form level: clean_status blocks closing directly
    tamper_closed = _supplierquality_scar_data(scar_a.supplier, status="closed")
    form = SupplierCorrectiveActionForm(data=tamper_closed, instance=scar_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors

    # 2. View level: forged closed_at and tenant ignored on edit
    url = reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar_a.pk})
    tamper_post = _supplierquality_scar_data(
        scar_a.supplier,
        status="rca_submitted",
        closed_at="2020-01-01",
        tenant=tenant_b.pk,
        number="FORGED-SCAR-888",
    )
    res = client_a.post(url, tamper_post)
    assert res.status_code == 302

    scar_a.refresh_from_db()
    assert scar_a.tenant == tenant_a
    assert scar_a.number != "FORGED-SCAR-888"
    assert scar_a.closed_at is None


def test_supplierquality_scn_mass_assignment_prevented(client_a, tenant_a, tenant_b, scn_a, admin_user):
    """SCN form cannot mass-assign disposition, approved_by, or disposition_date."""
    # Form doesn't expose disposition, approved_by, disposition_date
    url = reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn_a.pk})
    tamper_data = _supplierquality_scn_data(
        scn_a.supplier,
        disposition="approved",
        approved_by=admin_user.pk,
        disposition_date="2020-01-01",
        tenant=tenant_b.pk,
        number="FORGED-SCN-777",
    )
    res = client_a.post(url, tamper_data)
    assert res.status_code == 302

    scn_a.refresh_from_db()
    assert scn_a.tenant == tenant_a
    assert scn_a.number != "FORGED-SCN-777"
    assert scn_a.disposition != "approved"
    assert scn_a.approved_by is None
    assert scn_a.disposition_date is None


# =============================================================================
# 6. Injection Sanitization & Defense-in-Depth
# =============================================================================

def test_supplierquality_csv_safe_neutralizes_formula_injection():
    """Verify _csv_safe neutralizes malicious formula prefixes (=, +, -, @, \\t, \\r) and handles whitespace."""
    # Standard formula prefixes
    assert _csv_safe("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert _csv_safe("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert _csv_safe("-1+2") == "'-1+2"
    assert _csv_safe("@SUM(B1:B5)") == "'@SUM(B1:B5)"

    # Leading whitespace before formula triggers (e.g. " =cmd|...")
    assert _csv_safe("   =cmd|' /C calc'!A0") == "'   =cmd|' /C calc'!A0"
    assert _csv_safe("  +12345") == "'  +12345"
    assert _csv_safe(" -alert(1)") == "' -alert(1)"
    assert _csv_safe(" @malicious") == "' @malicious"
    assert _csv_safe("\t=cmd") == "'\t=cmd"
    assert _csv_safe("\r=cmd") == "'\r=cmd"

    # Non-formula inputs
    assert _csv_safe("Normal text") == "Normal text"
    assert _csv_safe("ISO-13485:2016") == "ISO-13485:2016"
    assert _csv_safe(None) == ""
    assert _csv_safe(100) == "100"
    assert _csv_safe(Decimal("95.50")) == "95.50"


def test_supplierquality_csv_exports_neutralize_formula_injection(
    client_a, tenant_a, admin_user
):
    """Verify CSV export responses neutralize formulas and set security headers across all 4 models."""
    formula_supplier = Party.objects.create(
        tenant=tenant_a,
        name=" =cmd|' /C calc'!A0",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=formula_supplier,
        role="vendor",
    )

    audit = SupplierQualificationAudit.objects.create(
        tenant=tenant_a,
        supplier=formula_supplier,
        assessment_type="initial_qualification",
        criticality_tier="critical",
        audit_method="on_site",
        qualification_status="approved",
        audit_result="passed",
        score=99.00,
    )
    scorecard = SupplierQualityScorecard.objects.create(
        tenant=tenant_a,
        supplier=formula_supplier,
        cadence="quarterly",
        period_start=timezone.now().date() - timedelta(days=90),
        period_end=timezone.now().date(),
        status="draft",
        lot_acceptance_rate_score=Decimal("90.00"),
        defect_ppm_score=Decimal("90.00"),
        scar_responsiveness_score=Decimal("90.00"),
        audit_compliance_score=Decimal("90.00"),
        documentation_coa_score=Decimal("90.00"),
    )
    scar = SupplierCorrectiveAction.objects.create(
        tenant=tenant_a,
        supplier=formula_supplier,
        title=" -cmd|' /C calc'!A0",
        severity="critical",
        status="draft",
        issued_date=timezone.now().date(),
    )
    scn = SupplierChangeNotification.objects.create(
        tenant=tenant_a,
        supplier=formula_supplier,
        title=" +SUM(1,2)",
        change_category="facility_location",
        risk_level="level_2_moderate",
        status="received",
    )

    # 1. Audit export
    res_audit = client_a.get(reverse("quality:supplier_qualification_audit_export"))
    assert res_audit.status_code == 200
    assert res_audit["X-Content-Type-Options"] == "nosniff"
    assert 'filename="supplier_qualification_audits.csv"' in res_audit["Content-Disposition"]
    rows_audit = _supplierquality_parse_csv(res_audit)
    audit_row = next(r for r in rows_audit if r[0] == audit.number)
    # Supplier name had leading space and =: " =cmd..." -> should start with "' "
    assert audit_row[1].startswith("'")

    # 2. Scorecard export
    res_scorecard = client_a.get(reverse("quality:supplier_quality_scorecard_export"))
    assert res_scorecard.status_code == 200
    assert res_scorecard["X-Content-Type-Options"] == "nosniff"
    rows_scorecard = _supplierquality_parse_csv(res_scorecard)
    scorecard_row = next(r for r in rows_scorecard if r[0] == scorecard.number)
    assert scorecard_row[1].startswith("'")

    # 3. SCAR export
    res_scar = client_a.get(reverse("quality:supplier_corrective_action_export"))
    assert res_scar.status_code == 200
    assert res_scar["X-Content-Type-Options"] == "nosniff"
    rows_scar = _supplierquality_parse_csv(res_scar)
    scar_row = next(r for r in rows_scar if r[0] == scar.number)
    # Title had leading space and minus: " -cmd..." -> should start with "' "
    assert scar_row[2].startswith("'")

    # 4. SCN export
    res_scn = client_a.get(reverse("quality:supplier_change_notification_export"))
    assert res_scn.status_code == 200
    assert res_scn["X-Content-Type-Options"] == "nosniff"
    rows_scn = _supplierquality_parse_csv(res_scn)
    scn_row = next(r for r in rows_scn if r[0] == scn.number)
    # Title had leading space and plus: " +SUM..." -> should start with "' "
    assert scn_row[2].startswith("'")


def test_supplierquality_template_rendering_escapes_xss_payloads(
    client_a, tenant_a, supplier_party_a, admin_user
):
    """HTML and script tags in user-controlled fields are properly escaped in templates."""
    xss_payload = "<script>alert('XSS-PAYLOAD')</script>"
    xss_img = "<img src=x onerror=alert(1)>"

    # Create records with script tags
    audit = SupplierQualificationAudit.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        assessment_type="initial_qualification",
        criticality_tier="critical",
        audit_method="on_site",
        qualification_status="approved",
        audit_result="passed",
        score=90.00,
        scope_commodities=xss_payload,
        notes=xss_img,
    )
    scorecard = SupplierQualityScorecard.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="quarterly",
        period_start=timezone.now().date() - timedelta(days=90),
        period_end=timezone.now().date(),
        status="draft",
        lot_acceptance_rate_score=Decimal("80.00"),
        defect_ppm_score=Decimal("80.00"),
        scar_responsiveness_score=Decimal("80.00"),
        audit_compliance_score=Decimal("80.00"),
        documentation_coa_score=Decimal("80.00"),
        evaluation_notes=xss_payload,
    )
    scar = SupplierCorrectiveAction.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title=xss_payload,
        defect_summary=xss_img,
        severity="major",
        status="draft",
        issued_date=timezone.now().date(),
    )
    scn = SupplierChangeNotification.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title=xss_payload,
        change_category="facility_location",
        risk_level="level_2_moderate",
        status="received",
        description=xss_img,
    )

    # Verify detail and list pages escape raw HTML tags
    views_to_check = [
        reverse("quality:supplier_qualification_audit_detail", kwargs={"pk": audit.pk}),
        reverse("quality:supplier_qualification_audit_list"),
        reverse("quality:supplier_quality_scorecard_detail", kwargs={"pk": scorecard.pk}),
        reverse("quality:supplier_quality_scorecard_list"),
        reverse("quality:supplier_corrective_action_detail", kwargs={"pk": scar.pk}),
        reverse("quality:supplier_corrective_action_list"),
        reverse("quality:supplier_change_notification_detail", kwargs={"pk": scn.pk}),
        reverse("quality:supplier_change_notification_list"),
    ]

    for url in views_to_check:
        resp = client_a.get(url)
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        # Ensure unescaped script tag is not present
        assert "<script>alert('XSS-PAYLOAD')</script>" not in content
        assert "<img src=x onerror=alert(1)>" not in content


# =============================================================================
# 7. Audit Logging & Compliance (21 CFR Part 11 / GxP)
# =============================================================================

def test_supplierquality_audit_log_audit_create_update_delete_advance(
    client_a, tenant_a, supplier_party_a, admin_user
):
    """Verify AuditLog records on audit create, update, advance status, and delete with verbs <= 10 chars."""
    # 1. Create
    create_data = _supplierquality_audit_data(supplier_party_a, auditor=admin_user)
    res_create = client_a.post(reverse("quality:supplier_qualification_audit_create"), create_data)
    assert res_create.status_code == 302
    audit = SupplierQualificationAudit.objects.filter(tenant=tenant_a).latest("id")

    logs_create = _supplierquality_audit_logs(audit, action="create", tenant=tenant_a)
    assert logs_create.exists()
    log_c = logs_create.first()
    assert log_c.user == admin_user
    assert len(log_c.action) <= 10
    assert log_c.action == "create"

    # 2. Update
    edit_data = _supplierquality_audit_data(supplier_party_a, auditor=admin_user, notes="Updated Audit Scope Notes")
    res_edit = client_a.post(reverse("quality:supplier_qualification_audit_edit", kwargs={"pk": audit.pk}), edit_data)
    assert res_edit.status_code == 302
    logs_update = _supplierquality_audit_logs(audit, action="update", tenant=tenant_a)
    assert logs_update.exists()
    log_u = logs_update.first()
    assert log_u.user == admin_user
    assert len(log_u.action) <= 10

    # 3. Status transition (advance)
    res_status = client_a.post(
        reverse("quality:supplier_qualification_audit_status", kwargs={"pk": audit.pk}),
        {"status": "conditional"},
    )
    assert res_status.status_code == 302
    logs_advance = _supplierquality_audit_logs(audit, action="advance", tenant=tenant_a)
    assert logs_advance.exists()
    log_adv = logs_advance.first()
    assert log_adv.user == admin_user
    assert len(log_adv.action) <= 10
    assert log_adv.action == "advance"

    # 4. Delete
    audit_id = audit.pk
    res_del = client_a.post(reverse("quality:supplier_qualification_audit_delete", kwargs={"pk": audit_id}))
    assert res_del.status_code == 302
    assert not SupplierQualificationAudit.objects.filter(pk=audit_id).exists()

    logs_delete = _supplierquality_audit_logs(SupplierQualificationAudit, object_id=audit_id, action="delete", tenant=tenant_a)
    assert logs_delete.exists()
    log_d = logs_delete.first()
    assert log_d.user == admin_user
    assert log_d.object_id == audit_id
    assert len(log_d.action) <= 10
    assert log_d.action == "delete"


def test_supplierquality_audit_log_scorecard_create_update_delete_publish(
    client_a, tenant_a, supplier_party_a, admin_user
):
    """Verify AuditLog records on scorecard create, update, publish, and delete."""
    # 1. Create
    create_data = _supplierquality_scorecard_data(supplier_party_a, evaluator=admin_user)
    res_create = client_a.post(reverse("quality:supplier_quality_scorecard_create"), create_data)
    assert res_create.status_code == 302
    scorecard = SupplierQualityScorecard.objects.filter(tenant=tenant_a).latest("id")

    logs_create = _supplierquality_audit_logs(scorecard, action="create", tenant=tenant_a)
    assert logs_create.exists()
    assert logs_create.first().user == admin_user

    # 2. Update
    edit_data = _supplierquality_scorecard_data(supplier_party_a, evaluator=admin_user, evaluation_notes="Updated notes")
    res_edit = client_a.post(reverse("quality:supplier_quality_scorecard_edit", kwargs={"pk": scorecard.pk}), edit_data)
    assert res_edit.status_code == 302
    assert _supplierquality_audit_logs(scorecard, action="update", tenant=tenant_a).exists()

    # 3. Publish
    res_pub = client_a.post(reverse("quality:supplier_quality_scorecard_publish", kwargs={"pk": scorecard.pk}))
    assert res_pub.status_code == 302
    logs_pub = _supplierquality_audit_logs(scorecard, action="publish", tenant=tenant_a)
    assert logs_pub.exists()
    log_p = logs_pub.first()
    assert log_p.user == admin_user
    assert len(log_p.action) <= 10
    assert log_p.action == "publish"

    # 4. Delete
    sc_id = scorecard.pk
    res_del = client_a.post(reverse("quality:supplier_quality_scorecard_delete", kwargs={"pk": sc_id}))
    assert res_del.status_code == 302
    logs_del = _supplierquality_audit_logs(SupplierQualityScorecard, object_id=sc_id, action="delete", tenant=tenant_a)
    assert logs_del.exists()
    assert logs_del.first().object_id == sc_id


def test_supplierquality_audit_log_scar_create_update_delete_advance_close(
    client_a, tenant_a, supplier_party_a, admin_user
):
    """Verify AuditLog records on SCAR create, update, status advance, close, and delete."""
    # 1. Create
    create_data = _supplierquality_scar_data(supplier_party_a, issued_by=admin_user)
    res_create = client_a.post(reverse("quality:supplier_corrective_action_create"), create_data)
    assert res_create.status_code == 302
    scar = SupplierCorrectiveAction.objects.filter(tenant=tenant_a).latest("id")

    logs_create = _supplierquality_audit_logs(scar, action="create", tenant=tenant_a)
    assert logs_create.exists()
    assert logs_create.first().user == admin_user

    # 2. Update
    edit_data = _supplierquality_scar_data(supplier_party_a, issued_by=admin_user, title="Updated SCAR Title")
    res_edit = client_a.post(reverse("quality:supplier_corrective_action_edit", kwargs={"pk": scar.pk}), edit_data)
    assert res_edit.status_code == 302
    assert _supplierquality_audit_logs(scar, action="update", tenant=tenant_a).exists()

    # 3. Status advance
    res_adv = client_a.post(
        reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar.pk}),
        {"status": "containment_submitted"},
    )
    assert res_adv.status_code == 302
    logs_adv = _supplierquality_audit_logs(scar, action="advance", tenant=tenant_a)
    assert logs_adv.exists()
    assert len(logs_adv.first().action) <= 10
    assert logs_adv.first().action == "advance"

    # 4. Status close
    res_close = client_a.post(
        reverse("quality:supplier_corrective_action_status", kwargs={"pk": scar.pk}),
        {"status": "closed"},
    )
    assert res_close.status_code == 302
    logs_close = _supplierquality_audit_logs(scar, action="close", tenant=tenant_a)
    assert logs_close.exists()
    assert len(logs_close.first().action) <= 10
    assert logs_close.first().action == "close"

    # 5. Delete
    scar_id = scar.pk
    res_del = client_a.post(reverse("quality:supplier_corrective_action_delete", kwargs={"pk": scar_id}))
    assert res_del.status_code == 302
    logs_del = _supplierquality_audit_logs(SupplierCorrectiveAction, object_id=scar_id, action="delete", tenant=tenant_a)
    assert logs_del.exists()
    assert logs_del.first().object_id == scar_id


def test_supplierquality_audit_log_scn_create_update_delete_disposition(
    client_a, tenant_a, supplier_party_a, admin_user
):
    """Verify AuditLog records on SCN create, update, disposition actions, and delete."""
    # 1. Create
    create_data = _supplierquality_scn_data(supplier_party_a, evaluator=admin_user)
    res_create = client_a.post(reverse("quality:supplier_change_notification_create"), create_data)
    assert res_create.status_code == 302
    scn = SupplierChangeNotification.objects.filter(tenant=tenant_a).latest("id")

    logs_create = _supplierquality_audit_logs(scn, action="create", tenant=tenant_a)
    assert logs_create.exists()
    assert logs_create.first().user == admin_user

    # 2. Update
    edit_data = _supplierquality_scn_data(supplier_party_a, evaluator=admin_user, title="Updated SCN Title")
    res_edit = client_a.post(reverse("quality:supplier_change_notification_edit", kwargs={"pk": scn.pk}), edit_data)
    assert res_edit.status_code == 302
    assert _supplierquality_audit_logs(scn, action="update", tenant=tenant_a).exists()

    # 3. Disposition - approve
    res_disp1 = client_a.post(
        reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn.pk}),
        {"disposition": "approved", "disposition_notes": "All qualification criteria met."},
    )
    assert res_disp1.status_code == 302
    logs_appr = _supplierquality_audit_logs(scn, action="approve", tenant=tenant_a)
    assert logs_appr.exists()
    assert len(logs_appr.first().action) <= 10
    assert logs_appr.first().action == "approve"

    # 4. Disposition - reject
    res_disp2 = client_a.post(
        reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn.pk}),
        {"disposition": "rejected", "disposition_notes": "Failed biocompatibility validation."},
    )
    assert res_disp2.status_code == 302
    logs_rej = _supplierquality_audit_logs(scn, action="reject", tenant=tenant_a)
    assert logs_rej.exists()
    assert len(logs_rej.first().action) <= 10
    assert logs_rej.first().action == "reject"

    # 5. Disposition - conditional approval (advance)
    res_disp3 = client_a.post(
        reverse("quality:supplier_change_notification_disposition", kwargs={"pk": scn.pk}),
        {"disposition": "conditional_approval", "disposition_notes": "First 3 lots require CMM report."},
    )
    assert res_disp3.status_code == 302
    logs_cond = _supplierquality_audit_logs(scn, action="advance", tenant=tenant_a)
    assert logs_cond.exists()
    assert len(logs_cond.first().action) <= 10
    assert logs_cond.first().action == "advance"

    # 6. Delete
    scn_id = scn.pk
    res_del = client_a.post(reverse("quality:supplier_change_notification_delete", kwargs={"pk": scn_id}))
    assert res_del.status_code == 302
    logs_del = _supplierquality_audit_logs(SupplierChangeNotification, object_id=scn_id, action="delete", tenant=tenant_a)
    assert logs_del.exists()
    assert logs_del.first().object_id == scn_id
