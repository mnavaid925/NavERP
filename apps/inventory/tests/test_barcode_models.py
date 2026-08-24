"""Inventory 5.14 Barcode & RFID Integration — model boundary.

Covers the three 5.14 entities against their frozen contract:

* ``BarcodeLabel`` [LBL-] — per-tenant auto-numbering, ``default_payload()`` derivation per
  target type (item SKU / bin code / lot number / free-form ref), ``print()`` stamping
  (printed_at/by + draft→printed, reprint allowed, voided refused) and ``void()`` (refuses
  ONLY a second void — from draft or printed it always works).
* ``resolve_code`` precedence walk — Item.sku beats Location.code beats LotSerial.number
  beats RfidTag.epc; unknown strings answer ``("unknown", None)`` rather than raising.
* ``ScanSession.close()`` — stamps ended_at exactly once and refuses a re-close;
  ``ScanEvent.record`` stores the resolution snapshot (kind/pk/label) plus ``ok`` and
  silently skips blank codes.
* ``RfidTag`` — EPC normalisation (strip + upper on save), the has_target-guarded
  lifecycle verbs (activate needs a target, mark_lost needs active, retire accepts
  unassigned OR active) and ``bulk_read`` stamping last-seen while reporting unknowns.
"""
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.inventory.models import (
    BarcodeLabel,
    RfidTag,
    ScanEvent,
    ScanSession,
    resolve_code,
)
from apps.scm.models import Location, LotSerial

pytestmark = pytest.mark.django_db


# ---- BarcodeLabel -----------------------------------------------------------------------------------


def test_barcode_label_auto_numbers_and_derives_payload_per_target_type(
        tenant_a, item_a, location_a):
    """A saved label mints its LBL- number once and derives a blank payload from whatever
    L36 master it points at — item SKU, bin code, or the free-form reference itself."""
    item_label = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="item", item=item_a, symbology="code128")
    assert item_label.number.startswith("LBL-")
    assert item_label.status == "draft"
    assert item_label.payload == item_a.sku

    bin_label = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="location", location=location_a, symbology="code39")
    assert bin_label.number.startswith("LBL-")
    assert bin_label.payload == location_a.code

    free_label = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="free", target_ref="PLT-77", symbology="qr")
    assert free_label.payload == "PLT-77"


def test_barcode_label_lot_target_derives_the_lot_number_payload(tenant_a, item_a):
    """target_type='lot' derives from scm.LotSerial.number — the third spine lookup."""
    lot = LotSerial.objects.create(tenant=tenant_a, item=item_a, number="LOTA-9001")
    label = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="lot", lot_serial=lot, symbology="code128")
    assert label.payload == "LOTA-9001"


def test_barcode_label_print_stamps_printed_at_by_and_flips_status(
        tenant_a, vendor_party_a, item_a):
    """print() flips draft→printed, stamps printed_at, and records the printing party when
    one is handed over; reprinting an already-printed label refreshes the stamp."""
    label = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="item", item=item_a, copies=3)
    assert label.printed_at is None
    assert label.printed_by_id is None

    label.print(party=vendor_party_a)
    label.refresh_from_db()
    assert label.status == "printed"
    assert label.printed_at is not None
    assert label.printed_by_id == vendor_party_a.pk

    first_stamp = label.printed_at
    label.print()
    label.refresh_from_db()
    assert label.status == "printed"
    assert label.printed_at >= first_stamp


def test_barcode_label_void_refuses_double_void_but_nothing_else(
        tenant_a, item_a, location_a):
    """void() works from BOTH draft and printed states — the only refusal is a second
    void — and a voided label can never be printed again."""
    draft = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="item", item=item_a)
    draft.void()
    draft.refresh_from_db()
    assert draft.status == "void"
    with pytest.raises(ValidationError):
        draft.void()

    printed = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="location", location=location_a)
    printed.print()
    printed.void()
    printed.refresh_from_db()
    assert printed.status == "void"

    with pytest.raises(ValidationError):
        printed.print()


# ---- resolve_code precedence ------------------------------------------------------------------------


def test_barcode_resolve_code_item_wins_when_codes_collide_across_spines(tenant_a, item_a,
                                                                         location_a):
    """An Item SKU and a Location code sharing ONE string collide deliberately: the spine
    walk answers the ITEM first, and lookups are case-insensitive end to end."""
    collision = "SHARED-CODE"
    item = type(item_a).objects.create(tenant=tenant_a, sku=collision, name="Collision item")
    Location.objects.create(tenant=tenant_a, code=collision, name="Collision bin")

    kind, obj = resolve_code(tenant_a, collision.lower())
    assert kind == "item"
    assert obj.pk == item.pk


