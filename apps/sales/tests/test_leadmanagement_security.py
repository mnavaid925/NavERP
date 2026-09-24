import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, ModuleAccessScope
from apps.crm.models import CrmTask, Lead, Opportunity
from apps.sales.admin import (
    LeadNurtureEnrollmentAdmin,
    LeadQualificationAdmin,
    LeadRoutingRuleAdmin,
    LeadScoreEventAdmin,
)
from apps.sales.models import (
    LeadNurtureEnrollment,
    LeadQualification,
    LeadRoutingRule,
    LeadScoreEvent,
)
from apps.sales.services import (
    activate_nurture,
    apply_qualification_decision,
    handoff_lead,
    preview_routing,
    record_score_event,
    route_lead,
)
from apps.sales.tests.conftest import (
    _leadmanagement_lead,
    _leadmanagement_nurture_enrollment,
    _leadmanagement_opportunity,
    _leadmanagement_qualification,
    _leadmanagement_routing_rule,
    _leadmanagement_score_event,
)

pytestmark = pytest.mark.django_db

_LEADMANAGEMENT_LIST_ROUTES = (
    "sales_root",
    "lead_overview",
    "lead_score_event_list",
    "lead_qualification_list",
    "lead_routing_rule_list",
    "lead_nurture_enrollment_list",
)

