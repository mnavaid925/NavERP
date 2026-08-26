"""Procurement 6.9 Catalog Management — security tests.

Covers the four-entity stack's defensive posture: cross-tenant IDOR on every mutating
route (all 404, rows byte-frozen), the authz ladder (anonymous → login redirect,
member vs ``tenant_admin_required`` decision verbs with the exact PermissionDenied
refusal shape), mass-assignment immunity on the hand-rolled forms (status/number/
approver stamps and the write-only punch-out secret are never craftable), secret
non-leakage (never rendered, never in the immutable AuditLog), upload hardening
(extension allowlist, 2 MB wire cap, CSV formula-injection escaping, the 10k staging
ceiling, forced ``pending_approval`` staging), POST-only enforcement on every verb
route, and hostile-querystring survival on all four registers.
"""
import csv
import io
import json
import tempfile
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from apps.core.models import AuditLog
from apps.procurement.forms.CatalogManagement.UploadBatches import MAX_UPLOAD_BYTES
from apps.procurement.models import (
    CatalogItem,
    CatalogPriceTier,
    CatalogUploadBatch,
    PunchOutEndpoint,
)

pytestmark = pytest.mark.django_db

#: Upload tests write real files — keep them out of the repo's media/ tree.
_MEDIA_TMP = tempfile.mkdtemp(prefix="naverp-catalogmgmt-media-")


# ------------------------------------------------------------------ builders/helpers
def _catalogmgmt_party(tenant, name):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _catalogmgmt_item(tenant, **overrides):
    fields = dict(tenant=tenant, source_type="supplier_product",
                  name="Security probe line", supplier_part_no="SEC-1",
                  base_price=Decimal("9.90"), status="draft")
    fields.update(overrides)
    return CatalogItem.objects.create(**fields)


def _catalogmgmt_tier(catalog_item, **overrides):
    fields = dict(tenant=catalog_item.tenant, catalog_item=catalog_item,
                  min_quantity=Decimal("10"), unit_price=Decimal("8.50"),
                  status="active")
    fields.update(overrides)
    return CatalogPriceTier.objects.create(**fields)


def _catalogmgmt_endpoint(tenant, party, **overrides):
    fields = dict(tenant=tenant, party=party, name="Probe punch-out",
                  protocol="cxml", punchout_url="https://probe.example/cxml")
    fields.update(overrides)
    return PunchOutEndpoint.objects.create(**fields)


def _catalogmgmt_upload(tenant, party=None, **overrides):
    fields = dict(tenant=tenant, party=party, original_filename="probe.csv",
                  status="received")
    fields.update(overrides)
    return CatalogUploadBatch.objects.create(**fields)


_catalogmgmt_frozen_fields = {
    "item": ("status", "name", "base_price", "supplier_part_no", "is_preferred",
             "submitted_by_id", "submitted_at", "approved_by_id", "approved_at",
             "rejection_reason"),
    "tier": ("status", "min_quantity", "unit_price", "discount_pct",
             "approved_by_id", "approved_at"),
    "endpoint": ("name", "protocol", "punchout_url", "username", "shared_secret",
                 "enabled", "notes", "last_session_at"),
    "upload": ("status", "notes", "original_filename", "validated_by_id",
               "validated_at", "rows_parsed", "rows_accepted", "rows_rejected",
               "error_log"),
}


def _catalogmgmt_frozen(obj, kind):
    return tuple(getattr(obj, f) for f in _catalogmgmt_frozen_fields[kind])


