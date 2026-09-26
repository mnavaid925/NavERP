"""Security and isolation tests for Sub-module 8.2: Opportunity & Pipeline Management.

Covers:
1. Cross-Tenant IDOR Protection (Assert 404):
   - Tenant A requests Tenant B objects across detail, edit, delete, set_default,
     stages, stage_create, stage_edit, stage_delete, stage_reorder, place, unplace,
     transition, team_member_add, team_member_edit, team_member_remove, competitor_detail,
     competitor_edit, competitor_delete, competitor_link_edit, competitor_link_remove,
     win_loss_reason_detail, win_loss_reason_edit, win_loss_reason_delete -> MUST return 404.
2. Cross-Tenant List Isolation:
   - Tenant A lists (pipelines, board, visibility, workspace, competitors, win/loss reasons)
     must NEVER show Tenant B records.
3. Cross-Tenant Foreign Key Injection:
   - Tenant A submitting Tenant B's pipeline, stage, user, competitor profile, or reason in POST -> rejected.
4. Auth & Role-Based Permissions:
   - Anonymous user -> 302 redirect to login across all 8.2 views.
   - Non-admin tenant user -> 403 Forbidden on admin-gated actions (@tenant_admin_required):
     pipeline create/edit/delete/set_default, stage create/edit/delete/reorder, competitor create/edit/delete,
     win/loss reason create/edit/delete.
   - Object-level authorization on opportunity_unplace: regular sales rep who is not owner/co-owner/approver -> 403 Forbidden.
5. CSRF Protection:
   - POST with Client(enforce_csrf_checks=True) without CSRF token -> 403 Forbidden.
6. HTTP Method Protection:
   - GET on POST-only endpoints -> 405 Method Not Allowed.
7. XSS Protection:
   - Script tags in pipeline names, notes, competitor descriptions are properly HTML-escaped.
8. Tenantless User Protection:
   - Superuser or user with tenant=None cannot view or mutate tenant-bound rows.
"""

from decimal import Decimal
import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.accounts.models import User
from apps.core.models import OrgUnit, Party, Tenant
from apps.crm.models import Opportunity
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


# ============================================================================
# Route Registry & Helpers (_opportunitypipeline_*)
# ============================================================================

_OPPORTUNITYPIPELINE_POST_ONLY_ROUTES = (
    ("opportunity_pipeline_delete", {"pk": "pipeline_a"}),
    ("opportunity_pipeline_set_default", {"pk": "pipeline_a"}),
    ("opportunity_pipeline_stage_delete", {"pk": "pipeline_a", "stage_pk": "stage_a"}),
    ("opportunity_pipeline_stage_reorder", {"pk": "pipeline_a"}),
    ("opportunity_unplace", {"opportunity_pk": "opportunity_a"}),
    ("opportunity_transition", {"opportunity_pk": "opportunity_a"}),
    ("opportunity_team_member_remove", {"opportunity_pk": "opportunity_a", "member_pk": "team_member_a"}),
    ("opportunity_competitor_profile_delete", {"pk": "competitor_a"}),
    ("opportunity_competitor_link_remove", {"opportunity_pk": "opportunity_a", "competitor_pk": "comp_link_a"}),
    ("opportunity_win_loss_reason_delete", {"pk": "reason_a"}),
)

_OPPORTUNITYPIPELINE_ADMIN_GATED_ROUTES = (
    ("opportunity_pipeline_create", {}, "both"),
    ("opportunity_pipeline_edit", {"pk": "pipeline_a"}, "both"),
    ("opportunity_pipeline_delete", {"pk": "pipeline_a"}, "post"),
    ("opportunity_pipeline_set_default", {"pk": "pipeline_a"}, "post"),
    ("opportunity_pipeline_stage_create", {"pk": "pipeline_a"}, "both"),
    ("opportunity_pipeline_stage_edit", {"pk": "pipeline_a", "stage_pk": "stage_a"}, "both"),
    ("opportunity_pipeline_stage_delete", {"pk": "pipeline_a", "stage_pk": "stage_a"}, "post"),
    ("opportunity_pipeline_stage_reorder", {"pk": "pipeline_a"}, "post"),
    ("opportunity_competitor_profile_create", {}, "both"),
    ("opportunity_competitor_profile_edit", {"pk": "competitor_a"}, "both"),
    ("opportunity_competitor_profile_delete", {"pk": "competitor_a"}, "post"),
    ("opportunity_win_loss_reason_create", {}, "both"),
    ("opportunity_win_loss_reason_edit", {"pk": "reason_a"}, "both"),
    ("opportunity_win_loss_reason_delete", {"pk": "reason_a"}, "post"),
)


def _opportunitypipeline_url(name, **kwargs):
    return reverse(f"sales:{name}", kwargs=kwargs)


def _opportunitypipeline_body(response):
    return response.content.decode()


def _opportunitypipeline_messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def _opportunitypipeline_said(response, fragment):
    return any(fragment.lower() in m.lower() for m in _opportunitypipeline_messages(response))


def _opportunitypipeline_bundle_b(
    tenant_b,
    admin_b,
    user_b,
    pipeline_b,
    opportunity_b,
):
    open_stage_b = pipeline_b.stages.filter(stage_kind="open").first()
    won_stage_b = pipeline_b.stages.filter(stage_kind="won").first()
    lost_stage_b = pipeline_b.stages.filter(stage_kind="lost").first()
    placement_b = _opportunitypipeline_placement(
        tenant_b,
        opportunity_b,
        pipeline_b,
        open_stage_b,
    )
    team_member_b = _opportunitypipeline_team_member(
        tenant_b,
        opportunity_b,
        user_b,
        role="sales_rep",
    )
    party_b = _opportunitypipeline_party(
        tenant_b,
        name=f"Globex Rival Corp {int(timezone.now().timestamp() * 1000) % 100000}",
        kind="organization",
    )
    competitor_b = _opportunitypipeline_competitor_profile(
        tenant_b,
        party=party_b,
        website="https://globex-competitor.example.com",
    )
    comp_link_b = _opportunitypipeline_opportunity_competitor(
        tenant_b,
        opportunity_b,
        competitor_b,
        threat_level="high",
    )
    reason_b = _opportunitypipeline_win_loss_reason(
        tenant_b,
        name="Globex Lower Price",
        code=f"glx_prc_{int(timezone.now().timestamp() * 1000) % 100000}",
        result="both",
        category="pricing",
    )
    return {
        "tenant": tenant_b,
        "admin": admin_b,
        "user": user_b,
        "pipeline": pipeline_b,
        "open_stage": open_stage_b,
        "won_stage": won_stage_b,
        "lost_stage": lost_stage_b,
        "opportunity": opportunity_b,
        "placement": placement_b,
        "team_member": team_member_b,
        "party": party_b,
        "competitor": competitor_b,
        "comp_link": comp_link_b,
        "reason": reason_b,
    }


