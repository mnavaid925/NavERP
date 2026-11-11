"""Security, multi-tenant isolation, IDOR, and authorization tests for Module 11.10: Lease & Rental Management."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.models.AssetLeaseRental.AssetLeaseSchedules import AssetLeaseSchedule
from apps.assets.models.AssetLeaseRental.AssetLeaseModifications import AssetLeaseModification
from apps.assets.models.AssetLeaseRental.AssetLeaseBuyAnalyses import AssetLeaseBuyAnalysis


# ==============================================================================
# 1. Multi-Tenant Isolation & IDOR Protection Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetleaserental_idor_detail_and_edit_blocked(
    client_a, lease_contract_b, lease_schedule_b, lease_modification_b, lease_buy_analysis_b
):
    """Acme tenant user accessing Globex records via GET must return HTTP 404."""
    routes = [
        ("assets:asset_lease_contract_detail", lease_contract_b.pk),
        ("assets:asset_lease_contract_edit", lease_contract_b.pk),
        ("assets:asset_lease_schedule_detail", lease_schedule_b.pk),
        ("assets:asset_lease_schedule_edit", lease_schedule_b.pk),
        ("assets:asset_lease_modification_detail", lease_modification_b.pk),
        ("assets:asset_lease_modification_edit", lease_modification_b.pk),
        ("assets:asset_lease_buy_analysis_detail", lease_buy_analysis_b.pk),
        ("assets:asset_lease_buy_analysis_edit", lease_buy_analysis_b.pk),
    ]
    for url_name, pk in routes:
        resp = client_a.get(reverse(url_name, kwargs={"pk": pk}))
        assert resp.status_code == 404, f"IDOR vulnerability on {url_name} for pk={pk}"


@pytest.mark.django_db
def test_assetleaserental_idor_actions_blocked(
    client_a, lease_contract_b, lease_schedule_b, lease_modification_b, lease_buy_analysis_b
):
    """Acme tenant user posting actions against Globex records must return HTTP 404."""
    actions = [
        ("assets:asset_lease_contract_calculate", lease_contract_b.pk),
        ("assets:asset_lease_contract_activate", lease_contract_b.pk),
        ("assets:asset_lease_contract_terminate", lease_contract_b.pk),
        ("assets:asset_lease_contract_delete", lease_contract_b.pk),
        ("assets:asset_lease_schedule_mark_paid", lease_schedule_b.pk),
        ("assets:asset_lease_schedule_accrue", lease_schedule_b.pk),
        ("assets:asset_lease_schedule_delete", lease_schedule_b.pk),
        ("assets:asset_lease_modification_approve", lease_modification_b.pk),
        ("assets:asset_lease_modification_delete", lease_modification_b.pk),
        ("assets:asset_lease_buy_analysis_evaluate", lease_buy_analysis_b.pk),
        ("assets:asset_lease_buy_analysis_delete", lease_buy_analysis_b.pk),
    ]
    for url_name, pk in actions:
        resp = client_a.post(reverse(url_name, kwargs={"pk": pk}))
        assert resp.status_code == 404, f"IDOR action vulnerability on {url_name} for pk={pk}"


@pytest.mark.django_db
def test_assetleaserental_list_views_tenant_isolation(
    client_a,
    client_b,
    lease_contract_a,
    lease_contract_b,
    lease_schedule_a,
    lease_schedule_b,
    lease_modification_a,
    lease_modification_b,
    lease_buy_analysis_a,
    lease_buy_analysis_b,
):
    """List views strictly filter data by tenant: Tenant A sees only A; Tenant B sees only B."""
    # Contracts
    resp_ctr_a = client_a.get(reverse("assets:asset_lease_contract_list"))
    assert lease_contract_a in resp_ctr_a.context["leases"]
    assert lease_contract_b not in resp_ctr_a.context["leases"]

    resp_ctr_b = client_b.get(reverse("assets:asset_lease_contract_list"))
    assert lease_contract_b in resp_ctr_b.context["leases"]
    assert lease_contract_a not in resp_ctr_b.context["leases"]

    # Schedules
    resp_sch_a = client_a.get(reverse("assets:asset_lease_schedule_list"))
    assert lease_schedule_a in resp_sch_a.context["schedules"]
    assert lease_schedule_b not in resp_sch_a.context["schedules"]

    resp_sch_b = client_b.get(reverse("assets:asset_lease_schedule_list"))
    assert lease_schedule_b in resp_sch_b.context["schedules"]
    assert lease_schedule_a not in resp_sch_b.context["schedules"]

    # Modifications
    resp_mod_a = client_a.get(reverse("assets:asset_lease_modification_list"))
    assert lease_modification_a in resp_mod_a.context["modifications"]
    assert lease_modification_b not in resp_mod_a.context["modifications"]

    resp_mod_b = client_b.get(reverse("assets:asset_lease_modification_list"))
    assert lease_modification_b in resp_mod_b.context["modifications"]
    assert lease_modification_a not in resp_mod_b.context["modifications"]

    # Buy Analyses
    resp_ba_a = client_a.get(reverse("assets:asset_lease_buy_analysis_list"))
    assert lease_buy_analysis_a in resp_ba_a.context["analyses"]
    assert lease_buy_analysis_b not in resp_ba_a.context["analyses"]

    resp_ba_b = client_b.get(reverse("assets:asset_lease_buy_analysis_list"))
    assert lease_buy_analysis_b in resp_ba_b.context["analyses"]
    assert lease_buy_analysis_a not in resp_ba_b.context["analyses"]


# ==============================================================================
# 2. Authentication & Authorization Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetleaserental_login_required(
    client, lease_contract_a, lease_schedule_a, lease_modification_a, lease_buy_analysis_a
):
    """Anonymous client accessing any sub-module endpoint is redirected to login (HTTP 302)."""
    urls = [
        reverse("assets:asset_lease_contract_list"),
        reverse("assets:asset_lease_contract_create"),
        reverse("assets:asset_lease_contract_detail", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_contract_edit", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_schedule_list"),
        reverse("assets:asset_lease_schedule_create"),
        reverse("assets:asset_lease_schedule_detail", kwargs={"pk": lease_schedule_a.pk}),
        reverse("assets:asset_lease_schedule_edit", kwargs={"pk": lease_schedule_a.pk}),
        reverse("assets:asset_lease_modification_list"),
        reverse("assets:asset_lease_modification_create"),
        reverse("assets:asset_lease_modification_detail", kwargs={"pk": lease_modification_a.pk}),
        reverse("assets:asset_lease_modification_edit", kwargs={"pk": lease_modification_a.pk}),
        reverse("assets:asset_lease_buy_analysis_list"),
        reverse("assets:asset_lease_buy_analysis_create"),
        reverse("assets:asset_lease_buy_analysis_detail", kwargs={"pk": lease_buy_analysis_a.pk}),
        reverse("assets:asset_lease_buy_analysis_edit", kwargs={"pk": lease_buy_analysis_a.pk}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect to login for {url}"
        assert "/accounts/login/" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_assetleaserental_require_post_enforced(
    client_a, lease_contract_a, lease_schedule_a, lease_modification_a, lease_buy_analysis_a
):
    """Mutating state endpoints require HTTP POST; GET returns HTTP 405 Method Not Allowed."""
    post_only_urls = [
        reverse("assets:asset_lease_contract_calculate", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_contract_activate", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_contract_terminate", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_contract_delete", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_schedule_mark_paid", kwargs={"pk": lease_schedule_a.pk}),
        reverse("assets:asset_lease_schedule_accrue", kwargs={"pk": lease_schedule_a.pk}),
        reverse("assets:asset_lease_schedule_delete", kwargs={"pk": lease_schedule_a.pk}),
        reverse("assets:asset_lease_modification_approve", kwargs={"pk": lease_modification_a.pk}),
        reverse("assets:asset_lease_modification_delete", kwargs={"pk": lease_modification_a.pk}),
        reverse("assets:asset_lease_buy_analysis_evaluate", kwargs={"pk": lease_buy_analysis_a.pk}),
        reverse("assets:asset_lease_buy_analysis_delete", kwargs={"pk": lease_buy_analysis_a.pk}),
    ]
    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 on GET for {url}"


@pytest.mark.django_db
def test_assetleaserental_tenant_admin_required_actions(
    member_client, lease_contract_a, lease_schedule_a, lease_modification_a, lease_buy_analysis_a
):
    """Privileged actions decorated with @tenant_admin_required reject non-admin members with HTTP 403."""
    admin_only_urls = [
        reverse("assets:asset_lease_contract_activate", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_contract_delete", kwargs={"pk": lease_contract_a.pk}),
        reverse("assets:asset_lease_schedule_delete", kwargs={"pk": lease_schedule_a.pk}),
        reverse("assets:asset_lease_modification_approve", kwargs={"pk": lease_modification_a.pk}),
        reverse("assets:asset_lease_modification_delete", kwargs={"pk": lease_modification_a.pk}),
        reverse("assets:asset_lease_buy_analysis_delete", kwargs={"pk": lease_buy_analysis_a.pk}),
    ]
    for url in admin_only_urls:
        resp = member_client.post(url)
        assert resp.status_code == 403, f"Expected 403 on non-admin POST for {url}"


# ==============================================================================
# 3. Cross-Tenant Data Injection Prevention
# ==============================================================================

@pytest.mark.django_db
def test_assetleaserental_cross_tenant_injection_prevented(
    client_a, vendor_party_b, category_root_b
):
    """Submitting foreign tenant FKs in contract create form fails form validation."""
    today = timezone.now().date()
    data = {
        "title": "Cross Tenant Exploit Contract",
        "lessor": vendor_party_b.pk,
        "category": category_root_b.pk,
        "inception_date": today.strftime("%Y-%m-%d"),
        "commencement_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today + timezone.timedelta(days=365)).strftime("%Y-%m-%d"),
        "lease_term_months": 12,
        "payment_amount": "1000.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "5.0000",
        "status": "draft",
    }
    resp = client_a.post(reverse("assets:asset_lease_contract_create"), data)
    assert resp.status_code == 200  # Stays on form with errors
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert not AssetLeaseContract.objects.filter(title="Cross Tenant Exploit Contract").exists()
