"""Inventory 5.2 — model invariants.

The vendor-log layer's whole contract lives at the model boundary: the per-tenant VC- number
sequence, the cross-workspace party guard, PROTECT so a deleted vendor cannot take its
conversation history along, and the follow-up date that answers "overdue" only once the day
has actually passed.
"""
import datetime
import time

import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.utils import timezone

from apps.inventory.models import VendorCommunication

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ VendorCommunication


class TestVendorCommunicationModel:
    def test_number_sequence_per_tenant(self, tenant_a, tenant_b, vendor_party_a, vendor_party_b):
        first = VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a, subject="First")
        second = VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a, subject="Second")
        assert first.number == "VC-00001"
        assert second.number == "VC-00002"
        # A second workspace's ledger starts at one — sequences never share across tenants.
        other = VendorCommunication.objects.create(
            tenant=tenant_b, party=vendor_party_b, subject="Theirs")
        assert other.number == "VC-00001"

    def test_explicit_number_is_kept(self, tenant_a, vendor_party_a):
        row = VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a, number="VC-99999", subject="Imported")
        row.refresh_from_db()
        assert row.number == "VC-99999"

    def test_ordering_most_recent_first(self, tenant_a, vendor_party_a):
        VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a, subject="Older",
            occurred_at=timezone.make_aware(datetime.datetime(2026, 8, 1, 9, 0)))
        VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a, subject="Newer",
            occurred_at=timezone.make_aware(datetime.datetime(2026, 8, 20, 9, 0)))
        subjects = list(VendorCommunication.objects.values_list("subject", flat=True))
        assert subjects == ["Newer", "Older"]

    def test_channel_css_covers_every_choice(self):
        for channel, _label in VendorCommunication.CHANNEL_CHOICES:
            row = VendorCommunication(channel=channel)
            assert row.channel_css in {
                "badge-info", "badge-green", "badge-amber", "badge-slate", "badge-muted"}

    def test_channel_css_unknown_falls_back_to_muted(self):
        row = VendorCommunication(channel="carrier_pigeon")
        assert row.channel_css == "badge-muted"

    def test_overdue_follow_up(self, communication_a):
        """2026-08-15 is strictly before today — the fixture is overdue."""
        assert communication_a.is_follow_up_overdue is True

    def test_follow_up_today_or_future_or_none_not_overdue(self, tenant_a, vendor_party_a):
        today = timezone.localdate()
        row = VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a, subject="Due today",
            follow_up_on=today)
        assert row.is_follow_up_overdue is False  # today is still due, not overdue
        row.follow_up_on = today + datetime.timedelta(days=7)
        assert row.is_follow_up_overdue is False
        row.follow_up_on = None
        assert row.is_follow_up_overdue is False

    def test_str_unsaved_has_no_none_and_starts_with_vc(self, tenant_a):
        row = VendorCommunication(tenant=tenant_a, channel="email")
        text = str(row)
        assert text.startswith("VC")
        assert "None" not in text

    def test_clean_rejects_foreign_party(self, communication_a, vendor_party_b):
        communication_a.party = vendor_party_b
        with pytest.raises(ValidationError) as err:
            communication_a.full_clean()
        assert "party" in err.value.message_dict

    def test_deleting_party_protected(self, vendor_party_a, communication_a):
        with pytest.raises(ProtectedError):
            vendor_party_a.delete()

    def test_row_delete_works(self, communication_a):
        pk = communication_a.pk
        communication_a.delete()
        assert not VendorCommunication.objects.filter(pk=pk).exists()

    def test_named_indexes_present(self):
        names = {idx.name for idx in VendorCommunication._meta.indexes}
        assert {
            "inv_vc_tnt_party_idx",
            "inv_vc_tnt_channel_idx",
            "inv_vc_tnt_followup_idx",
            "inv_vc_tnt_occur_idx",
        } <= names

    def test_timestamps_set_and_updated_on_second_save(self, tenant_a, vendor_party_a):
        row = VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a, subject="Timestamped")
        assert row.created_at is not None
        assert row.updated_at is not None
        created = row.created_at
        updated_before = row.updated_at
        time.sleep(0.05)  # distinct clock values — auto_now must move on the second save
        row.subject = "Edited"
        row.save()
        row.refresh_from_db()
        assert row.updated_at > updated_before
        assert row.created_at == created  # auto_now_add never moves
