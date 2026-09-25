import csv
import io
import json
from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import resolve, reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounting.models import Invoice
from apps.core.models import AuditLog
from apps.crm.models import HealthScore, HealthScoreHistory, Opportunity
from apps.sales import urls as sales_urls
from apps.sales.models import (
    AccountClassification,
    AccountPlan,
    AccountStakeholder,
    PartyEnrichmentEvent,
)
from apps.sales.services import (
    apply_enrichment_event,
    reject_enrichment_event,
    transition_account_plan,
)
from apps.sales.tests.conftest import (
    _contactaccountmanagement_classification,
    _contactaccountmanagement_contact_profile,
    _contactaccountmanagement_enrichment_event,
    _contactaccountmanagement_organization_party,
    _contactaccountmanagement_person_party,
    _contactaccountmanagement_plan,
    _contactaccountmanagement_stakeholder,
    _contactaccountmanagement_user,
)
from apps.scm.models import SalesOrder


pytestmark = pytest.mark.django_db


_contactaccountmanagement_routes = {
    "party_enrichment_list": ("enrichment-events/", "party_enrichment_list"),
    "party_enrichment_request": ("enrichment-events/request/", "party_enrichment_request"),
    "party_enrichment_export": ("enrichment-events/export/", "party_enrichment_export"),
    "party_enrichment_detail": ("enrichment-events/<int:pk>/", "party_enrichment_detail"),
    "party_enrichment_apply": ("enrichment-events/<int:pk>/apply/", "party_enrichment_apply"),
    "party_enrichment_reject": ("enrichment-events/<int:pk>/reject/", "party_enrichment_reject"),
    "account_stakeholder_list": ("account-stakeholders/", "account_stakeholder_list"),
    "account_stakeholder_create": ("account-stakeholders/add/", "account_stakeholder_create"),
    "account_stakeholder_export": ("account-stakeholders/export/", "account_stakeholder_export"),
    "account_stakeholder_detail": ("account-stakeholders/<int:pk>/", "account_stakeholder_detail"),
    "account_stakeholder_edit": ("account-stakeholders/<int:pk>/edit/", "account_stakeholder_edit"),
    "account_stakeholder_delete": ("account-stakeholders/<int:pk>/delete/", "account_stakeholder_delete"),
    "account_classification_list": ("account-classifications/", "account_classification_list"),
    "account_classification_create": ("account-classifications/add/", "account_classification_create"),
    "account_classification_export": ("account-classifications/export/", "account_classification_export"),
    "account_classification_detail": ("account-classifications/<int:pk>/", "account_classification_detail"),
    "account_classification_edit": ("account-classifications/<int:pk>/edit/", "account_classification_edit"),
    "account_classification_delete": ("account-classifications/<int:pk>/delete/", "account_classification_delete"),
    "account_plan_list": ("account-plans/", "account_plan_list"),
    "account_plan_create": ("account-plans/add/", "account_plan_create"),
    "account_plan_export": ("account-plans/export/", "account_plan_export"),
    "account_plan_detail": ("account-plans/<int:pk>/", "account_plan_detail"),
    "account_plan_edit": ("account-plans/<int:pk>/edit/", "account_plan_edit"),
    "account_plan_delete": ("account-plans/<int:pk>/delete/", "account_plan_delete"),
    "account_plan_activate": ("account-plans/<int:pk>/activate/", "account_plan_activate"),
    "account_plan_review_due": ("account-plans/<int:pk>/review-due/", "account_plan_review_due"),
    "account_plan_complete": ("account-plans/<int:pk>/complete/", "account_plan_complete"),
    "account_plan_archive": ("account-plans/<int:pk>/archive/", "account_plan_archive"),
    "account_hierarchy": ("accounts/hierarchy/", "account_hierarchy"),
    "account_workspace_export": ("accounts/workspace/export/", "account_workspace_export"),
    "account_workspace": ("accounts/workspace/", "account_workspace"),
    "account_coverage": ("accounts/coverage/", "account_coverage"),
    "account_white_space": ("accounts/white-space/", "account_white_space"),
}


_contactaccountmanagement_expected_context = {
    "party_enrichment_list": {
        "object_list", "page_obj", "q", "parties", "kind_choices", "source_kind_choices",
        "status_choices", "party_id", "kind", "source_kind", "status", "date_from", "date_to",
        "stats", "proposal_form", "export_url",
    },
    "party_enrichment_detail": {
        "obj", "party", "proposal_rows", "canonical_values", "can_apply", "can_reject",
        "apply_form", "reject_form", "audit_events", "export_url",
    },
    "account_stakeholder_list": {
        "object_list", "page_obj", "q", "accounts", "contacts", "role_choices",
        "influence_choices", "attitude_choices", "relationship_strength_choices", "status_choices",
        "account_id", "contact_id", "role", "influence", "attitude", "relationship_strength",
        "status", "valid_from", "valid_to", "stats", "export_url",
    },
    "account_stakeholder_create": {"form", "is_edit", "accounts", "contacts"},
    "account_stakeholder_detail": {
        "obj", "account", "contact", "is_primary_affiliation", "reports_to",
        "related_opportunities", "interaction_recency", "coverage_roles", "can_edit",
    },
    "account_stakeholder_edit": {"form", "obj", "is_edit", "accounts", "contacts"},
    "account_classification_list": {
        "object_list", "page_obj", "q", "accounts", "tier_choices", "lifecycle_stage_choices",
        "strategic_priority_choices", "revenue_potential_choices", "wallet_category_choices",
        "account_id", "tier", "lifecycle_stage", "strategic_priority", "revenue_potential",
        "wallet_category", "review_due", "stats", "export_url", "can_edit",
    },
    "account_classification_create": {"form", "is_edit", "accounts"},
    "account_classification_detail": {
        "obj", "account", "health", "health_history", "hierarchy_position", "opportunity_rollups",
        "invoice_rollups", "order_rollups", "currency_rollups", "can_edit",
    },
    "account_classification_edit": {"form", "obj", "is_edit", "accounts"},
    "account_plan_list": {
        "object_list", "page_obj", "q", "accounts", "owners", "status_choices", "account_id",
        "owner_id", "status", "next_review", "period_from", "period_to", "stats", "export_url",
        "can_edit_all",
    },
    "account_plan_create": {"form", "is_edit", "accounts", "owners", "opportunities"},
    "account_plan_detail": {
        "obj", "account", "owner", "related_opportunities", "opportunity_rollups", "health",
        "health_history", "tasks", "recent_activity", "documents", "currency_rollups", "coverage",
        "white_space_note", "allowed_actions", "can_edit",
    },
    "account_plan_edit": {"form", "obj", "is_edit", "accounts", "owners", "opportunities"},
    "account_hierarchy": {
        "accounts", "account_rows", "roots", "selected_account", "view_mode", "view_mode_choices",
        "q", "root_id", "parent_id", "rollup_rows", "stats", "currency_rollups", "caveats",
    },
    "account_workspace": {
        "account", "profile", "classification", "stakeholders", "primary_contacts", "plans",
        "opportunities", "orders", "invoices", "health", "health_history", "activities", "tasks",
        "documents", "coverage", "interaction_recency", "currency_rollups", "opportunity_rollups",
        "realized_rollups", "enrichment_events", "white_space_note", "caveats",
    },
    "account_coverage": {
        "coverage_rows", "accounts", "role_choices", "status_choices", "q", "account_id", "role",
        "status", "stats", "caveats",
    },
    "account_white_space": {
        "white_space_rows", "accounts", "tier_choices", "lifecycle_stage_choices", "q", "account_id",
        "tier", "lifecycle_stage", "review_due", "product_mapping_note", "stats", "caveats",
    },
}


def _contactaccountmanagement_url(name, pk=None):
    kwargs = {"pk": pk} if pk is not None else {}
    return reverse(f"sales:{name}", kwargs=kwargs)


def _contactaccountmanagement_body(response):
    return response.content.decode()


def _contactaccountmanagement_templates(response):
    return [template.name for template in response.templates if template.name]


def _contactaccountmanagement_messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _contactaccountmanagement_said(response, fragment):
    return any(fragment in message for message in _contactaccountmanagement_messages(response))


def _contactaccountmanagement_pks(response, key="object_list"):
    return [row.pk for row in response.context[key]]


def _contactaccountmanagement_explicit_context_keys(response):
    return set(response.context[-1].dicts[3])


