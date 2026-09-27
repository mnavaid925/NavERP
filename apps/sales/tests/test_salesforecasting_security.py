"""8.4 Sales Forecasting -- the SECURITY lane.

Naming: every test is ``test_salesforecasting_*`` and every module-level helper
``_salesforecasting_*`` so the next sub-module appending nearby cannot shadow
them (8.1/8.2/8.3 own the ``leadmanagement``/``opportunitypipeline``/
``contactaccountmanagement`` names in this same package).

This is the lane that would catch a cross-tenant forecast leak. It enforces
tenant isolation (a foreign row is 404, never 200), POST-only mutations, the
tenant-admin role gates, and the AI gate suppressing a prediction value rather
than merely its explanation.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.sales.tests.conftest import (
    _salesforecasting_scenario,
    _salesforecasting_submission,
)


def test_salesforecasting_every_forecast_route_resolves_to_a_named_pattern():
    from apps.sales import urls as sales_urls

    forecast = [p.name for p in sales_urls.urlpatterns if (p.name or "").startswith("forecast_")]
    assert len(forecast) >= 30, forecast
    assert all(forecast), "a forecast route is unnamed"


def test_salesforecasting_anonymous_requests_redirect_to_login():
    from django.test import Client

    response = Client().get(reverse("sales:forecast_submission_list"))
    assert response.status_code in (301, 302)
    assert "login" in response["Location"].lower()



# ------------------------------------------------------------ tenant isolation
def _foreign_rows(tenant_b):
    """One of every 8.4 model, owned by the OTHER tenant."""
    from apps.sales.models import (
        ForecastAdjustment,
        ForecastPeriod,
        ForecastScenario,
        ForecastSubmission,
    )

    period = ForecastPeriod.objects.create(
        tenant=tenant_b,
        name="B Q",
        period_type="quarter",
        period_year=2027,
        period_number=1,
    )
    submission = ForecastSubmission.objects.create(
        tenant=tenant_b, period=period, pipeline_amount=Decimal("1.00")
    )
    adjustment = ForecastAdjustment.objects.create(
        tenant=tenant_b,
        submission=submission,
        adjustment_kind="direct",
        target_field="category",
        adjusted_category="commit",
        reason_code="manager_judgement",
    )
    scenario = ForecastScenario.objects.create(
        tenant=tenant_b, period=period, name="B scenario", scenario_type="upside"
    )
    return {
        "sales:forecast_period_detail": period.pk,
        "sales:forecast_submission_detail": submission.pk,
        "sales:forecast_adjustment_detail": adjustment.pk,
        "sales:forecast_scenario_detail": scenario.pk,
    }


@pytest.mark.parametrize(
    "route",
    [
        "sales:forecast_period_detail",
        "sales:forecast_submission_detail",
        "sales:forecast_adjustment_detail",
        "sales:forecast_scenario_detail",
    ],
)
def test_salesforecasting_detail_route_404s_for_another_tenants_row(
    salesforecasting_client_a, salesforecasting_tenant_b, route
):
    """The core IDOR rule: tenant A must never read tenant B's forecast."""
    pk = _foreign_rows(salesforecasting_tenant_b)[route]
    assert salesforecasting_client_a.get(reverse(route, args=[pk])).status_code == 404


def test_salesforecasting_list_and_report_pages_never_leak_another_tenants_rows(
    salesforecasting_client_a, salesforecasting_tenant_b
):
    from apps.sales.models import ForecastPeriod, ForecastSubmission

    period_b = ForecastPeriod.objects.create(
        tenant=salesforecasting_tenant_b,
        name="SECRET PERIOD",
        period_type="quarter",
        period_year=2029,
        period_number=1,
    )
    ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_b, period=period_b, pipeline_amount=Decimal("7.00")
    )
    for route in (
        "sales:forecast_period_list",
        "sales:forecast_submission_list",
        "sales:forecast_adjustment_list",
        "sales:forecast_scenario_list",
        "sales:forecast_board",
        "sales:forecast_attainment",
        "sales:forecast_accuracy",
        "sales:forecast_call",
    ):
        body = salesforecasting_client_a.get(reverse(route)).content.decode("utf-8", "replace")
        assert "SECRET PERIOD" not in body, route


