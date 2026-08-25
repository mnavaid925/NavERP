"""Inventory 5.17 Reporting & Analytics — multi-tenancy IDOR & security.

Adversarial coverage around the ONE 5.17 entity (``InventoryReportSnapshot``) and
the shared compute engine behind it: engine-level tenant isolation (a ``Ledger``
built for Acme never sees Globex's moves even when both workspaces post identical
SKUs against identically-numbered locations), cross-tenant IDOR on detail/delete,
the member/admin gate (delete rewrites evidence so it is admin-only, while reading
and generating reports is everyone's job), the ``ReportSnapshotForm`` scoping
regression lock (the ``tenant=`` kwarg is what narrows the location dropdown; the
widened-queryset probe proves ``_reject_foreign`` is the real boundary), mass
assignment (``generated_by``/``number``/``summary`` are stamped server-side), the
POST-only destructive verb, zero leakage through the list page, the audit trail a
generate leaves behind, and the ``clamp_window`` DoS guard surviving a 5000-digit
query value.
"""
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.inventory.forms import ReportSnapshotForm
from apps.inventory.models import InventoryReportSnapshot
from apps.inventory.views.ReportingAnalytics._engine import (
    DEFAULT_WINDOW_DAYS,
    Ledger,
    build_summary,
    clamp_window,
    valuation_rows,
)
from apps.scm.models import Location

pytestmark = pytest.mark.django_db


# ---- module-level helpers --------------------------------------------------------------------------


def _post_move(tenant, item, location, lot=None, quantity="4", move_type="receipt",
               reference="", reason=""):
    """One append-only StockMove leg, mirroring conftest._post_move's shape."""
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, lot_serial=lot,
        quantity=Decimal(quantity), unit_cost=Decimal("1"),
        move_type=move_type, reference=reference, reason=reason,
        moved_at=timezone.now())


def _mirror_dock(tenant):
    """A location whose CODE matches Acme's DOCK-1 in the foreign workspace."""
    return Location.objects.create(
        tenant=tenant, code="DOCK-1", name=f"{tenant.slug} receiving dock")


def _cost(item, average_cost):
    """Pin the cached WAC (raw StockMove legs never roll it; posting helpers do)."""
    item.average_cost = Decimal(average_cost)
    item.save(update_fields=["average_cost"])
    return item


def _audit_logs(obj):
    """Every core.AuditLog row written about ``obj`` (object_id filtered as a string)."""
    ct = ContentType.objects.get_for_model(type(obj))
    return AuditLog.objects.filter(content_type=ct, object_id=str(obj.pk))


# ---- engine isolation ------------------------------------------------------------------------------


def test_ledger_never_indexes_foreign_moves_on_identically_numbered_spots(
        tenant_a, tenant_b, item_a, item_b, location_a):
    """Both workspaces post receipts at a location coded DOCK-1 with the SAME sku
    CAT-1 — Acme's one-fetch ledger must index ONLY Acme's leg anyway."""
    globex_dock = _mirror_dock(tenant_b)
    acme_leg = _post_move(tenant_a, item_a, location_a, quantity="10")
    globex_leg = _post_move(tenant_b, item_b, globex_dock, quantity="999")

    ledger = Ledger(tenant_a)

    assert acme_leg.item_id == item_a.pk
    assert globex_leg.item_id == item_b.pk
    assert [m.item_id for m in ledger.moves] == [item_a.pk]
    assert item_b.pk not in ledger.by_item
    assert set(ledger.by_spot) == {(item_a.pk, location_a.pk)}
    assert (item_b.pk, globex_dock.pk) not in ledger.by_spot


def test_valuation_rows_never_return_foreign_items_or_locations(
        tenant_a, tenant_b, item_a, item_b, location_a):
    """Even with a fat foreign balance sitting on the twin spot, Acme's valuation
    walk yields exactly one row — Acme's item at Acme's location, nothing else."""
    globex_dock = _mirror_dock(tenant_b)
    _post_move(tenant_a, item_a, location_a, quantity="10")
    _post_move(tenant_b, item_b, globex_dock, quantity="999")

    rows, totals = valuation_rows(tenant_a)

    assert totals["spots"] == 1
    assert len(rows) == 1
    assert rows[0]["item"].pk == item_a.pk
    assert rows[0]["location"].pk == location_a.pk
    for row in rows:
        assert row["item"].tenant_id == tenant_a.pk
        assert row["location"].tenant_id == tenant_a.pk
        assert row["item"].pk != item_b.pk
        assert row["location"].pk != globex_dock.pk


