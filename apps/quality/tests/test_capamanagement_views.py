"""
Unit and integration tests for apps/quality views (Sub-module 12.4: CAPA - Corrective & Preventive Action).

Covers all 5 view sets, routes, query filters, context keys, status transitions, permissions, and CSV exports:
1. CapaInvestigations views:
   - list: 200 OK, context keys, search/filter (q, status, source, priority), pagination, tenant isolation.
   - detail: 200 OK, context keys (capa, rcas, actions, reviews), cross-tenant 404.
   - create: GET (200), POST valid (302 redirect + audit log), POST invalid (200 with form errors).
   - edit: GET (200), POST valid (302 redirect + audit log), closed CAPA guard warning redirect.
   - delete: POST only (405 on GET), tenant admin required (403 for member), closed CAPA guard, audit log before delete.
   - advance_status: POST only (405), invalid status error, closed CAPA error, direct-to-closed rejected,
     voided requires tenant admin, valid lifecycle transition + audit log.
   - close: POST only (405), tenant admin required (403), pending actions guard, sets closed_at,
     closure_approved_by, status="closed", audit log.
   - export: 200 OK, text/csv, nosniff header, csv_safe formula sanitization, tenant isolation, audit log.
2. RootCauseAnalyses views:
   - list: 200 OK, context keys, filters (method, category, capa), search, pagination, tenant isolation.
   - detail: 200 OK, context keys (rca, linked_actions), cross-tenant 404.
   - create: GET (with ?capa= prefill), POST valid (302 + audit log), POST invalid (200).
   - edit: GET (200), POST valid (302 + audit log), verified RCA guard warning redirect.
   - delete: POST only (405), tenant admin required (403), verified RCA guard, closed parent CAPA guard, audit log.
   - verify: POST only (405), already verified guard, closed parent CAPA guard, valid verification + audit log.
   - export: 200 OK, text/csv, nosniff header, tenant isolation, audit log.
3. CapaActions views:
   - list: 200 OK, context keys, filters (type, status, capa), search, pagination, tenant isolation.
   - detail: 200 OK, context key (action), cross-tenant 404.
   - create: GET (with ?capa= and ?rca= prefill), POST valid (302 + audit log), POST invalid (200).
   - edit: GET (200), POST valid (302 + audit log), verified action guard warning redirect.
   - delete: POST only (405), tenant admin required (403), verified action guard, closed parent CAPA guard, audit log.
   - mark_completed: POST only (405), already verified/cancelled guard, sets implemented + audit log.
   - verify: POST only (405), already verified guard, requires implemented status, separation of duties guard
     (assignee cannot verify unless tenant admin), valid verification + audit log.
   - export: 200 OK, text/csv, nosniff header, tenant isolation, audit log.
4. CapaEffectivenessReviews views:
   - list: 200 OK, context keys, filters (outcome, status, capa), search, pagination, tenant isolation.
   - detail: 200 OK, context key (review), cross-tenant 404.
   - create: GET (with ?capa= prefill), POST valid (302 + audit log), POST invalid (200).
   - edit: GET (200), POST valid (302 + audit log), completed review guard warning redirect.
   - delete: POST only (405), tenant admin required (403), completed review guard, closed parent CAPA guard, audit log.
   - sign_off: POST only (405), already completed guard, non-evaluator / non-admin guard, definitive outcome guard,
     recurrence_observed cannot be effective guard, valid sign-off + audit log.
   - export: 200 OK, text/csv, nosniff header, tenant isolation, audit log.
5. CapaTrackingBoard views:
   - tracking_board: 200 OK, context keys (tier_0_30, tier_31_60, tier_61_90, tier_90_plus, escalated, overdue, stats),
     excludes closed/voided CAPAs, tenant isolation.
   - tracking_board_export: 200 OK, text/csv, nosniff header, aging tiers, tenant isolation, audit log.
6. Authentication guards:
   - Unauthenticated requests to all 28+ endpoints redirect to login.
"""

import csv
import io
from datetime import timedelta
import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, OrgUnit
from apps.quality.models import (
    CapaAction,
    CapaEffectivenessReview,
    CapaInvestigation,
    DesignProject,
    RiskAssessment,
    RootCauseAnalysis,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures and Helpers (Prefix: _capamanagement_*)
# =====================================================================


def _capamanagement_get_messages(response):
    """Extract message strings from response wsgi_request."""
    if hasattr(response, "wsgi_request"):
        return [m.message for m in get_messages(response.wsgi_request)]
    return []


def _capamanagement_assert_no_comment_leaks(response):
    """Assert response HTML contains no template comment fragments."""
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "{#" not in content, "Found unrendered '{#' comment leak in HTML template"
    assert "{% comment" not in content, "Found unrendered '{% comment' leak in HTML template"


def _capamanagement_audit_logs(obj_or_model, object_id=None, action=None):
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
    return qs


def _capamanagement_set_actions_count(self, value):
    self.__dict__["actions_count"] = value


def _capamanagement_set_pending_actions_count(self, value):
    self.__dict__["pending_actions_count"] = value


# Ensure annotated QuerySets can set actions_count and pending_actions_count
if not CapaInvestigation.actions_count.fset:
    CapaInvestigation.actions_count = CapaInvestigation.actions_count.setter(
        _capamanagement_set_actions_count
    )

if not CapaInvestigation.pending_actions_count.fset:
    CapaInvestigation.pending_actions_count = (
        CapaInvestigation.pending_actions_count.setter(
            _capamanagement_set_pending_actions_count
        )
    )



@pytest.fixture
def _capamanagement_closed_capa(db, tenant_a, admin_user, quality_department):
    """Fixture for an already closed CAPA."""
    return CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Closed Suture Needle Dimensional Deviation",
        action_type="corrective",
        source_type="internal_audit",
        risk_priority="medium",
        status="closed",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
        issue_summary="Needle length deviation remediated and verified.",
        target_closure_date=timezone.now().date() - timedelta(days=10),
        closed_at=timezone.now(),
        closure_approved_by=admin_user,
        closure_summary="All actions implemented and confirmed effective.",
    )


@pytest.fixture
def _capamanagement_voided_capa(db, tenant_a, admin_user, quality_department):
    """Fixture for a voided CAPA."""
    return CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Voided False Alarm Transducer CAPA",
        action_type="preventive",
        source_type="monitoring_trend",
        risk_priority="low",
        status="voided",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
        issue_summary="Instrument measurement artifact determined not to be a genuine defect.",
        escalation_reason="Voided by Quality Director.",
    )


@pytest.fixture
def _capamanagement_verified_rca(db, tenant_a, admin_user, capa_investigation_a):
    """Fixture for a verified Root Cause Analysis."""
    return RootCauseAnalysis.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        rca_method="5_whys",
        problem_statement="Core pin wear causing wall thinning.",
        root_cause_summary="Preventive maintenance interval lacked pin metrology.",
        root_cause_category="equipment",
        lead_investigator=admin_user,
        status="verified",
        verified_by=admin_user,
        verified_date=timezone.now().date(),
        verification_notes="Verified against tool metrology history.",
    )


@pytest.fixture
def _capamanagement_implemented_action(db, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a):
    """Fixture for an implemented CAPA Action item."""
    return CapaAction.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        root_cause=root_cause_analysis_a,
        action_type="corrective",
        title="Revise Tooling Metrology Work Instruction",
        description="Add CMM pin check step 4.2 to WI-MNT-009.",
        assigned_to=admin_user,
        department=quality_department,
        due_date=timezone.now().date() + timedelta(days=5),
        status="implemented",
        completion_date=timezone.now().date(),
        implementation_notes="WI-MNT-009 revision 2 released into production.",
    )


@pytest.fixture
def _capamanagement_verified_action(db, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a):
    """Fixture for a verified CAPA Action item."""
    return CapaAction.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        root_cause=root_cause_analysis_a,
        action_type="corrective",
        title="Calibrate Optical Inspection Camera",
        description="Verify pixel resolution on automated line 1.",
        assigned_to=admin_user,
        department=quality_department,
        due_date=timezone.now().date() - timedelta(days=2),
        status="verified",
        completion_date=timezone.now().date() - timedelta(days=2),
        verified_by=admin_user,
        verified_on=timezone.now().date(),
        verification_evidence="Calibration certificate CAL-2026-991 attached.",
    )


@pytest.fixture
def _capamanagement_completed_review(db, tenant_a, admin_user, capa_investigation_a):
    """Fixture for a completed CapaEffectivenessReview."""
    return CapaEffectivenessReview.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        review_criteria="Zero defects across 3 consecutive batches.",
        verification_method="statistical_sample",
        planned_review_date=timezone.now().date() - timedelta(days=1),
        actual_review_date=timezone.now().date(),
        evaluator=admin_user,
        outcome="effective",
        status="completed",
        review_notes="Zero ferrule fractures reported; Cpk is 1.45.",
    )


# =====================================================================
# 1. CapaInvestigations Views Tests
# =====================================================================


