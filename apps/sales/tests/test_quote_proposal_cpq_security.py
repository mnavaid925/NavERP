"""8.5 Quote & Proposal Management (CPQ) -- the SECURITY lane.

Naming: every test is ``test_quoteproposalcpq_*`` and every module-level helper
``_quoteproposalcpq_*``. Record factories are imported from the models lane.

The inventory this lane defends is: **every CPQ object route is tenant-scoped by
pk**, every staff page requires a session, the configuration routes (bundle and
rule create / edit / delete) additionally require a tenant admin, and the three
portal routes are deliberately *public* -- reached by an unguessable capability
token, not by a session.

That last point needs the most care. A public route is not an unprotected route:
the token must be unique, unguessable and non-editable, and the sign/toggle
endpoints must refuse an ineligible quote. So this lane pins both halves -- no
staff data leaks through a token, and no token grants more than the quote it
names.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.sales.models.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLine
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.QuoteProposalCPQ.ProductBundles import ProductBundleOption
from apps.sales.models.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRule

from apps.sales.tests.test_quote_proposal_cpq_models import (
    _quoteproposalcpq_bundle,
    _quoteproposalcpq_currency,
    _quoteproposalcpq_line,
    _quoteproposalcpq_party,
    _quoteproposalcpq_product,
    _quoteproposalcpq_quote,
    _quoteproposalcpq_rule,
    _quoteproposalcpq_user,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quoteproposalcpq_admin(tenant, key="admin_acme"):
    return _quoteproposalcpq_user(tenant, key, is_admin=True)


def _quoteproposalcpq_client(user):
    from django.test import Client

    client = Client()
    client.force_login(user)
    return client


# ---------------------------------------------------------------------------
# Every object route is tenant-scoped by pk
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_foreign_quote_detail_is_404(db, tenant_a, tenant_b):
    """A pk from another workspace must be indistinguishable from a missing one."""
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency, name="Globex secret proposal")
    response = _quoteproposalcpq_client(admin_a).get(reverse("sales:cpq_quote_detail", args=[foreign.pk]))
    assert response.status_code == 404
    assert "Globex secret proposal" not in response.content.decode()


def test_quoteproposalcpq_foreign_quote_edit_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency, name="Globex proposal")
    client = _quoteproposalcpq_client(admin_a)
    assert client.get(reverse("sales:cpq_quote_edit", args=[foreign.pk])).status_code == 404
    response = client.post(
        reverse("sales:cpq_quote_edit", args=[foreign.pk]),
        {"name": "Stolen", "currency": str(currency.pk), "header_discount_pct": ""},
    )
    assert response.status_code == 404
    foreign.refresh_from_db()
    assert foreign.name == "Globex proposal"


def test_quoteproposalcpq_foreign_quote_delete_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency, status="draft")
    response = _quoteproposalcpq_client(admin_a).post(reverse("sales:cpq_quote_delete", args=[foreign.pk]))
    assert response.status_code == 404
    assert CPQQuote.objects.filter(pk=foreign.pk).exists()


def test_quoteproposalcpq_foreign_quote_line_list_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency)
    _quoteproposalcpq_line(tenant_b, foreign, description="Globex confidential line")
    response = _quoteproposalcpq_client(admin_a).get(reverse("sales:cpq_quote_line_list", args=[foreign.pk]))
    assert response.status_code == 404
    assert "Globex confidential line" not in response.content.decode()


def test_quoteproposalcpq_foreign_quote_line_create_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency, status="draft")
    response = _quoteproposalcpq_client(admin_a).post(
        reverse("sales:cpq_quote_line_create", args=[foreign.pk]),
        {"line_type": "standard", "description": "Injected", "quantity": "1", "unit_price": "1", "sequence": "10"},
    )
    assert response.status_code == 404
    assert not CPQQuoteLine.objects.filter(quote=foreign).exists()


def test_quoteproposalcpq_foreign_quote_line_detail_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    mine = _quoteproposalcpq_quote(tenant_a, currency)
    foreign_quote = _quoteproposalcpq_quote(tenant_b, currency)
    foreign_line = _quoteproposalcpq_line(tenant_b, foreign_quote, description="Globex line")
    response = _quoteproposalcpq_client(admin_a).get(
        reverse("sales:cpq_quote_line_detail", args=[mine.pk, foreign_line.pk])
    )
    assert response.status_code == 404


def test_quoteproposalcpq_foreign_quote_line_delete_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign_quote = _quoteproposalcpq_quote(tenant_b, currency, status="draft")
    foreign_line = _quoteproposalcpq_line(tenant_b, foreign_quote, description="Globex line")
    response = _quoteproposalcpq_client(admin_a).post(
        reverse("sales:cpq_quote_line_delete", args=[foreign_quote.pk, foreign_line.pk])
    )
    assert response.status_code == 404
    assert CPQQuoteLine.objects.filter(pk=foreign_line.pk).exists()



def test_quoteproposalcpq_foreign_bundle_detail_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    foreign = _quoteproposalcpq_bundle(
        tenant_b,
        _quoteproposalcpq_product(tenant_b, "Rack"),
        _quoteproposalcpq_product(tenant_b, "Server"),
        name="Globex option",
    )
    response = _quoteproposalcpq_client(admin_a).get(reverse("sales:product_bundle_detail", args=[foreign.pk]))
    assert response.status_code == 404
    assert "Globex option" not in response.content.decode()


def test_quoteproposalcpq_foreign_bundle_edit_and_delete_are_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    foreign = _quoteproposalcpq_bundle(
        tenant_b,
        _quoteproposalcpq_product(tenant_b, "Rack"),
        _quoteproposalcpq_product(tenant_b, "Server"),
        name="Globex option",
    )
    client = _quoteproposalcpq_client(admin_a)
    assert client.get(reverse("sales:product_bundle_edit", args=[foreign.pk])).status_code == 404
    assert client.post(reverse("sales:product_bundle_delete", args=[foreign.pk])).status_code == 404
    assert ProductBundleOption.objects.filter(pk=foreign.pk).exists()


def test_quoteproposalcpq_foreign_rule_detail_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    foreign = _quoteproposalcpq_rule(tenant_b, name="Globex secret rule")
    response = _quoteproposalcpq_client(admin_a).get(reverse("sales:quote_approval_rule_detail", args=[foreign.pk]))
    assert response.status_code == 404
    assert "Globex secret rule" not in response.content.decode()


def test_quoteproposalcpq_foreign_rule_edit_and_delete_are_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    foreign = _quoteproposalcpq_rule(tenant_b, name="Globex rule")
    client = _quoteproposalcpq_client(admin_a)
    assert client.get(reverse("sales:quote_approval_rule_edit", args=[foreign.pk])).status_code == 404
    assert client.post(reverse("sales:quote_approval_rule_delete", args=[foreign.pk])).status_code == 404
    assert QuoteApprovalRule.objects.filter(pk=foreign.pk).exists()


def test_quoteproposalcpq_foreign_operational_verbs_are_404(db, tenant_a, tenant_b):
    """The POST-only workflow verbs are scoped too, not just the GET pages."""
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency, status="draft", account=_quoteproposalcpq_party(tenant_b))
    _quoteproposalcpq_line(tenant_b, foreign)
    client = _quoteproposalcpq_client(admin_a)
    for name in ("quote_submit_approval", "quote_create_revision", "quote_convert_to_order"):
        response = client.post(reverse(f"sales:{name}", args=[foreign.pk]))
        assert response.status_code == 404, name
    foreign.refresh_from_db()
    assert foreign.status == "draft"
    assert foreign.revisions.count() == 0
    assert foreign.converted_order_id is None


def test_quoteproposalcpq_foreign_compare_pair_is_404(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    foreign = _quoteproposalcpq_quote(tenant_b, currency)
    mine = _quoteproposalcpq_quote(tenant_a, currency)
    assert _quoteproposalcpq_client(admin_a).get(
        reverse("sales:quote_compare_versions", args=[mine.pk, foreign.pk])
    ).status_code == 404



# ---------------------------------------------------------------------------
# No foreign row leaks into any list, board or dropdown
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_lists_never_leak_another_tenants_rows(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    # Both records are pending, so the approval queue has a row of its own to show
    # -- and each board is filtered on a different status, so they cannot both be
    # asserted from one record.
    mine = _quoteproposalcpq_quote(tenant_a, currency, name="Acme proposal", status="in_review", approval_status="pending")
    mine_approved = _quoteproposalcpq_quote(tenant_a, currency, name="Acme approved", status="approved")
    theirs = _quoteproposalcpq_quote(
        tenant_b, currency, name="Globex proposal", status="in_review", approval_status="pending"
    )
    theirs_approved = _quoteproposalcpq_quote(tenant_b, currency, name="Globex approved", status="approved")
    client = _quoteproposalcpq_client(admin_a)
    expectations = {
        "cpq_quote_list": ("Acme proposal", "Globex proposal"),
        "quote_approval_queue": ("Acme proposal", "Globex proposal"),
        "quote_proposal_board": ("Acme approved", "Globex approved"),
        "quote_conversion_board": ("Acme approved", "Globex approved"),
        "quote_version_list": ("Acme proposal", "Globex proposal"),
    }
    for name, (present, absent) in expectations.items():
        body = client.get(reverse(f"sales:{name}")).content.decode()
        # numbers restart per tenant, so the NAME is the only reliable marker
        assert present in body, name
        assert absent not in body, name
    assert theirs.pk != mine.pk and theirs_approved.pk != mine_approved.pk


def test_quoteproposalcpq_bundle_and_rule_lists_never_leak(db, tenant_a, tenant_b):
    admin_a = _quoteproposalcpq_admin(tenant_a)
    my_bundle = _quoteproposalcpq_bundle(
        tenant_a, _quoteproposalcpq_product(tenant_a, "Rack"), _quoteproposalcpq_product(tenant_a, "Server"), name="Acme option"
    )
    their_bundle = _quoteproposalcpq_bundle(
        tenant_b, _quoteproposalcpq_product(tenant_b, "Rack"), _quoteproposalcpq_product(tenant_b, "Server"), name="Globex option"
    )
    my_rule = _quoteproposalcpq_rule(tenant_a, name="Acme floor")
    their_rule = _quoteproposalcpq_rule(tenant_b, name="Globex floor")
    client = _quoteproposalcpq_client(admin_a)
    bundles = client.get(reverse("sales:product_bundle_list")).content.decode()
    assert my_bundle.name in bundles
    assert "Globex option" not in bundles
    rules = client.get(reverse("sales:quote_approval_rule_list")).content.decode()
    assert "Acme floor" in rules
    assert "Globex floor" not in rules


def test_quoteproposalcpq_the_superuser_with_no_tenant_sees_nothing(db):
    """The `admin` superuser has tenant=None by design: every list is empty for
    it, which is correct rather than a bug."""
    from django.contrib.auth import get_user_model

    from django.test import Client

    User = get_user_model()
    root = User.objects.create_superuser(email="root@example.com", username="root", password="password")
    client = Client()
    client.force_login(root)
    for name in ("cpq_quote_list", "product_bundle_list", "quote_approval_rule_list"):
        response = client.get(reverse(f"sales:{name}"))
        assert response.status_code == 200
        assert len(response.context["quotes" if name == "cpq_quote_list" else ("bundles" if name == "product_bundle_list" else "rules")]) == 0


def test_quoteproposalcpq_a_foreign_product_is_never_offered_in_a_line_form(db, tenant_a, tenant_b):
    """The dropdown queryset is the tenant boundary, not just the save."""
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    _quoteproposalcpq_product(tenant_b, "Foreign widget")
    response = _quoteproposalcpq_client(_quoteproposalcpq_admin(tenant_a)).get(
        reverse("sales:cpq_quote_line_create", args=[quote.pk])
    )
    assert response.status_code == 200
    assert "Foreign widget" not in response.content.decode()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

QUOTEPROPOSALCPQ_PUBLIC_ROUTES = ["quote_portal_view", "quote_portal_sign", "quote_portal_toggle_line"]


def test_quoteproposalcpq_every_staff_route_refuses_an_anonymous_visitor(db):
    from django.test import Client

    client = Client()
    for name in (
        "cpq_quote_list",
        "cpq_quote_create",
        "quote_approval_queue",
        "quote_version_list",
        "quote_proposal_board",
        "quote_conversion_board",
        "cpq_guided_selling",
        "product_bundle_list",
        "product_bundle_create",
        "quote_approval_rule_list",
        "quote_approval_rule_create",
    ):
        response = client.get(reverse(f"sales:{name}"))
        assert response.status_code in (302, 403), name
        if response.status_code == 302:
            assert "/login" in response["Location"], name



def test_quoteproposalcpq_object_routes_refuse_an_anonymous_visitor(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    line = _quoteproposalcpq_line(tenant_a, quote)
    bundle = _quoteproposalcpq_bundle(
        tenant_a, _quoteproposalcpq_product(tenant_a, "Rack"), _quoteproposalcpq_product(tenant_a, "Server")
    )
    rule = _quoteproposalcpq_rule(tenant_a)
    client = Client()
    routes = [
        ("cpq_quote_detail", [quote.pk]),
        ("cpq_quote_edit", [quote.pk]),
        ("cpq_quote_line_list", [quote.pk]),
        ("cpq_quote_line_detail", [quote.pk, line.pk]),
        ("product_bundle_detail", [bundle.pk]),
        ("product_bundle_edit", [bundle.pk]),
        ("quote_approval_rule_detail", [rule.pk]),
        ("quote_approval_rule_edit", [rule.pk]),
    ]
    for name, args in routes:
        response = client.get(reverse(f"sales:{name}", args=args))
        assert response.status_code in (302, 403), name
        if response.status_code == 302:
            assert "/login" in response["Location"], name


def test_quoteproposalcpq_configuration_routes_require_a_tenant_admin(db, tenant_a):
    """A rep may read the governance configuration but not rewrite it."""
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    currency = _quoteproposalcpq_currency()
    bundle = _quoteproposalcpq_bundle(
        tenant_a, _quoteproposalcpq_product(tenant_a, "Rack"), _quoteproposalcpq_product(tenant_a, "Server")
    )
    rule = _quoteproposalcpq_rule(tenant_a)
    client = _quoteproposalcpq_client(rep)
    for name, args in (
        ("product_bundle_create", []),
        ("product_bundle_edit", [bundle.pk]),
        ("quote_approval_rule_create", []),
        ("quote_approval_rule_edit", [rule.pk]),
    ):
        assert client.get(reverse(f"sales:{name}", args=args)).status_code == 403, name
    assert client.post(reverse("sales:product_bundle_delete", args=[bundle.pk])).status_code == 403
    assert client.post(reverse("sales:quote_approval_rule_delete", args=[rule.pk])).status_code == 403
    assert ProductBundleOption.objects.filter(pk=bundle.pk).exists()
    assert QuoteApprovalRule.objects.filter(pk=rule.pk).exists()


def test_quoteproposalcpq_a_rep_may_still_read_the_configuration(db, tenant_a):
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    currency = _quoteproposalcpq_currency()
    _quoteproposalcpq_quote(tenant_a, currency, name="Readable")
    client = _quoteproposalcpq_client(rep)
    for name in ("product_bundle_list", "quote_approval_rule_list", "cpq_quote_list", "quote_approval_queue"):
        assert client.get(reverse(f"sales:{name}")).status_code == 200, name


# ---------------------------------------------------------------------------
# Mass assignment
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_a_posted_tenant_is_ignored_on_create(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    client = _quoteproposalcpq_client(_quoteproposalcpq_admin(tenant_a))
    client.post(
        reverse("sales:cpq_quote_create"),
        {
            "name": "Boundary probe",
            "currency": str(currency.pk),
            "header_discount_pct": "",
            "tenant": str(tenant_b.pk),
            "status": "approved",
            "approval_status": "approved",
            "total": "999999.00",
        },
    )
    mine = CPQQuote.objects.filter(tenant=tenant_a, name="Boundary probe").first()
    assert mine is not None
    assert not CPQQuote.objects.filter(tenant=tenant_b, name="Boundary probe").exists()
    assert mine.status == "draft"
    assert mine.approval_status == "not_required"
    assert mine.total == Decimal("0.00")


def test_quoteproposalcpq_a_posted_signing_token_is_ignored(db, tenant_a):
    """The token is the portal's capability -- it must never be form-settable."""
    currency = _quoteproposalcpq_currency()
    client = _quoteproposalcpq_client(_quoteproposalcpq_admin(tenant_a))
    client.post(
        reverse("sales:cpq_quote_create"),
        {
            "name": "Token probe",
            "currency": str(currency.pk),
            "header_discount_pct": "",
            "signing_token": "attacker-chosen-token",
        },
    )
    quote = CPQQuote.objects.get(tenant=tenant_a, name="Token probe")
    assert quote.signing_token != "attacker-chosen-token"
    assert len(quote.signing_token) == 32



