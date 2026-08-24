"""Inventory 5.14 Barcode & RFID Integration — view behaviour through real HTTP.

Exercises the primary UX end to end: the label register/detail plus the inline SVG render
route (code128 AND qr symbologies, voided labels 404 instead of rendering), the handheld
scan console (GET page + POST paste-run that resolves ok AND unknown codes into immutable
events), the session close verb, and the RFID lifecycle POSTs flipping statuses server-side.
Security lanes live in test_barcode_security.py.
"""
import pytest

from apps.inventory.models import BarcodeLabel, RfidTag

pytestmark = pytest.mark.django_db


def _unassigned_tag_with_target(tenant_a, item_a):
    """An activate-ready tag: unassigned status but anchored to an item."""
    return RfidTag.objects.create(
        tenant=tenant_a, epc="E280689E000000EE", kind="passive", item=item_a)


# ---- BarcodeLabel pages -----------------------------------------------------------------------------


def test_barcode_label_list_renders_the_seeded_number(client_a, barcode_label_a,
                                                      item_a):
    """The register shows this workspace's label — number and derived payload both up."""
    response = client_a.get("/inventory/labels/")
    assert response.status_code == 200
    html = response.content.decode()
    assert barcode_label_a.number in html
    assert item_a.sku in html


def test_barcode_label_detail_shows_number_and_live_render_url(client_a, barcode_label_a):
    """The detail card carries the LBL- number and the inline preview <img> pointing at
    this label's render route."""
    url = f"/inventory/labels/{barcode_label_a.pk}/render/"
    response = client_a.get(f"/inventory/labels/{barcode_label_a.pk}/")
    assert response.status_code == 200
    html = response.content.decode()
    assert barcode_label_a.number in html
    assert url in html


def test_barcode_label_render_serves_svg_for_code128_and_qr(client_a, tenant_a, item_a,
                                                            barcode_label_a):
    """Both renderable families answer image/svg+xml with real SVG markup: a code128
    linear barcode and a QR license-plate label alike."""
    response = client_a.get(f"/inventory/labels/{barcode_label_a.pk}/render/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/svg+xml"
    assert b"<svg" in response.content

    qr = BarcodeLabel.objects.create(
        tenant=tenant_a, target_type="free", target_ref="PALLET-QR-1", symbology="qr")
    qr_response = client_a.get(f"/inventory/labels/{qr.pk}/render/")
    assert qr_response.status_code == 200
    assert qr_response["Content-Type"] == "image/svg+xml"
    assert b"<svg" in qr_response.content


def test_barcode_label_render_404s_once_voided(client_a, tenant_a, item_a):
    """A voided label is pulled out of circulation — the render endpoint answers 404 so no
    stale symbol keeps circulating on scanned paperwork."""
    label = BarcodeLabel.objects.create(tenant=tenant_a, target_type="item", item=item_a)
    label.status = "void"
    label.save(update_fields=["status", "updated_at"])

    assert client_a.get(f"/inventory/labels/{label.pk}/render/").status_code == 404


# ---- Scan console / sessions ------------------------------------------------------------------------


def test_barcode_console_get_renders_and_post_records_ok_and_unknown_events(
        client_a, scan_session_open_a):
    """The handheld surface renders for GET; a batch POST resolves pasted codes against
    the spine — known codes land as resolved-ok events, unknown ones are RECORDED as
    unknown rather than dropped."""
    page = client_a.get("/inventory/console/")
    assert page.status_code == 200
    assert "Scan Console" in page.content.decode()

    response = client_a.post(
        "/inventory/console/",
        data={"session": str(scan_session_open_a.pk),
              "codes": "CAT-1\nDOCK-1\nGHOST-ZZZ\n"},
    )
    assert response.status_code == 302

    events = list(scan_session_open_a.events.order_by("id"))
    assert [e.raw_code for e in events] == ["CAT-1", "DOCK-1", "GHOST-ZZZ"]
    by_code = {e.raw_code: e for e in events}
    assert by_code["CAT-1"].ok is True
    assert by_code["CAT-1"].resolved_kind == "item"
    assert by_code["DOCK-1"].ok is True
    assert by_code["DOCK-1"].resolved_kind == "location"
    assert by_code["GHOST-ZZZ"].ok is False
    assert by_code["GHOST-ZZZ"].resolved_kind == "unknown"


def test_barcode_scansession_close_post_freezes_the_session(client_a, scan_session_open_a):
    """POST close stamps ended_at and freezes the session; re-closing is flash-refused
    back on the detail page without touching the original stamp."""
    first = client_a.post(f"/inventory/sessions/{scan_session_open_a.pk}/close/")
    assert first.status_code == 302

    scan_session_open_a.refresh_from_db()
    assert scan_session_open_a.status == "closed"
    assert scan_session_open_a.ended_at is not None
    stamp = scan_session_open_a.ended_at

    second = client_a.post(f"/inventory/sessions/{scan_session_open_a.pk}/close/",
                           follow=True)
    assert second.status_code == 200
    scan_session_open_a.refresh_from_db()
    assert scan_session_open_a.ended_at == stamp


# ---- RFID lifecycle ----------------------------------------------------------------------------------


def test_barcode_tag_lifecycle_posts_flip_statuses(client_a, tenant_a, item_a,
                                                   rfid_tag_active_a):
    """The verb buttons' POSTs are the real state machine: activate flips unassigned→
    active, mark-lost only from active, retire takes active→retired."""
    fresh = _unassigned_tag_with_target(tenant_a, item_a)

    assert client_a.post(f"/inventory/tags/{fresh.pk}/activate/").status_code == 302
    fresh.refresh_from_db()
    assert fresh.status == "active"

    assert client_a.post(f"/inventory/tags/{rfid_tag_active_a.pk}/retire/").status_code == 302
    rfid_tag_active_a.refresh_from_db()
    assert rfid_tag_active_a.status == "retired"

    assert client_a.post(f"/inventory/tags/{fresh.pk}/mark-lost/").status_code == 302
    fresh.refresh_from_db()
    assert fresh.status == "lost"
