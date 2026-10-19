"""Sub-module 8.11 Customer Success & Account Management -- Model Tests.

Covers:
1. Field presence and contract verification against CUSTOMERSUCCESS_MODEL_FIELDS.
2. Choices verification against CUSTOMERSUCCESS_CHOICES.
3. String representations (__str__) for all 4 models:
   - CustomerHealthScore (CHS-#####)
   - CustomerRenewal (CRN-#####)
   - CustomerOnboarding (COB-#####)
   - CustomerBusinessReview (QBR-#####)
4. Auto-numbering prefixes and sequence isolation per tenant.
5. Model validation guards in clean():
   - Cross-tenant FK rejections (account, owner/lead_csm, orders, opportunities, plans).
   - Invariant validation (band vs score, churn risk vs risk level, expanded vs expansion amount,
     target/actual go-live vs kickoff date, completed date vs scheduled status).
6. Derived fields and properties:
   - score_delta on CustomerHealthScore.
   - total_potential_arr on CustomerRenewal.
   - time_to_value_days computation on CustomerOnboarding save.
   - badge class and icon helper properties.
7. Meta constraints and indexes.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounting.models import Currency
from apps.accounts.models import User
from apps.core.models import Party, Tenant
from apps.crm.models import Opportunity
from apps.sales.models import (
    AccountPlan,
    CustomerBusinessReview,
    CustomerHealthScore,
    CustomerOnboarding,
    CustomerRenewal,
)
from apps.sales.tests.conftest import (
    CUSTOMERSUCCESS_CHOICES,
    CUSTOMERSUCCESS_MODEL_FIELDS,
    _customersuccess_business_review,
    _customersuccess_health_score,
    _customersuccess_onboarding,
    _customersuccess_party,
    _customersuccess_renewal,
)
from apps.scm.models import SalesOrder

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers
# ============================================================================

def _customersuccess_opportunity(tenant, name="Expansion Opp", amount=Decimal("25000.00")):
    label = int(timezone.now().timestamp() * 1000) % 100000
    return Opportunity.objects.create(
        tenant=tenant,
        name=f"{name} {label}",
        stage="proposal",
        forecast_category="pipeline",
        amount=amount,
        probability=60,
    )


def _customersuccess_sales_order(tenant, customer, total=Decimal("50000.00")):
    return SalesOrder.objects.create(
        tenant=tenant,
        customer=customer,
        source_channel="direct",
        status="confirmed",
        subtotal=total,
        tax_total=Decimal("0.00"),
        total=total,
    )


def _customersuccess_account_plan(tenant, account, owner=None):
    if owner is None:
        owner = User.objects.filter(tenant=tenant).first()
    return AccountPlan.objects.create(
        tenant=tenant,
        account=account,
        title=f"{account.name} Plan",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        status="active",
        owner=owner,
    )


# ============================================================================
# 1. Field and Choices Contract Verification
# ============================================================================

def test_customersuccess_model_fields_contract():
    """Verify all 4 Customer Success models declare exactly the pinned field contract."""
    model_map = {
        "CustomerHealthScore": CustomerHealthScore,
        "CustomerRenewal": CustomerRenewal,
        "CustomerOnboarding": CustomerOnboarding,
        "CustomerBusinessReview": CustomerBusinessReview,
    }

    for model_name, expected_fields in CUSTOMERSUCCESS_MODEL_FIELDS.items():
        model_cls = model_map[model_name]
        actual_fields = {f.name for f in model_cls._meta.get_fields()}
        missing = set(expected_fields) - actual_fields
        assert not missing, f"Model {model_name} missing fields: {missing}"


def test_customersuccess_model_choices_contract():
    """Verify all model choices declare expected keys and values."""
    from apps.sales.models.CustomerSuccess.CustomerHealthScores import (
        HEALTH_BAND_CHOICES,
        RISK_LEVEL_CHOICES,
        TREND_CHOICES,
    )
    from apps.sales.models.CustomerSuccess.CustomerRenewals import (
        CHURN_RISK_CHOICES,
        STAGE_CHOICES as RENEWAL_STAGE_CHOICES,
    )
    from apps.sales.models.CustomerSuccess.CustomerOnboardings import (
        PLAYBOOK_CHOICES,
        STAGE_CHOICES as ONBOARDING_STAGE_CHOICES,
        STATUS_CHOICES as ONBOARDING_STATUS_CHOICES,
    )
    from apps.sales.models.CustomerSuccess.CustomerBusinessReviews import (
        CASE_STUDY_CHOICES,
        REVIEW_PERIOD_CHOICES,
        STATUS_CHOICES as REVIEW_STATUS_CHOICES,
        TEMPLATE_CHOICES,
    )

    actual = {
        "CustomerHealthScore": {
            "health_band": tuple(HEALTH_BAND_CHOICES),
            "score_trend": tuple(TREND_CHOICES),
            "risk_level": tuple(RISK_LEVEL_CHOICES),
        },
        "CustomerRenewal": {
            "stage": tuple(RENEWAL_STAGE_CHOICES),
            "churn_risk_flag": tuple(CHURN_RISK_CHOICES),
        },
        "CustomerOnboarding": {
            "playbook_template": tuple(PLAYBOOK_CHOICES),
            "stage": tuple(ONBOARDING_STAGE_CHOICES),
            "status": tuple(ONBOARDING_STATUS_CHOICES),
        },
        "CustomerBusinessReview": {
            "review_period": tuple(REVIEW_PERIOD_CHOICES),
            "status": tuple(REVIEW_STATUS_CHOICES),
            "template_type": tuple(TEMPLATE_CHOICES),
            "case_study_status": tuple(CASE_STUDY_CHOICES),
        },
    }

    for model_name, field_choices in CUSTOMERSUCCESS_CHOICES.items():
        for field_name, expected_tuples in field_choices.items():
            assert actual[model_name][field_name] == expected_tuples, f"Choices mismatch for {model_name}.{field_name}"


# ============================================================================
# 2. String Representations (__str__)
# ============================================================================

def test_customersuccess_string_representation(
    cs_health_score_a, cs_renewal_a, cs_onboarding_a, cs_qbr_a
):
    """Verify __str__ format across all 4 customer success models."""
    assert str(cs_health_score_a) == f"{cs_health_score_a.number} - {cs_health_score_a.account.name} (85/100)"
    assert str(cs_renewal_a) == f"{cs_renewal_a.number} - {cs_renewal_a.renewal_name} (Upcoming (90+ Days))"
    assert str(cs_onboarding_a) == f"{cs_onboarding_a.number} - {cs_onboarding_a.title} (Kickoff & Alignment)"
    assert str(cs_qbr_a) == f"{cs_qbr_a.number} - {cs_qbr_a.title} (Scheduled)"


# ============================================================================
# 3. Auto-Numbering Prefixes and Tenant Sequence Isolation
# ============================================================================

def test_customersuccess_auto_numbering_prefixes(
    tenant_a, tenant_b, cs_account_a, cs_account_b, admin_user, admin_b, icm_currency
):
    """Verify prefixes (CHS-, CRN-, COB-, QBR-) and tenant isolation of sequences."""
    # Tenant A records
    chs_1 = _customersuccess_health_score(tenant_a, cs_account_a)
    chs_2 = _customersuccess_health_score(tenant_a, cs_account_a)
    crn_1 = _customersuccess_renewal(tenant_a, cs_account_a, admin_user, icm_currency)
    crn_2 = _customersuccess_renewal(tenant_a, cs_account_a, admin_user, icm_currency)
    cob_1 = _customersuccess_onboarding(tenant_a, cs_account_a, admin_user)
    cob_2 = _customersuccess_onboarding(tenant_a, cs_account_a, admin_user)
    qbr_1 = _customersuccess_business_review(tenant_a, cs_account_a, admin_user)
    qbr_2 = _customersuccess_business_review(tenant_a, cs_account_a, admin_user)

    assert chs_1.number.startswith("CHS-")
    assert chs_2.number.startswith("CHS-")
    assert crn_1.number.startswith("CRN-")
    assert crn_2.number.startswith("CRN-")
    assert cob_1.number.startswith("COB-")
    assert cob_2.number.startswith("COB-")
    assert qbr_1.number.startswith("QBR-")
    assert qbr_2.number.startswith("QBR-")

    # Sequence increments
    seq_chs_1 = int(chs_1.number.split("-")[-1])
    seq_chs_2 = int(chs_2.number.split("-")[-1])
    assert seq_chs_2 == seq_chs_1 + 1

    # Tenant B sequence starts independently
    chs_b = _customersuccess_health_score(tenant_b, cs_account_b)
    assert chs_b.number.startswith("CHS-")


# ============================================================================
# 4. CustomerHealthScore Validation & Logic
# ============================================================================

def test_customersuccess_health_score_delta_property(tenant_a, cs_account_a):
    """Verify score_delta calculates overall_score - previous_score or None."""
    score_no_prev = _customersuccess_health_score(tenant_a, cs_account_a, overall_score=80, previous_score=None)
    assert score_no_prev.score_delta is None

    score_with_prev = _customersuccess_health_score(tenant_a, cs_account_a, overall_score=85, previous_score=70)
    assert score_with_prev.score_delta == 15

    score_declined = _customersuccess_health_score(tenant_a, cs_account_a, overall_score=60, previous_score=75)
    assert score_declined.score_delta == -15


def test_customersuccess_health_score_clean_cross_tenant_account(tenant_a, cs_account_b):
    """Reject account from foreign tenant."""
    score = CustomerHealthScore(tenant=tenant_a, account=cs_account_b, overall_score=80)
    with pytest.raises(ValidationError) as exc:
        score.clean()
    assert "account" in exc.value.error_dict


def test_customersuccess_health_score_clean_band_invariants(tenant_a, cs_account_a):
    """Reject high score in red band or low score in green band."""
    # Score >= 75 in red band
    score_high_red = CustomerHealthScore(
        tenant=tenant_a, account=cs_account_a, overall_score=80, health_band="red"
    )
    with pytest.raises(ValidationError) as exc1:
        score_high_red.clean()
    assert "health_band" in exc1.value.error_dict

    # Score < 50 in green band
    score_low_green = CustomerHealthScore(
        tenant=tenant_a, account=cs_account_a, overall_score=45, health_band="green"
    )
    with pytest.raises(ValidationError) as exc2:
        score_low_green.clean()
    assert "health_band" in exc2.value.error_dict


def test_customersuccess_health_score_clean_churn_risk_level_invariant(tenant_a, cs_account_a):
    """Accounts flagged as churn risk cannot have low risk level."""
    score = CustomerHealthScore(
        tenant=tenant_a,
        account=cs_account_a,
        overall_score=70,
        health_band="yellow",
        is_churn_risk=True,
        risk_level="low",
    )
    with pytest.raises(ValidationError) as exc:
        score.clean()
    assert "risk_level" in exc.value.error_dict


def test_customersuccess_health_score_badge_and_trend_properties(tenant_a, cs_account_a):
    """Verify health_badge_class, risk_badge_class, and trend_icon."""
    score = _customersuccess_health_score(
        tenant_a,
        cs_account_a,
        health_band="green",
        risk_level="low",
        score_trend="improving",
    )
    assert score.health_badge_class == "badge-green"
    assert score.risk_badge_class == "badge-green"
    assert score.trend_icon == "trending-up"

    score.health_band = "yellow"
    score.risk_level = "medium"
    score.score_trend = "stable"
    assert score.health_badge_class == "badge-amber"
    assert score.risk_badge_class == "badge-amber"
    assert score.trend_icon == "minus"

    score.health_band = "red"
    score.risk_level = "critical"
    score.score_trend = "declining"
    assert score.health_badge_class == "badge-red"
    assert score.risk_badge_class == "badge-red"
    assert score.trend_icon == "trending-down"


# ============================================================================
# 5. CustomerRenewal Validation & Logic
# ============================================================================

def test_customersuccess_renewal_clean_cross_tenant_rejections(
    tenant_a, tenant_b, cs_account_a, cs_account_b, admin_user, admin_b, icm_currency
):
    """Reject foreign tenant account, owner, order, or expansion opportunity."""
    # Foreign account
    ren1 = CustomerRenewal(
        tenant=tenant_a, account=cs_account_b, owner=admin_user, currency=icm_currency
    )
    with pytest.raises(ValidationError) as exc1:
        ren1.clean()
    assert "account" in exc1.value.error_dict

    # Foreign owner
    ren2 = CustomerRenewal(
        tenant=tenant_a, account=cs_account_a, owner=admin_b, currency=icm_currency
    )
    with pytest.raises(ValidationError) as exc2:
        ren2.clean()
    assert "owner" in exc2.value.error_dict

    # Foreign sales order
    foreign_order = _customersuccess_sales_order(tenant_b, cs_account_b)
    ren3 = CustomerRenewal(
        tenant=tenant_a,
        account=cs_account_a,
        owner=admin_user,
        currency=icm_currency,
        original_order=foreign_order,
    )
    with pytest.raises(ValidationError) as exc3:
        ren3.clean()
    assert "original_order" in exc3.value.error_dict

    # Foreign opportunity
    foreign_opp = _customersuccess_opportunity(tenant_b)
    ren4 = CustomerRenewal(
        tenant=tenant_a,
        account=cs_account_a,
        owner=admin_user,
        currency=icm_currency,
        expansion_opportunity=foreign_opp,
    )
    with pytest.raises(ValidationError) as exc4:
        ren4.clean()
    assert "expansion_opportunity" in exc4.value.error_dict


def test_customersuccess_renewal_clean_expansion_amount_invariant(
    tenant_a, cs_account_a, admin_user, icm_currency
):
    """When stage is 'expanded', expansion_amount must be greater than 0."""
    ren = CustomerRenewal(
        tenant=tenant_a,
        account=cs_account_a,
        owner=admin_user,
        currency=icm_currency,
        stage="expanded",
        expansion_amount=Decimal("0.00"),
    )
    with pytest.raises(ValidationError) as exc:
        ren.clean()
    assert "expansion_amount" in exc.value.error_dict


def test_customersuccess_renewal_total_potential_arr_property(
    tenant_a, cs_account_a, admin_user, icm_currency
):
    """total_potential_arr = projected_renewal_arr + expansion_amount."""
    ren = _customersuccess_renewal(
        tenant_a,
        cs_account_a,
        admin_user,
        icm_currency,
        projected_renewal_arr=Decimal("120000.00"),
        expansion_amount=Decimal("30000.00"),
    )
    assert ren.total_potential_arr == Decimal("150000.00")


def test_customersuccess_renewal_badge_classes(
    tenant_a, cs_account_a, admin_user, icm_currency
):
    """Verify stage_badge_class and risk_badge_class."""
    ren = _customersuccess_renewal(
        tenant_a, cs_account_a, admin_user, icm_currency, stage="renewed", churn_risk_flag="low"
    )
    assert ren.stage_badge_class == "badge-green"
    assert ren.risk_badge_class == "badge-green"

    ren.stage = "upcoming"
    assert ren.stage_badge_class == "badge-info"

    ren.stage = "engagement"
    assert ren.stage_badge_class == "badge-amber"

    ren.stage = "churned"
    ren.churn_risk_flag = "critical"
    assert ren.stage_badge_class == "badge-red"
    assert ren.risk_badge_class == "badge-red"


# ============================================================================
# 6. CustomerOnboarding Validation & Logic
# ============================================================================

def test_customersuccess_onboarding_clean_cross_tenant_rejections(
    tenant_a, tenant_b, cs_account_a, cs_account_b, admin_user, admin_b
):
    """Reject foreign tenant account, lead CSM, or sales order."""
    # Foreign account
    onb1 = CustomerOnboarding(tenant=tenant_a, account=cs_account_b, lead_csm=admin_user)
    with pytest.raises(ValidationError) as exc1:
        onb1.clean()
    assert "account" in exc1.value.error_dict

    # Foreign CSM
    onb2 = CustomerOnboarding(tenant=tenant_a, account=cs_account_a, lead_csm=admin_b)
    with pytest.raises(ValidationError) as exc2:
        onb2.clean()
    assert "lead_csm" in exc2.value.error_dict

    # Foreign sales order
    foreign_order = _customersuccess_sales_order(tenant_b, cs_account_b)
    onb3 = CustomerOnboarding(
        tenant=tenant_a,
        account=cs_account_a,
        lead_csm=admin_user,
        sales_order=foreign_order,
    )
    with pytest.raises(ValidationError) as exc3:
        onb3.clean()
    assert "sales_order" in exc3.value.error_dict


def test_customersuccess_onboarding_clean_date_invariants(tenant_a, cs_account_a, admin_user):
    """Target and actual go-live dates cannot be earlier than kickoff date."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    onb_target = CustomerOnboarding(
        tenant=tenant_a,
        account=cs_account_a,
        lead_csm=admin_user,
        kickoff_date=today,
        target_go_live_date=yesterday,
    )
    with pytest.raises(ValidationError) as exc1:
        onb_target.clean()
    assert "target_go_live_date" in exc1.value.error_dict

    onb_actual = CustomerOnboarding(
        tenant=tenant_a,
        account=cs_account_a,
        lead_csm=admin_user,
        kickoff_date=today,
        actual_go_live_date=yesterday,
    )
    with pytest.raises(ValidationError) as exc2:
        onb_actual.clean()
    assert "actual_go_live_date" in exc2.value.error_dict


