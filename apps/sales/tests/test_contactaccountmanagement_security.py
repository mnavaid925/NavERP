import csv
import io
import json
import socket
import urllib.request
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, PartyRelationship
from apps.crm.models import AccountProfile, HealthScore, HealthScoreHistory, Opportunity
from apps.sales.models import (
    AccountClassification,
    AccountPlan,
    AccountStakeholder,
    PartyEnrichmentEvent,
)
from apps.sales.models.ContactAccountManagement.AccountPlans import (
    validate_account_plan_opportunities,
    validate_account_plan_opportunity_links,
)
from apps.sales.services import (
    account_hierarchy_rows,
    apply_enrichment_event,
    create_enrichment_event,
    reject_enrichment_event,
    transition_account_plan,
)
from apps.sales.tests.conftest import (
    _contactaccountmanagement_account_profile,
    _contactaccountmanagement_consent_purpose,
    _contactaccountmanagement_contact_profile,
    _contactaccountmanagement_enrichment_event,
    _contactaccountmanagement_organization_party,
    _contactaccountmanagement_person_party,
    _contactaccountmanagement_plan,
    _contactaccountmanagement_user,
)
from apps.sales.views._common import csv_safe
from apps.accounting.models import Invoice
from apps.scm.models import SalesOrder


pytestmark = pytest.mark.django_db


_contactaccountmanagement_action_routes = (
    ("party_enrichment_request", None),
    ("party_enrichment_apply", "contactaccountmanagement_enrichment_event_a"),
    ("party_enrichment_reject", "contactaccountmanagement_enrichment_event_a"),
    ("account_stakeholder_delete", "contactaccountmanagement_stakeholder_a"),
    ("account_classification_delete", "contactaccountmanagement_classification_a"),
    ("account_plan_delete", "contactaccountmanagement_plan_a"),
    ("account_plan_activate", "contactaccountmanagement_plan_a"),
    ("account_plan_review_due", "contactaccountmanagement_plan_a"),
    ("account_plan_complete", "contactaccountmanagement_plan_a"),
    ("account_plan_archive", "contactaccountmanagement_plan_a"),
)

_contactaccountmanagement_csrf_form_routes = (
    ("account_stakeholder_create", None),
    ("account_stakeholder_edit", "contactaccountmanagement_stakeholder_a"),
    ("account_classification_create", None),
    ("account_classification_edit", "contactaccountmanagement_classification_a"),
    ("account_plan_create", None),
    ("account_plan_edit", "contactaccountmanagement_plan_a"),
)

_contactaccountmanagement_read_routes = (
    ("party_enrichment_list", None),
    ("party_enrichment_detail", "contactaccountmanagement_enrichment_event_a"),
    ("party_enrichment_export", None),
    ("account_stakeholder_list", None),
    ("account_stakeholder_create", None),
    ("account_stakeholder_detail", "contactaccountmanagement_stakeholder_a"),
    ("account_stakeholder_edit", "contactaccountmanagement_stakeholder_a"),
    ("account_stakeholder_export", None),
    ("account_classification_list", None),
    ("account_classification_create", None),
    ("account_classification_detail", "contactaccountmanagement_classification_a"),
    ("account_classification_edit", "contactaccountmanagement_classification_a"),
    ("account_classification_export", None),
    ("account_plan_list", None),
    ("account_plan_create", None),
    ("account_plan_detail", "contactaccountmanagement_plan_a"),
    ("account_plan_edit", "contactaccountmanagement_plan_a"),
    ("account_plan_export", None),
    ("account_hierarchy", None),
    ("account_workspace", None),
    ("account_coverage", None),
    ("account_white_space", None),
    ("account_workspace_export", None),
)


def _contactaccountmanagement_url(name, pk=None):
    kwargs = {"pk": pk} if pk is not None else {}
    return reverse(f"sales:{name}", kwargs=kwargs)


def _contactaccountmanagement_body(response):
    return response.content.decode()


def _contactaccountmanagement_csv(response):
    return list(csv.reader(io.StringIO(_contactaccountmanagement_body(response))))


def _contactaccountmanagement_messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _contactaccountmanagement_said(response, fragment):
    return any(fragment in message for message in _contactaccountmanagement_messages(response))


def _contactaccountmanagement_date(offset=0):
    return (timezone.localdate() + timedelta(days=offset)).isoformat()


