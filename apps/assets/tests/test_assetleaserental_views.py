"""Functional view and workflow action tests for Module 11.10 Lease & Rental Management."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.models.AssetLeaseRental.AssetLeaseSchedules import AssetLeaseSchedule
from apps.assets.models.AssetLeaseRental.AssetLeaseModifications import AssetLeaseModification
from apps.assets.models.AssetLeaseRental.AssetLeaseBuyAnalyses import AssetLeaseBuyAnalysis


# ===========================================================================
# 1. AssetLeaseContract View Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_contract_list_view(client_a, lease_contract_a):
    url = reverse("assets:asset_lease_contract_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "leases" in resp.context
    assert lease_contract_a in resp.context["leases"]
    assert "status_choices" in resp.context
    assert "classification_choices" in resp.context
    assert "lessor_list" in resp.context
    assert "total_leases" in resp.context
    assert "active_count" in resp.context


@pytest.mark.django_db
def test_assetleaserental_contract_list_filtering(client_a, lease_contract_a):
    url = reverse("assets:asset_lease_contract_list")
    resp = client_a.get(f"{url}?status=active&classification=finance")
    assert resp.status_code == 200
    assert lease_contract_a in resp.context["leases"]

    resp_mismatch = client_a.get(f"{url}?status=draft")
    assert resp_mismatch.status_code == 200
    assert lease_contract_a not in resp_mismatch.context["leases"]


@pytest.mark.django_db
def test_assetleaserental_contract_detail_view(client_a, lease_contract_a, lease_schedule_a, lease_modification_a):
    url = reverse("assets:asset_lease_contract_detail", kwargs={"pk": lease_contract_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["lease"] == lease_contract_a
    assert "schedules" in resp.context
    assert "modifications" in resp.context


@pytest.mark.django_db
def test_assetleaserental_contract_create_view(client_a, tenant_a, vendor_party_a, category_root_a):
    url = reverse("assets:asset_lease_contract_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    today = timezone.now().date()
    data = {
        "title": "Haas Machining Center Operating Lease",
        "master_lease_agreement_ref": "MLA-TEST-001",
        "lessor": vendor_party_a.pk,
        "category": category_root_a.pk,
        "inception_date": today.strftime("%Y-%m-%d"),
        "commencement_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today + timezone.timedelta(days=730)).strftime("%Y-%m-%d"),
        "first_payment_date": today.strftime("%Y-%m-%d"),
        "lease_term_months": 24,
        "economic_life_months": 60,
        "payment_amount": "3200.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "5.5000",
        "fair_market_value": "95000.00",
        "initial_direct_costs": "0.00",
        "lease_incentives": "0.00",
        "residual_value_guarantee": "0.00",
        "purchase_option_price": "0.00",
        "classification": "operating",
        "status": "draft",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    created = AssetLeaseContract.objects.get(title="Haas Machining Center Operating Lease", tenant=tenant_a)
    assert created.lease_term_months == 24
    assert created.classification == "operating"


@pytest.mark.django_db
def test_assetleaserental_contract_edit_view(client_a, tenant_a, vendor_party_a, category_root_a):
    today = timezone.now().date()
    contract = AssetLeaseContract.objects.create(
        tenant=tenant_a,
        title="Forklift Short-Term Rental",
        lessor=vendor_party_a,
        category=category_root_a,
        inception_date=today,
        commencement_date=today,
        expiration_date=today + timezone.timedelta(days=365),
        first_payment_date=today,
        lease_term_months=12,
        economic_life_months=60,
        payment_amount=Decimal("1500.00"),
        status="draft",
    )
    url = reverse("assets:asset_lease_contract_edit", kwargs={"pk": contract.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    data = {
        "title": "Forklift Short-Term Rental Updated",
        "lessor": vendor_party_a.pk,
        "category": category_root_a.pk,
        "inception_date": today.strftime("%Y-%m-%d"),
        "commencement_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today + timezone.timedelta(days=365)).strftime("%Y-%m-%d"),
        "first_payment_date": today.strftime("%Y-%m-%d"),
        "lease_term_months": 12,
        "economic_life_months": 60,
        "payment_amount": "1800.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "5.0000",
        "fair_market_value": "35000.00",
        "initial_direct_costs": "0.00",
        "lease_incentives": "0.00",
        "residual_value_guarantee": "0.00",
        "purchase_option_price": "0.00",
        "classification": "operating",
        "status": "draft",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    contract.refresh_from_db()
    assert contract.title == "Forklift Short-Term Rental Updated"
    assert contract.payment_amount == Decimal("1800.00")


@pytest.mark.django_db
def test_assetleaserental_contract_delete_view(client_a, tenant_a, vendor_party_a, category_root_a):
    today = timezone.now().date()
    contract = AssetLeaseContract.objects.create(
        tenant=tenant_a,
        title="Temporary Delete Lease",
        lessor=vendor_party_a,
        category=category_root_a,
        commencement_date=today,
        expiration_date=today + timezone.timedelta(days=365),
        first_payment_date=today,
        lease_term_months=12,
        payment_amount=Decimal("1000.00"),
        status="draft",
    )
    url = reverse("assets:asset_lease_contract_delete", kwargs={"pk": contract.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not AssetLeaseContract.objects.filter(pk=contract.pk).exists()


@pytest.mark.django_db
def test_assetleaserental_contract_calculate_action(client_a, tenant_a, vendor_party_a, category_root_a):
    today = timezone.now().date()
    contract = AssetLeaseContract.objects.create(
        tenant=tenant_a,
        title="Uncalculated Lease Agreement",
        lessor=vendor_party_a,
        category=category_root_a,
        inception_date=today,
        commencement_date=today,
        expiration_date=today + timezone.timedelta(days=730),
        first_payment_date=today,
        lease_term_months=24,
        economic_life_months=48,
        payment_amount=Decimal("2000.00"),
        payment_frequency="monthly",
        payment_timing="arrears",
        discount_rate_pct=Decimal("6.0000"),
        fair_market_value=Decimal("50000.00"),
        status="draft",
    )
    url = reverse("assets:asset_lease_contract_calculate", kwargs={"pk": contract.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    contract.refresh_from_db()
    assert contract.initial_lease_liability > 0
    assert contract.initial_rou_asset_value > 0


@pytest.mark.django_db
def test_assetleaserental_contract_activate_action(client_a, tenant_a, vendor_party_a, category_root_a):
    today = timezone.now().date()
    contract = AssetLeaseContract.objects.create(
        tenant=tenant_a,
        title="Pending Inception Agreement",
        lessor=vendor_party_a,
        category=category_root_a,
        inception_date=today,
        commencement_date=today,
        expiration_date=today + timezone.timedelta(days=365),
        first_payment_date=today,
        lease_term_months=12,
        economic_life_months=60,
        payment_amount=Decimal("1500.00"),
        payment_frequency="monthly",
        payment_timing="arrears",
        discount_rate_pct=Decimal("5.0000"),
        fair_market_value=Decimal("30000.00"),
        status="draft",
    )
    url = reverse("assets:asset_lease_contract_activate", kwargs={"pk": contract.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    contract.refresh_from_db()
    assert contract.status == "active"
    assert contract.payment_schedules.count() == 12


@pytest.mark.django_db
def test_assetleaserental_contract_terminate_action(client_a, lease_contract_a):
    url = reverse("assets:asset_lease_contract_terminate", kwargs={"pk": lease_contract_a.pk})
    resp = client_a.post(url, {"action_type": "terminate", "notes": "Asset returned early."})
    assert resp.status_code == 302
    lease_contract_a.refresh_from_db()
    assert lease_contract_a.status == "terminated"


# ===========================================================================
# 2. AssetLeaseSchedule View Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_schedule_list_view(client_a, lease_schedule_a):
    url = reverse("assets:asset_lease_schedule_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "schedules" in resp.context
    assert lease_schedule_a in resp.context["schedules"]
    assert "status_choices" in resp.context
    assert "lease_list" in resp.context
    assert "total_schedules" in resp.context


@pytest.mark.django_db
def test_assetleaserental_schedule_list_filtering(client_a, lease_schedule_a, lease_contract_a):
    url = reverse("assets:asset_lease_schedule_list")
    resp = client_a.get(f"{url}?status=paid&lease={lease_contract_a.pk}")
    assert resp.status_code == 200
    assert lease_schedule_a in resp.context["schedules"]

    resp_empty = client_a.get(f"{url}?status=cancelled")
    assert resp_empty.status_code == 200
    assert lease_schedule_a not in resp_empty.context["schedules"]


@pytest.mark.django_db
def test_assetleaserental_schedule_detail_view(client_a, lease_schedule_a):
    url = reverse("assets:asset_lease_schedule_detail", kwargs={"pk": lease_schedule_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["schedule"] == lease_schedule_a


@pytest.mark.django_db
def test_assetleaserental_schedule_create_view(client_a, lease_contract_a):
    url = reverse("assets:asset_lease_schedule_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    today = timezone.now().date()
    data = {
        "lease_contract": lease_contract_a.pk,
        "period_number": 50,
        "due_date": today.strftime("%Y-%m-%d"),
        "payment_amount": "4500.00",
        "beginning_liability": "20000.00",
        "interest_expense": "100.00",
        "principal_reduction": "4400.00",
        "ending_liability": "15600.00",
        "rou_depreciation": "4000.00",
        "ending_rou_asset_value": "15000.00",
        "status": "scheduled",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    created = AssetLeaseSchedule.objects.get(lease_contract=lease_contract_a, period_number=50)
    assert created.payment_amount == Decimal("4500.00")


@pytest.mark.django_db
def test_assetleaserental_schedule_edit_view(client_a, lease_schedule_a):
    url = reverse("assets:asset_lease_schedule_edit", kwargs={"pk": lease_schedule_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    data = {
        "lease_contract": lease_schedule_a.lease_contract.pk,
        "period_number": lease_schedule_a.period_number,
        "due_date": lease_schedule_a.due_date.strftime("%Y-%m-%d"),
        "payment_amount": "4600.00",
        "beginning_liability": str(lease_schedule_a.beginning_liability),
        "interest_expense": str(lease_schedule_a.interest_expense),
        "principal_reduction": str(lease_schedule_a.principal_reduction),
        "ending_liability": str(lease_schedule_a.ending_liability),
        "rou_depreciation": str(lease_schedule_a.rou_depreciation),
        "ending_rou_asset_value": str(lease_schedule_a.ending_rou_asset_value),
        "status": "scheduled",
        "payment_reference": "REF-UPDATED-001",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    lease_schedule_a.refresh_from_db()
    assert lease_schedule_a.payment_amount == Decimal("4600.00")
    assert lease_schedule_a.payment_reference == "REF-UPDATED-001"


@pytest.mark.django_db
def test_assetleaserental_schedule_delete_view(client_a, tenant_a, lease_contract_a):
    sched = AssetLeaseSchedule.objects.create(
        tenant=tenant_a,
        lease_contract=lease_contract_a,
        period_number=999,
        due_date=timezone.now().date(),
        payment_amount=Decimal("1000.00"),
        status="scheduled",
    )
    url = reverse("assets:asset_lease_schedule_delete", kwargs={"pk": sched.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not AssetLeaseSchedule.objects.filter(pk=sched.pk).exists()


@pytest.mark.django_db
def test_assetleaserental_schedule_mark_paid_action(client_a, tenant_a, lease_contract_a):
    today = timezone.now().date()
    sched = AssetLeaseSchedule.objects.create(
        tenant=tenant_a,
        lease_contract=lease_contract_a,
        period_number=998,
        due_date=today,
        payment_amount=Decimal("4500.00"),
        beginning_liability=Decimal("50000.00"),
        ending_liability=Decimal("46000.00"),
        ending_rou_asset_value=Decimal("45000.00"),
        status="scheduled",
    )
    url = reverse("assets:asset_lease_schedule_mark_paid", kwargs={"pk": sched.pk})
    resp = client_a.post(url, {
        "paid_date": today.strftime("%Y-%m-%d"),
        "payment_reference": "ACH-PAID-0992",
    })
    assert resp.status_code == 302
    sched.refresh_from_db()
    assert sched.status == "paid"
    assert sched.payment_reference == "ACH-PAID-0992"


@pytest.mark.django_db
def test_assetleaserental_schedule_accrue_action(client_a, lease_schedule_a):
    url = reverse("assets:asset_lease_schedule_accrue", kwargs={"pk": lease_schedule_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    lease_schedule_a.refresh_from_db()
    assert lease_schedule_a.status == "accrued"


# ===========================================================================
# 3. AssetLeaseModification View Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_modification_list_view(client_a, lease_modification_a):
    url = reverse("assets:asset_lease_modification_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "modifications" in resp.context
    assert lease_modification_a in resp.context["modifications"]
    assert "status_choices" in resp.context
    assert "type_choices" in resp.context
    assert "lease_list" in resp.context
    assert "total_modifications" in resp.context


@pytest.mark.django_db
def test_assetleaserental_modification_list_filtering(client_a, lease_modification_a, lease_contract_a):
    url = reverse("assets:asset_lease_modification_list")
    resp = client_a.get(f"{url}?status=executed&type=term_extension")
    assert resp.status_code == 200
    assert lease_modification_a in resp.context["modifications"]

    resp_mismatch = client_a.get(f"{url}?status=rejected")
    assert resp_mismatch.status_code == 200
    assert lease_modification_a not in resp_mismatch.context["modifications"]


@pytest.mark.django_db
def test_assetleaserental_modification_detail_view(client_a, lease_modification_a):
    url = reverse("assets:asset_lease_modification_detail", kwargs={"pk": lease_modification_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["modification"] == lease_modification_a


@pytest.mark.django_db
def test_assetleaserental_modification_create_view(client_a, lease_contract_a, admin_user):
    url = reverse("assets:asset_lease_modification_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    today = timezone.now().date()
    data = {
        "lease_contract": lease_contract_a.pk,
        "modification_type": "term_extension",
        "request_date": today.strftime("%Y-%m-%d"),
        "effective_date": today.strftime("%Y-%m-%d"),
        "prior_lease_liability": "70000.00",
        "revised_lease_liability": "85000.00",
        "prior_rou_asset_value": "65000.00",
        "revised_rou_asset_value": "80000.00",
        "gain_loss_on_modification": "0.00",
        "impairment_loss_recognized": "0.00",
        "revised_term_months": 48,
        "revised_payment_amount": "4000.00",
        "revised_discount_rate_pct": "5.5000",
        "requested_by": admin_user.pk,
        "status": "draft",
        "justification": "Extended production commitments required 12-month extension.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    created = AssetLeaseModification.objects.get(
        lease_contract=lease_contract_a, modification_type="term_extension"
    )
    assert created.revised_term_months == 48


@pytest.mark.django_db
def test_assetleaserental_modification_edit_view(client_a, tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    mod = AssetLeaseModification.objects.create(
        tenant=tenant_a,
        lease_contract=lease_contract_a,
        modification_type="payment_change",
        request_date=today,
        effective_date=today,
        requested_by=admin_user,
        status="draft",
        justification="Draft renegotiation",
    )
    url = reverse("assets:asset_lease_modification_edit", kwargs={"pk": mod.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    data = {
        "lease_contract": lease_contract_a.pk,
        "modification_type": "payment_change",
        "request_date": today.strftime("%Y-%m-%d"),
        "effective_date": today.strftime("%Y-%m-%d"),
        "prior_lease_liability": "50000.00",
        "revised_lease_liability": "42000.00",
        "prior_rou_asset_value": "48000.00",
        "revised_rou_asset_value": "40000.00",
        "gain_loss_on_modification": "0.00",
        "impairment_loss_recognized": "0.00",
        "revised_payment_amount": "3200.00",
        "requested_by": admin_user.pk,
        "status": "draft",
        "justification": "Concession from lessor during slow season.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    mod.refresh_from_db()
    assert mod.revised_lease_liability == Decimal("42000.00")
    assert mod.justification == "Concession from lessor during slow season."


@pytest.mark.django_db
def test_assetleaserental_modification_delete_view(client_a, tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    mod = AssetLeaseModification.objects.create(
        tenant=tenant_a,
        lease_contract=lease_contract_a,
        modification_type="discount_rate_change",
        request_date=today,
        effective_date=today,
        requested_by=admin_user,
        status="draft",
        justification="Discarded rate analysis",
    )
    url = reverse("assets:asset_lease_modification_delete", kwargs={"pk": mod.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not AssetLeaseModification.objects.filter(pk=mod.pk).exists()


@pytest.mark.django_db
def test_assetleaserental_modification_approve_action(client_a, tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    mod = AssetLeaseModification.objects.create(
        tenant=tenant_a,
        lease_contract=lease_contract_a,
        modification_type="term_extension",
        request_date=today,
        effective_date=today,
        prior_lease_liability=Decimal("80000.00"),
        revised_lease_liability=Decimal("95000.00"),
        prior_rou_asset_value=Decimal("75000.00"),
        revised_rou_asset_value=Decimal("90000.00"),
        revised_payment_amount=Decimal("4500.00"),
        revised_term_months=48,
        requested_by=admin_user,
        status="submitted",
        justification="Awaiting controller signoff.",
    )
    url = reverse("assets:asset_lease_modification_approve", kwargs={"pk": mod.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    mod.refresh_from_db()
    assert mod.status == "executed"
    assert mod.approved_by == admin_user
    assert mod.liability_adjustment == Decimal("15000.00")
    assert mod.rou_asset_adjustment == Decimal("15000.00")
    lease_contract_a.refresh_from_db()
    assert lease_contract_a.status == "modified"
    assert lease_contract_a.current_lease_liability == Decimal("95000.00")


# ===========================================================================
# 4. AssetLeaseBuyAnalysis View Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_buy_analysis_list_view(client_a, lease_buy_analysis_a):
    url = reverse("assets:asset_lease_buy_analysis_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "analyses" in resp.context
    assert lease_buy_analysis_a in resp.context["analyses"]
    assert "status_choices" in resp.context
    assert "recommendation_choices" in resp.context
    assert "category_list" in resp.context
    assert "total_analyses" in resp.context


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_list_filtering(client_a, lease_buy_analysis_a, category_root_a):
    url = reverse("assets:asset_lease_buy_analysis_list")
    resp = client_a.get(f"{url}?status=evaluated&recommendation={lease_buy_analysis_a.recommendation}&category={category_root_a.pk}")
    assert resp.status_code == 200
    assert lease_buy_analysis_a in resp.context["analyses"]

    resp_empty = client_a.get(f"{url}?status=draft")
    assert resp_empty.status_code == 200
    assert lease_buy_analysis_a not in resp_empty.context["analyses"]


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_detail_view(client_a, lease_buy_analysis_a):
    url = reverse("assets:asset_lease_buy_analysis_detail", kwargs={"pk": lease_buy_analysis_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["analysis"] == lease_buy_analysis_a


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_create_view(client_a, category_root_a, admin_user):
    url = reverse("assets:asset_lease_buy_analysis_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    data = {
        "title": "Automated Stamping Press Acquisition Evaluation",
        "description": "Evaluate 1000-ton press purchase vs lease.",
        "target_asset_name": "Komatsu 1000T Mechanical Stamping Press",
        "category": category_root_a.pk,
        "expected_useful_life_years": "8.0",
        "purchase_price": "450000.00",
        "down_payment_pct": "15.00",
        "loan_interest_rate_pct": "6.00",
        "loan_term_years": "5.0",
        "estimated_salvage_value": "60000.00",
        "annual_maintenance_cost_buy": "12000.00",
        "annual_insurance_tax_buy": "4500.00",
        "lease_term_months": 60,
        "monthly_lease_payment": "7500.00",
        "upfront_lease_fees": "5000.00",
        "end_of_lease_purchase_option": "40000.00",
        "lessor_covers_maintenance": True,
        "annual_maintenance_cost_lease": "0.00",
        "discount_rate_wacc_pct": "8.00",
        "corporate_tax_rate_pct": "21.00",
        "status": "draft",
        "evaluated_by": admin_user.pk,
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    created = AssetLeaseBuyAnalysis.objects.get(title="Automated Stamping Press Acquisition Evaluation")
    assert created.purchase_price == Decimal("450000.00")
    assert created.status == "evaluated"


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_edit_view(client_a, tenant_a, category_root_a, admin_user):
    analysis = AssetLeaseBuyAnalysis.objects.create(
        tenant=tenant_a,
        title="Fleet Vehicle Evaluation Draft",
        target_asset_name="Delivery Van Fleet",
        category=category_root_a,
        purchase_price=Decimal("150000.00"),
        lease_term_months=36,
        monthly_lease_payment=Decimal("3500.00"),
        status="draft",
        evaluated_by=admin_user,
    )
    url = reverse("assets:asset_lease_buy_analysis_edit", kwargs={"pk": analysis.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    data = {
        "title": "Fleet Vehicle Evaluation Final Draft",
        "target_asset_name": "Delivery Van Fleet (10 Units)",
        "category": category_root_a.pk,
        "expected_useful_life_years": "4.0",
        "purchase_price": "160000.00",
        "down_payment_pct": "10.00",
        "loan_interest_rate_pct": "5.50",
        "loan_term_years": "4.0",
        "estimated_salvage_value": "20000.00",
        "annual_maintenance_cost_buy": "6000.00",
        "annual_insurance_tax_buy": "3000.00",
        "lease_term_months": 36,
        "monthly_lease_payment": "3800.00",
        "upfront_lease_fees": "2000.00",
        "end_of_lease_purchase_option": "15000.00",
        "lessor_covers_maintenance": True,
        "annual_maintenance_cost_lease": "0.00",
        "discount_rate_wacc_pct": "8.00",
        "corporate_tax_rate_pct": "21.00",
        "status": "draft",
        "evaluated_by": admin_user.pk,
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    analysis.refresh_from_db()
    assert analysis.title == "Fleet Vehicle Evaluation Final Draft"
    assert analysis.purchase_price == Decimal("160000.00")


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_delete_view(client_a, tenant_a, category_root_a):
    analysis = AssetLeaseBuyAnalysis.objects.create(
        tenant=tenant_a,
        title="Discarded Generator Analysis",
        target_asset_name="Backup Diesel Generator",
        category=category_root_a,
        purchase_price=Decimal("45000.00"),
        lease_term_months=24,
        monthly_lease_payment=Decimal("1200.00"),
        status="draft",
    )
    url = reverse("assets:asset_lease_buy_analysis_delete", kwargs={"pk": analysis.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not AssetLeaseBuyAnalysis.objects.filter(pk=analysis.pk).exists()


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_evaluate_action(client_a, tenant_a, category_root_a, admin_user):
    analysis = AssetLeaseBuyAnalysis.objects.create(
        tenant=tenant_a,
        title="Production Chiller Evaluation Action Test",
        target_asset_name="Industrial Water Chiller",
        category=category_root_a,
        expected_useful_life_years=Decimal("10.0"),
        purchase_price=Decimal("95000.00"),
        down_payment_pct=Decimal("10.00"),
        loan_interest_rate_pct=Decimal("6.00"),
        loan_term_years=Decimal("5.0"),
        estimated_salvage_value=Decimal("12000.00"),
        annual_maintenance_cost_buy=Decimal("3500.00"),
        annual_insurance_tax_buy=Decimal("1200.00"),
        lease_term_months=60,
        monthly_lease_payment=Decimal("1750.00"),
        upfront_lease_fees=Decimal("1500.00"),
        end_of_lease_purchase_option=Decimal("8000.00"),
        lessor_covers_maintenance=True,
        annual_maintenance_cost_lease=Decimal("0.00"),
        discount_rate_wacc_pct=Decimal("7.50"),
        corporate_tax_rate_pct=Decimal("21.00"),
        status="draft",
        evaluated_by=admin_user,
    )
    url = reverse("assets:asset_lease_buy_analysis_evaluate", kwargs={"pk": analysis.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    analysis.refresh_from_db()
    assert analysis.status == "evaluated"
    assert analysis.npv_purchase_option > 0
    assert analysis.npv_lease_option > 0
    assert analysis.recommendation in ["buy", "lease", "neutral"]
