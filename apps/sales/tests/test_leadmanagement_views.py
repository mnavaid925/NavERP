import json
from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.sales.models import LeadNurtureEnrollment, LeadQualification, LeadRoutingRule, LeadScoreEvent
from apps.sales.tests.conftest import (
    LEADMANAGEMENT_PAGE_SIZE,
    _leadmanagement_account,
    _leadmanagement_campaign,
    _leadmanagement_consent_purpose,
    _leadmanagement_email_campaign,
    _leadmanagement_lead,
    _leadmanagement_nurture_enrollment,
    _leadmanagement_opportunity,
    _leadmanagement_qualification,
    _leadmanagement_routing_rule,
)

pytestmark = pytest.mark.django_db


_LEADMANAGEMENT_POST_ONLY_ROUTES = (
    ("lead_handoff", True),
    ("lead_score_event_adjust", False),
    ("lead_score_event_recompute", False),
    ("lead_score_event_correct", True),
    ("lead_qualification_delete", True),
    ("lead_qualification_partial", True),
    ("lead_qualification_qualify", True),
    ("lead_qualification_disqualify", True),
    ("lead_qualification_archive", True),
    ("lead_qualification_recalculate", True),
    ("lead_routing_rule_delete", True),
    ("lead_routing_rule_toggle", True),
    ("lead_routing_rule_run", True),
    ("lead_nurture_enrollment_delete", True),
    ("lead_nurture_enrollment_activate", True),
    ("lead_nurture_enrollment_pause", True),
    ("lead_nurture_enrollment_resume", True),
    ("lead_nurture_enrollment_complete", True),
    ("lead_nurture_enrollment_cancel", True),
    ("lead_nurture_enrollment_reply", True),
    ("lead_nurture_enrollment_convert_exit", True),
)


def _leadmanagement_url(name, pk=None):
    kwargs = {"pk": pk} if pk is not None else {}
    return reverse(f"sales:{name}", kwargs=kwargs)


def _leadmanagement_templates(response):
    return [template.name for template in response.templates if template.name]


def _leadmanagement_body(response):
    return response.content.decode()


def _leadmanagement_messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _leadmanagement_said(response, fragment):
    return any(fragment in message for message in _leadmanagement_messages(response))


def _leadmanagement_pks(response, key="object_list"):
    return [row.pk for row in response.context[key]]


def _leadmanagement_date(offset=0):
    return (timezone.localdate() + timedelta(days=offset)).isoformat()


def _leadmanagement_datetime_value(moment=None):
    moment = moment or timezone.now() + timedelta(days=3)
    return timezone.localtime(moment).strftime("%Y-%m-%dT%H:%M")


def _leadmanagement_score_event_row(
    tenant,
    lead,
    event_type,
    signal_category,
    source_kind,
    score_delta,
    reason,
    occurred_at,
    source_ref=None,
):
    event = LeadScoreEvent(
        tenant=tenant,
        lead=lead,
        event_type=event_type,
        signal_category=signal_category,
        source_kind=source_kind,
        score_delta=score_delta,
        reason=reason,
        source_ref=source_ref or f"leadmanagement-view:{event_type}",
        occurred_at=occurred_at,
    )
    event.full_clean()
    event.save()
    return event


def _leadmanagement_alt_lead(tenant, owner, token, **overrides):
    fields = {
        "name": f"{token} Lead",
        "company": f"{token} Industries",
        "email": f"{token.lower()}@acme.example",
    }
    fields.update(overrides)
    return _leadmanagement_lead(tenant, owner=owner, **fields)


def _leadmanagement_alt_campaign(tenant, owner, token, **overrides):
    fields = {
        "name": f"{token} Campaign",
        "description": f"{token} campaign for Sales view tests.",
    }
    fields.update(overrides)
    return _leadmanagement_campaign(tenant, owner=owner, **fields)


def _leadmanagement_alt_email_campaign(tenant, campaign, owner, token, **overrides):
    fields = {"name": f"{token} Drip Campaign"}
    fields.update(overrides)
    return _leadmanagement_email_campaign(tenant, campaign, owner=owner, **fields)


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
        "need_summary": "Replace fragmented lead intake.",
        "expected_purchase_on": _leadmanagement_date(45),
        "economic_buyer": "Operations Director",
        "decision_criteria": "Time to value and adoption.",
        "decision_process": "Director review and finance approval.",
        "technical_requirements": "CRM integration and role-based access.",
        "pain_points": "Slow routing and inconsistent evidence.",
        "success_metrics": "Reduce response time and improve conversion.",
        "next_review_on": _leadmanagement_date(14),
        "notes": "Qualification payload from the Sales view tests.",
    }
    data.update(overrides)
    return data


def _leadmanagement_routing_payload(
    owner=None,
    territory=None,
    name="View routing rule",
    assignment_mode="fixed_owner",
    eligible_owners=(),
    conditions=None,
    **overrides,
):
    data = {
        "name": name,
        "description": "Routing payload from the Sales view tests.",
        "is_active": "on",
        "priority": "10",
        "match_mode": "all",
        "conditions": json.dumps(
            conditions if conditions is not None else [{"field": "status", "operator": "eq", "value": "new"}]
        ),
        "is_catch_all": "",
        "assignment_mode": assignment_mode,
        "default_owner": str(owner.pk) if owner is not None else "",
        "territory": str(territory.pk) if territory is not None else "",
        "eligible_owners": [str(eligible.pk) for eligible in eligible_owners],
        "fallback_owner": "",
        "max_open_leads": "25",
    }
    data.update(overrides)
    return data


def _leadmanagement_nurture_payload(lead, email_campaign, consent_purpose, owner=None, **overrides):
    data = {
        "lead": str(lead.pk),
        "email_campaign": str(email_campaign.pk),
        "trigger_kind": "manual",
        "consent_purpose": str(consent_purpose.pk) if consent_purpose is not None else "",
        "consent_evidence": "Consent reference captured by the Sales view test.",
        "owner": str(owner.pk) if owner is not None else "",
        "notes": "Nurture payload from the Sales view tests.",
    }
    data.update(overrides)
    return data


def _leadmanagement_qualification_case(tenant, owner, currency, token, **overrides):
    lead = _leadmanagement_alt_lead(tenant, owner, token)
    fields = {"assessed_by": None}
    fields.update(overrides)
    return _leadmanagement_qualification(tenant, lead, currency, **fields)


def _leadmanagement_bulk_score_events(tenant, lead, count=15):
    now = timezone.now()
    rows = []
    for index in range(count):
        rows.append(
            _leadmanagement_score_event_row(
                tenant,
                lead,
                event_type="email_open",
                signal_category="behavioral",
                source_kind="campaign_member",
                score_delta=2,
                reason=f"Bulk score event {index}.",
                occurred_at=now - timedelta(minutes=index + 1),
                source_ref=f"bulk-score-{index}",
            )
        )
    return rows


def _leadmanagement_bulk_qualifications(tenant, owner, currency, count=15):
    rows = []
    for index in range(count):
        rows.append(
            _leadmanagement_qualification_case(
                tenant,
                owner,
                currency,
                f"Qualification Bulk {index:02d}",
            )
        )
    return rows


def _leadmanagement_bulk_rules(tenant, owner, count=15):
    rows = []
    for index in range(count):
        rows.append(
            _leadmanagement_routing_rule(
                tenant,
                default_owner=owner,
                name=f"Bulk routing rule {index:02d}",
                conditions=[],
                is_catch_all=True,
                priority=100 + index,
            )
        )
    return rows


def _leadmanagement_bulk_enrollments(tenant, owner, email_campaign, consent_purpose, count=15):
    rows = []
    for index in range(count):
        lead = _leadmanagement_alt_lead(tenant, owner, f"Nurture Bulk {index:02d}")
        rows.append(
            _leadmanagement_nurture_enrollment(
                tenant,
                lead,
                email_campaign,
                consent_purpose,
                owner=owner,
            )
        )
    return rows


