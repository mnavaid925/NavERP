"""Inventory 5.9 Order Management & Fulfillment — security.

Adversarial multi-tenancy around the wave CRUD, the three lifecycle verbs and the two
membership verbs: cross-tenant IDOR on every route shape (GET pages, edit/delete POSTs,
lifecycle verb POSTs), the privilege-escalation regression (a plain member must never
reach the planner-only writes — role is checked BEFORE require_POST so the answer is a
403, never a misleading 405), duplicate-membership abuse degrading to a readable form
error instead of a 500, cross-tenant membership injection refused on BOTH verbs, the
anonymous wall over all ELEVEN routes, tenant-less superuser isolation (no 500, no
orphan rows), escaping of attacker-controlled wave text, method discipline, and the
mass-assignment contract: status/released_at/closed_at are system-set by the verbs and
stay off the form entirely, so a crafted POST cannot forge them.

House note: ``base.html`` ships legit ``<script>`` tags, so escape probes assert the FULL
payload (``<script>alert(1)</script>``) is absent — never the bare ``<script>`` prefix
(same idiom as 5.2/5.4).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory.forms.FulfillmentOrchestration.FulfillmentWaves import (
    FulfillmentWaveForm,
)
from apps.inventory.models import FulfillmentWave, FulfillmentWaveOrder

pytestmark = pytest.mark.django_db

_XSS_SCRIPT = "<script>alert(1)</script>"

#: Strings minted exclusively for Globex's workspace. Both tenants' first waves read
#: WAV-00001 (per-tenant numbering), so isolation is asserted ONLY on markers these
#: fixtures create for tenant_b — never on numbers.
_FOREIGN_MARKERS = ["Globex outbound batch", "Globex Wave Freight"]


# ---- module-level helpers ----------------------------------------------------------------------

def _fulfillment_assert_login_redirect(response):
    assert response.status_code == 302
    assert "/login" in response.url or response.url.endswith("login")


def _fulfillment_assert_no_foreign_marker(content):
    html = content.decode() if isinstance(content, bytes) else content
    for marker in _FOREIGN_MARKERS:
        assert marker not in html


def _fulfillment_wave_payload(location, carrier, **overrides):
    """A minimal VALID wave POST body — every field but description is optional; the
    overrides carry the adversarial bits."""
    data = {
        "description": "Security probe wave",
        "location": location.pk if location else "",
        "carrier": carrier.pk if carrier else "",
        "ship_method": "standard",
        "planned_ship_date": "",
        "cutoff_at": "",
        "priority": "50",
        "criteria_text": "",
        "notes": "",
    }
    data.update(overrides)
    return data


def _fulfillment_open_sales_order(customer, item):
    """An OPEN (submitted) scm.SalesOrder with one line — tenant-agnostic, so this file
    can mint both an owned spare and a FOREIGN injection target."""
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(
        tenant=customer.tenant, customer=customer, status="submitted",
        source_channel="manual", order_date=datetime.date(2026, 8, 21))
    SalesOrderLine.objects.create(
        sales_order=order, item=item, quantity_ordered=Decimal("2"),
        unit_price=Decimal("7.00"))
    order.recalc_totals()
    return order


def _fulfillment_extra_planned_wave(tenant, location, carrier):
    """A SECOND still-planned wave for the SAME tenant — lets the membership tests aim a
    real (own-tenant!) member row at the wrong wave without touching any foreign row."""
    return FulfillmentWave.objects.create(
        tenant=tenant, description="Second planned batch",
        location=location, carrier=carrier, ship_method="standard")


# ---- local fixtures ------------------------------------------------------------------------------

@pytest.fixture
def _fulfillment_tenantless_superuser(db):
    """The platform superuser: tenant=None BY DESIGN — it owns no workspace at all."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="sec-super@naverp.test", username="sec_superuser_fulfillment",
        password="TestPass123!", tenant=None, is_superuser=True, is_staff=True)


