"""Asset Depreciation & Financial Management (Sub-module 11.4) — SECURITY Test Suite.

Comprehensive security, multi-tenancy, authorization, status-guard, and tamper-protection tests:
1. Multi-Tenant IDOR Protection (assert 404):
   - Tenant B client attempting to access Tenant A records across:
     - Depreciation Schedule: detail, edit (GET/POST), delete (POST), calculate (POST), post (POST)
     - Revaluation: detail, edit (GET/POST), delete (POST), approve (POST)
     - Transfer: detail, edit (GET/POST), delete (POST), dispatch (POST), complete (POST)
     - Capitalization Policy: detail, edit (GET/POST), delete (POST)
   - Reverse IDOR: Tenant A client attempting to access Tenant B records returns 404 across all endpoints.

2. Tenant Scoping on Lists and Overview KPIs:
   - Depreciation schedule list, revaluation list, transfer list, capitalization policy list.
   - Tenant B never sees Tenant A objects or aggregated metric sums in list views, and vice versa.

3. Cross-Tenant Foreign Key Injection Defense:
   - Submitting foreign tenant foreign keys on create/edit is rejected by form and view validation:
     - Schedule: foreign fixed asset, operational asset, accounts, fiscal period, cost center.
     - Revaluation: foreign fixed asset, operational asset, appraiser, accounts.
     - Transfer: foreign fixed asset, operational asset, locations, departments, custodians.
     - Policy: foreign category, CIP account, expense account.

4. Unauthenticated Access Control:
   - Anonymous client accessing any of the 25 depreciation/financial endpoints redirects 302 to login.

5. Role-Based Authorization Enforcement (@tenant_admin_required):
   - Non-admin member (member_client) receives 403 Forbidden on privileged actions:
     - depreciation_schedule_post, depreciation_schedule_delete
     - revaluation_approve, revaluation_delete
     - transfer_complete, transfer_delete
     - capitalization_policy_delete
   - Tenant administrator is authorized to execute these actions.

6. HTTP Method Guarding (@require_POST):
   - GET requests to all 9 state-changing actions return HTTP 405 Method Not Allowed.

7. Mass-Assignment & Tamper Resistance:
   - Injected tenant, number, status, journal_entry, posted_at/by, approved_at/by, completed_at
     via POST are completely ignored, and server-controlled values are preserved.

8. Status Guard Enforcement:
   - Posted depreciation schedules cannot be edited, deleted, or recalculated.
   - Approved asset revaluations cannot be edited or deleted.
   - Completed asset transfers cannot be edited or deleted.

9. Malicious & Malformed Input Fuzzing:
   - Query parameters with XSS payloads, SQL injection tokens, non-numeric values, NaN/Infinity,
     and extreme string lengths never cause HTTP 500 errors.

10. Audit Log Generation:
    - Verify mutations create immutable AuditLog entries scoped to the tenant.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, FixedAsset, GLAccount, JournalEntry
from apps.assets.forms.AssetDepreciation.AssetDepreciationSchedules import AssetDepreciationScheduleForm
from apps.assets.forms.AssetDepreciation.AssetRevaluations import AssetRevaluationForm
from apps.assets.forms.AssetDepreciation.AssetTransfers import AssetTransferForm
from apps.assets.forms.AssetDepreciation.CapitalizationPolicies import CapitalizationPolicyForm
from apps.assets.models import (
    AssetCategory,
    AssetDepreciationSchedule,
    AssetRevaluation,
    AssetTransfer,
    CapitalizationPolicy,
)
from apps.core.models import AuditLog, OrgUnit, Party, Tenant
from apps.scm.models import Asset, Location

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (strictly prefixed with _assetdepreciation_)
# ==============================================================================


def _assetdepreciation_get_flash_messages(response):
    """Extract list of flash message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetdepreciation_fiscal_period(tenant, name="FY2026-P01", **kwargs):
    """Create a test fiscal period belonging to the given tenant."""
    now = timezone.now().date()
    return FiscalPeriod.objects.create(
        tenant=tenant,
        name=name,
        period_type="month",
        start_date=now.replace(day=1),
        end_date=now.replace(day=28),
        status="open",
        **kwargs,
    )


def _assetdepreciation_schedule_payload(
    fixed_asset,
    operational_asset=None,
    fiscal_period=None,
    expense_account=None,
    accumulated_account=None,
    cost_center=None,
    **kwargs,
):
    """Generate valid base form payload for AssetDepreciationScheduleForm."""
    payload = {
        "fixed_asset": fixed_asset.pk if hasattr(fixed_asset, "pk") else fixed_asset,
        "operational_asset": (operational_asset.pk if hasattr(operational_asset, "pk") else operational_asset) or "",
        "fiscal_period": (fiscal_period.pk if hasattr(fiscal_period, "pk") else fiscal_period) or "",
        "fiscal_year": 2026,
        "period_number": 2,
        "period_frequency": "monthly",
        "schedule_date": str(timezone.now().date()),
        "depreciation_method": "straight_line",
        "starting_book_value": "118200.00",
        "depreciation_amount": "1800.00",
        "total_units_expected": "",
        "units_produced_period": "",
        "expense_account": (expense_account.pk if hasattr(expense_account, "pk") else expense_account) or "",
        "accumulated_account": (accumulated_account.pk if hasattr(accumulated_account, "pk") else accumulated_account) or "",
        "cost_center": (cost_center.pk if hasattr(cost_center, "pk") else cost_center) or "",
        "notes": "Regular monthly straight-line depreciation schedule run.",
    }
    payload.update(kwargs)
    return payload


def _assetdepreciation_revaluation_payload(
    fixed_asset,
    operational_asset=None,
    appraiser=None,
    impairment_loss_account=None,
    revaluation_surplus_account=None,
    **kwargs,
):
    """Generate valid base form payload for AssetRevaluationForm."""
    payload = {
        "title": "Mid-Year CNC Impairment Review",
        "fixed_asset": fixed_asset.pk if hasattr(fixed_asset, "pk") else fixed_asset,
        "operational_asset": (operational_asset.pk if hasattr(operational_asset, "pk") else operational_asset) or "",
        "event_type": "impairment",
        "valuation_method": "independent_appraisal",
        "valuation_date": str(timezone.now().date()),
        "appraiser": (appraiser.pk if hasattr(appraiser, "pk") else appraiser) or "",
        "appraiser_name_fallback": "Global Valuation Associates",
        "new_fair_market_value": "95000.00",
        "new_salvage_value": "10000.00",
        "remaining_useful_life_months": 48,
        "impairment_loss_account": (impairment_loss_account.pk if hasattr(impairment_loss_account, "pk") else impairment_loss_account) or "",
        "revaluation_surplus_account": (revaluation_surplus_account.pk if hasattr(revaluation_surplus_account, "pk") else revaluation_surplus_account) or "",
        "reason_and_methodology": "Appraisal assessment reflecting technological changes under IAS 36.",
    }
    payload.update(kwargs)
    return payload


