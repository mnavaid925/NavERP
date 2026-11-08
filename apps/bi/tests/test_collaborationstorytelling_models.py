"""Unit tests for Sub-module 10.18 Collaboration & Data Storytelling models.

Models covered:
- BiSharedWorkspace (WSPC)
- BiDataStory (DSTY)
- BiVisualComment (VCOM)
- BiDecisionLog (DLOG)
"""
from datetime import date
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.bi.models import (
    BiDashboard,
    BiDashboardWidget,
    BiDataStory,
    BiDecisionLog,
    BiSharedWorkspace,
    BiVisualComment,
    KpiDefinition,
    ReportDefinition,
)
from apps.core.models import OrgUnit, Tenant

User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _collaborationstorytelling_)
# ---------------------------------------------------------------------------


def _collaborationstorytelling_choice_keys(choices):
    """Return list of valid key identifiers from Django model choices list."""
    return [key for key, _label in choices]


def _collaborationstorytelling_create_workspace(tenant, name="Strategy & Analytics Workspace", **kwargs):
    """Helper to create a BiSharedWorkspace with sensible defaults."""
    defaults = {
        "name": name,
        "description": "Shared analytical workspace for executive business reviews.",
        "default_access_level": "contributor",
        "status": "active",
        "is_public": False,
        "is_favorite": False,
        "color": "#3b82f6",
        "icon": "folder",
        "pinned_dashboard_ids": [],
        "pinned_report_ids": [],
        "pinned_story_ids": [],
        "members_json": [],
    }
    defaults.update(kwargs)
    return BiSharedWorkspace.objects.create(tenant=tenant, **defaults)


def _collaborationstorytelling_create_story(tenant, title="Executive Performance Review", **kwargs):
    """Helper to create a BiDataStory with sensible defaults."""
    defaults = {
        "title": title,
        "summary": "High-level summary of Q3 performance and variances.",
        "story_type": "narrative_deck",
        "status": "draft",
        "theme": "light_executive",
        "allow_live_drilldown": True,
        "slides_data": [
            {
                "id": "slide_1",
                "title": "Revenue Overview",
                "visual_type": "kpi_card",
                "narrative": "ARR expanded by 18% quarter-over-quarter.",
            }
        ],
        "excel_export_settings": {"include_raw_tables": True},
    }
    defaults.update(kwargs)
    return BiDataStory.objects.create(tenant=tenant, **defaults)


def _collaborationstorytelling_create_comment(tenant, content="Please verify margin divergence in Region West.", **kwargs):
    """Helper to create a BiVisualComment with sensible defaults."""
    defaults = {
        "target_type": "dashboard",
        "content": content,
        "status": "open",
        "priority": "medium",
        "coordinate_x": 45.0,
        "coordinate_y": 60.0,
        "filter_snapshot": {"fiscal_year": 2026, "region": "West"},
        "mentions_json": ["@finance_lead"],
    }
    defaults.update(kwargs)
    return BiVisualComment.objects.create(tenant=tenant, **defaults)


def _collaborationstorytelling_create_decision(tenant, title="Approve Enterprise Expansion Plan", **kwargs):
    """Helper to create a BiDecisionLog with sensible defaults."""
    defaults = {
        "title": title,
        "category": "strategic",
        "status": "approved",
        "decision_date": date(2026, 11, 1),
        "problem_statement": "Territory capacity reached 98% saturation.",
        "rationale": "Direct capital allocation toward secondary market sales pods.",
        "alternatives_considered": "Maintain status quo or outsource distribution.",
        "expected_impact": "Accelerate secondary territory revenue growth by 25%.",
        "actual_outcome": "",
        "show_on_charts": True,
        "marker_style": "pin_flag",
        "marker_color": "#10b981",
        "supporting_documents": ["https://docs.acme.corp/expansion_plan.pdf"],
    }
    defaults.update(kwargs)
    return BiDecisionLog.objects.create(tenant=tenant, **defaults)