@pytest.fixture
def _fulfillment_super_client(_fulfillment_tenantless_superuser):
    c = Client()
    c.force_login(_fulfillment_tenantless_superuser)
    return c


# ---- IDOR ----------------------------------------------------------------------------------------

def test_fulfillment_idor_get_detail_and_edit_404(client_a, fulfillment_foreign_wave_b):
    """A foreign wave pk must read as nonexistent to another workspace's admin."""
    for name in ["wave_detail", "wave_edit"]:
        url = reverse(f"inventory:{name}", args=[fulfillment_foreign_wave_b.pk])
        assert client_a.get(url).status_code == 404


def test_fulfillment_idor_writes_404_and_foreign_row_intact(
        client_a, fulfillment_foreign_wave_b, fulfillment_loc_wave_b,
        fulfillment_carrier_b):
    """The write shapes are where an IDOR would do damage: edit, ALL THREE lifecycle
    verbs and delete must 404 on a foreign pk and leave Globex's wave exactly where it
    was — same status, same description, same table size."""
    # Edit POST carrying a hijacking body.
    response = client_a.post(
        reverse("inventory:wave_edit", args=[fulfillment_foreign_wave_b.pk]),
        data=_fulfillment_wave_payload(fulfillment_loc_wave_b, fulfillment_carrier_b,
                                       description="hijacked"))
    assert response.status_code == 404

    # Lifecycle verb POSTs.
    for verb in ["wave_release", "wave_close", "wave_cancel"]:
        url = reverse(f"inventory:{verb}", args=[fulfillment_foreign_wave_b.pk])
        assert client_a.post(url).status_code == 404

    # Delete POST — the count assertion is the real proof nothing left the table.
    total_before = FulfillmentWave.objects.count()
    assert client_a.post(
        reverse("inventory:wave_delete", args=[fulfillment_foreign_wave_b.pk])
    ).status_code == 404
    assert FulfillmentWave.objects.count() == total_before

    fulfillment_foreign_wave_b.refresh_from_db()  # raises if deleted
    assert fulfillment_foreign_wave_b.status == "planned"
    assert fulfillment_foreign_wave_b.description == "Globex outbound batch"


def test_fulfillment_foreign_wave_never_leaks_into_list_or_board(
        client_a, fulfillment_foreign_wave_b):
    """List isolation on both read pages: Globex's unique markers must not surface
    anywhere in Acme's wave listing or planning board."""
    for name in ["wave_list", "wave_board"]:
        response = client_a.get(reverse(f"inventory:{name}"))
        assert response.status_code == 200
        _fulfillment_assert_no_foreign_marker(response.content)


# ---- privilege escalation (C2): member vs the planner-only writes -----------------------------------

def test_fulfillment_member_cannot_run_lifecycle_verbs(member_client,
                                                       fulfillment_wave_planned_a):
    """Releasing/closing/cancelling a batch is a planner decision: the decorator chain
    checks the ROLE before require_POST, so a member's POST gets a 403 (never a
    misleading 405) and the wave's system-set lifecycle state does not move."""
    for verb in ["wave_release", "wave_close", "wave_cancel"]:
        url = reverse(f"inventory:{verb}", args=[fulfillment_wave_planned_a.pk])
        assert member_client.post(url).status_code == 403
    fulfillment_wave_planned_a.refresh_from_db()
    assert fulfillment_wave_planned_a.status == "planned"
    assert fulfillment_wave_planned_a.released_at is None
    assert fulfillment_wave_planned_a.closed_at is None


def test_fulfillment_member_cannot_change_membership(member_client,
                                                     fulfillment_wave_planned_a,
                                                     fulfillment_so_second_a,
                                                     fulfillment_member_a):
    """Membership edits are gated exactly like the verbs: a member's add AND remove
    POSTs get 403 and the wave's roster stays untouched."""
    add_url = reverse("inventory:waveorder_add", args=[fulfillment_wave_planned_a.pk])
    remove_url = reverse("inventory:waveorder_remove",
                         args=[fulfillment_wave_planned_a.pk, fulfillment_member_a.pk])
    assert member_client.post(add_url, data={"sales_order": fulfillment_so_second_a.pk}
                              ).status_code == 403
    assert member_client.post(remove_url).status_code == 403
    assert fulfillment_wave_planned_a.orders.count() == 1