def _contactaccountmanagement_proposal_payload(party, purpose=None, **overrides):
    changes = {
        "industry": {"value": "technology", "confidence": 0.9},
    } if party.kind == "organization" else {
        "job_title": {"value": "Operations Director", "confidence": 0.9},
    }
    data = {
        "party": str(party.pk),
        "kind": "firmographic" if party.kind == "organization" else "contact",
        "source_kind": "manual",
        "source_name": "Manual review",
        "source_reference": "contactaccountmanagement:security",
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
        "notes": "Security stakeholder payload.",
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
        "rationale": "Security classification rationale.",
        "effective_on": _contactaccountmanagement_date(),
        "review_due_on": "",
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_plan_payload(account, owner, **overrides):
    data = {
        "account": str(account.pk),
        "title": "Security account plan",
        "period_start": _contactaccountmanagement_date(),
        "period_end": _contactaccountmanagement_date(90),
        "owner": str(owner.pk),
        "business_drivers": "Growth",
        "objectives": "Retain the account",
        "strategy": "Executive coverage",
        "strengths": "Sponsor access",
        "weaknesses": "Limited reach",
        "opportunities": "New region",
        "threats": "Competition",
        "white_space_assessment": "Product mapping unavailable",
        "growth_initiatives": "Executive workshop",
        "risk_summary": "Low risk",
        "next_review_on": _contactaccountmanagement_date(30),
        "related_opportunities": [],
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_state(row):
    names = (
        "tenant_id",
        "account_id",
        "contact_id",
        "owner_id",
        "number",
        "status",
        "tier",
        "lifecycle_stage",
        "classified_by_id",
        "requested_by_id",
        "reviewed_by_id",
        "applied_at",
        "error_summary",
    )
    return {name: getattr(row, name) for name in names if hasattr(row, name)}


def _contactaccountmanagement_tenantless_client():
    user = User.objects.create_user(
        email="contactaccountmanagement-root@example.com",
        username="contactaccountmanagement_root",
        password="TestPass123!",
        tenant=None,
        is_staff=True,
        is_superuser=True,
        is_tenant_admin=True,
    )
    client = Client()
    client.force_login(user)
    return client


def _contactaccountmanagement_forbid_network(*args, **kwargs):
    raise AssertionError("outbound network access is forbidden")


def _contactaccountmanagement_csv_safe_values():
    return ("=formula", "+formula", "-formula", "@formula", "\tformula", "\nformula")


def test_contactaccountmanagement_anonymous_requests_redirect_to_login(
    client,
    contactaccountmanagement_enrichment_event_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
):
    before = (
        PartyEnrichmentEvent.objects.count(),
        AccountStakeholder.objects.count(),
        AccountClassification.objects.count(),
        AccountPlan.objects.count(),
    )
    for route, fixture_name in _contactaccountmanagement_read_routes:
        pk = None
        if fixture_name is not None:
            pk = None
        if fixture_name == "contactaccountmanagement_enrichment_event_a":
            pk = contactaccountmanagement_enrichment_event_a.pk
        elif fixture_name == "contactaccountmanagement_stakeholder_a":
            pk = contactaccountmanagement_stakeholder_a.pk
        elif fixture_name == "contactaccountmanagement_classification_a":
            pk = contactaccountmanagement_classification_a.pk
        elif fixture_name == "contactaccountmanagement_plan_a":
            pk = contactaccountmanagement_plan_a.pk
        response = client.get(_contactaccountmanagement_url(route, pk))
        assert response.status_code == 302, route
        assert "login" in response.url.lower(), route
    for route, fixture_name in _contactaccountmanagement_action_routes:
        pk = None
        if fixture_name == "contactaccountmanagement_enrichment_event_a":
            pk = contactaccountmanagement_enrichment_event_a.pk
        elif fixture_name == "contactaccountmanagement_stakeholder_a":
            pk = contactaccountmanagement_stakeholder_a.pk
        elif fixture_name == "contactaccountmanagement_classification_a":
            pk = contactaccountmanagement_classification_a.pk
        elif fixture_name == "contactaccountmanagement_plan_a":
            pk = contactaccountmanagement_plan_a.pk
        assert client.get(_contactaccountmanagement_url(route, pk)).status_code == 405, route
        response = client.post(_contactaccountmanagement_url(route, pk), {})
        assert response.status_code == 302, route
        assert "login" in response.url.lower(), route
    assert (
        PartyEnrichmentEvent.objects.count(),
        AccountStakeholder.objects.count(),
        AccountClassification.objects.count(),
        AccountPlan.objects.count(),
    ) == before


def test_contactaccountmanagement_tenantless_user_cannot_see_or_write_tenant_rows(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_enrichment_event_a,
):
    client = _contactaccountmanagement_tenantless_client()
    list_names = (
        "party_enrichment_list",
        "account_stakeholder_list",
        "account_classification_list",
        "account_plan_list",
    )
    for name in list_names:
        response = client.get(_contactaccountmanagement_url(name))
        assert response.status_code == 200, name
        assert list(response.context["object_list"]) == [], name
        assert response.context["page_obj"].paginator.count == 0, name
        assert response.context["stats"]["total"] == 0, name
        assert contactaccountmanagement_account_a.name not in _contactaccountmanagement_body(response), name
    for name in ("account_hierarchy", "account_coverage", "account_white_space"):
        response = client.get(_contactaccountmanagement_url(name))
        assert response.status_code == 200, name
        assert list(response.context[{"account_hierarchy": "accounts", "account_coverage": "coverage_rows", "account_white_space": "white_space_rows"}[name]]) == []
    workspace = client.get(_contactaccountmanagement_url("account_workspace"))
    assert workspace.status_code == 302
    assert workspace["Location"] == _contactaccountmanagement_url("account_hierarchy")
    assert client.get(
        _contactaccountmanagement_url("account_workspace_export"),
        {"account": contactaccountmanagement_account_a.pk},
    ).status_code == 404
    for route, row in (
        ("party_enrichment_detail", contactaccountmanagement_enrichment_event_a),
        ("account_stakeholder_detail", contactaccountmanagement_stakeholder_a),
        ("account_stakeholder_edit", contactaccountmanagement_stakeholder_a),
        ("account_classification_detail", contactaccountmanagement_classification_a),
        ("account_classification_edit", contactaccountmanagement_classification_a),
        ("account_plan_detail", contactaccountmanagement_plan_a),
        ("account_plan_edit", contactaccountmanagement_plan_a),
    ):
        assert client.get(_contactaccountmanagement_url(route, row.pk)).status_code == 404, route
    for route, key in (
        ("account_stakeholder_create", "accounts"),
        ("account_classification_create", "accounts"),
        ("account_plan_create", "accounts"),
    ):
        response = client.get(_contactaccountmanagement_url(route))
        assert response.status_code == 200, route
        assert list(response.context[key]) == [], route
    before = (
        PartyEnrichmentEvent.objects.count(),
        AccountStakeholder.objects.count(),
        AccountClassification.objects.count(),
        AccountPlan.objects.count(),
    )
    assert client.post(
        _contactaccountmanagement_url("party_enrichment_request"),
        _contactaccountmanagement_proposal_payload(contactaccountmanagement_account_a),
    ).status_code == 302
    assert client.post(
        _contactaccountmanagement_url("account_stakeholder_create"),
        _contactaccountmanagement_stakeholder_payload(contactaccountmanagement_account_a, contactaccountmanagement_stakeholder_a.contact),
    ).status_code == 200
    assert client.post(
        _contactaccountmanagement_url("account_classification_create"),
        _contactaccountmanagement_classification_payload(contactaccountmanagement_account_a),
    ).status_code == 200
    assert client.post(
        _contactaccountmanagement_url("account_plan_create"),
        _contactaccountmanagement_plan_payload(contactaccountmanagement_account_a, contactaccountmanagement_admin_a),
    ).status_code == 200
    for route, row in (
        ("party_enrichment_apply", contactaccountmanagement_enrichment_event_a),
        ("party_enrichment_reject", contactaccountmanagement_enrichment_event_a),
        ("account_stakeholder_delete", contactaccountmanagement_stakeholder_a),
        ("account_classification_delete", contactaccountmanagement_classification_a),
        ("account_plan_delete", contactaccountmanagement_plan_a),
    ):
        payload = {"selected_fields": ["industry"]} if route == "party_enrichment_apply" else {"review_note": "No"} if route == "party_enrichment_reject" else {}
        assert client.post(_contactaccountmanagement_url(route, row.pk), payload).status_code == 404, route
    assert (
        PartyEnrichmentEvent.objects.count(),
        AccountStakeholder.objects.count(),
        AccountClassification.objects.count(),
        AccountPlan.objects.count(),
    ) == before
    assert contactaccountmanagement_admin_a.tenant_id == contactaccountmanagement_tenant_a.pk


def test_contactaccountmanagement_admin_only_routes_reject_members(
    contactaccountmanagement_member_client_a,
    contactaccountmanagement_enrichment_event_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
):
    assert contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("party_enrichment_apply", contactaccountmanagement_enrichment_event_a.pk)
    ).status_code == 405
    assert contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("party_enrichment_apply", contactaccountmanagement_enrichment_event_a.pk),
        {"selected_fields": ["industry"]},
    ).status_code == 403
    for method in ("get", "post"):
        assert getattr(contactaccountmanagement_member_client_a, method)(
            _contactaccountmanagement_url("account_classification_create"),
            _contactaccountmanagement_classification_payload(contactaccountmanagement_classification_a.account)
            if method == "post" else {},
        ).status_code == 403
    for method in ("get", "post"):
        assert getattr(contactaccountmanagement_member_client_a, method)(
            _contactaccountmanagement_url("account_classification_edit", contactaccountmanagement_classification_a.pk),
            _contactaccountmanagement_classification_payload(contactaccountmanagement_classification_a.account)
            if method == "post" else {},
        ).status_code == 403
    assert contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("account_classification_delete", contactaccountmanagement_classification_a.pk)
    ).status_code == 405
    assert contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_classification_delete", contactaccountmanagement_classification_a.pk)
    ).status_code == 403
    assert contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("account_plan_delete", contactaccountmanagement_plan_a.pk)
    ).status_code == 405
    assert contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_delete", contactaccountmanagement_plan_a.pk)
    ).status_code == 403
    contactaccountmanagement_enrichment_event_a.refresh_from_db()
    contactaccountmanagement_classification_a.refresh_from_db()
    contactaccountmanagement_plan_a.refresh_from_db()
    assert contactaccountmanagement_enrichment_event_a.status == "proposed"
    assert contactaccountmanagement_classification_a.tier == "strategic"
    assert contactaccountmanagement_plan_a.status == "draft"


