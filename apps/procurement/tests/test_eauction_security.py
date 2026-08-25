"""Procurement 6.7 E-Auction Management — security tests.

Pins the POST-fix reality of views/EAuctionManagement/{Auctions,Bids}.py:

* every staff-side pk route resolves through ``get_object_or_404(tenant=request.tenant)``
  BEFORE any verb logic → cross-tenant ids are 404, never 200/500;
* ``staff_required`` admits ANY workspace member (``user.tenant_id == request.tenant.pk``):
  a vendor-portal login that carries a tenant row therefore PASSES the buyer-console gate —
  a known accepted limitation, asserted here as-is;
* ``_bound_supplier`` pins ANY active ``VendorPortalAccess`` holder (even unlinked) to the
  portal branch — posted ``supplier=`` pks can never impersonate another invitee;
* the bid rule engine runs under a row lock: equal-amount ties are refused (strict
  improvement), foreign suppliers are never admissible choices;
* state-changing verbs are ``@require_POST`` — a GET mutates nothing;
* ``Eauction.award()`` is once-only and each success leaves exactly ONE audit effect.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, Party, PartyRole
from apps.procurement.models import EaucBid, EaucInvite, Eauction, VendorPortalAccess

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ local data builders

def _party(tenant, name):
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _supplier_role(tenant, party):
    return PartyRole.objects.create(tenant=tenant, party=party, role="supplier")


def _auction(tenant, creator, status="scheduled", title="Security suite auction", **over):
    now = timezone.now()
    fields = dict(
        tenant=tenant, title=title, status=status,
        start_price=Decimal("5000.00"), min_decrement=Decimal("100.00"),
        opens_at=now - timedelta(hours=1), closes_at=now + timedelta(hours=2),
        created_by=creator,
    )
    fields.update(over)
    return Eauction.objects.create(**fields)


def _invite(auction, party):
    return EaucInvite.objects.create(tenant=auction.tenant, auction=auction, supplier=party)


def _bid(auction, party, amount, placer):
    return EaucBid.objects.create(
        tenant=auction.tenant, auction=auction, supplier=party,
        amount=Decimal(amount), placed_by=placer)


# ------------------------------------------------------------------ fixtures

@pytest.fixture
def sup_x_a(db, tenant_a):
    """Invited supplier X of tenant A (carries the supplier role for the invite form)."""
    p = _party(tenant_a, "Xtel Components")
    _supplier_role(tenant_a, p)
    return p


@pytest.fixture
def sup_y_a(db, tenant_a):
    """Invited supplier Y of tenant A — the rival bidder."""
    p = _party(tenant_a, "Yankee Fasteners")
    _supplier_role(tenant_a, p)
    return p


@pytest.fixture
def foreign_sup_b(db, tenant_b):
    """A fully valid supplier of tenant B — must be poison in every tenant-A form."""
    p = _party(tenant_b, "Borderline Ltd")
    _supplier_role(tenant_b, p)
    return p


@pytest.fixture
def live_auction_a(db, tenant_a, admin_user, sup_x_a, sup_y_a):
    """LIVE auction of tenant A with both rivals invited."""
    a = _auction(tenant_a, admin_user)
    _invite(a, sup_x_a)
    _invite(a, sup_y_a)
    return a


@pytest.fixture
def closed_auction_a(db, tenant_a, admin_user, sup_x_a, sup_y_a):
    a = _auction(tenant_a, admin_user, status="closed")
    _invite(a, sup_x_a)
    _invite(a, sup_y_a)
    return a


@pytest.fixture
def portal_user_a(db, tenant_a):
    """A vendor-portal login that IS a tenant-A member (User.tenant set)."""
    return User.objects.create_user(
        email="portal@xtel.com", username="portal_xtel",
        password="PortalPass123!", tenant=tenant_a, is_tenant_admin=False)


@pytest.fixture
def vpa_bound_a(db, tenant_a, admin_user, portal_user_a, sup_x_a):
    return VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=sup_x_a, portal_user=portal_user_a,
        invited_by=admin_user)


@pytest.fixture
def portal_client_a(db, portal_user_a):
    c = Client()
    c.force_login(portal_user_a)
    return c


@pytest.fixture
def portal_user_b(db, tenant_b, foreign_sup_b, admin_b):
    u = User.objects.create_user(
        email="portal@border.com", username="portal_border",
        password="PortalPass123!", tenant=tenant_b, is_tenant_admin=False)
    VendorPortalAccess.objects.create(
        tenant=tenant_b, supplier=foreign_sup_b, portal_user=u, invited_by=admin_b)
    return u


@pytest.fixture
def portal_client_b(db, portal_user_b):
    c = Client()
    c.force_login(portal_user_b)
    return c


@pytest.fixture
def super_root(db):
    """The platform superuser — tenant=None BY DESIGN."""
    return User.objects.create_superuser(
        email="root@naverp.io", username="root", password="RootPass123!")


@pytest.fixture
def root_client(db, super_root):
    c = Client()
    c.force_login(super_root)
    return c


@pytest.fixture
def foreign_auction_b(db, tenant_b, admin_b, foreign_sup_b):
    a = _auction(tenant_b, admin_b, title="Globex internal auction")
    _invite(a, foreign_sup_b)
    return a


# ------------------------------------------------------------------ 1. IDOR

def test_eauction_sec_idor_all_pk_routes_404(client_a, foreign_auction_b):
    """Every pk route against a foreign-tenant auction is a bare 404 from
    get_object_or_404 — BEFORE any verb logic could touch the row."""
    fb = foreign_auction_b
    reads = ["eauc_detail", "eauc_edit", "eauc_console", "eauc_board",
             "eauc_results", "eauc_bid"]
    for name in reads:
        assert client_a.get(reverse(f"procurement:{name}", args=[fb.pk])).status_code == 404
    # Verbs must be POSTed (require_POST would 405 a GET before the 404 gate).
    posts = ["eauc_edit", "eauc_publish", "eauc_close", "eauc_cancel",
             "eauc_delete", "eauc_invite_add", "eauc_award", "eauc_bid"]
    for name in posts:
        assert client_a.post(reverse(f"procurement:{name}", args=[fb.pk]),
                             {"title": "x", "amount": "1"}).status_code == 404
    # Nested invite route dies on the AUCTION lookup first, not the invite lookup.
    inv = fb.invites.first()
    url = reverse("procurement:eauc_invite_remove", args=[fb.pk, inv.pk])
    assert client_a.post(url).status_code == 404
    fb.refresh_from_db()
    assert fb.status == "scheduled" and fb.invites.count() == 1


# ------------------------------------------------------------------ 2. anonymous

def test_eauction_sec_anonymous_redirects_to_login(client, live_auction_a):
    """login_required fronts every surface — including the deliberately unstacked
    eauc_bid — and an anonymous POST can never land a bid."""
    routes = [("eauc_list", []), ("eauc_floor", []), ("eauc_rules", []),
              ("eauc_detail", [live_auction_a.pk]), ("eauc_console", [live_auction_a.pk]),
              ("eauc_board", [live_auction_a.pk]), ("eauc_results", [live_auction_a.pk]),
              ("eauc_bid", [live_auction_a.pk])]
    for name, args in routes:
        resp = client.get(reverse(f"procurement:{name}", args=args))
        assert resp.status_code == 302
        assert resp.url.startswith("/login")
    assert client.post(reverse("procurement:eauc_bid", args=[live_auction_a.pk]),
                       {"amount": "100"}).status_code == 302
    assert live_auction_a.bids.count() == 0


# ------------------------------------------------------------------ 3. staff gate

def test_eauction_sec_staff_gate_blocks_tenantless_superuser(root_client):
    """/eauc_list under a tenant=None superuser: request.tenant is None → NOT a member
    of anything → staff_required bounces to the dashboard instead of rendering."""
    resp = root_client.get(reverse("procurement:eauc_list"))
    assert resp.status_code == 302
    assert resp.url == reverse("dashboard:home")
    assert root_client.get(reverse("procurement:eauc_rules")).status_code == 302


def test_eauction_sec_portal_same_tenant_passes_staff_gate_limitation(
        portal_client_a, vpa_bound_a, live_auction_a):
    """PINNED REALITY (known accepted limitation): staff_required admits ANY tenant
    member — ``user.tenant_id == request.tenant.pk`` — and a vendor-portal login whose
    User row carries tenant A satisfies exactly that. The decorator was written to close
    the ANONYMOUS-adjacent hole (logins with no tenant), not to distinguish portal
    bindings, so a bound portal user reaches buyer READ surfaces. Bidding stays their
    real surface (pinned supplier), and cross-tenant rows stay 404 — see the IDOR test."""
    assert portal_client_a.get(reverse("procurement:eauc_list")).status_code == 200
    assert portal_client_a.get(reverse("procurement:eauc_console",
                                       args=[live_auction_a.pk])).status_code == 200
    assert portal_client_a.get(reverse("procurement:eauc_results",
                                       args=[live_auction_a.pk])).status_code == 200


def test_eauction_sec_portal_cross_tenant_404_on_foreign_auctions(
        portal_client_b, live_auction_a):
    """A tenant-B portal login's request.tenant IS tenant B (TenantMiddleware takes it off
    the user), so acme auction ids miss get_object_or_404's tenant filter → 404 — even
    though eauc_bid has no staff_required stack."""
    for name in ("eauc_detail", "eauc_console", "eauc_board", "eauc_results", "eauc_bid"):
        assert portal_client_b.get(reverse(f"procurement:{name}",
                                           args=[live_auction_a.pk])).status_code == 404


# ------------------------------------------------------------------ 4. supplier pinning

def test_eauction_sec_bid_pinned_to_bound_supplier(
        portal_client_a, vpa_bound_a, portal_user_a, live_auction_a, sup_x_a, sup_y_a):
    """A VPA-bound user posting supplier=<other invited pk> gets recorded under the
    BOUND supplier — the posted pk never reaches the write."""
    resp = portal_client_a.post(reverse("procurement:eauc_bid", args=[live_auction_a.pk]),
                                {"supplier": str(sup_y_a.pk), "amount": "4500.00",
                                 "note": "impersonation attempt"})
    assert resp.status_code == 302
    assert live_auction_a.bids.count() == 1
    row = live_auction_a.bids.get()
    assert row.supplier_id == sup_x_a.pk
    assert row.placed_by_id == portal_user_a.pk
    assert row.amount == Decimal("4500.00")
    assert not live_auction_a.bids.filter(supplier_id=sup_y_a.pk).exists()


def test_eauction_sec_active_unlinked_vpa_pins_user_off_staff_branch(
        db, tenant_a, admin_user, live_auction_a, sup_x_a):
    """ANY binding row pins the login to the portal side — an ACTIVE but UNLINKED VPA
    (supplier=NULL) must NOT fall through to the staff branch where the posted supplier
    pk would be honoured."""
    ghost = User.objects.create_user(
        email="ghost@acme.com", username="ghost_acme",
        password="PortalPass123!", tenant=tenant_a, is_tenant_admin=False)
    VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=None, portal_user=ghost, invited_by=admin_user)
    c = Client()
    c.force_login(ghost)
    resp = c.post(reverse("procurement:eauc_bid", args=[live_auction_a.pk]),
                  {"supplier": str(sup_x_a.pk), "amount": "4500.00"})
    assert resp.status_code == 302
    assert live_auction_a.bids.count() == 0


# ------------------------------------------------------------------ 5. GET never mutates

def test_eauction_sec_get_never_mutates_state_routes(client_a, live_auction_a, tenant_a,
                                                     admin_user):
    """publish/close/cancel/invite_remove/award (+ delete on a draft) are @require_POST:
    a GET answers 405 from the decorator BEFORE the view body — the DB is untouched."""

    def snap(a):
        a.refresh_from_db()
        return (a.status, a.closes_at, a.extensions_used, a.awarded_supplier_id,
                a.invites.count(), a.bids.count())

    before = snap(live_auction_a)
    i_pk = live_auction_a.invites.first().pk
    for name, args in (("eauc_publish", [live_auction_a.pk]),
                       ("eauc_close", [live_auction_a.pk]),
                       ("eauc_cancel", [live_auction_a.pk]),
                       ("eauc_invite_remove", [live_auction_a.pk, i_pk]),
                       ("eauc_award", [live_auction_a.pk])):
        resp = client_a.get(reverse(f"procurement:{name}", args=args))
        assert resp.status_code == 405, name
    assert snap(live_auction_a) == before

    draft = _auction(tenant_a, admin_user, status="draft")
    assert client_a.get(reverse("procurement:eauc_delete",
                                args=[draft.pk])).status_code == 405
    assert Eauction.objects.filter(pk=draft.pk).exists()


# ------------------------------------------------------------------ 6. cross-tenant FK poisoning

def test_eauction_sec_invite_rejects_foreign_supplier_pk(client_a, live_auction_a,
                                                         foreign_sup_b):
    """invite_add with a VALID tenant-B supplier pk: EaucInviteForm narrows its queryset
    to request.tenant parties, so the choice is invalid → no EaucInvite row."""
    resp = client_a.post(reverse("procurement:eauc_invite_add", args=[live_auction_a.pk]),
                         {"supplier": str(foreign_sup_b.pk),
                          "contact_note": "poisoned"})
    assert resp.status_code == 302
    assert live_auction_a.invites.filter(supplier_id=foreign_sup_b.pk).exists() is False
    assert live_auction_a.invites.count() == 2


def test_eauction_sec_bid_refuses_foreign_supplier_choice(
        member_client, live_auction_a, foreign_sup_b):
    """Staff-recorded bid naming a tenant-B supplier pk: the choice only ever resolves
    from the INVITE list, so chosen stays None → error redirect, no bid row."""
    resp = member_client.post(reverse("procurement:eauc_bid", args=[live_auction_a.pk]),
                              {"supplier": str(foreign_sup_b.pk), "amount": "4500.00"})
    assert resp.status_code == 302
    assert EaucBid.objects.count() == 0


# ------------------------------------------------------------------ 7. filter isolation

@pytest.fixture
def closed_own_a(db, tenant_a, admin_user):
    return _auction(tenant_a, admin_user, status="closed", title="Own closed")


def test_eauction_sec_list_live_filter_leaks_no_foreign_links(
        client_a, live_auction_a, foreign_auction_b):
    """/eauc/?state=live is a tenant-scoped queryset: no href pointing at the foreign
    auction id may appear on the page."""
    html = client_a.get(
        f"{reverse('procurement:eauc_list')}?state=live").content.decode()
    assert f"/eauc/{foreign_auction_b.pk}/" not in html
    assert f"/eauc/{live_auction_a.pk}/" in html


def test_eauction_sec_list_closed_filter_leaks_no_foreign_links(
        client_a, closed_own_a, foreign_auction_b):
    """Same isolation for the ?state=closed deep-link the sidebar uses."""
    html = client_a.get(
        f"{reverse('procurement:eauc_list')}?state=closed").content.decode()
    assert f"/eauc/{foreign_auction_b.pk}/" not in html
    assert f"/eauc/{closed_own_a.pk}/" in html


# ------------------------------------------------------------------ 8. tie impossible

def test_eauction_sec_equal_amount_tie_refused(member_client, live_auction_a,
                                               admin_user, sup_x_a, sup_y_a):
    """Rival opener EQUAL to the standing best moves nothing: next_floor caps a first
    bid strictly below the global best (post F-CR-02 strict improvement)."""
    _bid(live_auction_a, sup_x_a, "4800.00", admin_user)
    resp = member_client.post(reverse("procurement:eauc_bid", args=[live_auction_a.pk]),
                              {"supplier": str(sup_y_a.pk), "amount": "4800.00"})
    assert resp.status_code == 302
    assert live_auction_a.bids.count() == 1
    assert live_auction_a.best_bid().supplier_id == sup_x_a.pk


# ------------------------------------------------------------------ 9. award race guard

def test_eauction_sec_award_twice_second_false_single_audit(
        client_a, admin_user, closed_auction_a, sup_x_a):
    """award() is once-only behind the view's row lock: the second sequential POST loses
    the guard, changes nothing, and the auction carries exactly ONE award audit effect."""
    leader = _bid(closed_auction_a, sup_x_a, "4800.00", admin_user)
    payload = {"supplier": str(sup_x_a.pk), "award_note": "winner"}
    first = client_a.post(reverse("procurement:eauc_award",
                                  args=[closed_auction_a.pk]), payload)
    second = client_a.post(reverse("procurement:eauc_award",
                                   args=[closed_auction_a.pk]), payload)
    assert first.status_code == 302 and second.status_code == 302
    closed_auction_a.refresh_from_db()
    assert closed_auction_a.status == "awarded"
    assert closed_auction_a.awarded_supplier_id == sup_x_a.pk
    assert closed_auction_a.awarded_amount == Decimal("4800.00")
    assert (AuditLog.objects.filter(action="award", object_id=closed_auction_a.pk)
            .count() == 1)
    assert closed_auction_a.bids.count() == 1 and leader.number.startswith("EBID")


# ------------------------------------------------------------------ positive controls

def test_eauction_sec_legal_staff_bid_positive_control(
        member_client, live_auction_a, sup_x_a):
    """The refusals above are rule-driven, not broken plumbing: an invited supplier's
    legal lowering bid records fine when recorded by staff."""
    resp = member_client.post(reverse("procurement:eauc_bid", args=[live_auction_a.pk]),
                              {"supplier": str(sup_x_a.pk), "amount": "4500.00"})
    assert resp.status_code == 302
    row = live_auction_a.bids.get()
    assert row.supplier_id == sup_x_a.pk
    assert row.amount == Decimal("4500.00")
    assert row.number.startswith("EBID")


def test_eauction_sec_award_refuses_non_leader_supplier(
        client_a, closed_auction_a, admin_user, sup_x_a, sup_y_a):
    """Only the current LEADING supplier can win: inviting sup_y doesn't let the buyer
    hand them the award — refused, status stays closed, zero award audits."""
    _bid(closed_auction_a, sup_x_a, "4800.00", admin_user)
    resp = client_a.post(reverse("procurement:eauc_award", args=[closed_auction_a.pk]),
                         {"supplier": str(sup_y_a.pk), "award_note": "backdoor"})
    assert resp.status_code == 302
    closed_auction_a.refresh_from_db()
    assert closed_auction_a.status == "closed"
    assert closed_auction_a.awarded_supplier_id is None
    assert AuditLog.objects.filter(action="award",
                                   object_id=closed_auction_a.pk).count() == 0