def test_barcode_resolve_code_answers_rfid_then_unknown(tenant_a, rfid_tag_active_a):
    """A non-SKU/non-bin/non-lot string falls through to the RFID leg (upper-cased), and
    anything unmatched — including whitespace — answers ("unknown", None) instead of
    raising."""
    kind, obj = resolve_code(tenant_a, rfid_tag_active_a.epc.lower())
    assert kind == "rfid"
    assert obj.pk == rfid_tag_active_a.pk

    assert resolve_code(tenant_a, "NOPE-404") == ("unknown", None)
    assert resolve_code(tenant_a, "   ") == ("unknown", None)


# ---- ScanSession / ScanEvent ------------------------------------------------------------------------


def test_barcode_scan_event_record_snapshots_resolution_and_skips_blanks(
        scan_session_open_a, item_a):
    """record() appends one immutable capture per code: the match's kind/pk/human label
    are snapshotted at scan time, ok flags the hit, blanks return None and write nothing."""
    hit = ScanEvent.record(scan_session_open_a, "CAT-1", kind="item", obj=item_a)
    assert hit.ok is True
    assert hit.resolved_kind == "item"
    assert hit.resolved_id == item_a.pk
    assert hit.resolved_label == str(item_a)[:120]
    assert hit.raw_code == "CAT-1"

    miss = ScanEvent.record(scan_session_open_a, "GHOST-99")
    assert miss.ok is False
    assert miss.resolved_kind == "unknown"
    assert miss.resolved_id is None
    assert miss.resolved_label == ""

    assert ScanEvent.record(scan_session_open_a, "   ") is None
    assert scan_session_open_a.events.count() == 2


def test_barcode_scan_session_close_stamps_ended_at_once_and_refuses_reclose(
        tenant_a, scan_session_open_a):
    """close() freezes the session exactly once — ended_at is stamped here — and a second
    close raises loudly instead of rewriting the audit timestamp."""
    assert scan_session_open_a.status == "open"
    assert scan_session_open_a.ended_at is None

    scan_session_open_a.close()
    scan_session_open_a.save()
    scan_session_open_a.refresh_from_db()
    assert scan_session_open_a.status == "closed"
    assert scan_session_open_a.ended_at is not None
    closed_at = scan_session_open_a.ended_at

    with pytest.raises(ValidationError):
        scan_session_open_a.close()

    scan_session_open_a.refresh_from_db()
    assert scan_session_open_a.ended_at == closed_at


# ---- RfidTag ----------------------------------------------------------------------------------------


def test_barcode_rfid_tag_normalizes_epc_and_activate_demands_a_target(tenant_a, item_a):
    """Lowercase (or padded) input is stored strip()+upper(); activating a target-less tag
    refuses, and anchoring an item unblocks activation."""
    tag = RfidTag.objects.create(tenant=tenant_a, epc="  e280689e000000aa  ")
    tag.refresh_from_db()
    assert tag.epc == "E280689E000000AA"
    assert tag.status == "unassigned"

    with pytest.raises(ValidationError):
        tag.activate()

    tag.item = item_a
    tag.activate()
    tag.save(update_fields=["status", "updated_at"])
    tag.refresh_from_db()
    assert tag.status == "active"


def test_barcode_rfid_lifecycle_guards_mark_lost_and_retire(tenant_a, item_a):
    """mark_lost only moves an ACTIVE tag; retire accepts unassigned or active but never
    runs twice."""
    stray = RfidTag.objects.create(tenant=tenant_a, epc="E280689E000000C1")
    with pytest.raises(ValidationError):
        stray.mark_lost()

    stray.retire()
    stray.refresh_from_db()
    assert stray.status == "retired"
    with pytest.raises(ValidationError):
        stray.retire()

    anchored = RfidTag.objects.create(tenant=tenant_a, epc="E280689E000000C2", item=item_a)
    anchored.activate()
    anchored.save(update_fields=["status"])
    anchored.mark_lost()
    anchored.refresh_from_db()
    assert anchored.status == "lost"


def test_barcode_rfid_bulk_read_stamps_last_seen_and_reports_unknown(tenant_a, location_a):
    """bulk_read dedupes/normalizes the sweep, updates last_seen(_location) on every
    matching tag of ANY status in one pass, and reports the unrecognized EPCs as a sorted
    list instead of raising."""
    seen_before = RfidTag.objects.create(tenant=tenant_a, epc="E280689E000000D1")
    retired = RfidTag.objects.create(tenant=tenant_a, epc="E280689E000000D2")
    retired.retire()
    retired.save(update_fields=["status"])

    result = RfidTag.bulk_read(
        tenant_a,
        ["e280689e000000d1", "E280689E000000D2", "E280689E000000D2", "FFFF0000", "  "],
        location=location_a,
    )
    assert result["matched"] == 2
    assert result["unknown"] == ["FFFF0000"]

    seen_before.refresh_from_db()
    retired.refresh_from_db()
    assert seen_before.last_seen_at is not None
    assert seen_before.last_seen_location_id == location_a.pk
    assert retired.last_seen_at is not None  # ANY status is swept