def test_build_summary_matches_manual_computation_over_own_moves_only(
        tenant_a, tenant_b, item_a, item_b, location_a):
    """Mirror ledgers (identical sku, identical move pattern, DIFFERENT cached WAC)
    must freeze independently: each workspace's total is its own on-hand x its own
    average cost — 7 x 8.00 vs 7 x 5.00 — never a blended figure."""
    _cost(item_a, "8.0000")
    _cost(item_b, "5.0000")
    globex_dock = _mirror_dock(tenant_b)
    for tenant, item, loc in [(tenant_a, item_a, location_a),
                              (tenant_b, item_b, globex_dock)]:
        _post_move(tenant, item, loc, quantity="10")
        _post_move(tenant, item, loc, quantity="-3", move_type="issue")

    summary_a = build_summary("valuation", tenant_a)
    summary_b = build_summary("valuation", tenant_b)

    assert summary_a["spots"] == 1
    assert summary_a["total_value"] == 56.0  # 7 units x 8.00 — Globex's 5.00 absent
    assert [(r["sku"], r["on_hand"], r["value"]) for r in summary_a["top_rows"]] == [
        ("CAT-1", 7.0, 56.0)]
    assert summary_b["total_value"] == 35.0  # 7 units x 5.00 — Acme's 8.00 absent


# ---- IDOR --------------------------------------------------------------------------------------------


def test_snapshot_detail_and_delete_of_foreign_pk_404_and_row_survives(
        client_a, tenant_b):
    """A Globex snapshot reads as nonexistent to Acme's admin: the detail GET and the
    delete POST both answer 404 and the frozen evidence stays alive."""
    foreign = InventoryReportSnapshot.objects.create(
        tenant=tenant_b, report_type="valuation", title="Globex month-end freeze")

    assert client_a.get(
        reverse("inventory:snapshot_detail", args=[foreign.pk])).status_code == 404
    assert client_a.post(
        reverse("inventory:snapshot_delete", args=[foreign.pk])).status_code == 404

    foreign.refresh_from_db()  # raises if deleted
    assert foreign.report_type == "valuation"
    assert foreign.title == "Globex month-end freeze"


# ---- role gate ---------------------------------------------------------------------------------------


def test_member_delete_is_403_but_reads_and_generation_stay_open(
        member_client, tenant_a):
    """Deleting a snapshot rewrites the audit trail, so it is tenant-admin-only (403
    for a plain member, row intact) — while generating and listing freezes is plain
    read/reporting work every signed-in member may do."""
    owned = InventoryReportSnapshot.objects.create(
        tenant=tenant_a, report_type="aging")

    assert member_client.post(
        reverse("inventory:snapshot_delete", args=[owned.pk])).status_code == 403
    owned.refresh_from_db()  # raises if deleted
    assert member_client.get(
        reverse("inventory:snapshot_list")).status_code == 200
    assert member_client.get(
        reverse("inventory:snapshot_generate")).status_code == 200


# ---- form scoping regression lock ---------------------------------------------------------------------


def test_location_queryset_scoped_only_when_tenant_kwarg_passed(
        tenant_a, tenant_b, location_a, location_b):
    """REGRESSION LOCK (fixed C1): the view builds ``ReportSnapshotForm(...,
    tenant=request.tenant)`` and the location dropdown MUST be workspace-scoped.
    Built WITHOUT the kwarg the queryset falls back UNFILTERED — both workspaces'
    locations — which is why the kwarg is mandatory and pinned in both directions."""
    scoped_pks = set(ReportSnapshotForm(tenant=tenant_a)
                     .fields["location"].queryset.values_list("pk", flat=True))
    assert location_a.pk in scoped_pks
    assert location_b.pk not in scoped_pks

    bare_pks = set(ReportSnapshotForm()
                   .fields["location"].queryset.values_list("pk", flat=True))
    assert {location_a.pk, location_b.pk} <= bare_pks


def test_widened_queryset_foreign_location_still_rejected_as_foreign_workspace(
        tenant_a, tenant_b, location_b):
    """The narrowed <select> normally kills a foreign pk at choice-validation; widen
    the queryset past that UX layer so ``_reject_foreign`` itself must fire — the
    crafted POST dies with 'another workspace' and saves nothing."""
    form = ReportSnapshotForm(
        data={"report_type": "valuation", "title": "", "window_days": "",
              "location": str(location_b.pk), "notes": ""},
        tenant=tenant_a)
    form.fields["location"].queryset = Location.objects.all()

    assert not form.is_valid()
    joined = " | ".join(form.errors["location"]).lower()
    assert "another workspace" in joined
    assert form.instance.pk is None


