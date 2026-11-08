"""Unit tests for Sub-module 10.18 Collaboration & Data Storytelling forms.

Forms covered:
- BiSharedWorkspaceForm (BiSharedWorkspace)
- BiDataStoryForm (BiDataStory)
- BiVisualCommentForm (BiVisualComment)
- BiDecisionLogForm (BiDecisionLog)
"""
import json
from datetime import date

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.bi.forms import (
    BiDataStoryForm,
    BiDecisionLogForm,
    BiSharedWorkspaceForm,
    BiVisualCommentForm,
)
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
from apps.core.models import OrgUnit

User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _collaborationstorytelling_)
# ---------------------------------------------------------------------------


def _collaborationstorytelling_create_org_unit(tenant, name="BI Analytics Dept"):
    """Helper to create a tenant-scoped OrgUnit record."""
    return OrgUnit.objects.create(tenant=tenant, name=name, kind="department")


def _collaborationstorytelling_create_second_dashboard(
    tenant, title="Secondary Operations Board", name=None, slug="sec-ops-board"
):
    """Helper to create a second tenant-scoped BiDashboard record."""
    final_title = name or title
    return BiDashboard.objects.create(
        tenant=tenant,
        title=final_title,
        slug=slug,
        is_published=True,
    )


def _collaborationstorytelling_create_report(
    tenant, name="Operational Test Report", slug="op-test-report"
):
    """Helper to create a tenant-scoped ReportDefinition record."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        slug=slug,
        category="sales",
        report_type="tabular",
    )


def _collaborationstorytelling_create_widget(
    tenant, dashboard, title="Region Variance Chart"
):
    """Helper to create a tenant-scoped BiDashboardWidget record on a dashboard."""
    return BiDashboardWidget.objects.create(
        tenant=tenant,
        dashboard=dashboard,
        title=title,
        widget_type="chart",
        pos_x=0,
        pos_y=0,
        width_cols=6,
        height_rows=4,
    )


def _collaborationstorytelling_valid_workspace_data(
    department=None, owner=None, **kwargs
):
    """Helper returning a valid data payload for BiSharedWorkspaceForm."""
    data = {
        "name": "Executive Collaboration Hub",
        "slug": "exec-collab-hub",
        "description": "Cross-functional collaborative workspace for business intelligence.",
        "default_access_level": "contributor",
        "status": "active",
        "is_public": False,
        "is_favorite": True,
        "color": "#3b82f6",
        "icon": "folder",
        "members_raw": '[{"username": "analyst1", "role": "contributor"}]',
    }
    if department:
        data["department"] = department.pk
    if owner:
        data["owner"] = owner.pk
    data.update(kwargs)
    return data


def _collaborationstorytelling_valid_story_data(
    workspace=None, author=None, **kwargs
):
    """Helper returning a valid data payload for BiDataStoryForm."""
    data = {
        "title": "Q3 Revenue Variance Walkthrough",
        "slug": "q3-rev-variance-walkthrough",
        "summary": "Detailed narrative covering regional variance and key operational drivers.",
        "story_type": "narrative_deck",
        "status": "draft",
        "theme": "light_executive",
        "allow_live_drilldown": True,
        "slides_data_raw": '[{"slide_num": 1, "title": "Revenue Overview", "narrative": "ARR expanded by 14%"}]',
    }
    if workspace:
        data["workspace"] = workspace.pk
    if author:
        data["author"] = author.pk
    data.update(kwargs)
    return data


def _collaborationstorytelling_valid_comment_data(
    dashboard=None,
    widget=None,
    report=None,
    story=None,
    parent_comment=None,
    **kwargs,
):
    """Helper returning a valid data payload for BiVisualCommentForm."""
    data = {
        "target_type": "dashboard",
        "content": "Investigate revenue divergence in Western region.",
        "status": "open",
        "priority": "medium",
        "coordinate_x": "25.0",
        "coordinate_y": "45.0",
        "slide_id": "",
    }
    if dashboard:
        data["dashboard"] = dashboard.pk
    if widget:
        data["widget"] = widget.pk
    if report:
        data["report"] = report.pk
    if story:
        data["story"] = story.pk
    if parent_comment:
        data["parent_comment"] = parent_comment.pk
    data.update(kwargs)
    return data


def _collaborationstorytelling_valid_decision_data(
    workspace=None,
    dashboard=None,
    widget=None,
    kpi=None,
    decision_maker=None,
    **kwargs,
):
    """Helper returning a valid data payload for BiDecisionLogForm."""
    data = {
        "title": "Authorize APAC Marketing Capital Reallocation",
        "slug": "authorize-apac-marketing-realloc",
        "category": "budget",
        "status": "approved",
        "decision_date": "2026-11-01",
        "problem_statement": "Marketing conversion dropped 8% across APAC territories.",
        "rationale": "Reallocate digital advertising funds into focused enterprise account pods.",
        "alternatives_considered": "Maintain budget status quo or pause outbound campaigns.",
        "expected_impact": "Accelerate secondary territory revenue growth by 20%.",
        "actual_outcome": "",
        "show_on_charts": True,
        "marker_style": "pin_flag",
        "marker_color": "#10b981",
        "review_date": "2026-12-01",
    }
    if workspace:
        data["workspace"] = workspace.pk
    if dashboard:
        data["dashboard"] = dashboard.pk
    if widget:
        data["widget"] = widget.pk
    if kpi:
        data["kpi"] = kpi.pk
    if decision_maker:
        data["decision_maker"] = decision_maker.pk
    data.update(kwargs)
    return data


# ===========================================================================
# 1. BiSharedWorkspaceForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_system_field_exclusions():
    """Verify system-managed fields are excluded from BiSharedWorkspaceForm."""
    form = BiSharedWorkspaceForm()
    system_fields = [
        "tenant",
        "number",
        "created_by",
        "created_at",
        "updated_at",
        "pinned_dashboard_ids",
        "pinned_report_ids",
        "pinned_story_ids",
        "members_json",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in BiSharedWorkspaceForm"
        )


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_valid_submission_and_save(tenant_a):
    """Verify valid form data creates a BiSharedWorkspace bound to tenant."""
    data = _collaborationstorytelling_valid_workspace_data()
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    workspace = form.save()
    assert workspace.pk is not None
    assert workspace.tenant == tenant_a
    assert workspace.name == "Executive Collaboration Hub"
    assert workspace.slug == "exec-collab-hub"
    assert workspace.default_access_level == "contributor"
    assert workspace.status == "active"
    assert workspace.is_favorite is True
    assert workspace.color == "#3b82f6"
    assert workspace.members_json == [{"username": "analyst1", "role": "contributor"}]


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_save_commit_false(tenant_a):
    """Verify commit=False sets instance attributes including members_json."""
    data = _collaborationstorytelling_valid_workspace_data()
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    workspace = form.save(commit=False)
    assert workspace.tenant == tenant_a
    assert workspace.members_json == [{"username": "analyst1", "role": "contributor"}]
    assert workspace.pk is None
    workspace.save()
    assert workspace.pk is not None


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_missing_required_name(tenant_a):
    """Verify missing required name field fails validation."""
    data = _collaborationstorytelling_valid_workspace_data(name="")
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_color_valid_hex_codes(tenant_a):
    """Verify valid 3-char and 6-char hex colors pass validation."""
    for valid_color in ["#3b82f6", "#fff", "#10b981", "#ABCDEF"]:
        data = _collaborationstorytelling_valid_workspace_data(color=valid_color)
        form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid color {valid_color} rejected: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_color_invalid_hex_rejected(tenant_a):
    """Verify invalid hex colors fail validation via HEX_COLOR_VALIDATOR."""
    for invalid_color in ["invalid-color", "3b82f6", "#12345", "#gggggg", "blue"]:
        data = _collaborationstorytelling_valid_workspace_data(color=invalid_color)
        form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "color" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_members_raw_valid_json_list(tenant_a):
    """Verify members_raw valid JSON array parses to python list on save."""
    members = [{"username": "dev1", "role": "admin"}, {"username": "qa1", "role": "viewer"}]
    data = _collaborationstorytelling_valid_workspace_data(members_raw=json.dumps(members))
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    workspace = form.save()
    assert workspace.members_json == members


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_members_raw_empty_defaults_to_list(tenant_a):
    """Verify empty or whitespace members_raw defaults to empty list."""
    data = _collaborationstorytelling_valid_workspace_data(members_raw="   ")
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    workspace = form.save()
    assert workspace.members_json == []


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_members_raw_invalid_json_syntax(tenant_a):
    """Verify malformed JSON syntax raises validation error on members_raw."""
    data = _collaborationstorytelling_valid_workspace_data(members_raw="{unclosed-json")
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "members_raw" in form.errors
    assert "Invalid JSON format" in form.errors["members_raw"][0]


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_members_raw_non_list_json(tenant_a):
    """Verify non-array JSON (e.g. dict or number) raises validation error on members_raw."""
    for payload in ['{"user": "analyst"}', "123", '"plain-string"']:
        data = _collaborationstorytelling_valid_workspace_data(members_raw=payload)
        form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "members_raw" in form.errors
        assert "Must be a JSON array of member objects." in form.errors["members_raw"][0]


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_members_raw_initial_population(
    tenant_a, bi_shared_workspace_a
):
    """Verify existing instance members_json populates initial members_raw."""
    bi_shared_workspace_a.members_json = [{"username": "lead1", "role": "admin"}]
    bi_shared_workspace_a.save()

    form = BiSharedWorkspaceForm(instance=bi_shared_workspace_a, tenant=tenant_a)
    assert form.fields["members_raw"].initial is not None
    parsed = json.loads(form.fields["members_raw"].initial)
    assert parsed == [{"username": "lead1", "role": "admin"}]


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_queryset_scoping(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify department and owner querysets are scoped to tenant."""
    dept_a = _collaborationstorytelling_create_org_unit(tenant_a, name="Acme Dept")
    dept_b = _collaborationstorytelling_create_org_unit(tenant_b, name="Globex Dept")

    form = BiSharedWorkspaceForm(tenant=tenant_a)
    assert dept_a in form.fields["department"].queryset
    assert dept_b not in form.fields["department"].queryset
    assert admin_user in form.fields["owner"].queryset
    assert admin_user_b not in form.fields["owner"].queryset


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_queryset_no_tenant():
    """Verify empty querysets when no tenant is supplied."""
    form = BiSharedWorkspaceForm(tenant=None)
    assert form.fields["department"].queryset.count() == 0
    assert form.fields["owner"].queryset.count() == 0


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_reject_foreign_department(
    tenant_a, tenant_b
):
    """Verify department from foreign tenant is rejected by choice validation."""
    dept_b = _collaborationstorytelling_create_org_unit(tenant_b, name="Foreign Dept")
    data = _collaborationstorytelling_valid_workspace_data(department=dept_b)
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "department" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_reject_foreign_owner(
    tenant_a, admin_user_b
):
    """Verify owner from foreign tenant is rejected by choice validation."""
    data = _collaborationstorytelling_valid_workspace_data(owner=admin_user_b)
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_defense_in_depth_foreign_department(
    tenant_a, tenant_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign department when queryset widened."""
    dept_b = _collaborationstorytelling_create_org_unit(tenant_b, name="Foreign Dept Widened")
    data = _collaborationstorytelling_valid_workspace_data(department=dept_b)
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    form.fields["department"].queryset = OrgUnit.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["department"]


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_defense_in_depth_foreign_owner(
    tenant_a, admin_user_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign owner when queryset widened."""
    data = _collaborationstorytelling_valid_workspace_data(owner=admin_user_b)
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    form.fields["owner"].queryset = User.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["owner"]


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_slug_uniqueness_same_tenant(tenant_a):
    """Verify duplicate slug within same tenant fails uniqueness validation."""
    BiSharedWorkspace.objects.create(
        tenant=tenant_a,
        number="WSPC-00099",
        name="Existing Workspace",
        slug="common-slug",
    )
    data = _collaborationstorytelling_valid_workspace_data(slug="common-slug")
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.errors.get("__all__", [])) or "slug" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_slug_allowed_different_tenants(
    tenant_a, tenant_b
):
    """Verify identical slug is allowed across different tenants."""
    BiSharedWorkspace.objects.create(
        tenant=tenant_b,
        number="WSPC-00099",
        name="Globex Workspace",
        slug="common-slug",
    )
    data = _collaborationstorytelling_valid_workspace_data(slug="common-slug")
    form = BiSharedWorkspaceForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Slug should be unique per tenant: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_workspace_form_widgets_and_attrs():
    """Verify form widgets and CSS class attributes."""
    form = BiSharedWorkspaceForm()
    assert "form-input" in form.fields["name"].widget.attrs["class"]
    assert "font-mono" in form.fields["slug"].widget.attrs["class"]
    assert "form-textarea" in form.fields["description"].widget.attrs["class"]
    assert form.fields["color"].widget.input_type == "color"


