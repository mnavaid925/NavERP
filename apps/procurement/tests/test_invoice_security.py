"""Procurement 6.13 Invoice & Voucher Management — isolation & hardening tests.

The defensive half of the 6.13 suite. Every test here asks the same question from a different
angle: *can a caller reach a row, a field or a state transition the product never meant to give
them — and does a hand-edited URL or POST ever reach a 500 instead of a message?*

Laid out in seven sections:

1. **Cross-tenant IDOR** — every pk-scoped 6.13 route (invoice, line, variance, dispute) aimed at
   another workspace's pk returns **404**, and every tenant-B row comes back byte-identical.
   No invoice is matched, submitted, approved, voided or deleted out of another workspace's data.
2. **Register & board isolation** — none of the four registers and none of the five boards ever
   renders another workspace's rows, and the tenant-less superuser is refused (or 404'd) rather
   than shown everybody's payables.
3. **The authz ladder** — anonymous bounces to ``/login/``; a plain member is refused on the
   eleven ``@tenant_admin_required`` routes and *allowed* on the seven the module deliberately
   keeps member-reachable (match / submit / schedule / line delete / variance accept / the two
   await verbs); CSRF is enforced on every POST; a GET on a ``@require_POST`` verb is 405 and
   mutates nothing.
4. **Mass assignment** — the crafted-POST surface: another workspace's pk in every FK field on
   all three write forms and on the inline line formset, the same-tenant WRONG-VENDOR case, and a
   forged ``tenant`` / ``number`` / ``status`` / ``total`` / ``match_status`` / ``source`` /
   ``supplier`` / ``line_total`` / ``matched_qty`` block that must be ignored wholesale.
5. **Hostile input** — junk FK filter params, junk enum params, the ``gl_missing`` truth-value
   fall-through, page junk and page 2 on every paginated surface, the ``?weeks`` clamp, the
   crafted capture ``stage``, and the decimal family (``NaN`` / ``Infinity`` / garbage / negative
   / over-``max_digits``) on ``fx_rate``, ``disputed_amount``, ``quantity`` and ``unit_price``
   (L11 / L35).
6. **Absent prerequisites are REJECTED, never fallen through** (L35) — no resolution, no
   settlement; no chart of accounts, no posting (and no half-written Bill either); no open
   variance, no dispute; no ``?invoice``, no orphan line; a settled variance cannot be re-accepted
   and a posted invoice cannot be deleted or voided.
7. **N+1** — the four registers, the match board and the invoice detail page hold their query
   count as rows are added.

Every negative case is paired with the POSITIVE path proving the guard did not simply break the
feature (L44). All dates derive from ``timezone.localdate()`` (never ``date.today()``) so nothing
here flakes in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.procurement.forms import CaptureUploadForm
from apps.procurement.models import (
    InvoiceDispute,
    InvoiceMatchVariance,
    SupplierInvoice,
    SupplierInvoiceLine,
)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers (module-private)
def _invoice_iso(offset_days=0):
    """A date string relative to TODAY as the CODE sees it — ``timezone.localdate()`` (L16)."""
    return (timezone.localdate() + datetime.timedelta(days=offset_days)).isoformat()


def _invoice_header_payload(**overrides):
    """A complete ``SupplierInvoiceForm`` POST body.

    ``vendor`` is the one non-nullable FK and ``discount_grace_days`` has a model default but no
    ``blank=True``, so both are always posted; every crafted-FK case below flips exactly one key.
    """
    payload = {
        "vendor": "",
        "purchase_order": "",
        "goods_receipt": "",
        "payment_term": "",
        "currency": "",
        "tax_code": "",
        "invoice_type": "standard",
        "invoice_number": "SUP-CRAFTED-1",
        "external_ref": "",
        "invoice_date": _invoice_iso(),
        "posting_date": "",
        "discount_base": "net_of_tax",
        "discount_grace_days": "0",
        "fx_rate": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _invoice_formset_payload(line=None):
    """The inline line formset's POST keys.

    The prefix is ``lines`` (the child FK's ``related_name``), and the default is an EMPTY
    formset — ``TOTAL_FORMS=0`` — so a header-only case cannot fail on a half-filled extra row.
    Pass ``line={...}`` to bind one row.
    """
    payload = {
        "lines-TOTAL_FORMS": "0",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }
    if line is not None:
        payload["lines-TOTAL_FORMS"] = "1"
        row = {
            "lines-0-id": "",
            "lines-0-po_line": "",
            "lines-0-receipt_line": "",
            "lines-0-item": "",
            "lines-0-description": "Crafted formset line",
            "lines-0-sku_hint": "",
            "lines-0-uom_hint": "",
            "lines-0-quantity": "1",
            "lines-0-unit_price": "10.00",
            "lines-0-tax_rate_pct": "0",
            "lines-0-gl_account": "",
            "lines-0-tax_code": "",
        }
        row.update({f"lines-0-{key}": value for key, value in line.items()})
        payload.update(row)
    return payload


def _invoice_line_payload(**overrides):
    """A complete standalone ``SupplierInvoiceLineForm`` POST body.

    ``gl_account`` is not optional here: every fixture header carries ``match_basis="none"``, and
    the model refuses a non-PO line that does not name the account it posts to.
    """
    payload = {
        "po_line": "",
        "receipt_line": "",
        "item": "",
        "description": "Crafted line",
        "sku_hint": "",
        "uom_hint": "",
        "quantity": "2",
        "unit_price": "10.00",
        "tax_rate_pct": "0",
        "gl_account": "",
        "tax_code": "",
    }
    payload.update(overrides)
    return payload


def _invoice_dispute_payload(**overrides):
    """A complete ``InvoiceDisputeForm`` POST body — ``invoice`` is the caller's."""
    payload = {
        "invoice": "",
        "invoice_line": "",
        "reason_code": "price",
        "supplier_contact": "",
        "disputed_amount": "10.00",
        "description": "Crafted dispute.",
        "assigned_to": "",
        "due_date": "",
    }
    payload.update(overrides)
    return payload


def _invoice_state(obj):
    """Every column a crafted request might move on an invoice header — the freeze probe."""
    obj.refresh_from_db()
    return (obj.tenant_id, obj.number, obj.status, obj.invoice_type, obj.invoice_number,
            obj.invoice_number_norm, obj.external_ref, obj.vendor_id, obj.purchase_order_id,
            obj.goods_receipt_id, obj.payment_term_id, obj.currency_id, obj.tax_code_id,
            obj.invoice_date, obj.posting_date, obj.due_date, obj.discount_date,
            obj.discount_expiry_date, obj.discount_base, obj.discount_grace_days,
            obj.subtotal, obj.tax_total, obj.total, obj.amount_paid, obj.fx_rate,
            obj.match_basis, obj.match_status, obj.match_notes, obj.source,
            obj.extraction_confidence, obj.notes, obj.bill_id, obj.journal_entry_id,
            obj.duplicate_of_id, obj.approved_by_id, obj.approved_at)


def _invoice_line_state(obj):
    obj.refresh_from_db()
    return (obj.invoice_id, obj.po_line_id, obj.receipt_line_id, obj.item_id, obj.gl_account_id,
            obj.tax_code_id, obj.description, obj.sku_hint, obj.uom_hint, obj.quantity,
            obj.unit_price, obj.tax_rate_pct, obj.line_total, obj.matched_qty)


def _invoice_variance_state(obj):
    obj.refresh_from_db()
    return (obj.tenant_id, obj.invoice_id, obj.invoice_line_id, obj.dispute_id,
            obj.variance_type, obj.basis, obj.expected_value, obj.actual_value,
            obj.variance_abs, obj.variance_pct, obj.tolerance_abs_applied,
            obj.tolerance_pct_applied, obj.outcome, obj.resolution, obj.message,
            obj.detected_at)


def _invoice_dispute_state(obj):
    obj.refresh_from_db()
    return (obj.tenant_id, obj.number, obj.invoice_id, obj.invoice_line_id, obj.supplier_id,
            obj.reason_code, obj.status, obj.disputed_amount, obj.description,
            obj.supplier_contact, obj.assigned_to_id, obj.due_date, obj.raised_by_id,
            obj.raised_at, obj.resolved_at, obj.resolution, obj.resolution_note,
            obj.credit_memo_invoice_id)


def _invoice_counts():
    """Row counts of every table 6.13 can write — the "nothing was created" probe.

    ``Bill`` and ``JournalEntry`` are in here because ``approve()`` is the module's only ledger
    writer: a refused approval that still minted half a posting is the bug this catches.
    """
    from apps.accounting.models import Bill, JournalEntry
    return {
        "invoices": SupplierInvoice.objects.count(),
        "lines": SupplierInvoiceLine.objects.count(),
        "variances": InvoiceMatchVariance.objects.count(),
        "disputes": InvoiceDispute.objects.count(),
        "bills": Bill.objects.count(),
        "entries": JournalEntry.objects.count(),
    }


#: Every 6.13 page that RENDERS and needs no pk. ``supplierinvoiceline_create`` is deliberately
#: absent — it REQUIRES ``?invoice=`` and redirects without one, which is its own test below.
_INVOICE_PAGE_ROUTES = (
    "procurement:invoicevoucher_dashboard",
    "procurement:supplierinvoice_list",
    "procurement:supplierinvoice_create",
    "procurement:supplierinvoice_duplicates",
    "procurement:supplierinvoice_capture",
    "procurement:supplierinvoiceline_list",
    "procurement:paymentschedule_list",
    "procurement:matchvariance_list",
    "procurement:invoice_match_board",
    "procurement:invoicedispute_list",
    "procurement:invoicedispute_create",
    "procurement:invoicedispute_aging",
)

#: Every 6.13 page that RENDERS off a pk: (url name, fixture kind).
_INVOICE_PK_GET_ROUTES = (
    ("procurement:supplierinvoice_detail", "invoice"),
    ("procurement:supplierinvoice_edit", "invoice"),
    ("procurement:supplierinvoiceline_detail", "line"),
    ("procurement:supplierinvoiceline_edit", "line"),
    ("procurement:matchvariance_detail", "variance"),
    # NOT @require_POST — its GET is the accept confirmation page, a legitimate 200.
    ("procurement:matchvariance_accept", "variance"),
    ("procurement:invoicedispute_detail", "dispute"),
    ("procurement:invoicedispute_edit", "dispute"),
)

#: Every POST-only verb that takes a pk, with a body that would otherwise succeed.
#: ``invoicedispute_resolve`` MUST carry a valid ``resolution`` — an invalid one is refused before
#: the row is ever looked up, which would mask the 404 this table is here to prove.
_INVOICE_VERB_ROUTES = (
    ("procurement:supplierinvoice_delete", "invoice", {}),
    ("procurement:supplierinvoice_match", "invoice", {}),
    ("procurement:supplierinvoice_submit", "invoice", {}),
    ("procurement:supplierinvoice_approve", "invoice", {}),
    ("procurement:supplierinvoice_override", "invoice", {}),
    ("procurement:supplierinvoice_void", "invoice", {"reason": "crafted"}),
    ("procurement:supplierinvoice_reverse", "invoice", {}),
    ("procurement:supplierinvoice_schedule", "invoice", {}),
    ("procurement:supplierinvoice_mark_paid", "invoice", {}),
    ("procurement:supplierinvoiceline_delete", "line", {}),
    ("procurement:invoicedispute_delete", "dispute", {}),
    ("procurement:invoicedispute_resolve", "dispute", {"resolution": "short_pay"}),
    ("procurement:invoicedispute_escalate", "dispute", {}),
    ("procurement:invoicedispute_await_supplier", "dispute", {}),
    ("procurement:invoicedispute_await_internal", "dispute", {}),
    ("procurement:invoicedispute_close", "dispute", {}),
)

#: The eleven routes ``@tenant_admin_required`` guards. ``supplierinvoice_revalidate`` takes no pk.
_INVOICE_ADMIN_ONLY_ROUTES = (
    ("procurement:supplierinvoice_delete", "invoice", {}),
    ("procurement:supplierinvoice_approve", "invoice", {}),
    ("procurement:supplierinvoice_override", "invoice", {}),
    ("procurement:supplierinvoice_void", "invoice", {"reason": "member says so"}),
    ("procurement:supplierinvoice_reverse", "invoice", {}),
    ("procurement:supplierinvoice_mark_paid", "invoice", {}),
    ("procurement:supplierinvoice_revalidate", None, {}),
    ("procurement:invoicedispute_delete", "dispute", {}),
    ("procurement:invoicedispute_resolve", "dispute", {"resolution": "short_pay"}),
    ("procurement:invoicedispute_escalate", "dispute", {}),
    ("procurement:invoicedispute_close", "dispute", {}),
)

#: Query strings anybody can type into the address bar. Every one must render 200, never 500 (L11).
_INVOICE_JUNK_QUERIES = (
    {"vendor": "abc"},
    {"vendor": "²"},
    {"vendor": "999999999999999999999"},
    {"vendor": "-1"},
    {"invoice": "abc"},
    {"po_line": "²"},
    {"item": "9" * 40},
    {"supplier": "abc"},
    {"assigned_to": "999999999999999999999"},
    {"terms": "abc"},
    {"status": "nope"},
    {"match_status": "nope"},
    {"source": "nope"},
    {"invoice_type": "nope"},
    {"variance_type": "nope"},
    {"outcome": "nope"},
    {"resolution": "nope"},
    {"basis": "nope"},
    {"reason_code": "nope"},
    {"gl_missing": "abc"},
    {"overdue": "maybe"},
    {"bucket": "not-a-bucket"},
    {"weeks": "abc"},
    {"page": "abc"},
    {"page": "0"},
    {"page": "-5"},
    {"page": "99999"},
    {"q": "'; DROP TABLE procurement_supplierinvoice; --"},
)

#: Every hand-fed figure that must land as a FIELD error rather than a 500 (L35).
_INVOICE_BAD_DECIMALS = ("NaN", "-NaN", "Infinity", "-Infinity", "inf", "abc", "1e400",
                         "12345678901234567890123456", "")


@pytest.fixture
def _invoice_superuser_client(db):
    """A logged-in SUPERUSER — ``tenant=None`` by design, so it owns no workspace at all."""
    from apps.accounts.models import User
    user = User.objects.create_superuser(email="root@naverp.test", username="root",
                                         password="TestPass123!")
    assert user.tenant_id is None
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def _invoice_bulk_a(db, tenant_a, invoice_vendor_a, usd):
    """Sixteen invoices, each with a line, a variance and a dispute — one more than a page.

    Every paginated 6.13 surface (the four registers, the match board and the aging board) needs
    16 rows before page 2 can be proved to differ from page 1.
    """
    rows = []
    for index in range(16):
        invoice = SupplierInvoice.objects.create(
            tenant=tenant_a, vendor=invoice_vendor_a, invoice_number=f"BULK-{index:03d}",
            invoice_date=timezone.localdate(), currency=usd)
        SupplierInvoiceLine.objects.create(
            invoice=invoice, description=f"Bulk line {index:03d}", sku_hint=f"BLK-{index:03d}",
            quantity=Decimal("1"), unit_price=Decimal("5.00"))
        InvoiceMatchVariance.objects.create(
            tenant=tenant_a, invoice=invoice, variance_type="price", basis="po",
            expected_value=Decimal("5.0000"), actual_value=Decimal("6.0000"),
            outcome="warn", resolution="open", message=f"Bulk variance {index:03d}")
        InvoiceDispute.objects.create(
            tenant=tenant_a, invoice=invoice, reason_code="price",
            disputed_amount=Decimal("1.00"), description=f"Bulk dispute {index:03d}")
        rows.append(invoice)
    return rows


# ==================================================================== 1. cross-tenant IDOR
def test_invoice_cross_tenant_pks_404_on_every_scoped_route(
        client_a, invoice_b, invoice_line_b, invoice_variance_b, invoice_dispute_b):
    """Tenant A's admin aiming any pk-scoped 6.13 route at a tenant-B row gets 404 — reads, edits,
    deletes and every one of the sixteen verbs alike — and every tenant-B row is byte-identical
    afterwards.

    Nothing is matched, submitted, approved, overridden, voided, reversed, scheduled, paid,
    accepted or resolved out of another workspace's payables, and no ledger row is minted.
    """
    before = (_invoice_state(invoice_b), _invoice_line_state(invoice_line_b),
              _invoice_variance_state(invoice_variance_b),
              _invoice_dispute_state(invoice_dispute_b))
    counts = _invoice_counts()
    pk_for = {"invoice": invoice_b.pk, "line": invoice_line_b.pk,
              "variance": invoice_variance_b.pk, "dispute": invoice_dispute_b.pk}

    for name, kind in _INVOICE_PK_GET_ROUTES:
        assert client_a.get(reverse(name, args=[pk_for[kind]])).status_code == 404, name

    for name, kind, body in _INVOICE_VERB_ROUTES:
        assert client_a.post(reverse(name, args=[pk_for[kind]]),
                             body).status_code == 404, name

    # The three write forms' POST paths reach the same guard.
    assert client_a.post(reverse("procurement:supplierinvoice_edit", args=[invoice_b.pk]),
                         _invoice_header_payload(**_invoice_formset_payload(),
                                                 invoice_number="hijacked")).status_code == 404
    assert client_a.post(reverse("procurement:supplierinvoiceline_edit",
                                 args=[invoice_line_b.pk]),
                         _invoice_line_payload(description="hijacked")).status_code == 404
    assert client_a.post(reverse("procurement:invoicedispute_edit",
                                 args=[invoice_dispute_b.pk]),
                         _invoice_dispute_payload(description="hijacked")).status_code == 404
    assert client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_b.pk]),
                         {"note": "hijacked"}).status_code == 404

    assert (_invoice_state(invoice_b), _invoice_line_state(invoice_line_b),
            _invoice_variance_state(invoice_variance_b),
            _invoice_dispute_state(invoice_dispute_b)) == before
    assert _invoice_counts() == counts