def _leadmanagement_set_qualified(qualification, tenant, admin, notes="Qualified for the view test."):
    from apps.sales.services import apply_qualification_decision

    return apply_qualification_decision(
        qualification,
        tenant,
        admin,
        status="qualified",
        notes=notes,
    )


def test_leadmanagement_root_and_overview_render_contracted_content(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_score_event_a,
    leadmanagement_admin_a,
):
    from apps.core.models import ContactMethod

    duplicate_party = _leadmanagement_account(
        leadmanagement_tenant_a,
        name="Existing Party matching the lead",
    )
    ContactMethod.objects.create(
        tenant=leadmanagement_tenant_a,
        party=duplicate_party,
        kind="email",
        value=leadmanagement_lead_a.email,
    )

    root = leadmanagement_admin_client_a.get(_leadmanagement_url("sales_root"))
    assert root.status_code == 200
    assert "Lead Operations" in _leadmanagement_body(root)
    assert root.context["stats"]["total_leads"] == 1

    response = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_overview"))
    assert response.status_code == 200
    assert "sales/overview.html" in _leadmanagement_templates(response)
    assert 'id="handoff"' in _leadmanagement_body(response)
    assert leadmanagement_lead_a.number in _leadmanagement_body(response)
    assert leadmanagement_lead_b.name not in _leadmanagement_body(response)
    assert leadmanagement_lead_b.email not in _leadmanagement_body(response)
    assert leadmanagement_routing_rule_a.name in _leadmanagement_body(response)
    assert leadmanagement_nurture_enrollment_a.get_status_display() in _leadmanagement_body(response)
    assert "Form Submitted" in _leadmanagement_body(response)
    assert "Existing Party matching the lead" in _leadmanagement_body(response)
    assert response.context["stats"]["total_leads"] == 1
    assert response.context["stats"]["routing_rule_count"] == 1
    assert response.context["stats"]["active_nurture"] == 0
    assert response.context["enrollment_labels"][leadmanagement_lead_a.pk] == "Pending"
    assert response.context["duplicate_warnings"][0]["party_name"] == duplicate_party.name
    assert leadmanagement_qualification_a.pk in [row.pk for row in response.context["qualifications"]]
    assert leadmanagement_score_event_a.pk in [row.pk for row in response.context["latest_score_events"]]
    assert response.context["leads"][0].owner_id == leadmanagement_admin_a.pk


def test_leadmanagement_score_list_renders_content_and_all_valid_filters(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
    leadmanagement_admin_a,
):
    today = timezone.localdate()
    yesterday = timezone.now() - timedelta(days=1)
    alternate_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Score Filter")
    fit_event = _leadmanagement_score_event_row(
        leadmanagement_tenant_a,
        alternate_lead,
        event_type="fit_match",
        signal_category="qualification",
        source_kind="qualification",
        score_delta=20,
        reason="Qualification fit signal for the filter test.",
        occurred_at=yesterday,
        source_ref="score-filter-fit",
    )
    web_event = _leadmanagement_score_event_row(
        leadmanagement_tenant_a,
        alternate_lead,
        event_type="web_visit",
        signal_category="behavioral",
        source_kind="api",
        score_delta=1,
        reason="API web visit for the filter test.",
        occurred_at=yesterday,
        source_ref="score-filter-web",
    )
    expected_rows = {
        leadmanagement_score_event_a.pk,
        fit_event.pk,
        web_event.pk,
    }

    response = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_score_event_list"))
    assert response.status_code == 200
    assert "sales/leadmanagement/leadscoreevent/list.html" in _leadmanagement_templates(response)
    assert response.context["page_obj"].paginator.per_page == LEADMANAGEMENT_PAGE_SIZE
    assert response.context["signal_category_choices"] == LeadScoreEvent.SIGNAL_CATEGORY_CHOICES
    assert response.context["event_type_choices"] == LeadScoreEvent.EVENT_TYPE_CHOICES
    assert response.context["source_kind_choices"] == LeadScoreEvent.SOURCE_KIND_CHOICES
    assert leadmanagement_lead_a in list(response.context["leads"])
    assert leadmanagement_score_event_a.lead.number in _leadmanagement_body(response)
    assert leadmanagement_score_event_a.reason in _leadmanagement_body(response)
    assert "{#" not in _leadmanagement_body(response)
    assert "{% comment" not in _leadmanagement_body(response)

    valid_cases = (
        ({"signal_category": "qualification"}, {fit_event.pk}),
        ({"event_type": "fit_match"}, {fit_event.pk}),
        ({"source_kind": "api"}, {web_event.pk}),
        ({"lead": str(alternate_lead.pk)}, {fit_event.pk, web_event.pk}),
        ({"date_from": today.isoformat()}, {leadmanagement_score_event_a.pk}),
        ({"date_to": (today - timedelta(days=1)).isoformat()}, {fit_event.pk, web_event.pk}),
        ({"q": "filter test"}, {fit_event.pk, web_event.pk}),
    )
    for params, expected in valid_cases:
        filtered = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_score_event_list"), params)
        assert filtered.status_code == 200, params
        assert set(_leadmanagement_pks(filtered)) == expected, params

    for params in (
        {"signal_category": "not-a-signal", "event_type": "not-an-event", "source_kind": "not-a-source", "lead": "abc"},
        {"lead": "0"},
        {"lead": "999999999999999999999"},
        {"date_from": "not-a-date", "date_to": "also-not-a-date"},
    ):
        junk = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_score_event_list"), params)
        assert junk.status_code == 200, params
        assert set(_leadmanagement_pks(junk)) == expected_rows, params


def test_leadmanagement_score_list_paginates_at_the_contracted_page_size(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
):
    _leadmanagement_bulk_score_events(leadmanagement_tenant_a, leadmanagement_lead_a, 15)
    first = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_score_event_list"))
    assert first.status_code == 200
    assert len(_leadmanagement_pks(first)) == LEADMANAGEMENT_PAGE_SIZE
    assert first.context["page_obj"].has_next() is True

    second = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_score_event_list"), {"page": "2"})
    assert second.status_code == 200
    assert len(_leadmanagement_pks(second)) == 1
    assert second.context["page_obj"].number == 2
    assert not set(_leadmanagement_pks(first)).intersection(_leadmanagement_pks(second))
    assert leadmanagement_score_event_a.pk in _leadmanagement_pks(first) or leadmanagement_score_event_a.pk in _leadmanagement_pks(second)


def test_leadmanagement_score_detail_renders_projection_and_correction_controls(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
):
    response = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_score_event_detail", leadmanagement_score_event_a.pk)
    )
    assert response.status_code == 200
    assert "sales/leadmanagement/leadscoreevent/detail.html" in _leadmanagement_templates(response)
    assert response.context["obj"].pk == leadmanagement_score_event_a.pk
    assert response.context["lead"].pk == leadmanagement_lead_a.pk
    assert response.context["projection_score"] == 5
    assert response.context["projection_rating"] == "cold"
    assert response.context["can_correct"] is True
    body = _leadmanagement_body(response)
    assert leadmanagement_lead_a.number in body
    assert leadmanagement_score_event_a.reason in body
    assert "Current projection" in body
    assert "Record correction" in body