# ---------------------------------------------------------------------------
# The public portal: a capability token, not a session
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_signing_token_is_unique_per_quote(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    tokens = {
        _quoteproposalcpq_quote(tenant_a, currency, name=f"Proposal {index}").signing_token
        for index in range(8)
    }
    assert len(tokens) == 8
    assert all(len(token) >= 32 for token in tokens)


def test_quoteproposalcpq_a_quote_token_does_not_expose_another_quote(db, tenant_a):
    """The token addresses exactly one quote and reveals nothing else."""
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    presented = _quoteproposalcpq_quote(tenant_a, currency, name="Shared proposal", status="presented")
    _quoteproposalcpq_line(tenant_a, presented, description="Visible line")
    draft = _quoteproposalcpq_quote(tenant_a, currency, name="Unrelated internal draft")
    body = Client().get(reverse("sales:quote_portal_view", args=[presented.signing_token])).content.decode()
    assert "Visible line" in body
    assert draft.number not in body
    assert "Unrelated internal draft" not in body


def test_quoteproposalcpq_a_token_cannot_reach_another_tenants_quote(db, tenant_a, tenant_b):
    """Guessing tenant A's token must not surface tenant B's data."""
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    a_quote = _quoteproposalcpq_quote(tenant_a, currency, name="Acme shown", status="presented")
    _quoteproposalcpq_line(tenant_a, a_quote, description="Acme line")
    b_quote = _quoteproposalcpq_quote(tenant_b, currency, name="Globex shown", status="presented")
    _quoteproposalcpq_line(tenant_b, b_quote, description="Globex line")
    body = Client().get(reverse("sales:quote_portal_view", args=[a_quote.signing_token])).content.decode()
    assert "Acme line" in body
    assert "Globex line" not in body
    # quote numbers restart per tenant, so brand the record by name instead
    assert "Globex shown" not in body
    assert "Acme shown" in body


def test_quoteproposalcpq_an_unknown_token_is_404_not_500(db):
    from django.test import Client

    assert Client().get(reverse("sales:quote_portal_view", args=["deadbeef" * 4])).status_code == 404
    assert Client().post(reverse("sales:quote_portal_sign", args=["deadbeef" * 4])).status_code == 404


def test_quoteproposalcpq_a_token_cannot_toggle_another_quotes_line(db, tenant_a):
    """toggle_line is scoped to the quote the token names, not just the line pk."""
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    mine = _quoteproposalcpq_quote(tenant_a, currency, name="Mine", status="presented")
    other = _quoteproposalcpq_quote(tenant_a, currency, name="Theirs", status="presented")
    other_line = _quoteproposalcpq_line(tenant_a, other, description="Theirs", is_optional=True, is_selected=True)
    response = Client().post(
        reverse("sales:quote_portal_toggle_line", args=[mine.signing_token, other_line.pk])
    )
    assert response.status_code == 404
    other_line.refresh_from_db()
    assert other_line.is_selected is True



def test_quoteproposalcpq_a_draft_quote_token_cannot_be_signed(db, tenant_a):
    """C7: the public sign endpoint had no status guard before the fix."""
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    draft = _quoteproposalcpq_quote(tenant_a, currency, name="Internal draft", status="draft")
    _quoteproposalcpq_line(tenant_a, draft, description="Secret scope")
    Client().post(
        reverse("sales:quote_portal_sign", args=[draft.signing_token]),
        {
            "signer_name": "Mallory",
            "signer_title": "Nobody",
            "signer_email": "mallory@example.com",
            "signature_data": "Mallory",
            "agree_terms": "on",
        },
    )
    draft.refresh_from_db()
    assert draft.signed_at is None
    assert draft.signer_name == ""
    assert draft.status == "draft"


def test_quoteproposalcpq_an_already_signed_quote_cannot_be_re_signed(db, tenant_a):
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    accepted = _quoteproposalcpq_quote(
        tenant_a, currency, name="Done", status="accepted", signer_name="Dana"
    )
    Client().post(
        reverse("sales:quote_portal_sign", args=[accepted.signing_token]),
        {
            "signer_name": "Impostor",
            "signer_title": "Nobody",
            "signer_email": "impostor@example.com",
            "signature_data": "Impostor",
            "agree_terms": "on",
        },
    )
    accepted.refresh_from_db()
    assert accepted.signer_name == "Dana"


def test_quoteproposalcpq_the_portal_requires_an_explicit_terms_agreement(db, tenant_a):
    """Signing is a binding act, so the consent box is mandatory."""
    from django.test import Client

    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Needs consent", status="presented")
    response = Client().post(
        reverse("sales:quote_portal_sign", args=[quote.signing_token]),
        {
            "signer_name": "Dana Okafor",
            "signer_title": "VP Procurement",
            "signer_email": "dana@example.com",
            "signature_data": "Dana Okafor",
        },
    )
    assert response.status_code == 200  # re-renders the form carrying the error
    quote.refresh_from_db()
    assert quote.signed_at is None


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_mutating_routes_enforce_csrf(db, tenant_a):
    from django.test import Client

    admin = _quoteproposalcpq_admin(tenant_a)
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, status="draft")
    _quoteproposalcpq_line(tenant_a, quote)
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin)
    response = client.post(reverse("sales:cpq_quote_delete", args=[quote.pk]))
    assert response.status_code == 403
    assert CPQQuote.objects.filter(pk=quote.pk).exists()