def test_invoice_owner_tenant_reaches_the_same_routes(
        client_b, invoice_b, invoice_line_b, invoice_variance_b, invoice_dispute_b):
    """L44 pair for the IDOR block: the 404s above are a TENANT boundary, not a broken module —
    tenant B's own admin reads every one of those pages at 200 on the very same pks."""
    pk_for = {"invoice": invoice_b.pk, "line": invoice_line_b.pk,
              "variance": invoice_variance_b.pk, "dispute": invoice_dispute_b.pk}
    for name, kind in _INVOICE_PK_GET_ROUTES:
        assert client_b.get(reverse(name, args=[pk_for[kind]])).status_code == 200, name


def test_invoice_create_prefill_ignores_a_cross_tenant_invoice_pk(
        client_a, invoice_b, invoice_draft_a):
    """``?invoice=`` is a prefill, and a prefill is still an authorization surface.

    The dispute form silently drops another workspace's pk (never leaking it into ``initial``),
    and the line form — where the pk is not a hint but the parent — refuses outright rather than
    creating an orphan against a document the caller cannot see.
    """
    resp = client_a.get(reverse("procurement:invoicedispute_create"),
                        {"invoice": str(invoice_b.pk)})
    assert resp.status_code == 200
    assert resp.context["invoice"] is None
    assert resp.context["form"].initial.get("invoice") is None

    resp = client_a.get(reverse("procurement:supplierinvoiceline_create"),
                        {"invoice": str(invoice_b.pk)})
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_list")
    assert not SupplierInvoiceLine.objects.filter(invoice__tenant=invoice_b.tenant).exclude(
        pk__in=list(invoice_b.lines.values_list("pk", flat=True))).exists()

    # L44 pair: the SAME parameter carrying this workspace's own pk works.
    resp = client_a.get(reverse("procurement:supplierinvoiceline_create"),
                        {"invoice": str(invoice_draft_a.pk)})
    assert resp.status_code == 200
    assert resp.context["invoice"].pk == invoice_draft_a.pk


