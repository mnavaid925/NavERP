"""8.5 Quote & Proposal Management (CPQ) -- the VIEWS lane.

Naming: every test is ``test_quoteproposalcpq_*`` and every module-level helper
``_quoteproposalcpq_*``. Record factories are imported from the models lane.

The discipline of this lane is L8: a 200 proves the template compiled, not that
the context variable resolved. Every page assertion here therefore checks that
a named piece of the record actually appears in the rendered HTML -- the quote
number, the line description, the rule name.

It also pins the operational behaviour the Phase 4 review fixed, because each
of those is a silent wrong-answer rather than a crash:
  * C10 / I13 -- the version register and the three operational boards page.
  * M7  -- two quotes from different revision families refuse to be diffed.
  * M6  -- a foreign ``?quote=`` pk is never pre-filled into guided selling.
  * I15 -- previewing a proposal does not advance the quote's status.
  * C8  -- approval actions are refused once a quote is no longer pending.
  * C7  -- the public portal refuses to sign or toggle an ineligible quote.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sales.models.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLine
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.QuoteProposalCPQ.ProductBundles import ProductBundleOption
from apps.sales.models.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRule

from apps.sales.tests.test_quote_proposal_cpq_models import (
    _quoteproposalcpq_bundle,
    _quoteproposalcpq_currency,
    _quoteproposalcpq_item,
    _quoteproposalcpq_line,
    _quoteproposalcpq_opportunity,
    _quoteproposalcpq_party,
    _quoteproposalcpq_price_book,
    _quoteproposalcpq_product,
    _quoteproposalcpq_quote,
    _quoteproposalcpq_rule,
    _quoteproposalcpq_user,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Client / record helpers
# ---------------------------------------------------------------------------

def _quoteproposalcpq_admin(tenant, key="admin_acme"):
    return _quoteproposalcpq_user(tenant, key, is_admin=True)


def _quoteproposalcpq_client(user):
    from django.test import Client

    client = Client()
    client.force_login(user)
    return client


def _quoteproposalcpq_revision_family(tenant, currency, name="Rack deal", revisions=2):
    """A quote plus its cloned revisions, sharing one quote_group_id."""
    from apps.sales.cpq_services import cpq_create_revision

    latest = _quoteproposalcpq_quote(tenant, currency, name=name)
    for _ in range(revisions - 1):
        latest = cpq_create_revision(latest, user=None)
    return latest


def _quoteproposalcpq_other_family(tenant, currency):
    return _quoteproposalcpq_quote(tenant, currency, name="Unrelated deal")


# ---------------------------------------------------------------------------
# CPQ quote list
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_list_renders_with_content(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Visible proposal")
    body = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_list")).content.decode()
    assert quote.number in body
    assert "Visible proposal" in body


def test_quoteproposalcpq_quote_list_pins_its_context_keys(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_list"))
    assert response.status_code == 200
    for key in ("quotes", "status_choices", "approval_status_choices", "opportunities", "stats"):
        assert key in response.context, key
    for stat_key in ("total", "draft", "approved", "converted"):
        assert stat_key in response.context["stats"], stat_key


def test_quoteproposalcpq_quote_list_search_narrows_by_name(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    wanted = _quoteproposalcpq_quote(tenant_a, currency, name="Findable proposal")
    other = _quoteproposalcpq_quote(tenant_a, currency, name="Unrelated proposal")
    body = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_list"), {"q": "Findable"}).content.decode()
    assert wanted.number in body
    assert other.number not in body


def test_quoteproposalcpq_quote_list_search_narrows_by_number(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    wanted = _quoteproposalcpq_quote(tenant_a, currency, name="First")
    _quoteproposalcpq_quote(tenant_a, currency, name="Second")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"q": wanted.number}
    ).content.decode()
    assert wanted.number in body


def test_quoteproposalcpq_quote_list_status_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    draft = _quoteproposalcpq_quote(tenant_a, currency, name="Still a draft", status="draft")
    approved = _quoteproposalcpq_quote(tenant_a, currency, name="Already approved", status="approved")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"status": "draft"}
    ).content.decode()
    assert draft.number in body
    assert approved.number not in body


def test_quoteproposalcpq_quote_list_approval_status_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    pending = _quoteproposalcpq_quote(
        tenant_a, currency, name="Awaiting", status="in_review", approval_status="pending"
    )
    settled = _quoteproposalcpq_quote(
        tenant_a, currency, name="Settled", status="approved", approval_status="approved"
    )
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"approval_status": "pending"}
    ).content.decode()
    assert pending.number in body
    assert settled.number not in body


def test_quoteproposalcpq_quote_list_is_primary_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    primary = _quoteproposalcpq_quote(tenant_a, currency, name="Primary", is_primary=True)
    secondary = _quoteproposalcpq_quote(tenant_a, currency, name="Secondary", is_primary=False)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"is_primary": "true"}
    ).content.decode()
    assert primary.number in body
    assert secondary.number not in body


def test_quoteproposalcpq_quote_list_opportunity_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    opportunity = _quoteproposalcpq_opportunity(tenant_a, name="Rack deal")
    linked = _quoteproposalcpq_quote(tenant_a, currency, name="Linked", opportunity=opportunity)
    unlinked = _quoteproposalcpq_quote(tenant_a, currency, name="Unlinked")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"opportunity": str(opportunity.pk)}
    ).content.decode()
    assert linked.number in body
    assert unlinked.number not in body



@pytest.mark.parametrize(
    "params",
    [
        {"status": "not-a-status"},
        {"approval_status": "not-a-status"},
        {"opportunity": "abc"},
        {"is_primary": "maybe"},
        {"page": "999"},
        {"page": "abc"},
        {"q": ""},
    ],
)
def test_quoteproposalcpq_quote_list_survives_junk_parameters(db, tenant_a, params):
    """I2: a non-numeric pk param used to reach .filter() and 500 the list."""
    admin = _quoteproposalcpq_admin(tenant_a)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_list"), params)
    assert response.status_code == 200


def test_quoteproposalcpq_quote_list_pages(db, tenant_a):
    """The list paginates at 15, so page 2 must be reachable and distinct."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    for index in range(20):
        _quoteproposalcpq_quote(tenant_a, currency, name=f"Bulk proposal {index:02d}")
    client = _quoteproposalcpq_client(admin)
    first = client.get(reverse("sales:cpq_quote_list")).content.decode()
    second = client.get(reverse("sales:cpq_quote_list"), {"page": 2})
    assert second.status_code == 200
    assert second.context["quotes"].number == 2
    assert first != second.content.decode()