# ------------------------------------------------------------------ 1. IDOR matrix
def test_catalogmgmt_idor_matrix_tenant_b_routes_404_rows_frozen(
        client_a, tenant_b, catalog_item_b):
    """Every mutating route scoped against a tenant-B row 404s for tenant-A's admin,
    GET or POST alike, and tenant-B rows come out byte-identical."""
    party_b = _catalogmgmt_party(tenant_b, "Globex Punch-out Supplier")
    tier_b = _catalogmgmt_tier(catalog_item_b)
    endpoint_b = _catalogmgmt_endpoint(tenant_b, party_b)
    upload_b = _catalogmgmt_upload(tenant_b, party_b)

    before = {
        "item": _catalogmgmt_frozen(catalog_item_b, "item"),
        "tier": _catalogmgmt_frozen(tier_b, "tier"),
        "endpoint": _catalogmgmt_frozen(endpoint_b, "endpoint"),
        "upload": _catalogmgmt_frozen(upload_b, "upload"),
    }

    i, t, e, u = catalog_item_b.pk, tier_b.pk, endpoint_b.pk, upload_b.pk
    probes = [
        # CatalogItem — GET renders the object (must scope), POST mutates.
        ("GET", "procurement:catalog_item_detail", i),
        ("GET", "procurement:catalog_item_edit", i),
        ("POST", "procurement:catalog_item_edit", i),
        ("POST", "procurement:catalog_item_delete", i),
        ("POST", "procurement:catalog_item_submit", i),
        ("POST", "procurement:catalog_item_approve", i),
        ("POST", "procurement:catalog_item_reject", i),
        ("POST", "procurement:catalog_item_block", i),
        # CatalogPriceTier
        ("GET", "procurement:catalog_tier_detail", t),
        ("GET", "procurement:catalog_tier_edit", t),
        ("POST", "procurement:catalog_tier_edit", t),
        ("POST", "procurement:catalog_tier_delete", t),
        ("POST", "procurement:catalog_tier_approve", t),
        ("POST", "procurement:catalog_tier_retire", t),
        # PunchOutEndpoint
        ("GET", "procurement:punchout_endpoint_detail", e),
        ("GET", "procurement:punchout_endpoint_edit", e),
        ("POST", "procurement:punchout_endpoint_edit", e),
        ("POST", "procurement:punchout_endpoint_delete", e),
        ("POST", "procurement:punchout_endpoint_test", e),
        # CatalogUploadBatch
        ("GET", "procurement:catalog_upload_detail", u),
        ("GET", "procurement:catalog_upload_edit", u),
        ("POST", "procurement:catalog_upload_edit", u),
        ("POST", "procurement:catalog_upload_delete", u),
        ("POST", "procurement:catalog_upload_validate", u),
        ("POST", "procurement:catalog_upload_publish", u),
        ("POST", "procurement:catalog_upload_reject", u),
    ]
    for method, name, pk in probes:
        url = reverse(name, args=[pk])
        if method == "POST":
            resp = client_a.post(url, {"reason": "cross-tenant"})
        else:
            resp = client_a.get(url)
        assert resp.status_code == 404, (method, name)

    for obj, kind in ((catalog_item_b, "item"), (tier_b, "tier"),
                      (endpoint_b, "endpoint"), (upload_b, "upload")):
        obj.refresh_from_db()
        assert _catalogmgmt_frozen(obj, kind) == before[kind], kind


# ------------------------------------------------------------------ 2. authz ladder
def test_catalogmgmt_anonymous_redirects_to_login(db):
    """Unauthenticated requests land on the accounts login for reads AND verb POSTs."""
    anon = Client()
    reads = [
        reverse("procurement:catalog_item_list"),
        reverse("procurement:catalog_item_create"),
        reverse("procurement:catalog_item_detail", args=[1]),
        reverse("procurement:catalog_tier_list"),
        reverse("procurement:punchout_endpoint_list"),
        reverse("procurement:catalog_upload_list"),
    ]
    verbs = [
        reverse("procurement:catalog_item_submit", args=[1]),
        reverse("procurement:catalog_item_approve", args=[1]),
        reverse("procurement:catalog_tier_approve", args=[1]),
        reverse("procurement:catalog_tier_retire", args=[1]),
        reverse("procurement:punchout_endpoint_test", args=[1]),
        reverse("procurement:catalog_upload_validate", args=[1]),
        reverse("procurement:catalog_upload_publish", args=[1]),
    ]
    login_prefix = reverse("accounts:login")
    for url in reads:
        resp = anon.get(url)
        assert resp.status_code == 302, url
        assert resp["Location"].startswith(login_prefix), url
    for url in verbs:
        resp = anon.post(url)
        assert resp.status_code == 302, url
        assert resp["Location"].startswith(login_prefix), url