# ==================================================================== 2. register & board isolation
def test_invoice_registers_never_show_another_workspace(
        client_a, client_b, tenant_a, tenant_b, invoice_draft_a, invoice_line_a,
        invoice_variance_block_a, invoice_dispute_open_a, invoice_b, invoice_line_b,
        invoice_variance_b, invoice_dispute_b):
    """A's four registers hold A's rows and only A's, and B's admin sees the mirror image."""
    probes = (
        ("procurement:supplierinvoice_list", invoice_draft_a.pk, invoice_b.pk),
        ("procurement:supplierinvoiceline_list", invoice_line_a.pk, invoice_line_b.pk),
        ("procurement:matchvariance_list", invoice_variance_block_a.pk, invoice_variance_b.pk),
        ("procurement:invoicedispute_list", invoice_dispute_open_a.pk, invoice_dispute_b.pk),
    )
    for name, own_pk, foreign_pk in probes:
        resp = client_a.get(reverse(name))
        assert resp.status_code == 200, name
        pks = {row.pk for row in resp.context["object_list"]}
        assert own_pk in pks, name
        assert foreign_pk not in pks, name
        assert b"Globex" not in resp.content, name

        resp = client_b.get(reverse(name))
        assert resp.status_code == 200, name
        pks = {row.pk for row in resp.context["object_list"]}
        assert foreign_pk in pks, name
        assert own_pk not in pks, name


def test_invoice_boards_never_show_another_workspace(
        client_a, tenant_b, invoice_vendor_b, invoice_term_b, usd, invoice_draft_a,
        invoice_line_a, invoice_duplicate_a, invoice_variance_b, invoice_dispute_b, invoice_b):
    """The five boards are projections, and a projection leaks just as badly as a register.

    A tenant-B invoice is put into the ``scheduled`` state on purpose so the Payment Schedule has
    something of B's it *could* have rendered — the assertion is that it does not.
    """
    SupplierInvoice.objects.create(
        tenant=tenant_b, vendor=invoice_vendor_b, invoice_number="GBX-9002",
        invoice_date=timezone.localdate(), status="scheduled",
        payment_term=invoice_term_b, currency=usd)

    for name in ("procurement:invoicevoucher_dashboard",
                 "procurement:supplierinvoice_duplicates",
                 "procurement:paymentschedule_list",
                 "procurement:invoice_match_board",
                 "procurement:invoicedispute_aging"):
        resp = client_a.get(reverse(name))
        assert resp.status_code == 200, name
        assert b"Globex" not in resp.content, name
        assert b"GBX-9002" not in resp.content, name

    # The dashboard counts the workspace, so its own stat must agree with A's own table.
    resp = client_a.get(reverse("procurement:invoicevoucher_dashboard"))
    assert resp.context["stats"]["invoices"] == SupplierInvoice.objects.filter(
        tenant=invoice_draft_a.tenant).count()
    # L44 pair: A's own duplicate pair IS on its duplicate board.
    resp = client_a.get(reverse("procurement:supplierinvoice_duplicates"))
    assert resp.context["stats"]["suspect"] >= 1


def test_invoice_tenantless_superuser_is_refused_not_shown_everything(
        _invoice_superuser_client, invoice_draft_a, invoice_line_a, invoice_variance_block_a,
        invoice_dispute_open_a):
    """``request.tenant`` is ``None`` for the superuser by design.

    Every register / board / create route says so and redirects to the dashboard; every pk-scoped
    route 404s, because ``get_object_or_404(..., tenant=None)`` matches nothing. Neither path may
    render another workspace's payables.
    """
    home = reverse("dashboard:home")
    for name in _INVOICE_PAGE_ROUTES:
        resp = _invoice_superuser_client.get(reverse(name))
        assert resp.status_code == 302, name
        assert resp["Location"] == home, name

    pk_for = {"invoice": invoice_draft_a.pk, "line": invoice_line_a.pk,
              "variance": invoice_variance_block_a.pk, "dispute": invoice_dispute_open_a.pk}
    for name, kind in _INVOICE_PK_GET_ROUTES:
        # matchvariance_accept guards on the tenant FIRST and redirects; the rest 404.
        resp = _invoice_superuser_client.get(reverse(name, args=[pk_for[kind]]))
        assert resp.status_code in (302, 404), name
        if resp.status_code == 302:
            assert resp["Location"] == home, name


# ==================================================================== 3. the authz ladder
def test_invoice_anonymous_redirected_to_login_on_every_route(
        db, invoice_draft_a, invoice_line_a, invoice_variance_block_a, invoice_dispute_open_a):
    """No 6.13 URL — page, pk page or verb — answers an unauthenticated request; each one bounces
    to ``/login/`` and every row is untouched afterwards."""
    anon = Client()
    login_prefix = reverse("accounts:login")
    before = (_invoice_state(invoice_draft_a), _invoice_line_state(invoice_line_a),
              _invoice_variance_state(invoice_variance_block_a),
              _invoice_dispute_state(invoice_dispute_open_a))
    counts = _invoice_counts()
    pk_for = {"invoice": invoice_draft_a.pk, "line": invoice_line_a.pk,
              "variance": invoice_variance_block_a.pk, "dispute": invoice_dispute_open_a.pk}

    for name in _INVOICE_PAGE_ROUTES + ("procurement:supplierinvoiceline_create",):
        resp = anon.get(reverse(name))
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    for name, kind in _INVOICE_PK_GET_ROUTES:
        resp = anon.get(reverse(name, args=[pk_for[kind]]))
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    for name, kind, body in _INVOICE_VERB_ROUTES:
        resp = anon.post(reverse(name, args=[pk_for[kind]]), body)
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    resp = anon.post(reverse("procurement:supplierinvoice_revalidate"))
    assert resp.status_code == 302
    assert resp["Location"].startswith(login_prefix)

    assert (_invoice_state(invoice_draft_a), _invoice_line_state(invoice_line_a),
            _invoice_variance_state(invoice_variance_block_a),
            _invoice_dispute_state(invoice_dispute_open_a)) == before
    assert _invoice_counts() == counts


def test_invoice_member_refused_on_every_admin_only_route(
        member_client, invoice_pending_a, invoice_dispute_open_a):
    """``@tenant_admin_required`` guards the eleven moves that commit the workspace's money —
    deleting, approving (the only ledger write), overriding a block, voiding, reversing, marking
    paid, the workspace-wide revalidate, and the four dispute settlements.

    A plain member gets PermissionDenied (403) on all eleven, by POST and by GET alike (the gate
    sits OUTSIDE ``@require_POST``), and nothing moves.
    """
    before = (_invoice_state(invoice_pending_a),
              _invoice_dispute_state(invoice_dispute_open_a))
    counts = _invoice_counts()
    pk_for = {"invoice": invoice_pending_a.pk, "dispute": invoice_dispute_open_a.pk}

    for name, kind, body in _INVOICE_ADMIN_ONLY_ROUTES:
        url = reverse(name) if kind is None else reverse(name, args=[pk_for[kind]])
        assert member_client.post(url, body).status_code == 403, name
        assert member_client.get(url).status_code == 403, name

    assert (_invoice_state(invoice_pending_a),
            _invoice_dispute_state(invoice_dispute_open_a)) == before
    assert _invoice_counts() == counts


def test_invoice_member_may_use_every_other_route(
        member_client, tenant_a, invoice_vendor_a, usd, invoice_draft_a, invoice_line_a,
        invoice_captured_a, invoice_blocked_a, invoice_variance_block_a,
        invoice_dispute_open_a, invoice_dispute_escalated_a):
    """L44 pair for the admin gate: 6.13 keeps the everyday AP work member-reachable on purpose.

    Matching, submitting for approval, scheduling an already-approved invoice, removing a line,
    accepting an exception and parking a dispute with either side are all a clerk's job — the
    approval that follows is not. Every read renders and every one of those seven verbs succeeds.
    """
    for name in _INVOICE_PAGE_ROUTES:
        assert member_client.get(reverse(name)).status_code == 200, name

    pk_for = {"invoice": invoice_draft_a.pk, "line": invoice_line_a.pk,
              "variance": invoice_variance_block_a.pk, "dispute": invoice_dispute_open_a.pk}
    for name, kind in _INVOICE_PK_GET_ROUTES:
        assert member_client.get(reverse(name, args=[pk_for[kind]])).status_code == 200, name

    # match — the row is re-judged, so the match status must leave "not run".
    assert member_client.post(reverse("procurement:supplierinvoice_match",
                                      args=[invoice_draft_a.pk])).status_code == 302
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.match_status != "not_run"

    # submit — a captured invoice reaches the approver.
    assert member_client.post(reverse("procurement:supplierinvoice_submit",
                                      args=[invoice_captured_a.pk])).status_code == 302
    invoice_captured_a.refresh_from_db()
    assert invoice_captured_a.status == "pending_approval"

    # schedule — approved is a clerk's queue, not an approver's.
    approved = SupplierInvoice.objects.create(
        tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="SUP-APPROVED-1",
        invoice_date=timezone.localdate(), status="approved", currency=usd)
    assert member_client.post(reverse("procurement:supplierinvoice_schedule",
                                      args=[approved.pk])).status_code == 302
    approved.refresh_from_db()
    assert approved.status == "scheduled"

    # accept a variance.
    assert member_client.post(reverse("procurement:matchvariance_accept",
                                      args=[invoice_variance_block_a.pk]),
                              {"note": "agreed by phone"}).status_code == 302
    invoice_variance_block_a.refresh_from_db()
    assert invoice_variance_block_a.resolution == "accepted"

    # both dispute "waiting" verbs.
    assert member_client.post(reverse("procurement:invoicedispute_await_supplier",
                                      args=[invoice_dispute_open_a.pk])).status_code == 302
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "awaiting_supplier"
    assert member_client.post(reverse("procurement:invoicedispute_await_internal",
                                      args=[invoice_dispute_escalated_a.pk])).status_code == 302
    invoice_dispute_escalated_a.refresh_from_db()
    assert invoice_dispute_escalated_a.status == "awaiting_internal"

    # line delete — deliberately NOT admin-gated (the header edit it mirrors is not either).
    #
    # Off a still-EDITABLE header, and not off ``invoice_line_a``: the clean match above moved
    # invoice_draft_a to pending_approval, and past EDITABLE_STATUSES a line may no longer be
    # pulled out from under an invoice that is already waiting on an approver. That refusal is a
    # 302 too, so the row check below is what tells the two apart.
    spare_invoice = SupplierInvoice.objects.create(
        tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="SUP-MEMBER-LINE-1",
        invoice_date=timezone.localdate(), status="draft", currency=usd)
    spare_line = SupplierInvoiceLine.objects.create(
        invoice=spare_invoice, description="Removable line", quantity=Decimal("1"),
        unit_price=Decimal("5.00"))
    assert member_client.post(reverse("procurement:supplierinvoiceline_delete",
                                      args=[spare_line.pk])).status_code == 302
    assert not SupplierInvoiceLine.objects.filter(pk=spare_line.pk).exists()


