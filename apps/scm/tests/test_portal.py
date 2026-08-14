"""SCM 4.16 Customer Portal — regression locks for the defects this sub-module actually shipped.

Every class below is anchored on a REAL failure found and fixed during the 4.16 build, not on a
hypothetical. Where a test would still pass against the unfixed code it says so and asserts the
thing that would not.

WHAT THIS FILE DELIBERATELY DOES **NOT** COVER — read before adding a "we already test that":

* **Nothing here exercises the production database engine.** The suite runs on SQLite
  (``config.settings_test``) while the product runs on MariaDB, so ``select_for_update()`` is a
  no-op, partial/functional indexes are not built, and — most relevant to this sub-module —
  ``PortalDocumentShare.public_token``'s ``unique=True, null=True`` column relies on **MySQL/MariaDB
  NULL-distinctness under a unique index**, which SQLite spells the same way by accident rather than
  by the same rule. A green run here is NOT evidence about any of the three. The token-minting race
  (two rows reaching the database before ``save()`` mints a token) is therefore untested, and so are
  the index-shaped claims in the ``Meta.indexes`` comments.
* **No template is asserted through ``response.context``.** ``response.context`` is ``None`` unless
  ``django.test.utils.setup_test_environment()`` has run, and an assertion against ``None`` passes
  trivially — a whole QA pass was lost to that once. Every visibility claim below is asserted
  against the RENDERED BYTES, which is what the customer actually receives.
* **The ``.empty-state`` sweep uses a DEPTH-MATCHING scan, not a non-greedy regex.** A
  ``<div class="empty-state">(.*?)</div>`` pattern stops at the first NESTED ``</div>``, which in
  these templates is the icon/heading wrapper — so it silently skips the call-to-action links the
  audit exists to check, and reports a confident pass over nothing. ``_empty_state_blocks`` below is
  tested against that exact shape by ``test_the_scan_survives_a_nested_div``.

Fixture policy: the root ``conftest.py`` (``tenant_a``/``tenant_b``, ``admin_user``/``member_user``/
``admin_b``, ``client_a``/``client_b``/``member_client``) and the scm ``conftest.py`` (4.10's
``portal_user_a`` / ``portal_access_a`` / ``portal_client_a``, ``customer_a``, ``item_a``,
``sales_order_submitted_a``, …) are REUSED. Everything 4.16-specific is defined in THIS module with a
``pf_`` prefix, so nothing is added to the shared conftest and no name in another test module can be
rebound by importing this one.
"""
import datetime
import re
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone


# =================================================================================================
# Fixtures — all pf_-prefixed and local to this module
# =================================================================================================
@pytest.fixture
def pf_account_a(db, tenant_a, customer_a):
    """customer_a's portal account with EVERY entitlement on, including the money one.

    ``show_credit_and_balance`` defaults to ``False`` on the model (financial data is opt-in); it is
    switched on here so each entitlement test can turn exactly one thing OFF and measure it.
    """
    from apps.scm.models import PortalAccount
    return PortalAccount.objects.create(
        tenant=tenant_a, customer=customer_a, is_active=True,
        show_credit_and_balance=True, stock_display="availability_text",
        low_stock_threshold=Decimal("5.0000"), catalog_scope="all_active",
        price_basis="last_ordered", welcome_message="Welcome to your order portal.",
        support_email="support@acme.example",
    )


@pytest.fixture
def pf_other_customer_a(db, tenant_a):
    """A SECOND tenant_a customer — the counterparty in every "same tenant is not same customer" test."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Second Customer",
                                 kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="customer", status="active")
    return party


@pytest.fixture
def pf_other_account_a(db, tenant_a, pf_other_customer_a):
    from apps.scm.models import PortalAccount
    return PortalAccount.objects.create(tenant=tenant_a, customer=pf_other_customer_a)


@pytest.fixture
def pf_other_order_a(db, tenant_a, pf_other_customer_a, item_a, usd):
    """A SUBMITTED order belonging to the OTHER tenant_a customer."""
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(
        tenant=tenant_a, customer=pf_other_customer_a, order_date=timezone.localdate(),
        currency=usd, status="submitted")
    SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                  quantity_ordered=Decimal("2"), unit_price=Decimal("9.00"))
    order.recalc_totals()
    return order


@pytest.fixture
def pf_account_b(db, tenant_b, customer_b):
    from apps.scm.models import PortalAccount
    return PortalAccount.objects.create(tenant=tenant_b, customer=customer_b)


@pytest.fixture
def pf_media(settings, tmp_path):
    """A throwaway MEDIA_ROOT.

    ``FileSystemStorage`` clears its cached ``base_location`` on the ``setting_changed`` signal, so
    overriding the setting is enough for a file saved below to land under ``tmp_path`` rather than in
    the developer's real ``media/`` directory.
    """
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return settings.MEDIA_ROOT


#: The bytes the token route must stream verbatim. Distinctive, so a template accidentally rendering
#: the file instead of streaming it would be obvious.
PF_FILE_BYTES = b"%PDF-1.4 acme statement bytes 4.16"


@pytest.fixture
def pf_document_a(db, tenant_a, pf_media):
    """A tenant_a ``core.Document`` with REAL bytes on disk — the only shareable pointer with a file."""
    from apps.core.models import Document
    doc = Document.objects.create(tenant=tenant_a, name="Marchington statement.pdf",
                                  classification="internal", file="")
    doc.file.save("marchington.pdf", ContentFile(PF_FILE_BYTES), save=True)
    return doc


@pytest.fixture
def pf_confidential_document_a(db, tenant_a, pf_media):
    from apps.core.models import Document
    doc = Document.objects.create(tenant=tenant_a, name="Internal pricing.pdf",
                                  classification="confidential", file="")
    doc.file.save("pricing.pdf", ContentFile(b"never for a customer"), save=True)
    return doc


@pytest.fixture
def pf_share_a(db, tenant_a, pf_account_a, pf_document_a):
    """A LIVE share of that document. ``title`` carries a CR/LF and a traversal attempt on purpose —
    the ``Content-Disposition`` filename is built from it, and a header is a line-oriented format."""
    from apps.scm.models import PortalDocumentShare
    return PortalDocumentShare.objects.create(
        tenant=tenant_a, portal_account=pf_account_a, doc_type="other",
        title="Marchington statement\r\nX-Injected: 1 ../../etc/passwd",
        document=pf_document_a,
        expires_at=timezone.now() + datetime.timedelta(days=30))


@pytest.fixture
def pf_invoice_a(db, tenant_a, customer_a, usd):
    """A SENT invoice for customer_a — 987.65, the only place that figure appears."""
    from apps.accounting.models import Invoice
    return Invoice.objects.create(
        tenant=tenant_a, party=customer_a, kind="invoice", status="sent",
        issue_date=timezone.localdate(), currency=usd,
        subtotal=Decimal("987.65"), total=Decimal("987.65"))


@pytest.fixture
def pf_draft_invoice_a(db, tenant_a, customer_a, usd):
    """A DRAFT invoice — ours until we send it, and never shareable."""
    from apps.accounting.models import Invoice
    return Invoice.objects.create(
        tenant=tenant_a, party=customer_a, kind="invoice", status="draft",
        issue_date=timezone.localdate(), currency=usd, total=Decimal("55.00"))


@pytest.fixture
def pf_credit_note_a(db, tenant_a, customer_a, usd):
    """A SENT credit note — right status, wrong kind. The seeded-share defect pointed at one of these."""
    from apps.accounting.models import Invoice
    return Invoice.objects.create(
        tenant=tenant_a, party=customer_a, kind="credit_note", status="sent",
        issue_date=timezone.localdate(), currency=usd, total=Decimal("15.00"))


@pytest.fixture
def pf_customer_profile_a(db, tenant_a, customer_a, usd, payment_terms_a):
    """The AR profile behind the credit block — 432.10 appears nowhere else on the page."""
    from apps.accounting.models import CustomerProfile
    return CustomerProfile.objects.create(
        tenant=tenant_a, party=customer_a, credit_limit=Decimal("432.10"),
        currency=usd, payment_terms=payment_terms_a)


@pytest.fixture
def pf_inquiry_a(db, tenant_a, pf_account_a, sales_order_submitted_a, admin_user):
    from apps.scm.models import PortalOrderInquiry
    return PortalOrderInquiry.open_for(
        tenant=tenant_a, portal_account=pf_account_a, subject="Where is my order?",
        description="Nothing has arrived.", user=admin_user, source="portal",
        inquiry_type="wismo", sales_order=sales_order_submitted_a)


@pytest.fixture
def pf_inquiry_b(db, tenant_b, pf_account_b, admin_b):
    from apps.scm.models import PortalOrderInquiry
    return PortalOrderInquiry.open_for(
        tenant=tenant_b, portal_account=pf_account_b, subject="Globex question",
        description="A general question.", user=admin_b, source="staff",
        inquiry_type="other")


@pytest.fixture
def pf_share_b(db, tenant_b, pf_account_b, evidence_document_b):
    from apps.scm.models import PortalDocumentShare
    return PortalDocumentShare.objects.create(
        tenant=tenant_b, portal_account=pf_account_b, doc_type="other",
        title="Globex statement", document=evidence_document_b)


@pytest.fixture
def pf_activity_b(db, pf_account_b):
    from apps.scm.models import PortalActivity
    return PortalActivity.record(pf_account_b, "login", object_label="Globex")


# --- the deliberately EMPTY account: a brand-new customer, the modal first session ---------------
@pytest.fixture
def pf_empty_customer_a(db, tenant_a):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Brand New Customer",
                                 kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="customer", status="active")
    return party


@pytest.fixture
def pf_empty_account_a(db, tenant_a, pf_empty_customer_a):
    """Everything switched ON and nothing behind it — zero orders, documents, invoices, inquiries."""
    from apps.scm.models import PortalAccount
    return PortalAccount.objects.create(
        tenant=tenant_a, customer=pf_empty_customer_a, is_active=True,
        show_credit_and_balance=True, stock_display="band", catalog_scope="all_active")


@pytest.fixture
def pf_empty_client(db, tenant_a, pf_empty_account_a, pf_empty_customer_a):
    from apps.accounts.models import User
    from apps.crm.models import CustomerPortalAccess
    user = User.objects.create_user(email="newshopper@acme.com", username="newshopper_acme",
                                    password="TestPass123!", tenant=tenant_a)
    CustomerPortalAccess.objects.create(tenant=tenant_a, customer_party=pf_empty_customer_a,
                                        portal_user=user, is_active=True)
    client = Client()
    client.force_login(user)
    return client


# =================================================================================================
# Helpers
# =================================================================================================
#: Opening tag of an empty state, whatever else is in its class attribute.
_EMPTY_STATE_OPEN = re.compile(r'<div\b[^>]*class="[^"]*\bempty-state\b[^"]*"[^>]*>')
#: The sibling block these templates deliberately put the call to action in — see
#: ``_empty_state_blocks``. Anchored, so it only matches when it IMMEDIATELY follows the close.
_ACTIONS_OPEN = re.compile(r'\s*<div\b[^>]*class="[^"]*\bpage-actions\b[^"]*"[^>]*>')
#: Any div boundary. Used by the DEPTH scan below — never as a lone terminator.
_DIV_BOUNDARY = re.compile(r"<div\b|</div\s*>")
_HREF = re.compile(r'href="([^"]*)"')


def _div_end(html, position):
    """Walk forward from just inside an open ``<div>`` to just past its matching close."""
    depth = 1
    while depth:
        boundary = _DIV_BOUNDARY.search(html, position)
        if boundary is None:                  # unbalanced markup — take what there is
            return len(html)
        position = boundary.end()
        depth += 1 if boundary.group(0).startswith("<div") else -1
    return position


def _empty_state_blocks(html):
    """Every ``.empty-state`` block **plus the ``.page-actions`` block that immediately follows it**,
    matched by DEPTH rather than by the first ``</div>``.

    Two traps, and the sweep is worthless if it falls into either:

    1. The naive ``<div class="empty-state">(.*?)</div>`` truncates at the first NESTED close — in
       these templates that is the icon or heading wrapper — so the anchors an empty-state audit
       exists to follow are never seen and the sweep reports a clean pass over an empty set.
       ``test_the_scan_survives_a_nested_div`` pins that difference.
    2. ``customer_orders.html`` documents that its call-to-action buttons sit **outside**
       ``.empty-state`` on purpose (theme.css sizes every ``<i>`` inside that block to 40px, so an
       icon button placed within it renders enormous). A scan that stopped at the block's own
       closing tag would therefore skip five of the six links on the page every new customer lands
       on. Including the adjacent ``.page-actions`` block follows the convention the templates
       actually use, and still never reaches the global sidebar or top bar.
    """
    blocks = []
    for opening in _EMPTY_STATE_OPEN.finditer(html):
        start = opening.end()
        position = _div_end(html, start)
        block = html[start:position]
        actions = _ACTIONS_OPEN.match(html, position)
        if actions is not None:
            block += html[actions.end():_div_end(html, actions.end())]
        blocks.append(block)
    return blocks


def _links_in(html):
    """In-app hrefs inside the page's empty states — anchors only, deduplicated, order preserved."""
    found = []
    for block in _empty_state_blocks(html):
        for href in _HREF.findall(block):
            target = href.replace("&amp;", "&").strip()
            if target.startswith("/") and target not in found:
                found.append(target)
    return found


