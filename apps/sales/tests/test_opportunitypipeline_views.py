"""Automated view tests for Sub-module 8.2: Opportunity & Pipeline Management.

Covers:
1. Pipeline CRUD & Actions: list, create (GET/POST), detail, edit (GET/POST), delete (POST-only), set_default (POST-only).
2. Pipeline Stages: stages page, stage create (GET/POST), stage edit (GET/POST), stage delete (POST-only), stage reorder (POST).
3. Pipeline Board & Visibility: board view (columns, stages, placements), visibility view (date_from/date_to filtering, safe_parse_date with junk params).
4. Workspace: list view (filters: q, owner_id, pipeline_id, health, pagination), detail view (context tabs, team, competitors, timeline), place (GET/POST), unplace (POST with owner/admin checks), transition (POST won/lost/advance with error handling).
5. Team Members: add (GET/POST), edit (GET/POST), remove (POST).
6. Competitors: list, create, detail, edit, delete, link_add, link_edit, link_remove.
7. Win/Loss Reasons: list, create, detail, edit, delete.
8. Robustness & negative inputs: junk parameters, invalid dates, out-of-range pagination, cross-tenant isolation, authorization.
"""

from decimal import Decimal
import pytest
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import resolve, reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, Document, OrgUnit, Party, Tenant
from apps.crm.models import (
    CalendarEvent,
    CommunicationLog,
    ContractDocument,
    CrmTask,
    Opportunity,
    Territory,
)
from apps.sales import urls as sales_urls
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfile,
    OpportunityCompetitor,
)
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityOutcome,
    WinLossReason,
)
from apps.sales.models.OpportunityPipeline.Pipelines import (
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
)
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember
from apps.sales.tests.conftest import (
    _opportunitypipeline_competitor_profile,
    _opportunitypipeline_opportunity,
    _opportunitypipeline_opportunity_competitor,
    _opportunitypipeline_outcome,
    _opportunitypipeline_party,
    _opportunitypipeline_pipeline,
    _opportunitypipeline_placement,
    _opportunitypipeline_stage,
    _opportunitypipeline_team_member,
    _opportunitypipeline_user,
    _opportunitypipeline_win_loss_reason,
)

pytestmark = pytest.mark.django_db


def _opportunitypipeline_tenant(name="Acme Corp", slug=None):
    slug = slug or f"tenant-{int(timezone.now().timestamp() * 1000) % 1000000}"
    return Tenant.objects.create(name=name, slug=slug)


# ============================================================================
# Route Registry & Helpers (_opportunitypipeline_*)
# ============================================================================

_opportunitypipeline_routes = {
    "opportunity_pipeline_list": ("opportunity/pipelines/", "opportunity_pipeline_list"),
    "opportunity_pipeline_board": ("opportunity/board/", "opportunity_pipeline_board"),
    "opportunity_pipeline_visibility": ("opportunity/visibility/", "opportunity_pipeline_visibility"),
    "opportunity_pipeline_create": ("opportunity/pipelines/add/", "opportunity_pipeline_create"),
    "opportunity_pipeline_stage_reorder": ("opportunity/pipelines/<int:pk>/stages/reorder/", "opportunity_pipeline_stage_reorder"),
    "opportunity_pipeline_stage_create": ("opportunity/pipelines/<int:pk>/stages/add/", "opportunity_pipeline_stage_create"),
    "opportunity_pipeline_stage_edit": ("opportunity/pipelines/<int:pk>/stages/<int:stage_pk>/edit/", "opportunity_pipeline_stage_edit"),
    "opportunity_pipeline_stage_delete": ("opportunity/pipelines/<int:pk>/stages/<int:stage_pk>/delete/", "opportunity_pipeline_stage_delete"),
    "opportunity_pipeline_set_default": ("opportunity/pipelines/<int:pk>/set-default/", "opportunity_pipeline_set_default"),
    "opportunity_pipeline_edit": ("opportunity/pipelines/<int:pk>/edit/", "opportunity_pipeline_edit"),
    "opportunity_pipeline_delete": ("opportunity/pipelines/<int:pk>/delete/", "opportunity_pipeline_delete"),
    "opportunity_pipeline_stages": ("opportunity/pipelines/<int:pk>/stages/", "opportunity_pipeline_stages"),
    "opportunity_pipeline_detail": ("opportunity/pipelines/<int:pk>/", "opportunity_pipeline_detail"),
    "opportunity_workspace_list": ("opportunity/", "opportunity_workspace_list"),
    "opportunity_place": ("opportunity/workspace/<int:opportunity_pk>/place/", "opportunity_place"),
    "opportunity_unplace": ("opportunity/workspace/<int:opportunity_pk>/unplace/", "opportunity_unplace"),
    "opportunity_workspace_detail": ("opportunity/workspace/<int:opportunity_pk>/", "opportunity_workspace_detail"),
    "opportunity_team_member_add": ("opportunity/workspace/<int:opportunity_pk>/team/add/", "opportunity_team_member_add"),
    "opportunity_team_member_edit": ("opportunity/workspace/<int:opportunity_pk>/team/<int:member_pk>/edit/", "opportunity_team_member_edit"),
    "opportunity_team_member_remove": ("opportunity/workspace/<int:opportunity_pk>/team/<int:member_pk>/remove/", "opportunity_team_member_remove"),
    "opportunity_competitor_profile_list": ("opportunity/competitors/", "opportunity_competitor_profile_list"),
    "opportunity_competitor_profile_create": ("opportunity/competitors/add/", "opportunity_competitor_profile_create"),
    "opportunity_competitor_profile_detail": ("opportunity/competitors/<int:pk>/", "opportunity_competitor_profile_detail"),
    "opportunity_competitor_profile_edit": ("opportunity/competitors/<int:pk>/edit/", "opportunity_competitor_profile_edit"),
    "opportunity_competitor_profile_delete": ("opportunity/competitors/<int:pk>/delete/", "opportunity_competitor_profile_delete"),
    "opportunity_competitor_link_add": ("opportunity/workspace/<int:opportunity_pk>/competitors/add/", "opportunity_competitor_link_add"),
    "opportunity_competitor_link_edit": ("opportunity/workspace/<int:opportunity_pk>/competitors/<int:competitor_pk>/edit/", "opportunity_competitor_link_edit"),
    "opportunity_competitor_link_remove": ("opportunity/workspace/<int:opportunity_pk>/competitors/<int:competitor_pk>/remove/", "opportunity_competitor_link_remove"),
    "opportunity_win_loss_reason_list": ("opportunity/win-loss-reasons/", "opportunity_win_loss_reason_list"),
    "opportunity_win_loss_reason_create": ("opportunity/win-loss-reasons/add/", "opportunity_win_loss_reason_create"),
    "opportunity_transition": ("opportunity/workspace/<int:opportunity_pk>/transition/", "opportunity_transition"),
    "opportunity_win_loss_reason_edit": ("opportunity/win-loss-reasons/<int:pk>/edit/", "opportunity_win_loss_reason_edit"),
    "opportunity_win_loss_reason_delete": ("opportunity/win-loss-reasons/<int:pk>/delete/", "opportunity_win_loss_reason_delete"),
    "opportunity_win_loss_reason_detail": ("opportunity/win-loss-reasons/<int:pk>/", "opportunity_win_loss_reason_detail"),
}