_LEADMANAGEMENT_FOREIGN_GET_ROUTES = (
    ("lead_score_event_detail", "leadmanagement_score_event_b"),
    ("lead_qualification_detail", "leadmanagement_qualification_b"),
    ("lead_qualification_edit", "leadmanagement_qualification_b"),
    ("lead_qualification_route_preview", "leadmanagement_qualification_b"),
    ("lead_routing_rule_detail", "leadmanagement_routing_rule_b"),
    ("lead_routing_rule_edit", "leadmanagement_routing_rule_b"),
    ("lead_routing_rule_preview", "leadmanagement_routing_rule_b"),
    ("lead_nurture_enrollment_detail", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_edit", "leadmanagement_nurture_enrollment_b"),
)

_LEADMANAGEMENT_FOREIGN_POST_ROUTES = (
    ("lead_handoff", "leadmanagement_lead_b"),
    ("lead_score_event_correct", "leadmanagement_score_event_b"),
    ("lead_qualification_delete", "leadmanagement_qualification_b"),
    ("lead_qualification_partial", "leadmanagement_qualification_b"),
    ("lead_qualification_qualify", "leadmanagement_qualification_b"),
    ("lead_qualification_disqualify", "leadmanagement_qualification_b"),
    ("lead_qualification_archive", "leadmanagement_qualification_b"),
    ("lead_qualification_recalculate", "leadmanagement_qualification_b"),
    ("lead_routing_rule_delete", "leadmanagement_routing_rule_b"),
    ("lead_routing_rule_toggle", "leadmanagement_routing_rule_b"),
    ("lead_routing_rule_run", "leadmanagement_routing_rule_b"),
    ("lead_nurture_enrollment_delete", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_activate", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_pause", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_resume", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_complete", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_cancel", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_reply", "leadmanagement_nurture_enrollment_b"),
    ("lead_nurture_enrollment_convert_exit", "leadmanagement_nurture_enrollment_b"),
)

_LEADMANAGEMENT_POST_ROUTES = (
    ("lead_handoff", "leadmanagement_lead_a"),
    ("lead_score_event_adjust", None),
    ("lead_score_event_recompute", None),
    ("lead_score_event_correct", "leadmanagement_score_event_a"),
    ("lead_qualification_delete", "leadmanagement_qualification_a"),
    ("lead_qualification_partial", "leadmanagement_qualification_a"),
    ("lead_qualification_qualify", "leadmanagement_qualification_a"),
    ("lead_qualification_disqualify", "leadmanagement_qualification_a"),
    ("lead_qualification_archive", "leadmanagement_qualification_a"),
    ("lead_qualification_recalculate", "leadmanagement_qualification_a"),
    ("lead_routing_rule_delete", "leadmanagement_routing_rule_a"),
    ("lead_routing_rule_toggle", "leadmanagement_routing_rule_a"),
    ("lead_routing_rule_run", "leadmanagement_routing_rule_a"),
    ("lead_nurture_enrollment_delete", "leadmanagement_nurture_enrollment_a"),
    ("lead_nurture_enrollment_activate", "leadmanagement_nurture_enrollment_a"),
    ("lead_nurture_enrollment_pause", "leadmanagement_nurture_enrollment_a"),
    ("lead_nurture_enrollment_resume", "leadmanagement_nurture_enrollment_a"),
    ("lead_nurture_enrollment_complete", "leadmanagement_nurture_enrollment_a"),
    ("lead_nurture_enrollment_cancel", "leadmanagement_nurture_enrollment_a"),
    ("lead_nurture_enrollment_reply", "leadmanagement_nurture_enrollment_a"),
    ("lead_nurture_enrollment_convert_exit", "leadmanagement_nurture_enrollment_a"),
)

_LEADMANAGEMENT_CSRF_ROUTES = _LEADMANAGEMENT_POST_ROUTES + (
    ("lead_qualification_create", None),
    ("lead_routing_rule_create", None),
    ("lead_nurture_enrollment_create", None),
)


@pytest.fixture
def _leadmanagement_tenantless_superuser_client(db):
    user = get_user_model().objects.create_superuser(
        email="sales-rootless@example.com",
        username="sales_rootless",
        password="TestPass123!",
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def _leadmanagement_tenantless_admin_client(db):
    user = get_user_model().objects.create_user(
        email="sales-tenantless-admin@example.com",
        username="sales_tenantless_admin",
        password="TestPass123!",
        tenant=None,
        is_tenant_admin=True,
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def _leadmanagement_csrf_client(db, leadmanagement_admin_a):
    client = Client(enforce_csrf_checks=True)
    client.force_login(leadmanagement_admin_a)
    return client


def _leadmanagement_url(name, pk=None):
    kwargs = {"pk": pk} if pk is not None else {}
    return reverse(f"sales:{name}", kwargs=kwargs)


def _leadmanagement_param_id(value):
    if value is None:
        return "no-pk"
    if isinstance(value, tuple):
        return str(value[0])
    return str(value)


def _leadmanagement_date(offset=0):
    return (timezone.localdate() + timedelta(days=offset)).isoformat()


def _leadmanagement_score_payload(lead, score_delta=1, reason="Security test adjustment."):
    return {
        "lead": str(lead.pk),
        "score_delta": str(score_delta),
        "reason": reason,
    }


def _leadmanagement_qualification_payload(lead, currency=None, **overrides):
    data = {
        "lead": str(lead.pk),
        "framework": "bant",
        "country_code": "US",
        "region": "North",
        "city": "Springfield",
        "industry": "Industrial Technology",
        "employee_count": "240",
        "seniority": "director",
        "budget_status": "confirmed",
        "budget_amount": "75000.00" if currency is not None else "",
        "budget_currency": str(currency.pk) if currency is not None else "",
        "authority_level": "director",
        "need_summary": "Security qualification evidence.",
        "expected_purchase_on": _leadmanagement_date(45),
        "economic_buyer": "Operations Director",
        "decision_criteria": "Time to value and adoption.",
        "decision_process": "Director review and finance approval.",
        "technical_requirements": "CRM integration and role-based access.",
        "pain_points": "Slow routing and inconsistent evidence.",
        "success_metrics": "Reduce response time and improve conversion.",
        "next_review_on": _leadmanagement_date(14),
        "notes": "Security qualification payload.",
    }
    data.update(overrides)
    return data


def _leadmanagement_routing_payload(
    name="Security routing rule",
    owner=None,
    territory=None,
    eligible_owners=(),
    fallback_owner=None,
    assignment_mode="fixed_owner",
    conditions=None,
    **overrides,
):
    data = {
        "name": name,
        "description": "Security routing payload.",
        "is_active": "on",
        "priority": "10",
        "match_mode": "all",
        "conditions": (
            conditions
            if isinstance(conditions, str)
            else json.dumps(
                conditions
                if conditions is not None
                else [{"field": "status", "operator": "eq", "value": "new"}]
            )
        ),
        "is_catch_all": "",
        "assignment_mode": assignment_mode,
        "default_owner": str(owner.pk) if owner is not None else "",
        "territory": str(territory.pk) if territory is not None else "",
        "eligible_owners": [str(value.pk) for value in eligible_owners],
        "fallback_owner": str(fallback_owner.pk) if fallback_owner is not None else "",
        "max_open_leads": "25",
    }
    data.update(overrides)
    return data


def _leadmanagement_nurture_payload(
    lead,
    email_campaign,
    consent_purpose,
    owner=None,
    **overrides,
):
    data = {
        "lead": str(lead.pk),
        "email_campaign": str(email_campaign.pk),
        "trigger_kind": "manual",
        "consent_purpose": str(consent_purpose.pk),
        "consent_evidence": "Consent evidence from the security test.",
        "owner": str(owner.pk) if owner is not None else "",
        "notes": "Security nurture payload.",
    }
    data.update(overrides)
    return data


def _leadmanagement_invalid_routing_json():
    return (
        ("malformed", "not-json"),
        ("object", json.dumps({"field": "status", "operator": "eq", "value": "new"})),
        ("empty", "[]"),
        ("missing-value", json.dumps([{"field": "status", "operator": "eq"}])),
        ("extra-key", json.dumps([{"field": "status", "operator": "eq", "value": "new", "extra": True}])),
        ("unhashable-field", json.dumps([{"field": [], "operator": "eq", "value": "new"}])),
        ("unhashable-operator", json.dumps([{"field": "status", "operator": [], "value": "new"}])),
        ("nested-value", json.dumps([{"field": "status", "operator": "eq", "value": {"nested": "object"}}])),
        ("relation-traversal", json.dumps([{"field": "owner__tenant_id", "operator": "eq", "value": 1}])),
        ("unsupported-operator", json.dumps([{"field": "status", "operator": "eval", "value": "new"}])),
        ("nonfinite-number", json.dumps([{"field": "score", "operator": "eq", "value": float("nan")}])),
        ("nonfinite-infinity", json.dumps([{"field": "score", "operator": "eq", "value": float("inf")}])),
        ("raw-nan", '[{"field":"score","operator":"eq","value":NaN}]'),
        ("oversized-scalar", json.dumps([{"field": "company", "operator": "icontains", "value": "x" * 256}])),
        ("oversized-list", json.dumps([{"field": "status", "operator": "in", "value": [str(i) for i in range(21)]}])),
        ("oversized-document", json.dumps([{"field": "company", "operator": "icontains", "value": "x" * 17_000}])),
        (
            "too-many-conditions",
            json.dumps([{"field": "status", "operator": "eq", "value": "new"} for _ in range(21)]),
        ),
    )


def _leadmanagement_row_state(row):
    names = ("status", "is_active", "owner_id", "corrects_event_id")
    return {name: getattr(row, name) for name in names if hasattr(row, name)}


def _leadmanagement_audit_rows(row, action=None):
    queryset = AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(row.__class__),
        object_id=row.pk,
    )
    if action is not None:
        queryset = queryset.filter(action=action)
    return queryset.order_by("-at")


def _leadmanagement_admin_request(user, tenant):
    request = RequestFactory().get("/")
    request.user = user
    request.tenant = tenant
    return request


def _leadmanagement_assert_tenantless_lists_are_empty(client):
    for route in _LEADMANAGEMENT_LIST_ROUTES:
        response = client.get(_leadmanagement_url(route))
        assert response.status_code == 200, route
        for key in ("object_list", "leads", "qualifications", "enrollments", "latest_score_events"):
            assert not response.context.get(key, []), (route, key)


def test_leadmanagement_tenantless_superuser_reads_empty_and_cannot_write(
    _leadmanagement_tenantless_superuser_client,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_score_event_a,
):
    client = _leadmanagement_tenantless_superuser_client
    _leadmanagement_assert_tenantless_lists_are_empty(client)

    for route, row in (
        ("lead_score_event_detail", leadmanagement_score_event_a),
        ("lead_qualification_detail", leadmanagement_qualification_a),
        ("lead_qualification_edit", leadmanagement_qualification_a),
        ("lead_routing_rule_detail", leadmanagement_routing_rule_a),
        ("lead_nurture_enrollment_detail", leadmanagement_nurture_enrollment_a),
    ):
        assert client.get(_leadmanagement_url(route, row.pk)).status_code == 404, route

    for route in (
        "lead_qualification_create",
        "lead_routing_rule_create",
        "lead_nurture_enrollment_create",
    ):
        get_response = client.get(_leadmanagement_url(route))
        post_response = client.post(_leadmanagement_url(route), {})
        assert get_response.status_code == 302, route
        assert post_response.status_code == 302, route
        assert post_response.url == reverse("dashboard:home"), route

    before = LeadScoreEvent.objects.count()
    assert client.post(
        _leadmanagement_url("lead_score_event_adjust"),
        _leadmanagement_score_payload(leadmanagement_lead_a),
    ).status_code == 302
    assert client.post(
        _leadmanagement_url("lead_score_event_recompute"),
        {"lead_id": leadmanagement_lead_a.pk},
    ).status_code == 404
    assert client.post(
        _leadmanagement_url("lead_handoff", leadmanagement_lead_a.pk),
        {},
    ).status_code == 404
    assert LeadScoreEvent.objects.count() == before
    assert leadmanagement_tenant_a.pk is not None


def test_leadmanagement_tenantless_admin_flag_cannot_bypass_workspace_scope(
    _leadmanagement_tenantless_admin_client,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
):
    client = _leadmanagement_tenantless_admin_client
    _leadmanagement_assert_tenantless_lists_are_empty(client)
    assert client.get(
        _leadmanagement_url("lead_qualification_detail", leadmanagement_qualification_a.pk)
    ).status_code == 404
    assert client.post(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        {},
    ).status_code == 404
    assert client.post(_leadmanagement_url("lead_routing_rule_create"), {}).url == reverse("dashboard:home")
    assert LeadQualification.objects.filter(pk=leadmanagement_qualification_a.pk).exists()
    assert LeadNurtureEnrollment.objects.filter(pk=leadmanagement_nurture_enrollment_a.pk).exists()


@pytest.mark.parametrize("route,fixture_name", _LEADMANAGEMENT_FOREIGN_GET_ROUTES, ids=_leadmanagement_param_id)
def test_leadmanagement_cross_tenant_detail_edit_and_preview_are_404(
    route,
    fixture_name,
    request,
    leadmanagement_admin_client_a,
):
    row = request.getfixturevalue(fixture_name)
    response = leadmanagement_admin_client_a.get(_leadmanagement_url(route, row.pk))
    assert response.status_code == 404, route
    assert type(row).objects.filter(pk=row.pk).exists(), route


@pytest.mark.parametrize("route,fixture_name", _LEADMANAGEMENT_FOREIGN_POST_ROUTES, ids=_leadmanagement_param_id)
def test_leadmanagement_cross_tenant_actions_are_404_and_do_not_mutate(
    route,
    fixture_name,
    request,
    leadmanagement_admin_client_a,
):
    row = request.getfixturevalue(fixture_name)
    before = _leadmanagement_row_state(row)
    response = leadmanagement_admin_client_a.post(_leadmanagement_url(route, row.pk), {})
    assert response.status_code == 404, route
    row.refresh_from_db()
    assert _leadmanagement_row_state(row) == before, route
    assert type(row).objects.filter(pk=row.pk).exists(), route


def test_leadmanagement_cross_tenant_recompute_lead_id_is_404(
    leadmanagement_admin_client_a,
    leadmanagement_lead_b,
    leadmanagement_score_event_b,
):
    before = leadmanagement_lead_b.status
    response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_score_event_recompute"),
        {"lead_id": leadmanagement_lead_b.pk},
    )
    assert response.status_code == 404
    leadmanagement_lead_b.refresh_from_db()
    assert leadmanagement_lead_b.status == before
    assert LeadScoreEvent.objects.filter(pk=leadmanagement_score_event_b.pk).exists()


def test_leadmanagement_tenant_b_admin_cannot_read_or_act_on_tenant_a_rows(
    leadmanagement_admin_client_b,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
):
    assert leadmanagement_admin_client_b.get(
        _leadmanagement_url("lead_qualification_detail", leadmanagement_qualification_a.pk)
    ).status_code == 404
    assert leadmanagement_admin_client_b.get(
        _leadmanagement_url("lead_nurture_enrollment_detail", leadmanagement_nurture_enrollment_a.pk)
    ).status_code == 404
    assert leadmanagement_admin_client_b.post(
        _leadmanagement_url("lead_qualification_archive", leadmanagement_qualification_a.pk),
        {"status": "archived"},
    ).status_code == 404
    assert leadmanagement_admin_client_b.post(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        {},
    ).status_code == 404


def test_leadmanagement_crafted_foreign_qualification_fk_is_rejected_without_creating_a_row(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_lead_b,
    leadmanagement_currency,
):
    before = LeadQualification.objects.count()
    response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_create"),
        _leadmanagement_qualification_payload(leadmanagement_lead_b, leadmanagement_currency),
    )
    assert response.status_code == 200
    assert "lead" in response.context["form"].errors
    assert LeadQualification.objects.count() == before
    assert not LeadQualification.objects.filter(tenant=leadmanagement_tenant_a, lead=leadmanagement_lead_b).exists()
    assert leadmanagement_tenant_b.pk != leadmanagement_tenant_a.pk