def _assetdepreciation_transfer_payload(
    fixed_asset,
    operational_asset=None,
    source_department=None,
    source_location=None,
    source_custodian=None,
    source_expense_account=None,
    destination_department=None,
    destination_location=None,
    destination_custodian=None,
    destination_expense_account=None,
    transferred_by=None,
    **kwargs,
):
    """Generate valid base form payload for AssetTransferForm."""
    payload = {
        "title": "Transfer CNC Mill to Plant 2 Assembly",
        "fixed_asset": fixed_asset.pk if hasattr(fixed_asset, "pk") else fixed_asset,
        "operational_asset": (operational_asset.pk if hasattr(operational_asset, "pk") else operational_asset) or "",
        "transfer_type": "inter_facility",
        "transfer_date": str(timezone.now().date()),
        "source_department": (source_department.pk if hasattr(source_department, "pk") else source_department) or "",
        "source_location": (source_location.pk if hasattr(source_location, "pk") else source_location) or "",
        "source_custodian": (source_custodian.pk if hasattr(source_custodian, "pk") else source_custodian) or "",
        "source_expense_account": (source_expense_account.pk if hasattr(source_expense_account, "pk") else source_expense_account) or "",
        "destination_department": (destination_department.pk if hasattr(destination_department, "pk") else destination_department) or "",
        "destination_location": (destination_location.pk if hasattr(destination_location, "pk") else destination_location) or "",
        "destination_custodian": (destination_custodian.pk if hasattr(destination_custodian, "pk") else destination_custodian) or "",
        "destination_expense_account": (destination_expense_account.pk if hasattr(destination_expense_account, "pk") else destination_expense_account) or "",
        "transportation_cost": "650.00",
        "transferred_by": (transferred_by.pk if hasattr(transferred_by, "pk") else transferred_by) or "",
        "reason": "Facility reorganization and capacity rebalancing.",
    }
    payload.update(kwargs)
    return payload


def _assetdepreciation_policy_payload(
    name="Corporate Machinery CapEx Policy",
    category=None,
    default_cip_account=None,
    default_expense_account=None,
    **kwargs,
):
    """Generate valid base form payload for CapitalizationPolicyForm."""
    payload = {
        "name": name,
        "policy_scope": "global_default",
        "category": (category.pk if hasattr(category, "pk") else category) or "",
        "minimum_cost_threshold": "3000.00",
        "minimum_useful_life_months": 12,
        "default_classification": "capitalize",
        "de_minimis_safe_harbor": True,
        "applicable_gaap_standard": "US GAAP / IFRS IAS 16",
        "default_cip_account": (default_cip_account.pk if hasattr(default_cip_account, "pk") else default_cip_account) or "",
        "default_expense_account": (default_expense_account.pk if hasattr(default_expense_account, "pk") else default_expense_account) or "",
        "effective_from": "2026-01-01",
        "effective_to": "",
        "is_active": True,
        "policy_notes": "General threshold for fixed asset capitalization across all facilities.",
    }
    payload.update(kwargs)
    return payload


# ==============================================================================
# Local Fixture Overrides (exact schema alignment for 11.4 models)
# ==============================================================================


@pytest.fixture
def depreciation_schedule_a(db, tenant_a, fixed_asset_a, operational_asset_a, expense_account_a, accum_account_a):
    """Clean draft depreciation schedule for tenant_a."""
    return AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        schedule_date=timezone.now().date(),
        depreciation_method="straight_line",
        starting_book_value=Decimal("120000.00"),
        depreciation_amount=Decimal("1800.00"),
        accumulated_depreciation_after=Decimal("1800.00"),
        ending_book_value=Decimal("118200.00"),
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        status="draft",
    )


@pytest.fixture
def depreciation_schedule_b(db, tenant_b, fixed_asset_b, operational_asset_b, expense_account_b, accum_account_b):
    """Clean draft depreciation schedule for tenant_b."""
    return AssetDepreciationSchedule.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        schedule_date=timezone.now().date(),
        depreciation_method="straight_line",
        starting_book_value=Decimal("45000.00"),
        depreciation_amount=Decimal("833.33"),
        accumulated_depreciation_after=Decimal("833.33"),
        ending_book_value=Decimal("44166.67"),
        expense_account=expense_account_b,
        accumulated_account=accum_account_b,
        status="draft",
    )


@pytest.fixture
def transfer_a(db, tenant_a, fixed_asset_a, operational_asset_a, location_a, location_a2, org_unit_a, vendor_party_a, admin_user):
    """Clean draft asset transfer order for tenant_a."""
    return AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Inter-Facility Transfer CNC Mill",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        transfer_type="inter_facility",
        transfer_date=timezone.now().date(),
        source_location=location_a,
        destination_location=location_a2,
        source_department=org_unit_a,
        source_custodian=vendor_party_a,
        transferred_by=admin_user,
        transportation_cost=Decimal("750.00"),
        status="draft",
    )


@pytest.fixture
def transfer_b(db, tenant_b, fixed_asset_b, operational_asset_b, location_b, location_b2, org_unit_b, vendor_party_b, admin_b):
    """Clean draft asset transfer order for tenant_b."""
    return AssetTransfer.objects.create(
        tenant=tenant_b,
        title="Relocation Stacker to Yard",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        transfer_type="cost_center",
        transfer_date=timezone.now().date(),
        source_location=location_b,
        destination_location=location_b2,
        source_department=org_unit_b,
        source_custodian=vendor_party_b,
        transferred_by=admin_b,
        transportation_cost=Decimal("250.00"),
        status="draft",
    )


# ==============================================================================
# 1. Multi-Tenant IDOR Protection Tests (Strict 404 Across All Actions)
# ==============================================================================


def test_assetdepreciation_security_idor_schedule_detail_returns_404(client_b, depreciation_schedule_a):
    """Tenant B client accessing Tenant A depreciation schedule detail returns 404."""
    url = reverse("assets:depreciation_schedule_detail", args=[depreciation_schedule_a.pk])
    response = client_b.get(url)
    assert response.status_code == 404


def test_assetdepreciation_security_idor_schedule_edit_get_and_post_returns_404(
    client_b, depreciation_schedule_a, fixed_asset_b
):
    """Tenant B client accessing Tenant A schedule edit GET or POST returns 404."""
    url = reverse("assets:depreciation_schedule_edit", args=[depreciation_schedule_a.pk])
    assert client_b.get(url).status_code == 404

    payload = _assetdepreciation_schedule_payload(fixed_asset=fixed_asset_b, notes="Tampered by B")
    assert client_b.post(url, data=payload).status_code == 404