def _opportunitypipeline_bundle_a(
    tenant_a,
    admin_a,
    user_a,
    pipeline_a,
    opportunity_a,
    placement_a,
    competitor_a,
    reason_a,
):
    open_stage_a = pipeline_a.stages.filter(stage_kind="open").first()
    won_stage_a = pipeline_a.stages.filter(stage_kind="won").first()
    lost_stage_a = pipeline_a.stages.filter(stage_kind="lost").first()
    team_member_a = _opportunitypipeline_team_member(
        tenant_a,
        opportunity_a,
        user_a,
        role="sales_rep",
    )
    comp_link_a = _opportunitypipeline_opportunity_competitor(
        tenant_a,
        opportunity_a,
        competitor_a,
        threat_level="medium",
    )
    return {
        "tenant": tenant_a,
        "admin": admin_a,
        "user": user_a,
        "pipeline": pipeline_a,
        "open_stage": open_stage_a,
        "won_stage": won_stage_a,
        "lost_stage": lost_stage_a,
        "opportunity": opportunity_a,
        "placement": placement_a,
        "team_member": team_member_a,
        "competitor": competitor_a,
        "comp_link": comp_link_a,
        "reason": reason_a,
    }


# ============================================================================
# 1. Cross-Tenant IDOR Protection Tests (Assert 404)
# ============================================================================