def test_leadmanagement_crafted_foreign_routing_fk_and_m2m_values_are_rejected(
    leadmanagement_admin_client_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_territory_b,
):
    cases = (
        ("default_owner", leadmanagement_admin_b, "fixed_owner"),
        ("fallback_owner", leadmanagement_admin_b, "fixed_owner"),
        ("territory", leadmanagement_territory_b, "fixed_owner"),
        ("eligible_owners", leadmanagement_admin_b, "round_robin"),
    )
    for field_name, foreign, assignment_mode in cases:
        before = LeadRoutingRule.objects.count()
        payload = _leadmanagement_routing_payload(
            name=f"Foreign {field_name}",
            owner=leadmanagement_admin_a,
            assignment_mode=assignment_mode,
            eligible_owners=(leadmanagement_admin_a,) if assignment_mode == "round_robin" else (),
        )
        payload[field_name] = [str(foreign.pk)] if field_name == "eligible_owners" else str(foreign.pk)
        response = leadmanagement_admin_client_a.post(
            _leadmanagement_url("lead_routing_rule_create"),
            payload,
        )
        assert response.status_code == 200, field_name
        assert field_name in response.context["form"].errors, field_name
        assert LeadRoutingRule.objects.count() == before, field_name


def test_leadmanagement_crafted_foreign_nurture_fk_values_are_rejected_without_creating_a_row(
    leadmanagement_admin_client_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_email_campaign_a,
    leadmanagement_email_campaign_b,
    leadmanagement_consent_purpose_a,
    leadmanagement_consent_purpose_b,
):
    cases = (
        ("lead", leadmanagement_lead_b),
        ("email_campaign", leadmanagement_email_campaign_b),
        ("consent_purpose", leadmanagement_consent_purpose_b),
        ("owner", leadmanagement_admin_b),
    )
    for field_name, foreign in cases:
        before = LeadNurtureEnrollment.objects.count()
        payload = _leadmanagement_nurture_payload(
            leadmanagement_lead_a,
            leadmanagement_email_campaign_a,
            leadmanagement_consent_purpose_a,
            owner=leadmanagement_admin_a,
        )
        payload[field_name] = str(foreign.pk)
        response = leadmanagement_admin_client_a.post(
            _leadmanagement_url("lead_nurture_enrollment_create"),
            payload,
        )
        assert response.status_code == 200, field_name
        assert field_name in response.context["form"].errors, field_name
        assert LeadNurtureEnrollment.objects.count() == before, field_name