def test_invoice_csrf_enforced_on_every_post_route(
        admin_user, invoice_draft_a, invoice_line_a, invoice_variance_block_a,
        invoice_dispute_open_a, invoice_vendor_a, gl_expense_a):
    """A logged-in session is not enough: every mutating 6.13 POST needs a CSRF token. Without
    one each is rejected 403 and nothing is created, matched, posted, accepted or deleted."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    before = (_invoice_state(invoice_draft_a), _invoice_line_state(invoice_line_a),
              _invoice_variance_state(invoice_variance_block_a),
              _invoice_dispute_state(invoice_dispute_open_a))
    counts = _invoice_counts()
    pk_for = {"invoice": invoice_draft_a.pk, "line": invoice_line_a.pk,
              "variance": invoice_variance_block_a.pk, "dispute": invoice_dispute_open_a.pk}

    posts = [(reverse(name, args=[pk_for[kind]]), body)
             for name, kind, body in _INVOICE_VERB_ROUTES]
    posts += [
        (reverse("procurement:supplierinvoice_revalidate"), {}),
        (reverse("procurement:supplierinvoice_create"),
         dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk)),
              **_invoice_formset_payload())),
        (reverse("procurement:supplierinvoice_edit", args=[invoice_draft_a.pk]),
         dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk),
                                      invoice_number="no token"),
              **_invoice_formset_payload())),
        (reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
         _invoice_line_payload(gl_account=str(gl_expense_a.pk))),
        (reverse("procurement:supplierinvoiceline_edit", args=[invoice_line_a.pk]),
         _invoice_line_payload(gl_account=str(gl_expense_a.pk))),
        (reverse("procurement:invoicedispute_create"),
         _invoice_dispute_payload(invoice=str(invoice_draft_a.pk))),
        (reverse("procurement:invoicedispute_edit", args=[invoice_dispute_open_a.pk]),
         _invoice_dispute_payload(description="no token")),
        (reverse("procurement:matchvariance_accept", args=[invoice_variance_block_a.pk]),
         {"note": "no token"}),
        (reverse("procurement:supplierinvoice_capture"),
         dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk)), stage="confirm")),
    ]
    for url, body in posts:
        assert csrf_client.post(url, body).status_code == 403, url

    assert (_invoice_state(invoice_draft_a), _invoice_line_state(invoice_line_a),
            _invoice_variance_state(invoice_variance_block_a),
            _invoice_dispute_state(invoice_dispute_open_a)) == before
    assert _invoice_counts() == counts

    # L44 pair: the SAME csrf-enforcing session reads happily — only unsafe methods are gated.
    assert csrf_client.get(reverse("procurement:supplierinvoice_detail",
                                   args=[invoice_draft_a.pk])).status_code == 200


def test_invoice_get_on_post_only_verbs_is_405_and_never_mutates(
        client_a, invoice_draft_a, invoice_line_a, invoice_dispute_open_a,
        invoice_variance_block_a):
    """``@require_POST`` fires before any of the verbs' own guards: a GET on a 6.13 verb URL is
    refused outright — nothing matched, submitted, posted, voided or deleted — and every row
    survives untouched.

    ``matchvariance_accept`` is deliberately excluded: it is the one verb whose GET is a page.
    """
    pk_for = {"invoice": invoice_draft_a.pk, "line": invoice_line_a.pk,
              "dispute": invoice_dispute_open_a.pk}
    before = (_invoice_state(invoice_draft_a), _invoice_line_state(invoice_line_a),
              _invoice_dispute_state(invoice_dispute_open_a))
    counts = _invoice_counts()

    for name, kind, _body in _INVOICE_VERB_ROUTES:
        assert client_a.get(reverse(name, args=[pk_for[kind]])).status_code == 405, name
    assert client_a.get(reverse("procurement:supplierinvoice_revalidate")).status_code == 405

    assert (_invoice_state(invoice_draft_a), _invoice_line_state(invoice_line_a),
            _invoice_dispute_state(invoice_dispute_open_a)) == before
    assert _invoice_counts() == counts

    # L44 pair: the accept confirmation page IS a GET, and it renders without accepting anything.
    resp = client_a.get(reverse("procurement:matchvariance_accept",
                                args=[invoice_variance_block_a.pk]))
    assert resp.status_code == 200
    invoice_variance_block_a.refresh_from_db()
    assert invoice_variance_block_a.resolution == "open"


# ==================================================================== 4. mass assignment
@pytest.mark.parametrize("field", ["vendor", "purchase_order", "goods_receipt", "payment_term",
                                   "tax_code"])
def test_invoice_header_rejects_a_cross_tenant_fk(
        client_a, field, invoice_vendor_a, invoice_vendor_b, invoice_po_b, invoice_grn_b,
        invoice_term_b, invoice_taxcode_b):
    """A narrowed ``<select>`` is UX; the boundary is the re-check. Every tenant-scoped FK on the
    header form refuses another workspace's pk as a FIELD error — a 200 re-render with nothing
    saved, never a 500 and never a saved row pointing across the boundary."""
    foreign = {"vendor": invoice_vendor_b, "purchase_order": invoice_po_b,
               "goods_receipt": invoice_grn_b, "payment_term": invoice_term_b,
               "tax_code": invoice_taxcode_b}[field]
    counts = _invoice_counts()
    # ONE dict, then the crafted key - ``vendor`` is both the always-valid baseline and one of the
    # five scopes, and naming it twice in a single call is a TypeError rather than an assertion.
    # Every other field stays a valid tenant-A value, so the foreign pk is the only thing on trial.
    payload = dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk)),
                   **_invoice_formset_payload())
    payload[field] = str(foreign.pk)
    resp = client_a.post(reverse("procurement:supplierinvoice_create"), payload)
    assert resp.status_code == 200
    assert field in resp.context["form"].errors
    assert _invoice_counts() == counts


def test_invoice_header_accepts_its_own_workspace_and_the_global_currency(
        client_a, tenant_a, invoice_vendor_a, invoice_po_a, invoice_grn_a, invoice_term_a,
        invoice_taxcode_a, usd):
    """L44 pair for the crafted-FK block: every one of those five FKs saves happily when the row
    is this workspace's own — and ``accounting.Currency`` is GLOBAL, so it is deliberately never
    tenant-scoped and never rejected."""
    payload = dict(_invoice_header_payload(
        vendor=str(invoice_vendor_a.pk), purchase_order=str(invoice_po_a.pk),
        goods_receipt=str(invoice_grn_a.pk), payment_term=str(invoice_term_a.pk),
        tax_code=str(invoice_taxcode_a.pk), currency=str(usd.pk),
        invoice_number="SUP-OK-1"), **_invoice_formset_payload())
    resp = client_a.post(reverse("procurement:supplierinvoice_create"), payload)
    assert resp.status_code == 302

    obj = SupplierInvoice.objects.get(invoice_number="SUP-OK-1")
    assert obj.tenant_id == tenant_a.pk
    assert obj.currency_id == usd.pk
    assert obj.purchase_order_id == invoice_po_a.pk
    assert obj.payment_term_id == invoice_term_a.pk


def test_invoice_header_rejects_a_same_tenant_order_from_another_vendor(
        client_a, invoice_vendor_a, invoice_po_other_a):
    """Vendor agreement is a control in its own right: an invoice FROM one supplier against
    ANOTHER supplier's order is either a mis-key or an attempt to draw funds to a third party.

    Both rows live in this workspace, so tenant scoping cannot catch it — the field error must.
    """
    counts = _invoice_counts()
    payload = dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk),
                                           purchase_order=str(invoice_po_other_a.pk)),
                   **_invoice_formset_payload())
    resp = client_a.post(reverse("procurement:supplierinvoice_create"), payload)
    assert resp.status_code == 200
    assert "different vendor" in " ".join(resp.context["form"].errors["purchase_order"])
    assert _invoice_counts() == counts


def test_invoice_header_ignores_forged_system_fields(
        client_a, tenant_a, tenant_b, invoice_vendor_a, admin_b):
    """The exclusion list is the security control, so it is asserted through a crafted POST.

    ``tenant`` / ``number`` / ``status`` / the four money columns / ``match_*`` / ``source`` /
    ``invoice_number_norm`` / ``due_date`` / ``approved_*`` are all system-owned. A POST that
    carries every one of them must land a perfectly ordinary DRAFT invoice in THIS workspace.
    """
    payload = dict(_invoice_header_payload(
        vendor=str(invoice_vendor_a.pk), invoice_number="SUP-FORGED-1"),
        **_invoice_formset_payload())
    payload.update({
        "tenant": str(tenant_b.pk),
        "number": "SIV-99999",
        "invoice_number_norm": "SOMETHINGELSE",
        "status": "approved",
        "subtotal": "9999.00", "tax_total": "9999.00", "total": "9999.00",
        "amount_paid": "9999.00",
        "match_basis": "amount", "match_status": "matched", "match_notes": "forged",
        "source": "ocr", "extraction_confidence": "100",
        "due_date": _invoice_iso(365), "discount_date": _invoice_iso(365),
        "approved_by": str(admin_b.pk), "approved_at": timezone.now().isoformat(),
    })
    resp = client_a.post(reverse("procurement:supplierinvoice_create"), payload)
    assert resp.status_code == 302

    obj = SupplierInvoice.objects.get(invoice_number="SUP-FORGED-1")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("SIV-") and obj.number != "SIV-99999"
    assert obj.invoice_number_norm == "SUPFORGED1"
    assert obj.status == "draft"
    assert (obj.subtotal, obj.tax_total, obj.total, obj.amount_paid) == (
        Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
    assert obj.match_status == "not_run"
    assert obj.match_notes == ""
    assert obj.source == "manual"
    assert obj.extraction_confidence is None
    # No payment term was chosen, so save() derives NO dates at all — the typed ones are gone.
    assert obj.due_date is None and obj.discount_date is None
    assert obj.approved_by_id is None and obj.approved_at is None
    assert obj.bill_id is None and obj.journal_entry_id is None


@pytest.mark.parametrize("field", ["item", "gl_account", "tax_code", "po_line", "receipt_line"])
def test_invoice_line_rejects_a_cross_tenant_fk(
        client_a, field, invoice_draft_a, gl_expense_a, invoice_item_b, gl_expense_b,
        invoice_taxcode_b, invoice_po_line_b, invoice_grn_line_b):
    """The child carries no tenant column, so ``po_line`` / ``receipt_line`` have to be checked
    through their OWN headers — and ``item`` / ``gl_account`` / ``tax_code`` through
    ``_reject_foreign``. All five refuse tenant B's pk as a field error, nothing is written."""
    foreign = {"item": invoice_item_b, "gl_account": gl_expense_b,
               "tax_code": invoice_taxcode_b, "po_line": invoice_po_line_b,
               "receipt_line": invoice_grn_line_b}[field]
    counts = _invoice_counts()
    # Same shape as the header case: ``gl_account`` is the mandatory baseline AND one of the five
    # crafted scopes, so it is set once and then overwritten.
    payload = _invoice_line_payload(gl_account=str(gl_expense_a.pk))
    payload[field] = str(foreign.pk)
    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        payload)
    assert resp.status_code == 200
    assert field in resp.context["form"].errors
    assert _invoice_counts() == counts