def _contactaccountmanagement_date(offset=0):
    return (timezone.localdate() + timedelta(days=offset)).isoformat()


def _contactaccountmanagement_proposal_payload(party, purpose=None, **overrides):
    if party.kind == "organization":
        kind = "firmographic"
        changes = {"employee_count": {"value": 321, "confidence": 0.95}}
    else:
        kind = "contact"
        changes = {"job_title": {"value": "Senior Operations Director", "confidence": 0.95}}
    data = {
        "party": str(party.pk),
        "kind": kind,
        "source_kind": "manual",
        "source_name": "Manual account review",
        "source_reference": "contactaccountmanagement:view-request",
        "changes": json.dumps(changes),
        "legal_basis_purpose": str(purpose.pk) if purpose is not None else "",
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_stakeholder_payload(account, contact, **overrides):
    data = {
        "account": str(account.pk),
        "contact": str(contact.pk),
        "role": "advisor",
        "influence": "medium",
        "attitude": "neutral",
        "relationship_strength": "moderate",
        "status": "active",
        "valid_from": _contactaccountmanagement_date(-30),
        "valid_to": _contactaccountmanagement_date(30),
        "notes": "Stakeholder evidence written through the Sales view.",
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_classification_payload(account, **overrides):
    data = {
        "account": str(account.pk),
        "tier": "growth",
        "lifecycle_stage": "prospect",
        "strategic_priority": "medium",
        "revenue_potential": "unknown",
        "wallet_category": "none",
        "rationale": "Account classification written through the Sales view.",
        "effective_on": _contactaccountmanagement_date(),
        "review_due_on": "",
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_plan_payload(account, owner, **overrides):
    data = {
        "account": str(account.pk),
        "title": "Account growth plan written through the Sales view",
        "period_start": _contactaccountmanagement_date(),
        "period_end": _contactaccountmanagement_date(90),
        "owner": str(owner.pk),
        "business_drivers": "Executive demand and retention",
        "objectives": "Expand adoption across the buying committee",
        "strategy": "Coordinate stakeholders and measurable outcomes",
        "strengths": "Strong executive sponsorship",
        "weaknesses": "Limited operational reach",
        "opportunities": "Additional regional demand",
        "threats": "Competitive pressure",
        "white_space_assessment": "Exact product white-space is unavailable",
        "growth_initiatives": "Executive value workshop",
        "risk_summary": "Low delivery risk",
        "next_review_on": _contactaccountmanagement_date(30),
        "related_opportunities": [],
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_csv(response):
    return list(csv.reader(io.StringIO(_contactaccountmanagement_body(response))))


def _contactaccountmanagement_event(tenant, party, requester, token, **overrides):
    changes = {"employee_count": {"value": 100 + len(token), "confidence": 0.8}}
    kind = "firmographic"
    if party.kind == "person":
        changes = {"job_title": {"value": f"Director {token}", "confidence": 0.8}}
        kind = "contact"
    values = {
        "kind": kind,
        "source_name": f"Source {token}",
        "source_reference": f"contactaccountmanagement:{token}",
        "changes": changes,
        "occurred_at": timezone.now(),
    }
    values.update(overrides)
    return _contactaccountmanagement_enrichment_event(
        tenant,
        party,
        requester,
        **values,
    )


def test_contactaccountmanagement_routes_reverse_and_preserve_literal_first_resolution(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_profile_a,
    contactaccountmanagement_account_child_profile_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_profile_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_reports_to_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_enrichment_event_a,
):
    assert len(_contactaccountmanagement_routes) == 33
    positions = {
        pattern.name: index
        for index, pattern in enumerate(sales_urls.urlpatterns)
        if pattern.name in _contactaccountmanagement_routes
    }
    assert set(positions) == set(_contactaccountmanagement_routes)
    for name, (route, callback_name) in _contactaccountmanagement_routes.items():
        path = reverse(f"sales:{name}", kwargs={"pk": 7} if "<int:pk>" in route else {})
        assert path == f"/sales/{route.replace('<int:pk>', '7')}"
        match = resolve(path)
        assert match.url_name == name
        assert match.func.__name__ == callback_name
        pattern = sales_urls.urlpatterns[positions[name]]
        assert str(pattern.pattern) == route
        assert pattern.callback.__name__ == callback_name

    assert positions["party_enrichment_request"] < positions["party_enrichment_detail"]
    assert positions["party_enrichment_export"] < positions["party_enrichment_detail"]
    assert positions["account_stakeholder_create"] < positions["account_stakeholder_detail"]
    assert positions["account_stakeholder_export"] < positions["account_stakeholder_detail"]
    assert positions["account_classification_create"] < positions["account_classification_detail"]
    assert positions["account_classification_export"] < positions["account_classification_detail"]
    assert positions["account_plan_create"] < positions["account_plan_detail"]
    assert positions["account_plan_export"] < positions["account_plan_detail"]
    assert positions["account_workspace_export"] < positions["account_workspace"]

    html_cases = (
        ("party_enrichment_list", None, {}, "sales/contactaccountmanagement/partyenrichmentevent/list.html", contactaccountmanagement_account_a.name),
        ("party_enrichment_detail", contactaccountmanagement_enrichment_event_a.pk, {}, "sales/contactaccountmanagement/partyenrichmentevent/detail.html", contactaccountmanagement_account_a.name),
        ("account_stakeholder_list", None, {}, "sales/contactaccountmanagement/accountstakeholder/list.html", contactaccountmanagement_contact_a.name),
        ("account_stakeholder_create", None, {}, "sales/contactaccountmanagement/accountstakeholder/form.html", "New Stakeholder"),
        ("account_stakeholder_detail", contactaccountmanagement_stakeholder_a.pk, {}, "sales/contactaccountmanagement/accountstakeholder/detail.html", contactaccountmanagement_contact_a.name),
        ("account_stakeholder_edit", contactaccountmanagement_stakeholder_a.pk, {}, "sales/contactaccountmanagement/accountstakeholder/form.html", "Edit Stakeholder"),
        ("account_classification_list", None, {}, "sales/contactaccountmanagement/accountclassification/list.html", contactaccountmanagement_account_a.name),
        ("account_classification_create", None, {}, "sales/contactaccountmanagement/accountclassification/form.html", "Classify Account"),
        ("account_classification_detail", contactaccountmanagement_classification_a.pk, {}, "sales/contactaccountmanagement/accountclassification/detail.html", contactaccountmanagement_classification_a.rationale),
        ("account_classification_edit", contactaccountmanagement_classification_a.pk, {}, "sales/contactaccountmanagement/accountclassification/form.html", "Edit Classification"),
        ("account_plan_list", None, {}, "sales/contactaccountmanagement/accountplan/list.html", contactaccountmanagement_plan_a.number),
        ("account_plan_create", None, {}, "sales/contactaccountmanagement/accountplan/form.html", "New Account Plan"),
        ("account_plan_detail", contactaccountmanagement_plan_a.pk, {}, "sales/contactaccountmanagement/accountplan/detail.html", contactaccountmanagement_plan_a.number),
        ("account_plan_edit", contactaccountmanagement_plan_a.pk, {}, "sales/contactaccountmanagement/accountplan/form.html", "Edit Account Plan"),
        ("account_hierarchy", None, {}, "sales/contactaccountmanagement/account_hierarchy.html", contactaccountmanagement_account_a.name),
        ("account_workspace", None, {"account": contactaccountmanagement_account_a.pk}, "sales/contactaccountmanagement/account_workspace.html", contactaccountmanagement_account_a.name),
        ("account_coverage", None, {}, "sales/contactaccountmanagement/account_coverage.html", contactaccountmanagement_account_a.name),
        ("account_white_space", None, {}, "sales/contactaccountmanagement/account_white_space.html", contactaccountmanagement_account_a.name),
    )
    for name, pk, params, template_name, fragment in html_cases:
        response = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(name, pk), params)
        assert response.status_code == 200, name
        assert template_name in _contactaccountmanagement_templates(response), name
        assert fragment in _contactaccountmanagement_body(response), name

    export_cases = (
        ("party_enrichment_export", None, {}),
        ("account_stakeholder_export", None, {}),
        ("account_classification_export", None, {}),
        ("account_plan_export", None, {}),
        ("account_workspace_export", None, {"account": contactaccountmanagement_account_a.pk}),
    )
    for name, pk, params in export_cases:
        response = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(name, pk), params)
        assert response.status_code == 200, name
        assert response["Content-Type"] == "text/csv", name
        assert response["Content-Disposition"].startswith("attachment;"), name

    action_cases = (
        ("party_enrichment_request", None),
        ("party_enrichment_apply", contactaccountmanagement_enrichment_event_a.pk),
        ("party_enrichment_reject", contactaccountmanagement_enrichment_event_a.pk),
        ("account_stakeholder_delete", contactaccountmanagement_stakeholder_a.pk),
        ("account_classification_delete", contactaccountmanagement_classification_a.pk),
        ("account_plan_delete", contactaccountmanagement_plan_a.pk),
        ("account_plan_activate", contactaccountmanagement_plan_a.pk),
        ("account_plan_review_due", contactaccountmanagement_plan_a.pk),
        ("account_plan_complete", contactaccountmanagement_plan_a.pk),
        ("account_plan_archive", contactaccountmanagement_plan_a.pk),
    )
    for name, pk in action_cases:
        response = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(name, pk))
        assert response.status_code == 405, name
        assert name in positions


def test_contactaccountmanagement_view_context_keys_match_contract(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_profile_a,
    contactaccountmanagement_account_child_profile_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_profile_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_reports_to_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_enrichment_event_a,
):
    responses = {}
    for name in (
        "party_enrichment_list",
        "party_enrichment_detail",
        "account_stakeholder_list",
        "account_stakeholder_create",
        "account_stakeholder_detail",
        "account_stakeholder_edit",
        "account_classification_list",
        "account_classification_create",
        "account_classification_detail",
        "account_classification_edit",
        "account_plan_list",
        "account_plan_create",
        "account_plan_detail",
        "account_plan_edit",
        "account_hierarchy",
        "account_workspace",
        "account_coverage",
        "account_white_space",
    ):
        pk = None
        params = {}
        if name in {"party_enrichment_detail", "account_stakeholder_detail", "account_stakeholder_edit"}:
            pk = contactaccountmanagement_enrichment_event_a.pk if name == "party_enrichment_detail" else contactaccountmanagement_stakeholder_a.pk
        elif name in {"account_classification_detail", "account_classification_edit"}:
            pk = contactaccountmanagement_classification_a.pk
        elif name in {"account_plan_detail", "account_plan_edit"}:
            pk = contactaccountmanagement_plan_a.pk
        elif name == "account_workspace":
            params = {"account": contactaccountmanagement_account_a.pk}
        response = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(name, pk), params)
        assert response.status_code == 200, name
        responses[name] = response
        assert _contactaccountmanagement_explicit_context_keys(response) == _contactaccountmanagement_expected_context[name], name

    assert responses["party_enrichment_list"].context["page_obj"].paginator.per_page == 20
    assert responses["account_stakeholder_list"].context["page_obj"].paginator.per_page == 20
    assert responses["account_classification_list"].context["page_obj"].paginator.per_page == 20
    assert responses["account_plan_list"].context["page_obj"].paginator.per_page == 20
    assert responses["account_stakeholder_detail"].context["is_primary_affiliation"] is True
    assert responses["account_stakeholder_detail"].context["reports_to"][0].pk == contactaccountmanagement_reports_to_a.pk
    assert responses["account_stakeholder_detail"].context["related_opportunities"] == []
    assert responses["account_classification_detail"].context["health"] is None
    assert list(responses["account_classification_detail"].context["health_history"]) == []
    assert responses["account_plan_detail"].context["related_opportunities"] == []
    assert responses["account_plan_detail"].context["tasks"] == []
    assert responses["account_plan_detail"].context["recent_activity"] == []
    assert responses["account_plan_detail"].context["documents"] == []
    assert responses["account_workspace"].context["profile"].pk == contactaccountmanagement_account_profile_a.pk
    assert responses["account_workspace"].context["opportunities"] == []
    assert responses["account_workspace"].context["orders"] == []
    assert responses["account_workspace"].context["invoices"] == []
    assert responses["account_workspace"].context["health"] is None
    assert responses["account_workspace"].context["health_history"] == []
    assert responses["account_white_space"].context["stats"] == {
        "accounts": 1,
        "with_plans": 1,
        "with_opportunities": 0,
    }
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0
    assert HealthScoreHistory.objects.count() == 0


