"""Procurement 6.13 Invoice & Voucher Management - view / CRUD integration flows.

Everything here goes through the real URLconf and the real templates: the four registers
(supplier invoices, invoice lines, match variances, disputes), the six computed boards (invoice
dashboard, duplicate detection, capture, payment schedule, match board, dispute aging) and every
verb POST (match, revalidate, submit, approve, override, void, reverse, schedule, mark paid,
variance accept, and the six dispute transitions).

Lane discipline followed here:

* a context key is never asserted "present" alone - it is asserted POPULATED (L41);
* every reference date derives from ``timezone.localdate()`` / ``timezone.now()``, never
  ``datetime.date.today()`` (L16);
* the page-2 cases build enough rows to actually cross the page size (15 on every paginated
  surface) - a page-2 guard is invisible at fixture size (L9);
* junk FK params, junk enum params and junk truth values render 200 with the filter skipped,
  never a 500 (L11);
* every hand-parsed money surface is probed with NaN / Infinity / garbage / over-``max_digits``,
  and a verb POST missing its prerequisite is REJECTED rather than falling through (L35);
* every register plus the two heaviest boards are wrapped in ``django_assert_max_num_queries``,
  and the supplier-invoice register additionally asserts the query count does NOT move when rows
  are added - the only assertion that actually proves the chained ``__str__`` hops are joined.

Every test is ``test_invoice_*`` and every module-level helper / fixture ``_invoice_*`` so the
next sub-module appending nearby cannot shadow them.
"""
import datetime
from decimal import Decimal

import pytest

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Bill, JournalEntry
from apps.procurement.models import (
    InvoiceDispute,
    InvoiceMatchVariance,
    SupplierInvoice,
    SupplierInvoiceLine,
)

pytestmark = pytest.mark.django_db


# ================================================================== helpers

def _invoice_today():
    """The SAME basis every 6.13 window uses - never ``date.today()`` (L16)."""
    return timezone.localdate()


def _invoice_templates(response):
    return [t.name for t in response.templates if t.name]


def _invoice_messages(response):
    """Works on a 302 too - the storage hangs off the request, not the context."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _invoice_pks(response):
    return [obj.pk for obj in response.context["object_list"]]


#: Junk every int-FK filter on every 6.13 register must SKIP rather than 500 on (L11). The
#: superscript two is the sharp one: ``isdigit()`` is True for it but ``int()`` refuses it.
_INVOICE_JUNK_INTS = ["abc", "999999999999999999999", "²", "-1", "1.5", "0"]

#: Junk money every hand-typed decimal surface must turn into a FIELD error, never a 500 (L35).
_INVOICE_JUNK_MONEY = ["NaN", "Infinity", "-Infinity", "not-a-number", "1e400",
                       "999999999999999999999999.99"]


def _invoice_header_body(vendor, **overrides):
    """A complete, valid ``SupplierInvoiceForm`` POST body (header only)."""
    body = {
        "vendor": str(vendor.pk),
        "purchase_order": "",
        "goods_receipt": "",
        "payment_term": "",
        "currency": "",
        "tax_code": "",
        "invoice_type": "standard",
        "invoice_number": "SUP-9100",
        "external_ref": "",
        "invoice_date": _invoice_today().isoformat(),
        "posting_date": "",
        "discount_base": "net_of_tax",
        "discount_grace_days": "0",
        "fx_rate": "",
        "notes": "Keyed by the view test.",
    }
    body.update(overrides)
    return body


def _invoice_formset_body(total=1, initial=0, rows=()):
    """The ``lines`` inline formset management form plus its rows.

    The prefix is ``lines`` - the child FK's ``related_name`` - so a body that hard-coded
    ``form-TOTAL_FORMS`` would post no ManagementForm at all and could never validate.
    """
    body = {
        "lines-TOTAL_FORMS": str(total),
        "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(rows):
        for name, value in row.items():
            body[f"lines-{index}-{name}"] = value
    return body


def _invoice_line_row(**overrides):
    """One row of the ``lines`` formset (also a complete ``SupplierInvoiceLineForm`` body)."""
    row = {
        "po_line": "",
        "receipt_line": "",
        "item": "",
        "description": "Reams of A4",
        "sku_hint": "PPR-A4",
        "uom_hint": "EA",
        "quantity": "2",
        "unit_price": "10.00",
        "tax_rate_pct": "0",
        "gl_account": "",
        "tax_code": "",
    }
    row.update(overrides)
    return row


def _invoice_dispute_body(invoice, **overrides):
    """A complete, valid ``InvoiceDisputeForm`` POST body."""
    body = {
        "invoice": str(invoice.pk),
        "invoice_line": "",
        "reason_code": "price",
        "supplier_contact": "ap@northwind.example",
        "disputed_amount": "10.00",
        "description": "Billed above the agreed contract rate.",
        "assigned_to": "",
        "due_date": (_invoice_today() + datetime.timedelta(days=10)).isoformat(),
    }
    body.update(overrides)
    return body


def _invoice_header(tenant, vendor, number, **overrides):
    """One bare SupplierInvoice header - money, number and norm are all DERIVED."""
    fields = dict(tenant=tenant, vendor=vendor, invoice_number=number,
                  invoice_date=_invoice_today())
    fields.update(overrides)
    return SupplierInvoice.objects.create(**fields)


# ================================================================== bulk fixtures (page 2, L9)

@pytest.fixture
def _invoice_bulk_headers(db, tenant_a, invoice_vendor_a):
    """18 extra invoices - enough to cross the 15-row register page size on its own."""
    return [_invoice_header(tenant_a, invoice_vendor_a, f"BULK-{i:03d}") for i in range(18)]


@pytest.fixture
def _invoice_bulk_lines(db, _invoice_bulk_headers):
    """18 lines, one per bulk header - the line register's page-2 population."""
    return [SupplierInvoiceLine.objects.create(
        invoice=header, description=f"Bulk line {index:02d}", sku_hint="BULK",
        quantity=Decimal("1"), unit_price=Decimal("5.00"))
        for index, header in enumerate(_invoice_bulk_headers)]


@pytest.fixture
def _invoice_bulk_variances(db, _invoice_bulk_headers):
    """18 variances spread over 18 invoices - page 2 on BOTH the register and the match board
    (the board's paginated unit is the invoice, so one variance each is what crosses it)."""
    return [InvoiceMatchVariance.objects.create(
        tenant=header.tenant, invoice=header, variance_type="price", basis="po",
        expected_value=Decimal("10.0000"), actual_value=Decimal("11.0000"),
        outcome="warn", resolution="open", message=f"Bulk exception {index:02d}")
        for index, header in enumerate(_invoice_bulk_headers)]


@pytest.fixture
def _invoice_bulk_disputes(db, tenant_a, admin_user, _invoice_bulk_headers):
    """18 OPEN disputes - page 2 on the register AND on the aging board (all in the 0-7 bucket,
    because ``age_bucket`` measures age since ``raised_at``, not time to the due date)."""
    return [InvoiceDispute.objects.create(
        tenant=tenant_a, invoice=header, reason_code="price",
        disputed_amount=Decimal("0.00"), raised_by=admin_user,
        description=f"Bulk argument {index:02d}")
        for index, header in enumerate(_invoice_bulk_headers)]


@pytest.fixture
def _invoice_bulk_duplicate_pairs(db, tenant_a, invoice_vendor_a):
    """Nine PAIRS sharing a normalised number, a vendor, a total and a date.

    Each member of a pair scores four reasons against the other, so the board reports 18 groups -
    three more than its 15-per-page slice.
    """
    pairs = []
    for index in range(9):
        first = _invoice_header(tenant_a, invoice_vendor_a, f"DUP-{index:03d}")
        second = _invoice_header(tenant_a, invoice_vendor_a, f"dup {index:03d}")
        pairs.append((first, second))
    return pairs


# =================================================================================================
# SupplierInvoice register
# =================================================================================================

def test_invoice_list_renders_contract_context(client_a, invoice_vendor_a, invoice_draft_a,
                                               invoice_line_a, invoice_blocked_a,
                                               invoice_pending_a, invoice_paid_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_list"))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/supplierinvoice/list.html"
            in _invoice_templates(resp))
    assert set(_invoice_pks(resp)) == {invoice_draft_a.pk, invoice_blocked_a.pk,
                                       invoice_pending_a.pk, invoice_paid_a.pk}
    ctx = resp.context
    assert ctx["q"] == ""
    assert dict(ctx["status_choices"])["pending_approval"] == "Pending Approval"
    assert dict(ctx["match_status_choices"])["matched"]
    assert dict(ctx["source_choices"])["manual"]
    assert dict(ctx["invoice_type_choices"])["credit_memo"]
    assert [v.pk for v in ctx["vendors"]] == [invoice_vendor_a.pk]
    assert ctx["stats"] == {"total": 4, "blocked": 1, "disputed": 0,
                            "pending_approval": 1, "overdue": 0}


def test_invoice_list_search_narrows_rows_but_not_stats(client_a, invoice_draft_a,
                                                        invoice_blocked_a, invoice_pending_a):
    url = reverse("procurement:supplierinvoice_list")

    by_supplier_number = client_a.get(url, {"q": "SUP-7003"})
    assert _invoice_pks(by_supplier_number) == [invoice_blocked_a.pk]
    assert by_supplier_number.context["q"] == "SUP-7003"
    # The stat strip describes the WORKSPACE, so a search must not move it.
    assert by_supplier_number.context["stats"]["total"] == 3

    by_own_number = client_a.get(url, {"q": invoice_draft_a.number})
    assert _invoice_pks(by_own_number) == [invoice_draft_a.pk]

    by_norm = client_a.get(url, {"q": "SUP7001"})
    assert _invoice_pks(by_norm) == [invoice_draft_a.pk]

    by_vendor = client_a.get(url, {"q": "Northwind"})
    assert len(_invoice_pks(by_vendor)) == 3


def test_invoice_list_every_filter_narrows(client_a, invoice_draft_a, invoice_blocked_a,
                                           invoice_pending_a, invoice_credit_memo_a,
                                           invoice_vendor_a):
    url = reverse("procurement:supplierinvoice_list")

    by_status = client_a.get(url, {"status": "blocked"})
    assert _invoice_pks(by_status) == [invoice_blocked_a.pk]

    by_match = client_a.get(url, {"match_status": "matched"})
    assert _invoice_pks(by_match) == [invoice_pending_a.pk]

    by_source = client_a.get(url, {"source": "manual"})
    assert len(_invoice_pks(by_source)) == 4

    by_type = client_a.get(url, {"invoice_type": "credit_memo"})
    assert _invoice_pks(by_type) == [invoice_credit_memo_a.pk]

    by_vendor = client_a.get(url, {"vendor": str(invoice_vendor_a.pk)})
    assert len(_invoice_pks(by_vendor)) == 4


@pytest.mark.parametrize("junk", _INVOICE_JUNK_INTS)
def test_invoice_list_junk_vendor_param_renders_the_full_register(client_a, invoice_draft_a,
                                                                  invoice_blocked_a, junk):
    resp = client_a.get(reverse("procurement:supplierinvoice_list"), {"vendor": junk})
    assert resp.status_code == 200
    # Skipped, not applied: a value that cannot be a pk is not a narrowing request (L11).
    assert set(_invoice_pks(resp)) == {invoice_draft_a.pk, invoice_blocked_a.pk}


def test_invoice_list_junk_enum_params_fall_back_to_the_full_list(client_a, invoice_draft_a,
                                                                  invoice_blocked_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_list"),
                        {"status": "nope", "match_status": "??", "source": "ocr-ish",
                         "invoice_type": "not-a-type"})
    assert resp.status_code == 200
    assert set(_invoice_pks(resp)) == {invoice_draft_a.pk, invoice_blocked_a.pk}