def test_invoice_line_accepts_its_own_workspace_and_ignores_forged_derived_columns(
        client_a, invoice_draft_a, invoice_po_line_a, invoice_grn_line_a, invoice_item_a,
        gl_expense_a, invoice_taxcode_a):
    """L44 pair for the line's crafted-FK block, plus the derived-column exclusion.

    ``line_total`` and ``matched_qty`` are ``editable=False``: a POST carrying both must be
    ignored and the total re-derived from quantity x unit_price.
    """
    payload = _invoice_line_payload(
        po_line=str(invoice_po_line_a.pk), receipt_line=str(invoice_grn_line_a.pk),
        item=str(invoice_item_a.pk), gl_account=str(gl_expense_a.pk),
        tax_code=str(invoice_taxcode_a.pk), description="Genuine line",
        quantity="3", unit_price="7.00")
    payload.update({"line_total": "999999.00", "matched_qty": "999.0000",
                    "invoice": "0"})
    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        payload)
    assert resp.status_code == 302

    line = SupplierInvoiceLine.objects.get(description="Genuine line")
    assert line.invoice_id == invoice_draft_a.pk        # the header came from the URL, not the body
    assert line.line_total == Decimal("21.00")
    assert line.matched_qty == Decimal("0.0000")


@pytest.mark.parametrize("field", ["item", "gl_account", "tax_code", "po_line", "receipt_line"])
def test_invoice_line_formset_rejects_a_cross_tenant_fk(
        client_a, field, invoice_vendor_a, invoice_item_b, gl_expense_b, invoice_taxcode_b,
        invoice_po_line_b, invoice_grn_line_b):
    """The same five FKs, reached through the header page's INLINE formset (prefix ``lines``) —
    the surface a crafted POST actually has, since the header form and the line form are
    submitted together."""
    foreign = {"item": invoice_item_b, "gl_account": gl_expense_b,
               "tax_code": invoice_taxcode_b, "po_line": invoice_po_line_b,
               "receipt_line": invoice_grn_line_b}[field]
    counts = _invoice_counts()
    payload = dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk)),
                   **_invoice_formset_payload(line={field: str(foreign.pk)}))
    resp = client_a.post(reverse("procurement:supplierinvoice_create"), payload)
    assert resp.status_code == 200
    assert field in resp.context["line_formset"].forms[0].errors
    assert _invoice_counts() == counts


def test_invoice_dispute_rejects_cross_tenant_invoice_and_line(
        client_a, invoice_b, invoice_line_b, invoice_draft_a, invoice_line_a):
    """A dispute points at a document and at one of its lines; both are re-checked. Another
    workspace's invoice, and another workspace's line under this workspace's invoice, are both
    field errors — and the valid pair saves (L44)."""
    counts = _invoice_counts()

    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_payload(invoice=str(invoice_b.pk)))
    assert resp.status_code == 200
    assert "invoice" in resp.context["form"].errors

    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_payload(invoice=str(invoice_draft_a.pk),
                                                  invoice_line=str(invoice_line_b.pk)))
    assert resp.status_code == 200
    assert "invoice_line" in resp.context["form"].errors
    assert _invoice_counts() == counts

    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_payload(invoice=str(invoice_draft_a.pk),
                                                  invoice_line=str(invoice_line_a.pk),
                                                  description="Genuine dispute."))
    assert resp.status_code == 302
    assert InvoiceDispute.objects.filter(description="Genuine dispute.").exists()


def test_invoice_dispute_edit_cannot_be_repointed_or_restamped(
        client_a, admin_user, admin_b, tenant_a, tenant_b, invoice_dispute_open_a,
        invoice_captured_a, invoice_b, invoice_line_b, invoice_credit_memo_a):
    """``invoice`` and ``invoice_line`` are POPPED on edit, and every stamp is excluded.

    A crafted POST carrying another invoice (even one of THIS workspace's), a forged ``tenant`` /
    ``number`` / ``status`` / ``supplier`` / ``resolution`` / ``raised_by`` / ``credit_memo_invoice``
    block saves the fields it is allowed to and moves nothing else.
    """
    before = _invoice_dispute_state(invoice_dispute_open_a)
    payload = _invoice_dispute_payload(description="Amended text.",
                                       disputed_amount="20.00")
    payload.update({
        "invoice": str(invoice_captured_a.pk),
        "invoice_line": str(invoice_line_b.pk),
        "tenant": str(tenant_b.pk),
        "number": "DSP-99999",
        "status": "resolved",
        "supplier": "0",
        "resolution": "withdrawn",
        "resolution_note": "forged",
        "raised_by": str(admin_b.pk),
        "credit_memo_invoice": str(invoice_credit_memo_a.pk),
        "resolved_at": timezone.now().isoformat(),
    })
    resp = client_a.post(
        reverse("procurement:invoicedispute_edit", args=[invoice_dispute_open_a.pk]), payload)
    assert resp.status_code == 302

    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.description == "Amended text."
    assert invoice_dispute_open_a.disputed_amount == Decimal("20.00")
    # Everything the form does not own is exactly where it was.
    assert invoice_dispute_open_a.tenant_id == tenant_a.pk
    assert invoice_dispute_open_a.invoice_id == before[2]
    assert invoice_dispute_open_a.invoice_line_id == before[3]
    assert invoice_dispute_open_a.supplier_id == before[4]
    assert invoice_dispute_open_a.number == before[1]
    assert invoice_dispute_open_a.status == "open"
    assert invoice_dispute_open_a.resolution == ""
    assert invoice_dispute_open_a.resolution_note == ""
    assert invoice_dispute_open_a.resolved_at is None
    assert invoice_dispute_open_a.raised_by_id == admin_user.pk
    assert invoice_dispute_open_a.credit_memo_invoice_id is None


def test_invoice_capture_confirm_ignores_a_cross_tenant_document(
        client_a, tenant_a, tenant_b, invoice_vendor_a):
    """The confirm stage carries only the document's pk, so the pk is re-validated against the
    workspace. Another workspace's document is dropped, and the provenance columns are stamped
    server-side — ``source`` / ``extraction_confidence`` / ``extraction_raw_text`` are never on
    the form."""
    from apps.core.models import Document
    foreign_doc = Document.objects.create(tenant=tenant_b, name="globex-invoice.pdf",
                                          file="documents/globex.pdf")

    payload = dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk),
                                           invoice_number="SUP-CAPTURED-1"),
                   stage="confirm", document=str(foreign_doc.pk),
                   source="e_invoice_xml", extraction_confidence="99",
                   extraction_raw_text="forged")
    resp = client_a.post(reverse("procurement:supplierinvoice_capture"), payload)
    assert resp.status_code == 302

    obj = SupplierInvoice.objects.get(invoice_number="SUP-CAPTURED-1")
    assert obj.tenant_id == tenant_a.pk
    assert obj.document_id is None
    assert obj.source == "manual"                     # the no-text-layer fallback path
    assert obj.extraction_confidence == Decimal("0")
    assert obj.extraction_raw_text == ""