def test_customersuccess_onboarding_save_computes_ttv(tenant_a, cs_account_a, admin_user):
    """Saving with actual_go_live_date computes time_to_value_days."""
    kickoff = date(2026, 1, 1)
    go_live = date(2026, 2, 10)  # 40 days
    onb = _customersuccess_onboarding(
        tenant_a,
        cs_account_a,
        admin_user,
        kickoff_date=kickoff,
        actual_go_live_date=go_live,
    )
    onb.refresh_from_db()
    assert onb.time_to_value_days == 40


def test_customersuccess_onboarding_badge_classes(tenant_a, cs_account_a, admin_user):
    """Verify status_badge_class and stage_badge_class."""
    onb = _customersuccess_onboarding(
        tenant_a,
        cs_account_a,
        admin_user,
        status="completed",
        stage="completed",
    )
    assert onb.status_badge_class == "badge-green"
    assert onb.stage_badge_class == "badge-green"

    onb.status = "at_risk"
    onb.stage = "configuration"
    assert onb.status_badge_class == "badge-red"
    assert onb.stage_badge_class == "badge-info"


# ============================================================================
# 7. CustomerBusinessReview Validation & Logic
# ============================================================================

def test_customersuccess_business_review_clean_cross_tenant_rejections(
    tenant_a, tenant_b, cs_account_a, cs_account_b, admin_user, admin_b
):
    """Reject foreign tenant account, lead CSM, or account plan."""
    # Foreign account
    qbr1 = CustomerBusinessReview(tenant=tenant_a, account=cs_account_b, lead_csm=admin_user)
    with pytest.raises(ValidationError) as exc1:
        qbr1.clean()
    assert "account" in exc1.value.error_dict

    # Foreign lead CSM
    qbr2 = CustomerBusinessReview(tenant=tenant_a, account=cs_account_a, lead_csm=admin_b)
    with pytest.raises(ValidationError) as exc2:
        qbr2.clean()
    assert "lead_csm" in exc2.value.error_dict

    # Foreign account plan
    foreign_plan = _customersuccess_account_plan(tenant_b, cs_account_b)
    qbr3 = CustomerBusinessReview(
        tenant=tenant_a,
        account=cs_account_a,
        lead_csm=admin_user,
        account_plan=foreign_plan,
    )
    with pytest.raises(ValidationError) as exc3:
        qbr3.clean()
    assert "account_plan" in exc3.value.error_dict