# ---------------------------------------------------------------------------
# Quote create / detail / edit / delete
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_create_renders(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_create"))
    assert response.status_code == 200
    assert "form" in response.context


def test_quoteproposalcpq_quote_create_persists_a_quote(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    client = _quoteproposalcpq_client(admin)
    response = client.post(
        reverse("sales:cpq_quote_create"),
        {"name": "Created proposal", "currency": str(currency.pk), "header_discount_pct": "", "owner": ""},
    )
    assert response.status_code == 302
    quote = CPQQuote.objects.get(tenant=tenant_a, name="Created proposal")
    assert quote.status == "draft"
    assert quote.number.startswith("CPQ-")
    # the view stamps the owner itself when the form did not
    assert quote.owner == admin


def test_quoteproposalcpq_quote_create_assigns_owner_to_the_acting_rep(db, tenant_a):
    """The M8 guard pins owner to the acting user for a non-admin; the view must
    not then overwrite it with someone else."""
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    currency = _quoteproposalcpq_currency()
    client = _quoteproposalcpq_client(rep)
    client.post(
        reverse("sales:cpq_quote_create"),
        {"name": "Rep owned", "currency": str(currency.pk), "header_discount_pct": "", "owner": ""},
    )
    quote = CPQQuote.objects.get(tenant=tenant_a, name="Rep owned")
    assert quote.owner == rep


def test_quoteproposalcpq_quote_detail_renders_its_lines(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Workspace")
    _quoteproposalcpq_line(tenant_a, quote, description="Distinctive blade server")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_detail", args=[quote.pk])
    ).content.decode()
    assert quote.number in body
    assert "Distinctive blade server" in body


def test_quoteproposalcpq_quote_detail_pins_its_context_keys(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_detail", args=[quote.pk]))
    for key in ("quote", "lines", "revisions", "can_edit", "can_approve", "can_convert"):
        assert key in response.context, key


def test_quoteproposalcpq_quote_detail_lists_the_revision_family(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    latest = _quoteproposalcpq_revision_family(tenant_a, currency, revisions=2)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_detail", args=[latest.pk])
    ).content.decode()
    assert latest.number in body


def test_quoteproposalcpq_quote_detail_is_read_only_for_totals(db, tenant_a):
    """C11: the detail page recalculates for display but must not write on GET."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, total=Decimal("0.00"))
    _quoteproposalcpq_line(tenant_a, quote, quantity=Decimal("3.00"), unit_price=Decimal("100.00"))
    client = _quoteproposalcpq_client(admin)
    client.get(reverse("sales:cpq_quote_detail", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.total == Decimal("0.00")



def test_quoteproposalcpq_quote_edit_renders_for_a_draft(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_edit", args=[quote.pk]))
    assert response.status_code == 200
    assert response.context["is_create"] is False


def test_quoteproposalcpq_quote_edit_saves_a_rename(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Before")
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:cpq_quote_edit", args=[quote.pk]),
        {"name": "After", "currency": str(currency.pk), "header_discount_pct": "", "owner": ""},
    )
    assert response.status_code == 302
    quote.refresh_from_db()
    assert quote.name == "After"


def test_quoteproposalcpq_quote_edit_is_refused_on_a_locked_quote_for_a_rep(db, tenant_a):
    """An approved quote is immutable to a rep -- the fix is a new revision."""
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Locked", status="approved")
    response = _quoteproposalcpq_client(rep).post(
        reverse("sales:cpq_quote_edit", args=[quote.pk]),
        {"name": "Tampered", "currency": str(currency.pk), "header_discount_pct": "", "owner": ""},
    )
    assert response.status_code == 302
    quote.refresh_from_db()
    assert quote.name == "Locked"


def test_quoteproposalcpq_quote_delete_removes_a_draft(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    response = _quoteproposalcpq_client(admin).post(reverse("sales:cpq_quote_delete", args=[quote.pk]))
    assert response.status_code == 302
    assert not CPQQuote.objects.filter(pk=quote.pk).exists()


def test_quoteproposalcpq_quote_delete_is_post_only(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_delete", args=[quote.pk]))
    assert response.status_code == 405
    assert CPQQuote.objects.filter(pk=quote.pk).exists()


@pytest.mark.parametrize("status", ["in_review", "approved", "presented", "accepted", "converted"])
def test_quoteproposalcpq_quote_delete_refuses_a_committed_quote(db, tenant_a, status):
    """I7: only draft or rejected quotes may be destroyed."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status=status)
    response = _quoteproposalcpq_client(admin).post(reverse("sales:cpq_quote_delete", args=[quote.pk]))
    assert response.status_code == 302
    assert CPQQuote.objects.filter(pk=quote.pk).exists()


def test_quoteproposalcpq_quote_delete_allows_a_rejected_quote(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="rejected")
    _quoteproposalcpq_client(admin).post(reverse("sales:cpq_quote_delete", args=[quote.pk]))
    assert not CPQQuote.objects.filter(pk=quote.pk).exists()



# ---------------------------------------------------------------------------
# Quote lines
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_line_list_renders_with_content(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    _quoteproposalcpq_line(tenant_a, quote, description="Nightly reconciliation")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk])
    ).content.decode()
    assert "Nightly reconciliation" in body


def test_quoteproposalcpq_quote_line_list_pins_its_context_keys(db, tenant_a):
    """M1 removed the dead `stats` key together with the queries that fed it,
    so the context contract here is exactly quote + lines."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_line_list", args=[quote.pk]))
    assert "quote" in response.context
    assert "lines" in response.context
    assert "stats" not in response.context


def test_quoteproposalcpq_quote_line_create_persists_and_recalculates(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:cpq_quote_line_create", args=[quote.pk]),
        {
            "line_type": "standard",
            "description": "Installation",
            "quantity": "2.00",
            "unit_price": "150.00",
            "list_price": "150.00",
            "discount_pct": "0",
            "tax_pct": "0",
            "unit_cost": "50.00",
            "sequence": "10",
            "is_selected": True,
        },
    )
    assert response.status_code == 302
    line = CPQQuoteLine.objects.get(quote=quote, description="Installation")
    assert line.tenant == tenant_a
    quote.refresh_from_db()
    assert quote.subtotal == Decimal("300.00")


def test_quoteproposalcpq_quote_line_create_is_refused_on_a_locked_quote_for_a_rep(db, tenant_a):
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="approved")
    response = _quoteproposalcpq_client(rep).post(
        reverse("sales:cpq_quote_line_create", args=[quote.pk]),
        {"line_type": "standard", "description": "Sneaky", "quantity": "1", "unit_price": "1", "sequence": "10"},
    )
    assert response.status_code == 302
    assert not CPQQuoteLine.objects.filter(quote=quote).exists()


def test_quoteproposalcpq_quote_line_detail_renders(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    line = _quoteproposalcpq_line(tenant_a, quote, description="Warranty extension")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_line_detail", args=[quote.pk, line.pk])
    ).content.decode()
    assert "Warranty extension" in body


def test_quoteproposalcpq_quote_line_delete_recalculates_the_header(db, tenant_a):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    kept = _quoteproposalcpq_line(
        tenant_a, quote, description="Keep", quantity=Decimal("1.00"), unit_price=Decimal("100.00"), sequence=10
    )
    doomed = _quoteproposalcpq_line(
        tenant_a, quote, description="Remove", quantity=Decimal("1.00"), unit_price=Decimal("50.00"), sequence=20
    )
    cpq_recalc_quote_totals(quote, save=True)
    assert quote.total == Decimal("150.00")
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:cpq_quote_line_delete", args=[quote.pk, doomed.pk])
    )
    assert response.status_code == 302
    assert not CPQQuoteLine.objects.filter(pk=doomed.pk).exists()
    assert CPQQuoteLine.objects.filter(pk=kept.pk).exists()
    quote.refresh_from_db()
    assert quote.total == Decimal("100.00")



# ---------------------------------------------------------------------------
# Product bundle options
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_bundle_list_renders_with_content(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    _quoteproposalcpq_bundle(tenant_a, bundle, component, name="Rack blade option")
    body = _quoteproposalcpq_client(admin).get(reverse("sales:product_bundle_list")).content.decode()
    assert "Rack blade option" in body


def test_quoteproposalcpq_bundle_list_pins_its_context_keys(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:product_bundle_list"))
    for key in ("bundles", "bundle_products", "option_groups", "compatibility_choices", "stats"):
        assert key in response.context, key
    for stat_key in ("total", "active", "required", "with_rules"):
        assert stat_key in response.context["stats"], stat_key


def test_quoteproposalcpq_bundle_list_filters_narrow(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    wanted = _quoteproposalcpq_bundle(tenant_a, bundle, component, name="Wanted", option_group="Hardware")
    other = _quoteproposalcpq_product(tenant_a, "Other Rack")
    other_component = _quoteproposalcpq_product(tenant_a, "Other Blade")
    _quoteproposalcpq_bundle(tenant_a, other, other_component, name="Unwanted", option_group="Support")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:product_bundle_list"), {"option_group": "Hardware"}
    ).content.decode()
    assert wanted.name in body
    assert "Unwanted" not in body


def test_quoteproposalcpq_bundle_list_survives_junk_parameters(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    for params in ({"bundle": "abc"}, {"page": "abc"}, {"compatibility_rule": "nope"}, {"is_active": "x"}):
        response = _quoteproposalcpq_client(admin).get(reverse("sales:product_bundle_list"), params)
        assert response.status_code == 200


def test_quoteproposalcpq_bundle_detail_renders_with_siblings(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    first_component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    second_component = _quoteproposalcpq_product(tenant_a, "Rack Switch")
    first = _quoteproposalcpq_bundle(tenant_a, bundle, first_component, name="Blade option")
    _quoteproposalcpq_bundle(tenant_a, bundle, second_component, name="Switch option")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:product_bundle_detail", args=[first.pk])
    ).content.decode()
    assert "Blade option" in body
    assert "Switch option" in body



def test_quoteproposalcpq_bundle_create_persists(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:product_bundle_create"),
        {
            "name": "New option",
            "bundle_product": str(bundle.pk),
            "component_product": str(component.pk),
            "option_group": "Hardware",
            "min_quantity": "1",
            "max_quantity": "4",
            "default_quantity": "1",
            "compatibility_rule": "none",
            "sort_order": "10",
            "is_active": True,
        },
    )
    assert response.status_code == 302
    option = ProductBundleOption.objects.get(tenant=tenant_a, name="New option")
    assert option.number.startswith("BND-")


def test_quoteproposalcpq_bundle_delete_is_post_only(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    option = _quoteproposalcpq_bundle(tenant_a, bundle, component)
    client = _quoteproposalcpq_client(admin)
    assert client.get(reverse("sales:product_bundle_delete", args=[option.pk])).status_code == 405
    assert ProductBundleOption.objects.filter(pk=option.pk).exists()
    client.post(reverse("sales:product_bundle_delete", args=[option.pk]))
    assert not ProductBundleOption.objects.filter(pk=option.pk).exists()


# ---------------------------------------------------------------------------
# Quote approval rules
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_rule_list_renders_with_content(db, tenant_a):
    """C13: the I9 pass added a select_related("currency") to a model with no such
    FK, so this page 500'd for everyone. Rendering it is the regression test."""
    admin = _quoteproposalcpq_admin(tenant_a)
    _quoteproposalcpq_rule(tenant_a, name="Executive discount floor")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_approval_rule_list"))
    assert response.status_code == 200
    assert "Executive discount floor" in response.content.decode()


def test_quoteproposalcpq_rule_detail_renders(db, tenant_a):
    """C13 on the detail page too."""
    admin = _quoteproposalcpq_admin(tenant_a)
    rule = _quoteproposalcpq_rule(tenant_a, name="Margin floor")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_approval_rule_detail", args=[rule.pk]))
    assert response.status_code == 200
    assert "Margin floor" in response.content.decode()


def test_quoteproposalcpq_rule_list_pins_its_context_keys(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_approval_rule_list"))
    for key in ("rules", "rule_type_choices", "approver_role_choices", "stats"):
        assert key in response.context, key
    for stat_key in ("total", "active", "max_discount", "min_margin"):
        assert stat_key in response.context["stats"], stat_key


def test_quoteproposalcpq_rule_list_filters_narrow(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    _quoteproposalcpq_rule(tenant_a, name="Discount floor", rule_type="max_discount")
    _quoteproposalcpq_rule(tenant_a, name="Margin floor", rule_type="min_margin")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_approval_rule_list"), {"rule_type": "min_margin"}
    ).content.decode()
    assert "Margin floor" in body
    assert "Discount floor" not in body


def test_quoteproposalcpq_rule_create_persists(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:quote_approval_rule_create"),
        {
            "name": "New discount floor",
            "rule_type": "max_discount",
            "discount_threshold_pct": "25",
            "min_margin_pct": "10",
            "approver_role": "vp_sales",
            "priority": "20",
            "is_active": True,
        },
    )
    assert response.status_code == 302
    rule = QuoteApprovalRule.objects.get(tenant=tenant_a, name="New discount floor")
    assert rule.number.startswith("QAR-")


def test_quoteproposalcpq_rule_delete_is_post_only(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    rule = _quoteproposalcpq_rule(tenant_a, name="Doomed rule")
    client = _quoteproposalcpq_client(admin)
    assert client.get(reverse("sales:quote_approval_rule_delete", args=[rule.pk])).status_code == 405
    client.post(reverse("sales:quote_approval_rule_delete", args=[rule.pk]))
    assert not QuoteApprovalRule.objects.filter(pk=rule.pk).exists()



# ---------------------------------------------------------------------------
# Approval governance
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_submit_approval_auto_approves_within_thresholds(db, tenant_a):
    """With no active rule, a priced quote is approved on submit."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    _quoteproposalcpq_line(tenant_a, quote, discount_pct=Decimal("0"))
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:quote_submit_approval", args=[quote.pk])
    )
    assert response.status_code == 302
    quote.refresh_from_db()
    assert quote.status == "approved"
    assert quote.approval_status == "approved"
    assert quote.approved_by == admin


def test_quoteproposalcpq_submit_approval_routes_over_threshold_to_review(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    _quoteproposalcpq_rule(tenant_a, name="Discount floor", discount_threshold_pct=Decimal("10"))
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    _quoteproposalcpq_line(tenant_a, quote, discount_pct=Decimal("40"))
    _quoteproposalcpq_client(admin).post(reverse("sales:quote_submit_approval", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.status == "in_review"
    assert quote.approval_status == "pending"
    assert quote.approval_rule is not None


def test_quoteproposalcpq_submit_approval_honours_auto_reject(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    _quoteproposalcpq_rule(
        tenant_a, name="Hard floor", discount_threshold_pct=Decimal("10"), auto_reject=True
    )
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    _quoteproposalcpq_line(tenant_a, quote, discount_pct=Decimal("55"))
    _quoteproposalcpq_client(admin).post(reverse("sales:quote_submit_approval", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.status == "rejected"
    assert quote.approval_status == "rejected"


def test_quoteproposalcpq_submit_approval_refuses_an_empty_quote(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    _quoteproposalcpq_client(admin).post(reverse("sales:quote_submit_approval", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.status == "draft"


@pytest.mark.parametrize("status", ["approved", "in_review", "presented", "converted"])
def test_quoteproposalcpq_submit_approval_refuses_an_ineligible_status(db, tenant_a, status):
    """C8: submitting from a status other than draft/rejected used to silently
    re-evaluate rules on a quote already in flight."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status=status)
    _quoteproposalcpq_line(tenant_a, quote)
    before_approval = quote.approval_status
    _quoteproposalcpq_client(admin).post(reverse("sales:quote_submit_approval", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.status == status
    assert quote.approval_status == before_approval


def test_quoteproposalcpq_submit_approval_is_post_only(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    _quoteproposalcpq_line(tenant_a, quote)
    assert _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_submit_approval", args=[quote.pk])
    ).status_code == 405


def test_quoteproposalcpq_approval_queue_renders_pending_quotes(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    pending = _quoteproposalcpq_quote(
        tenant_a, currency, name="Needs a decision", status="in_review", approval_status="pending"
    )
    settled = _quoteproposalcpq_quote(
        tenant_a, currency, name="Already decided", status="approved", approval_status="approved"
    )
    body = _quoteproposalcpq_client(admin).get(reverse("sales:quote_approval_queue")).content.decode()
    assert pending.number in body
    assert settled.number not in body



def test_quoteproposalcpq_approval_queue_pages(db, tenant_a):
    """I13: the three operational boards paginate at 15."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    for index in range(20):
        _quoteproposalcpq_quote(
            tenant_a,
            currency,
            name=f"Pending {index:02d}",
            status="in_review",
            approval_status="pending",
        )
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_approval_queue"), {"page": 2})
    assert response.status_code == 200
    assert response.context["page_obj"].number == 2


def test_quoteproposalcpq_approval_action_approves_a_pending_quote(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="in_review", approval_status="pending")
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:quote_approval_action", args=[quote.pk]),
        {"action": "approved", "note": "Margin is fine."},
    )
    assert response.status_code == 302
    quote.refresh_from_db()
    assert quote.status == "approved"
    assert quote.approval_status == "approved"
    assert quote.approved_by == admin


def test_quoteproposalcpq_approval_action_rejects_with_a_note(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="in_review", approval_status="pending")
    _quoteproposalcpq_client(admin).post(
        reverse("sales:quote_approval_action", args=[quote.pk]),
        {"action": "rejected", "note": "Discount too deep."},
    )
    quote.refresh_from_db()
    assert quote.status == "rejected"
    assert quote.approval_note == "Discount too deep."


@pytest.mark.parametrize("approval_status", ["not_required", "approved", "rejected"])
def test_quoteproposalcpq_approval_action_refuses_a_settled_quote(db, tenant_a, approval_status):
    """C8: acting on a quote that is no longer pending used to overwrite the
    earlier decision."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(
        tenant_a, currency, status="approved", approval_status=approval_status
    )
    _quoteproposalcpq_client(admin).post(
        reverse("sales:quote_approval_action", args=[quote.pk]),
        {"action": "rejected", "note": "Second thoughts."},
    )
    quote.refresh_from_db()
    assert quote.approval_status == approval_status
    assert quote.status == "approved"


def test_quoteproposalcpq_approval_action_is_tenant_admin_only(db, tenant_a):
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="in_review", approval_status="pending")
    response = _quoteproposalcpq_client(rep).post(
        reverse("sales:quote_approval_action", args=[quote.pk]),
        {"action": "approved", "note": "Self approval."},
    )
    assert response.status_code == 403
    quote.refresh_from_db()
    assert quote.approval_status == "pending"



# ---------------------------------------------------------------------------
# Versioning and comparison
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_create_revision_clones_and_supersedes(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    original = _quoteproposalcpq_quote(tenant_a, currency, name="Rack deal")
    _quoteproposalcpq_line(tenant_a, original, description="Original line")
    group = original.quote_group_id

    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:quote_create_revision", args=[original.pk])
    )
    assert response.status_code == 302
    original.refresh_from_db()
    new_quote = CPQQuote.objects.get(tenant=tenant_a, revision_of=original)
    assert original.status == "superseded"
    assert new_quote.revision_number == 2
    assert new_quote.quote_group_id == group
    assert new_quote.lines.count() == 1


def test_quoteproposalcpq_create_revision_is_post_only(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    assert _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_create_revision", args=[quote.pk])
    ).status_code == 405


def test_quoteproposalcpq_compare_renders_two_revisions_of_one_family(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    latest = _quoteproposalcpq_revision_family(tenant_a, currency, revisions=2)
    root = CPQQuote.objects.get(tenant=tenant_a, quote_group_id=latest.quote_group_id, revision_number=1)
    response = _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_compare_versions", args=[root.pk, latest.pk])
    )
    assert response.status_code == 200
    for key in ("quote_a", "quote_b", "diff_data"):
        assert key in response.context, key


def test_quoteproposalcpq_compare_refuses_two_different_families(db, tenant_a):
    """M7: diffing across unrelated families produced a meaningless side-by-side
    that read as if one quote had become the other."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    first = _quoteproposalcpq_quote(tenant_a, currency, name="Deal A")
    second = _quoteproposalcpq_other_family(tenant_a, currency)
    assert first.quote_group_id != second.quote_group_id
    response = _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_compare_versions", args=[first.pk, second.pk])
    )
    assert response.status_code == 302


def test_quoteproposalcpq_compare_keeps_both_lines_that_share_a_description(db, tenant_a):
    """M5: keying the diff on description collapsed two identical lines into one
    dict entry, silently dropping a line from the comparison."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    first = _quoteproposalcpq_quote(tenant_a, currency, name="Deal")
    for sequence in (10, 20):
        _quoteproposalcpq_line(
            tenant_a, first, description="Identical label", sequence=sequence, unit_price=Decimal("10.00")
        )
    second = _quoteproposalcpq_quote(
        tenant_a, currency, name="Deal", quote_group_id=first.quote_group_id, revision_number=2
    )
    for sequence in (10, 20):
        _quoteproposalcpq_line(
            tenant_a, second, description="Identical label", sequence=sequence, unit_price=Decimal("20.00")
        )
    response = _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_compare_versions", args=[first.pk, second.pk])
    )
    assert response.status_code == 200
    diff_data = response.context["diff_data"]
    assert set(diff_data) == {
        "quote_a",
        "quote_b",
        "subtotal_delta",
        "total_delta",
        "margin_delta",
        "line_diffs",
    }
    # both same-description lines survive as their own rows, and the price move shows
    assert len(diff_data["line_diffs"]) == 2
    assert {row["status"] for row in diff_data["line_diffs"]} == {"modified"}
    assert all(row["price_delta"] == Decimal("10.00") for row in diff_data["line_diffs"])


def test_quoteproposalcpq_version_list_renders_families_and_pages(db, tenant_a):
    """C10/I13: the register used to run one query per family with no paging."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    for index in range(22):
        _quoteproposalcpq_quote(tenant_a, currency, name=f"Family {index:02d}")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_version_list"))
    assert response.status_code == 200
    assert "families" in response.context
    second = _quoteproposalcpq_client(admin).get(reverse("sales:quote_version_list"), {"page": 2})
    assert second.status_code == 200
    assert second.context["page_obj"].number == 2



# ---------------------------------------------------------------------------
# Proposals and the public e-signature portal
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_proposal_board_lists_presentable_quotes(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    ready = _quoteproposalcpq_quote(tenant_a, currency, name="Ready to present", status="approved")
    draft = _quoteproposalcpq_quote(tenant_a, currency, name="Still a draft", status="draft")
    body = _quoteproposalcpq_client(admin).get(reverse("sales:quote_proposal_board")).content.decode()
    assert ready.number in body
    assert draft.number not in body


def test_quoteproposalcpq_proposal_board_pages(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    for index in range(20):
        _quoteproposalcpq_quote(tenant_a, currency, name=f"Proposal {index:02d}", status="approved")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_proposal_board"), {"page": 2})
    assert response.status_code == 200
    assert response.context["page_obj"].number == 2


def test_quoteproposalcpq_generate_proposal_renders_content(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Branded proposal", status="approved")
    _quoteproposalcpq_line(tenant_a, quote, description="Managed support")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_generate_proposal", args=[quote.pk]))
    assert response.status_code == 200
    assert "proposal_html" in response.context
    body = response.content.decode()
    assert "Branded proposal" in body
    assert "Managed support" in body


def test_quoteproposalcpq_generate_proposal_does_not_advance_status(db, tenant_a):
    """I15: preview used to auto-transition approved -> presented on a GET."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Read only preview", status="approved")
    _quoteproposalcpq_client(admin).get(reverse("sales:quote_generate_proposal", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.status == "approved"


def test_quoteproposalcpq_generate_proposal_escapes_user_content(db, tenant_a):
    """C5: proposal_html is injected with |safe, so every dynamic field must be
    escaped at render time or this is a stored XSS."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(
        tenant_a,
        currency,
        name="Proposal",
        status="approved",
        terms_and_conditions="<script>alert('xss')</script>",
        signer_name="<script>alert('signer')</script>",
    )
    _quoteproposalcpq_line(tenant_a, quote, description="<script>alert('line')</script>")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_generate_proposal", args=[quote.pk]))
    body = response.content.decode()
    assert "<script>alert('xss')</script>" not in body
    assert "<script>alert('signer')</script>" not in body
    assert "<script>alert('line')</script>" not in body



def _quoteproposalcpq_portal_sign(client, quote):
    return client.post(
        reverse("sales:quote_portal_sign", args=[quote.signing_token]),
        {
            "signer_name": "Dana Okafor",
            "signer_title": "VP Procurement",
            "signer_email": "dana@example.com",
            "signature_data": "Dana Okafor",
            "agree_terms": "on",
        },
    )


def test_quoteproposalcpq_portal_is_public_and_renders(db, tenant_a):
    """The portal is reached by capability token, not by a session."""
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Customer facing", status="presented")
    _quoteproposalcpq_line(tenant_a, quote, description="Optional upgrade")
    response = Client().get(reverse("sales:quote_portal_view", args=[quote.signing_token]))
    assert response.status_code == 200
    assert "Optional upgrade" in response.content.decode()


def test_quoteproposalcpq_portal_404s_on_an_unknown_token(db):
    from django.test import Client

    assert Client().get(reverse("sales:quote_portal_view", args=["no-such-token"])).status_code == 404


def test_quoteproposalcpq_portal_sign_accepts_and_transitions(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="To sign", status="presented")
    assert _quoteproposalcpq_portal_sign(Client(), quote).status_code == 302
    quote.refresh_from_db()
    assert quote.status == "accepted"
    assert quote.signer_name == "Dana Okafor"
    assert quote.signed_at is not None


def test_quoteproposalcpq_portal_sign_is_post_only(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="presented")
    assert Client().get(
        reverse("sales:quote_portal_sign", args=[quote.signing_token])
    ).status_code == 405


@pytest.mark.parametrize("status", ["draft", "in_review", "rejected", "declined", "superseded"])
def test_quoteproposalcpq_portal_sign_refuses_an_ineligible_status(db, tenant_a, status):
    """C7: the public endpoint had no status guard, so a draft could be signed."""
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Not signable", status=status)
    _quoteproposalcpq_portal_sign(Client(), quote)
    quote.refresh_from_db()
    assert quote.status == status
    assert quote.signed_at is None


def test_quoteproposalcpq_portal_sign_refuses_an_expired_quote(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(
        tenant_a,
        currency,
        name="Stale proposal",
        status="presented",
        valid_until=timezone.localdate() - timedelta(days=1),
    )
    assert quote.is_expired is True
    _quoteproposalcpq_portal_sign(Client(), quote)
    quote.refresh_from_db()
    assert quote.signed_at is None
    assert quote.status == "presented"


def test_quoteproposalcpq_portal_toggles_an_optional_line(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Configurable", status="presented")
    line = _quoteproposalcpq_line(
        tenant_a, quote, description="Optional add-on", is_optional=True, is_selected=True
    )
    response = Client().post(
        reverse("sales:quote_portal_toggle_line", args=[quote.signing_token, line.pk])
    )
    assert response.status_code == 302
    line.refresh_from_db()
    assert line.is_selected is False


def test_quoteproposalcpq_portal_toggle_refuses_an_expired_quote(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(
        tenant_a,
        currency,
        name="Stale",
        status="presented",
        valid_until=timezone.localdate() - timedelta(days=1),
    )
    line = _quoteproposalcpq_line(tenant_a, quote, description="Add-on", is_optional=True, is_selected=True)
    Client().post(reverse("sales:quote_portal_toggle_line", args=[quote.signing_token, line.pk]))
    line.refresh_from_db()
    assert line.is_selected is True


def test_quoteproposalcpq_portal_toggle_is_post_only(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="presented")
    line = _quoteproposalcpq_line(tenant_a, quote, description="Add-on", is_optional=True, is_selected=True)
    assert Client().get(
        reverse("sales:quote_portal_toggle_line", args=[quote.signing_token, line.pk])
    ).status_code == 405



# ---------------------------------------------------------------------------
# Quote-to-order conversion
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_conversion_board_lists_ready_quotes(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    ready = _quoteproposalcpq_quote(tenant_a, currency, name="Ready to convert", status="approved")
    draft = _quoteproposalcpq_quote(tenant_a, currency, name="Not yet", status="draft")
    body = _quoteproposalcpq_client(admin).get(reverse("sales:quote_conversion_board")).content.decode()
    assert ready.number in body
    assert draft.number not in body


def test_quoteproposalcpq_conversion_board_pages(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    for index in range(20):
        _quoteproposalcpq_quote(tenant_a, currency, name=f"Convertible {index:02d}", status="approved")
    response = _quoteproposalcpq_client(admin).get(reverse("sales:quote_conversion_board"), {"page": 2})
    assert response.status_code == 200
    assert response.context["page_obj"].number == 2


def test_quoteproposalcpq_convert_to_order_creates_a_sales_order(db, tenant_a):
    """C3: the service had to be aligned with the real SCM model contract."""
    from apps.scm.models.OrderManagement.SalesOrders import SalesOrder

    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant_a, name="Acme Buyer")
    item = _quoteproposalcpq_item(tenant_a, "Blade SKU")
    quote = _quoteproposalcpq_quote(
        tenant_a, currency, name="Convert me", status="approved", account=account
    )
    _quoteproposalcpq_line(
        tenant_a,
        quote,
        description="Blade server",
        quantity=Decimal("2.00"),
        unit_price=Decimal("500.00"),
        item=item,
    )
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:quote_convert_to_order", args=[quote.pk])
    )
    assert response.status_code == 302
    order = SalesOrder.objects.get(tenant=tenant_a)
    assert order.customer == account
    assert order.currency == currency
    assert order.lines.count() == 1
    assert order.lines.first().quantity_ordered == Decimal("2.00")
    quote.refresh_from_db()
    assert quote.status == "converted"
    assert quote.converted_order == order


def test_quoteproposalcpq_convert_refuses_without_an_account(db, tenant_a):
    """C3: the SCM SalesOrder requires a customer party."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="No account", status="approved")
    _quoteproposalcpq_line(tenant_a, quote)
    _quoteproposalcpq_client(admin).post(reverse("sales:quote_convert_to_order", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.status == "approved"
    assert quote.converted_order is None


def test_quoteproposalcpq_convert_refuses_an_unapproved_quote(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant_a, name="Acme Buyer")
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Draft", status="draft", account=account)
    _quoteproposalcpq_line(tenant_a, quote)
    _quoteproposalcpq_client(admin).post(reverse("sales:quote_convert_to_order", args=[quote.pk]))
    quote.refresh_from_db()
    assert quote.status == "draft"
    assert quote.converted_order is None


def test_quoteproposalcpq_convert_is_post_only(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="approved")
    assert _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_convert_to_order", args=[quote.pk])
    ).status_code == 405



def test_quoteproposalcpq_convert_is_one_way(db, tenant_a):
    """The second conversion must be refused -- one quote, one order."""
    from apps.scm.models.OrderManagement.SalesOrders import SalesOrder

    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant_a, name="Acme Buyer")
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Once only", status="approved", account=account)
    _quoteproposalcpq_line(tenant_a, quote)
    client = _quoteproposalcpq_client(admin)
    client.post(reverse("sales:quote_convert_to_order", args=[quote.pk]))
    assert SalesOrder.objects.filter(tenant=tenant_a).count() == 1
    quote.refresh_from_db()
    quote.status = "approved"  # force it back so the one-way guard is the only thing tested
    quote.save(update_fields=["status", "updated_at"])
    client.post(reverse("sales:quote_convert_to_order", args=[quote.pk]))
    assert SalesOrder.objects.filter(tenant=tenant_a).count() == 1


# ---------------------------------------------------------------------------
# Guided selling
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_guided_selling_lists_bundles(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    _quoteproposalcpq_bundle(tenant_a, bundle, component)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_guided_selling"))
    assert response.status_code == 200
    assert "bundle_products" in response.context
    assert "opportunities" in response.context


def test_quoteproposalcpq_guided_selling_shows_options_for_a_bundle(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    _quoteproposalcpq_bundle(tenant_a, bundle, component, name="Blade option", is_active=True)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_guided_selling"), {"bundle": str(bundle.pk)}
    ).content.decode()
    assert "Blade option" in body


def test_quoteproposalcpq_guided_selling_404s_on_a_foreign_bundle(db, tenant_a, tenant_b):
    admin = _quoteproposalcpq_admin(tenant_a)
    foreign = _quoteproposalcpq_product(tenant_b, "Foreign bundle")
    assert _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_guided_selling"), {"bundle": str(foreign.pk)}
    ).status_code == 404


def test_quoteproposalcpq_guided_selling_survives_a_junk_bundle_param(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    for params in ({"bundle": "abc"}, {"bundle": ""}, {"quote": "abc"}):
        response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_guided_selling"), params)
        assert response.status_code == 200



def test_quoteproposalcpq_guided_selling_does_not_preselect_a_foreign_quote(db, tenant_a, tenant_b):
    """M6: the ?quote= pk reached the template after only an isdigit() check, so
    another tenant's quote id could be pre-filled into the hidden inputs."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency, name="Globex proposal")
    response = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_guided_selling"), {"quote": str(foreign.pk)}
    )
    assert response.status_code == 200
    assert response.context["preselect_quote_id"] is None
    assert f'value="{foreign.pk}"' not in response.content.decode()


def test_quoteproposalcpq_guided_selling_preselects_an_own_quote(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    mine = _quoteproposalcpq_quote(tenant_a, currency, name="Acme proposal")
    response = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_guided_selling"), {"quote": str(mine.pk)}
    )
    assert response.status_code == 200
    assert response.context["preselect_quote_id"] == mine.pk


def test_quoteproposalcpq_guided_selling_applies_a_bundle_to_a_new_quote(db, tenant_a):
    """I6: the multi-model create is atomic, and C4 fixed the currency fallback
    for the no-opportunity case."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    _quoteproposalcpq_bundle(tenant_a, bundle, component, is_required=True)
    response = _quoteproposalcpq_client(admin).post(
        reverse("sales:cpq_guided_selling"),
        {"apply_guided_bundle": "1", "bundle": str(bundle.pk), "quote_id": "", "opportunity_id": ""},
    )
    assert response.status_code == 302
    quote = CPQQuote.objects.filter(tenant=tenant_a).order_by("-created_at").first()
    assert quote is not None
    assert quote.currency_id is not None
    parent = quote.lines.filter(line_type="bundle_parent").first()
    assert parent is not None
    assert quote.lines.filter(parent_line=parent).count() == 1


def test_quoteproposalcpq_guided_selling_refuses_a_locked_quote_for_a_rep(db, tenant_a):
    """C9: supplying a quote_id used to inject lines into a locked quote."""
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    currency = _quoteproposalcpq_currency()
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    _quoteproposalcpq_bundle(tenant_a, bundle, component, is_required=True)
    locked = _quoteproposalcpq_quote(tenant_a, currency, name="Locked", status="approved")
    before = locked.lines.count()
    _quoteproposalcpq_client(rep).post(
        reverse("sales:cpq_guided_selling"),
        {
            "apply_guided_bundle": "1",
            "bundle": str(bundle.pk),
            "quote_id": str(locked.pk),
            "opportunity_id": "",
        },
    )
    assert locked.lines.count() == before


def test_quoteproposalcpq_guided_selling_rejects_a_non_finite_quantity(db, tenant_a):
    """I5: hand-parsed quantity input must be finite and positive."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    option = _quoteproposalcpq_bundle(
        tenant_a, bundle, component, default_quantity=Decimal("2"), is_required=True
    )
    _quoteproposalcpq_client(admin).post(
        reverse("sales:cpq_guided_selling"),
        {
            "apply_guided_bundle": "1",
            "bundle": str(bundle.pk),
            "quote_id": "",
            "opportunity_id": "",
            f"opt_{option.pk}": "on",
            f"qty_{option.pk}": "NaN",
        },
    )
    quote = CPQQuote.objects.filter(tenant=tenant_a).order_by("-created_at").first()
    child = quote.lines.filter(line_type="bundle_component").first()
    assert child is not None
    assert child.quantity == Decimal("2")


# ---------------------------------------------------------------------------
# ATP soft reservation on conversion
# ---------------------------------------------------------------------------

def _quoteproposalcpq_location(tenant, code="WH1", **overrides):
    from apps.scm.models.InventoryManagement.Locations import Location

    fields = {
        "tenant": tenant,
        "code": code,
        "name": f"Warehouse {code}",
        "location_type": "warehouse",
        "is_active": True,
        "is_pickable": True,
    }
    fields.update(overrides)
    return Location.objects.create(**fields)


def _quoteproposalcpq_fresh_tenant(slug, username):
    from apps.accounts.models import User
    from apps.core.models import Tenant

    tenant = Tenant.objects.create(name=f"{slug.title()} Corp", slug=slug)
    admin = User.objects.create_user(
        email=f"{slug}_admin@example.com",
        username=username,
        password="password",
        tenant=tenant,
        is_tenant_admin=True,
    )
    return tenant, admin


def test_quoteproposalcpq_conversion_soft_reserves_stock_at_the_default_warehouse():
    """A converted line with a scm.Item must come back with a `reserved`
    allocation. The research rates ATP table-stakes and the contract's verify
    list requires it; nothing created one before."""
    from apps.scm.models.OrderManagement.SalesOrderAllocations import SalesOrderAllocation

    from apps.sales.cpq_services import cpq_convert_to_sales_order

    tenant, admin = _quoteproposalcpq_fresh_tenant("atp", "atp_admin")
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant, name="ATP Buyer")
    warehouse = _quoteproposalcpq_location(tenant, code="WH-MAIN")
    item = _quoteproposalcpq_item(tenant, "Reservable SKU")
    quote = _quoteproposalcpq_quote(tenant, currency, name="Reserve me", status="approved", account=account)
    _quoteproposalcpq_line(
        tenant, quote, description="Blade", quantity=Decimal("3.00"), unit_price=Decimal("100.00"), item=item
    )

    order = cpq_convert_to_sales_order(quote, user=admin)
    allocations = SalesOrderAllocation.objects.filter(sales_order_line__sales_order=order)
    assert allocations.count() == 1
    allocation = allocations.first()
    assert allocation.status == "reserved"
    assert allocation.location_id == warehouse.pk
    assert allocation.quantity == Decimal("3.00")
    # A soft reservation must NOT claim a warehouse gap it did not have.
    assert "ATP note" not in (order.notes or "")
    assert quote.status == "converted"


def test_quoteproposalcpq_a_service_line_with_no_item_is_reported_not_silently_skipped():
    from apps.sales.cpq_services import cpq_convert_to_sales_order
    from apps.scm.models.OrderManagement.SalesOrderAllocations import SalesOrderAllocation

    tenant, admin = _quoteproposalcpq_fresh_tenant("svc", "svc_admin")
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant, name="Svc Buyer")
    _quoteproposalcpq_location(tenant, code="WH-SVC")
    quote = _quoteproposalcpq_quote(tenant, currency, name="Services only", status="approved", account=account)
    _quoteproposalcpq_line(tenant, quote, description="Consulting", quantity=Decimal("2.00"), unit_price=Decimal("50.00"))

    order = cpq_convert_to_sales_order(quote, user=admin)
    assert SalesOrderAllocation.objects.filter(sales_order_line__sales_order=order).count() == 0
    assert "ATP note" in (order.notes or "")


def test_quoteproposalcpq_no_warehouse_configured_is_reported_on_the_order():
    from apps.sales.cpq_services import cpq_convert_to_sales_order

    tenant, admin = _quoteproposalcpq_fresh_tenant("nowh", "nowh_admin")
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant, name="NoWH Buyer")
    item = _quoteproposalcpq_item(tenant, "SKU with nowhere to live")
    quote = _quoteproposalcpq_quote(tenant, currency, name="No warehouse", status="approved", account=account)
    _quoteproposalcpq_line(tenant, quote, description="Widget", quantity=Decimal("1.00"), unit_price=Decimal("10.00"), item=item)

    order = cpq_convert_to_sales_order(quote, user=admin)
    assert "ATP note" in (order.notes or "")
    assert "no active pickable warehouse" in order.notes


def test_quoteproposalcpq_default_warehouse_prefers_the_lowest_pick_sequence():
    from apps.sales.cpq_services import _default_fulfillment_location

    tenant, _admin = _quoteproposalcpq_fresh_tenant("seq", "seq_admin")
    _quoteproposalcpq_location(tenant, code="WH-AAA", pick_sequence=90)
    preferred = _quoteproposalcpq_location(tenant, code="WH-ZZZ", pick_sequence=10)
    _quoteproposalcpq_location(tenant, code="WH-BIN", location_type="bin")
    assert _default_fulfillment_location(tenant).pk == preferred.pk


def test_quoteproposalcpq_an_inactive_warehouse_is_not_chosen():
    from apps.sales.cpq_services import _default_fulfillment_location

    tenant, _admin = _quoteproposalcpq_fresh_tenant("inact", "inact_admin")
    _quoteproposalcpq_location(tenant, code="WH-OFF", is_active=False)
    assert _default_fulfillment_location(tenant) is None




# ---------------------------------------------------------------------------
# The win is recorded, once, on conversion
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_conversion_records_the_won_outcome():
    """A deal moved to closed_won with no OpportunityOutcome leaves 8.4's
    accuracy report with no ground truth to learn from."""
    from apps.sales.cpq_services import cpq_convert_to_sales_order
    from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome

    tenant, admin = _quoteproposalcpq_fresh_tenant("win", "win_admin")
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant, name="Win Buyer")
    _quoteproposalcpq_location(tenant, code="WH-WIN")
    opportunity = _quoteproposalcpq_opportunity(tenant, account=account, stage="negotiation")
    quote = _quoteproposalcpq_quote(
        tenant, currency, name="Closed won", status="approved", account=account, opportunity=opportunity
    )
    _quoteproposalcpq_line(tenant, quote, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))

    cpq_convert_to_sales_order(quote, user=admin)
    opportunity.refresh_from_db()
    assert opportunity.stage == "closed_won"
    outcomes = OpportunityOutcome.objects.filter(tenant=tenant, opportunity=opportunity, result="won")
    assert outcomes.count() == 1
    outcome = outcomes.first()
    assert outcome.reason is not None
    assert outcome.recorded_by_id == admin.pk
    assert quote.number in outcome.notes
    assert outcome.number.startswith("OUT-")


def test_quoteproposalcpq_the_win_is_recorded_only_once():
    """OpportunityOutcome is append-only and a deal is won once, so a second
    row would double-count it in every forecast that reads outcomes."""
    from django.core.exceptions import ValidationError as DjangoValidationError

    from apps.sales.cpq_services import cpq_convert_to_sales_order, cpq_record_won_outcome
    from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome

    tenant, admin = _quoteproposalcpq_fresh_tenant("once", "once_admin")
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant, name="Once Buyer")
    _quoteproposalcpq_location(tenant, code="WH-ONCE")
    opportunity = _quoteproposalcpq_opportunity(tenant, account=account, stage="negotiation")
    quote = _quoteproposalcpq_quote(
        tenant, currency, name="Convert once", status="approved", account=account, opportunity=opportunity
    )
    _quoteproposalcpq_line(tenant, quote, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))

    cpq_convert_to_sales_order(quote, user=admin)
    assert cpq_record_won_outcome(opportunity, quote, admin) is None
    assert OpportunityOutcome.objects.filter(tenant=tenant, opportunity=opportunity, result="won").count() == 1
    # and the one-way door still holds
    with pytest.raises(DjangoValidationError):
        cpq_convert_to_sales_order(quote, user=admin)


def test_quoteproposalcpq_the_win_reason_reuses_the_tenants_configured_catalog():
    from apps.sales.cpq_services import cpq_record_won_outcome
    from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome, WinLossReason

    tenant, admin = _quoteproposalcpq_fresh_tenant("cat", "cat_admin")
    configured = WinLossReason.objects.create(
        tenant=tenant, code="exec_sponsor", name="Executive Sponsor",
        sequence=5, result="won", category="relationship",
    )
    opportunity = _quoteproposalcpq_opportunity(tenant, stage="negotiation")
    quote = _quoteproposalcpq_quote(tenant, _quoteproposalcpq_currency(), name="Reason reuse")
    outcome = cpq_record_won_outcome(opportunity, quote, admin)
    assert outcome.reason_id == configured.pk
    # no extra reason row invented when the tenant already configured one
    assert WinLossReason.objects.filter(tenant=tenant).count() == 1
    assert OpportunityOutcome.objects.filter(tenant=tenant, opportunity=opportunity).count() == 1


def test_quoteproposalcpq_the_win_is_not_recorded_twice_across_two_quotes():
    """Two quotes on one opportunity is a real CRM state; the win belongs to the
    opportunity, not to each conversion."""
    from apps.sales.cpq_services import cpq_convert_to_sales_order
    from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome

    tenant, admin = _quoteproposalcpq_fresh_tenant("twoq", "twoq_admin")
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant, name="TwoQ Buyer")
    _quoteproposalcpq_location(tenant, code="WH-TWOQ")
    opportunity = _quoteproposalcpq_opportunity(tenant, account=account, stage="negotiation")
    for label in ("First quote", "Second quote"):
        quote = _quoteproposalcpq_quote(
            tenant, currency, name=label, status="approved", account=account, opportunity=opportunity
        )
        _quoteproposalcpq_line(tenant, quote, quantity=Decimal("1.00"), unit_price=Decimal("10.00"))
        cpq_convert_to_sales_order(quote, user=admin)

    assert OpportunityOutcome.objects.filter(tenant=tenant, opportunity=opportunity, result="won").count() == 1


# ---------------------------------------------------------------------------
# The three quote-list filters the plan named and the build never wired up
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_list_account_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    acme_account = _quoteproposalcpq_party(tenant_a, name="Acme Holdings")
    other_account = _quoteproposalcpq_party(tenant_a, name="Acme Subsidiary")
    wanted = _quoteproposalcpq_quote(tenant_a, currency, name="For Holdings", account=acme_account)
    _quoteproposalcpq_quote(tenant_a, currency, name="For Subsidiary", account=other_account)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"account": str(acme_account.pk)}
    ).content.decode()
    assert wanted.number in body
    assert "For Subsidiary" not in body


def test_quoteproposalcpq_quote_list_owner_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    other = _quoteproposalcpq_user(tenant_a, "colleague")
    _quoteproposalcpq_quote(tenant_a, currency, name="Owned by admin", owner=admin)
    _quoteproposalcpq_quote(tenant_a, currency, name="Owned by colleague", owner=other)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"owner": str(other.pk)}
    ).content.decode()
    assert "Owned by colleague" in body
    assert "Owned by admin" not in body


def test_quoteproposalcpq_quote_list_owner_filter_finds_unassigned(db, tenant_a):
    """owner is a nullable FK, so "nobody owns it" is a real bucket to filter on."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    _quoteproposalcpq_quote(tenant_a, currency, name="Owned by admin", owner=admin)
    _quoteproposalcpq_quote(tenant_a, currency, name="Nobody owns this", owner=None)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"owner": "none"}
    ).content.decode()
    assert "Nobody owns this" in body
    assert "Owned by admin" not in body


def test_quoteproposalcpq_quote_list_currency_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    usd = _quoteproposalcpq_currency(code="USD")
    eur = _quoteproposalcpq_currency(code="EUR", name="Euro")
    _quoteproposalcpq_quote(tenant_a, usd, name="Dollar deal")
    _quoteproposalcpq_quote(tenant_a, eur, name="Euro deal")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_list"), {"currency": str(eur.pk)}
    ).content.decode()
    assert "Euro deal" in body
    assert "Dollar deal" not in body


@pytest.mark.parametrize("param", ["account", "owner", "currency"])
def test_quoteproposalcpq_new_quote_filters_survive_junk_values(db, tenant_a, param):
    admin = _quoteproposalcpq_admin(tenant_a)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_list"), {param: "abc"})
    assert response.status_code == 200


def test_quoteproposalcpq_quote_list_exposes_the_new_filter_dropdowns(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    account = _quoteproposalcpq_party(tenant_a, name="Dropdown Account")
    _quoteproposalcpq_quote(tenant_a, currency, name="Owned", account=account, owner=admin)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_list"))
    for key in ("accounts", "owners", "currencies"):
        assert key in response.context, key
    body = response.content.decode()
    assert "Dropdown Account" in body
    assert 'name="account"' in body
    assert 'name="owner"' in body
    assert 'name="currency"' in body



# ---------------------------------------------------------------------------
# The five line-list filters the plan named and the build never wired up
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_line_list_line_type_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    _quoteproposalcpq_line(tenant_a, quote, description="A plain line", line_type="standard", sequence=10)
    _quoteproposalcpq_line(tenant_a, quote, description="An add-on", line_type="optional_addon", sequence=20)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk]), {"line_type": "optional_addon"}
    ).content.decode()
    assert "An add-on" in body
    assert "A plain line" not in body