def test_contactaccountmanagement_plan_owner_and_admin_policy(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_member_a,
    contactaccountmanagement_member_client_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
):
    other_member = _contactaccountmanagement_user(
        contactaccountmanagement_tenant_a,
        "security-other-member",
    )
    other_client = Client()
    other_client.force_login(other_member)
    member_created = contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_create"),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            title="Member-owned security plan",
        ),
    )
    assert member_created.status_code == 302
    member_plan = AccountPlan.objects.get(title="Member-owned security plan")
    assert member_plan.owner_id == contactaccountmanagement_member_a.pk
    assert member_plan.status == "draft"
    assert other_client.get(_contactaccountmanagement_url("account_plan_edit", member_plan.pk)).status_code == 403
    assert other_client.post(
        _contactaccountmanagement_url("account_plan_edit", member_plan.pk),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            other_member,
            title="Unauthorized edit",
        ),
    ).status_code == 403
    denied = other_client.post(_contactaccountmanagement_url("account_plan_activate", member_plan.pk))
    assert denied.status_code == 302
    assert _contactaccountmanagement_said(denied, "Only the plan owner or a tenant administrator")
    member_plan.refresh_from_db()
    assert member_plan.status == "draft"
    assert contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_activate", member_plan.pk)
    ).status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "active"
    assert contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_archive", member_plan.pk)
    ).status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.status == "archived"
    archived_edit = contactaccountmanagement_member_client_a.get(
        _contactaccountmanagement_url("account_plan_edit", member_plan.pk)
    )
    assert archived_edit.status_code == 302
    assert archived_edit["Location"] == _contactaccountmanagement_url("account_plan_detail", member_plan.pk)
    assert contactaccountmanagement_member_client_a.post(
        _contactaccountmanagement_url("account_plan_edit", member_plan.pk),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_member_a,
            title="Archived edit",
        ),
    ).status_code == 302
    for route in ("account_plan_activate", "account_plan_review_due", "account_plan_complete", "account_plan_archive"):
        assert contactaccountmanagement_member_client_a.post(_contactaccountmanagement_url(route, member_plan.pk)).status_code == 302
    member_plan.refresh_from_db()
    assert member_plan.title == "Member-owned security plan"
    assert contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_delete", member_plan.pk)
    ).status_code == 302
    assert AccountPlan.objects.filter(pk=member_plan.pk).exists()
    admin_target = _contactaccountmanagement_plan(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_member_a,
        title="Admin-managed security plan",
    )
    admin_edit = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_edit", admin_target.pk),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_member_a,
            title="Admin-managed security plan updated",
        ),
    )
    assert admin_edit.status_code == 302
    admin_target.refresh_from_db()
    assert admin_target.title == "Admin-managed security plan updated"
    assert contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_archive", admin_target.pk)
    ).status_code == 302
    admin_target.refresh_from_db()
    assert admin_target.status == "archived"


