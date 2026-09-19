"""Projects 7.15 Financial & Billing Management — SECURITY tests.
"""
import pytest
from django.urls import reverse

from apps.projects.models import (
    ProjectBillingRun,
    ProjectPaymentRecord,
    ProjectRateCard,
    ProjectRevenueSchedule,
)
from apps.projects.tests.conftest import (
    _financialbilling_billing_run,
    _financialbilling_payment_record,
    _financialbilling_rate_card,
    _financialbilling_revenue_schedule,
)


# ==============================================================================================
# Cross-Tenant IDOR Protection (Tenant B -> Tenant A pk -> 404)
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_cross_tenant_idor_returns_404(
    client_b,
    financialbilling_rate_card_a,
    financialbilling_billing_run_a,
    financialbilling_revenue_schedule_a,
    financialbilling_payment_record_a,
):
    idor_urls = [
        # Rate Card
        reverse("projects:rtc_detail", args=[financialbilling_rate_card_a.pk]),
        reverse("projects:rtc_edit", args=[financialbilling_rate_card_a.pk]),
        reverse("projects:rtc_delete", args=[financialbilling_rate_card_a.pk]),
        # Billing Run
        reverse("projects:pbr_detail", args=[financialbilling_billing_run_a.pk]),
        reverse("projects:pbr_edit", args=[financialbilling_billing_run_a.pk]),
        reverse("projects:pbr_delete", args=[financialbilling_billing_run_a.pk]),
        reverse("projects:pbr_approve", args=[financialbilling_billing_run_a.pk]),
        reverse("projects:pbr_generate_invoice", args=[financialbilling_billing_run_a.pk]),
        reverse("projects:pbr_dispatch", args=[financialbilling_billing_run_a.pk]),
        reverse("projects:pbr_preview_pdf", args=[financialbilling_billing_run_a.pk]),
        # Revenue Schedule
        reverse("projects:prs_detail", args=[financialbilling_revenue_schedule_a.pk]),
        reverse("projects:prs_edit", args=[financialbilling_revenue_schedule_a.pk]),
        reverse("projects:prs_delete", args=[financialbilling_revenue_schedule_a.pk]),
        reverse("projects:prs_approve", args=[financialbilling_revenue_schedule_a.pk]),
        reverse("projects:prs_recognize", args=[financialbilling_revenue_schedule_a.pk]),
        reverse("projects:prs_lock", args=[financialbilling_revenue_schedule_a.pk]),
        # Payment Record
        reverse("projects:ppr_detail", args=[financialbilling_payment_record_a.pk]),
        reverse("projects:ppr_edit", args=[financialbilling_payment_record_a.pk]),
        reverse("projects:ppr_delete", args=[financialbilling_payment_record_a.pk]),
        reverse("projects:ppr_log_contact", args=[financialbilling_payment_record_a.pk]),
        reverse("projects:ppr_record_promise", args=[financialbilling_payment_record_a.pk]),
        reverse("projects:ppr_escalate", args=[financialbilling_payment_record_a.pk]),
        reverse("projects:ppr_resolve", args=[financialbilling_payment_record_a.pk]),
    ]
    for url in idor_urls:
        # GET
        res_get = client_b.get(url)
        assert res_get.status_code == 404, f"IDOR GET {url} did not return 404, got {res_get.status_code}"

        # POST
        res_post = client_b.post(url, {})
        assert res_post.status_code == 404, f"IDOR POST {url} did not return 404, got {res_post.status_code}"


@pytest.mark.django_db
def test_financialbilling_list_views_isolate_tenants(
    client_b,
    financialbilling_rate_card_a,
    financialbilling_billing_run_a,
    financialbilling_revenue_schedule_a,
    financialbilling_payment_record_a,
):
    for url_name in ["rtc_list", "pbr_list", "prs_list", "ppr_list"]:
        res = client_b.get(reverse(f"projects:{url_name}"))
        assert res.status_code == 200
        # Tenant B must see 0 items belonging to Tenant A
        assert len(res.context["object_list"]) == 0


# ==============================================================================================
# Authentication Enforcement (@login_required)
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_anonymous_redirects_to_login(
    projectinitiation_anon_client,
    financialbilling_rate_card_a,
):
    urls = [
        reverse("projects:rtc_list"),
        reverse("projects:rtc_create"),
        reverse("projects:rtc_detail", args=[financialbilling_rate_card_a.pk]),
        reverse("projects:financial_pnl"),
        reverse("projects:financial_variance"),
        reverse("projects:ar_aging"),
        reverse("projects:cash_flow_forecast"),
    ]
    for url in urls:
        res = projectinitiation_anon_client.get(url)
        assert res.status_code == 302
        assert "/accounts/login/" in res.url


# ==============================================================================================
# CSRF Protection
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_post_without_csrf_is_forbidden(
    projectinitiation_csrf_client,
    financialbilling_rate_card_a,
):
    delete_url = reverse("projects:rtc_delete", args=[financialbilling_rate_card_a.pk])
    res = projectinitiation_csrf_client.post(delete_url, {})
    assert res.status_code == 403


# ==============================================================================================
# Tenantless User Handling
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_tenantless_user_redirected_on_create(
    projectinitiation_tenantless_client,
):
    create_urls = [
        reverse("projects:rtc_create"),
        reverse("projects:pbr_create"),
        reverse("projects:prs_create"),
        reverse("projects:ppr_create"),
    ]
    for url in create_urls:
        res = projectinitiation_tenantless_client.get(url)
        assert res.status_code == 302
        assert res.url == reverse("dashboard:home")
