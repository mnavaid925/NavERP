"""Sales 8.9 — Sales Enablement Security Test Suite.

Covers:
1. Authentication & @login_required:
   - All 4 models (list, create, detail, edit, delete), all 5 boards, and custom action routes
     redirect unauthenticated callers to login.
2. HTTP Method Restrictions:
   - GET requests to all 4 delete views return 405 Method Not Allowed.
   - GET requests to custom actions (share, acknowledge) return 405 Method Not Allowed.
3. Multi-Tenant IDOR Isolation:
   - Tenant A client requesting Tenant B records for detail, edit, delete, share, and acknowledge
     strictly returns 404 Not Found across all 4 models.
4. Object-Level & Role Authorization:
   - `coaching_scorecard_acknowledge`: non-coachee / non-admin user gets denied (403/302).
     Coachee or tenant admin succeeds.
   - Delete endpoints: standard user who is not owner/author and not tenant admin gets denied.
     Tenant admin or author succeeds.
   - `sales_certification_create`: unprivileged rep cannot self-certify as completed.
5. CSRF Defenses:
   - Verifies forms and state-changing POST routes require CSRF tokens (403 Forbidden).
6. Cross-Tenant Foreign Key Injection:
   - Injecting foreign tenant PKs into forms fails validation and does not leak or write across tenants.
"""
from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Document, Party
from apps.crm.models.ActivityManagement.CommunicationLogs import CommunicationLog
from apps.sales.forms.SalesEnablement.CoachingScorecards import CoachingScorecardForm
from apps.sales.forms.SalesEnablement.EnablementContents import EnablementContentForm
from apps.sales.forms.SalesEnablement.SalesCertifications import SalesCertificationForm
from apps.sales.forms.SalesEnablement.SalesPlaybooks import SalesPlaybookForm
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import CompetitorProfile
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline, PipelineStage
from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import ActivityLog
from apps.sales.models.SalesEnablement.CoachingScorecards import CoachingScorecard
from apps.sales.models.SalesEnablement.EnablementContents import EnablementContent
from apps.sales.models.SalesEnablement.SalesCertifications import SalesCertification
from apps.sales.models.SalesEnablement.SalesPlaybooks import SalesPlaybook
from apps.sales.tests.conftest import (
    _salesenablement_certification,
    _salesenablement_competitor,
    _salesenablement_content,
    _salesenablement_document,
    _salesenablement_playbook,
    _salesenablement_scorecard,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_salesenablement_*)
# ==============================================================================


def _salesenablement_create_user(tenant, username, is_admin=False):
    """Helper to create a tenant user with distinct role/credentials."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@{tenant.slug}.example.com",
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
    )


def _salesenablement_csrf_client(user):
    """Create a test client with CSRF protection enabled and user logged in."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    return client


def _salesenablement_create_pipeline_and_stage(tenant, name="Standard Pipeline"):
    """Helper to create a pipeline and associated pipeline stage."""
    pipeline = Pipeline.objects.create(
        tenant=tenant,
        name=name,
        is_active=True,
    )
    stage = PipelineStage.objects.create(
        tenant=tenant,
        pipeline=pipeline,
        name=f"{name} Discovery",
        sequence=10,
        crm_stage_key="qualification",
        is_active=True,
    )
    return pipeline, stage


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


def _salesenablement_create_training_course(tenant, title="Security Curriculum"):
    """Helper to create an HRM TrainingCourse if the model is available."""
    TrainingCourse = apps.get_model("hrm", "TrainingCourse", require_ready=False)
    if TrainingCourse:
        return TrainingCourse.objects.create(
            tenant=tenant,
            title=title,
            category="sales",
            is_active=True,
        )
    return None


def _salesenablement_create_activity_log(tenant, communication_log, owner):
    """Helper to create an ActivityLog linked to a communication log."""
    from apps.sales.models.SalesActivityTaskManagement.ActivityTypes import ActivityType

    activity_type, _ = ActivityType.objects.get_or_create(
        tenant=tenant,
        name="Sales Call",
        defaults={"kind": "call"},
    )
    return ActivityLog.objects.create(
        tenant=tenant,
        communication_log=communication_log,
        activity_type=activity_type,
        owner=owner,
    )


# ==============================================================================
# 1. Authentication & @login_required
# ==============================================================================