def test_contactaccountmanagement_cross_tenant_detail_edit_action_and_board_ids_are_404(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_admin_client_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_enrichment_event_a,
    contactaccountmanagement_enrichment_event_b,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_stakeholder_b,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_classification_b,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_plan_b,
):
    foreign_rows = (
        ("party_enrichment_detail", contactaccountmanagement_enrichment_event_b),
        ("account_stakeholder_detail", contactaccountmanagement_stakeholder_b),
        ("account_stakeholder_edit", contactaccountmanagement_stakeholder_b),
        ("account_classification_detail", contactaccountmanagement_classification_b),
        ("account_classification_edit", contactaccountmanagement_classification_b),
        ("account_plan_detail", contactaccountmanagement_plan_b),
        ("account_plan_edit", contactaccountmanagement_plan_b),
    )
    for route, row in foreign_rows:
        assert contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(route, row.pk)).status_code == 404, route
    action_rows = (
        ("party_enrichment_apply", contactaccountmanagement_enrichment_event_b),
        ("party_enrichment_reject", contactaccountmanagement_enrichment_event_b),
        ("account_stakeholder_delete", contactaccountmanagement_stakeholder_b),
        ("account_classification_delete", contactaccountmanagement_classification_b),
        ("account_plan_delete", contactaccountmanagement_plan_b),
        ("account_plan_activate", contactaccountmanagement_plan_b),
        ("account_plan_review_due", contactaccountmanagement_plan_b),
        ("account_plan_complete", contactaccountmanagement_plan_b),
        ("account_plan_archive", contactaccountmanagement_plan_b),
    )
    for route, row in action_rows:
        before = _contactaccountmanagement_state(row)
        payload = {"selected_fields": ["industry"]} if route == "party_enrichment_apply" else {"review_note": "Foreign action"} if route == "party_enrichment_reject" else {}
        response = contactaccountmanagement_admin_client_a.post(
            _contactaccountmanagement_url(route, row.pk),
            payload,
        )
        assert response.status_code == 404, route
        row.refresh_from_db()
        assert _contactaccountmanagement_state(row) == before, route
    for route in ("account_workspace", "account_coverage", "account_white_space", "account_workspace_export"):
        response = contactaccountmanagement_admin_client_a.get(
            _contactaccountmanagement_url(route),
            {"account": contactaccountmanagement_account_b.pk},
        )
        assert response.status_code == 404, route
    hierarchy = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("account_hierarchy"),
        {"root": contactaccountmanagement_account_b.pk, "parent": contactaccountmanagement_account_b.pk},
    )
    assert hierarchy.status_code == 200
    assert hierarchy.context["selected_account"] is None
    assert contactaccountmanagement_account_b not in list(hierarchy.context["accounts"])
    list_cases = (
        ("party_enrichment_list", {"party": contactaccountmanagement_account_b.pk}),
        ("account_stakeholder_list", {"account": contactaccountmanagement_account_b.pk}),
        ("account_classification_list", {"account": contactaccountmanagement_account_b.pk}),
        ("account_plan_list", {"account": contactaccountmanagement_account_b.pk}),
    )
    for route, params in list_cases:
        response = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(route), params)
        assert response.status_code == 200, route
        assert list(response.context["object_list"]) == [], route
    export_cases = (
        ("party_enrichment_export", {"party": contactaccountmanagement_account_b.pk}),
        ("account_stakeholder_export", {"account": contactaccountmanagement_account_b.pk}),
        ("account_classification_export", {"account": contactaccountmanagement_account_b.pk}),
        ("account_plan_export", {"account": contactaccountmanagement_account_b.pk}),
    )
    for route, params in export_cases:
        response = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(route), params)
        assert response.status_code == 200, route
        rows = _contactaccountmanagement_csv(response)
        assert len(rows) == 1, route
    for route, row in (
        ("party_enrichment_detail", contactaccountmanagement_enrichment_event_a),
        ("account_stakeholder_detail", contactaccountmanagement_stakeholder_a),
        ("account_stakeholder_edit", contactaccountmanagement_stakeholder_a),
        ("account_classification_detail", contactaccountmanagement_classification_a),
        ("account_classification_edit", contactaccountmanagement_classification_a),
        ("account_plan_detail", contactaccountmanagement_plan_a),
        ("account_plan_edit", contactaccountmanagement_plan_a),
    ):
        assert contactaccountmanagement_admin_client_b.get(_contactaccountmanagement_url(route, row.pk)).status_code == 404, route
    assert contactaccountmanagement_account_a.tenant_id != contactaccountmanagement_account_b.tenant_id


def test_contactaccountmanagement_crafted_foreign_fk_payloads_are_rejected_without_mutation(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_consent_purpose_a,
    contactaccountmanagement_consent_purpose_b,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_manager_b,
):
    before = (
        PartyEnrichmentEvent.objects.count(),
        AccountStakeholder.objects.count(),
        AccountClassification.objects.count(),
        AccountPlan.objects.count(),
    )
    proposal = _contactaccountmanagement_proposal_payload(
        contactaccountmanagement_account_b,
        contactaccountmanagement_consent_purpose_b,
        source_kind="provider",
    )
    assert contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("party_enrichment_request"),
        proposal,
    ).status_code == 302
    for account, contact, role in (
        (contactaccountmanagement_account_b, contactaccountmanagement_contact_a, "advisor"),
        (contactaccountmanagement_account_a, contactaccountmanagement_contact_b, "advisor"),
    ):
        response = contactaccountmanagement_admin_client_a.post(
            _contactaccountmanagement_url("account_stakeholder_create"),
            _contactaccountmanagement_stakeholder_payload(account, contact, role=role),
        )
        assert response.status_code == 200
        assert "account" in response.context["form"].errors or "contact" in response.context["form"].errors
    classification_response = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_classification_create"),
        _contactaccountmanagement_classification_payload(
            contactaccountmanagement_account_b,
            tenant=contactaccountmanagement_tenant_b.pk,
            classified_by=contactaccountmanagement_admin_b.pk,
        ),
    )
    assert classification_response.status_code == 200
    assert "account" in classification_response.context["form"].errors
    for account, owner, title in (
        (contactaccountmanagement_account_b, contactaccountmanagement_admin_a, "Foreign account plan"),
        (contactaccountmanagement_account_a, contactaccountmanagement_admin_b, "Foreign owner plan"),
    ):
        response = contactaccountmanagement_admin_client_a.post(
            _contactaccountmanagement_url("account_plan_create"),
            _contactaccountmanagement_plan_payload(account, owner, title=title),
        )
        assert response.status_code == 200
        assert "account" in response.context["form"].errors or "owner" in response.context["form"].errors
    plan = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_create"),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            title="Crafted opportunity plan",
            related_opportunities=[str(contactaccountmanagement_account_b.pk), "not-an-id", "999999999999999999999"],
        ),
    )
    assert plan.status_code == 200
    assert "related_opportunities" in plan.context["form"].errors
    assert (
        PartyEnrichmentEvent.objects.count(),
        AccountStakeholder.objects.count(),
        AccountClassification.objects.count(),
        AccountPlan.objects.count(),
    ) == before
    relationship_before = PartyRelationship.objects.count()
    for from_party, to_party, kind in (
        (contactaccountmanagement_contact_a, contactaccountmanagement_manager_b, "reports_to"),
        (contactaccountmanagement_contact_a, contactaccountmanagement_contact_a, "reports_to"),
    ):
        relationship = PartyRelationship(
            tenant=contactaccountmanagement_tenant_a,
            from_party=from_party,
            to_party=to_party,
            kind=kind,
        )
        with pytest.raises(ValidationError):
            relationship.save()
    assert PartyRelationship.objects.count() == relationship_before
    assert contactaccountmanagement_consent_purpose_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert contactaccountmanagement_consent_purpose_b.tenant_id == contactaccountmanagement_tenant_b.pk