def test_contactaccountmanagement_enrichment_list_filters_search_pagination_and_export_url(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_consent_purpose_a,
    contactaccountmanagement_enrichment_event_a,
):
    contact_event = _contactaccountmanagement_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_contact_a,
        contactaccountmanagement_admin_a,
        "contact-filter",
    )
    old_external = _contactaccountmanagement_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        "external-filter",
        source_kind="provider",
        legal_basis_purpose=contactaccountmanagement_consent_purpose_a,
        occurred_at=timezone.now() - timedelta(days=1),
    )
    rejected = _contactaccountmanagement_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        "rejected-filter",
        kind="duplicate_check",
    )
    reject_enrichment_event(rejected, contactaccountmanagement_tenant_a, contactaccountmanagement_admin_a, "Not a duplicate")
    apply_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Applied Enrichment Account",
    )
    applied = _contactaccountmanagement_event(
        contactaccountmanagement_tenant_a,
        apply_account,
        contactaccountmanagement_admin_a,
        "applied-filter",
        changes={"employee_count": {"value": 777, "confidence": 1}},
    )
    apply_enrichment_event(applied, contactaccountmanagement_tenant_a, contactaccountmanagement_admin_a, ["employee_count"])
    page_events = [
        _contactaccountmanagement_event(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            f"page-{index:02d}",
        )
        for index in range(16)
    ]

    response = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("party_enrichment_list"),
        {"party": contactaccountmanagement_account_a.pk, "status": "proposed"},
    )
    assert response.status_code == 200
    assert response.context["q"] == ""
    assert response.context["party_id"] == contactaccountmanagement_account_a.pk
    assert response.context["status"] == "proposed"
    assert response.context["export_url"] == (
        f"/sales/enrichment-events/export/?party={contactaccountmanagement_account_a.pk}&status=proposed"
    )
    assert contactaccountmanagement_account_a in list(response.context["parties"])
    assert contactaccountmanagement_contact_a in list(response.context["parties"])
    assert contactaccountmanagement_account_a.name in _contactaccountmanagement_body(response)
    assert "Request enrichment review" in _contactaccountmanagement_body(response)

    page_pks = {event.pk for event in page_events}
    account_event_pks = page_pks | {
        contactaccountmanagement_enrichment_event_a.pk,
        old_external.pk,
        rejected.pk,
    }
    valid_cases = (
        ({"party": contactaccountmanagement_account_a.pk}, account_event_pks),
        ({"kind": "contact"}, {contact_event.pk}),
        ({"source_kind": "provider"}, {old_external.pk}),
        ({"status": "rejected"}, {rejected.pk}),
        ({"status": "applied"}, {applied.pk}),
        ({"date_from": _contactaccountmanagement_date()}, {
            contactaccountmanagement_enrichment_event_a.pk,
            contact_event.pk,
            rejected.pk,
            applied.pk,
        } | page_pks),
        ({"date_to": _contactaccountmanagement_date(-1)}, {old_external.pk}),
        ({"q": "external-filter"}, {old_external.pk}),
    )
    for params, expected in valid_cases:
        filtered = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("party_enrichment_list"),
            params,
        )
        assert filtered.status_code == 200, params
        assert set(_contactaccountmanagement_pks(filtered)) == expected, params

    expected_total = 21
    assert response.context["stats"]["total"] == expected_total
    assert response.context["stats"]["applied"] == 1
    assert response.context["stats"]["rejected"] == 1
    first = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url("party_enrichment_list"))
    second = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("party_enrichment_list"),
        {"page": "2"},
    )
    assert len(_contactaccountmanagement_pks(first)) == 20
    assert len(_contactaccountmanagement_pks(second)) == 1
    assert first.context["page_obj"].number == 1
    assert second.context["page_obj"].number == 2
    assert not set(_contactaccountmanagement_pks(first)).intersection(_contactaccountmanagement_pks(second))
    assert set(_contactaccountmanagement_pks(first)).union(_contactaccountmanagement_pks(second)) == set(
        PartyEnrichmentEvent.objects.filter(tenant=contactaccountmanagement_tenant_a).values_list("pk", flat=True)
    )