def test_catalogmgmt_member_denied_on_decision_verbs_refusal_shape(
        member_client, tenant_a, catalog_item_pending_a, catalog_item_approved_a,
        tier_active_a, upload_batch_received_a):
    """Decision verbs are tenant-admin-only post-I2: a plain member gets
    ``tenant_admin_required``'s PermissionDenied → generic 403 page, never a silent
    success, and no row moves."""
    proposed_tier = _catalogmgmt_tier(catalog_item_approved_a, status="draft")
    frozen = {
        catalog_item_pending_a: "item",
        catalog_item_approved_a: "item",
        tier_active_a: "tier",
        proposed_tier: "tier",
        upload_batch_received_a: "upload",
    }
    before = {id(obj): _catalogmgmt_frozen(obj, kind)
              for obj, kind in frozen.items()}

    probes = [
        ("procurement:catalog_item_approve", catalog_item_pending_a),
        ("procurement:catalog_item_reject", catalog_item_pending_a),
        ("procurement:catalog_item_block", catalog_item_approved_a),
        ("procurement:catalog_tier_approve", proposed_tier),
        ("procurement:catalog_tier_retire", tier_active_a),
        ("procurement:catalog_upload_validate", upload_batch_received_a),
        ("procurement:catalog_upload_publish", upload_batch_received_a),
        ("procurement:catalog_upload_reject", upload_batch_received_a),
    ]
    for name, obj in probes:
        resp = member_client.post(reverse(name, args=[obj.pk]))
        assert resp.status_code == 403, name
        # Refusal shape of apps/core/decorators.tenant_admin_required: PermissionDenied
        # through Django's default handler -> the generic 403 page (the exception text
        # itself is never rendered for PermissionDenied), never a success redirect.
        assert "403 Forbidden" in resp.content.decode(), name

    for obj, kind in frozen.items():
        obj.refresh_from_db()
        assert _catalogmgmt_frozen(obj, kind) == before[id(obj)], (kind, obj.pk)


# ------------------------------------------------------------------ 3. mass assignment
def test_catalogmgmt_item_create_mass_assignment_ignored(client_a, tenant_a,
                                                         admin_user):
    """status/number/approver/timestamps are NOT form fields — a crafted POST cannot
    mint an approved, pre-numbered catalog entry."""
    resp = client_a.post(reverse("procurement:catalog_item_create"), {
        "source_type": "supplier_product",
        "name": "Forged instant-approved entry",
        "base_price": "9.90",
        "status": "approved",
        "number": "PCI-99999",
        "approved_by": str(admin_user.pk),
        "submitted_by": str(admin_user.pk),
        "submitted_at": "2026-01-01 10:00",
        "approved_at": "2026-01-01 10:00",
    })
    assert resp.status_code == 302
    obj = CatalogItem.objects.filter(tenant=tenant_a).latest("id")
    assert obj.status == "draft"                       # server-side lifecycle only
    assert obj.number != "PCI-99999"                   # numbering is server-minted
    assert obj.number.startswith("PCI-")
    assert obj.approved_by_id is None
    assert obj.submitted_by_id is None
    assert obj.submitted_at is None and obj.approved_at is None


def test_catalogmgmt_item_edit_mass_assignment_ignored(client_a, tenant_a,
                                                       admin_user):
    """Same crafted fields against EDIT — the row keeps its server-side workflow state."""
    obj = _catalogmgmt_item(tenant_a, status="draft")
    resp = client_a.post(reverse("procurement:catalog_item_edit", args=[obj.pk]), {
        "source_type": "supplier_product",
        "name": "Renamed legitimately",
        "base_price": "9.90",
        "status": "blocked",
        "number": "PCI-88888",
        "approved_by": str(admin_user.pk),
        "approved_at": "2026-01-01 10:00",
    })
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.name == "Renamed legitimately"          # real form field went through
    assert obj.status == "draft"
    assert obj.number != "PCI-88888"
    assert obj.approved_by_id is None and obj.approved_at is None