#: Every argument-free customer-facing page. ``portal_inquiry_create`` is a form and is swept for
#: 200s but is not required to carry an empty state.
PF_CUSTOMER_PAGES = ["scm:portal_home", "scm:portal_order_list", "scm:portal_documents",
                     "scm:portal_catalog", "scm:portal_profile"]

#: The junk a hand-edited query string actually carries. ``²`` is the interesting one — ``isdigit()``
#: says yes and ``int()`` says no — and the 20-digit value converts cleanly and then overflows
#: inside the driver.
PF_JUNK_VALUES = ["abc", "²", "99999999999999999999", "-1"]


def _post_inquiry(**overrides):
    data = {"subject": "Where is my order?", "description": "Nothing has arrived yet.",
            "inquiry_type": "other", "requested_resolution": "information"}
    data.update(overrides)
    return data


# =================================================================================================
# 1. `_portal_account` — the refusal ladder. Each rung refuses; none falls through.
# =================================================================================================
@pytest.mark.django_db
class TestPortalIdentityRefusalLadder:
    """``user -> crm.CustomerPortalAccess (active) -> customer_party -> scm.PortalAccount (active)``.

    The failure mode this ladder exists to prevent is not a crash: a ``party`` of ``None`` turns
    "this customer's own orders" into a filter on NULL, which for an OR-composed or nullable-FK
    lookup is *everybody's*. So each test asserts the REFUSAL (a redirect away from the portal) and
    — where there is data to leak — that no other customer's row reached the response body.
    """

    def test_a_user_with_no_access_row_is_refused(self, member_client, pf_account_a):
        """``member_user`` is a perfectly ordinary tenant_a login with no ``CustomerPortalAccess``."""
        response = member_client.get(reverse("scm:portal_home"))
        assert response.status_code == 302
        assert reverse("dashboard:home") in response["Location"]

    def test_an_inactive_access_row_is_refused(self, portal_client_a, portal_access_a,
                                               pf_account_a):
        portal_access_a.is_active = False
        portal_access_a.save(update_fields=["is_active"])
        response = portal_client_a.get(reverse("scm:portal_home"))
        assert response.status_code == 302
        assert reverse("dashboard:home") in response["Location"]

    def test_an_access_row_with_no_customer_is_refused_not_scoped_to_null(
            self, portal_client_a, portal_access_a, pf_account_a, pf_other_order_a):
        """THE one that matters. ``customer_party = None`` must refuse, never scope on NULL.

        ``pf_other_order_a`` belongs to a DIFFERENT customer of the same workspace, so a page that
        fell through to an unscoped queryset would render its number.
        """
        portal_access_a.customer_party = None
        portal_access_a.save(update_fields=["customer_party"])
        for name in PF_CUSTOMER_PAGES:
            response = portal_client_a.get(reverse(name), follow=True)
            assert response.status_code == 200
            assert response.redirect_chain, f"{name} served a portal page with no customer resolved"
            assert reverse("dashboard:home") in response.redirect_chain[-1][0]
            assert pf_other_order_a.number not in response.content.decode(), (
                f"{name} rendered another customer's order for an access row with no customer")

    def test_a_customer_with_no_portal_account_is_refused_on_every_page(
            self, portal_client_a, pf_other_order_a, sales_order_submitted_a):
        """No ``PortalAccount`` row = the portal was never switched on. That is what makes the staff
        enablement console mean anything, so it must refuse rather than show a default projection."""
        for name in PF_CUSTOMER_PAGES + ["scm:portal_inquiry_create"]:
            response = portal_client_a.get(reverse(name))
            assert response.status_code == 302, f"{name} did not refuse"
            assert reverse("dashboard:home") in response["Location"]

    def test_a_deactivated_portal_account_is_refused(self, portal_client_a, pf_account_a,
                                                     sales_order_submitted_a):
        pf_account_a.is_active = False
        pf_account_a.save(update_fields=["is_active"])
        response = portal_client_a.get(reverse("scm:portal_home"), follow=True)
        assert response.status_code == 200
        assert sales_order_submitted_a.number not in response.content.decode()

    def test_an_anonymous_visitor_is_sent_to_the_login_page(self, db):
        for name in PF_CUSTOMER_PAGES + ["scm:portal_inquiry_create"]:
            response = Client().get(reverse(name))
            assert response.status_code == 302
            assert "/login" in response["Location"] or "next=" in response["Location"]

    def test_the_resolver_returns_a_pair_and_never_a_bare_account(self, rf, tenant_a,
                                                                  portal_user_a, portal_access_a,
                                                                  pf_account_a):
        """The ``(portal, refusal)`` SHAPE is the guard: a caller that ignores the second element
        gets an AttributeError on a tuple, which is loud. The shape it replaced — return the account
        or ``None`` — fails quietly, by scoping a query to ``None``."""
        from django.contrib.messages.storage.fallback import FallbackStorage
        from apps.scm.views._helpers import _portal_account

        request = rf.get("/scm/portal/")
        request.user = portal_user_a
        request.tenant = tenant_a
        request.session = {}
        request._messages = FallbackStorage(request)

        portal, refusal = _portal_account(request)
        assert refusal is None
        assert portal.account == pf_account_a
        assert portal.party == pf_account_a.customer
        assert portal.access == portal_access_a