def test_contactaccountmanagement_enrichment_request_apply_reject_and_terminal_replay(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_member_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_profile_a,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_enrichment_event_a,
):
    existing = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("party_enrichment_detail", contactaccountmanagement_enrichment_event_a.pk)
    )
    assert existing.status_code == 200
    assert existing.context["can_apply"] is True
    assert existing.context["can_reject"] is True
    assert existing.context["canonical_values"]["industry"] == "technology"
    assert {row["field"] for row in existing.context["proposal_rows"]} == {"industry"}
    assert contactaccountmanagement_account_a.name in _contactaccountmanagement_body(existing)
    assert "Request enrichment review" in contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("party_enrichment_list")
    ).content.decode()

    apply_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Enrichment Apply View Account",
    )
    requested = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("party_enrichment_request"),
        _contactaccountmanagement_proposal_payload(apply_account),
    )
    assert requested.status_code == 302
    event = PartyEnrichmentEvent.objects.get(
        tenant=contactaccountmanagement_tenant_a,
        party=apply_account,
        changes={"employee_count": {"value": 321, "confidence": 0.95}},
    )
    assert requested["Location"] == _contactaccountmanagement_url("party_enrichment_detail", event.pk)
    assert _contactaccountmanagement_said(requested, "Enrichment proposal submitted")

    member_detail = contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("party_enrichment_detail", event.pk)
    )
    assert member_detail.context["can_apply"] is False
    assert member_detail.context["can_reject"] is True
    member_body = _contactaccountmanagement_body(member_detail)
    assert _contactaccountmanagement_url("party_enrichment_reject", event.pk) in member_body
    assert _contactaccountmanagement_url("party_enrichment_apply", event.pk) not in member_body

    member_apply = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("party_enrichment_apply", event.pk),
        {"selected_fields": ["employee_count"], "review_note": "Not allowed."},
    )
    assert member_apply.status_code == 403
    event.refresh_from_db()
    assert event.status == "proposed"

    applied = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("party_enrichment_apply", event.pk),
        {"selected_fields": ["employee_count"], "review_note": "Validated by the account owner."},
    )
    assert applied.status_code == 302
    assert _contactaccountmanagement_said(applied, "Selected enrichment fields were applied")
    event.refresh_from_db()
    assert event.status == "applied"
    assert event.reviewed_by_id == contactaccountmanagement_admin_a.pk
    assert event.applied_at is not None
    assert apply_account.crm_account_profile.employee_count == 321

    replay_apply = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("party_enrichment_apply", event.pk),
        {"selected_fields": ["employee_count"]},
    )
    replay_reject = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("party_enrichment_reject", event.pk),
        {"review_note": "Late rejection."},
    )
    assert replay_apply.status_code == 302
    assert replay_reject.status_code == 302
    event.refresh_from_db()
    assert event.status == "applied"
    assert event.error_summary == ""
    assert _contactaccountmanagement_said(replay_apply, "Only proposed enrichment events can be applied")
    assert _contactaccountmanagement_said(replay_reject, "Only proposed enrichment events can be rejected")

    rejected_request = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("party_enrichment_request"),
        _contactaccountmanagement_proposal_payload(contactaccountmanagement_manager_a),
    )
    assert rejected_request.status_code == 302
    rejected = PartyEnrichmentEvent.objects.get(
        tenant=contactaccountmanagement_tenant_a,
        party=contactaccountmanagement_manager_a,
    )
    rejected_response = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("party_enrichment_reject", rejected.pk),
        {"review_note": "The source could not be verified."},
    )
    assert rejected_response.status_code == 302
    assert _contactaccountmanagement_said(rejected_response, "Enrichment proposal rejected")
    rejected.refresh_from_db()
    assert rejected.status == "rejected"
    assert rejected.reviewed_by.username == "member_acme"
    rejected_replay = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("party_enrichment_reject", rejected.pk),
        {"review_note": "Replay."},
    )
    assert rejected_replay.status_code == 302
    rejected.refresh_from_db()
    assert rejected.status == "rejected"
    assert PartyEnrichmentEvent.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        party__in=(apply_account, contactaccountmanagement_manager_a),
    ).count() == 2
    assert Opportunity.objects.count() == 0
    assert contactaccountmanagement_account_profile_a.employee_count == 125


def test_contactaccountmanagement_stakeholder_crud_filters_and_detail_context(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_admin_client_b,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_stakeholder_b,
    contactaccountmanagement_contact_profile_a,
    contactaccountmanagement_reports_to_a,
):
    former = _contactaccountmanagement_stakeholder(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_child_a,
        contactaccountmanagement_manager_a,
        role="champion",
        influence="low",
        attitude="negative",
        relationship_strength="weak",
        status="former",
        notes="Former relationship evidence",
    )
    create_form = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_stakeholder_create")
    )
    assert create_form.status_code == 200
    assert create_form.context["is_edit"] is False
    assert contactaccountmanagement_account_a in list(create_form.context["accounts"])
    assert contactaccountmanagement_manager_a in list(create_form.context["contacts"])

    created_response = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_stakeholder_create"),
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_child_a,
            contactaccountmanagement_manager_a,
            role="advisor",
        ),
    )
    assert created_response.status_code == 302
    created = AccountStakeholder.objects.get(role="advisor")
    assert created.tenant_id == contactaccountmanagement_tenant_a.pk
    assert created.account_id == contactaccountmanagement_account_child_a.pk
    assert created.contact_id == contactaccountmanagement_manager_a.pk

    edit_form = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_stakeholder_edit", created.pk)
    )
    assert edit_form.status_code == 200
    assert edit_form.context["obj"].pk == created.pk
    assert edit_form.context["form"].fields["account"].disabled is True
    assert edit_form.context["form"].fields["contact"].disabled is True
    edited = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_stakeholder_edit", created.pk),
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_contact_b,
            role="advisor",
            status="former",
            notes="Updated through the stakeholder edit view",
        ),
    )
    assert edited.status_code == 302
    created.refresh_from_db()
    assert created.account_id == contactaccountmanagement_account_child_a.pk
    assert created.contact_id == contactaccountmanagement_manager_a.pk
    assert created.status == "former"
    assert created.notes == "Updated through the stakeholder edit view"

    detail = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_stakeholder_detail", contactaccountmanagement_stakeholder_a.pk)
    )
    assert detail.status_code == 200
    assert detail.context["obj"].pk == contactaccountmanagement_stakeholder_a.pk
    assert detail.context["account"].pk == contactaccountmanagement_account_a.pk
    assert detail.context["contact"].pk == contactaccountmanagement_contact_a.pk
    assert detail.context["is_primary_affiliation"] is True
    assert detail.context["reports_to"][0].to_party_id == contactaccountmanagement_manager_a.pk
    assert detail.context["related_opportunities"] == []
    assert detail.context["interaction_recency"] is None
    assert detail.context["coverage_roles"] == ["decision_maker"]
    assert detail.context["can_edit"] is True
    body = _contactaccountmanagement_body(detail)
    assert contactaccountmanagement_contact_profile_a.account_id == contactaccountmanagement_account_a.pk
    assert contactaccountmanagement_manager_a.name in body
    assert "No opportunities are linked to this account." in body
    assert "Not available" in body

    indirect = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_stakeholder_detail", former.pk)
    )
    assert indirect.context["is_primary_affiliation"] is False

    valid_cases = (
        ({"account": contactaccountmanagement_account_a.pk}, {contactaccountmanagement_stakeholder_a.pk}),
        ({"contact": contactaccountmanagement_contact_a.pk}, {contactaccountmanagement_stakeholder_a.pk}),
        ({"role": "decision_maker"}, {contactaccountmanagement_stakeholder_a.pk}),
        ({"influence": "high"}, {contactaccountmanagement_stakeholder_a.pk}),
        ({"attitude": "positive"}, {contactaccountmanagement_stakeholder_a.pk}),
        ({"relationship_strength": "strong"}, {contactaccountmanagement_stakeholder_a.pk}),
        ({"status": "former"}, {former.pk, created.pk}),
        ({"valid_from": _contactaccountmanagement_date()}, {
            contactaccountmanagement_stakeholder_a.pk,
            former.pk,
            created.pk,
        }),
            ({"valid_to": _contactaccountmanagement_date(30)}, {
                contactaccountmanagement_stakeholder_a.pk,
                former.pk,
                created.pk,
            }),

        ({"q": "Former relationship evidence"}, {former.pk}),
    )
    for params, expected in valid_cases:
        response = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("account_stakeholder_list"),
            params,
        )
        assert response.status_code == 200, params
        assert set(_contactaccountmanagement_pks(response)) == expected, params
    assert response.context["page_obj"].paginator.per_page == 20

    foreign_detail = contactaccountmanagement_admin_client_b.get(
        _contactaccountmanagement_url("account_stakeholder_detail", contactaccountmanagement_stakeholder_a.pk)
    )
    assert foreign_detail.status_code == 404
    deleted = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_stakeholder_delete", created.pk)
    )
    assert deleted.status_code == 302
    assert not AccountStakeholder.objects.filter(pk=created.pk).exists()
    assert AccountStakeholder.objects.filter(pk=contactaccountmanagement_stakeholder_b.pk).exists()
    assert contactaccountmanagement_reports_to_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert Opportunity.objects.count() == 0


