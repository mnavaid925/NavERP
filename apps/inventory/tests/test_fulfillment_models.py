"""Inventory 5.9 — model invariants for FulfillmentWave + FulfillmentWaveOrder.

The wave layer owns no stock and posts nothing into scm: its whole contract is the
lifecycle verbs (release/close/cancel, each locked and audited), the honest derived
picture (progress answers ``None``, never a flattering zero; cancelled orders are never
progress), the text-convention pick linkage (``PickTask.wave_ref == wave.number``), and
the membership rules (unique per order per wave, frozen once the wave leaves planned).
"""
import re

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import AuditLog
from apps.inventory.models import FulfillmentWave, FulfillmentWaveOrder
from apps.scm.models import PickTask, SalesOrder

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _fulfillment_wave(tenant, **fields):
    """A minimal planned wave; location/carrier are optional header dressing."""
    return FulfillmentWave.objects.create(tenant=tenant, **fields)


def _fulfillment_sales_order(tenant, customer):
    """An open (submitted) scm.SalesOrder — no lines needed for model-lane tests."""
    return SalesOrder.objects.create(
        tenant=tenant, customer=customer, status="submitted")


def _fulfillment_add_member(wave, sales_order, user=None):
    from apps.inventory.models import FulfillmentWaveOrder as Member
    return Member.objects.create(
        tenant=wave.tenant, wave=wave, sales_order=sales_order, added_by=user)


def _fulfillment_pick(tenant, number, status="pending", **fields):
    """A scm.PickTask matched through the wave_ref text convention."""
    return PickTask.objects.create(
        tenant=tenant, strategy="single", status=status, wave_ref=number, **fields)


def _fulfillment_audit_rows(obj):
    """Every core.AuditLog row written about ``obj`` (house pattern: ContentType + id)."""
    return AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=str(obj.pk))


# ------------------------------------------------------------------ basics


class TestFulfillmentWaveBasics:
    def test_str_saved_counts_members_and_unsaved_is_safe(self, fulfillment_wave_planned_a,
                                                          fulfillment_member_a):
        text = str(fulfillment_wave_planned_a)
        assert text.startswith("WAV-")
        assert "1 order(s)" in text  # the fixture's single membership row is counted
        unsaved = FulfillmentWave(tenant=fulfillment_wave_planned_a.tenant)
        assert "None" not in str(unsaved)  # admin preview on an unpersisted row must not blow up
        assert "WAV" in str(unsaved)

    def test_number_auto_assigned_wav_per_tenant(self, tenant_a, tenant_b):
        first = _fulfillment_wave(tenant_a)
        assert re.fullmatch(r"WAV-\d{5}", first.number)
        second = _fulfillment_wave(tenant_a)
        assert second.number != first.number and second.number > first.number
        foreign = _fulfillment_wave(tenant_b)
        assert foreign.number == "WAV-00001"  # sequences never share across workspaces

    def test_ordering_newest_first(self, tenant_a):
        older = _fulfillment_wave(tenant_a)
        newer = _fulfillment_wave(tenant_a)
        ids = list(FulfillmentWave.objects.all().values_list("id", flat=True))
        assert ids.index(newer.id) < ids.index(older.id)

    def test_status_css_map_complete_and_colour_named(self, fulfillment_wave_planned_a):
        choices = {code for code, _label in FulfillmentWave.STATUS_CHOICES}
        assert set(FulfillmentWave.STATUS_CSS) == choices  # every status has a badge
        colour_named = {
            "badge-slate", "badge-info", "badge-green", "badge-red",
            "badge-amber", "badge-muted"}
        for css in FulfillmentWave.STATUS_CSS.values():
            assert css in colour_named  # L33: theme.css ships colour-named modifiers only
        assert fulfillment_wave_planned_a.status_css == "badge-slate"
        assert FulfillmentWave(status="teleported").status_css == "badge-muted"

    def test_is_editable_only_planned(self, tenant_a, admin_user,
                                      fulfillment_wave_planned_a,
                                      fulfillment_wave_released_a):
        assert fulfillment_wave_planned_a.is_editable is True
        released = fulfillment_wave_released_a
        assert released.is_editable is False
        closed = released.close(admin_user)
        assert closed.is_editable is False
        cancelled = fulfillment_wave_planned_a.cancel(admin_user)
        assert cancelled.is_editable is False