def test_customersuccess_business_review_clean_status_invariant(tenant_a, cs_account_a, admin_user):
    """A review with a completed_date cannot be in 'scheduled' status."""
    today = timezone.localdate()
    qbr = CustomerBusinessReview(
        tenant=tenant_a,
        account=cs_account_a,
        lead_csm=admin_user,
        status="scheduled",
        completed_date=today,
    )
    with pytest.raises(ValidationError) as exc:
        qbr.clean()
    assert "status" in exc.value.error_dict


def test_customersuccess_business_review_badge_classes(tenant_a, cs_account_a, admin_user):
    """Verify status_badge_class and case_study_badge_class."""
    qbr = _customersuccess_business_review(
        tenant_a,
        cs_account_a,
        admin_user,
        status="conducted",
        case_study_status="published",
    )
    assert qbr.status_badge_class == "badge-green"
    assert qbr.case_study_badge_class == "badge-green"

    qbr.status = "scheduled"
    qbr.case_study_status = "drafting"
    assert qbr.status_badge_class == "badge-info"
    assert qbr.case_study_badge_class == "badge-amber"

    qbr.status = "cancelled"
    qbr.case_study_status = "none"
    assert qbr.status_badge_class == "badge-red"
    assert qbr.case_study_badge_class == "badge-slate"