# ---- duplicate membership abuse (C1) -----------------------------------------------------------------

def test_fulfillment_duplicate_membership_never_500s(client_a, fulfillment_wave_planned_a,
                                                     fulfillment_so_second_a):
    """[C1] The same sales order POSTed twice must degrade to a readable refusal — the
    unique_together is checked where it can render ("wave" is not a form field, so
    validate_unique would silently skip it), never as an uncaught IntegrityError on
    save(). One roster row per SO and the second response surfaces the error."""
    url = reverse("inventory:waveorder_add", args=[fulfillment_wave_planned_a.pk])
    first = client_a.post(url, data={"sales_order": fulfillment_so_second_a.pk})
    assert first.status_code == 302   # the legitimate add succeeded

    second = client_a.post(url, data={"sales_order": fulfillment_so_second_a.pk},
                           follow=True)
    assert second.status_code == 200  # never a 500
    assert "already in this wave" in second.content.decode()
    assert (FulfillmentWaveOrder.objects
            .filter(wave=fulfillment_wave_planned_a,
                    sales_order=fulfillment_so_second_a).count() == 1)


# ---- cross-tenant membership --------------------------------------------------------------------------

def test_fulfillment_add_rejects_foreign_sales_order(client_a, fulfillment_wave_planned_a,
                                                     customer_party_b, item_b):
    """Crafted-POST FK injection on the add form: a Globex sales order aimed at an Acme
    wave dies as a field error, leaves NO new row anywhere and surfaces the refusal."""
    foreign_so = _fulfillment_open_sales_order(customer_party_b, item_b)

    total_before = FulfillmentWaveOrder.objects.count()
    response = client_a.post(
        reverse("inventory:waveorder_add", args=[fulfillment_wave_planned_a.pk]),
        data={"sales_order": foreign_so.pk}, follow=True)
    assert response.status_code == 200
    # The scoped <select> usually refuses first ("valid choice"); _reject_foreign's
    # field-error wording is the fallback when a stale pk still parses. Either way:
    html = response.content.decode()
    assert ("valid choice" in html
            or "That record belongs to another workspace." in html)

    assert FulfillmentWaveOrder.objects.count() == total_before
    assert not FulfillmentWaveOrder.objects.filter(sales_order=foreign_so).exists()


def test_fulfillment_remove_mismatched_pair_is_inert(client_a, tenant_a, admin_user,
                                                     fulfillment_wave_planned_a,
                                                     fulfillment_member_a,
                                                     fulfillment_loc_wave_a,
                                                     fulfillment_carrier_a,
                                                     customer_party_a, item_a):
    """remove(wave=<planned_a>, member=<ANOTHER wave's row>) matches nothing under the
    view's (wave=obj, pk=order_pk) filter — the mismatched pair is refused with a flash
    and both membership rows survive untouched."""
    extra_wave = _fulfillment_extra_planned_wave(tenant_a, fulfillment_loc_wave_a,
                                                 fulfillment_carrier_a)
    stray_member = FulfillmentWaveOrder.objects.create(
        tenant=tenant_a, wave=extra_wave,
        sales_order=_fulfillment_open_sales_order(customer_party_a, item_a),
        added_by=admin_user)

    total_before = FulfillmentWaveOrder.objects.count()
    response = client_a.post(
        reverse("inventory:waveorder_remove",
                args=[fulfillment_wave_planned_a.pk, stray_member.pk]),
        follow=True)
    assert response.status_code == 200
    assert "not part of this wave" in response.content.decode()

    assert FulfillmentWaveOrder.objects.count() == total_before
    stray_member.refresh_from_db()   # raises if deleted — the real assertions
    fulfillment_member_a.refresh_from_db()
    assert extra_wave.orders.count() == 1
    assert fulfillment_wave_planned_a.orders.count() == 1