# ------------------------------------------------------------------ verbs


class TestFulfillmentWaveVerbs:
    def test_release_refuses_zero_members_and_wrong_state(
            self, tenant_a, admin_user, fulfillment_wave_released_a):
        empty = _fulfillment_wave(tenant_a)
        with pytest.raises(ValidationError) as err:
            empty.release(admin_user)
        assert "no sales orders" in " ".join(err.value.messages)
        empty.refresh_from_db()
        assert empty.status == "planned"
        assert empty.released_at is None

        with pytest.raises(ValidationError) as err:
            fulfillment_wave_released_a.release(admin_user)
        assert "cannot be released" in " ".join(err.value.messages)

    def test_release_stamps_released_at(self, fulfillment_wave_planned_a, admin_user,
                                        fulfillment_member_a):
        got = fulfillment_wave_planned_a.release(admin_user)
        assert got.status == "released"
        assert got.released_at is not None
        assert got.released_at <= timezone.now()
        assert got.closed_at is None

    def test_close_from_released_stamps_closed_at(self, fulfillment_wave_released_a,
                                                  admin_user):
        stamped = fulfillment_wave_released_a.released_at
        got = fulfillment_wave_released_a.close(admin_user)
        assert got.status == "closed"
        assert got.closed_at is not None
        assert got.released_at == stamped  # closing never re-stamps release

    def test_close_from_planned_refused(self, fulfillment_wave_planned_a, admin_user):
        with pytest.raises(ValidationError) as err:
            fulfillment_wave_planned_a.close(admin_user)
        assert "release it first" in " ".join(err.value.messages)
        fulfillment_wave_planned_a.refresh_from_db()
        assert fulfillment_wave_planned_a.status == "planned"
        assert fulfillment_wave_planned_a.closed_at is None

    def test_cancel_from_planned_and_released_works(
            self, fulfillment_wave_planned_a, fulfillment_wave_released_a, admin_user):
        paper = fulfillment_wave_planned_a.cancel(admin_user)
        assert paper.status == "cancelled"
        assert paper.closed_at is not None
        assert paper.released_at is None  # paper cancellation never touched the floor
        pulled = fulfillment_wave_released_a.cancel(admin_user)
        assert pulled.status == "cancelled"
        assert pulled.released_at is not None  # release history survives the cancel

    def test_cancel_after_closed_refused(self, fulfillment_wave_released_a, admin_user):
        done = fulfillment_wave_released_a.close(admin_user)
        with pytest.raises(ValidationError) as err:
            done.cancel(admin_user)
        assert "cannot be cancelled" in " ".join(err.value.messages)
        done.refresh_from_db()
        assert done.status == "closed"

    def test_verbs_write_audit_rows(self, tenant_a, admin_user, customer_party_a,
                                    fulfillment_wave_planned_a, fulfillment_member_a,
                                    fulfillment_wave_released_a):
        # release + close each land exactly one attributed row, oldest first.
        fulfillment_wave_planned_a.release(admin_user)
        fulfillment_wave_planned_a.close(admin_user)
        rows = list(_fulfillment_audit_rows(fulfillment_wave_planned_a).order_by("id"))
        assert [row.action for row in rows] == ["release", "close"]
        assert rows[0].user == admin_user and rows[0].tenant == tenant_a
        assert rows[0].changes == {"status": "released"}

        # a paper cancellation records that the wave was never on the floor.
        fresh = _fulfillment_wave(tenant_a)
        _fulfillment_add_member(fresh, _fulfillment_sales_order(tenant_a, customer_party_a),
                                admin_user)
        fresh.cancel(admin_user)
        log = _fulfillment_audit_rows(fresh).get()
        assert log.changes == {"status": "cancelled", "was_released": False}

        # cancelling a really-released wave says so.
        fulfillment_wave_released_a.cancel(admin_user)
        pulled_log = _fulfillment_audit_rows(fulfillment_wave_released_a).get(action="cancel")
        assert pulled_log.changes["was_released"] is True