def test_leadmanagement_widened_form_querysets_still_reject_foreign_relations(
    leadmanagement_tenant_a,
    leadmanagement_lead_b,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_territory_b,
):
    from apps.sales.forms import LeadNurtureEnrollmentForm, LeadRoutingRuleForm

    routing_payload = _leadmanagement_routing_payload(
        name="Widened routing rejection",
        owner=leadmanagement_admin_b,
    )

    routing_form = LeadRoutingRuleForm(routing_payload, tenant=leadmanagement_tenant_a)
    routing_form.fields["default_owner"].queryset = type(leadmanagement_admin_b).objects.all()
    assert not routing_form.is_valid()
    assert "default_owner" in routing_form.errors

    nurture_form = LeadNurtureEnrollmentForm(
        _leadmanagement_nurture_payload(
            leadmanagement_lead_b,
            leadmanagement_email_campaign_a,
            leadmanagement_consent_purpose_a,
            owner=leadmanagement_admin_a,
        ),
        tenant=leadmanagement_tenant_a,
    )
    nurture_form.fields["lead"].queryset = Lead.objects.all()
    assert not nurture_form.is_valid()
    assert "lead" in nurture_form.errors
    assert leadmanagement_territory_b.tenant_id != leadmanagement_tenant_a.pk


def test_leadmanagement_member_cannot_cross_admin_only_gates(
    request,
    leadmanagement_member_client_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
    leadmanagement_nurture_enrollment_a,
):
    cases = (
        ("lead_handoff", leadmanagement_lead_a),
        ("lead_score_event_adjust", None),
        ("lead_score_event_recompute", None),
        ("lead_score_event_correct", leadmanagement_score_event_a),
        ("lead_qualification_archive", leadmanagement_qualification_a),
        ("lead_routing_rule_create", None),
        ("lead_routing_rule_edit", leadmanagement_routing_rule_a),
        ("lead_routing_rule_delete", leadmanagement_routing_rule_a),
        ("lead_routing_rule_toggle", leadmanagement_routing_rule_a),
        ("lead_routing_rule_run", leadmanagement_routing_rule_a),
        ("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a),
        ("lead_nurture_enrollment_resume", leadmanagement_nurture_enrollment_a),
        ("lead_nurture_enrollment_convert_exit", leadmanagement_nurture_enrollment_a),
    )
    for route, row in cases:
        pk = row.pk if row is not None else None
        response = leadmanagement_member_client_a.post(_leadmanagement_url(route, pk), {})
        assert response.status_code == 403, route
        if row is not None:
            assert type(row).objects.filter(pk=row.pk).exists(), route
    assert LeadScoreEvent.objects.filter(event_type="manual_adjustment").count() == 0
    assert leadmanagement_qualification_a.status == "unassessed"
    assert leadmanagement_nurture_enrollment_a.status == "pending"
    assert leadmanagement_routing_rule_a.is_active is True


def test_leadmanagement_member_cannot_reach_admin_configuration_forms(
    leadmanagement_member_client_a,
    leadmanagement_routing_rule_a,
):
    assert leadmanagement_member_client_a.get(
        _leadmanagement_url("lead_routing_rule_create")
    ).status_code == 403
    assert leadmanagement_member_client_a.get(
        _leadmanagement_url("lead_routing_rule_edit", leadmanagement_routing_rule_a.pk)
    ).status_code == 403


def test_leadmanagement_member_login_only_transitions_remain_available(
    leadmanagement_member_client_a,
    leadmanagement_qualification_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_lead_a,
):
    partial = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_qualification_partial", leadmanagement_qualification_a.pk),
        {"status": "partially_qualified"},
    )
    assert partial.status_code == 302
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "partially_qualified"

    enrollment = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
        owner=leadmanagement_admin_a,
    )
    activate_nurture(enrollment, leadmanagement_tenant_a, leadmanagement_admin_a)
    paused = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_pause", enrollment.pk),
    )
    assert paused.status_code == 302
    enrollment.refresh_from_db()
    assert enrollment.status == "paused"


@pytest.mark.parametrize("route,fixture_name", _LEADMANAGEMENT_POST_ROUTES, ids=_leadmanagement_param_id)
def test_leadmanagement_post_only_routes_return_405_for_admin(
    route,
    fixture_name,
    request,
    leadmanagement_admin_client_a,
):
    pk = None if fixture_name is None else request.getfixturevalue(fixture_name).pk
    assert leadmanagement_admin_client_a.get(_leadmanagement_url(route, pk)).status_code == 405, route


@pytest.mark.parametrize("route,fixture_name", _LEADMANAGEMENT_POST_ROUTES, ids=_leadmanagement_param_id)
def test_leadmanagement_post_only_routes_return_405_for_member(
    route,
    fixture_name,
    request,
    leadmanagement_member_client_a,
):
    pk = None if fixture_name is None else request.getfixturevalue(fixture_name).pk
    assert leadmanagement_member_client_a.get(_leadmanagement_url(route, pk)).status_code == 405, route


def test_leadmanagement_unsupported_methods_are_refused_on_post_only_routes(
    leadmanagement_admin_client_a,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
):
    assert leadmanagement_admin_client_a.put(
        _leadmanagement_url("lead_qualification_delete", leadmanagement_qualification_a.pk)
    ).status_code == 405
    assert leadmanagement_admin_client_a.delete(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk)
    ).status_code == 405


@pytest.mark.parametrize("route,fixture_name", _LEADMANAGEMENT_CSRF_ROUTES, ids=_leadmanagement_param_id)
def test_leadmanagement_csrf_is_required_for_every_state_changing_route(
    route,
    fixture_name,
    request,
    _leadmanagement_csrf_client,
):
    pk = None if fixture_name is None else request.getfixturevalue(fixture_name).pk
    response = _leadmanagement_csrf_client.post(_leadmanagement_url(route, pk), {})
    assert response.status_code == 403, route


def test_leadmanagement_anonymous_access_redirects_to_login(
    client,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
):
    for route in _LEADMANAGEMENT_LIST_ROUTES:
        response = client.get(_leadmanagement_url(route))
        assert response.status_code == 302, route
        assert "login" in response.url.lower(), route
    assert client.get(
        _leadmanagement_url("lead_qualification_detail", leadmanagement_qualification_a.pk)
    ).status_code == 302
    assert client.post(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        {},
    ).status_code == 302