def test_contactaccountmanagement_classification_crud_duplicate_upsert_and_detail_rollups(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_admin_client_b,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_account_profile_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_classification_b,
):
    key_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Key Classification Account",
    )
    key = _contactaccountmanagement_classification(
        contactaccountmanagement_tenant_a,
        key_account,
        contactaccountmanagement_admin_a,
        tier="key",
        lifecycle_stage="active_customer",
        strategic_priority="medium",
        revenue_potential="very_high",
        wallet_category="full_wallet",
        review_due_on=timezone.localdate() + timedelta(days=10),
    )
    overdue_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Overdue Classification Account",
    )
    overdue = _contactaccountmanagement_classification(
        contactaccountmanagement_tenant_a,
        overdue_account,
        contactaccountmanagement_admin_a,
        tier="growth",
        lifecycle_stage="dormant",
        strategic_priority="low",
        revenue_potential="low",
        wallet_category="small",
        effective_on=timezone.localdate() - timedelta(days=10),
        review_due_on=timezone.localdate() - timedelta(days=1),
    )
    nurture_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Nurture Classification Account",
    )
    nurture = _contactaccountmanagement_classification(
        contactaccountmanagement_tenant_a,
        nurture_account,
        contactaccountmanagement_admin_a,
        tier="nurture",
        lifecycle_stage="former_customer",
        strategic_priority="low",
        review_due_on=None,
    )

    valid_cases = (
        ({"account": contactaccountmanagement_account_a.pk}, {contactaccountmanagement_classification_a.pk}),
        ({"tier": "key"}, {key.pk}),
        ({"lifecycle_stage": "active_customer"}, {key.pk}),
        ({"strategic_priority": "low"}, {overdue.pk, nurture.pk}),
        ({"revenue_potential": "very_high"}, {key.pk}),
        ({"wallet_category": "full_wallet"}, {key.pk}),
        ({"review_due": "overdue"}, {overdue.pk}),
        ({"review_due": "due_soon"}, {key.pk}),
        ({"review_due": "scheduled"}, {contactaccountmanagement_classification_a.pk, key.pk, overdue.pk}),
        ({"q": "Nurture Classification"}, {nurture.pk}),
    )
    for params, expected in valid_cases:
        response = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("account_classification_list"),
            params,
        )
        assert response.status_code == 200, params
        assert set(_contactaccountmanagement_pks(response)) == expected, params
    assert response.context["page_obj"].paginator.per_page == 20
    assert response.context["stats"]["total"] == 4
    assert response.context["stats"]["strategic"] == 1
    assert response.context["stats"]["key"] == 1
    assert response.context["stats"]["review_overdue"] == 1

    create_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Created Classification Account",
    )
    create_form = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_classification_create")
    )
    assert create_form.status_code == 200
    assert create_form.context["is_edit"] is False
    assert create_account in list(create_form.context["accounts"])
    created_response = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_classification_create"),
        _contactaccountmanagement_classification_payload(create_account),
    )
    assert created_response.status_code == 302
    created = AccountClassification.objects.get(account=create_account)
    assert created.tenant_id == contactaccountmanagement_tenant_a.pk
    assert created.classified_by_id == contactaccountmanagement_admin_a.pk

    duplicate = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_classification_create"),
        _contactaccountmanagement_classification_payload(
            contactaccountmanagement_account_a,
            rationale="This duplicate must redirect to the current row.",
        ),
    )
    assert duplicate.status_code == 302
    assert duplicate["Location"] == _contactaccountmanagement_url(
        "account_classification_edit",
        contactaccountmanagement_classification_a.pk,
    )
    assert _contactaccountmanagement_said(duplicate, "already has a current classification")
    assert AccountClassification.objects.filter(account=contactaccountmanagement_account_a).count() == 1

    edited = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_classification_edit", created.pk),
        _contactaccountmanagement_classification_payload(
            create_account,
            tier="key",
            lifecycle_stage="expansion_candidate",
            rationale="Updated through the classification edit view",
            review_due_on=_contactaccountmanagement_date(45),
        ),
    )
    assert edited.status_code == 302
    created.refresh_from_db()
    assert created.tier == "key"
    assert created.lifecycle_stage == "expansion_candidate"
    assert created.rationale == "Updated through the classification edit view"

    detail = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_classification_detail", contactaccountmanagement_classification_a.pk)
    )
    assert detail.status_code == 200
    assert detail.context["health"] is None
    assert list(detail.context["health_history"]) == []
    assert detail.context["hierarchy_position"]["depth"] == 0
    assert detail.context["currency_rollups"] == {}
    assert detail.context["opportunity_rollups"] == {"currencies": {}}
    assert detail.context["invoice_rollups"] == {"currencies": {}}
    assert detail.context["order_rollups"] == {"currencies": {}}
    detail_body = _contactaccountmanagement_body(detail)
    assert "Health is not available for this account." in detail_body
    assert "No currency-qualified commercial records." in detail_body
    assert contactaccountmanagement_account_profile_a.party_id == contactaccountmanagement_account_a.pk

    foreign_detail = contactaccountmanagement_admin_client_b.get(
        _contactaccountmanagement_url("account_classification_detail", contactaccountmanagement_classification_a.pk)
    )
    assert foreign_detail.status_code == 404
    deleted = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_classification_delete", created.pk)
    )
    assert deleted.status_code == 302
    assert not AccountClassification.objects.filter(pk=created.pk).exists()
    assert AccountClassification.objects.filter(pk=contactaccountmanagement_classification_b.pk).exists()
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0