def test_leadmanagement_score_adjust_recompute_and_correction_write_projection_rows(
    leadmanagement_admin_client_a,
    leadmanagement_member_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
    leadmanagement_admin_a,
):
    adjust_url = _leadmanagement_url("lead_score_event_adjust")
    correction_url = _leadmanagement_url("lead_score_event_correct", leadmanagement_score_event_a.pk)
    recompute_url = _leadmanagement_url("lead_score_event_recompute")

    member_adjust = leadmanagement_member_client_a.post(
        adjust_url,
        {"lead": leadmanagement_lead_a.pk, "score_delta": "5", "reason": "Member must not write."},
    )
    assert member_adjust.status_code == 403
    assert not LeadScoreEvent.objects.filter(event_type="manual_adjustment").exists()

    adjusted = leadmanagement_admin_client_a.post(
        adjust_url,
        {"lead": leadmanagement_lead_a.pk, "score_delta": "7", "reason": "Sales view adjustment."},
    )
    assert adjusted.status_code == 302
    assert _leadmanagement_said(adjusted, "Manual score adjustment recorded")
    assert LeadScoreEvent.objects.filter(event_type="manual_adjustment").count() == 1
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.score == 12

    before_invalid = LeadScoreEvent.objects.count()
    invalid_adjust = leadmanagement_admin_client_a.post(
        adjust_url,
        {"lead": leadmanagement_lead_a.pk, "score_delta": "101", "reason": "Out of range."},
    )
    assert invalid_adjust.status_code == 302
    assert LeadScoreEvent.objects.count() == before_invalid
    assert _leadmanagement_said(invalid_adjust, "could not be recorded")

    corrected = leadmanagement_admin_client_a.post(
        correction_url,
        {
            "lead": leadmanagement_lead_a.pk,
            "corrects_event": leadmanagement_score_event_a.pk,
            "score_delta": "-5",
            "reason": "Reverse the original view-test event.",
        },
    )
    assert corrected.status_code == 302
    assert corrected["Location"] == _leadmanagement_url("lead_score_event_detail", leadmanagement_score_event_a.pk)
    assert LeadScoreEvent.objects.filter(corrects_event=leadmanagement_score_event_a).count() == 1
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.score == 7

    before_invalid_correction = LeadScoreEvent.objects.count()
    invalid_correction = leadmanagement_admin_client_a.post(
        correction_url,
        {
            "lead": leadmanagement_lead_a.pk,
            "corrects_event": leadmanagement_score_event_a.pk,
            "score_delta": "-4",
            "reason": "Wrong inverse delta.",
        },
    )
    assert invalid_correction.status_code == 302
    assert LeadScoreEvent.objects.count() == before_invalid_correction

    leadmanagement_lead_a.score = 0
    leadmanagement_lead_a.rating = "hot"
    leadmanagement_lead_a.save(update_fields=["score", "rating", "updated_at"])
    recomputed = leadmanagement_admin_client_a.post(recompute_url, {"lead_id": leadmanagement_lead_a.pk})
    assert recomputed.status_code == 302
    assert _leadmanagement_said(recomputed, "Score projection refreshed")
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.score == 7
    assert leadmanagement_lead_a.rating == "cold"

    for invalid_lead_id in ("abc", "0", "999999999999999999999"):
        junk = leadmanagement_admin_client_a.post(recompute_url, {"lead_id": invalid_lead_id})
        assert junk.status_code == 302
        assert _leadmanagement_said(junk, "Choose a valid lead")
    member_recompute = leadmanagement_member_client_a.post(recompute_url, {"lead_id": leadmanagement_lead_a.pk})
    assert member_recompute.status_code == 403


def test_leadmanagement_score_actions_reject_get_requests(
    leadmanagement_admin_client_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
):
    for name, requires_pk in (
        ("lead_handoff", True),
        ("lead_score_event_adjust", False),
        ("lead_score_event_recompute", False),
        ("lead_score_event_correct", True),
    ):
        pk = None
        if requires_pk:
            pk = leadmanagement_lead_a.pk if name == "lead_handoff" else leadmanagement_score_event_a.pk
        response = leadmanagement_admin_client_a.get(_leadmanagement_url(name, pk))
        assert response.status_code == 405, name


def test_leadmanagement_qualification_list_renders_content_and_all_valid_filters(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_member_a,
    leadmanagement_currency,
    leadmanagement_qualification_a,
):
    today = timezone.localdate()
    qualified = _leadmanagement_qualification_case(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        leadmanagement_currency,
        "Qualified filter",
        status="qualified",
        assessed_by=leadmanagement_admin_a,
        country_code="CA",
        region="West",
        city="Vancouver",
        seniority="executive",
        budget_status="adequate",
        authority_level="executive",
        next_review_on=today + timedelta(days=1),
    )
    partial = _leadmanagement_qualification_case(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        leadmanagement_currency,
        "Partial filter",
        framework="meddic",
        status="partially_qualified",
        assessed_by=leadmanagement_admin_a,
        country_code="GB",
        region="South",
        city="London",
        seniority="manager",
        budget_status="insufficient",
        authority_level="manager",
        next_review_on=today + timedelta(days=7),
    )
    disqualified = _leadmanagement_qualification_case(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        leadmanagement_currency,
        "Disqualified filter",
        status="disqualified",
        assessed_by=leadmanagement_admin_a,
        disqualification_reason="No viable budget.",
        country_code="AU",
        next_review_on=today - timedelta(days=1),
    )
    archived = _leadmanagement_qualification_case(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        leadmanagement_currency,
        "Archived filter",
        status="archived",
        assessed_by=leadmanagement_admin_a,
        country_code="DE",
        next_review_on=today + timedelta(days=30),
    )

    response = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_qualification_list"))
    assert response.status_code == 200
    assert "sales/leadmanagement/leadqualification/list.html" in _leadmanagement_templates(response)
    assert response.context["page_obj"].paginator.per_page == LEADMANAGEMENT_PAGE_SIZE
    assert response.context["status_choices"] == LeadQualification.STATUS_CHOICES
    assert response.context["framework_choices"] == LeadQualification.FRAMEWORK_CHOICES
    assert response.context["seniority_choices"] == LeadQualification.SENIORITY_CHOICES
    assert response.context["budget_status_choices"] == LeadQualification.BUDGET_STATUS_CHOICES
    assert response.context["authority_level_choices"] == LeadQualification.AUTHORITY_LEVEL_CHOICES
    assert leadmanagement_admin_a in list(response.context["assessors"])
    assert leadmanagement_member_a in list(response.context["assessors"])
    assert leadmanagement_qualification_a.lead.number in _leadmanagement_body(response)
    assert "New assessment" in _leadmanagement_body(response)
    assert "{#" not in _leadmanagement_body(response)

    valid_cases = (
        ({"status": "qualified"}, {qualified.pk}),
        ({"framework": "meddic"}, {partial.pk}),
        ({"country": "GB"}, {partial.pk}),
        ({"region": "South"}, {partial.pk}),
        ({"seniority": "executive"}, {qualified.pk}),
        ({"budget_status": "adequate"}, {qualified.pk}),
        ({"authority_level": "manager"}, {partial.pk}),
        ({"assessor": str(leadmanagement_admin_a.pk)}, {qualified.pk, partial.pk, disqualified.pk, archived.pk}),
        ({"review_due": "overdue"}, {disqualified.pk}),
        ({"review_due": "week"}, {qualified.pk, partial.pk}),
        ({"q": "Disqualified filter"}, {disqualified.pk}),
    )
    for params, expected in valid_cases:
        filtered = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_qualification_list"), params)
        assert filtered.status_code == 200, params
        assert set(_leadmanagement_pks(filtered)) == expected, params

    expected_rows = {
        leadmanagement_qualification_a.pk,
        qualified.pk,
        partial.pk,
        disqualified.pk,
        archived.pk,
    }
    for params in (
        {
            "status": "invalid",
            "framework": "invalid",
            "seniority": "invalid",
            "budget_status": "invalid",
            "authority_level": "invalid",
            "assessor": "abc",
        },
        {"assessor": "0"},
        {"assessor": "999999999999999999999"},
    ):
        junk = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_qualification_list"), params)
        assert junk.status_code == 200, params
        assert set(_leadmanagement_pks(junk)) == expected_rows, params


def test_leadmanagement_qualification_list_paginates_at_the_contracted_page_size(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_currency,
    leadmanagement_qualification_a,
):
    _leadmanagement_bulk_qualifications(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        leadmanagement_currency,
        15,
    )
    first = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_qualification_list"))
    assert first.status_code == 200
    assert len(_leadmanagement_pks(first)) == LEADMANAGEMENT_PAGE_SIZE
    assert first.context["page_obj"].has_next() is True

    second = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_qualification_list"), {"page": "2"})
    assert second.status_code == 200
    assert len(_leadmanagement_pks(second)) == 1
    assert second.context["page_obj"].number == 2
    assert not set(_leadmanagement_pks(first)).intersection(_leadmanagement_pks(second))