# ==================================================================== 5. hostile input
@pytest.mark.parametrize("params", _INVOICE_JUNK_QUERIES)
def test_invoice_junk_query_params_never_500_on_any_surface(
        client_a, params, invoice_draft_a, invoice_line_a, invoice_variance_block_a,
        invoice_dispute_open_a):
    """Every register and every board answers 200 to anything typeable in the address bar —
    a junk FK pk, a superscript digit, an over-64-bit integer, an unrecognised enum, a junk
    truth value, a junk bucket, a junk week count, a junk page and an injection attempt (L11)."""
    for name in _INVOICE_PAGE_ROUTES:
        resp = client_a.get(reverse(name), params)
        assert resp.status_code == 200, (name, params)


def test_invoice_junk_fk_filter_is_skipped_rather_than_matched(
        client_a, invoice_draft_a, invoice_line_a, invoice_variance_block_a,
        invoice_dispute_open_a, invoice_vendor_a):
    """L11 completed: an unusable FK filter value is not a narrowing request, so it is SKIPPED —
    the register still renders its rows rather than going blank (or 500ing).

    Paired with the real pk, which DOES narrow: the guard must not have broken the filter.
    """
    for junk in ("abc", "²", "999999999999999999999"):
        resp = client_a.get(reverse("procurement:supplierinvoice_list"), {"vendor": junk})
        assert resp.status_code == 200
        assert invoice_draft_a.pk in {row.pk for row in resp.context["object_list"]}, junk

    resp = client_a.get(reverse("procurement:supplierinvoice_list"),
                        {"vendor": str(invoice_vendor_a.pk)})
    assert resp.status_code == 200
    assert invoice_draft_a.pk in {row.pk for row in resp.context["object_list"]}

    for name, param in (("procurement:supplierinvoiceline_list", "invoice"),
                        ("procurement:matchvariance_list", "invoice"),
                        ("procurement:invoicedispute_list", "supplier")):
        resp = client_a.get(reverse(name), {param: "abc"})
        assert resp.status_code == 200
        assert list(resp.context["object_list"]), name


def test_invoice_junk_enum_filter_falls_back_to_the_full_register(
        client_a, invoice_draft_a, invoice_variance_block_a, invoice_dispute_open_a):
    """An unrecognised CHOICES value matches nothing and would silently EMPTY the register, so
    ``crud_list``'s enum guard ignores it. The fallback is the FULL list, not a blank page —
    and the real value still narrows (L44)."""
    resp = client_a.get(reverse("procurement:supplierinvoice_list"), {"status": "nope"})
    assert resp.status_code == 200
    assert invoice_draft_a.pk in {row.pk for row in resp.context["object_list"]}

    resp = client_a.get(reverse("procurement:supplierinvoice_list"), {"status": "paid"})
    assert resp.status_code == 200
    assert invoice_draft_a.pk not in {row.pk for row in resp.context["object_list"]}

    resp = client_a.get(reverse("procurement:matchvariance_list"), {"outcome": "nope"})
    assert invoice_variance_block_a.pk in {row.pk for row in resp.context["object_list"]}
    resp = client_a.get(reverse("procurement:matchvariance_list"), {"outcome": "block"})
    assert invoice_variance_block_a.pk in {row.pk for row in resp.context["object_list"]}

    resp = client_a.get(reverse("procurement:invoicedispute_list"), {"status": "nope"})
    assert invoice_dispute_open_a.pk in {row.pk for row in resp.context["object_list"]}


def test_invoice_gl_missing_truth_values_fall_through_unfiltered(
        client_a, invoice_draft_a, invoice_line_a, gl_expense_a):
    """``?gl_missing=`` is an ``__isnull`` lookup, which cannot go through ``crud_list`` at all —
    it is only validated when the SQL is compiled, inside ``paginate()``. Anything that is not a
    recognised truth value must fall through UNFILTERED, and the two recognised ones must still
    select opposite sets."""
    coded = SupplierInvoiceLine.objects.create(
        invoice=invoice_draft_a, description="Coded line", quantity=Decimal("1"),
        unit_price=Decimal("1.00"), gl_account=gl_expense_a)

    for junk in ("abc", "maybe", "²", ""):
        resp = client_a.get(reverse("procurement:supplierinvoiceline_list"),
                            {"gl_missing": junk})
        assert resp.status_code == 200, junk
        pks = {row.pk for row in resp.context["object_list"]}
        assert {invoice_line_a.pk, coded.pk} <= pks, junk

    resp = client_a.get(reverse("procurement:supplierinvoiceline_list"), {"gl_missing": "1"})
    pks = {row.pk for row in resp.context["object_list"]}
    assert invoice_line_a.pk in pks and coded.pk not in pks

    resp = client_a.get(reverse("procurement:supplierinvoiceline_list"), {"gl_missing": "0"})
    pks = {row.pk for row in resp.context["object_list"]}
    assert coded.pk in pks and invoice_line_a.pk not in pks


def test_invoice_pagination_guards_hold_on_every_paginated_surface(client_a, _invoice_bulk_a):
    """L9: page 2 must DIFFER from page 1 once the rows exceed the page size, a page past the end
    must land on the last page, and a junk page must land on the first — on every paginated 6.13
    surface. The payment schedule is deliberately absent: it is bucketed, not paged."""
    paginated = ("procurement:supplierinvoice_list", "procurement:supplierinvoiceline_list",
                 "procurement:matchvariance_list", "procurement:invoicedispute_list",
                 "procurement:invoice_match_board", "procurement:invoicedispute_aging",
                 "procurement:supplierinvoice_duplicates")
    for name in paginated:
        first = client_a.get(reverse(name))
        assert first.status_code == 200, name
        page_obj = first.context["page_obj"]
        assert page_obj.number == 1, name

        last = client_a.get(reverse(name), {"page": "99999"})
        assert last.status_code == 200, name
        assert last.context["page_obj"].number == last.context["page_obj"].paginator.num_pages

        junk = client_a.get(reverse(name), {"page": "abc"})
        assert junk.status_code == 200, name
        assert junk.context["page_obj"].number == 1, name

    # The four registers carry >15 rows, so page 2 must be a genuinely different slice.
    for name in ("procurement:supplierinvoice_list", "procurement:supplierinvoiceline_list",
                 "procurement:matchvariance_list", "procurement:invoicedispute_list"):
        first = client_a.get(reverse(name))
        second = client_a.get(reverse(name), {"page": "2"})
        assert second.status_code == 200, name
        assert second.context["page_obj"].paginator.num_pages > 1, name
        assert {row.pk for row in first.context["object_list"]} != {
            row.pk for row in second.context["object_list"]}, name

    # The match board pages INVOICES, not variances — its unit of work is the card.
    first = client_a.get(reverse("procurement:invoice_match_board"))
    second = client_a.get(reverse("procurement:invoice_match_board"), {"page": "2"})
    assert second.context["page_obj"].paginator.num_pages > 1
    assert ({group["invoice"].pk for group in first.context["groups"]}
            != {group["invoice"].pk for group in second.context["groups"]})


def test_invoice_payment_schedule_clamps_the_week_horizon(client_a, invoice_scheduled_a):
    """``?weeks=`` builds one bucket per week, so an unclamped 10000 is a ten-thousand-bucket
    render. It is clamped to 1..26 and junk falls back to the default 8 — and the schedule still
    shows the invoice that is genuinely due (L44)."""
    cases = {"0": 1, "1": 1, "10000": 26, "26": 26, "27": 26,
             "NaN": 8, "abc": 8, "-5": 8, "²": 8, "999999999999999999999": 8, "": 8}
    for raw, expected in cases.items():
        resp = client_a.get(reverse("procurement:paymentschedule_list"), {"weeks": raw})
        assert resp.status_code == 200, raw
        assert resp.context["horizon_weeks"] == expected, raw
        # 1 overdue bucket + one per week.
        assert len(resp.context["buckets"]) == expected + 1, raw

    resp = client_a.get(reverse("procurement:paymentschedule_list"))
    rows = [row.pk for bucket in resp.context["buckets"] for row in bucket["rows"]]
    assert invoice_scheduled_a.pk in rows
    assert resp.context["page_obj"] if "page_obj" in resp.context else True


@pytest.mark.parametrize("raw", _INVOICE_BAD_DECIMALS + ("-1", "-0.5"))
def test_invoice_fx_rate_rejects_hostile_numbers_as_a_field_error(
        client_a, raw, invoice_vendor_a):
    """``fx_rate`` is hand-parsed after the field validates, so every hostile shape has to be
    refused BEFORE it reaches the driver: ``NaN`` / ``Infinity`` parse cleanly as Decimals and
    then raise on comparison, ``1e400`` dies inside the database, and a negative rate is not a
    rate at all. Each is a friendly FIELD error and a 200 — never a 500 (L35)."""
    if raw == "":
        pytest.skip("fx_rate is optional — the empty case is the no-rate path, not a rejection")
    counts = _invoice_counts()
    payload = dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk), fx_rate=raw),
                   **_invoice_formset_payload())
    resp = client_a.post(reverse("procurement:supplierinvoice_create"), payload)
    assert resp.status_code == 200, raw
    assert "fx_rate" in resp.context["form"].errors, raw
    assert _invoice_counts() == counts