def test_contactaccountmanagement_plan_crud_owner_policy_and_lifecycle(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_member_client_a,
    contactaccountmanagement_admin_client_b,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_member_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_plan_b,
):
    other_member = _contactaccountmanagement_user(
        contactaccountmanagement_tenant_a,
        "other-member",
    )
    other_client = Client()
    other_client.force_login(other_member)

    create_form = contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("account_plan_create")
    )
    assert create_form.status_code == 200
    assert create_form.context["form"].fields["owner"].disabled is True
    assert list(create_form.context["form"].fields["owner"].queryset) == [contactaccountmanagement_member_a]
    assert contactaccountmanagement_account_a in list(create_form.context["accounts"])
    assert create_form.context["opportunities"] == []

    member_plan_response = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_create"),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            title="Member-owned account plan",
        ),
    )
    assert member_plan_response.status_code == 302
    member_plan = AccountPlan.objects.get(title="Member-owned account plan")
    assert member_plan.owner_id == contactaccountmanagement_member_a.pk
    assert member_plan.status == "draft"
    assert member_plan.related_opportunities.count() == 0

    own_edit_form = contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("account_plan_edit", member_plan.pk)
    )
    assert own_edit_form.status_code == 200
    assert own_edit_form.context["form"].fields["account"].disabled is True
    own_edit = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_edit", member_plan.pk),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            title="Member-owned account plan updated",
        ),
    )
    assert own_edit.status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.title == "Member-owned account plan updated"

    denied_edit = other_client.get(
        _contactaccountmanagement_url("account_plan_edit", member_plan.pk)
    )
    assert denied_edit.status_code == 403
    denied_activate = other_client.post(
        _contactaccountmanagement_url("account_plan_activate", member_plan.pk)
    )
    assert denied_activate.status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "draft"
    assert _contactaccountmanagement_said(denied_activate, "Only the plan owner or a tenant administrator")

    activated = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_activate", member_plan.pk)
    )
    assert activated.status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "active"
    assert _contactaccountmanagement_said(activated, "marked active")

    replay_activate = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_activate", member_plan.pk)
    )
    assert replay_activate.status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "active"
    assert _contactaccountmanagement_said(replay_activate, "transition is not available")

    review_due = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_review_due", member_plan.pk)
    )
    assert review_due.status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "review_due"
    complete = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_complete", member_plan.pk)
    )
    assert complete.status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "completed"
    archive = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_archive", member_plan.pk)
    )
    assert archive.status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "archived"

    archived_detail = contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("account_plan_detail", member_plan.pk)
    )
    assert archived_detail.status_code == 200
    assert archived_detail.context["can_edit"] is False
    assert not any(archived_detail.context["allowed_actions"].values())
    archived_edit = contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("account_plan_edit", member_plan.pk)
    )
    assert archived_edit.status_code == 302
    assert archived_edit["Location"] == _contactaccountmanagement_url("account_plan_detail", member_plan.pk)
    member_plan.refresh_from_db()
    assert member_plan.title == "Member-owned account plan updated"

    non_draft_delete = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_delete", member_plan.pk)
    )
    assert non_draft_delete.status_code == 302
    assert AccountPlan.objects.filter(pk=member_plan.pk).exists()
    assert _contactaccountmanagement_said(non_draft_delete, "archive non-draft plans instead")

    member_delete = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_delete", contactaccountmanagement_plan_a.pk)
    )
    assert member_delete.status_code == 403
    assert AccountPlan.objects.filter(pk=contactaccountmanagement_plan_a.pk).exists()
    draft_delete = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_delete", contactaccountmanagement_plan_a.pk)
    )
    assert draft_delete.status_code == 302
    assert not AccountPlan.objects.filter(pk=contactaccountmanagement_plan_a.pk).exists()

    foreign_detail = contactaccountmanagement_admin_client_b.get(
        _contactaccountmanagement_url("account_plan_detail", member_plan.pk)
    )
    assert foreign_detail.status_code == 404
    assert AccountPlan.objects.filter(pk=contactaccountmanagement_plan_b.pk).exists()
    assert Opportunity.objects.count() == 0


def test_contactaccountmanagement_plan_list_filters_pagination_and_detail_evidence(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_member_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_plan_a,
):
    member_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Member Plan Filter Account",
    )
    active = _contactaccountmanagement_plan(
        contactaccountmanagement_tenant_a,
        member_account,
        contactaccountmanagement_member_a,
        title="Active member-owned filter plan",
    )
    transition_account_plan(active, contactaccountmanagement_tenant_a, contactaccountmanagement_member_a, "active")
    overdue = _contactaccountmanagement_plan(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_child_a,
        contactaccountmanagement_admin_a,
        title="Overdue review filter plan",
        next_review_on=timezone.localdate() - timedelta(days=1),
    )
    for index in range(20):
        _contactaccountmanagement_plan(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            title=f"Pagination account plan {index:02d}",
        )

    valid_cases = (
        ({"account": member_account.pk}, {active.pk}),
        ({"owner": contactaccountmanagement_member_a.pk}, {active.pk}),
        ({"status": "active"}, {active.pk}),
        ({"next_review": "overdue"}, {overdue.pk}),
        ({"q": "Pagination account plan 07"}, {AccountPlan.objects.get(title="Pagination account plan 07").pk}),
    )
    for params, expected in valid_cases:
        response = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("account_plan_list"),
            params,
        )
        assert response.status_code == 200, params
        assert set(_contactaccountmanagement_pks(response)) == expected, params
    assert response.context["page_obj"].paginator.per_page == 20
    assert contactaccountmanagement_admin_a in list(response.context["owners"])
    assert response.context["can_edit_all"] is True

    first = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url("account_plan_list"))
    second = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_plan_list"),
        {"page": "2"},
    )
    assert len(_contactaccountmanagement_pks(first)) == 20
    assert len(_contactaccountmanagement_pks(second)) == 3
    assert not set(_contactaccountmanagement_pks(first)).intersection(_contactaccountmanagement_pks(second))

    detail = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_plan_detail", contactaccountmanagement_plan_a.pk)
    )
    assert detail.status_code == 200
    assert detail.context["account"].pk == contactaccountmanagement_account_a.pk
    assert detail.context["owner"].pk == contactaccountmanagement_admin_a.pk
    assert detail.context["related_opportunities"] == []
    assert detail.context["opportunity_rollups"] == {"currencies": {}}
    assert detail.context["health"] is None
    assert list(detail.context["health_history"]) == []
    assert detail.context["tasks"] == []
    assert detail.context["recent_activity"] == []
    assert detail.context["documents"] == []
    assert detail.context["currency_rollups"] == {}
    assert detail.context["coverage"] == ["decision_maker"]
    body = _contactaccountmanagement_body(detail)
    assert contactaccountmanagement_plan_a.number in body
    assert "No opportunities linked." in body
    assert "Health:" in body and "Not available" in body
    assert "No tasks linked to this account." in body
    assert "No currency-qualified commercial records." in body
    assert "Exact product white-space is incomplete" in body
    assert Opportunity.objects.count() == 0
    assert HealthScore.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0