def test_leadmanagement_converted_lead_blocks_requalification_reopening_and_routing(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
):
    leadmanagement_lead_a.status = "converted"
    leadmanagement_lead_a.save(update_fields=["status", "updated_at"])
    before_events = LeadScoreEvent.objects.filter(
        tenant=leadmanagement_tenant_a,
        lead=leadmanagement_lead_a,
    ).count()

    with pytest.raises(ValidationError, match="converted lead"):
        apply_qualification_decision(
            leadmanagement_qualification_a,
            leadmanagement_tenant_a,
            leadmanagement_admin_a,
            status="qualified",
        )

    for route, payload in (
        ("lead_qualification_partial", {"status": "partially_qualified"}),
        ("lead_qualification_qualify", {"status": "qualified"}),
        ("lead_qualification_disqualify", {"status": "disqualified", "disqualification_reason": "No."}),
        ("lead_qualification_archive", {"status": "archived"}),
    ):
        response = leadmanagement_admin_client_a.post(
            _leadmanagement_url(route, leadmanagement_qualification_a.pk),
            payload,
        )
        assert response.status_code == 302, route

    leadmanagement_qualification_a.refresh_from_db()
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "unassessed"
    assert leadmanagement_lead_a.status == "converted"
    assert LeadScoreEvent.objects.filter(
        tenant=leadmanagement_tenant_a,
        lead=leadmanagement_lead_a,
    ).count() == before_events

    edit_get = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_qualification_edit", leadmanagement_qualification_a.pk)
    )
    assert edit_get.status_code == 302
    original_notes = leadmanagement_qualification_a.notes
    edit_post = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_edit", leadmanagement_qualification_a.pk),
        _leadmanagement_qualification_payload(leadmanagement_lead_a, notes="forged converted edit"),
    )
    assert edit_post.status_code in {200, 302}
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.notes == original_notes

    converted_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=None,
        name="Converted routing lead",
        email="converted-routing@example.com",
        status="converted",
    )
    catch_all = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        default_owner=leadmanagement_admin_a,
        name="Converted routing guard",
        conditions=[],
        is_catch_all=True,
    )
    preview = preview_routing(converted_lead, leadmanagement_tenant_a, catch_all)
    result = route_lead(converted_lead, leadmanagement_tenant_a, leadmanagement_admin_a, catch_all)
    converted_lead.refresh_from_db()
    catch_all.refresh_from_db()
    assert preview["matched"] is False
    assert "Converted" in preview["reason"]
    assert result["changed"] is False
    assert converted_lead.owner_id is None
    assert catch_all.last_assigned_owner_id is None
    assert not CrmTask.objects.filter(tenant=leadmanagement_tenant_a, subject=f"Follow up {converted_lead.number}").exists()
    assert leadmanagement_routing_rule_a.is_active is True


def test_leadmanagement_archived_assessment_blocks_edit_decisions_and_routing(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
):
    leadmanagement_qualification_a.status = "archived"
    leadmanagement_qualification_a.assessed_by = leadmanagement_admin_a
    leadmanagement_qualification_a.assessed_at = timezone.now()
    leadmanagement_qualification_a.save(update_fields=["status", "assessed_by", "assessed_at", "updated_at"])
    leadmanagement_lead_a.owner = None
    leadmanagement_lead_a.status = "new"
    leadmanagement_lead_a.save(update_fields=["owner", "status", "updated_at"])

    for route, payload in (
        ("lead_qualification_partial", {"status": "partially_qualified"}),
        ("lead_qualification_qualify", {"status": "qualified"}),
        ("lead_qualification_edit", _leadmanagement_qualification_payload(leadmanagement_lead_a, notes="forged archive edit")),
    ):
        response = leadmanagement_admin_client_a.post(
            _leadmanagement_url(route, leadmanagement_qualification_a.pk),
            payload,
        )
        assert response.status_code in {200, 302}, route

    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "archived"
    assert leadmanagement_qualification_a.notes != "forged archive edit"

    catch_all = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        default_owner=leadmanagement_admin_a,
        name="Archived routing guard",
        conditions=[],
        is_catch_all=True,
    )
    preview = preview_routing(leadmanagement_lead_a, leadmanagement_tenant_a, catch_all)
    result = route_lead(leadmanagement_lead_a, leadmanagement_tenant_a, leadmanagement_admin_a, catch_all)
    leadmanagement_lead_a.refresh_from_db()
    catch_all.refresh_from_db()
    assert preview["matched"] is False
    assert "Archived" in preview["reason"]
    assert result["changed"] is False
    assert leadmanagement_lead_a.owner_id is None
    assert catch_all.last_assigned_owner_id is None
    assert not CrmTask.objects.filter(tenant=leadmanagement_tenant_a, subject=f"Follow up {leadmanagement_lead_a.number}").exists()
    assert leadmanagement_routing_rule_a.is_active is True


def test_leadmanagement_converted_lead_cannot_enter_nurture(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_nurture_enrollment_a,
):
    leadmanagement_lead_a.status = "converted"
    leadmanagement_lead_a.save(update_fields=["status", "updated_at"])
    response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        {},
    )
    assert response.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "pending"
    assert leadmanagement_nurture_enrollment_a.tenant_id == leadmanagement_tenant_a.pk


@pytest.mark.parametrize(
    "conditions",
    _leadmanagement_invalid_routing_json(),
    ids=_leadmanagement_param_id,
)
def test_leadmanagement_routing_rejects_injection_and_non_finite_json(
    conditions,
    leadmanagement_admin_client_a,
    leadmanagement_admin_a,
):
    before = LeadRoutingRule.objects.count()
    response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_routing_rule_create"),
        _leadmanagement_routing_payload(
            name=f"Rejected {conditions[0] if isinstance(conditions, tuple) else 'json'}",
            owner=leadmanagement_admin_a,
            assignment_mode="round_robin",
            eligible_owners=(leadmanagement_admin_a,),
            conditions=conditions[1] if isinstance(conditions, tuple) else conditions,
        ),
    )
    assert response.status_code == 200
    assert "conditions" in response.context["form"].errors
    assert LeadRoutingRule.objects.count() == before


def test_leadmanagement_routing_json_injection_is_stored_as_data_and_escaped_on_detail(
    leadmanagement_admin_client_a,
    leadmanagement_admin_a,
):
    payload = _leadmanagement_routing_payload(
        name="Escaped routing value",
        owner=leadmanagement_admin_a,
        conditions=[{"field": "company", "operator": "icontains", "value": "</script><script>alert(1)</script>"}],
    )
    created = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_routing_rule_create"),
        payload,
    )
    assert created.status_code == 302
    rule = LeadRoutingRule.objects.get(name="Escaped routing value")
    detail = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_detail", rule.pk))
    body = detail.content.decode()
    assert "</script><script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
    assert rule.conditions[0]["value"] == "</script><script>alert(1)</script>"


@pytest.mark.parametrize("raw_delta", ("NaN", "Infinity", "-Infinity", "1e3", "", "-101", "101"))
def test_leadmanagement_score_adjust_rejects_non_finite_and_out_of_range_input(
    raw_delta,
    leadmanagement_admin_client_a,
    leadmanagement_lead_a,
):
    before = LeadScoreEvent.objects.count()
    response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_score_event_adjust"),
        {
            "lead": leadmanagement_lead_a.pk,
            "score_delta": raw_delta,
            "reason": "Hostile score input.",
        },
    )
    assert response.status_code == 302
    assert LeadScoreEvent.objects.count() == before


@pytest.mark.parametrize("raw_id", ("0", "-1", "abc", "²", "9" * 40))
def test_leadmanagement_score_recompute_rejects_non_pk_ids_without_500(
    raw_id,
    leadmanagement_admin_client_a,
    leadmanagement_lead_a,
):
    response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_score_event_recompute"),
        {"lead_id": raw_id},
    )
    assert response.status_code == 302
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.score == 25


