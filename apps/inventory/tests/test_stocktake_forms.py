"""Inventory 5.11 Stocktaking & Cycle Counting — form boundary.

Two planning-form surfaces over verb-driven documents:

* ``CountProgramForm`` — a recurring count cadence [CTP-]. Its ``location`` dropdown
  offers THIS workspace's zones/bins (warehouses excluded — a whole-building cadence is
  the PhysicalInventory event's job), and the model's ``clean()`` refuses cadences that
  promise a day they don't name (weekly without a weekday, monthly without a
  day-of-month) plus any foreign-tenant location.
* ``PhysicalInventoryForm`` — the FREEZE EVENT's planning fields only [PHY-]. Status,
  the ``is_frozen`` marker and ``requested_by`` are system/verb-driven columns kept OFF
  the form entirely, so a crafted POST cannot mass-assign a freeze into existence.

The security boundary is the vendor-log trio again: tenant-scoped dropdowns refusing
foreign pks and wrong-kind pks at choice-validation, ``_reject_foreign`` beneath them as
belt-and-braces, and workspace identity never being a form field — a form built with no
``tenant=`` kwarg narrows nothing and therefore saves nothing.
"""
import datetime

import pytest

from apps.inventory.forms import CountProgramForm, PhysicalInventoryForm
from apps.inventory.models import CountProgram, PhysicalInventory

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _stocktake_program_data(location=None, **overrides):
    # Strings, as a real QueryDict POST would carry them.
    data = {
        "name": "Nightly A-class sweep",
        "location": "" if location is None else str(location.pk),
        "abc_class": "",
        "frequency": "weekly",
        "weekday": "0",
        "day_of_month": "",
        "count_method": "zone",
        "is_active": "on",
        "notes": "Seeded by the form-boundary tests",
    }
    data.update(overrides)
    return data