@override_settings(MEDIA_ROOT=_MEDIA_TMP)
def test_catalogmgmt_endpoint_shared_secret_craft_via_edit_ignored(
        client_a, tenant_a, supplier_a):
    """Fix M-form pops ``shared_secret`` off the EDIT form — posting one back must
    never touch the stored value."""
    _, party = supplier_a
    endpoint = _catalogmgmt_endpoint(tenant_a, party,
                                     shared_secret="REAL-SECRET-do-not-rotate")
    resp = client_a.post(reverse("procurement:punchout_endpoint_edit",
                                 args=[endpoint.pk]), {
        "party": str(party.pk),
        "name": endpoint.name,
        "protocol": "cxml",
        "punchout_url": endpoint.punchout_url,
        "username": "svc-buyer",
        "shared_secret": "EVIL-INJECTED-SECRET",
        "enabled": "on",
        "notes": "attempted rotation",
    })
    assert resp.status_code == 302
    endpoint.refresh_from_db()
    assert endpoint.shared_secret == "REAL-SECRET-do-not-rotate"


# ------------------------------------------------------------------ 4. secret leakage
def test_catalogmgmt_endpoint_secret_never_rendered(client_a, tenant_a, supplier_a):
    """No page of the stack ever echoes the persisted secret; the detail page shows the
    fixed bullet placeholder instead."""
    _, party = supplier_a
    secret = "Hunt3r2-S3cr3t!"
    endpoint = _catalogmgmt_endpoint(tenant_a, party, shared_secret=secret)

    pages = [
        reverse("procurement:punchout_endpoint_list"),
        reverse("procurement:punchout_endpoint_create"),
        reverse("procurement:punchout_endpoint_detail", args=[endpoint.pk]),
        reverse("procurement:punchout_endpoint_edit", args=[endpoint.pk]),
    ]
    for url in pages:
        resp = client_a.get(url)
        assert resp.status_code == 200, url
        assert secret not in resp.content.decode(), url
    detail_html = client_a.get(pages[2]).content.decode()
    assert "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" in detail_html  # ••••••••


def test_catalogmgmt_endpoint_audit_trail_excludes_secret(client_a, tenant_a,
                                                          supplier_a):
    """An admin EDIT changing only notes must leave NO trace of the secret in the
    immutable AuditLog — neither its value nor a 'shared_secret' plaintext entry
    (M13 belt-and-braces: redaction marker OR outright absence both pass)."""
    _, party = supplier_a
    secret = "S3cr3t-Hunt3r2!"
    endpoint = _catalogmgmt_endpoint(tenant_a, party, shared_secret=secret)

    resp = client_a.post(reverse("procurement:punchout_endpoint_edit",
                                 args=[endpoint.pk]), {
        "party": str(party.pk),
        "name": endpoint.name,
        "protocol": "cxml",
        "punchout_url": endpoint.punchout_url,
        "username": "",
        "enabled": "on",
        "notes": "note changed, nothing else",
    })
    assert resp.status_code == 302
    endpoint.refresh_from_db()
    assert endpoint.shared_secret == secret

    ct = ContentType.objects.get_for_model(PunchOutEndpoint)
    logs = AuditLog.objects.filter(content_type=ct, object_id=endpoint.pk)
    assert logs.exists()
    for log in logs:
        serialized = json.dumps(log.changes, default=str)
        assert secret not in serialized                       # value never logged
        if "shared_secret" in serialized:
            # Belt-and-braces branch: if the key appears at all it MUST be redacted.
            assert log.changes.get("shared_secret") == "***redacted***"
    latest = logs.latest("id")
    assert latest.action == "update"
    assert "shared_secret" not in latest.changes              # skipped, not copied


# ------------------------------------------------------------------ 5. upload hardening
@override_settings(MEDIA_ROOT=_MEDIA_TMP)
def test_catalogmgmt_upload_exe_refused(client_a, tenant_a, supplier_a):
    _, party = supplier_a
    before = CatalogUploadBatch.objects.filter(tenant=tenant_a).count()
    upload = SimpleUploadedFile("payload.exe", b"MZ\x90\x00definitely-not-a-csv")
    resp = client_a.post(reverse("procurement:catalog_upload_create"),
                         {"party": str(party.pk), "notes": "", "file": upload})
    assert resp.status_code == 200                      # re-rendered with errors
    assert "file" in resp.context["form"].errors
    assert CatalogUploadBatch.objects.filter(tenant=tenant_a).count() == before