# ---------------------------------------------------------------------------
# Template hygiene
# ---------------------------------------------------------------------------

QUOTEPROPOSALCPQ_TEMPLATES = [
    "sales/quote_proposal_cpq/cpqquote/list.html",
    "sales/quote_proposal_cpq/cpqquote/detail.html",
    "sales/quote_proposal_cpq/cpqquote/form.html",
    "sales/quote_proposal_cpq/cpqquoteline/list.html",
    "sales/quote_proposal_cpq/cpqquoteline/detail.html",
    "sales/quote_proposal_cpq/cpqquoteline/form.html",
    "sales/quote_proposal_cpq/productbundleoption/list.html",
    "sales/quote_proposal_cpq/productbundleoption/detail.html",
    "sales/quote_proposal_cpq/productbundleoption/form.html",
    "sales/quote_proposal_cpq/quoteapprovalrule/list.html",
    "sales/quote_proposal_cpq/quoteapprovalrule/detail.html",
    "sales/quote_proposal_cpq/quoteapprovalrule/form.html",
    "sales/quote_proposal_cpq/operations/approval_queue.html",
    "sales/quote_proposal_cpq/operations/approval_action.html",
    "sales/quote_proposal_cpq/operations/compare.html",
    "sales/quote_proposal_cpq/operations/conversion_board.html",
    "sales/quote_proposal_cpq/operations/guided_selling.html",
    "sales/quote_proposal_cpq/operations/portal.html",
    "sales/quote_proposal_cpq/operations/proposal_board.html",
    "sales/quote_proposal_cpq/operations/proposal_preview.html",
    "sales/quote_proposal_cpq/operations/version_list.html",
]