def test_leadmanagement_qualification_detail_renders_evidence_and_route_preview(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_score_event_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_routing_rule_a,
):
    response = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_qualification_detail", leadmanagement_qualification_a.pk)
    )
    assert response.status_code == 200
    assert "sales/leadmanagement/leadqualification/detail.html" in _leadmanagement_templates(response)
    assert response.context["obj"].pk == leadmanagement_qualification_a.pk
    assert response.context["lead"].pk == leadmanagement_lead_a.pk
    assert leadmanagement_score_event_a.pk in [row.pk for row in response.context["score_events"]]
    assert leadmanagement_nurture_enrollment_a.pk in [row.pk for row in response.context["enrollments"]]
    body = _leadmanagement_body(response)
    assert leadmanagement_lead_a.number in body
    assert leadmanagement_qualification_a.city in body
    assert leadmanagement_qualification_a.need_summary in body
    assert leadmanagement_score_event_a.reason in body
    assert leadmanagement_nurture_enrollment_a.number in body
    assert "Qualification decision" in body
    assert "Routing preview" in body

    preview = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_qualification_route_preview", leadmanagement_qualification_a.pk),
        {"lead": leadmanagement_lead_a.pk},
    )
    assert preview.status_code == 200
    assert preview.context["routing_preview"]["matched"] is True
    assert preview.context["routing_preview"]["rule"].pk == leadmanagement_routing_rule_a.pk
    assert preview.context["routing_preview"]["owner"].pk == leadmanagement_routing_rule_a.default_owner_id
    assert leadmanagement_routing_rule_a.name in _leadmanagement_body(preview)
    assert "Rule matched this lead." in _leadmanagement_body(preview)

    junk_preview = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_qualification_route_preview", leadmanagement_qualification_a.pk),
        {"lead": "not-a-lead"},
    )
    assert junk_preview.status_code == 200
    assert junk_preview.context["routing_preview"] is None


def test_leadmanagement_qualification_create_edit_and_delete_round_trip(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_currency,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
):
    create = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_qualification_create"))
    assert create.status_code == 200
    assert "sales/leadmanagement/leadqualification/form.html" in _leadmanagement_templates(create)
    assert create.context["is_edit"] is False
    assert "form" in create.context
    assert leadmanagement_lead_a.pk in [lead.pk for lead in create.context["leads"]]

    new_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Created qualification")
    created = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_create"),
        _leadmanagement_qualification_payload(new_lead, leadmanagement_currency, notes="Created through the view."),
    )
    assert created.status_code == 302
    created_row = LeadQualification.objects.get(lead=new_lead)
    assert created_row.tenant_id == leadmanagement_tenant_a.pk
    assert created_row.status == "unassessed"
    assert created_row.notes == "Created through the view."

    before_invalid = LeadQualification.objects.count()
    invalid_payload = _leadmanagement_qualification_payload(
        new_lead,
        leadmanagement_currency,
    )
    invalid_payload["lead"] = ""
    invalid_payload["country_code"] = "USA"
    invalid = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_create"),
        invalid_payload,
    )
    assert invalid.status_code == 200
    assert "form" in invalid.context
    assert LeadQualification.objects.count() == before_invalid

    edit = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_qualification_edit", leadmanagement_qualification_a.pk)
    )
    assert edit.status_code == 200
    assert edit.context["is_edit"] is True
    assert edit.context["obj"].pk == leadmanagement_qualification_a.pk
    assert "Edit Qualification" in _leadmanagement_body(edit)

    updated = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_edit", leadmanagement_qualification_a.pk),
        _leadmanagement_qualification_payload(
            leadmanagement_lead_a,
            leadmanagement_currency,
            framework="meddic",
            notes="Updated through the edit view.",
        ),
    )
    assert updated.status_code == 302
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.framework == "meddic"
    assert leadmanagement_qualification_a.notes == "Updated through the edit view."

    deletable_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Deletable qualification")
    deletable = _leadmanagement_qualification(
        leadmanagement_tenant_a,
        deletable_lead,
        leadmanagement_currency,
    )
    deleted = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_delete", deletable.pk)
    )
    assert deleted.status_code == 302
    assert not LeadQualification.objects.filter(pk=deletable.pk).exists()


def test_leadmanagement_qualification_lifecycle_transitions_recalculate_and_recalculate_projection(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_qualification_a,
    leadmanagement_lead_a,
    leadmanagement_routing_rule_a,
):
    catch_all = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        default_owner=leadmanagement_admin_a,
        name="Qualification catch all",
        conditions=[],
        is_catch_all=True,
    )
    partial = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_partial", leadmanagement_qualification_a.pk),
        {"status": "partially_qualified", "notes": "Partially qualified through the view."},
    )
    assert partial.status_code == 302
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "partially_qualified"
    assert leadmanagement_qualification_a.notes == "Partially qualified through the view."

    wrong_transition = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_partial", leadmanagement_qualification_a.pk),
        {"status": "qualified"},
    )
    assert wrong_transition.status_code == 302
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "partially_qualified"

    qualified = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_qualify", leadmanagement_qualification_a.pk),
        {"status": "qualified", "notes": "Qualified through the view."},
    )
    assert qualified.status_code == 302
    leadmanagement_qualification_a.refresh_from_db()
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "qualified"
    assert leadmanagement_qualification_a.assessed_by_id == leadmanagement_admin_a.pk
    assert leadmanagement_lead_a.status == "qualified"
    assert LeadScoreEvent.objects.filter(lead=leadmanagement_lead_a, event_type="fit_match").exists()
    catch_all.refresh_from_db()
    assert catch_all.last_assigned_owner_id == leadmanagement_admin_a.pk

    leadmanagement_lead_a.score = 0
    leadmanagement_lead_a.rating = "hot"
    leadmanagement_lead_a.save(update_fields=["score", "rating", "updated_at"])
    recalculated = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_recalculate", leadmanagement_qualification_a.pk)
    )
    assert recalculated.status_code == 302
    assert _leadmanagement_said(recalculated, "Lead score projection refreshed")
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.score == 20

    disqualified = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_disqualify", leadmanagement_qualification_a.pk),
        {"status": "disqualified", "disqualification_reason": "No viable buying budget."},
    )
    assert disqualified.status_code == 302
    leadmanagement_qualification_a.refresh_from_db()
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "disqualified"
    assert leadmanagement_lead_a.status == "unqualified"
    assert LeadScoreEvent.objects.filter(lead=leadmanagement_lead_a, event_type="fit_mismatch").exists()

    archived = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_qualification_archive", leadmanagement_qualification_a.pk),
        {"status": "archived"},
    )
    assert archived.status_code == 302
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "archived"