def test_contactaccountmanagement_post_only_routes_require_post_and_csrf(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_member_client_a,
    contactaccountmanagement_enrichment_event_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
):
    for route, fixture_name in _contactaccountmanagement_action_routes:
        pk = None
        if fixture_name == "contactaccountmanagement_enrichment_event_a":
            pk = contactaccountmanagement_enrichment_event_a.pk
        elif fixture_name == "contactaccountmanagement_stakeholder_a":
            pk = contactaccountmanagement_stakeholder_a.pk
        elif fixture_name == "contactaccountmanagement_classification_a":
            pk = contactaccountmanagement_classification_a.pk
        elif fixture_name == "contactaccountmanagement_plan_a":
            pk = contactaccountmanagement_plan_a.pk
        url = _contactaccountmanagement_url(route, pk)
        assert contactaccountmanagement_admin_client_a.get(url).status_code == 405, route
        assert contactaccountmanagement_member_client_a.get(url).status_code == 405, route
        assert contactaccountmanagement_admin_client_a.put(url).status_code == 405, route
        assert contactaccountmanagement_admin_client_a.delete(url).status_code == 405, route
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(contactaccountmanagement_admin_a)
    for route, fixture_name in _contactaccountmanagement_csrf_form_routes:
        pk = None
        if fixture_name == "contactaccountmanagement_stakeholder_a":
            pk = contactaccountmanagement_stakeholder_a.pk
        elif fixture_name == "contactaccountmanagement_classification_a":
            pk = contactaccountmanagement_classification_a.pk
        elif fixture_name == "contactaccountmanagement_plan_a":
            pk = contactaccountmanagement_plan_a.pk
        payload = {}
        if route == "account_stakeholder_create":
            payload = _contactaccountmanagement_stakeholder_payload(contactaccountmanagement_account_a, contactaccountmanagement_contact_a)
        elif route == "account_stakeholder_edit":
            payload = _contactaccountmanagement_stakeholder_payload(contactaccountmanagement_account_a, contactaccountmanagement_contact_a)
        elif route in {"account_classification_create", "account_classification_edit"}:
            payload = _contactaccountmanagement_classification_payload(contactaccountmanagement_account_a)
        elif route in {"account_plan_create", "account_plan_edit"}:
            payload = _contactaccountmanagement_plan_payload(contactaccountmanagement_account_a, contactaccountmanagement_admin_a)
        assert csrf_client.post(_contactaccountmanagement_url(route, pk), payload).status_code == 403, route
    for route, fixture_name in _contactaccountmanagement_action_routes:
        pk = None
        if fixture_name == "contactaccountmanagement_enrichment_event_a":
            pk = contactaccountmanagement_enrichment_event_a.pk
        elif fixture_name == "contactaccountmanagement_stakeholder_a":
            pk = contactaccountmanagement_stakeholder_a.pk
        elif fixture_name == "contactaccountmanagement_classification_a":
            pk = contactaccountmanagement_classification_a.pk
        elif fixture_name == "contactaccountmanagement_plan_a":
            pk = contactaccountmanagement_plan_a.pk
        payload = {"selected_fields": ["industry"]} if route == "party_enrichment_apply" else {"review_note": "Reason"} if route == "party_enrichment_reject" else {}
        assert csrf_client.post(_contactaccountmanagement_url(route, pk), payload).status_code == 403, route
    assert contactaccountmanagement_enrichment_event_a.status == "proposed"
    assert AccountStakeholder.objects.filter(pk=contactaccountmanagement_stakeholder_a.pk).exists()
    assert AccountClassification.objects.filter(pk=contactaccountmanagement_classification_a.pk).exists()
    assert AccountPlan.objects.filter(pk=contactaccountmanagement_plan_a.pk).exists()


def test_contactaccountmanagement_enrichment_hostile_input_cannot_execute_or_leak(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_consent_purpose_a,
    monkeypatch,
):
    monkeypatch.setattr(socket, "create_connection", _contactaccountmanagement_forbid_network)
    monkeypatch.setattr(urllib.request, "urlopen", _contactaccountmanagement_forbid_network)
    hostile_changes = (
        {"unknown_field": {"value": "value"}},
        {"job_title": {"value": {"instructions": "ignore"}}},
        {"job_title": {"value": ["nested"]}},
        {"job_title": {"value": True}},
        {"job_title": {"value": "VP", "confidence": float("nan")}},
        {"job_title": {"value": "VP", "confidence": float("inf")}},
        {"job_title": {"value": "password=LEAKME"}},
        {"job_title": {"value": "x" * 9000}},
        {"website": {"value": "javascript:alert(1)"}},
        {"industry": {"value": "not-supported"}},
    )
    before = PartyEnrichmentEvent.objects.count()
    for index, changes in enumerate(hostile_changes):
        response = contactaccountmanagement_admin_client_a.post(
            _contactaccountmanagement_url("party_enrichment_request"),
            _contactaccountmanagement_proposal_payload(
                contactaccountmanagement_account_a,
                contactaccountmanagement_consent_purpose_a,
                source_kind="provider",
                changes=json.dumps(changes, allow_nan=True),
                source_reference=f"security-hostile:{index}",
            ),
        )
        assert response.status_code == 302, index
    assert PartyEnrichmentEvent.objects.count() == before
    secret = "CONTACT-ENRICHMENT-SECRET-8F4C"
    valid = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("party_enrichment_request"),
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_consent_purpose_a,
            source_kind="provider",
            source_name=f"provider password={secret}",
            source_reference=f"https://provider.example/?api_key={secret}",
        ),
    )
    assert valid.status_code == 302
    event = PartyEnrichmentEvent.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        party=contactaccountmanagement_account_a,
    ).order_by("-pk").first()
    assert event is not None
    assert event.source_kind == "provider"
    assert event.status == "proposed"
    persisted = " ".join(
        str(getattr(event, field.name, ""))
        for field in event._meta.fields
    )
    assert secret not in persisted
    assert event.source_name != f"provider password={secret}"
    assert event.source_reference != f"https://provider.example/?api_key={secret}"
    assert "raw_payload" not in {field.name for field in PartyEnrichmentEvent._meta.fields}
    assert "provider_response" not in {field.name for field in PartyEnrichmentEvent._meta.fields}
    audit = AuditLog.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        content_type=ContentType.objects.get_for_model(PartyEnrichmentEvent),
        object_id=event.pk,
    ).order_by("-at").first()
    assert audit is not None
    assert secret not in json.dumps(audit.changes, default=str)
    assert "changes" not in audit.changes
    assert connection.vendor == "sqlite"
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0
    assert HealthScoreHistory.objects.count() == 0


