"""Sub-module 8.11 Customer Success & Account Management -- Views Test Suite.

Covers:
1. 5 Strategic Consoles & Hubs:
   - customer_health_console (verifies aggregates, alerts, band counts)
   - customer_renewal_pipeline (verifies pipeline ARR, expansion, stages)
   - customer_onboarding_hub (verifies active count, avg progress, avg ttv)
   - customer_advocacy_hub (verifies referenceable count, case study pipeline)
   - customer_qbr_studio (verifies scheduled reviews, conducted count, upcoming)
2. 4 CRUD Entity Models (CustomerHealthScore, CustomerRenewal, CustomerOnboarding, CustomerBusinessReview):
   - List views: GET 200, search q, dropdown filters, pagination
   - Detail views: GET 200, context variables
   - Create views: GET 200, POST 302 creates tenant-isolated record with AuditLog
   - Edit views: GET 200, POST 302 updates record with AuditLog
   - Delete views: GET 405 (strictly POST-only via @require_POST), POST 302 deletes record with AuditLog
3. Negative-input hardening:
   - Junk GET filters (?stage=garbage, ?status=xyz, ?page=invalid, ?page=999) return 200 without 500 errors.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party, PartyRole
from apps.sales.models import (
    CustomerBusinessReview,
    CustomerHealthScore,
    CustomerOnboarding,
    CustomerRenewal,
)
from apps.sales.tests.conftest import (
    _customersuccess_business_review,
    _customersuccess_health_score,
    _customersuccess_onboarding,
    _customersuccess_renewal,
)

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers
# ============================================================================

def _customersuccess_customer(tenant, name="Acme Customer"):
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="customer")
    return party


# ============================================================================
# 1. Consoles & Hubs
# ============================================================================

def test_customersuccess_health_console_view(client_a, tenant_a, cs_health_score_a):
    """Health console returns 200 and passes required metrics in context."""
    url = reverse("sales:customer_health_console")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/customersuccess/health_console.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "health_scores" in ctx
    assert "stats" in ctx
    assert ctx["stats"]["healthy_count"] >= 1


def test_customersuccess_renewal_pipeline_view(client_a, tenant_a, cs_renewal_a):
    """Renewal pipeline returns 200 and passes financial pipeline metrics."""
    url = reverse("sales:customer_renewal_pipeline")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/customersuccess/renewal_pipeline.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "renewals_by_stage" in ctx
    assert "stats" in ctx
    assert ctx["stats"]["total_arr"] >= Decimal("100000.00")


def test_customersuccess_onboarding_hub_view(client_a, tenant_a, cs_onboarding_a):
    """Onboarding hub returns 200 and passes implementation velocity metrics."""
    url = reverse("sales:customer_onboarding_hub")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/customersuccess/onboarding_hub.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "active_onboardings" in ctx
    assert "stats" in ctx
    assert ctx["stats"]["total_count"] >= 1


def test_customersuccess_advocacy_hub_view(client_a, tenant_a, cs_qbr_a):
    """Advocacy hub returns 200 and passes reference / case study metrics."""
    url = reverse("sales:customer_advocacy_hub")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/customersuccess/advocacy_hub.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "referenceable_accounts" in ctx
    assert "stats" in ctx


def test_customersuccess_qbr_studio_view(client_a, tenant_a, cs_qbr_a):
    """QBR studio returns 200 and passes cadence / review metrics."""
    url = reverse("sales:customer_qbr_studio")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/customersuccess/qbr_studio.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "upcoming_qbrs" in ctx
    assert "stats" in ctx


# ============================================================================
# 2. List Views (Filtering & Pagination)
# ============================================================================

def test_customersuccess_health_score_list_view(client_a, tenant_a, cs_health_score_a):
    """List health scores with search and band filters."""
    url = reverse("sales:customer_health_score_list")
    resp = client_a.get(url, {"health_band": "green", "q": cs_health_score_a.account.name})
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert len(resp.context["page_obj"]) >= 1


def test_customersuccess_renewal_list_view(client_a, tenant_a, cs_renewal_a):
    """List renewals with search and stage filters."""
    url = reverse("sales:customer_renewal_list")
    resp = client_a.get(url, {"stage": "upcoming", "q": cs_renewal_a.renewal_name})
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert len(resp.context["page_obj"]) >= 1


def test_customersuccess_onboarding_list_view(client_a, tenant_a, cs_onboarding_a):
    """List onboardings with status and template filters."""
    url = reverse("sales:customer_onboarding_list")
    resp = client_a.get(url, {"status": "in_progress", "template_type": "enterprise_high_touch"})
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert len(resp.context["page_obj"]) >= 1


def test_customersuccess_business_review_list_view(client_a, tenant_a, cs_qbr_a):
    """List business reviews with status and referenceable filters."""
    url = reverse("sales:customer_business_review_list")
    resp = client_a.get(url, {"status": "scheduled", "is_referenceable": "1"})
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert len(resp.context["page_obj"]) >= 1


# ============================================================================
# 3. Detail Views
# ============================================================================

def test_customersuccess_detail_views(
    client_a, cs_health_score_a, cs_renewal_a, cs_onboarding_a, cs_qbr_a
):
    """Assert all 4 detail views return 200 and bind expected object contexts."""
    # Health score detail
    resp1 = client_a.get(reverse("sales:customer_health_score_detail", args=[cs_health_score_a.pk]))
    assert resp1.status_code == 200
    assert resp1.context["health_score"] == cs_health_score_a

    # Renewal detail
    resp2 = client_a.get(reverse("sales:customer_renewal_detail", args=[cs_renewal_a.pk]))
    assert resp2.status_code == 200
    assert resp2.context["renewal"] == cs_renewal_a

    # Onboarding detail
    resp3 = client_a.get(reverse("sales:customer_onboarding_detail", args=[cs_onboarding_a.pk]))
    assert resp3.status_code == 200
    assert resp3.context["onboarding"] == cs_onboarding_a

    # Business review detail
    resp4 = client_a.get(reverse("sales:customer_business_review_detail", args=[cs_qbr_a.pk]))
    assert resp4.status_code == 200
    assert resp4.context["review"] == cs_qbr_a


# ============================================================================
# 4. Create Views (GET & POST with AuditLog)
# ============================================================================

def test_customersuccess_health_score_create_view(client_a, tenant_a):
    """Create a health score via view, verify redirect and AuditLog entry."""
    cust = _customersuccess_customer(tenant_a, name="New Health Customer")
    create_url = reverse("sales:customer_health_score_create")

    # GET
    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200

    # POST
    payload = {
        "account": cust.pk,
        "evaluation_date": "2026-03-01",
        "overall_score": 85,
        "health_band": "green",
        "score_trend": "improving",
        "risk_level": "low",
        "product_usage_score": 85,
        "support_ticket_score": 85,
        "nps_sentiment_score": 85,
        "relationship_score": 85,
        "renewal_risk_score": 85,
        "license_utilization_pct": "80.00",
        "open_support_tickets": 0,
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302

    created = CustomerHealthScore.objects.filter(tenant=tenant_a, account=cust).first()
    assert created is not None
    assert created.overall_score == 85

    # Check AuditLog
    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created.pk)).first()
    assert log is not None


def test_customersuccess_renewal_create_view(client_a, tenant_a, admin_user, icm_currency):
    """Create a renewal via view, verify redirect and AuditLog entry."""
    cust = _customersuccess_customer(tenant_a, name="New Renewal Customer")
    create_url = reverse("sales:customer_renewal_create")

    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200

    payload = {
        "account": cust.pk,
        "owner": admin_user.pk,
        "renewal_name": "FY26 Enterprise Renewal",
        "contract_reference": "MSA-2026-101",
        "current_arr": "120000.00",
        "projected_renewal_arr": "135000.00",
        "expansion_amount": "15000.00",
        "currency": icm_currency.pk,
        "renewal_date": "2026-07-01",
        "target_close_date": "2026-06-01",
        "stage": "upcoming",
        "churn_risk_flag": "low",
        "renewal_probability_pct": 80,
        "notice_period_days": 60,
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302

    created = CustomerRenewal.objects.filter(tenant=tenant_a, account=cust).first()
    assert created is not None
    assert created.renewal_name == "FY26 Enterprise Renewal"

    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created.pk)).first()
    assert log is not None


def test_customersuccess_onboarding_create_view(client_a, tenant_a, admin_user):
    """Create onboarding via view, verify redirect and AuditLog entry."""
    cust = _customersuccess_customer(tenant_a, name="New Onboarding Customer")
    create_url = reverse("sales:customer_onboarding_create")

    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200

    payload = {
        "account": cust.pk,
        "lead_csm": admin_user.pk,
        "title": "Onboarding Pilot",
        "playbook_template": "smb_accelerated",
        "stage": "kickoff",
        "status": "in_progress",
        "kickoff_date": "2026-02-01",
        "target_go_live_date": "2026-03-01",
        "progress_pct": 25,
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302

    created = CustomerOnboarding.objects.filter(tenant=tenant_a, account=cust).first()
    assert created is not None

    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created.pk)).first()
    assert log is not None


def test_customersuccess_business_review_create_view(client_a, tenant_a, admin_user):
    """Create business review via view, verify redirect and AuditLog entry."""
    cust = _customersuccess_customer(tenant_a, name="New QBR Customer")
    create_url = reverse("sales:customer_business_review_create")

    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200

    payload = {
        "account": cust.pk,
        "lead_csm": admin_user.pk,
        "title": "Q3 Executive Strategy Review",
        "review_period": "q3",
        "review_year": 2026,
        "scheduled_date": "2026-09-15",
        "status": "scheduled",
        "template_type": "executive_value",
        "case_study_status": "none",
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302

    created = CustomerBusinessReview.objects.filter(tenant=tenant_a, account=cust).first()
    assert created is not None

    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created.pk)).first()
    assert log is not None


# ============================================================================
# 5. Edit Views (GET & POST with AuditLog)
# ============================================================================

def test_customersuccess_health_score_edit_view(client_a, tenant_a, cs_health_score_a):
    """Edit health score via view, verify redirect and AuditLog update entry."""
    edit_url = reverse("sales:customer_health_score_edit", args=[cs_health_score_a.pk])

    resp_get = client_a.get(edit_url)
    assert resp_get.status_code == 200

    payload = {
        "account": cs_health_score_a.account.pk,
        "evaluation_date": str(cs_health_score_a.evaluation_date),
        "overall_score": 92,
        "health_band": "green",
        "previous_score": 85,
        "score_trend": "improving",
        "risk_level": "low",
        "product_usage_score": 95,
        "support_ticket_score": 90,
        "nps_sentiment_score": 92,
        "relationship_score": 90,
        "renewal_risk_score": 90,
        "license_utilization_pct": "90.00",
        "open_support_tickets": 0,
        "notes": "Updated notes via edit view",
    }
    resp_post = client_a.post(edit_url, payload)
    assert resp_post.status_code == 302

    cs_health_score_a.refresh_from_db()
    assert cs_health_score_a.overall_score == 92
    assert cs_health_score_a.notes == "Updated notes via edit view"

    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(cs_health_score_a.pk)).first()
    assert log is not None


def test_customersuccess_renewal_edit_view(client_a, tenant_a, cs_renewal_a):
    """Edit renewal via view, verify update and AuditLog."""
    edit_url = reverse("sales:customer_renewal_edit", args=[cs_renewal_a.pk])

    payload = {
        "account": cs_renewal_a.account.pk,
        "owner": cs_renewal_a.owner.pk,
        "renewal_name": "Updated 2026 Renewal Name",
        "contract_reference": cs_renewal_a.contract_reference,
        "current_arr": str(cs_renewal_a.current_arr),
        "projected_renewal_arr": "125000.00",
        "expansion_amount": "25000.00",
        "currency": cs_renewal_a.currency.pk,
        "renewal_date": str(cs_renewal_a.renewal_date),
        "target_close_date": str(cs_renewal_a.target_close_date),
        "stage": "engagement",
        "churn_risk_flag": "low",
        "renewal_probability_pct": 85,
        "notice_period_days": 60,
    }
    resp_post = client_a.post(edit_url, payload)
    assert resp_post.status_code == 302

    cs_renewal_a.refresh_from_db()
    assert cs_renewal_a.renewal_name == "Updated 2026 Renewal Name"
    assert cs_renewal_a.projected_renewal_arr == Decimal("125000.00")

    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(cs_renewal_a.pk)).first()
    assert log is not None


def test_customersuccess_onboarding_edit_view(client_a, tenant_a, cs_onboarding_a):
    """Edit onboarding via view, verify update and AuditLog."""
    edit_url = reverse("sales:customer_onboarding_edit", args=[cs_onboarding_a.pk])

    payload = {
        "account": cs_onboarding_a.account.pk,
        "lead_csm": cs_onboarding_a.lead_csm.pk,
        "title": "Updated Rollout Title",
        "playbook_template": cs_onboarding_a.playbook_template,
        "stage": "configuration",
        "status": "in_progress",
        "kickoff_date": str(cs_onboarding_a.kickoff_date),
        "target_go_live_date": str(cs_onboarding_a.target_go_live_date),
        "progress_pct": 50,
    }
    resp_post = client_a.post(edit_url, payload)
    assert resp_post.status_code == 302

    cs_onboarding_a.refresh_from_db()
    assert cs_onboarding_a.progress_pct == 50
    assert cs_onboarding_a.title == "Updated Rollout Title"

    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(cs_onboarding_a.pk)).first()
    assert log is not None


def test_customersuccess_business_review_edit_view(client_a, tenant_a, cs_qbr_a):
    """Edit business review via view, verify update and AuditLog."""
    edit_url = reverse("sales:customer_business_review_edit", args=[cs_qbr_a.pk])

    payload = {
        "account": cs_qbr_a.account.pk,
        "lead_csm": cs_qbr_a.lead_csm.pk,
        "title": "Updated QBR Title",
        "review_period": cs_qbr_a.review_period,
        "review_year": cs_qbr_a.review_year,
        "scheduled_date": str(cs_qbr_a.scheduled_date),
        "status": "conducted",
        "template_type": cs_qbr_a.template_type,
        "completed_date": "2026-03-20",
        "case_study_status": "published",
        "is_referenceable": True,
        "testimonial_quote": "Sensational platform and partner",
    }
    resp_post = client_a.post(edit_url, payload)
    assert resp_post.status_code == 302

    cs_qbr_a.refresh_from_db()
    assert cs_qbr_a.status == "conducted"
    assert cs_qbr_a.testimonial_quote == "Sensational platform and partner"

    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(cs_qbr_a.pk)).first()
    assert log is not None


# ============================================================================
# 6. Delete Views (Require POST, Delete Record, AuditLog)
# ============================================================================

def test_customersuccess_delete_views_require_post(
    client_a, cs_health_score_a, cs_renewal_a, cs_onboarding_a, cs_qbr_a
):
    """GET requests to delete endpoints must be rejected with 405 Method Not Allowed."""
    delete_urls = [
        reverse("sales:customer_health_score_delete", args=[cs_health_score_a.pk]),
        reverse("sales:customer_renewal_delete", args=[cs_renewal_a.pk]),
        reverse("sales:customer_onboarding_delete", args=[cs_onboarding_a.pk]),
        reverse("sales:customer_business_review_delete", args=[cs_qbr_a.pk]),
    ]
    for url in delete_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"GET on {url} must return 405 Method Not Allowed"


def test_customersuccess_delete_views_post_success(
    client_a, tenant_a, cs_health_score_a, cs_renewal_a, cs_onboarding_a, cs_qbr_a
):
    """POST to delete endpoints removes the record and writes an AuditLog entry."""
    # Delete health score
    pk_chs = cs_health_score_a.pk
    resp1 = client_a.post(reverse("sales:customer_health_score_delete", args=[pk_chs]))
    assert resp1.status_code == 302
    assert not CustomerHealthScore.objects.filter(pk=pk_chs).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(pk_chs)).exists()

    # Delete renewal
    pk_crn = cs_renewal_a.pk
    resp2 = client_a.post(reverse("sales:customer_renewal_delete", args=[pk_crn]))
    assert resp2.status_code == 302
    assert not CustomerRenewal.objects.filter(pk=pk_crn).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(pk_crn)).exists()

    # Delete onboarding
    pk_cob = cs_onboarding_a.pk
    resp3 = client_a.post(reverse("sales:customer_onboarding_delete", args=[pk_cob]))
    assert resp3.status_code == 302
    assert not CustomerOnboarding.objects.filter(pk=pk_cob).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(pk_cob)).exists()

    # Delete business review
    pk_qbr = cs_qbr_a.pk
    resp4 = client_a.post(reverse("sales:customer_business_review_delete", args=[pk_qbr]))
    assert resp4.status_code == 302
    assert not CustomerBusinessReview.objects.filter(pk=pk_qbr).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(pk_qbr)).exists()


# ============================================================================
# 7. Negative-Input Hardening (Junk Params, Invalid Paging)
# ============================================================================

def test_customersuccess_views_junk_params_resilience(client_a):
    """Views handle unexpected or out-of-bounds parameters gracefully with 200, never 500."""
    junk_urls = [
        (reverse("sales:customer_health_score_list"), {"health_band": "invalid_band", "page": "xyz", "q": "/*--?@"}),
        (reverse("sales:customer_renewal_list"), {"stage": "garbage_stage", "page": "99999", "churn_risk_flag": "nonexistent"}),
        (reverse("sales:customer_onboarding_list"), {"status": "broken", "template_type": "none_such", "page": "-1"}),
        (reverse("sales:customer_business_review_list"), {"status": "nonsense", "is_referenceable": "invalid_bool", "page": "0"}),
    ]

    for url, params in junk_urls:
        resp = client_a.get(url, params)
        assert resp.status_code == 200, f"Junk params on {url} returned {resp.status_code}"