def test_leadmanagement_qualification_admin_member_controls_and_get_guards(
    leadmanagement_admin_client_a,
    leadmanagement_member_client_a,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
):
    admin_detail = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_qualification_detail", leadmanagement_qualification_a.pk)
    )
    member_detail = leadmanagement_member_client_a.get(
        _leadmanagement_url("lead_qualification_detail", leadmanagement_qualification_a.pk)
    )
    assert admin_detail.status_code == 200
    assert member_detail.status_code == 200
    assert "Archive" in _leadmanagement_body(admin_detail)
    assert 'action="/sales/qualifications/{}/archive/"'.format(leadmanagement_qualification_a.pk) in _leadmanagement_body(admin_detail)
    assert 'action="/sales/qualifications/{}/archive/"'.format(leadmanagement_qualification_a.pk) not in _leadmanagement_body(member_detail)

    before_status = leadmanagement_qualification_a.status
    member_archive = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_qualification_archive", leadmanagement_qualification_a.pk),
        {"status": "archived"},
    )
    assert member_archive.status_code == 403
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == before_status

    member_routing_create = leadmanagement_member_client_a.get(_leadmanagement_url("lead_routing_rule_create"))
    assert member_routing_create.status_code == 403
    member_nurture_create = leadmanagement_member_client_a.get(_leadmanagement_url("lead_nurture_enrollment_create"))
    assert member_nurture_create.status_code == 200
    member_nurture_detail = leadmanagement_member_client_a.get(
        _leadmanagement_url("lead_nurture_enrollment_detail", leadmanagement_nurture_enrollment_a.pk)
    )
    assert member_nurture_detail.status_code == 200
    assert _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk) not in _leadmanagement_body(member_nurture_detail)

    for name, pk in (
        ("lead_qualification_delete", leadmanagement_qualification_a.pk),
        ("lead_qualification_partial", leadmanagement_qualification_a.pk),
        ("lead_qualification_qualify", leadmanagement_qualification_a.pk),
        ("lead_qualification_disqualify", leadmanagement_qualification_a.pk),
        ("lead_qualification_archive", leadmanagement_qualification_a.pk),
        ("lead_qualification_recalculate", leadmanagement_qualification_a.pk),
        ("lead_routing_rule_delete", leadmanagement_routing_rule_a.pk),
        ("lead_routing_rule_toggle", leadmanagement_routing_rule_a.pk),
        ("lead_routing_rule_run", leadmanagement_routing_rule_a.pk),
        ("lead_nurture_enrollment_delete", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_pause", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_resume", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_complete", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_cancel", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_reply", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_convert_exit", leadmanagement_nurture_enrollment_a.pk),
    ):
        response = leadmanagement_admin_client_a.get(_leadmanagement_url(name, pk))
        assert response.status_code == 405, name

    member_actions = (
        ("lead_handoff", leadmanagement_lead_a.pk),
        ("lead_score_event_adjust", None),
        ("lead_score_event_recompute", None),
        ("lead_score_event_correct", leadmanagement_score_event_a.pk),
        ("lead_qualification_archive", leadmanagement_qualification_a.pk),
        ("lead_routing_rule_create", None),
        ("lead_routing_rule_edit", leadmanagement_routing_rule_a.pk),
        ("lead_routing_rule_delete", leadmanagement_routing_rule_a.pk),
        ("lead_routing_rule_toggle", leadmanagement_routing_rule_a.pk),
        ("lead_routing_rule_run", leadmanagement_routing_rule_a.pk),
        ("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_resume", leadmanagement_nurture_enrollment_a.pk),
        ("lead_nurture_enrollment_convert_exit", leadmanagement_nurture_enrollment_a.pk),
    )
    for name, pk in member_actions:
        response = leadmanagement_member_client_a.post(_leadmanagement_url(name, pk), {})
        assert response.status_code == 403, name


def test_leadmanagement_routing_list_renders_content_and_all_valid_filters(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_member_a,
    leadmanagement_territory_a,
    leadmanagement_routing_rule_a,
):
    inactive = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        default_owner=leadmanagement_admin_a,
        name="Inactive routing filter",
        is_active=False,
        priority=20,
    )
    round_robin = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        name="Round robin filter",
        assignment_mode="round_robin",
        eligible_owners=(leadmanagement_member_a,),
        conditions=[{"field": "company", "operator": "icontains", "value": "Industries"}],
        match_mode="any",
        priority=20,
    )
    territory_rule = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        territory=leadmanagement_territory_a,
        name="Territory filter",
        assignment_mode="territory_manager",
        conditions=[{"field": "region", "operator": "eq", "value": "North"}],
        priority=30,
    )

    response = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_list"))
    assert response.status_code == 200
    assert "sales/leadmanagement/leadroutingrule/list.html" in _leadmanagement_templates(response)
    assert response.context["page_obj"].paginator.per_page == LEADMANAGEMENT_PAGE_SIZE
    assert response.context["assignment_mode_choices"] == LeadRoutingRule.ASSIGNMENT_MODE_CHOICES
    assert response.context["match_mode_choices"] == LeadRoutingRule.MATCH_MODE_CHOICES
    assert leadmanagement_admin_a in list(response.context["users"])
    assert leadmanagement_territory_a in list(response.context["territories"])
    assert leadmanagement_routing_rule_a.name in _leadmanagement_body(response)
    assert "New rule" in _leadmanagement_body(response)
    assert "{#" not in _leadmanagement_body(response)

    valid_cases = (
        ({"active": "False"}, {inactive.pk}),
        ({"assignment_mode": "round_robin"}, {round_robin.pk}),
        ({"match_mode": "any"}, {round_robin.pk}),
        ({"territory": str(leadmanagement_territory_a.pk)}, {territory_rule.pk}),
        ({"priority": "10"}, {leadmanagement_routing_rule_a.pk}),
        ({"q": "Inactive routing"}, {inactive.pk}),
    )
    for params, expected in valid_cases:
        filtered = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_list"), params)
        assert filtered.status_code == 200, params
        assert set(_leadmanagement_pks(filtered)) == expected, params

    expected_rows = {
        leadmanagement_routing_rule_a.pk,
        inactive.pk,
        round_robin.pk,
        territory_rule.pk,
    }
    for params in (
        {"active": "not-a-boolean", "assignment_mode": "invalid", "match_mode": "invalid", "territory": "abc"},
        {"territory": "0"},
        {"territory": "999999999999999999999"},
    ):
        junk = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_list"), params)
        assert junk.status_code == 200, params
        assert set(_leadmanagement_pks(junk)) == expected_rows, params


def test_leadmanagement_routing_list_paginates_at_the_contracted_page_size(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_routing_rule_a,
):
    _leadmanagement_bulk_rules(leadmanagement_tenant_a, leadmanagement_admin_a, 15)
    first = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_list"))
    assert first.status_code == 200
    assert len(_leadmanagement_pks(first)) == LEADMANAGEMENT_PAGE_SIZE
    assert first.context["page_obj"].has_next() is True

    second = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_list"), {"page": "2"})
    assert second.status_code == 200
    assert len(_leadmanagement_pks(second)) == 1
    assert second.context["page_obj"].number == 2
    assert not set(_leadmanagement_pks(first)).intersection(_leadmanagement_pks(second))


