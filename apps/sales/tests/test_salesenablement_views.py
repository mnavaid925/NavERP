"""Sales 8.9 — Sales Enablement Views Test Suite.

Covers:
1. Full CRUD for all 4 models:
   - EnablementContent (list filters/search, create with prepopulation/tenant/author, detail view_count/doc name, edit, delete POST-only/audit/permissions)
   - SalesPlaybook (list filters/search, create with tenant/owner, detail, edit, delete POST-only/audit/permissions)
   - SalesCertification (list filters/search, create with self-certify block, detail, edit, delete POST-only/audit/permissions)
   - CoachingScorecard (list filters/search, create with prepopulation/draft status, detail, edit, delete POST-only/audit/permissions)
2. 5 Enablement Boards:
   - sales_enablement_content_hub
   - sales_playbook_board
   - sales_readiness_board
   - sales_coaching_workbench
   - sales_competitive_intelligence_library
3. Custom Actions:
   - enablement_content_share (POST increments share_count, GET 405, inactive/expired blocked)
   - coaching_scorecard_acknowledge (POST transitions status for coachee or admin, GET 405, unauthorized blocked)
4. Robustness:
   - Junk GET query parameters return 200 cleanly
   - Multi-page pagination across models
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, Party
from apps.crm.models import CommunicationLog
from apps.sales.models import (
    CoachingScorecard,
    CompetitorProfile,
    EnablementContent,
    Pipeline,
    SalesCertification,
    SalesPlaybook,
)
from apps.sales.tests.conftest import (
    _salesenablement_certification,
    _salesenablement_content,
    _salesenablement_document,
    _salesenablement_playbook,
    _salesenablement_scorecard,
)

pytestmark = pytest.mark.django_db


def _salesenablement_create_user(tenant, username, is_admin=False):
    """Helper to create a tenant user for permission testing."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
    )


def _salesenablement_create_competitor(tenant, name="Alpha Corp", **overrides):
    """Helper to create CompetitorProfile with valid model fields."""
    label = f"{timezone.now().timestamp():.6f}"[-6:]
    party = Party.objects.create(
        tenant=tenant,
        name=f"{name} {label}",
        kind="organization",
    )
    defaults = {
        "tenant": tenant,
        "party": party,
        "market_positioning": "Tier 1 Enterprise Competitor",
        "strengths": "Brand legacy, large salesforce",
        "weaknesses": "Outdated UI, high implementation cost",
        "differentiators": "Modern API and lower TCO",
        "objection_handling": "Anchor on developer agility and ROI",
        "is_active": True,
    }
    defaults.update(overrides)
    return CompetitorProfile.objects.create(**defaults)


# ==============================================================================
# 1. EnablementContent CRUD
# ==============================================================================


def test_salesenablement_content_list_unauthenticated(client):
    """Unauthenticated access redirects to login."""
    url = reverse("sales:enablement_content_list")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login" in resp["Location"]