# ===========================================================================
# 2. BiDataStoryForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_system_field_exclusions():
    """Verify system-managed fields are excluded from BiDataStoryForm."""
    form = BiDataStoryForm()
    system_fields = [
        "tenant",
        "number",
        "office_embed_token",
        "created_by",
        "created_at",
        "updated_at",
        "slides_count",
        "view_count",
        "last_presented_at",
        "slides_data",
        "excel_export_settings",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in BiDataStoryForm"
        )


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_valid_submission_and_save(
    tenant_a, bi_shared_workspace_a, admin_user
):
    """Verify valid form data creates a BiDataStory bound to tenant."""
    data = _collaborationstorytelling_valid_story_data(
        workspace=bi_shared_workspace_a, author=admin_user
    )
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    story = form.save()
    assert story.pk is not None
    assert story.tenant == tenant_a
    assert story.title == "Q3 Revenue Variance Walkthrough"
    assert story.story_type == "narrative_deck"
    assert story.status == "draft"
    assert story.theme == "light_executive"
    assert story.workspace == bi_shared_workspace_a
    assert story.author == admin_user
    assert story.allow_live_drilldown is True
    assert len(story.slides_data) == 1
    assert story.slides_data[0]["title"] == "Revenue Overview"


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_save_commit_false(
    tenant_a, bi_shared_workspace_a
):
    """Verify commit=False sets instance attributes including slides_data."""
    data = _collaborationstorytelling_valid_story_data(workspace=bi_shared_workspace_a)
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    story = form.save(commit=False)
    assert story.tenant == tenant_a
    assert story.pk is None
    assert len(story.slides_data) == 1
    story.save()
    assert story.pk is not None


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_missing_required_title(tenant_a):
    """Verify missing required title field fails validation."""
    data = _collaborationstorytelling_valid_story_data(title="")
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_slides_data_raw_valid_list(
    tenant_a, bi_shared_workspace_a
):
    """Verify slides_data_raw valid JSON array parses to python list."""
    slides = [
        {"slide_num": 1, "title": "Intro", "narrative": "Executive Summary"},
        {"slide_num": 2, "title": "Deep Dive", "narrative": "Regional Breakdown"},
    ]
    data = _collaborationstorytelling_valid_story_data(
        workspace=bi_shared_workspace_a, slides_data_raw=json.dumps(slides)
    )
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    story = form.save()
    assert story.slides_data == slides


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_slides_data_raw_empty_defaults_to_list(
    tenant_a, bi_shared_workspace_a
):
    """Verify empty or whitespace slides_data_raw defaults to empty list."""
    data = _collaborationstorytelling_valid_story_data(
        workspace=bi_shared_workspace_a, slides_data_raw="   "
    )
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    story = form.save()
    assert story.slides_data == []


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_slides_data_raw_invalid_json_syntax(
    tenant_a, bi_shared_workspace_a
):
    """Verify malformed JSON syntax in slides_data_raw raises validation error."""
    data = _collaborationstorytelling_valid_story_data(
        workspace=bi_shared_workspace_a, slides_data_raw="[unclosed"
    )
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "slides_data_raw" in form.errors
    assert "Invalid JSON format for slides" in form.errors["slides_data_raw"][0]


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_slides_data_raw_non_list_json(
    tenant_a, bi_shared_workspace_a
):
    """Verify non-array JSON raises validation error on slides_data_raw."""
    for payload in ['{"slide": 1}', "999", '"hello"']:
        data = _collaborationstorytelling_valid_story_data(
            workspace=bi_shared_workspace_a, slides_data_raw=payload
        )
        form = BiDataStoryForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "slides_data_raw" in form.errors
        assert "Slides data must be a JSON array of slide objects." in form.errors["slides_data_raw"][0]


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_slides_data_raw_initial_population(
    tenant_a, bi_data_story_a
):
    """Verify existing instance slides_data populates initial slides_data_raw."""
    form = BiDataStoryForm(instance=bi_data_story_a, tenant=tenant_a)
    assert form.fields["slides_data_raw"].initial is not None
    parsed = json.loads(form.fields["slides_data_raw"].initial)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "Macro Overview"


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_queryset_scoping(
    tenant_a,
    tenant_b,
    bi_shared_workspace_a,
    bi_shared_workspace_b,
    admin_user,
    admin_user_b,
):
    """Verify workspace and author querysets are scoped to tenant."""
    form = BiDataStoryForm(tenant=tenant_a)
    assert bi_shared_workspace_a in form.fields["workspace"].queryset
    assert bi_shared_workspace_b not in form.fields["workspace"].queryset
    assert admin_user in form.fields["author"].queryset
    assert admin_user_b not in form.fields["author"].queryset


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_queryset_no_tenant():
    """Verify empty querysets when tenant is None."""
    form = BiDataStoryForm(tenant=None)
    assert form.fields["workspace"].queryset.count() == 0
    assert form.fields["author"].queryset.count() == 0


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_reject_foreign_workspace(
    tenant_a, bi_shared_workspace_b
):
    """Verify workspace from foreign tenant is rejected by choice validation."""
    data = _collaborationstorytelling_valid_story_data(workspace=bi_shared_workspace_b)
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "workspace" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_reject_foreign_author(
    tenant_a, admin_user_b
):
    """Verify author from foreign tenant is rejected by choice validation."""
    data = _collaborationstorytelling_valid_story_data(author=admin_user_b)
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "author" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_defense_in_depth_foreign_workspace(
    tenant_a, bi_shared_workspace_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign workspace when queryset widened."""
    data = _collaborationstorytelling_valid_story_data(workspace=bi_shared_workspace_b)
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    form.fields["workspace"].queryset = BiSharedWorkspace.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["workspace"]


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_defense_in_depth_foreign_author(
    tenant_a, admin_user_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign author when queryset widened."""
    data = _collaborationstorytelling_valid_story_data(author=admin_user_b)
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    form.fields["author"].queryset = User.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["author"]


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_slug_uniqueness_same_tenant(
    tenant_a, bi_shared_workspace_a
):
    """Verify duplicate slug within same tenant fails uniqueness validation."""
    BiDataStory.objects.create(
        tenant=tenant_a,
        number="DSTY-00088",
        title="Existing Story",
        slug="shared-story-slug",
        workspace=bi_shared_workspace_a,
    )
    data = _collaborationstorytelling_valid_story_data(
        workspace=bi_shared_workspace_a, slug="shared-story-slug"
    )
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.errors.get("__all__", [])) or "slug" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_slug_allowed_different_tenants(
    tenant_a, tenant_b, bi_shared_workspace_a, bi_shared_workspace_b
):
    """Verify identical slug is allowed on different tenants."""
    BiDataStory.objects.create(
        tenant=tenant_b,
        number="DSTY-00088",
        title="Globex Story",
        slug="shared-story-slug",
        workspace=bi_shared_workspace_b,
    )
    data = _collaborationstorytelling_valid_story_data(
        workspace=bi_shared_workspace_a, slug="shared-story-slug"
    )
    form = BiDataStoryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Story slug should be isolated per tenant: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_story_form_widgets_and_attrs():
    """Verify story form widgets and classes."""
    form = BiDataStoryForm()
    assert "form-input" in form.fields["title"].widget.attrs["class"]
    assert "font-mono" in form.fields["slug"].widget.attrs["class"]
    assert "form-textarea" in form.fields["summary"].widget.attrs["class"]
    assert "form-checkbox" in form.fields["allow_live_drilldown"].widget.attrs["class"]