def test_leadmanagement_routing_crud_preview_run_and_toggle_state(
    leadmanagement_admin_client_a,
    leadmanagement_member_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_member_a,
    leadmanagement_lead_a,
    leadmanagement_routing_rule_a,
):
    create = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_create"))
    assert create.status_code == 200
    assert "sales/leadmanagement/leadroutingrule/form.html" in _leadmanagement_templates(create)
    assert create.context["is_edit"] is False
    assert leadmanagement_admin_a in list(create.context["users"])

    new_rule = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_routing_rule_create"),
        _leadmanagement_routing_payload(
            owner=leadmanagement_member_a,
            name="Created by routing view",
            description="Created through the view.",
        ),
    )
    assert new_rule.status_code == 302
    created = LeadRoutingRule.objects.get(name="Created by routing view")
    assert created.tenant_id == leadmanagement_tenant_a.pk
    assert list(created.eligible_owners.all()) == []
    assert created.default_owner_id == leadmanagement_member_a.pk

    edit = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_routing_rule_edit", created.pk)
    )
    assert edit.status_code == 200
    assert edit.context["is_edit"] is True
    assert edit.context["obj"].pk == created.pk
    updated = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_routing_rule_edit", created.pk),
        _leadmanagement_routing_payload(
            owner=leadmanagement_admin_a,
            name=created.name,
            description="Updated through the routing view.",
            priority="22",
        ),
    )
    assert updated.status_code == 302
    created.refresh_from_db()
    assert created.description == "Updated through the routing view."
    assert created.priority == 22

    detail = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_routing_rule_detail", created.pk))
    assert detail.status_code == 200
    assert "sales/leadmanagement/leadroutingrule/detail.html" in _leadmanagement_templates(detail)
    assert created.name in _leadmanagement_body(detail)
    assert '"field": "status"' in detail.context["conditions_json"]
    assert "Preview routing" in _leadmanagement_body(detail)

    preview = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_routing_rule_preview", leadmanagement_routing_rule_a.pk),
        {"lead": leadmanagement_lead_a.pk},
    )
    assert preview.status_code == 200
    assert preview.context["preview_result"]["matched"] is True
    assert preview.context["preview_result"]["rule"].pk == leadmanagement_routing_rule_a.pk
    assert leadmanagement_routing_rule_a.name in _leadmanagement_body(preview)

    run_rule = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        default_owner=leadmanagement_member_a,
        name="Run view rule",
        conditions=[],
        is_catch_all=True,
    )
    before_tasks = 0
    run = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_routing_rule_run", run_rule.pk),
        {"lead": leadmanagement_lead_a.pk},
    )
    assert run.status_code == 302
    leadmanagement_lead_a.refresh_from_db()
    run_rule.refresh_from_db()
    assert leadmanagement_lead_a.owner_id == leadmanagement_member_a.pk
    assert run_rule.last_assigned_owner_id == leadmanagement_member_a.pk
    assert run_rule.last_assigned_at is not None
    from apps.crm.models import CrmTask

    assert CrmTask.objects.filter(subject=f"Follow up {leadmanagement_lead_a.number}").count() == 1
    replay = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_routing_rule_run", run_rule.pk),
        {"lead": leadmanagement_lead_a.pk},
    )
    assert replay.status_code == 302
    assert CrmTask.objects.filter(subject=f"Follow up {leadmanagement_lead_a.number}").count() == 1

    toggled = leadmanagement_admin_client_a.post(_leadmanagement_url("lead_routing_rule_toggle", run_rule.pk))
    assert toggled.status_code == 302
    run_rule.refresh_from_db()
    assert run_rule.is_active is False

    delete_rule = _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        default_owner=leadmanagement_admin_a,
        name="Delete from routing view",
    )
    deleted = leadmanagement_admin_client_a.post(_leadmanagement_url("lead_routing_rule_delete", delete_rule.pk))
    assert deleted.status_code == 302
    assert not LeadRoutingRule.objects.filter(pk=delete_rule.pk).exists()

    member_detail = leadmanagement_member_client_a.get(
        _leadmanagement_url("lead_routing_rule_detail", leadmanagement_routing_rule_a.pk)
    )
    assert member_detail.status_code == 200
    body = _leadmanagement_body(member_detail)
    assert "New rule" not in body
    assert "Run this rule" not in body
    assert "Disable" not in body
    for name, pk in (
        ("lead_routing_rule_create", None),
        ("lead_routing_rule_edit", leadmanagement_routing_rule_a.pk),
    ):
        response = leadmanagement_member_client_a.get(_leadmanagement_url(name, pk))
        assert response.status_code == 403, name
    for name, pk in (
        ("lead_routing_rule_delete", leadmanagement_routing_rule_a.pk),
        ("lead_routing_rule_toggle", leadmanagement_routing_rule_a.pk),
        ("lead_routing_rule_run", leadmanagement_routing_rule_a.pk),
    ):
        response = leadmanagement_member_client_a.post(_leadmanagement_url(name, pk), {})
        assert response.status_code == 403, name
    member_preview = leadmanagement_member_client_a.get(
        _leadmanagement_url("lead_routing_rule_preview", leadmanagement_routing_rule_a.pk),
        {"lead": leadmanagement_lead_a.pk},
    )
    assert member_preview.status_code == 200
    assert "Run this rule" not in _leadmanagement_body(member_preview)


def test_leadmanagement_nurture_list_renders_content_and_all_valid_filters(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_member_a,
    leadmanagement_email_campaign_a,
    leadmanagement_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_nurture_enrollment_a,
):
    active_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Active")
    active = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        active_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
        owner=leadmanagement_admin_a,
        status="active",
        next_touch_at=timezone.now() + timedelta(days=2),
    )
    overdue_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_member_a, "Nurture Overdue")
    overdue = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        overdue_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
        owner=leadmanagement_member_a,
        status="active",
        next_touch_at=timezone.now() - timedelta(days=2),
    )
    second_campaign = _leadmanagement_alt_campaign(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Second")
    second_email_campaign = _leadmanagement_alt_email_campaign(
        leadmanagement_tenant_a,
        second_campaign,
        leadmanagement_admin_a,
        "Nurture Second",
    )
    second_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Campaign")
    second = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        second_lead,
        second_email_campaign,
        leadmanagement_consent_purpose_a,
        owner=leadmanagement_admin_a,
        trigger_kind="score_threshold",
    )

    response = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_nurture_enrollment_list"))
    assert response.status_code == 200
    assert "sales/leadmanagement/leadnurtureenrollment/list.html" in _leadmanagement_templates(response)
    assert response.context["page_obj"].paginator.per_page == LEADMANAGEMENT_PAGE_SIZE
    assert response.context["status_choices"] == LeadNurtureEnrollment.STATUS_CHOICES
    assert response.context["trigger_kind_choices"] == LeadNurtureEnrollment.TRIGGER_KIND_CHOICES
    assert leadmanagement_email_campaign_a in list(response.context["drip_campaigns"])
    assert leadmanagement_admin_a in list(response.context["owners"])
    assert leadmanagement_nurture_enrollment_a.number in _leadmanagement_body(response)
    assert "New enrollment" in _leadmanagement_body(response)
    assert "{#" not in _leadmanagement_body(response)

    valid_cases = (
        ({"status": "active"}, {active.pk, overdue.pk}),
        ({"status": "pending"}, {leadmanagement_nurture_enrollment_a.pk, second.pk}),
        ({"trigger_kind": "score_threshold"}, {second.pk}),
        ({"email_campaign": str(leadmanagement_email_campaign_a.pk)}, {
            leadmanagement_nurture_enrollment_a.pk,
            active.pk,
            overdue.pk,
        }),
        ({"owner": str(leadmanagement_member_a.pk)}, {overdue.pk}),
        ({"next_touch": "overdue"}, {overdue.pk}),
        ({"q": "Nurture Active"}, {active.pk}),
    )
    for params, expected in valid_cases:
        filtered = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_nurture_enrollment_list"), params)
        assert filtered.status_code == 200, params
        assert set(_leadmanagement_pks(filtered)) == expected, params

    expected_rows = {
        leadmanagement_nurture_enrollment_a.pk,
        active.pk,
        overdue.pk,
        second.pk,
    }
    for params in (
        {"status": "invalid", "trigger_kind": "invalid", "email_campaign": "abc", "owner": "abc"},
        {"email_campaign": "0"},
        {"owner": "999999999999999999999"},
    ):
        junk = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_nurture_enrollment_list"), params)
        assert junk.status_code == 200, params
        assert set(_leadmanagement_pks(junk)) == expected_rows, params


def test_leadmanagement_nurture_list_paginates_at_the_contracted_page_size(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_nurture_enrollment_a,
):
    _leadmanagement_bulk_enrollments(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
        15,
    )
    first = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_nurture_enrollment_list"))
    assert first.status_code == 200
    assert len(_leadmanagement_pks(first)) == LEADMANAGEMENT_PAGE_SIZE
    assert first.context["page_obj"].has_next() is True

    second = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_nurture_enrollment_list"), {"page": "2"})
    assert second.status_code == 200
    assert len(_leadmanagement_pks(second)) == 1
    assert second.context["page_obj"].number == 2
    assert not set(_leadmanagement_pks(first)).intersection(_leadmanagement_pks(second))


