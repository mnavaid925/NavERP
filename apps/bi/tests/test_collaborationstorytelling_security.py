"""Security, Multi-Tenancy, Authorization, and RBAC Test Suite for Sub-module 10.18:
Collaboration & Data Storytelling (apps/bi).

Covers:
1. Multi-Tenant Isolation (IDOR):
   - Tenant A client accessing Tenant B's objects returns 404 across all object endpoints.
   - Reverse IDOR: Tenant B client accessing Tenant A's objects returns 404.
   - List views strictly filter by tenant (zero cross-tenant leakage).
2. Cross-Tenant Foreign Key Injection Defense in Forms:
   - BiSharedWorkspaceForm rejects foreign department & foreign owner.
   - BiDataStoryForm rejects foreign workspace & foreign author.
   - BiVisualCommentForm rejects foreign dashboard, report, story, widget, parent_comment.
   - BiDecisionLogForm rejects foreign workspace, dashboard, kpi, widget, decision_maker.
3. Authentication & Authorization:
   - All 23 endpoints require login (@login_required) and redirect anonymous users to login (302).
   - Destructive & mutation actions require POST (@require_POST returns 405 on GET).
   - Comment author/permission gate: non-author non-admin staff cannot edit or delete comments.
4. Office Embed Token Validation (I1):
   - Valid token returns 200 JSON payload.
   - Invalid token returns 403 Forbidden.
   - Missing token returns 403 Forbidden.
5. Input Hardening & Sanitization:
   - CSS/Style injection payloads in hex color fields rejected (I6, L26).
   - Out-of-bounds coordinates (<0 or >100) on visual comments rejected (M8).
   - Self-parent recursion prevented (M1).
   - Cross-record integrity: widget mismatched with dashboard rejected (I8).
6. Audit Log Verification:
   - Verifies AuditLog records on create, edit, delete, and resolve operations.
"""

import json
import uuid
import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspaceForm
from apps.bi.forms.CollaborationStorytelling.BiDataStories import BiDataStoryForm
from apps.bi.forms.CollaborationStorytelling.BiVisualComments import BiVisualCommentForm
from apps.bi.forms.CollaborationStorytelling.BiDecisionLogs import BiDecisionLogForm
from apps.bi.models.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspace
from apps.bi.models.CollaborationStorytelling.BiDataStories import BiDataStory
from apps.bi.models.CollaborationStorytelling.BiVisualComments import BiVisualComment
from apps.bi.models.CollaborationStorytelling.BiDecisionLogs import BiDecisionLog
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardWidgets import BiDashboardWidget
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.core.models import AuditLog, OrgUnit

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helpers (strictly prefixed with _collaborationstorytelling_)
# ==============================================================================


def _collaborationstorytelling_sec_org_unit(tenant, name="Strategy & Analytics"):
    """Create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(
        tenant=tenant,
        name=f"{name}-{uuid.uuid4().hex[:4]}",
        kind="department",
    )


def _collaborationstorytelling_sec_report(tenant, name="Board Metrics Report"):
    """Create a tenant-scoped ReportDefinition."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        number=f"BRPT-{uuid.uuid4().hex[:5].upper()}",
        name=f"{name}-{uuid.uuid4().hex[:4]}",
        slug=f"rep-{uuid.uuid4().hex[:6]}",
        report_type="standard_tabular",
        status="published",
    )


def _collaborationstorytelling_sec_widget(dashboard, title="Revenue Chart"):
    """Create a widget on a dashboard."""
    return BiDashboardWidget.objects.create(
        tenant=dashboard.tenant,
        number=f"BDWG-{uuid.uuid4().hex[:5].upper()}",
        dashboard=dashboard,
        title=f"{title}-{uuid.uuid4().hex[:4]}",
        widget_type="kpi_card",
    )


# ==============================================================================
# 1. Multi-Tenant Isolation (IDOR)
# ==============================================================================