def test_invoice_fx_rate_accepts_a_real_rate(client_a, invoice_vendor_a):
    """L44 pair for the ``fx_rate`` guard — a legitimate six-decimal rate still saves."""
    payload = dict(_invoice_header_payload(vendor=str(invoice_vendor_a.pk),
                                           invoice_number="SUP-FX-1", fx_rate="1.234567"),
                   **_invoice_formset_payload())
    assert client_a.post(reverse("procurement:supplierinvoice_create"),
                         payload).status_code == 302
    assert SupplierInvoice.objects.get(invoice_number="SUP-FX-1").fx_rate == Decimal("1.234567")


@pytest.mark.parametrize("raw", _INVOICE_BAD_DECIMALS + ("-1", "-0.01"))
def test_invoice_disputed_amount_rejects_hostile_numbers_as_a_field_error(
        client_a, raw, invoice_draft_a):
    """The same decimal family on ``disputed_amount`` — plus the negative case, because money
    withheld cannot be negative. Every one is a field error on a 200, nothing is created."""
    counts = _invoice_counts()
    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_payload(invoice=str(invoice_draft_a.pk),
                                                  disputed_amount=raw))
    assert resp.status_code == 200, raw
    assert "disputed_amount" in resp.context["form"].errors, raw
    assert _invoice_counts() == counts


def test_invoice_disputed_amount_is_capped_at_the_invoice_total(client_a, invoice_draft_a,
                                                                invoice_line_a):
    """A dispute cannot be worth more than the claim it argues with. ``invoice_draft_a`` totals
    250.00 once its 10 @ 25.00 line is on it, so 999.00 is a field error and 250.00 is accepted
    (L44).

    ``invoice_line_a`` is what puts the money there - the header fixture on its own has no lines,
    so its derived ``total`` is a correct 0 - and the in-memory header has to be re-read, because
    ``recalc_totals()`` runs in the LINE's save() and writes the row, not this object.
    """
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.total == Decimal("250.00")
    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_payload(invoice=str(invoice_draft_a.pk),
                                                  disputed_amount="999.00"))
    assert resp.status_code == 200
    assert "disputed_amount" in resp.context["form"].errors

    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_payload(invoice=str(invoice_draft_a.pk),
                                                  disputed_amount="250.00",
                                                  description="At the cap."))
    assert resp.status_code == 302
    assert InvoiceDispute.objects.get(description="At the cap.").disputed_amount == Decimal(
        "250.00")


@pytest.mark.parametrize("field,raw", [
    ("quantity", "NaN"), ("quantity", "Infinity"), ("quantity", "abc"),
    ("quantity", "1e400"), ("quantity", "10000000000"),
    ("unit_price", "NaN"), ("unit_price", "-Infinity"), ("unit_price", "abc"),
    ("unit_price", "1e400"), ("unit_price", "1000000000000"),
])
def test_invoice_line_money_rejects_hostile_numbers_as_a_field_error(
        client_a, field, raw, invoice_draft_a, gl_expense_a):
    """``quantity`` is Decimal(14, 4) and ``unit_price`` Decimal(14, 2), and both are checked for
    finiteness AND magnitude before anything is written — a value at the column ceiling parses
    cleanly and then dies inside the driver. Each shape is a field error on a 200 (L35)."""
    counts = _invoice_counts()
    payload = _invoice_line_payload(gl_account=str(gl_expense_a.pk), **{field: raw})
    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        payload)
    assert resp.status_code == 200, (field, raw)
    assert resp.context["form"].errors, (field, raw)
    assert _invoice_counts() == counts


def test_invoice_line_money_accepts_a_figure_just_under_the_ceiling(
        client_a, invoice_draft_a, gl_expense_a):
    """L44 pair for the magnitude guard: the ceilings are exclusive, so a large but storable
    figure still saves and the signed line total is derived from it."""
    payload = _invoice_line_payload(gl_account=str(gl_expense_a.pk), quantity="9999999999.9999",
                                    unit_price="0.01", description="Just under")
    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        payload)
    assert resp.status_code == 302
    assert SupplierInvoiceLine.objects.get(description="Just under").line_total == Decimal(
        "100000000.00")


def test_invoice_capture_survives_a_crafted_stage_and_a_bad_upload(client_a):
    """The capture flow is driven by a hidden ``stage`` field, i.e. by client-supplied text.

    A crafted stage falls back to the upload card rather than 500ing, an upload with no file is a
    form error, and a non-document extension is refused before any ``core.Document`` is written.
    """
    from apps.core.models import Document
    counts = _invoice_counts()
    documents = Document.objects.count()

    for stage in ("hijack", "", "confirm-ish", "__proto__"):
        resp = client_a.post(reverse("procurement:supplierinvoice_capture"), {"stage": stage})
        assert resp.status_code == 200, stage
        assert resp.context["stage"] == "upload", stage

    resp = client_a.post(reverse("procurement:supplierinvoice_capture"), {"stage": "upload"})
    assert resp.status_code == 200
    assert resp.context["stage"] == "upload"
    assert resp.context["upload_form"].errors

    resp = client_a.post(reverse("procurement:supplierinvoice_capture"), {
        "stage": "upload",
        "document_file": SimpleUploadedFile("payload.exe", b"MZ", content_type="application/exe"),
    })
    assert resp.status_code == 200
    assert resp.context["stage"] == "upload"
    assert resp.context["upload_form"].errors

    assert Document.objects.count() == documents
    assert _invoice_counts() == counts

    # L44 pair: the extension guard accepts a real PDF (checked on the form, so no file is
    # written to MEDIA_ROOT by this assertion).
    good = CaptureUploadForm(
        files={"document_file": SimpleUploadedFile("invoice.pdf", b"%PDF-1.4 ",
                                                   content_type="application/pdf")})
    assert good.is_valid(), good.errors


def test_invoice_capture_get_takes_the_no_text_layer_fallback(client_a):
    """``pdfplumber`` is an OPTIONAL import, so the designed path is an honest manual-keying form:
    ``has_text_layer`` False, ``source`` manual, no confidence claimed, every extracted field
    empty. Nothing here may depend on a library being installed."""
    resp = client_a.get(reverse("procurement:supplierinvoice_capture"))
    assert resp.status_code == 200
    assert resp.context["stage"] == "upload"
    assert resp.context["has_text_layer"] is False
    assert resp.context["source"] == "manual"
    assert resp.context["raw_text"] == ""
    assert all(field["value"] == "" for field in resp.context["extraction"].values())


# ==================================================================== 6. absent prerequisites (L35)
def test_invoice_dispute_resolve_refuses_a_missing_or_junk_resolution(
        client_a, invoice_dispute_open_a):
    """A settlement with no stated outcome is not a settlement. An absent or unrecognised
    ``resolution`` must be REJECTED — not defaulted, not fallen through to "resolved" — and the
    dispute must come back byte-identical.

    The view strips before it checks membership, so "   " is an absent outcome while a padded but
    REAL choice is a real choice — the L44 pair at the bottom posts one to prove the strip is a
    tolerance and not a hole. Case is not folded: "RESOLVED" is not "resolved".
    """
    before = _invoice_dispute_state(invoice_dispute_open_a)
    url = reverse("procurement:invoicedispute_resolve", args=[invoice_dispute_open_a.pk])

    for body in ({}, {"resolution": ""}, {"resolution": "   "}, {"resolution": "hijack"},
                 {"resolution": "RESOLVED"}, {"resolution_note": "no outcome given"},
                 {"resolution": "credit-memo", "spawn_credit_memo": "1"}):
        resp = client_a.post(url, body)
        assert resp.status_code == 302, body
        assert resp["Location"] == reverse("procurement:invoicedispute_detail",
                                           args=[invoice_dispute_open_a.pk]), body
        assert _invoice_dispute_state(invoice_dispute_open_a) == before, body

    # L44 pair: a real resolution settles it — padded, because the strip above is a tolerance for
    # a genuine choice, not a way past the membership check.
    resp = client_a.post(url, {"resolution": " short_pay ", "resolution_note": "Paid net."})
    assert resp.status_code == 302
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "resolved"
    assert invoice_dispute_open_a.resolution == "short_pay"
    assert invoice_dispute_open_a.resolved_at is not None


def test_invoice_approve_without_a_chart_of_accounts_posts_nothing(
        client_a, invoice_pending_a):
    """A missing GL account is a CONFIGURATION fault, not a refusal — and the whole posting must
    roll back rather than leave a Bill with no entry.

    Without ``invoice_chart_a`` there is no expense account in the workspace, so ``approve()``
    raises ``ValidationError`` inside the view: the message is shown, the invoice is STILL
    pending approval, and ZERO ``Bill`` / ``JournalEntry`` rows exist (L35).
    """
    from apps.accounting.models import Bill, JournalEntry
    assert invoice_pending_a.status == "pending_approval"

    resp = client_a.post(reverse("procurement:supplierinvoice_approve",
                                 args=[invoice_pending_a.pk]))
    assert resp.status_code == 302
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "pending_approval"
    assert invoice_pending_a.bill_id is None
    assert invoice_pending_a.journal_entry_id is None
    assert Bill.objects.count() == 0
    assert JournalEntry.objects.count() == 0