def _stocktake_event_data(warehouse, **overrides):
    data = {
        "warehouse": str(warehouse.pk),
        "scheduled_date": "2026-09-01",
        "notes": "Quarterly wall-to-wall count",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ CountProgramForm


class TestStocktakeCountProgramForm:
    def test_stocktake_program_meta_fields_are_exactly_the_cadence_columns(self):
        """The form exposes the nine planning columns and NOTHING else — ``number`` /
        ``last_run_date`` (system) and ``tenant`` (workspace identity) are unreachable."""
        assert CountProgramForm.Meta.fields == [
            "name", "location", "abc_class", "frequency", "weekday",
            "day_of_month", "count_method", "is_active", "notes"]
        form = CountProgramForm(tenant=None)
        assert "last_run_date" not in form.fields
        assert "number" not in form.fields
        assert "tenant" not in form.fields

    def test_stocktake_program_valid_create_stamps_tenant_and_mints_number(
            self, tenant_a, stocktake_zone_a):
        """instance.tenant is stamped during __init__ BEFORE validation, so model clean()
        sees a workspace instead of falsely rejecting every create as cross-tenant."""
        form = CountProgramForm(
            data=_stocktake_program_data(stocktake_zone_a), tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.instance.tenant_id == tenant_a.pk
        obj = form.save()
        assert obj.number.startswith("CTP")
        assert obj.frequency == "weekly"
        assert obj.weekday == 0
        assert CountProgram.objects.filter(pk=obj.pk).exists()

    def test_stocktake_program_blank_abc_class_means_any_class(
            self, tenant_a, stocktake_zone_a):
        """An empty abc_class is the catalogued 'Any class' choice, not a gap."""
        form = CountProgramForm(
            data=_stocktake_program_data(stocktake_zone_a, abc_class=""), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.abc_class == ""

    def test_stocktake_program_weekly_without_weekday_rejected_on_clean(
            self, tenant_a, stocktake_zone_a):
        """Model clean(): a weekly cadence must NAME its day."""
        form = CountProgramForm(
            data=_stocktake_program_data(stocktake_zone_a, weekday=""), tenant=tenant_a)
        assert not form.is_valid()
        assert "weekday" in form.errors
        assert CountProgram.objects.count() == 0

    def test_stocktake_program_monthly_without_day_of_month_rejected_on_clean(
            self, tenant_a, stocktake_zone_a):
        """Model clean(): a monthly cadence must NAME its day."""
        form = CountProgramForm(
            data=_stocktake_program_data(
                stocktake_zone_a, frequency="monthly", day_of_month=""),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "day_of_month" in form.errors
        assert CountProgram.objects.count() == 0

    def test_stocktake_program_invalid_frequency_rejected_at_field_level(
            self, tenant_a, stocktake_zone_a):
        """'hourly' is not a FREQUENCY_CHOICES member — it dies at choice validation,
        before model clean() ever runs (no cadence-consistency side errors)."""
        form = CountProgramForm(
            data=_stocktake_program_data(stocktake_zone_a, frequency="hourly"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "frequency" in form.errors
        assert "weekday" not in form.errors
        assert CountProgram.objects.count() == 0

    def test_stocktake_program_location_queryset_excludes_warehouses_and_foreign_rows(
            self, tenant_a, stocktake_warehouse_a, stocktake_zone_a,
            stocktake_bin_a, stocktake_bin_b):
        """A cadence counts a SECTION: the dropdown offers this workspace's zones/bins —
        never a warehouse (that is the freeze event's scope) nor another workspace's rows."""
        qs = CountProgramForm(tenant=tenant_a).fields["location"].queryset
        assert stocktake_zone_a in qs
        assert stocktake_bin_a in qs
        assert stocktake_warehouse_a not in qs
        assert stocktake_bin_b not in qs

    def test_stocktake_program_rejects_warehouse_as_location_choice(
            self, tenant_a, stocktake_warehouse_a):
        """A crafted POST naming a warehouse pk dies at choice validation — the narrowed
        <select> never offered it."""
        form = CountProgramForm(
            data=_stocktake_program_data(stocktake_warehouse_a), tenant=tenant_a)
        assert not form.is_valid()
        assert "location" in form.errors
        assert CountProgram.objects.count() == 0

    def test_stocktake_program_rejects_foreign_location_pk(
            self, tenant_a, stocktake_bin_b):
        """Globex's bin pk smuggled into Acme's POST is a FIELD error, not a 500."""
        form = CountProgramForm(data=_stocktake_program_data(stocktake_bin_b),
                                tenant=tenant_a)
        assert not form.is_valid()
        assert "location" in form.errors
        assert CountProgram.objects.count() == 0

    def test_stocktake_program_without_tenant_kwarg_narrows_nothing_and_saves_nothing(
            self, tenant_a, stocktake_warehouse_a, stocktake_zone_a, stocktake_bin_b):
        """Actual behaviour of the no-tenant build: the queryset stays UNFILTERED (every
        kind and workspace visible), but ``_reject_foreign`` then refuses ANY named
        location against its None workspace — so the form renders choices yet can never
        persist one."""
        form = CountProgramForm(data=_stocktake_program_data(stocktake_zone_a))
        assert stocktake_warehouse_a in form.fields["location"].queryset
        assert stocktake_bin_b in form.fields["location"].queryset
        assert not form.is_valid()
        assert "location" in form.errors
        assert "another workspace" in form.errors["location"][0]
        assert CountProgram.objects.count() == 0

    def test_stocktake_program_edit_keeps_number_and_last_run_intact(
            self, tenant_a, stocktake_program_a):
        """Re-saving an edited program must not mass-assign the system columns: the CTP-
        number survives and a recorded last_run_date cannot be rewritten through the form."""
        CountProgram.objects.filter(pk=stocktake_program_a.pk).update(
            last_run_date=datetime.date(2026, 8, 20))
        stocktake_program_a.refresh_from_db()

        form = CountProgramForm(
            data=_stocktake_program_data(stocktake_program_a.location,
                                         name="Renamed sweep",
                                         frequency="daily"),
            instance=stocktake_program_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        obj.refresh_from_db()
        assert obj.number == stocktake_program_a.number
        assert obj.number.startswith("CTP")
        assert obj.last_run_date == datetime.date(2026, 8, 20)


# ------------------------------------------------------------------ PhysicalInventoryForm


class TestStocktakePhysicalInventoryForm:
    def test_stocktake_event_meta_fields_exclude_the_system_columns(self):
        """Status, the freeze marker, provenance and lifecycle timestamps are verb-driven
        (editable=False) — none may ever arrive through the planning form."""
        assert PhysicalInventoryForm.Meta.fields == ["warehouse", "scheduled_date", "notes"]
        for forbidden in ("status", "is_frozen", "requested_by",
                          "started_at", "closed_at", "number", "tenant"):
            assert forbidden not in PhysicalInventoryForm.Meta.fields
        form = PhysicalInventoryForm(tenant=None)
        for forbidden in ("status", "is_frozen", "requested_by"):
            assert forbidden not in form.fields

    def test_stocktake_event_valid_create_saves_draft_unfrozen_unclaimed(
            self, tenant_a, stocktake_warehouse_a):
        """Saving the planning fields mints a DRAFT event: no freeze, no requester, a PHY-
        number — everything else is earned through start()/reconcile()/cancel()."""
        form = PhysicalInventoryForm(
            data=_stocktake_event_data(stocktake_warehouse_a), tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.instance.tenant_id == tenant_a.pk
        obj = form.save()
        assert obj.number.startswith("PHY")
        assert obj.status == "draft"
        assert obj.is_frozen is False
        assert obj.requested_by_id is None
        assert PhysicalInventory.objects.filter(pk=obj.pk).exists()

    def test_stocktake_event_warehouse_queryset_is_this_tenants_warehouses_only(
            self, tenant_a, stocktake_warehouse_a, stocktake_zone_a,
            stocktake_bin_a, stocktake_warehouse_b):
        """Only buildings of THIS workspace are freezable — zones/bins and Globex's
        warehouse stay out of the dropdown."""
        qs = PhysicalInventoryForm(tenant=tenant_a).fields["warehouse"].queryset
        assert stocktake_warehouse_a in qs
        assert stocktake_zone_a not in qs
        assert stocktake_bin_a not in qs
        assert stocktake_warehouse_b not in qs

    def test_stocktake_event_rejects_non_warehouse_location(
            self, tenant_a, stocktake_zone_a):
        """A crafted POST pointing the freeze at a zone dies at choice validation."""
        form = PhysicalInventoryForm(
            data=_stocktake_event_data(stocktake_zone_a), tenant=tenant_a)
        assert not form.is_valid()
        assert "warehouse" in form.errors
        assert PhysicalInventory.objects.count() == 0

    def test_stocktake_event_rejects_foreign_warehouse(
            self, tenant_a, stocktake_warehouse_b):
        """Globex's warehouse pk smuggled into Acme's POST is a FIELD error, not a 500."""
        form = PhysicalInventoryForm(
            data=_stocktake_event_data(stocktake_warehouse_b), tenant=tenant_a)
        assert not form.is_valid()
        assert "warehouse" in form.errors
        assert PhysicalInventory.objects.count() == 0

    def test_stocktake_event_without_tenant_kwarg_rejects_even_an_owned_warehouse(
            self, tenant_a, stocktake_warehouse_a, stocktake_warehouse_b):
        """No ``tenant=`` kwarg → no scoping anywhere: the queryset shows every building,
        but ``_reject_foreign`` judges each choice against a None workspace and refuses —
        the form can browse, never save."""
        form = PhysicalInventoryForm(
            data=_stocktake_event_data(stocktake_warehouse_a))
        assert stocktake_warehouse_b in form.fields["warehouse"].queryset
        assert not form.is_valid()
        assert "warehouse" in form.errors
        assert "another workspace" in form.errors["warehouse"][0]
        assert PhysicalInventory.objects.count() == 0

    def test_stocktake_event_edit_keeps_number_status_and_freeze_intact(
            self, tenant_a, admin_user, stocktake_event_counting_a):
        """Editing a LIVE (counting/frozen) event re-plans the date and notes only: the
        number, status, freeze marker, started_at and requester all survive untouched —
        no mass assignment can unfreeze a wall-to-wall count."""
        frozen_at = stocktake_event_counting_a.started_at
        form = PhysicalInventoryForm(
            data=_stocktake_event_data(stocktake_event_counting_a.warehouse,
                                       scheduled_date="2026-10-05",
                                       notes="Rescheduled mid-count"),
            instance=stocktake_event_counting_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        obj.refresh_from_db()
        assert obj.number == stocktake_event_counting_a.number
        assert obj.status == "counting"
        assert obj.is_frozen is True
        assert obj.started_at == frozen_at
        assert obj.requested_by_id == admin_user.pk