# ===========================================================================
# 3. BiVisualCommentForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_system_field_exclusions():
    """Verify system-managed fields are excluded from BiVisualCommentForm."""
    form = BiVisualCommentForm()
    system_fields = [
        "tenant",
        "number",
        "author",
        "created_by",
        "created_at",
        "updated_at",
        "resolved_at",
        "resolved_by",
        "filter_snapshot",
        "mentions_json",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in BiVisualCommentForm"
        )


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_valid_submission_and_save(
    tenant_a, bi_dashboard_a, bi_widget_a
):
    """Verify valid comment form data saves and binds to tenant."""
    data = _collaborationstorytelling_valid_comment_data(
        dashboard=bi_dashboard_a, widget=bi_widget_a
    )
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    comment = form.save()
    assert comment.pk is not None
    assert comment.tenant == tenant_a
    assert comment.target_type == "dashboard"
    assert comment.dashboard == bi_dashboard_a
    assert comment.widget == bi_widget_a
    assert comment.content == "Investigate revenue divergence in Western region."
    assert comment.status == "open"
    assert comment.priority == "medium"
    assert comment.coordinate_x == 25.0
    assert comment.coordinate_y == 45.0


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_save_commit_false(tenant_a):
    """Verify commit=False yields unsaved instance with tenant assigned."""
    data = _collaborationstorytelling_valid_comment_data()
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    comment = form.save(commit=False)
    assert comment.tenant == tenant_a
    assert comment.pk is None
    comment.save()
    assert comment.pk is not None


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_missing_required_content(tenant_a):
    """Verify missing content field fails validation."""
    data = _collaborationstorytelling_valid_comment_data(content="")
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "content" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_coordinate_bounds_valid(tenant_a):
    """Verify coordinate_x and coordinate_y boundaries (0.0 to 100.0) are valid."""
    for coord in ["0.0", "50.5", "100.0"]:
        data = _collaborationstorytelling_valid_comment_data(
            coordinate_x=coord, coordinate_y=coord
        )
        form = BiVisualCommentForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Boundary coordinate {coord} rejected: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_coordinate_bounds_negative_rejected(
    tenant_a,
):
    """Verify negative coordinate percentages are rejected (min_value=0.0)."""
    data = _collaborationstorytelling_valid_comment_data(
        coordinate_x="-0.1", coordinate_y="-10.0"
    )
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "coordinate_x" in form.errors
    assert "coordinate_y" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_coordinate_bounds_exceed_100_rejected(
    tenant_a,
):
    """Verify coordinate percentages greater than 100.0 are rejected (max_value=100.0)."""
    data = _collaborationstorytelling_valid_comment_data(
        coordinate_x="100.1", coordinate_y="150.0"
    )
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "coordinate_x" in form.errors
    assert "coordinate_y" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_coordinate_none_allowed(tenant_a):
    """Verify coordinates are optional (required=False)."""
    data = _collaborationstorytelling_valid_comment_data(coordinate_x="", coordinate_y="")
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Coordinates should be optional: {form.errors}"
    comment = form.save()
    assert comment.coordinate_x is None
    assert comment.coordinate_y is None


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_self_parent_recursion_prevented(
    tenant_a, bi_visual_comment_a
):
    """Verify clean() prevents setting comment as its own parent_comment."""
    data = _collaborationstorytelling_valid_comment_data(
        parent_comment=bi_visual_comment_a
    )
    form = BiVisualCommentForm(
        data=data, instance=bi_visual_comment_a, tenant=tenant_a
    )
    form.fields["parent_comment"].queryset = BiVisualComment.objects.all()
    assert not form.is_valid()
    assert "parent_comment" in form.errors
    assert "A comment cannot be its own parent." in form.errors["parent_comment"]


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_parent_comment_queryset_excludes_self(
    tenant_a, bi_visual_comment_a
):
    """Verify parent_comment queryset excludes self.instance when editing."""
    form = BiVisualCommentForm(instance=bi_visual_comment_a, tenant=tenant_a)
    assert bi_visual_comment_a not in form.fields["parent_comment"].queryset


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_widget_must_belong_to_dashboard_valid(
    tenant_a, bi_dashboard_a, bi_widget_a
):
    """Verify widget belonging to the selected dashboard passes cross-record validation."""
    data = _collaborationstorytelling_valid_comment_data(
        dashboard=bi_dashboard_a, widget=bi_widget_a
    )
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Valid widget/dashboard rejected: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_widget_mismatched_dashboard_rejected(
    tenant_a, bi_dashboard_a
):
    """Verify widget belonging to a different dashboard raises cross-record error."""
    dash2 = _collaborationstorytelling_create_second_dashboard(
        tenant_a, title="Board 2", slug="board-2"
    )
    widget2 = _collaborationstorytelling_create_widget(
        tenant_a, dash2, title="Widget on Board 2"
    )

    data = _collaborationstorytelling_valid_comment_data(
        dashboard=bi_dashboard_a, widget=widget2
    )
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "widget" in form.errors
    assert (
        "The selected widget does not belong to the selected dashboard."
        in form.errors["widget"]
    )


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_resolved_status_guard_new_comment_rejected(
    tenant_a,
):
    """Verify submitting status='resolved' on a new comment is rejected without metadata."""
    data = _collaborationstorytelling_valid_comment_data(status="resolved")
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert (
        "Comments must be marked resolved via the Resolve action"
        in form.errors["status"][0]
    )


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_resolved_status_guard_resolved_instance_allowed(
    tenant_a, bi_visual_comment_a, admin_user
):
    """Verify an existing comment with resolved_at populated can retain status='resolved'."""
    bi_visual_comment_a.mark_resolved(admin_user)

    data = _collaborationstorytelling_valid_comment_data(status="resolved")
    form = BiVisualCommentForm(
        data=data, instance=bi_visual_comment_a, tenant=tenant_a
    )
    assert form.is_valid(), f"Resolved comment edit should be allowed: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_resolved_status_guard_open_status_allowed(
    tenant_a,
):
    """Verify open and in_review statuses do not require resolution metadata."""
    for st in ["open", "in_review", "acknowledged"]:
        data = _collaborationstorytelling_valid_comment_data(status=st)
        form = BiVisualCommentForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Status {st} should be valid: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_queryset_scoping(
    tenant_a,
    tenant_b,
    bi_dashboard_a,
    bi_dashboard_b,
    bi_data_story_a,
    bi_data_story_b,
    bi_visual_comment_a,
    bi_visual_comment_b,
):
    """Verify dashboard, widget, story, and parent_comment querysets are scoped to tenant."""
    form = BiVisualCommentForm(tenant=tenant_a)
    assert bi_dashboard_a in form.fields["dashboard"].queryset
    assert bi_dashboard_b not in form.fields["dashboard"].queryset
    assert bi_data_story_a in form.fields["story"].queryset
    assert bi_data_story_b not in form.fields["story"].queryset
    assert bi_visual_comment_a in form.fields["parent_comment"].queryset
    assert bi_visual_comment_b not in form.fields["parent_comment"].queryset


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_queryset_no_tenant():
    """Verify empty querysets when tenant is None."""
    form = BiVisualCommentForm(tenant=None)
    assert form.fields["dashboard"].queryset.count() == 0
    assert form.fields["widget"].queryset.count() == 0
    assert form.fields["report"].queryset.count() == 0
    assert form.fields["story"].queryset.count() == 0
    assert form.fields["parent_comment"].queryset.count() == 0


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_defense_in_depth_reject_foreign_dashboard(
    tenant_a, bi_dashboard_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign dashboard when queryset widened."""
    data = _collaborationstorytelling_valid_comment_data(dashboard=bi_dashboard_b)
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    form.fields["dashboard"].queryset = BiDashboard.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["dashboard"]


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_defense_in_depth_reject_foreign_widget(
    tenant_a, bi_widget_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign widget when queryset widened."""
    data = _collaborationstorytelling_valid_comment_data(widget=bi_widget_b)
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    form.fields["widget"].queryset = BiDashboardWidget.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["widget"]


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_defense_in_depth_reject_foreign_report(
    tenant_a, tenant_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign report when queryset widened."""
    report_b = _collaborationstorytelling_create_report(
        tenant_b, name="Globex Report", slug="globex-report"
    )
    data = _collaborationstorytelling_valid_comment_data(report=report_b)
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    form.fields["report"].queryset = ReportDefinition.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["report"]


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_defense_in_depth_reject_foreign_story(
    tenant_a, bi_data_story_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign story when queryset widened."""
    data = _collaborationstorytelling_valid_comment_data(story=bi_data_story_b)
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    form.fields["story"].queryset = BiDataStory.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["story"]


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_defense_in_depth_reject_foreign_parent_comment(
    tenant_a, bi_visual_comment_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign parent_comment when queryset widened."""
    data = _collaborationstorytelling_valid_comment_data(parent_comment=bi_visual_comment_b)
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    form.fields["parent_comment"].queryset = BiVisualComment.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["parent_comment"]


@pytest.mark.django_db
def test_collaborationstorytelling_comment_form_threaded_reply_valid(
    tenant_a, bi_visual_comment_a
):
    """Verify valid reply to an existing comment saves correctly."""
    data = _collaborationstorytelling_valid_comment_data(
        content="Affirmative, checking ERP ledger entries now.",
        parent_comment=bi_visual_comment_a,
    )
    form = BiVisualCommentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    reply = form.save()
    assert reply.parent_comment == bi_visual_comment_a


# ===========================================================================
# 4. BiDecisionLogForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_system_field_exclusions():
    """Verify system-managed fields are excluded from BiDecisionLogForm."""
    form = BiDecisionLogForm()
    system_fields = [
        "tenant",
        "number",
        "created_by",
        "created_at",
        "updated_at",
        "supporting_documents",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in BiDecisionLogForm"
        )


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_valid_submission_and_save(
    tenant_a,
    bi_shared_workspace_a,
    bi_dashboard_a,
    bi_widget_a,
    kpi_definition_a,
    admin_user,
):
    """Verify valid decision log form creates a BiDecisionLog bound to tenant."""
    data = _collaborationstorytelling_valid_decision_data(
        workspace=bi_shared_workspace_a,
        dashboard=bi_dashboard_a,
        widget=bi_widget_a,
        kpi=kpi_definition_a,
        decision_maker=admin_user,
    )
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    decision = form.save()
    assert decision.pk is not None
    assert decision.tenant == tenant_a
    assert decision.title == "Authorize APAC Marketing Capital Reallocation"
    assert decision.slug == "authorize-apac-marketing-realloc"
    assert decision.category == "budget"
    assert decision.status == "approved"
    assert decision.decision_date == date(2026, 11, 1)
    assert decision.workspace == bi_shared_workspace_a
    assert decision.dashboard == bi_dashboard_a
    assert decision.widget == bi_widget_a
    assert decision.kpi == kpi_definition_a
    assert decision.decision_maker == admin_user
    assert decision.show_on_charts is True
    assert decision.marker_style == "pin_flag"
    assert decision.marker_color == "#10b981"
    assert decision.review_date == date(2026, 12, 1)


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_save_commit_false(tenant_a):
    """Verify commit=False sets instance attributes with tenant assigned."""
    data = _collaborationstorytelling_valid_decision_data()
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    decision = form.save(commit=False)
    assert decision.tenant == tenant_a
    assert decision.pk is None
    decision.save()
    assert decision.pk is not None


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_missing_required_fields(tenant_a):
    """Verify missing required fields fail form validation."""
    for req in ["title", "decision_date", "rationale"]:
        data = _collaborationstorytelling_valid_decision_data()
        data[req] = ""
        form = BiDecisionLogForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert req in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_marker_color_valid_hex_codes(tenant_a):
    """Verify valid hex color formats for marker_color pass validation."""
    for valid_color in ["#10b981", "#ef4444", "#3b82f6", "#fff"]:
        data = _collaborationstorytelling_valid_decision_data(marker_color=valid_color)
        form = BiDecisionLogForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid marker color {valid_color} rejected: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_marker_color_invalid_hex_rejected(
    tenant_a,
):
    """Verify invalid hex colors fail validation via HEX_COLOR_VALIDATOR."""
    for invalid_color in ["not-a-color", "#xyz", "10b981", "#12345"]:
        data = _collaborationstorytelling_valid_decision_data(marker_color=invalid_color)
        form = BiDecisionLogForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "marker_color" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_widget_must_belong_to_dashboard_valid(
    tenant_a, bi_dashboard_a, bi_widget_a
):
    """Verify widget belonging to dashboard passes cross-record validation."""
    data = _collaborationstorytelling_valid_decision_data(
        dashboard=bi_dashboard_a, widget=bi_widget_a
    )
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Valid widget/dashboard rejected: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_widget_mismatched_dashboard_rejected(
    tenant_a, bi_dashboard_a
):
    """Verify widget belonging to another dashboard raises cross-record validation error."""
    dash2 = _collaborationstorytelling_create_second_dashboard(
        tenant_a, title="Executive Board 2", slug="exec-board-2"
    )
    widget2 = _collaborationstorytelling_create_widget(
        tenant_a, dash2, title="Widget on Board 2"
    )

    data = _collaborationstorytelling_valid_decision_data(
        dashboard=bi_dashboard_a, widget=widget2
    )
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "widget" in form.errors
    assert (
        "The selected widget does not belong to the selected dashboard."
        in form.errors["widget"]
    )


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_queryset_scoping(
    tenant_a,
    tenant_b,
    bi_shared_workspace_a,
    bi_shared_workspace_b,
    bi_dashboard_a,
    bi_dashboard_b,
    kpi_definition_a,
    kpi_definition_b,
    admin_user,
    admin_user_b,
):
    """Verify workspace, dashboard, kpi, and decision_maker querysets are scoped to tenant."""
    form = BiDecisionLogForm(tenant=tenant_a)
    assert bi_shared_workspace_a in form.fields["workspace"].queryset
    assert bi_shared_workspace_b not in form.fields["workspace"].queryset
    assert bi_dashboard_a in form.fields["dashboard"].queryset
    assert bi_dashboard_b not in form.fields["dashboard"].queryset
    assert kpi_definition_a in form.fields["kpi"].queryset
    assert kpi_definition_b not in form.fields["kpi"].queryset
    assert admin_user in form.fields["decision_maker"].queryset
    assert admin_user_b not in form.fields["decision_maker"].queryset


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_queryset_no_tenant():
    """Verify empty querysets when tenant is None."""
    form = BiDecisionLogForm(tenant=None)
    assert form.fields["workspace"].queryset.count() == 0
    assert form.fields["dashboard"].queryset.count() == 0
    assert form.fields["widget"].queryset.count() == 0
    assert form.fields["kpi"].queryset.count() == 0
    assert form.fields["decision_maker"].queryset.count() == 0


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_defense_in_depth_reject_foreign_workspace(
    tenant_a, bi_shared_workspace_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign workspace when queryset widened."""
    data = _collaborationstorytelling_valid_decision_data(workspace=bi_shared_workspace_b)
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    form.fields["workspace"].queryset = BiSharedWorkspace.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["workspace"]


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_defense_in_depth_reject_foreign_dashboard(
    tenant_a, bi_dashboard_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign dashboard when queryset widened."""
    data = _collaborationstorytelling_valid_decision_data(dashboard=bi_dashboard_b)
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    form.fields["dashboard"].queryset = BiDashboard.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["dashboard"]


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_defense_in_depth_reject_foreign_widget(
    tenant_a, bi_widget_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign widget when queryset widened."""
    data = _collaborationstorytelling_valid_decision_data(widget=bi_widget_b)
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    form.fields["widget"].queryset = BiDashboardWidget.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["widget"]


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_defense_in_depth_reject_foreign_kpi(
    tenant_a, kpi_definition_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign kpi when queryset widened."""
    data = _collaborationstorytelling_valid_decision_data(kpi=kpi_definition_b)
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    form.fields["kpi"].queryset = KpiDefinition.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["kpi"]


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_defense_in_depth_reject_foreign_decision_maker(
    tenant_a, admin_user_b
):
    """Verify defense-in-depth: reject_foreign rejects foreign decision_maker when queryset widened."""
    data = _collaborationstorytelling_valid_decision_data(decision_maker=admin_user_b)
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    form.fields["decision_maker"].queryset = User.objects.all()
    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["decision_maker"]


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_slug_uniqueness_same_tenant(tenant_a):
    """Verify duplicate slug on same tenant fails uniqueness validation."""
    BiDecisionLog.objects.create(
        tenant=tenant_a,
        number="DLOG-00077",
        title="Existing Decision",
        slug="common-decision-slug",
        decision_date="2026-11-01",
        rationale="Justification rationale",
    )
    data = _collaborationstorytelling_valid_decision_data(slug="common-decision-slug")
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.errors.get("__all__", [])) or "slug" in form.errors


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_slug_allowed_different_tenants(
    tenant_a, tenant_b
):
    """Verify duplicate slug across different tenants is permitted."""
    BiDecisionLog.objects.create(
        tenant=tenant_b,
        number="DLOG-00077",
        title="Globex Decision",
        slug="common-decision-slug",
        decision_date="2026-11-01",
        rationale="Globex rationale",
    )
    data = _collaborationstorytelling_valid_decision_data(slug="common-decision-slug")
    form = BiDecisionLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Slug should be isolated per tenant: {form.errors}"


@pytest.mark.django_db
def test_collaborationstorytelling_decision_form_widgets_and_attrs():
    """Verify decision form widgets and classes."""
    form = BiDecisionLogForm()
    assert "form-input" in form.fields["title"].widget.attrs["class"]
    assert "font-mono" in form.fields["slug"].widget.attrs["class"]
    assert "form-textarea" in form.fields["rationale"].widget.attrs["class"]
    assert form.fields["decision_date"].widget.input_type == "date"
    assert form.fields["marker_color"].widget.input_type == "color"