def test_invoice_list_page_two_and_past_the_end(client_a, _invoice_bulk_headers):
    url = reverse("procurement:supplierinvoice_list")

    page_one = client_a.get(url)
    assert len(_invoice_pks(page_one)) == 15
    assert page_one.context["page_obj"].paginator.num_pages == 2

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(_invoice_pks(page_two)) == 3
    assert set(_invoice_pks(page_one)).isdisjoint(_invoice_pks(page_two))

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == 2

    junk_page = client_a.get(url, {"page": "abc"})
    assert junk_page.status_code == 200
    assert junk_page.context["page_obj"].number == 1


def test_invoice_list_query_budget(client_a, _invoice_bulk_headers, invoice_draft_a,
                                   invoice_line_a, django_assert_max_num_queries):
    """15 rows whose ``__str__`` and columns walk vendor / order / receipt / currency / term."""
    with django_assert_max_num_queries(14):
        resp = client_a.get(reverse("procurement:supplierinvoice_list"))
    assert len(_invoice_pks(resp)) == 15


def test_invoice_list_query_count_does_not_grow_with_rows(client_a, tenant_a, invoice_vendor_a,
                                                          invoice_draft_a, invoice_line_a):
    """The real N+1 assertion: adding rows must not add queries (chained FK hops included)."""
    url = reverse("procurement:supplierinvoice_list")
    with CaptureQueriesContext(connection) as small:
        client_a.get(url)

    for index in range(10):
        _invoice_header(tenant_a, invoice_vendor_a, f"GROW-{index:03d}",
                        purchase_order=invoice_draft_a.purchase_order,
                        goods_receipt=invoice_draft_a.goods_receipt,
                        payment_term=invoice_draft_a.payment_term,
                        currency=invoice_draft_a.currency)

    with CaptureQueriesContext(connection) as large:
        client_a.get(url)

    assert len(large.captured_queries) == len(small.captured_queries)


def test_invoice_list_never_shows_another_workspace(client_a, invoice_draft_a, invoice_b):
    resp = client_a.get(reverse("procurement:supplierinvoice_list"))
    assert _invoice_pks(resp) == [invoice_draft_a.pk]
    assert invoice_b.pk not in _invoice_pks(resp)


# =================================================================================================
# SupplierInvoice detail
# =================================================================================================

def test_invoice_detail_renders_every_contract_key(client_a, invoice_draft_a, invoice_line_a,
                                                   invoice_dispute_open_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_detail",
                                args=[invoice_draft_a.pk]))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/supplierinvoice/detail.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"].pk == invoice_draft_a.pk
    assert [line.pk for line in ctx["lines"]] == [invoice_line_a.pk]
    # ``_stamp_cumulatives`` runs once for the whole document, not once per row.
    assert ctx["lines"][0].cum_invoiced == Decimal("10.0000")
    assert ctx["lines"][0].cum_received == Decimal("10.0000")
    assert list(ctx["variances"]) == []
    assert [d.pk for d in ctx["disputes"]] == [invoice_dispute_open_a.pk]
    assert ctx["bill"] is None and ctx["journal_entry"] is None
    assert ctx["allowed_transitions"] == ["parked", "captured", "void"]
    assert ctx["is_locked"] is False
    assert ctx["discount"] == {
        "base_amount": Decimal("250.00"),
        "amount": Decimal("5.00"),
        "payable_if_discounted": Decimal("245.00"),
        "days_to_discount": 10,
        "annualised_pct": Decimal("36.73"),
        "capturable": True,
    }
    assert set(ctx["tolerances"]) == {
        "price_pct_upper", "price_pct_lower", "price_abs_upper", "qty_pct_upper",
        "qty_abs_upper", "qty_pct_upper_no_grn", "qty_pct_lower", "total_pct", "total_abs",
        "fx_pct", "tax_abs", "duplicate_window_days", "duplicate_amount_tol_pct",
        "discount_annualisation_days"}
    assert ctx["tolerances"]["price_pct_upper"] == Decimal("2.00")
    assert (ctx["can_edit"], ctx["can_submit"], ctx["can_match"]) == (True, True, True)
    assert (ctx["can_override"], ctx["can_approve"], ctx["can_reverse"]) == (False, False, False)
    assert ctx["can_void"] is True
    assert ctx["is_admin"] is True


def test_invoice_detail_duplicate_panel_is_populated(client_a, invoice_draft_a,
                                                     invoice_duplicate_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_detail",
                                args=[invoice_draft_a.pk]))

    candidates = resp.context["duplicate_candidates"]
    assert [entry["invoice"].pk for entry in candidates] == [invoice_duplicate_a.pk]
    # A candidate is only reported once it scores at least three independent reasons.
    assert len(candidates[0]["reasons"]) == 4


def test_invoice_detail_flags_mirror_a_locked_invoice(client_a, invoice_paid_a):
    ctx = client_a.get(reverse("procurement:supplierinvoice_detail",
                               args=[invoice_paid_a.pk])).context
    assert ctx["is_locked"] is True
    assert ctx["can_edit"] is False
    assert ctx["can_match"] is False
    assert ctx["can_void"] is False
    assert ctx["allowed_transitions"] == ["reversed"]


def test_invoice_detail_hides_admin_verbs_from_a_member(member_client, invoice_blocked_a,
                                                        invoice_variance_block_a):
    ctx = member_client.get(reverse("procurement:supplierinvoice_detail",
                                    args=[invoice_blocked_a.pk])).context
    assert ctx["is_admin"] is False
    assert ctx["can_override"] is False
    assert ctx["can_approve"] is False
    assert ctx["can_void"] is False
    # ...but the ordinary verbs stay on offer, which is the split the routes enforce.
    assert ctx["can_match"] is True


def test_invoice_detail_cross_tenant_pk_is_404(client_a, invoice_b):
    resp = client_a.get(reverse("procurement:supplierinvoice_detail", args=[invoice_b.pk]))
    assert resp.status_code == 404
    invoice_b.refresh_from_db()
    assert invoice_b.status == "draft"


def test_invoice_detail_query_budget(client_a, invoice_draft_a, invoice_line_a,
                                     invoice_dispute_open_a, invoice_duplicate_a,
                                     django_assert_max_num_queries):
    with django_assert_max_num_queries(20):
        resp = client_a.get(reverse("procurement:supplierinvoice_detail",
                                    args=[invoice_draft_a.pk]))
    assert resp.status_code == 200


# =================================================================================================
# SupplierInvoice create / edit / delete
# =================================================================================================

def test_invoice_create_get_renders_form_and_line_formset(client_a, invoice_vendor_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_create"))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/supplierinvoice/form.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"] is None
    assert ctx["is_edit"] is False
    assert ctx["title"] == "New supplier invoice"
    assert ctx["submit_label"] == "Create invoice"
    assert ctx["cancel_url"] == reverse("procurement:supplierinvoice_list")
    assert ctx["line_formset"].prefix == "lines"
    # Every system-owned column is absent from the header form.
    assert "status" not in ctx["form"].fields
    assert "number" not in ctx["form"].fields
    assert "total" not in ctx["form"].fields
    # The workspace's own vendor IS offered.
    assert invoice_vendor_a.pk in [v.pk for v in ctx["form"].fields["vendor"].queryset]


def test_invoice_create_post_saves_with_the_request_tenant(client_a, tenant_a, invoice_vendor_a):
    body = _invoice_header_body(invoice_vendor_a)
    body.update(_invoice_formset_body(rows=[_invoice_line_row()]))

    resp = client_a.post(reverse("procurement:supplierinvoice_create"), body)

    obj = SupplierInvoice.objects.get(invoice_number="SUP-9100")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail", args=[obj.pk])
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("SIV-")
    assert obj.status == "draft"
    # Derived, never posted.
    assert obj.invoice_number_norm == "SUP9100"
    assert obj.lines.count() == 1
    assert obj.subtotal == Decimal("20.00")
    assert obj.total == Decimal("20.00")
    assert any("saved" in m for m in _invoice_messages(resp))


def test_invoice_create_post_invalid_rerenders_without_saving(client_a, invoice_vendor_a):
    body = _invoice_header_body(invoice_vendor_a, invoice_number="")
    body.update(_invoice_formset_body(rows=[_invoice_line_row()]))

    resp = client_a.post(reverse("procurement:supplierinvoice_create"), body)

    assert resp.status_code == 200
    assert resp.context["form"].errors["invoice_number"]
    assert not SupplierInvoice.objects.filter(notes="Keyed by the view test.").exists()


def test_invoice_create_post_with_a_tenant_b_vendor_is_a_field_error(client_a, invoice_vendor_b):
    body = _invoice_header_body(invoice_vendor_b)
    body.update(_invoice_formset_body(rows=[_invoice_line_row()]))

    resp = client_a.post(reverse("procurement:supplierinvoice_create"), body)

    assert resp.status_code == 200
    assert resp.context["form"].errors["vendor"]
    assert not SupplierInvoice.objects.filter(invoice_number="SUP-9100").exists()


def test_invoice_create_post_with_another_vendors_order_is_a_field_error(
        client_a, invoice_vendor_a, invoice_po_other_a):
    body = _invoice_header_body(invoice_vendor_a,
                                purchase_order=str(invoice_po_other_a.pk))
    body.update(_invoice_formset_body(rows=[_invoice_line_row()]))

    resp = client_a.post(reverse("procurement:supplierinvoice_create"), body)

    assert resp.status_code == 200
    assert ("That purchase order belongs to a different vendor."
            in resp.context["form"].errors["purchase_order"])
    assert not SupplierInvoice.objects.filter(invoice_number="SUP-9100").exists()


@pytest.mark.parametrize("junk", _INVOICE_JUNK_MONEY)
def test_invoice_create_post_junk_fx_rate_is_a_field_error(client_a, invoice_vendor_a, junk):
    body = _invoice_header_body(invoice_vendor_a, fx_rate=junk)
    body.update(_invoice_formset_body(rows=[_invoice_line_row()]))

    resp = client_a.post(reverse("procurement:supplierinvoice_create"), body)

    assert resp.status_code == 200            # a friendly refusal, never a 500 (L35)
    assert resp.context["form"].errors["fx_rate"]
    assert not SupplierInvoice.objects.filter(invoice_number="SUP-9100").exists()


def test_invoice_create_post_with_a_tenant_b_line_fk_is_rejected(client_a, invoice_vendor_a,
                                                                 invoice_item_b):
    body = _invoice_header_body(invoice_vendor_a)
    body.update(_invoice_formset_body(
        rows=[_invoice_line_row(item=str(invoice_item_b.pk))]))

    resp = client_a.post(reverse("procurement:supplierinvoice_create"), body)

    assert resp.status_code == 200
    assert resp.context["line_formset"].forms[0].errors["item"]
    assert not SupplierInvoice.objects.filter(invoice_number="SUP-9100").exists()


def test_invoice_edit_get_prefills_the_instance(client_a, invoice_captured_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_edit",
                                args=[invoice_captured_a.pk]))

    assert resp.status_code == 200
    ctx = resp.context
    assert ctx["obj"].pk == invoice_captured_a.pk
    assert ctx["is_edit"] is True
    assert ctx["title"] == "Edit supplier invoice"
    assert ctx["submit_label"] == "Save changes"
    assert ctx["cancel_url"] == reverse("procurement:supplierinvoice_detail",
                                        args=[invoice_captured_a.pk])
    assert ctx["form"].initial["invoice_number"] == "SUP-7002"