def test_quoteproposalcpq_line_list_product_and_item_filters_narrow(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    product = _quoteproposalcpq_product(tenant_a, "Filterable widget")
    item = _quoteproposalcpq_item(tenant_a, "Filterable SKU")
    _quoteproposalcpq_line(tenant_a, quote, description="On the product", product=product, sequence=10)
    _quoteproposalcpq_line(tenant_a, quote, description="On the item", item=item, sequence=20)
    _quoteproposalcpq_line(tenant_a, quote, description="Neither", sequence=30)
    client = _quoteproposalcpq_client(admin)
    by_product = client.get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk]), {"product": str(product.pk)}
    ).content.decode()
    assert "On the product" in by_product
    assert "Neither" not in by_product
    by_item = client.get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk]), {"item": str(item.pk)}
    ).content.decode()
    assert "On the item" in by_item
    assert "Neither" not in by_item


def test_quoteproposalcpq_line_list_optional_and_selected_filters_narrow(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    _quoteproposalcpq_line(tenant_a, quote, description="Optional included", is_optional=True, is_selected=True, sequence=10)
    _quoteproposalcpq_line(tenant_a, quote, description="Optional declined", is_optional=True, is_selected=False, sequence=20)
    _quoteproposalcpq_line(tenant_a, quote, description="Required line", is_optional=False, is_selected=True, sequence=30)
    client = _quoteproposalcpq_client(admin)
    declined = client.get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk]), {"is_selected": "0"}
    ).content.decode()
    assert "Optional declined" in declined
    assert "Required line" not in declined
    required = client.get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk]), {"is_optional": "0"}
    ).content.decode()
    assert "Required line" in required
    assert "Optional declined" not in required