@override_settings(MEDIA_ROOT=_MEDIA_TMP)
def test_catalogmgmt_upload_oversize_refused(client_a, tenant_a, supplier_a):
    """Just past the forms-module cap constant (forms/UploadBatches.py) → refused."""
    _, party = supplier_a
    before = CatalogUploadBatch.objects.filter(tenant=tenant_a).count()
    blob = b"a" * (MAX_UPLOAD_BYTES + 1)
    assert len(blob) > MAX_UPLOAD_BYTES
    upload = SimpleUploadedFile("big-but-named-csv.csv", blob)
    resp = client_a.post(reverse("procurement:catalog_upload_create"),
                         {"party": str(party.pk), "notes": "", "file": upload})
    assert resp.status_code == 200
    assert "file" in resp.context["form"].errors
    assert CatalogUploadBatch.objects.filter(tenant=tenant_a).count() == before


@override_settings(MEDIA_ROOT=_MEDIA_TMP)
def test_catalogmgmt_upload_formula_cells_escaped_or_rejected_staging_gate(
        client_a, tenant_a, supplier_a):
    """CSV-injection cells: TEXT cells stage ESCAPED (apostrophe-prefixed, never raw),
    identifier cells are rejected outright, and EVERY staged item lands
    ``pending_approval`` regardless of how hostile its content was (bullet-3 gate)."""
    _, party = supplier_a
    raw_name = "=cmd|' /C calc'!A0"

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "supplier_part_no", "unit_price", "uom_code",
                     "category_text"])
    writer.writerow([raw_name, "NW-F1", "10.00", "", "Safety wear"])
    writer.writerow(["Safe Widget", '=HYPERLINK("http://evil.example","pwn")',
                     "5.00", "", ""])
    writer.writerow(["+SUM(A1:A9)", "NW-F3", "7.25", "", "+recalc"])

    batch = CatalogUploadBatch(tenant=tenant_a, party=party)
    batch.file = ContentFile(buf.getvalue().encode("utf-8"), name="evil.csv")
    batch.save()

    resp = client_a.post(reverse("procurement:catalog_upload_validate",
                                 args=[batch.pk]))
    assert resp.status_code == 302
    batch.refresh_from_db()
    assert batch.status == "validated"
    assert batch.rows_parsed == 3
    assert batch.rows_accepted == 2
    assert batch.rows_rejected == 1
    assert "row 2:" in batch.error_log                 # the formula part-number row

    staged = CatalogItem.objects.filter(tenant=tenant_a, supplier=party,
                                        source_type="supplier_product")
    assert staged.count() == 2
    for item in staged:
        # Bullet-3 gate: malicious content NEVER stages as approvable.
        assert item.status == "pending_approval"
        assert item.name[:1] not in ("=", "+", "-", "@", "\t")
        assert item.category_text[:1] not in ("=", "+", "-", "@", "\t")
    names = [item.name for item in staged]
    assert raw_name not in names                       # never staged RAW
    assert any(name.startswith("'") for name in names)  # …only ESCAPED


@override_settings(MEDIA_ROOT=_MEDIA_TMP)
def test_catalogmgmt_upload_row_limit_refuses_cleanly(client_a, tenant_a,
                                                      supplier_a):
    """A synthetic file just past CatalogUploadBatch.MAX_DATA_ROWS refuses cleanly:
    batch stays received, counters stay zero, NOTHING stages, and the refusal is
    recorded on the detail page."""
    _, party = supplier_a
    header = "name,supplier_part_no,unit_price,uom_code,category_text\n"
    body = "".join(f"Row item {i},P-{i},{i % 500}.50,,Bulk\n"
                   for i in range(1, CatalogUploadBatch.MAX_DATA_ROWS + 2))
    assert body.count("\n") == CatalogUploadBatch.MAX_DATA_ROWS + 1

    batch = CatalogUploadBatch(tenant=tenant_a, party=party)
    batch.file = ContentFile((header + body).encode("utf-8"), name="flood.csv")
    batch.save()

    staged_before = CatalogItem.objects.filter(
        tenant=tenant_a, source_type="supplier_product").count()

    resp = client_a.post(reverse("procurement:catalog_upload_validate",
                                 args=[batch.pk]))
    assert resp.status_code == 302
    batch.refresh_from_db()
    assert batch.status == "received"                  # clean refusal, not validated
    assert batch.rows_parsed == 0
    assert batch.rows_accepted == 0
    assert batch.rows_rejected == 0
    assert CatalogItem.objects.filter(
        tenant=tenant_a, source_type="supplier_product").count() == staged_before

    followed = client_a.get(resp["Location"])          # refusal recorded for the buyer
    assert followed.status_code == 200
    assert "data-row limit" in followed.content.decode()