def test_invoice_edit_post_updates_the_header(client_a, invoice_captured_a, invoice_vendor_a):
    body = _invoice_header_body(invoice_vendor_a, invoice_number="SUP-7002",
                                invoice_type="service",
                                posting_date=_invoice_today().isoformat(),
                                external_ref="AMENDED")
    # TOTAL_FORMS=0: a header-only edit posts NO line rows. Declaring one row and then omitting
    # every ``lines-0-*`` key is not an empty row, it is an INCOMPLETE one - ``quantity`` /
    # ``unit_price`` / ``tax_rate_pct`` carry model defaults as their initial, so the extra form
    # reads as changed and comes back "This field is required" (the rendered page posts those
    # inputs, so a real browser never sends this shape).
    body.update(_invoice_formset_body(total=0, initial=0))

    resp = client_a.post(reverse("procurement:supplierinvoice_edit",
                                 args=[invoice_captured_a.pk]), body)

    invoice_captured_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_captured_a.external_ref == "AMENDED"
    assert invoice_captured_a.status == "captured"       # the verbs own the status, not the form


def test_invoice_edit_refuses_a_non_editable_invoice(client_a, invoice_pending_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_edit",
                                args=[invoice_pending_a.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_pending_a.pk])
    assert any("only a draft, parked or captured invoice can be edited"
               in m for m in _invoice_messages(resp))


def test_invoice_edit_cross_tenant_pk_is_404(client_a, invoice_b):
    resp = client_a.get(reverse("procurement:supplierinvoice_edit", args=[invoice_b.pk]))
    assert resp.status_code == 404


def test_invoice_delete_get_is_405_and_deletes_nothing(client_a, invoice_draft_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_delete",
                                args=[invoice_draft_a.pk]))

    assert resp.status_code == 405
    assert SupplierInvoice.objects.filter(pk=invoice_draft_a.pk).exists()


def test_invoice_delete_post_removes_the_row(client_a, invoice_draft_a, invoice_line_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_delete",
                                 args=[invoice_draft_a.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_list")
    assert not SupplierInvoice.objects.filter(pk=invoice_draft_a.pk).exists()
    # The lines cascade with the header.
    assert not SupplierInvoiceLine.objects.filter(pk=invoice_line_a.pk).exists()


def test_invoice_delete_refuses_a_non_editable_invoice(client_a, invoice_pending_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_delete",
                                 args=[invoice_pending_a.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_pending_a.pk])
    assert any("void or reverse it instead" in m for m in _invoice_messages(resp))
    assert SupplierInvoice.objects.filter(pk=invoice_pending_a.pk).exists()


def test_invoice_delete_cross_tenant_pk_is_404(client_a, invoice_b):
    resp = client_a.post(reverse("procurement:supplierinvoice_delete", args=[invoice_b.pk]))
    assert resp.status_code == 404
    assert SupplierInvoice.objects.filter(pk=invoice_b.pk).exists()


# =================================================================================================
# SupplierInvoice verbs
# =================================================================================================

def test_invoice_match_post_runs_the_three_way_match(client_a, invoice_draft_a, invoice_line_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_match",
                                 args=[invoice_draft_a.pk]))

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_draft_a.pk])
    assert invoice_draft_a.status == "pending_approval"
    assert invoice_draft_a.match_status == "matched"
    assert invoice_draft_a.match_basis == "quantity"
    assert any("Match complete" in m for m in _invoice_messages(resp))


def test_invoice_match_get_is_405_and_changes_nothing(client_a, invoice_draft_a,
                                                      invoice_line_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_match", args=[invoice_draft_a.pk]))

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 405
    assert invoice_draft_a.status == "draft"
    assert invoice_draft_a.match_status == "not_run"


def test_invoice_match_refuses_a_locked_invoice(client_a, invoice_paid_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_match", args=[invoice_paid_a.pk]))

    invoice_paid_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_paid_a.status == "paid"
    assert any("already posted" in m for m in _invoice_messages(resp))


def test_invoice_match_cross_tenant_pk_is_404(client_a, invoice_b):
    resp = client_a.post(reverse("procurement:supplierinvoice_match", args=[invoice_b.pk]))
    assert resp.status_code == 404
    invoice_b.refresh_from_db()
    assert invoice_b.match_status == "not_run"


def test_invoice_submit_captures_then_sends_a_draft_for_approval(client_a, invoice_draft_a,
                                                                 invoice_line_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_submit",
                                 args=[invoice_draft_a.pk]))

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_draft_a.status == "pending_approval"
    assert any("sent for approval" in m for m in _invoice_messages(resp))


def test_invoice_submit_refuses_a_paid_invoice(client_a, invoice_paid_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_submit", args=[invoice_paid_a.pk]))

    invoice_paid_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_paid_a.status == "paid"
    assert any("cannot be sent for approval" in m for m in _invoice_messages(resp))


def test_invoice_approve_posts_a_bill_and_a_balanced_journal_entry(client_a, invoice_pending_a,
                                                                   invoice_chart_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_approve",
                                 args=[invoice_pending_a.pk]))

    invoice_pending_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_pending_a.status == "approved"
    assert invoice_pending_a.bill_id is not None
    assert invoice_pending_a.journal_entry_id is not None
    assert invoice_pending_a.approved_at is not None
    entry = invoice_pending_a.journal_entry
    lines = list(entry.lines.all())
    assert lines, "the posting must actually write journal lines"
    assert sum(line.debit for line in lines) == sum(line.credit for line in lines)
    assert invoice_pending_a.bill.lines.count() == invoice_pending_a.lines.count()


def test_invoice_approve_without_a_chart_of_accounts_posts_nothing(client_a, invoice_pending_a):
    """L35 - an ABSENT prerequisite is refused, never fallen through to a half posting."""
    bills_before = Bill.objects.count()
    entries_before = JournalEntry.objects.count()

    resp = client_a.post(reverse("procurement:supplierinvoice_approve",
                                 args=[invoice_pending_a.pk]))

    invoice_pending_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_pending_a.status == "pending_approval"
    assert invoice_pending_a.bill_id is None
    assert invoice_pending_a.journal_entry_id is None
    assert Bill.objects.count() == bills_before
    assert JournalEntry.objects.count() == entries_before
    assert any("GL account is configured" in m for m in _invoice_messages(resp))


def test_invoice_approve_twice_does_not_post_a_second_entry(client_a, invoice_pending_a,
                                                            invoice_chart_a):
    url = reverse("procurement:supplierinvoice_approve", args=[invoice_pending_a.pk])
    client_a.post(url)
    invoice_pending_a.refresh_from_db()
    first_entry = invoice_pending_a.journal_entry_id
    entries_after_first = JournalEntry.objects.count()

    client_a.post(url)

    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.journal_entry_id == first_entry
    assert JournalEntry.objects.count() == entries_after_first


def test_invoice_override_accepts_every_blocking_variance(client_a, invoice_blocked_a,
                                                          invoice_variance_block_a,
                                                          invoice_variance_warn_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_override",
                                 args=[invoice_blocked_a.pk]))

    invoice_blocked_a.refresh_from_db()
    invoice_variance_block_a.refresh_from_db()
    invoice_variance_warn_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_blocked_a.status == "pending_approval"
    assert invoice_variance_block_a.resolution == "accepted"
    # A warning was never blocking, so the override leaves it alone.
    assert invoice_variance_warn_a.resolution == "open"
    assert "Overridden by" in invoice_blocked_a.match_notes


def test_invoice_override_refuses_an_unblocked_invoice(client_a, invoice_draft_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_override",
                                 args=[invoice_draft_a.pk]))

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_draft_a.status == "draft"
    assert any("cannot be overridden" in m for m in _invoice_messages(resp))


def test_invoice_void_keeps_the_reason_on_the_record(client_a, invoice_draft_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_void", args=[invoice_draft_a.pk]),
                         {"reason": "Keyed twice from the same paper."})

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_draft_a.status == "void"
    assert invoice_draft_a.notes.startswith("Keyed twice from the same paper.")


def test_invoice_void_refuses_a_posted_invoice(client_a, invoice_pending_a, invoice_chart_a,
                                               admin_user):
    assert invoice_pending_a.approve(admin_user) is True

    resp = client_a.post(reverse("procurement:supplierinvoice_void",
                                 args=[invoice_pending_a.pk]))

    invoice_pending_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_pending_a.status == "approved"
    assert any("cannot be voided" in m for m in _invoice_messages(resp))


def test_invoice_reverse_posts_a_mirroring_entry(client_a, invoice_pending_a, invoice_chart_a,
                                                 admin_user):
    assert invoice_pending_a.approve(admin_user) is True
    original = invoice_pending_a.journal_entry

    resp = client_a.post(reverse("procurement:supplierinvoice_reverse",
                                 args=[invoice_pending_a.pk]))

    invoice_pending_a.refresh_from_db()
    reversal = JournalEntry.objects.get(reversal_of=original)
    assert resp.status_code == 302
    assert invoice_pending_a.status == "reversed"
    assert reversal.entry_type == "reversal"
    assert (sum(line.debit for line in reversal.lines.all())
            == sum(line.credit for line in original.lines.all()))


def test_invoice_reverse_refuses_an_unposted_invoice(client_a, invoice_draft_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_reverse",
                                 args=[invoice_draft_a.pk]))

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_draft_a.status == "draft"
    assert any("cannot be reversed" in m for m in _invoice_messages(resp))


def test_invoice_schedule_and_mark_paid_move_the_invoice(client_a, invoice_pending_a,
                                                         invoice_chart_a, admin_user):
    assert invoice_pending_a.approve(admin_user) is True

    scheduled = client_a.post(reverse("procurement:supplierinvoice_schedule",
                                      args=[invoice_pending_a.pk]))
    invoice_pending_a.refresh_from_db()
    assert scheduled.status_code == 302
    assert invoice_pending_a.status == "scheduled"

    paid = client_a.post(reverse("procurement:supplierinvoice_mark_paid",
                                 args=[invoice_pending_a.pk]))
    invoice_pending_a.refresh_from_db()
    assert paid.status_code == 302
    assert invoice_pending_a.status == "paid"


def test_invoice_mark_paid_refuses_an_unscheduled_invoice(client_a, invoice_draft_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_mark_paid",
                                 args=[invoice_draft_a.pk]))

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_draft_a.status == "draft"


def test_invoice_revalidate_rematches_and_lands_on_the_variance_register(
        client_a, invoice_blocked_a, invoice_variance_block_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_revalidate"))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:matchvariance_list")
    assert any("Re-matched" in m for m in _invoice_messages(resp))


def test_invoice_revalidate_get_is_405(client_a, invoice_blocked_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_revalidate"))
    assert resp.status_code == 405


# =================================================================================================
# Duplicate detection board
# =================================================================================================

def test_invoice_duplicates_board_renders_groups_and_stats(client_a, invoice_draft_a,
                                                           invoice_duplicate_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_duplicates"))

    assert resp.status_code == 200
    assert "procurement/invoicevouchermanagement/duplicates.html" in _invoice_templates(resp)
    ctx = resp.context
    groups = list(ctx["groups"])
    assert {group["invoice"].pk for group in groups} == {invoice_draft_a.pk,
                                                         invoice_duplicate_a.pk}
    assert all(group["count"] == 1 for group in groups)
    assert all(group["candidates"][0]["reasons"] for group in groups)
    assert ctx["window_days"] == SupplierInvoice.DUPLICATE_WINDOW_DAYS
    assert ctx["stats"] == {"scanned": 2, "suspect": 2, "linked": 0}
    assert ctx["page_obj"].number == 1


def test_invoice_duplicates_board_page_two_differs(client_a, _invoice_bulk_duplicate_pairs):
    url = reverse("procurement:supplierinvoice_duplicates")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})

    first = [group["invoice"].pk for group in page_one.context["groups"]]
    second = [group["invoice"].pk for group in page_two.context["groups"]]
    assert len(first) == 15
    assert len(second) == 3
    assert set(first).isdisjoint(second)
    assert page_one.context["stats"]["suspect"] == 18

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == 2