def test_salesenablement_content_list_empty(client_a):
    """Empty list returns 200 OK and expected context keys."""
    url = reverse("sales:enablement_content_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert len(resp.context["contents"]) == 0
    assert "content_type_choices" in resp.context
    assert "stage_choices" in resp.context
    assert "persona_choices" in resp.context
    assert "competitors" in resp.context


def test_salesenablement_content_list_filters_and_search(client_a, tenant_a, admin_user):
    """Filter by content_type, target_stage, target_persona, competitor and search q."""
    comp = _salesenablement_create_competitor(tenant_a, name="Apex Competitor")
    c1 = _salesenablement_content(
        tenant_a,
        author=admin_user,
        title="Enterprise Pitch Deck Q4",
        content_type="pitch_deck",
        target_stage="prospecting",
        target_persona="c_level",
        tags="pitch,enterprise,deck",
    )
    c2 = _salesenablement_content(
        tenant_a,
        author=admin_user,
        title="Apex Battlecard 2026",
        content_type="battle_card",
        competitor=comp,
        target_stage="closing",
        target_persona="procurement",
        tags="battlecard,apex",
    )
    c3 = _salesenablement_content(
        tenant_a,
        author=admin_user,
        title="Customer Case Study Fintech",
        content_type="case_study",
        target_stage="qualification",
        target_persona="vp_director",
        tags="fintech,case_study",
    )

    url = reverse("sales:enablement_content_list")

    # Search q by title
    resp_q = client_a.get(url, {"q": "Battlecard"})
    assert resp_q.status_code == 200
    results_q = list(resp_q.context["contents"])
    assert len(results_q) == 1
    assert results_q[0].pk == c2.pk

    # Search q by tag
    resp_tag = client_a.get(url, {"q": "fintech"})
    assert resp_tag.status_code == 200
    assert len(resp_tag.context["contents"]) == 1
    assert resp_tag.context["contents"][0].pk == c3.pk

    # Search q by number
    resp_num = client_a.get(url, {"q": c1.number})
    assert resp_num.status_code == 200
    assert len(resp_num.context["contents"]) == 1
    assert resp_num.context["contents"][0].pk == c1.pk

    # Filter content_type
    resp_type = client_a.get(url, {"content_type": "battle_card"})
    assert resp_type.status_code == 200
    assert len(resp_type.context["contents"]) == 1
    assert resp_type.context["contents"][0].pk == c2.pk

    # Filter target_stage
    resp_stage = client_a.get(url, {"target_stage": "prospecting"})
    assert resp_stage.status_code == 200
    assert len(resp_stage.context["contents"]) == 1
    assert resp_stage.context["contents"][0].pk == c1.pk

    # Filter target_persona
    resp_persona = client_a.get(url, {"target_persona": "procurement"})
    assert resp_persona.status_code == 200
    assert len(resp_persona.context["contents"]) == 1
    assert resp_persona.context["contents"][0].pk == c2.pk

    # Filter competitor
    resp_comp = client_a.get(url, {"competitor": str(comp.pk)})
    assert resp_comp.status_code == 200
    assert len(resp_comp.context["contents"]) == 1
    assert resp_comp.context["contents"][0].pk == c2.pk


def test_salesenablement_content_list_tenant_isolation(
    client_a, client_b, enablement_content_a, enablement_content_b
):
    """Tenant A sees only its content; Tenant B sees only its content."""
    url = reverse("sales:enablement_content_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["contents"])
    assert enablement_content_a in items_a
    assert enablement_content_b not in items_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["contents"])
    assert enablement_content_b in items_b
    assert enablement_content_a not in items_b


def test_salesenablement_content_create_get_prepopulates_competitor(client_a, tenant_a):
    """GET create view prepopulates competitor when ?competitor=<id> is supplied."""
    comp = _salesenablement_create_competitor(tenant_a, name="Target Prepop Corp")
    url = reverse("sales:enablement_content_create")

    # Valid competitor id
    resp = client_a.get(url, {"competitor": str(comp.pk)})
    assert resp.status_code == 200
    assert resp.context["form"].initial.get("competitor") == comp.pk
    assert resp.context["is_edit"] is False

    # Junk competitor id does not crash
    resp_junk = client_a.get(url, {"competitor": "not-an-id"})
    assert resp_junk.status_code == 200
    assert "competitor" not in resp_junk.context["form"].initial


def test_salesenablement_content_create_post_success(client_a, tenant_a, admin_user):
    """POST creates EnablementContent, sets tenant and defaults author to request.user."""
    url = reverse("sales:enablement_content_create")
    post_data = {
        "title": "Master Pitch Deck 2026",
        "description": "Standard corporate presentation for enterprise buyers.",
        "content_type": "pitch_deck",
        "target_stage": "prospecting",
        "target_persona": "c_level",
        "tags": "pitch,deck,sales",
        "version": "1.0",
        "is_client_facing": True,
        "is_active": True,
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    created = EnablementContent.objects.get(tenant=tenant_a, title="Master Pitch Deck 2026")
    assert resp["Location"] == reverse("sales:enablement_content_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.author == admin_user
    assert created.is_client_facing is True
    assert created.view_count == 0

    # Audit log check
    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).first()
    assert audit is not None
    assert audit.changes.get("title") == created.title


def test_salesenablement_content_create_post_invalid(client_a):
    """POST invalid data returns form with errors and 200 OK."""
    url = reverse("sales:enablement_content_create")
    # Empty title and no content payload (neither doc nor url nor description)
    resp = client_a.post(url, data={"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_salesenablement_content_detail_renders_document_and_increments_views(
    client_a, tenant_a, admin_user
):
    """Detail view increments view_count and renders document.name."""
    doc = _salesenablement_document(tenant_a, name="Security Whitepaper Collateral")
    content = _salesenablement_content(
        tenant_a,
        author=admin_user,
        title="Enterprise Security Brief",
        document=doc,
        view_count=0,
    )
    url = reverse("sales:enablement_content_detail", kwargs={"pk": content.pk})

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "content" in resp.context
    assert resp.context["content"].pk == content.pk
    assert doc.name in resp.content.decode()

    content.refresh_from_db()
    assert content.view_count == 1

    # Second view increments again
    client_a.get(url)
    content.refresh_from_db()
    assert content.view_count == 2


def test_salesenablement_content_detail_cross_tenant_404(client_a, enablement_content_b):
    """Cross-tenant detail request returns 404."""
    url = reverse("sales:enablement_content_detail", kwargs={"pk": enablement_content_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_salesenablement_content_edit_get_and_post(client_a, tenant_a, enablement_content_a):
    """GET and POST edit view updates fields and writes audit log."""
    url = reverse("sales:enablement_content_edit", kwargs={"pk": enablement_content_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["content"].pk == enablement_content_a.pk

    # POST
    post_data = {
        "title": "Updated Collateral Pitch Deck",
        "description": "Updated corporate overview description.",
        "content_type": enablement_content_a.content_type,
        "target_stage": "demo_eval",
        "target_persona": "technical_buyer",
        "version": "2.0",
        "is_active": True,
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "sales:enablement_content_detail", kwargs={"pk": enablement_content_a.pk}
    )

    enablement_content_a.refresh_from_db()
    assert enablement_content_a.title == "Updated Collateral Pitch Deck"
    assert enablement_content_a.target_stage == "demo_eval"
    assert enablement_content_a.version == "2.0"

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=enablement_content_a.pk
    ).first()
    assert audit is not None
    assert audit.changes.get("title") == "Updated Collateral Pitch Deck"


def test_salesenablement_content_edit_cross_tenant_404(client_a, enablement_content_b):
    """Cross-tenant edit returns 404."""
    url = reverse("sales:enablement_content_edit", kwargs={"pk": enablement_content_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_salesenablement_content_delete_post_only(client_a, enablement_content_a):
    """GET delete returns 405 Method Not Allowed."""
    url = reverse("sales:enablement_content_delete", kwargs={"pk": enablement_content_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert EnablementContent.objects.filter(pk=enablement_content_a.pk).exists()


def test_salesenablement_content_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Non-admin non-author rep cannot delete; author or admin can delete."""
    content_admin = _salesenablement_content(tenant_a, author=admin_user, title="Admin Authored Content")

    # Member rep attempts delete on admin-authored content
    url_admin = reverse("sales:enablement_content_delete", kwargs={"pk": content_admin.pk})
    resp_member = member_client.post(url_admin, follow=True)
    assert resp_member.status_code == 200
    assert EnablementContent.objects.filter(pk=content_admin.pk).exists()
    messages = [m.message for m in get_messages(resp_member.wsgi_request)]
    assert any("Only the author or a tenant administrator" in m for m in messages)

    # Member rep deletes their own authored content
    content_member = _salesenablement_content(tenant_a, author=member_user, title="Member Authored Content")
    url_member = reverse("sales:enablement_content_delete", kwargs={"pk": content_member.pk})
    resp_author = member_client.post(url_member)
    assert resp_author.status_code == 302
    assert resp_author["Location"] == reverse("sales:enablement_content_list")
    assert not EnablementContent.objects.filter(pk=content_member.pk).exists()

    # Admin deletes content_admin
    resp_admin = client_a.post(url_admin)
    assert resp_admin.status_code == 302
    assert not EnablementContent.objects.filter(pk=content_admin.pk).exists()
    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=content_admin.pk
    ).first()
    assert audit is not None


def test_salesenablement_content_delete_cross_tenant_404(client_a, enablement_content_b):
    """Cross-tenant delete returns 404."""
    url = reverse("sales:enablement_content_delete", kwargs={"pk": enablement_content_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 2. SalesPlaybook CRUD
# ==============================================================================


def test_salesenablement_playbook_list_filters_and_search(client_a, tenant_a, admin_user):
    """Filter playbooks by motion_type, status, pipeline, and search q."""
    pipeline = Pipeline.objects.create(
        tenant=tenant_a,
        name="Enterprise Sales Pipeline",
        is_active=True,
    )
    pb1 = _salesenablement_playbook(
        tenant_a,
        owner=admin_user,
        name="Enterprise New Business Playbook",
        motion_type="new_business",
        status="published",
        pipeline=pipeline,
        summary="Detailed steps for closing Fortune 500 accounts.",
    )
    pb2 = _salesenablement_playbook(
        tenant_a,
        owner=admin_user,
        name="Expansion Upsell Matrix",
        motion_type="expansion",
        status="draft",
        summary="Playbook for cross-selling additional business units.",
    )

    url = reverse("sales:sales_playbook_list")

    # Search q
    resp_q = client_a.get(url, {"q": "Fortune 500"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["playbooks"]) == 1
    assert resp_q.context["playbooks"][0].pk == pb1.pk

    # Filter motion_type
    resp_motion = client_a.get(url, {"motion_type": "expansion"})
    assert resp_motion.status_code == 200
    assert len(resp_motion.context["playbooks"]) == 1
    assert resp_motion.context["playbooks"][0].pk == pb2.pk

    # Filter status
    resp_status = client_a.get(url, {"status": "published"})
    assert resp_status.status_code == 200
    assert len(resp_status.context["playbooks"]) == 1
    assert resp_status.context["playbooks"][0].pk == pb1.pk

    # Filter pipeline
    resp_pipe = client_a.get(url, {"pipeline": str(pipeline.pk)})
    assert resp_pipe.status_code == 200
    assert len(resp_pipe.context["playbooks"]) == 1
    assert resp_pipe.context["playbooks"][0].pk == pb1.pk


def test_salesenablement_playbook_list_tenant_isolation(
    client_a, client_b, sales_playbook_a, sales_playbook_b
):
    """Playbooks are strictly scoped to tenant."""
    url = reverse("sales:sales_playbook_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["playbooks"])
    assert sales_playbook_a in items_a
    assert sales_playbook_b not in items_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["playbooks"])
    assert sales_playbook_b in items_b
    assert sales_playbook_a not in items_b


def test_salesenablement_playbook_create_get_and_post(client_a, tenant_a, admin_user):
    """GET renders empty form; POST creates playbook with owner defaulting to request.user."""
    url = reverse("sales:sales_playbook_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False
    assert "form" in resp_get.context

    # POST
    post_data = {
        "name": "Competitive Takeout Playbook",
        "summary": "Tactical guidelines to displace legacy vendors.",
        "motion_type": "competitive_displacement",
        "status": "published",
        "target_audience": "Mid-Market Account Executives",
        "discovery_questions": "What limitations are you experiencing with current tool?",
        "talk_tracks": "Focus on API speed and modern UX.",
        "objection_scripts": "Address migration concerns upfront.",
        "dos_and_donts": "Do highlight ROI; Don't badmouth competitor.",
        "exit_criteria": "Signed security evaluation.",
        "version": "1.0",
        "is_active": True,
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    created = SalesPlaybook.objects.get(tenant=tenant_a, name="Competitive Takeout Playbook")
    assert resp["Location"] == reverse("sales:sales_playbook_detail", kwargs={"pk": created.pk})
    assert created.owner == admin_user
    assert created.tenant == tenant_a
    assert created.motion_type == "competitive_displacement"

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).first()
    assert audit is not None
    assert audit.changes.get("name") == created.name


def test_salesenablement_playbook_create_invalid(client_a):
    """POST with missing required name re-renders form with errors."""
    url = reverse("sales:sales_playbook_create")
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_salesenablement_playbook_detail_and_cross_tenant(
    client_a, sales_playbook_a, sales_playbook_b
):
    """Detail view renders 200 OK for own tenant, 404 for cross tenant."""
    url_a = reverse("sales:sales_playbook_detail", kwargs={"pk": sales_playbook_a.pk})
    resp_a = client_a.get(url_a)
    assert resp_a.status_code == 200
    assert "playbook" in resp_a.context
    assert resp_a.context["playbook"].pk == sales_playbook_a.pk

    url_b = reverse("sales:sales_playbook_detail", kwargs={"pk": sales_playbook_b.pk})
    resp_b = client_a.get(url_b)
    assert resp_b.status_code == 404


def test_salesenablement_playbook_edit_get_and_post(client_a, tenant_a, sales_playbook_a):
    """GET and POST edit view updates playbook and logs audit."""
    url = reverse("sales:sales_playbook_edit", kwargs={"pk": sales_playbook_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    post_data = {
        "name": "Updated Playbook Name",
        "summary": "Updated summary text.",
        "motion_type": "expansion",
        "status": "under_review",
        "version": "1.1",
        "is_active": True,
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "sales:sales_playbook_detail", kwargs={"pk": sales_playbook_a.pk}
    )

    sales_playbook_a.refresh_from_db()
    assert sales_playbook_a.name == "Updated Playbook Name"
    assert sales_playbook_a.motion_type == "expansion"
    assert sales_playbook_a.status == "under_review"

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=sales_playbook_a.pk
    ).first()
    assert audit is not None


def test_salesenablement_playbook_edit_cross_tenant_404(client_a, sales_playbook_b):
    """Cross-tenant playbook edit returns 404."""
    url = reverse("sales:sales_playbook_edit", kwargs={"pk": sales_playbook_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_salesenablement_playbook_delete_post_only(client_a, sales_playbook_a):
    """GET delete returns 405 Method Not Allowed."""
    url = reverse("sales:sales_playbook_delete", kwargs={"pk": sales_playbook_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert SalesPlaybook.objects.filter(pk=sales_playbook_a.pk).exists()


def test_salesenablement_playbook_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Non-owner non-admin rep cannot delete; owner or admin can delete."""
    pb_admin = _salesenablement_playbook(tenant_a, owner=admin_user, name="Admin Owned Playbook")
    url_admin = reverse("sales:sales_playbook_delete", kwargs={"pk": pb_admin.pk})

    # Member rep attempts delete on admin-owned playbook
    resp_member = member_client.post(url_admin, follow=True)
    assert resp_member.status_code == 200
    assert SalesPlaybook.objects.filter(pk=pb_admin.pk).exists()
    messages = [m.message for m in get_messages(resp_member.wsgi_request)]
    assert any("Only the playbook owner or a tenant administrator" in m for m in messages)

    # Member rep deletes their own owned playbook
    pb_member = _salesenablement_playbook(tenant_a, owner=member_user, name="Member Owned Playbook")
    url_member = reverse("sales:sales_playbook_delete", kwargs={"pk": pb_member.pk})
    resp_owner = member_client.post(url_member)
    assert resp_owner.status_code == 302
    assert not SalesPlaybook.objects.filter(pk=pb_member.pk).exists()

    # Admin deletes pb_admin
    resp_admin = client_a.post(url_admin)
    assert resp_admin.status_code == 302
    assert not SalesPlaybook.objects.filter(pk=pb_admin.pk).exists()
    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=pb_admin.pk
    ).first()
    assert audit is not None


def test_salesenablement_playbook_delete_cross_tenant_404(client_a, sales_playbook_b):
    """Cross-tenant delete returns 404."""
    url = reverse("sales:sales_playbook_delete", kwargs={"pk": sales_playbook_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 3. SalesCertification CRUD
# ==============================================================================


def test_salesenablement_certification_list_filters_and_search(
    client_a, tenant_a, admin_user, member_user
):
    """Filter certifications by category, status, rep, and search q."""
    cert1 = _salesenablement_certification(
        tenant_a,
        rep=member_user,
        certified_by=admin_user,
        curriculum_name="Challenger Sales Accreditation",
        category="methodology",
        status="completed",
        score_percent=Decimal("92.00"),
    )
    cert2 = _salesenablement_certification(
        tenant_a,
        rep=admin_user,
        curriculum_name="New Rep Onboarding 101",
        category="onboarding",
        status="enrolled",
    )

    url = reverse("sales:sales_certification_list")

    # Search q
    resp_q = client_a.get(url, {"q": "Challenger"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["certifications"]) == 1
    assert resp_q.context["certifications"][0].pk == cert1.pk

    # Filter category
    resp_cat = client_a.get(url, {"category": "onboarding"})
    assert resp_cat.status_code == 200
    assert len(resp_cat.context["certifications"]) == 1
    assert resp_cat.context["certifications"][0].pk == cert2.pk

    # Filter status
    resp_stat = client_a.get(url, {"status": "completed"})
    assert resp_stat.status_code == 200
    assert len(resp_stat.context["certifications"]) == 1
    assert resp_stat.context["certifications"][0].pk == cert1.pk

    # Filter rep
    resp_rep = client_a.get(url, {"rep": str(member_user.pk)})
    assert resp_rep.status_code == 200
    assert len(resp_rep.context["certifications"]) == 1
    assert resp_rep.context["certifications"][0].pk == cert1.pk


def test_salesenablement_certification_list_tenant_isolation(
    client_a, client_b, sales_certification_a, sales_certification_b
):
    """Certifications are scoped to tenant."""
    url = reverse("sales:sales_certification_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["certifications"])
    assert sales_certification_a in items_a
    assert sales_certification_b not in items_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["certifications"])
    assert sales_certification_b in items_b
    assert sales_certification_a not in items_b


def test_salesenablement_certification_create_self_certify_prevented(
    member_client, tenant_a, member_user
):
    """Sales rep cannot self-certify or approve their own completed certification."""
    url = reverse("sales:sales_certification_create")
    post_data = {
        "curriculum_name": "MEDDPICC Certification",
        "category": "methodology",
        "rep": member_user.pk,
        "status": "completed",
        "score_percent": "88.00",
        "passing_score_percent": "80.00",
    }
    resp = member_client.post(url, data=post_data)
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert "status" in resp.context["form"].errors
    assert not SalesCertification.objects.filter(
        tenant=tenant_a, curriculum_name="MEDDPICC Certification"
    ).exists()


def test_salesenablement_certification_create_by_admin(
    client_a, tenant_a, member_user, admin_user
):
    """Admin can create completed certification; certified_by defaults to admin."""
    url = reverse("sales:sales_certification_create")
    post_data = {
        "curriculum_name": "Product Specialist Exam",
        "category": "product_certification",
        "rep": member_user.pk,
        "status": "completed",
        "score_percent": "95.00",
        "passing_score_percent": "80.00",
        "accreditation_notes": "Passed with distinction.",
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    created = SalesCertification.objects.get(tenant=tenant_a, curriculum_name="Product Specialist Exam")
    assert resp["Location"] == reverse(
        "sales:sales_certification_detail", kwargs={"pk": created.pk}
    )
    assert created.certified_by == admin_user
    assert created.status == "completed"
    assert created.rep == member_user

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).first()
    assert audit is not None


def test_salesenablement_certification_create_enrolled_by_rep(
    member_client, tenant_a, member_user
):
    """Rep can enroll self into a curriculum with status='enrolled'."""
    url = reverse("sales:sales_certification_create")
    post_data = {
        "curriculum_name": "Compliance & Security Onboarding",
        "category": "compliance",
        "rep": member_user.pk,
        "status": "enrolled",
        "passing_score_percent": "80.00",
    }
    resp = member_client.post(url, data=post_data)
    assert resp.status_code == 302
    created = SalesCertification.objects.get(
        tenant=tenant_a, curriculum_name="Compliance & Security Onboarding"
    )
    assert resp["Location"] == reverse(
        "sales:sales_certification_detail", kwargs={"pk": created.pk}
    )
    assert created.status == "enrolled"


def test_salesenablement_certification_detail_and_cross_tenant(
    client_a, sales_certification_a, sales_certification_b
):
    """Detail view renders for own tenant, 404 for cross tenant."""
    url_a = reverse("sales:sales_certification_detail", kwargs={"pk": sales_certification_a.pk})
    resp_a = client_a.get(url_a)
    assert resp_a.status_code == 200
    assert "certification" in resp_a.context

    url_b = reverse("sales:sales_certification_detail", kwargs={"pk": sales_certification_b.pk})
    resp_b = client_a.get(url_b)
    assert resp_b.status_code == 404


def test_salesenablement_certification_edit_self_certify_prevented(
    member_client, tenant_a, member_user
):
    """Rep cannot edit their enrolled certification into completed."""
    cert = _salesenablement_certification(
        tenant_a, rep=member_user, status="enrolled", curriculum_name="Self Enroll Test"
    )
    url = reverse("sales:sales_certification_edit", kwargs={"pk": cert.pk})
    post_data = {
        "curriculum_name": cert.curriculum_name,
        "category": cert.category,
        "rep": member_user.pk,
        "status": "completed",
        "score_percent": "85.00",
        "passing_score_percent": "80.00",
    }
    resp = member_client.post(url, data=post_data)
    assert resp.status_code == 200
    assert "status" in resp.context["form"].errors
    cert.refresh_from_db()
    assert cert.status == "enrolled"


def test_salesenablement_certification_edit_by_admin(
    client_a, tenant_a, sales_certification_a
):
    """Admin can edit certification, update score, and write audit log."""
    url = reverse("sales:sales_certification_edit", kwargs={"pk": sales_certification_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    post_data = {
        "curriculum_name": sales_certification_a.curriculum_name,
        "category": sales_certification_a.category,
        "rep": sales_certification_a.rep.pk,
        "status": "completed",
        "score_percent": "98.50",
        "passing_score_percent": "80.00",
        "accreditation_notes": "Perfect practical demonstration.",
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "sales:sales_certification_detail", kwargs={"pk": sales_certification_a.pk}
    )

    sales_certification_a.refresh_from_db()
    assert sales_certification_a.status == "completed"
    assert sales_certification_a.score_percent == Decimal("98.50")

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=sales_certification_a.pk
    ).first()
    assert audit is not None


def test_salesenablement_certification_edit_cross_tenant_404(client_a, sales_certification_b):
    """Cross-tenant certification edit returns 404."""
    url = reverse("sales:sales_certification_edit", kwargs={"pk": sales_certification_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_salesenablement_certification_delete_post_only(client_a, sales_certification_a):
    """GET delete returns 405 Method Not Allowed."""
    url = reverse("sales:sales_certification_delete", kwargs={"pk": sales_certification_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert SalesCertification.objects.filter(pk=sales_certification_a.pk).exists()


def test_salesenablement_certification_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Only certifying user or tenant admin can delete certification."""
    cert = _salesenablement_certification(
        tenant_a,
        rep=member_user,
        certified_by=admin_user,
        curriculum_name="Admin Certified Exam",
    )
    url = reverse("sales:sales_certification_delete", kwargs={"pk": cert.pk})

    # Rep (coachee/student) cannot delete
    resp_member = member_client.post(url, follow=True)
    assert resp_member.status_code == 200
    assert SalesCertification.objects.filter(pk=cert.pk).exists()
    messages = [m.message for m in get_messages(resp_member.wsgi_request)]
    assert any("Only the certifying manager or a tenant administrator" in m for m in messages)

    # Admin deletes
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not SalesCertification.objects.filter(pk=cert.pk).exists()
    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=cert.pk
    ).first()
    assert audit is not None


def test_salesenablement_certification_delete_cross_tenant_404(
    client_a, sales_certification_b
):
    """Cross-tenant delete returns 404."""
    url = reverse("sales:sales_certification_delete", kwargs={"pk": sales_certification_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 4. CoachingScorecard CRUD
# ==============================================================================


def test_salesenablement_scorecard_list_filters_and_search(
    client_a, tenant_a, admin_user, member_user
):
    """Filter scorecards by review_status, coach, coachee, and search q."""
    comm1 = CommunicationLog.objects.create(
        tenant=tenant_a, channel="call", subject="Discovery Call with Enterprise Prospect"
    )
    comm2 = CommunicationLog.objects.create(
        tenant=tenant_a, channel="call", subject="Technical Demo Session"
    )

    sc1 = _salesenablement_scorecard(
        tenant_a,
        coach=admin_user,
        coachee=member_user,
        communication_log=comm1,
        review_status="draft",
    )
    sc2 = _salesenablement_scorecard(
        tenant_a,
        coach=member_user,
        coachee=admin_user,
        communication_log=comm2,
        review_status="shared",
    )

    url = reverse("sales:coaching_scorecard_list")

    # Search q
    resp_q = client_a.get(url, {"q": "Technical Demo"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["scorecards"]) == 1
    assert resp_q.context["scorecards"][0].pk == sc2.pk

    # Filter review_status
    resp_stat = client_a.get(url, {"review_status": "draft"})
    assert resp_stat.status_code == 200
    assert len(resp_stat.context["scorecards"]) == 1
    assert resp_stat.context["scorecards"][0].pk == sc1.pk

    # Filter coach
    resp_coach = client_a.get(url, {"coach": str(admin_user.pk)})
    assert resp_coach.status_code == 200
    assert len(resp_coach.context["scorecards"]) == 1
    assert resp_coach.context["scorecards"][0].pk == sc1.pk

    # Filter coachee
    resp_coachee = client_a.get(url, {"coachee": str(admin_user.pk)})
    assert resp_coachee.status_code == 200
    assert len(resp_coachee.context["scorecards"]) == 1
    assert resp_coachee.context["scorecards"][0].pk == sc2.pk


def test_salesenablement_scorecard_list_tenant_isolation(
    client_a, client_b, coaching_scorecard_a, coaching_scorecard_b
):
    """Scorecards are scoped to tenant."""
    url = reverse("sales:coaching_scorecard_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["scorecards"])
    assert coaching_scorecard_a in items_a
    assert coaching_scorecard_b not in items_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["scorecards"])
    assert coaching_scorecard_b in items_b
    assert coaching_scorecard_a not in items_b


def test_salesenablement_scorecard_create_get_prepopulation(client_a, tenant_a):
    """GET create view prepopulates communication_log and initializes default fields."""
    comm = CommunicationLog.objects.create(
        tenant=tenant_a, channel="call", subject="Prospecting Call Prepop"
    )
    url = reverse("sales:coaching_scorecard_create")
    resp = client_a.get(url, {"communication_log": str(comm.pk)})
    assert resp.status_code == 200
    form = resp.context["form"]
    assert form.initial.get("communication_log") == comm.pk
    assert form.fields["call_sentiment"].initial == "neutral"
    assert form.fields["evaluated_on"].initial == timezone.now().date()
    assert resp.context["is_edit"] is False


def test_salesenablement_scorecard_create_post_success(
    client_a, tenant_a, admin_user, member_user
):
    """POST creates scorecard with default review_status='draft' and coach=request.user."""
    comm = CommunicationLog.objects.create(
        tenant=tenant_a, channel="call", subject="Discovery Coaching Session"
    )
    url = reverse("sales:coaching_scorecard_create")
    post_data = {
        "communication_log": comm.pk,
        "coachee": member_user.pk,
        "discovery_score": 4,
        "value_prop_score": 4,
        "objection_handling_score": 4,
        "next_steps_score": 4,
        "talk_listen_ratio_percent": 42,
        "call_sentiment": "positive",
        "transcript_summary": "Thorough business diagnosis.",
        "key_strengths": "Crisp objection answering.",
        "areas_for_improvement": "More time on ROI quantify.",
        "action_items": "Review playbook objection script.",
        "evaluated_on": timezone.now().date().isoformat(),
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    created = CoachingScorecard.objects.get(tenant=tenant_a, communication_log=comm)
    assert resp["Location"] == reverse(
        "sales:coaching_scorecard_detail", kwargs={"pk": created.pk}
    )
    assert created.coach == admin_user
    assert created.coachee == member_user
    assert created.review_status == "draft"
    assert created.overall_score == 80  # (4+4+4+4)/20 * 100 = 80

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).first()
    assert audit is not None


def test_salesenablement_scorecard_create_invalid(client_a):
    """POST with missing required fields returns 200 with form errors."""
    url = reverse("sales:coaching_scorecard_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_salesenablement_scorecard_detail_and_cross_tenant(
    client_a, coaching_scorecard_a, coaching_scorecard_b
):
    """Detail view renders for own tenant, 404 for cross tenant."""
    url_a = reverse("sales:coaching_scorecard_detail", kwargs={"pk": coaching_scorecard_a.pk})
    resp_a = client_a.get(url_a)
    assert resp_a.status_code == 200
    assert "scorecard" in resp_a.context

    url_b = reverse("sales:coaching_scorecard_detail", kwargs={"pk": coaching_scorecard_b.pk})
    resp_b = client_a.get(url_b)
    assert resp_b.status_code == 404


def test_salesenablement_scorecard_edit_get_and_post(
    client_a, tenant_a, coaching_scorecard_a
):
    """GET and POST edit view updates rubric scores, recomputes overall_score and logs audit."""
    url = reverse("sales:coaching_scorecard_edit", kwargs={"pk": coaching_scorecard_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    post_data = {
        "communication_log": coaching_scorecard_a.communication_log.pk,
        "coachee": coaching_scorecard_a.coachee.pk,
        "discovery_score": 5,
        "value_prop_score": 5,
        "objection_handling_score": 5,
        "next_steps_score": 5,
        "talk_listen_ratio_percent": 45,
        "call_sentiment": "positive",
        "transcript_summary": "Top-tier demonstration.",
        "key_strengths": "Exemplary pitch framing.",
        "areas_for_improvement": "None.",
        "action_items": "Share call recording with team.",
        "evaluated_on": coaching_scorecard_a.evaluated_on.isoformat(),
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "sales:coaching_scorecard_detail", kwargs={"pk": coaching_scorecard_a.pk}
    )

    coaching_scorecard_a.refresh_from_db()
    assert coaching_scorecard_a.discovery_score == 5
    assert coaching_scorecard_a.overall_score == 100

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=coaching_scorecard_a.pk
    ).first()
    assert audit is not None


def test_salesenablement_scorecard_edit_cross_tenant_404(client_a, coaching_scorecard_b):
    """Cross-tenant scorecard edit returns 404."""
    url = reverse("sales:coaching_scorecard_edit", kwargs={"pk": coaching_scorecard_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_salesenablement_scorecard_delete_post_only(client_a, coaching_scorecard_a):
    """GET delete returns 405 Method Not Allowed."""
    url = reverse("sales:coaching_scorecard_delete", kwargs={"pk": coaching_scorecard_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert CoachingScorecard.objects.filter(pk=coaching_scorecard_a.pk).exists()


def test_salesenablement_scorecard_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Only evaluating coach or tenant admin can delete scorecard."""
    comm = CommunicationLog.objects.create(tenant=tenant_a, channel="call", subject="Delete Perm Call")
    sc = _salesenablement_scorecard(
        tenant_a, coach=admin_user, coachee=member_user, communication_log=comm
    )
    url = reverse("sales:coaching_scorecard_delete", kwargs={"pk": sc.pk})

    # Coachee cannot delete
    resp_member = member_client.post(url, follow=True)
    assert resp_member.status_code == 200
    assert CoachingScorecard.objects.filter(pk=sc.pk).exists()
    messages = [m.message for m in get_messages(resp_member.wsgi_request)]
    assert any("Only the evaluating coach or a tenant administrator" in m for m in messages)

    # Admin coach deletes
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not CoachingScorecard.objects.filter(pk=sc.pk).exists()
    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=sc.pk
    ).first()
    assert audit is not None


def test_salesenablement_scorecard_delete_cross_tenant_404(client_a, coaching_scorecard_b):
    """Cross-tenant delete returns 404."""
    url = reverse("sales:coaching_scorecard_delete", kwargs={"pk": coaching_scorecard_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 5. Enablement Boards (5 surfaces)
# ==============================================================================


def test_salesenablement_content_hub_board(client_a, tenant_a, admin_user):
    """sales_enablement_content_hub renders 200 OK and validates all required context keys."""
    # Seed various content
    _salesenablement_content(
        tenant_a, author=admin_user, content_type="battle_card", is_client_facing=True
    )
    _salesenablement_content(
        tenant_a, author=admin_user, content_type="battle_card", is_client_facing=False
    )
    _salesenablement_content(
        tenant_a, author=admin_user, content_type="pitch_deck", is_client_facing=True
    )

    url = reverse("sales:enablement_content_hub")
    resp = client_a.get(url)
    assert resp.status_code == 200

    ctx = resp.context
    assert ctx["total_contents"] == 3
    assert ctx["total_battlecards"] == 2
    assert ctx["total_client_facing"] == 2
    assert len(ctx["battlecards"]) == 2
    assert len(ctx["decks"]) == 1
    assert ctx["sheets"] == []
    assert "recent_contents" in ctx
    assert "popular_contents" in ctx
    assert "content_type_choices" in ctx
    assert "stage_choices" in ctx
    assert "persona_choices" in ctx


def test_salesenablement_playbook_board(client_a, tenant_a, admin_user):
    """sales_playbook_board renders 200 OK with motion breakdown and published counts."""
    _salesenablement_playbook(
        tenant_a, owner=admin_user, motion_type="new_business", status="published"
    )
    _salesenablement_playbook(
        tenant_a, owner=admin_user, motion_type="expansion", status="draft"
    )

    url = reverse("sales:sales_playbook_board")
    resp = client_a.get(url)
    assert resp.status_code == 200

    ctx = resp.context
    assert ctx["total_playbooks"] == 2
    published_count = ctx.get("published_count", ctx.get("total_published"))
    assert published_count == 1
    assert "playbooks_by_motion" in ctx

    motions = {m["code"]: m for m in ctx["playbooks_by_motion"]}
    assert "new_business" in motions
    assert motions["new_business"]["count"] == 1
    assert "expansion" in motions
    assert motions["expansion"]["count"] == 1


def test_salesenablement_readiness_board(client_a, tenant_a, admin_user, member_user):
    """sales_readiness_board renders 200 OK with matrix, completion stats and expiring counts."""
    today = timezone.now().date()
    # Expiring soon (within 30 days)
    _salesenablement_certification(
        tenant_a,
        rep=member_user,
        status="completed",
        score_percent=Decimal("88.00"),
        certified_by=admin_user,
        certified_at=today,
        expires_at=today + timedelta(days=12),
    )
    # In-progress enrolled
    _salesenablement_certification(
        tenant_a,
        rep=member_user,
        status="enrolled",
    )

    url = reverse("sales:sales_readiness_board")
    resp = client_a.get(url)
    assert resp.status_code == 200

    ctx = resp.context
    assert ctx["total_certifications"] == 2
    assert ctx["completed_count"] == 1
    assert ctx["in_progress_count"] == 1
    assert ctx["completion_rate"] == 50
    assert ctx["expiring_soon_count"] == 1
    assert "rep_readiness_matrix" in ctx
    assert "rep_matrix" in ctx
    assert "certifications_summary" in ctx

    summary = ctx["certifications_summary"]
    assert summary["total"] == 2
    assert summary["completed"] == 1
    assert summary["in_progress"] == 1
    assert summary["expiring_soon"] == 1


def test_salesenablement_coaching_workbench_board(client_a, tenant_a, admin_user, member_user):
    """sales_coaching_workbench renders 200 OK with rubrics, averages and unreviewed logs."""
    _salesenablement_scorecard(
        tenant_a,
        coach=admin_user,
        coachee=member_user,
        discovery_score=4,
        value_prop_score=4,
        objection_handling_score=4,
        next_steps_score=4,
        talk_listen_ratio_percent=44,
    )
    client_party = Party.objects.create(tenant=tenant_a, name="Acme Prospect", kind="organization")
    unreviewed = CommunicationLog.objects.create(
        tenant=tenant_a,
        channel="call",
        subject="Unreviewed Prospect Conversation",
        owner=admin_user,
        party=client_party,
    )

    url = reverse("sales:sales_coaching_workbench")
    resp = client_a.get(url)
    assert resp.status_code == 200

    ctx = resp.context
    assert ctx["total_evaluations"] == 1
    assert ctx["avg_overall_score"] == 80.0
    assert ctx["talk_ratio_avg"] == 44.0
    assert ctx["avg_talk_ratio"] == 44.0
    assert "recent_scorecards" in ctx
    assert "unreviewed_logs" in ctx
    assert unreviewed in ctx["unreviewed_logs"]

    dist = ctx["strengths_distribution"]
    assert dist["discovery"] == 4.0
    assert dist["value_prop"] == 4.0
    assert dist["objection_handling"] == 4.0
    assert dist["next_steps"] == 4.0


def test_salesenablement_competitive_intelligence_library_board(
    client_a, tenant_a, admin_user
):
    """sales_competitive_intelligence_library renders 200 OK with competitor battlecard mapping."""
    comp1 = _salesenablement_create_competitor(tenant_a, name="Omni Competitor")
    comp2 = _salesenablement_create_competitor(tenant_a, name="Beta Competitor")
    _salesenablement_content(
        tenant_a,
        author=admin_user,
        content_type="battle_card",
        competitor=comp1,
        is_active=True,
    )

    url = reverse("sales:sales_competitive_intelligence_library")
    resp = client_a.get(url)
    assert resp.status_code == 200

    ctx = resp.context
    assert ctx["total_competitors"] >= 2
    assert "competitor_data" in ctx
    assert "competitors_with_battlecards" in ctx
    assert "win_loss_outcomes" in ctx

    entry = [d for d in ctx["competitor_data"] if d["profile"].pk == comp1.pk][0]
    assert len(entry["battlecards"]) == 1
    assert entry["profile"] == comp1


# ==============================================================================
# 6. Custom Actions
# ==============================================================================


def test_salesenablement_content_share_action(client_a, tenant_a, admin_user):
    """POST increments share_count and redirects; GET returns 405."""
    content = _salesenablement_content(
        tenant_a, author=admin_user, is_active=True, share_count=0
    )
    url = reverse("sales:enablement_content_share", kwargs={"pk": content.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    content.refresh_from_db()
    assert content.share_count == 0

    # First POST increments share_count to 1
    resp1 = client_a.post(url)
    assert resp1.status_code == 302
    assert resp1["Location"] == reverse(
        "sales:enablement_content_detail", kwargs={"pk": content.pk}
    )
    content.refresh_from_db()
    assert content.share_count == 1

    # Second POST increments share_count to 2
    resp2 = client_a.post(url)
    assert resp2.status_code == 302
    content.refresh_from_db()
    assert content.share_count == 2


def test_salesenablement_content_share_inactive_rejected(client_a, tenant_a, admin_user):
    """Cannot share inactive enablement content."""
    content = _salesenablement_content(
        tenant_a, author=admin_user, is_active=False, share_count=0
    )
    url = reverse("sales:enablement_content_share", kwargs={"pk": content.pk})

    resp = client_a.post(url, follow=True)
    assert resp.status_code == 200
    content.refresh_from_db()
    assert content.share_count == 0
    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("inactive" in m.lower() for m in messages)


def test_salesenablement_content_share_expired_rejected(client_a, tenant_a, admin_user):
    """Cannot share expired enablement content."""
    yesterday = timezone.now().date() - timedelta(days=1)
    content = _salesenablement_content(
        tenant_a,
        author=admin_user,
        is_active=True,
        expires_on=yesterday,
        share_count=0,
    )
    url = reverse("sales:enablement_content_share", kwargs={"pk": content.pk})

    resp = client_a.post(url, follow=True)
    assert resp.status_code == 200
    content.refresh_from_db()
    assert content.share_count == 0
    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("expired" in m.lower() for m in messages)


def test_salesenablement_content_share_cross_tenant_404(client_a, enablement_content_b):
    """Cross-tenant share request returns 404."""
    url = reverse("sales:enablement_content_share", kwargs={"pk": enablement_content_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_salesenablement_scorecard_acknowledge_action_coachee(
    member_client, tenant_a, admin_user, member_user
):
    """Coachee can acknowledge their scorecard; status transitions to 'acknowledged'."""
    sc = _salesenablement_scorecard(
        tenant_a, coach=admin_user, coachee=member_user, review_status="draft"
    )
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": sc.pk})

    # GET returns 405
    resp_get = member_client.get(url)
    assert resp_get.status_code == 405
    sc.refresh_from_db()
    assert sc.review_status == "draft"

    # POST succeeds
    resp_post = member_client.post(url)
    assert resp_post.status_code == 302
    assert resp_post["Location"] == reverse(
        "sales:coaching_scorecard_detail", kwargs={"pk": sc.pk}
    )
    sc.refresh_from_db()
    assert sc.review_status == "acknowledged"

    audit = AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=sc.pk
    ).order_by("-id").first()
    assert audit is not None
    assert audit.changes.get("review_status") == "acknowledged"


def test_salesenablement_scorecard_acknowledge_action_admin(client_a, tenant_a, member_user):
    """Tenant admin can acknowledge any scorecard."""
    other_rep = _salesenablement_create_user(tenant_a, "peer_rep", is_admin=False)
    sc = _salesenablement_scorecard(
        tenant_a, coach=other_rep, coachee=member_user, review_status="draft"
    )
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": sc.pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    sc.refresh_from_db()
    assert sc.review_status == "acknowledged"


def test_salesenablement_scorecard_acknowledge_unauthorized_user(
    tenant_a, admin_user, member_user
):
    """Unauthorized user (neither coachee nor admin) cannot acknowledge scorecard."""
    other_rep = _salesenablement_create_user(tenant_a, "unauthorized_rep", is_admin=False)
    other_client = Client()
    other_client.force_login(other_rep)

    sc = _salesenablement_scorecard(
        tenant_a, coach=admin_user, coachee=member_user, review_status="draft"
    )
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": sc.pk})

    resp = other_client.post(url, follow=True)
    assert resp.status_code == 200
    sc.refresh_from_db()
    assert sc.review_status == "draft"
    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("Only the coachee or a tenant administrator" in m for m in messages)


def test_salesenablement_scorecard_acknowledge_cross_tenant_404(
    client_a, coaching_scorecard_b
):
    """Cross-tenant acknowledge returns 404."""
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": coaching_scorecard_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 7. Robustness & Multi-Page Pagination
# ==============================================================================


def test_salesenablement_junk_query_params_return_200(client_a, tenant_a, admin_user):
    """Junk GET query parameters on all 4 list views return 200 cleanly without 500 error."""
    _salesenablement_content(tenant_a, author=admin_user)
    _salesenablement_playbook(tenant_a, owner=admin_user)
    _salesenablement_certification(tenant_a, rep=admin_user)
    _salesenablement_scorecard(tenant_a, coach=admin_user, coachee=admin_user)

    # 1. Content list junk params
    resp1 = client_a.get(
        reverse("sales:enablement_content_list"),
        {
            "competitor": "abc",
            "page": "999",
            "content_type": "nonexistent_type",
            "target_stage": "invalid_stage",
            "target_persona": "invalid_persona",
            "q": "!@#$%^&*()",
        },
    )
    assert resp1.status_code == 200

    # 2. Playbook list junk params
    resp2 = client_a.get(
        reverse("sales:sales_playbook_list"),
        {
            "pipeline": "not_a_pipeline_id",
            "page": "-99",
            "motion_type": "invalid_motion",
            "status": "invalid_status",
            "q": "???",
        },
    )
    assert resp2.status_code == 200

    # 3. Certification list junk params
    resp3 = client_a.get(
        reverse("sales:sales_certification_list"),
        {
            "rep": "junk_rep_id",
            "page": "invalid_page",
            "category": "junk_category",
            "status": "junk_status",
            "q": "<script>alert(1)</script>",
        },
    )
    assert resp3.status_code == 200

    # 4. Scorecard list junk params
    resp4 = client_a.get(
        reverse("sales:coaching_scorecard_list"),
        {
            "coach": "invalid_coach",
            "coachee": "invalid_coachee",
            "page": "99999",
            "review_status": "bogus_status",
            "q": "///",
        },
    )
    assert resp4.status_code == 200


def test_salesenablement_content_pagination_multipage(client_a, tenant_a, admin_user):
    """EnablementContent list paginates cleanly across multiple pages."""
    for i in range(16):
        _salesenablement_content(tenant_a, author=admin_user, title=f"Pagination Content {i:02d}")

    url = reverse("sales:enablement_content_list")

    # Page 1
    resp1 = client_a.get(url, {"page": "1"})
    assert resp1.status_code == 200
    page1 = resp1.context["contents"]
    assert len(page1) == 15
    assert page1.has_next()
    assert not page1.has_previous()

    # Page 2
    resp2 = client_a.get(url, {"page": "2"})
    assert resp2.status_code == 200
    page2 = resp2.context["contents"]
    assert len(page2) == 1
    assert not page2.has_next()
    assert page2.has_previous()

    # Out of range page defaults to last page
    resp_oor = client_a.get(url, {"page": "999"})
    assert resp_oor.status_code == 200
    assert resp_oor.context["contents"].number == 2


def test_salesenablement_playbook_pagination_multipage(client_a, tenant_a, admin_user):
    """SalesPlaybook list paginates cleanly across multiple pages."""
    for i in range(16):
        _salesenablement_playbook(tenant_a, owner=admin_user, name=f"Pagination Playbook {i:02d}")

    url = reverse("sales:sales_playbook_list")

    # Page 1
    resp1 = client_a.get(url, {"page": "1"})
    assert resp1.status_code == 200
    page1 = resp1.context["playbooks"]
    assert len(page1) == 15
    assert page1.has_next()

    # Page 2
    resp2 = client_a.get(url, {"page": "2"})
    assert resp2.status_code == 200
    page2 = resp2.context["playbooks"]
    assert len(page2) == 1


def test_salesenablement_certification_pagination_multipage(
    client_a, tenant_a, admin_user, member_user
):
    """SalesCertification list paginates cleanly across multiple pages."""
    for i in range(16):
        _salesenablement_certification(
            tenant_a, rep=member_user, curriculum_name=f"Pagination Cert {i:02d}"
        )

    url = reverse("sales:sales_certification_list")

    # Page 1
    resp1 = client_a.get(url, {"page": "1"})
    assert resp1.status_code == 200
    page1 = resp1.context["certifications"]
    assert len(page1) == 15
    assert page1.has_next()

    # Page 2
    resp2 = client_a.get(url, {"page": "2"})
    assert resp2.status_code == 200
    page2 = resp2.context["certifications"]
    assert len(page2) == 1


def test_salesenablement_scorecard_pagination_multipage(
    client_a, tenant_a, admin_user, member_user
):
    """CoachingScorecard list paginates cleanly across multiple pages."""
    for i in range(16):
        _salesenablement_scorecard(tenant_a, coach=admin_user, coachee=member_user)

    url = reverse("sales:coaching_scorecard_list")

    # Page 1
    resp1 = client_a.get(url, {"page": "1"})
    assert resp1.status_code == 200
    page1 = resp1.context["scorecards"]
    assert len(page1) == 15
    assert page1.has_next()

    # Page 2
    resp2 = client_a.get(url, {"page": "2"})
    assert resp2.status_code == 200
    page2 = resp2.context["scorecards"]
    assert len(page2) == 1