def test_opportunitypipeline_idor_pipeline_detail_and_stages_return_404(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Tenant A requesting Tenant B pipeline detail and stages must return 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    detail_url = _opportunitypipeline_url("opportunity_pipeline_detail", pk=b["pipeline"].pk)
    stages_url = _opportunitypipeline_url("opportunity_pipeline_stages", pk=b["pipeline"].pk)

    assert opportunitypipeline_client_a.get(detail_url).status_code == 404
    assert opportunitypipeline_client_a.get(stages_url).status_code == 404


def test_opportunitypipeline_idor_pipeline_edit_delete_set_default_return_404(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Tenant A editing, deleting, or setting default on Tenant B's pipeline must return 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    edit_url = _opportunitypipeline_url("opportunity_pipeline_edit", pk=b["pipeline"].pk)
    delete_url = _opportunitypipeline_url("opportunity_pipeline_delete", pk=b["pipeline"].pk)
    set_default_url = _opportunitypipeline_url("opportunity_pipeline_set_default", pk=b["pipeline"].pk)

    assert opportunitypipeline_client_a.get(edit_url).status_code == 404
    assert opportunitypipeline_client_a.post(edit_url, {"name": "Hacked Pipeline", "is_active": True}).status_code == 404
    assert opportunitypipeline_client_a.post(delete_url).status_code == 404
    assert opportunitypipeline_client_a.post(set_default_url).status_code == 404

    b["pipeline"].refresh_from_db()
    assert b["pipeline"].name == "Globex Direct"
    assert Pipeline.objects.filter(pk=b["pipeline"].pk).exists()


def test_opportunitypipeline_idor_stage_crud_and_reorder_return_404(
    opportunitypipeline_client_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Tenant A modifying stages of Tenant B pipeline or cross-pipeline stage IDOR must return 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    create_url = _opportunitypipeline_url("opportunity_pipeline_stage_create", pk=b["pipeline"].pk)
    edit_b_url = _opportunitypipeline_url(
        "opportunity_pipeline_stage_edit",
        pk=b["pipeline"].pk,
        stage_pk=b["open_stage"].pk,
    )
    edit_cross_url = _opportunitypipeline_url(
        "opportunity_pipeline_stage_edit",
        pk=opportunitypipeline_pipeline_a.pk,
        stage_pk=b["open_stage"].pk,
    )
    delete_b_url = _opportunitypipeline_url(
        "opportunity_pipeline_stage_delete",
        pk=b["pipeline"].pk,
        stage_pk=b["open_stage"].pk,
    )
    delete_cross_url = _opportunitypipeline_url(
        "opportunity_pipeline_stage_delete",
        pk=opportunitypipeline_pipeline_a.pk,
        stage_pk=b["open_stage"].pk,
    )
    reorder_url = _opportunitypipeline_url("opportunity_pipeline_stage_reorder", pk=b["pipeline"].pk)

    assert opportunitypipeline_client_a.get(create_url).status_code == 404
    assert opportunitypipeline_client_a.post(create_url, {"name": "Hacked Stage"}).status_code == 404
    assert opportunitypipeline_client_a.get(edit_b_url).status_code == 404
    assert opportunitypipeline_client_a.post(edit_b_url, {"name": "Renamed Stage"}).status_code == 404
    assert opportunitypipeline_client_a.get(edit_cross_url).status_code == 404
    assert opportunitypipeline_client_a.post(edit_cross_url, {"name": "Cross Injected"}).status_code == 404
    assert opportunitypipeline_client_a.post(delete_b_url).status_code == 404
    assert opportunitypipeline_client_a.post(delete_cross_url).status_code == 404
    assert opportunitypipeline_client_a.post(reorder_url, {"ordered_stage_ids": "1,2"}).status_code == 404

    assert PipelineStage.objects.filter(pk=b["open_stage"].pk).exists()


def test_opportunitypipeline_idor_workspace_detail_place_unplace_transition_return_404(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Tenant A workspace detail, place, unplace, transition on Tenant B opportunity must return 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    detail_url = _opportunitypipeline_url("opportunity_workspace_detail", opportunity_pk=b["opportunity"].pk)
    place_url = _opportunitypipeline_url("opportunity_place", opportunity_pk=b["opportunity"].pk)
    unplace_url = _opportunitypipeline_url("opportunity_unplace", opportunity_pk=b["opportunity"].pk)
    transition_url = _opportunitypipeline_url("opportunity_transition", opportunity_pk=b["opportunity"].pk)

    assert opportunitypipeline_client_a.get(detail_url).status_code == 404
    assert opportunitypipeline_client_a.get(place_url).status_code == 404
    assert opportunitypipeline_client_a.post(place_url, {}).status_code == 404
    assert opportunitypipeline_client_a.post(unplace_url).status_code == 404
    assert opportunitypipeline_client_a.post(transition_url, {}).status_code == 404

    b["opportunity"].refresh_from_db()
    b["placement"].refresh_from_db()
    assert b["placement"].current_stage_id == b["open_stage"].pk


def test_opportunitypipeline_idor_team_member_actions_return_404(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Tenant A adding, editing, or removing team members on Tenant B opportunity must return 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    add_url = _opportunitypipeline_url("opportunity_team_member_add", opportunity_pk=b["opportunity"].pk)
    edit_b_url = _opportunitypipeline_url(
        "opportunity_team_member_edit",
        opportunity_pk=b["opportunity"].pk,
        member_pk=b["team_member"].pk,
    )
    edit_cross_url = _opportunitypipeline_url(
        "opportunity_team_member_edit",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        member_pk=b["team_member"].pk,
    )
    remove_b_url = _opportunitypipeline_url(
        "opportunity_team_member_remove",
        opportunity_pk=b["opportunity"].pk,
        member_pk=b["team_member"].pk,
    )
    remove_cross_url = _opportunitypipeline_url(
        "opportunity_team_member_remove",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        member_pk=b["team_member"].pk,
    )

    assert opportunitypipeline_client_a.get(add_url).status_code == 404
    assert opportunitypipeline_client_a.post(add_url, {}).status_code == 404
    assert opportunitypipeline_client_a.get(edit_b_url).status_code == 404
    assert opportunitypipeline_client_a.post(edit_b_url, {}).status_code == 404
    assert opportunitypipeline_client_a.get(edit_cross_url).status_code == 404
    assert opportunitypipeline_client_a.post(edit_cross_url, {}).status_code == 404
    assert opportunitypipeline_client_a.post(remove_b_url).status_code == 404
    assert opportunitypipeline_client_a.post(remove_cross_url).status_code == 404

    assert OpportunityTeamMember.objects.filter(pk=b["team_member"].pk).exists()


def test_opportunitypipeline_idor_competitor_profile_and_links_return_404(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Tenant A viewing, editing, or deleting Tenant B competitors and competitor links must return 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    detail_url = _opportunitypipeline_url("opportunity_competitor_profile_detail", pk=b["competitor"].pk)
    edit_url = _opportunitypipeline_url("opportunity_competitor_profile_edit", pk=b["competitor"].pk)
    delete_url = _opportunitypipeline_url("opportunity_competitor_profile_delete", pk=b["competitor"].pk)
    link_add_url = _opportunitypipeline_url("opportunity_competitor_link_add", opportunity_pk=b["opportunity"].pk)
    link_edit_b_url = _opportunitypipeline_url(
        "opportunity_competitor_link_edit",
        opportunity_pk=b["opportunity"].pk,
        competitor_pk=b["comp_link"].pk,
    )
    link_edit_cross_url = _opportunitypipeline_url(
        "opportunity_competitor_link_edit",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        competitor_pk=b["comp_link"].pk,
    )
    link_remove_b_url = _opportunitypipeline_url(
        "opportunity_competitor_link_remove",
        opportunity_pk=b["opportunity"].pk,
        competitor_pk=b["comp_link"].pk,
    )
    link_remove_cross_url = _opportunitypipeline_url(
        "opportunity_competitor_link_remove",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
        competitor_pk=b["comp_link"].pk,
    )

    assert opportunitypipeline_client_a.get(detail_url).status_code == 404
    assert opportunitypipeline_client_a.get(edit_url).status_code == 404
    assert opportunitypipeline_client_a.post(edit_url, {}).status_code == 404
    assert opportunitypipeline_client_a.post(delete_url).status_code == 404
    assert opportunitypipeline_client_a.get(link_add_url).status_code == 404
    assert opportunitypipeline_client_a.post(link_add_url, {}).status_code == 404
    assert opportunitypipeline_client_a.get(link_edit_b_url).status_code == 404
    assert opportunitypipeline_client_a.post(link_edit_b_url, {}).status_code == 404
    assert opportunitypipeline_client_a.get(link_edit_cross_url).status_code == 404
    assert opportunitypipeline_client_a.post(link_edit_cross_url, {}).status_code == 404
    assert opportunitypipeline_client_a.post(link_remove_b_url).status_code == 404
    assert opportunitypipeline_client_a.post(link_remove_cross_url).status_code == 404

    assert CompetitorProfile.objects.filter(pk=b["competitor"].pk).exists()
    assert OpportunityCompetitor.objects.filter(pk=b["comp_link"].pk).exists()


def test_opportunitypipeline_idor_win_loss_reason_actions_return_404(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Tenant A viewing, editing, or deleting Tenant B win/loss reasons must return 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    detail_url = _opportunitypipeline_url("opportunity_win_loss_reason_detail", pk=b["reason"].pk)
    edit_url = _opportunitypipeline_url("opportunity_win_loss_reason_edit", pk=b["reason"].pk)
    delete_url = _opportunitypipeline_url("opportunity_win_loss_reason_delete", pk=b["reason"].pk)

    assert opportunitypipeline_client_a.get(detail_url).status_code == 404
    assert opportunitypipeline_client_a.get(edit_url).status_code == 404
    assert opportunitypipeline_client_a.post(edit_url, {}).status_code == 404
    assert opportunitypipeline_client_a.post(delete_url).status_code == 404

    assert WinLossReason.objects.filter(pk=b["reason"].pk).exists()


def test_opportunitypipeline_idor_comprehensive_matrix_404(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Exhaustive check across all 23 prompt-specified IDOR endpoints returning 404."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    cases = [
        ("opportunity_pipeline_detail", {"pk": b["pipeline"].pk}, "get"),
        ("opportunity_pipeline_edit", {"pk": b["pipeline"].pk}, "get"),
        ("opportunity_pipeline_delete", {"pk": b["pipeline"].pk}, "post"),
        ("opportunity_pipeline_set_default", {"pk": b["pipeline"].pk}, "post"),
        ("opportunity_pipeline_stages", {"pk": b["pipeline"].pk}, "get"),
        ("opportunity_pipeline_stage_create", {"pk": b["pipeline"].pk}, "get"),
        ("opportunity_pipeline_stage_edit", {"pk": b["pipeline"].pk, "stage_pk": b["open_stage"].pk}, "get"),
        ("opportunity_pipeline_stage_delete", {"pk": b["pipeline"].pk, "stage_pk": b["open_stage"].pk}, "post"),
        ("opportunity_pipeline_stage_reorder", {"pk": b["pipeline"].pk}, "post"),
        ("opportunity_place", {"opportunity_pk": b["opportunity"].pk}, "get"),
        ("opportunity_unplace", {"opportunity_pk": b["opportunity"].pk}, "post"),
        ("opportunity_transition", {"opportunity_pk": b["opportunity"].pk}, "post"),
        ("opportunity_team_member_add", {"opportunity_pk": b["opportunity"].pk}, "get"),
        ("opportunity_team_member_edit", {"opportunity_pk": b["opportunity"].pk, "member_pk": b["team_member"].pk}, "get"),
        ("opportunity_team_member_remove", {"opportunity_pk": b["opportunity"].pk, "member_pk": b["team_member"].pk}, "post"),
        ("opportunity_competitor_profile_detail", {"pk": b["competitor"].pk}, "get"),
        ("opportunity_competitor_profile_edit", {"pk": b["competitor"].pk}, "get"),
        ("opportunity_competitor_profile_delete", {"pk": b["competitor"].pk}, "post"),
        ("opportunity_competitor_link_edit", {"opportunity_pk": b["opportunity"].pk, "competitor_pk": b["comp_link"].pk}, "get"),
        ("opportunity_competitor_link_remove", {"opportunity_pk": b["opportunity"].pk, "competitor_pk": b["comp_link"].pk}, "post"),
        ("opportunity_win_loss_reason_detail", {"pk": b["reason"].pk}, "get"),
        ("opportunity_win_loss_reason_edit", {"pk": b["reason"].pk}, "get"),
        ("opportunity_win_loss_reason_delete", {"pk": b["reason"].pk}, "post"),
    ]
    for route, kwargs, method in cases:
        url = _opportunitypipeline_url(route, **kwargs)
        caller = getattr(opportunitypipeline_client_a, method)
        response = caller(url)
        assert response.status_code == 404, f"Expected 404 on {route} ({method.upper()}) but got {response.status_code}"


# ============================================================================
# 2. Cross-Tenant List Isolation Tests
# ============================================================================

def test_opportunitypipeline_list_isolation_pipelines(
    opportunitypipeline_client_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Pipeline list must show Tenant A pipelines and never show Tenant B pipelines."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    url = _opportunitypipeline_url("opportunity_pipeline_list")
    response = opportunitypipeline_client_a.get(url)
    assert response.status_code == 200

    content = _opportunitypipeline_body(response)
    assert opportunitypipeline_pipeline_a.name in content
    assert b["pipeline"].name not in content
    assert all(obj.tenant_id == opportunitypipeline_pipeline_a.tenant_id for obj in response.context["object_list"])


def test_opportunitypipeline_list_isolation_board(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_placement_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Pipeline board must show Tenant A placements and never show Tenant B deals."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    url = _opportunitypipeline_url("opportunity_pipeline_board")
    response = opportunitypipeline_client_a.get(url)
    assert response.status_code == 200

    content = _opportunitypipeline_body(response)
    assert opportunitypipeline_opportunity_a.name in content
    assert b["opportunity"].name not in content
    assert all(p.tenant_id == opportunitypipeline_placement_a.tenant_id for p in response.context["pipelines"])


def test_opportunitypipeline_list_isolation_visibility(
    opportunitypipeline_client_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Visibility overview must only roll up Tenant A data."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    url = _opportunitypipeline_url("opportunity_pipeline_visibility")
    response = opportunitypipeline_client_a.get(url)
    assert response.status_code == 200

    content = _opportunitypipeline_body(response)
    assert b["pipeline"].name not in content
    assert b["opportunity"].name not in content
    assert response.context["tenant"] == opportunitypipeline_pipeline_a.tenant


def test_opportunitypipeline_list_isolation_workspace(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Workspace list must only show Tenant A opportunities."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    url = _opportunitypipeline_url("opportunity_workspace_list")
    response = opportunitypipeline_client_a.get(url)
    assert response.status_code == 200

    content = _opportunitypipeline_body(response)
    assert opportunitypipeline_opportunity_a.name in content
    assert b["opportunity"].name not in content
    assert all(opp.tenant_id == opportunitypipeline_opportunity_a.tenant_id for opp in response.context["opportunities"])


def test_opportunitypipeline_list_isolation_competitors(
    opportunitypipeline_client_a,
    opportunitypipeline_competitor_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Competitor list must only show Tenant A competitors."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    url = _opportunitypipeline_url("opportunity_competitor_profile_list")
    response = opportunitypipeline_client_a.get(url)
    assert response.status_code == 200

    content = _opportunitypipeline_body(response)
    assert opportunitypipeline_competitor_a.party.name in content
    assert b["competitor"].party.name not in content
    assert all(comp.tenant_id == opportunitypipeline_competitor_a.tenant_id for comp in response.context["object_list"])


def test_opportunitypipeline_list_isolation_win_loss_reasons(
    opportunitypipeline_client_a,
    opportunitypipeline_reason_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Win/loss reasons list must only show Tenant A reasons."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    url = _opportunitypipeline_url("opportunity_win_loss_reason_list")
    response = opportunitypipeline_client_a.get(url)
    assert response.status_code == 200

    content = _opportunitypipeline_body(response)
    assert opportunitypipeline_reason_a.name in content
    assert b["reason"].name not in content
    assert all(r.tenant_id == opportunitypipeline_reason_a.tenant_id for r in response.context["object_list"])


# ============================================================================
# 3. Cross-Tenant Foreign Key Injection Tests
# ============================================================================

def test_opportunitypipeline_fk_injection_placement_rejects_foreign_pipeline_and_stage(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Submitting Tenant B's pipeline or stage to Tenant A opportunity placement must be rejected."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    place_url = _opportunitypipeline_url("opportunity_place", opportunity_pk=opportunitypipeline_opportunity_a.pk)

    # 1. Foreign pipeline injection
    response1 = opportunitypipeline_client_a.post(
        place_url,
        {
            "pipeline": b["pipeline"].pk,
            "current_stage": b["open_stage"].pk,
        },
    )
    # Form error or rejection; placement must not point to pipeline_b
    assert not OpportunityPipelinePlacement.objects.filter(
        opportunity=opportunitypipeline_opportunity_a,
        pipeline=b["pipeline"],
    ).exists()

    # 2. Foreign stage injection on tenant A pipeline
    response2 = opportunitypipeline_client_a.post(
        place_url,
        {
            "pipeline": opportunitypipeline_pipeline_a.pk,
            "current_stage": b["open_stage"].pk,
        },
    )
    assert not OpportunityPipelinePlacement.objects.filter(
        opportunity=opportunitypipeline_opportunity_a,
        current_stage=b["open_stage"],
    ).exists()


def test_opportunitypipeline_fk_injection_team_member_rejects_foreign_user_and_org_unit(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_user_b,
):
    """Submitting Tenant B's user or OrgUnit in team member add/edit must be rejected."""
    foreign_org = OrgUnit.objects.create(tenant=opportunitypipeline_tenant_b, name="Globex Sales Ops")
    add_url = _opportunitypipeline_url("opportunity_team_member_add", opportunity_pk=opportunitypipeline_opportunity_a.pk)

    # Foreign user
    response = opportunitypipeline_client_a.post(
        add_url,
        {
            "user": opportunitypipeline_user_b.pk,
            "role": "technical_lead",
            "responsibility": "Injected member",
            "is_active": True,
        },
    )
    assert not OpportunityTeamMember.objects.filter(
        opportunity=opportunitypipeline_opportunity_a,
        user=opportunitypipeline_user_b,
    ).exists()

    # Foreign OrgUnit
    response_org = opportunitypipeline_client_a.post(
        add_url,
        {
            "user": opportunitypipeline_opportunity_a.owner_id,
            "org_unit": foreign_org.pk,
            "role": "technical_lead",
            "responsibility": "Injected org",
            "is_active": True,
        },
    )
    assert not OpportunityTeamMember.objects.filter(
        opportunity=opportunitypipeline_opportunity_a,
        org_unit=foreign_org,
    ).exists()


def test_opportunitypipeline_fk_injection_competitor_link_rejects_foreign_profile(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Submitting Tenant B's competitor profile to Tenant A competitor link must be rejected."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    link_add_url = _opportunitypipeline_url(
        "opportunity_competitor_link_add",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
    )
    response = opportunitypipeline_client_a.post(
        link_add_url,
        {
            "competitor_profile": b["competitor"].pk,
            "relationship": "incumbent",
            "is_primary": True,
        },
    )
    assert not OpportunityCompetitor.objects.filter(
        opportunity=opportunitypipeline_opportunity_a,
        competitor_profile=b["competitor"],
    ).exists()


def test_opportunitypipeline_fk_injection_competitor_profile_rejects_foreign_party(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_tenant_b,
):
    """Submitting Tenant B's party organization to Tenant A competitor create must be rejected."""
    party_b = _opportunitypipeline_party(
        opportunitypipeline_tenant_b,
        name=f"Foreign Organization {timezone.now().timestamp()}",
        kind="organization",
    )
    url = _opportunitypipeline_url("opportunity_competitor_profile_create")
    response = opportunitypipeline_client_a.post(
        url,
        {
            "party": party_b.pk,
            "website_url": "https://foreign-party.example.com",
            "is_active": True,
        },
    )
    assert not CompetitorProfile.objects.filter(tenant=opportunitypipeline_tenant_a, party=party_b).exists()


def test_opportunitypipeline_fk_injection_transition_rejects_foreign_stage_reason_link(
    opportunitypipeline_client_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_placement_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Transitioning an opportunity with Tenant B's stage, reason, or competitor link must be rejected."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    transition_url = _opportunitypipeline_url(
        "opportunity_transition",
        opportunity_pk=opportunitypipeline_opportunity_a.pk,
    )
    initial_stage = opportunitypipeline_placement_a.current_stage

    # 1. Foreign target stage
    opportunitypipeline_client_a.post(
        transition_url,
        {"target_stage": b["open_stage"].pk},
    )
    opportunitypipeline_placement_a.refresh_from_db()
    assert opportunitypipeline_placement_a.current_stage == initial_stage

    # 2. Foreign reason on closed won transition
    won_stage = opportunitypipeline_pipeline_a.stages.filter(stage_kind="won").first()
    opportunitypipeline_client_a.post(
        transition_url,
        {
            "target_stage": won_stage.pk,
            "reason": b["reason"].pk,
        },
    )
    opportunitypipeline_placement_a.refresh_from_db()
    assert opportunitypipeline_placement_a.current_stage == initial_stage

    # 3. Foreign competitor link on closed lost transition
    lost_stage = opportunitypipeline_pipeline_a.stages.filter(stage_kind="lost").first()
    reason_lost_a = _opportunitypipeline_win_loss_reason(
        opportunitypipeline_pipeline_a.tenant,
        name="Price Unfavorable",
        code=f"rsn_lost_{int(timezone.now().timestamp() * 1000) % 100000}",
        result="lost",
    )
    opportunitypipeline_client_a.post(
        transition_url,
        {
            "target_stage": lost_stage.pk,
            "reason": reason_lost_a.pk,
            "competitor_link": b["comp_link"].pk,
        },
    )
    opportunitypipeline_placement_a.refresh_from_db()
    assert opportunitypipeline_placement_a.current_stage == initial_stage


def test_opportunitypipeline_fk_injection_stage_reorder_rejects_foreign_stage_id(
    opportunitypipeline_client_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_b,
    opportunitypipeline_user_b,
    opportunitypipeline_pipeline_b,
    opportunitypipeline_opportunity_b,
):
    """Stage reorder POST with Tenant B stage ID must be rejected."""
    b = _opportunitypipeline_bundle_b(
        opportunitypipeline_tenant_b,
        opportunitypipeline_admin_b,
        opportunitypipeline_user_b,
        opportunitypipeline_pipeline_b,
        opportunitypipeline_opportunity_b,
    )
    url = _opportunitypipeline_url("opportunity_pipeline_stage_reorder", pk=opportunitypipeline_pipeline_a.pk)
    stages_before = list(opportunitypipeline_pipeline_a.stages.order_by("sequence").values_list("pk", "sequence"))

    # Attempt injecting foreign stage id into sequence
    foreign_sequence = f"{b['open_stage'].pk}"
    response = opportunitypipeline_client_a.post(url, {"ordered_stage_ids": foreign_sequence})
    stages_after = list(opportunitypipeline_pipeline_a.stages.order_by("sequence").values_list("pk", "sequence"))
    assert stages_before == stages_after


# ============================================================================
# 4. Auth & Role-Based Permissions Tests
# ============================================================================

def test_opportunitypipeline_anonymous_redirects_to_login_across_all_views(
    client,
    opportunitypipeline_tenant_a,
    opportunitypipeline_admin_a,
    opportunitypipeline_user_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_placement_a,
    opportunitypipeline_competitor_a,
    opportunitypipeline_reason_a,
):
    """Anonymous unauthenticated requests to all 8.2 views must redirect (302) to login."""
    a = _opportunitypipeline_bundle_a(
        opportunitypipeline_tenant_a,
        opportunitypipeline_admin_a,
        opportunitypipeline_user_a,
        opportunitypipeline_pipeline_a,
        opportunitypipeline_opportunity_a,
        opportunitypipeline_placement_a,
        opportunitypipeline_competitor_a,
        opportunitypipeline_reason_a,
    )
    route_cases = [
        ("opportunity_pipeline_list", {}),
        ("opportunity_pipeline_board", {}),
        ("opportunity_pipeline_visibility", {}),
        ("opportunity_pipeline_create", {}),
        ("opportunity_pipeline_stage_reorder", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_stage_create", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_stage_edit", {"pk": a["pipeline"].pk, "stage_pk": a["open_stage"].pk}),
        ("opportunity_pipeline_stage_delete", {"pk": a["pipeline"].pk, "stage_pk": a["open_stage"].pk}),
        ("opportunity_pipeline_set_default", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_edit", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_delete", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_stages", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_detail", {"pk": a["pipeline"].pk}),
        ("opportunity_workspace_list", {}),
        ("opportunity_place", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_unplace", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_workspace_detail", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_team_member_add", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_team_member_edit", {"opportunity_pk": a["opportunity"].pk, "member_pk": a["team_member"].pk}),
        ("opportunity_team_member_remove", {"opportunity_pk": a["opportunity"].pk, "member_pk": a["team_member"].pk}),
        ("opportunity_competitor_profile_list", {}),
        ("opportunity_competitor_profile_create", {}),
        ("opportunity_competitor_profile_detail", {"pk": a["competitor"].pk}),
        ("opportunity_competitor_profile_edit", {"pk": a["competitor"].pk}),
        ("opportunity_competitor_profile_delete", {"pk": a["competitor"].pk}),
        ("opportunity_competitor_link_add", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_competitor_link_edit", {"opportunity_pk": a["opportunity"].pk, "competitor_pk": a["comp_link"].pk}),
        ("opportunity_competitor_link_remove", {"opportunity_pk": a["opportunity"].pk, "competitor_pk": a["comp_link"].pk}),
        ("opportunity_win_loss_reason_list", {}),
        ("opportunity_win_loss_reason_create", {}),
        ("opportunity_transition", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_win_loss_reason_edit", {"pk": a["reason"].pk}),
        ("opportunity_win_loss_reason_delete", {"pk": a["reason"].pk}),
        ("opportunity_win_loss_reason_detail", {"pk": a["reason"].pk}),
    ]

    post_only_routes = {
        "opportunity_pipeline_stage_reorder",
        "opportunity_pipeline_stage_delete",
        "opportunity_pipeline_set_default",
        "opportunity_pipeline_delete",
        "opportunity_unplace",
        "opportunity_transition",
        "opportunity_team_member_remove",
        "opportunity_competitor_profile_delete",
        "opportunity_competitor_link_remove",
        "opportunity_win_loss_reason_delete",
    }

    for name, kwargs in route_cases:
        url = _opportunitypipeline_url(name, **kwargs)
        # Check GET redirect or 405 for POST-only
        resp_get = client.get(url)
        if name in post_only_routes:
            assert resp_get.status_code in (302, 405), f"Expected 302 or 405 on GET {name} but got {resp_get.status_code}"
            if resp_get.status_code == 302:
                assert "login" in resp_get.url.lower(), f"Expected login in redirect URL for {name}"
        else:
            assert resp_get.status_code == 302, f"Expected 302 on GET {name} but got {resp_get.status_code}"
            assert "login" in resp_get.url.lower(), f"Expected login in redirect URL for {name}"

        # Check POST redirect
        resp_post = client.post(url, {})
        assert resp_post.status_code == 302, f"Expected 302 on POST {name} but got {resp_post.status_code}"
        assert "login" in resp_post.url.lower(), f"Expected login in redirect URL for {name}"


def test_opportunitypipeline_non_admin_forbidden_on_pipeline_actions(
    opportunitypipeline_client_member_a,
    opportunitypipeline_pipeline_a,
):
    """Non-admin tenant user must receive 403 Forbidden on admin-gated pipeline actions."""
    create_url = _opportunitypipeline_url("opportunity_pipeline_create")
    edit_url = _opportunitypipeline_url("opportunity_pipeline_edit", pk=opportunitypipeline_pipeline_a.pk)
    delete_url = _opportunitypipeline_url("opportunity_pipeline_delete", pk=opportunitypipeline_pipeline_a.pk)
    default_url = _opportunitypipeline_url("opportunity_pipeline_set_default", pk=opportunitypipeline_pipeline_a.pk)

    assert opportunitypipeline_client_member_a.get(create_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(create_url, {"name": "NonAdmin Pipe"}).status_code == 403
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(edit_url, {"name": "Changed Name"}).status_code == 403
    assert opportunitypipeline_client_member_a.post(delete_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(default_url).status_code == 403


def test_opportunitypipeline_non_admin_forbidden_on_stage_actions(
    opportunitypipeline_client_member_a,
    opportunitypipeline_pipeline_a,
):
    """Non-admin tenant user must receive 403 Forbidden on stage create/edit/delete/reorder."""
    stage = opportunitypipeline_pipeline_a.stages.first()
    create_url = _opportunitypipeline_url("opportunity_pipeline_stage_create", pk=opportunitypipeline_pipeline_a.pk)
    edit_url = _opportunitypipeline_url("opportunity_pipeline_stage_edit", pk=opportunitypipeline_pipeline_a.pk, stage_pk=stage.pk)
    delete_url = _opportunitypipeline_url("opportunity_pipeline_stage_delete", pk=opportunitypipeline_pipeline_a.pk, stage_pk=stage.pk)
    reorder_url = _opportunitypipeline_url("opportunity_pipeline_stage_reorder", pk=opportunitypipeline_pipeline_a.pk)

    assert opportunitypipeline_client_member_a.get(create_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(create_url, {"name": "Stage"}).status_code == 403
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(edit_url, {"name": "Stage Mod"}).status_code == 403
    assert opportunitypipeline_client_member_a.post(delete_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(reorder_url, {"ordered_stage_ids": f"{stage.pk}"}).status_code == 403


def test_opportunitypipeline_non_admin_forbidden_on_competitor_actions(
    opportunitypipeline_client_member_a,
    opportunitypipeline_competitor_a,
):
    """Non-admin tenant user must receive 403 Forbidden on competitor create/edit/delete."""
    create_url = _opportunitypipeline_url("opportunity_competitor_profile_create")
    edit_url = _opportunitypipeline_url("opportunity_competitor_profile_edit", pk=opportunitypipeline_competitor_a.pk)
    delete_url = _opportunitypipeline_url("opportunity_competitor_profile_delete", pk=opportunitypipeline_competitor_a.pk)

    assert opportunitypipeline_client_member_a.get(create_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(create_url, {"website_url": "https://test.com"}).status_code == 403
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(edit_url, {"website_url": "https://test.com"}).status_code == 403
    assert opportunitypipeline_client_member_a.post(delete_url).status_code == 403


def test_opportunitypipeline_non_admin_forbidden_on_win_loss_reason_actions(
    opportunitypipeline_client_member_a,
    opportunitypipeline_reason_a,
):
    """Non-admin tenant user must receive 403 Forbidden on win/loss reason create/edit/delete."""
    create_url = _opportunitypipeline_url("opportunity_win_loss_reason_create")
    edit_url = _opportunitypipeline_url("opportunity_win_loss_reason_edit", pk=opportunitypipeline_reason_a.pk)
    delete_url = _opportunitypipeline_url("opportunity_win_loss_reason_delete", pk=opportunitypipeline_reason_a.pk)

    assert opportunitypipeline_client_member_a.get(create_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(create_url, {"name": "Reason"}).status_code == 403
    assert opportunitypipeline_client_member_a.get(edit_url).status_code == 403
    assert opportunitypipeline_client_member_a.post(edit_url, {"name": "Reason Mod"}).status_code == 403
    assert opportunitypipeline_client_member_a.post(delete_url).status_code == 403


def test_opportunitypipeline_object_auth_unplace_regular_rep_forbidden(
    opportunitypipeline_client_member_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_user_a,
    opportunitypipeline_placement_a,
):
    """Regular sales rep who is neither owner nor co-owner/approver gets 403 on unplace."""
    unplace_url = _opportunitypipeline_url("opportunity_unplace", opportunity_pk=opportunitypipeline_opportunity_a.pk)

    # user_a is not owner, no team membership
    assert opportunitypipeline_client_member_a.post(unplace_url).status_code == 403

    # user_a added with role='sales_rep' (not co_owner or approver) -> still 403
    member = _opportunitypipeline_team_member(
        opportunitypipeline_opportunity_a.tenant,
        opportunitypipeline_opportunity_a,
        opportunitypipeline_user_a,
        role="sales_rep",
    )
    assert opportunitypipeline_client_member_a.post(unplace_url).status_code == 403
    member.delete()


def test_opportunitypipeline_object_auth_unplace_authorized_roles_allowed(
    opportunitypipeline_tenant_a,
    opportunitypipeline_user_a,
    opportunitypipeline_admin_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_client_member_a,
    opportunitypipeline_client_a,
):
    """Owner, co-owner, approver, or tenant admin can successfully unplace an opportunity."""
    stage = opportunitypipeline_pipeline_a.stages.filter(stage_kind="open").first()

    # 1. Opportunity owner (regular user)
    owned_opp = _opportunitypipeline_opportunity(
        opportunitypipeline_tenant_a,
        title="Rep Owned Deal",
        owner=opportunitypipeline_user_a,
    )
    _opportunitypipeline_placement(opportunitypipeline_tenant_a, owned_opp, opportunitypipeline_pipeline_a, stage)
    unplace_url = _opportunitypipeline_url("opportunity_unplace", opportunity_pk=owned_opp.pk)
    resp = opportunitypipeline_client_member_a.post(unplace_url)
    assert resp.status_code == 302
    assert not OpportunityPipelinePlacement.objects.filter(opportunity=owned_opp).exists()

    # 2. Team member with role='co_owner'
    co_owned_opp = _opportunitypipeline_opportunity(
        opportunitypipeline_tenant_a,
        title="Co-owned Deal",
        owner=opportunitypipeline_admin_a,
    )
    _opportunitypipeline_placement(opportunitypipeline_tenant_a, co_owned_opp, opportunitypipeline_pipeline_a, stage)
    _opportunitypipeline_team_member(
        opportunitypipeline_tenant_a,
        co_owned_opp,
        opportunitypipeline_user_a,
        role="co_owner",
    )
    unplace_url2 = _opportunitypipeline_url("opportunity_unplace", opportunity_pk=co_owned_opp.pk)
    resp2 = opportunitypipeline_client_member_a.post(unplace_url2)
    assert resp2.status_code == 302
    assert not OpportunityPipelinePlacement.objects.filter(opportunity=co_owned_opp).exists()

    # 3. Team member with role='approver'
    approved_opp = _opportunitypipeline_opportunity(
        opportunitypipeline_tenant_a,
        title="Approver Deal",
        owner=opportunitypipeline_admin_a,
    )
    _opportunitypipeline_placement(opportunitypipeline_tenant_a, approved_opp, opportunitypipeline_pipeline_a, stage)
    _opportunitypipeline_team_member(
        opportunitypipeline_tenant_a,
        approved_opp,
        opportunitypipeline_user_a,
        role="approver",
    )
    unplace_url3 = _opportunitypipeline_url("opportunity_unplace", opportunity_pk=approved_opp.pk)
    resp3 = opportunitypipeline_client_member_a.post(unplace_url3)
    assert resp3.status_code == 302
    assert not OpportunityPipelinePlacement.objects.filter(opportunity=approved_opp).exists()

    # 4. Tenant admin
    admin_opp = _opportunitypipeline_opportunity(
        opportunitypipeline_tenant_a,
        title="Admin Managed Deal",
        owner=opportunitypipeline_user_a,
    )
    _opportunitypipeline_placement(opportunitypipeline_tenant_a, admin_opp, opportunitypipeline_pipeline_a, stage)
    unplace_url4 = _opportunitypipeline_url("opportunity_unplace", opportunity_pk=admin_opp.pk)
    resp4 = opportunitypipeline_client_a.post(unplace_url4)
    assert resp4.status_code == 302
    assert not OpportunityPipelinePlacement.objects.filter(opportunity=admin_opp).exists()


# ============================================================================
# 5. CSRF Protection Tests
# ============================================================================

def test_opportunitypipeline_csrf_protection_on_post_endpoints(
    opportunitypipeline_tenant_a,
    opportunitypipeline_admin_a,
    opportunitypipeline_user_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_placement_a,
    opportunitypipeline_competitor_a,
    opportunitypipeline_reason_a,
):
    """POST to endpoints without CSRF token using Client(enforce_csrf_checks=True) must return 403."""
    a = _opportunitypipeline_bundle_a(
        opportunitypipeline_tenant_a,
        opportunitypipeline_admin_a,
        opportunitypipeline_user_a,
        opportunitypipeline_pipeline_a,
        opportunitypipeline_opportunity_a,
        opportunitypipeline_placement_a,
        opportunitypipeline_competitor_a,
        opportunitypipeline_reason_a,
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(opportunitypipeline_admin_a)

    post_routes = [
        ("opportunity_pipeline_create", {}),
        ("opportunity_pipeline_edit", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_delete", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_set_default", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_stage_create", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_stage_edit", {"pk": a["pipeline"].pk, "stage_pk": a["open_stage"].pk}),
        ("opportunity_pipeline_stage_delete", {"pk": a["pipeline"].pk, "stage_pk": a["open_stage"].pk}),
        ("opportunity_pipeline_stage_reorder", {"pk": a["pipeline"].pk}),
        ("opportunity_place", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_unplace", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_transition", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_team_member_add", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_team_member_edit", {"opportunity_pk": a["opportunity"].pk, "member_pk": a["team_member"].pk}),
        ("opportunity_team_member_remove", {"opportunity_pk": a["opportunity"].pk, "member_pk": a["team_member"].pk}),
        ("opportunity_competitor_profile_create", {}),
        ("opportunity_competitor_profile_edit", {"pk": a["competitor"].pk}),
        ("opportunity_competitor_profile_delete", {"pk": a["competitor"].pk}),
        ("opportunity_competitor_link_add", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_competitor_link_edit", {"opportunity_pk": a["opportunity"].pk, "competitor_pk": a["comp_link"].pk}),
        ("opportunity_competitor_link_remove", {"opportunity_pk": a["opportunity"].pk, "competitor_pk": a["comp_link"].pk}),
        ("opportunity_win_loss_reason_create", {}),
        ("opportunity_win_loss_reason_edit", {"pk": a["reason"].pk}),
        ("opportunity_win_loss_reason_delete", {"pk": a["reason"].pk}),
    ]

    for name, kwargs in post_routes:
        url = _opportunitypipeline_url(name, **kwargs)
        response = csrf_client.post(url, {})
        assert response.status_code == 403, f"Expected 403 CSRF rejection on {name}, got {response.status_code}"


# ============================================================================
# 6. HTTP Method Protection Tests
# ============================================================================

def test_opportunitypipeline_http_method_protection_post_only_endpoints_reject_get(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_admin_a,
    opportunitypipeline_user_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_placement_a,
    opportunitypipeline_competitor_a,
    opportunitypipeline_reason_a,
):
    """GET on POST-only endpoints must return 405 Method Not Allowed."""
    a = _opportunitypipeline_bundle_a(
        opportunitypipeline_tenant_a,
        opportunitypipeline_admin_a,
        opportunitypipeline_user_a,
        opportunitypipeline_pipeline_a,
        opportunitypipeline_opportunity_a,
        opportunitypipeline_placement_a,
        opportunitypipeline_competitor_a,
        opportunitypipeline_reason_a,
    )
    post_only_routes = [
        ("opportunity_pipeline_delete", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_set_default", {"pk": a["pipeline"].pk}),
        ("opportunity_pipeline_stage_delete", {"pk": a["pipeline"].pk, "stage_pk": a["open_stage"].pk}),
        ("opportunity_pipeline_stage_reorder", {"pk": a["pipeline"].pk}),
        ("opportunity_unplace", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_transition", {"opportunity_pk": a["opportunity"].pk}),
        ("opportunity_team_member_remove", {"opportunity_pk": a["opportunity"].pk, "member_pk": a["team_member"].pk}),
        ("opportunity_competitor_profile_delete", {"pk": a["competitor"].pk}),
        ("opportunity_competitor_link_remove", {"opportunity_pk": a["opportunity"].pk, "competitor_pk": a["comp_link"].pk}),
        ("opportunity_win_loss_reason_delete", {"pk": a["reason"].pk}),
    ]

    for name, kwargs in post_only_routes:
        url = _opportunitypipeline_url(name, **kwargs)
        response = opportunitypipeline_client_a.get(url)
        assert response.status_code == 405, f"Expected 405 on GET {name} but got {response.status_code}"


# ============================================================================
# 7. XSS Protection Tests
# ============================================================================

def test_opportunitypipeline_xss_protection_pipeline_fields(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_admin_a,
):
    """Script tags in pipeline names and descriptions must be HTML-escaped."""
    xss_payload = '<script>alert("pipeline_xss")</script>'
    pipeline = _opportunitypipeline_pipeline(
        opportunitypipeline_tenant_a,
        name=f"SecPipe {xss_payload}",
        code="XSS_P1",
        owner=opportunitypipeline_admin_a,
    )
    _opportunitypipeline_stage(
        opportunitypipeline_tenant_a,
        pipeline,
        name=f"Stage {xss_payload}",
        sequence=10,
    )

    # 1. Pipeline list
    list_resp = opportunitypipeline_client_a.get(_opportunitypipeline_url("opportunity_pipeline_list"))
    assert list_resp.status_code == 200
    list_body = _opportunitypipeline_body(list_resp)
    assert xss_payload not in list_body
    assert escape(xss_payload) in list_body or "&lt;script&gt;" in list_body

    # 2. Pipeline detail
    detail_resp = opportunitypipeline_client_a.get(_opportunitypipeline_url("opportunity_pipeline_detail", pk=pipeline.pk))
    assert detail_resp.status_code == 200
    detail_body = _opportunitypipeline_body(detail_resp)
    assert xss_payload not in detail_body
    assert escape(xss_payload) in detail_body or "&lt;script&gt;" in detail_body


def test_opportunitypipeline_xss_protection_competitor_fields(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
):
    """Script tags in competitor descriptions and notes must be HTML-escaped."""
    xss_payload = '<script>alert("competitor_xss")</script>'
    party = _opportunitypipeline_party(
        opportunitypipeline_tenant_a,
        name=f"CompParty {xss_payload}",
        kind="organization",
    )
    comp = _opportunitypipeline_competitor_profile(
        opportunitypipeline_tenant_a,
        party=party,
        description=f"Desc {xss_payload}",
        website="https://xss.example.com",
    )

    list_resp = opportunitypipeline_client_a.get(_opportunitypipeline_url("opportunity_competitor_profile_list"))
    assert list_resp.status_code == 200
    list_body = _opportunitypipeline_body(list_resp)
    assert xss_payload not in list_body

    detail_resp = opportunitypipeline_client_a.get(_opportunitypipeline_url("opportunity_competitor_profile_detail", pk=comp.pk))
    assert detail_resp.status_code == 200
    detail_body = _opportunitypipeline_body(detail_resp)
    assert xss_payload not in detail_body
    assert "&lt;script&gt;" in detail_body or escape(xss_payload) in detail_body


def test_opportunitypipeline_xss_protection_team_member_and_outcome_notes(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
    opportunitypipeline_opportunity_a,
    opportunitypipeline_user_a,
    opportunitypipeline_reason_a,
):
    """Script tags in team member responsibility and outcome notes must be HTML-escaped."""
    xss_payload = '<script>alert("workspace_xss")</script>'
    _opportunitypipeline_team_member(
        opportunitypipeline_tenant_a,
        opportunitypipeline_opportunity_a,
        opportunitypipeline_user_a,
        role="technical_lead",
        responsibility=f"Lead {xss_payload}",
    )
    _opportunitypipeline_outcome(
        opportunitypipeline_tenant_a,
        opportunitypipeline_opportunity_a,
        result="won",
        reason=opportunitypipeline_reason_a,
        notes=f"Outcome notes {xss_payload}",
    )

    detail_url = _opportunitypipeline_url("opportunity_workspace_detail", opportunity_pk=opportunitypipeline_opportunity_a.pk)
    resp = opportunitypipeline_client_a.get(detail_url)
    assert resp.status_code == 200
    body = _opportunitypipeline_body(resp)
    assert xss_payload not in body
    assert "&lt;script&gt;" in body or escape(xss_payload) in body


def test_opportunitypipeline_xss_protection_win_loss_reason_fields(
    opportunitypipeline_client_a,
    opportunitypipeline_tenant_a,
):
    """Script tags in win/loss reason names and descriptions must be HTML-escaped."""
    xss_payload = '<script>alert("reason_xss")</script>'
    reason = _opportunitypipeline_win_loss_reason(
        opportunitypipeline_tenant_a,
        name=f"Reason {xss_payload}",
        code="XSS_RSN",
        description=f"Desc {xss_payload}",
        result="lost",
    )

    list_resp = opportunitypipeline_client_a.get(_opportunitypipeline_url("opportunity_win_loss_reason_list"))
    assert list_resp.status_code == 200
    list_body = _opportunitypipeline_body(list_resp)
    assert xss_payload not in list_body

    detail_resp = opportunitypipeline_client_a.get(_opportunitypipeline_url("opportunity_win_loss_reason_detail", pk=reason.pk))
    assert detail_resp.status_code == 200
    detail_body = _opportunitypipeline_body(detail_resp)
    assert xss_payload not in detail_body
    assert "&lt;script&gt;" in detail_body or escape(xss_payload) in detail_body


# ============================================================================
# 8. Tenantless User Protection Tests
# ============================================================================

def test_opportunitypipeline_tenantless_user_cannot_access_or_mutate_tenant_data(
    opportunitypipeline_tenant_a,
    opportunitypipeline_pipeline_a,
    opportunitypipeline_opportunity_a,
):
    """A user without a tenant (e.g. root/tenantless superuser) cannot view or mutate tenant data."""
    root_user = User.objects.create_user(
        email="root_pipeline_sec@example.com",
        username="root_pipe_sec",
        password="password",
        tenant=None,
        is_staff=True,
        is_superuser=True,
        is_tenant_admin=True,
    )
    root_client = Client()
    root_client.force_login(root_user)

    # 1. Lists return empty
    list_resp = root_client.get(_opportunitypipeline_url("opportunity_pipeline_list"))
    assert list_resp.status_code == 200
    assert list(list_resp.context["object_list"]) == []

    workspace_resp = root_client.get(_opportunitypipeline_url("opportunity_workspace_list"))
    assert workspace_resp.status_code == 200
    assert list(workspace_resp.context["opportunities"]) == []

    comp_resp = root_client.get(_opportunitypipeline_url("opportunity_competitor_profile_list"))
    assert comp_resp.status_code == 200
    assert list(comp_resp.context["object_list"]) == []

    reason_resp = root_client.get(_opportunitypipeline_url("opportunity_win_loss_reason_list"))
    assert reason_resp.status_code == 200
    assert list(reason_resp.context["object_list"]) == []

    # 2. Detail pages return 404
    assert root_client.get(_opportunitypipeline_url("opportunity_pipeline_detail", pk=opportunitypipeline_pipeline_a.pk)).status_code == 404
    assert root_client.get(_opportunitypipeline_url("opportunity_workspace_detail", opportunity_pk=opportunitypipeline_opportunity_a.pk)).status_code == 404