def test_salesenablement_auth_content_routes_redirect_unauthenticated(
    client, enablement_content_a
):
    """Unauthenticated calls to EnablementContent CRUD and share routes redirect to login."""
    routes = [
        ("GET", reverse("sales:enablement_content_list"), {}),
        ("GET", reverse("sales:enablement_content_create"), {}),
        ("POST", reverse("sales:enablement_content_create"), {"title": "Anon Content"}),
        ("GET", reverse("sales:enablement_content_detail", kwargs={"pk": enablement_content_a.pk}), {}),
        ("GET", reverse("sales:enablement_content_edit", kwargs={"pk": enablement_content_a.pk}), {}),
        ("POST", reverse("sales:enablement_content_edit", kwargs={"pk": enablement_content_a.pk}), {"title": "Anon Edit"}),
        ("POST", reverse("sales:enablement_content_delete", kwargs={"pk": enablement_content_a.pk}), {}),
        ("POST", reverse("sales:enablement_content_share", kwargs={"pk": enablement_content_a.pk}), {}),
    ]
    for method, url, data in routes:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, data)
        assert resp.status_code == 302, f"Failed on {method} {url}"
        assert "/login" in resp["Location"], f"Expected /login redirect for {url}"


def test_salesenablement_auth_playbook_routes_redirect_unauthenticated(
    client, sales_playbook_a
):
    """Unauthenticated calls to SalesPlaybook CRUD routes redirect to login."""
    routes = [
        ("GET", reverse("sales:sales_playbook_list"), {}),
        ("GET", reverse("sales:sales_playbook_create"), {}),
        ("POST", reverse("sales:sales_playbook_create"), {"name": "Anon Playbook"}),
        ("GET", reverse("sales:sales_playbook_detail", kwargs={"pk": sales_playbook_a.pk}), {}),
        ("GET", reverse("sales:sales_playbook_edit", kwargs={"pk": sales_playbook_a.pk}), {}),
        ("POST", reverse("sales:sales_playbook_edit", kwargs={"pk": sales_playbook_a.pk}), {"name": "Anon Edit"}),
        ("POST", reverse("sales:sales_playbook_delete", kwargs={"pk": sales_playbook_a.pk}), {}),
    ]
    for method, url, data in routes:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, data)
        assert resp.status_code == 302, f"Failed on {method} {url}"
        assert "/login" in resp["Location"], f"Expected /login redirect for {url}"


def test_salesenablement_auth_certification_routes_redirect_unauthenticated(
    client, sales_certification_a
):
    """Unauthenticated calls to SalesCertification CRUD routes redirect to login."""
    routes = [
        ("GET", reverse("sales:sales_certification_list"), {}),
        ("GET", reverse("sales:sales_certification_create"), {}),
        ("POST", reverse("sales:sales_certification_create"), {"curriculum_name": "Anon Cert"}),
        ("GET", reverse("sales:sales_certification_detail", kwargs={"pk": sales_certification_a.pk}), {}),
        ("GET", reverse("sales:sales_certification_edit", kwargs={"pk": sales_certification_a.pk}), {}),
        ("POST", reverse("sales:sales_certification_edit", kwargs={"pk": sales_certification_a.pk}), {"curriculum_name": "Anon Edit"}),
        ("POST", reverse("sales:sales_certification_delete", kwargs={"pk": sales_certification_a.pk}), {}),
    ]
    for method, url, data in routes:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, data)
        assert resp.status_code == 302, f"Failed on {method} {url}"
        assert "/login" in resp["Location"], f"Expected /login redirect for {url}"


def test_salesenablement_auth_scorecard_routes_redirect_unauthenticated(
    client, coaching_scorecard_a
):
    """Unauthenticated calls to CoachingScorecard CRUD and acknowledge routes redirect to login."""
    routes = [
        ("GET", reverse("sales:coaching_scorecard_list"), {}),
        ("GET", reverse("sales:coaching_scorecard_create"), {}),
        ("POST", reverse("sales:coaching_scorecard_create"), {"action_items": "Anon Notes"}),
        ("GET", reverse("sales:coaching_scorecard_detail", kwargs={"pk": coaching_scorecard_a.pk}), {}),
        ("GET", reverse("sales:coaching_scorecard_edit", kwargs={"pk": coaching_scorecard_a.pk}), {}),
        ("POST", reverse("sales:coaching_scorecard_edit", kwargs={"pk": coaching_scorecard_a.pk}), {"action_items": "Anon Edit"}),
        ("POST", reverse("sales:coaching_scorecard_delete", kwargs={"pk": coaching_scorecard_a.pk}), {}),
        ("POST", reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": coaching_scorecard_a.pk}), {}),
    ]
    for method, url, data in routes:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, data)
        assert resp.status_code == 302, f"Failed on {method} {url}"
        assert "/login" in resp["Location"], f"Expected /login redirect for {url}"


def test_salesenablement_auth_all_boards_redirect_unauthenticated(client):
    """All 5 enablement boards redirect unauthenticated visitors to login."""
    board_urls = [
        reverse("sales:enablement_content_hub"),
        reverse("sales:sales_playbook_board"),
        reverse("sales:sales_readiness_board"),
        reverse("sales:sales_coaching_workbench"),
        reverse("sales:sales_competitive_intelligence_library"),
    ]
    for url in board_urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect on board {url}"
        assert "/login" in resp["Location"], f"Expected /login redirect for board {url}"