# =================================================================================================
# 2. Entitlements are SERVER-SIDE. Each flag off = the page refuses or the data is absent.
# =================================================================================================
@pytest.mark.django_db
class TestEntitlementsAreEnforcedNotHidden:
    """Every assertion is against the rendered bytes.

    "The button is hidden" is not an access control, and neither is "the context key is empty" —
    ``response.context`` is ``None`` without ``setup_test_environment()`` and an assertion on it
    passes for the wrong reason.
    """

    def test_track_shipments_off_refuses_both_order_pages(self, portal_client_a, pf_account_a,
                                                          sales_order_submitted_a):
        pf_account_a.can_track_shipments = False
        pf_account_a.save(update_fields=["can_track_shipments"])
        for path in (reverse("scm:portal_order_list"),
                     reverse("scm:portal_order_detail", args=[sales_order_submitted_a.pk])):
            response = portal_client_a.get(path)
            assert response.status_code == 302, f"{path} served an ungated order page"
            assert reverse("scm:portal_home") in response["Location"]

    def test_track_shipments_off_removes_the_orders_from_the_home_page(
            self, portal_client_a, pf_account_a, sales_order_submitted_a):
        """Gated BEFORE the queryset is built: the tile's rows are never fetched, so a template that
        forgot its ``{% if %}`` has nothing to leak."""
        on = portal_client_a.get(reverse("scm:portal_home")).content.decode()
        assert sales_order_submitted_a.number in on, "denominator — the order must be visible when on"
        pf_account_a.can_track_shipments = False
        pf_account_a.save(update_fields=["can_track_shipments"])
        off = portal_client_a.get(reverse("scm:portal_home")).content.decode()
        assert sales_order_submitted_a.number not in off

    def test_view_documents_off_refuses_the_library_and_kills_the_live_link(
            self, portal_client_a, pf_account_a, pf_share_a):
        """One control, two surfaces. An admin who unticks the box reasonably believes the links
        already sitting in a customer's inbox died — before the fix, every one of them stayed live."""
        download = reverse("scm:portal_document_download", args=[pf_share_a.public_token])
        assert Client().get(download).status_code == 200, "denominator — the link works when on"

        pf_account_a.can_view_documents = False
        pf_account_a.save(update_fields=["can_view_documents"])

        listing = portal_client_a.get(reverse("scm:portal_documents"))
        assert listing.status_code == 302
        assert reverse("scm:portal_home") in listing["Location"]
        assert Client().get(download).status_code == 404, (
            "the bearer link outlived the entitlement that authorises it")

    def test_view_documents_off_removes_the_share_from_the_home_page(
            self, portal_client_a, pf_account_a, pf_share_a):
        on = portal_client_a.get(reverse("scm:portal_home")).content.decode()
        assert "Marchington" in on, "denominator — the share must be visible when on"
        pf_account_a.can_view_documents = False
        pf_account_a.save(update_fields=["can_view_documents"])
        off = portal_client_a.get(reverse("scm:portal_home")).content.decode()
        assert "Marchington" not in off

    def test_raise_inquiries_off_refuses_the_form_and_the_post(self, portal_client_a, pf_account_a,
                                                               sales_order_submitted_a):
        from apps.scm.models import PortalOrderInquiry
        pf_account_a.can_raise_inquiries = False
        pf_account_a.save(update_fields=["can_raise_inquiries"])
        path = reverse("scm:portal_inquiry_create")

        assert portal_client_a.get(path).status_code == 302
        response = portal_client_a.post(path, _post_inquiry())
        assert response.status_code == 302
        assert reverse("scm:portal_home") in response["Location"]
        assert not PortalOrderInquiry.objects.filter(portal_account=pf_account_a).exists(), (
            "a POST filed an inquiry the gate refuses to render a form for")

    def test_credit_and_balance_off_removes_the_figures_from_the_profile(
            self, portal_client_a, pf_account_a, pf_customer_profile_a, pf_invoice_a):
        path = reverse("scm:portal_profile")
        on = portal_client_a.get(path).content.decode()
        assert "432.10" in on, "denominator — the credit limit must render when on"

        pf_account_a.show_credit_and_balance = False
        pf_account_a.save(update_fields=["show_credit_and_balance"])
        off = portal_client_a.get(path).content.decode()
        assert "432.10" not in off, "the credit limit survived the entitlement being switched off"

    def test_credit_and_balance_off_removes_the_balance_from_the_home_page(
            self, portal_client_a, pf_account_a, pf_invoice_a):
        """987.65 is the invoice total and appears on the home page only through the balance tile."""
        path = reverse("scm:portal_home")
        assert "987.65" in portal_client_a.get(path).content.decode(), "denominator"
        pf_account_a.show_credit_and_balance = False
        pf_account_a.save(update_fields=["show_credit_and_balance"])
        assert "987.65" not in portal_client_a.get(path).content.decode()

    def test_view_invoices_off_removes_the_invoice_history(self, portal_client_a, pf_account_a,
                                                           pf_invoice_a):
        path = reverse("scm:portal_profile")
        on = portal_client_a.get(path).content.decode()
        assert pf_invoice_a.number in on, "denominator — the invoice must be listed when on"

        pf_account_a.can_view_invoices = False
        pf_account_a.save(update_fields=["can_view_invoices"])
        off = portal_client_a.get(path).content.decode()
        assert pf_invoice_a.number not in off


# =================================================================================================
# 3. `can_request_returns` is enforced at 4.10's route, and 4.10 must not regress
# =================================================================================================
@pytest.mark.django_db
class TestReturnRequestEntitlement:
    """4.16 hides the "Request a return" button on four pages. Hiding a button is not an access
    control — ``scm:portal_return_create`` is a plain URL anybody who has seen it can type."""

    def test_the_entitlement_off_refuses_the_route(self, portal_client_a, pf_account_a):
        pf_account_a.can_request_returns = False
        pf_account_a.save(update_fields=["can_request_returns"])
        response = portal_client_a.get(reverse("scm:portal_return_create"))
        assert response.status_code == 302
        assert reverse("dashboard:home") in response["Location"]

    def test_the_entitlement_off_refuses_a_crafted_post(self, portal_client_a, pf_account_a,
                                                        item_a, return_reason_a):
        from apps.scm.models import ReturnAuthorization
        pf_account_a.can_request_returns = False
        pf_account_a.save(update_fields=["can_request_returns"])
        before = ReturnAuthorization.objects.count()
        portal_client_a.post(reverse("scm:portal_return_create"),
                             {"item": str(item_a.pk), "reason": str(return_reason_a.pk),
                              "quantity_requested": "1"})
        assert ReturnAuthorization.objects.count() == before

    def test_a_deactivated_account_refuses_the_route(self, portal_client_a, pf_account_a):
        pf_account_a.is_active = False
        pf_account_a.save(update_fields=["is_active"])
        response = portal_client_a.get(reverse("scm:portal_return_create"))
        assert response.status_code == 302

    def test_the_entitlement_on_still_serves_the_form(self, portal_client_a, pf_account_a):
        assert portal_client_a.get(reverse("scm:portal_return_create")).status_code == 200

    def test_a_customer_with_no_portal_account_is_still_allowed(self, portal_client_a):
        """4.10 PREDATES 4.16. Requiring a ``PortalAccount`` here would silently switch returns off
        for every tenant that never adopts 4.16 — a regression in one sub-module caused by a later
        one. The rule only ever SUBTRACTS: no account means nothing changed."""
        from apps.scm.models import PortalAccount
        assert not PortalAccount.objects.exists(), "fixture guard — this test needs NO account"
        assert portal_client_a.get(reverse("scm:portal_return_create")).status_code == 200


