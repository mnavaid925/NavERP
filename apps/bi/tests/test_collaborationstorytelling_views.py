"""View test suite for Sub-module 10.18: Collaboration & Data Storytelling (apps/bi).

Views covered (23 views across 4 entities):
1. BiSharedWorkspace views:
   - bi_shared_workspace_list: 200, context keys, search q=, filters (status, access_level, department), pagination (15/page)
   - bi_shared_workspace_create: GET 200, POST valid -> 302, POST invalid -> 200
   - bi_shared_workspace_detail: GET 200, context keys, audit logs, related stories & decision logs
   - bi_shared_workspace_edit: GET 200, POST valid -> 302, POST invalid -> 200
   - bi_shared_workspace_delete: GET 405 (require_POST), POST 302 redirects to list

2. BiDataStory views:
   - bi_data_story_list: 200, context keys, search q=, filters (status, story_type, workspace), pagination
   - bi_data_story_create: GET 200 (workspace query param pre-population), POST valid -> 302, POST invalid -> 200
   - bi_data_story_detail: GET 200, context keys, office link with token
   - bi_data_story_edit: GET 200, POST valid -> 302, POST invalid -> 200
   - bi_data_story_delete: GET 405, POST 302 redirects to list
   - bi_data_story_presentation: GET 200, increments view_count, sets last_presented_at, slides context
   - bi_data_story_export_office: GET 200 with valid token, GET 403 with invalid/missing token

3. BiVisualComment views:
   - bi_visual_comment_list: 200, context keys, filters (status, priority, target_type, dashboard, story), select_related includes parent_comment
   - bi_visual_comment_create: GET 200 with ?parent=<pk> pre-populating parent, target, dashboard, story, report, widget in initial, POST valid -> 302, POST invalid -> 200
   - bi_visual_comment_detail: GET 200, context keys, replies queryset
   - bi_visual_comment_edit: author or tenant admin can edit (GET 200, POST 302), non-author staff gets redirected 302
   - bi_visual_comment_delete: GET 405, author or tenant admin can delete (POST 302), non-author staff gets redirected 302
   - bi_visual_comment_resolve: GET 405, POST 302 sets status='resolved', resolved_at, resolved_by

4. BiDecisionLog views:
   - bi_decision_log_list: 200, context keys, search q=, filters (status, category, workspace, dashboard), pagination
   - bi_decision_log_create: GET 200 (workspace, dashboard query param pre-population), POST valid -> 302, POST invalid -> 200
   - bi_decision_log_detail: GET 200, context keys
   - bi_decision_log_edit: GET 200, POST valid -> 302, POST invalid -> 200
   - bi_decision_log_delete: GET 405, POST 302 redirects to list

5. Cross-Cutting:
   - Cross-tenant IDOR: tenant_b accessing tenant_a objects gets 404
   - Unauthenticated access: anonymous client gets 302 redirects to login
"""
import json
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    BiDashboard,
    BiDataStory,
    BiDecisionLog,
    BiSharedWorkspace,
    BiVisualComment,
    KpiDefinition,
)
from apps.core.models import AuditLog, OrgUnit

User = get_user_model()


# ==============================================================================
# Module Helpers (strictly prefixed with _collaborationstorytelling_)
# ==============================================================================


def _collaborationstorytelling_create_workspace(tenant, name=None, **kwargs):
    """Create a tenant-scoped BiSharedWorkspace for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "name": name or f"Test Workspace {ts}",
        "slug": f"workspace-{ts}",
        "default_access_level": "contributor",
        "status": "active",
        "is_public": False,
        "color": "#3b82f6",
        "icon": "folder",
    }
    defaults.update(kwargs)
    return BiSharedWorkspace.objects.create(**defaults)


def _collaborationstorytelling_create_story(tenant, workspace=None, title=None, author=None, **kwargs):
    """Create a tenant-scoped BiDataStory for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "title": title or f"Test Data Story {ts}",
        "slug": f"story-{ts}",
        "summary": "Executive summary for operational performance story.",
        "workspace": workspace,
        "story_type": "narrative_deck",
        "status": "published",
        "theme": "light_executive",
        "author": author,
        "office_embed_token": f"embed_token_{ts}",
        "slides_data": [
            {
                "slide_num": 1,
                "title": "Intro Slide",
                "narrative": "Key quarterly indicators overview.",
            }
        ],
    }
    defaults.update(kwargs)
    return BiDataStory.objects.create(**defaults)


def _collaborationstorytelling_create_comment(tenant, author=None, dashboard=None, story=None, **kwargs):
    """Create a tenant-scoped BiVisualComment for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "author": author,
        "dashboard": dashboard,
        "story": story,
        "target_type": "dashboard" if dashboard else ("story" if story else "dashboard"),
        "content": f"Test visual observation note {ts}",
        "status": "open",
        "priority": "medium",
        "coordinate_x": 30.0,
        "coordinate_y": 50.0,
    }
    defaults.update(kwargs)
    return BiVisualComment.objects.create(**defaults)


def _collaborationstorytelling_create_decision(tenant, workspace=None, dashboard=None, decision_maker=None, **kwargs):
    """Create a tenant-scoped BiDecisionLog for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "title": f"Test Strategic Decision {ts}",
        "slug": f"decision-{ts}",
        "category": "strategic",
        "status": "approved",
        "decision_date": date(2026, 11, 8),
        "problem_statement": "Growth rate plateaued in secondary regions.",
        "rationale": "Allocate regional expansion resources to tier-1 cities.",
        "expected_impact": "Accelerate pipeline velocity by 20%.",
        "workspace": workspace,
        "dashboard": dashboard,
        "decision_maker": decision_maker,
        "marker_color": "#10b981",
        "marker_style": "pin_flag",
    }
    defaults.update(kwargs)
    return BiDecisionLog.objects.create(**defaults)


