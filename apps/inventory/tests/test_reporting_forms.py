"""Inventory 5.17 — form boundary for Reporting & Analytics snapshots.

``ReportSnapshotForm`` fronts ``InventoryReportSnapshot``, a FREEZE of one report's
headline numbers written once and never edited. Only generation knobs are POSTable:
``Meta.fields`` whitelists report_type/title/window_days/location/notes, so the
engine-owned columns (``tenant``, the minted ``number``, ``generated_by``, the computed
``summary``) cannot be mass-assigned by a crafted POST. The location FK is scoped by
``TenantModelForm`` ONLY when the view passes ``tenant=`` — this module pins that
contract both ways (scoped with the kwarg, unscoped without, documenting why the kwarg
is mandatory), and proves ``_reject_foreign`` still renders a foreign location as a
field error beneath the narrowed select. ``clean_window_days`` keeps the window inside
1..3650 or blank; blank is legal because valuation/aging compute whole-history.
"""
import pytest

from apps.inventory.forms import ReportSnapshotForm
from apps.scm.models import Location

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers

SNAPSHOT_DATA = {
    "report_type": "valuation",
    "title": "",
    "window_days": "",
    "location": "",
    "notes": "",
}


def snapshot_data(**overrides):
    data = dict(SNAPSHOT_DATA)
    data.update(overrides)
    return data


# ------------------------------------------------------------------ mass-assignment guard


class TestReportSnapshotFormFieldWhitelist:
    def test_meta_fields_whitelist_is_exact(self, tenant_a):
        """Exactly the five generation knobs are fields — set equality, not subset."""
        assert set(ReportSnapshotForm._meta.fields) == {
            "report_type", "title", "window_days", "location", "notes"}

    def test_engine_owned_columns_are_not_postable(self, tenant_a):
        """A crafted POST can smuggle neither the workspace stamp nor the engine-owned
        columns: ``number`` is minted by save(), ``generated_by``/``summary`` are
        assigned by the view after the engine runs, ``tenant`` never was a field."""
        fields = ReportSnapshotForm(tenant=tenant_a).fields
        for smuggled in ("tenant", "number", "generated_by", "summary"):
            assert smuggled not in fields


# ------------------------------------------------------------------ validation


class TestReportSnapshotFormValidation:
    def test_minimal_valuation_binds_and_saves_without_commit(self, tenant_a):
        """report_type alone is enough: every other knob is optional, and save(commit=False)
        builds the frozen row without touching the database (the view fills summary/number)."""
        form = ReportSnapshotForm(data=snapshot_data(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        assert obj.report_type == "valuation"
        assert obj.window_days is None
        assert obj.location_id is None

    def test_blank_window_legal_for_whole_history_reports(self, tenant_a):
        """Valuation and aging run over ALL history — blank means the report's own
        default, not zero days."""
        for report_type in ("valuation", "aging"):
            form = ReportSnapshotForm(
                data=snapshot_data(report_type=report_type), tenant=tenant_a)
            assert form.is_valid(), form.errors
            assert form.cleaned_data["window_days"] is None

    def test_window_outside_1_to_3650_rejected(self, tenant_a):
        """0 and 3651 die in ``clean_window_days`` with the human message. A negative
        input is rejected too, one layer EARLIER: the model column is a
        PositiveIntegerField, so the field's built-in >= 0 bound fires before the form's
        own validator runs — either layer rejecting is a pass."""
        zero = ReportSnapshotForm(data=snapshot_data(window_days="0"), tenant=tenant_a)
        over = ReportSnapshotForm(data=snapshot_data(window_days="3651"), tenant=tenant_a)
        negative = ReportSnapshotForm(data=snapshot_data(window_days="-5"), tenant=tenant_a)

        for bad in (zero, over):
            assert not bad.is_valid()
            joined = " | ".join(bad.errors["window_days"]).lower()
            assert "between 1 and 3650" in joined
        assert not negative.is_valid()
        assert "window_days" in negative.errors
        assert negative.instance.pk is None

    def test_window_ceiling_3650_accepted(self, tenant_a):
        """The ceiling itself is legal — ten years of trailing ledger."""
        form = ReportSnapshotForm(data=snapshot_data(window_days="3650"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.save(commit=False).window_days == 3650


# ------------------------------------------------------------------ tenant scoping (regression lock)


class TestReportSnapshotFormTenantScoping:
    def test_location_queryset_scoped_only_when_tenant_kwarg_passed(
            self, tenant_a, tenant_b, location_a, location_b):
        """REGRESSION LOCK: the view constructs ``ReportSnapshotForm(data, initial,
        tenant=request.tenant)`` and the location dropdown MUST be scoped to this
        workspace. Built WITHOUT the kwarg the queryset falls back to UNFILTERED —
        every workspace's locations — which is exactly why the kwarg is mandatory
        and pinned here in both directions."""
        scoped_pks = set(ReportSnapshotForm(tenant=tenant_a)
                         .fields["location"].queryset.values_list("pk", flat=True))
        assert location_a.pk in scoped_pks
        assert location_b.pk not in scoped_pks

        bare_pks = set(ReportSnapshotForm()
                       .fields["location"].queryset.values_list("pk", flat=True))
        assert {location_a.pk, location_b.pk} <= bare_pks

    def test_foreign_location_yields_workspace_field_error(
            self, tenant_a, tenant_b, location_a, location_b):
        """The narrowed <select> normally kills a foreign pk at choice-validation; widen
        the queryset past that UX layer so ``_reject_foreign`` itself is what fires —
        the crafted-POST re-check renders 'another workspace' as a location field error
        and saves nothing."""
        form = ReportSnapshotForm(data=snapshot_data(location=location_b.pk),
                                  tenant=tenant_a)
        form.fields["location"].queryset = Location.objects.all()
        assert not form.is_valid()
        assert "location" in form.errors
        joined = " | ".join(form.errors["location"]).lower()
        assert "another workspace" in joined
        assert form.instance.pk is None


# ------------------------------------------------------------------ ?type preselect contract


class TestReportSnapshotTypePreselect:
    def test_initial_report_type_preselects_aging(self):
        """The GET entry point seeds ``initial={'report_type': <type>}`` from ?type=;
        the unbound form carries it (and renders the matching option selected)."""
        form = ReportSnapshotForm(initial={"report_type": "aging"})
        assert form.initial["report_type"] == "aging"
        assert form["report_type"].value() == "aging"