def test_invoice_duplicates_board_never_crosses_the_workspace(client_a, invoice_draft_a,
                                                              invoice_duplicate_a, invoice_b):
    resp = client_a.get(reverse("procurement:supplierinvoice_duplicates"))
    seen = {group["invoice"].pk for group in resp.context["groups"]}
    assert invoice_b.pk not in seen


# =================================================================================================
# Capture Invoice
# =================================================================================================

def test_invoice_capture_get_renders_the_upload_stage(client_a):
    resp = client_a.get(reverse("procurement:supplierinvoice_capture"))

    assert resp.status_code == 200
    assert "procurement/invoicevouchermanagement/capture.html" in _invoice_templates(resp)
    ctx = resp.context
    assert ctx["stage"] == "upload"
    assert "document_file" in ctx["upload_form"].fields
    assert ctx["form"] is None
    assert ctx["document"] is None
    assert set(ctx["extraction"]) == {"invoice_number", "invoice_date", "due_date", "po_number",
                                      "subtotal", "tax_total", "total", "currency_code",
                                      "vendor_name"}
    assert ctx["source"] == "manual"
    assert ctx["has_text_layer"] is False
    assert ctx["title"] == "Capture Invoice"
    assert ctx["cancel_url"] == reverse("procurement:supplierinvoice_list")


def test_invoice_capture_upload_falls_back_to_manual_keying(client_a, tenant_a, settings,
                                                            tmp_path):
    """No readable text layer - the designed fallback, asserted rather than assumed."""
    settings.MEDIA_ROOT = str(tmp_path)
    upload = SimpleUploadedFile("northwind.pdf", b"%PDF-1.4 not really a pdf",
                                content_type="application/pdf")

    resp = client_a.post(reverse("procurement:supplierinvoice_capture"),
                         {"stage": "upload", "document_file": upload})

    assert resp.status_code == 200
    ctx = resp.context
    assert ctx["stage"] == "confirm"
    assert ctx["has_text_layer"] is False
    assert ctx["source"] == "manual"
    assert ctx["confidence"] == Decimal("0")
    assert ctx["warnings"], "the page must say why nothing was extracted"
    assert ctx["document"].tenant_id == tenant_a.pk
    assert ctx["form"] is not None


def test_invoice_capture_upload_rejects_a_disallowed_extension(client_a, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    upload = SimpleUploadedFile("payload.exe", b"MZ-not-a-pdf")

    resp = client_a.post(reverse("procurement:supplierinvoice_capture"),
                         {"stage": "upload", "document_file": upload})

    assert resp.status_code == 200
    assert resp.context["stage"] == "upload"
    assert resp.context["upload_form"].errors["document_file"]


def test_invoice_capture_confirm_creates_a_header_only_invoice(client_a, tenant_a,
                                                               invoice_vendor_a):
    body = _invoice_header_body(invoice_vendor_a, invoice_number="CAP-0001")

    resp = client_a.post(reverse("procurement:supplierinvoice_capture"),
                         dict(body, stage="confirm"))

    obj = SupplierInvoice.objects.get(invoice_number="CAP-0001")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail", args=[obj.pk])
    assert obj.tenant_id == tenant_a.pk
    # Provenance is stamped SERVER-side, never posted.
    assert obj.source == "manual"
    assert obj.extraction_confidence == Decimal("0.00")
    assert obj.lines.count() == 0
    assert any("captured" in m for m in _invoice_messages(resp))


def test_invoice_capture_confirm_invalid_rerenders_the_confirm_stage(client_a,
                                                                     invoice_vendor_a):
    body = _invoice_header_body(invoice_vendor_a, invoice_number="")

    resp = client_a.post(reverse("procurement:supplierinvoice_capture"),
                         dict(body, stage="confirm"))

    assert resp.status_code == 200
    assert resp.context["stage"] == "confirm"
    assert resp.context["form"].errors["invoice_number"]


def test_invoice_capture_crafted_stage_falls_back_to_upload(client_a):
    resp = client_a.post(reverse("procurement:supplierinvoice_capture"),
                         {"stage": "../../etc/passwd"})

    assert resp.status_code == 200
    assert resp.context["stage"] == "upload"


# =================================================================================================
# Invoice & Voucher dashboard
# =================================================================================================

def test_invoice_dashboard_renders_every_panel(client_a, invoice_draft_a, invoice_line_a,
                                               invoice_blocked_a, invoice_dispute_open_a,
                                               invoice_dispute_overdue_a):
    resp = client_a.get(reverse("procurement:invoicevoucher_dashboard"))

    assert resp.status_code == 200
    assert "procurement/invoicevouchermanagement/dashboard.html" in _invoice_templates(resp)
    ctx = resp.context
    assert len(ctx["tiles"]) == 9
    assert all(tile["url"] and tile["label"] and tile["icon"] for tile in ctx["tiles"])
    assert ctx["stats"]["invoices"] == 2
    assert ctx["stats"]["blocked"] == 1
    assert ctx["stats"]["open_disputes"] == 2
    assert ctx["stats"]["capturable_discount"] > Decimal("0")
    assert [row.pk for row in ctx["recent"]]
    assert [row.pk for row in ctx["blocked"]] == [invoice_blocked_a.pk]
    # ``expiring`` is the 7-day (EXPIRING_WINDOW_DAYS) slice of the capturable set, not the whole
    # of it: invoice_draft_a is on 2/10 Net 30 dated today, so its window closes in TEN days - it
    # is in ``capturable_discount`` above and deliberately NOT here yet. The populated case is
    # test_invoice_dashboard_lists_a_discount_closing_inside_the_window below.
    assert ctx["expiring"] == []
    assert {row.pk for row in ctx["open_disputes"]} == {invoice_dispute_open_a.pk,
                                                        invoice_dispute_overdue_a.pk}
    aging = {bucket["key"]: bucket["count"] for bucket in ctx["aging"]}
    assert aging["overdue"] == 1
    assert aging["0-7"] == 1
    # The label/count pairs carry a human label, never the machine key.
    assert all(bucket["label"] for bucket in ctx["aging"])


def test_invoice_dashboard_lists_a_discount_closing_inside_the_window(
        client_a, tenant_a, invoice_vendor_a, invoice_term_a, usd):
    """The populated half of ``expiring``: a 2/10 window on an invoice dated five days back closes
    in five days, which is inside the panel's seven-day horizon - and the row carries the whole
    discount panel, not just the invoice."""
    invoice = SupplierInvoice.objects.create(
        tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="SUP-EXPIRING-1",
        invoice_date=_invoice_today() - datetime.timedelta(days=5),
        payment_term=invoice_term_a, currency=usd, status="captured")
    SupplierInvoiceLine.objects.create(invoice=invoice, description="Reams of A4",
                                       quantity=Decimal("10"), unit_price=Decimal("25.00"))
    invoice.refresh_from_db()
    assert invoice.discount_date == _invoice_today() + datetime.timedelta(days=5)

    ctx = client_a.get(reverse("procurement:invoicevoucher_dashboard")).context

    entries = {entry["invoice"].pk: entry["discount"] for entry in ctx["expiring"]}
    assert list(entries) == [invoice.pk]
    assert entries[invoice.pk]["capturable"] is True
    assert entries[invoice.pk]["amount"] > Decimal("0")
    assert entries[invoice.pk]["days_to_discount"] == 5


def test_invoice_dashboard_never_counts_another_workspace(client_a, invoice_draft_a, invoice_b,
                                                          invoice_dispute_b):
    ctx = client_a.get(reverse("procurement:invoicevoucher_dashboard")).context
    assert ctx["stats"]["invoices"] == 1
    assert ctx["stats"]["open_disputes"] == 0
    assert invoice_b.pk not in [row.pk for row in ctx["recent"]]


# =================================================================================================
# SupplierInvoiceLine register
# =================================================================================================

def test_invoice_line_list_renders_contract_context(client_a, invoice_draft_a, invoice_line_a,
                                                    invoice_item_a):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_list"))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/supplierinvoiceline/list.html"
            in _invoice_templates(resp))
    assert _invoice_pks(resp) == [invoice_line_a.pk]
    ctx = resp.context
    assert ctx["q"] == ""
    assert [i.pk for i in ctx["invoices"]] == [invoice_draft_a.pk]
    assert [i.pk for i in ctx["items"]] == [invoice_item_a.pk]
    assert ctx["stats"] == {"lines": 1, "matched": 0, "unmatched": 1, "non_po": 0}
    # The two cumulative figures arrive as Subquery annotations, not per-row aggregates.
    row = ctx["object_list"][0]
    assert row.cum_invoiced_qty == Decimal("10.0000")
    assert row.cum_received_qty == Decimal("10.0000")


def test_invoice_line_list_search_and_filters_narrow(client_a, invoice_draft_a, invoice_line_a,
                                                     invoice_captured_a):
    other = SupplierInvoiceLine.objects.create(
        invoice=invoice_captured_a, description="Monthly cleaning", sku_hint="SVC-1",
        quantity=Decimal("1"), unit_price=Decimal("99.00"))
    url = reverse("procurement:supplierinvoiceline_list")

    by_text = client_a.get(url, {"q": "cleaning"})
    assert _invoice_pks(by_text) == [other.pk]

    by_header_number = client_a.get(url, {"q": invoice_draft_a.number})
    assert _invoice_pks(by_header_number) == [invoice_line_a.pk]

    by_invoice = client_a.get(url, {"invoice": str(invoice_captured_a.pk)})
    assert _invoice_pks(by_invoice) == [other.pk]

    by_po_line = client_a.get(url, {"po_line": str(invoice_line_a.po_line_id)})
    assert _invoice_pks(by_po_line) == [invoice_line_a.pk]


def test_invoice_line_list_gl_missing_filter_and_junk_truth_value(client_a, invoice_draft_a,
                                                                  invoice_line_a,
                                                                  invoice_captured_a,
                                                                  gl_expense_a):
    coded = SupplierInvoiceLine.objects.create(
        invoice=invoice_captured_a, description="Coded line", gl_account=gl_expense_a,
        quantity=Decimal("1"), unit_price=Decimal("1.00"))
    url = reverse("procurement:supplierinvoiceline_list")

    missing = client_a.get(url, {"gl_missing": "1"})
    assert _invoice_pks(missing) == [invoice_line_a.pk]

    present = client_a.get(url, {"gl_missing": "0"})
    assert _invoice_pks(present) == [coded.pk]

    # An unrecognised truth value falls through UNFILTERED - an __isnull lookup cannot go
    # through crud_list's guard at all, so this is the only place it can be handled (L11).
    junk = client_a.get(url, {"gl_missing": "abc"})
    assert junk.status_code == 200
    assert set(_invoice_pks(junk)) == {invoice_line_a.pk, coded.pk}


@pytest.mark.parametrize("junk", _INVOICE_JUNK_INTS)
def test_invoice_line_list_junk_int_params_render_the_full_register(client_a, invoice_line_a,
                                                                    junk):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_list"),
                        {"invoice": junk, "po_line": junk, "item": junk})
    assert resp.status_code == 200
    assert _invoice_pks(resp) == [invoice_line_a.pk]


