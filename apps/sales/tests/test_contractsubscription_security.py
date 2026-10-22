"""Security & Multi-Tenant IDOR tests for Sales 8.15 Contract & Subscription Management."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sales.models import (
    CustomerContract,
    CustomerSubscription,
    UsageMeterRecord,
    ContractObligation,
)


# ----------------------------------------------------------------------
# 1. Cross-Tenant IDOR Protection (Tenant A accessing Tenant B -> 404)
# ----------------------------------------------------------------------

@pytest.mark.django_db
def test_contractsubscription_contract_idor_detail(client_a, cs_contract_b):
    url = reverse("sales:customer_contract_detail", kwargs={"pk": cs_contract_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_contractsubscription_contract_idor_edit(client_a, cs_contract_b):
    url = reverse("sales:customer_contract_edit", kwargs={"pk": cs_contract_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_contractsubscription_contract_idor_actions(client_a, cs_contract_b):
    activate_url = reverse("sales:customer_contract_activate", kwargs={"pk": cs_contract_b.pk})
    assert client_a.post(activate_url).status_code == 404

    renew_quote_url = reverse("sales:customer_contract_generate_renewal_quote", kwargs={"pk": cs_contract_b.pk})
    assert client_a.post(renew_quote_url).status_code == 404

    auto_renew_url = reverse("sales:customer_contract_execute_auto_renew", kwargs={"pk": cs_contract_b.pk})
    assert client_a.post(auto_renew_url).status_code == 404

    delete_url = reverse("sales:customer_contract_delete", kwargs={"pk": cs_contract_b.pk})
    assert client_a.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_contractsubscription_subscription_idor(client_a, cs_subscription_b):
    detail_url = reverse("sales:customer_subscription_detail", kwargs={"pk": cs_subscription_b.pk})
    assert client_a.get(detail_url).status_code == 404

    edit_url = reverse("sales:customer_subscription_edit", kwargs={"pk": cs_subscription_b.pk})
    assert client_a.get(edit_url).status_code == 404

    pause_url = reverse("sales:customer_subscription_pause", kwargs={"pk": cs_subscription_b.pk})
    assert client_a.post(pause_url).status_code == 404

    resume_url = reverse("sales:customer_subscription_resume", kwargs={"pk": cs_subscription_b.pk})
    assert client_a.post(resume_url).status_code == 404

    cancel_url = reverse("sales:customer_subscription_cancel", kwargs={"pk": cs_subscription_b.pk})
    assert client_a.post(cancel_url).status_code == 404

    upgrade_url = reverse("sales:customer_subscription_upgrade", kwargs={"pk": cs_subscription_b.pk})
    assert client_a.post(upgrade_url).status_code == 404

    delete_url = reverse("sales:customer_subscription_delete", kwargs={"pk": cs_subscription_b.pk})
    assert client_a.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_contractsubscription_meter_record_idor(client_a, cs_meter_record_b):
    detail_url = reverse("sales:usage_meter_record_detail", kwargs={"pk": cs_meter_record_b.pk})
    assert client_a.get(detail_url).status_code == 404

    edit_url = reverse("sales:usage_meter_record_edit", kwargs={"pk": cs_meter_record_b.pk})
    assert client_a.get(edit_url).status_code == 404

    calc_url = reverse("sales:usage_meter_record_calculate", kwargs={"pk": cs_meter_record_b.pk})
    assert client_a.post(calc_url).status_code == 404

    inv_url = reverse("sales:usage_meter_record_invoice", kwargs={"pk": cs_meter_record_b.pk})
    assert client_a.post(inv_url).status_code == 404

    del_url = reverse("sales:usage_meter_record_delete", kwargs={"pk": cs_meter_record_b.pk})
    assert client_a.post(del_url).status_code == 404


@pytest.mark.django_db
def test_contractsubscription_obligation_idor(client_a, cs_obligation_b):
    detail_url = reverse("sales:contract_obligation_detail", kwargs={"pk": cs_obligation_b.pk})
    assert client_a.get(detail_url).status_code == 404

    edit_url = reverse("sales:contract_obligation_edit", kwargs={"pk": cs_obligation_b.pk})
    assert client_a.get(edit_url).status_code == 404

    fulfill_url = reverse("sales:contract_obligation_fulfill", kwargs={"pk": cs_obligation_b.pk})
    assert client_a.post(fulfill_url).status_code == 404

    breach_url = reverse("sales:contract_obligation_breach", kwargs={"pk": cs_obligation_b.pk})
    assert client_a.post(breach_url).status_code == 404

    del_url = reverse("sales:contract_obligation_delete", kwargs={"pk": cs_obligation_b.pk})
    assert client_a.post(del_url).status_code == 404


# ----------------------------------------------------------------------
# 2. Authentication Gates (@login_required -> 302 to login)
# ----------------------------------------------------------------------

@pytest.mark.django_db
def test_contractsubscription_unauthenticated_access_redirects():
    from django.test import Client
    anon = Client()
    routes = [
        reverse("sales:contract_subscription_workspace"),
        reverse("sales:renewal_automation_dashboard"),
        reverse("sales:customer_contract_list"),
        reverse("sales:customer_contract_create"),
        reverse("sales:customer_subscription_list"),
        reverse("sales:customer_subscription_create"),
        reverse("sales:usage_meter_record_list"),
        reverse("sales:usage_meter_record_create"),
        reverse("sales:contract_obligation_list"),
        reverse("sales:contract_obligation_create"),
    ]
    for url in routes:
        resp = anon.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url


# ----------------------------------------------------------------------
# 3. Authorization & Tenant Admin Gates (@tenant_admin_required -> 403)
# ----------------------------------------------------------------------

@pytest.mark.django_db
def test_contractsubscription_non_admin_delete_forbidden(member_client, cs_contract_a, cs_subscription_a, cs_meter_record_a):
    contract_del = reverse("sales:customer_contract_delete", kwargs={"pk": cs_contract_a.pk})
    assert member_client.post(contract_del).status_code == 403

    sub_del = reverse("sales:customer_subscription_delete", kwargs={"pk": cs_subscription_a.pk})
    assert member_client.post(sub_del).status_code == 403

    meter_del = reverse("sales:usage_meter_record_delete", kwargs={"pk": cs_meter_record_a.pk})
    assert member_client.post(meter_del).status_code == 403


# ----------------------------------------------------------------------
# 4. View-Level Status Guards on State Mutations
# ----------------------------------------------------------------------

@pytest.mark.django_db
def test_contractsubscription_activate_guard_on_active_contract(client_a, cs_contract_a):
    cs_contract_a.status = "active"
    cs_contract_a.save()

    url = reverse("sales:customer_contract_activate", kwargs={"pk": cs_contract_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    # Status must still be active, not changed or corrupted
    cs_contract_a.refresh_from_db()
    assert cs_contract_a.status == "active"


@pytest.mark.django_db
def test_contractsubscription_meter_calculate_guard_on_invoiced(client_a, cs_meter_record_a):
    cs_meter_record_a.status = "invoiced"
    cs_meter_record_a.billable_overage_units = Decimal("500.00")
    cs_meter_record_a.overage_total_charge = Decimal("1000.00")
    cs_meter_record_a.save()

    url = reverse("sales:usage_meter_record_calculate", kwargs={"pk": cs_meter_record_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    # Status must NOT be reset to calculated; billed figures must remain intact
    cs_meter_record_a.refresh_from_db()
    assert cs_meter_record_a.status == "invoiced"
    assert cs_meter_record_a.overage_total_charge == Decimal("1000.00")


@pytest.mark.django_db
def test_contractsubscription_auto_renew_guard_on_inactive_contract(client_a, cs_contract_a):
    cs_contract_a.status = "terminated"
    cs_contract_a.auto_renew = True
    cs_contract_a.save()

    url = reverse("sales:customer_contract_execute_auto_renew", kwargs={"pk": cs_contract_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    # Terminated contract must not be extended
    cs_contract_a.refresh_from_db()
    assert cs_contract_a.status == "terminated"