def test_quoteproposalcpq_line_list_search_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    _quoteproposalcpq_line(tenant_a, quote, description="Managed support retainer", sequence=10)
    _quoteproposalcpq_line(tenant_a, quote, description="Onsite installation", sequence=20)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk]), {"q": "retainer"}
    ).content.decode()
    assert "Managed support retainer" in body
    assert "Onsite installation" not in body


@pytest.mark.parametrize(
    "params",
    [
        {"line_type": "nope"},
        {"product": "abc"},
        {"item": "abc"},
        {"is_optional": "maybe"},
        {"is_selected": "maybe"},
        {"q": ""},
    ],
)
def test_quoteproposalcpq_line_list_survives_junk_parameters(db, tenant_a, params):
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    _quoteproposalcpq_line(tenant_a, quote)
    response = _quoteproposalcpq_client(admin).get(
        reverse("sales:cpq_quote_line_list", args=[quote.pk]), params
    )
    assert response.status_code == 200


def test_quoteproposalcpq_line_list_dropdowns_are_scoped_to_this_quote(db, tenant_a):
    """A dropdown offering another quote's product is a disclosure, so the
    queryset is the boundary -- not just the filter."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    other_quote = _quoteproposalcpq_quote(tenant_a, currency)
    mine = _quoteproposalcpq_product(tenant_a, "Mine on this quote")
    theirs = _quoteproposalcpq_product(tenant_a, "Theirs on another quote")
    _quoteproposalcpq_line(tenant_a, quote, description="Mine", product=mine, sequence=10)
    _quoteproposalcpq_line(tenant_a, other_quote, description="Theirs", product=theirs, sequence=10)
    response = _quoteproposalcpq_client(admin).get(reverse("sales:cpq_quote_line_list", args=[quote.pk]))
    assert "Mine on this quote" in response.content.decode()
    assert "Theirs on another quote" not in response.content.decode()
    assert [p.pk for p in response.context["products"]] == [mine.pk]





def test_quoteproposalcpq_bundle_list_component_product_filter_narrows(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    wanted_component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    other_component = _quoteproposalcpq_product(tenant_a, "Rack Switch")
    wanted = _quoteproposalcpq_bundle(tenant_a, bundle, wanted_component, name="Blade option")
    _quoteproposalcpq_bundle(tenant_a, bundle, other_component, name="Switch option")
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:product_bundle_list"), {"component_product": str(wanted_component.pk)}
    ).content.decode()
    assert wanted.name in body
    assert "Switch option" not in body
    assert 'name="component_product"' in body


def test_quoteproposalcpq_bundle_list_component_filter_survives_junk(db, tenant_a):
    admin = _quoteproposalcpq_admin(tenant_a)


def test_quoteproposalcpq_compare_reports_added_and_removed_lines(db, tenant_a):
    """The verify list asks the comparison to highlight added/removed lines, not
    only price changes. A line present in only one of the two revisions must show
    up as its own row rather than as a modification of nothing."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    older = _quoteproposalcpq_quote(tenant_a, currency, name="Deal")
    _quoteproposalcpq_line(tenant_a, older, description="Kept line", sequence=10)
    _quoteproposalcpq_line(tenant_a, older, description="Dropped line", sequence=20)
    newer = _quoteproposalcpq_quote(
        tenant_a, currency, name="Deal", quote_group_id=older.quote_group_id, revision_number=2
    )
    _quoteproposalcpq_line(tenant_a, newer, description="Kept line", sequence=10)
    _quoteproposalcpq_line(tenant_a, newer, description="Fresh line", sequence=20)

    response = _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_compare_versions", args=[older.pk, newer.pk])
    )
    assert response.status_code == 200
    rows = {row["description"]: row["status"] for row in response.context["diff_data"]["line_diffs"]}
    assert rows["Fresh line"] == "added"
    assert rows["Dropped line"] == "removed"
    assert rows["Kept line"] == "unchanged"


def test_quoteproposalcpq_the_compare_page_labels_added_and_removed_rows(db, tenant_a):
    """The diff is only useful if the reader can SEE which row is which; an
    unlabelled table of deltas is the defect this bullet exists to prevent."""
    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    older = _quoteproposalcpq_quote(tenant_a, currency, name="Labelled deal")
    _quoteproposalcpq_line(tenant_a, older, description="Removed widget", sequence=10)
    newer = _quoteproposalcpq_quote(
        tenant_a, currency, name="Labelled deal", quote_group_id=older.quote_group_id, revision_number=2
    )
    _quoteproposalcpq_line(tenant_a, newer, description="Added widget", sequence=10)
    body = _quoteproposalcpq_client(admin).get(
        reverse("sales:quote_compare_versions", args=[older.pk, newer.pk])
    ).content.decode()
    assert "+ Added" in body
    assert "- Removed" in body

    assert _quoteproposalcpq_client(admin).get(
        reverse("sales:product_bundle_list"), {"component_product": "abc"}
    ).status_code == 200