# =================================================================================================
# 4. The public token route — every refusal is the SAME bare 404
# =================================================================================================
@pytest.mark.django_db
class TestTokenDownload:
    """The one endpoint in 4.16 that serves bytes to somebody with no login at all.

    Every refusal below must be indistinguishable from a wrong token: a message (or a status) that
    separated "expired" from "revoked" from "wrong workspace" hands an enumerator a classifier.
    """

    def _download(self, share):
        return reverse("scm:portal_document_download", args=[share.public_token])

    def test_a_live_share_streams_the_bytes_to_an_anonymous_holder(self, pf_share_a):
        response = Client().get(self._download(pf_share_a))
        assert response.status_code == 200
        assert response.streaming, "the file must stream through the view"
        assert b"".join(response.streaming_content) == PF_FILE_BYTES

    def test_the_response_is_never_a_redirect_into_media(self, pf_share_a, settings):
        """``config/urls.py`` serves ``MEDIA_URL`` directly under ``DEBUG``, so a redirect to
        ``obj.file.url`` would make the token decorative — the ``/media/...`` path answers without
        it. Asserting the absence of the redirect, not merely the presence of the bytes."""
        response = Client().get(self._download(pf_share_a))
        assert response.status_code == 200
        assert "Location" not in response
        assert settings.MEDIA_URL not in response.headers.get("Content-Disposition", "")

    def test_the_filename_cannot_carry_a_header_or_a_path(self, pf_share_a):
        """``title`` is free text a staff user typed and a header is a line-oriented format.

        The property is that no SEPARATOR survives — a CR or LF would split the response header and
        a ``/`` or ``..`` would escape the download directory. The injected *word* legitimately
        survives as ordinary filename text (``X-Injected`` is only ``\\w`` and ``-``): it is inert
        once the newline that would have made it a header is gone, and stripping alphanumerics would
        mangle every honest title without adding any protection.
        """
        disposition = Client().get(self._download(pf_share_a)).headers["Content-Disposition"]
        assert "attachment" in disposition
        assert "\r" not in disposition and "\n" not in disposition, (
            "a CR/LF in the share title reached the response header")
        filename = disposition.split("filename=")[-1]
        assert "/" not in filename and "\\" not in filename
        assert ".." not in filename
        assert filename.strip('"').endswith(".pdf"), "the stored extension should still be appended"

    def test_a_download_stamps_the_evidence_trail_once(self, pf_share_a, pf_account_a):
        from apps.scm.models import PortalActivity
        Client().get(self._download(pf_share_a))
        pf_share_a.refresh_from_db()
        assert pf_share_a.download_count == 1
        assert pf_share_a.first_viewed_at is not None
        assert PortalActivity.objects.filter(portal_account=pf_account_a,
                                             action="download_document").count() == 1

    def test_a_wrong_token_is_404(self, pf_share_a):
        assert Client().get(reverse("scm:portal_document_download",
                                    args=["not-a-real-token"])).status_code == 404

    def test_a_revoked_share_is_404(self, pf_share_a):
        assert pf_share_a.revoke() is True
        assert Client().get(self._download(pf_share_a)).status_code == 404

    def test_an_expired_share_is_404(self, pf_share_a):
        pf_share_a.expires_at = timezone.now() - datetime.timedelta(minutes=1)
        pf_share_a.save(update_fields=["expires_at"])
        assert Client().get(self._download(pf_share_a)).status_code == 404

    def test_a_deactivated_account_kills_its_links(self, pf_share_a, pf_account_a):
        pf_account_a.is_active = False
        pf_account_a.save(update_fields=["is_active"])
        assert Client().get(self._download(pf_share_a)).status_code == 404

    def test_a_deactivated_tenant_stops_serving(self, pf_share_a, tenant_a):
        """The tenant is taken OFF THE OBJECT — ``request.tenant`` is None for an anonymous visitor
        — so a churned or suspended workspace has to be re-checked here or not at all."""
        tenant_a.is_active = False
        tenant_a.save(update_fields=["is_active"])
        assert Client().get(self._download(pf_share_a)).status_code == 404

    def test_a_confidential_document_is_404(self, tenant_a, pf_account_a,
                                            pf_confidential_document_a):
        from apps.scm.models import PortalDocumentShare
        share = PortalDocumentShare.objects.create(
            tenant=tenant_a, portal_account=pf_account_a, doc_type="other",
            title="Pricing", document=pf_confidential_document_a)
        assert Client().get(self._download(share)).status_code == 404, (
            "a file whose own record says it is not for outsiders was served to a bearer")

    def test_an_invoice_the_customer_may_not_see_is_404(self, tenant_a, pf_account_a,
                                                       pf_invoice_a, pf_draft_invoice_a,
                                                       pf_credit_note_a):
        """A share is created once and read for as long as it lives, so ``kind``/``status`` are
        re-checked when the bytes are served rather than only when the row was written."""
        from apps.scm.models import PortalDocumentShare
        visible = PortalDocumentShare.objects.create(
            tenant=tenant_a, portal_account=pf_account_a, doc_type="invoice",
            title="Invoice", invoice=pf_invoice_a)
        # Denominator: a sent invoice resolves. It has no file on disk (it is a RENDERED document),
        # so the view answers in plain text rather than streaming — that is a 200, not a 404.
        assert Client().get(self._download(visible)).status_code == 200

        for invoice in (pf_draft_invoice_a, pf_credit_note_a):
            share = PortalDocumentShare.objects.create(
                tenant=tenant_a, portal_account=pf_account_a, doc_type="invoice",
                title="Not for you", invoice=invoice)
            assert Client().get(self._download(share)).status_code == 404, (
                f"a {invoice.kind}/{invoice.status} invoice was served through a bearer token")

    def test_a_voided_invoice_share_stops_working(self, tenant_a, pf_account_a, pf_invoice_a):
        from apps.scm.models import PortalDocumentShare
        share = PortalDocumentShare.objects.create(
            tenant=tenant_a, portal_account=pf_account_a, doc_type="invoice",
            title="Invoice", invoice=pf_invoice_a)
        assert Client().get(self._download(share)).status_code == 200
        pf_invoice_a.status = "void"
        pf_invoice_a.save(update_fields=["status"])
        assert Client().get(self._download(share)).status_code == 404

    def test_post_is_405(self, pf_share_a):
        """An unauthenticated endpoint should accept exactly the method it is for. A POST reaching a
        bare view is a CSRF-shaped request arriving where there is no CSRF protection to have."""
        assert Client().post(self._download(pf_share_a)).status_code == 405

    def test_a_missing_file_on_disk_is_404_and_never_a_500(self, pf_share_a, pf_document_a):
        pf_document_a.file.storage.delete(pf_document_a.file.name)
        assert Client().get(self._download(pf_share_a)).status_code == 404

    def test_a_refused_download_writes_no_evidence(self, pf_share_a):
        """Both ``record_download()`` and the activity row are read in a dispute as *the customer
        received this document*, so neither may fire for a retrieval that failed."""
        from apps.scm.models import PortalActivity
        pf_share_a.revoke()
        Client().get(self._download(pf_share_a))
        pf_share_a.refresh_from_db()
        assert pf_share_a.download_count == 0
        assert not PortalActivity.objects.filter(action="download_document").exists()