def test_contactaccountmanagement_enrichment_apply_is_atomic_and_protects_canonical_values(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_consent_purpose_a,
):
    account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Atomic enrichment account",
    )
    profile = _contactaccountmanagement_account_profile(
        contactaccountmanagement_tenant_a,
        account,
        owner=contactaccountmanagement_admin_a,
    )
    protected_event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        account,
        contactaccountmanagement_admin_a,
        changes={
            "employee_count": {"value": 321, "confidence": 0.9},
            "industry": {"value": "finance", "confidence": 0.9},
        },
    )
    with pytest.raises(ValidationError):
        apply_enrichment_event(
            protected_event,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            ["employee_count", "industry"],
        )
    profile.refresh_from_db()
    protected_event.refresh_from_db()
    assert profile.employee_count == 125
    assert profile.industry == "technology"
    assert protected_event.status == "proposed"
    with pytest.raises(ValidationError):
        apply_enrichment_event(
            protected_event,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            ["industry"],
        )
    with pytest.raises(ValidationError):
        apply_enrichment_event(
            protected_event,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_b,
            ["employee_count"],
        )
    contact = _contactaccountmanagement_person_party(
        contactaccountmanagement_tenant_a,
        name="Protected contact enrichment",
    )
    contact_profile = _contactaccountmanagement_contact_profile(
        contactaccountmanagement_tenant_a,
        contact,
        owner=contactaccountmanagement_admin_a,
    )
    contact_event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        contact,
        contactaccountmanagement_admin_a,
        changes={"work_email": {"value": "replacement@acme.example"}},
    )
    with pytest.raises(ValidationError):
        apply_enrichment_event(
            contact_event,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            ["work_email"],
        )
    contact_profile.refresh_from_db()
    assert contact_profile.email == f"contact@{contactaccountmanagement_tenant_a.slug}.example"
    purpose = _contactaccountmanagement_consent_purpose(
        contactaccountmanagement_tenant_a,
        code="atomic-external-purpose",
        name="Atomic external purpose",
    )
    external_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="External enrichment account",
    )
    external_event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        external_account,
        contactaccountmanagement_admin_a,
        source_kind="provider",
        legal_basis_purpose=purpose,
        changes={"employee_count": {"value": 222, "confidence": 0.8}},
    )
    purpose.is_active = False
    purpose.save(update_fields=["is_active"])
    with pytest.raises(ValidationError):
        apply_enrichment_event(
            external_event,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            ["employee_count"],
        )
    external_event.refresh_from_db()
    assert external_event.status == "proposed"
    assert not AccountClassification.objects.filter(account=external_account).exists()
    success_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Successful enrichment account",
    )
    success_event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        success_account,
        contactaccountmanagement_admin_a,
        changes={"employee_count": {"value": 444, "confidence": 1}},
    )
    applied = apply_enrichment_event(
        success_event,
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_admin_a,
        ["employee_count"],
    )
    assert applied.status == "applied"
    assert applied.reviewed_by_id == contactaccountmanagement_admin_a.pk
    assert applied.applied_at is not None
    assert success_account.crm_account_profile.employee_count == 444
    with pytest.raises(ValidationError):
        apply_enrichment_event(
            success_event,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            ["employee_count"],
        )
    success_event.refresh_from_db()
    assert success_event.status == "applied"
    assert contactaccountmanagement_tenant_b.pk != contactaccountmanagement_tenant_a.pk
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0
    assert HealthScoreHistory.objects.count() == 0