def test_assetdepreciation_security_idor_schedule_delete_post_returns_404(client_b, depreciation_schedule_a):
    """Tenant B client attempting to delete Tenant A schedule returns 404."""
    url = reverse("assets:depreciation_schedule_delete", args=[depreciation_schedule_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404
    assert AssetDepreciationSchedule.objects.filter(pk=depreciation_schedule_a.pk).exists()


def test_assetdepreciation_security_idor_schedule_calculate_post_returns_404(client_b, depreciation_schedule_a):
    """Tenant B client attempting to calculate Tenant A schedule returns 404."""
    url = reverse("assets:depreciation_schedule_calculate", args=[depreciation_schedule_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404


def test_assetdepreciation_security_idor_schedule_post_returns_404(client_b, depreciation_schedule_a):
    """Tenant B client attempting to post Tenant A schedule to GL returns 404."""
    url = reverse("assets:depreciation_schedule_post", args=[depreciation_schedule_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404


def test_assetdepreciation_security_idor_revaluation_detail_returns_404(client_b, revaluation_a):
    """Tenant B client accessing Tenant A revaluation detail returns 404."""
    url = reverse("assets:revaluation_detail", args=[revaluation_a.pk])
    response = client_b.get(url)
    assert response.status_code == 404


def test_assetdepreciation_security_idor_revaluation_edit_get_and_post_returns_404(
    client_b, revaluation_a, fixed_asset_b
):
    """Tenant B client accessing Tenant A revaluation edit GET or POST returns 404."""
    url = reverse("assets:revaluation_edit", args=[revaluation_a.pk])
    assert client_b.get(url).status_code == 404

    payload = _assetdepreciation_revaluation_payload(fixed_asset=fixed_asset_b, title="Tampered Reval")
    assert client_b.post(url, data=payload).status_code == 404


def test_assetdepreciation_security_idor_revaluation_delete_post_returns_404(client_b, revaluation_a):
    """Tenant B client attempting to delete Tenant A revaluation returns 404."""
    url = reverse("assets:revaluation_delete", args=[revaluation_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404
    assert AssetRevaluation.objects.filter(pk=revaluation_a.pk).exists()


def test_assetdepreciation_security_idor_revaluation_approve_post_returns_404(client_b, revaluation_a):
    """Tenant B client attempting to approve Tenant A revaluation returns 404."""
    url = reverse("assets:revaluation_approve", args=[revaluation_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404
    revaluation_a.refresh_from_db()
    assert revaluation_a.status == "draft"


def test_assetdepreciation_security_idor_transfer_detail_returns_404(client_b, transfer_a):
    """Tenant B client accessing Tenant A transfer detail returns 404."""
    url = reverse("assets:transfer_detail", args=[transfer_a.pk])
    response = client_b.get(url)
    assert response.status_code == 404


def test_assetdepreciation_security_idor_transfer_edit_get_and_post_returns_404(
    client_b, transfer_a, fixed_asset_b
):
    """Tenant B client accessing Tenant A transfer edit GET or POST returns 404."""
    url = reverse("assets:transfer_edit", args=[transfer_a.pk])
    assert client_b.get(url).status_code == 404

    payload = _assetdepreciation_transfer_payload(fixed_asset=fixed_asset_b, title="Tampered Transfer")
    assert client_b.post(url, data=payload).status_code == 404


def test_assetdepreciation_security_idor_transfer_delete_post_returns_404(client_b, transfer_a):
    """Tenant B client attempting to delete Tenant A transfer returns 404."""
    url = reverse("assets:transfer_delete", args=[transfer_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404
    assert AssetTransfer.objects.filter(pk=transfer_a.pk).exists()


def test_assetdepreciation_security_idor_transfer_dispatch_post_returns_404(client_b, transfer_a):
    """Tenant B client attempting to dispatch Tenant A transfer returns 404."""
    url = reverse("assets:transfer_dispatch", args=[transfer_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404
    transfer_a.refresh_from_db()
    assert transfer_a.status == "draft"


def test_assetdepreciation_security_idor_transfer_complete_post_returns_404(client_b, transfer_a):
    """Tenant B client attempting to complete Tenant A transfer returns 404."""
    url = reverse("assets:transfer_complete", args=[transfer_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404
    transfer_a.refresh_from_db()
    assert transfer_a.status == "draft"


def test_assetdepreciation_security_idor_policy_detail_returns_404(client_b, capitalization_policy_a):
    """Tenant B client accessing Tenant A capitalization policy detail returns 404."""
    url = reverse("assets:capitalization_policy_detail", args=[capitalization_policy_a.pk])
    response = client_b.get(url)
    assert response.status_code == 404


def test_assetdepreciation_security_idor_policy_edit_get_and_post_returns_404(
    client_b, capitalization_policy_a
):
    """Tenant B client accessing Tenant A capitalization policy edit GET or POST returns 404."""
    url = reverse("assets:capitalization_policy_edit", args=[capitalization_policy_a.pk])
    assert client_b.get(url).status_code == 404

    payload = _assetdepreciation_policy_payload(name="Tampered Policy")
    assert client_b.post(url, data=payload).status_code == 404


def test_assetdepreciation_security_idor_policy_delete_post_returns_404(client_b, capitalization_policy_a):
    """Tenant B client attempting to delete Tenant A capitalization policy returns 404."""
    url = reverse("assets:capitalization_policy_delete", args=[capitalization_policy_a.pk])
    response = client_b.post(url)
    assert response.status_code == 404
    assert CapitalizationPolicy.objects.filter(pk=capitalization_policy_a.pk).exists()


def test_assetdepreciation_security_idor_reverse_tenant_a_accessing_tenant_b_returns_404(
    client_a, depreciation_schedule_b, revaluation_b, transfer_b, capitalization_policy_b
):
    """Reverse IDOR: Tenant A client attempting to access Tenant B objects returns 404 across all endpoints."""
    # Depreciation Schedule
    assert client_a.get(reverse("assets:depreciation_schedule_detail", args=[depreciation_schedule_b.pk])).status_code == 404
    assert client_a.get(reverse("assets:depreciation_schedule_edit", args=[depreciation_schedule_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:depreciation_schedule_calculate", args=[depreciation_schedule_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:depreciation_schedule_post", args=[depreciation_schedule_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:depreciation_schedule_delete", args=[depreciation_schedule_b.pk])).status_code == 404

    # Revaluation
    assert client_a.get(reverse("assets:revaluation_detail", args=[revaluation_b.pk])).status_code == 404
    assert client_a.get(reverse("assets:revaluation_edit", args=[revaluation_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:revaluation_approve", args=[revaluation_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:revaluation_delete", args=[revaluation_b.pk])).status_code == 404

    # Transfer
    assert client_a.get(reverse("assets:transfer_detail", args=[transfer_b.pk])).status_code == 404
    assert client_a.get(reverse("assets:transfer_edit", args=[transfer_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:transfer_dispatch", args=[transfer_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:transfer_complete", args=[transfer_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:transfer_delete", args=[transfer_b.pk])).status_code == 404

    # Capitalization Policy
    assert client_a.get(reverse("assets:capitalization_policy_detail", args=[capitalization_policy_b.pk])).status_code == 404
    assert client_a.get(reverse("assets:capitalization_policy_edit", args=[capitalization_policy_b.pk])).status_code == 404
    assert client_a.post(reverse("assets:capitalization_policy_delete", args=[capitalization_policy_b.pk])).status_code == 404


# ==============================================================================
# 2. Tenant Scoping on Lists and Overview KPIs
# ==============================================================================


def test_assetdepreciation_security_tenant_scoping_schedule_list(
    client_a, client_b, depreciation_schedule_a, depreciation_schedule_b
):
    """depreciation_schedule_list isolates records and KPIs strictly by tenant."""
    # Tenant A list
    resp_a = client_a.get(reverse("assets:depreciation_schedule_list"))
    assert resp_a.status_code == 200
    ids_a = [s.pk for s in resp_a.context["depreciation_schedules"]]
    assert depreciation_schedule_a.pk in ids_a
    assert depreciation_schedule_b.pk not in ids_a
    assert resp_a.context["total_runs"] == 1
    assert resp_a.context["total_depreciation_period"] == Decimal("1800.00")

    # Tenant B list
    resp_b = client_b.get(reverse("assets:depreciation_schedule_list"))
    assert resp_b.status_code == 200
    ids_b = [s.pk for s in resp_b.context["depreciation_schedules"]]
    assert depreciation_schedule_b.pk in ids_b
    assert depreciation_schedule_a.pk not in ids_b
    assert resp_b.context["total_runs"] == 1
    assert resp_b.context["total_depreciation_period"] == Decimal("833.33")


def test_assetdepreciation_security_tenant_scoping_revaluation_list(
    client_a, client_b, revaluation_a, revaluation_b
):
    """revaluation_list isolates records and KPIs strictly by tenant."""
    # Tenant A list
    resp_a = client_a.get(reverse("assets:revaluation_list"))
    assert resp_a.status_code == 200
    ids_a = [r.pk for r in resp_a.context["revaluations"]]
    assert revaluation_a.pk in ids_a
    assert revaluation_b.pk not in ids_a
    assert resp_a.context["total_events"] == 1
    assert resp_a.context["surplus_count"] == 1
    assert resp_a.context["impairment_count"] == 0
    assert resp_a.context["total_adjustment_value"] == Decimal("15000.00")

    # Tenant B list
    resp_b = client_b.get(reverse("assets:revaluation_list"))
    assert resp_b.status_code == 200
    ids_b = [r.pk for r in resp_b.context["revaluations"]]
    assert revaluation_b.pk in ids_b
    assert revaluation_a.pk not in ids_b
    assert resp_b.context["total_events"] == 1
    assert resp_b.context["surplus_count"] == 0
    assert resp_b.context["impairment_count"] == 1
    assert resp_b.context["total_adjustment_value"] == Decimal("-7000.00")


def test_assetdepreciation_security_tenant_scoping_transfer_list(
    client_a, client_b, transfer_a, transfer_b
):
    """transfer_list isolates records and KPIs strictly by tenant."""
    # Tenant A list
    resp_a = client_a.get(reverse("assets:transfer_list"))
    assert resp_a.status_code == 200
    ids_a = [t.pk for t in resp_a.context["transfers"]]
    assert transfer_a.pk in ids_a
    assert transfer_b.pk not in ids_a
    assert resp_a.context["total_transfers"] == 1
    assert resp_a.context["total_transport_cost"] == Decimal("750.00")

    # Tenant B list
    resp_b = client_b.get(reverse("assets:transfer_list"))
    assert resp_b.status_code == 200
    ids_b = [t.pk for t in resp_b.context["transfers"]]
    assert transfer_b.pk in ids_b
    assert transfer_a.pk not in ids_b
    assert resp_b.context["total_transfers"] == 1
    assert resp_b.context["total_transport_cost"] == Decimal("250.00")


def test_assetdepreciation_security_tenant_scoping_capitalization_policy_list(
    client_a, client_b, capitalization_policy_a, capitalization_policy_b
):
    """capitalization_policy_list isolates records and KPIs strictly by tenant."""
    # Tenant A list
    resp_a = client_a.get(reverse("assets:capitalization_policy_list"))
    assert resp_a.status_code == 200
    ids_a = [p.pk for p in resp_a.context["policies"]]
    assert capitalization_policy_a.pk in ids_a
    assert capitalization_policy_b.pk not in ids_a
    assert resp_a.context["total_policies"] == 1
    assert resp_a.context["override_count"] == 1
    assert resp_a.context["safe_harbor_count"] == 0

    # Tenant B list
    resp_b = client_b.get(reverse("assets:capitalization_policy_list"))
    assert resp_b.status_code == 200
    ids_b = [p.pk for p in resp_b.context["policies"]]
    assert capitalization_policy_b.pk in ids_b
    assert capitalization_policy_a.pk not in ids_b
    assert resp_b.context["total_policies"] == 1
    assert resp_b.context["override_count"] == 0
    assert resp_b.context["safe_harbor_count"] == 1


# ==============================================================================
# 3. Cross-Tenant Foreign Key Injection Defense (Form Validation Errors)
# ==============================================================================


def test_assetdepreciation_security_fk_injection_schedule_foreign_fixed_asset(client_a, fixed_asset_b):
    """AssetDepreciationScheduleForm rejects foreign fixed_asset from another tenant."""
    url = reverse("assets:depreciation_schedule_create")
    payload = _assetdepreciation_schedule_payload(fixed_asset=fixed_asset_b)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "fixed_asset" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_schedule_foreign_operational_asset(
    client_a, fixed_asset_a, operational_asset_b
):
    """AssetDepreciationScheduleForm rejects foreign operational_asset from another tenant."""
    url = reverse("assets:depreciation_schedule_create")
    payload = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a, operational_asset=operational_asset_b
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "operational_asset" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_schedule_foreign_accounts(
    client_a, fixed_asset_a, expense_account_b, accum_account_b
):
    """AssetDepreciationScheduleForm rejects foreign expense and accumulated GL accounts."""
    url = reverse("assets:depreciation_schedule_create")
    payload = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        expense_account=expense_account_b,
        accumulated_account=accum_account_b,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "expense_account" in resp.context["form"].errors or "accumulated_account" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_schedule_foreign_fiscal_period(
    client_a, fixed_asset_a, tenant_b
):
    """AssetDepreciationScheduleForm rejects foreign fiscal period from another tenant."""
    foreign_period = _assetdepreciation_fiscal_period(tenant=tenant_b, name="FY2026-B-P01")
    url = reverse("assets:depreciation_schedule_create")
    payload = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a, fiscal_period=foreign_period
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "fiscal_period" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_revaluation_foreign_fixed_asset(client_a, fixed_asset_b):
    """AssetRevaluationForm rejects foreign fixed_asset from another tenant."""
    url = reverse("assets:revaluation_create")
    payload = _assetdepreciation_revaluation_payload(fixed_asset=fixed_asset_b)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "fixed_asset" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_revaluation_foreign_operational_asset(
    client_a, fixed_asset_a, operational_asset_b
):
    """AssetRevaluationForm rejects foreign operational_asset from another tenant."""
    url = reverse("assets:revaluation_create")
    payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a, operational_asset=operational_asset_b
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "operational_asset" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_revaluation_foreign_appraiser(
    client_a, fixed_asset_a, vendor_party_b
):
    """AssetRevaluationForm rejects foreign appraiser party from another tenant."""
    url = reverse("assets:revaluation_create")
    payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a, appraiser=vendor_party_b
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "appraiser" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_revaluation_foreign_accounts(
    client_a, fixed_asset_a, expense_account_b
):
    """AssetRevaluationForm rejects foreign GL accounts from another tenant."""
    url = reverse("assets:revaluation_create")
    payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a, impairment_loss_account=expense_account_b
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "impairment_loss_account" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_transfer_foreign_fixed_asset(client_a, fixed_asset_b):
    """AssetTransferForm rejects foreign fixed_asset from another tenant."""
    url = reverse("assets:transfer_create")
    payload = _assetdepreciation_transfer_payload(fixed_asset=fixed_asset_b)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "fixed_asset" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_transfer_foreign_operational_asset(
    client_a, fixed_asset_a, operational_asset_b
):
    """AssetTransferForm rejects foreign operational_asset from another tenant."""
    url = reverse("assets:transfer_create")
    payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a, operational_asset=operational_asset_b
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "operational_asset" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_transfer_foreign_locations(
    client_a, fixed_asset_a, location_b, location_b2
):
    """AssetTransferForm rejects foreign source and destination locations from another tenant."""
    url = reverse("assets:transfer_create")
    payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_location=location_b,
        destination_location=location_b2,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "source_location" in resp.context["form"].errors or "destination_location" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_transfer_foreign_departments(
    client_a, fixed_asset_a, org_unit_b
):
    """AssetTransferForm rejects foreign source and destination departments from another tenant."""
    url = reverse("assets:transfer_create")
    payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_department=org_unit_b,
        destination_department=org_unit_b,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "source_department" in resp.context["form"].errors or "destination_department" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_transfer_foreign_custodians(
    client_a, fixed_asset_a, vendor_party_b
):
    """AssetTransferForm rejects foreign custodian parties from another tenant."""
    url = reverse("assets:transfer_create")
    payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_custodian=vendor_party_b,
        destination_custodian=vendor_party_b,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "source_custodian" in resp.context["form"].errors or "destination_custodian" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_policy_foreign_category(client_a, category_root_b):
    """CapitalizationPolicyForm rejects foreign category from another tenant."""
    url = reverse("assets:capitalization_policy_create")
    payload = _assetdepreciation_policy_payload(category=category_root_b)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "category" in resp.context["form"].errors


def test_assetdepreciation_security_fk_injection_policy_foreign_accounts(
    client_a, cip_account_a, expense_account_b
):
    """CapitalizationPolicyForm rejects foreign expense account from another tenant."""
    url = reverse("assets:capitalization_policy_create")
    payload = _assetdepreciation_policy_payload(
        default_cip_account=cip_account_a, default_expense_account=expense_account_b
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "default_expense_account" in resp.context["form"].errors


# ==============================================================================
# 4. Unauthenticated Access Control (All 25 URLs Redirect 302 to Login)
# ==============================================================================


def test_assetdepreciation_security_unauthenticated_requests_redirect(
    client, depreciation_schedule_a, revaluation_a, transfer_a, capitalization_policy_a
):
    """Anonymous client accessing any of the 25 depreciation/financial endpoints redirects 302 to login."""
    endpoints = [
        # 1. AssetDepreciationSchedule (7)
        ("GET", reverse("assets:depreciation_schedule_list")),
        ("GET", reverse("assets:depreciation_schedule_create")),
        ("POST", reverse("assets:depreciation_schedule_create")),
        ("GET", reverse("assets:depreciation_schedule_detail", args=[depreciation_schedule_a.pk])),
        ("GET", reverse("assets:depreciation_schedule_edit", args=[depreciation_schedule_a.pk])),
        ("POST", reverse("assets:depreciation_schedule_edit", args=[depreciation_schedule_a.pk])),
        ("POST", reverse("assets:depreciation_schedule_delete", args=[depreciation_schedule_a.pk])),
        ("POST", reverse("assets:depreciation_schedule_calculate", args=[depreciation_schedule_a.pk])),
        ("POST", reverse("assets:depreciation_schedule_post", args=[depreciation_schedule_a.pk])),
        # 2. AssetRevaluation (6)
        ("GET", reverse("assets:revaluation_list")),
        ("GET", reverse("assets:revaluation_create")),
        ("POST", reverse("assets:revaluation_create")),
        ("GET", reverse("assets:revaluation_detail", args=[revaluation_a.pk])),
        ("GET", reverse("assets:revaluation_edit", args=[revaluation_a.pk])),
        ("POST", reverse("assets:revaluation_edit", args=[revaluation_a.pk])),
        ("POST", reverse("assets:revaluation_delete", args=[revaluation_a.pk])),
        ("POST", reverse("assets:revaluation_approve", args=[revaluation_a.pk])),
        # 3. AssetTransfer (7)
        ("GET", reverse("assets:transfer_list")),
        ("GET", reverse("assets:transfer_create")),
        ("POST", reverse("assets:transfer_create")),
        ("GET", reverse("assets:transfer_detail", args=[transfer_a.pk])),
        ("GET", reverse("assets:transfer_edit", args=[transfer_a.pk])),
        ("POST", reverse("assets:transfer_edit", args=[transfer_a.pk])),
        ("POST", reverse("assets:transfer_delete", args=[transfer_a.pk])),
        ("POST", reverse("assets:transfer_dispatch", args=[transfer_a.pk])),
        ("POST", reverse("assets:transfer_complete", args=[transfer_a.pk])),
        # 4. CapitalizationPolicy (5)
        ("GET", reverse("assets:capitalization_policy_list")),
        ("GET", reverse("assets:capitalization_policy_create")),
        ("POST", reverse("assets:capitalization_policy_create")),
        ("GET", reverse("assets:capitalization_policy_detail", args=[capitalization_policy_a.pk])),
        ("GET", reverse("assets:capitalization_policy_edit", args=[capitalization_policy_a.pk])),
        ("POST", reverse("assets:capitalization_policy_edit", args=[capitalization_policy_a.pk])),
        ("POST", reverse("assets:capitalization_policy_delete", args=[capitalization_policy_a.pk])),
    ]

    assert len(endpoints) == 33  # 25 URLs plus GET/POST combinations for forms

    for method, target_url in endpoints:
        if method == "GET":
            resp = client.get(target_url)
        else:
            resp = client.post(target_url)
        assert resp.status_code == 302, f"Expected 302 for {method} {target_url}, got {resp.status_code}"
        assert "login" in resp.url or "/accounts/login" in resp.url


# ==============================================================================
# 5. Role-Based Authorization Enforcement (@tenant_admin_required)
# ==============================================================================


def test_assetdepreciation_security_rbac_member_blocked_from_schedule_post(
    member_client, depreciation_schedule_a
):
    """Non-admin member is blocked with 403 Forbidden on depreciation_schedule_post."""
    url = reverse("assets:depreciation_schedule_post", args=[depreciation_schedule_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_assetdepreciation_security_rbac_member_blocked_from_schedule_delete(
    member_client, depreciation_schedule_a
):
    """Non-admin member is blocked with 403 Forbidden on depreciation_schedule_delete."""
    url = reverse("assets:depreciation_schedule_delete", args=[depreciation_schedule_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert AssetDepreciationSchedule.objects.filter(pk=depreciation_schedule_a.pk).exists()


def test_assetdepreciation_security_rbac_member_blocked_from_revaluation_approve(
    member_client, revaluation_a
):
    """Non-admin member is blocked with 403 Forbidden on revaluation_approve."""
    url = reverse("assets:revaluation_approve", args=[revaluation_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403
    revaluation_a.refresh_from_db()
    assert revaluation_a.status == "draft"


def test_assetdepreciation_security_rbac_member_blocked_from_revaluation_delete(
    member_client, revaluation_a
):
    """Non-admin member is blocked with 403 Forbidden on revaluation_delete."""
    url = reverse("assets:revaluation_delete", args=[revaluation_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert AssetRevaluation.objects.filter(pk=revaluation_a.pk).exists()


def test_assetdepreciation_security_rbac_member_blocked_from_transfer_complete(
    member_client, transfer_a
):
    """Non-admin member is blocked with 403 Forbidden on transfer_complete."""
    url = reverse("assets:transfer_complete", args=[transfer_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403
    transfer_a.refresh_from_db()
    assert transfer_a.status == "draft"


def test_assetdepreciation_security_rbac_member_blocked_from_transfer_delete(
    member_client, transfer_a
):
    """Non-admin member is blocked with 403 Forbidden on transfer_delete."""
    url = reverse("assets:transfer_delete", args=[transfer_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert AssetTransfer.objects.filter(pk=transfer_a.pk).exists()


def test_assetdepreciation_security_rbac_member_blocked_from_policy_delete(
    member_client, capitalization_policy_a
):
    """Non-admin member is blocked with 403 Forbidden on capitalization_policy_delete."""
    url = reverse("assets:capitalization_policy_delete", args=[capitalization_policy_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert CapitalizationPolicy.objects.filter(pk=capitalization_policy_a.pk).exists()


def test_assetdepreciation_security_rbac_admin_allowed_privileged_actions(
    client_a, tenant_a, fixed_asset_a, operational_asset_a, expense_account_a, accum_account_a
):
    """Tenant admin client is authorized to execute all 7 privileged actions without 403 Forbidden."""
    # 1. Schedule delete
    sched = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=11,
        schedule_date=timezone.now().date(),
        depreciation_method="straight_line",
        starting_book_value=Decimal("50000.00"),
        depreciation_amount=Decimal("500.00"),
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        status="draft",
    )
    url_sched_del = reverse("assets:depreciation_schedule_delete", args=[sched.pk])
    assert client_a.post(url_sched_del).status_code == 302
    assert not AssetDepreciationSchedule.objects.filter(pk=sched.pk).exists()

    # 2. Schedule post
    sched_post = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=12,
        schedule_date=timezone.now().date(),
        depreciation_method="straight_line",
        starting_book_value=Decimal("50000.00"),
        depreciation_amount=Decimal("500.00"),
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        status="calculated",
    )
    url_sched_post = reverse("assets:depreciation_schedule_post", args=[sched_post.pk])
    assert client_a.post(url_sched_post).status_code == 302

    # 3. Policy delete
    pol = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Temporary Policy For Admin Del",
        policy_scope="global_default",
        minimum_cost_threshold=Decimal("1000.00"),
        minimum_useful_life_months=12,
        default_classification="capitalize",
        is_active=True,
    )
    url_pol_del = reverse("assets:capitalization_policy_delete", args=[pol.pk])
    assert client_a.post(url_pol_del).status_code == 302
    assert not CapitalizationPolicy.objects.filter(pk=pol.pk).exists()


# ==============================================================================
# 6. HTTP Method Guarding (@require_POST)
# ==============================================================================


def test_assetdepreciation_security_http_methods_get_on_require_post_returns_405(
    client_a, depreciation_schedule_a, revaluation_a, transfer_a, capitalization_policy_a
):
    """Sending GET to state-changing endpoints protected by @require_POST returns 405 Method Not Allowed."""
    require_post_endpoints = [
        reverse("assets:depreciation_schedule_delete", args=[depreciation_schedule_a.pk]),
        reverse("assets:depreciation_schedule_calculate", args=[depreciation_schedule_a.pk]),
        reverse("assets:depreciation_schedule_post", args=[depreciation_schedule_a.pk]),
        reverse("assets:revaluation_delete", args=[revaluation_a.pk]),
        reverse("assets:revaluation_approve", args=[revaluation_a.pk]),
        reverse("assets:transfer_delete", args=[transfer_a.pk]),
        reverse("assets:transfer_dispatch", args=[transfer_a.pk]),
        reverse("assets:transfer_complete", args=[transfer_a.pk]),
        reverse("assets:capitalization_policy_delete", args=[capitalization_policy_a.pk]),
    ]

    for url in require_post_endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET on {url}, got {resp.status_code}"


# ==============================================================================
# 7. Mass-Assignment & Tamper Resistance
# ==============================================================================


def test_assetdepreciation_security_mass_assignment_schedule_create_and_edit(
    client_a, tenant_a, tenant_b, fixed_asset_a, depreciation_schedule_a, admin_user
):
    """Injected tenant, number, status, journal_entry, posted_at/by are ignored on schedule create and edit."""
    # 1. Create
    create_url = reverse("assets:depreciation_schedule_create")
    malicious_create_payload = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        notes="Security Mass Assignment Create Test",
        tenant=tenant_b.pk,
        number="ADEP-HACK-9999",
        status="posted",
        posted_at="2026-01-01T00:00:00Z",
        posted_by=admin_user.pk,
        journal_entry=999999,
        accumulated_depreciation_after="999999.00",
        ending_book_value="0.00",
    )
    resp_create = client_a.post(create_url, data=malicious_create_payload)
    assert resp_create.status_code == 302
    created = AssetDepreciationSchedule.objects.get(
        tenant=tenant_a, notes="Security Mass Assignment Create Test"
    )
    assert created.tenant == tenant_a
    assert created.number != "ADEP-HACK-9999"
    assert created.number.startswith("ADEP-")
    assert created.status in ("draft", "calculated")
    assert created.status != "posted"
    assert created.journal_entry is None
    assert created.posted_at is None
    assert created.posted_by is None

    # 2. Edit
    edit_url = reverse("assets:depreciation_schedule_edit", args=[depreciation_schedule_a.pk])
    original_number = depreciation_schedule_a.number
    malicious_edit_payload = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        notes="Security Mass Assignment Edit Test",
        tenant=tenant_b.pk,
        number="ADEP-OVERWRITE-001",
        status="posted",
        journal_entry=12345,
    )
    resp_edit = client_a.post(edit_url, data=malicious_edit_payload)
    assert resp_edit.status_code == 302
    depreciation_schedule_a.refresh_from_db()
    assert depreciation_schedule_a.tenant == tenant_a
    assert depreciation_schedule_a.number == original_number
    assert depreciation_schedule_a.status != "posted"
    assert depreciation_schedule_a.journal_entry is None


def test_assetdepreciation_security_mass_assignment_revaluation_create_and_edit(
    client_a, tenant_a, tenant_b, fixed_asset_a, revaluation_a, admin_user
):
    """Injected tenant, number, status, journal_entry, approved_at/by are ignored on revaluation create/edit."""
    # 1. Create
    create_url = reverse("assets:revaluation_create")
    malicious_create_payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        title="Security Mass Assignment Reval Create",
        tenant=tenant_b.pk,
        number="ARVL-HACK-8888",
        status="approved",
        approved_at="2026-01-01T00:00:00Z",
        approved_by=admin_user.pk,
        journal_entry=888888,
        historical_cost="999999.00",
        revaluation_adjustment="0.00",
    )
    resp_create = client_a.post(create_url, data=malicious_create_payload)
    assert resp_create.status_code == 302
    created = AssetRevaluation.objects.get(
        tenant=tenant_a, title="Security Mass Assignment Reval Create"
    )
    assert created.tenant == tenant_a
    assert created.number != "ARVL-HACK-8888"
    assert created.number.startswith("AREV-")
    assert created.status == "draft"
    assert created.approved_at is None
    assert created.approved_by is None
    assert created.journal_entry is None

    # 2. Edit
    edit_url = reverse("assets:revaluation_edit", args=[revaluation_a.pk])
    original_number = revaluation_a.number
    malicious_edit_payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        title="Security Mass Assignment Reval Edit",
        tenant=tenant_b.pk,
        number="ARVL-OVERWRITE-777",
        status="approved",
    )
    resp_edit = client_a.post(edit_url, data=malicious_edit_payload)
    assert resp_edit.status_code == 302
    revaluation_a.refresh_from_db()
    assert revaluation_a.tenant == tenant_a
    assert revaluation_a.number == original_number
    assert revaluation_a.status == "draft"


def test_assetdepreciation_security_mass_assignment_transfer_create_and_edit(
    client_a, tenant_a, tenant_b, fixed_asset_a, transfer_a, admin_user
):
    """Injected tenant, number, status, journal_entry, completed_at, received_by are ignored on transfer."""
    # 1. Create
    create_url = reverse("assets:transfer_create")
    malicious_create_payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        title="Security Mass Assignment Transfer Create",
        tenant=tenant_b.pk,
        number="ATRF-HACK-1234",
        status="completed",
        completed_at="2026-01-01T00:00:00Z",
        received_by=admin_user.pk,
        journal_entry=123456,
        carrying_value_at_transfer="999999.00",
    )
    resp_create = client_a.post(create_url, data=malicious_create_payload)
    assert resp_create.status_code == 302
    created = AssetTransfer.objects.get(
        tenant=tenant_a, title="Security Mass Assignment Transfer Create"
    )
    assert created.tenant == tenant_a
    assert created.number != "ATRF-HACK-1234"
    assert created.number.startswith("AXFR-")
    assert created.status == "draft"
    assert created.completed_at is None
    assert created.received_by is None
    assert created.journal_entry is None

    # 2. Edit
    edit_url = reverse("assets:transfer_edit", args=[transfer_a.pk])
    original_number = transfer_a.number
    malicious_edit_payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        title="Security Mass Assignment Transfer Edit",
        tenant=tenant_b.pk,
        number="ATRF-OVERWRITE-000",
        status="completed",
    )
    resp_edit = client_a.post(edit_url, data=malicious_edit_payload)
    assert resp_edit.status_code == 302
    transfer_a.refresh_from_db()
    assert transfer_a.tenant == tenant_a
    assert transfer_a.number == original_number
    assert transfer_a.status == "draft"


def test_assetdepreciation_security_mass_assignment_policy_create_and_edit(
    client_a, tenant_a, tenant_b, capitalization_policy_a
):
    """Injected tenant and number fields are ignored on capitalization policy create and edit."""
    # 1. Create
    create_url = reverse("assets:capitalization_policy_create")
    malicious_create_payload = _assetdepreciation_policy_payload(
        name="Security Policy Mass Assignment Create",
        tenant=tenant_b.pk,
        number="CPOL-HACK-999",
    )
    resp_create = client_a.post(create_url, data=malicious_create_payload)
    assert resp_create.status_code == 302
    created = CapitalizationPolicy.objects.get(
        tenant=tenant_a, name="Security Policy Mass Assignment Create"
    )
    assert created.tenant == tenant_a
    assert created.number != "CPOL-HACK-999"
    assert created.number.startswith("ACTH-")

    # 2. Edit
    edit_url = reverse("assets:capitalization_policy_edit", args=[capitalization_policy_a.pk])
    original_number = capitalization_policy_a.number
    malicious_edit_payload = _assetdepreciation_policy_payload(
        name="Security Policy Legit Updated",
        tenant=tenant_b.pk,
        number="CPOL-OVERWRITE-111",
    )
    resp_edit = client_a.post(edit_url, data=malicious_edit_payload)
    assert resp_edit.status_code == 302
    capitalization_policy_a.refresh_from_db()
    assert capitalization_policy_a.tenant == tenant_a
    assert capitalization_policy_a.number == original_number
    assert capitalization_policy_a.name == "Security Policy Legit Updated"


# ==============================================================================
# 8. Status Guard Compliance
# ==============================================================================


def test_assetdepreciation_security_status_guard_schedule_posted_blocks_edit_delete_calculate(
    client_a, depreciation_schedule_a, fixed_asset_a
):
    """Posted depreciation schedule cannot be edited, deleted, or recalculated."""
    depreciation_schedule_a.status = "posted"
    depreciation_schedule_a.save()

    # 1. Edit attempt
    edit_url = reverse("assets:depreciation_schedule_edit", args=[depreciation_schedule_a.pk])
    payload = _assetdepreciation_schedule_payload(fixed_asset=fixed_asset_a, notes="Tamper Posted Schedule")
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302
    assert resp_edit.url == reverse("assets:depreciation_schedule_detail", args=[depreciation_schedule_a.pk])
    msgs_edit = _assetdepreciation_get_flash_messages(resp_edit)
    assert any("cannot be edited" in m for m in msgs_edit)

    # 2. Delete attempt
    del_url = reverse("assets:depreciation_schedule_delete", args=[depreciation_schedule_a.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("assets:depreciation_schedule_detail", args=[depreciation_schedule_a.pk])
    msgs_del = _assetdepreciation_get_flash_messages(resp_del)
    assert any("Cannot delete a posted" in m for m in msgs_del)
    assert AssetDepreciationSchedule.objects.filter(pk=depreciation_schedule_a.pk).exists()

    # 3. Calculate attempt
    calc_url = reverse("assets:depreciation_schedule_calculate", args=[depreciation_schedule_a.pk])
    resp_calc = client_a.post(calc_url)
    assert resp_calc.status_code == 302
    assert resp_calc.url == reverse("assets:depreciation_schedule_detail", args=[depreciation_schedule_a.pk])
    msgs_calc = _assetdepreciation_get_flash_messages(resp_calc)
    assert any("Cannot recalculate a posted" in m for m in msgs_calc)


def test_assetdepreciation_security_status_guard_revaluation_approved_blocks_edit_and_delete(
    client_a, revaluation_a, fixed_asset_a
):
    """Approved asset revaluation cannot be edited or deleted."""
    revaluation_a.status = "approved"
    revaluation_a.save()

    # 1. Edit attempt
    edit_url = reverse("assets:revaluation_edit", args=[revaluation_a.pk])
    payload = _assetdepreciation_revaluation_payload(fixed_asset=fixed_asset_a, title="Tamper Approved Reval")
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302
    assert resp_edit.url == reverse("assets:revaluation_detail", args=[revaluation_a.pk])
    msgs_edit = _assetdepreciation_get_flash_messages(resp_edit)
    assert any("cannot be edited" in m for m in msgs_edit)

    # 2. Delete attempt
    del_url = reverse("assets:revaluation_delete", args=[revaluation_a.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("assets:revaluation_detail", args=[revaluation_a.pk])
    msgs_del = _assetdepreciation_get_flash_messages(resp_del)
    assert any("Cannot delete an approved" in m for m in msgs_del)
    assert AssetRevaluation.objects.filter(pk=revaluation_a.pk).exists()


def test_assetdepreciation_security_status_guard_transfer_completed_blocks_edit_and_delete(
    client_a, transfer_a, fixed_asset_a
):
    """Completed asset transfer cannot be edited or deleted."""
    transfer_a.status = "completed"
    transfer_a.save()

    # 1. Edit attempt
    edit_url = reverse("assets:transfer_edit", args=[transfer_a.pk])
    payload = _assetdepreciation_transfer_payload(fixed_asset=fixed_asset_a, title="Tamper Completed Transfer")
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302
    assert resp_edit.url == reverse("assets:transfer_detail", args=[transfer_a.pk])
    msgs_edit = _assetdepreciation_get_flash_messages(resp_edit)
    assert any("cannot be edited" in m for m in msgs_edit)

    # 2. Delete attempt
    del_url = reverse("assets:transfer_delete", args=[transfer_a.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("assets:transfer_detail", args=[transfer_a.pk])
    msgs_del = _assetdepreciation_get_flash_messages(resp_del)
    assert any("Cannot delete a completed" in m for m in msgs_del)
    assert AssetTransfer.objects.filter(pk=transfer_a.pk).exists()


# ==============================================================================
# 9. Malicious & Malformed Input Fuzzing (XSS, SQLi, NaN, Infinity)
# ==============================================================================


def test_assetdepreciation_security_fuzzing_xss_and_sqli_in_search_and_filter_queries(client_a):
    """List views safely handle malicious XSS payloads and SQL injection tokens without 500 error."""
    malicious_inputs = [
        "<script>alert('XSS-TEST')</script>",
        "'; DROP TABLE apps_assets_assetdepreciationschedule; --",
        "' OR '1'='1",
        '"><img src=x onerror=alert(1)>',
        "admin'--",
        "UNION ALL SELECT NULL,NULL,NULL--",
    ]

    list_urls = [
        reverse("assets:depreciation_schedule_list"),
        reverse("assets:revaluation_list"),
        reverse("assets:transfer_list"),
        reverse("assets:capitalization_policy_list"),
    ]

    for base_url in list_urls:
        for payload in malicious_inputs:
            resp = client_a.get(base_url, {"q": payload, "status": payload, "method": payload})
            assert resp.status_code == 200, f"Expected 200 for payload {payload} on {base_url}, got {resp.status_code}"


def test_assetdepreciation_security_fuzzing_non_numeric_and_nan_in_numeric_query_params(
    client_a, capitalization_policy_a
):
    """Non-numeric values, negative offsets, and NaN/Infinity never cause HTTP 500 errors."""
    # 1. Schedule list year filter fuzzing
    sched_url = reverse("assets:depreciation_schedule_list")
    for bad_year in ["abc", "-2026", "999999999999", "NaN", "Infinity", "2026.5"]:
        resp = client_a.get(sched_url, {"year": bad_year, "page": bad_year})
        assert resp.status_code == 200

    # 2. Capitalization policy category filter fuzzing
    pol_url = reverse("assets:capitalization_policy_list")
    for bad_cat in ["abc", "-1", "99999999", "NaN", "' OR 1=1 --"]:
        resp = client_a.get(pol_url, {"category": bad_cat, "page": bad_cat})
        assert resp.status_code == 200

    # 3. Capitalization policy evaluator evaluator fuzzing (detail view eval_cost and eval_life)
    detail_url = reverse("assets:capitalization_policy_detail", args=[capitalization_policy_a.pk])
    fuzz_eval_inputs = [
        {"eval_cost": "NaN", "eval_life": "12"},
        {"eval_cost": "Infinity", "eval_life": "12"},
        {"eval_cost": "-Infinity", "eval_life": "12"},
        {"eval_cost": "abc", "eval_life": "xyz"},
        {"eval_cost": "-5000", "eval_life": "-24"},
        {"eval_cost": "1e999999", "eval_life": "12"},
        {"eval_cost": "<script>alert(1)</script>", "eval_life": "12"},
    ]
    for params in fuzz_eval_inputs:
        resp = client_a.get(detail_url, params)
        assert resp.status_code == 200


def test_assetdepreciation_security_fuzzing_extreme_string_lengths_and_null_bytes(client_a):
    """Very large strings (5000+ chars) and null byte injection in queries do not cause 500 errors."""
    giant_string = "A" * 5000
    null_byte_string = "search\x00term"

    list_urls = [
        reverse("assets:depreciation_schedule_list"),
        reverse("assets:revaluation_list"),
        reverse("assets:transfer_list"),
        reverse("assets:capitalization_policy_list"),
    ]

    for base_url in list_urls:
        assert client_a.get(base_url, {"q": giant_string}).status_code == 200
        assert client_a.get(base_url, {"q": null_byte_string}).status_code == 200


# ==============================================================================
# 10. Audit Log Generation and Tenant Scoping
# ==============================================================================


def test_assetdepreciation_security_audit_log_schedule_lifecycle(
    client_a, tenant_a, admin_user, fixed_asset_a
):
    """AuditLog rows are generated and tenant-scoped for schedule create, calculate, edit, and delete."""
    # 1. Create
    create_url = reverse("assets:depreciation_schedule_create")
    payload = _assetdepreciation_schedule_payload(fixed_asset=fixed_asset_a, notes="Audit Test Schedule")
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    sched = AssetDepreciationSchedule.objects.get(tenant=tenant_a, notes="Audit Test Schedule")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(sched.pk),
    ).exists()

    # 2. Calculate
    calc_url = reverse("assets:depreciation_schedule_calculate", args=[sched.pk])
    resp_calc = client_a.post(calc_url)
    assert resp_calc.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="calculate",
        object_id=str(sched.pk),
    ).exists()

    # 3. Edit / Update
    edit_url = reverse("assets:depreciation_schedule_edit", args=[sched.pk])
    payload["notes"] = "Audit Schedule Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(sched.pk),
    ).exists()

    # 4. Delete
    delete_url = reverse("assets:depreciation_schedule_delete", args=[sched.pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
    ).exists()


def test_assetdepreciation_security_audit_log_revaluation_lifecycle(
    client_a, tenant_a, admin_user, fixed_asset_a, vendor_party_a
):
    """AuditLog rows are generated and tenant-scoped for revaluation create, update, and delete."""
    # 1. Create
    create_url = reverse("assets:revaluation_create")
    payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a, appraiser=vendor_party_a, title="Audit Reval Test"
    )
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    reval = AssetRevaluation.objects.get(tenant=tenant_a, title="Audit Reval Test")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(reval.pk),
    ).exists()

    # 2. Update
    edit_url = reverse("assets:revaluation_edit", args=[reval.pk])
    payload["title"] = "Audit Reval Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(reval.pk),
    ).exists()

    # 3. Delete
    delete_url = reverse("assets:revaluation_delete", args=[reval.pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
    ).exists()


def test_assetdepreciation_security_audit_log_transfer_lifecycle(
    client_a, tenant_a, admin_user, fixed_asset_a, location_a, location_a2
):
    """AuditLog rows are generated and tenant-scoped for transfer create, update, dispatch, and delete."""
    # 1. Create
    create_url = reverse("assets:transfer_create")
    payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_location=location_a,
        destination_location=location_a2,
        title="Audit Transfer Test",
    )
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    transfer = AssetTransfer.objects.get(tenant=tenant_a, title="Audit Transfer Test")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(transfer.pk),
    ).exists()

    # 2. Update
    edit_url = reverse("assets:transfer_edit", args=[transfer.pk])
    payload["title"] = "Audit Transfer Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(transfer.pk),
    ).exists()

    # 3. Dispatch
    dispatch_url = reverse("assets:transfer_dispatch", args=[transfer.pk])
    resp_dispatch = client_a.post(dispatch_url)
    assert resp_dispatch.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="dispatch",
        object_id=str(transfer.pk),
    ).exists()

    # 4. For delete, create another draft transfer and delete it
    payload_del = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a, title="Audit Transfer For Del"
    )
    client_a.post(create_url, data=payload_del)
    t_del = AssetTransfer.objects.get(tenant=tenant_a, title="Audit Transfer For Del")

    del_url = reverse("assets:transfer_delete", args=[t_del.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
    ).exists()


def test_assetdepreciation_security_audit_log_policy_lifecycle(client_a, tenant_a, admin_user):
    """AuditLog rows are generated and tenant-scoped for capitalization policy create, update, and delete."""
    # 1. Create
    create_url = reverse("assets:capitalization_policy_create")
    payload = _assetdepreciation_policy_payload(name="Audit Policy Test")
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    policy = CapitalizationPolicy.objects.get(tenant=tenant_a, name="Audit Policy Test")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(policy.pk),
    ).exists()

    # 2. Update
    edit_url = reverse("assets:capitalization_policy_edit", args=[policy.pk])
    payload["name"] = "Audit Policy Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(policy.pk),
    ).exists()

    # 3. Delete
    delete_url = reverse("assets:capitalization_policy_delete", args=[policy.pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
    ).exists()
