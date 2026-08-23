"""Inventory 5.9 — form boundary for waves and their membership rows.

The wave header is planner configuration: ``status``/``released_at``/``closed_at`` are
system-set by the verbs, so a crafted POST cannot smuggle them in as fields. Every
tenant-scoped FK is re-checked by ``_reject_foreign`` where it renders as a field error,
and the membership form enforces both the release lock and the duplicate-member rule as
readable ``__all__`` errors instead of uncaught IntegrityErrors (C1).
"""
import datetime
from decimal import Decimal

import pytest

from apps.inventory.forms import FulfillmentWaveForm, FulfillmentWaveOrderForm
from apps.inventory.models import FulfillmentWave, FulfillmentWaveOrder

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers

EXPECTED_FIELDS = ["description", "location", "carrier", "ship_method",
                   "planned_ship_date", "cutoff_at", "priority", "criteria_text", "notes"]


def _fulfillment_valid_wave_data(**overrides):
    data = {
        "description": "September parcel sweep",
        "location": "",
        "carrier": "",
        "ship_method": "standard",
        "planned_ship_date": "2026-09-01",
        "cutoff_at": "2026-08-31T18:00",
        "priority": "75",
        "criteria_text": "All submitted orders under 20 kg",
        "notes": "Planner note",
    }
    data.update(overrides)
    return data


def _fulfillment_extra_wave(tenant):
    """A second PLANNED wave on tenant_a — proves one SO may travel in two waves."""
    return FulfillmentWave.objects.create(
        tenant=tenant, description="Second planned grouping", ship_method="economy")


def _fulfillment_foreign_sales_order(customer, item):
    """An OPEN sales order owned by ANOTHER workspace (tenant_b) — the IDOR target."""
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(
        tenant=customer.tenant, customer=customer, status="submitted",
        source_channel="manual", order_date=datetime.date(2026, 8, 21))
    SalesOrderLine.objects.create(
        sales_order=order, item=item, quantity_ordered=Decimal("2"),
        unit_price=Decimal("10.00"))
    order.recalc_totals()
    return order


def _fulfillment_waveorder_form(wave, sales_order_pk, tenant):
    """The view stamps instance.wave BEFORE is_valid() [FROZEN] — mimic that exactly;
    the mixin then stamps instance.tenant from the ``tenant=`` kwarg."""
    return FulfillmentWaveOrderForm(
        data={"sales_order": sales_order_pk},
        instance=FulfillmentWaveOrder(wave=wave),
        tenant=tenant)


# ------------------------------------------------------------------ FulfillmentWaveForm


class TestFulfillmentWaveForm:
    def test_fulfillment_wave_form_meta_fields_exact(self):
        """Workflow columns are system-set by the verbs — they must never be form fields."""
        assert FulfillmentWaveForm.Meta.fields == EXPECTED_FIELDS
        for banned in ("status", "released_at", "closed_at"):
            assert banned not in FulfillmentWaveForm._meta.fields

    def test_fulfillment_wave_form_full_payload_saves_planned(
            self, tenant_a, fulfillment_loc_wave_a, fulfillment_carrier_a):
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(
                location=fulfillment_loc_wave_a.pk, carrier=fulfillment_carrier_a.pk),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.status == "planned"
        assert obj.released_at is None and obj.closed_at is None
        assert obj.location_id == fulfillment_loc_wave_a.pk
        assert obj.carrier_id == fulfillment_carrier_a.pk
        assert obj.priority == 75

    def test_fulfillment_wave_form_blank_optional_payload_saves(self, tenant_a):
        """location/carrier/ship_method/dates are all optional; only priority (model
        default 100 but not blank) must still be posted."""
        data = {key: "" for key in EXPECTED_FIELDS}
        data["priority"] = "100"
        form = FulfillmentWaveForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.location_id is None
        assert obj.carrier_id is None
        assert obj.ship_method == ""
        assert obj.planned_ship_date is None
        assert obj.cutoff_at is None
        assert obj.priority == 100

    def test_fulfillment_wave_form_rejects_foreign_location(
            self, tenant_a, fulfillment_loc_wave_b):
        before = FulfillmentWave.objects.count()
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(location=fulfillment_loc_wave_b.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["location"]
        assert form.instance.pk is None
        assert FulfillmentWave.objects.count() == before

    def test_fulfillment_wave_form_rejects_foreign_carrier(
            self, tenant_a, fulfillment_carrier_b):
        before = FulfillmentWave.objects.count()
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(carrier=fulfillment_carrier_b.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["carrier"]
        assert FulfillmentWave.objects.count() == before

    def test_fulfillment_wave_form_cross_tenant_pair_rejected_and_saves_nothing(
            self, tenant_a, fulfillment_loc_wave_b, fulfillment_carrier_b):
        """The docstring's belt-and-braces pair: both foreign FKs at once -> two field
        errors, zero rows."""
        before = FulfillmentWave.objects.count()
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(
                location=fulfillment_loc_wave_b.pk, carrier=fulfillment_carrier_b.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "location" in form.errors
        assert "carrier" in form.errors
        assert FulfillmentWave.objects.count() == before

    def test_fulfillment_wave_form_ship_method_junk_rejected(self, tenant_a):
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(ship_method="teleport"), tenant=tenant_a)
        assert not form.is_valid()
        assert "ship_method" in form.errors

    def test_fulfillment_wave_form_priority_junk_rejected(self, tenant_a):
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(priority="abc"), tenant=tenant_a)
        assert not form.is_valid()
        assert "priority" in form.errors

    def test_fulfillment_wave_form_crafted_post_cannot_set_workflow_fields(self, tenant_a):
        """status/released_at/closed_at are off Meta.fields, so smuggled POST values are
        ignored and the row saves as a fresh planned wave with no stamps."""
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(
                status="closed", released_at="2026-01-01T00:00",
                closed_at="2026-01-02T00:00"),
            tenant=tenant_a)
        assert "status" not in form.fields
        assert "released_at" not in form.fields
        assert "closed_at" not in form.fields
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.status == "planned"
        assert obj.released_at is None
        assert obj.closed_at is None