def test_invoice_line_list_page_two_and_past_the_end(client_a, _invoice_bulk_lines):
    url = reverse("procurement:supplierinvoiceline_list")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})

    assert len(_invoice_pks(page_one)) == 15
    assert len(_invoice_pks(page_two)) == 3
    assert set(_invoice_pks(page_one)).isdisjoint(_invoice_pks(page_two))

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.context["page_obj"].number == 2


def test_invoice_line_list_query_budget(client_a, _invoice_bulk_lines, invoice_line_a,
                                        django_assert_max_num_queries):
    """Rows walk invoice / currency / po_line / order / receipt_line / GRN / item / GL / tax."""
    with django_assert_max_num_queries(14):
        resp = client_a.get(reverse("procurement:supplierinvoiceline_list"))
    assert len(_invoice_pks(resp)) == 15


def test_invoice_line_list_never_shows_another_workspace(client_a, invoice_line_a,
                                                         invoice_line_b):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_list"))
    assert _invoice_pks(resp) == [invoice_line_a.pk]


def test_invoice_line_detail_renders_the_cumulative_block(client_a, invoice_line_a):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_detail",
                                args=[invoice_line_a.pk]))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/supplierinvoiceline/detail.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"].pk == invoice_line_a.pk
    assert ctx["invoice"].pk == invoice_line_a.invoice_id
    assert list(ctx["variances"]) == []
    assert ctx["cumulative"] == {"invoiced": Decimal("10.0000"),
                                 "received": Decimal("10.0000"),
                                 "ordered": Decimal("10.0000"),
                                 "remaining": Decimal("0.0000")}
    assert ctx["can_edit"] is True


def test_invoice_line_detail_cross_tenant_pk_is_404(client_a, invoice_line_b):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_detail",
                                args=[invoice_line_b.pk]))
    assert resp.status_code == 404


def test_invoice_line_create_requires_a_usable_invoice_param(client_a, invoice_draft_a,
                                                             invoice_b):
    url = reverse("procurement:supplierinvoiceline_create")
    before = SupplierInvoiceLine.objects.count()

    missing = client_a.get(url)
    junk = client_a.get(url, {"invoice": "abc"})
    foreign = client_a.get(url, {"invoice": str(invoice_b.pk)})

    for resp in (missing, junk, foreign):
        assert resp.status_code == 302
        assert resp["Location"] == reverse("procurement:supplierinvoice_list")
    assert SupplierInvoiceLine.objects.count() == before


def test_invoice_line_create_get_renders_the_form_for_its_header(client_a, invoice_draft_a):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_create"),
                        {"invoice": str(invoice_draft_a.pk)})

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/supplierinvoiceline/form.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"] is None
    assert ctx["is_edit"] is False
    assert ctx["invoice"].pk == invoice_draft_a.pk
    assert ctx["title"] == f"Add a line to {invoice_draft_a.number}"
    assert ctx["submit_label"] == "Add line"
    assert ctx["cancel_url"] == reverse("procurement:supplierinvoice_detail",
                                        args=[invoice_draft_a.pk])
    assert "invoice" not in ctx["form"].fields
    assert "line_total" not in ctx["form"].fields


def test_invoice_line_create_post_saves_and_recalcs_the_header(client_a, invoice_draft_a,
                                                               gl_expense_a):
    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        _invoice_line_row(quantity="3", unit_price="7.00",
                          gl_account=str(gl_expense_a.pk)))

    invoice_draft_a.refresh_from_db()
    line = invoice_draft_a.lines.get()
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_draft_a.pk])
    assert line.line_total == Decimal("21.00")
    assert invoice_draft_a.total == Decimal("21.00")


def test_invoice_line_create_takes_its_header_from_the_url_not_the_body(client_a,
                                                                       invoice_draft_a,
                                                                       invoice_captured_a,
                                                                       gl_expense_a):
    body = _invoice_line_row(gl_account=str(gl_expense_a.pk))
    body["invoice"] = str(invoice_captured_a.pk)          # crafted - must be ignored

    client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        body)

    assert invoice_draft_a.lines.count() == 1
    assert invoice_captured_a.lines.count() == 0


def test_invoice_line_create_refuses_a_non_editable_header(client_a, invoice_pending_a):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_create"),
                        {"invoice": str(invoice_pending_a.pk)})

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_pending_a.pk])
    assert any("can take new lines" in m for m in _invoice_messages(resp))


@pytest.mark.parametrize("field,value", [("quantity", "10000000000"),
                                         ("unit_price", "1000000000000"),
                                         ("quantity", "NaN"),
                                         ("unit_price", "Infinity"),
                                         ("quantity", "abc")])
def test_invoice_line_create_post_junk_money_is_a_field_error(client_a, invoice_draft_a,
                                                              gl_expense_a, field, value):
    body = _invoice_line_row(gl_account=str(gl_expense_a.pk))
    body[field] = value

    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        body)

    assert resp.status_code == 200            # a friendly refusal, never a 500 (L35)
    assert resp.context["form"].errors[field]
    assert invoice_draft_a.lines.count() == 0


def test_invoice_line_create_post_with_a_tenant_b_fk_is_rejected(client_a, invoice_draft_a,
                                                                 invoice_item_b,
                                                                 invoice_po_line_b,
                                                                 gl_expense_a):
    body = _invoice_line_row(gl_account=str(gl_expense_a.pk),
                             item=str(invoice_item_b.pk),
                             po_line=str(invoice_po_line_b.pk))

    resp = client_a.post(
        reverse("procurement:supplierinvoiceline_create") + f"?invoice={invoice_draft_a.pk}",
        body)

    assert resp.status_code == 200
    assert resp.context["form"].errors["item"]
    assert resp.context["form"].errors["po_line"]
    assert invoice_draft_a.lines.count() == 0


def test_invoice_line_edit_post_updates_and_recalcs(client_a, invoice_draft_a, invoice_line_a,
                                                    gl_expense_a):
    body = _invoice_line_row(quantity="4", unit_price="25.00",
                             gl_account=str(gl_expense_a.pk),
                             po_line=str(invoice_line_a.po_line_id),
                             receipt_line=str(invoice_line_a.receipt_line_id))

    resp = client_a.post(reverse("procurement:supplierinvoiceline_edit",
                                 args=[invoice_line_a.pk]), body)

    invoice_line_a.refresh_from_db()
    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_draft_a.pk])
    assert invoice_line_a.quantity == Decimal("4.0000")
    assert invoice_line_a.line_total == Decimal("100.00")
    assert invoice_draft_a.total == Decimal("100.00")


def test_invoice_line_edit_refuses_a_non_editable_header(client_a, invoice_pending_a):
    line = invoice_pending_a.lines.get()

    resp = client_a.get(reverse("procurement:supplierinvoiceline_edit", args=[line.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoiceline_detail", args=[line.pk])
    assert any("can no longer be edited" in m for m in _invoice_messages(resp))


def test_invoice_line_edit_cross_tenant_pk_is_404(client_a, invoice_line_b):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_edit",
                                args=[invoice_line_b.pk]))
    assert resp.status_code == 404


def test_invoice_line_delete_get_is_405_and_deletes_nothing(client_a, invoice_line_a):
    resp = client_a.get(reverse("procurement:supplierinvoiceline_delete",
                                args=[invoice_line_a.pk]))

    assert resp.status_code == 405
    assert SupplierInvoiceLine.objects.filter(pk=invoice_line_a.pk).exists()


def test_invoice_line_delete_post_removes_and_recalcs_the_header(client_a, invoice_draft_a,
                                                                 invoice_line_a):
    resp = client_a.post(reverse("procurement:supplierinvoiceline_delete",
                                 args=[invoice_line_a.pk]))

    invoice_draft_a.refresh_from_db()
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:supplierinvoice_detail",
                                       args=[invoice_draft_a.pk])
    assert not SupplierInvoiceLine.objects.filter(pk=invoice_line_a.pk).exists()
    # A delete has no save() to ride, so the header money is re-derived by the view.
    assert invoice_draft_a.total == Decimal("0.00")


def test_invoice_line_delete_refuses_a_non_editable_header(client_a, invoice_pending_a):
    line = invoice_pending_a.lines.get()

    resp = client_a.post(reverse("procurement:supplierinvoiceline_delete", args=[line.pk]))

    assert resp.status_code == 302
    assert SupplierInvoiceLine.objects.filter(pk=line.pk).exists()
    assert any("can no longer be removed" in m for m in _invoice_messages(resp))


def test_invoice_line_delete_cross_tenant_pk_is_404(client_a, invoice_line_b):
    resp = client_a.post(reverse("procurement:supplierinvoiceline_delete",
                                 args=[invoice_line_b.pk]))
    assert resp.status_code == 404
    assert SupplierInvoiceLine.objects.filter(pk=invoice_line_b.pk).exists()


# =================================================================================================
# Payment Schedule
# =================================================================================================

def test_invoice_payment_schedule_renders_buckets_and_stats(client_a, invoice_scheduled_a,
                                                            invoice_vendor_a, invoice_term_a):
    resp = client_a.get(reverse("procurement:paymentschedule_list"))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/payment_schedule.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["horizon_weeks"] == 8
    assert ctx["today"] == _invoice_today()
    assert ctx["q"] == ""
    assert [b["key"] for b in ctx["buckets"]][:2] == ["overdue", "w0"]
    assert len(ctx["buckets"]) == 9                       # overdue + 8 weekly
    week_one = ctx["buckets"][1]
    assert [row.pk for row in week_one["rows"]] == [invoice_scheduled_a.pk]
    assert week_one["count"] == 1
    assert week_one["total"] == Decimal("240.00")
    assert ctx["total_payable"] == Decimal("240.00")
    assert ctx["stats"] == {"invoices": 1, "total_payable": Decimal("240.00"),
                            "overdue_total": Decimal("0.00"),
                            "discounted_total": Decimal("0.00")}
    assert [t.pk for t in ctx["terms"]] == [invoice_term_a.pk]
    assert [v.pk for v in ctx["vendors"]] == [invoice_vendor_a.pk]
    assert ctx["currency"] is not None


def test_invoice_payment_schedule_is_not_paginated(client_a, invoice_scheduled_a):
    """NOT paginated by design - a pager over bucketed rows made page 2 identical to page 1."""
    resp = client_a.get(reverse("procurement:paymentschedule_list"))
    assert "page_obj" not in resp.context


@pytest.mark.parametrize("weeks,expected", [("0", 1), ("1", 1), ("26", 26), ("10000", 26),
                                            ("NaN", 8), ("abc", 8), ("-3", 8), ("", 8)])
def test_invoice_payment_schedule_weeks_is_clamped(client_a, invoice_scheduled_a, weeks,
                                                   expected):
    resp = client_a.get(reverse("procurement:paymentschedule_list"), {"weeks": weeks})
    assert resp.status_code == 200
    assert resp.context["horizon_weeks"] == expected
    assert len(resp.context["buckets"]) == expected + 1


def test_invoice_payment_schedule_filters_narrow_the_buckets(client_a, invoice_scheduled_a,
                                                             invoice_vendor_a, invoice_term_a,
                                                             invoice_vendor_other_a):
    url = reverse("procurement:paymentschedule_list")

    by_q = client_a.get(url, {"q": "SUP-7005"})
    assert by_q.context["stats"]["invoices"] == 1

    by_other_vendor = client_a.get(url, {"vendor": str(invoice_vendor_other_a.pk)})
    assert by_other_vendor.context["stats"]["invoices"] == 0

    by_terms = client_a.get(url, {"terms": str(invoice_term_a.pk)})
    assert by_terms.context["stats"]["invoices"] == 1

    junk_vendor = client_a.get(url, {"vendor": "abc"})
    assert junk_vendor.status_code == 200
    assert junk_vendor.context["stats"]["invoices"] == 1