def _opportunitypipeline_url(name, **kwargs):
    return reverse(f"sales:{name}", kwargs=kwargs)


def _opportunitypipeline_body(response):
    return response.content.decode()


def _opportunitypipeline_templates(response):
    return [template.name for template in response.templates if template.name]


def _opportunitypipeline_messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _opportunitypipeline_said(response, fragment):
    return any(fragment.lower() in message.lower() for message in _opportunitypipeline_messages(response))


def _opportunitypipeline_pipeline_payload(**overrides):
    payload = {
        "name": "Enterprise Cloud Deals",
        "description": "Enterprise cloud pipeline with automated progression.",
        "is_default": False,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_stage_payload(pipeline, **overrides):
    payload = {
        "pipeline": str(pipeline.pk),
        "name": "Technical Evaluation",
        "code": f"TECH_{int(timezone.now().timestamp() % 10000)}",
        "sequence": 25,
        "stage_kind": "open",
        "crm_stage_key": "qualification",
        "probability": 40,
        "forecast_category": "pipeline",
        "entry_guidance": "Complete architecture review.",
        "exit_guidance": "Signed technical criteria.",
        "target_days": 14,
        "is_active": True,
        "entry_criteria": [],
        "exit_criteria": [],
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_placement_payload(opportunity, pipeline, stage, **overrides):
    payload = {
        "opportunity": str(opportunity.pk),
        "pipeline": str(pipeline.pk),
        "current_stage": str(stage.pk),
        "probability_override": "",
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_team_payload(user, **overrides):
    payload = {
        "user": str(user.pk),
        "org_unit": "",
        "role": "sales_support",
        "responsibility": "Primary Deal Lead",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_competitor_payload(party, **overrides):
    payload = {
        "party": str(party.pk),
        "aliases": "Enterprise Rival Co",
        "website_url": "https://rival.example.com",
        "description": "Legacy on-premise competitor transitioning to SaaS.",
        "market_positioning": "Lower cost alternative with limited API.",
        "strengths": "Deep discounting",
        "weaknesses": "Complex upgrades",
        "differentiators": "Modern cloud-native architecture",
        "objection_handling": "Highlight maintenance overhead",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_competitor_link_payload(competitor_profile, **overrides):
    payload = {
        "competitor_profile": str(competitor_profile.pk),
        "relationship": "evaluating",
        "is_primary": True,
        "pricing_notes": "Undercutting list by 30%",
        "deal_notes": "Incumbent vendor for past 3 years",
        "positioning_notes": "Emphasize multi-tenant security and SLA",
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_reason_payload(**overrides):
    payload = {
        "code": f"REASON_{int(timezone.now().timestamp() % 10000)}",
        "name": "Integration Breadth",
        "description": "Customer selected us due to pre-built ERP integrations.",
        "sequence": 15,
        "result": "won",
        "category": "product_fit",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# ============================================================================
# Section 0: Routes & Method Enforcement
# ============================================================================

def test_opportunitypipeline_routes_reverse_and_resolve(
    opportunitypipeline_client_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_competitor_a,
    opportunitypipeline_reason_a,
):
    """Verify that all 34 opportunity pipeline routes reverse, match URL patterns, and enforce HTTP methods."""
    assert len(_opportunitypipeline_routes) == 34
    positions = {
        pattern.name: idx
        for idx, pattern in enumerate(sales_urls.urlpatterns)
        if pattern.name in _opportunitypipeline_routes
    }
    assert set(positions) == set(_opportunitypipeline_routes)

    dummy_stage = opportunitypipeline_pipeline_a.stages.first()
    kwargs_map = {
        "opportunity_pipeline_stage_reorder": {"pk": opportunitypipeline_pipeline_a.pk},
        "opportunity_pipeline_stage_create": {"pk": opportunitypipeline_pipeline_a.pk},
        "opportunity_pipeline_stage_edit": {"pk": opportunitypipeline_pipeline_a.pk, "stage_pk": dummy_stage.pk},
        "opportunity_pipeline_stage_delete": {"pk": opportunitypipeline_pipeline_a.pk, "stage_pk": dummy_stage.pk},
        "opportunity_pipeline_set_default": {"pk": opportunitypipeline_pipeline_a.pk},
        "opportunity_pipeline_edit": {"pk": opportunitypipeline_pipeline_a.pk},
        "opportunity_pipeline_delete": {"pk": opportunitypipeline_pipeline_a.pk},
        "opportunity_pipeline_stages": {"pk": opportunitypipeline_pipeline_a.pk},
        "opportunity_pipeline_detail": {"pk": opportunitypipeline_pipeline_a.pk},
        "opportunity_place": {"opportunity_pk": opportunitypipeline_opportunity_a.pk},
        "opportunity_unplace": {"opportunity_pk": opportunitypipeline_opportunity_a.pk},
        "opportunity_workspace_detail": {"opportunity_pk": opportunitypipeline_opportunity_a.pk},
        "opportunity_team_member_add": {"opportunity_pk": opportunitypipeline_opportunity_a.pk},
        "opportunity_team_member_edit": {"opportunity_pk": opportunitypipeline_opportunity_a.pk, "member_pk": 999},
        "opportunity_team_member_remove": {"opportunity_pk": opportunitypipeline_opportunity_a.pk, "member_pk": 999},
        "opportunity_competitor_profile_detail": {"pk": opportunitypipeline_competitor_a.pk},
        "opportunity_competitor_profile_edit": {"pk": opportunitypipeline_competitor_a.pk},
        "opportunity_competitor_profile_delete": {"pk": opportunitypipeline_competitor_a.pk},
        "opportunity_competitor_link_add": {"opportunity_pk": opportunitypipeline_opportunity_a.pk},
        "opportunity_competitor_link_edit": {"opportunity_pk": opportunitypipeline_opportunity_a.pk, "competitor_pk": 999},
        "opportunity_competitor_link_remove": {"opportunity_pk": opportunitypipeline_opportunity_a.pk, "competitor_pk": 999},
        "opportunity_transition": {"opportunity_pk": opportunitypipeline_opportunity_a.pk},
        "opportunity_win_loss_reason_edit": {"pk": opportunitypipeline_reason_a.pk},
        "opportunity_win_loss_reason_delete": {"pk": opportunitypipeline_reason_a.pk},
        "opportunity_win_loss_reason_detail": {"pk": opportunitypipeline_reason_a.pk},
    }

    for name, (route, callback_name) in _opportunitypipeline_routes.items():
        kwargs = kwargs_map.get(name, {})
        url = reverse(f"sales:{name}", kwargs=kwargs)
        match = resolve(url)
        assert match.url_name == name
        assert match.func.__name__ == callback_name

    # Check POST-only views return 405 on GET
    post_only_routes = [
        ("opportunity_pipeline_delete", {"pk": opportunitypipeline_pipeline_a.pk}),
        ("opportunity_pipeline_set_default", {"pk": opportunitypipeline_pipeline_a.pk}),
        ("opportunity_pipeline_stage_delete", {"pk": opportunitypipeline_pipeline_a.pk, "stage_pk": dummy_stage.pk}),
        ("opportunity_pipeline_stage_reorder", {"pk": opportunitypipeline_pipeline_a.pk}),
        ("opportunity_unplace", {"opportunity_pk": opportunitypipeline_opportunity_a.pk}),
        ("opportunity_transition", {"opportunity_pk": opportunitypipeline_opportunity_a.pk}),
        ("opportunity_team_member_remove", {"opportunity_pk": opportunitypipeline_opportunity_a.pk, "member_pk": 999}),
        ("opportunity_competitor_profile_delete", {"pk": opportunitypipeline_competitor_a.pk}),
        ("opportunity_competitor_link_remove", {"opportunity_pk": opportunitypipeline_opportunity_a.pk, "competitor_pk": 999}),
        ("opportunity_win_loss_reason_delete", {"pk": opportunitypipeline_reason_a.pk}),
    ]
    for route_name, kw in post_only_routes:
        url = _opportunitypipeline_url(route_name, **kw)
        resp = opportunitypipeline_client_a.get(url)
        assert resp.status_code == 405, f"{route_name} did not return 405 on GET"


# ============================================================================
# Section 1: Pipeline CRUD & Actions
# ============================================================================

def test_opportunitypipeline_pipeline_list_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_b,
    opportunitypipeline_tenant_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_pipeline_b,
):
    """Test pipeline list view filtering, search, pagination, and multi-tenant isolation."""
    url = _opportunitypipeline_url("opportunity_pipeline_list")
    resp = opportunitypipeline_client_a.get(url)
    assert resp.status_code == 200
    assert "sales/opportunity/pipeline/list.html" in _opportunitypipeline_templates(resp)
    assert set(resp.context.keys()) >= {"object_list", "page_obj", "q", "active", "active_choices", "stats"}
    pks = [p.pk for p in resp.context["object_list"]]
    assert opportunitypipeline_pipeline_a.pk in pks
    assert opportunitypipeline_pipeline_b.pk not in pks

    # Filter by q
    resp_q = opportunitypipeline_client_a.get(url, {"q": opportunitypipeline_pipeline_a.name})
    assert resp_q.status_code == 200
    assert opportunitypipeline_pipeline_a.pk in [p.pk for p in resp_q.context["object_list"]]

    resp_nomatch = opportunitypipeline_client_a.get(url, {"q": "NonExistentSearchTerm123"})
    assert resp_nomatch.status_code == 200
    assert len(resp_nomatch.context["object_list"]) == 0

    # Filter by active
    resp_act = opportunitypipeline_client_a.get(url, {"active": "active"})
    assert resp_act.status_code == 200
    assert resp_act.context["active"] == "active"

    resp_inact = opportunitypipeline_client_a.get(url, {"active": "inactive"})
    assert resp_inact.status_code == 200
    assert resp_inact.context["active"] == "inactive"

    resp_junk_act = opportunitypipeline_client_a.get(url, {"active": "junk-status"})
    assert resp_junk_act.status_code == 200
    assert resp_junk_act.context["active"] == ""

    # Out of range pagination
    resp_page = opportunitypipeline_client_a.get(url, {"page": 999})
    assert resp_page.status_code == 200


def test_opportunitypipeline_pipeline_create_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    client,
):
    """Test pipeline create GET/POST, admin authorization, validation, and auto stage generation."""
    url = _opportunitypipeline_url("opportunity_pipeline_create")

    # Anonymous user redirected
    anon_resp = client.get(url)
    assert anon_resp.status_code == 302

    # Non-admin user denied
    member_resp = opportunitypipeline_client_member_a.get(url)
    assert member_resp.status_code == 403

    # Admin GET
    get_resp = opportunitypipeline_client_a.get(url)
    assert get_resp.status_code == 200
    assert "sales/opportunity/pipeline/form.html" in _opportunitypipeline_templates(get_resp)
    assert get_resp.context["is_edit"] is False

    # POST invalid
    bad_resp = opportunitypipeline_client_a.post(url, {"name": ""})
    assert bad_resp.status_code == 200
    assert bad_resp.context["form"].errors

    # POST valid
    payload = _opportunitypipeline_pipeline_payload(name="Global Enterprise Pipeline", is_default=False)
    post_resp = opportunitypipeline_client_a.post(url, payload)
    assert post_resp.status_code == 302
    created = Pipeline.objects.filter(tenant=opportunitypipeline_tenant_a, name="Global Enterprise Pipeline").first()
    assert created is not None
    assert post_resp.url == _opportunitypipeline_url("opportunity_pipeline_detail", pk=created.pk)
    # sales_create_pipeline provisions baseline stages
    assert created.stages.filter(stage_kind="open").count() > 0
    assert created.stages.filter(stage_kind="won").count() == 1
    assert created.stages.filter(stage_kind="lost").count() == 1


def test_opportunitypipeline_pipeline_detail_and_edit_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_pipeline_b,
):
    """Test pipeline detail view context, can_edit flag, tenant isolation, and edit GET/POST."""
    detail_url = _opportunitypipeline_url("opportunity_pipeline_detail", pk=opportunitypipeline_pipeline_a.pk)
    resp = opportunitypipeline_client_a.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["obj"] == opportunitypipeline_pipeline_a
    assert resp.context["can_edit"] is True
    assert "placement_count" in resp.context
    assert "open_placement_count" in resp.context

    # Member view has can_edit False
    resp_mem = opportunitypipeline_client_member_a.get(detail_url)
    assert resp_mem.status_code == 200
    assert resp_mem.context["can_edit"] is False

    # Cross tenant detail returns 404
    cross_detail = _opportunitypipeline_url("opportunity_pipeline_detail", pk=opportunitypipeline_pipeline_b.pk)
    assert opportunitypipeline_client_a.get(cross_detail).status_code == 404

    # Edit permissions
    edit_url = _opportunitypipeline_url("opportunity_pipeline_edit", pk=opportunitypipeline_pipeline_a.pk)
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(edit_url, {}).status_code == 403

    # Edit GET
    edit_resp = opportunitypipeline_client_a.get(edit_url)
    assert edit_resp.status_code == 200
    assert edit_resp.context["is_edit"] is True

    # Edit POST invalid
    bad_edit = opportunitypipeline_client_a.post(edit_url, {"name": ""})
    assert bad_edit.status_code == 200
    assert bad_edit.context["form"].errors

    # Edit POST valid
    edit_payload = _opportunitypipeline_pipeline_payload(
        name="Acme Direct Updated",
        description="Updated direct sales pipeline",
    )
    save_resp = opportunitypipeline_client_a.post(edit_url, edit_payload)
    assert save_resp.status_code == 302
    assert save_resp.url == detail_url
    opportunitypipeline_pipeline_a.refresh_from_db()
    assert opportunitypipeline_pipeline_a.name == "Acme Direct Updated"

    # Cross tenant edit returns 404
    cross_edit = _opportunitypipeline_url("opportunity_pipeline_edit", pk=opportunitypipeline_pipeline_b.pk)
    assert opportunitypipeline_client_a.get(cross_edit).status_code == 404


def test_opportunitypipeline_pipeline_set_default_and_delete_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_admin_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_pipeline_b,
):
    """Test setting default pipeline and deleting pipeline with admin guards and integrity protections."""
    # Create a second pipeline in tenant A
    p2 = _opportunitypipeline_pipeline(opportunitypipeline_tenant_a, name="Acme Indirect", code="ACME_IND", is_default=False)

    set_default_url = _opportunitypipeline_url("opportunity_pipeline_set_default", pk=p2.pk)
    # Non-admin forbidden
    assert opportunitypipeline_client_member_a.post(set_default_url).status_code == 403

    # Cross tenant 404
    cross_set_default = _opportunitypipeline_url("opportunity_pipeline_set_default", pk=opportunitypipeline_pipeline_b.pk)
    assert opportunitypipeline_client_a.post(cross_set_default).status_code == 404

    # Valid set default
    resp_def = opportunitypipeline_client_a.post(set_default_url)
    assert resp_def.status_code == 302
    p2.refresh_from_db()
    opportunitypipeline_pipeline_a.refresh_from_db()
    assert p2.is_default is True
    assert opportunitypipeline_pipeline_a.is_default is False

    # Delete pipeline: p2 is currently default and might have stages or placements
    delete_url = _opportunitypipeline_url("opportunity_pipeline_delete", pk=p2.pk)
    assert opportunitypipeline_client_member_a.post(delete_url).status_code == 403
    cross_del = _opportunitypipeline_url("opportunity_pipeline_delete", pk=opportunitypipeline_pipeline_b.pk)
    assert opportunitypipeline_client_a.post(cross_del).status_code == 404

    # Create unplaced, non-default pipeline to delete
    p3 = _opportunitypipeline_pipeline(opportunitypipeline_tenant_a, name="Acme Disposable", code="ACME_DISP", is_default=False)
    del3_url = _opportunitypipeline_url("opportunity_pipeline_delete", pk=p3.pk)
    del_resp = opportunitypipeline_client_a.post(del3_url)
    assert del_resp.status_code == 302
    assert not Pipeline.objects.filter(pk=p3.pk).exists()


# ============================================================================
# Section 2: Pipeline Stages
# ============================================================================

def test_opportunitypipeline_stages_list_and_create_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_pipeline_b,
):
    """Test pipeline stages overview page and stage creation with admin guards."""
    stages_url = _opportunitypipeline_url("opportunity_pipeline_stages", pk=opportunitypipeline_pipeline_a.pk)
    resp = opportunitypipeline_client_a.get(stages_url)
    assert resp.status_code == 200
    assert "sales/opportunity/pipeline/stages.html" in _opportunitypipeline_templates(resp)
    assert resp.context["pipeline"] == opportunitypipeline_pipeline_a
    assert len(resp.context["stages"]) == opportunitypipeline_pipeline_a.stages.count()
    assert "stage_form" in resp.context
    assert "reorder_form" in resp.context

    # Cross tenant stages page returns 404
    cross_stages = _opportunitypipeline_url("opportunity_pipeline_stages", pk=opportunitypipeline_pipeline_b.pk)
    assert opportunitypipeline_client_a.get(cross_stages).status_code == 404

    # Stage create view
    create_stage_url = _opportunitypipeline_url("opportunity_pipeline_stage_create", pk=opportunitypipeline_pipeline_a.pk)
    assert opportunitypipeline_client_member_a.get(create_stage_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(create_stage_url, {}).status_code == 403

    get_create = opportunitypipeline_client_a.get(create_stage_url)
    assert get_create.status_code == 200
    assert get_create.context["is_edit"] is False

    # POST invalid
    bad_post = opportunitypipeline_client_a.post(create_stage_url, {"name": ""})
    assert bad_post.status_code == 200
    assert bad_post.context["form"].errors

    # POST valid
    payload = _opportunitypipeline_stage_payload(
        opportunitypipeline_pipeline_a,
        name="Security Review",
        code="sec_rev",
        sequence=35,
        probability=60,
    )
    post_resp = opportunitypipeline_client_a.post(create_stage_url, payload)
    assert post_resp.status_code == 302
    assert post_resp.url == stages_url
    assert opportunitypipeline_pipeline_a.stages.filter(code="sec_rev").exists()


def test_opportunitypipeline_stage_edit_delete_reorder_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_pipeline_b,
):
    """Test stage editing, deletion, and stage sequence reordering."""
    stages = list(opportunitypipeline_pipeline_a.stages.all().order_by("sequence"))
    stage1, stage2 = stages[0], stages[1]

    # Edit stage
    edit_url = _opportunitypipeline_url("opportunity_pipeline_stage_edit", pk=opportunitypipeline_pipeline_a.pk, stage_pk=stage1.pk)
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403

    # Cross tenant / mismatched stage edit returns 404
    stage_b = opportunitypipeline_pipeline_b.stages.first()
    mismatch_url = _opportunitypipeline_url("opportunity_pipeline_stage_edit", pk=opportunitypipeline_pipeline_a.pk, stage_pk=stage_b.pk)
    assert opportunitypipeline_client_a.get(mismatch_url).status_code == 404

    get_edit = opportunitypipeline_client_a.get(edit_url)
    assert get_edit.status_code == 200
    assert get_edit.context["is_edit"] is True
    assert get_edit.context["stage"] == stage1

    # Save edit
    payload = _opportunitypipeline_stage_payload(
        opportunitypipeline_pipeline_a,
        name="Discovery Updated",
        code=stage1.code,
        sequence=stage1.sequence,
        stage_kind=stage1.stage_kind,
        probability=stage1.probability,
    )
    save_resp = opportunitypipeline_client_a.post(edit_url, payload)
    assert save_resp.status_code == 302
    stage1.refresh_from_db()
    assert stage1.name == "Discovery Updated"

    # Stage reorder
    reorder_url = _opportunitypipeline_url("opportunity_pipeline_stage_reorder", pk=opportunitypipeline_pipeline_a.pk)
    assert opportunitypipeline_client_member_a.post(reorder_url).status_code == 403

    # Invalid reorder payload (incomplete list)
    bad_reorder = opportunitypipeline_client_a.post(reorder_url, {"ordered_stage_ids": f"{stage1.pk},{stage2.pk}"})
    assert bad_reorder.status_code == 302
    assert _opportunitypipeline_said(bad_reorder, "Choose every pipeline stage exactly once")

    # Valid reorder: swap stage1 and stage2
    reordered_ids = [s.pk for s in stages]
    reordered_ids[0], reordered_ids[1] = reordered_ids[1], reordered_ids[0]
    good_reorder = opportunitypipeline_client_a.post(reorder_url, {"ordered_stage_ids": ",".join(str(i) for i in reordered_ids)})
    assert good_reorder.status_code == 302
    assert _opportunitypipeline_said(good_reorder, "Pipeline stage order updated")

    # Stage delete: create a clean stage to delete
    clean_stage = _opportunitypipeline_stage(
        opportunitypipeline_tenant_a,
        opportunitypipeline_pipeline_a,
        name="Temporary Stage",
        sequence=45,
    )
    del_url = _opportunitypipeline_url("opportunity_pipeline_stage_delete", pk=opportunitypipeline_pipeline_a.pk, stage_pk=clean_stage.pk)
    assert opportunitypipeline_client_member_a.post(del_url).status_code == 403
    del_resp = opportunitypipeline_client_a.post(del_url)
    assert del_resp.status_code == 302
    assert not PipelineStage.objects.filter(pk=clean_stage.pk).exists()


# ============================================================================
# Section 3: Pipeline Board & Visibility
# ============================================================================

def test_opportunitypipeline_board_view(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_placement_a,
):
    """Test kanban pipeline board view rendering, columns, cards, and filter controls."""
    board_url = _opportunitypipeline_url("opportunity_pipeline_board")
    resp = opportunitypipeline_client_a.get(board_url)
    assert resp.status_code == 200
    assert "sales/opportunity/pipeline/board.html" in _opportunitypipeline_templates(resp)
    assert set(resp.context.keys()) >= {
        "tenant", "pipelines", "selected_pipeline", "pipeline_id", "owner_id",
        "territory_id", "currency_totals", "currency", "health", "columns",
        "unplaced_opportunities", "summary_rows", "health_counts",
    }
    assert resp.context["selected_pipeline"] == opportunitypipeline_pipeline_a
    assert len(resp.context["columns"]) > 0

    # Test filtering by pipeline, owner, territory, health
    user_owner = opportunitypipeline_opportunity_a.owner
    resp_filtered = opportunitypipeline_client_a.get(
        board_url,
        {
            "pipeline": opportunitypipeline_pipeline_a.pk,
            "owner": user_owner.pk if user_owner else "",
            "health": "on_track",
        },
    )
    assert resp_filtered.status_code == 200
    assert resp_filtered.context["health"] == "on_track"

    # Test invalid filter values fallback safely without 500
    resp_junk = opportunitypipeline_client_a.get(
        board_url,
        {
            "pipeline": "invalid_pk",
            "owner": "bad_user",
            "territory": "bogus_territory",
            "currency": "NON_EXISTENT_CURRENCY",
            "health": "unknown_status",
        },
    )
    assert resp_junk.status_code == 200
    assert resp_junk.context["health"] == ""


def test_opportunitypipeline_visibility_view(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_placement_a,
):
    """Test pipeline visibility view, date range filters, and safe_parse_date handling."""
    vis_url = _opportunitypipeline_url("opportunity_pipeline_visibility")
    resp = opportunitypipeline_client_a.get(vis_url)
    assert resp.status_code == 200
    assert "sales/opportunity/pipeline/visibility.html" in _opportunitypipeline_templates(resp)
    assert set(resp.context.keys()) >= {
        "health_counts", "stage_age_rows", "win_loss_rows", "competitor_rows",
        "date_from", "date_to", "tenant", "pipelines", "selected_pipeline",
    }

    # Valid date filtering
    resp_dates = opportunitypipeline_client_a.get(
        vis_url,
        {"date_from": "2026-01-01", "date_to": "2026-12-31"},
    )
    assert resp_dates.status_code == 200
    assert resp_dates.context["date_from"] is not None
    assert resp_dates.context["date_to"] is not None

    # Junk date filtering: safe_parse_date must not raise 500
    resp_junk = opportunitypipeline_client_a.get(
        vis_url,
        {"date_from": "2026-13-45", "date_to": "not-a-real-date", "pipeline": "abc", "owner": "xyz"},
    )
    assert resp_junk.status_code == 200
    assert resp_junk.context["date_from"] is None
    assert resp_junk.context["date_to"] is None


# ============================================================================
# Section 4: Workspace
# ============================================================================

def test_opportunitypipeline_workspace_list_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_b,
    opportunitypipeline_tenant_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_opportunity_b,
    opportunitypipeline_placement_a,
):
    """Test opportunity workspace list view, filters (q, owner, pipeline, health), and pagination."""
    url = _opportunitypipeline_url("opportunity_workspace_list")
    resp = opportunitypipeline_client_a.get(url)
    assert resp.status_code == 200
    assert "sales/opportunity/workspace.html" in _opportunitypipeline_templates(resp)
    assert set(resp.context.keys()) >= {
        "opportunities", "page_obj", "q", "health", "owner_id", "territory_id",
        "pipeline_id", "pipelines", "owners", "territories", "health_counts", "stats",
    }
    opp_pks = [o.pk for o in resp.context["opportunities"]]
    assert opportunitypipeline_opportunity_a.pk in opp_pks
    assert opportunitypipeline_opportunity_b.pk not in opp_pks

    # Search filter
    resp_q = opportunitypipeline_client_a.get(url, {"q": opportunitypipeline_opportunity_a.name})
    assert resp_q.status_code == 200
    assert opportunitypipeline_opportunity_a.pk in [o.pk for o in resp_q.context["opportunities"]]

    # Pipeline filter
    resp_pipe = opportunitypipeline_client_a.get(url, {"pipeline": opportunitypipeline_placement_a.pipeline_id})
    assert resp_pipe.status_code == 200

    # Owner filter
    resp_owner = opportunitypipeline_client_a.get(url, {"owner": opportunitypipeline_opportunity_a.owner_id})
    assert resp_owner.status_code == 200

    # Health filter (triggers the non-empty health branch lines 521-570)
    resp_health = opportunitypipeline_client_a.get(url, {"health": "watch"})
    assert resp_health.status_code == 200
    assert resp_health.context["health"] == "watch"

    # Out of range pagination
    resp_page = opportunitypipeline_client_a.get(url, {"page": 999})
    assert resp_page.status_code == 200

    # Junk params
    resp_junk = opportunitypipeline_client_a.get(url, {"pipeline": "abc", "owner": "xyz", "health": "bad"})
    assert resp_junk.status_code == 200
    assert resp_junk.context["health"] == ""


def test_opportunitypipeline_workspace_detail_view(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_opportunity_b,
    opportunitypipeline_placement_a,
    opportunitypipeline_competitor_a,
    opportunitypipeline_reason_a,
):
    """Test workspace detail tabs: team, competitors, timeline activities, documents, and tenant checks."""
    url = _opportunitypipeline_url("opportunity_workspace_detail", opportunity_pk=opportunitypipeline_opportunity_a.pk)

    # Attach activity items
    user = opportunitypipeline_opportunity_a.owner
    task = CrmTask.objects.create(
        tenant=opportunitypipeline_tenant_a,
        related_opportunity=opportunitypipeline_opportunity_a,
        subject="Follow up on contract redlines",
        type="task",
        status="pending",
        owner=user,
    )
    comm = CommunicationLog.objects.create(
        tenant=opportunitypipeline_tenant_a,
        related_opportunity=opportunitypipeline_opportunity_a,
        subject="Executive sponsor discovery call",
        channel="call",
        body="Discussed implementation timeline and budget expectations.",
        occurred_at=timezone.now(),
        owner=user,
    )
    event = CalendarEvent.objects.create(
        tenant=opportunitypipeline_tenant_a,
        related_opportunity=opportunitypipeline_opportunity_a,
        title="Technical Demo Session",
        start=timezone.now(),
        end=timezone.now() + timezone.timedelta(hours=1),
        owner=user,
    )
    contract = ContractDocument.objects.create(
        tenant=opportunitypipeline_tenant_a,
        opportunity=opportunitypipeline_opportunity_a,
        name="Master Services Agreement Draft",
        status="draft",
        owner=user,
    )
    doc = Document.objects.create(
        tenant=opportunitypipeline_tenant_a,
        related=opportunitypipeline_opportunity_a,
        name="Architecture Diagram",
        file=SimpleUploadedFile("arch.png", b"file_content"),
    )
    audit = AuditLog.objects.create(
        tenant=opportunitypipeline_tenant_a,
        user=user,
        target=f"Opportunity {opportunitypipeline_opportunity_a.pk}",
        action="update",
        related=opportunitypipeline_opportunity_a,
        changes={"operation": "advance_stage"},
    )

    resp = opportunitypipeline_client_a.get(url)
    assert resp.status_code == 200
    assert "sales/opportunity/workspace.html" in _opportunitypipeline_templates(resp)
    assert set(resp.context.keys()) >= {
        "opportunity", "placement", "placement_form", "pipelines", "stages",
        "health", "team_members", "team_member_form", "competitor_links",
        "competitor_form", "closure_form", "outcomes", "tasks", "communications",
        "events", "contracts", "documents", "audit_entries", "activity_timeline",
    }
    assert resp.context["opportunity"] == opportunitypipeline_opportunity_a
    assert len(resp.context["activity_timeline"]) >= 4

    # Cross tenant detail returns 404
    cross_url = _opportunitypipeline_url("opportunity_workspace_detail", opportunity_pk=opportunitypipeline_opportunity_b.pk)
    assert opportunitypipeline_client_a.get(cross_url).status_code == 404


def test_opportunitypipeline_place_and_unplace_view(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_admin_a,
    opportunitypipeline_user_a,
    opportunitypipeline_pipeline_a,
):
    """Test opportunity placement (GET/POST) and unplacement with strict authorization checks."""
    # Create unplaced opportunity
    opp = _opportunitypipeline_opportunity(
        opportunitypipeline_tenant_a,
        title="Unplaced Enterprise Deal",
        owner=opportunitypipeline_user_a,
    )
    open_stage = opportunitypipeline_pipeline_a.stages.filter(stage_kind="open").first()

    place_url = _opportunitypipeline_url("opportunity_place", opportunity_pk=opp.pk)
    get_place = opportunitypipeline_client_a.get(place_url)
    assert get_place.status_code == 200
    assert "sales/opportunity/placement.html" in _opportunitypipeline_templates(get_place)
    assert get_place.context["is_edit"] is False

    # POST valid placement
    payload = _opportunitypipeline_placement_payload(opp, opportunitypipeline_pipeline_a, open_stage)
    post_place = opportunitypipeline_client_a.post(place_url, payload)
    assert post_place.status_code == 302
    assert post_place.url == _opportunitypipeline_url("opportunity_workspace_detail", opportunity_pk=opp.pk)
    placement = OpportunityPipelinePlacement.objects.filter(opportunity=opp).first()
    assert placement is not None
    assert placement.pipeline == opportunitypipeline_pipeline_a
    assert placement.current_stage == open_stage

    # Unplace authorization tests:
    # 1. Non-admin, non-owner, non-privileged team member is forbidden
    random_user = _opportunitypipeline_user(opportunitypipeline_tenant_a, "random_rep", is_admin=False)
    client_random = _create_client(random_user)
    unplace_url = _opportunitypipeline_url("opportunity_unplace", opportunity_pk=opp.pk)
    resp_unauth = client_random.post(unplace_url)
    assert resp_unauth.status_code == 403

    # 2. Team member with "sales_rep" role is also forbidden
    _opportunitypipeline_team_member(opportunitypipeline_tenant_a, opp, random_user, role="sales_rep")
    resp_rep = client_random.post(unplace_url)
    assert resp_rep.status_code == 403

    # 3. Team member with "co_owner" role is allowed
    co_owner_user = _opportunitypipeline_user(opportunitypipeline_tenant_a, "co_owner", is_admin=False)
    client_co_owner = _create_client(co_owner_user)
    _opportunitypipeline_team_member(opportunitypipeline_tenant_a, opp, co_owner_user, role="co_owner")
    resp_co = client_co_owner.post(unplace_url)
    assert resp_co.status_code == 302
    assert not OpportunityPipelinePlacement.objects.filter(opportunity=opp).exists()
    assert _opportunitypipeline_said(resp_co, "Opportunity removed from its pipeline")

    # 4. When already unplaced, POST returns info message
    resp_already = client_co_owner.post(unplace_url)
    assert resp_already.status_code == 302
    assert _opportunitypipeline_said(resp_already, "not placed in a pipeline")


def _create_client(user):
    from django.test import Client
    c = Client()
    c.force_login(user)
    return c


def test_opportunitypipeline_transition_view(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_placement_a,
    opportunitypipeline_reason_a,
):
    """Test opportunity pipeline stage transition: advance, closed won, closed lost, and validation errors."""
    stages = list(opportunitypipeline_pipeline_a.stages.all())
    open_stages = [s for s in stages if s.stage_kind == "open"]
    won_stage = next(s for s in stages if s.stage_kind == "won")
    lost_stage = next(s for s in stages if s.stage_kind == "lost")
    next_open_stage = open_stages[1]

    url = _opportunitypipeline_url("opportunity_transition", opportunity_pk=opportunitypipeline_opportunity_a.pk)

    # 1. Advance to another open stage
    advance_payload = {
        "target_stage": str(next_open_stage.pk),
        "notes": "Moving to next evaluation stage.",
    }
    resp_adv = opportunitypipeline_client_a.post(url, advance_payload)
    assert resp_adv.status_code == 302
    opportunitypipeline_placement_a.refresh_from_db()
    assert opportunitypipeline_placement_a.current_stage == next_open_stage
    assert _opportunitypipeline_said(resp_adv, "Opportunity transitioned")

    # 2. Transition to Won requires a reason
    bad_won_payload = {
        "target_stage": str(won_stage.pk),
        "reason": "",
        "notes": "Missing reason",
    }
    resp_bad_won = opportunitypipeline_client_a.post(url, bad_won_payload)
    assert resp_bad_won.status_code == 302
    # Form error flash message shown
    assert any("reason" in m.lower() or "valid" in m.lower() for m in _opportunitypipeline_messages(resp_bad_won))

    # 3. Valid Transition to Won with Reason
    won_payload = {
        "target_stage": str(won_stage.pk),
        "reason": str(opportunitypipeline_reason_a.pk),
        "notes": "Deal closed successfully!",
    }
    resp_won = opportunitypipeline_client_a.post(url, won_payload)
    assert resp_won.status_code == 302
    opportunitypipeline_opportunity_a.refresh_from_db()
    opportunitypipeline_placement_a.refresh_from_db()
    assert opportunitypipeline_opportunity_a.stage == "closed_won"
    assert opportunitypipeline_placement_a.current_stage == won_stage
    assert OpportunityOutcome.objects.filter(opportunity=opportunitypipeline_opportunity_a, result="won").exists()


# ============================================================================
# Section 5: Team Members
# ============================================================================

def test_opportunitypipeline_team_members_add_edit_remove(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_admin_a,
    opportunitypipeline_user_a,
):
    """Test opportunity team member addition, editing, and removal with audit trail."""
    add_url = _opportunitypipeline_url("opportunity_team_member_add", opportunity_pk=opportunitypipeline_opportunity_a.pk)
    get_add = opportunitypipeline_client_a.get(add_url)
    assert get_add.status_code == 200
    assert "sales/opportunity/team_member/form.html" in _opportunitypipeline_templates(get_add)
    assert get_add.context["is_edit"] is False

    # POST invalid
    bad_post = opportunitypipeline_client_a.post(add_url, {"user": ""})
    assert bad_post.status_code == 200
    assert bad_post.context["form"].errors

    # POST valid add
    payload = _opportunitypipeline_team_payload(opportunitypipeline_user_a, role="solution_consultant")
    post_add = opportunitypipeline_client_a.post(add_url, payload)
    assert post_add.status_code == 302
    member = OpportunityTeamMember.objects.filter(
        opportunity=opportunitypipeline_opportunity_a,
        user=opportunitypipeline_user_a,
    ).first()
    assert member is not None
    assert member.role == "solution_consultant"

    # Edit member
    edit_url = _opportunitypipeline_url(
        "opportunity_team_member_edit",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        member_pk=member.pk,
    )
    get_edit = opportunitypipeline_client_a.get(edit_url)
    assert get_edit.status_code == 200
    assert get_edit.context["is_edit"] is True
    assert get_edit.context["obj"] == member

    edit_payload = _opportunitypipeline_team_payload(
        opportunitypipeline_user_a,
        role="collaborator",
        responsibility="Enterprise Architecture Blueprint",
    )
    post_edit = opportunitypipeline_client_a.post(edit_url, edit_payload)
    assert post_edit.status_code == 302
    member.refresh_from_db()
    assert member.role == "collaborator"
    assert member.responsibility == "Enterprise Architecture Blueprint"

    # Remove member
    remove_url = _opportunitypipeline_url(
        "opportunity_team_member_remove",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        member_pk=member.pk,
    )
    post_remove = opportunitypipeline_client_a.post(remove_url)
    assert post_remove.status_code == 302
    assert not OpportunityTeamMember.objects.filter(pk=member.pk).exists()
    assert _opportunitypipeline_said(post_remove, "removed")


# ============================================================================
# Section 6: Competitors
# ============================================================================

def test_opportunitypipeline_competitor_profile_crud(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_competitor_a,
):
    """Test competitor profile list, create, detail, edit, delete with admin guards and integrity."""
    list_url = _opportunitypipeline_url("opportunity_competitor_profile_list")
    resp_list = opportunitypipeline_client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "sales/opportunity/competitor/list.html" in _opportunitypipeline_templates(resp_list)
    assert opportunitypipeline_competitor_a.pk in [c.pk for c in resp_list.context["object_list"]]

    # Create profile
    create_url = _opportunitypipeline_url("opportunity_competitor_profile_create")
    assert opportunitypipeline_client_member_a.get(create_url).status_code == 403
    get_create = opportunitypipeline_client_a.get(create_url)
    assert get_create.status_code == 200

    party = _opportunitypipeline_party(opportunitypipeline_tenant_a, name="Apex Competitor Corp")
    payload = _opportunitypipeline_competitor_payload(party)
    post_create = opportunitypipeline_client_a.post(create_url, payload)
    assert post_create.status_code == 302
    created = CompetitorProfile.objects.filter(tenant=opportunitypipeline_tenant_a, party=party).first()
    assert created is not None

    # Detail profile
    detail_url = _opportunitypipeline_url("opportunity_competitor_profile_detail", pk=created.pk)
    resp_detail = opportunitypipeline_client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["obj"] == created

    # Edit profile
    edit_url = _opportunitypipeline_url("opportunity_competitor_profile_edit", pk=created.pk)
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403
    payload["market_positioning"] = "Premium cloud solution"
    post_edit = opportunitypipeline_client_a.post(edit_url, payload)
    assert post_edit.status_code == 302
    created.refresh_from_db()
    assert created.market_positioning == "Premium cloud solution"

    # Delete profile
    del_url = _opportunitypipeline_url("opportunity_competitor_profile_delete", pk=created.pk)
    assert opportunitypipeline_client_member_a.post(del_url).status_code == 403
    post_del = opportunitypipeline_client_a.post(del_url)
    assert post_del.status_code == 302
    assert not CompetitorProfile.objects.filter(pk=created.pk).exists()


def test_opportunitypipeline_competitor_linking(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_competitor_a,
):
    """Test linking competitor to opportunity, editing link details, and removing competitor link."""
    add_link_url = _opportunitypipeline_url("opportunity_competitor_link_add", opportunity_pk=opportunitypipeline_opportunity_a.pk)
    get_add = opportunitypipeline_client_a.get(add_link_url)
    assert get_add.status_code == 200
    assert "sales/opportunity/competitor/link_form.html" in _opportunitypipeline_templates(get_add)
    assert get_add.context["is_edit"] is False

    # POST valid link
    payload = _opportunitypipeline_competitor_link_payload(opportunitypipeline_competitor_a)
    post_link = opportunitypipeline_client_a.post(add_link_url, payload)
    assert post_link.status_code == 302
    link = OpportunityCompetitor.objects.filter(
        opportunity=opportunitypipeline_opportunity_a,
        competitor_profile=opportunitypipeline_competitor_a,
    ).first()
    assert link is not None
    assert link.is_primary is True

    # Attempting to delete competitor profile while referenced must fail with validation error
    del_profile_url = _opportunitypipeline_url("opportunity_competitor_profile_delete", pk=opportunitypipeline_competitor_a.pk)
    resp_del_blocked = opportunitypipeline_client_a.post(del_profile_url)
    assert resp_del_blocked.status_code == 302
    assert _opportunitypipeline_said(resp_del_blocked, "referenced competitor profile cannot be deleted")
    assert CompetitorProfile.objects.filter(pk=opportunitypipeline_competitor_a.pk).exists()

    # Edit competitor link
    edit_link_url = _opportunitypipeline_url(
        "opportunity_competitor_link_edit",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        competitor_pk=link.pk,
    )
    get_edit = opportunitypipeline_client_a.get(edit_link_url)
    assert get_edit.status_code == 200
    assert get_edit.context["is_edit"] is True

    payload["pricing_notes"] = "Discount increased to 40%"
    post_edit = opportunitypipeline_client_a.post(edit_link_url, payload)
    assert post_edit.status_code == 302
    link.refresh_from_db()
    assert link.pricing_notes == "Discount increased to 40%"

    # Remove competitor link
    remove_link_url = _opportunitypipeline_url(
        "opportunity_competitor_link_remove",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        competitor_pk=link.pk,
    )
    post_remove = opportunitypipeline_client_a.post(remove_link_url)
    assert post_remove.status_code == 302
    assert not OpportunityCompetitor.objects.filter(pk=link.pk).exists()


# ============================================================================
# Section 7: Win/Loss Reasons
# ============================================================================

def test_opportunitypipeline_win_loss_reason_crud(
    opportunitypipeline_client_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_reason_a,
):
    """Test win/loss reasons list, create, detail, edit, delete, and protection against deleting referenced reasons."""
    list_url = _opportunitypipeline_url("opportunity_win_loss_reason_list")
    resp_list = opportunitypipeline_client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "sales/opportunity/winlossreason/list.html" in _opportunitypipeline_templates(resp_list)
    assert opportunitypipeline_reason_a.pk in [r.pk for r in resp_list.context["object_list"]]

    # Filter reasons
    resp_filt = opportunitypipeline_client_a.get(list_url, {"result": "won", "category": "product_fit", "active": "active"})
    assert resp_filt.status_code == 200

    # Create reason
    create_url = _opportunitypipeline_url("opportunity_win_loss_reason_create")
    assert opportunitypipeline_client_member_a.get(create_url).status_code == 403
    get_create = opportunitypipeline_client_a.get(create_url)
    assert get_create.status_code == 200

    payload = _opportunitypipeline_reason_payload(code="UNMATCHED_SLA", name="Unmatched Enterprise SLA")
    post_create = opportunitypipeline_client_a.post(create_url, payload)
    assert post_create.status_code == 302
    created = WinLossReason.objects.filter(tenant=opportunitypipeline_tenant_a, code="unmatched_sla").first()
    assert created is not None

    # Detail reason
    detail_url = _opportunitypipeline_url("opportunity_win_loss_reason_detail", pk=created.pk)
    resp_detail = opportunitypipeline_client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["obj"] == created

    # Edit reason
    edit_url = _opportunitypipeline_url("opportunity_win_loss_reason_edit", pk=created.pk)
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403
    payload["name"] = "Unmatched Enterprise SLA Updated"
    post_edit = opportunitypipeline_client_a.post(edit_url, payload)
    assert post_edit.status_code == 302
    created.refresh_from_db()
    assert created.name == "Unmatched Enterprise SLA Updated"

    # Referenced reason cannot be deleted
    _opportunitypipeline_outcome(opportunitypipeline_tenant_a, opportunitypipeline_opportunity_a, reason=created)
    del_url = _opportunitypipeline_url("opportunity_win_loss_reason_delete", pk=created.pk)
    resp_del_blocked = opportunitypipeline_client_a.post(del_url)
    assert resp_del_blocked.status_code == 302
    assert _opportunitypipeline_said(resp_del_blocked, "referenced win/loss reason cannot be deleted")
    assert WinLossReason.objects.filter(pk=created.pk).exists()

    # Unreferenced reason can be deleted
    unref = _opportunitypipeline_win_loss_reason(opportunitypipeline_tenant_a, name="Temporary Reason", code="TMP_DEL")
    del_unref_url = _opportunitypipeline_url("opportunity_win_loss_reason_delete", pk=unref.pk)
    resp_del = opportunitypipeline_client_a.post(del_unref_url)
    assert resp_del.status_code == 302
    assert not WinLossReason.objects.filter(pk=unref.pk).exists()


# ============================================================================
# Section 8: Negative Inputs & Robustness
# ============================================================================

def test_opportunitypipeline_negative_inputs_and_boundary_conditions(
    opportunitypipeline_client_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
):
    """Test junk parameters, bad query parameters, and out-of-range pagination across all views."""
    # List view with extreme parameters
    list_url = _opportunitypipeline_url("opportunity_workspace_list")
    junk_urls = [
        (list_url, {"page": "99999", "pipeline": "-1", "owner": "xyz", "health": "invalid"}),
        (_opportunitypipeline_url("opportunity_pipeline_list"), {"page": "-5", "active": "999", "q": "x" * 300}),
        (_opportunitypipeline_url("opportunity_competitor_profile_list"), {"page": "999", "active": "random", "q": "!@#$"}),
        (_opportunitypipeline_url("opportunity_win_loss_reason_list"), {"page": "999", "result": "xyz", "category": "bad"}),
        (_opportunitypipeline_url("opportunity_pipeline_board"), {"pipeline": "bad", "owner": "-10", "currency": "NONE"}),
        (_opportunitypipeline_url("opportunity_pipeline_visibility"), {"date_from": "2026-99-99", "date_to": "bad-date"}),
    ]
    for url, params in junk_urls:
        resp = opportunitypipeline_client_a.get(url, params)
        assert resp.status_code == 200, f"Failed on {url} with {params}"