# ------------------------------------------------------------------ FulfillmentWaveOrderForm


class TestFulfillmentWaveOrderForm:
    def test_fulfillment_waveorder_valid_add_to_planned_wave_saves(
            self, tenant_a, admin_user, fulfillment_wave_planned_a, fulfillment_so_second_a):
        before = FulfillmentWaveOrder.objects.count()
        form = _fulfillment_waveorder_form(
            fulfillment_wave_planned_a, fulfillment_so_second_a.pk, tenant_a)
        assert form.is_valid(), form.errors
        member = form.save()
        member.added_by = admin_user
        member.save(update_fields=["added_by"])
        assert FulfillmentWaveOrder.objects.count() == before + 1
        assert member.wave_id == fulfillment_wave_planned_a.pk
        assert member.sales_order_id == fulfillment_so_second_a.pk

    def test_fulfillment_waveorder_duplicate_same_wave_rejected_as__all__(
            self, tenant_a, fulfillment_wave_planned_a, fulfillment_member_a):
        """C1 regression: unique_together ("wave","sales_order") never form-validates
        because "wave" is not a field — the explicit check must render "__all__"."""
        before = FulfillmentWaveOrder.objects.count()
        form = _fulfillment_waveorder_form(
            fulfillment_wave_planned_a, fulfillment_member_a.sales_order_id, tenant_a)
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert any("already in this wave" in msg for msg in form.errors["__all__"])
        assert FulfillmentWaveOrder.objects.count() == before

    def test_fulfillment_waveorder_same_so_other_wave_is_legal(
            self, tenant_a, fulfillment_wave_planned_a, fulfillment_member_a):
        """Uniqueness is per-wave: the same SO joining a DIFFERENT planned wave passes."""
        other = _fulfillment_extra_wave(tenant_a)
        form = _fulfillment_waveorder_form(
            other, fulfillment_member_a.sales_order_id, tenant_a)
        assert form.is_valid(), form.errors
        member = form.save()
        assert member.wave_id == other.pk

    def test_fulfillment_waveorder_released_wave_lock_refuses_membership(
            self, tenant_a, fulfillment_wave_released_a, fulfillment_so_open_a):
        before = FulfillmentWaveOrder.objects.count()
        form = _fulfillment_waveorder_form(
            fulfillment_wave_released_a, fulfillment_so_open_a.pk, tenant_a)
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert any("no longer be changed" in msg for msg in form.errors["__all__"])
        assert FulfillmentWaveOrder.objects.count() == before

    def test_fulfillment_waveorder_foreign_sales_order_rejected(
            self, tenant_a, customer_party_b, item_b, fulfillment_wave_planned_a):
        foreign = _fulfillment_foreign_sales_order(customer_party_b, item_b)
        before = FulfillmentWaveOrder.objects.count()
        form = _fulfillment_waveorder_form(
            fulfillment_wave_planned_a, foreign.pk, tenant_a)
        assert not form.is_valid()
        assert form.errors["sales_order"]
        assert FulfillmentWaveOrder.objects.count() == before


# ------------------------------------------------------------------ TenantUniqueMixin stamping


class TestFulfillmentTenantStamping:
    def test_fulfillment_wave_form_tenant_kwarg_stamps_instance_pre_validation(
            self, tenant_a):
        """Mimics the sibling construction exactly: ``tenant=`` kwarg stamps
        instance.tenant during CREATE validation, so same-tenant payloads validate cleanly
        and save into the right workspace."""
        form = FulfillmentWaveForm(
            data=_fulfillment_valid_wave_data(), tenant=tenant_a)
        assert form.instance.tenant_id == tenant_a.pk
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk

    def test_fulfillment_waveorder_form_tenant_kwarg_stamps_instance_pre_validation(
            self, tenant_a, fulfillment_wave_planned_a, fulfillment_so_second_a):
        form = _fulfillment_waveorder_form(
            fulfillment_wave_planned_a, fulfillment_so_second_a.pk, tenant_a)
        assert form.instance.tenant_id == tenant_a.pk
        assert form.is_valid(), form.errors
        member = form.save()
        assert member.tenant_id == tenant_a.pk