def test_invoice_payment_schedule_never_shows_another_workspace(client_a, invoice_scheduled_a,
                                                                tenant_b, invoice_vendor_b,
                                                                invoice_term_b):
    foreign = _invoice_header(tenant_b, invoice_vendor_b, "GBX-SCHED", status="scheduled",
                              payment_term=invoice_term_b)
    assert foreign.due_date is not None

    resp = client_a.get(reverse("procurement:paymentschedule_list"))

    seen = {row.pk for bucket in resp.context["buckets"] for row in bucket["rows"]}
    assert foreign.pk not in seen
    assert seen == {invoice_scheduled_a.pk}


# =================================================================================================
# Match variance register / detail / accept
# =================================================================================================

def test_invoice_variance_list_renders_contract_context(client_a, invoice_blocked_a,
                                                        invoice_variance_block_a,
                                                        invoice_variance_warn_a,
                                                        invoice_variance_accepted_a):
    resp = client_a.get(reverse("procurement:matchvariance_list"))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/matchvariance/list.html"
            in _invoice_templates(resp))
    assert set(_invoice_pks(resp)) == {invoice_variance_block_a.pk, invoice_variance_warn_a.pk,
                                       invoice_variance_accepted_a.pk}
    ctx = resp.context
    assert dict(ctx["variance_type_choices"])["price"]
    assert dict(ctx["outcome_choices"])["block"]
    assert dict(ctx["resolution_choices"])["open"]
    assert dict(ctx["basis_choices"])["po"]
    assert [i.pk for i in ctx["invoices"]] == [invoice_blocked_a.pk]
    assert ctx["stats"] == {"open": 2, "blocking": 2, "warn": 1, "auto_accept": 0}


def test_invoice_variance_list_search_and_filters_narrow(client_a, invoice_blocked_a,
                                                         invoice_variance_block_a,
                                                         invoice_variance_warn_a,
                                                         invoice_variance_accepted_a):
    url = reverse("procurement:matchvariance_list")

    by_message = client_a.get(url, {"q": "Unit price"})
    assert _invoice_pks(by_message) == [invoice_variance_block_a.pk]

    by_header = client_a.get(url, {"q": invoice_blocked_a.number})
    assert len(_invoice_pks(by_header)) == 3

    by_type = client_a.get(url, {"variance_type": "tax"})
    assert _invoice_pks(by_type) == [invoice_variance_warn_a.pk]

    by_outcome = client_a.get(url, {"outcome": "warn"})
    assert _invoice_pks(by_outcome) == [invoice_variance_warn_a.pk]

    by_resolution = client_a.get(url, {"resolution": "accepted"})
    assert _invoice_pks(by_resolution) == [invoice_variance_accepted_a.pk]

    by_basis = client_a.get(url, {"basis": "header"})
    assert _invoice_pks(by_basis) == [invoice_variance_warn_a.pk]

    by_invoice = client_a.get(url, {"invoice": str(invoice_blocked_a.pk)})
    assert len(_invoice_pks(by_invoice)) == 3


@pytest.mark.parametrize("junk", _INVOICE_JUNK_INTS)
def test_invoice_variance_list_junk_invoice_param_renders_the_full_register(
        client_a, invoice_variance_block_a, junk):
    resp = client_a.get(reverse("procurement:matchvariance_list"), {"invoice": junk})
    assert resp.status_code == 200
    assert _invoice_pks(resp) == [invoice_variance_block_a.pk]


def test_invoice_variance_list_junk_enum_params_fall_back(client_a, invoice_variance_block_a):
    resp = client_a.get(reverse("procurement:matchvariance_list"),
                        {"variance_type": "nope", "outcome": "??", "resolution": "later",
                         "basis": "whatever"})
    assert resp.status_code == 200
    assert _invoice_pks(resp) == [invoice_variance_block_a.pk]


def test_invoice_variance_list_page_two_and_past_the_end(client_a, _invoice_bulk_variances):
    url = reverse("procurement:matchvariance_list")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})

    assert len(_invoice_pks(page_one)) == 15
    assert len(_invoice_pks(page_two)) == 3
    assert set(_invoice_pks(page_one)).isdisjoint(_invoice_pks(page_two))

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.context["page_obj"].number == 2


def test_invoice_variance_list_query_budget(client_a, _invoice_bulk_variances,
                                            django_assert_max_num_queries):
    with django_assert_max_num_queries(12):
        resp = client_a.get(reverse("procurement:matchvariance_list"))
    assert len(_invoice_pks(resp)) == 15


def test_invoice_variance_list_never_shows_another_workspace(client_a, invoice_variance_block_a,
                                                             invoice_variance_b):
    resp = client_a.get(reverse("procurement:matchvariance_list"))
    assert _invoice_pks(resp) == [invoice_variance_block_a.pk]


def test_invoice_variance_detail_offers_the_accept_action(client_a, invoice_blocked_a,
                                                          invoice_variance_block_a):
    resp = client_a.get(reverse("procurement:matchvariance_detail",
                                args=[invoice_variance_block_a.pk]))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/matchvariance/detail.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"].pk == invoice_variance_block_a.pk
    assert ctx["invoice"].pk == invoice_blocked_a.pk
    assert ctx["invoice_line"] is None
    assert ctx["dispute"] is None
    assert ctx["explanation"]
    assert ctx["tolerance"] == {"abs": None, "pct": Decimal("2.0000")}
    assert ctx["can_accept"] is True
    assert [a["url"] for a in ctx["actions"]] == [
        reverse("procurement:matchvariance_accept", args=[invoice_variance_block_a.pk])]
    assert ctx["actions"][0]["verb"] == "get"
    assert ctx["is_admin"] is True


def test_invoice_variance_detail_offers_nothing_on_a_settled_row(client_a,
                                                                 invoice_variance_accepted_a):
    ctx = client_a.get(reverse("procurement:matchvariance_detail",
                               args=[invoice_variance_accepted_a.pk])).context
    assert ctx["can_accept"] is False
    assert ctx["actions"] == []


def test_invoice_variance_detail_cross_tenant_pk_is_404(client_a, invoice_variance_b):
    resp = client_a.get(reverse("procurement:matchvariance_detail",
                                args=[invoice_variance_b.pk]))
    assert resp.status_code == 404


def test_invoice_variance_accept_get_renders_the_confirmation_page(client_a,
                                                                   invoice_variance_block_a):
    resp = client_a.get(reverse("procurement:matchvariance_accept",
                                args=[invoice_variance_block_a.pk]))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/matchvariance/form.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"].pk == invoice_variance_block_a.pk
    assert list(ctx["form"].fields) == ["note"]
    assert ctx["is_edit"] is False
    # A GET must not settle anything.
    invoice_variance_block_a.refresh_from_db()
    assert invoice_variance_block_a.resolution == "open"


def test_invoice_variance_accept_post_settles_the_row(client_a, invoice_variance_block_a):
    resp = client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_block_a.pk]),
                         {"note": "Price rise agreed by phone."})

    invoice_variance_block_a.refresh_from_db()
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:matchvariance_detail",
                                       args=[invoice_variance_block_a.pk])
    assert invoice_variance_block_a.resolution == "accepted"


def test_invoice_variance_accept_post_on_a_settled_row_is_refused(client_a,
                                                                  invoice_variance_accepted_a):
    resp = client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_accepted_a.pk]), {"note": ""})

    invoice_variance_accepted_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_variance_accepted_a.resolution == "accepted"
    assert any("already accepted" in m for m in _invoice_messages(resp))


def test_invoice_variance_accept_post_with_an_over_long_note_is_refused(
        client_a, invoice_variance_block_a):
    resp = client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_block_a.pk]),
                         {"note": "x" * 501})

    invoice_variance_block_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_variance_block_a.resolution == "open"
    assert any("500 characters at most" in m for m in _invoice_messages(resp))


def test_invoice_variance_accept_cross_tenant_pk_is_404(client_a, invoice_variance_b):
    resp = client_a.post(reverse("procurement:matchvariance_accept",
                                 args=[invoice_variance_b.pk]), {"note": ""})
    assert resp.status_code == 404
    invoice_variance_b.refresh_from_db()
    assert invoice_variance_b.resolution == "open"


# =================================================================================================
# Match Board
# =================================================================================================

def test_invoice_match_board_renders_grouped_cards(client_a, invoice_blocked_a,
                                                   invoice_variance_block_a,
                                                   invoice_variance_warn_a):
    resp = client_a.get(reverse("procurement:invoice_match_board"))

    assert resp.status_code == 200
    assert "procurement/invoicevouchermanagement/match_board.html" in _invoice_templates(resp)
    ctx = resp.context
    assert len(ctx["groups"]) == 1
    group = ctx["groups"][0]
    assert group["invoice"].pk == invoice_blocked_a.pk
    assert {v.pk for v in group["variances"]} == {invoice_variance_block_a.pk,
                                                  invoice_variance_warn_a.pk}
    assert group["blocking_count"] == 1
    assert group["warn_count"] == 1
    assert group["oldest_at"] is not None
    assert ctx["stats"] == {"invoices": 1, "blocking": 1, "warn": 0, "overdue": 0}
    assert ctx["today"] == _invoice_today()
    assert ctx["q"] == ""
    assert dict(ctx["outcome_choices"])["block"]
    assert dict(ctx["variance_type_choices"])["price"]


def test_invoice_match_board_filters_apply_before_grouping(client_a, invoice_blocked_a,
                                                           invoice_variance_block_a,
                                                           invoice_variance_warn_a):
    url = reverse("procurement:invoice_match_board")

    by_outcome = client_a.get(url, {"outcome": "warn"})
    group = by_outcome.context["groups"][0]
    assert [v.pk for v in group["variances"]] == [invoice_variance_warn_a.pk]
    assert group["blocking_count"] == 0

    by_type = client_a.get(url, {"variance_type": "price"})
    assert [v.pk for v in by_type.context["groups"][0]["variances"]] == [
        invoice_variance_block_a.pk]

    by_q = client_a.get(url, {"q": "Northwind"})
    assert len(by_q.context["groups"]) == 1

    no_match = client_a.get(url, {"q": "nothing-matches-this"})
    assert no_match.status_code == 200
    assert no_match.context["groups"] == []


def test_invoice_match_board_page_two_and_past_the_end(client_a, _invoice_bulk_variances):
    url = reverse("procurement:invoice_match_board")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})

    first = [g["invoice"].pk for g in page_one.context["groups"]]
    second = [g["invoice"].pk for g in page_two.context["groups"]]
    assert len(first) == 15
    assert len(second) == 3
    assert set(first).isdisjoint(second)

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.context["page_obj"].number == 2


def test_invoice_match_board_query_budget(client_a, _invoice_bulk_variances,
                                          django_assert_max_num_queries):
    with django_assert_max_num_queries(14):
        resp = client_a.get(reverse("procurement:invoice_match_board"))
    assert len(resp.context["groups"]) == 15


def test_invoice_match_board_never_shows_another_workspace(client_a, invoice_variance_block_a,
                                                           invoice_variance_b):
    resp = client_a.get(reverse("procurement:invoice_match_board"))
    seen = {group["invoice"].pk for group in resp.context["groups"]}
    assert invoice_variance_b.invoice_id not in seen


# =================================================================================================
# InvoiceDispute register / detail
# =================================================================================================

