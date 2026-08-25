"""Procurement 6.7 - E-Auction Management form tests.

The setup form IS the Auction Setup & Configuration boundary: required window/pricing
fields, a reverse-only choice set, crafted-POST foreign requisitions rejected as field
errors, and the anti-snipe trigger floored at 5 seconds. The invite form narrows its
dropdown to tenant parties carrying the supplier role (minus already-invited rows) and its
save() must swallow a double-submitted POST via get_or_create. The bid form is the Live
Bidding Interface input: amount parsing, note length, and the model's own positive-amount
validators reached through full_clean.
"""
import datetime
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.procurement.forms import EaucBidForm, EaucInviteForm, EauctionForm
from apps.procurement.models import EaucBid, EaucInvite, Eauction

pytestmark = pytest.mark.django_db


# -- local factories ---------------------------------------------------------------------------------

def _window():
    now = timezone.now()
    return now + datetime.timedelta(days=1), now + datetime.timedelta(days=2)


def _auction(tenant, **overrides):
    opens_at, closes_at = _window()
    fields = dict(
        tenant=tenant,
        title="Steel plate reverse auction",
        start_price=Decimal("10000.00"),
        min_decrement=Decimal("100.00"),
        opens_at=opens_at,
        closes_at=closes_at,
    )
    fields.update(overrides)
    return Eauction.objects.create(**fields)


def _party(tenant, name, roles=()):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    for role in roles:
        PartyRole.objects.get_or_create(party=party, tenant=tenant, defaults={"role": role})
    return party


def _requisition(tenant, requester=None):
    from apps.scm.models import PurchaseRequisition
    return PurchaseRequisition.objects.create(
        tenant=tenant, title="Spot buy request", requester=requester,
        required_by=datetime.date.today() + datetime.timedelta(days=10),
        justification="E-auction sourcing support.")


def _valid_data(**overrides):
    opens_at, closes_at = _window()
    data = {
        "title": "Copper cathode reverse auction",
        "description": "Monthly spot buy against the approved requisition.",
        "auction_type": "reverse",
        "start_price": "10000.00",
        "min_decrement": "100.00",
        "extension_trigger_seconds": "60",
        "extension_seconds": "120",
        "max_extensions": "3",
        "opens_at": opens_at.strftime("%Y-%m-%dT%H:%M"),
        "closes_at": closes_at.strftime("%Y-%m-%dT%H:%M"),
    }
    data.update(overrides)
    return data


# -- EauctionForm ------------------------------------------------------------------------------------

