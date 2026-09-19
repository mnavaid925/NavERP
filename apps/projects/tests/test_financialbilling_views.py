"""Projects 7.15 Financial & Billing Management — VIEW tests.
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

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
    _financialbilling_today,
)


# ==============================================================================================
# List Views
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_list_views_render_200(
    client_a,
    financialbilling_rate_card_a,
    financialbilling_billing_run_a,
    financialbilling_revenue_schedule_a,
    financialbilling_payment_record_a,
):
    for url_name in ["rtc_list", "pbr_list", "prs_list", "ppr_list"]:
        res = client_a.get(reverse(f"projects:{url_name}"))
        assert res.status_code == 200
        assert "object_list" in res.context
        assert len(res.context["object_list"]) >= 1


@pytest.mark.django_db
def test_financialbilling_list_views_filter_by_query(
    client_a,
    financialbilling_rate_card_a,
):
    # Match
    res_match = client_a.get(reverse("projects:rtc_list") + "?q=Solutions")
    assert res_match.status_code == 200
    assert len(res_match.context["object_list"]) == 1

    # Non-match
    res_nomatch = client_a.get(reverse("projects:rtc_list") + "?q=NonExistentQueryXYZ")
    assert res_nomatch.status_code == 200
    assert len(res_nomatch.context["object_list"]) == 0


# ==============================================================================================
# Detail Views
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_detail_views_render_200(
    client_a,
    financialbilling_rate_card_a,
    financialbilling_billing_run_a,
    financialbilling_revenue_schedule_a,
    financialbilling_payment_record_a,
):
    urls = [
        reverse("projects:rtc_detail", args=[financialbilling_rate_card_a.pk]),
        reverse("projects:pbr_detail", args=[financialbilling_billing_run_a.pk]),
        reverse("projects:prs_detail", args=[financialbilling_revenue_schedule_a.pk]),
        reverse("projects:ppr_detail", args=[financialbilling_payment_record_a.pk]),
    ]
    for url in urls:
        res = client_a.get(url)
        assert res.status_code == 200


# ==============================================================================================
# Create & Edit Views
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_rate_card_create_and_edit(
    client_a,
    tenant_a,
    financialbilling_project_a,
    financialbilling_party_a,
    projectinitiation_currency,
):
    # Create
    create_url = reverse("projects:rtc_create")
    post_data = {
        "name": "DevOps Specialist",
        "project": financialbilling_project_a.pk,
        "client": financialbilling_party_a.pk,
        "role_name": "DevOps Engineer",
        "hourly_rate": "160.00",
        "expense_markup_pct": "10.00",
        "currency": projectinitiation_currency.pk,
        "is_active": True,
    }
    res_create = client_a.post(create_url, post_data)
    assert res_create.status_code == 302
    created = ProjectRateCard.objects.filter(tenant=tenant_a, name="DevOps Specialist").first()
    assert created is not None

    # Edit
    edit_url = reverse("projects:rtc_edit", args=[created.pk])
    post_data["name"] = "Lead DevOps Specialist"
    res_edit = client_a.post(edit_url, post_data)
    assert res_edit.status_code == 302
    created.refresh_from_db()
    assert created.name == "Lead DevOps Specialist"


# ==============================================================================================
# Delete Views (POST-only)
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_delete_requires_post(
    client_a,
    financialbilling_rate_card_a,
):
    delete_url = reverse("projects:rtc_delete", args=[financialbilling_rate_card_a.pk])
    # GET redirects without deleting
    res_get = client_a.get(delete_url)
    assert res_get.status_code == 302
    assert ProjectRateCard.objects.filter(pk=financialbilling_rate_card_a.pk).exists()

    # POST deletes
    res_post = client_a.post(delete_url)
    assert res_post.status_code == 302
    assert not ProjectRateCard.objects.filter(pk=financialbilling_rate_card_a.pk).exists()


# ==============================================================================================
# Action Views: Billing Run Lifecycle & Invoice Generation
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_billing_run_generate_invoice_creates_invoice_lines(
    client_a,
    tenant_a,
    financialbilling_billing_run_a,
):
    # Approve
    approve_url = reverse("projects:pbr_approve", args=[financialbilling_billing_run_a.pk])
    res_appr = client_a.post(approve_url)
    assert res_appr.status_code == 302
    financialbilling_billing_run_a.refresh_from_db()
    assert financialbilling_billing_run_a.status == "approved"

    # Generate Invoice
    gen_url = reverse("projects:pbr_generate_invoice", args=[financialbilling_billing_run_a.pk])
    res_gen = client_a.post(gen_url)
    assert res_gen.status_code == 302
    financialbilling_billing_run_a.refresh_from_db()
    assert financialbilling_billing_run_a.status == "invoiced"
    assert financialbilling_billing_run_a.accounting_invoice is not None

    inv = financialbilling_billing_run_a.accounting_invoice
    assert inv.lines.count() >= 1
    # Check that tax was calculated with line tax_rate_pct
    first_line = inv.lines.first()
    assert first_line.tax_rate_pct == financialbilling_billing_run_a.tax_rate_pct


# ==============================================================================================
# Computed Financial Boards
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_computed_boards_render_200(
    client_a,
    financialbilling_project_a,
    financialbilling_rate_card_a,
    financialbilling_billing_run_a,
    financialbilling_revenue_schedule_a,
    financialbilling_payment_record_a,
):
    boards = [
        reverse("projects:financial_pnl"),
        reverse("projects:financial_variance"),
        reverse("projects:ar_aging"),
        reverse("projects:cash_flow_forecast"),
    ]
    for b_url in boards:
        res = client_a.get(b_url)
        assert res.status_code == 200

        # Filter with project parameter
        res_filtered = client_a.get(b_url + f"?project={financialbilling_project_a.pk}")
        assert res_filtered.status_code == 200

        # Junk parameter hardening
        res_junk = client_a.get(b_url + "?project=invalid999&q=junktest")
        assert res_junk.status_code == 200