def test_invoice_dispute_list_renders_contract_context(client_a, admin_user, invoice_vendor_a,
                                                       invoice_dispute_open_a,
                                                       invoice_dispute_escalated_a,
                                                       invoice_dispute_resolved_a,
                                                       invoice_dispute_overdue_a):
    resp = client_a.get(reverse("procurement:invoicedispute_list"))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/invoicedispute/list.html"
            in _invoice_templates(resp))
    assert set(_invoice_pks(resp)) == {invoice_dispute_open_a.pk,
                                       invoice_dispute_escalated_a.pk,
                                       invoice_dispute_resolved_a.pk,
                                       invoice_dispute_overdue_a.pk}
    ctx = resp.context
    assert dict(ctx["status_choices"])["awaiting_supplier"]
    assert dict(ctx["reason_choices"])["price"]
    assert [s.pk for s in ctx["suppliers"]] == [invoice_vendor_a.pk]
    assert [a.pk for a in ctx["assignees"]] == [admin_user.pk]
    assert ctx["stats"] == {"open": 3, "overdue": 1, "escalated": 1, "resolved": 1}


def test_invoice_dispute_list_search_and_filters_narrow(client_a, admin_user,
                                                        invoice_vendor_a,
                                                        invoice_dispute_open_a,
                                                        invoice_dispute_escalated_a,
                                                        invoice_dispute_resolved_a,
                                                        invoice_dispute_overdue_a):
    url = reverse("procurement:invoicedispute_list")

    by_number = client_a.get(url, {"q": invoice_dispute_open_a.number})
    assert _invoice_pks(by_number) == [invoice_dispute_open_a.pk]

    by_description = client_a.get(url, {"q": "surcharge"})
    assert _invoice_pks(by_description) == [invoice_dispute_resolved_a.pk]

    by_supplier_name = client_a.get(url, {"q": "Northwind"})
    assert len(_invoice_pks(by_supplier_name)) == 4

    by_status = client_a.get(url, {"status": "escalated"})
    assert _invoice_pks(by_status) == [invoice_dispute_escalated_a.pk]

    by_reason = client_a.get(url, {"reason_code": "duplicate"})
    assert _invoice_pks(by_reason) == [invoice_dispute_overdue_a.pk]

    by_supplier = client_a.get(url, {"supplier": str(invoice_vendor_a.pk)})
    assert len(_invoice_pks(by_supplier)) == 4

    by_assignee = client_a.get(url, {"assigned_to": str(admin_user.pk)})
    assert _invoice_pks(by_assignee) == [invoice_dispute_open_a.pk]

    overdue_only = client_a.get(url, {"overdue": "1"})
    assert _invoice_pks(overdue_only) == [invoice_dispute_overdue_a.pk]

    # ``?overdue=0`` is the unchecked box - it must not filter.
    unchecked = client_a.get(url, {"overdue": "0"})
    assert len(_invoice_pks(unchecked)) == 4


@pytest.mark.parametrize("junk", _INVOICE_JUNK_INTS)
def test_invoice_dispute_list_junk_int_params_render_the_full_register(
        client_a, invoice_dispute_open_a, junk):
    resp = client_a.get(reverse("procurement:invoicedispute_list"),
                        {"supplier": junk, "assigned_to": junk})
    assert resp.status_code == 200
    assert _invoice_pks(resp) == [invoice_dispute_open_a.pk]


def test_invoice_dispute_list_junk_enum_params_fall_back(client_a, invoice_dispute_open_a):
    resp = client_a.get(reverse("procurement:invoicedispute_list"),
                        {"status": "nope", "reason_code": "??"})
    assert resp.status_code == 200
    assert _invoice_pks(resp) == [invoice_dispute_open_a.pk]


def test_invoice_dispute_list_page_two_and_past_the_end(client_a, _invoice_bulk_disputes):
    url = reverse("procurement:invoicedispute_list")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})

    assert len(_invoice_pks(page_one)) == 15
    assert len(_invoice_pks(page_two)) == 3
    assert set(_invoice_pks(page_one)).isdisjoint(_invoice_pks(page_two))

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.context["page_obj"].number == 2


def test_invoice_dispute_list_query_budget(client_a, _invoice_bulk_disputes,
                                           django_assert_max_num_queries):
    with django_assert_max_num_queries(14):
        resp = client_a.get(reverse("procurement:invoicedispute_list"))
    assert len(_invoice_pks(resp)) == 15


def test_invoice_dispute_list_never_shows_another_workspace(client_a, invoice_dispute_open_a,
                                                            invoice_dispute_b):
    resp = client_a.get(reverse("procurement:invoicedispute_list"))
    assert _invoice_pks(resp) == [invoice_dispute_open_a.pk]


def test_invoice_dispute_detail_renders_actions_and_flags(client_a, invoice_draft_a,
                                                          invoice_line_a,
                                                          invoice_dispute_open_a):
    resp = client_a.get(reverse("procurement:invoicedispute_detail",
                                args=[invoice_dispute_open_a.pk]))

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/invoicedispute/detail.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"].pk == invoice_dispute_open_a.pk
    assert ctx["invoice"].pk == invoice_draft_a.pk
    assert ctx["invoice_line"].pk == invoice_line_a.pk
    assert list(ctx["variances"]) == []
    assert dict(ctx["resolution_choices"])["credit_memo"]
    assert ctx["days_open"] == 0
    assert ctx["is_overdue"] is False
    assert ctx["can_edit"] is True
    assert ctx["can_resolve"] is True
    assert ctx["is_admin"] is True
    labels = [a["label"] for a in ctx["actions"]]
    assert labels == ["Escalate", "Await supplier", "Await internal review"]
    assert all(a["url"] and a["verb"] == "post" for a in ctx["actions"])


def test_invoice_dispute_detail_hides_admin_actions_from_a_member(member_client,
                                                                  invoice_dispute_open_a):
    ctx = member_client.get(reverse("procurement:invoicedispute_detail",
                                    args=[invoice_dispute_open_a.pk])).context
    assert ctx["is_admin"] is False
    assert ctx["can_resolve"] is False
    labels = [a["label"] for a in ctx["actions"]]
    assert "Escalate" not in labels
    # ...but the two waiting verbs are open to a member, which is what the routes allow.
    assert labels == ["Await supplier", "Await internal review"]


def test_invoice_dispute_detail_cross_tenant_pk_is_404(client_a, invoice_dispute_b):
    resp = client_a.get(reverse("procurement:invoicedispute_detail",
                                args=[invoice_dispute_b.pk]))
    assert resp.status_code == 404


# =================================================================================================
# InvoiceDispute create / edit / delete
# =================================================================================================

def test_invoice_dispute_create_get_prefills_from_the_invoice_param(client_a, invoice_draft_a):
    resp = client_a.get(reverse("procurement:invoicedispute_create"),
                        {"invoice": str(invoice_draft_a.pk)})

    assert resp.status_code == 200
    assert ("procurement/invoicevouchermanagement/invoicedispute/form.html"
            in _invoice_templates(resp))
    ctx = resp.context
    assert ctx["obj"] is None
    assert ctx["is_edit"] is False
    assert ctx["invoice"].pk == invoice_draft_a.pk
    assert ctx["title"] == "Raise a dispute"
    assert ctx["submit_label"] == "Raise dispute"
    assert ctx["cancel_url"] == reverse("procurement:supplierinvoice_detail",
                                        args=[invoice_draft_a.pk])
    assert ctx["form"].initial["invoice"] == invoice_draft_a.pk
    # System-owned columns are absent from the form.
    for name in ("tenant", "number", "supplier", "status", "resolution", "raised_by",
                 "credit_memo_invoice"):
        assert name not in ctx["form"].fields


def test_invoice_dispute_create_ignores_a_cross_tenant_invoice_param(client_a, invoice_b):
    resp = client_a.get(reverse("procurement:invoicedispute_create"),
                        {"invoice": str(invoice_b.pk)})

    assert resp.status_code == 200
    assert resp.context["invoice"] is None
    assert resp.context["form"].initial == {}


def test_invoice_dispute_create_post_stamps_tenant_and_author(client_a, tenant_a, admin_user,
                                                              invoice_draft_a, invoice_line_a):
    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_body(invoice_draft_a))

    obj = InvoiceDispute.objects.get(description="Billed above the agreed contract rate.")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:invoicedispute_detail", args=[obj.pk])
    assert obj.tenant_id == tenant_a.pk
    assert obj.raised_by_id == admin_user.pk
    assert obj.number.startswith("DSP-")
    assert obj.status == "open"
    # ``supplier`` is DENORMALISED from the invoice, never posted.
    assert obj.supplier_id == invoice_draft_a.vendor_id


def test_invoice_dispute_create_post_with_a_tenant_b_invoice_is_a_field_error(client_a,
                                                                             invoice_b):
    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_body(invoice_b))

    assert resp.status_code == 200
    assert resp.context["form"].errors["invoice"]
    assert not InvoiceDispute.objects.filter(invoice=invoice_b).exists()


def test_invoice_dispute_create_post_with_a_tenant_b_line_is_a_field_error(client_a,
                                                                          invoice_draft_a,
                                                                          invoice_line_b):
    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_body(invoice_draft_a,
                                               invoice_line=str(invoice_line_b.pk)))

    assert resp.status_code == 200
    assert resp.context["form"].errors["invoice_line"]
    assert InvoiceDispute.objects.count() == 0


@pytest.mark.parametrize("junk", _INVOICE_JUNK_MONEY)
def test_invoice_dispute_create_post_junk_amount_is_a_field_error(client_a, invoice_draft_a,
                                                                  invoice_line_a, junk):
    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_body(invoice_draft_a, disputed_amount=junk))

    assert resp.status_code == 200            # a friendly refusal, never a 500 (L35)
    assert resp.context["form"].errors["disputed_amount"]
    assert InvoiceDispute.objects.count() == 0


def test_invoice_dispute_create_post_over_the_invoice_total_is_refused(client_a,
                                                                      invoice_draft_a,
                                                                      invoice_line_a):
    resp = client_a.post(reverse("procurement:invoicedispute_create"),
                         _invoice_dispute_body(invoice_draft_a, disputed_amount="9999.00"))

    assert resp.status_code == 200
    assert ("The disputed amount cannot be more than the invoice total."
            in resp.context["form"].errors["disputed_amount"])
    assert InvoiceDispute.objects.count() == 0


def test_invoice_dispute_edit_pops_the_invoice_and_saves(client_a, invoice_dispute_open_a,
                                                         invoice_captured_a):
    url = reverse("procurement:invoicedispute_edit", args=[invoice_dispute_open_a.pk])
    page = client_a.get(url)
    assert page.context["is_edit"] is True
    assert "invoice" not in page.context["form"].fields
    assert "invoice_line" not in page.context["form"].fields

    body = _invoice_dispute_body(invoice_captured_a, reason_code="quantity",
                                 description="Three reams short.")
    resp = client_a.post(url, body)

    invoice_dispute_open_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_dispute_open_a.reason_code == "quantity"
    # A crafted ``invoice`` in the body cannot re-point a saved dispute.
    assert invoice_dispute_open_a.invoice_id != invoice_captured_a.pk