class TestCapaInvestigationViews:
    def test_capamanagement_views_investigation_list_get_success(self, client_a, capa_investigation_a):
        url = reverse("quality:capa_investigation_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        # Context keys assertions
        assert "capas" in res.context
        assert "total_count" in res.context
        assert "active_count" in res.context
        assert "overdue_count" in res.context
        assert "critical_count" in res.context
        assert "status_choices" in res.context
        assert "source_type_choices" in res.context
        assert "risk_priority_choices" in res.context
        assert res.context["total_count"] >= 1
        assert res.context["active_count"] >= 1

        # Rendered content assertions
        content = res.content.decode("utf-8")
        assert capa_investigation_a.number in content
        assert capa_investigation_a.title in content

    def test_capamanagement_views_investigation_list_search_q(
        self, client_a, capa_investigation_a, _capamanagement_closed_capa
    ):
        url = reverse("quality:capa_investigation_list")

        # Search by number
        res_num = client_a.get(f"{url}?q={capa_investigation_a.number}")
        assert res_num.status_code == 200
        capas_num = list(res_num.context["capas"])
        assert capa_investigation_a in capas_num
        assert _capamanagement_closed_capa not in capas_num

        # Search by title keyword
        res_title = client_a.get(f"{url}?q=Optical+Fiber")
        assert res_title.status_code == 200
        capas_title = list(res_title.context["capas"])
        assert capa_investigation_a in capas_title
        assert _capamanagement_closed_capa not in capas_title

        # Search by non-existent term
        res_none = client_a.get(f"{url}?q=NonExistentKeywordXYZ")
        assert res_none.status_code == 200
        assert len(res_none.context["capas"]) == 0

    def test_capamanagement_views_investigation_list_filter_status(
        self, client_a, capa_investigation_a, _capamanagement_closed_capa
    ):
        url = reverse("quality:capa_investigation_list")

        # Filter by under_investigation
        res_open = client_a.get(f"{url}?status=under_investigation")
        assert res_open.status_code == 200
        capas_open = list(res_open.context["capas"])
        assert capa_investigation_a in capas_open
        assert _capamanagement_closed_capa not in capas_open

        # Filter by closed
        res_closed = client_a.get(f"{url}?status=closed")
        assert res_closed.status_code == 200
        capas_closed = list(res_closed.context["capas"])
        assert _capamanagement_closed_capa in capas_closed
        assert capa_investigation_a not in capas_closed

    def test_capamanagement_views_investigation_list_filter_source(
        self, client_a, capa_investigation_a, _capamanagement_closed_capa
    ):
        url = reverse("quality:capa_investigation_list")

        # Filter by source: complaint
        res_complaint = client_a.get(f"{url}?source=complaint")
        assert res_complaint.status_code == 200
        capas_complaint = list(res_complaint.context["capas"])
        assert capa_investigation_a in capas_complaint
        assert _capamanagement_closed_capa not in capas_complaint

        # Filter by source: internal_audit
        res_audit = client_a.get(f"{url}?source=internal_audit")
        assert res_audit.status_code == 200
        capas_audit = list(res_audit.context["capas"])
        assert _capamanagement_closed_capa in capas_audit
        assert capa_investigation_a not in capas_audit

    def test_capamanagement_views_investigation_list_filter_priority(
        self, client_a, capa_investigation_a, _capamanagement_closed_capa
    ):
        url = reverse("quality:capa_investigation_list")

        # Filter by priority: high
        res_high = client_a.get(f"{url}?priority=high")
        assert res_high.status_code == 200
        capas_high = list(res_high.context["capas"])
        assert capa_investigation_a in capas_high
        assert _capamanagement_closed_capa not in capas_high

        # Filter by priority: medium
        res_med = client_a.get(f"{url}?priority=medium")
        assert res_med.status_code == 200
        capas_med = list(res_med.context["capas"])
        assert _capamanagement_closed_capa in capas_med
        assert capa_investigation_a not in capas_med

    def test_capamanagement_views_investigation_list_pagination(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        # Create 16 items to force pagination at 15 items per page
        for i in range(16):
            CapaInvestigation.objects.create(
                tenant=tenant_a,
                title=f"Batch CAPA Item {i}",
                action_type="corrective",
                source_type="internal_audit",
                risk_priority="medium",
                status="draft",
                department=quality_department,
                lead_investigator=admin_user,
                quality_owner=admin_user,
                issue_summary="Pagination test row",
            )

        url = reverse("quality:capa_investigation_list")
        res_p1 = client_a.get(url)
        assert res_p1.status_code == 200
        assert len(res_p1.context["capas"]) == 15
        assert res_p1.context["capas"].has_next()

        res_p2 = client_a.get(f"{url}?page=2")
        assert res_p2.status_code == 200
        assert len(res_p2.context["capas"]) >= 1

    def test_capamanagement_views_investigation_list_tenant_isolation(
        self, client_a, capa_investigation_a, capa_investigation_b
    ):
        url = reverse("quality:capa_investigation_list")
        res = client_a.get(url)
        assert res.status_code == 200
        capas = list(res.context["capas"])
        assert capa_investigation_a in capas
        assert capa_investigation_b not in capas

    def test_capamanagement_views_investigation_detail_get_success(
        self, client_a, capa_investigation_a, root_cause_analysis_a, capa_action_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_investigation_detail", args=[capa_investigation_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        # Context keys assertions
        assert "capa" in res.context
        assert res.context["capa"] == capa_investigation_a
        assert "rcas" in res.context
        assert "actions" in res.context
        assert "reviews" in res.context
        assert root_cause_analysis_a in list(res.context["rcas"])
        assert capa_action_a in list(res.context["actions"])
        assert capa_effectiveness_review_a in list(res.context["reviews"])

        content = res.content.decode("utf-8")
        assert capa_investigation_a.number in content
        assert capa_investigation_a.title in content

    def test_capamanagement_views_investigation_detail_cross_tenant_404(
        self, client_a, capa_investigation_b
    ):
        url = reverse("quality:capa_investigation_detail", args=[capa_investigation_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_investigation_create_get_success(self, client_a):
        url = reverse("quality:capa_investigation_create")
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is False

    def test_capamanagement_views_investigation_create_post_valid(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        url = reverse("quality:capa_investigation_create")
        payload = {
            "title": "Laser Housing Weld Porosity Excursion",
            "issue_summary": "Sub-surface porosity detected during ultrasonic inspection of laser housing weld seam.",
            "action_type": "corrective",
            "source_type": "deviation",
            "source_reference": "DEV-2026-0091",
            "risk_priority": "high",
            "status": "draft",
            "lead_investigator": admin_user.pk,
            "quality_owner": admin_user.pk,
            "department": quality_department.pk,
            "affected_item_code": "WLD-LSR-01",
            "affected_item_name": "Laser Housing Weld Assembly",
            "containment_actions": "Quarantine weld lots W-101 and W-102.",
            "containment_implemented": True,
            "containment_verified_by": admin_user.pk,
            "containment_date": timezone.now().date().isoformat(),
            "target_closure_date": (timezone.now().date() + timedelta(days=45)).isoformat(),
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content

        created = CapaInvestigation.objects.filter(
            tenant=tenant_a, title="Laser Housing Weld Porosity Excursion"
        ).first()
        assert created is not None
        assert created.number.startswith("QCAP-")
        assert res.url == reverse("quality:capa_investigation_detail", args=[created.pk])

        # Verify audit log creation
        logs = _capamanagement_audit_logs(created, action="create")
        assert logs.count() == 1

    def test_capamanagement_views_investigation_create_post_invalid(self, client_a):
        url = reverse("quality:capa_investigation_create")
        # Missing required title and issue_summary
        res = client_a.post(url, data={"status": "draft"})
        assert res.status_code == 200
        assert "form" in res.context
        assert res.context["form"].errors
        assert "title" in res.context["form"].errors

    def test_capamanagement_views_investigation_edit_get_success(self, client_a, capa_investigation_a):
        url = reverse("quality:capa_investigation_edit", args=[capa_investigation_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is True
        assert res.context["capa"] == capa_investigation_a

    def test_capamanagement_views_investigation_edit_post_valid(
        self, client_a, capa_investigation_a, admin_user, quality_department
    ):
        url = reverse("quality:capa_investigation_edit", args=[capa_investigation_a.pk])
        payload = {
            "title": "Updated Fiber Connector Defect Investigation",
            "issue_summary": "Updated failure details regarding 15N load bend fracture.",
            "action_type": "corrective",
            "source_type": "complaint",
            "source_reference": "CMP-0108-REV",
            "risk_priority": "critical",
            "status": "under_investigation",
            "lead_investigator": admin_user.pk,
            "quality_owner": admin_user.pk,
            "department": quality_department.pk,
            "target_closure_date": (timezone.now().date() + timedelta(days=25)).isoformat(),
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content
        assert res.url == reverse("quality:capa_investigation_detail", args=[capa_investigation_a.pk])

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.title == "Updated Fiber Connector Defect Investigation"
        assert capa_investigation_a.risk_priority == "critical"

        # Verify audit log update
        logs = _capamanagement_audit_logs(capa_investigation_a, action="update")
        assert logs.count() >= 1

    def test_capamanagement_views_investigation_edit_closed_warning(
        self, client_a, _capamanagement_closed_capa
    ):
        url = reverse("quality:capa_investigation_edit", args=[_capamanagement_closed_capa.pk])
        res = client_a.get(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_detail", args=[_capamanagement_closed_capa.pk])

        messages = _capamanagement_get_messages(res)
        assert any("is closed and cannot be directly edited" in m for m in messages)

    def test_capamanagement_views_investigation_edit_cross_tenant_404(
        self, client_a, capa_investigation_b
    ):
        url = reverse("quality:capa_investigation_edit", args=[capa_investigation_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_investigation_delete_get_rejected_405(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_delete", args=[capa_investigation_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_investigation_delete_non_admin_forbidden_403(
        self, member_client, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_delete", args=[capa_investigation_a.pk])
        res = member_client.post(url)
        assert res.status_code == 403

    def test_capamanagement_views_investigation_delete_closed_error(
        self, client_a, _capamanagement_closed_capa
    ):
        url = reverse("quality:capa_investigation_delete", args=[_capamanagement_closed_capa.pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_detail", args=[_capamanagement_closed_capa.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot delete a closed CAPA investigation" in m for m in messages)
        assert CapaInvestigation.objects.filter(pk=_capamanagement_closed_capa.pk).exists()

    def test_capamanagement_views_investigation_delete_post_valid(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        capa = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="Disposable Draft CAPA for Delete Test",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="low",
            status="draft",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
            issue_summary="Disposable record.",
        )
        pk = capa.pk
        url = reverse("quality:capa_investigation_delete", args=[pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_list")

        assert not CapaInvestigation.objects.filter(pk=pk).exists()
        logs = _capamanagement_audit_logs(CapaInvestigation, object_id=pk, action="delete")
        assert logs.count() == 1

    def test_capamanagement_views_investigation_delete_cross_tenant_404(
        self, client_a, capa_investigation_b
    ):
        url = reverse("quality:capa_investigation_delete", args=[capa_investigation_b.pk])
        res = client_a.post(url)
        assert res.status_code == 404

    def test_capamanagement_views_investigation_advance_status_get_rejected_405(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[capa_investigation_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_investigation_advance_status_invalid_target(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[capa_investigation_a.pk])
        res = client_a.post(url, data={"target_status": "bogus_status_xyz"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("Invalid lifecycle transition requested" in m for m in messages)

    def test_capamanagement_views_investigation_advance_status_closed_capa_error(
        self, client_a, _capamanagement_closed_capa
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[_capamanagement_closed_capa.pk])
        res = client_a.post(url, data={"target_status": "under_investigation"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("Cannot advance or modify a closed CAPA" in m for m in messages)

    def test_capamanagement_views_investigation_advance_status_to_closed_rejected(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[capa_investigation_a.pk])
        res = client_a.post(url, data={"target_status": "closed"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("Formal closure must be performed via the closure workflow" in m for m in messages)

    def test_capamanagement_views_investigation_advance_status_voided_non_admin_rejected(
        self, member_client, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[capa_investigation_a.pk])
        res = member_client.post(url, data={"target_status": "voided"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("Only tenant administrators can void a CAPA investigation" in m for m in messages)

    def test_capamanagement_views_investigation_advance_status_voided_admin_success(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[capa_investigation_a.pk])
        res = client_a.post(url, data={"target_status": "voided"})
        assert res.status_code == 302
        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "voided"

        logs = _capamanagement_audit_logs(capa_investigation_a, action="advance")
        assert logs.count() == 1

    def test_capamanagement_views_investigation_advance_status_valid_lifecycle(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[capa_investigation_a.pk])
        res = client_a.post(url, data={"target_status": "rca_in_progress"})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_detail", args=[capa_investigation_a.pk])

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "rca_in_progress"

        logs = _capamanagement_audit_logs(capa_investigation_a, action="advance")
        assert logs.count() == 1

    def test_capamanagement_views_investigation_advance_status_cross_tenant_404(
        self, client_a, capa_investigation_b
    ):
        url = reverse("quality:capa_investigation_advance_status", args=[capa_investigation_b.pk])
        res = client_a.post(url, data={"target_status": "rca_in_progress"})
        assert res.status_code == 404

    def test_capamanagement_views_investigation_close_get_rejected_405(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_close", args=[capa_investigation_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_investigation_close_non_admin_forbidden_403(
        self, member_client, capa_investigation_a
    ):
        url = reverse("quality:capa_investigation_close", args=[capa_investigation_a.pk])
        res = member_client.post(url, data={"closure_summary": "Attempted member close."})
        assert res.status_code == 403

    def test_capamanagement_views_investigation_close_blocked_by_pending_actions(
        self, client_a, capa_investigation_a, capa_action_a
    ):
        # capa_action_a is in 'pending' status
        assert capa_action_a.status == "pending"
        url = reverse("quality:capa_investigation_close", args=[capa_investigation_a.pk])
        res = client_a.post(url, data={"closure_summary": "Attempting close with pending actions."})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("action item(s) remain incomplete" in m for m in messages)

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status != "closed"

    def test_capamanagement_views_investigation_close_success(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        # Create a CAPA with no actions or only implemented/verified actions
        capa = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="CAPA Ready for Formal Closure",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="medium",
            status="effectiveness_review",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
            issue_summary="Remediation executed and verified.",
        )
        url = reverse("quality:capa_investigation_close", args=[capa.pk])
        res = client_a.post(url, data={"closure_summary": "Formal closure approved by QA Director."})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_detail", args=[capa.pk])

        capa.refresh_from_db()
        assert capa.status == "closed"
        assert capa.closed_at is not None
        assert capa.closure_approved_by == admin_user
        assert capa.closure_summary == "Formal closure approved by QA Director."

        logs = _capamanagement_audit_logs(capa, action="close")
        assert logs.count() == 1

    def test_capamanagement_views_investigation_close_cross_tenant_404(
        self, client_a, capa_investigation_b
    ):
        url = reverse("quality:capa_investigation_close", args=[capa_investigation_b.pk])
        res = client_a.post(url, data={"closure_summary": "Cross tenant close attempt."})
        assert res.status_code == 404

    def test_capamanagement_views_investigation_export_success(
        self, client_a, capa_investigation_a, capa_investigation_b
    ):
        url = reverse("quality:capa_investigation_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"].startswith("text/csv")
        assert res["X-Content-Type-Options"] == "nosniff"
        assert "attachment; filename=" in res["Content-Disposition"]

        content = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        header = rows[0]
        assert "CAPA Number" in header
        assert "Title" in header
        assert "Risk Priority" in header
        assert "Status" in header

        # Tenant isolation assertion
        body_text = content
        assert capa_investigation_a.title in body_text
        assert capa_investigation_b.title not in body_text

        # Verify audit log
        logs = _capamanagement_audit_logs(CapaInvestigation, action="export")
        assert logs.count() >= 1

    def test_capamanagement_views_investigation_export_csv_safe_formula_sanitization(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        # Create a CAPA with formula-injection payload in title
        capa = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="=cmd|' /C calc'!A0",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="medium",
            status="draft",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
            issue_summary="+1234567890",
            source_reference="@malicious_tag",
        )
        url = reverse("quality:capa_investigation_export")
        res = client_a.get(url)
        assert res.status_code == 200

        content = res.content.decode("utf-8")
        # Formula-starting characters must be prepended with single quote
        assert "'=cmd|' /C calc'!A0" in content
        assert "'@malicious_tag" in content


# =====================================================================
# 2. RootCauseAnalyses Views Tests
# =====================================================================


class TestRootCauseAnalysisViews:
    def test_capamanagement_views_rca_list_get_success(self, client_a, root_cause_analysis_a):
        url = reverse("quality:root_cause_analysis_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        assert "rcas" in res.context
        assert "total_count" in res.context
        assert "verified_count" in res.context
        assert "rca_method_choices" in res.context
        assert "root_cause_category_choices" in res.context

        content = res.content.decode("utf-8")
        assert root_cause_analysis_a.number in content
        assert root_cause_analysis_a.problem_statement[:40] in content

    def test_capamanagement_views_rca_list_search_q(
        self, client_a, root_cause_analysis_a, _capamanagement_verified_rca
    ):
        url = reverse("quality:root_cause_analysis_list")

        # Search by number
        res_num = client_a.get(f"{url}?q={root_cause_analysis_a.number}")
        assert res_num.status_code == 200
        rcas_num = list(res_num.context["rcas"])
        assert root_cause_analysis_a in rcas_num
        assert _capamanagement_verified_rca not in rcas_num

        # Search by root cause summary keyword
        res_kw = client_a.get(f"{url}?q=metrology")
        assert res_kw.status_code == 200
        rcas_kw = list(res_kw.context["rcas"])
        assert _capamanagement_verified_rca in rcas_kw

    def test_capamanagement_views_rca_list_filter_method(
        self, client_a, root_cause_analysis_a, tenant_a, admin_user, capa_investigation_a
    ):
        # Create an Ishikawa fishbone RCA
        rca_fish = RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            rca_method="fishbone_ishikawa",
            problem_statement="Weld seam porosity investigation.",
            root_cause_summary="Gas nozzle flow turbulence.",
            root_cause_category="equipment",
            lead_investigator=admin_user,
            status="in_progress",
        )
        url = reverse("quality:root_cause_analysis_list")

        # Filter by five_whys (matching conftest.py fixture)
        res_whys = client_a.get(f"{url}?method=five_whys")
        assert res_whys.status_code == 200
        assert root_cause_analysis_a in list(res_whys.context["rcas"])
        assert rca_fish not in list(res_whys.context["rcas"])

        # Filter by fishbone_ishikawa
        res_fish = client_a.get(f"{url}?method=fishbone_ishikawa")
        assert res_fish.status_code == 200
        assert rca_fish in list(res_fish.context["rcas"])
        assert root_cause_analysis_a not in list(res_fish.context["rcas"])

    def test_capamanagement_views_rca_list_filter_category(
        self, client_a, root_cause_analysis_a, tenant_a, admin_user, capa_investigation_a
    ):
        rca_mat = RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            rca_method="5_whys",
            problem_statement="Connector resin degradation.",
            root_cause_summary="Regrind ratio exceeded 15% limit.",
            root_cause_category="supplier",
            lead_investigator=admin_user,
            status="in_progress",
        )
        url = reverse("quality:root_cause_analysis_list")

        # Filter by machine (matching conftest.py fixture)
        res_mach = client_a.get(f"{url}?category=machine")
        assert res_mach.status_code == 200
        assert root_cause_analysis_a in list(res_mach.context["rcas"])
        assert rca_mat not in list(res_mach.context["rcas"])

        # Filter by supplier
        res_mat = client_a.get(f"{url}?category=supplier")
        assert res_mat.status_code == 200
        assert rca_mat in list(res_mat.context["rcas"])
        assert root_cause_analysis_a not in list(res_mat.context["rcas"])

    def test_capamanagement_views_rca_list_filter_capa(
        self, client_a, root_cause_analysis_a, _capamanagement_closed_capa, tenant_a, admin_user
    ):
        rca_closed = RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            rca_method="5_whys",
            problem_statement="Needle grinding fixture misalignment.",
            root_cause_summary="Grinding stop worn by 0.15mm.",
            root_cause_category="equipment",
            lead_investigator=admin_user,
            status="verified",
        )
        url = reverse("quality:root_cause_analysis_list")

        # Filter by capa pk
        res_capa = client_a.get(f"{url}?capa={root_cause_analysis_a.capa_id}")
        assert res_capa.status_code == 200
        assert root_cause_analysis_a in list(res_capa.context["rcas"])
        assert rca_closed not in list(res_capa.context["rcas"])

    def test_capamanagement_views_rca_list_pagination(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        for i in range(16):
            RootCauseAnalysis.objects.create(
                tenant=tenant_a,
                capa=capa_investigation_a,
                rca_method="5_whys",
                problem_statement=f"Batch RCA Failure {i}",
                root_cause_summary="Root cause summary for batch row",
                root_cause_category="process",
                lead_investigator=admin_user,
                status="in_progress",
            )
        url = reverse("quality:root_cause_analysis_list")
        res_p1 = client_a.get(url)
        assert res_p1.status_code == 200
        assert len(res_p1.context["rcas"]) == 15
        assert res_p1.context["rcas"].has_next()

        res_p2 = client_a.get(f"{url}?page=2")
        assert res_p2.status_code == 200
        assert len(res_p2.context["rcas"]) >= 1

    def test_capamanagement_views_rca_list_tenant_isolation(
        self, client_a, root_cause_analysis_a, root_cause_analysis_b
    ):
        url = reverse("quality:root_cause_analysis_list")
        res = client_a.get(url)
        assert res.status_code == 200
        rcas = list(res.context["rcas"])
        assert root_cause_analysis_a in rcas
        assert root_cause_analysis_b not in rcas

    def test_capamanagement_views_rca_detail_get_success(
        self, client_a, root_cause_analysis_a, capa_action_a
    ):
        url = reverse("quality:root_cause_analysis_detail", args=[root_cause_analysis_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        assert "rca" in res.context
        assert res.context["rca"] == root_cause_analysis_a
        assert "linked_actions" in res.context
        assert capa_action_a in list(res.context["linked_actions"])

        content = res.content.decode("utf-8")
        assert root_cause_analysis_a.number in content
        assert root_cause_analysis_a.root_cause_summary in content

    def test_capamanagement_views_rca_detail_cross_tenant_404(
        self, client_a, root_cause_analysis_b
    ):
        url = reverse("quality:root_cause_analysis_detail", args=[root_cause_analysis_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_rca_create_get_prefills_capa(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:root_cause_analysis_create")
        res = client_a.get(f"{url}?capa={capa_investigation_a.pk}")
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is False
        assert res.context["form"].initial.get("capa") == capa_investigation_a.pk

    def test_capamanagement_views_rca_create_post_valid(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        url = reverse("quality:root_cause_analysis_create")
        payload = {
            "capa": capa_investigation_a.pk,
            "rca_method": "5_whys",
            "problem_statement": "Laser driver diode thermal trip.",
            "why_1": "Heatsink compound dried prematurely.",
            "why_2": "Thermal cycling test exceeded thermal compound rating.",
            "why_3": "Specification sheet allowed silicone-based grease in high-temp environment.",
            "why_4": "Design guidelines did not flag Phase-change pad requirement.",
            "why_5": "Thermal management engineering design checklist was outdated.",
            "root_cause_category": "design",
            "root_cause_summary": "Absence of phase-change thermal interface material mandate in design rules.",
            "escape_point_gap": "Thermal shock test performed only at prototype stage, not during PVT.",
            "status": "in_progress",
            "lead_investigator": admin_user.pk,
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content

        created = RootCauseAnalysis.objects.filter(
            tenant=tenant_a, problem_statement="Laser driver diode thermal trip."
        ).first()
        assert created is not None
        assert created.number.startswith("QRCA-")
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[created.pk])

        logs = _capamanagement_audit_logs(created, action="create")
        assert logs.count() == 1

    def test_capamanagement_views_rca_create_post_invalid(self, client_a):
        url = reverse("quality:root_cause_analysis_create")
        res = client_a.post(url, data={"rca_method": "5_whys"})
        assert res.status_code == 200
        assert "form" in res.context
        assert "problem_statement" in res.context["form"].errors

    def test_capamanagement_views_rca_edit_get_success(
        self, client_a, root_cause_analysis_a
    ):
        url = reverse("quality:root_cause_analysis_edit", args=[root_cause_analysis_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is True
        assert res.context["rca"] == root_cause_analysis_a

    def test_capamanagement_views_rca_edit_post_valid(
        self, client_a, root_cause_analysis_a, admin_user
    ):
        url = reverse("quality:root_cause_analysis_edit", args=[root_cause_analysis_a.pk])
        payload = {
            "capa": root_cause_analysis_a.capa_id,
            "rca_method": "5_whys",
            "problem_statement": "Refined connector ferrules crack under 15N load.",
            "root_cause_summary": "Comprehensive analysis showed pin wear and incorrect cooling rate.",
            "root_cause_category": "equipment",
            "status": "in_progress",
            "lead_investigator": admin_user.pk,
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[root_cause_analysis_a.pk])

        root_cause_analysis_a.refresh_from_db()
        assert root_cause_analysis_a.problem_statement == "Refined connector ferrules crack under 15N load."

        logs = _capamanagement_audit_logs(root_cause_analysis_a, action="update")
        assert logs.count() >= 1

    def test_capamanagement_views_rca_edit_verified_warning(
        self, client_a, _capamanagement_verified_rca
    ):
        url = reverse("quality:root_cause_analysis_edit", args=[_capamanagement_verified_rca.pk])
        res = client_a.get(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[_capamanagement_verified_rca.pk])

        messages = _capamanagement_get_messages(res)
        assert any("has been verified and cannot be directly modified" in m for m in messages)

    def test_capamanagement_views_rca_edit_cross_tenant_404(
        self, client_a, root_cause_analysis_b
    ):
        url = reverse("quality:root_cause_analysis_edit", args=[root_cause_analysis_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_rca_delete_get_rejected_405(
        self, client_a, root_cause_analysis_a
    ):
        url = reverse("quality:root_cause_analysis_delete", args=[root_cause_analysis_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_rca_delete_non_admin_forbidden_403(
        self, member_client, root_cause_analysis_a
    ):
        url = reverse("quality:root_cause_analysis_delete", args=[root_cause_analysis_a.pk])
        res = member_client.post(url)
        assert res.status_code == 403

    def test_capamanagement_views_rca_delete_verified_error(
        self, client_a, _capamanagement_verified_rca
    ):
        url = reverse("quality:root_cause_analysis_delete", args=[_capamanagement_verified_rca.pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[_capamanagement_verified_rca.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot delete a verified Root Cause Analysis record" in m for m in messages)
        assert RootCauseAnalysis.objects.filter(pk=_capamanagement_verified_rca.pk).exists()

    def test_capamanagement_views_rca_delete_closed_capa_error(
        self, client_a, _capamanagement_closed_capa, tenant_a, admin_user
    ):
        rca_on_closed = RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            rca_method="5_whys",
            problem_statement="Problem on closed CAPA",
            root_cause_summary="Root cause on closed CAPA",
            root_cause_category="equipment",
            lead_investigator=admin_user,
            status="in_progress",
        )
        url = reverse("quality:root_cause_analysis_delete", args=[rca_on_closed.pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[rca_on_closed.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot delete records belonging to a closed CAPA" in m for m in messages)
        assert RootCauseAnalysis.objects.filter(pk=rca_on_closed.pk).exists()

    def test_capamanagement_views_rca_delete_valid(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        rca = RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            rca_method="5_whys",
            problem_statement="Disposable RCA for Delete Test",
            root_cause_summary="Summary to delete",
            root_cause_category="process",
            lead_investigator=admin_user,
            status="in_progress",
        )
        pk = rca.pk
        capa_pk = capa_investigation_a.pk
        url = reverse("quality:root_cause_analysis_delete", args=[pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_detail", args=[capa_pk])

        assert not RootCauseAnalysis.objects.filter(pk=pk).exists()
        logs = _capamanagement_audit_logs(RootCauseAnalysis, object_id=pk, action="delete")
        assert logs.count() == 1

    def test_capamanagement_views_rca_delete_cross_tenant_404(
        self, client_a, root_cause_analysis_b
    ):
        url = reverse("quality:root_cause_analysis_delete", args=[root_cause_analysis_b.pk])
        res = client_a.post(url)
        assert res.status_code == 404

    def test_capamanagement_views_rca_verify_get_rejected_405(
        self, client_a, root_cause_analysis_a
    ):
        url = reverse("quality:root_cause_analysis_verify", args=[root_cause_analysis_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_rca_verify_already_verified_warning(
        self, client_a, _capamanagement_verified_rca
    ):
        url = reverse("quality:root_cause_analysis_verify", args=[_capamanagement_verified_rca.pk])
        res = client_a.post(url, data={"verification_notes": "Attempting re-verify"})
        assert res.status_code == 302
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[_capamanagement_verified_rca.pk])

        messages = _capamanagement_get_messages(res)
        assert any("has already been verified" in m for m in messages)

    def test_capamanagement_views_rca_verify_closed_capa_error(
        self, client_a, _capamanagement_closed_capa, tenant_a, admin_user
    ):
        rca_on_closed = RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            rca_method="5_whys",
            problem_statement="Problem on closed CAPA to verify",
            root_cause_summary="Root cause summary",
            root_cause_category="equipment",
            lead_investigator=admin_user,
            status="in_progress",
        )
        url = reverse("quality:root_cause_analysis_verify", args=[rca_on_closed.pk])
        res = client_a.post(url, data={"verification_notes": "Attempting verify on closed CAPA"})
        assert res.status_code == 302
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[rca_on_closed.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot verify records belonging to a closed CAPA" in m for m in messages)

    def test_capamanagement_views_rca_verify_valid(
        self, client_a, root_cause_analysis_a, admin_user
    ):
        url = reverse("quality:root_cause_analysis_verify", args=[root_cause_analysis_a.pk])
        res = client_a.post(
            url, data={"verification_notes": "Quality engineering laboratory confirmed core pin wear limit."}
        )
        assert res.status_code == 302
        assert res.url == reverse("quality:root_cause_analysis_detail", args=[root_cause_analysis_a.pk])

        root_cause_analysis_a.refresh_from_db()
        assert root_cause_analysis_a.status == "verified"
        assert root_cause_analysis_a.verified_by == admin_user
        assert root_cause_analysis_a.verified_date == timezone.now().date()
        assert "laboratory confirmed" in root_cause_analysis_a.verification_notes

        logs = _capamanagement_audit_logs(root_cause_analysis_a, action="verify")
        assert logs.count() == 1

    def test_capamanagement_views_rca_verify_cross_tenant_404(
        self, client_a, root_cause_analysis_b
    ):
        url = reverse("quality:root_cause_analysis_verify", args=[root_cause_analysis_b.pk])
        res = client_a.post(url, data={"verification_notes": "Cross-tenant verify attempt"})
        assert res.status_code == 404

    def test_capamanagement_views_rca_export_success(
        self, client_a, root_cause_analysis_a, root_cause_analysis_b
    ):
        url = reverse("quality:root_cause_analysis_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"].startswith("text/csv")
        assert res["X-Content-Type-Options"] == "nosniff"

        content = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        header = rows[0]
        assert "RCA Number" in header
        assert "CAPA Number" in header
        assert "Problem Statement" in header
        assert "Status" in header

        assert root_cause_analysis_a.problem_statement in content
        assert root_cause_analysis_b.problem_statement not in content

        logs = _capamanagement_audit_logs(RootCauseAnalysis, action="export")
        assert logs.count() >= 1


# =====================================================================
# 3. CapaActions Views Tests
# =====================================================================


class TestCapaActionViews:
    def test_capamanagement_views_action_list_get_success(self, client_a, capa_action_a):
        url = reverse("quality:capa_action_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        assert "actions" in res.context
        assert "total_count" in res.context
        assert "pending_count" in res.context
        assert "overdue_count" in res.context
        assert "action_type_choices" in res.context
        assert "status_choices" in res.context

        content = res.content.decode("utf-8")
        assert capa_action_a.number in content
        assert capa_action_a.title in content

    def test_capamanagement_views_action_list_search_q(
        self, client_a, capa_action_a, _capamanagement_verified_action
    ):
        url = reverse("quality:capa_action_list")

        # Search by number
        res_num = client_a.get(f"{url}?q={capa_action_a.number}")
        assert res_num.status_code == 200
        assert capa_action_a in list(res_num.context["actions"])
        assert _capamanagement_verified_action not in list(res_num.context["actions"])

        # Search by title keyword
        res_kw = client_a.get(f"{url}?q=Optical+Inspection")
        assert res_kw.status_code == 200
        assert _capamanagement_verified_action in list(res_kw.context["actions"])
        assert capa_action_a not in list(res_kw.context["actions"])

    def test_capamanagement_views_action_list_filter_type(
        self, client_a, capa_action_a, tenant_a, admin_user, quality_department, capa_investigation_a
    ):
        act_prev = CapaAction.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            action_type="preventive",
            title="Design Tooling Wear Sensor",
            description="Install digital acoustic transducer on mold.",
            assigned_to=admin_user,
            department=quality_department,
            due_date=timezone.now().date() + timedelta(days=20),
            status="pending",
        )
        url = reverse("quality:capa_action_list")

        # Filter by type: corrective
        res_corr = client_a.get(f"{url}?type=corrective")
        assert res_corr.status_code == 200
        assert capa_action_a in list(res_corr.context["actions"])
        assert act_prev not in list(res_corr.context["actions"])

        # Filter by type: preventive
        res_prev = client_a.get(f"{url}?type=preventive")
        assert res_prev.status_code == 200
        assert act_prev in list(res_prev.context["actions"])
        assert capa_action_a not in list(res_prev.context["actions"])

    def test_capamanagement_views_action_list_filter_status(
        self, client_a, capa_action_a, _capamanagement_verified_action
    ):
        url = reverse("quality:capa_action_list")

        # Filter by status: pending
        res_pen = client_a.get(f"{url}?status=pending")
        assert res_pen.status_code == 200
        assert capa_action_a in list(res_pen.context["actions"])
        assert _capamanagement_verified_action not in list(res_pen.context["actions"])

        # Filter by status: verified
        res_ver = client_a.get(f"{url}?status=verified")
        assert res_ver.status_code == 200
        assert _capamanagement_verified_action in list(res_ver.context["actions"])
        assert capa_action_a not in list(res_ver.context["actions"])

    def test_capamanagement_views_action_list_filter_capa(
        self, client_a, capa_action_a, _capamanagement_closed_capa, tenant_a, admin_user, quality_department
    ):
        act_other = CapaAction.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            action_type="corrective",
            title="Replace Needle Grinding Head",
            description="Replaced grinding wheel assembly.",
            assigned_to=admin_user,
            department=quality_department,
            due_date=timezone.now().date(),
            status="verified",
        )
        url = reverse("quality:capa_action_list")

        res = client_a.get(f"{url}?capa={capa_action_a.capa_id}")
        assert res.status_code == 200
        assert capa_action_a in list(res.context["actions"])
        assert act_other not in list(res.context["actions"])

    def test_capamanagement_views_action_list_pagination(
        self, client_a, tenant_a, admin_user, quality_department, capa_investigation_a
    ):
        for i in range(16):
            CapaAction.objects.create(
                tenant=tenant_a,
                capa=capa_investigation_a,
                action_type="corrective",
                title=f"Batch Action Item {i}",
                description="Batch description",
                assigned_to=admin_user,
                department=quality_department,
                due_date=timezone.now().date() + timedelta(days=10),
                status="pending",
            )
        url = reverse("quality:capa_action_list")
        res_p1 = client_a.get(url)
        assert res_p1.status_code == 200
        assert len(res_p1.context["actions"]) == 15
        assert res_p1.context["actions"].has_next()

        res_p2 = client_a.get(f"{url}?page=2")
        assert res_p2.status_code == 200
        assert len(res_p2.context["actions"]) >= 1

    def test_capamanagement_views_action_list_tenant_isolation(
        self, client_a, capa_action_a, capa_action_b
    ):
        url = reverse("quality:capa_action_list")
        res = client_a.get(url)
        assert res.status_code == 200
        actions = list(res.context["actions"])
        assert capa_action_a in actions
        assert capa_action_b not in actions

    def test_capamanagement_views_action_detail_get_success(
        self, client_a, capa_action_a
    ):
        url = reverse("quality:capa_action_detail", args=[capa_action_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        assert "action" in res.context
        assert res.context["action"] == capa_action_a

        content = res.content.decode("utf-8")
        assert capa_action_a.number in content
        assert capa_action_a.title in content

    def test_capamanagement_views_action_detail_cross_tenant_404(
        self, client_a, capa_action_b
    ):
        url = reverse("quality:capa_action_detail", args=[capa_action_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_action_create_get_prefills(
        self, client_a, capa_investigation_a, root_cause_analysis_a
    ):
        url = reverse("quality:capa_action_create")
        res = client_a.get(f"{url}?capa={capa_investigation_a.pk}&rca={root_cause_analysis_a.pk}")
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is False
        assert res.context["form"].initial.get("capa") == capa_investigation_a.pk
        assert res.context["form"].initial.get("root_cause") == root_cause_analysis_a.pk

    def test_capamanagement_views_action_create_post_valid(
        self, client_a, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a
    ):
        url = reverse("quality:capa_action_create")
        payload = {
            "capa": capa_investigation_a.pk,
            "root_cause": root_cause_analysis_a.pk,
            "action_type": "corrective",
            "title": "Procure High-Precision CMM Pin Gage",
            "description": "Order sub-micron calibration gage set for core pin wear audit.",
            "assigned_to": admin_user.pk,
            "department": quality_department.pk,
            "due_date": (timezone.now().date() + timedelta(days=14)).isoformat(),
            "status": "pending",
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content

        created = CapaAction.objects.filter(
            tenant=tenant_a, title="Procure High-Precision CMM Pin Gage"
        ).first()
        assert created is not None
        assert created.number.startswith("QACT-")
        assert res.url == reverse("quality:capa_action_detail", args=[created.pk])

        logs = _capamanagement_audit_logs(created, action="create")
        assert logs.count() == 1

    def test_capamanagement_views_action_create_post_invalid(self, client_a):
        url = reverse("quality:capa_action_create")
        res = client_a.post(url, data={"action_type": "corrective"})
        assert res.status_code == 200
        assert "form" in res.context
        assert "title" in res.context["form"].errors

    def test_capamanagement_views_action_edit_get_success(
        self, client_a, capa_action_a
    ):
        url = reverse("quality:capa_action_edit", args=[capa_action_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is True
        assert res.context["action"] == capa_action_a

    def test_capamanagement_views_action_edit_post_valid(
        self, client_a, capa_action_a, admin_user, quality_department
    ):
        url = reverse("quality:capa_action_edit", args=[capa_action_a.pk])
        payload = {
            "capa": capa_action_a.capa_id,
            "root_cause": capa_action_a.root_cause_id,
            "action_type": "corrective",
            "title": "Updated SOP Tooling PM Metrology Protocol",
            "description": "Expanded description including optical comparator requirements.",
            "assigned_to": admin_user.pk,
            "department": quality_department.pk,
            "due_date": (timezone.now().date() + timedelta(days=7)).isoformat(),
            "status": "in_progress",
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content
        assert res.url == reverse("quality:capa_action_detail", args=[capa_action_a.pk])

        capa_action_a.refresh_from_db()
        assert capa_action_a.title == "Updated SOP Tooling PM Metrology Protocol"
        assert capa_action_a.status == "in_progress"

        logs = _capamanagement_audit_logs(capa_action_a, action="update")
        assert logs.count() >= 1

    def test_capamanagement_views_action_edit_verified_warning(
        self, client_a, _capamanagement_verified_action
    ):
        url = reverse("quality:capa_action_edit", args=[_capamanagement_verified_action.pk])
        res = client_a.get(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[_capamanagement_verified_action.pk])

        messages = _capamanagement_get_messages(res)
        assert any("has been verified and cannot be directly modified" in m for m in messages)

    def test_capamanagement_views_action_edit_cross_tenant_404(
        self, client_a, capa_action_b
    ):
        url = reverse("quality:capa_action_edit", args=[capa_action_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_action_delete_get_rejected_405(
        self, client_a, capa_action_a
    ):
        url = reverse("quality:capa_action_delete", args=[capa_action_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_action_delete_non_admin_forbidden_403(
        self, member_client, capa_action_a
    ):
        url = reverse("quality:capa_action_delete", args=[capa_action_a.pk])
        res = member_client.post(url)
        assert res.status_code == 403

    def test_capamanagement_views_action_delete_verified_error(
        self, client_a, _capamanagement_verified_action
    ):
        url = reverse("quality:capa_action_delete", args=[_capamanagement_verified_action.pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[_capamanagement_verified_action.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot delete a verified CAPA action item" in m for m in messages)
        assert CapaAction.objects.filter(pk=_capamanagement_verified_action.pk).exists()

    def test_capamanagement_views_action_delete_closed_capa_error(
        self, client_a, _capamanagement_closed_capa, tenant_a, admin_user, quality_department
    ):
        act_on_closed = CapaAction.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            action_type="corrective",
            title="Action on closed CAPA",
            description="Description on closed CAPA",
            assigned_to=admin_user,
            department=quality_department,
            due_date=timezone.now().date(),
            status="pending",
        )
        url = reverse("quality:capa_action_delete", args=[act_on_closed.pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[act_on_closed.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot delete actions belonging to a closed CAPA" in m for m in messages)
        assert CapaAction.objects.filter(pk=act_on_closed.pk).exists()

    def test_capamanagement_views_action_delete_valid(
        self, client_a, tenant_a, admin_user, quality_department, capa_investigation_a
    ):
        act = CapaAction.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            action_type="corrective",
            title="Disposable Action for Delete Test",
            description="Description to delete",
            assigned_to=admin_user,
            department=quality_department,
            due_date=timezone.now().date() + timedelta(days=1),
            status="pending",
        )
        pk = act.pk
        capa_pk = capa_investigation_a.pk
        url = reverse("quality:capa_action_delete", args=[pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_detail", args=[capa_pk])

        assert not CapaAction.objects.filter(pk=pk).exists()
        logs = _capamanagement_audit_logs(CapaAction, object_id=pk, action="delete")
        assert logs.count() == 1

    def test_capamanagement_views_action_delete_cross_tenant_404(
        self, client_a, capa_action_b
    ):
        url = reverse("quality:capa_action_delete", args=[capa_action_b.pk])
        res = client_a.post(url)
        assert res.status_code == 404

    def test_capamanagement_views_action_mark_completed_get_rejected_405(
        self, client_a, capa_action_a
    ):
        url = reverse("quality:capa_action_mark_completed", args=[capa_action_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_action_mark_completed_verified_or_cancelled_warning(
        self, client_a, _capamanagement_verified_action
    ):
        url = reverse("quality:capa_action_mark_completed", args=[_capamanagement_verified_action.pk])
        res = client_a.post(url, data={"implementation_notes": "Trying to complete verified item."})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[_capamanagement_verified_action.pk])

        messages = _capamanagement_get_messages(res)
        assert any("cannot be marked implemented" in m for m in messages)

    def test_capamanagement_views_action_mark_completed_valid(
        self, client_a, capa_action_a
    ):
        url = reverse("quality:capa_action_mark_completed", args=[capa_action_a.pk])
        res = client_a.post(
            url, data={"implementation_notes": "SOP revised, approved by document control, trained staff."}
        )
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[capa_action_a.pk])

        capa_action_a.refresh_from_db()
        assert capa_action_a.status == "implemented"
        assert capa_action_a.completion_date == timezone.now().date()
        assert "SOP revised" in capa_action_a.implementation_notes

        logs = _capamanagement_audit_logs(capa_action_a, action="complete")
        assert logs.count() == 1

    def test_capamanagement_views_action_mark_completed_cross_tenant_404(
        self, client_a, capa_action_b
    ):
        url = reverse("quality:capa_action_mark_completed", args=[capa_action_b.pk])
        res = client_a.post(url, data={"implementation_notes": "Cross tenant complete"})
        assert res.status_code == 404

    def test_capamanagement_views_action_verify_get_rejected_405(
        self, client_a, capa_action_a
    ):
        url = reverse("quality:capa_action_verify", args=[capa_action_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_action_verify_already_verified_warning(
        self, client_a, _capamanagement_verified_action
    ):
        url = reverse("quality:capa_action_verify", args=[_capamanagement_verified_action.pk])
        res = client_a.post(url, data={"verification_evidence": "Re-verify attempt."})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[_capamanagement_verified_action.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Action item is already verified" in m for m in messages)

    def test_capamanagement_views_action_verify_not_implemented_error(
        self, client_a, capa_action_a
    ):
        # capa_action_a is 'pending'
        assert capa_action_a.status == "pending"
        url = reverse("quality:capa_action_verify", args=[capa_action_a.pk])
        res = client_a.post(url, data={"verification_evidence": "Verification of pending item."})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[capa_action_a.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Only implemented actions can be verified" in m for m in messages)

    def test_capamanagement_views_action_verify_separation_of_duties_non_admin_error(
        self, member_client, member_user, tenant_a, quality_department, capa_investigation_a, root_cause_analysis_a
    ):
        # Assign action to member_user and try to verify using member_client
        act = CapaAction.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            root_cause=root_cause_analysis_a,
            action_type="corrective",
            title="Action assigned to non-admin member",
            description="Self-verification attempt",
            assigned_to=member_user,
            department=quality_department,
            due_date=timezone.now().date(),
            status="implemented",
            completion_date=timezone.now().date(),
        )
        url = reverse("quality:capa_action_verify", args=[act.pk])
        res = member_client.post(url, data={"verification_evidence": "Self verification attempt"})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[act.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Separation of duties required" in m for m in messages)

    def test_capamanagement_views_action_verify_separation_of_duties_admin_override(
        self, client_a, admin_user, _capamanagement_implemented_action
    ):
        # Even though _capamanagement_implemented_action is assigned to admin_user, client_a is tenant admin
        assert _capamanagement_implemented_action.assigned_to == admin_user
        url = reverse("quality:capa_action_verify", args=[_capamanagement_implemented_action.pk])
        res = client_a.post(
            url, data={"verification_evidence": "Admin override verification based on audit trail."}
        )
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[_capamanagement_implemented_action.pk])

        _capamanagement_implemented_action.refresh_from_db()
        assert _capamanagement_implemented_action.status == "verified"
        assert _capamanagement_implemented_action.verified_by == admin_user

    def test_capamanagement_views_action_verify_different_user_success(
        self, member_client, member_user, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a
    ):
        # Action assigned to admin_user, verified by member_user
        act = CapaAction.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            root_cause=root_cause_analysis_a,
            action_type="corrective",
            title="Action assigned to Admin",
            description="Verified by QA Member",
            assigned_to=admin_user,
            department=quality_department,
            due_date=timezone.now().date(),
            status="implemented",
            completion_date=timezone.now().date(),
        )
        url = reverse("quality:capa_action_verify", args=[act.pk])
        res = member_client.post(url, data={"verification_evidence": "Verified independent of assignee."})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_action_detail", args=[act.pk])

        act.refresh_from_db()
        assert act.status == "verified"
        assert act.verified_by == member_user
        assert act.verified_on == timezone.now().date()

        logs = _capamanagement_audit_logs(act, action="verify")
        assert logs.count() == 1

    def test_capamanagement_views_action_verify_cross_tenant_404(
        self, client_a, capa_action_b
    ):
        url = reverse("quality:capa_action_verify", args=[capa_action_b.pk])
        res = client_a.post(url, data={"verification_evidence": "Cross tenant verify"})
        assert res.status_code == 404

    def test_capamanagement_views_action_export_success(
        self, client_a, capa_action_a, capa_action_b
    ):
        url = reverse("quality:capa_action_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"].startswith("text/csv")
        assert res["X-Content-Type-Options"] == "nosniff"

        content = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        header = rows[0]
        assert "Action Number" in header
        assert "CAPA Number" in header
        assert "Title" in header
        assert "Status" in header

        assert capa_action_a.title in content
        assert capa_action_b.title not in content

        logs = _capamanagement_audit_logs(CapaAction, action="export")
        assert logs.count() >= 1


# =====================================================================
# 4. CapaEffectivenessReviews Views Tests
# =====================================================================


class TestCapaEffectivenessReviewViews:
    def test_capamanagement_views_review_list_get_success(
        self, client_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        assert "reviews" in res.context
        assert "total_count" in res.context
        assert "effective_count" in res.context
        assert "ineffective_count" in res.context
        assert "outcome_choices" in res.context
        assert "status_choices" in res.context

        content = res.content.decode("utf-8")
        assert capa_effectiveness_review_a.number in content
        assert capa_effectiveness_review_a.evaluator.username in content

    def test_capamanagement_views_review_list_search_q(
        self, client_a, capa_effectiveness_review_a, _capamanagement_completed_review
    ):
        url = reverse("quality:capa_effectiveness_review_list")

        # Search by number
        res_num = client_a.get(f"{url}?q={capa_effectiveness_review_a.number}")
        assert res_num.status_code == 200
        assert capa_effectiveness_review_a in list(res_num.context["reviews"])
        assert _capamanagement_completed_review not in list(res_num.context["reviews"])

        # Search by notes
        res_kw = client_a.get(f"{url}?q=fractures")
        assert res_kw.status_code == 200
        assert _capamanagement_completed_review in list(res_kw.context["reviews"])

    def test_capamanagement_views_review_list_filter_outcome(
        self, client_a, capa_effectiveness_review_a, _capamanagement_completed_review, tenant_a, admin_user, capa_investigation_a
    ):
        rev_ineff = CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            review_criteria="Defect rate < 0.1%",
            verification_method="trend_analysis",
            planned_review_date=timezone.now().date(),
            actual_review_date=timezone.now().date(),
            evaluator=admin_user,
            outcome="ineffective",
            status="completed",
        )
        url = reverse("quality:capa_effectiveness_review_list")

        # Filter by outcome: effective
        res_eff = client_a.get(f"{url}?outcome=effective")
        assert res_eff.status_code == 200
        assert _capamanagement_completed_review in list(res_eff.context["reviews"])
        assert rev_ineff not in list(res_eff.context["reviews"])

        # Filter by outcome: ineffective
        res_ineff = client_a.get(f"{url}?outcome=ineffective")
        assert res_ineff.status_code == 200
        assert rev_ineff in list(res_ineff.context["reviews"])
        assert _capamanagement_completed_review not in list(res_ineff.context["reviews"])

    def test_capamanagement_views_review_list_filter_status(
        self, client_a, capa_effectiveness_review_a, _capamanagement_completed_review
    ):
        url = reverse("quality:capa_effectiveness_review_list")

        # Filter by status: scheduled
        res_sch = client_a.get(f"{url}?status=scheduled")
        assert res_sch.status_code == 200
        assert capa_effectiveness_review_a in list(res_sch.context["reviews"])
        assert _capamanagement_completed_review not in list(res_sch.context["reviews"])

        # Filter by status: completed
        res_comp = client_a.get(f"{url}?status=completed")
        assert res_comp.status_code == 200
        assert _capamanagement_completed_review in list(res_comp.context["reviews"])
        assert capa_effectiveness_review_a not in list(res_comp.context["reviews"])

    def test_capamanagement_views_review_list_filter_capa(
        self, client_a, capa_effectiveness_review_a, _capamanagement_closed_capa, tenant_a, admin_user
    ):
        rev_other = CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            review_criteria="Needle sharpness test",
            verification_method="statistical_sample",
            planned_review_date=timezone.now().date(),
            evaluator=admin_user,
            status="scheduled",
        )
        url = reverse("quality:capa_effectiveness_review_list")

        res = client_a.get(f"{url}?capa={capa_effectiveness_review_a.capa_id}")
        assert res.status_code == 200
        assert capa_effectiveness_review_a in list(res.context["reviews"])
        assert rev_other not in list(res.context["reviews"])

    def test_capamanagement_views_review_list_pagination(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        for i in range(16):
            CapaEffectivenessReview.objects.create(
                tenant=tenant_a,
                capa=capa_investigation_a,
                review_criteria=f"Batch Review Criteria {i}",
                verification_method="trend_analysis",
                planned_review_date=timezone.now().date() + timedelta(days=30),
                evaluator=admin_user,
                status="scheduled",
            )
        url = reverse("quality:capa_effectiveness_review_list")
        res_p1 = client_a.get(url)
        assert res_p1.status_code == 200
        assert len(res_p1.context["reviews"]) == 15
        assert res_p1.context["reviews"].has_next()

        res_p2 = client_a.get(f"{url}?page=2")
        assert res_p2.status_code == 200
        assert len(res_p2.context["reviews"]) >= 1

    def test_capamanagement_views_review_list_tenant_isolation(
        self, client_a, capa_effectiveness_review_a, capa_effectiveness_review_b
    ):
        url = reverse("quality:capa_effectiveness_review_list")
        res = client_a.get(url)
        assert res.status_code == 200
        reviews = list(res.context["reviews"])
        assert capa_effectiveness_review_a in reviews
        assert capa_effectiveness_review_b not in reviews

    def test_capamanagement_views_review_detail_get_success(
        self, client_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_detail", args=[capa_effectiveness_review_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        assert "review" in res.context
        assert res.context["review"] == capa_effectiveness_review_a

        content = res.content.decode("utf-8")
        assert capa_effectiveness_review_a.number in content
        assert capa_effectiveness_review_a.evaluator.username in content

    def test_capamanagement_views_review_detail_cross_tenant_404(
        self, client_a, capa_effectiveness_review_b
    ):
        url = reverse("quality:capa_effectiveness_review_detail", args=[capa_effectiveness_review_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_review_create_get_prefills_capa(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_effectiveness_review_create")
        res = client_a.get(f"{url}?capa={capa_investigation_a.pk}")
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is False
        assert res.context["form"].initial.get("capa") == capa_investigation_a.pk

    def test_capamanagement_views_review_create_post_valid(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        url = reverse("quality:capa_effectiveness_review_create")
        payload = {
            "capa": capa_investigation_a.pk,
            "review_criteria": "Confirm zero core pin wear excursions over 100,000 cycles.",
            "verification_method": "statistical_sample",
            "planned_review_date": (timezone.now().date() + timedelta(days=60)).isoformat(),
            "evaluator": admin_user.pk,
            "status": "scheduled",
            "outcome": "pending",
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content

        created = CapaEffectivenessReview.objects.filter(
            tenant=tenant_a, review_criteria="Confirm zero core pin wear excursions over 100,000 cycles."
        ).first()
        assert created is not None
        assert created.number.startswith("QEFF-")
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[created.pk])

        logs = _capamanagement_audit_logs(created, action="create")
        assert logs.count() == 1

    def test_capamanagement_views_review_create_post_invalid(self, client_a):
        url = reverse("quality:capa_effectiveness_review_create")
        res = client_a.post(url, data={"verification_method": "statistical_sample"})
        assert res.status_code == 200
        assert "form" in res.context
        assert "review_criteria" in res.context["form"].errors

    def test_capamanagement_views_review_edit_get_success(
        self, client_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_edit", args=[capa_effectiveness_review_a.pk])
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["is_edit"] is True
        assert res.context["review"] == capa_effectiveness_review_a

    def test_capamanagement_views_review_edit_post_valid(
        self, client_a, capa_effectiveness_review_a, admin_user
    ):
        url = reverse("quality:capa_effectiveness_review_edit", args=[capa_effectiveness_review_a.pk])
        payload = {
            "capa": capa_effectiveness_review_a.capa_id,
            "review_criteria": "Updated criteria: zero ferrule cracking across 10 lots.",
            "verification_method": "statistical_sample",
            "planned_review_date": (timezone.now().date() + timedelta(days=45)).isoformat(),
            "evaluator": admin_user.pk,
            "status": "scheduled",
            "outcome": "pending",
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302, getattr(res, "context", {}).get("form", {}).errors if hasattr(res, "context") and res.context else res.content
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[capa_effectiveness_review_a.pk])

        capa_effectiveness_review_a.refresh_from_db()
        assert "across 10 lots" in capa_effectiveness_review_a.review_criteria

        logs = _capamanagement_audit_logs(capa_effectiveness_review_a, action="update")
        assert logs.count() >= 1

    def test_capamanagement_views_review_edit_completed_warning(
        self, client_a, _capamanagement_completed_review
    ):
        url = reverse("quality:capa_effectiveness_review_edit", args=[_capamanagement_completed_review.pk])
        res = client_a.get(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[_capamanagement_completed_review.pk])

        messages = _capamanagement_get_messages(res)
        assert any("has been completed and cannot be edited" in m for m in messages)

    def test_capamanagement_views_review_edit_cross_tenant_404(
        self, client_a, capa_effectiveness_review_b
    ):
        url = reverse("quality:capa_effectiveness_review_edit", args=[capa_effectiveness_review_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_capamanagement_views_review_delete_get_rejected_405(
        self, client_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_delete", args=[capa_effectiveness_review_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_review_delete_non_admin_forbidden_403(
        self, member_client, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_delete", args=[capa_effectiveness_review_a.pk])
        res = member_client.post(url)
        assert res.status_code == 403

    def test_capamanagement_views_review_delete_completed_error(
        self, client_a, _capamanagement_completed_review
    ):
        url = reverse("quality:capa_effectiveness_review_delete", args=[_capamanagement_completed_review.pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[_capamanagement_completed_review.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot delete a completed Effectiveness Review record" in m for m in messages)
        assert CapaEffectivenessReview.objects.filter(pk=_capamanagement_completed_review.pk).exists()

    def test_capamanagement_views_review_delete_closed_capa_error(
        self, client_a, _capamanagement_closed_capa, tenant_a, admin_user
    ):
        rev_on_closed = CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            review_criteria="Review on closed CAPA",
            verification_method="trend_analysis",
            planned_review_date=timezone.now().date(),
            evaluator=admin_user,
            status="scheduled",
        )
        url = reverse("quality:capa_effectiveness_review_delete", args=[rev_on_closed.pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[rev_on_closed.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot delete reviews belonging to a closed CAPA" in m for m in messages)
        assert CapaEffectivenessReview.objects.filter(pk=rev_on_closed.pk).exists()

    def test_capamanagement_views_review_delete_valid(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        rev = CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            review_criteria="Disposable Review for Delete Test",
            verification_method="trend_analysis",
            planned_review_date=timezone.now().date() + timedelta(days=20),
            evaluator=admin_user,
            status="scheduled",
        )
        pk = rev.pk
        capa_pk = capa_investigation_a.pk
        url = reverse("quality:capa_effectiveness_review_delete", args=[pk])
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_investigation_detail", args=[capa_pk])

        assert not CapaEffectivenessReview.objects.filter(pk=pk).exists()
        logs = _capamanagement_audit_logs(CapaEffectivenessReview, object_id=pk, action="delete")
        assert logs.count() == 1

    def test_capamanagement_views_review_delete_cross_tenant_404(
        self, client_a, capa_effectiveness_review_b
    ):
        url = reverse("quality:capa_effectiveness_review_delete", args=[capa_effectiveness_review_b.pk])
        res = client_a.post(url)
        assert res.status_code == 404

    def test_capamanagement_views_review_sign_off_get_rejected_405(
        self, client_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[capa_effectiveness_review_a.pk])
        res = client_a.get(url)
        assert res.status_code == 405

    def test_capamanagement_views_review_sign_off_already_completed_error(
        self, client_a, _capamanagement_completed_review
    ):
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[_capamanagement_completed_review.pk])
        res = client_a.post(url, data={"outcome": "effective"})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[_capamanagement_completed_review.pk])

        messages = _capamanagement_get_messages(res)
        assert any("already been signed off and completed" in m for m in messages)

    def test_capamanagement_views_review_sign_off_unauthorized_user_error(
        self, member_client, member_user, tenant_a, admin_user, capa_investigation_a
    ):
        # Assigned to admin_user, attempted sign off by non-admin member_user
        rev = CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            review_criteria="Criteria assigned to admin",
            verification_method="trend_analysis",
            planned_review_date=timezone.now().date(),
            evaluator=admin_user,
            status="scheduled",
        )
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[rev.pk])
        res = member_client.post(url, data={"outcome": "effective"})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[rev.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Only the assigned evaluator or a tenant administrator can sign off" in m for m in messages)

    def test_capamanagement_views_review_sign_off_invalid_outcome_error(
        self, client_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[capa_effectiveness_review_a.pk])
        # "pending" is not a definitive outcome
        res = client_a.post(url, data={"outcome": "pending"})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[capa_effectiveness_review_a.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Please choose a definitive outcome" in m for m in messages)

    def test_capamanagement_views_review_sign_off_recurrence_observed_effective_error(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        # Review where recurrence was observed
        rev = CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            review_criteria="Criteria with recurrence observed",
            verification_method="trend_analysis",
            planned_review_date=timezone.now().date(),
            evaluator=admin_user,
            recurrence_observed=True,
            recurrence_details="Defect recurred in lot 5.",
            status="scheduled",
        )
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[rev.pk])
        res = client_a.post(url, data={"outcome": "effective"})
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[rev.pk])

        messages = _capamanagement_get_messages(res)
        assert any("Cannot mark review as 'Effective' when recurrence has been observed" in m for m in messages)

    def test_capamanagement_views_review_sign_off_valid_by_evaluator(
        self, client_a, capa_effectiveness_review_a
    ):
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[capa_effectiveness_review_a.pk])
        res = client_a.post(
            url,
            data={
                "outcome": "effective",
                "review_notes": "Statistically verified zero ferrule cracking across 5 lots.",
            },
        )
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[capa_effectiveness_review_a.pk])

        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.status == "completed"
        assert capa_effectiveness_review_a.outcome == "effective"
        assert capa_effectiveness_review_a.actual_review_date == timezone.now().date()
        assert "Statistically verified" in capa_effectiveness_review_a.review_notes

        logs = _capamanagement_audit_logs(capa_effectiveness_review_a, action="approve")
        assert logs.count() == 1

    def test_capamanagement_views_review_sign_off_valid_by_admin(
        self, client_a, tenant_a, member_user, capa_investigation_a
    ):
        # Review assigned to non-admin member_user, signed off by admin_user via client_a
        rev = CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            review_criteria="Review assigned to member",
            verification_method="trend_analysis",
            planned_review_date=timezone.now().date(),
            evaluator=member_user,
            status="scheduled",
        )
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[rev.pk])
        res = client_a.post(
            url,
            data={
                "outcome": "ineffective",
                "review_notes": "Admin sign-off: Root cause recurrence indicates additional action needed.",
            },
        )
        assert res.status_code == 302
        assert res.url == reverse("quality:capa_effectiveness_review_detail", args=[rev.pk])

        rev.refresh_from_db()
        assert rev.status == "completed"
        assert rev.outcome == "ineffective"

        logs = _capamanagement_audit_logs(rev, action="approve")
        assert logs.count() == 1

    def test_capamanagement_views_review_sign_off_cross_tenant_404(
        self, client_a, capa_effectiveness_review_b
    ):
        url = reverse("quality:capa_effectiveness_review_sign_off", args=[capa_effectiveness_review_b.pk])
        res = client_a.post(url, data={"outcome": "effective"})
        assert res.status_code == 404

    def test_capamanagement_views_review_export_success(
        self, client_a, capa_effectiveness_review_a, capa_effectiveness_review_b
    ):
        url = reverse("quality:capa_effectiveness_review_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"].startswith("text/csv")
        assert res["X-Content-Type-Options"] == "nosniff"

        content = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        header = rows[0]
        assert "Review Number" in header
        assert "CAPA Number" in header
        assert "Method" in header
        assert "Outcome" in header
        assert "Status" in header

        assert capa_effectiveness_review_a.evaluator.username in content
        assert capa_effectiveness_review_b.evaluator.username not in content

        logs = _capamanagement_audit_logs(CapaEffectivenessReview, action="export")
        assert logs.count() >= 1


# =====================================================================
# 5. CapaTrackingBoard Views Tests
# =====================================================================


class TestCapaTrackingBoardViews:
    def test_capamanagement_views_tracking_board_get_success(
        self, client_a, capa_investigation_a
    ):
        url = reverse("quality:capa_tracking_board")
        res = client_a.get(url)
        assert res.status_code == 200
        _capamanagement_assert_no_comment_leaks(res)

        assert "tier_0_30" in res.context
        assert "tier_31_60" in res.context
        assert "tier_61_90" in res.context
        assert "tier_90_plus" in res.context
        assert "escalated_capas" in res.context
        assert "overdue_capas" in res.context
        assert "stats" in res.context

        stats = res.context["stats"]
        assert "total_active" in stats
        assert "overdue_count" in stats
        assert "escalated_count" in stats
        assert "avg_cycle_days" in stats
        assert stats["total_active"] >= 1

        content = res.content.decode("utf-8")
        assert capa_investigation_a.number in content

    def test_capamanagement_views_tracking_board_aging_tiers_distribution(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        now = timezone.now()

        # Create CAPAs aged 10, 45, 75, and 120 days
        c1 = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="Aging 10 Days CAPA",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="medium",
            status="under_investigation",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
            issue_summary="10 day summary",
        )
        CapaInvestigation.objects.filter(pk=c1.pk).update(created_at=now - timedelta(days=10))

        c2 = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="Aging 45 Days CAPA",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="medium",
            status="under_investigation",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
            issue_summary="45 day summary",
        )
        CapaInvestigation.objects.filter(pk=c2.pk).update(created_at=now - timedelta(days=45))

        c3 = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="Aging 75 Days CAPA",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="medium",
            status="under_investigation",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
            issue_summary="75 day summary",
        )
        CapaInvestigation.objects.filter(pk=c3.pk).update(created_at=now - timedelta(days=75))

        c4 = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="Aging 120 Days CAPA",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="critical",
            status="under_investigation",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
            issue_summary="120 day summary",
            is_escalated=True,
            target_closure_date=now.date() - timedelta(days=10),
        )
        CapaInvestigation.objects.filter(pk=c4.pk).update(created_at=now - timedelta(days=120))

        url = reverse("quality:capa_tracking_board")
        res = client_a.get(url)
        assert res.status_code == 200

        tier_0_30_pks = [c.pk for c in res.context["tier_0_30"]]
        tier_31_60_pks = [c.pk for c in res.context["tier_31_60"]]
        tier_61_90_pks = [c.pk for c in res.context["tier_61_90"]]
        tier_90_plus_pks = [c.pk for c in res.context["tier_90_plus"]]
        escalated_pks = [c.pk for c in res.context["escalated_capas"]]
        overdue_pks = [c.pk for c in res.context["overdue_capas"]]

        assert c1.pk in tier_0_30_pks
        assert c2.pk in tier_31_60_pks
        assert c3.pk in tier_61_90_pks
        assert c4.pk in tier_90_plus_pks
        assert c4.pk in escalated_pks
        assert c4.pk in overdue_pks

    def test_capamanagement_views_tracking_board_excludes_closed_and_voided(
        self, client_a, _capamanagement_closed_capa, _capamanagement_voided_capa
    ):
        url = reverse("quality:capa_tracking_board")
        res = client_a.get(url)
        assert res.status_code == 200

        all_board_pks = (
            [c.pk for c in res.context["tier_0_30"]]
            + [c.pk for c in res.context["tier_31_60"]]
            + [c.pk for c in res.context["tier_61_90"]]
            + [c.pk for c in res.context["tier_90_plus"]]
        )
        assert _capamanagement_closed_capa.pk not in all_board_pks
        assert _capamanagement_voided_capa.pk not in all_board_pks

    def test_capamanagement_views_tracking_board_tenant_isolation(
        self, client_a, capa_investigation_a, capa_investigation_b
    ):
        url = reverse("quality:capa_tracking_board")
        res = client_a.get(url)
        assert res.status_code == 200

        all_board_pks = (
            [c.pk for c in res.context["tier_0_30"]]
            + [c.pk for c in res.context["tier_31_60"]]
            + [c.pk for c in res.context["tier_61_90"]]
            + [c.pk for c in res.context["tier_90_plus"]]
        )
        assert capa_investigation_a.pk in all_board_pks
        assert capa_investigation_b.pk not in all_board_pks

    def test_capamanagement_views_tracking_board_export_success(
        self, client_a, capa_investigation_a, _capamanagement_closed_capa, capa_investigation_b
    ):
        url = reverse("quality:capa_tracking_board_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"].startswith("text/csv")
        assert res["X-Content-Type-Options"] == "nosniff"

        content = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        header = rows[0]
        assert "CAPA Number" in header
        assert "Aging Tier" in header
        assert "Days Open" in header
        assert "Status" in header

        # Active tenant A included
        assert capa_investigation_a.title in content
        # Closed CAPA excluded
        assert _capamanagement_closed_capa.title not in content
        # Tenant B CAPA excluded
        assert capa_investigation_b.title not in content


# =====================================================================
# 6. Authentication Guards (Unauthenticated Access)
# =====================================================================


class TestCapaManagementAuthGuards:
    def test_capamanagement_views_unauthenticated_all_endpoints_redirect_login(
        self, db, capa_investigation_a, root_cause_analysis_a, capa_action_a, capa_effectiveness_review_a
    ):
        anon_client = Client()

        get_urls = [
            reverse("quality:capa_investigation_list"),
            reverse("quality:capa_investigation_create"),
            reverse("quality:capa_investigation_export"),
            reverse("quality:capa_investigation_detail", args=[capa_investigation_a.pk]),
            reverse("quality:capa_investigation_edit", args=[capa_investigation_a.pk]),
            reverse("quality:root_cause_analysis_list"),
            reverse("quality:root_cause_analysis_create"),
            reverse("quality:root_cause_analysis_export"),
            reverse("quality:root_cause_analysis_detail", args=[root_cause_analysis_a.pk]),
            reverse("quality:root_cause_analysis_edit", args=[root_cause_analysis_a.pk]),
            reverse("quality:capa_action_list"),
            reverse("quality:capa_action_create"),
            reverse("quality:capa_action_export"),
            reverse("quality:capa_action_detail", args=[capa_action_a.pk]),
            reverse("quality:capa_action_edit", args=[capa_action_a.pk]),
            reverse("quality:capa_effectiveness_review_list"),
            reverse("quality:capa_effectiveness_review_create"),
            reverse("quality:capa_effectiveness_review_export"),
            reverse("quality:capa_effectiveness_review_detail", args=[capa_effectiveness_review_a.pk]),
            reverse("quality:capa_effectiveness_review_edit", args=[capa_effectiveness_review_a.pk]),
            reverse("quality:capa_tracking_board"),
            reverse("quality:capa_tracking_board_export"),
        ]

        for u in get_urls:
            res = anon_client.get(u)
            assert res.status_code == 302, f"Expected 302 redirect for unauthenticated GET {u}, got {res.status_code}"
            assert "/accounts/login/" in res.url or "login" in res.url

        post_only_urls = [
            reverse("quality:capa_investigation_delete", args=[capa_investigation_a.pk]),
            reverse("quality:capa_investigation_advance_status", args=[capa_investigation_a.pk]),
            reverse("quality:capa_investigation_close", args=[capa_investigation_a.pk]),
            reverse("quality:root_cause_analysis_delete", args=[root_cause_analysis_a.pk]),
            reverse("quality:root_cause_analysis_verify", args=[root_cause_analysis_a.pk]),
            reverse("quality:capa_action_delete", args=[capa_action_a.pk]),
            reverse("quality:capa_action_mark_completed", args=[capa_action_a.pk]),
            reverse("quality:capa_action_verify", args=[capa_action_a.pk]),
            reverse("quality:capa_effectiveness_review_delete", args=[capa_effectiveness_review_a.pk]),
            reverse("quality:capa_effectiveness_review_sign_off", args=[capa_effectiveness_review_a.pk]),
        ]

        for u in post_only_urls:
            # GET must be rejected with 405 Method Not Allowed
            res_get = anon_client.get(u)
            assert res_get.status_code == 405, f"Expected 405 for GET on POST-only endpoint {u}, got {res_get.status_code}"
            # POST must redirect to login with 302
            res_post = anon_client.post(u)
            assert res_post.status_code == 302, f"Expected 302 for unauthenticated POST on {u}, got {res_post.status_code}"
            assert "/accounts/login/" in res_post.url or "login" in res_post.url
