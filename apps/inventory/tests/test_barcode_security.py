"""Inventory 5.14 Barcode & RFID Integration — multi-tenancy IDOR & security.

Adversarial coverage around all THREE 5.14 entities: cross-tenant IDOR on every read and
write shape (detail/edit GETs, render, print/void/delete/lifecycle POSTs — every probe must
answer 404 and leave the foreign row byte-identical), the member/admin gate (writes are
tenant-admin-only for labels and tags while the scan console and session creation stay
open to every signed-in member), and junk-input hardening (attacker-controlled query
values and an out-of-range copies count must degrade to validation/blank filters, never a
500).
"""
import pytest

from apps.inventory.models import BarcodeLabel, RfidTag, ScanSession

pytestmark = pytest.mark.django_db


# ---- IDOR: cross-tenant reads -----------------------------------------------------------------------


def test_barcode_labels_cross_tenant_reads_404(client_a, barcode_label_b):
    """A foreign label pk must read as nonexistent to Acme's admin — detail, edit page
    AND the inline SVG render alike."""
    for suffix in ["", "edit/", "render/"]:
        url = f"/inventory/labels/{barcode_label_b.pk}/{suffix}"
        assert client_a.get(url).status_code == 404


def test_barcode_sessions_cross_tenant_reads_and_close_404(client_a, tenant_b):
    """A Globex session is invisible to Acme: reads 404 and the close/delete POSTs refuse,
    leaving the session open and intact."""
    foreign = ScanSession.objects.create(
        tenant=tenant_b, device_label="Globex handheld", mode="single")
    assert client_a.get(f"/inventory/sessions/{foreign.pk}/").status_code == 404
    assert client_a.get(f"/inventory/sessions/{foreign.pk}/edit/").status_code == 404
    assert client_a.post(f"/inventory/sessions/{foreign.pk}/close/").status_code == 404
    assert client_a.post(f"/inventory/sessions/{foreign.pk}/delete/").status_code == 404

    foreign.refresh_from_db()
    assert foreign.status == "open"
    assert foreign.ended_at is None


def test_barcode_tags_cross_tenant_reads_and_lifecycle_404(client_a, rfid_tag_b):
    """Every read shape and every lifecycle POST against Globex's tag answers 404; the
    tag stays unassigned with its EPC untouched."""
    assert client_a.get(f"/inventory/tags/{rfid_tag_b.pk}/").status_code == 404
    assert client_a.get(f"/inventory/tags/{rfid_tag_b.pk}/edit/").status_code == 404
    for verb in ["activate", "retire", "mark-lost", "delete"]:
        assert client_a.post(
            f"/inventory/tags/{rfid_tag_b.pk}/{verb}/").status_code == 404

    rfid_tag_b.refresh_from_db()
    assert rfid_tag_b.status == "unassigned"
    assert rfid_tag_b.epc == "E280-689E-0000-000B"


# ---- IDOR: cross-tenant writes ----------------------------------------------------------------------


def test_barcode_labels_cross_tenant_writes_404_and_leave_row_intact(
        client_a, barcode_label_b):
    """The write shapes are where IDOR damage happens: print/void/delete POSTs against
    Globex's draft must 404 and leave it a live, unprinted draft."""
    assert client_a.post(
        f"/inventory/labels/{barcode_label_b.pk}/print/").status_code == 404
    assert client_a.post(
        f"/inventory/labels/{barcode_label_b.pk}/void/").status_code == 404
    assert client_a.post(
        f"/inventory/labels/{barcode_label_b.pk}/delete/").status_code == 404

    barcode_label_b.refresh_from_db()  # raises if deleted
    assert barcode_label_b.status == "draft"
    assert barcode_label_b.printed_at is None


# ---- role gate ----------------------------------------------------------------------------------------


def test_barcode_member_client_gets_403_on_writes_but_console_stays_open(
        member_client, barcode_label_a, rfid_tag_active_a):
    """Labels and tags are admin-gated writes (403 for a plain member) — but scanning is
    everyone's job: the console and session creation answer 200. The probes move nothing."""
    assert member_client.get("/inventory/labels/add/").status_code == 403
    assert member_client.get(
        f"/inventory/labels/{barcode_label_a.pk}/edit/").status_code == 403
    assert member_client.post(
        f"/inventory/labels/{barcode_label_a.pk}/delete/").status_code == 403
    assert member_client.post(
        f"/inventory/labels/{barcode_label_a.pk}/print/").status_code == 403

    assert member_client.get("/inventory/tags/add/").status_code == 403
    assert member_client.post(
        f"/inventory/tags/{rfid_tag_active_a.pk}/delete/").status_code == 403

    assert member_client.get("/inventory/console/").status_code == 200
    assert member_client.get("/inventory/sessions/add/").status_code == 200

    barcode_label_a.refresh_from_db()
    assert barcode_label_a.status == "draft"
    rfid_tag_active_a.refresh_from_db()
    assert rfid_tag_active_a.status == "active"


# ---- junk input hardening -----------------------------------------------------------------------------


def test_barcode_junk_query_params_never_500(client_a, barcode_label_a):
    """Attacker-controlled filter/mode values fall back to sane defaults instead of
    crashing or echoing into the page as markup."""
    probes = [
        ("/inventory/labels/", {"status": "<script>alert(1)</script>", "q": "'--"}),
        ("/inventory/labels/", {"label_kind": "zzz"}),
        ("/inventory/sessions/", {"status": "<script>alert(1)</script>"}),
        ("/inventory/console/", {"mode": "zzz"}),
        ("/inventory/tags/", {"status": "zzz", "kind": "<script>"}),
    ]
    for url, params in probes:
        response = client_a.get(url, data=params)
        assert response.status_code == 200, (url, params)
        assert b"alert(1)" not in response.content


def test_barcode_huge_copies_post_is_validation_refused_not_500(client_a, tenant_a,
                                                                item_a):
    """copies=100000 through the create form dies at the model's MaxValueValidator(500)
    as a re-rendered form error — no 500, and no label row survives the probe."""
    response = client_a.post("/inventory/labels/add/", data={
        "label_kind": "product",
        "target_type": "item",
        "item": str(item_a.pk),
        "location": "",
        "lot_serial": "",
        "target_ref": "",
        "pallet_ref": "",
        "symbology": "code128",
        "payload": "",
        "copies": "100000",
        "notes": "",
    })
    assert response.status_code == 200  # form re-rendered with errors
    # Scope the probe to THIS submission — a shared dev DB legitimately carries other labels.
    assert not BarcodeLabel.objects.filter(tenant=tenant_a, item=item_a,
                                           symbology="code128", notes="").exists()