def test_salesforecasting_reports_degrade_to_empty_for_the_tenantless_superuser(db):
    """``request.tenant is None`` (the ``admin`` superuser) must render, not 500."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    User = get_user_model()
    root = User.objects.filter(tenant__isnull=True).first() or User.objects.create_superuser(
        email="root_nobody_84@example.com", username="root_nobody_84", password="password"
    )
    client = Client()
    client.force_login(root)
    for route in (
        "sales:forecast_board",
        "sales:forecast_attainment",
        "sales:forecast_accuracy",
        "sales:forecast_call",
        "sales:forecast_submission_list",
    ):
        assert client.get(reverse(route)).status_code == 200, route



# ------------------------------------------------------------------ POST only
def test_salesforecasting_period_lock_rejects_get(
    salesforecasting_client_a, salesforecasting_period_a
):
    url = reverse("sales:forecast_period_lock", args=[salesforecasting_period_a.pk])
    assert salesforecasting_client_a.get(url).status_code in (405, 302)
    salesforecasting_period_a.refresh_from_db()
    assert salesforecasting_period_a.is_locked is False


def test_salesforecasting_submission_submit_rejects_get(
    salesforecasting_client_a, salesforecasting_submission_a
):
    url = reverse("sales:forecast_submission_submit", args=[salesforecasting_submission_a.pk])
    assert salesforecasting_client_a.get(url).status_code in (405, 302)
    salesforecasting_submission_a.refresh_from_db()
    assert salesforecasting_submission_a.status == "draft"


def test_salesforecasting_adjustment_revert_rejects_get(
    salesforecasting_client_a, salesforecasting_adjustment_a
):
    url = reverse("sales:forecast_adjustment_revert", args=[salesforecasting_adjustment_a.pk])
    assert salesforecasting_client_a.get(url).status_code in (405, 302)
    salesforecasting_adjustment_a.refresh_from_db()
    assert salesforecasting_adjustment_a.is_reverted is False


def test_salesforecasting_scenario_select_and_apply_reject_get(
    salesforecasting_client_a, salesforecasting_scenario_a
):
    """``select`` is per-row; ``apply`` is a period-level action and takes no pk."""
    select_url = reverse("sales:forecast_scenario_select", args=[salesforecasting_scenario_a.pk])
    apply_url = reverse("sales:forecast_scenario_apply")
    assert salesforecasting_client_a.get(select_url).status_code in (405, 302)
    assert salesforecasting_client_a.get(apply_url).status_code in (405, 302)
    salesforecasting_scenario_a.refresh_from_db()
    assert salesforecasting_scenario_a.is_selected is False


# ------------------------------------------------------------------- role gates
def test_salesforecasting_a_plain_rep_cannot_lock_a_period(
    salesforecasting_client_rep_a, salesforecasting_period_a
):
    url = reverse("sales:forecast_period_lock", args=[salesforecasting_period_a.pk])
    assert salesforecasting_client_rep_a.post(url).status_code in (302, 403)
    salesforecasting_period_a.refresh_from_db()
    assert salesforecasting_period_a.is_locked is False


def test_salesforecasting_a_plain_rep_cannot_approve_a_submission(
    salesforecasting_client_rep_a, salesforecasting_submission_a
):
    url = reverse("sales:forecast_submission_approve", args=[salesforecasting_submission_a.pk])
    assert salesforecasting_client_rep_a.post(url, {"note": "ok"}).status_code in (302, 403)
    salesforecasting_submission_a.refresh_from_db()
    assert salesforecasting_submission_a.status != "approved"


def test_salesforecasting_a_plain_rep_cannot_create_an_override(
    salesforecasting_client_rep_a, salesforecasting_submission_a
):
    response = salesforecasting_client_rep_a.post(
        reverse("sales:forecast_adjustment_create"),
        {
            "submission": str(salesforecasting_submission_a.pk),
            "adjustment_kind": "direct",
            "target_field": "category",
            "adjusted_category": "commit",
            "reason_code": "manager_judgement",
        },
    )
    assert response.status_code in (302, 403)



# ------------------------------------------------------------------- the AI gate
def test_salesforecasting_ai_gate_needs_forty_won_and_forty_lost(salesforecasting_tenant_a):
    from apps.sales.forecast_services import AI_GATE_MIN_PER_CLASS, forecast_ai_gate

    available, message = forecast_ai_gate(salesforecasting_tenant_a)
    assert available is False
    assert str(AI_GATE_MIN_PER_CLASS) in message


def test_salesforecasting_ai_gate_is_off_for_a_tenant_with_no_outcomes(salesforecasting_tenant_b):
    from apps.sales.forecast_services import forecast_ai_gate

    available, message = forecast_ai_gate(salesforecasting_tenant_b)
    assert available is False
    assert message


def test_salesforecasting_reports_show_no_prediction_value_while_the_gate_is_shut(
    salesforecasting_client_a, salesforecasting_tenant_a, salesforecasting_period_a
):
    """The gate must suppress the number, not merely the explanation."""
    _salesforecasting_submission(
        salesforecasting_tenant_a,
        salesforecasting_period_a,
        ai_predicted_commit=Decimal("999999.00"),
        ai_confidence_pct=99,
    )
    body = salesforecasting_client_a.get(
        reverse("sales:forecast_board")
    ).content.decode("utf-8", "replace")
    assert "Prediction unavailable" in body
    assert "Predicted commit" not in body
    assert "999999" not in body


# ---------------------------------------------------------------- scenario isolation
def test_salesforecasting_applying_a_scenario_never_mutates_a_submission(
    salesforecasting_client_a,
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_admin_a,
):
    """The isolation rule the whole scenario entity rests on."""
    from apps.sales.models import ForecastSubmission

    _salesforecasting_submission(salesforecasting_tenant_a, salesforecasting_period_a)
    scenario = _salesforecasting_scenario(
        salesforecasting_tenant_a,
        salesforecasting_period_a,
        name="Upside",
        owner=salesforecasting_admin_a,
        commit_delta_pct=Decimal("50.00"),
    )
    fields = ("pk", "commit_amount", "pipeline_amount", "status", "weighted_amount")
    before = list(
        ForecastSubmission.objects.filter(tenant=salesforecasting_tenant_a).values(*fields)
    )
    response = salesforecasting_client_a.post(
        reverse("sales:forecast_scenario_apply"),
        {
            "period": str(salesforecasting_period_a.pk),
            "target": "commit",
            "variance_threshold_pct": "10",
        },
    )
    assert response.status_code in (200, 302)
    after = list(
        ForecastSubmission.objects.filter(tenant=salesforecasting_tenant_a).values(*fields)
    )
    assert before == after


def test_salesforecasting_a_reverted_override_keeps_its_audit_row(
    salesforecasting_client_a, salesforecasting_tenant_a, salesforecasting_adjustment_a
):
    """Reset must not delete history -- storing the delta is what makes that possible."""
    from apps.sales.models import ForecastAdjustment

    response = salesforecasting_client_a.post(
        reverse("sales:forecast_adjustment_revert", args=[salesforecasting_adjustment_a.pk]),
        {"revert_reason": "Reverted after audit."},
    )
    assert response.status_code in (200, 302)
    assert ForecastAdjustment.objects.filter(
        tenant=salesforecasting_tenant_a, pk=salesforecasting_adjustment_a.pk
    ).exists()
    salesforecasting_adjustment_a.refresh_from_db()
    assert salesforecasting_adjustment_a.is_reverted is True
    assert salesforecasting_adjustment_a.revert_reason == "Reverted after audit."


def test_salesforecasting_revert_refuses_a_post_without_a_reason(
    salesforecasting_client_a, salesforecasting_adjustment_a
):
    salesforecasting_client_a.post(
        reverse("sales:forecast_adjustment_revert", args=[salesforecasting_adjustment_a.pk]),
        {"revert_reason": ""},
    )
    salesforecasting_adjustment_a.refresh_from_db()
    assert salesforecasting_adjustment_a.is_reverted is False


# ------------------------------------------- "you cannot adjust a level above you"
# The 8.4 plan calls this rule out by name -- "you cannot adjust a level above
# you (Microsoft, security-sensitive)" -- and the rule is IMPLEMENTED, in
# ForecastAdjustments._adjusts_above_acting_level(): it resolves the acting user's
# org node through sales.OpportunityTeamMember.org_unit and refuses a submission
# sitting on a strict ancestor, walking core.OrgUnit.parent. It had no test at all.
#
# Writing one exposed a defect: the view it guards is @tenant_admin_required, and
# _adjusts_above_acting_level() returns False immediately for a tenant admin. So
# the only users who reach the call are the ones it exempts, and the
# PermissionDenied it raises is UNREACHABLE. The rule is dead code today.
#
# These tests pin two separate things: the rule's own logic, tested directly on
# the helper so it cannot silently rot, and the view's real gate, so the
# dead-code shape stays visible rather than assumed away. Fixing it means
# deciding who may override whom, which is a product decision -- recorded in
# review-sales-8.4.md as C1, not silently changed here.

def _salesforecasting_level_membership(tenant, opportunity, user, org_unit=None):
    from apps.sales.models import OpportunityTeamMember

    return OpportunityTeamMember.objects.create(
        tenant=tenant, opportunity=opportunity, user=user,
        org_unit=org_unit, role="sales_support", is_active=True,
    )


def test_salesforecasting_the_level_rule_refuses_a_strict_ancestor(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
    salesforecasting_org_unit_parent_a,
    salesforecasting_org_unit_child_a,
    salesforecasting_period_a,
):
    """The rule itself: a user at the CHILD node faces a submission on the
    PARENT node. This is the case the plan means."""
    from apps.crm.models import Opportunity
    from apps.sales.models import ForecastSubmission
    from apps.sales.views.SalesForecasting.ForecastAdjustments import _adjusts_above_acting_level

    opportunity = Opportunity.objects.create(tenant=salesforecasting_tenant_a, name="Level probe")
    _salesforecasting_level_membership(
        salesforecasting_tenant_a, opportunity, salesforecasting_rep_a,
        org_unit=salesforecasting_org_unit_child_a,
    )
    parent_submission = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        org_unit=salesforecasting_org_unit_parent_a,
    )
    assert _adjusts_above_acting_level(salesforecasting_rep_a, parent_submission) is True


def test_salesforecasting_the_level_rule_allows_your_own_node(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
    salesforecasting_org_unit_child_a,
    salesforecasting_period_a,
):
    """A node is not a strict ancestor of itself. Without this the guard would
    make the feature unusable for its intended user."""
    from apps.crm.models import Opportunity
    from apps.sales.models import ForecastSubmission
    from apps.sales.views.SalesForecasting.ForecastAdjustments import _adjusts_above_acting_level

    opportunity = Opportunity.objects.create(tenant=salesforecasting_tenant_a, name="Own node")
    _salesforecasting_level_membership(
        salesforecasting_tenant_a, opportunity, salesforecasting_rep_a,
        org_unit=salesforecasting_org_unit_child_a,
    )
    own = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        org_unit=salesforecasting_org_unit_child_a,
    )
    assert _adjusts_above_acting_level(salesforecasting_rep_a, own) is False


def test_salesforecasting_the_level_rule_allows_a_descendant(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
    salesforecasting_org_unit_parent_a,
    salesforecasting_period_a,
):
    """The rule is one-directional: a manager may always adjust below them. Only
    ABOVE is a violation, so a submission on a descendant is fine."""
    from apps.crm.models import Opportunity
    from apps.core.models import OrgUnit
    from apps.sales.models import ForecastSubmission
    from apps.sales.views.SalesForecasting.ForecastAdjustments import _adjusts_above_acting_level

    root = OrgUnit.objects.create(
        tenant=salesforecasting_tenant_a, name="Level root", kind="department",
        parent=salesforecasting_org_unit_parent_a,
    )
    opportunity = Opportunity.objects.create(tenant=salesforecasting_tenant_a, name="Below me")
    _salesforecasting_level_membership(
        salesforecasting_tenant_a, opportunity, salesforecasting_rep_a,
        org_unit=salesforecasting_org_unit_parent_a,
    )
    below = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, org_unit=root,
    )
    assert _adjusts_above_acting_level(salesforecasting_rep_a, below) is False



def test_salesforecasting_the_level_rule_ignores_a_sibling_branch(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
    salesforecasting_period_a,
):
    """A peer under a shared parent is not an ancestor of the acting node."""
    from apps.crm.models import Opportunity
    from apps.core.models import OrgUnit
    from apps.sales.models import ForecastSubmission
    from apps.sales.views.SalesForecasting.ForecastAdjustments import _adjusts_above_acting_level

    root = OrgUnit.objects.create(tenant=salesforecasting_tenant_a, name="Peer root", kind="department")
    mine = OrgUnit.objects.create(tenant=salesforecasting_tenant_a, name="Mine", kind="department", parent=root)
    peer = OrgUnit.objects.create(tenant=salesforecasting_tenant_a, name="Peer", kind="department", parent=root)
    opportunity = Opportunity.objects.create(tenant=salesforecasting_tenant_a, name="Peers")
    _salesforecasting_level_membership(
        salesforecasting_tenant_a, opportunity, salesforecasting_rep_a, org_unit=mine,
    )
    peer_submission = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, org_unit=peer,
    )
    assert _adjusts_above_acting_level(salesforecasting_rep_a, peer_submission) is False


def test_salesforecasting_the_level_rule_fails_open_without_provable_nesting(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
    salesforecasting_period_a,
):
    """No membership, or no org unit on either side, means no level to compare --
    so no violation is claimed. Pinned because a fail-CLOSED reading of the same
    code would lock every user out of the feature."""
    from apps.sales.models import ForecastSubmission
    from apps.sales.views.SalesForecasting.ForecastAdjustments import _adjusts_above_acting_level

    submission = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
    )
    assert _adjusts_above_acting_level(salesforecasting_rep_a, submission) is False


def test_salesforecasting_the_level_rule_exempts_a_tenant_admin(
    salesforecasting_tenant_a,
    salesforecasting_admin_a,
    salesforecasting_org_unit_parent_a,
    salesforecasting_period_a,
):
    """A tenant admin passes unconditionally -- the director may always correct a
    rep's number. This exemption is WHY the rule is currently unreachable."""
    from apps.sales.models import ForecastSubmission
    from apps.sales.views.SalesForecasting.ForecastAdjustments import _adjusts_above_acting_level

    root_submission = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        org_unit=salesforecasting_org_unit_parent_a,
    )
    assert _adjusts_above_acting_level(salesforecasting_admin_a, root_submission) is False