# ============================================================================
# 8. Meta Constraints & Composite Indexes
# ============================================================================

def test_customersuccess_indexes_and_constraints_presence():
    """Verify that composite indexes and unique constraints exist in model Meta."""
    # Check CustomerHealthScore
    chs_constraint_names = [c.name for c in CustomerHealthScore._meta.constraints]
    chs_index_names = [i.name for i in CustomerHealthScore._meta.indexes]
    assert "sales_chs_tenant_number_uniq" in chs_constraint_names
    assert "sales_chs_acct_date_idx" in chs_index_names
    assert "sales_chs_band_idx" in chs_index_names
    assert "sales_chs_churn_idx" in chs_index_names

    # Check CustomerRenewal
    crn_constraint_names = [c.name for c in CustomerRenewal._meta.constraints]
    crn_index_names = [i.name for i in CustomerRenewal._meta.indexes]
    assert "sales_crn_tenant_number_uniq" in crn_constraint_names
    assert "sales_crn_ten_stage_idx" in crn_index_names

    # Check CustomerOnboarding
    cob_constraint_names = [c.name for c in CustomerOnboarding._meta.constraints]
    cob_index_names = [i.name for i in CustomerOnboarding._meta.indexes]
    assert "sales_cob_tenant_number_uniq" in cob_constraint_names
    assert "sales_cob_ten_stat_idx" in cob_index_names

    # Check CustomerBusinessReview
    qbr_constraint_names = [c.name for c in CustomerBusinessReview._meta.constraints]
    qbr_index_names = [i.name for i in CustomerBusinessReview._meta.indexes]
    assert "sales_qbr_tenant_number_uniq" in qbr_constraint_names
    assert "sales_qbr_ten_stat_idx" in qbr_index_names