# ===========================================================================
# 1. BiSharedWorkspace Model Tests (WSPC)
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_fixture_and_str(bi_shared_workspace_a):
    """Test BiSharedWorkspace fixture from conftest, prefix, and __str__."""
    assert bi_shared_workspace_a.pk is not None
    assert bi_shared_workspace_a.number.startswith("WSPC-")
    expected_str = f"{bi_shared_workspace_a.number} - {bi_shared_workspace_a.name}"
    assert str(bi_shared_workspace_a) == expected_str


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_autonumbering(tenant_a):
    """Test auto-number sequence WSPC-##### increments monotonically per tenant."""
    w1 = _collaborationstorytelling_create_workspace(tenant_a, name="Workspace Alpha")
    w2 = _collaborationstorytelling_create_workspace(tenant_a, name="Workspace Beta")

    assert w1.number.startswith("WSPC-")
    assert w2.number.startswith("WSPC-")
    num1 = int(w1.number.split("-")[1])
    num2 = int(w2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_defaults(tenant_a):
    """Verify default field values on BiSharedWorkspace."""
    w = BiSharedWorkspace.objects.create(tenant=tenant_a, name="Default Settings Workspace")
    assert w.default_access_level == "contributor"
    assert w.status == "active"
    assert w.is_public is False
    assert w.is_favorite is False
    assert w.color == "#3b82f6"
    assert w.icon == "folder"
    assert w.pinned_dashboard_ids == []
    assert w.pinned_report_ids == []
    assert w.pinned_story_ids == []
    assert w.members_json == []
    assert w.slug == "default-settings-workspace"


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_choices():
    """Verify ACCESS_LEVEL_CHOICES and STATUS_CHOICES keys in BiSharedWorkspace."""
    access_keys = _collaborationstorytelling_choice_keys(BiSharedWorkspace.ACCESS_LEVEL_CHOICES)
    assert "viewer" in access_keys
    assert "contributor" in access_keys
    assert "member" in access_keys
    assert "admin" in access_keys

    status_keys = _collaborationstorytelling_choice_keys(BiSharedWorkspace.STATUS_CHOICES)
    assert "active" in status_keys
    assert "archived" in status_keys


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_slug_generation_and_uniqueness(tenant_a):
    """Verify automatic slug generation and collision deduplication within same tenant."""
    w1 = _collaborationstorytelling_create_workspace(tenant_a, name="Finance Operations")
    w2 = _collaborationstorytelling_create_workspace(tenant_a, name="Finance Operations")
    w3 = _collaborationstorytelling_create_workspace(tenant_a, name="Finance Operations")

    assert w1.slug == "finance-operations"
    assert w2.slug == "finance-operations-1"
    assert w3.slug == "finance-operations-2"


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_same_slug_different_tenants(tenant_a, tenant_b):
    """Verify workspaces in different tenants can safely share the same slug."""
    w_a = _collaborationstorytelling_create_workspace(tenant_a, name="Global Performance")
    w_b = _collaborationstorytelling_create_workspace(tenant_b, name="Global Performance")

    assert w_a.slug == "global-performance"
    assert w_b.slug == "global-performance"
    assert w_a.tenant != w_b.tenant


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_color_validator_valid(tenant_a):
    """Verify HEX_COLOR_VALIDATOR accepts 3-digit and 6-digit hex codes."""
    for valid_color in ["#fff", "#FFF", "#3b82f6", "#2563EB", "#000000", "#123"]:
        w = _collaborationstorytelling_create_workspace(tenant_a, name=f"Color {valid_color}", color=valid_color)
        w.full_clean()
        assert w.color == valid_color


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_color_validator_invalid(tenant_a):
    """Verify HEX_COLOR_VALIDATOR raises ValidationError on invalid color values."""
    for invalid_color in ["red", "3b82f6", "#gggggg", "#12345", "#1234567", ""]:
        w = _collaborationstorytelling_create_workspace(tenant_a, name="Invalid Color", color=invalid_color)
        with pytest.raises(ValidationError):
            w.full_clean()


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_json_fields(tenant_a):
    """Verify JSON fields store and retrieve list structures correctly."""
    dash_ids = [101, 102, 103]
    rep_ids = [201, 202]
    story_ids = [301]
    members = [{"user_id": 1, "role": "admin"}, {"user_id": 2, "role": "viewer"}]

    w = _collaborationstorytelling_create_workspace(
        tenant_a,
        name="JSON Data Hub",
        pinned_dashboard_ids=dash_ids,
        pinned_report_ids=rep_ids,
        pinned_story_ids=story_ids,
        members_json=members,
    )
    w.refresh_from_db()
    assert w.pinned_dashboard_ids == dash_ids
    assert w.pinned_report_ids == rep_ids
    assert w.pinned_story_ids == story_ids
    assert w.members_json == members


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_relations(tenant_a, admin_user):
    """Verify department, owner, created_by, and reverse relations."""
    org = OrgUnit.objects.create(tenant=tenant_a, name="Enterprise Analytics", kind="department")
    w = _collaborationstorytelling_create_workspace(
        tenant_a,
        name="Org Workspace",
        department=org,
        owner=admin_user,
        created_by=admin_user,
    )
    assert w.department == org
    assert w.owner == admin_user
    assert w.created_by == admin_user
    assert w in org.bi_workspaces.all()
    assert w in admin_user.bi_owned_workspaces.all()
    assert w in admin_user.bi_created_workspaces.all()


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_unique_number_constraint(tenant_a):
    """Verify database unique constraint on (tenant, number)."""
    w1 = _collaborationstorytelling_create_workspace(tenant_a, name="Workspace Primary")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiSharedWorkspace.objects.create(
                tenant=tenant_a,
                number=w1.number,
                name="Duplicate Number Workspace",
            )


# ===========================================================================
# 2. BiDataStory Model Tests (DSTY)
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_story_fixture_and_str(bi_data_story_a):
    """Test BiDataStory fixture from conftest, prefix, and __str__."""
    assert bi_data_story_a.pk is not None
    assert bi_data_story_a.number.startswith("DSTY-")
    expected_str = f"{bi_data_story_a.number} - {bi_data_story_a.title}"
    assert str(bi_data_story_a) == expected_str


@pytest.mark.django_db
def test_collaborationstorytelling_story_autonumbering(tenant_a):
    """Test auto-number sequence DSTY-##### increments monotonically per tenant."""
    s1 = _collaborationstorytelling_create_story(tenant_a, title="Story Alpha")
    s2 = _collaborationstorytelling_create_story(tenant_a, title="Story Beta")

    assert s1.number.startswith("DSTY-")
    assert s2.number.startswith("DSTY-")
    num1 = int(s1.number.split("-")[1])
    num2 = int(s2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_collaborationstorytelling_story_defaults(tenant_a):
    """Verify default field values on BiDataStory."""
    s = BiDataStory.objects.create(tenant=tenant_a, title="Quarterly Operations Snapshot")
    assert s.story_type == "narrative_deck"
    assert s.status == "draft"
    assert s.theme == "light_executive"
    assert s.allow_live_drilldown is True
    assert s.slides_data == []
    assert s.slides_count == 0
    assert s.view_count == 0
    assert s.excel_export_settings == {}
    assert s.slug == "quarterly-operations-snapshot"
    assert len(s.office_embed_token) > 20


@pytest.mark.django_db
def test_collaborationstorytelling_story_choices():
    """Verify choices in BiDataStory."""
    story_keys = _collaborationstorytelling_choice_keys(BiDataStory.STORY_TYPE_CHOICES)
    assert "narrative_deck" in story_keys
    assert "annotated_walkthrough" in story_keys
    assert "dashboard_snapshot" in story_keys
    assert "kpi_review" in story_keys

    status_keys = _collaborationstorytelling_choice_keys(BiDataStory.STATUS_CHOICES)
    assert "draft" in status_keys
    assert "published" in status_keys
    assert "archived" in status_keys

    theme_keys = _collaborationstorytelling_choice_keys(BiDataStory.PRESENTATION_THEME_CHOICES)
    assert "light_executive" in theme_keys
    assert "dark_boardroom" in theme_keys
    assert "vibrant_accent" in theme_keys


@pytest.mark.django_db
def test_collaborationstorytelling_story_slides_count_automatic_calculation(tenant_a):
    """Verify save() method calculates slides_count from slides_data list length."""
    slides = [
        {"id": "slide_1", "title": "Overview", "visual_type": "kpi_card"},
        {"id": "slide_2", "title": "Deep Dive", "visual_type": "bar_chart"},
        {"id": "slide_3", "title": "Forecast", "visual_type": "line_trend"},
    ]
    s = _collaborationstorytelling_create_story(tenant_a, title="Three Slide Walkthrough", slides_data=slides)
    assert s.slides_count == 3

    s.slides_data = slides[:1]
    s.save()
    assert s.slides_count == 1

    s.slides_data = []
    s.save()
    assert s.slides_count == 0

    s.slides_data = {"non_list": True}
    s.save()
    assert s.slides_count == 0


@pytest.mark.django_db
def test_collaborationstorytelling_story_office_token_generation(tenant_a):
    """Verify ensure_office_token populates a secure random token if empty."""
    s = _collaborationstorytelling_create_story(tenant_a, title="Token Test Story", office_embed_token="")
    assert bool(s.office_embed_token)
    token1 = s.office_embed_token

    # Saving again should preserve existing token
    s.title = "Token Test Story Renamed"
    s.save()
    assert s.office_embed_token == token1


@pytest.mark.django_db
def test_collaborationstorytelling_story_slug_generation_and_collision_handling(tenant_a):
    """Verify automatic slug generation and collision handling."""
    s1 = _collaborationstorytelling_create_story(tenant_a, title="Board of Directors Review")
    s2 = _collaborationstorytelling_create_story(tenant_a, title="Board of Directors Review")

    assert s1.slug == "board-of-directors-review"
    assert s2.slug == "board-of-directors-review-1"


@pytest.mark.django_db
def test_collaborationstorytelling_story_same_slug_different_tenants(tenant_a, tenant_b):
    """Verify stories across different tenants do not collide on slug."""
    s_a = _collaborationstorytelling_create_story(tenant_a, title="Annual Summary")
    s_b = _collaborationstorytelling_create_story(tenant_b, title="Annual Summary")

    assert s_a.slug == "annual-summary"
    assert s_b.slug == "annual-summary"


@pytest.mark.django_db
def test_collaborationstorytelling_story_relations(tenant_a, admin_user, bi_shared_workspace_a):
    """Verify workspace container and author relations on BiDataStory."""
    s = _collaborationstorytelling_create_story(
        tenant_a,
        title="Contained Story",
        workspace=bi_shared_workspace_a,
        author=admin_user,
        created_by=admin_user,
    )
    assert s.workspace == bi_shared_workspace_a
    assert s.author == admin_user
    assert s.created_by == admin_user
    assert s in bi_shared_workspace_a.stories.all()
    assert s in admin_user.bi_authored_stories.all()
    assert s in admin_user.bi_created_stories.all()


@pytest.mark.django_db
def test_collaborationstorytelling_story_unique_number_constraint(tenant_a):
    """Verify database unique constraint on (tenant, number)."""
    s1 = _collaborationstorytelling_create_story(tenant_a, title="Primary Story")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiDataStory.objects.create(
                tenant=tenant_a,
                number=s1.number,
                title="Duplicate Story",
            )


# ===========================================================================
# 3. BiVisualComment Model Tests (VCOM)
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_comment_fixture_and_str(bi_visual_comment_a):
    """Test BiVisualComment fixture from conftest, prefix, and __str__."""
    assert bi_visual_comment_a.pk is not None
    assert bi_visual_comment_a.number.startswith("VCOM-")
    expected_str = f"{bi_visual_comment_a.number} ({bi_visual_comment_a.get_target_type_display()}) - {bi_visual_comment_a.status}"
    assert str(bi_visual_comment_a) == expected_str


@pytest.mark.django_db
def test_collaborationstorytelling_comment_autonumbering(tenant_a):
    """Test auto-number sequence VCOM-##### increments monotonically per tenant."""
    c1 = _collaborationstorytelling_create_comment(tenant_a, content="Annotation Alpha")
    c2 = _collaborationstorytelling_create_comment(tenant_a, content="Annotation Beta")

    assert c1.number.startswith("VCOM-")
    assert c2.number.startswith("VCOM-")
    num1 = int(c1.number.split("-")[1])
    num2 = int(c2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_collaborationstorytelling_comment_defaults(tenant_a):
    """Verify default field values on BiVisualComment."""
    c = BiVisualComment.objects.create(tenant=tenant_a, content="Raw Comment Body")
    assert c.target_type == "dashboard"
    assert c.status == "open"
    assert c.priority == "medium"
    assert c.filter_snapshot == {}
    assert c.mentions_json == []
    assert c.coordinate_x is None
    assert c.coordinate_y is None
    assert c.resolved_by is None
    assert c.resolved_at is None


@pytest.mark.django_db
def test_collaborationstorytelling_comment_choices():
    """Verify choices in BiVisualComment."""
    target_keys = _collaborationstorytelling_choice_keys(BiVisualComment.TARGET_TYPE_CHOICES)
    assert "dashboard" in target_keys
    assert "widget" in target_keys
    assert "report" in target_keys
    assert "story" in target_keys

    status_keys = _collaborationstorytelling_choice_keys(BiVisualComment.STATUS_CHOICES)
    assert "open" in status_keys
    assert "in_review" in status_keys
    assert "acknowledged" in status_keys
    assert "resolved" in status_keys

    priority_keys = _collaborationstorytelling_choice_keys(BiVisualComment.PRIORITY_CHOICES)
    assert "low" in priority_keys
    assert "medium" in priority_keys
    assert "high" in priority_keys
    assert "urgent" in priority_keys


@pytest.mark.django_db
def test_collaborationstorytelling_comment_coordinate_bounds_valid(tenant_a):
    """Verify coordinate_x and coordinate_y accept values within 0.0 to 100.0."""
    for x, y in [(0.0, 0.0), (50.5, 75.25), (100.0, 100.0), (None, None)]:
        c = _collaborationstorytelling_create_comment(
            tenant_a,
            content=f"Coord check ({x}, {y})",
            coordinate_x=x,
            coordinate_y=y,
        )
        c.full_clean()
        assert c.coordinate_x == x
        assert c.coordinate_y == y


@pytest.mark.django_db
def test_collaborationstorytelling_comment_coordinate_bounds_invalid_negative(tenant_a):
    """Verify coordinates below 0.0 raise ValidationError."""
    c = _collaborationstorytelling_create_comment(
        tenant_a,
        content="Negative coordinate comment",
        coordinate_x=-0.5,
        coordinate_y=50.0,
    )
    with pytest.raises(ValidationError):
        c.full_clean()

    c.coordinate_x = 50.0
    c.coordinate_y = -0.1
    with pytest.raises(ValidationError):
        c.full_clean()


@pytest.mark.django_db
def test_collaborationstorytelling_comment_coordinate_bounds_invalid_excessive(tenant_a):
    """Verify coordinates above 100.0 raise ValidationError."""
    c = _collaborationstorytelling_create_comment(
        tenant_a,
        content="Excessive coordinate comment",
        coordinate_x=100.1,
        coordinate_y=50.0,
    )
    with pytest.raises(ValidationError):
        c.full_clean()

    c.coordinate_x = 50.0
    c.coordinate_y = 105.0
    with pytest.raises(ValidationError):
        c.full_clean()


@pytest.mark.django_db
def test_collaborationstorytelling_comment_parent_reply_hierarchy_and_cascade(tenant_a):
    """Verify threaded replies hierarchy and cascade deletion of children."""
    parent = _collaborationstorytelling_create_comment(tenant_a, content="Root discussion comment")
    reply1 = _collaborationstorytelling_create_comment(tenant_a, content="Reply 1", parent_comment=parent)
    reply2 = _collaborationstorytelling_create_comment(tenant_a, content="Reply 2", parent_comment=parent)

    assert reply1.parent_comment == parent
    assert reply2.parent_comment == parent
    assert list(parent.replies.all()) == [reply2, reply1]  # ordering is -created_at

    # Deleting parent cascades to replies
    parent_id = parent.pk
    parent.delete()
    assert not BiVisualComment.objects.filter(pk=parent_id).exists()
    assert not BiVisualComment.objects.filter(pk=reply1.pk).exists()
    assert not BiVisualComment.objects.filter(pk=reply2.pk).exists()


@pytest.mark.django_db
def test_collaborationstorytelling_comment_mark_resolved(tenant_a, admin_user):
    """Verify mark_resolved helper sets status, resolved_by, and timestamp."""
    c = _collaborationstorytelling_create_comment(tenant_a, content="Pending resolution annotation")
    assert c.status == "open"
    assert c.resolved_by is None
    assert c.resolved_at is None

    c.mark_resolved(admin_user)
    c.save()

    c.refresh_from_db()
    assert c.status == "resolved"
    assert c.resolved_by == admin_user
    assert c.resolved_at is not None


@pytest.mark.django_db
def test_collaborationstorytelling_comment_relations(
    tenant_a,
    admin_user,
    bi_dashboard_a,
    bi_data_story_a,
):
    """Verify foreign key relations to dashboard, story, author, and resolved_by."""
    c = _collaborationstorytelling_create_comment(
        tenant_a,
        content="Targeted annotation",
        target_type="dashboard",
        dashboard=bi_dashboard_a,
        story=bi_data_story_a,
        author=admin_user,
    )
    assert c.dashboard == bi_dashboard_a
    assert c.story == bi_data_story_a
    assert c.author == admin_user
    assert c in bi_dashboard_a.comments.all()
    assert c in bi_data_story_a.comments.all()
    assert c in admin_user.bi_authored_comments.all()


@pytest.mark.django_db
def test_collaborationstorytelling_comment_unique_number_constraint(tenant_a):
    """Verify database unique constraint on (tenant, number)."""
    c1 = _collaborationstorytelling_create_comment(tenant_a, content="Original Comment")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiVisualComment.objects.create(
                tenant=tenant_a,
                number=c1.number,
                content="Duplicate Number Comment",
            )


# ===========================================================================
# 4. BiDecisionLog Model Tests (DLOG)
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_decision_fixture_and_str(bi_decision_log_a):
    """Test BiDecisionLog fixture from conftest, prefix, and __str__."""
    assert bi_decision_log_a.pk is not None
    assert bi_decision_log_a.number.startswith("DLOG-")
    expected_str = f"{bi_decision_log_a.number} - {bi_decision_log_a.title} ({bi_decision_log_a.decision_date})"
    assert str(bi_decision_log_a) == expected_str


@pytest.mark.django_db
def test_collaborationstorytelling_decision_autonumbering(tenant_a):
    """Test auto-number sequence DLOG-##### increments monotonically per tenant."""
    d1 = _collaborationstorytelling_create_decision(tenant_a, title="Decision Alpha")
    d2 = _collaborationstorytelling_create_decision(tenant_a, title="Decision Beta")

    assert d1.number.startswith("DLOG-")
    assert d2.number.startswith("DLOG-")
    num1 = int(d1.number.split("-")[1])
    num2 = int(d2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_collaborationstorytelling_decision_defaults(tenant_a):
    """Verify default field values on BiDecisionLog."""
    d = BiDecisionLog.objects.create(
        tenant=tenant_a,
        title="Automated Routing Decision",
        decision_date=date(2026, 11, 8),
        rationale="Optimize fulfillment dispatch logic.",
    )
    assert d.category == "operational"
    assert d.status == "approved"
    assert d.show_on_charts is True
    assert d.marker_style == "pin_flag"
    assert d.marker_color == "#10b981"
    assert d.supporting_documents == []
    assert d.slug == "automated-routing-decision"


@pytest.mark.django_db
def test_collaborationstorytelling_decision_choices():
    """Verify choices in BiDecisionLog."""
    cat_keys = _collaborationstorytelling_choice_keys(BiDecisionLog.CATEGORY_CHOICES)
    assert "strategic" in cat_keys
    assert "operational" in cat_keys
    assert "pricing" in cat_keys
    assert "budget" in cat_keys
    assert "inventory" in cat_keys

    status_keys = _collaborationstorytelling_choice_keys(BiDecisionLog.STATUS_CHOICES)
    assert "proposed" in status_keys
    assert "approved" in status_keys
    assert "superseded" in status_keys
    assert "revoked" in status_keys

    marker_keys = _collaborationstorytelling_choice_keys(BiDecisionLog.MARKER_STYLE_CHOICES)
    assert "pin_flag" in marker_keys
    assert "vertical_line_event" in marker_keys
    assert "highlight_band" in marker_keys


@pytest.mark.django_db
def test_collaborationstorytelling_decision_marker_color_validator_valid(tenant_a):
    """Verify marker_color validator accepts valid hex colors."""
    for color in ["#10b981", "#ef4444", "#3b82f6", "#fff", "#000"]:
        d = _collaborationstorytelling_create_decision(tenant_a, title=f"Color {color}", marker_color=color)
        d.full_clean()
        assert d.marker_color == color


@pytest.mark.django_db
def test_collaborationstorytelling_decision_marker_color_validator_invalid(tenant_a):
    """Verify marker_color validator rejects invalid color strings."""
    for bad_color in ["green", "#12", "#12345", "10b981", "#xyz123"]:
        d = _collaborationstorytelling_create_decision(tenant_a, title="Bad Color", marker_color=bad_color)
        with pytest.raises(ValidationError):
            d.full_clean()


@pytest.mark.django_db
def test_collaborationstorytelling_decision_slug_generation_and_uniqueness(tenant_a):
    """Verify slug generation and deduplication on title collisions."""
    d1 = _collaborationstorytelling_create_decision(tenant_a, title="Revise Tier 1 Pricing")
    d2 = _collaborationstorytelling_create_decision(tenant_a, title="Revise Tier 1 Pricing")

    assert d1.slug == "revise-tier-1-pricing"
    assert d2.slug == "revise-tier-1-pricing-1"


@pytest.mark.django_db
def test_collaborationstorytelling_decision_same_slug_different_tenants(tenant_a, tenant_b):
    """Verify decisions across different tenants do not collide on slug."""
    d_a = _collaborationstorytelling_create_decision(tenant_a, title="Budget Realignment")
    d_b = _collaborationstorytelling_create_decision(tenant_b, title="Budget Realignment")

    assert d_a.slug == "budget-realignment"
    assert d_b.slug == "budget-realignment"


@pytest.mark.django_db
def test_collaborationstorytelling_decision_relations(
    tenant_a,
    admin_user,
    bi_shared_workspace_a,
    bi_dashboard_a,
    kpi_definition_a,
):
    """Verify foreign key relations to workspace, dashboard, kpi, decision_maker, and created_by."""
    d = _collaborationstorytelling_create_decision(
        tenant_a,
        title="Integrated Milestone Decision",
        workspace=bi_shared_workspace_a,
        dashboard=bi_dashboard_a,
        kpi=kpi_definition_a,
        decision_maker=admin_user,
        created_by=admin_user,
    )
    assert d.workspace == bi_shared_workspace_a
    assert d.dashboard == bi_dashboard_a
    assert d.kpi == kpi_definition_a
    assert d.decision_maker == admin_user
    assert d.created_by == admin_user
    assert d in bi_shared_workspace_a.decision_logs.all()
    assert d in bi_dashboard_a.decision_logs.all()
    assert d in kpi_definition_a.decision_logs.all()
    assert d in admin_user.bi_made_decisions.all()
    assert d in admin_user.bi_created_decisions.all()


@pytest.mark.django_db
def test_collaborationstorytelling_decision_ordering(tenant_a):
    """Verify ordering by -decision_date, -created_at."""
    d1 = _collaborationstorytelling_create_decision(tenant_a, title="Older Decision", decision_date=date(2026, 1, 1))
    d2 = _collaborationstorytelling_create_decision(tenant_a, title="Newer Decision", decision_date=date(2026, 6, 1))
    d3 = _collaborationstorytelling_create_decision(tenant_a, title="Latest Decision", decision_date=date(2026, 11, 1))

    qs = list(BiDecisionLog.objects.filter(tenant=tenant_a, pk__in=[d1.pk, d2.pk, d3.pk]))
    assert qs == [d3, d2, d1]


@pytest.mark.django_db
def test_collaborationstorytelling_decision_unique_number_constraint(tenant_a):
    """Verify database unique constraint on (tenant, number)."""
    d1 = _collaborationstorytelling_create_decision(tenant_a, title="Primary Decision")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiDecisionLog.objects.create(
                tenant=tenant_a,
                number=d1.number,
                title="Duplicate Decision",
                decision_date=date(2026, 11, 1),
                rationale="Duplicate test",
            )


# ===========================================================================
# 5. Tenant Isolation and Cross-Cutting Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_tenant_isolation_workspaces(tenant_a, tenant_b):
    """Verify querysets for BiSharedWorkspace are strictly isolated by tenant."""
    w_a = _collaborationstorytelling_create_workspace(tenant_a, name="Acme Shared Hub")
    w_b = _collaborationstorytelling_create_workspace(tenant_b, name="Globex Shared Hub")

    qs_a = BiSharedWorkspace.objects.filter(tenant=tenant_a)
    qs_b = BiSharedWorkspace.objects.filter(tenant=tenant_b)

    assert w_a in qs_a
    assert w_b not in qs_a
    assert w_b in qs_b
    assert w_a not in qs_b


@pytest.mark.django_db
def test_collaborationstorytelling_tenant_isolation_stories(tenant_a, tenant_b):
    """Verify querysets for BiDataStory are strictly isolated by tenant."""
    s_a = _collaborationstorytelling_create_story(tenant_a, title="Acme Annual Review")
    s_b = _collaborationstorytelling_create_story(tenant_b, title="Globex Annual Review")

    qs_a = BiDataStory.objects.filter(tenant=tenant_a)
    qs_b = BiDataStory.objects.filter(tenant=tenant_b)

    assert s_a in qs_a
    assert s_b not in qs_a
    assert s_b in qs_b
    assert s_a not in qs_b


@pytest.mark.django_db
def test_collaborationstorytelling_tenant_isolation_comments(tenant_a, tenant_b):
    """Verify querysets for BiVisualComment are strictly isolated by tenant."""
    c_a = _collaborationstorytelling_create_comment(tenant_a, content="Acme Visual Note")
    c_b = _collaborationstorytelling_create_comment(tenant_b, content="Globex Visual Note")

    qs_a = BiVisualComment.objects.filter(tenant=tenant_a)
    qs_b = BiVisualComment.objects.filter(tenant=tenant_b)

    assert c_a in qs_a
    assert c_b not in qs_a
    assert c_b in qs_b
    assert c_a not in qs_b


@pytest.mark.django_db
def test_collaborationstorytelling_tenant_isolation_decisions(tenant_a, tenant_b):
    """Verify querysets for BiDecisionLog are strictly isolated by tenant."""
    d_a = _collaborationstorytelling_create_decision(tenant_a, title="Acme Price Policy")
    d_b = _collaborationstorytelling_create_decision(tenant_b, title="Globex Price Policy")

    qs_a = BiDecisionLog.objects.filter(tenant=tenant_a)
    qs_b = BiDecisionLog.objects.filter(tenant=tenant_b)

    assert d_a in qs_a
    assert d_b not in qs_a
    assert d_b in qs_b
    assert d_a not in qs_b


@pytest.mark.django_db
def test_collaborationstorytelling_models_meta_indexes_and_tables():
    """Verify table names and expected composite indexes on models."""
    assert BiSharedWorkspace._meta.db_table == "bi_shared_workspace"
    w_index_names = [idx.name for idx in BiSharedWorkspace._meta.indexes]
    assert "idx_wspc_ten_stat" in w_index_names
    assert "idx_swsp_ten_dacc" in w_index_names
    assert "idx_wspc_ten_dept" in w_index_names
    assert "idx_wspc_ten_owner" in w_index_names
    assert "idx_wspc_ten_created" in w_index_names

    assert BiDataStory._meta.db_table == "bi_data_story"
    s_index_names = [idx.name for idx in BiDataStory._meta.indexes]
    assert "idx_dsty_ten_stat" in s_index_names
    assert "idx_dsty_ten_type" in s_index_names
    assert "idx_dsty_ten_wspc" in s_index_names
    assert "idx_dsty_ten_author" in s_index_names
    assert "idx_dsty_ten_created" in s_index_names

    assert BiVisualComment._meta.db_table == "bi_visual_comment"
    c_index_names = [idx.name for idx in BiVisualComment._meta.indexes]
    assert "idx_vcom_ten_stat" in c_index_names
    assert "idx_vcom_ten_prio" in c_index_names
    assert "idx_vcom_ten_type" in c_index_names
    assert "idx_vcom_ten_dash" in c_index_names
    assert "idx_vcom_ten_story" in c_index_names
    assert "idx_vcom_ten_author" in c_index_names
    assert "idx_vcom_ten_created" in c_index_names

    assert BiDecisionLog._meta.db_table == "bi_decision_log"
    d_index_names = [idx.name for idx in BiDecisionLog._meta.indexes]
    assert "idx_dlog_ten_wspc" in d_index_names
    assert "idx_dlog_ten_stat" in d_index_names
    assert "idx_dlog_ten_cat" in d_index_names
    assert "idx_dlog_ten_date" in d_index_names
    assert "idx_dlog_ten_dash" in d_index_names
    assert "idx_dlog_ten_kpi" in d_index_names
    assert "idx_dlog_ten_created" in d_index_names