def _salesforecasting_adjust_post(submission, note="gate probe"):
    # Mirrors _adjustment_form_data in the forms lane exactly: a `category`
    # target takes a CATEGORY, and leaving adjusted_value populated fails the
    # form's own coherence check in clean().
    return {
        "submission": str(submission.pk),
        "opportunity": "",
        "placement": "",
        "adjustment_kind": "direct",
        "target_field": "category",
        "adjusted_value": "",
        "adjusted_category": "commit",
        "reason_code": "manager_judgement",
        "note": note,
    }


def test_salesforecasting_the_adjust_create_view_is_tenant_admin_gated(
    salesforecasting_tenant_a,
    salesforecasting_client_rep_a,
    salesforecasting_period_a,
):
    """The gate the level rule sits behind. A non-admin is refused by the
    DECORATOR, which is why _adjusts_above_acting_level never runs for the user
    it was written for. Pinned deliberately: if that gate ever changes, this test
    is what will say so."""
    from apps.sales.models import ForecastAdjustment, ForecastSubmission

    submission = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        commit_amount=Decimal("100.00"),
    )
    response = salesforecasting_client_rep_a.post(
        reverse("sales:forecast_adjustment_create"),
        _salesforecasting_adjust_post(submission, "rep gate probe"),
    )
    assert response.status_code == 403
    assert not ForecastAdjustment.objects.filter(
        tenant=salesforecasting_tenant_a, submission=submission
    ).exists()


def test_salesforecasting_a_tenant_admin_may_create_an_adjustment(
    salesforecasting_tenant_a,
    salesforecasting_client_a,
    salesforecasting_period_a,
):
    """The happy path the admin-only gate leaves working today."""
    from apps.sales.models import ForecastAdjustment, ForecastSubmission

    submission = ForecastSubmission.objects.create(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        commit_amount=Decimal("100.00"),
    )
    response = salesforecasting_client_a.post(
        reverse("sales:forecast_adjustment_create"),
        _salesforecasting_adjust_post(submission, "admin override"),
    )
    assert response.status_code == 302
    assert ForecastAdjustment.objects.filter(
        tenant=salesforecasting_tenant_a, submission=submission
    ).exists()