# ------------------------------------------------------------------ 6. POST-only surface
def test_catalogmgmt_get_on_verb_routes_never_mutates(
        client_a, catalog_item_pending_a, catalog_item_approved_a,
        catalog_item_blocked_a, tier_active_a, punchout_endpoint_a,
        upload_batch_received_a):
    """GET against every state-changing route is refused (405 from require_POST) and
    leaves every row exactly as it was."""
    frozen = {
        catalog_item_pending_a: "item",
        catalog_item_approved_a: "item",
        catalog_item_blocked_a: "item",
        tier_active_a: "tier",
        punchout_endpoint_a: "endpoint",
        upload_batch_received_a: "upload",
    }
    before = {id(obj): _catalogmgmt_frozen(obj, kind) for obj, kind in frozen.items()}
    counts = {m: m.objects.count() for m in
              (CatalogItem, CatalogPriceTier, PunchOutEndpoint, CatalogUploadBatch)}

    probes = [
        ("procurement:catalog_item_delete", catalog_item_pending_a),
        ("procurement:catalog_item_submit", catalog_item_blocked_a),
        ("procurement:catalog_item_approve", catalog_item_blocked_a),
        ("procurement:catalog_item_reject", catalog_item_blocked_a),
        ("procurement:catalog_item_block", catalog_item_pending_a),
        ("procurement:catalog_tier_delete", tier_active_a),
        ("procurement:catalog_tier_approve", tier_active_a),
        ("procurement:catalog_tier_retire", tier_active_a),
        ("procurement:punchout_endpoint_delete", punchout_endpoint_a),
        ("procurement:punchout_endpoint_test", punchout_endpoint_a),
        ("procurement:catalog_upload_delete", upload_batch_received_a),
        ("procurement:catalog_upload_validate", upload_batch_received_a),
        ("procurement:catalog_upload_publish", upload_batch_received_a),
        ("procurement:catalog_upload_reject", upload_batch_received_a),
    ]
    for name, obj in probes:
        resp = client_a.get(reverse(name, args=[obj.pk]))
        assert resp.status_code in (400, 403, 405), name   # never a mutating 200/302

    for obj, kind in frozen.items():
        obj.refresh_from_db()
        assert _catalogmgmt_frozen(obj, kind) == before[id(obj)], (kind, obj.pk)
    for m, n in counts.items():
        assert m.objects.count() == n


# ------------------------------------------------------------------ 7. injection smoke
def test_catalogmgmt_injection_smoke_registers_survive_hostile_querystrings(
        client_a):
    """SQL metacharacters in q, a unicode-superscript FK filter, and page junk hit all
    four registers: 200/404, never 500 — and the tables still exist afterwards."""
    lists = [
        ("procurement:catalog_item_list", "supplier"),
        ("procurement:catalog_tier_list", "catalog_item"),
        ("procurement:punchout_endpoint_list", "protocol"),
        ("procurement:catalog_upload_list", "party"),
    ]
    hostile_sets = [
        {"q": "'; DROP TABLE procurement_procmementocatalogitem;--"},
        {"q": "'; DELETE FROM users WHERE '1'='1"},
    ]
    for _, filter_param in lists:
        hostile_sets.append({filter_param: "\u00b2"})               # superscript ²
        hostile_sets.append({"page": "-1"})
        hostile_sets.append({"page": "abc"})
        hostile_sets.append({"page": "999999999999999999999"})

    for name, _ in lists:
        url = reverse(name)
        for params in hostile_sets:
            resp = client_a.get(url, params)
            assert resp.status_code in (200, 404), (name, params)
            assert resp.status_code < 500, (name, params)

    # The DROP TABLE above was a string, not an execution: every register still serves.
    for name, _ in lists:
        assert client_a.get(reverse(name)).status_code == 200, name