def test_invoice_dispute_edit_refuses_a_settled_dispute(client_a, invoice_dispute_resolved_a):
    resp = client_a.get(reverse("procurement:invoicedispute_edit",
                                args=[invoice_dispute_resolved_a.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:invoicedispute_detail",
                                       args=[invoice_dispute_resolved_a.pk])
    assert any("only an open dispute can be edited" in m for m in _invoice_messages(resp))


def test_invoice_dispute_edit_cross_tenant_pk_is_404(client_a, invoice_dispute_b):
    resp = client_a.get(reverse("procurement:invoicedispute_edit",
                                args=[invoice_dispute_b.pk]))
    assert resp.status_code == 404


def test_invoice_dispute_delete_get_is_405_and_deletes_nothing(client_a,
                                                               invoice_dispute_open_a):
    resp = client_a.get(reverse("procurement:invoicedispute_delete",
                                args=[invoice_dispute_open_a.pk]))

    assert resp.status_code == 405
    assert InvoiceDispute.objects.filter(pk=invoice_dispute_open_a.pk).exists()


def test_invoice_dispute_delete_post_removes_the_row(client_a, invoice_dispute_open_a):
    resp = client_a.post(reverse("procurement:invoicedispute_delete",
                                 args=[invoice_dispute_open_a.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:invoicedispute_list")
    assert not InvoiceDispute.objects.filter(pk=invoice_dispute_open_a.pk).exists()


def test_invoice_dispute_delete_cross_tenant_pk_is_404(client_a, invoice_dispute_b):
    resp = client_a.post(reverse("procurement:invoicedispute_delete",
                                 args=[invoice_dispute_b.pk]))
    assert resp.status_code == 404
    assert InvoiceDispute.objects.filter(pk=invoice_dispute_b.pk).exists()


# =================================================================================================
# InvoiceDispute verbs
# =================================================================================================

def test_invoice_dispute_resolve_without_a_resolution_changes_nothing(client_a,
                                                                      invoice_dispute_open_a):
    """L35 - an absent prerequisite is REJECTED, never fallen through to a settlement."""
    resp = client_a.post(reverse("procurement:invoicedispute_resolve",
                                 args=[invoice_dispute_open_a.pk]), {})

    invoice_dispute_open_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_dispute_open_a.status == "open"
    assert invoice_dispute_open_a.resolution == ""
    assert any("Choose how this dispute was resolved." in m for m in _invoice_messages(resp))


def test_invoice_dispute_resolve_with_a_junk_resolution_changes_nothing(client_a,
                                                                        invoice_dispute_open_a):
    resp = client_a.post(reverse("procurement:invoicedispute_resolve",
                                 args=[invoice_dispute_open_a.pk]),
                         {"resolution": "whatever-they-agreed"})

    invoice_dispute_open_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_dispute_open_a.status == "open"
    assert invoice_dispute_open_a.resolution == ""


def test_invoice_dispute_resolve_settles_the_dispute(client_a, invoice_dispute_open_a):
    resp = client_a.post(reverse("procurement:invoicedispute_resolve",
                                 args=[invoice_dispute_open_a.pk]),
                         {"resolution": "short_pay", "resolution_note": "Paid net."})

    invoice_dispute_open_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_dispute_open_a.status == "resolved"
    assert invoice_dispute_open_a.resolution == "short_pay"
    assert invoice_dispute_open_a.resolution_note == "Paid net."
    assert invoice_dispute_open_a.resolved_at is not None


def test_invoice_dispute_resolve_spawns_the_credit_memo_only_when_asked(
        client_a, invoice_dispute_open_a, invoice_draft_a):
    resp = client_a.post(reverse("procurement:invoicedispute_resolve",
                                 args=[invoice_dispute_open_a.pk]),
                         {"resolution": "credit_memo", "spawn_credit_memo": "1"})

    invoice_dispute_open_a.refresh_from_db()
    memo = invoice_dispute_open_a.credit_memo_invoice
    assert resp.status_code == 302
    assert memo is not None
    assert memo.invoice_type == "credit_memo"
    assert memo.invoice_number == f"CM-{invoice_draft_a.invoice_number}"
    assert memo.tenant_id == invoice_dispute_open_a.tenant_id
    # ONE line, for the NEGATIVE disputed amount.
    line = memo.lines.get()
    assert line.quantity == Decimal("1.0000")
    assert line.unit_price == Decimal("-50.00")
    assert memo.total == Decimal("-50.00")


def test_invoice_dispute_resolve_without_the_spawn_flag_mints_nothing(client_a,
                                                                      invoice_dispute_open_a):
    before = SupplierInvoice.objects.filter(invoice_type="credit_memo").count()

    client_a.post(reverse("procurement:invoicedispute_resolve",
                          args=[invoice_dispute_open_a.pk]),
                  {"resolution": "credit_memo"})

    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "resolved"
    assert invoice_dispute_open_a.credit_memo_invoice_id is None
    assert SupplierInvoice.objects.filter(invoice_type="credit_memo").count() == before


def test_invoice_dispute_resolve_refuses_a_settled_dispute(client_a,
                                                           invoice_dispute_resolved_a):
    resp = client_a.post(reverse("procurement:invoicedispute_resolve",
                                 args=[invoice_dispute_resolved_a.pk]),
                         {"resolution": "withdrawn"})

    invoice_dispute_resolved_a.refresh_from_db()
    assert resp.status_code == 302
    assert invoice_dispute_resolved_a.resolution == "short_pay"
    assert any("cannot be resolved" in m for m in _invoice_messages(resp))


def test_invoice_dispute_escalate_and_close_walk_the_lifecycle(client_a,
                                                               invoice_dispute_open_a):
    escalated = client_a.post(reverse("procurement:invoicedispute_escalate",
                                      args=[invoice_dispute_open_a.pk]))
    invoice_dispute_open_a.refresh_from_db()
    assert escalated.status_code == 302
    assert invoice_dispute_open_a.status == "escalated"

    # Only a RESOLVED dispute closes - an escalated one is refused.
    refused = client_a.post(reverse("procurement:invoicedispute_close",
                                    args=[invoice_dispute_open_a.pk]))
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "escalated"
    assert any("only a resolved dispute can be closed" in m for m in _invoice_messages(refused))

    client_a.post(reverse("procurement:invoicedispute_resolve",
                          args=[invoice_dispute_open_a.pk]), {"resolution": "withdrawn"})
    closed = client_a.post(reverse("procurement:invoicedispute_close",
                                   args=[invoice_dispute_open_a.pk]))
    invoice_dispute_open_a.refresh_from_db()
    assert closed.status_code == 302
    assert invoice_dispute_open_a.status == "closed"


def test_invoice_dispute_await_verbs_are_open_to_a_member(member_client,
                                                          invoice_dispute_open_a):
    supplier = member_client.post(reverse("procurement:invoicedispute_await_supplier",
                                          args=[invoice_dispute_open_a.pk]))
    invoice_dispute_open_a.refresh_from_db()
    assert supplier.status_code == 302
    assert invoice_dispute_open_a.status == "awaiting_supplier"

    internal = member_client.post(reverse("procurement:invoicedispute_await_internal",
                                          args=[invoice_dispute_open_a.pk]))
    invoice_dispute_open_a.refresh_from_db()
    assert internal.status_code == 302
    assert invoice_dispute_open_a.status == "awaiting_internal"


def test_invoice_dispute_verb_get_is_405_and_changes_nothing(client_a, invoice_dispute_open_a):
    for name in ("invoicedispute_resolve", "invoicedispute_escalate",
                 "invoicedispute_await_supplier", "invoicedispute_await_internal",
                 "invoicedispute_close"):
        resp = client_a.get(reverse(f"procurement:{name}", args=[invoice_dispute_open_a.pk]))
        assert resp.status_code == 405, name
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "open"


def test_invoice_dispute_verbs_cross_tenant_pk_is_404(client_a, invoice_dispute_b):
    for name in ("invoicedispute_escalate", "invoicedispute_await_supplier",
                 "invoicedispute_await_internal", "invoicedispute_close"):
        resp = client_a.post(reverse(f"procurement:{name}", args=[invoice_dispute_b.pk]))
        assert resp.status_code == 404, name
    resolve = client_a.post(reverse("procurement:invoicedispute_resolve",
                                    args=[invoice_dispute_b.pk]), {"resolution": "withdrawn"})
    assert resolve.status_code == 404
    invoice_dispute_b.refresh_from_db()
    assert invoice_dispute_b.status == "open"


# =================================================================================================
# Dispute Aging board
# =================================================================================================

def test_invoice_dispute_aging_renders_buckets_and_stats(client_a, invoice_dispute_open_a,
                                                         invoice_dispute_overdue_a,
                                                         invoice_dispute_resolved_a):
    resp = client_a.get(reverse("procurement:invoicedispute_aging"))

    assert resp.status_code == 200
    assert "procurement/invoicevouchermanagement/dispute_aging.html" in _invoice_templates(resp)
    ctx = resp.context
    buckets = {bucket["key"]: bucket for bucket in ctx["buckets"]}
    assert [bucket["key"] for bucket in ctx["buckets"]] == [
        "overdue", "0-7", "8-14", "15-30", "31-60", "60+", "none"]
    assert all(bucket["label"] for bucket in ctx["buckets"])
    assert buckets["overdue"]["count"] == 1
    assert [d.pk for d in buckets["overdue"]["rows"]] == [invoice_dispute_overdue_a.pk]
    assert buckets["overdue"]["amount"] == Decimal("25.00")
    assert buckets["0-7"]["count"] == 1
    assert [d.pk for d in buckets["0-7"]["rows"]] == [invoice_dispute_open_a.pk]
    assert ctx["today"] == _invoice_today()
    assert ctx["bucket"] == ""
    assert ctx["stats"] == {"open": 2, "overdue": 1, "due_7d": 0, "resolved_30d": 1}
    assert [key for key, _label in ctx["bucket_choices"]][0] == "overdue"


def test_invoice_dispute_aging_bucket_filter_and_unknown_value(client_a,
                                                               invoice_dispute_open_a,
                                                               invoice_dispute_overdue_a):
    url = reverse("procurement:invoicedispute_aging")

    filtered = client_a.get(url, {"bucket": "overdue"})
    rows = [row for bucket in filtered.context["buckets"] for row in bucket["rows"]]
    assert [row.pk for row in rows] == [invoice_dispute_overdue_a.pk]
    assert filtered.context["bucket"] == "overdue"
    # The card headers still describe the WHOLE bucket, not the filtered slice.
    counts = {bucket["key"]: bucket["count"] for bucket in filtered.context["buckets"]}
    assert counts["0-7"] == 1

    unknown = client_a.get(url, {"bucket": "not-a-bucket"})
    assert unknown.status_code == 200
    seen = {row.pk for bucket in unknown.context["buckets"] for row in bucket["rows"]}
    assert seen == {invoice_dispute_open_a.pk, invoice_dispute_overdue_a.pk}


def test_invoice_dispute_aging_page_two_and_past_the_end(client_a, _invoice_bulk_disputes):
    url = reverse("procurement:invoicedispute_aging")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})

    first = {row.pk for bucket in page_one.context["buckets"] for row in bucket["rows"]}
    second = {row.pk for bucket in page_two.context["buckets"] for row in bucket["rows"]}
    assert len(first) == 15
    assert len(second) == 3
    assert first.isdisjoint(second)
    # The bucket header counts the whole bucket, which is why paging must not move it.
    counts = {bucket["key"]: bucket["count"] for bucket in page_two.context["buckets"]}
    assert counts["0-7"] == 18

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.context["page_obj"].number == 2


def test_invoice_dispute_aging_never_shows_another_workspace(client_a, invoice_dispute_open_a,
                                                             invoice_dispute_b):
    resp = client_a.get(reverse("procurement:invoicedispute_aging"))
    seen = {row.pk for bucket in resp.context["buckets"] for row in bucket["rows"]}
    assert seen == {invoice_dispute_open_a.pk}