# ------------------------------------------------------------------ derived picture


class TestFulfillmentWaveDerivedPicture:
    def test_orders_fulfilled_count_honest_and_reads_deterministic(
            self, tenant_a, customer_party_a,
            fulfillment_wave_planned_a, fulfillment_so_open_a):
        """member_order_count counts every row; fulfilled counts only fulfilled-or-later;
        cancelled is deliberately never progress; repeated property reads agree."""
        extra_so = _fulfillment_sales_order(tenant_a, customer_party_a)
        _fulfillment_add_member(fulfillment_wave_planned_a, fulfillment_so_open_a)
        _fulfillment_add_member(fulfillment_wave_planned_a, extra_so)
        assert fulfillment_wave_planned_a.member_order_count == 2
        assert fulfillment_wave_planned_a.orders_fulfilled_count == 0  # submitted ≠ progress

        SalesOrder.objects.filter(pk=fulfillment_so_open_a.pk).update(status="fulfilled")
        assert fulfillment_wave_planned_a.orders_fulfilled_count == 1
        SalesOrder.objects.filter(pk=extra_so.pk).update(status="partially_fulfilled")
        assert fulfillment_wave_planned_a.orders_fulfilled_count == 2

        SalesOrder.objects.filter(pk=extra_so.pk).update(status="cancelled")
        assert fulfillment_wave_planned_a.orders_fulfilled_count == 1

        # kwargs-free determinism: identical reads answer identically.
        assert fulfillment_wave_planned_a.member_order_count == 2
        assert (fulfillment_wave_planned_a.orders_fulfilled_count ==
                fulfillment_wave_planned_a.orders_fulfilled_count)
        assert (fulfillment_wave_planned_a.pick_progress_pct ==
                fulfillment_wave_planned_a.pick_progress_pct)

    def test_pick_progress_none_without_picks(self, fulfillment_wave_planned_a):
        """A numbered wave with zero matching picks answers None — never a 0% accusation."""
        assert fulfillment_wave_planned_a.number
        assert fulfillment_wave_planned_a.pick_progress_pct is None

    def test_pick_progress_none_when_all_matched_cancelled(self, fulfillment_wave_planned_a):
        _fulfillment_pick(fulfillment_wave_planned_a.tenant,
                          fulfillment_wave_planned_a.number, status="cancelled")
        assert fulfillment_wave_planned_a.pick_progress_pct is None  # no live denominator

    def test_pick_progress_computed_over_done_vs_active(self, fulfillment_wave_planned_a):
        tenant = fulfillment_wave_planned_a.tenant
        _fulfillment_pick(tenant, fulfillment_wave_planned_a.number, status="picked")
        active = _fulfillment_pick(tenant, fulfillment_wave_planned_a.number,
                                   status="pending")
        assert fulfillment_wave_planned_a.pick_progress_pct == 50
        active.status = "packed"  # packed is also a PICK_DONE_STATUS
        active.save(update_fields=["status"])
        assert fulfillment_wave_planned_a.pick_progress_pct == 100

    def test_linked_picks_matches_only_same_refs_newest_first(
            self, tenant_a, tenant_b, fulfillment_wave_planned_a,
            fulfillment_wave_released_a):
        wave = fulfillment_wave_planned_a
        first = _fulfillment_pick(tenant_a, wave.number, ship_to="Acme depot")
        second = _fulfillment_pick(tenant_a, wave.number, ship_to="Acme annex")
        _fulfillment_pick(tenant_b, wave.number)  # same ref, WRONG workspace — never matches
        _fulfillment_pick(tenant_a, fulfillment_wave_released_a.number)  # another wave's ref

        linked = list(wave.linked_picks())
        assert [task.id for task in linked] == [second.id, first.id]  # newest first
        assert all(task.wave_ref == wave.number and task.tenant_id == wave.tenant_id
                   for task in linked)