def test_contactaccountmanagement_hierarchy_workspace_coverage_and_white_space_boards(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_account_profile_a,
    contactaccountmanagement_account_child_profile_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_profile_a,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_enrichment_event_a,
):
    child_classification = _contactaccountmanagement_classification(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_child_a,
        contactaccountmanagement_admin_a,
        tier="growth",
        lifecycle_stage="prospect",
        strategic_priority="medium",
        review_due_on=timezone.localdate() + timedelta(days=60),
    )
    _contactaccountmanagement_contact_profile(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_manager_a,
        account=contactaccountmanagement_account_child_a,
        owner=contactaccountmanagement_admin_a,
    )
    assert contactaccountmanagement_account_child_profile_a.parent_account_id == contactaccountmanagement_account_a.pk

    hierarchy = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url("account_hierarchy"))
    assert hierarchy.status_code == 200
    assert hierarchy.context["stats"] == {"total": 2, "roots": 1, "leaves": 1, "cycles": 0}
    assert set(hierarchy.context["accounts"]) == {
        contactaccountmanagement_account_a,
        contactaccountmanagement_account_child_a,
    }
    assert hierarchy.context["roots"] == [contactaccountmanagement_account_a]
    assert hierarchy.context["currency_rollups"] == {}
    row_by_id = {row["party"].pk: row for row in hierarchy.context["account_rows"]}
    assert row_by_id[contactaccountmanagement_account_a.pk]["depth"] == 0
    assert row_by_id[contactaccountmanagement_account_a.pk]["descendant_count"] == 1
    assert row_by_id[contactaccountmanagement_account_child_a.pk]["depth"] == 1
    assert row_by_id[contactaccountmanagement_account_child_a.pk]["is_leaf"] is True

    descendants = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_hierarchy"),
        {"view_mode": "descendants", "root": contactaccountmanagement_account_a.pk},
    )
    assert set(descendants.context["accounts"]) == {
        contactaccountmanagement_account_a,
        contactaccountmanagement_account_child_a,
    }
    assert descendants.context["selected_account"].pk == contactaccountmanagement_account_a.pk
    children = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_hierarchy"),
        {"view_mode": "parent", "parent": contactaccountmanagement_account_a.pk},
    )
    assert [row.pk for row in children.context["accounts"]] == [contactaccountmanagement_account_child_a.pk]
    leaves = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_hierarchy"),
        {"view_mode": "leaves"},
    )
    assert [row.pk for row in leaves.context["accounts"]] == [contactaccountmanagement_account_child_a.pk]
    searched = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_hierarchy"),
        {"q": "Child Organization", "view_mode": "invalid"},
    )
    assert searched.context["view_mode"] == "tree"
    assert [row.pk for row in searched.context["accounts"]] == [contactaccountmanagement_account_child_a.pk]

    workspace = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_workspace"),
        {"account": contactaccountmanagement_account_a.pk},
    )
    assert workspace.status_code == 200
    assert workspace.context["profile"].pk == contactaccountmanagement_account_profile_a.pk
    assert workspace.context["classification"].pk == contactaccountmanagement_classification_a.pk
    assert [row.pk for row in workspace.context["stakeholders"]] == [contactaccountmanagement_stakeholder_a.pk]
    assert [row.party_id for row in workspace.context["primary_contacts"]] == [contactaccountmanagement_contact_a.pk]
    assert [row.pk for row in workspace.context["plans"]] == [contactaccountmanagement_plan_a.pk]
    assert [row.pk for row in workspace.context["enrichment_events"]] == [contactaccountmanagement_enrichment_event_a.pk]
    assert workspace.context["opportunities"] == []
    assert workspace.context["orders"] == []
    assert workspace.context["invoices"] == []
    assert workspace.context["health"] is None
    assert workspace.context["health_history"] == []
    assert workspace.context["tasks"] == []
    assert workspace.context["documents"] == []
    assert workspace.context["currency_rollups"] == {}
    body = _contactaccountmanagement_body(workspace)
    assert contactaccountmanagement_account_a.name in body
    assert contactaccountmanagement_contact_a.name in body
    assert contactaccountmanagement_plan_a.number in body
    assert "No commercial records." in body
    assert "Not available" in body
    assert "Exact product white-space is incomplete" in body

    coverage = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_coverage"),
        {"account": contactaccountmanagement_account_a.pk, "status": "active"},
    )
    assert coverage.status_code == 200
    assert coverage.context["stats"] == {
        "accounts": 1,
        "with_decision_maker": 1,
        "with_champion": 0,
        "with_blocker": 0,
    }
    assert coverage.context["coverage_rows"][0]["primary_count"] == 1
    assert coverage.context["coverage_rows"][0]["stakeholder_count"] == 1
    assert coverage.context["coverage_rows"][0]["coverage_label"] == "Covered"
    assert coverage.context["coverage_rows"][0]["role_values"] == {"decision_maker"}
    child_coverage = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_coverage"),
        {"account": contactaccountmanagement_account_child_a.pk, "status": "active"},
    )
    assert child_coverage.context["coverage_rows"][0]["coverage_label"] == "Primary affiliation"
    assert child_coverage.context["coverage_rows"][0]["stakeholder_count"] == 0
    role_filtered = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_coverage"),
        {"role": "decision_maker"},
    )
    assert [row["account"].pk for row in role_filtered.context["coverage_rows"]] == [contactaccountmanagement_account_a.pk]
    assert contactaccountmanagement_contact_profile_a.account_id == contactaccountmanagement_account_a.pk

    white_space = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_white_space"),
        {"tier": "strategic", "lifecycle_stage": "prospect"},
    )
    assert white_space.status_code == 200
    assert white_space.context["stats"] == {
        "accounts": 1,
        "with_plans": 1,
        "with_opportunities": 0,
    }
    assert white_space.context["white_space_rows"][0]["plan_count"] == 1
    assert white_space.context["white_space_rows"][0]["opportunity_count"] == 0
    assert "Product and SCM Item" in _contactaccountmanagement_body(white_space)
    all_white_space = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_white_space")
    )
    assert len(all_white_space.context["white_space_rows"]) == 2
    assert all_white_space.context["white_space_rows"][1]["classification"].pk == child_classification.pk

    for account in (contactaccountmanagement_account_b.pk, "abc", "0", "999999999999999999999"):
        assert contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("account_workspace"),
            {"account": account},
        ).status_code == 404
        assert contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("account_coverage"),
            {"account": account},
        ).status_code == 404
        assert contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("account_white_space"),
            {"account": account},
        ).status_code == 404
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0
    assert HealthScoreHistory.objects.count() == 0


def test_contactaccountmanagement_exports_are_filtered_capped_and_csv_safe(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_enrichment_event_a,
):
    contactaccountmanagement_account_a.name = "=Formula Account"
    contactaccountmanagement_account_a.save(update_fields=["name"])
    contactaccountmanagement_contact_a.name = "+Formula Contact"
    contactaccountmanagement_contact_a.save(update_fields=["name"])
    _contactaccountmanagement_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        "formula-export",
        source_name="@Formula Source",
    )
    contactaccountmanagement_classification_a.rationale = "-Formula Rationale"
    contactaccountmanagement_classification_a.save(update_fields=["rationale"])
    contactaccountmanagement_plan_a.title = "=Formula Plan"
    contactaccountmanagement_plan_a.save(update_fields=["title"])

    cases = (
        (
            "party_enrichment_export",
            {"party": contactaccountmanagement_account_a.pk, "source_kind": "manual"},
            ["Party", "Kind", "Source", "Status", "Occurred", "Applied", "Error code", "Error summary"],
            2,
            2,
        ),
        (
            "account_stakeholder_export",
            {"account": contactaccountmanagement_account_a.pk, "role": "decision_maker"},
            ["Account", "Contact", "Role", "Influence", "Attitude", "Strength", "Status", "Valid from", "Valid to"],
            1,
            0,
        ),
        (
            "account_classification_export",
            {"account": contactaccountmanagement_account_a.pk, "tier": "strategic"},
            ["Account", "Tier", "Lifecycle", "Priority", "Potential", "Wallet", "Effective", "Review due", "Rationale"],
            1,
            8,
        ),
        (
            "account_plan_export",
            {"account": contactaccountmanagement_account_a.pk, "owner": contactaccountmanagement_admin_a.pk},
            ["Number", "Account", "Title", "Status", "Period start", "Period end", "Owner", "Next review", "Linked opportunities"],
            1,
            2,
        ),
        (
            "account_workspace_export",
            {"account": contactaccountmanagement_account_a.pk},
            ["Account", "Tier", "Lifecycle", "Health score", "Currency", "Open opportunities", "Weighted pipeline", "Orders", "Invoices"],
            1,
            0,
        ),
    )
    for name, params, headers, row_count, formula_column in cases:
        response = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url(name),
            params,
        )
        assert response.status_code == 200, name
        rows = _contactaccountmanagement_csv(response)
        assert rows[0] == headers, name
        assert len(rows) == row_count + 1, name
        if row_count:
            assert rows[1][formula_column].startswith("'"), (name, rows[1])

    export_audits = [
        row.changes
        for row in AuditLog.objects.filter(
            tenant=contactaccountmanagement_tenant_a,
            action="update",
        ).order_by("-at")
        if row.changes.get("action") == "export"
    ]
    assert len(export_audits) == 5
    assert all("q" not in changes["filters"] for changes in export_audits)
    assert all("changes" not in changes and "review_note" not in changes for changes in export_audits)
    assert all("Formula Rationale" not in str(changes) for changes in export_audits)

    occurred_at = timezone.now() + timedelta(minutes=1)
    PartyEnrichmentEvent.objects.bulk_create(
        [
            PartyEnrichmentEvent(
                tenant=contactaccountmanagement_tenant_a,
                party=contactaccountmanagement_account_a,
                kind="firmographic",
                source_kind="manual",
                source_name="=Capped Export" if index == 0 else f"Bulk export {index}",
                source_reference=f"bulk-export:{index}",
                status="proposed",
                changes={"employee_count": {"value": 1000 + index}},
                requested_by=contactaccountmanagement_admin_a,
                occurred_at=occurred_at if index == 0 else timezone.now(),
            )
            for index in range(5001)
        ],
        batch_size=500,
    )
    capped = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("party_enrichment_export"),
        {"status": "proposed"},
    )
    capped_rows = _contactaccountmanagement_csv(capped)
    assert len(capped_rows) == 5001
    assert capped_rows[0] == [
        "Party", "Kind", "Source", "Status", "Occurred", "Applied", "Error code", "Error summary",
    ]
    assert capped_rows[1][2] == "'=Capped Export"
    assert all(len(row) == 8 for row in capped_rows)
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0


