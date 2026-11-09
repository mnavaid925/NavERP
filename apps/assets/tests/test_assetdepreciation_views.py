"""Asset Depreciation & Financial Management (11.4) — VIEWS Integration Test Suite.

Covers all 25 views across the 4 entities:
1. AssetDepreciationSchedule:
   - depreciation_schedule_list (GET, context keys, search, filters by status/method/year, pagination, junk params)
   - depreciation_schedule_detail (GET, context contract, cross-tenant 404)
   - depreciation_schedule_create (GET, POST valid -> 302 with auto calculate, POST invalid -> 200)
   - depreciation_schedule_edit (GET, POST valid -> 302, POST invalid -> 200, posted status guard)
   - depreciation_schedule_delete (require_POST, tenant_admin_required, posted status guard, valid delete)
   - depreciation_schedule_calculate (require_POST, posted status guard, valid calculation -> 302)
   - depreciation_schedule_post (require_POST, tenant_admin_required, GL posting -> 302, ValidationError handling)

2. AssetRevaluation:
   - revaluation_list (GET, context keys, search, filters by event_type/status, pagination, junk params)
   - revaluation_detail (GET, context contract, cross-tenant 404)
   - revaluation_create (GET, POST valid -> 302 with auto calculate adjustment, POST invalid -> 200)
   - revaluation_edit (GET, POST valid -> 302, POST invalid -> 200, approved status guard)
   - revaluation_delete (require_POST, tenant_admin_required, approved status guard, valid delete)
   - revaluation_approve (require_POST, tenant_admin_required, GL posting -> 302, ValidationError handling)

3. AssetTransfer:
   - transfer_list (GET, context keys, search, filters by type/status, pagination, junk params)
   - transfer_detail (GET, context contract, cross-tenant 404)
   - transfer_create (GET, POST valid -> 302 with carrying value capture, POST invalid -> 200)
   - transfer_edit (GET, POST valid -> 302, POST invalid -> 200, completed status guard)
   - transfer_delete (require_POST, tenant_admin_required, completed status guard, valid delete)
   - transfer_dispatch (require_POST, status transition to in_transit -> 302)
   - transfer_complete (require_POST, tenant_admin_required, asset destination sync -> 302)

4. CapitalizationPolicy:
   - capitalization_policy_list (GET, context keys, search, filters by scope/category, pagination, junk params)
   - capitalization_policy_detail (GET, context contract, capitalization evaluator, negative/invalid/NaN costs, cross-tenant 404)
   - capitalization_policy_create (GET, POST valid -> 302, POST invalid -> 200)
   - capitalization_policy_edit (GET, POST valid -> 302, POST invalid -> 200)
   - capitalization_policy_delete (require_POST, tenant_admin_required, valid delete)

5. Security:
   - Unauthenticated redirects for all entities and actions
   - Cross-tenant IDOR rejection (404) on edit, delete, and workflow actions
"""
from decimal import Decimal
import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, FixedAsset, GLAccount, JournalEntry
from apps.assets.models import (
    AssetCategory,
    AssetDepreciationSchedule,
    AssetRevaluation,
    AssetTransfer,
    CapitalizationPolicy,
)
from apps.core.models import AuditLog, OrgUnit, Party
from apps.scm.models import Asset, Location


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
# 1. AssetDepreciationSchedule Views
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_list_renders_200_and_context(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_list renders 200 with required context keys and aggregates."""
    url = reverse("assets:depreciation_schedule_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "depreciation_schedules" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "status_choices" in resp.context
    assert "method_choices" in resp.context
    assert "year_choices" in resp.context
    assert "total_depreciation_period" in resp.context
    assert "posted_count" in resp.context
    assert "calculated_count" in resp.context
    assert "total_runs" in resp.context
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert "selected_status" in resp.context
    assert "selected_method" in resp.context
    assert "selected_year" in resp.context

    assert resp.context["total_runs"] >= 1
    assert resp.context["total_depreciation_period"] >= Decimal("1800.00")


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_list_filter_search(
    client_a, depreciation_schedule_a, fixed_asset_a
):
    """depreciation_schedule_list filters by q search query across number, fixed asset, notes."""
    url = reverse("assets:depreciation_schedule_list")

    # Match by schedule number
    resp_num = client_a.get(url, {"q": depreciation_schedule_a.number})
    assert resp_num.status_code == 200
    pks = [s.pk for s in resp_num.context["depreciation_schedules"]]
    assert depreciation_schedule_a.pk in pks

    # Match by fixed asset name
    resp_fa = client_a.get(url, {"q": fixed_asset_a.name[:10]})
    assert resp_fa.status_code == 200
    pks_fa = [s.pk for s in resp_fa.context["depreciation_schedules"]]
    assert depreciation_schedule_a.pk in pks_fa

    # No match
    resp_none = client_a.get(url, {"q": "NONEXISTENT_SCHEDULE_QUERY_XYZ"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["depreciation_schedules"]) == 0


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_list_filter_status_and_method_and_year(
    client_a, tenant_a, fixed_asset_a, depreciation_schedule_a
):
    """depreciation_schedule_list filters by status, method, and fiscal year."""
    url = reverse("assets:depreciation_schedule_list")

    # Create a secondary posted schedule in 2025 with declining balance
    sched_2025 = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2025,
        period_number=12,
        period_frequency="monthly",
        schedule_date=timezone.now().date(),
        depreciation_method="declining_balance_200",
        starting_book_value=Decimal("120000.00"),
        depreciation_amount=Decimal("4000.00"),
        accumulated_depreciation_after=Decimal("4000.00"),
        ending_book_value=Decimal("116000.00"),
        status="posted",
    )

    # Filter status=draft
    resp_draft = client_a.get(url, {"status": "draft"})
    assert resp_draft.status_code == 200
    draft_pks = [s.pk for s in resp_draft.context["depreciation_schedules"]]
    assert depreciation_schedule_a.pk in draft_pks
    assert sched_2025.pk not in draft_pks

    # Filter status=posted
    resp_posted = client_a.get(url, {"status": "posted"})
    assert resp_posted.status_code == 200
    posted_pks = [s.pk for s in resp_posted.context["depreciation_schedules"]]
    assert sched_2025.pk in posted_pks
    assert depreciation_schedule_a.pk not in posted_pks

    # Filter method=declining_balance_200
    resp_method = client_a.get(url, {"method": "declining_balance_200"})
    assert resp_method.status_code == 200
    method_pks = [s.pk for s in resp_method.context["depreciation_schedules"]]
    assert sched_2025.pk in method_pks
    assert depreciation_schedule_a.pk not in method_pks

    # Filter year=2025
    resp_year = client_a.get(url, {"year": "2025"})
    assert resp_year.status_code == 200
    year_pks = [s.pk for s in resp_year.context["depreciation_schedules"]]
    assert sched_2025.pk in year_pks
    assert depreciation_schedule_a.pk not in year_pks


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_list_junk_parameters_safe(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_list handles invalid year, invalid status, and malformed query without crashing."""
    url = reverse("assets:depreciation_schedule_list")
    resp = client_a.get(
        url,
        {
            "year": "not_an_int",
            "status": "mythical_status",
            "method": "unsupported_method",
            "page": "invalid_page_str",
        },
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_list_pagination(
    client_a, tenant_a, fixed_asset_a
):
    """depreciation_schedule_list paginates with 15 per page, preserving query filters."""
    for i in range(1, 18):
        AssetDepreciationSchedule.objects.create(
            tenant=tenant_a,
            fixed_asset=fixed_asset_a,
            fiscal_year=2026,
            period_number=i % 12 + 1,
            period_frequency="monthly",
            schedule_date=timezone.now().date(),
            depreciation_method="straight_line",
            starting_book_value=Decimal("120000.00"),
            depreciation_amount=Decimal("1800.00"),
            accumulated_depreciation_after=Decimal("1800.00"),
            ending_book_value=Decimal("118200.00"),
            status="draft",
        )

    url = reverse("assets:depreciation_schedule_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["depreciation_schedules"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["depreciation_schedules"]) >= 2
    assert resp_p2.context["page_obj"].has_previous()

    # Out of range page defaults to last page
    resp_out = client_a.get(url, {"page": "99999"})
    assert resp_out.status_code == 200
    assert resp_out.context["page_obj"].number == resp_p2.context["page_obj"].number


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_detail_renders_200_and_context(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_detail renders 200 with schedule and object context keys."""
    url = reverse("assets:depreciation_schedule_detail", kwargs={"pk": depreciation_schedule_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "schedule" in resp.context
    assert "object" in resp.context
    assert resp.context["schedule"].pk == depreciation_schedule_a.pk


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_detail_cross_tenant_404(
    client_b, depreciation_schedule_a
):
    """depreciation_schedule_detail returns 404 when accessed by a different tenant."""
    url = reverse("assets:depreciation_schedule_detail", kwargs={"pk": depreciation_schedule_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_create_get_renders_form(client_a):
    """depreciation_schedule_create GET renders form with is_edit=False and empty instance."""
    url = reverse("assets:depreciation_schedule_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["schedule"] is None
    assert resp.context["object"] is None


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_create_post_success(
    client_a, tenant_a, fixed_asset_a, expense_account_a, accum_account_a
):
    """depreciation_schedule_create valid POST saves, auto-calculates, logs audit, and redirects to detail."""
    url = reverse("assets:depreciation_schedule_create")
    payload = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        period_number=3,
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetDepreciationSchedule.objects.filter(
        tenant=tenant_a, fixed_asset=fixed_asset_a, period_number=3
    ).first()
    assert created is not None
    assert resp.url == reverse("assets:depreciation_schedule_detail", kwargs={"pk": created.pk})
    assert created.status == "calculated"
    assert created.depreciation_amount > Decimal("0.00")

    # Audit log entry written
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=created.pk,
        action="create",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_create_post_invalid(client_a):
    """depreciation_schedule_create invalid POST returns 200 with form errors."""
    url = reverse("assets:depreciation_schedule_create")
    # Empty payload missing fixed_asset
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].is_valid() is False
    assert "fixed_asset" in resp.context["form"].errors


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_edit_get_renders_form_for_draft(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_edit GET renders edit form for draft schedule."""
    url = reverse("assets:depreciation_schedule_edit", kwargs={"pk": depreciation_schedule_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["schedule"].pk == depreciation_schedule_a.pk


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_edit_get_blocked_for_posted(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_edit GET redirects to detail with error if schedule is already posted."""
    depreciation_schedule_a.status = "posted"
    depreciation_schedule_a.save()

    url = reverse("assets:depreciation_schedule_edit", kwargs={"pk": depreciation_schedule_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:depreciation_schedule_detail", kwargs={"pk": depreciation_schedule_a.pk})
    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("Posted depreciation schedules cannot be edited" in m for m in messages)


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_edit_post_success(
    client_a, tenant_a, depreciation_schedule_a, fixed_asset_a
):
    """depreciation_schedule_edit valid POST updates schedule, recalculates, writes audit log, and redirects."""
    url = reverse("assets:depreciation_schedule_edit", kwargs={"pk": depreciation_schedule_a.pk})
    payload = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        period_number=5,
        notes="Updated depreciation schedule notes for testing.",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:depreciation_schedule_detail", kwargs={"pk": depreciation_schedule_a.pk})

    depreciation_schedule_a.refresh_from_db()
    assert depreciation_schedule_a.period_number == 5
    assert "Updated depreciation schedule notes" in depreciation_schedule_a.notes

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=depreciation_schedule_a.pk,
        action="update",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_edit_post_invalid(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_edit invalid POST returns 200 with form errors."""
    url = reverse("assets:depreciation_schedule_edit", kwargs={"pk": depreciation_schedule_a.pk})
    resp = client_a.post(url, data={"schedule_date": ""})
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_delete_require_post(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_delete rejects GET with 405 Method Not Allowed."""
    url = reverse("assets:depreciation_schedule_delete", kwargs={"pk": depreciation_schedule_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_delete_tenant_admin_guard(
    member_client, depreciation_schedule_a
):
    """depreciation_schedule_delete requires tenant admin; member_client receives 403."""
    url = reverse("assets:depreciation_schedule_delete", kwargs={"pk": depreciation_schedule_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_delete_blocked_for_posted(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_delete blocks deletion of posted schedules, redirecting with error message."""
    depreciation_schedule_a.status = "posted"
    depreciation_schedule_a.save()

    url = reverse("assets:depreciation_schedule_delete", kwargs={"pk": depreciation_schedule_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:depreciation_schedule_detail", kwargs={"pk": depreciation_schedule_a.pk})
    assert AssetDepreciationSchedule.objects.filter(pk=depreciation_schedule_a.pk).exists()
    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("Cannot delete a posted depreciation schedule" in m for m in messages)


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_delete_success(
    client_a, tenant_a, depreciation_schedule_a
):
    """depreciation_schedule_delete successfully deletes draft schedule and writes audit log."""
    pk = depreciation_schedule_a.pk
    url = reverse("assets:depreciation_schedule_delete", kwargs={"pk": pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:depreciation_schedule_list")
    assert not AssetDepreciationSchedule.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_calculate_action(
    client_a, depreciation_schedule_a
):
    """depreciation_schedule_calculate action triggers calculation and logs audit."""
    url = reverse("assets:depreciation_schedule_calculate", kwargs={"pk": depreciation_schedule_a.pk})

    # GET rejected 405
    assert client_a.get(url).status_code == 405

    # POST triggers recalculate
    depreciation_schedule_a.depreciation_amount = Decimal("0.00")
    depreciation_schedule_a.save()

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:depreciation_schedule_detail", kwargs={"pk": depreciation_schedule_a.pk})

    depreciation_schedule_a.refresh_from_db()
    assert depreciation_schedule_a.depreciation_amount > Decimal("0.00")
    assert depreciation_schedule_a.status == "calculated"

    # Posted schedule calculate guard
    depreciation_schedule_a.status = "posted"
    depreciation_schedule_a.save()

    resp_posted = client_a.post(url)
    assert resp_posted.status_code == 302
    messages = _assetdepreciation_get_flash_messages(resp_posted)
    assert any("Cannot recalculate a posted depreciation schedule" in m for m in messages)


@pytest.mark.django_db
def test_assetdepreciation_views_schedule_post_action_success_and_guards(
    client_a, member_client, depreciation_schedule_a, fixed_asset_a, expense_account_a, accum_account_a
):
    """depreciation_schedule_post validates permissions, executes GL posting, and creates JournalEntry."""
    url = reverse("assets:depreciation_schedule_post", kwargs={"pk": depreciation_schedule_a.pk})

    # GET rejected 405
    assert client_a.get(url).status_code == 405

    # Member user rejected 403
    assert member_client.post(url).status_code == 403

    # Admin user POST posts to GL
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:depreciation_schedule_detail", kwargs={"pk": depreciation_schedule_a.pk})

    depreciation_schedule_a.refresh_from_db()
    assert depreciation_schedule_a.status == "posted"
    assert depreciation_schedule_a.journal_entry is not None
    assert isinstance(depreciation_schedule_a.journal_entry, JournalEntry)
    assert depreciation_schedule_a.journal_entry.status == "posted"

    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("posted to General Ledger" in m for m in messages)

    # Re-posting already posted schedule handles ValidationError gracefully
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages_again = _assetdepreciation_get_flash_messages(resp_again)
    assert any("already posted" in m for m in messages_again)


# ==============================================================================
# 2. AssetRevaluation Views
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_list_renders_200_and_context(
    client_a, revaluation_a
):
    """revaluation_list renders 200 with required context keys and aggregates."""
    url = reverse("assets:revaluation_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "revaluations" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "event_type_choices" in resp.context
    assert "status_choices" in resp.context
    assert "total_adjustment_value" in resp.context
    assert "total_events" in resp.context
    assert "approved_count" in resp.context
    assert "impairment_count" in resp.context
    assert "surplus_count" in resp.context
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert "selected_event_type" in resp.context
    assert "selected_status" in resp.context

    assert resp.context["total_events"] >= 1
    assert resp.context["surplus_count"] >= 1


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_list_filter_search(
    client_a, revaluation_a, fixed_asset_a
):
    """revaluation_list filters by q search query across number, title, fixed asset."""
    url = reverse("assets:revaluation_list")

    # Match by title
    resp_title = client_a.get(url, {"q": revaluation_a.title[:15]})
    assert resp_title.status_code == 200
    pks = [r.pk for r in resp_title.context["revaluations"]]
    assert revaluation_a.pk in pks

    # Match by fixed asset name
    resp_fa = client_a.get(url, {"q": fixed_asset_a.name[:10]})
    assert resp_fa.status_code == 200
    pks_fa = [r.pk for r in resp_fa.context["revaluations"]]
    assert revaluation_a.pk in pks_fa

    # No match
    resp_none = client_a.get(url, {"q": "NONEXISTENT_REVALUATION_SEARCH_XYZ"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["revaluations"]) == 0


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_list_filter_event_type_and_status(
    client_a, tenant_a, fixed_asset_a, revaluation_a, expense_account_a
):
    """revaluation_list filters by event_type and status."""
    url = reverse("assets:revaluation_list")

    # Create an impairment event with approved status
    rev_impair = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="CNC Minor Crack Impairment",
        fixed_asset=fixed_asset_a,
        event_type="impairment",
        valuation_method="market_approach",
        valuation_date=timezone.now().date(),
        historical_cost=Decimal("120000.00"),
        accumulated_depreciation_before=Decimal("20000.00"),
        carrying_value_before=Decimal("100000.00"),
        new_fair_market_value=Decimal("80000.00"),
        revaluation_adjustment=Decimal("-20000.00"),
        impairment_loss_account=expense_account_a,
        status="approved",
    )

    # Filter event_type=revaluation_up
    resp_up = client_a.get(url, {"event_type": "revaluation_up"})
    assert resp_up.status_code == 200
    up_pks = [r.pk for r in resp_up.context["revaluations"]]
    assert revaluation_a.pk in up_pks
    assert rev_impair.pk not in up_pks

    # Filter event_type=impairment
    resp_imp = client_a.get(url, {"event_type": "impairment"})
    assert resp_imp.status_code == 200
    imp_pks = [r.pk for r in resp_imp.context["revaluations"]]
    assert rev_impair.pk in imp_pks
    assert revaluation_a.pk not in imp_pks

    # Filter status=approved
    resp_appr = client_a.get(url, {"status": "approved"})
    assert resp_appr.status_code == 200
    appr_pks = [r.pk for r in resp_appr.context["revaluations"]]
    assert rev_impair.pk in appr_pks
    assert revaluation_a.pk not in appr_pks


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_list_junk_parameters_safe(
    client_a, revaluation_a
):
    """revaluation_list handles invalid event_type, status, and page without crashing."""
    url = reverse("assets:revaluation_list")
    resp = client_a.get(
        url,
        {
            "event_type": "alien_event_type",
            "status": "mythical_status",
            "page": "page_not_a_number",
        },
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_list_pagination(
    client_a, tenant_a, fixed_asset_a
):
    """revaluation_list paginates with 15 items per page."""
    for i in range(1, 18):
        AssetRevaluation.objects.create(
            tenant=tenant_a,
            title=f"Revaluation Batch Item {i}",
            fixed_asset=fixed_asset_a,
            event_type="revaluation_up",
            valuation_method="independent_appraisal",
            valuation_date=timezone.now().date(),
            historical_cost=Decimal("120000.00"),
            carrying_value_before=Decimal("100000.00"),
            new_fair_market_value=Decimal("105000.00"),
            revaluation_adjustment=Decimal("5000.00"),
            status="draft",
        )

    url = reverse("assets:revaluation_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["revaluations"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["revaluations"]) >= 2
    assert resp_p2.context["page_obj"].has_previous()

    # Out of range page defaults to last page
    resp_out = client_a.get(url, {"page": "99999"})
    assert resp_out.status_code == 200
    assert resp_out.context["page_obj"].number == resp_p2.context["page_obj"].number


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_detail_renders_200_and_context(
    client_a, revaluation_a
):
    """revaluation_detail renders 200 with revaluation and object context keys."""
    url = reverse("assets:revaluation_detail", kwargs={"pk": revaluation_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "revaluation" in resp.context
    assert "object" in resp.context
    assert resp.context["revaluation"].pk == revaluation_a.pk


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_detail_cross_tenant_404(
    client_b, revaluation_a
):
    """revaluation_detail returns 404 when accessed by another tenant."""
    url = reverse("assets:revaluation_detail", kwargs={"pk": revaluation_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_create_get_renders_form(client_a):
    """revaluation_create GET renders form with is_edit=False and empty instance."""
    url = reverse("assets:revaluation_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["revaluation"] is None
    assert resp.context["object"] is None


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_create_post_success(
    client_a, tenant_a, fixed_asset_a, expense_account_a
):
    """revaluation_create valid POST saves, auto-calculates adjustment, and redirects to detail."""
    url = reverse("assets:revaluation_create")
    payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        impairment_loss_account=expense_account_a,
        title="Q3 Machinery Impairment Assessment",
        new_fair_market_value="85000.00",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetRevaluation.objects.filter(
        tenant=tenant_a, title="Q3 Machinery Impairment Assessment"
    ).first()
    assert created is not None
    assert resp.url == reverse("assets:revaluation_detail", kwargs={"pk": created.pk})
    assert created.revaluation_adjustment != Decimal("0.00")

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=created.pk,
        action="create",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_create_post_invalid(client_a):
    """revaluation_create invalid POST returns 200 with form errors."""
    url = reverse("assets:revaluation_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_edit_get_renders_form_for_draft(
    client_a, revaluation_a
):
    """revaluation_edit GET renders edit form for draft revaluation."""
    url = reverse("assets:revaluation_edit", kwargs={"pk": revaluation_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["revaluation"].pk == revaluation_a.pk


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_edit_get_blocked_for_approved(
    client_a, revaluation_a
):
    """revaluation_edit GET redirects to detail with error if revaluation is already approved."""
    revaluation_a.status = "approved"
    revaluation_a.save()

    url = reverse("assets:revaluation_edit", kwargs={"pk": revaluation_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:revaluation_detail", kwargs={"pk": revaluation_a.pk})
    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("Approved revaluations cannot be edited" in m for m in messages)


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_edit_post_success(
    client_a, tenant_a, revaluation_a, fixed_asset_a, surplus_account_a
):
    """revaluation_edit valid POST updates record, recalculates adjustment, and redirects."""
    url = reverse("assets:revaluation_edit", kwargs={"pk": revaluation_a.pk})
    payload = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        event_type="revaluation_up",
        revaluation_surplus_account=surplus_account_a,
        title="Updated Appraisal Title",
        new_fair_market_value="130000.00",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:revaluation_detail", kwargs={"pk": revaluation_a.pk})

    revaluation_a.refresh_from_db()
    assert revaluation_a.title == "Updated Appraisal Title"
    assert revaluation_a.new_fair_market_value == Decimal("130000.00")

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=revaluation_a.pk,
        action="update",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_edit_post_invalid(
    client_a, revaluation_a
):
    """revaluation_edit invalid POST returns 200 with form errors."""
    url = reverse("assets:revaluation_edit", kwargs={"pk": revaluation_a.pk})
    resp = client_a.post(url, data={"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_delete_require_post(
    client_a, revaluation_a
):
    """revaluation_delete rejects GET with 405 Method Not Allowed."""
    url = reverse("assets:revaluation_delete", kwargs={"pk": revaluation_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_delete_tenant_admin_guard(
    member_client, revaluation_a
):
    """revaluation_delete requires tenant admin; member_client receives 403."""
    url = reverse("assets:revaluation_delete", kwargs={"pk": revaluation_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_delete_blocked_for_approved(
    client_a, revaluation_a
):
    """revaluation_delete blocks deletion of approved records, redirecting with error."""
    revaluation_a.status = "approved"
    revaluation_a.save()

    url = reverse("assets:revaluation_delete", kwargs={"pk": revaluation_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:revaluation_detail", kwargs={"pk": revaluation_a.pk})
    assert AssetRevaluation.objects.filter(pk=revaluation_a.pk).exists()
    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("Cannot delete an approved revaluation record" in m for m in messages)


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_delete_success(
    client_a, tenant_a, revaluation_a
):
    """revaluation_delete successfully deletes draft record and writes audit log."""
    pk = revaluation_a.pk
    url = reverse("assets:revaluation_delete", kwargs={"pk": pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:revaluation_list")
    assert not AssetRevaluation.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_revaluation_approve_action_success_and_guards(
    client_a, member_client, revaluation_a, fixed_asset_a, surplus_account_a, asset_account_a
):
    """revaluation_approve validates admin permissions, executes revaluation, creates JournalEntry."""
    url = reverse("assets:revaluation_approve", kwargs={"pk": revaluation_a.pk})

    # GET rejected 405
    assert client_a.get(url).status_code == 405

    # Member user rejected 403
    assert member_client.post(url).status_code == 403

    # Admin user POST approves
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:revaluation_detail", kwargs={"pk": revaluation_a.pk})

    revaluation_a.refresh_from_db()
    assert revaluation_a.status == "approved"
    assert revaluation_a.journal_entry is not None
    assert revaluation_a.journal_entry.status == "posted"

    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("approved and applied to fixed asset subledger" in m for m in messages)

    # Re-approving already approved revaluation handles ValidationError gracefully
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages_again = _assetdepreciation_get_flash_messages(resp_again)
    assert any("already been approved" in m for m in messages_again)


# ==============================================================================
# 3. AssetTransfer Views
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_list_renders_200_and_context(
    client_a, transfer_a
):
    """transfer_list renders 200 with required context keys and aggregates."""
    url = reverse("assets:transfer_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "transfers" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "transfer_type_choices" in resp.context
    assert "status_choices" in resp.context
    assert "total_transfers" in resp.context
    assert "in_transit_count" in resp.context
    assert "completed_count" in resp.context
    assert "total_transport_cost" in resp.context
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert "selected_type" in resp.context
    assert "selected_status" in resp.context

    assert resp.context["total_transfers"] >= 1


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_list_filter_search(
    client_a, transfer_a, fixed_asset_a
):
    """transfer_list filters by q search query across number, title, fixed asset."""
    url = reverse("assets:transfer_list")

    # Match by title
    resp_title = client_a.get(url, {"q": transfer_a.title[:15]})
    assert resp_title.status_code == 200
    pks = [t.pk for t in resp_title.context["transfers"]]
    assert transfer_a.pk in pks

    # Match by fixed asset name
    resp_fa = client_a.get(url, {"q": fixed_asset_a.name[:10]})
    assert resp_fa.status_code == 200
    pks_fa = [t.pk for t in resp_fa.context["transfers"]]
    assert transfer_a.pk in pks_fa

    # No match
    resp_none = client_a.get(url, {"q": "NONEXISTENT_TRANSFER_QUERY_XYZ"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["transfers"]) == 0


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_list_filter_type_and_status(
    client_a, tenant_a, fixed_asset_a, transfer_a
):
    """transfer_list filters by transfer_type and status."""
    url = reverse("assets:transfer_list")

    # Create a secondary transfer with cost_center type and in_transit status
    t_cc = AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Departmental Machine Reassignment",
        fixed_asset=fixed_asset_a,
        transfer_type="cost_center",
        transfer_date=timezone.now().date(),
        transportation_cost=Decimal("150.00"),
        status="in_transit",
    )

    # Filter type=inter_facility
    resp_if = client_a.get(url, {"type": "inter_facility"})
    assert resp_if.status_code == 200
    if_pks = [t.pk for t in resp_if.context["transfers"]]
    assert transfer_a.pk in if_pks
    assert t_cc.pk not in if_pks

    # Filter type=cost_center
    resp_cc = client_a.get(url, {"type": "cost_center"})
    assert resp_cc.status_code == 200
    cc_pks = [t.pk for t in resp_cc.context["transfers"]]
    assert t_cc.pk in cc_pks
    assert transfer_a.pk not in cc_pks

    # Filter status=in_transit
    resp_stat = client_a.get(url, {"status": "in_transit"})
    assert resp_stat.status_code == 200
    stat_pks = [t.pk for t in resp_stat.context["transfers"]]
    assert t_cc.pk in stat_pks
    assert transfer_a.pk not in stat_pks


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_list_junk_parameters_safe(
    client_a, transfer_a
):
    """transfer_list handles invalid type, status, and page without crashing."""
    url = reverse("assets:transfer_list")
    resp = client_a.get(
        url,
        {
            "type": "space_teleportation",
            "status": "mythical_status",
            "page": "page_not_a_number",
        },
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_list_pagination(
    client_a, tenant_a, fixed_asset_a
):
    """transfer_list paginates with 15 items per page."""
    for i in range(1, 18):
        AssetTransfer.objects.create(
            tenant=tenant_a,
            title=f"Transfer Order #{i}",
            fixed_asset=fixed_asset_a,
            transfer_type="custodian_change",
            transfer_date=timezone.now().date(),
            transportation_cost=Decimal("100.00"),
            status="draft",
        )

    url = reverse("assets:transfer_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["transfers"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["transfers"]) >= 2
    assert resp_p2.context["page_obj"].has_previous()

    # Out of range page defaults to last page
    resp_out = client_a.get(url, {"page": "99999"})
    assert resp_out.status_code == 200
    assert resp_out.context["page_obj"].number == resp_p2.context["page_obj"].number


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_detail_renders_200_and_context(
    client_a, transfer_a
):
    """transfer_detail renders 200 with transfer and object context keys."""
    url = reverse("assets:transfer_detail", kwargs={"pk": transfer_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "transfer" in resp.context
    assert "object" in resp.context
    assert resp.context["transfer"].pk == transfer_a.pk


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_detail_cross_tenant_404(
    client_b, transfer_a
):
    """transfer_detail returns 404 when accessed by another tenant."""
    url = reverse("assets:transfer_detail", kwargs={"pk": transfer_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_create_get_renders_form(client_a):
    """transfer_create GET renders form with is_edit=False and empty instance."""
    url = reverse("assets:transfer_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["transfer"] is None
    assert resp.context["object"] is None


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_create_post_success(
    client_a, tenant_a, fixed_asset_a, location_a, location_a2
):
    """transfer_create valid POST saves, auto-captures carrying value, and redirects to detail."""
    url = reverse("assets:transfer_create")
    payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_location=location_a,
        destination_location=location_a2,
        title="Inter-Building CNC Relocation Order",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetTransfer.objects.filter(
        tenant=tenant_a, title="Inter-Building CNC Relocation Order"
    ).first()
    assert created is not None
    assert resp.url == reverse("assets:transfer_detail", kwargs={"pk": created.pk})
    assert created.carrying_value_at_transfer is not None

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=created.pk,
        action="create",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_create_post_invalid(client_a):
    """transfer_create invalid POST returns 200 with form errors."""
    url = reverse("assets:transfer_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_edit_get_renders_form_for_draft(
    client_a, transfer_a
):
    """transfer_edit GET renders edit form for draft transfer."""
    url = reverse("assets:transfer_edit", kwargs={"pk": transfer_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["transfer"].pk == transfer_a.pk


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_edit_get_blocked_for_completed(
    client_a, transfer_a
):
    """transfer_edit GET redirects to detail with error if transfer is already completed."""
    transfer_a.status = "completed"
    transfer_a.save()

    url = reverse("assets:transfer_edit", kwargs={"pk": transfer_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:transfer_detail", kwargs={"pk": transfer_a.pk})
    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("Completed transfers cannot be edited" in m for m in messages)


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_edit_post_success(
    client_a, tenant_a, transfer_a, fixed_asset_a
):
    """transfer_edit valid POST updates record, recaptures carrying value, and redirects."""
    url = reverse("assets:transfer_edit", kwargs={"pk": transfer_a.pk})
    payload = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        title="Updated Transfer Order Title",
        transportation_cost="850.00",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:transfer_detail", kwargs={"pk": transfer_a.pk})

    transfer_a.refresh_from_db()
    assert transfer_a.title == "Updated Transfer Order Title"
    assert transfer_a.transportation_cost == Decimal("850.00")

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=transfer_a.pk,
        action="update",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_edit_post_invalid(
    client_a, transfer_a
):
    """transfer_edit invalid POST returns 200 with form errors."""
    url = reverse("assets:transfer_edit", kwargs={"pk": transfer_a.pk})
    resp = client_a.post(url, data={"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_delete_require_post(
    client_a, transfer_a
):
    """transfer_delete rejects GET with 405 Method Not Allowed."""
    url = reverse("assets:transfer_delete", kwargs={"pk": transfer_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_delete_tenant_admin_guard(
    member_client, transfer_a
):
    """transfer_delete requires tenant admin; member_client receives 403."""
    url = reverse("assets:transfer_delete", kwargs={"pk": transfer_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_delete_blocked_for_completed(
    client_a, transfer_a
):
    """transfer_delete blocks deletion of completed transfers, redirecting with error."""
    transfer_a.status = "completed"
    transfer_a.save()

    url = reverse("assets:transfer_delete", kwargs={"pk": transfer_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:transfer_detail", kwargs={"pk": transfer_a.pk})
    assert AssetTransfer.objects.filter(pk=transfer_a.pk).exists()
    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("Cannot delete a completed transfer order" in m for m in messages)


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_delete_success(
    client_a, tenant_a, transfer_a
):
    """transfer_delete successfully deletes draft transfer and writes audit log."""
    pk = transfer_a.pk
    url = reverse("assets:transfer_delete", kwargs={"pk": pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:transfer_list")
    assert not AssetTransfer.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_dispatch_action(
    client_a, transfer_a
):
    """transfer_dispatch transitions status to in_transit and captures carrying value."""
    url = reverse("assets:transfer_dispatch", kwargs={"pk": transfer_a.pk})

    # GET rejected 405
    assert client_a.get(url).status_code == 405

    # POST dispatches
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:transfer_detail", kwargs={"pk": transfer_a.pk})

    transfer_a.refresh_from_db()
    assert transfer_a.status == "in_transit"
    assert transfer_a.carrying_value_at_transfer is not None

    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("marked In Transit" in m for m in messages)

    # Re-dispatching non-draft order handles ValidationError
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages_again = _assetdepreciation_get_flash_messages(resp_again)
    assert any("Only draft transfer orders can be dispatched" in m for m in messages_again)


@pytest.mark.django_db
def test_assetdepreciation_views_transfer_complete_action_success_and_guards(
    client_a, member_client, transfer_a, fixed_asset_a, operational_asset_a, location_a2, org_unit_a, vendor_party_a, expense_account_a
):
    """transfer_complete validates admin permission, updates asset records, and sets status=completed."""
    transfer_a.status = "in_transit"
    transfer_a.destination_department = org_unit_a
    transfer_a.destination_location = location_a2
    transfer_a.destination_custodian = vendor_party_a
    transfer_a.destination_expense_account = expense_account_a
    transfer_a.save()

    url = reverse("assets:transfer_complete", kwargs={"pk": transfer_a.pk})

    # GET rejected 405
    assert client_a.get(url).status_code == 405

    # Member user rejected 403
    assert member_client.post(url).status_code == 403

    # Admin user POST completes transfer
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:transfer_detail", kwargs={"pk": transfer_a.pk})

    transfer_a.refresh_from_db()
    assert transfer_a.status == "completed"

    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.location == org_unit_a
    assert fixed_asset_a.custodian == vendor_party_a

    operational_asset_a.refresh_from_db()
    assert operational_asset_a.location == location_a2
    assert operational_asset_a.custodian == vendor_party_a

    messages = _assetdepreciation_get_flash_messages(resp)
    assert any("Fixed asset allocations updated" in m for m in messages)

    # Completing already completed transfer handles ValidationError
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages_again = _assetdepreciation_get_flash_messages(resp_again)
    assert any("already been completed" in m for m in messages_again)


# ==============================================================================
# 4. CapitalizationPolicy Views
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_views_policy_list_renders_200_and_context(
    client_a, capitalization_policy_a
):
    """capitalization_policy_list renders 200 with required context keys and aggregates."""
    url = reverse("assets:capitalization_policy_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "policies" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "scope_choices" in resp.context
    assert "categories" in resp.context
    assert "total_policies" in resp.context
    assert "active_count" in resp.context
    assert "safe_harbor_count" in resp.context
    assert "override_count" in resp.context
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert "selected_scope" in resp.context
    assert "selected_category" in resp.context

    assert resp.context["total_policies"] >= 1
    assert resp.context["active_count"] >= 1


@pytest.mark.django_db
def test_assetdepreciation_views_policy_list_filter_search(
    client_a, capitalization_policy_a
):
    """capitalization_policy_list filters by q search query across name, standard, notes."""
    url = reverse("assets:capitalization_policy_list")

    # Match by policy name
    resp_name = client_a.get(url, {"q": capitalization_policy_a.name[:10]})
    assert resp_name.status_code == 200
    pks = [p.pk for p in resp_name.context["policies"]]
    assert capitalization_policy_a.pk in pks

    # No match
    resp_none = client_a.get(url, {"q": "NONEXISTENT_CAPEX_POLICY_QUERY_XYZ"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["policies"]) == 0


@pytest.mark.django_db
def test_assetdepreciation_views_policy_list_filter_scope_and_category(
    client_a, tenant_a, category_root_a, capitalization_policy_a, cip_account_a, expense_account_a
):
    """capitalization_policy_list filters by policy_scope and category."""
    url = reverse("assets:capitalization_policy_list")

    # Create a secondary global default policy without category
    pol_global = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Global CapEx Base Policy",
        policy_scope="global_default",
        category=None,
        minimum_cost_threshold=Decimal("2500.00"),
        minimum_useful_life_months=12,
        default_classification="capitalize",
        is_active=True,
    )

    # Filter scope=category_override
    resp_ov = client_a.get(url, {"scope": "category_override"})
    assert resp_ov.status_code == 200
    ov_pks = [p.pk for p in resp_ov.context["policies"]]
    assert capitalization_policy_a.pk in ov_pks
    assert pol_global.pk not in ov_pks

    # Filter scope=global_default
    resp_gd = client_a.get(url, {"scope": "global_default"})
    assert resp_gd.status_code == 200
    gd_pks = [p.pk for p in resp_gd.context["policies"]]
    assert pol_global.pk in gd_pks
    assert capitalization_policy_a.pk not in gd_pks

    # Filter category
    resp_cat = client_a.get(url, {"category": str(category_root_a.pk)})
    assert resp_cat.status_code == 200
    cat_pks = [p.pk for p in resp_cat.context["policies"]]
    assert capitalization_policy_a.pk in cat_pks
    assert pol_global.pk not in cat_pks


@pytest.mark.django_db
def test_assetdepreciation_views_policy_list_junk_parameters_safe(
    client_a, capitalization_policy_a
):
    """capitalization_policy_list handles invalid scope, category, and page without crashing."""
    url = reverse("assets:capitalization_policy_list")
    resp = client_a.get(
        url,
        {
            "scope": "interstellar_scope",
            "category": "not_an_int",
            "page": "page_not_a_number",
        },
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_assetdepreciation_views_policy_list_pagination(
    client_a, tenant_a
):
    """capitalization_policy_list paginates with 15 items per page."""
    for i in range(1, 18):
        CapitalizationPolicy.objects.create(
            tenant=tenant_a,
            name=f"Policy Item #{i}",
            policy_scope="global_default",
            minimum_cost_threshold=Decimal("1000.00"),
            minimum_useful_life_months=12,
            default_classification="capitalize",
            is_active=True,
        )

    url = reverse("assets:capitalization_policy_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["policies"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["policies"]) >= 2
    assert resp_p2.context["page_obj"].has_previous()

    # Out of range page defaults to last page
    resp_out = client_a.get(url, {"page": "99999"})
    assert resp_out.status_code == 200
    assert resp_out.context["page_obj"].number == resp_p2.context["page_obj"].number


@pytest.mark.django_db
def test_assetdepreciation_views_policy_detail_renders_200_and_context(
    client_a, capitalization_policy_a
):
    """capitalization_policy_detail renders 200 with policy, object, and empty eval_result."""
    url = reverse("assets:capitalization_policy_detail", kwargs={"pk": capitalization_policy_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "policy" in resp.context
    assert "object" in resp.context
    assert resp.context["policy"].pk == capitalization_policy_a.pk
    assert resp.context["eval_result"] is None


@pytest.mark.django_db
def test_assetdepreciation_views_policy_detail_evaluator_valid_and_edge_cases(
    client_a, capitalization_policy_a
):
    """capitalization_policy_detail evaluator handles valid queries, negative numbers, strings, and NaN/inf."""
    url = reverse("assets:capitalization_policy_detail", kwargs={"pk": capitalization_policy_a.pk})

    # 1. Valid evaluation meeting thresholds -> capitalize
    resp_cap = client_a.get(url, {"eval_cost": "10000.00", "eval_life": "24"})
    assert resp_cap.status_code == 200
    assert resp_cap.context["eval_result"] is not None
    assert resp_cap.context["eval_result"]["classification"] == "capitalize"
    assert "Meets capitalization threshold" in resp_cap.context["eval_result"]["reason"]

    # 2. Valid evaluation failing cost threshold -> default_classification
    resp_exp = client_a.get(url, {"eval_cost": "1500.00", "eval_life": "24"})
    assert resp_exp.status_code == 200
    assert resp_exp.context["eval_result"] is not None
    assert resp_exp.context["eval_result"]["classification"] == capitalization_policy_a.default_classification

    # 3. Negative cost value -> caught gracefully, eval_result is None
    resp_neg = client_a.get(url, {"eval_cost": "-500.00", "eval_life": "12"})
    assert resp_neg.status_code == 200
    assert resp_neg.context["eval_result"] is None

    # 4. Invalid string cost value -> caught gracefully, eval_result is None
    resp_str = client_a.get(url, {"eval_cost": "not_a_valid_number", "eval_life": "12"})
    assert resp_str.status_code == 200
    assert resp_str.context["eval_result"] is None

    # 5. NaN and Infinity values -> caught gracefully, eval_result is None
    for inf_val in ["NaN", "Infinity", "-Infinity", "inf", "-inf"]:
        resp_inf = client_a.get(url, {"eval_cost": inf_val, "eval_life": "12"})
        assert resp_inf.status_code == 200
        assert resp_inf.context["eval_result"] is None


@pytest.mark.django_db
def test_assetdepreciation_views_policy_detail_cross_tenant_404(
    client_b, capitalization_policy_a
):
    """capitalization_policy_detail returns 404 when accessed by another tenant."""
    url = reverse("assets:capitalization_policy_detail", kwargs={"pk": capitalization_policy_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetdepreciation_views_policy_create_get_renders_form(client_a):
    """capitalization_policy_create GET renders form with is_edit=False and empty instance."""
    url = reverse("assets:capitalization_policy_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["policy"] is None
    assert resp.context["object"] is None


@pytest.mark.django_db
def test_assetdepreciation_views_policy_create_post_success(
    client_a, tenant_a, category_root_a, cip_account_a, expense_account_a
):
    """capitalization_policy_create valid POST saves, logs audit, and redirects to detail."""
    url = reverse("assets:capitalization_policy_create")
    payload = _assetdepreciation_policy_payload(
        name="New Production Tooling CapEx Standard",
        category=category_root_a,
        default_cip_account=cip_account_a,
        default_expense_account=expense_account_a,
        minimum_cost_threshold="7500.00",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = CapitalizationPolicy.objects.filter(
        tenant=tenant_a, name="New Production Tooling CapEx Standard"
    ).first()
    assert created is not None
    assert resp.url == reverse("assets:capitalization_policy_detail", kwargs={"pk": created.pk})
    assert created.minimum_cost_threshold == Decimal("7500.00")

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=created.pk,
        action="create",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_policy_create_post_invalid(client_a):
    """capitalization_policy_create invalid POST returns 200 with form errors."""
    url = reverse("assets:capitalization_policy_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False


@pytest.mark.django_db
def test_assetdepreciation_views_policy_edit_get_renders_form(
    client_a, capitalization_policy_a
):
    """capitalization_policy_edit GET renders edit form."""
    url = reverse("assets:capitalization_policy_edit", kwargs={"pk": capitalization_policy_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["policy"].pk == capitalization_policy_a.pk


@pytest.mark.django_db
def test_assetdepreciation_views_policy_edit_post_success(
    client_a, tenant_a, capitalization_policy_a
):
    """capitalization_policy_edit valid POST updates record and redirects to detail."""
    url = reverse("assets:capitalization_policy_edit", kwargs={"pk": capitalization_policy_a.pk})
    payload = _assetdepreciation_policy_payload(
        name="Updated CapEx Policy Title",
        minimum_cost_threshold="6000.00",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:capitalization_policy_detail", kwargs={"pk": capitalization_policy_a.pk})

    capitalization_policy_a.refresh_from_db()
    assert capitalization_policy_a.name == "Updated CapEx Policy Title"
    assert capitalization_policy_a.minimum_cost_threshold == Decimal("6000.00")

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=capitalization_policy_a.pk,
        action="update",
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_assetdepreciation_views_policy_edit_post_invalid(
    client_a, capitalization_policy_a
):
    """capitalization_policy_edit invalid POST returns 200 with form errors."""
    url = reverse("assets:capitalization_policy_edit", kwargs={"pk": capitalization_policy_a.pk})
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False


@pytest.mark.django_db
def test_assetdepreciation_views_policy_delete_require_post(
    client_a, capitalization_policy_a
):
    """capitalization_policy_delete rejects GET with 405 Method Not Allowed."""
    url = reverse("assets:capitalization_policy_delete", kwargs={"pk": capitalization_policy_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetdepreciation_views_policy_delete_tenant_admin_guard(
    member_client, capitalization_policy_a
):
    """capitalization_policy_delete requires tenant admin; member_client receives 403."""
    url = reverse("assets:capitalization_policy_delete", kwargs={"pk": capitalization_policy_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetdepreciation_views_policy_delete_success(
    client_a, tenant_a, capitalization_policy_a
):
    """capitalization_policy_delete successfully deletes policy and writes audit log."""
    pk = capitalization_policy_a.pk
    url = reverse("assets:capitalization_policy_delete", kwargs={"pk": pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:capitalization_policy_list")
    assert not CapitalizationPolicy.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).first()
    assert audit is not None


# ==============================================================================
# 5. Security & Isolation Views
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_views_unauthenticated_redirects():
    """Unauthenticated access to any view redirects to login page."""
    anon = Client()

    test_urls = [
        reverse("assets:depreciation_schedule_list"),
        reverse("assets:depreciation_schedule_create"),
        reverse("assets:depreciation_schedule_detail", kwargs={"pk": 1}),
        reverse("assets:depreciation_schedule_edit", kwargs={"pk": 1}),
        reverse("assets:revaluation_list"),
        reverse("assets:revaluation_create"),
        reverse("assets:revaluation_detail", kwargs={"pk": 1}),
        reverse("assets:revaluation_edit", kwargs={"pk": 1}),
        reverse("assets:transfer_list"),
        reverse("assets:transfer_create"),
        reverse("assets:transfer_detail", kwargs={"pk": 1}),
        reverse("assets:transfer_edit", kwargs={"pk": 1}),
        reverse("assets:capitalization_policy_list"),
        reverse("assets:capitalization_policy_create"),
        reverse("assets:capitalization_policy_detail", kwargs={"pk": 1}),
        reverse("assets:capitalization_policy_edit", kwargs={"pk": 1}),
    ]

    for u in test_urls:
        resp = anon.get(u)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_assetdepreciation_views_cross_tenant_edit_delete_actions_404(
    client_b, depreciation_schedule_a, revaluation_a, transfer_a, capitalization_policy_a
):
    """Tenant B cannot access or mutate Tenant A records; all return 404."""
    # Edit GET / POST
    assert client_b.get(reverse("assets:depreciation_schedule_edit", kwargs={"pk": depreciation_schedule_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:depreciation_schedule_edit", kwargs={"pk": depreciation_schedule_a.pk})).status_code == 404

    assert client_b.get(reverse("assets:revaluation_edit", kwargs={"pk": revaluation_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:revaluation_edit", kwargs={"pk": revaluation_a.pk})).status_code == 404

    assert client_b.get(reverse("assets:transfer_edit", kwargs={"pk": transfer_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:transfer_edit", kwargs={"pk": transfer_a.pk})).status_code == 404

    assert client_b.get(reverse("assets:capitalization_policy_edit", kwargs={"pk": capitalization_policy_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:capitalization_policy_edit", kwargs={"pk": capitalization_policy_a.pk})).status_code == 404

    # Delete POST
    assert client_b.post(reverse("assets:depreciation_schedule_delete", kwargs={"pk": depreciation_schedule_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:revaluation_delete", kwargs={"pk": revaluation_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:transfer_delete", kwargs={"pk": transfer_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:capitalization_policy_delete", kwargs={"pk": capitalization_policy_a.pk})).status_code == 404

    # Actions POST
    assert client_b.post(reverse("assets:depreciation_schedule_calculate", kwargs={"pk": depreciation_schedule_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:depreciation_schedule_post", kwargs={"pk": depreciation_schedule_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:revaluation_approve", kwargs={"pk": revaluation_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:transfer_dispatch", kwargs={"pk": transfer_a.pk})).status_code == 404
    assert client_b.post(reverse("assets:transfer_complete", kwargs={"pk": transfer_a.pk})).status_code == 404