def test_eauction_form_valid_bind_with_tenant_kwarg(tenant_a):
    form = EauctionForm(_valid_data(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    # TenantUniqueMixin stamps instance.tenant BEFORE full_clean on CREATE.
    assert form.instance.tenant_id == tenant_a.pk
    auction = form.save()
    assert auction.number.startswith("EAUC-")
    assert auction.start_price == Decimal("10000.00")


def test_eauction_form_required_title_start_price_and_window(tenant_a):
    form = EauctionForm({"title": "", "start_price": "", "opens_at": "", "closes_at": ""},
                        tenant=tenant_a)
    assert not form.is_valid()
    for field in ("title", "start_price", "opens_at", "closes_at"):
        assert field in form.errors, f"{field} missing from errors: {form.errors}"


def test_eauction_form_reverse_only_choice_set(tenant_a):
    form = EauctionForm(tenant=tenant_a)
    values = [choice[0] for choice in form.fields["auction_type"].choices]
    assert values == ["reverse"]
    assert "forward" not in values


def test_eauction_form_rejects_foreign_requisition_pk(tenant_a, tenant_b, admin_user):
    foreign_pr = _requisition(tenant_b, requester=admin_user)
    form = EauctionForm(_valid_data(requisition=str(foreign_pr.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "requisition" in form.errors  # _reject_foreign renders it where the select is


def test_eauction_form_extension_trigger_below_five_seconds_rejected(tenant_a):
    form = EauctionForm(_valid_data(extension_trigger_seconds="3"), tenant=tenant_a)
    assert not form.is_valid()
    assert "extension_trigger_seconds" in form.errors
    assert any("5 seconds" in message
               for message in form.errors["extension_trigger_seconds"])


def test_eauction_form_close_after_open_surfaces_as_closes_at_field_error(tenant_a):
    now = timezone.now()
    data = _valid_data(
        opens_at=(now + datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        closes_at=(now + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"))
    form = EauctionForm(data, tenant=tenant_a)
    # The form's clean() only handles FKs + the trigger floor; this error can only come
    # from Eauction.clean() running through ModelForm._post_clean -> full_clean().
    assert not form.is_valid()
    assert "closes_at" in form.errors


# -- widgets (post F-FE-01) --------------------------------------------------------------------------

def test_eauction_forms_widgets_carry_framework_classes(tenant_a):
    auction = _auction(tenant_a)
    ea_form = EauctionForm(tenant=tenant_a)
    invite_form = EaucInviteForm(tenant=tenant_a, auction=auction)
    assert ea_form.fields["title"].widget.attrs["class"] == "form-input"
    assert ea_form.fields["auction_type"].widget.attrs["class"] == "form-select"
    # Django 5 Input.__init__ pops "type" out of attrs into widget.input_type.
    assert ea_form.fields["opens_at"].widget.input_type == "datetime-local"
    assert ea_form.fields["opens_at"].widget.attrs["class"] == "form-input"
    assert invite_form.fields["supplier"].widget.attrs["class"] == "form-select"
    assert invite_form.fields["contact_note"].widget.attrs["class"] == "form-input"


# -- EaucInviteForm ----------------------------------------------------------------------------------

def test_eauction_invite_queryset_lists_only_tenant_supplier_parties(tenant_a, tenant_b):
    auction = _auction(tenant_a)
    supplier = _party(tenant_a, "Northwind Industrial Supply", roles=("supplier",))
    _party(tenant_a, "No Role Co")
    _party(tenant_a, "Vendor Only Co", roles=("vendor",))
    _party(tenant_b, "Globex Foreign Supplier", roles=("supplier",))

    form = EaucInviteForm(tenant=tenant_a, auction=auction)
    listed = list(form.fields["supplier"].queryset.values_list("pk", flat=True))
    assert listed == [supplier.pk]


def test_eauction_invite_queryset_excludes_already_invited(tenant_a):
    auction = _auction(tenant_a)
    first = _party(tenant_a, "Alpha Supply Co", roles=("supplier",))
    second = _party(tenant_a, "Beta Supply Co", roles=("supplier",))
    EaucInvite.objects.create(tenant=tenant_a, auction=auction, supplier=first)

    form = EaucInviteForm(tenant=tenant_a, auction=auction)
    listed = list(form.fields["supplier"].queryset.values_list("pk", flat=True))
    assert listed == [second.pk]


def test_eauction_invite_save_creates_row_with_tenant_auction_note(tenant_a):
    auction = _auction(tenant_a)
    supplier = _party(tenant_a, "Gamma Supply Co", roles=("supplier",))
    form = EaucInviteForm({"supplier": str(supplier.pk), "contact_note": "RFQ pack emailed"},
                          tenant=tenant_a, auction=auction)
    assert form.is_valid(), form.errors
    invite = form.save()
    assert invite.tenant_id == tenant_a.pk
    assert invite.auction_id == auction.pk
    assert invite.supplier_id == supplier.pk
    assert invite.contact_note == "RFQ pack emailed"


def test_eauction_invite_save_double_submit_is_noop_not_integrityerror(tenant_a):
    auction = _auction(tenant_a)
    supplier = _party(tenant_a, "Delta Supply Co", roles=("supplier",))
    data = {"supplier": str(supplier.pk), "contact_note": "Call before close"}
    form = EaucInviteForm(data, tenant=tenant_a, auction=auction)
    assert form.is_valid(), form.errors
    first = form.save()
    second = form.save()  # double-submitted POST — get_or_create semantics (post F-CR-08)
    assert first.pk == second.pk
    assert EaucInvite.objects.filter(auction=auction, supplier=supplier).count() == 1


# -- EaucBidForm -------------------------------------------------------------------------------------

def test_eauction_bid_form_amount_parses_decimal():
    form = EaucBidForm({"amount": "9250.75", "note": "sharpest price"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["amount"] == Decimal("9250.75")
    assert form.cleaned_data["note"] == "sharpest price"


def test_eauction_bid_form_overlong_note_rejected():
    ok = EaucBidForm({"amount": "9000.00", "note": "x" * 255})
    assert ok.is_valid(), ok.errors
    bad = EaucBidForm({"amount": "9000.00", "note": "x" * 256})
    assert not bad.is_valid()
    assert "note" in bad.errors


# -- model-level amount validators (through full_clean) ----------------------------------------------

@pytest.mark.parametrize("amount", [Decimal("-50.00"), Decimal("0.00")])
def test_eauction_bid_model_full_clean_rejects_non_positive_amount(tenant_a, amount):
    auction = _auction(tenant_a)
    supplier = _party(tenant_a, "Epsilon Supply Co", roles=("supplier",))
    bid = EaucBid(tenant=tenant_a, auction=auction, supplier=supplier, amount=amount)
    with pytest.raises(ValidationError) as excinfo:
        bid.full_clean(exclude={"number", "placed_by"})
    assert "amount" in excinfo.value.message_dict