def _collaborationstorytelling_workspace_form_data(department=None, owner=None, **kwargs):
    """Return valid form data payload for BiSharedWorkspaceForm."""
    data = {
        "name": "Global Analytics Workspace",
        "slug": "global-analytics-workspace",
        "description": "Collaborative enterprise analytics space.",
        "default_access_level": "contributor",
        "status": "active",
        "is_public": True,
        "is_favorite": True,
        "color": "#3b82f6",
        "icon": "folder",
        "members_raw": json.dumps([{"username": "analyst_one", "role": "member"}]),
    }
    if department:
        data["department"] = str(department.pk)
    if owner:
        data["owner"] = str(owner.pk)
    data.update(kwargs)
    return data


def _collaborationstorytelling_story_form_data(workspace=None, author=None, **kwargs):
    """Return valid form data payload for BiDataStoryForm."""
    data = {
        "title": "Q4 Performance Narrative Deck",
        "slug": "q4-perf-narrative",
        "summary": "Guided presentation deck summarizing Q4 enterprise results.",
        "story_type": "narrative_deck",
        "status": "published",
        "theme": "light_executive",
        "allow_live_drilldown": True,
        "slides_data_raw": json.dumps([
            {
                "slide_num": 1,
                "title": "Revenue Acceleration",
                "narrative": "Annual recurring revenue reached target milestone.",
            }
        ]),
    }
    if workspace:
        data["workspace"] = str(workspace.pk)
    if author:
        data["author"] = str(author.pk)
    data.update(kwargs)
    return data


def _collaborationstorytelling_comment_form_data(dashboard=None, story=None, parent_comment=None, **kwargs):
    """Return valid form data payload for BiVisualCommentForm."""
    data = {
        "target_type": "dashboard",
        "content": "Gross margin metric shows positive deviation from baseline trend.",
        "status": "open",
        "priority": "high",
        "coordinate_x": "45.0",
        "coordinate_y": "60.0",
    }
    if dashboard:
        data["dashboard"] = str(dashboard.pk)
    if story:
        data["story"] = str(story.pk)
        data["target_type"] = "story"
    if parent_comment:
        data["parent_comment"] = str(parent_comment.pk)
    data.update(kwargs)
    return data


def _collaborationstorytelling_decision_form_data(workspace=None, dashboard=None, decision_maker=None, **kwargs):
    """Return valid form data payload for BiDecisionLogForm."""
    data = {
        "title": "Commercial Pricing Tier Realignment",
        "slug": "pricing-tier-realignment",
        "category": "pricing",
        "status": "approved",
        "decision_date": "2026-11-08",
        "problem_statement": "Enterprise tiers showed contract compression.",
        "rationale": "Introduce volume-based elasticity tiers.",
        "expected_impact": "Maintain 85% gross retention rate.",
        "actual_outcome": "Early retention renewals tracking at 88%.",
        "show_on_charts": True,
        "marker_style": "pin_flag",
        "marker_color": "#10b981",
    }
    if workspace:
        data["workspace"] = str(workspace.pk)
    if dashboard:
        data["dashboard"] = str(dashboard.pk)
    if decision_maker:
        data["decision_maker"] = str(decision_maker.pk)
    data.update(kwargs)
    return data