def test_quoteproposalcpq_every_cpq_template_compiles(db):
    """A template that does not compile 500s the whole lane."""
    from django.template.loader import get_template

    for source in QUOTEPROPOSALCPQ_TEMPLATES:
        assert get_template(source) is not None, source


def test_quoteproposalcpq_no_cpq_template_leaks_a_raw_django_comment(db):
    """L2: a multi-line {# ... #} is not a comment in Django and renders as text."""
    import re
    from pathlib import Path

    from django.conf import settings

    root = Path(settings.BASE_DIR) / "templates" / "sales" / "quote_proposal_cpq"
    assert root.is_dir(), root
    found = sorted(root.rglob("*.html"))
    assert len(found) == len(QUOTEPROPOSALCPQ_TEMPLATES), (
        f"the CPQ template inventory drifted: {len(found)} on disk vs "
        f"{len(QUOTEPROPOSALCPQ_TEMPLATES)} pinned"
    )
    for path in found:
        text = path.read_text(encoding="utf-8")
        leak = re.search(r"\{#", text)
        assert leak is None, f"{path.name} uses {{# ... #}} which leaks as visible text"


def test_quoteproposalcpq_no_cpq_template_uses_an_undefined_badge_colour(db):
    """L33: a semantic badge-success/-danger renders UNSTYLED. Copy colours only."""
    import re
    from pathlib import Path

    from django.conf import settings

    root = Path(settings.BASE_DIR) / "templates" / "sales" / "quote_proposal_cpq"
    semantic = re.compile(r"badge-(success|danger|warning|info-2|primary)\b")
    for path in sorted(root.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        assert semantic.search(text) is None, f"{path.name} uses a non-colour-named badge class"