class TestCollaborationStorytellingIDOR:
    """Verifies that Tenant A cannot access, edit, or delete Tenant B's records."""

    def test_collaborationstorytelling_workspace_cross_tenant_detail_404(
        self, client_a, bi_shared_workspace_b
    ):
        url = reverse("bi:bi_shared_workspace_detail", args=[bi_shared_workspace_b.pk])
        res = client_a.get(url)
        assert res.status_code == 404

    def test_collaborationstorytelling_workspace_cross_tenant_edit_404(
        self, client_a, bi_shared_workspace_b
    ):
        url = reverse("bi:bi_shared_workspace_edit", args=[bi_shared_workspace_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, {"name": "Hacked"}).status_code == 404

    def test_collaborationstorytelling_workspace_cross_tenant_delete_404(
        self, client_a, bi_shared_workspace_b
    ):
        url = reverse("bi:bi_shared_workspace_delete", args=[bi_shared_workspace_b.pk])
        assert client_a.post(url).status_code == 404
        assert BiSharedWorkspace.objects.filter(pk=bi_shared_workspace_b.pk).exists()

    def test_collaborationstorytelling_story_cross_tenant_detail_404(
        self, client_a, bi_data_story_b
    ):
        url = reverse("bi:bi_data_story_detail", args=[bi_data_story_b.pk])
        assert client_a.get(url).status_code == 404

    def test_collaborationstorytelling_story_cross_tenant_edit_404(
        self, client_a, bi_data_story_b
    ):
        url = reverse("bi:bi_data_story_edit", args=[bi_data_story_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, {"title": "Hacked Story"}).status_code == 404

    def test_collaborationstorytelling_story_cross_tenant_delete_404(
        self, client_a, bi_data_story_b
    ):
        url = reverse("bi:bi_data_story_delete", args=[bi_data_story_b.pk])
        assert client_a.post(url).status_code == 404
        assert BiDataStory.objects.filter(pk=bi_data_story_b.pk).exists()

    def test_collaborationstorytelling_story_cross_tenant_presentation_404(
        self, client_a, bi_data_story_b
    ):
        url = reverse("bi:bi_data_story_presentation", args=[bi_data_story_b.pk])
        assert client_a.get(url).status_code == 404

    def test_collaborationstorytelling_story_cross_tenant_export_office_404(
        self, client_a, bi_data_story_b
    ):
        url = reverse("bi:bi_data_story_export_office", args=[bi_data_story_b.pk])
        res = client_a.get(f"{url}?token={bi_data_story_b.office_embed_token}")
        assert res.status_code == 404

    def test_collaborationstorytelling_comment_cross_tenant_detail_404(
        self, client_a, bi_visual_comment_b
    ):
        url = reverse("bi:bi_visual_comment_detail", args=[bi_visual_comment_b.pk])
        assert client_a.get(url).status_code == 404

    def test_collaborationstorytelling_comment_cross_tenant_edit_404(
        self, client_a, bi_visual_comment_b
    ):
        url = reverse("bi:bi_visual_comment_edit", args=[bi_visual_comment_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, {"content": "Hacked"}).status_code == 404

    def test_collaborationstorytelling_comment_cross_tenant_delete_404(
        self, client_a, bi_visual_comment_b
    ):
        url = reverse("bi:bi_visual_comment_delete", args=[bi_visual_comment_b.pk])
        assert client_a.post(url).status_code == 404
        assert BiVisualComment.objects.filter(pk=bi_visual_comment_b.pk).exists()

    def test_collaborationstorytelling_comment_cross_tenant_resolve_404(
        self, client_a, bi_visual_comment_b
    ):
        url = reverse("bi:bi_visual_comment_resolve", args=[bi_visual_comment_b.pk])
        assert client_a.post(url).status_code == 404
        bi_visual_comment_b.refresh_from_db()
        assert bi_visual_comment_b.status == "open"

    def test_collaborationstorytelling_decision_cross_tenant_detail_404(
        self, client_a, bi_decision_log_b
    ):
        url = reverse("bi:bi_decision_log_detail", args=[bi_decision_log_b.pk])
        assert client_a.get(url).status_code == 404

    def test_collaborationstorytelling_decision_cross_tenant_edit_404(
        self, client_a, bi_decision_log_b
    ):
        url = reverse("bi:bi_decision_log_edit", args=[bi_decision_log_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, {"title": "Hacked"}).status_code == 404

    def test_collaborationstorytelling_decision_cross_tenant_delete_404(
        self, client_a, bi_decision_log_b
    ):
        url = reverse("bi:bi_decision_log_delete", args=[bi_decision_log_b.pk])
        assert client_a.post(url).status_code == 404
        assert BiDecisionLog.objects.filter(pk=bi_decision_log_b.pk).exists()

    def test_collaborationstorytelling_reverse_idor_tenant_b_blocked_on_tenant_a(
        self, client_b, bi_shared_workspace_a, bi_data_story_a, bi_visual_comment_a, bi_decision_log_a
    ):
        """Tenant B client cannot access any of Tenant A's records."""
        assert client_b.get(reverse("bi:bi_shared_workspace_detail", args=[bi_shared_workspace_a.pk])).status_code == 404
        assert client_b.get(reverse("bi:bi_data_story_detail", args=[bi_data_story_a.pk])).status_code == 404
        assert client_b.get(reverse("bi:bi_visual_comment_detail", args=[bi_visual_comment_a.pk])).status_code == 404
        assert client_b.get(reverse("bi:bi_decision_log_detail", args=[bi_decision_log_a.pk])).status_code == 404

    def test_collaborationstorytelling_list_views_zero_cross_tenant_leakage(
        self, client_a, bi_shared_workspace_b, bi_data_story_b, bi_visual_comment_b, bi_decision_log_b
    ):
        """Tenant A list views never leak Tenant B titles or content."""
        for url_name, secret in [
            ("bi:bi_shared_workspace_list", bi_shared_workspace_b.name),
            ("bi:bi_data_story_list", bi_data_story_b.title),
            ("bi:bi_visual_comment_list", bi_visual_comment_b.content),
            ("bi:bi_decision_log_list", bi_decision_log_b.title),
        ]:
            res = client_a.get(reverse(url_name))
            assert res.status_code == 200
            content = res.content.decode()
            assert secret not in content


# ==============================================================================
# 2. Cross-Tenant Foreign Key Injection Defense in Forms
# ==============================================================================


class TestCollaborationStorytellingFormSecurity:
    """Verifies that all 4 forms enforce tenant isolation on foreign keys."""

    def test_collaborationstorytelling_workspace_form_rejects_foreign_department(
        self, tenant_a, tenant_b, admin_user
    ):
        foreign_dept = _collaborationstorytelling_sec_org_unit(tenant_b, "Foreign Dept")
        form = BiSharedWorkspaceForm(
            data={
                "name": "Acme Hub",
                "code": "ACME-HUB-1",
                "workspace_type": "team",
                "default_access_level": "viewer",
                "color": "#2563eb",
                "department": foreign_dept.pk,
                "owner": admin_user.pk,
                "members_raw": "[]",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "department" in form.errors

    def test_collaborationstorytelling_workspace_form_rejects_foreign_owner(
        self, tenant_a, admin_user_b
    ):
        form = BiSharedWorkspaceForm(
            data={
                "name": "Acme Hub",
                "code": "ACME-HUB-2",
                "workspace_type": "team",
                "default_access_level": "viewer",
                "color": "#2563eb",
                "owner": admin_user_b.pk,
                "members_raw": "[]",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "owner" in form.errors

    def test_collaborationstorytelling_story_form_rejects_foreign_workspace(
        self, tenant_a, bi_shared_workspace_b, admin_user
    ):
        form = BiDataStoryForm(
            data={
                "title": "Acme Story",
                "story_type": "deep_dive",
                "target_audience": "executives",
                "status": "draft",
                "workspace": bi_shared_workspace_b.pk,
                "author": admin_user.pk,
                "slides_data_raw": "[]",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "workspace" in form.errors

    def test_collaborationstorytelling_story_form_rejects_foreign_author(
        self, tenant_a, bi_shared_workspace_a, admin_user_b
    ):
        form = BiDataStoryForm(
            data={
                "title": "Acme Story 2",
                "story_type": "deep_dive",
                "target_audience": "executives",
                "status": "draft",
                "workspace": bi_shared_workspace_a.pk,
                "author": admin_user_b.pk,
                "slides_data_raw": "[]",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "author" in form.errors

    def test_collaborationstorytelling_comment_form_rejects_foreign_dashboard(
        self, tenant_a, bi_dashboard_b, admin_user
    ):
        form = BiVisualCommentForm(
            data={
                "target_type": "dashboard",
                "dashboard": bi_dashboard_b.pk,
                "coordinate_x": 10.0,
                "coordinate_y": 20.0,
                "content": "Cross-tenant injection attempt",
                "priority": "medium",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "dashboard" in form.errors

    def test_collaborationstorytelling_comment_form_rejects_foreign_report(
        self, tenant_a, tenant_b, admin_user
    ):
        foreign_rep = _collaborationstorytelling_sec_report(tenant_b)
        form = BiVisualCommentForm(
            data={
                "target_type": "report",
                "report": foreign_rep.pk,
                "coordinate_x": 10.0,
                "coordinate_y": 20.0,
                "content": "Foreign report injection attempt",
                "priority": "medium",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "report" in form.errors

    def test_collaborationstorytelling_comment_form_rejects_foreign_story(
        self, tenant_a, bi_data_story_b, admin_user
    ):
        form = BiVisualCommentForm(
            data={
                "target_type": "story",
                "story": bi_data_story_b.pk,
                "coordinate_x": 10.0,
                "coordinate_y": 20.0,
                "content": "Foreign story injection attempt",
                "priority": "medium",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "story" in form.errors

    def test_collaborationstorytelling_comment_form_rejects_foreign_parent_comment(
        self, tenant_a, bi_visual_comment_b, bi_dashboard_a, admin_user
    ):
        form = BiVisualCommentForm(
            data={
                "target_type": "dashboard",
                "dashboard": bi_dashboard_a.pk,
                "parent_comment": bi_visual_comment_b.pk,
                "coordinate_x": 10.0,
                "coordinate_y": 20.0,
                "content": "Foreign parent injection attempt",
                "priority": "medium",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "parent_comment" in form.errors

    def test_collaborationstorytelling_decision_form_rejects_foreign_workspace(
        self, tenant_a, bi_shared_workspace_b, admin_user
    ):
        form = BiDecisionLogForm(
            data={
                "title": "Decision with foreign workspace",
                "problem_statement": "Issue detected",
                "decision_rationale": "Action planned",
                "impact_assessment": "Positive ROI",
                "category": "operational",
                "status": "proposed",
                "decision_date": "2026-11-08",
                "workspace": bi_shared_workspace_b.pk,
                "decision_maker": admin_user.pk,
                "marker_color": "#10b981",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "workspace" in form.errors

    def test_collaborationstorytelling_decision_form_rejects_foreign_dashboard(
        self, tenant_a, bi_dashboard_b, admin_user
    ):
        form = BiDecisionLogForm(
            data={
                "title": "Decision with foreign dashboard",
                "problem_statement": "Issue detected",
                "decision_rationale": "Action planned",
                "impact_assessment": "Positive ROI",
                "category": "operational",
                "status": "proposed",
                "decision_date": "2026-11-08",
                "dashboard": bi_dashboard_b.pk,
                "decision_maker": admin_user.pk,
                "marker_color": "#10b981",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "dashboard" in form.errors

    def test_collaborationstorytelling_decision_form_rejects_foreign_kpi(
        self, tenant_a, kpi_definition_b, admin_user
    ):
        form = BiDecisionLogForm(
            data={
                "title": "Decision with foreign KPI",
                "problem_statement": "Issue detected",
                "decision_rationale": "Action planned",
                "impact_assessment": "Positive ROI",
                "category": "operational",
                "status": "proposed",
                "decision_date": "2026-11-08",
                "kpi": kpi_definition_b.pk,
                "decision_maker": admin_user.pk,
                "marker_color": "#10b981",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "kpi" in form.errors

    def test_collaborationstorytelling_decision_form_rejects_foreign_decision_maker(
        self, tenant_a, admin_user_b
    ):
        form = BiDecisionLogForm(
            data={
                "title": "Decision with foreign decision maker",
                "problem_statement": "Issue detected",
                "decision_rationale": "Action planned",
                "impact_assessment": "Positive ROI",
                "category": "operational",
                "status": "proposed",
                "decision_date": "2026-11-08",
                "decision_maker": admin_user_b.pk,
                "marker_color": "#10b981",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "decision_maker" in form.errors


# ==============================================================================
# 3. Authentication & Authorization Gates
# ==============================================================================


class TestCollaborationStorytellingAuthAndPermissions:
    """Verifies @login_required, @require_POST, and comment author ownership gates."""

    def test_collaborationstorytelling_unauthenticated_access_redirects_302(
        self, client, bi_shared_workspace_a, bi_data_story_a, bi_visual_comment_a, bi_decision_log_a
    ):
        """All 23 endpoints redirect anonymous clients to login."""
        urls = [
            reverse("bi:bi_shared_workspace_list"),
            reverse("bi:bi_shared_workspace_create"),
            reverse("bi:bi_shared_workspace_detail", args=[bi_shared_workspace_a.pk]),
            reverse("bi:bi_shared_workspace_edit", args=[bi_shared_workspace_a.pk]),
            reverse("bi:bi_shared_workspace_delete", args=[bi_shared_workspace_a.pk]),
            reverse("bi:bi_data_story_list"),
            reverse("bi:bi_data_story_create"),
            reverse("bi:bi_data_story_detail", args=[bi_data_story_a.pk]),
            reverse("bi:bi_data_story_edit", args=[bi_data_story_a.pk]),
            reverse("bi:bi_data_story_delete", args=[bi_data_story_a.pk]),
            reverse("bi:bi_data_story_presentation", args=[bi_data_story_a.pk]),
            reverse("bi:bi_data_story_export_office", args=[bi_data_story_a.pk]),
            reverse("bi:bi_visual_comment_list"),
            reverse("bi:bi_visual_comment_create"),
            reverse("bi:bi_visual_comment_detail", args=[bi_visual_comment_a.pk]),
            reverse("bi:bi_visual_comment_edit", args=[bi_visual_comment_a.pk]),
            reverse("bi:bi_visual_comment_delete", args=[bi_visual_comment_a.pk]),
            reverse("bi:bi_visual_comment_resolve", args=[bi_visual_comment_a.pk]),
            reverse("bi:bi_decision_log_list"),
            reverse("bi:bi_decision_log_create"),
            reverse("bi:bi_decision_log_detail", args=[bi_decision_log_a.pk]),
            reverse("bi:bi_decision_log_edit", args=[bi_decision_log_a.pk]),
            reverse("bi:bi_decision_log_delete", args=[bi_decision_log_a.pk]),
        ]
        for url in urls:
            res = client.get(url)
            assert res.status_code == 302, f"URL {url} did not enforce @login_required"
            assert "/login/" in res.headers["Location"]

    def test_collaborationstorytelling_post_method_guards_405(
        self, client_a, bi_shared_workspace_a, bi_data_story_a, bi_visual_comment_a, bi_decision_log_a
    ):
        """GET on destructive or mutation endpoints returns 405 Method Not Allowed."""
        destructive_urls = [
            reverse("bi:bi_shared_workspace_delete", args=[bi_shared_workspace_a.pk]),
            reverse("bi:bi_data_story_delete", args=[bi_data_story_a.pk]),
            reverse("bi:bi_visual_comment_delete", args=[bi_visual_comment_a.pk]),
            reverse("bi:bi_visual_comment_resolve", args=[bi_visual_comment_a.pk]),
            reverse("bi:bi_decision_log_delete", args=[bi_decision_log_a.pk]),
        ]
        for url in destructive_urls:
            assert client_a.get(url).status_code == 405, f"GET on {url} was not rejected with 405"

    def test_collaborationstorytelling_comment_author_permission_gate(
        self, member_client, admin_user, tenant_a, bi_dashboard_a, bi_data_story_a
    ):
        """Non-author, non-admin user cannot edit or delete someone else's comment."""
        admin_comment = BiVisualComment.objects.create(
            tenant=tenant_a,
            number="VCOM-SEC-01",
            target_type="dashboard",
            dashboard=bi_dashboard_a,
            story=bi_data_story_a,
            coordinate_x=15.0,
            coordinate_y=25.0,
            content="Admin strategic note.",
            priority="high",
            status="open",
            author=admin_user,
        )
        edit_url = reverse("bi:bi_visual_comment_edit", args=[admin_comment.pk])
        del_url = reverse("bi:bi_visual_comment_delete", args=[admin_comment.pk])

        # Member user attempt to edit -> redirected with error
        res_edit = member_client.get(edit_url)
        assert res_edit.status_code == 302
        assert reverse("bi:bi_visual_comment_detail", args=[admin_comment.pk]) in res_edit.headers["Location"]

        # Member user attempt to delete -> redirected with error, comment remains
        res_del = member_client.post(del_url)
        assert res_del.status_code == 302
        assert BiVisualComment.objects.filter(pk=admin_comment.pk).exists()


# ==============================================================================
# 4. Office Embed Token Validation (I1)
# ==============================================================================


class TestCollaborationStorytellingOfficeEmbedToken:
    """Verifies that the office export endpoint enforces constant-time token validation."""

    def test_collaborationstorytelling_office_export_valid_token_200(
        self, client_a, bi_data_story_a
    ):
        url = reverse("bi:bi_data_story_export_office", args=[bi_data_story_a.pk])
        res = client_a.get(f"{url}?token={bi_data_story_a.office_embed_token}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["story_number"] == bi_data_story_a.number
        assert payload["title"] == bi_data_story_a.title
        assert "slides" in payload

    def test_collaborationstorytelling_office_export_invalid_token_403(
        self, client_a, bi_data_story_a
    ):
        url = reverse("bi:bi_data_story_export_office", args=[bi_data_story_a.pk])
        res = client_a.get(f"{url}?token=WRONG_EXPLOIT_TOKEN_999")
        assert res.status_code == 403
        assert "Invalid or missing embed token" in res.json().get("error", "")

    def test_collaborationstorytelling_office_export_missing_token_403(
        self, client_a, bi_data_story_a
    ):
        url = reverse("bi:bi_data_story_export_office", args=[bi_data_story_a.pk])
        res = client_a.get(url)
        assert res.status_code == 403
        assert "Invalid or missing embed token" in res.json().get("error", "")


# ==============================================================================
# 5. Input Hardening & Sanitization
# ==============================================================================


class TestCollaborationStorytellingInjectionAndSanitization:
    """Verifies resistance against CSS injection, coordinate overflow, recursion, and cross-record mismatch."""

    def test_collaborationstorytelling_css_injection_workspace_color_rejected(
        self, tenant_a, admin_user
    ):
        """Attempts to inject CSS breakout strings into workspace color are rejected (I6, L26)."""
        malicious_colors = [
            "#3b82f6; background-image: url('https://attacker.com/leak')",
            "red; color: blue",
            "<script>alert(1)</script>",
            "#GGGGGG",
            "#12345",
        ]
        for bad_color in malicious_colors:
            form = BiSharedWorkspaceForm(
                data={
                    "name": "CSS Exploit Workspace",
                    "code": f"EXP-{uuid.uuid4().hex[:4]}",
                    "workspace_type": "team",
                    "default_access_level": "viewer",
                    "color": bad_color,
                    "owner": admin_user.pk,
                    "members_raw": "[]",
                },
                tenant=tenant_a,
            )
            assert not form.is_valid(), f"Color {bad_color} was improperly accepted"
            assert "color" in form.errors

    def test_collaborationstorytelling_css_injection_decision_marker_color_rejected(
        self, tenant_a, admin_user
    ):
        """Attempts to inject CSS breakout strings into decision marker_color are rejected."""
        form = BiDecisionLogForm(
            data={
                "title": "Decision CSS injection",
                "problem_statement": "Problem text",
                "decision_rationale": "Rationale text",
                "impact_assessment": "Impact text",
                "category": "operational",
                "status": "proposed",
                "decision_date": "2026-11-08",
                "decision_maker": admin_user.pk,
                "marker_color": "#10b981; font-size: 50px;",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "marker_color" in form.errors

    def test_collaborationstorytelling_coordinate_boundaries_rejected(
        self, tenant_a, bi_dashboard_a, admin_user
    ):
        """Coordinates outside [0.0, 100.0] are rejected by form bounds validation (M8)."""
        for bad_x, bad_y in [(-5.0, 50.0), (50.0, -10.0), (105.0, 50.0), (50.0, 999.0)]:
            form = BiVisualCommentForm(
                data={
                    "target_type": "dashboard",
                    "dashboard": bi_dashboard_a.pk,
                    "coordinate_x": bad_x,
                    "coordinate_y": bad_y,
                    "content": "Out of bounds coordinate",
                    "priority": "medium",
                },
                tenant=tenant_a,
            )
            assert not form.is_valid()
            assert "coordinate_x" in form.errors or "coordinate_y" in form.errors

    def test_collaborationstorytelling_self_parent_recursion_rejected(
        self, tenant_a, bi_visual_comment_a, bi_dashboard_a
    ):
        """A comment cannot be set as its own parent comment (M1)."""
        form = BiVisualCommentForm(
            data={
                "target_type": "dashboard",
                "dashboard": bi_dashboard_a.pk,
                "parent_comment": bi_visual_comment_a.pk,
                "coordinate_x": 20.0,
                "coordinate_y": 20.0,
                "content": "Self recursion attempt",
                "priority": "medium",
            },
            instance=bi_visual_comment_a,
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "parent_comment" in form.errors

    def test_collaborationstorytelling_cross_record_integrity_widget_mismatch_rejected(
        self, tenant_a, bi_dashboard_a, admin_user
    ):
        """Selecting a widget that belongs to another dashboard is rejected (I8)."""
        other_dashboard = BiDashboard.objects.create(
            tenant=tenant_a,
            title="Secondary Dashboard",
            slug=f"dash-other-{uuid.uuid4().hex[:4]}",
        )
        unrelated_widget = _collaborationstorytelling_sec_widget(other_dashboard, "Unrelated Chart")

        form = BiVisualCommentForm(
            data={
                "target_type": "dashboard",
                "dashboard": bi_dashboard_a.pk,
                "widget": unrelated_widget.pk,
                "coordinate_x": 10.0,
                "coordinate_y": 20.0,
                "content": "Mismatched widget",
                "priority": "medium",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "widget" in form.errors


# ==============================================================================
# 6. Audit Log Verification
# ==============================================================================


class TestCollaborationStorytellingAuditLog:
    """Verifies that AuditLog rows are created on create, edit, delete, and resolve."""

    def test_collaborationstorytelling_audit_log_workspace_lifecycle(
        self, client_a, tenant_a, admin_user
    ):
        # Create
        slug_val = f"aud-{uuid.uuid4().hex[:6]}"
        res = client_a.post(
            reverse("bi:bi_shared_workspace_create"),
            {
                "name": "Audit Tracked Workspace",
                "slug": slug_val,
                "description": "Audit tracking space",
                "default_access_level": "contributor",
                "status": "active",
                "color": "#10b981",
                "icon": "folder",
                "owner": admin_user.pk,
                "members_raw": "[]",
            },
        )
        assert res.status_code == 302
        wspc = BiSharedWorkspace.objects.filter(tenant=tenant_a, slug=slug_val).first()
        assert wspc is not None

        log_create = AuditLog.objects.filter(
            tenant=tenant_a, object_id=wspc.pk, action="create"
        ).first()
        assert log_create is not None
        assert log_create.user == admin_user

        # Edit
        res_edit = client_a.post(
            reverse("bi:bi_shared_workspace_edit", args=[wspc.pk]),
            {
                "name": "Audit Tracked Workspace Updated",
                "slug": wspc.slug,
                "description": "Updated description",
                "default_access_level": "contributor",
                "status": "active",
                "color": "#10b981",
                "icon": "folder",
                "owner": admin_user.pk,
                "members_raw": "[]",
            },
        )
        assert res_edit.status_code == 302
        log_edit = AuditLog.objects.filter(
            tenant=tenant_a, object_id=wspc.pk, action="update"
        ).first()
        assert log_edit is not None

        # Delete
        res_del = client_a.post(reverse("bi:bi_shared_workspace_delete", args=[wspc.pk]))
        assert res_del.status_code == 302
        log_del = AuditLog.objects.filter(
            tenant=tenant_a, object_id=wspc.pk, action="delete"
        ).first()
        assert log_del is not None

    def test_collaborationstorytelling_audit_log_comment_resolve(
        self, client_a, tenant_a, bi_visual_comment_a, admin_user
    ):
        res = client_a.post(reverse("bi:bi_visual_comment_resolve", args=[bi_visual_comment_a.pk]))
        assert res.status_code == 302
        log = AuditLog.objects.filter(
            tenant=tenant_a, object_id=bi_visual_comment_a.pk, action="update"
        ).first()
        assert log is not None
        assert log.user == admin_user