# ------------------------------------------------------------------ membership


class TestFulfillmentWaveMembership:
    def test_duplicate_member_rejected_at_db_level(self, fulfillment_member_a):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                FulfillmentWaveOrder.objects.create(
                    tenant=fulfillment_member_a.tenant, wave=fulfillment_member_a.wave,
                    sales_order=fulfillment_member_a.sales_order)

    def test_duplicate_member_via_full_clean_keyed_all(self, tenant_a,
                                                       fulfillment_member_a,
                                                       fulfillment_so_second_a):
        existing_text = str(fulfillment_member_a)
        assert fulfillment_member_a.wave.number in existing_text
        assert fulfillment_member_a.sales_order.number in existing_text

        dup = FulfillmentWaveOrder(
            tenant=tenant_a, wave=fulfillment_member_a.wave,
            sales_order=fulfillment_member_a.sales_order)
        with pytest.raises(ValidationError) as err:
            dup.full_clean()
        assert "__all__" in err.value.message_dict  # validate_unique catches it model-side too

    def test_membership_locked_once_wave_left_planned(self, tenant_a, fulfillment_member_a,
                                                      fulfillment_wave_released_a):
        # the planned wave's own SO is free to join ANOTHER wave — only the lock fires.
        late = FulfillmentWaveOrder(
            tenant=tenant_a, wave=fulfillment_wave_released_a,
            sales_order=fulfillment_member_a.sales_order)
        with pytest.raises(ValidationError) as err:
            late.full_clean()
        assert "__all__" in err.value.message_dict
        assert "membership" in " ".join(err.value.messages)

    def test_member_cross_tenant_guards_keyed_per_field(self, tenant_a, tenant_b,
                                                        customer_party_b,
                                                        fulfillment_wave_planned_a,
                                                        fulfillment_so_open_a,
                                                        fulfillment_foreign_wave_b):
        foreign_so = _fulfillment_sales_order(tenant_b, customer_party_b)
        bad_order = FulfillmentWaveOrder(
            tenant=tenant_a, wave=fulfillment_wave_planned_a, sales_order=foreign_so)
        with pytest.raises(ValidationError) as err:
            bad_order.full_clean()
        assert err.value.message_dict["sales_order"] == [
            "That record belongs to another workspace."]

        bad_wave = FulfillmentWaveOrder(
            tenant=tenant_a, wave=fulfillment_foreign_wave_b,
            sales_order=fulfillment_so_open_a)
        with pytest.raises(ValidationError) as err:
            bad_wave.full_clean()
        assert err.value.message_dict["wave"] == ["That record belongs to another workspace."]


# ------------------------------------------------------------------ header clean()


class TestFulfillmentWaveClean:
    def test_location_and_carrier_cross_tenant_guards_keyed_per_field(
            self, tenant_a, fulfillment_loc_wave_a, fulfillment_loc_wave_b,
            fulfillment_carrier_a, fulfillment_carrier_b):
        both_foreign = FulfillmentWave(
            tenant=tenant_a, description="Guarded header",
            location=fulfillment_loc_wave_b, carrier=fulfillment_carrier_b)
        with pytest.raises(ValidationError) as err:
            both_foreign.full_clean()
        assert err.value.message_dict["location"] == [
            "That record belongs to another workspace."]
        assert err.value.message_dict["carrier"] == [
            "That record belongs to another workspace."]

        owned = FulfillmentWave(
            tenant=tenant_a, description="Clean header",
            location=fulfillment_loc_wave_a, carrier=fulfillment_carrier_a)
        owned.full_clean()  # must not raise