# ---- auth walls -----------------------------------------------------------------------------------------

def test_fulfillment_anonymous_redirected_on_all_eleven_routes(
        client, fulfillment_wave_planned_a, fulfillment_member_a):
    """Every 5.9 route sits behind @login_required — the three plain pages, the seven
    detail-shaped routes and the two-key membership remove. No exception."""
    plain_routes = ["wave_list", "wave_board", "wave_create"]
    detail_routes = ["wave_detail", "wave_edit", "wave_delete", "wave_release",
                     "wave_close", "wave_cancel", "waveorder_add"]
    for name in plain_routes:
        _fulfillment_assert_login_redirect(client.get(reverse(f"inventory:{name}")))
    for name in detail_routes:
        url = reverse(f"inventory:{name}", args=[fulfillment_wave_planned_a.pk])
        _fulfillment_assert_login_redirect(client.get(url))
    remove_url = reverse("inventory:waveorder_remove",
                         args=[fulfillment_wave_planned_a.pk, fulfillment_member_a.pk])
    _fulfillment_assert_login_redirect(client.get(remove_url))


# ---- tenant-less superuser isolation ---------------------------------------------------------------------

def test_fulfillment_tenantless_superuser_no_500_no_orphan_rows(
        _fulfillment_super_client, fulfillment_foreign_wave_b, fulfillment_loc_wave_a,
        fulfillment_carrier_a):
    """tenant=None means NO workspace: list and board render their empty states, create
    is bounced to the dashboard BEFORE the form runs (GET and POST alike), and no wave —
    or membership row — may ever exist with a NULL tenant afterwards."""
    listing = _fulfillment_super_client.get(reverse("inventory:wave_list"))
    assert listing.status_code == 200
    assert "No waves yet" in listing.content.decode()
    _fulfillment_assert_no_foreign_marker(listing.content)

    board = _fulfillment_super_client.get(reverse("inventory:wave_board"))
    assert board.status_code == 200
    assert board.context["stats"]["open_waves"] == 0
    _fulfillment_assert_no_foreign_marker(board.content)

    total_before = FulfillmentWave.objects.count()
    create_url = reverse("inventory:wave_create")
    assert _fulfillment_super_client.get(create_url).status_code == 302
    assert _fulfillment_super_client.post(
        create_url,
        data=_fulfillment_wave_payload(fulfillment_loc_wave_a, fulfillment_carrier_a)
    ).status_code == 302

    assert FulfillmentWave.objects.filter(tenant__isnull=True).count() == 0
    assert FulfillmentWaveOrder.objects.filter(tenant__isnull=True).count() == 0
    assert FulfillmentWave.objects.count() == total_before


# ---- XSS -------------------------------------------------------------------------------------------------

def test_fulfillment_notes_render_escaped_on_list_board_and_detail(
        client_a, tenant_a, fulfillment_loc_wave_a, fulfillment_carrier_a):
    """Wave text is attacker-controlled free text rendered on all three pages —
    autoescape is the only sanitizer any of them may rely on."""
    wave = FulfillmentWave.objects.create(
        tenant=tenant_a, description=_XSS_SCRIPT, notes=_XSS_SCRIPT,
        location=fulfillment_loc_wave_a, carrier=fulfillment_carrier_a)

    listing = client_a.get(reverse("inventory:wave_list")).content.decode()
    assert _XSS_SCRIPT not in listing
    assert "&lt;script&gt;" in listing

    board = client_a.get(reverse("inventory:wave_board")).content.decode()
    assert _XSS_SCRIPT not in board
    assert "&lt;script&gt;" in board

    detail = client_a.get(reverse("inventory:wave_detail",
                                  args=[wave.pk])).content.decode()
    assert _XSS_SCRIPT not in detail
    assert "&lt;script&gt;" in detail  # notes render escaped on the detail page