# ==============================================================================
# 2. HTTP Method Restrictions
# ==============================================================================


def test_salesenablement_method_not_allowed_on_delete_endpoints(
    client_a,
    enablement_content_a,
    sales_playbook_a,
    sales_certification_a,
    coaching_scorecard_a,
):
    """GET requests to all 4 delete views strictly return 405 Method Not Allowed."""
    delete_urls = [
        reverse("sales:enablement_content_delete", kwargs={"pk": enablement_content_a.pk}),
        reverse("sales:sales_playbook_delete", kwargs={"pk": sales_playbook_a.pk}),
        reverse("sales:sales_certification_delete", kwargs={"pk": sales_certification_a.pk}),
        reverse("sales:coaching_scorecard_delete", kwargs={"pk": coaching_scorecard_a.pk}),
    ]
    for url in delete_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {resp.status_code}"


def test_salesenablement_method_not_allowed_on_custom_actions(
    client_a, enablement_content_a, coaching_scorecard_a
):
    """GET requests to custom actions (share, acknowledge) return 405 Method Not Allowed."""
    action_urls = [
        reverse("sales:enablement_content_share", kwargs={"pk": enablement_content_a.pk}),
        reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": coaching_scorecard_a.pk}),
    ]
    for url in action_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {resp.status_code}"


# ==============================================================================
# 3. Multi-Tenant IDOR Isolation
# ==============================================================================