def test_leadmanagement_nurture_create_edit_detail_and_delete_round_trip(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_nurture_enrollment_a,
):
    create = leadmanagement_admin_client_a.get(_leadmanagement_url("lead_nurture_enrollment_create"))
    assert create.status_code == 200
    assert "sales/leadmanagement/leadnurtureenrollment/form.html" in _leadmanagement_templates(create)
    assert create.context["is_edit"] is False
    assert leadmanagement_email_campaign_a in list(create.context["drip_campaigns"])
    assert leadmanagement_consent_purpose_a in list(create.context["consent_purposes"])
    assert leadmanagement_admin_a in list(create.context["owners"])

    create_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Create")
    created = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_create"),
        _leadmanagement_nurture_payload(
            create_lead,
            leadmanagement_email_campaign_a,
            leadmanagement_consent_purpose_a,
            owner=leadmanagement_admin_a,
            notes="Created through the nurture view.",
        ),
    )
    assert created.status_code == 302
    created_row = LeadNurtureEnrollment.objects.get(lead=create_lead)
    assert created_row.tenant_id == leadmanagement_tenant_a.pk
    assert created_row.status == "pending"
    assert created_row.notes == "Created through the nurture view."

    before_invalid = LeadNurtureEnrollment.objects.count()
    invalid_payload = _leadmanagement_nurture_payload(
        create_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    invalid_payload["lead"] = ""
    invalid = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_create"),
        invalid_payload,
    )
    assert invalid.status_code == 200
    assert LeadNurtureEnrollment.objects.count() == before_invalid

    edit = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_nurture_enrollment_edit", leadmanagement_nurture_enrollment_a.pk)
    )
    assert edit.status_code == 200
    assert edit.context["is_edit"] is True
    assert edit.context["obj"].pk == leadmanagement_nurture_enrollment_a.pk
    updated = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_edit", leadmanagement_nurture_enrollment_a.pk),
        _leadmanagement_nurture_payload(
            leadmanagement_nurture_enrollment_a.lead,
            leadmanagement_email_campaign_a,
            leadmanagement_consent_purpose_a,
            owner=leadmanagement_admin_a,
            notes="Updated through the nurture view.",
        ),
    )
    assert updated.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.notes == "Updated through the nurture view."

    detail = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_nurture_enrollment_detail", leadmanagement_nurture_enrollment_a.pk)
    )
    assert detail.status_code == 200
    assert "sales/leadmanagement/leadnurtureenrollment/detail.html" in _leadmanagement_templates(detail)
    body = _leadmanagement_body(detail)
    assert leadmanagement_nurture_enrollment_a.number in body
    assert leadmanagement_email_campaign_a.name in body
    assert leadmanagement_consent_purpose_a.name in body
    assert "records lifecycle state only" in body
    assert "Consent evidence" in body

    deletable_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Delete")
    deletable = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        deletable_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    deleted = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_delete", deletable.pk)
    )
    assert deleted.status_code == 302
    assert not LeadNurtureEnrollment.objects.filter(pk=deletable.pk).exists()


def test_leadmanagement_nurture_lifecycle_transitions_and_invalid_transitions(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_lead_a,
):
    target = (timezone.now() + timedelta(days=5)).replace(microsecond=0)
    activated = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        {"next_touch_at": _leadmanagement_datetime_value(target)},
    )
    assert activated.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "active"
    assert leadmanagement_nurture_enrollment_a.score_at_enrollment == leadmanagement_lead_a.score
    assert leadmanagement_nurture_enrollment_a.next_touch_at.strftime("%Y-%m-%dT%H:%M") == _leadmanagement_datetime_value(target)

    paused = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_pause", leadmanagement_nurture_enrollment_a.pk)
    )
    assert paused.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "paused"
    assert leadmanagement_nurture_enrollment_a.exit_reason == ""

    resumed = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_resume", leadmanagement_nurture_enrollment_a.pk)
    )
    assert resumed.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "active"
    assert leadmanagement_nurture_enrollment_a.next_touch_at.strftime("%Y-%m-%dT%H:%M") == _leadmanagement_datetime_value(target)

    completed = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_complete", leadmanagement_nurture_enrollment_a.pk),
        {"exit_reason": "completed", "notes": "Sequence complete."},
    )
    assert completed.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "completed"
    assert leadmanagement_nurture_enrollment_a.exit_reason == "completed"
    assert leadmanagement_nurture_enrollment_a.completed_at is not None

    cancel_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Cancel")
    cancel_row = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        cancel_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    cancelled = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_cancel", cancel_row.pk),
        {"exit_reason": "cancelled", "notes": "Cancelled by test."},
    )
    assert cancelled.status_code == 302
    cancel_row.refresh_from_db()
    assert cancel_row.status == "cancelled"
    assert cancel_row.exit_reason == "cancelled"

    reply_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Reply")
    reply_row = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        reply_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    from apps.sales.services import activate_nurture

    activate_nurture(reply_row, leadmanagement_tenant_a, leadmanagement_admin_a)
    replied = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_reply", reply_row.pk),
        {"exit_reason": "replied", "notes": "Lead replied."},
    )
    assert replied.status_code == 302
    reply_row.refresh_from_db()
    assert reply_row.status == "replied"
    assert reply_row.exit_reason == "replied"

    invalid_pending_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Invalid Pending")
    invalid_pending = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        invalid_pending_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    invalid_transition = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_complete", invalid_pending.pk),
        {"exit_reason": "completed"},
    )
    assert invalid_transition.status_code == 302
    invalid_pending.refresh_from_db()
    assert invalid_pending.status == "pending"

    wrong_reason_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Wrong Reason")
    wrong_reason = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        wrong_reason_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    activate_nurture(wrong_reason, leadmanagement_tenant_a, leadmanagement_admin_a)
    invalid_reason = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_complete", wrong_reason.pk),
        {"exit_reason": "cancelled"},
    )
    assert invalid_reason.status_code == 302
    wrong_reason.refresh_from_db()
    assert wrong_reason.status == "active"

    account = _leadmanagement_account(leadmanagement_tenant_a, name="Nurture conversion account")
    conversion_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Conversion")
    opportunity = _leadmanagement_opportunity(
        leadmanagement_tenant_a,
        conversion_lead,
        account,
        currency=None,
        owner=leadmanagement_admin_a,
    )
    converted_row = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        conversion_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    activate_nurture(
        converted_row,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    conversion_lead.status = "converted"
    conversion_lead.save(update_fields=["status", "updated_at"])
    converted = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_convert_exit", converted_row.pk),
        {"exit_reason": "converted", "notes": "Verified CRM conversion."},
    )
    assert converted.status_code == 302
    converted_row.refresh_from_db()
    assert converted_row.status == "converted"
    assert converted_row.exit_reason == "converted"
    assert opportunity.source_lead_id == conversion_lead.pk


def test_leadmanagement_nurture_admin_member_controls_and_invalid_activation(
    leadmanagement_admin_client_a,
    leadmanagement_member_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_nurture_enrollment_a,
):
    invalid_date = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        {"next_touch_at": "not-a-date"},
    )
    assert invalid_date.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "pending"
    assert _leadmanagement_said(invalid_date, "valid next-touch")

    member_activate = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_a.pk),
        {},
    )
    assert member_activate.status_code == 403
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "pending"

    from apps.sales.services import activate_nurture

    activate_nurture(leadmanagement_nurture_enrollment_a, leadmanagement_tenant_a, leadmanagement_admin_a)
    pause_lead = _leadmanagement_alt_lead(leadmanagement_tenant_a, leadmanagement_admin_a, "Nurture Member Pause")
    paused_row = _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        pause_lead,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
    )
    activate_nurture(paused_row, leadmanagement_tenant_a, leadmanagement_admin_a)
    leadmanagement_admin_client_a.post(_leadmanagement_url("lead_nurture_enrollment_pause", paused_row.pk))
    member_resume = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_resume", paused_row.pk)
    )
    assert member_resume.status_code == 403
    paused_row.refresh_from_db()
    assert paused_row.status == "paused"

    member_detail = leadmanagement_member_client_a.get(
        _leadmanagement_url("lead_nurture_enrollment_detail", paused_row.pk)
    )
    assert member_detail.status_code == 200
    assert _leadmanagement_url("lead_nurture_enrollment_resume", paused_row.pk) not in _leadmanagement_body(member_detail)
    admin_detail = leadmanagement_admin_client_a.get(
        _leadmanagement_url("lead_nurture_enrollment_detail", paused_row.pk)
    )
    assert _leadmanagement_url("lead_nurture_enrollment_resume", paused_row.pk) in _leadmanagement_body(admin_detail)

    member_delete = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_nurture_enrollment_delete", leadmanagement_nurture_enrollment_a.pk)
    )
    assert member_delete.status_code == 302
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "active"
    assert LeadNurtureEnrollment.objects.filter(pk=leadmanagement_nurture_enrollment_a.pk).exists()