# ---- method discipline ------------------------------------------------------------------------------------

def test_fulfillment_verbs_membership_and_delete_are_post_only(client_a,
                                                               fulfillment_wave_planned_a,
                                                               fulfillment_member_a):
    """GET on every mutating route is a 405 — release/close/cancel/delete carry
    require_POST explicitly and crud_delete re-checks POST itself."""
    argged = ["wave_delete", "wave_release", "wave_close", "wave_cancel",
              "waveorder_add"]
    for name in argged:
        url = reverse(f"inventory:{name}", args=[fulfillment_wave_planned_a.pk])
        assert client_a.get(url).status_code == 405
    remove_url = reverse("inventory:waveorder_remove",
                         args=[fulfillment_wave_planned_a.pk, fulfillment_member_a.pk])
    assert client_a.get(remove_url).status_code == 405
    fulfillment_member_a.refresh_from_db()  # nothing was removed by the GET probes


def test_fulfillment_board_post_is_read_only_consistent(client_a,
                                                        fulfillment_wave_planned_a,
                                                        fulfillment_member_a):
    """As-built the board is read-only BY CONSTRUCTION rather than require_POST-wrapped,
    so a mutation attempt answers the ordinary 200 page — the property locked here is
    harmlessness: identical stats, same rows, zero state movement behind it."""
    get_response = client_a.get(reverse("inventory:wave_board"))
    assert get_response.status_code == 200

    total_before = FulfillmentWave.objects.count()
    members_before = fulfillment_wave_planned_a.orders.count()
    post_response = client_a.post(reverse("inventory:wave_board"), data={})
    assert post_response.status_code == 200  # actual behaviour: plain re-render
    assert post_response.context["stats"] == get_response.context["stats"]

    fulfillment_wave_planned_a.refresh_from_db()
    assert fulfillment_wave_planned_a.status == "planned"
    assert FulfillmentWave.objects.count() == total_before
    assert fulfillment_wave_planned_a.orders.count() == members_before


# ---- mass assignment ----------------------------------------------------------------------------------------

def test_fulfillment_form_drops_workflow_keys_from_cleaned_data(
        tenant_a, fulfillment_loc_wave_a, fulfillment_carrier_a):
    """Unit-level contract: status/released_at/closed_at are NOT form fields, so a bound
    payload carrying them loses them silently — they never reach cleaned_data and can
    never be written by a save() from this form."""
    data = _fulfillment_wave_payload(
        fulfillment_loc_wave_a, fulfillment_carrier_a,
        status="closed",
        released_at="2026-08-01T10:00",
        closed_at="2026-08-02T18:00")
    form = FulfillmentWaveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    for key in ["status", "released_at", "closed_at"]:
        assert key not in form.fields
        assert key not in form.cleaned_data


def test_fulfillment_crafted_edit_post_cannot_flip_status(
        client_a, fulfillment_wave_planned_a, fulfillment_loc_wave_a,
        fulfillment_carrier_a):
    """View-level regression: a crafted edit POST injecting status=closed plus both
    lifecycle timestamps saves its LEGITIMATE fields (302) but leaves the workflow
    columns strictly alone — only the verbs move them."""
    response = client_a.post(
        reverse("inventory:wave_edit", args=[fulfillment_wave_planned_a.pk]),
        data=_fulfillment_wave_payload(
            fulfillment_loc_wave_a, fulfillment_carrier_a,
            description="still planned",
            status="closed",
            released_at="2026-08-01T10:00",
            closed_at="2026-08-02T18:00"))
    assert response.status_code == 302  # the edit itself succeeded...

    fulfillment_wave_planned_a.refresh_from_db()
    assert fulfillment_wave_planned_a.description == "still planned"  # ...and really saved
    assert fulfillment_wave_planned_a.status == "planned"
    assert fulfillment_wave_planned_a.released_at is None
    assert fulfillment_wave_planned_a.closed_at is None