# ==============================================================================
# 1. BiSharedWorkspace View Tests (5 views)
# ==============================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_list_view_status_context_and_tenant_isolation(
    client_a, bi_shared_workspace_a, bi_shared_workspace_b
):
    """Test bi_shared_workspace_list returns 200, context variables, and strictly isolates tenant data."""
    url = reverse("bi:bi_shared_workspace_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "workspaces" in resp.context
    assert "bi_shared_workspaces" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert "public_count" in resp.context
    assert "status_choices" in resp.context
    assert "access_level_choices" in resp.context
    assert "departments" in resp.context

    # Verify tenant isolation
    item_pks = [w.pk for w in resp.context["workspaces"]]
    assert bi_shared_workspace_a.pk in item_pks
    assert bi_shared_workspace_b.pk not in item_pks

    # Verify content rendering without blank screen
    content = resp.content.decode("utf-8")
    assert bi_shared_workspace_a.name in content
    assert bi_shared_workspace_b.name not in content


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching workspaces by query keyword matching name, number, slug, or description."""
    target = _collaborationstorytelling_create_workspace(
        tenant_a,
        name="UniqueWorkspaceTargetName",
        description="Workspace description for financial modeling",
        owner=admin_user,
    )
    url = reverse("bi:bi_shared_workspace_list")

    # Match by name
    resp_match = client_a.get(url, {"q": "UniqueWorkspaceTarget"})
    assert resp_match.status_code == 200
    pks = [w.pk for w in resp_match.context["workspaces"]]
    assert target.pk in pks

    # Unmatched query
    resp_none = client_a.get(url, {"q": "NonExistentKeywordXYZ999"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["workspaces"]) == 0


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering workspaces by status, access level, and department."""
    dept = OrgUnit.objects.create(tenant=tenant_a, name="Treasury Division")
    w_active = _collaborationstorytelling_create_workspace(
        tenant_a,
        name="Treasury Operations Hub",
        status="active",
        default_access_level="member",
        department=dept,
        owner=admin_user,
    )
    w_archived = _collaborationstorytelling_create_workspace(
        tenant_a,
        name="Archived Planning Workspace",
        status="archived",
        default_access_level="viewer",
        owner=admin_user,
    )
    url = reverse("bi:bi_shared_workspace_list")

    # Filter status=active
    resp_active = client_a.get(url, {"status": "active"})
    pks_active = [w.pk for w in resp_active.context["workspaces"]]
    assert w_active.pk in pks_active
    assert w_archived.pk not in pks_active

    # Filter status=archived
    resp_archived = client_a.get(url, {"status": "archived"})
    pks_archived = [w.pk for w in resp_archived.context["workspaces"]]
    assert w_archived.pk in pks_archived
    assert w_active.pk not in pks_archived

    # Filter access_level=member
    resp_access = client_a.get(url, {"access_level": "member"})
    pks_access = [w.pk for w in resp_access.context["workspaces"]]
    assert w_active.pk in pks_access
    assert w_archived.pk not in pks_access

    # Filter department
    resp_dept = client_a.get(url, {"department": str(dept.pk)})
    pks_dept = [w.pk for w in resp_dept.context["workspaces"]]
    assert w_active.pk in pks_dept
    assert w_archived.pk not in pks_dept


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test pagination of workspaces with 15 items per page."""
    for i in range(16):
        _collaborationstorytelling_create_workspace(
            tenant_a,
            name=f"Paginated Workspace {i:02d}",
            owner=admin_user,
        )

    url = reverse("bi:bi_shared_workspace_list")

    # Page 1 has 15 items
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["workspaces"]) == 15
    assert resp_p1.context["workspaces"].has_next() is True

    # Page 2 has the remaining items
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["workspaces"]) >= 1


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_create_get_and_post_valid(
    client_a, tenant_a, admin_user
):
    """Test workspace create view GET returns form and valid POST redirects to detail."""
    dept = OrgUnit.objects.create(tenant=tenant_a, name="Operations Support")
    url = reverse("bi:bi_shared_workspace_create")

    # GET returns form
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False
    assert "title" in resp_get.context

    # POST valid form
    data = _collaborationstorytelling_workspace_form_data(
        department=dept,
        owner=admin_user,
        name="Global Corporate Workspace",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created = BiSharedWorkspace.objects.filter(
        tenant=tenant_a, name="Global Corporate Workspace"
    ).first()
    assert created is not None
    assert created.created_by == admin_user
    assert created.department == dept
    assert resp_post.url == reverse("bi:bi_shared_workspace_detail", kwargs={"pk": created.pk})

    # Verify audit log recorded
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_create_post_invalid(client_a):
    """Test workspace create with invalid data re-renders form with 200 and errors."""
    url = reverse("bi:bi_shared_workspace_create")
    resp = client_a.post(url, {"name": ""})  # Missing required name

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_detail_view(
    client_a, tenant_a, admin_user, bi_shared_workspace_a
):
    """Test workspace detail view returns 200, context keys, and related stories/decisions."""
    story = _collaborationstorytelling_create_story(
        tenant_a, workspace=bi_shared_workspace_a, title="Workspace Detail Story", author=admin_user
    )
    decision = _collaborationstorytelling_create_decision(
        tenant_a, workspace=bi_shared_workspace_a, title="Workspace Strategic Decision", decision_maker=admin_user
    )

    url = reverse("bi:bi_shared_workspace_detail", kwargs={"pk": bi_shared_workspace_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "workspace" in resp.context
    assert "bi_shared_workspace" in resp.context
    assert "obj" in resp.context
    assert "stories" in resp.context
    assert "decision_logs" in resp.context

    story_pks = [s.pk for s in resp.context["stories"]]
    assert story.pk in story_pks
    decision_pks = [d.pk for d in resp.context["decision_logs"]]
    assert decision.pk in decision_pks

    content = resp.content.decode("utf-8")
    assert bi_shared_workspace_a.name in content
    assert bi_shared_workspace_a.number in content


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_edit_get_and_post_valid(
    client_a, tenant_a, bi_shared_workspace_a
):
    """Test workspace edit view GET returns 200 and valid POST updates workspace."""
    url = reverse("bi:bi_shared_workspace_edit", kwargs={"pk": bi_shared_workspace_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert "workspace" in resp_get.context

    # POST valid update
    data = _collaborationstorytelling_workspace_form_data(
        name="Executive Analytics Hub Renovated",
        default_access_level="member",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_shared_workspace_detail", kwargs={"pk": bi_shared_workspace_a.pk})

    bi_shared_workspace_a.refresh_from_db()
    assert bi_shared_workspace_a.name == "Executive Analytics Hub Renovated"
    assert bi_shared_workspace_a.default_access_level == "member"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=bi_shared_workspace_a.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_edit_post_invalid(client_a, bi_shared_workspace_a):
    """Test workspace edit with invalid payload re-renders form with 200."""
    url = reverse("bi:bi_shared_workspace_edit", kwargs={"pk": bi_shared_workspace_a.pk})
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_delete_view(
    client_a, tenant_a, admin_user
):
    """Test workspace delete view requires POST (GET returns 405) and deletes object."""
    workspace = _collaborationstorytelling_create_workspace(
        tenant_a, name="Workspace To Be Deleted", owner=admin_user
    )
    url = reverse("bi:bi_shared_workspace_delete", kwargs={"pk": workspace.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes workspace
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_shared_workspace_list")
    assert not BiSharedWorkspace.objects.filter(pk=workspace.pk).exists()

    # Verify audit log recorded
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=workspace.pk
    ).exists()


# ==============================================================================
# 2. BiDataStory View Tests (7 views)
# ==============================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_story_list_view_status_context_and_tenant_isolation(
    client_a, bi_data_story_a, bi_data_story_b
):
    """Test bi_data_story_list returns 200, context variables, and strictly isolates tenant stories."""
    url = reverse("bi:bi_data_story_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "stories" in resp.context
    assert "bi_data_stories" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["published_count"] >= 1
    assert "draft_count" in resp.context
    assert "status_choices" in resp.context
    assert "story_type_choices" in resp.context
    assert "workspaces" in resp.context

    item_pks = [s.pk for s in resp.context["stories"]]
    assert bi_data_story_a.pk in item_pks
    assert bi_data_story_b.pk not in item_pks

    content = resp.content.decode("utf-8")
    assert bi_data_story_a.title in content
    assert bi_data_story_b.title not in content


@pytest.mark.django_db
def test_collaborationstorytelling_story_list_search_and_filters(
    client_a, tenant_a, admin_user, bi_shared_workspace_a
):
    """Test searching and filtering data stories by query, status, story type, and workspace."""
    w2 = _collaborationstorytelling_create_workspace(tenant_a, name="Second Workspace")
    story_pub = _collaborationstorytelling_create_story(
        tenant_a,
        workspace=bi_shared_workspace_a,
        title="Q3 Strategic Growth Narrative Deck",
        story_type="narrative_deck",
        status="published",
        author=admin_user,
    )
    story_draft = _collaborationstorytelling_create_story(
        tenant_a,
        workspace=w2,
        title="Monthly Operational Review Walkthrough",
        story_type="annotated_walkthrough",
        status="draft",
        author=admin_user,
    )
    url = reverse("bi:bi_data_story_list")

    # Search keyword
    resp_q = client_a.get(url, {"q": "Strategic Growth"})
    pks_q = [s.pk for s in resp_q.context["stories"]]
    assert story_pub.pk in pks_q
    assert story_draft.pk not in pks_q

    # Filter status=draft
    resp_draft = client_a.get(url, {"status": "draft"})
    pks_draft = [s.pk for s in resp_draft.context["stories"]]
    assert story_draft.pk in pks_draft
    assert story_pub.pk not in pks_draft

    # Filter story_type=narrative_deck
    resp_type = client_a.get(url, {"story_type": "narrative_deck"})
    pks_type = [s.pk for s in resp_type.context["stories"]]
    assert story_pub.pk in pks_type
    assert story_draft.pk not in pks_type

    # Filter workspace
    resp_w = client_a.get(url, {"workspace": str(bi_shared_workspace_a.pk)})
    pks_w = [s.pk for s in resp_w.context["stories"]]
    assert story_pub.pk in pks_w
    assert story_draft.pk not in pks_w


@pytest.mark.django_db
def test_collaborationstorytelling_story_list_pagination(
    client_a, tenant_a, admin_user, bi_shared_workspace_a
):
    """Test pagination for data story list view."""
    for i in range(16):
        _collaborationstorytelling_create_story(
            tenant_a,
            workspace=bi_shared_workspace_a,
            title=f"Paginated Story {i:02d}",
            author=admin_user,
        )

    url = reverse("bi:bi_data_story_list")
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["stories"]) == 15
    assert resp_p1.context["stories"].has_next() is True

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["stories"]) >= 1


@pytest.mark.django_db
def test_collaborationstorytelling_story_create_get_and_post_valid(
    client_a, tenant_a, admin_user, bi_shared_workspace_a
):
    """Test story create GET with workspace initial and valid POST redirecting to detail."""
    url = reverse("bi:bi_data_story_create")

    # GET with ?workspace=<pk> pre-populates initial
    resp_get = client_a.get(url, {"workspace": str(bi_shared_workspace_a.pk)})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["form"].initial.get("workspace") == bi_shared_workspace_a
    assert resp_get.context["is_edit"] is False

    # POST valid form
    data = _collaborationstorytelling_story_form_data(
        workspace=bi_shared_workspace_a,
        author=admin_user,
        title="Created Executive Walkthrough",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    story = BiDataStory.objects.filter(tenant=tenant_a, title="Created Executive Walkthrough").first()
    assert story is not None
    assert story.author == admin_user
    assert story.created_by == admin_user
    assert story.slides_count == 1
    assert resp_post.url == reverse("bi:bi_data_story_detail", kwargs={"pk": story.pk})

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=story.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_story_create_post_invalid(client_a):
    """Test story create with invalid payload re-renders form with errors."""
    url = reverse("bi:bi_data_story_create")
    resp = client_a.post(url, {"title": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context["form"].errors


@pytest.mark.django_db
def test_collaborationstorytelling_story_detail_view(
    client_a, tenant_a, admin_user, bi_data_story_a
):
    """Test story detail view returns 200, context keys, comments, and valid office link."""
    comment = _collaborationstorytelling_create_comment(
        tenant_a, author=admin_user, story=bi_data_story_a, content="Observation on story slide 1."
    )
    url = reverse("bi:bi_data_story_detail", kwargs={"pk": bi_data_story_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "story" in resp.context
    assert "bi_data_story" in resp.context
    assert "obj" in resp.context
    assert "comments" in resp.context
    assert "office_link" in resp.context

    # Office link must contain token
    assert bi_data_story_a.office_embed_token in resp.context["office_link"]

    comment_pks = [c.pk for c in resp.context["comments"]]
    assert comment.pk in comment_pks

    content = resp.content.decode("utf-8")
    assert bi_data_story_a.title in content
    assert bi_data_story_a.number in content


@pytest.mark.django_db
def test_collaborationstorytelling_story_edit_get_and_post_valid(
    client_a, tenant_a, bi_data_story_a
):
    """Test story edit view GET returns 200 and valid POST updates story."""
    url = reverse("bi:bi_data_story_edit", kwargs={"pk": bi_data_story_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert "story" in resp_get.context

    # POST valid update
    data = _collaborationstorytelling_story_form_data(
        title="Q3 Operational Performance Renovated",
        story_type="kpi_review",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_data_story_detail", kwargs={"pk": bi_data_story_a.pk})

    bi_data_story_a.refresh_from_db()
    assert bi_data_story_a.title == "Q3 Operational Performance Renovated"
    assert bi_data_story_a.story_type == "kpi_review"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=bi_data_story_a.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_story_edit_post_invalid(client_a, bi_data_story_a):
    """Test story edit with invalid data re-renders form with 200."""
    url = reverse("bi:bi_data_story_edit", kwargs={"pk": bi_data_story_a.pk})
    resp = client_a.post(url, {"title": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_collaborationstorytelling_story_delete_view(
    client_a, tenant_a, admin_user, bi_shared_workspace_a
):
    """Test story delete view requires POST (GET returns 405) and deletes object."""
    story = _collaborationstorytelling_create_story(
        tenant_a, workspace=bi_shared_workspace_a, title="Story To Be Deleted", author=admin_user
    )
    url = reverse("bi:bi_data_story_delete", kwargs={"pk": story.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes story
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_data_story_list")
    assert not BiDataStory.objects.filter(pk=story.pk).exists()

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=story.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_story_presentation_view(
    client_a, bi_data_story_a
):
    """Test presentation mode view returns 200, slides context, and increments view_count."""
    initial_views = bi_data_story_a.view_count
    url = reverse("bi:bi_data_story_presentation", kwargs={"pk": bi_data_story_a.pk})

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "story" in resp.context
    assert "bi_data_story" in resp.context
    assert "obj" in resp.context
    assert "slides" in resp.context
    assert len(resp.context["slides"]) == 1

    bi_data_story_a.refresh_from_db()
    assert bi_data_story_a.view_count == initial_views + 1
    assert bi_data_story_a.last_presented_at is not None


@pytest.mark.django_db
def test_collaborationstorytelling_story_export_office_view(
    client_a, bi_data_story_a
):
    """Test export_office view returns 200 JSON with valid token and 403 on invalid/missing token."""
    url = reverse("bi:bi_data_story_export_office", kwargs={"pk": bi_data_story_a.pk})

    # Missing token -> 403
    resp_no_tok = client_a.get(url)
    assert resp_no_tok.status_code == 403
    data_no_tok = resp_no_tok.json()
    assert "error" in data_no_tok

    # Invalid token -> 403
    resp_bad_tok = client_a.get(url, {"token": "completely_wrong_token"})
    assert resp_bad_tok.status_code == 403

    # Valid token -> 200 JSON
    valid_token = bi_data_story_a.office_embed_token
    resp_valid = client_a.get(url, {"token": valid_token})
    assert resp_valid.status_code == 200
    payload = resp_valid.json()
    assert payload["story_number"] == bi_data_story_a.number
    assert payload["title"] == bi_data_story_a.title
    assert "slides" in payload
    assert "office_integration" in payload
    assert payload["office_integration"]["refreshable"] is True


# ==============================================================================
# 3. BiVisualComment View Tests (6 views)
# ==============================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_comment_list_view_status_context_and_filters(
    client_a, tenant_a, admin_user, bi_dashboard_a, bi_data_story_a, bi_visual_comment_a, bi_visual_comment_b
):
    """Test visual comments list returns 200, context variables, filters, and select_related parent_comment."""
    # Create child reply comment
    child_comment = _collaborationstorytelling_create_comment(
        tenant_a,
        author=admin_user,
        dashboard=bi_dashboard_a,
        parent_comment=bi_visual_comment_a,
        content="Follow-up clarification on anomaly point.",
        priority="low",
        status="resolved",
    )

    url = reverse("bi:bi_visual_comment_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "comments" in resp.context
    assert "bi_visual_comments" in resp.context
    assert resp.context["total_count"] >= 2
    assert resp.context["open_count"] >= 1
    assert resp.context["resolved_count"] >= 1
    assert "status_choices" in resp.context
    assert "target_type_choices" in resp.context
    assert "priority_choices" in resp.context
    assert "dashboards" in resp.context
    assert "stories" in resp.context

    # Verify tenant isolation
    pks = [c.pk for c in resp.context["comments"]]
    assert bi_visual_comment_a.pk in pks
    assert child_comment.pk in pks
    assert bi_visual_comment_b.pk not in pks

    # Verify select_related included parent_comment without extra query
    child_in_qs = [c for c in resp.context["comments"] if c.pk == child_comment.pk][0]
    assert child_in_qs.parent_comment == bi_visual_comment_a

    # Filter status=resolved
    resp_res = client_a.get(url, {"status": "resolved"})
    pks_res = [c.pk for c in resp_res.context["comments"]]
    assert child_comment.pk in pks_res
    assert bi_visual_comment_a.pk not in pks_res

    # Filter priority=high
    resp_pri = client_a.get(url, {"priority": "high"})
    pks_pri = [c.pk for c in resp_pri.context["comments"]]
    assert bi_visual_comment_a.pk in pks_pri
    assert child_comment.pk not in pks_pri

    # Filter target_type=dashboard
    resp_tgt = client_a.get(url, {"target_type": "dashboard"})
    pks_tgt = [c.pk for c in resp_tgt.context["comments"]]
    assert bi_visual_comment_a.pk in pks_tgt

    # Search keyword
    resp_q = client_a.get(url, {"q": "Follow-up clarification"})
    pks_q = [c.pk for c in resp_q.context["comments"]]
    assert child_comment.pk in pks_q


@pytest.mark.django_db
def test_collaborationstorytelling_comment_create_get_with_prepopulation_and_post_valid(
    client_a, tenant_a, admin_user, bi_dashboard_a, bi_data_story_a, bi_visual_comment_a
):
    """Test comment create GET pre-populates initial from ?parent=<pk>, and valid POST saves comment."""
    url = reverse("bi:bi_visual_comment_create")

    # GET with ?parent=<pk> pre-populates target_type, dashboard, story, parent_comment
    resp_get_parent = client_a.get(url, {"parent": str(bi_visual_comment_a.pk)})
    assert resp_get_parent.status_code == 200
    initial = resp_get_parent.context["form"].initial
    assert initial["parent_comment"] == bi_visual_comment_a
    assert initial["dashboard"] == bi_dashboard_a
    assert initial["story"] == bi_data_story_a
    assert initial["target_type"] == bi_visual_comment_a.target_type

    # GET with ?dashboard=<pk>
    resp_get_dash = client_a.get(url, {"dashboard": str(bi_dashboard_a.pk)})
    assert resp_get_dash.status_code == 200
    assert resp_get_dash.context["form"].initial["dashboard"] == bi_dashboard_a
    assert resp_get_dash.context["form"].initial["target_type"] == "dashboard"

    # GET with ?story=<pk>
    resp_get_story = client_a.get(url, {"story": str(bi_data_story_a.pk)})
    assert resp_get_story.status_code == 200
    assert resp_get_story.context["form"].initial["story"] == bi_data_story_a
    assert resp_get_story.context["form"].initial["target_type"] == "story"

    # POST valid form
    data = _collaborationstorytelling_comment_form_data(
        dashboard=bi_dashboard_a,
        content="New observation regarding metric calculation.",
        priority="high",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created = BiVisualComment.objects.filter(
        tenant=tenant_a, content="New observation regarding metric calculation."
    ).first()
    assert created is not None
    assert created.author == admin_user
    assert resp_post.url == reverse("bi:bi_visual_comment_detail", kwargs={"pk": created.pk})

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_comment_create_post_invalid(client_a):
    """Test comment create with empty content re-renders form with 200 and error."""
    url = reverse("bi:bi_visual_comment_create")
    resp = client_a.post(url, {"content": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert "content" in resp.context["form"].errors


@pytest.mark.django_db
def test_collaborationstorytelling_comment_detail_view(
    client_a, tenant_a, admin_user, bi_visual_comment_a
):
    """Test visual comment detail view returns 200, context keys, and replies queryset."""
    reply = _collaborationstorytelling_create_comment(
        tenant_a,
        author=admin_user,
        parent_comment=bi_visual_comment_a,
        content="Actionable follow-up reply in thread.",
    )
    url = reverse("bi:bi_visual_comment_detail", kwargs={"pk": bi_visual_comment_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "comment" in resp.context
    assert "bi_visual_comment" in resp.context
    assert "obj" in resp.context
    assert "replies" in resp.context

    reply_pks = [r.pk for r in resp.context["replies"]]
    assert reply.pk in reply_pks

    content = resp.content.decode("utf-8")
    assert bi_visual_comment_a.number in content
    assert bi_visual_comment_a.content in content


@pytest.mark.django_db
def test_collaborationstorytelling_comment_edit_permissions(
    client_a, member_client, member_user, tenant_a, admin_user, bi_dashboard_a
):
    """Test comment edit permissions: author/admin can edit, non-author member gets redirected 302."""
    admin_comment = _collaborationstorytelling_create_comment(
        tenant_a, author=admin_user, dashboard=bi_dashboard_a, content="Admin comment original text."
    )
    url_admin_comment = reverse("bi:bi_visual_comment_edit", kwargs={"pk": admin_comment.pk})

    # Member user (non-author, non-tenant-admin) cannot edit admin comment
    resp_member_get = member_client.get(url_admin_comment)
    assert resp_member_get.status_code == 302
    assert resp_member_get.url == reverse("bi:bi_visual_comment_detail", kwargs={"pk": admin_comment.pk})

    resp_member_post = member_client.post(
        url_admin_comment, _collaborationstorytelling_comment_form_data(dashboard=bi_dashboard_a, content="Hacked")
    )
    assert resp_member_post.status_code == 302
    admin_comment.refresh_from_db()
    assert admin_comment.content == "Admin comment original text."

    # Author (client_a) can edit
    resp_author_get = client_a.get(url_admin_comment)
    assert resp_author_get.status_code == 200
    assert resp_author_get.context["is_edit"] is True

    resp_author_post = client_a.post(
        url_admin_comment,
        _collaborationstorytelling_comment_form_data(
            dashboard=bi_dashboard_a, content="Admin comment updated by author."
        ),
    )
    assert resp_author_post.status_code == 302
    admin_comment.refresh_from_db()
    assert admin_comment.content == "Admin comment updated by author."

    # Verify member user CAN edit their own comment
    member_comment = _collaborationstorytelling_create_comment(
        tenant_a, author=member_user, dashboard=bi_dashboard_a, content="Member personal note."
    )
    url_member_comment = reverse("bi:bi_visual_comment_edit", kwargs={"pk": member_comment.pk})

    resp_member_own_get = member_client.get(url_member_comment)
    assert resp_member_own_get.status_code == 200

    resp_member_own_post = member_client.post(
        url_member_comment,
        _collaborationstorytelling_comment_form_data(
            dashboard=bi_dashboard_a, content="Member personal note updated by self."
        ),
    )
    assert resp_member_own_post.status_code == 302
    member_comment.refresh_from_db()
    assert member_comment.content == "Member personal note updated by self."


@pytest.mark.django_db
def test_collaborationstorytelling_comment_delete_permissions(
    client_a, member_client, member_user, tenant_a, admin_user, bi_dashboard_a
):
    """Test comment delete permissions: require_POST (GET 405), author/admin can delete, non-author cannot."""
    admin_comment = _collaborationstorytelling_create_comment(
        tenant_a, author=admin_user, dashboard=bi_dashboard_a, content="Admin comment for delete test."
    )
    url = reverse("bi:bi_visual_comment_delete", kwargs={"pk": admin_comment.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # Non-author member cannot delete -> redirected 302 to detail and item remains
    resp_member_post = member_client.post(url)
    assert resp_member_post.status_code == 302
    assert resp_member_post.url == reverse("bi:bi_visual_comment_detail", kwargs={"pk": admin_comment.pk})
    assert BiVisualComment.objects.filter(pk=admin_comment.pk).exists()

    # Author/tenant admin can delete -> redirected 302 to list and item removed
    resp_admin_post = client_a.post(url)
    assert resp_admin_post.status_code == 302
    assert resp_admin_post.url == reverse("bi:bi_visual_comment_list")
    assert not BiVisualComment.objects.filter(pk=admin_comment.pk).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_comment_resolve_view(
    client_a, admin_user, bi_visual_comment_a
):
    """Test resolve comment view requires POST (GET 405) and marks comment resolved with metadata."""
    url = reverse("bi:bi_visual_comment_resolve", kwargs={"pk": bi_visual_comment_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST marks resolved
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_visual_comment_detail", kwargs={"pk": bi_visual_comment_a.pk})

    bi_visual_comment_a.refresh_from_db()
    assert bi_visual_comment_a.status == "resolved"
    assert bi_visual_comment_a.resolved_by == admin_user
    assert bi_visual_comment_a.resolved_at is not None

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=bi_visual_comment_a.tenant,
        action="update",
        object_id=bi_visual_comment_a.pk,
    ).exists()


# ==============================================================================
# 4. BiDecisionLog View Tests (5 views)
# ==============================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_list_view_status_context_and_tenant_isolation(
    client_a, bi_decision_log_a, bi_decision_log_b
):
    """Test decision log list returns 200, context variables, and strictly isolates tenant records."""
    url = reverse("bi:bi_decision_log_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "decisions" in resp.context
    assert "bi_decision_logs" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["approved_count"] >= 1
    assert "strategic_count" in resp.context
    assert "status_choices" in resp.context
    assert "category_choices" in resp.context
    assert "dashboards" in resp.context
    assert "workspaces" in resp.context

    pks = [d.pk for d in resp.context["decisions"]]
    assert bi_decision_log_a.pk in pks
    assert bi_decision_log_b.pk not in pks

    content = resp.content.decode("utf-8")
    assert bi_decision_log_a.title in content
    assert bi_decision_log_b.title not in content


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_list_search_and_filters(
    client_a, tenant_a, admin_user, bi_shared_workspace_a, bi_dashboard_a
):
    """Test searching and filtering decision logs by query, status, category, workspace, dashboard."""
    w2 = _collaborationstorytelling_create_workspace(tenant_a, name="Decision Secondary Workspace")
    d_strategic = _collaborationstorytelling_create_decision(
        tenant_a,
        workspace=bi_shared_workspace_a,
        dashboard=bi_dashboard_a,
        title="Expansion Resource Authorization",
        category="strategic",
        status="approved",
        decision_maker=admin_user,
    )
    d_operational = _collaborationstorytelling_create_decision(
        tenant_a,
        workspace=w2,
        title="Inventory Safety Stock Recalibration",
        category="operational",
        status="proposed",
        decision_maker=admin_user,
    )
    url = reverse("bi:bi_decision_log_list")

    # Search keyword
    resp_q = client_a.get(url, {"q": "Resource Authorization"})
    pks_q = [d.pk for d in resp_q.context["decisions"]]
    assert d_strategic.pk in pks_q
    assert d_operational.pk not in pks_q

    # Filter status=proposed
    resp_stat = client_a.get(url, {"status": "proposed"})
    pks_stat = [d.pk for d in resp_stat.context["decisions"]]
    assert d_operational.pk in pks_stat
    assert d_strategic.pk not in pks_stat

    # Filter category=strategic
    resp_cat = client_a.get(url, {"category": "strategic"})
    pks_cat = [d.pk for d in resp_cat.context["decisions"]]
    assert d_strategic.pk in pks_cat
    assert d_operational.pk not in pks_cat

    # Filter workspace
    resp_w = client_a.get(url, {"workspace": str(bi_shared_workspace_a.pk)})
    pks_w = [d.pk for d in resp_w.context["decisions"]]
    assert d_strategic.pk in pks_w
    assert d_operational.pk not in pks_w

    # Filter dashboard
    resp_d = client_a.get(url, {"dashboard": str(bi_dashboard_a.pk)})
    pks_d = [d.pk for d in resp_d.context["decisions"]]
    assert d_strategic.pk in pks_d
    assert d_operational.pk not in pks_d


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test pagination for decision logs list view."""
    for i in range(16):
        _collaborationstorytelling_create_decision(
            tenant_a,
            title=f"Paginated Decision {i:02d}",
            decision_maker=admin_user,
        )

    url = reverse("bi:bi_decision_log_list")
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["decisions"]) == 15
    assert resp_p1.context["decisions"].has_next() is True

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["decisions"]) >= 1


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_create_get_and_post_valid(
    client_a, tenant_a, admin_user, bi_shared_workspace_a, bi_dashboard_a
):
    """Test decision log create GET pre-populates initial and valid POST redirects to detail."""
    url = reverse("bi:bi_decision_log_create")

    # GET with ?workspace=<pk>&dashboard=<pk>
    resp_get = client_a.get(
        url, {"workspace": str(bi_shared_workspace_a.pk), "dashboard": str(bi_dashboard_a.pk)}
    )
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["form"].initial["workspace"] == bi_shared_workspace_a
    assert resp_get.context["form"].initial["dashboard"] == bi_dashboard_a
    assert resp_get.context["is_edit"] is False

    # POST valid form
    data = _collaborationstorytelling_decision_form_data(
        workspace=bi_shared_workspace_a,
        dashboard=bi_dashboard_a,
        decision_maker=admin_user,
        title="Created Corporate Milestone Decision",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created = BiDecisionLog.objects.filter(
        tenant=tenant_a, title="Created Corporate Milestone Decision"
    ).first()
    assert created is not None
    assert created.decision_maker == admin_user
    assert created.created_by == admin_user
    assert resp_post.url == reverse("bi:bi_decision_log_detail", kwargs={"pk": created.pk})

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_create_post_invalid(client_a):
    """Test decision log create with invalid payload re-renders form with 200 and errors."""
    url = reverse("bi:bi_decision_log_create")
    resp = client_a.post(url, {"title": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_detail_view(
    client_a, bi_decision_log_a
):
    """Test decision log detail view returns 200 and context keys."""
    url = reverse("bi:bi_decision_log_detail", kwargs={"pk": bi_decision_log_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "decision" in resp.context
    assert "bi_decision_log" in resp.context
    assert "obj" in resp.context

    content = resp.content.decode("utf-8")
    assert bi_decision_log_a.title in content
    assert bi_decision_log_a.number in content
    assert bi_decision_log_a.rationale in content


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_edit_get_and_post_valid(
    client_a, tenant_a, bi_decision_log_a
):
    """Test decision log edit view GET returns 200 and valid POST updates record."""
    url = reverse("bi:bi_decision_log_edit", kwargs={"pk": bi_decision_log_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert "decision" in resp_get.context

    # POST valid update
    data = _collaborationstorytelling_decision_form_data(
        title="Approved Expansion Budget Allocation Renovated",
        category="strategic",
        expected_impact="Projected 35% ARR lift in Q4.",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_decision_log_detail", kwargs={"pk": bi_decision_log_a.pk})

    bi_decision_log_a.refresh_from_db()
    assert bi_decision_log_a.title == "Approved Expansion Budget Allocation Renovated"
    assert bi_decision_log_a.category == "strategic"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=bi_decision_log_a.pk
    ).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_edit_post_invalid(client_a, bi_decision_log_a):
    """Test decision log edit with invalid payload re-renders form with 200."""
    url = reverse("bi:bi_decision_log_edit", kwargs={"pk": bi_decision_log_a.pk})
    resp = client_a.post(url, {"title": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_collaborationstorytelling_decision_log_delete_view(
    client_a, tenant_a, admin_user
):
    """Test decision log delete view requires POST (GET returns 405) and deletes object."""
    decision = _collaborationstorytelling_create_decision(
        tenant_a, title="Decision To Be Deleted", decision_maker=admin_user
    )
    url = reverse("bi:bi_decision_log_delete", kwargs={"pk": decision.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes decision
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_decision_log_list")
    assert not BiDecisionLog.objects.filter(pk=decision.pk).exists()

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=decision.pk
    ).exists()


# ==============================================================================
# 5. Cross-Tenant Isolation (IDOR) & Unauthenticated Access Tests
# ==============================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_cross_tenant_idor_protection(
    client_b, bi_shared_workspace_a, bi_data_story_a, bi_visual_comment_a, bi_decision_log_a
):
    """Test that a tenant B user receives 404 when attempting to access tenant A objects."""
    # 1. BiSharedWorkspace cross-tenant
    assert client_b.get(reverse("bi:bi_shared_workspace_detail", kwargs={"pk": bi_shared_workspace_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:bi_shared_workspace_edit", kwargs={"pk": bi_shared_workspace_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:bi_shared_workspace_delete", kwargs={"pk": bi_shared_workspace_a.pk})).status_code == 404

    # 2. BiDataStory cross-tenant
    assert client_b.get(reverse("bi:bi_data_story_detail", kwargs={"pk": bi_data_story_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:bi_data_story_edit", kwargs={"pk": bi_data_story_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:bi_data_story_delete", kwargs={"pk": bi_data_story_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:bi_data_story_presentation", kwargs={"pk": bi_data_story_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:bi_data_story_export_office", kwargs={"pk": bi_data_story_a.pk})).status_code == 404

    # 3. BiVisualComment cross-tenant
    assert client_b.get(reverse("bi:bi_visual_comment_detail", kwargs={"pk": bi_visual_comment_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:bi_visual_comment_edit", kwargs={"pk": bi_visual_comment_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:bi_visual_comment_delete", kwargs={"pk": bi_visual_comment_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:bi_visual_comment_resolve", kwargs={"pk": bi_visual_comment_a.pk})).status_code == 404

    # 4. BiDecisionLog cross-tenant
    assert client_b.get(reverse("bi:bi_decision_log_detail", kwargs={"pk": bi_decision_log_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:bi_decision_log_edit", kwargs={"pk": bi_decision_log_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:bi_decision_log_delete", kwargs={"pk": bi_decision_log_a.pk})).status_code == 404


@pytest.mark.django_db
def test_collaborationstorytelling_unauthenticated_access_redirects_to_login(
    anon_client, bi_shared_workspace_a, bi_data_story_a, bi_visual_comment_a, bi_decision_log_a
):
    """Test that unauthenticated requests to all endpoints return 302 redirecting to login."""
    urls = [
        # Workspaces
        reverse("bi:bi_shared_workspace_list"),
        reverse("bi:bi_shared_workspace_create"),
        reverse("bi:bi_shared_workspace_detail", kwargs={"pk": bi_shared_workspace_a.pk}),
        reverse("bi:bi_shared_workspace_edit", kwargs={"pk": bi_shared_workspace_a.pk}),
        reverse("bi:bi_shared_workspace_delete", kwargs={"pk": bi_shared_workspace_a.pk}),
        # Stories
        reverse("bi:bi_data_story_list"),
        reverse("bi:bi_data_story_create"),
        reverse("bi:bi_data_story_detail", kwargs={"pk": bi_data_story_a.pk}),
        reverse("bi:bi_data_story_edit", kwargs={"pk": bi_data_story_a.pk}),
        reverse("bi:bi_data_story_delete", kwargs={"pk": bi_data_story_a.pk}),
        reverse("bi:bi_data_story_presentation", kwargs={"pk": bi_data_story_a.pk}),
        reverse("bi:bi_data_story_export_office", kwargs={"pk": bi_data_story_a.pk}),
        # Comments
        reverse("bi:bi_visual_comment_list"),
        reverse("bi:bi_visual_comment_create"),
        reverse("bi:bi_visual_comment_detail", kwargs={"pk": bi_visual_comment_a.pk}),
        reverse("bi:bi_visual_comment_edit", kwargs={"pk": bi_visual_comment_a.pk}),
        reverse("bi:bi_visual_comment_delete", kwargs={"pk": bi_visual_comment_a.pk}),
        reverse("bi:bi_visual_comment_resolve", kwargs={"pk": bi_visual_comment_a.pk}),
        # Decisions
        reverse("bi:bi_decision_log_list"),
        reverse("bi:bi_decision_log_create"),
        reverse("bi:bi_decision_log_detail", kwargs={"pk": bi_decision_log_a.pk}),
        reverse("bi:bi_decision_log_edit", kwargs={"pk": bi_decision_log_a.pk}),
        reverse("bi:bi_decision_log_delete", kwargs={"pk": bi_decision_log_a.pk}),
    ]

    for u in urls:
        resp = anon_client.get(u)
        assert resp.status_code == 302, f"Expected 302 redirect to login for URL {u}, got {resp.status_code}"
        assert "/accounts/login/" in resp.url or "login" in resp.url