def test_salesenablement_idor_detail_views_return_404_cross_tenant(
    client_a,
    client_b,
    enablement_content_a,
    enablement_content_b,
    sales_playbook_a,
    sales_playbook_b,
    sales_certification_a,
    sales_certification_b,
    coaching_scorecard_a,
    coaching_scorecard_b,
):
    """Tenant A client requesting Tenant B records for detail strictly returns 404, and vice versa."""
    # Tenant A requesting Tenant B records
    assert client_a.get(reverse("sales:enablement_content_detail", kwargs={"pk": enablement_content_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:sales_playbook_detail", kwargs={"pk": sales_playbook_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:sales_certification_detail", kwargs={"pk": sales_certification_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:coaching_scorecard_detail", kwargs={"pk": coaching_scorecard_b.pk})).status_code == 404

    # Tenant B requesting Tenant A records
    assert client_b.get(reverse("sales:enablement_content_detail", kwargs={"pk": enablement_content_a.pk})).status_code == 404
    assert client_b.get(reverse("sales:sales_playbook_detail", kwargs={"pk": sales_playbook_a.pk})).status_code == 404
    assert client_b.get(reverse("sales:sales_certification_detail", kwargs={"pk": sales_certification_a.pk})).status_code == 404
    assert client_b.get(reverse("sales:coaching_scorecard_detail", kwargs={"pk": coaching_scorecard_a.pk})).status_code == 404


def test_salesenablement_idor_edit_views_return_404_cross_tenant(
    client_a,
    enablement_content_b,
    sales_playbook_b,
    sales_certification_b,
    coaching_scorecard_b,
):
    """Tenant A requesting Tenant B records for edit (GET and POST) strictly returns 404."""
    # EnablementContent
    orig_title = enablement_content_b.title
    assert client_a.get(reverse("sales:enablement_content_edit", kwargs={"pk": enablement_content_b.pk})).status_code == 404
    resp_post = client_a.post(
        reverse("sales:enablement_content_edit", kwargs={"pk": enablement_content_b.pk}),
        {"title": "Compromised Title"},
    )
    assert resp_post.status_code == 404
    enablement_content_b.refresh_from_db()
    assert enablement_content_b.title == orig_title

    # SalesPlaybook
    orig_pb_name = sales_playbook_b.name
    assert client_a.get(reverse("sales:sales_playbook_edit", kwargs={"pk": sales_playbook_b.pk})).status_code == 404
    assert client_a.post(
        reverse("sales:sales_playbook_edit", kwargs={"pk": sales_playbook_b.pk}),
        {"name": "Compromised Playbook"},
    ).status_code == 404
    sales_playbook_b.refresh_from_db()
    assert sales_playbook_b.name == orig_pb_name

    # SalesCertification
    orig_cert_name = sales_certification_b.curriculum_name
    assert client_a.get(reverse("sales:sales_certification_edit", kwargs={"pk": sales_certification_b.pk})).status_code == 404
    assert client_a.post(
        reverse("sales:sales_certification_edit", kwargs={"pk": sales_certification_b.pk}),
        {"curriculum_name": "Compromised Cert"},
    ).status_code == 404
    sales_certification_b.refresh_from_db()
    assert sales_certification_b.curriculum_name == orig_cert_name

    # CoachingScorecard
    orig_items = coaching_scorecard_b.action_items
    assert client_a.get(reverse("sales:coaching_scorecard_edit", kwargs={"pk": coaching_scorecard_b.pk})).status_code == 404
    assert client_a.post(
        reverse("sales:coaching_scorecard_edit", kwargs={"pk": coaching_scorecard_b.pk}),
        {"action_items": "Compromised Items"},
    ).status_code == 404
    coaching_scorecard_b.refresh_from_db()
    assert coaching_scorecard_b.action_items == orig_items


def test_salesenablement_idor_delete_views_return_404_cross_tenant(
    client_a,
    enablement_content_b,
    sales_playbook_b,
    sales_certification_b,
    coaching_scorecard_b,
):
    """Tenant A POSTing delete on Tenant B records strictly returns 404, objects are not deleted."""
    # EnablementContent
    assert client_a.post(reverse("sales:enablement_content_delete", kwargs={"pk": enablement_content_b.pk})).status_code == 404
    assert EnablementContent.objects.filter(pk=enablement_content_b.pk).exists()

    # SalesPlaybook
    assert client_a.post(reverse("sales:sales_playbook_delete", kwargs={"pk": sales_playbook_b.pk})).status_code == 404
    assert SalesPlaybook.objects.filter(pk=sales_playbook_b.pk).exists()

    # SalesCertification
    assert client_a.post(reverse("sales:sales_certification_delete", kwargs={"pk": sales_certification_b.pk})).status_code == 404
    assert SalesCertification.objects.filter(pk=sales_certification_b.pk).exists()

    # CoachingScorecard
    assert client_a.post(reverse("sales:coaching_scorecard_delete", kwargs={"pk": coaching_scorecard_b.pk})).status_code == 404
    assert CoachingScorecard.objects.filter(pk=coaching_scorecard_b.pk).exists()


def test_salesenablement_idor_share_action_returns_404_cross_tenant(
    client_a, enablement_content_b
):
    """Tenant A cannot trigger share action on Tenant B content asset."""
    orig_shares = enablement_content_b.share_count
    url = reverse("sales:enablement_content_share", kwargs={"pk": enablement_content_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    enablement_content_b.refresh_from_db()
    assert enablement_content_b.share_count == orig_shares


def test_salesenablement_idor_acknowledge_action_returns_404_cross_tenant(
    client_a, coaching_scorecard_b
):
    """Tenant A cannot acknowledge Tenant B scorecard."""
    orig_status = coaching_scorecard_b.review_status
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": coaching_scorecard_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    coaching_scorecard_b.refresh_from_db()
    assert coaching_scorecard_b.review_status == orig_status


def test_salesenablement_idor_tenant_b_cannot_access_tenant_a_records(
    client_b,
    enablement_content_a,
    sales_playbook_a,
    sales_certification_a,
    coaching_scorecard_a,
):
    """Tenant B cannot mutate or delete Tenant A records via POST."""
    assert client_b.post(reverse("sales:enablement_content_delete", kwargs={"pk": enablement_content_a.pk})).status_code == 404
    assert EnablementContent.objects.filter(pk=enablement_content_a.pk).exists()

    assert client_b.post(reverse("sales:sales_playbook_delete", kwargs={"pk": sales_playbook_a.pk})).status_code == 404
    assert SalesPlaybook.objects.filter(pk=sales_playbook_a.pk).exists()

    assert client_b.post(reverse("sales:sales_certification_delete", kwargs={"pk": sales_certification_a.pk})).status_code == 404
    assert SalesCertification.objects.filter(pk=sales_certification_a.pk).exists()

    assert client_b.post(reverse("sales:coaching_scorecard_delete", kwargs={"pk": coaching_scorecard_a.pk})).status_code == 404
    assert CoachingScorecard.objects.filter(pk=coaching_scorecard_a.pk).exists()

    assert client_b.post(reverse("sales:enablement_content_share", kwargs={"pk": enablement_content_a.pk})).status_code == 404
    assert client_b.post(reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": coaching_scorecard_a.pk})).status_code == 404


# ==============================================================================
# 4. Object-Level & Role Authorization
# ==============================================================================


def test_salesenablement_authorization_coaching_scorecard_acknowledge_forbidden_for_non_coachee(
    tenant_a, admin_user, member_user
):
    """Non-coachee / non-admin user gets denied when attempting to acknowledge scorecard."""
    other_rep = _salesenablement_create_user(tenant_a, "peer_rep", is_admin=False)
    client_peer = Client()
    client_peer.force_login(other_rep)

    scorecard = _salesenablement_scorecard(
        tenant_a, coach=admin_user, coachee=member_user, review_status="draft"
    )
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": scorecard.pk})

    resp = client_peer.post(url, follow=True)
    assert resp.status_code in (200, 302, 403)
    scorecard.refresh_from_db()
    assert scorecard.review_status == "draft"

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("Only the coachee or a tenant administrator" in m for m in messages)


def test_salesenablement_authorization_coaching_scorecard_acknowledge_succeeds_for_coachee(
    member_client, tenant_a, admin_user, member_user
):
    """The coachee rep can acknowledge their scorecard."""
    scorecard = _salesenablement_scorecard(
        tenant_a, coach=admin_user, coachee=member_user, review_status="draft"
    )
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": scorecard.pk})

    resp = member_client.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:coaching_scorecard_detail", kwargs={"pk": scorecard.pk})
    scorecard.refresh_from_db()
    assert scorecard.review_status == "acknowledged"


def test_salesenablement_authorization_coaching_scorecard_acknowledge_succeeds_for_admin(
    client_a, tenant_a, member_user
):
    """A tenant admin can acknowledge any scorecard in their tenant."""
    coach_rep = _salesenablement_create_user(tenant_a, "coach_rep", is_admin=False)
    scorecard = _salesenablement_scorecard(
        tenant_a, coach=coach_rep, coachee=member_user, review_status="draft"
    )
    url = reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": scorecard.pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    scorecard.refresh_from_db()
    assert scorecard.review_status == "acknowledged"


def test_salesenablement_authorization_enablement_content_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Non-author non-admin cannot delete; author or tenant admin can delete."""
    admin_content = _salesenablement_content(tenant_a, author=admin_user, title="Admin Authored Content")
    member_content = _salesenablement_content(tenant_a, author=member_user, title="Member Authored Content")

    # Member user attempts to delete admin-authored content -> denied
    url_admin = reverse("sales:enablement_content_delete", kwargs={"pk": admin_content.pk})
    resp_unauth = member_client.post(url_admin, follow=True)
    assert resp_unauth.status_code in (200, 302, 403)
    assert EnablementContent.objects.filter(pk=admin_content.pk).exists()
    messages = [m.message for m in get_messages(resp_unauth.wsgi_request)]
    assert any("Only the author or a tenant administrator" in m for m in messages)

    # Member user deletes their own authored content -> succeeds
    url_member = reverse("sales:enablement_content_delete", kwargs={"pk": member_content.pk})
    resp_author = member_client.post(url_member)
    assert resp_author.status_code == 302
    assert not EnablementContent.objects.filter(pk=member_content.pk).exists()

    # Admin deletes admin_content -> succeeds
    resp_admin = client_a.post(url_admin)
    assert resp_admin.status_code == 302
    assert not EnablementContent.objects.filter(pk=admin_content.pk).exists()


def test_salesenablement_authorization_sales_playbook_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Non-owner non-admin cannot delete playbook; owner or tenant admin can delete."""
    admin_pb = _salesenablement_playbook(tenant_a, owner=admin_user, name="Admin Playbook")
    member_pb = _salesenablement_playbook(tenant_a, owner=member_user, name="Member Playbook")

    # Member attempts to delete admin playbook -> denied
    url_admin = reverse("sales:sales_playbook_delete", kwargs={"pk": admin_pb.pk})
    resp_unauth = member_client.post(url_admin, follow=True)
    assert resp_unauth.status_code in (200, 302, 403)
    assert SalesPlaybook.objects.filter(pk=admin_pb.pk).exists()
    messages = [m.message for m in get_messages(resp_unauth.wsgi_request)]
    assert any("Only the playbook owner or a tenant administrator" in m for m in messages)

    # Member deletes their own playbook -> succeeds
    url_member = reverse("sales:sales_playbook_delete", kwargs={"pk": member_pb.pk})
    resp_owner = member_client.post(url_member)
    assert resp_owner.status_code == 302
    assert not SalesPlaybook.objects.filter(pk=member_pb.pk).exists()

    # Admin deletes admin playbook -> succeeds
    resp_admin = client_a.post(url_admin)
    assert resp_admin.status_code == 302
    assert not SalesPlaybook.objects.filter(pk=admin_pb.pk).exists()


def test_salesenablement_authorization_sales_certification_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Non-certifying user cannot delete certification; certifier or tenant admin can delete."""
    cert = _salesenablement_certification(
        tenant_a, rep=member_user, certified_by=admin_user
    )

    # Coachee/rep attempts to delete certification record -> denied
    url = reverse("sales:sales_certification_delete", kwargs={"pk": cert.pk})
    resp_unauth = member_client.post(url, follow=True)
    assert resp_unauth.status_code in (200, 302, 403)
    assert SalesCertification.objects.filter(pk=cert.pk).exists()
    messages = [m.message for m in get_messages(resp_unauth.wsgi_request)]
    assert any("Only the certifying manager or a tenant administrator" in m for m in messages)

    # Certifying manager / Admin deletes -> succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not SalesCertification.objects.filter(pk=cert.pk).exists()


def test_salesenablement_authorization_coaching_scorecard_delete_permissions(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Non-coach non-admin cannot delete scorecard; coach or tenant admin can delete."""
    scorecard = _salesenablement_scorecard(
        tenant_a, coach=admin_user, coachee=member_user
    )

    # Coachee rep attempts to delete scorecard -> denied
    url = reverse("sales:coaching_scorecard_delete", kwargs={"pk": scorecard.pk})
    resp_unauth = member_client.post(url, follow=True)
    assert resp_unauth.status_code in (200, 302, 403)
    assert CoachingScorecard.objects.filter(pk=scorecard.pk).exists()
    messages = [m.message for m in get_messages(resp_unauth.wsgi_request)]
    assert any("Only the evaluating coach or a tenant administrator" in m for m in messages)

    # Coach / Admin deletes -> succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not CoachingScorecard.objects.filter(pk=scorecard.pk).exists()


def test_salesenablement_authorization_sales_certification_rep_cannot_self_certify(
    member_client, client_a, member_user, tenant_a
):
    """Unprivileged sales rep cannot self-certify as completed on sales_certification_create."""
    url = reverse("sales:sales_certification_create")
    forbidden_payload = {
        "curriculum_name": "Autonomous Self Promotion",
        "category": "methodology",
        "rep": member_user.pk,
        "status": "completed",
        "score_percent": "98.50",
        "passing_score_percent": "80.00",
    }

    # Member user attempts self-certification as completed -> rejected
    resp_member = member_client.post(url, forbidden_payload)
    assert resp_member.status_code in (200, 400, 403)
    assert not SalesCertification.objects.filter(
        curriculum_name="Autonomous Self Promotion", rep=member_user, status="completed"
    ).exists()

    # Member user CAN create an enrollment with status='enrolled'
    enrolled_payload = {
        "curriculum_name": "Valid Rep Enrollment",
        "category": "methodology",
        "rep": member_user.pk,
        "status": "enrolled",
        "passing_score_percent": "80.00",
    }
    resp_enroll = member_client.post(url, enrolled_payload)
    assert resp_enroll.status_code == 302
    assert SalesCertification.objects.filter(
        curriculum_name="Valid Rep Enrollment", rep=member_user, status="enrolled"
    ).exists()

    # Tenant admin CAN create a completed certification record
    admin_payload = {
        "curriculum_name": "Admin Approved Certification",
        "category": "product_certification",
        "rep": member_user.pk,
        "status": "completed",
        "score_percent": "95.00",
        "passing_score_percent": "80.00",
        "accreditation_notes": "Passed with distinction.",
    }
    resp_admin = client_a.post(url, admin_payload)
    assert resp_admin.status_code == 302
    assert SalesCertification.objects.filter(
        curriculum_name="Admin Approved Certification", rep=member_user, status="completed"
    ).exists()


# ==============================================================================
# 5. CSRF Defenses
# ==============================================================================


def test_salesenablement_csrf_enforced_on_all_model_create_and_edit_endpoints(
    admin_user,
    enablement_content_a,
    sales_playbook_a,
    sales_certification_a,
    coaching_scorecard_a,
):
    """Every create and edit form POST route strictly requires a valid CSRF token."""
    csrf_client = _salesenablement_csrf_client(admin_user)

    routes = [
        reverse("sales:enablement_content_create"),
        reverse("sales:enablement_content_edit", kwargs={"pk": enablement_content_a.pk}),
        reverse("sales:sales_playbook_create"),
        reverse("sales:sales_playbook_edit", kwargs={"pk": sales_playbook_a.pk}),
        reverse("sales:sales_certification_create"),
        reverse("sales:sales_certification_edit", kwargs={"pk": sales_certification_a.pk}),
        reverse("sales:coaching_scorecard_create"),
        reverse("sales:coaching_scorecard_edit", kwargs={"pk": coaching_scorecard_a.pk}),
    ]

    for url in routes:
        resp = csrf_client.post(url, {"name": "CSRF Attack", "title": "CSRF Attack"})
        assert resp.status_code == 403, f"Expected 403 CSRF Forbidden for POST {url}, got {resp.status_code}"


def test_salesenablement_csrf_enforced_on_all_delete_endpoints(
    admin_user,
    enablement_content_a,
    sales_playbook_a,
    sales_certification_a,
    coaching_scorecard_a,
):
    """Every delete POST endpoint strictly requires a valid CSRF token."""
    csrf_client = _salesenablement_csrf_client(admin_user)

    delete_routes = [
        reverse("sales:enablement_content_delete", kwargs={"pk": enablement_content_a.pk}),
        reverse("sales:sales_playbook_delete", kwargs={"pk": sales_playbook_a.pk}),
        reverse("sales:sales_certification_delete", kwargs={"pk": sales_certification_a.pk}),
        reverse("sales:coaching_scorecard_delete", kwargs={"pk": coaching_scorecard_a.pk}),
    ]

    for url in delete_routes:
        resp = csrf_client.post(url, {})
        assert resp.status_code == 403, f"Expected 403 CSRF Forbidden for POST {url}, got {resp.status_code}"


def test_salesenablement_csrf_enforced_on_custom_actions(
    admin_user, enablement_content_a, coaching_scorecard_a
):
    """Custom action POST routes (share, acknowledge) strictly require a valid CSRF token."""
    csrf_client = _salesenablement_csrf_client(admin_user)

    action_routes = [
        reverse("sales:enablement_content_share", kwargs={"pk": enablement_content_a.pk}),
        reverse("sales:coaching_scorecard_acknowledge", kwargs={"pk": coaching_scorecard_a.pk}),
    ]

    for url in action_routes:
        resp = csrf_client.post(url, {})
        assert resp.status_code == 403, f"Expected 403 CSRF Forbidden for POST {url}, got {resp.status_code}"


# ==============================================================================
# 6. Cross-Tenant Foreign Key Injection
# ==============================================================================


def test_salesenablement_fk_injection_enablement_content_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_user, admin_b
):
    """EnablementContentForm and create view reject foreign tenant document, competitor, stage, and author."""
    foreign_doc = _salesenablement_document(tenant_b, name="Foreign Doc")
    foreign_comp = _salesenablement_create_competitor(tenant_b, name="Foreign Competitor")
    _, foreign_stage = _salesenablement_create_pipeline_and_stage(tenant_b, name="Foreign Pipe")

    # 1. Foreign document injection
    form1 = EnablementContentForm(
        data={
            "title": "Injected Doc Test",
            "content_type": "battle_card",
            "document": foreign_doc.pk,
            "version": "1.0",
        },
        tenant=tenant_a,
    )
    assert not form1.is_valid()
    assert "document" in form1.errors

    # 2. Foreign competitor injection
    form2 = EnablementContentForm(
        data={
            "title": "Injected Competitor Test",
            "content_type": "battle_card",
            "competitor": foreign_comp.pk,
            "version": "1.0",
        },
        tenant=tenant_a,
    )
    assert not form2.is_valid()
    assert "competitor" in form2.errors

    # 3. Foreign pipeline stage injection
    form3 = EnablementContentForm(
        data={
            "title": "Injected Stage Test",
            "content_type": "battle_card",
            "pipeline_stage": foreign_stage.pk,
            "version": "1.0",
        },
        tenant=tenant_a,
    )
    assert not form3.is_valid()
    assert "pipeline_stage" in form3.errors

    # 4. Foreign author injection
    form4 = EnablementContentForm(
        data={
            "title": "Injected Author Test",
            "content_type": "battle_card",
            "author": admin_b.pk,
            "version": "1.0",
        },
        tenant=tenant_a,
    )
    assert not form4.is_valid()
    assert "author" in form4.errors

    # 5. Injection via HTTP client_a to enablement_content_create
    resp = client_a.post(
        reverse("sales:enablement_content_create"),
        {
            "title": "Client FK Injection Attack",
            "content_type": "battle_card",
            "competitor": foreign_comp.pk,
            "document": foreign_doc.pk,
            "author": admin_b.pk,
        },
    )
    assert resp.status_code in (200, 400)
    assert not EnablementContent.objects.filter(title="Client FK Injection Attack").exists()


def test_salesenablement_fk_injection_sales_playbook_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_b
):
    """SalesPlaybookForm and create view reject foreign tenant pipeline and owner."""
    foreign_pipe, _ = _salesenablement_create_pipeline_and_stage(tenant_b, name="Foreign Pipeline")

    # 1. Foreign pipeline injection
    form1 = SalesPlaybookForm(
        data={
            "name": "Injected Pipeline Playbook",
            "motion_type": "new_business",
            "status": "draft",
            "pipeline": foreign_pipe.pk,
            "version": "1.0",
        },
        tenant=tenant_a,
    )
    assert not form1.is_valid()
    assert "pipeline" in form1.errors

    # 2. Foreign owner injection
    form2 = SalesPlaybookForm(
        data={
            "name": "Injected Owner Playbook",
            "motion_type": "new_business",
            "status": "draft",
            "owner": admin_b.pk,
            "version": "1.0",
        },
        tenant=tenant_a,
    )
    assert not form2.is_valid()
    assert "owner" in form2.errors

    # 3. HTTP injection attempt via client_a
    resp = client_a.post(
        reverse("sales:sales_playbook_create"),
        {
            "name": "HTTP Foreign Playbook Injection",
            "motion_type": "new_business",
            "status": "draft",
            "pipeline": foreign_pipe.pk,
            "owner": admin_b.pk,
        },
    )
    assert resp.status_code in (200, 400)
    assert not SalesPlaybook.objects.filter(name="HTTP Foreign Playbook Injection").exists()


def test_salesenablement_fk_injection_sales_certification_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_b
):
    """SalesCertificationForm and create view reject foreign rep, certified_by, and hrm_course."""
    foreign_course = _salesenablement_create_training_course(tenant_b, title="Foreign Course")

    # 1. Foreign rep injection
    form1 = SalesCertificationForm(
        data={
            "curriculum_name": "Injected Rep Certification",
            "category": "methodology",
            "rep": admin_b.pk,
            "status": "enrolled",
            "passing_score_percent": "80.00",
        },
        tenant=tenant_a,
    )
    assert not form1.is_valid()
    assert "rep" in form1.errors

    # 2. Foreign certified_by injection
    form2 = SalesCertificationForm(
        data={
            "curriculum_name": "Injected Certifier Certification",
            "category": "methodology",
            "certified_by": admin_b.pk,
            "status": "enrolled",
            "passing_score_percent": "80.00",
        },
        tenant=tenant_a,
    )
    assert not form2.is_valid()
    assert "certified_by" in form2.errors

    # 3. Foreign HRM course injection (if course exists)
    if foreign_course:
        form3 = SalesCertificationForm(
            data={
                "curriculum_name": "Injected HRM Course Certification",
                "category": "methodology",
                "hrm_course": foreign_course.pk,
                "status": "enrolled",
                "passing_score_percent": "80.00",
            },
            tenant=tenant_a,
        )
        assert not form3.is_valid()
        assert "hrm_course" in form3.errors

    # 4. HTTP injection attempt via client_a
    resp = client_a.post(
        reverse("sales:sales_certification_create"),
        {
            "curriculum_name": "HTTP Foreign Cert Injection",
            "category": "methodology",
            "rep": admin_b.pk,
            "certified_by": admin_b.pk,
            "status": "enrolled",
            "passing_score_percent": "80.00",
        },
    )
    assert resp.status_code in (200, 400)
    assert not SalesCertification.objects.filter(curriculum_name="HTTP Foreign Cert Injection").exists()


def test_salesenablement_fk_injection_coaching_scorecard_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_b
):
    """CoachingScorecardForm and create view reject foreign communication_log, activity_log, coach, and coachee."""
    foreign_comm = CommunicationLog.objects.create(
        tenant=tenant_b,
        channel="call",
        subject="Foreign Tenant Communication",
        owner=admin_b,
    )
    foreign_act = _salesenablement_create_activity_log(tenant_b, foreign_comm, admin_b)

    # 1. Foreign communication_log injection
    form1 = CoachingScorecardForm(
        data={
            "communication_log": foreign_comm.pk,
            "discovery_score": 4,
            "value_prop_score": 4,
            "objection_handling_score": 4,
            "next_steps_score": 4,
        },
        tenant=tenant_a,
    )
    assert not form1.is_valid()
    assert "communication_log" in form1.errors

    # 2. Foreign activity_log injection
    form2 = CoachingScorecardForm(
        data={
            "activity_log": foreign_act.pk,
            "discovery_score": 4,
            "value_prop_score": 4,
            "objection_handling_score": 4,
            "next_steps_score": 4,
        },
        tenant=tenant_a,
    )
    assert not form2.is_valid()
    assert "activity_log" in form2.errors

    # 3. Foreign coach injection
    form3 = CoachingScorecardForm(
        data={
            "coach": admin_b.pk,
            "discovery_score": 4,
            "value_prop_score": 4,
            "objection_handling_score": 4,
            "next_steps_score": 4,
        },
        tenant=tenant_a,
    )
    assert not form3.is_valid()
    assert "coach" in form3.errors

    # 4. Foreign coachee injection
    form4 = CoachingScorecardForm(
        data={
            "coachee": admin_b.pk,
            "discovery_score": 4,
            "value_prop_score": 4,
            "objection_handling_score": 4,
            "next_steps_score": 4,
        },
        tenant=tenant_a,
    )
    assert not form4.is_valid()
    assert "coachee" in form4.errors

    # 5. HTTP injection attempt via client_a
    resp = client_a.post(
        reverse("sales:coaching_scorecard_create"),
        {
            "communication_log": foreign_comm.pk,
            "coach": admin_b.pk,
            "coachee": admin_b.pk,
            "discovery_score": 4,
            "value_prop_score": 4,
            "objection_handling_score": 4,
            "next_steps_score": 4,
        },
    )
    assert resp.status_code in (200, 400)
    assert not CoachingScorecard.objects.filter(communication_log=foreign_comm).exists()