def test_leadmanagement_score_idempotency_rejects_conflicting_replay_payloads(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_admin_a,
):
    first = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        recorded_by=leadmanagement_admin_a,
        idempotency_key="security-idempotency-key",
    )
    replay = record_score_event(
        leadmanagement_lead_a,
        leadmanagement_tenant_a,
        event_type="form_submitted",
        score_delta=first.score_delta,
        source_kind=first.source_kind,
        source_ref=first.source_ref,
        reason=first.reason,
        recorded_by=leadmanagement_admin_a,
        idempotency_key="security-idempotency-key",
    )
    assert replay.pk == first.pk
    with pytest.raises(ValidationError, match="different score event"):
        record_score_event(
            leadmanagement_lead_a,
            leadmanagement_tenant_a,
            event_type="web_visit",
            score_delta=1,
            source_kind=first.source_kind,
            source_ref=first.source_ref,
            reason=first.reason,
            recorded_by=leadmanagement_admin_a,
            idempotency_key="security-idempotency-key",
        )
    assert LeadScoreEvent.objects.filter(idempotency_key="security-idempotency-key").count() == 1


def test_leadmanagement_score_correction_is_inverse_single_use_and_replay_safe(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_admin_a,
    leadmanagement_score_event_a,
):
    wrong = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_score_event_correct", leadmanagement_score_event_a.pk),
        {
            "lead": leadmanagement_lead_a.pk,
            "corrects_event": leadmanagement_score_event_a.pk,
            "score_delta": "-4",
            "reason": "Wrong inverse delta.",
        },
    )
    assert wrong.status_code == 302
    assert not LeadScoreEvent.objects.filter(corrects_event=leadmanagement_score_event_a).exists()

    valid = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_score_event_correct", leadmanagement_score_event_a.pk),
        {
            "lead": leadmanagement_lead_a.pk,
            "corrects_event": leadmanagement_score_event_a.pk,
            "score_delta": "-5",
            "reason": "Reverse the original event.",
        },
    )
    assert valid.status_code == 302
    assert LeadScoreEvent.objects.filter(corrects_event=leadmanagement_score_event_a).count() == 1

    replay = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_score_event_correct", leadmanagement_score_event_a.pk),
        {
            "lead": leadmanagement_lead_a.pk,
            "corrects_event": leadmanagement_score_event_a.pk,
            "score_delta": "-5",
            "reason": "Reverse the original event.",
        },
    )
    assert replay.status_code == 302
    assert LeadScoreEvent.objects.filter(corrects_event=leadmanagement_score_event_a).count() == 1

    with pytest.raises(ValidationError, match="already been corrected"):
        record_score_event(
            leadmanagement_lead_a,
            leadmanagement_tenant_a,
            event_type="correction",
            score_delta=-5,
            reason="Attempt a second correction.",
            recorded_by=leadmanagement_admin_a,
            corrects_event=leadmanagement_score_event_a,
            idempotency_key="second-correction-attempt",
        )

    other_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=leadmanagement_admin_a,
        name="Wrong correction lead",
        email="wrong-correction@example.com",
    )
    with pytest.raises(ValidationError, match="selected lead"):
        record_score_event(
            other_lead,
            leadmanagement_tenant_a,
            event_type="correction",
            score_delta=-5,
            reason="Wrong lead correction.",
            recorded_by=leadmanagement_admin_a,
            corrects_event=leadmanagement_score_event_a,
            idempotency_key="wrong-lead-correction",
        )


def test_leadmanagement_score_correction_rejects_foreign_event_without_mutating_it(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_b,
):
    foreign = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_score_event_correct", leadmanagement_score_event_b.pk),
        {
            "lead": leadmanagement_lead_a.pk,
            "corrects_event": leadmanagement_score_event_b.pk,
            "score_delta": "-5",
            "reason": "Foreign event correction.",
        },
    )
    assert foreign.status_code == 404
    assert not LeadScoreEvent.objects.filter(corrects_event=leadmanagement_score_event_b).exists()


def test_leadmanagement_mass_assignment_cannot_set_system_state_or_foreign_tenant(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_admin_a,
    leadmanagement_currency,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
):
    qualification_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=leadmanagement_admin_a,
        name="Mass assignment qualification lead",
        email="mass-assignment-qualification@example.com",
    )
    qualification_response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_create"),
        _leadmanagement_qualification_payload(
            qualification_lead,
            leadmanagement_currency,
            status="qualified",
            assessed_by=leadmanagement_admin_a.pk,
            assessed_at="2020-01-01T00:00:00Z",
            tenant=leadmanagement_tenant_b.pk,
        ),
    )
    assert qualification_response.status_code == 302
    qualification = LeadQualification.objects.get(lead=qualification_lead)
    assert qualification.tenant_id == leadmanagement_tenant_a.pk
    assert qualification.status == "unassessed"
    assert qualification.assessed_by_id is None
    assert qualification.assessed_at is None

    routing_response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_routing_rule_create"),
        _leadmanagement_routing_payload(
            name="Mass assignment routing",
            owner=leadmanagement_admin_a,
            tenant=leadmanagement_tenant_b.pk,
            cursor="99",
            last_assigned_owner=leadmanagement_admin_a.pk,
            last_assigned_at="2020-01-01T00:00:00Z",
        ),
    )
    assert routing_response.status_code == 302
    rule = LeadRoutingRule.objects.get(name="Mass assignment routing")
    assert rule.tenant_id == leadmanagement_tenant_a.pk
    assert rule.cursor == 0
    assert rule.last_assigned_owner_id is None
    assert rule.last_assigned_at is None

    nurture_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=leadmanagement_admin_a,
        name="Mass assignment nurture lead",
        email="mass-assignment-nurture@example.com",
    )
    nurture_response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_create"),
        _leadmanagement_nurture_payload(
            nurture_lead,
            leadmanagement_email_campaign_a,
            leadmanagement_consent_purpose_a,
            owner=leadmanagement_admin_a,
            status="active",
            number="LNE-99999",
            score_at_enrollment="100",
            tenant=leadmanagement_tenant_b.pk,
            started_at="2020-01-01T00:00:00Z",
            completed_at="2020-01-01T00:00:00Z",
        ),
    )
    assert nurture_response.status_code == 302
    enrollment = LeadNurtureEnrollment.objects.get(lead=nurture_lead)
    assert enrollment.tenant_id == leadmanagement_tenant_a.pk
    assert enrollment.status == "pending"
    assert enrollment.number != "LNE-99999"
    assert enrollment.score_at_enrollment is None
    assert enrollment.started_at is None
    assert enrollment.completed_at is None