def test_contactaccountmanagement_views_reject_malformed_and_junk_filters_without_narrowing(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_enrichment_event_a,
):
    list_cases = (
        (
            "party_enrichment_list",
            {
                "party": "abc",
                "kind": "invalid",
                "source_kind": "invalid",
                "status": "invalid",
                "date_from": "not-a-date",
                "date_to": "also-not-a-date",
            },
            {contactaccountmanagement_enrichment_event_a.pk},
        ),
        (
            "account_stakeholder_list",
            {
                "account": "0",
                "contact": "999999999999999999999",
                "role": "invalid",
                "influence": "invalid",
                "attitude": "invalid",
                "relationship_strength": "invalid",
                "status": "invalid",
                "valid_from": "bad",
                "valid_to": "bad",
            },
            {contactaccountmanagement_stakeholder_a.pk},
        ),
        (
            "account_classification_list",
            {
                "account": "abc",
                "tier": "invalid",
                "lifecycle_stage": "invalid",
                "strategic_priority": "invalid",
                "revenue_potential": "invalid",
                "wallet_category": "invalid",
                "review_due": "invalid",
            },
            {contactaccountmanagement_classification_a.pk},
        ),
        (
            "account_plan_list",
            {
                "account": "999999999999999999999",
                "owner": "abc",
                "status": "invalid",
                "next_review": "invalid",
                "period_from": "not-a-date",
                "period_to": "not-a-date",
                "page": "not-a-page",
            },
            {contactaccountmanagement_plan_a.pk},
        ),
    )
    for name, params, expected in list_cases:
        response = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url(name),
            params,
        )
        assert response.status_code == 200, name
        assert set(_contactaccountmanagement_pks(response)) == expected, name

    for params in (
        {"party": "0"},
        {"party": "999999999999999999999"},
        {"kind": "invalid"},
        {"date_from": "bad", "date_to": "9999-99-99"},
    ):
        response = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url("party_enrichment_list"),
            params,
        )
        assert response.status_code == 200, params
        assert set(_contactaccountmanagement_pks(response)) == {contactaccountmanagement_enrichment_event_a.pk}

    hierarchy = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_hierarchy"),
        {"root": "abc", "parent": "999999999999999999999", "view_mode": "junk"},
    )
    assert hierarchy.status_code == 200
    assert hierarchy.context["selected_account"] is None
    assert hierarchy.context["view_mode"] == "tree"

    coverage = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_coverage"),
        {"role": "junk", "status": "junk"},
    )
    assert coverage.status_code == 200
    assert coverage.context["role"] == ""
    assert coverage.context["status"] == "active"
    white_space = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_white_space"),
        {"tier": "junk", "lifecycle_stage": "junk", "review_due": "junk"},
    )
    assert white_space.status_code == 200
    assert white_space.context["tier"] == ""
    assert white_space.context["lifecycle_stage"] == ""
    assert white_space.context["review_due"] == ""

    for board_name in ("account_coverage", "account_white_space"):
        for account in ("abc", "0", "999999999999999999999"):
            response = contactaccountmanagement_admin_client_a.get(
                _contactaccountmanagement_url(board_name),
                {"account": account},
            )
            assert response.status_code == 404, (board_name, account)

    export = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("party_enrichment_export"),
        {"party": "abc", "status": "junk", "date_from": "bad"},
    )
    assert export.status_code == 200
    assert len(_contactaccountmanagement_csv(export)) == 2


def test_contactaccountmanagement_list_pagination_uses_twenty_rows_for_each_register(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
):
    for index in range(21):
        _contactaccountmanagement_event(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            f"pagination-{index:02d}",
        )
    for index in range(21):
        contact = _contactaccountmanagement_person_party(
            contactaccountmanagement_tenant_a,
            name=f"Pagination Contact {index:02d}",
        )
        _contactaccountmanagement_stakeholder(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contact,
            role="advisor",
            notes=f"Pagination stakeholder {index:02d}",
        )
    for index in range(21):
        account = _contactaccountmanagement_organization_party(
            contactaccountmanagement_tenant_a,
            name=f"Pagination Classification {index:02d}",
        )
        _contactaccountmanagement_classification(
            contactaccountmanagement_tenant_a,
            account,
            contactaccountmanagement_admin_a,
            rationale=f"Pagination classification {index:02d}",
        )
    for index in range(21):
        _contactaccountmanagement_plan(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            title=f"Pagination plan {index:02d}",
        )

    for name, key in (
        ("party_enrichment_list", "PartyEnrichmentEvent"),
        ("account_stakeholder_list", "AccountStakeholder"),
        ("account_classification_list", "AccountClassification"),
        ("account_plan_list", "AccountPlan"),
    ):
        first = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(name))
        second = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url(name),
            {"page": "2"},
        )
        assert first.status_code == 200, name
        assert second.status_code == 200, name
        assert len(_contactaccountmanagement_pks(first)) == 20, name
        assert len(_contactaccountmanagement_pks(second)) == 1, name
        assert not set(_contactaccountmanagement_pks(first)).intersection(_contactaccountmanagement_pks(second)), name
        assert first.context["page_obj"].paginator.per_page == 20, name
        assert set(_contactaccountmanagement_pks(first)).union(_contactaccountmanagement_pks(second)) == set(
            globals()[key].objects.filter(tenant=contactaccountmanagement_tenant_a).values_list("pk", flat=True)
        )
    assert Opportunity.objects.count() == 0


def test_contactaccountmanagement_tenantless_reads_are_empty_and_do_not_fabricate_evidence(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_profile_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_profile_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_enrichment_event_a,
):
    tenantless_user = User.objects.create_user(
        email="root@naverp.example",
        username="tenantless_root",
        password="TestPass123!",
        tenant=None,
        is_staff=True,
        is_superuser=True,
        is_tenant_admin=True,
    )
    tenantless_client = Client()
    tenantless_client.force_login(tenantless_user)

    list_names = (
        "party_enrichment_list",
        "account_stakeholder_list",
        "account_classification_list",
        "account_plan_list",
    )
    for name in list_names:
        response = tenantless_client.get(_contactaccountmanagement_url(name))
        assert response.status_code == 200, name
        assert list(response.context["object_list"]) == [], name
        assert response.context["page_obj"].paginator.count == 0, name
        assert response.context["stats"]["total"] == 0, name
        assert contactaccountmanagement_account_a.name not in _contactaccountmanagement_body(response), name

    hierarchy = tenantless_client.get(_contactaccountmanagement_url("account_hierarchy"))
    assert hierarchy.status_code == 200
    assert hierarchy.context["accounts"] == []
    assert hierarchy.context["account_rows"] == []
    assert hierarchy.context["roots"] == []
    assert hierarchy.context["stats"]["total"] == 0
    coverage = tenantless_client.get(_contactaccountmanagement_url("account_coverage"))
    assert coverage.status_code == 200
    assert coverage.context["coverage_rows"] == []
    white_space = tenantless_client.get(_contactaccountmanagement_url("account_white_space"))
    assert white_space.status_code == 200
    assert white_space.context["white_space_rows"] == []
    workspace = tenantless_client.get(_contactaccountmanagement_url("account_workspace"))
    assert workspace.status_code == 302
    assert workspace["Location"] == _contactaccountmanagement_url("account_hierarchy")
    assert tenantless_client.get(
        _contactaccountmanagement_url("account_workspace_export"),
        {"account": contactaccountmanagement_account_a.pk},
    ).status_code == 404

    for name, pk in (
        ("party_enrichment_detail", contactaccountmanagement_enrichment_event_a.pk),
        ("account_stakeholder_detail", contactaccountmanagement_stakeholder_a.pk),
        ("account_stakeholder_edit", contactaccountmanagement_stakeholder_a.pk),
        ("account_classification_detail", contactaccountmanagement_classification_a.pk),
        ("account_classification_edit", contactaccountmanagement_classification_a.pk),
        ("account_plan_detail", contactaccountmanagement_plan_a.pk),
        ("account_plan_edit", contactaccountmanagement_plan_a.pk),
    ):
        assert tenantless_client.get(_contactaccountmanagement_url(name, pk)).status_code == 404

    for name, expected_choices in (
        ("account_stakeholder_create", ("accounts", "contacts")),
        ("account_classification_create", ("accounts",)),
        ("account_plan_create", ("accounts", "owners", "opportunities")),
    ):
        response = tenantless_client.get(_contactaccountmanagement_url(name))
        assert response.status_code == 200, name
        for key in expected_choices:
            assert list(response.context[key]) == [], (name, key)

    assert AccountClassification.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account=contactaccountmanagement_account_a,
    ).count() == 1
    assert AccountPlan.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account=contactaccountmanagement_account_a,
    ).count() == 1
    assert PartyEnrichmentEvent.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        party=contactaccountmanagement_account_a,
    ).count() == 1
    assert AccountStakeholder.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account=contactaccountmanagement_account_a,
    ).count() == 1
    assert contactaccountmanagement_admin_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert contactaccountmanagement_account_profile_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert contactaccountmanagement_contact_profile_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0
    assert HealthScoreHistory.objects.count() == 0