def test_leadmanagement_handoff_converts_crm_lead_and_is_idempotent(
    leadmanagement_admin_client_a,
    leadmanagement_member_client_a,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_nurture_enrollment_a,
):
    from apps.crm.models import CrmTask, Opportunity
    from apps.core.models import ContactMethod, Party
    from apps.sales.services import activate_nurture

    unqualified = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_handoff", leadmanagement_lead_a.pk)
    )
    assert unqualified.status_code == 302
    assert unqualified["Location"] == _leadmanagement_url("lead_overview")
    assert _leadmanagement_said(unqualified, "qualified assessment is required")
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.status == "new"
    assert not Opportunity.objects.filter(tenant=leadmanagement_tenant_a, source_lead=leadmanagement_lead_a).exists()

    _leadmanagement_set_qualified(
        leadmanagement_qualification_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    activate_nurture(leadmanagement_nurture_enrollment_a, leadmanagement_tenant_a, leadmanagement_admin_a)

    member_handoff = leadmanagement_member_client_a.post(
        _leadmanagement_url("lead_handoff", leadmanagement_lead_a.pk)
    )
    assert member_handoff.status_code == 403

    handoff = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_handoff", leadmanagement_lead_a.pk)
    )
    assert handoff.status_code == 302
    opportunity = Opportunity.objects.get(
        tenant=leadmanagement_tenant_a,
        source_lead=leadmanagement_lead_a,
    )
    assert handoff["Location"] == reverse("crm:opportunity_detail", kwargs={"pk": opportunity.pk})
    assert _leadmanagement_said(handoff, f"Lead handed off to opportunity {opportunity.number}")
    leadmanagement_lead_a.refresh_from_db()
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_lead_a.status == "converted"
    assert leadmanagement_lead_a.converted_party_id is not None
    assert leadmanagement_nurture_enrollment_a.status == "converted"
    assert leadmanagement_nurture_enrollment_a.exit_reason == "converted"
    assert Opportunity.objects.filter(tenant=leadmanagement_tenant_a, source_lead=leadmanagement_lead_a).count() == 1
    assert Party.objects.filter(tenant=leadmanagement_tenant_a, name=leadmanagement_lead_a.name).exists()
    assert ContactMethod.objects.filter(tenant=leadmanagement_tenant_a, value=leadmanagement_lead_a.email).exists()
    assert CrmTask.objects.filter(
        tenant=leadmanagement_tenant_a,
        related_opportunity=opportunity,
        subject=f"Follow up {leadmanagement_lead_a.number}",
    ).count() == 1

    replay = leadmanagement_admin_client_a.post(
        _leadmanagement_url("lead_handoff", leadmanagement_lead_a.pk)
    )
    assert replay.status_code == 302
    assert Opportunity.objects.filter(tenant=leadmanagement_tenant_a, source_lead=leadmanagement_lead_a).count() == 1
    assert CrmTask.objects.filter(
        tenant=leadmanagement_tenant_a,
        related_opportunity=opportunity,
        subject=f"Follow up {leadmanagement_lead_a.number}",
    ).count() == 1


def test_leadmanagement_views_enforce_tenant_object_boundaries(
    leadmanagement_admin_client_a,
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_lead_b,
    leadmanagement_qualification_b,
    leadmanagement_routing_rule_b,
    leadmanagement_nurture_enrollment_b,
    leadmanagement_score_event_b,
):
    detail_objects = (
        ("lead_score_event_detail", leadmanagement_score_event_b.pk),
        ("lead_qualification_detail", leadmanagement_qualification_b.pk),
        ("lead_routing_rule_detail", leadmanagement_routing_rule_b.pk),
        ("lead_nurture_enrollment_detail", leadmanagement_nurture_enrollment_b.pk),
        ("lead_qualification_edit", leadmanagement_qualification_b.pk),
        ("lead_routing_rule_edit", leadmanagement_routing_rule_b.pk),
        ("lead_nurture_enrollment_edit", leadmanagement_nurture_enrollment_b.pk),
        ("lead_qualification_route_preview", leadmanagement_qualification_b.pk),
        ("lead_routing_rule_preview", leadmanagement_routing_rule_b.pk),
    )
    for name, pk in detail_objects:
        response = leadmanagement_admin_client_a.get(_leadmanagement_url(name, pk))
        assert response.status_code == 404, name

    action_objects = (
        ("lead_handoff", leadmanagement_lead_b.pk),
        ("lead_score_event_correct", leadmanagement_score_event_b.pk),
        ("lead_qualification_delete", leadmanagement_qualification_b.pk),
        ("lead_qualification_partial", leadmanagement_qualification_b.pk),
        ("lead_qualification_qualify", leadmanagement_qualification_b.pk),
        ("lead_qualification_disqualify", leadmanagement_qualification_b.pk),
        ("lead_qualification_archive", leadmanagement_qualification_b.pk),
        ("lead_qualification_recalculate", leadmanagement_qualification_b.pk),
        ("lead_routing_rule_delete", leadmanagement_routing_rule_b.pk),
        ("lead_routing_rule_toggle", leadmanagement_routing_rule_b.pk),
        ("lead_routing_rule_run", leadmanagement_routing_rule_b.pk),
        ("lead_nurture_enrollment_delete", leadmanagement_nurture_enrollment_b.pk),
        ("lead_nurture_enrollment_activate", leadmanagement_nurture_enrollment_b.pk),
        ("lead_nurture_enrollment_pause", leadmanagement_nurture_enrollment_b.pk),
        ("lead_nurture_enrollment_resume", leadmanagement_nurture_enrollment_b.pk),
        ("lead_nurture_enrollment_complete", leadmanagement_nurture_enrollment_b.pk),
        ("lead_nurture_enrollment_cancel", leadmanagement_nurture_enrollment_b.pk),
        ("lead_nurture_enrollment_reply", leadmanagement_nurture_enrollment_b.pk),
        ("lead_nurture_enrollment_convert_exit", leadmanagement_nurture_enrollment_b.pk),
    )
    for name, pk in action_objects:
        response = leadmanagement_admin_client_a.post(_leadmanagement_url(name, pk), {})
        assert response.status_code == 404, name


def test_leadmanagement_anonymous_read_routes_redirect_to_login(
    client,
    leadmanagement_tenant_a,
):
    for name in (
        "sales_root",
        "lead_overview",
        "lead_score_event_list",
        "lead_qualification_list",
        "lead_routing_rule_list",
        "lead_nurture_enrollment_list",
    ):
        response = client.get(_leadmanagement_url(name))
        assert response.status_code == 302, name
        assert "login" in response["Location"].lower(), name


@pytest.mark.parametrize("route,requires_pk", _LEADMANAGEMENT_POST_ONLY_ROUTES)
def test_leadmanagement_all_post_only_routes_return_405_for_get(
    route,
    requires_pk,
    leadmanagement_admin_client_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
    leadmanagement_nurture_enrollment_a,
):
    pk = None
    if requires_pk:
        if route == "lead_handoff":
            pk = leadmanagement_lead_a.pk
        elif route == "lead_score_event_correct":
            pk = leadmanagement_score_event_a.pk
        elif route.startswith("lead_qualification_"):
            pk = leadmanagement_qualification_a.pk
        elif route.startswith("lead_routing_rule_"):
            pk = leadmanagement_routing_rule_a.pk
        elif route.startswith("lead_nurture_enrollment_"):
            pk = leadmanagement_nurture_enrollment_a.pk
    response = leadmanagement_admin_client_a.get(_leadmanagement_url(route, pk))
    assert response.status_code == 405, route