def test_contactaccountmanagement_hierarchy_and_reporting_lines_do_not_cross_tenants(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_admin_client_b,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_manager_b,
    contactaccountmanagement_reports_to_a,
):
    root = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Hierarchy security root",
    )
    child = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Hierarchy security child",
    )
    root_profile = _contactaccountmanagement_account_profile(
        contactaccountmanagement_tenant_a,
        root,
        owner=contactaccountmanagement_admin_a,
    )
    child_profile = _contactaccountmanagement_account_profile(
        contactaccountmanagement_tenant_a,
        child,
        parent=root,
        owner=contactaccountmanagement_admin_a,
    )
    root_profile.parent_account = child
    with pytest.raises(ValidationError):
        root_profile.save()
    root_profile.refresh_from_db()
    assert root_profile.parent_account_id is None
    foreign_child = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Hierarchy foreign parent candidate",
    )
    foreign_parent_profile = type(child_profile)(
        tenant=contactaccountmanagement_tenant_a,
        party=foreign_child,
        parent_account=contactaccountmanagement_account_b,
        owner=contactaccountmanagement_admin_a,
    )
    with pytest.raises(ValidationError):
        foreign_parent_profile.save()
    person_profile = type(child_profile)(
        tenant=contactaccountmanagement_tenant_a,
        party=contactaccountmanagement_contact_a,
        owner=contactaccountmanagement_admin_a,
    )
    with pytest.raises(ValidationError):
        person_profile.save()
    relationship_before = PartyRelationship.objects.count()
    for from_party, to_party, kind in (
        (contactaccountmanagement_contact_a, contactaccountmanagement_manager_b, "reports_to"),
        (contactaccountmanagement_contact_a, contactaccountmanagement_contact_a, "reports_to"),
        (contactaccountmanagement_account_a, contactaccountmanagement_manager_a, "reports_to"),
        (contactaccountmanagement_contact_a, contactaccountmanagement_manager_b, "employee_of"),
    ):
        relationship = PartyRelationship(
            tenant=contactaccountmanagement_tenant_a,
            from_party=from_party,
            to_party=to_party,
            kind=kind,
        )
        with pytest.raises(ValidationError):
            relationship.save()
    assert PartyRelationship.objects.count() == relationship_before
    assert contactaccountmanagement_reports_to_a.tenant_id == contactaccountmanagement_tenant_a.pk
    AccountProfile.objects.filter(pk=root_profile.pk).update(parent_account_id=child.pk)
    AccountProfile.objects.filter(pk=child_profile.pk).update(parent_account_id=root.pk)
    rows = account_hierarchy_rows(contactaccountmanagement_tenant_a)
    by_id = {row["party"].pk: row for row in rows}
    assert by_id[root.pk]["cycle_detected"] is True
    assert by_id[child.pk]["cycle_detected"] is True
    assert by_id[root.pk]["rollup_available"] is False
    assert by_id[child.pk]["rollup_available"] is False
    board = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url("account_hierarchy"))
    assert board.status_code == 200
    assert board.context["stats"]["cycles"] >= 2
    assert contactaccountmanagement_account_b not in list(board.context["accounts"])
    tenant_b_board = contactaccountmanagement_admin_client_b.get(
        _contactaccountmanagement_url("account_hierarchy"),
        {"root": root.pk},
    )
    assert tenant_b_board.context["selected_account"] is None
    assert contactaccountmanagement_tenant_b.pk != contactaccountmanagement_tenant_a.pk
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0


def test_contactaccountmanagement_plan_m2m_cannot_cross_tenant_or_account(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_plan_a,
):
    assert Opportunity.objects.count() == 0
    for opportunity_id, opportunity_account_id in (
        (contactaccountmanagement_account_b.pk, contactaccountmanagement_account_a.pk),
        (9_223_372_036_854_775_808, contactaccountmanagement_account_a.pk),
    ):
        with pytest.raises(ValidationError):
            validate_account_plan_opportunities(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_a,
                [SimpleNamespace(pk=opportunity_id, account_id=opportunity_account_id)],
            )
    with pytest.raises(ValidationError):
        validate_account_plan_opportunity_links(
            sender=AccountPlan.related_opportunities.through,
            instance=contactaccountmanagement_plan_a,
            action="pre_add",
            reverse=False,
            model=Opportunity,
            pk_set={contactaccountmanagement_account_b.pk, 9_223_372_036_854_775_808},
        )
    assert contactaccountmanagement_plan_a.related_opportunities.count() == 0
    response = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_create"),
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            title="Rejected M2M security plan",
            related_opportunities=[
                str(contactaccountmanagement_account_b.pk),
                "not-an-id",
                str(9_223_372_036_854_775_808),
            ],
        ),
    )
    assert response.status_code == 200
    assert "related_opportunities" in response.context["form"].errors
    assert not AccountPlan.objects.filter(title="Rejected M2M security plan").exists()
    assert contactaccountmanagement_tenant_b.pk != contactaccountmanagement_tenant_a.pk
    assert Opportunity.objects.count() == 0


def test_contactaccountmanagement_mass_assignment_cannot_set_tenant_status_number_or_actors(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_consent_purpose_a,
):
    account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Mass assignment classification account",
    )
    plan_account = _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Mass assignment plan account",
    )
    enrichment = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("party_enrichment_request"),
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_consent_purpose_a,
            tenant=contactaccountmanagement_tenant_b.pk,
            status="applied",
            match_confidence="not-a-number",
            requested_by=contactaccountmanagement_admin_b.pk,
            reviewed_by=contactaccountmanagement_admin_b.pk,
            occurred_at="2000-01-01T00:00:00Z",
            applied_at="2000-01-01T00:00:00Z",
        ),
    )
    assert enrichment.status_code == 302
    event = PartyEnrichmentEvent.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        party=contactaccountmanagement_account_a,
    ).order_by("-pk").first()
    assert event.tenant_id == contactaccountmanagement_tenant_a.pk
    assert event.status == "proposed"
    assert event.requested_by_id == contactaccountmanagement_admin_a.pk
    assert event.reviewed_by_id is None
    assert event.applied_at is None
    assert event.occurred_at.year >= 2020
    stakeholder = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_stakeholder_create"),
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_manager_a,
            role="advisor",
            tenant=contactaccountmanagement_tenant_b.pk,
        ),
    )
    assert stakeholder.status_code == 302
    stakeholder_row = AccountStakeholder.objects.get(role="advisor", contact=contactaccountmanagement_manager_a)
    assert stakeholder_row.tenant_id == contactaccountmanagement_tenant_a.pk
    classification = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_classification_create"),
        _contactaccountmanagement_classification_payload(
            account,
            tenant=contactaccountmanagement_tenant_b.pk,
            classified_by=contactaccountmanagement_admin_b.pk,
            status="archived",
        ),
    )
    assert classification.status_code == 302
    classification_row = AccountClassification.objects.get(account=account)
    assert classification_row.tenant_id == contactaccountmanagement_tenant_a.pk
    assert classification_row.classified_by_id == contactaccountmanagement_admin_a.pk
    plan = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_plan_create"),
        _contactaccountmanagement_plan_payload(
            plan_account,
            contactaccountmanagement_admin_a,
            title="Mass assignment plan",
            tenant=contactaccountmanagement_tenant_b.pk,
            status="archived",
            number="ACPL-FORGED",
            created_at="2000-01-01T00:00:00Z",
            updated_at="2000-01-01T00:00:00Z",
        ),
    )
    assert plan.status_code == 302
    plan_row = AccountPlan.objects.get(title="Mass assignment plan")
    assert plan_row.tenant_id == contactaccountmanagement_tenant_a.pk
    assert plan_row.status == "draft"
    assert plan_row.number != "ACPL-FORGED"
    assert plan_row.number.startswith("ACPL-")
    assert plan_row.owner_id == contactaccountmanagement_admin_a.pk
    assert contactaccountmanagement_admin_b.tenant_id == contactaccountmanagement_tenant_b.pk