def test_leadmanagement_consent_evidence_and_sensitive_qualification_text_are_redacted_in_audit(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_currency,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
):
    consent_secret = "CONSENT-EVIDENCE-SECRET-8f4c"
    enrollment_response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_edit", leadmanagement_nurture_enrollment_a.pk),
        _leadmanagement_nurture_payload(
            leadmanagement_nurture_enrollment_a.lead,
            leadmanagement_email_campaign_a,
            leadmanagement_consent_purpose_a,
            owner=leadmanagement_nurture_enrollment_a.owner,
            consent_evidence=consent_secret,
        ),
    )
    assert enrollment_response.status_code == 302
    enrollment_log = _leadmanagement_audit_rows(leadmanagement_nurture_enrollment_a, action="update").first()
    assert enrollment_log is not None
    assert enrollment_log.changes.get("consent_evidence") == "***redacted***"
    assert consent_secret not in json.dumps(enrollment_log.changes, default=str)

    qualification_secret = "QUALIFICATION-FREE-TEXT-SECRET-2a91"
    qualification_response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_edit", leadmanagement_qualification_a.pk),
        _leadmanagement_qualification_payload(
            leadmanagement_qualification_a.lead,
            leadmanagement_currency,
            need_summary=qualification_secret,
            notes="Updated audit-safe note.",
        ),
    )
    assert qualification_response.status_code == 302
    qualification_log = _leadmanagement_audit_rows(leadmanagement_qualification_a, action="update").first()
    assert qualification_log is not None
    assert qualification_log.changes.get("need_summary") == "***redacted***"
    assert qualification_secret not in json.dumps(qualification_log.changes, default=str)
    assert qualification_log.tenant_id == leadmanagement_tenant_a.pk
    assert qualification_log.user_id == leadmanagement_admin_a.pk
    assert enrollment_log.tenant_id == leadmanagement_tenant_a.pk
    assert enrollment_log.user_id == leadmanagement_admin_a.pk


def test_leadmanagement_crm_handoff_preserves_identity_and_replay_is_idempotent(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
):
    from apps.core.models import ContactMethod, Party, PartyRole

    apply_qualification_decision(
        leadmanagement_qualification_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        status="qualified",
    )
    activate_nurture(
        leadmanagement_nurture_enrollment_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    before_parties = Party.objects.filter(tenant=leadmanagement_tenant_a).count()
    before_methods = ContactMethod.objects.filter(tenant=leadmanagement_tenant_a).count()
    before_roles = PartyRole.objects.filter(tenant=leadmanagement_tenant_a).count()
    original_campaign_id = leadmanagement_nurture_enrollment_a.email_campaign_id

    response = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_handoff", leadmanagement_lead_a.pk),
    )
    assert response.status_code == 302
    opportunity = Opportunity.objects.get(tenant=leadmanagement_tenant_a, source_lead=leadmanagement_lead_a)
    leadmanagement_lead_a.refresh_from_db()
    leadmanagement_nurture_enrollment_a.refresh_from_db()

    assert leadmanagement_lead_a.status == "converted"
    assert leadmanagement_lead_a.converted_party_id in {
        opportunity.account_id,
        opportunity.primary_contact_id,
    }
    assert opportunity.tenant_id == leadmanagement_tenant_a.pk
    assert opportunity.source_lead_id == leadmanagement_lead_a.pk
    assert leadmanagement_nurture_enrollment_a.status == "converted"
    assert leadmanagement_nurture_enrollment_a.lead_id == leadmanagement_lead_a.pk
    assert leadmanagement_nurture_enrollment_a.email_campaign_id == original_campaign_id
    assert Party.objects.filter(tenant=leadmanagement_tenant_a).count() == before_parties + 2
    assert ContactMethod.objects.filter(
        tenant=leadmanagement_tenant_a,
        value=leadmanagement_lead_a.email,
    ).exists()
    assert PartyRole.objects.filter(tenant=leadmanagement_tenant_a).count() == before_roles + 2
    assert CrmTask.objects.filter(
        tenant=leadmanagement_tenant_a,
        related_opportunity=opportunity,
        subject=f"Follow up {leadmanagement_lead_a.number}",
    ).count() == 1

    replay = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_handoff", leadmanagement_lead_a.pk),
    )
    assert replay.status_code == 302
    assert Opportunity.objects.filter(tenant=leadmanagement_tenant_a, source_lead=leadmanagement_lead_a).count() == 1
    assert Party.objects.filter(tenant=leadmanagement_tenant_a).count() == before_parties + 2
    assert ContactMethod.objects.filter(tenant=leadmanagement_tenant_a).count() == before_methods + 1
    assert PartyRole.objects.filter(tenant=leadmanagement_tenant_a).count() == before_roles + 2
    assert CrmTask.objects.filter(
        tenant=leadmanagement_tenant_a,
        related_opportunity=opportunity,
        subject=f"Follow up {leadmanagement_lead_a.number}",
    ).count() == 1


def test_leadmanagement_crm_handoff_reuses_an_existing_source_opportunity_without_minting_identity(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_account_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_currency,
):
    from apps.core.models import ContactMethod, Party, PartyRole

    opportunity = _leadmanagement_opportunity(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        leadmanagement_account_a,
        currency=leadmanagement_currency,
        owner=leadmanagement_admin_a,
    )
    apply_qualification_decision(
        leadmanagement_qualification_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        status="qualified",
    )
    before_parties = Party.objects.filter(tenant=leadmanagement_tenant_a).count()
    before_methods = ContactMethod.objects.filter(tenant=leadmanagement_tenant_a).count()
    before_roles = PartyRole.objects.filter(tenant=leadmanagement_tenant_a).count()

    result = handoff_lead(leadmanagement_lead_a, leadmanagement_tenant_a, leadmanagement_admin_a)
    leadmanagement_lead_a.refresh_from_db()
    assert result.pk == opportunity.pk
    assert leadmanagement_lead_a.status == "converted"
    assert leadmanagement_lead_a.converted_party_id == opportunity.account_id
    assert Opportunity.objects.filter(tenant=leadmanagement_tenant_a, source_lead=leadmanagement_lead_a).count() == 1
    assert Party.objects.filter(tenant=leadmanagement_tenant_a).count() == before_parties
    assert ContactMethod.objects.filter(tenant=leadmanagement_tenant_a).count() == before_methods
    assert PartyRole.objects.filter(tenant=leadmanagement_tenant_a).count() == before_roles