# =================================================================================================
# 5. Cross-tenant IDOR — 404 on every detail route
# =================================================================================================
@pytest.mark.django_db
class TestCrossTenantIsolation:

    def test_every_staff_detail_route_404s_across_tenants(self, client_a, pf_account_b, pf_share_b,
                                                          pf_inquiry_b, pf_activity_b):
        """404, never 302 or 403 — a redirect leaks "there is a row there, you just cannot have it"."""
        targets = [
            reverse("scm:portalaccount_detail", args=[pf_account_b.pk]),
            reverse("scm:portalaccount_edit", args=[pf_account_b.pk]),
            reverse("scm:portaldocumentshare_detail", args=[pf_share_b.pk]),
            reverse("scm:portaldocumentshare_edit", args=[pf_share_b.pk]),
            reverse("scm:portalorderinquiry_detail", args=[pf_inquiry_b.pk]),
            reverse("scm:portalorderinquiry_edit", args=[pf_inquiry_b.pk]),
            reverse("scm:portalactivity_detail", args=[pf_activity_b.pk]),
        ]
        assert len(targets) >= 7, "denominator guard — the sweep must not silently shrink"
        leaks = [(t, client_a.get(t).status_code) for t in targets]
        leaks = [(t, code) for t, code in leaks if code != 404]
        assert not leaks, leaks

    def test_every_post_only_verb_404s_across_tenants(self, client_a, pf_account_b, pf_share_b,
                                                      pf_inquiry_b):
        targets = [
            reverse("scm:portalaccount_delete", args=[pf_account_b.pk]),
            reverse("scm:portaldocumentshare_delete", args=[pf_share_b.pk]),
            reverse("scm:portaldocumentshare_revoke", args=[pf_share_b.pk]),
            reverse("scm:portalorderinquiry_delete", args=[pf_inquiry_b.pk]),
            reverse("scm:portalorderinquiry_resolve", args=[pf_inquiry_b.pk]),
            reverse("scm:portalorderinquiry_reopen", args=[pf_inquiry_b.pk]),
        ]
        leaks = [(t, client_a.post(t, {"outcome": "duplicate"}).status_code) for t in targets]
        leaks = [(t, code) for t, code in leaks if code != 404]
        assert not leaks, leaks

    def test_a_customer_cannot_open_another_tenants_order(self, portal_client_a, pf_account_a,
                                                          sales_order_b):
        """The ownership check is IN THE LOOKUP, so another customer's order — and this customer's
        own draft — answer 404 rather than 403."""
        assert portal_client_a.get(
            reverse("scm:portal_order_detail", args=[sales_order_b.pk])).status_code == 404

    def test_a_customer_cannot_open_a_sibling_customers_order(self, portal_client_a, pf_account_a,
                                                              pf_other_order_a):
        """Same tenant is NOT the same customer — the case a tenant filter alone would let through."""
        assert portal_client_a.get(
            reverse("scm:portal_order_detail", args=[pf_other_order_a.pk])).status_code == 404

    def test_a_customer_cannot_open_their_own_draft_order(self, portal_client_a, pf_account_a,
                                                          sales_order_a):
        """A draft is internal work in progress — quantities and prices are still being negotiated."""
        assert sales_order_a.status == "draft"
        assert portal_client_a.get(
            reverse("scm:portal_order_detail", args=[sales_order_a.pk])).status_code == 404

    def test_the_order_list_never_carries_another_customers_row(self, portal_client_a,
                                                                pf_account_a, pf_other_order_a,
                                                                sales_order_submitted_a):
        body = portal_client_a.get(reverse("scm:portal_order_list")).content.decode()
        assert sales_order_submitted_a.number in body, "denominator — own order must be listed"
        assert pf_other_order_a.number not in body

    def test_a_crafted_portal_account_pk_cannot_bind_a_share_across_tenants(
            self, client_a, pf_account_b, pf_document_a):
        """A narrowed dropdown has never held against a crafted POST. Asserting the ROW COUNT: a 200
        re-rendering the form with an error and a 200 that quietly saved look identical outside."""
        from apps.scm.models import PortalDocumentShare
        before = PortalDocumentShare.objects.count()
        client_a.post(reverse("scm:portaldocumentshare_create"), {
            "portal_account": str(pf_account_b.pk), "doc_type": "other", "title": "Crafted",
            "document": str(pf_document_a.pk),
            "expires_at": (timezone.localtime(timezone.now()) +
                           datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
        })
        assert PortalDocumentShare.objects.count() == before


# =================================================================================================
# 6. The counterparty rule — same tenant is not the same customer
# =================================================================================================
@pytest.mark.django_db
class TestInquiryCounterpartyRule:
    """Everything else in ``clean()`` proves the FKs belong to this WORKSPACE. None of it proved
    they belong to the CUSTOMER whose portal the inquiry is filed under — and the staff form's
    ``sales_order`` queryset is tenant-wide, so a POST naming Acme's account and Contoso's order
    validated cleanly. ``portal_home`` filters on ``portal_account`` alone, so Acme's own portal page
    would then have rendered Contoso's order number."""

    def test_clean_rejects_another_customers_order_keyed_on_sales_order(
            self, tenant_a, pf_account_a, pf_other_order_a):
        from apps.scm.models import PortalOrderInquiry
        inquiry = PortalOrderInquiry(tenant=tenant_a, portal_account=pf_account_a,
                                     sales_order=pf_other_order_a, inquiry_type="wismo")
        with pytest.raises(ValidationError) as caught:
            inquiry.clean()
        assert "sales_order" in caught.value.error_dict, (
            "the counterparty refusal must be keyed on the field the staff form declares")

    def test_open_for_refuses_and_leaves_no_orphan_case(self, tenant_a, pf_account_a,
                                                        pf_other_order_a, admin_user):
        """``full_clean()`` runs INSIDE the atomic block, after the case exists — without the
        transaction every rejected submission would leave a customer-visible ticket in the CRM
        queue."""
        from apps.crm.models import Case
        from apps.scm.models import PortalOrderInquiry
        before = Case.objects.count()
        with pytest.raises(ValidationError) as caught:
            PortalOrderInquiry.open_for(
                tenant=tenant_a, portal_account=pf_account_a, subject="Where is it?",
                description="...", user=admin_user, source="staff",
                inquiry_type="wismo", sales_order=pf_other_order_a)
        assert "sales_order" in caught.value.error_dict
        assert Case.objects.count() == before, "a rejected inquiry left an orphaned crm.Case"

    def test_the_customers_own_order_is_accepted(self, tenant_a, pf_account_a,
                                                 sales_order_submitted_a, admin_user):
        """Denominator: the rule must not reject the legitimate case it was written around."""
        from apps.scm.models import PortalOrderInquiry
        inquiry = PortalOrderInquiry.open_for(
            tenant=tenant_a, portal_account=pf_account_a, subject="Where is it?",
            description="...", user=admin_user, source="staff",
            inquiry_type="wismo", sales_order=sales_order_submitted_a)
        assert inquiry.pk is not None
        assert inquiry.number.startswith("PIQ-")
        assert inquiry.source == "staff"
        assert inquiry.outcome == "open"

    def test_a_crafted_staff_post_naming_another_customers_order_is_refused(
            self, client_a, pf_account_a, pf_other_order_a):
        from apps.scm.models import PortalOrderInquiry
        before = PortalOrderInquiry.objects.count()
        response = client_a.post(reverse("scm:portalorderinquiry_create"), {
            "portal_account": str(pf_account_a.pk),
            "sales_order": str(pf_other_order_a.pk),
            "inquiry_type": "wismo", "requested_resolution": "information",
            "subject": "Crafted", "description": "Crafted",
        })
        assert response.status_code == 200, "the refusal must render a form error, never a 500"
        assert PortalOrderInquiry.objects.count() == before


# =================================================================================================
# 7. `invoice_dispute` on the CUSTOMER form — a validation error, never a 500
# =================================================================================================
@pytest.mark.django_db
class TestCustomerInquiryFormUnsupportedType:
    """``clean()`` raises ``{"invoice": …}`` for an invoice dispute, ``_post_clean`` forwards it to
    ``add_error("invoice")``, and ``add_error`` on a field the form does not declare raises
    ``ValueError`` — a **500 on a customer-facing page** for anybody who picked "Invoice dispute".

    Two locks, because the fix has two halves: the option is no longer offered (the primary fix), and
    a crafted POST carrying it is an ordinary field error (the backstop)."""

    def test_the_option_is_not_offered(self, tenant_a, customer_a):
        from apps.scm.forms import PortalInquiryCustomerForm
        form = PortalInquiryCustomerForm(tenant=tenant_a, customer=customer_a)
        values = [value for value, _label in form.fields["inquiry_type"].choices]
        assert "invoice_dispute" not in values
        assert "wismo" in values, "denominator — the vocabulary must not have been emptied"

    def test_the_option_is_not_rendered_on_the_page(self, portal_client_a, pf_account_a):
        html = portal_client_a.get(reverse("scm:portal_inquiry_create")).content.decode()
        assert 'value="invoice_dispute"' not in html
        assert 'value="wismo"' in html, "denominator — the select must still be rendered"

    def test_the_form_has_no_invoice_field_at_all(self, tenant_a, customer_a):
        """The reason the choice cannot be offered: an invoice picker here would expose a document
        ``can_view_invoices`` gates separately."""
        from apps.scm.forms import PortalInquiryCustomerForm
        assert "invoice" not in PortalInquiryCustomerForm(tenant=tenant_a,
                                                          customer=customer_a).fields

    def test_a_crafted_post_is_a_field_error_not_a_500(self, portal_client_a, pf_account_a,
                                                       sales_order_submitted_a):
        from apps.scm.models import PortalOrderInquiry
        response = portal_client_a.post(reverse("scm:portal_inquiry_create"), _post_inquiry(
            inquiry_type="invoice_dispute", sales_order=str(sales_order_submitted_a.pk)))
        assert response.status_code == 200, (
            "the crafted choice raised out of add_error instead of rendering an error")
        assert not PortalOrderInquiry.objects.exists()

    def test_a_legitimate_submission_still_files_the_inquiry(self, portal_client_a, pf_account_a,
                                                             sales_order_submitted_a):
        """Denominator for the whole class: removing the option must not have broken the form."""
        from apps.scm.models import PortalOrderInquiry
        response = portal_client_a.post(reverse("scm:portal_inquiry_create"), _post_inquiry(
            inquiry_type="wismo", sales_order=str(sales_order_submitted_a.pk)))
        assert response.status_code == 302
        inquiry = PortalOrderInquiry.objects.get()
        assert inquiry.source == "portal", "source is forced server-side, never taken from the POST"
        assert inquiry.portal_account_id == pf_account_a.pk
        assert inquiry.case_id is not None


# =================================================================================================
# 8. The share form could not create a share at all
# =================================================================================================
@pytest.mark.django_db
class TestShareFormCanActuallyCreateAShare:
    """``_scope_pointers`` read the account off ``self.instance`` alone. The create view hands in
    ``PortalDocumentShare(tenant=…)`` with no account, so ``customer_id`` was ``None``, all six
    pointer querysets collapsed to ``.none()``, and the user was offered nothing to pick — on the GET
    *and* on the POST, so a valid choice could not even be re-validated. The seeder builds rows with
    ``objects.create()``, which never touches a form, which is exactly why the demo data looked
    healthy."""

    def _form(self, **kwargs):
        from apps.scm.forms import PortalDocumentShareForm
        from apps.scm.models import PortalDocumentShare
        kwargs.setdefault("instance", PortalDocumentShare(tenant=kwargs["tenant"]))
        return PortalDocumentShareForm(**kwargs)

    def test_initial_populates_the_pointer_dropdowns(self, tenant_a, pf_account_a, pf_document_a,
                                                     pf_invoice_a):
        form = self._form(tenant=tenant_a, initial={"portal_account": pf_account_a.pk})
        assert pf_document_a in form.fields["document"].queryset
        assert pf_invoice_a in form.fields["invoice"].queryset

    def test_the_bound_post_repopulates_them(self, tenant_a, pf_account_a, pf_document_a):
        """The POST path matters on its own: a queryset is also the VALIDATOR, so an empty one
        rejects the choice the user just made."""
        form = self._form(tenant=tenant_a,
                          data={"portal_account": str(pf_account_a.pk), "doc_type": "other",
                                "title": "Statement", "document": str(pf_document_a.pk)})
        assert pf_document_a in form.fields["document"].queryset

    def test_no_account_still_means_no_pointers(self, tenant_a, pf_document_a):
        """The empty fallback is deliberate — a tenant-wide default would offer every customer's
        invoices in one select and the first one picked would belong to whoever the user scrolled to."""
        form = self._form(tenant=tenant_a)
        assert list(form.fields["document"].queryset) == []

    def test_junk_in_the_account_slot_leaves_the_dropdowns_empty_not_a_500(self, tenant_a,
                                                                          pf_document_a):
        for junk in PF_JUNK_VALUES:
            form = self._form(tenant=tenant_a, initial={"portal_account": junk})
            assert list(form.fields["document"].queryset) == []

    def test_a_share_can_be_created_through_the_form(self, tenant_a, pf_account_a, pf_document_a):
        from apps.scm.models import PortalDocumentShare
        expires = (timezone.localtime(timezone.now()) +
                   datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
        form = self._form(tenant=tenant_a,
                          data={"portal_account": str(pf_account_a.pk), "doc_type": "other",
                                "title": "March statement", "document": str(pf_document_a.pk),
                                "expires_at": expires})
        assert form.is_valid(), form.errors
        share = form.save(commit=False)
        share.tenant = tenant_a
        share.save()
        assert PortalDocumentShare.objects.filter(pk=share.pk).exists()
        assert share.public_token, "the bearer token is minted in save()"

    def test_a_share_can_be_created_through_the_view(self, client_a, pf_account_a, pf_document_a):
        """End to end, because a form test alone would not notice the view handing in an instance
        with no tenant."""
        from apps.scm.models import PortalDocumentShare
        expires = (timezone.localtime(timezone.now()) +
                   datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
        response = client_a.post(reverse("scm:portaldocumentshare_create"), {
            "portal_account": str(pf_account_a.pk), "doc_type": "other",
            "title": "March statement", "document": str(pf_document_a.pk),
            "expires_at": expires})
        assert response.status_code == 302, "the create POST did not save"
        share = PortalDocumentShare.objects.get()
        assert share.portal_account_id == pf_account_a.pk
        assert share.shared_by_id is not None, "shared_by is stamped server-side"

    def test_expiry_is_required_on_create(self, tenant_a, pf_account_a, pf_document_a):
        """CREATE is ``@login_required`` while edit and revoke are admin-only, so without this a
        member could mint a link that NEVER expires and only an admin can then kill."""
        form = self._form(tenant=tenant_a,
                          data={"portal_account": str(pf_account_a.pk), "doc_type": "other",
                                "title": "Forever", "document": str(pf_document_a.pk)})
        assert not form.is_valid()
        assert "expires_at" in form.errors

    def test_the_invoice_dropdown_offers_no_draft_and_no_credit_note(
            self, tenant_a, pf_account_a, pf_invoice_a, pf_draft_invoice_a, pf_credit_note_a):
        """The seeder walked straight into this: every demo share pointed at a draft CREDIT NOTE and
        the anonymous bearer token served it."""
        form = self._form(tenant=tenant_a, initial={"portal_account": pf_account_a.pk})
        offered = list(form.fields["invoice"].queryset)
        assert pf_invoice_a in offered
        assert pf_draft_invoice_a not in offered
        assert pf_credit_note_a not in offered

    def test_the_document_dropdown_offers_no_confidential_file(self, tenant_a, pf_account_a,
                                                               pf_document_a,
                                                               pf_confidential_document_a):
        form = self._form(tenant=tenant_a, initial={"portal_account": pf_account_a.pk})
        offered = list(form.fields["document"].queryset)
        assert pf_document_a in offered
        assert pf_confidential_document_a not in offered

    def test_the_credential_is_not_a_form_field(self, tenant_a, pf_account_a):
        """L20 — a secret in ``Meta.fields`` ships plaintext in the edit form."""
        form = self._form(tenant=tenant_a)
        for name in ("public_token", "revoked_at", "download_count", "first_viewed_at",
                     "last_downloaded_at", "shared_by"):
            assert name not in form.fields

    def test_the_token_is_never_rendered_on_the_staff_pages(self, client_a, pf_share_a):
        for path in (reverse("scm:portaldocumentshare_list"),
                     reverse("scm:portaldocumentshare_detail", args=[pf_share_a.pk])):
            assert pf_share_a.public_token not in client_a.get(path).content.decode(), (
                f"{path} printed the bearer credential as text")


# =================================================================================================
# 9. PortalAccount.clean(), and the seeded demo rows surviving their own edit form
# =================================================================================================
@pytest.mark.django_db
class TestPortalAccountValidation:

    def test_a_threshold_against_an_exact_quantity_display_is_refused(self, tenant_a, customer_a):
        """A number a user typed and the system silently dropped is worse than an error: they leave
        believing it applied. Only the availability-text and colour-band displays read it."""
        from apps.scm.models import PortalAccount
        account = PortalAccount(tenant=tenant_a, customer=customer_a,
                                stock_display="exact_quantity",
                                low_stock_threshold=Decimal("25.0000"))
        with pytest.raises(ValidationError) as caught:
            account.clean()
        assert "low_stock_threshold" in caught.value.error_dict

    def test_a_threshold_against_a_hidden_display_is_refused(self, tenant_a, customer_a):
        from apps.scm.models import PortalAccount
        account = PortalAccount(tenant=tenant_a, customer=customer_a, stock_display="hidden",
                                low_stock_threshold=Decimal("1.0000"))
        with pytest.raises(ValidationError):
            account.clean()

    def test_a_threshold_against_the_two_displays_that_read_it_is_accepted(self, tenant_a,
                                                                          customer_a):
        from apps.scm.models import PortalAccount
        for display in ("availability_text", "band"):
            PortalAccount(tenant=tenant_a, customer=customer_a, stock_display=display,
                          low_stock_threshold=Decimal("25.0000")).clean()

    def test_a_ship_to_belonging_to_another_customer_is_refused(self, tenant_a, customer_a,
                                                                pf_other_customer_a):
        from apps.core.models import Address
        from apps.scm.models import PortalAccount
        address = Address.objects.create(tenant=tenant_a, party=pf_other_customer_a,
                                         kind="shipping", line1="1 Other Street")
        account = PortalAccount(tenant=tenant_a, customer=customer_a, default_ship_to=address)
        with pytest.raises(ValidationError) as caught:
            account.clean()
        assert "default_ship_to" in caught.value.error_dict

    def test_activated_on_is_stamped_once_and_never_restamped(self, tenant_a, customer_a):
        from apps.scm.models import PortalAccount
        account = PortalAccount.objects.create(tenant=tenant_a, customer=customer_a)
        first = account.activated_on
        assert first == timezone.localdate()
        account.is_active = False
        account.save(update_fields=["is_active", "updated_at"])
        account.is_active = True
        account.save(update_fields=["is_active", "updated_at"])
        account.refresh_from_db()
        assert account.activated_on == first, (
            "a deactivate/reactivate cycle rewrote the adoption date")

    def test_activated_on_is_not_a_form_field(self, tenant_a):
        from apps.scm.forms import PortalAccountForm
        form = PortalAccountForm(tenant=tenant_a)
        for name in ("tenant", "number", "activated_on", "created_at", "updated_at"):
            assert name not in form.fields

    def test_the_categories_scope_needs_at_least_one_category(self, tenant_a, customer_a):
        """The rule can only live on the FORM: an M2M has no rows until after ``save()``, so the
        equivalent model check would see an empty set for every create."""
        from apps.scm.forms import PortalAccountForm
        form = PortalAccountForm(tenant=tenant_a, data={
            "customer": str(customer_a.pk), "is_active": "on", "stock_display": "band",
            "low_stock_threshold": "0", "catalog_scope": "categories", "price_basis": "hidden",
            "preferred_channel": "email"})
        assert not form.is_valid()
        assert "catalog_categories" in form.errors

    def test_every_seeded_demo_account_survives_full_clean(self, tenant_a, admin_user, item_a,
                                                           category_a, sales_order_submitted_a,
                                                           pf_other_order_a, non_supplier_party_a):
        """Demo data that cannot survive its own edit form is a trap laid for whoever clicks it
        first — the seeded ``exact_quantity`` account carried a threshold ``clean()`` refuses, and
        ``objects.create()`` skips ``full_clean()``, so it saved happily and then failed on Save."""
        from apps.scm.management.commands.seed_scm import Command
        from apps.scm.models import PortalAccount

        Command()._seed_portal_tenant(tenant_a)
        accounts = list(PortalAccount.objects.filter(tenant=tenant_a))
        assert len(accounts) >= 2, (
            "the seeder produced fewer accounts than expected — this test would pass over nothing")
        for account in accounts:
            account.full_clean()


# =================================================================================================
# 10. The staff console is an IAM surface — create/edit are admin-only
# =================================================================================================
@pytest.mark.django_db
class TestPortalAccountAdminGate:
    """This row decides more than a CRM portal login does: ``show_credit_and_balance`` publishes the
    workspace's AR position to an outsider and ``stock_display="exact_quantity"`` publishes its stock
    position."""

    def test_a_member_cannot_reach_create_or_edit(self, member_client, pf_account_a):
        for path in (reverse("scm:portalaccount_create"),
                     reverse("scm:portalaccount_edit", args=[pf_account_a.pk])):
            assert member_client.get(path).status_code == 403, f"{path} was open to a member"

    def test_a_member_cannot_post_create_or_edit(self, member_client, pf_account_a, customer_a):
        from apps.scm.models import PortalAccount
        before = PortalAccount.objects.count()
        member_client.post(reverse("scm:portalaccount_create"), {
            "customer": str(customer_a.pk), "stock_display": "band", "low_stock_threshold": "0",
            "catalog_scope": "all_active", "price_basis": "hidden", "preferred_channel": "email"})
        assert PortalAccount.objects.count() == before

        member_client.post(reverse("scm:portalaccount_edit", args=[pf_account_a.pk]), {
            "customer": str(pf_account_a.customer_id), "stock_display": "exact_quantity",
            "low_stock_threshold": "0", "catalog_scope": "all_active", "price_basis": "hidden",
            "preferred_channel": "email", "show_credit_and_balance": "on"})
        pf_account_a.refresh_from_db()
        assert pf_account_a.stock_display == "availability_text"

    def test_a_member_cannot_delete_an_account(self, member_client, pf_account_a):
        from apps.scm.models import PortalAccount
        assert member_client.post(
            reverse("scm:portalaccount_delete", args=[pf_account_a.pk])).status_code == 403
        assert PortalAccount.objects.filter(pk=pf_account_a.pk).exists()

    def test_the_delete_route_refuses_get(self, client_a, pf_account_a):
        from apps.scm.models import PortalAccount
        assert client_a.get(
            reverse("scm:portalaccount_delete", args=[pf_account_a.pk])).status_code == 405
        assert PortalAccount.objects.filter(pk=pf_account_a.pk).exists()

    def test_an_admin_can_reach_them(self, client_a, pf_account_a):
        """Denominator: the fix must not have been "gate it for everybody"."""
        for path in (reverse("scm:portalaccount_create"),
                     reverse("scm:portalaccount_edit", args=[pf_account_a.pk])):
            assert client_a.get(path).status_code == 200

    def test_a_member_cannot_edit_or_revoke_a_share(self, member_client, pf_share_a):
        """``expires_at`` (on the edit form) and ``revoked_at`` (the admin verb) are two halves of
        ONE control — blank means never expires, on a share only an admin may revoke."""
        assert member_client.get(
            reverse("scm:portaldocumentshare_edit", args=[pf_share_a.pk])).status_code == 403
        assert member_client.post(
            reverse("scm:portaldocumentshare_revoke", args=[pf_share_a.pk])).status_code == 403
        pf_share_a.refresh_from_db()
        assert pf_share_a.revoked_at is None

    def test_csrf_is_enforced_on_the_staff_create_post(self, admin_user, customer_a):
        from apps.scm.models import PortalAccount
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin_user)
        response = client.post(reverse("scm:portalaccount_create"), {
            "customer": str(customer_a.pk), "stock_display": "band", "low_stock_threshold": "0",
            "catalog_scope": "all_active", "price_basis": "hidden", "preferred_channel": "email"})
        assert response.status_code == 403
        assert not PortalAccount.objects.exists()

    def test_csrf_is_enforced_on_the_customer_inquiry_post(self, portal_user_a, portal_access_a,
                                                           pf_account_a, sales_order_submitted_a):
        from apps.scm.models import PortalOrderInquiry
        client = Client(enforce_csrf_checks=True)
        client.force_login(portal_user_a)
        response = client.post(reverse("scm:portal_inquiry_create"), _post_inquiry(
            inquiry_type="wismo", sales_order=str(sales_order_submitted_a.pk)))
        assert response.status_code == 403
        assert not PortalOrderInquiry.objects.exists()


# =================================================================================================
# 11. The empty state — the modal first session, and the branch no smoke sweep renders
# =================================================================================================
@pytest.mark.django_db
class TestEmptyStates:
    """``pf_empty_client`` is a fully-entitled portal customer with ZERO orders, documents,
    invoices, inquiries and items. That is what every account looks like the day it is switched on,
    and it is the branch a seeded smoke sweep can never reach."""

    def test_the_scan_survives_a_nested_div(self):
        """The harness's own regression lock. A non-greedy ``(.*?)</div>`` stops at the NESTED close
        and never sees the anchor — which is exactly the link an empty-state audit exists to follow.
        This test fails if ``_empty_state_blocks`` is ever "simplified" back to that."""
        html = ('<div class="card"><div class="empty-state">'
                '<div class="icon"><i></i></div><h3>Nothing</h3>'
                '<a href="/scm/portal/catalog/">Browse</a></div></div>')
        blocks = _empty_state_blocks(html)
        assert len(blocks) == 1
        assert "/scm/portal/catalog/" in blocks[0], (
            "the scan truncated at the first nested </div> and skipped the call to action")
        naive = re.search(r'<div class="empty-state">(.*?)</div>', html)
        assert "/scm/portal/catalog/" not in naive.group(1), (
            "the naive pattern is supposed to MISS it — if it does not, this test proves nothing")

    def test_the_scan_reaches_the_sibling_call_to_action_block(self):
        """``customer_orders.html`` puts its buttons in a ``.page-actions`` sibling on purpose (an
        ``<i>`` inside ``.empty-state`` is sized to 40px by theme.css). A scan that stopped at the
        block's own ``</div>`` would skip five of the six links on the page a brand-new customer
        lands on — and would report a confident pass having followed none of them."""
        html = ('<div class="card-body"><div class="empty-state">'
                '<i></i><h3>No orders</h3></div>'
                '<div class="page-actions"><a href="/scm/portal/catalog/">Browse</a>'
                '<a href="/scm/return-portal/request/">Return</a></div></div>')
        blocks = _empty_state_blocks(html)
        assert len(blocks) == 1
        assert "/scm/portal/catalog/" in blocks[0]
        assert "/scm/return-portal/request/" in blocks[0]

    def test_every_customer_page_is_200_on_a_brand_new_account(self, pf_empty_client):
        broken = [(name, pf_empty_client.get(reverse(name)).status_code)
                  for name in PF_CUSTOMER_PAGES + ["scm:portal_inquiry_create"]]
        broken = [row for row in broken if row[1] != 200]
        assert not broken, broken

    def test_every_list_and_gated_page_renders_its_empty_branch(self, pf_empty_client):
        missing = []
        for name in PF_CUSTOMER_PAGES:
            html = pf_empty_client.get(reverse(name)).content.decode()
            if not _empty_state_blocks(html):
                missing.append(name)
        assert not missing, (
            "these pages rendered no .empty-state block for an account with nothing in it, so "
            f"nothing below is being checked on them: {missing}")

    def test_every_empty_state_link_accepts_a_GET(self, pf_empty_client):
        """The 4.14 defect exactly: a call to action pointing at a POST-only route renders as an
        ordinary link and is a guaranteed 405 on click. Checked by ISSUING the GET, which is what a
        click does — probing the decorator reports a confident, wrong zero."""
        seen, bad = set(), []
        for name in PF_CUSTOMER_PAGES:
            html = pf_empty_client.get(reverse(name)).content.decode()
            for target in _links_in(html):
                if target in seen:
                    continue
                seen.add(target)
                code = pf_empty_client.get(target).status_code
                if code == 405:
                    bad.append(f"{name} links to {target} -> 405 (POST-only route)")
                elif code >= 500:
                    bad.append(f"{name} links to {target} -> {code}")
        # The MEASURED denominator (6: catalog, documents, inquiries/add, return-portal/request,
        # profile, home), asserted rather than assumed. Zero anchors followed and zero failures is
        # indistinguishable from a clean sweep, and is how a scan that stopped matching the rendered
        # HTML would keep reporting green.
        assert len(seen) >= 6, (
            f"only {len(seen)} in-app links were followed inside the empty states — too few to be a "
            "real sweep; the anchor scan has probably stopped matching the rendered HTML")
        assert not bad, bad

    def test_a_missing_figure_is_never_rendered_as_zero(self, pf_empty_client):
        """``None`` and ``0`` are different statements. *No invoice exists* is not *you owe
        nothing*, and the templates render the first as an em-dash."""
        html = pf_empty_client.get(reverse("scm:portal_home")).content.decode()
        assert "—" in html, "the em-dash for an absent figure never rendered"

    def test_the_catalog_of_an_empty_workspace_is_not_a_500(self, pf_empty_client):
        assert pf_empty_client.get(reverse("scm:portal_catalog")).status_code == 200


# =================================================================================================
# 12. Junk GET parameters — 200, never 500
# =================================================================================================
@pytest.mark.django_db
class TestJunkQueryParameters:
    """``?category=²`` is the interesting one: ``isdigit()`` says yes and ``int()`` says no. The
    20-digit value converts cleanly and then overflows inside the database driver."""

    def _sweep(self, client, paths_and_params):
        broken = []
        for path, param in paths_and_params:
            for junk in PF_JUNK_VALUES + [""]:
                code = client.get(f"{path}?{param}={junk}").status_code
                if code != 200:
                    broken.append((path, param, junk, code))
        assert not broken, broken

    def test_the_customer_pages_survive_junk_filters(self, portal_client_a, pf_account_a,
                                                     sales_order_submitted_a, pf_share_a, item_a):
        self._sweep(portal_client_a, [
            (reverse("scm:portal_catalog"), "category"),
            (reverse("scm:portal_catalog"), "q"),
            (reverse("scm:portal_catalog"), "page"),
            (reverse("scm:portal_order_list"), "status"),
            (reverse("scm:portal_order_list"), "q"),
            (reverse("scm:portal_order_list"), "page"),
            (reverse("scm:portal_documents"), "doc_type"),
            (reverse("scm:portal_documents"), "q"),
            (reverse("scm:portal_documents"), "page"),
            (reverse("scm:portal_inquiry_create"), "sales_order"),
            (reverse("scm:portal_inquiry_create"), "shipment"),
            (reverse("scm:portal_inquiry_create"), "inquiry_type"),
        ])

    def test_the_staff_lists_survive_junk_filters(self, client_a, pf_account_a, pf_share_a,
                                                  pf_inquiry_a):
        self._sweep(client_a, [
            (reverse("scm:portalaccount_list"), "customer"),
            (reverse("scm:portalaccount_list"), "is_active"),
            (reverse("scm:portalaccount_list"), "stock_display"),
            (reverse("scm:portalaccount_list"), "page"),
            (reverse("scm:portaldocumentshare_list"), "portal_account"),
            (reverse("scm:portaldocumentshare_list"), "state"),
            (reverse("scm:portaldocumentshare_list"), "doc_type"),
            (reverse("scm:portalorderinquiry_list"), "portal_account"),
            (reverse("scm:portalorderinquiry_list"), "sales_order"),
            (reverse("scm:portalorderinquiry_list"), "sla"),
            (reverse("scm:portalactivity_list"), "portal_account"),
            (reverse("scm:portalactivity_list"), "action"),
            (reverse("scm:portalactivity_list"), "date_from"),
            (reverse("scm:portalactivity_list"), "date_to"),
        ])

    def test_a_junk_status_narrows_nothing_and_is_not_echoed_as_selected(self, portal_client_a,
                                                                        pf_account_a,
                                                                        sales_order_submitted_a):
        """A hand-edited value that narrowed nothing must not render as the selected option, or the
        page shows a filter that did not happen (the 4.14 ``effective`` finding)."""
        html = portal_client_a.get(
            reverse("scm:portal_order_list") + "?status=abc").content.decode()
        assert sales_order_submitted_a.number in html, "a junk status filtered the rows out"
        assert 'value="abc"' not in html

    def test_a_page_past_the_end_is_the_last_page_not_a_500(self, portal_client_a, pf_account_a,
                                                            sales_order_submitted_a):
        for path in (reverse("scm:portal_order_list"), reverse("scm:portal_documents"),
                     reverse("scm:portal_catalog")):
            assert portal_client_a.get(f"{path}?page=9999").status_code == 200

    def test_page_two_works_when_the_rows_exceed_the_page_size(self, portal_client_a, pf_account_a,
                                                              tenant_a, customer_a, item_a, usd):
        """PORTAL_PAGE_SIZE is 12, so 15 orders is a genuine second page rather than a guess."""
        from apps.scm.models import SalesOrder
        for index in range(15):
            SalesOrder.objects.create(tenant=tenant_a, customer=customer_a, currency=usd,
                                      status="submitted",
                                      order_date=timezone.localdate() - datetime.timedelta(days=index))
        first = portal_client_a.get(reverse("scm:portal_order_list"))
        second = portal_client_a.get(reverse("scm:portal_order_list") + "?page=2")
        assert first.status_code == second.status_code == 200
        assert first.content != second.content, "page 2 rendered the same rows as page 1"


# =================================================================================================
# Negative input on the two write paths — a friendly refusal, never a 500, never a fall-through
# =================================================================================================
@pytest.mark.django_db
class TestNegativeInputHardening:
    """``quantity_affected`` is the only number a customer types in 4.16, and the inquiry verbs are
    the only place a staff POST names a value the model must refuse."""

    @pytest.mark.parametrize("quantity", ["NaN", "sNaN", "Infinity", "-1", "abc", "1e999",
                                          "99999999999999.9999", "12345678901.0000"])
    def test_a_hostile_quantity_is_a_form_error_not_a_500(self, portal_client_a, pf_account_a,
                                                          sales_order_submitted_a, quantity):
        """``max_digits=14, decimal_places=4`` leaves ten integer digits, so the last two values are
        over the column's ceiling — the shape that raises ``DataError`` from the driver if it is
        allowed as far as the INSERT."""
        from apps.scm.models import PortalOrderInquiry
        line = sales_order_submitted_a.lines.first()
        response = portal_client_a.post(reverse("scm:portal_inquiry_create"), _post_inquiry(
            inquiry_type="short_shipment", sales_order=str(sales_order_submitted_a.pk),
            sales_order_line=str(line.pk), quantity_affected=quantity))
        assert response.status_code == 200, f"{quantity!r} was not refused cleanly"
        assert not PortalOrderInquiry.objects.exists()

    def test_a_legitimate_quantity_on_a_line_still_files(self, portal_client_a, pf_account_a,
                                                         sales_order_submitted_a):
        """The denominator for the whole parametrized sweep above: the same POST with a SANE
        quantity must succeed, or every refusal test could be passing for an unrelated reason."""
        from apps.scm.models import PortalOrderInquiry
        line = sales_order_submitted_a.lines.first()
        response = portal_client_a.post(reverse("scm:portal_inquiry_create"), _post_inquiry(
            inquiry_type="short_shipment", sales_order=str(sales_order_submitted_a.pk),
            sales_order_line=str(line.pk), quantity_affected="3"))
        assert response.status_code == 302
        assert PortalOrderInquiry.objects.get().quantity_affected == Decimal("3.0000")

    def test_a_quantity_with_no_line_is_rejected_not_accepted_anyway(self, portal_client_a,
                                                                    pf_account_a,
                                                                    sales_order_submitted_a):
        """L35 — the absent prerequisite must be REFUSED, never allowed to fall through. A quantity
        has to be a quantity OF something, or the claim cannot be checked against what was sold."""
        from apps.scm.models import PortalOrderInquiry
        response = portal_client_a.post(reverse("scm:portal_inquiry_create"), _post_inquiry(
            inquiry_type="short_shipment", sales_order=str(sales_order_submitted_a.pk),
            quantity_affected="3"))
        assert response.status_code == 200
        assert not PortalOrderInquiry.objects.exists()

    def test_a_claim_larger_than_the_line_is_rejected(self, portal_client_a, pf_account_a,
                                                      sales_order_submitted_a):
        """A claim for more units than we sold is a credit note waiting to be written for goods that
        never existed. The fixture line ordered 10."""
        from apps.scm.models import PortalOrderInquiry
        line = sales_order_submitted_a.lines.first()
        assert line.quantity_ordered == Decimal("10")
        response = portal_client_a.post(reverse("scm:portal_inquiry_create"), _post_inquiry(
            inquiry_type="short_shipment", sales_order=str(sales_order_submitted_a.pk),
            sales_order_line=str(line.pk), quantity_affected="11"))
        assert response.status_code == 200
        assert not PortalOrderInquiry.objects.exists()

    def test_an_order_bound_type_with_no_order_is_rejected(self, portal_client_a, pf_account_a):
        """A WISMO ticket with no order is a question nobody can answer and a row that can never
        join to a shipment."""
        from apps.scm.models import PortalOrderInquiry
        response = portal_client_a.post(reverse("scm:portal_inquiry_create"),
                                        _post_inquiry(inquiry_type="wismo"))
        assert response.status_code == 200
        assert not PortalOrderInquiry.objects.exists()

    @pytest.mark.parametrize("outcome", ["", "banana", "open", "rma_raised"])
    def test_a_junk_resolve_outcome_is_a_message_not_a_500(self, client_a, pf_inquiry_a, outcome):
        """``open`` and ``rma_raised`` are deliberately NOT resolvable: reopening is its own verb,
        and an inquiry badged "RMA raised" with no return to click is a lie the list page repeats."""
        response = client_a.post(reverse("scm:portalorderinquiry_resolve", args=[pf_inquiry_a.pk]),
                                 {"outcome": outcome})
        assert response.status_code == 302
        pf_inquiry_a.refresh_from_db()
        assert pf_inquiry_a.outcome == "open"
        assert pf_inquiry_a.resolved_at is None

    def test_a_legitimate_resolve_still_works(self, client_a, pf_inquiry_a):
        """Denominator: the guard must not have made the verb unusable."""
        client_a.post(reverse("scm:portalorderinquiry_resolve", args=[pf_inquiry_a.pk]),
                      {"outcome": "information_provided", "note": "Delivered on Tuesday."})
        pf_inquiry_a.refresh_from_db()
        assert pf_inquiry_a.outcome == "information_provided"
        assert pf_inquiry_a.resolved_at is not None

    @pytest.mark.parametrize("raw", PF_JUNK_VALUES + [""])
    def test_a_junk_rma_pk_on_raise_return_is_a_message_not_a_500(self, client_a, pf_inquiry_a,
                                                                  raw):
        response = client_a.post(
            reverse("scm:portalorderinquiry_raise_return", args=[pf_inquiry_a.pk]),
            {"return_authorization": raw})
        assert response.status_code == 302
        pf_inquiry_a.refresh_from_db()
        assert pf_inquiry_a.return_authorization_id is None
        assert pf_inquiry_a.outcome == "open"

    def test_the_customers_own_rma_links_and_badges_the_inquiry(self, client_a, tenant_a,
                                                                pf_account_a, customer_a,
                                                                return_policy_a, usd, admin_user):
        """Denominator for the two refusals above, and the only writer of ``return_authorization``:
        ``rma_raised`` is not resolvable precisely so the badge always has a document behind it."""
        from apps.scm.models import PortalOrderInquiry, ReturnAuthorization
        inquiry = PortalOrderInquiry.open_for(
            tenant=tenant_a, portal_account=pf_account_a, subject="Return please",
            description="...", user=admin_user, source="staff", inquiry_type="return_request")
        rma = ReturnAuthorization.objects.create(
            tenant=tenant_a, customer=customer_a, policy=return_policy_a,
            requested_on=timezone.localdate(), currency=usd)
        client_a.post(reverse("scm:portalorderinquiry_raise_return", args=[inquiry.pk]),
                      {"return_authorization": str(rma.pk)})
        inquiry.refresh_from_db()
        assert inquiry.return_authorization_id == rma.pk
        assert inquiry.outcome == "rma_raised"

    def test_another_customers_rma_cannot_be_linked(self, client_a, tenant_a, pf_account_a,
                                                    pf_other_customer_a, return_policy_a,
                                                    return_reason_a, item_a, usd, admin_user):
        """Linking another customer's return here would publish its number, dates and disposition on
        this customer's portal inquiry — an authorisation rule, not a typo check."""
        from apps.scm.models import PortalOrderInquiry, ReturnAuthorization
        inquiry = PortalOrderInquiry.open_for(
            tenant=tenant_a, portal_account=pf_account_a, subject="Return please",
            description="...", user=admin_user, source="staff", inquiry_type="return_request")
        rma = ReturnAuthorization.objects.create(
            tenant=tenant_a, customer=pf_other_customer_a, policy=return_policy_a,
            requested_on=timezone.localdate(), currency=usd)
        response = client_a.post(
            reverse("scm:portalorderinquiry_raise_return", args=[inquiry.pk]),
            {"return_authorization": str(rma.pk)})
        assert response.status_code == 302
        inquiry.refresh_from_db()
        assert inquiry.return_authorization_id is None
        assert inquiry.outcome == "open"


# =================================================================================================
# The list pages must not be N+1 — including the chained __str__ FK hops
# =================================================================================================
@pytest.mark.django_db
class TestListPagesAreNotNPlusOne:

    def test_the_customer_document_list_does_not_grow_with_its_rows(
            self, portal_client_a, pf_account_a, pf_document_a, django_assert_max_num_queries):
        from apps.scm.models import PortalDocumentShare
        for index in range(8):
            PortalDocumentShare.objects.create(
                tenant=pf_account_a.tenant, portal_account=pf_account_a, doc_type="other",
                title=f"Statement {index}", document=pf_document_a)
        with django_assert_max_num_queries(20):
            assert portal_client_a.get(reverse("scm:portal_documents")).status_code == 200

    def test_the_staff_account_list_does_not_grow_with_its_rows(
            self, client_a, tenant_a, django_assert_max_num_queries):
        """``obj.linked_user_count`` and ``obj.has_never_logged_in`` are a query per row each — this
        page annotates instead, and the bound is what keeps it that way."""
        from apps.core.models import Party, PartyRole
        from apps.scm.models import PortalAccount
        for index in range(10):
            party = Party.objects.create(tenant=tenant_a, name=f"Customer {index}",
                                         kind="organization")
            PartyRole.objects.create(tenant=tenant_a, party=party, role="customer")
            PortalAccount.objects.create(tenant=tenant_a, customer=party)
        with django_assert_max_num_queries(25):
            assert client_a.get(reverse("scm:portalaccount_list")).status_code == 200

    def test_the_activity_list_does_not_grow_with_its_rows(self, client_a, pf_account_a,
                                                           django_assert_max_num_queries):
        """``PortalActivity.__str__`` walks ``portal_account.customer`` — a chained FK hop, which is
        two joins per row without ``select_related``."""
        from apps.scm.models import PortalActivity
        for index in range(10):
            PortalActivity.record(pf_account_a, "view_order", object_label=f"SO-{index}")
        with django_assert_max_num_queries(20):
            assert client_a.get(reverse("scm:portalactivity_list")).status_code == 200