def test_invoice_approve_with_a_chart_posts_once_and_only_once(
        client_a, invoice_pending_a, invoice_chart_a):
    """L44 pair for the configuration fault above — and the double-submit guard.

    With the chart configured the approval posts one balanced entry and one bill; a SECOND POST
    (a double click, a back button) finds ``journal_entry_id`` already set and no-ops rather than
    minting a second bill for the same invoice.
    """
    from apps.accounting.models import Bill, JournalEntry

    resp = client_a.post(reverse("procurement:supplierinvoice_approve",
                                 args=[invoice_pending_a.pk]))
    assert resp.status_code == 302
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "approved"
    assert invoice_pending_a.bill_id is not None
    assert invoice_pending_a.journal_entry_id is not None
    assert Bill.objects.count() == 1
    assert JournalEntry.objects.count() == 1
    entry_id, bill_id = invoice_pending_a.journal_entry_id, invoice_pending_a.bill_id

    assert client_a.post(reverse("procurement:supplierinvoice_approve",
                                 args=[invoice_pending_a.pk])).status_code == 302
    invoice_pending_a.refresh_from_db()
    assert (invoice_pending_a.journal_entry_id, invoice_pending_a.bill_id) == (entry_id, bill_id)
    assert Bill.objects.count() == 1
    assert JournalEntry.objects.count() == 1


def test_invoice_raise_dispute_needs_an_open_variance(
        db, invoice_blocked_a, invoice_variance_block_a):
    """A dispute with nothing to point at cannot be answered, so ``raise_dispute()`` refuses a
    blocked invoice that carries no OPEN variance rather than moving it to ``disputed`` anyway."""
    invoice_variance_block_a.resolution = "accepted"
    invoice_variance_block_a.save(update_fields=["resolution"])
    assert invoice_blocked_a.raise_dispute() is False
    invoice_blocked_a.refresh_from_db()
    assert invoice_blocked_a.status == "blocked"

    # L44 pair: one open variance is all it needs.
    invoice_variance_block_a.resolution = "open"
    invoice_variance_block_a.save(update_fields=["resolution"])
    assert invoice_blocked_a.raise_dispute() is True
    invoice_blocked_a.refresh_from_db()
    assert invoice_blocked_a.status == "disputed"


def test_invoice_line_create_without_a_parent_makes_no_orphan(
        client_a, invoice_draft_a, gl_expense_a):
    """A line with no header is an orphan row, so the create route REQUIRES ``?invoice=``.
    A missing, junk or over-range pk redirects to the register and writes nothing — and the real
    pk still works (L44)."""
    counts = _invoice_counts()
    url = reverse("procurement:supplierinvoiceline_create")

    for query in ("", "?invoice=", "?invoice=abc", "?invoice=²",
                  "?invoice=999999999999999999999", "?invoice=0"):
        resp = client_a.post(url + query,
                             _invoice_line_payload(gl_account=str(gl_expense_a.pk),
                                                   description="Orphan"))
        assert resp.status_code == 302, query
        assert resp["Location"] == reverse("procurement:supplierinvoice_list"), query
    assert _invoice_counts() == counts
    assert not SupplierInvoiceLine.objects.filter(description="Orphan").exists()

    resp = client_a.post(url + f"?invoice={invoice_draft_a.pk}",
                         _invoice_line_payload(gl_account=str(gl_expense_a.pk),
                                               description="Parented"))
    assert resp.status_code == 302
    assert SupplierInvoiceLine.objects.get(description="Parented").invoice_id == invoice_draft_a.pk


def test_invoice_line_writes_are_refused_once_the_header_is_posted(
        client_a, invoice_pending_a, gl_expense_a):
    """Past ``EDITABLE_STATUSES`` the header's bill is (or is about to be) posted, so adding,
    editing or removing a line would silently rewrite a total the GL has already booked. All
    three routes refuse with a message and a redirect, and the line survives."""
    line = invoice_pending_a.lines.first()
    before = _invoice_line_state(line)
    counts = _invoice_counts()

    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_pending_a.pk}",
        _invoice_line_payload(gl_account=str(gl_expense_a.pk), description="Late line"))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_pending_a.pk])

    resp = client_a.post(reverse("procurement:supplierinvoiceline_edit", args=[line.pk]),
                         _invoice_line_payload(gl_account=str(gl_expense_a.pk),
                                               description="Rewritten"))
    assert resp.status_code == 302
    resp = client_a.post(reverse("procurement:supplierinvoiceline_delete", args=[line.pk]))
    assert resp.status_code == 302

    assert _invoice_line_state(line) == before
    assert _invoice_counts() == counts


def test_invoice_settled_variance_cannot_be_re_accepted(
        client_a, invoice_variance_accepted_a, invoice_variance_block_a):
    """``accept()`` is a one-way decision. An already-accepted exception is refused with a
    message rather than re-stamped, and the still-open one accepts normally (L44)."""
    before = _invoice_variance_state(invoice_variance_accepted_a)
    resp = client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_accepted_a.pk]), {"note": "again"})
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:matchvariance_detail",
                                       args=[invoice_variance_accepted_a.pk])
    assert _invoice_variance_state(invoice_variance_accepted_a) == before

    # A note over 500 characters is refused too — a redirect with a message, not a 500.
    resp = client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_block_a.pk]), {"note": "x" * 501})
    assert resp.status_code == 302
    invoice_variance_block_a.refresh_from_db()
    assert invoice_variance_block_a.resolution == "open"

    resp = client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_block_a.pk]), {"note": "agreed"})
    assert resp.status_code == 302
    invoice_variance_block_a.refresh_from_db()
    assert invoice_variance_block_a.resolution == "accepted"


def test_invoice_posted_and_terminal_invoices_refuse_destructive_verbs(
        client_a, invoice_paid_a, invoice_blocked_a, invoice_draft_a):
    """A paid invoice is TERMINAL: it cannot be edited, deleted, re-matched, voided or re-paid,
    and a blocked one cannot be deleted either (void or reverse is the honest route).

    Every refusal is a redirect with a message; the rows and the row count are untouched.
    """
    before_paid = _invoice_state(invoice_paid_a)
    before_blocked = _invoice_state(invoice_blocked_a)
    counts = _invoice_counts()

    for name in ("procurement:supplierinvoice_delete", "procurement:supplierinvoice_match",
                 "procurement:supplierinvoice_void", "procurement:supplierinvoice_mark_paid",
                 "procurement:supplierinvoice_submit",
                 "procurement:supplierinvoice_schedule"):
        resp = client_a.post(reverse(name, args=[invoice_paid_a.pk]), {"reason": "because"})
        assert resp.status_code == 302, name
    assert client_a.get(reverse("procurement:supplierinvoice_edit",
                                args=[invoice_paid_a.pk])).status_code == 302

    assert client_a.post(reverse("procurement:supplierinvoice_delete",
                                 args=[invoice_blocked_a.pk])).status_code == 302

    assert _invoice_state(invoice_paid_a) == before_paid
    assert _invoice_state(invoice_blocked_a) == before_blocked
    assert _invoice_counts() == counts

    # L44 pair: a DRAFT invoice is deletable and voidable, so the guards did not break the verbs.
    assert client_a.post(reverse("procurement:supplierinvoice_delete",
                                 args=[invoice_draft_a.pk])).status_code == 302
    assert not SupplierInvoice.objects.filter(pk=invoice_draft_a.pk).exists()


def test_invoice_void_keeps_a_posted_invoice_out_of_reach(
        client_a, invoice_pending_a, invoice_chart_a, invoice_captured_a):
    """Once an invoice carries a journal entry it is reversed, never voided — voiding would mark
    the document withdrawn while the GL liability stood with nothing to offset it."""
    assert client_a.post(reverse("procurement:supplierinvoice_approve",
                                 args=[invoice_pending_a.pk])).status_code == 302
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.journal_entry_id is not None

    assert client_a.post(reverse("procurement:supplierinvoice_void",
                                 args=[invoice_pending_a.pk]),
                         {"reason": "changed my mind"}).status_code == 302
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "approved"

    # L44 pair: an UNPOSTED invoice voids, carrying its reason.
    assert client_a.post(reverse("procurement:supplierinvoice_void",
                                 args=[invoice_captured_a.pk]),
                         {"reason": "Duplicate of SUP-7001"}).status_code == 302
    invoice_captured_a.refresh_from_db()
    assert invoice_captured_a.status == "void"
    assert "Duplicate of SUP-7001" in invoice_captured_a.notes


# ==================================================================== 7. N+1
def test_invoice_registers_hold_their_query_count(
        django_assert_max_num_queries, client_a, _invoice_bulk_a):
    """Each register ``select_related``s every hop its rows (and their ``__str__``) walk, and the
    two cumulative figures are resolved as Subqueries — so sixteen rows cost the same fixed
    number of queries as one, not one query per row per FK."""
    for name in ("procurement:supplierinvoice_list", "procurement:supplierinvoiceline_list",
                 "procurement:matchvariance_list", "procurement:invoicedispute_list"):
        with django_assert_max_num_queries(20):
            resp = client_a.get(reverse(name))
            assert resp.status_code == 200, name
            assert [str(row) for row in resp.context["object_list"]], name

    with django_assert_max_num_queries(20):
        resp = client_a.get(reverse("procurement:invoice_match_board"))
        assert resp.status_code == 200
        assert [str(group["invoice"]) for group in resp.context["groups"]]


def test_invoice_detail_holds_its_query_count_as_lines_are_added(
        django_assert_max_num_queries, client_a, invoice_draft_a, invoice_line_a,
        invoice_po_line_a, gl_expense_a):
    """``_stamp_cumulatives`` resolves both over-invoicing figures for the WHOLE document in two
    queries. Twelve extra lines — each with a chained ``po_line -> purchase_order`` hop the page
    renders — must not add twelve more."""
    for index in range(12):
        SupplierInvoiceLine.objects.create(
            invoice=invoice_draft_a, po_line=invoice_po_line_a, gl_account=gl_expense_a,
            description=f"Extra {index:02d}", quantity=Decimal("1"),
            unit_price=Decimal("1.00"))

    with django_assert_max_num_queries(32):
        resp = client_a.get(reverse("procurement:supplierinvoice_detail",
                                    args=[invoice_draft_a.pk]))
        assert resp.status_code == 200
        assert [(str(line), line.cum_invoiced, line.cum_received)
                for line in resp.context["lines"]]
