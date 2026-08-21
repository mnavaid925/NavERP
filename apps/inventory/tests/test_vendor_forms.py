"""Inventory 5.2 — form boundary.

The vendor log's security boundary is the same trio the catalog tests pin down: the scoped
vendor dropdown that refuses a foreign pk at choice-validation, ``_reject_foreign`` beneath
it, and the fact that ``tenant``/``number`` are never form fields — a crafted POST cannot
mass-assign a workspace or mint its own VC- number.
"""
import re

import pytest

from apps.inventory.forms import VendorCommunicationForm
from apps.inventory.models import VendorCommunication

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers

VALID_DATA = {
    "channel": "call",
    "direction": "outbound",
    "subject": "Quarterly capacity check",
    "body": "Asked for a revised lead-time commitment.",
    "occurred_at": "2026-08-20 10:00",
    "follow_up_on": "",
}


def form_data(**overrides):
    data = dict(VALID_DATA)
    data.update(overrides)
    return data


# ------------------------------------------------------------------ VendorCommunicationForm


class TestVendorCommunicationForm:
    def test_valid_create_stamps_tenant_and_mints_number(self, tenant_a, vendor_party_a):
        form = VendorCommunicationForm(
            data=form_data(party=vendor_party_a.pk), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("VC-")

    def test_missing_required_fields_are_field_errors(self, tenant_a, vendor_party_a):
        form = VendorCommunicationForm(data=form_data(party="", subject=""), tenant=tenant_a)
        assert not form.is_valid()
        assert "party" in form.errors
        assert "subject" in form.errors

    def test_rejects_foreign_party(self, tenant_a, communication_a, vendor_party_b):
        """The scoped dropdown refuses a foreign pk at choice-validation ("Select a valid
        choice"); _reject_foreign is the belt-and-braces layer beneath it. Either message is a
        rejection — assert invalid + nothing saved, not one exact wording."""
        before = VendorCommunication.objects.count()
        form = VendorCommunicationForm(
            data=form_data(party=vendor_party_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["party"]
        assert form.instance.pk is None  # save() would raise on an invalid form anyway
        assert VendorCommunication.objects.count() == before

    def test_crafted_post_cannot_set_tenant_or_number(self, tenant_a, tenant_b, vendor_party_a):
        """Neither ``tenant`` nor ``number`` is a form field, so mass-assigning them in POST
        data changes nothing — the mixin stamps the real workspace and ``save()`` mints the
        next sequence value, never the smuggled literal."""
        form = VendorCommunicationForm(
            data=form_data(party=vendor_party_a.pk, tenant=tenant_b.pk,
                           number="VC-99999"),
            tenant=tenant_a)
        assert "tenant" not in form.fields
        assert "number" not in form.fields
        assert form.is_valid(), form.errors
        obj = form.save()  # the mixin has already stamped instance.tenant pre-validation
        assert obj.tenant_id == tenant_a.pk
        assert obj.number != "VC-99999"
        assert re.fullmatch(r"VC-\d{5}", obj.number)

    def test_party_dropdown_narrowed_to_vendor_roles(
            self, tenant_a, tenant_b, vendor_party_a, vendor_party_b):
        """Only parties carrying a supplier OR vendor role appear — customers, carriers and
        other workspaces' vendors stay out of the <select> entirely."""
        from apps.core.models import Party, PartyRole
        customer = Party.objects.create(
            tenant=tenant_a, name="Customer Co", kind="organization")
        PartyRole.objects.create(tenant=tenant_a, party=customer, role="customer")
        spelled_other_way = Party.objects.create(
            tenant=tenant_a, name="Vendor Spelling Co", kind="organization")
        PartyRole.objects.create(tenant=tenant_a, party=spelled_other_way, role="vendor")

        queryset = VendorCommunicationForm(tenant=tenant_a).fields["party"].queryset
        assert vendor_party_a in queryset       # supplier-role spelling
        assert spelled_other_way in queryset    # vendor-role spelling
        assert customer not in queryset         # wrong role
        assert vendor_party_b not in queryset   # another workspace

    def test_follow_up_optional_and_datetime_string_occurred_at(
            self, tenant_a, vendor_party_a):
        form = VendorCommunicationForm(
            data=form_data(party=vendor_party_a.pk, channel="site_visit"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.follow_up_on is None
        assert obj.occurred_at.strftime("%Y-%m-%d %H:%M") == "2026-08-20 10:00"

    def test_direction_blank_ok_channel_choices_enforced(self, tenant_a, vendor_party_a):
        ok = VendorCommunicationForm(
            data=form_data(party=vendor_party_a.pk, direction=""), tenant=tenant_a)
        assert ok.is_valid(), ok.errors
        bad = VendorCommunicationForm(
            data=form_data(party=vendor_party_a.pk, channel="carrier_pigeon"),
            tenant=tenant_a)
        assert not bad.is_valid()
        assert "channel" in bad.errors