def test_leadmanagement_nurture_conversion_exit_requires_a_same_tenant_verified_opportunity(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_account_a,
    leadmanagement_account_b,
    leadmanagement_lead_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_admin_a,
    leadmanagement_currency,
):
    activate_nurture(
        leadmanagement_nurture_enrollment_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    leadmanagement_lead_a.status = "converted"
    leadmanagement_lead_a.save(update_fields=["status", "updated_at"])
    Opportunity.objects.create(
        tenant=leadmanagement_tenant_b,
        account=leadmanagement_account_b,
        name="Foreign source opportunity",
        stage="prospecting",
        amount=Decimal("100.00"),
        owner=leadmanagement_admin_a,
        source_lead=leadmanagement_lead_a,
    )

    refused = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_convert_exit", leadmanagement_nurture_enrollment_a.pk),
        {"exit_reason": "converted"},
    )
    assert refused.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "active"

    opportunity = _leadmanagement_opportunity(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        leadmanagement_account_a,
        currency=leadmanagement_currency,
        owner=leadmanagement_admin_a,
    )
    converted = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_convert_exit", leadmanagement_nurture_enrollment_a.pk),
        {"exit_reason": "converted"},
    )
    assert converted.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "converted"
    assert leadmanagement_nurture_enrollment_a.exit_reason == "converted"
    assert leadmanagement_nurture_enrollment_a.lead_id == leadmanagement_lead_a.pk
    assert opportunity.tenant_id == leadmanagement_tenant_a.pk
    assert opportunity.source_lead_id == leadmanagement_lead_a.pk

    replay = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_convert_exit", leadmanagement_nurture_enrollment_a.pk),
        {"exit_reason": "converted"},
    )
    assert replay.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "converted"


@pytest.mark.parametrize("scope_value", ("own", "team"))
def test_leadmanagement_configured_sales_scope_limits_member_rows_and_actions(
    scope_value,
    leadmanagement_member_client_a,
    leadmanagement_member_a,
    leadmanagement_admin_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_score_event_a,
    leadmanagement_routing_rule_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_currency,
):
    own_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=leadmanagement_member_a,
        name="Member-owned scoped lead",
        email="member-scoped@example.com",
    )
    own_score = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        own_lead,
        recorded_by=leadmanagement_member_a,
    )
    own_qualification = _leadmanagement_qualification(
        leadmanagement_tenant_a,
        own_lead,
        leadmanagement_currency,
        assessed_by=leadmanagement_member_a,
    )
    own_enrollment = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        own_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
        owner=leadmanagement_member_a,
    )
    ModuleAccessScope.objects.create(
        tenant=leadmanagement_tenant_a,
        module_number="8",
        module_slug="sales",
        module_title="Sales",
        is_enabled=True,
        data_scope=scope_value,
    )

    overview = leadmanagement_member_client_a.get(_leadmanagement_url("lead_overview"))
    assert overview.status_code == 200
    assert overview.context["stats"]["total_leads"] == 1
    assert [row.pk for row in overview.context["leads"]] == [own_lead.pk]
    assert leadmanagement_lead_a.name not in overview.content.decode()

    for route, expected in (
        ("lead_score_event_list", own_score.pk),
        ("lead_qualification_list", own_qualification.pk),
        ("lead_nurture_enrollment_list", own_enrollment.pk),
    ):
        response = leadmanagement_member_client_a.get(_leadmanagement_url(route))
        assert response.status_code == 200, route
        assert [row.pk for row in response.context["object_list"]] == [expected], route

    for route, row in (
        ("lead_score_event_detail", leadmanagement_score_event_a),
        ("lead_qualification_detail", leadmanagement_qualification_a),
        ("lead_qualification_edit", leadmanagement_qualification_a),
        ("lead_qualification_route_preview", leadmanagement_qualification_a),
        ("lead_nurture_enrollment_detail", leadmanagement_nurture_enrollment_a),
        ("lead_nurture_enrollment_edit", leadmanagement_nurture_enrollment_a),
    ):
        assert leadmanagement_member_client_a.get(
            _leadmanagement_url(route, row.pk)
        ).status_code == 404, route

    for route, row, payload in (
        ("lead_qualification_partial", leadmanagement_qualification_a, {"status": "partially_qualified"}),
        ("lead_qualification_recalculate", leadmanagement_qualification_a, {}),
        ("lead_nurture_enrollment_pause", leadmanagement_nurture_enrollment_a, {}),
        ("lead_nurture_enrollment_delete", leadmanagement_nurture_enrollment_a, {}),
    ):
        assert leadmanagement_member_client_a.post(
            _leadmanagement_url(route, row.pk),
            payload,
        ).status_code == 404, route

    own_partial = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_qualification_partial", own_qualification.pk),
        {"status": "partially_qualified"},
    )
    assert own_partial.status_code == 302
    own_qualification.refresh_from_db()
    assert own_qualification.status == "partially_qualified"
    assert leadmanagement_routing_rule_a.tenant_id == leadmanagement_tenant_a.pk
    assert leadmanagement_admin_a.is_tenant_admin is True


def test_leadmanagement_admin_relation_querysets_and_lifecycle_readonly_controls_are_enforced(
    request,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_territory_b,
    leadmanagement_score_event_a,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
):
    site = django_admin.AdminSite()
    routing_admin = LeadRoutingRuleAdmin(LeadRoutingRule, site)
    qualification_admin = LeadQualificationAdmin(LeadQualification, site)
    nurture_admin = LeadNurtureEnrollmentAdmin(LeadNurtureEnrollment, site)
    score_admin = LeadScoreEventAdmin(LeadScoreEvent, site)
    admin_request = _leadmanagement_admin_request(leadmanagement_admin_a, leadmanagement_tenant_a)

    owner_field = LeadRoutingRule._meta.get_field("default_owner")
    owner_formfield = routing_admin.formfield_for_foreignkey(owner_field, admin_request)
    assert leadmanagement_admin_a in owner_formfield.queryset
    assert leadmanagement_admin_b not in owner_formfield.queryset

    territory_field = LeadRoutingRule._meta.get_field("territory")
    territory_formfield = routing_admin.formfield_for_foreignkey(territory_field, admin_request)
    assert leadmanagement_territory_b not in territory_formfield.queryset

    eligible_field = LeadRoutingRule._meta.get_field("eligible_owners")
    eligible_formfield = routing_admin.formfield_for_manytomany(eligible_field, admin_request)
    assert leadmanagement_admin_a in eligible_formfield.queryset
    assert leadmanagement_admin_b not in eligible_formfield.queryset

    assert score_admin.has_add_permission(admin_request) is False
    assert score_admin.has_change_permission(admin_request, leadmanagement_score_event_a) is False
    assert score_admin.has_delete_permission(admin_request, leadmanagement_score_event_a) is False

    qualification = leadmanagement_qualification_a
    qualification.status = "archived"
    qualification_fields = qualification_admin.get_readonly_fields(admin_request, qualification)
    assert set(qualification_admin.assessment_fields).issubset(set(qualification_fields))

    enrollment = leadmanagement_nurture_enrollment_a
    enrollment.status = "active"
    enrollment_fields = nurture_admin.get_readonly_fields(admin_request, enrollment)
    assert set(nurture_admin.identity_fields).issubset(set(enrollment_fields))
    assert request is not None