def test_contactaccountmanagement_csv_and_audit_outputs_are_safe(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
):
    secret = "EXPORT-SECRET-2A91"
    contactaccountmanagement_account_a.name = "=Formula Account"
    contactaccountmanagement_account_a.save(update_fields=["name"])
    contactaccountmanagement_contact_a.name = "+Formula Contact"
    contactaccountmanagement_contact_a.save(update_fields=["name"])
    contactaccountmanagement_classification_a.rationale = f"-Formula {secret}"
    contactaccountmanagement_classification_a.save(update_fields=["rationale"])
    contactaccountmanagement_plan_a.title = "@Formula Plan"
    contactaccountmanagement_plan_a.save(update_fields=["title"])
    formula_event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        source_name="=Formula Source",
        source_reference=f"@Formula Reference api_key={secret}",
    )
    for value in _contactaccountmanagement_csv_safe_values():
        assert csv_safe(value).startswith("'")
    export_cases = (
        ("party_enrichment_export", {"party": contactaccountmanagement_account_a.pk}, 1),
        ("account_stakeholder_export", {"account": contactaccountmanagement_account_a.pk}, 1),
        ("account_classification_export", {"account": contactaccountmanagement_account_a.pk}, 1),
        ("account_plan_export", {"account": contactaccountmanagement_account_a.pk}, 1),
        ("account_workspace_export", {"account": contactaccountmanagement_account_a.pk}, 1),
    )
    for route, params, expected_rows in export_cases:
        response = contactaccountmanagement_admin_client_a.get(_contactaccountmanagement_url(route), params)
        assert response.status_code == 200, route
        rows = _contactaccountmanagement_csv(response)
        assert len(rows) == expected_rows + 1, route
    formula_export = contactaccountmanagement_admin_client_a.get(
        _contactaccountmanagement_url("party_enrichment_export"),
        {"party": contactaccountmanagement_account_a.pk},
    )
    formula_rows = _contactaccountmanagement_csv(formula_export)
    assert any("'=Formula Account" in cell for row in formula_rows[1:] for cell in row)
    assert any("'=Formula Source" in cell for row in formula_rows[1:] for cell in row)
    assert secret not in _contactaccountmanagement_body(formula_export)
    audits = [
        row.changes
        for row in AuditLog.objects.filter(
            tenant=contactaccountmanagement_tenant_a,
            action="update",
        ).order_by("-at")
        if row.changes.get("action") == "export"
    ]
    assert audits
    for changes in audits:
        serialized = json.dumps(changes, default=str)
        assert "changes" not in changes
        assert "review_note" not in changes
        assert secret not in serialized
        assert "password" not in serialized.lower()
    assert contactaccountmanagement_stakeholder_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert contactaccountmanagement_classification_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert contactaccountmanagement_plan_a.tenant_id == contactaccountmanagement_tenant_a.pk
    assert formula_event.status == "proposed"


def test_contactaccountmanagement_duplicate_and_race_guarded_writes_are_idempotent(
    contactaccountmanagement_admin_client_a,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
):
    event = create_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_admin_a,
        party=contactaccountmanagement_account_a,
        kind="firmographic",
        source_kind="manual",
        source_name="Idempotency security",
        source_reference="idempotency-security",
        changes={"employee_count": {"value": 100}},
        idempotency_key="security-idempotency-key",
    )
    replay = create_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_admin_a,
        party=contactaccountmanagement_account_a,
        kind="firmographic",
        source_kind="manual",
        source_name="Idempotency security",
        source_reference="idempotency-security",
        changes={"employee_count": {"value": 100}},
        idempotency_key="security-idempotency-key",
    )
    assert replay.pk == event.pk
    with pytest.raises(ValidationError):
        create_enrichment_event(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            party=contactaccountmanagement_account_a,
            kind="firmographic",
            source_kind="manual",
            source_name="Different evidence",
            source_reference="idempotency-security",
            changes={"employee_count": {"value": 101}},
            idempotency_key="security-idempotency-key",
        )
    assert PartyEnrichmentEvent.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        idempotency_key="security-idempotency-key",
    ).count() == 1
    reject_enrichment_event(
        event,
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_admin_a,
        "No trustworthy source",
    )
    with pytest.raises(ValidationError):
        reject_enrichment_event(
            event,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            "Replay",
        )
    event.refresh_from_db()
    assert event.status == "rejected"
    duplicate_classification = contactaccountmanagement_admin_client_a.post(
        _contactaccountmanagement_url("account_classification_create"),
        _contactaccountmanagement_classification_payload(
            contactaccountmanagement_classification_a.account,
            rationale="Duplicate security submission",
        ),
    )
    assert duplicate_classification.status_code == 302
    assert duplicate_classification["Location"] == _contactaccountmanagement_url(
        "account_classification_edit",
        contactaccountmanagement_classification_a.pk,
    )
    assert AccountClassification.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account=contactaccountmanagement_classification_a.account,
    ).count() == 1
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AccountStakeholder(
                tenant=contactaccountmanagement_stakeholder_a.tenant,
                account=contactaccountmanagement_stakeholder_a.account,
                contact=contactaccountmanagement_stakeholder_a.contact,
                role=contactaccountmanagement_stakeholder_a.role,
            ).save()
    first_plan = _contactaccountmanagement_plan(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        title="Number allocation one",
    )
    second_plan = _contactaccountmanagement_plan(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        title="Number allocation two",
    )
    assert first_plan.number != second_plan.number
    transition_account_plan(
        first_plan,
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_admin_a,
        "active",
    )
    with pytest.raises(ValidationError):
        transition_account_plan(
            first_plan,
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_admin_a,
            "active",
        )
    first_plan.refresh_from_db()
    assert first_plan.status == "active"
    assert AccountPlan.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        number__in=(first_plan.number, second_plan.number),
    ).count() == 2
    assert Opportunity.objects.count() == 0
    assert SalesOrder.objects.count() == 0
    assert Invoice.objects.count() == 0
    assert HealthScore.objects.count() == 0
    assert HealthScoreHistory.objects.count() == 0