# ---- mass assignment -----------------------------------------------------------------------------------


def test_crafted_generate_post_cannot_stamp_generated_by_number_or_summary(
        client_a, admin_user, admin_b, tenant_a):
    """A generate POST smuggling ``generated_by``/``number``/``summary`` still lands:
    the server stamps generated_by from request.user, mints the per-tenant IRS-
    sequence number, and OVERWRITES summary with the engine's live computation."""
    response = client_a.post(reverse("inventory:snapshot_generate"), data={
        "report_type": "valuation",
        "title": "",
        "window_days": "",
        "location": "",
        "notes": "probe",
        "generated_by": str(admin_b.pk),
        "number": "IRS-99999",
        "summary": '{"total_value": -999}',
    })
    assert response.status_code == 302  # generation succeeded...

    snap = InventoryReportSnapshot.objects.get(tenant=tenant_a)
    assert snap.notes == "probe"  # ...and really saved its legitimate knob
    assert snap.generated_by_id == admin_user.pk
    assert snap.number.startswith("IRS-")
    assert snap.number != "IRS-99999"
    assert snap.summary != {"total_value": -999}
    assert set(snap.summary) == {"total_value", "spots", "top_rows"}
    assert snap.summary["spots"] == 0  # engine output over this (empty) ledger
    assert snap.summary["total_value"] == 0.0


# ---- method discipline ----------------------------------------------------------------------------------


def test_get_on_delete_url_is_405_not_a_deletion(client_a, tenant_a):
    """snapshot_delete carries require_POST explicitly: a GET answers 405 and deletes
    nothing — the frozen row survives the probe byte-for-byte."""
    owned = InventoryReportSnapshot.objects.create(
        tenant=tenant_a, report_type="abc", notes="evidence")

    assert client_a.get(
        reverse("inventory:snapshot_delete", args=[owned.pk])).status_code == 405

    owned.refresh_from_db()  # raises if deleted
    assert owned.notes == "evidence"


# ---- list-page leakage -----------------------------------------------------------------------------------


def test_snapshot_list_shows_only_own_tenant_numbers(client_b, tenant_a, tenant_b):
    """Globex's lens renders Globex's freezes only: its own markers appear, Acme's do
    not, and the colliding per-tenant IRS-00001 appears exactly ONCE (Acme's twin
    row did not leak into the table)."""
    InventoryReportSnapshot.objects.create(
        tenant=tenant_a, report_type="valuation", title="ACME-FREEZE-MARKER")
    InventoryReportSnapshot.objects.create(
        tenant=tenant_b, report_type="valuation", title="GLOBEX-FREEZE-MARKER-A")
    InventoryReportSnapshot.objects.create(
        tenant=tenant_b, report_type="turnover",
        title="GLOBEX-FREEZE-MARKER-B")

    html = client_b.get(reverse("inventory:snapshot_list")).content.decode()

    assert "GLOBEX-FREEZE-MARKER-A" in html
    assert "GLOBEX-FREEZE-MARKER-B" in html
    assert "ACME-FREEZE-MARKER" not in html
    assert "IRS-00002" in html          # exists only in Globex's sequence
    # Globex's first — not Acme's same-numbered twin. Counted as a CELL
    # (" >IRS-00001< ") because every row also echoes its number inside the
    # delete-confirm JS string, which would double any naive page count.
    assert html.count(">IRS-00001<") == 1


# ---- audit trail -------------------------------------------------------------------------------------------


def test_successful_generate_writes_one_create_audit_row(client_a, admin_user,
                                                         tenant_a):
    """A successful generate lands exactly ONE core.AuditLog 'create' row about the
    new snapshot, attributed to the acting admin inside its tenant."""
    response = client_a.post(reverse("inventory:snapshot_generate"), data={
        "report_type": "aging", "title": "", "window_days": "",
        "location": "", "notes": ""})
    assert response.status_code == 302

    snap = InventoryReportSnapshot.objects.get(tenant=tenant_a)
    logs = _audit_logs(snap).filter(action="create")
    assert logs.count() == 1
    log = logs.get()
    assert log.user_id == admin_user.pk
    assert log.tenant_id == tenant_a.pk


# ---- DoS guard --------------------------------------------------------------------------------------------


def test_clamp_window_survives_5000_digit_input_without_raising():
    """A 5000-digit ?days= passes the old isdecimal() check and used to blow Python's
    int->str conversion limit inside int(); the length guard degrades it to the
    default window instead."""
    assert clamp_window("9" * 5000) == DEFAULT_WINDOW_DAYS
    assert clamp_window("9" * 5000) == 90  # pinned literally: the documented default
