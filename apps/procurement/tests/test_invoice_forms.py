"""Procurement 6.13 Invoice & Voucher Management - form tests.

The forms are this sub-module's crafted-POST boundary, so this lane asserts five things
over and over:

1. **Nothing system-owned reaches a form field** (L20/L22). ``tenant``, the auto-numbers
   (``SIV-`` / ``DSP-``), the derived money block (``subtotal`` / ``tax_total`` / ``total`` /
   ``amount_paid`` / ``line_total`` / ``matched_qty``), the derived dates
   (``due_date`` / ``discount_date`` / ``discount_expiry_date`` / ``invoice_number_norm``),
   the match verdict (``match_status`` / ``match_notes``), the verb-only workflow ``status``,
   the ledger links (``bill`` / ``journal_entry``), the capture provenance
   (``source`` / ``extraction_confidence`` / ``extraction_raw_text``), the denormalised
   ``supplier``, the resolution block and every system ``*_at`` / ``*_by`` stamp stay OFF
   every form.
2. **Every FK ``<select>`` is tenant-scoped** - a field offered to tenant A never contains a
   tenant B row, and a tenant-less form (the superuser is ``tenant=None``) offers nothing at
   all except the GLOBAL ``accounting.Currency``.
3. **The narrowed ``<select>`` is UX, not the boundary.** Each cross-tenant case is asserted
   TWICE: once against the narrowed queryset (layer 1, "Select a valid choice") and once with
   the queryset deliberately widened to simulate a hand-edited POST (layer 2, the explicit
   ``_reject_foreign`` / model ``clean()`` rule message).
4. **Popped fields cannot 500 the POST.** ``purchase_order`` / ``goods_receipt`` (non-editable
   invoice) and ``invoice`` / ``invoice_line`` (saved dispute) are removed from
   ``self.fields``, and the overridden ``add_error`` re-keys the model-level error that still
   arrives for them onto ``NON_FIELD_ERRORS`` instead of raising ``ValueError``.
5. **Every hand-parsed number surface is friendly, never a 500** (L35) - ``NaN``,
   ``Infinity``, ``-Infinity``, garbage, ``1e400`` and over-``max_digits`` figures all land as
   field errors.

Dates derive from ``timezone.localdate()`` - never ``date.today()`` - so exact-date
assertions stay stable in the hours after local midnight (L16).
"""
import datetime
import importlib
import re
from decimal import Decimal

import pytest
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import InlineForeignKeyField
from django.utils import timezone

from apps.core.forms import TenantModelForm
from apps.core.forms._common import MAX_UPLOAD_BYTES
from apps.procurement.forms import (
    CaptureUploadForm,
    InvoiceDisputeForm,
    InvoiceVarianceAcceptForm,
    SupplierInvoiceForm,
    SupplierInvoiceLineForm,
    SupplierInvoiceLineFormSet,
)
from apps.procurement.forms._common import TenantUniqueMixin
from apps.procurement.forms.InvoiceVoucherManagement.SupplierInvoices import (
    _FX_CEILING,
    _safe_decimal,
)
from apps.procurement.models import (
    InvoiceDispute,
    InvoiceMatchVariance,
    SupplierInvoice,
    SupplierInvoiceLine,
)
from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote, PurchaseOrderLine

pytestmark = pytest.mark.django_db


# -- local helpers (module-level names are _invoice_* so a later sub-module cannot shadow) --------

_INVOICE_FOREIGN = "That record belongs to another workspace."
_INVOICE_INVALID_CHOICE = "Select a valid choice"

#: The exact ``Meta.fields`` each ModelForm ships, in order.
_INVOICE_HEADER_FIELDS = ["vendor", "purchase_order", "goods_receipt", "payment_term", "currency",
                          "tax_code", "invoice_type", "invoice_number", "external_ref",
                          "invoice_date", "posting_date", "discount_base", "discount_grace_days",
                          "fx_rate", "notes"]
_INVOICE_LINE_FIELDS = ["po_line", "receipt_line", "item", "description", "sku_hint", "uom_hint",
                        "quantity", "unit_price", "tax_rate_pct", "gl_account", "tax_code"]
_INVOICE_DISPUTE_FIELDS = ["invoice", "invoice_line", "reason_code", "supplier_contact",
                           "disputed_amount", "description", "assigned_to", "due_date"]

#: Every system-owned name that must never be keyable on the header.
_INVOICE_HEADER_FORBIDDEN = [
    "tenant", "number", "invoice_number_norm", "due_date", "discount_date",
    "discount_expiry_date", "subtotal", "tax_total", "total", "amount_paid",
    "match_basis", "match_status", "match_notes", "status", "source",
    "extraction_confidence", "extraction_raw_text", "approved_by", "approved_at",
    "bill", "journal_entry", "source_submission", "duplicate_of", "document",
    "created_at", "updated_at",
]
_INVOICE_DISPUTE_FORBIDDEN = [
    "tenant", "number", "supplier", "status", "resolution", "resolution_note", "resolved_at",
    "raised_by", "raised_at", "credit_memo_invoice", "created_at", "updated_at",
]
_INVOICE_LINE_FORBIDDEN = ["line_total", "matched_qty"]

#: L35 - the junk a hand-edited POST puts in a decimal box.
_INVOICE_JUNK_DECIMALS = ["NaN", "Infinity", "-Infinity", "abc", "1e400", "12,34"]


def _invoice_day(offset=0):
    """A date derived from the SAME basis the models use (L16)."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _invoice_iso(offset=0):
    return _invoice_day(offset).strftime("%Y-%m-%d")


def _invoice_widen(form, name, queryset):
    """Simulate a crafted POST: drop the narrowing so layer 2 (the explicit re-check) is what
    has to refuse the foreign pk."""
    form.fields[name].queryset = queryset
    return form


def _invoice_model(path):
    module_name, attr = path.rsplit(".", 1)
    return getattr(importlib.import_module(module_name), attr)


def _invoice_header_post(vendor=None, **overrides):
    """The minimum a header POST must carry (every non-blank field on the form)."""
    data = {
        "vendor": "",
        "purchase_order": "",
        "goods_receipt": "",
        "payment_term": "",
        "currency": "",
        "tax_code": "",
        "invoice_type": "standard",
        "invoice_number": "SUP-8001",
        "external_ref": "",
        "invoice_date": _invoice_iso(),
        "posting_date": "",
        "discount_base": "net_of_tax",
        "discount_grace_days": "0",
        "fx_rate": "",
        "notes": "",
    }
    if vendor is not None:
        data["vendor"] = str(vendor.pk)
    data.update(overrides)
    return data


def _invoice_line_post(**overrides):
    data = {
        "po_line": "",
        "receipt_line": "",
        "item": "",
        "description": "A4 copy paper 80gsm",
        "sku_hint": "",
        "uom_hint": "",
        "quantity": "2",
        "unit_price": "10.00",
        "tax_rate_pct": "0",
        "gl_account": "",
        "tax_code": "",
    }
    data.update(overrides)
    return data


def _invoice_formset_post(rows, initial=0):
    """The ``lines``-prefixed management form plus one dict per row."""
    data = {
        "lines-TOTAL_FORMS": str(len(rows)),
        "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(rows):
        for key, value in row.items():
            data[f"lines-{index}-{key}"] = value
    return data


def _invoice_dispute_post(invoice=None, **overrides):
    data = {
        "invoice": "",
        "invoice_line": "",
        "reason_code": "price",
        "supplier_contact": "",
        "disputed_amount": "50.00",
        "description": "Unit price billed above the agreed contract rate.",
        "assigned_to": "",
        "due_date": "",
    }
    if invoice is not None:
        data["invoice"] = str(invoice.pk)
    data.update(overrides)
    return data


def _invoice_grn_for(po, ref="DN-8001"):
    """A receipt against ``po`` - the vendor-agreement case needs a GRN whose order belongs to
    the OTHER supplier."""
    return GoodsReceiptNote.objects.create(tenant=po.tenant, purchase_order=po,
                                           receipt_date=timezone.localdate(), status="draft",
                                           delivery_note_ref=ref)


def _invoice_non_editable_names(model):
    """Every model field a form must never expose: ``editable=False``, ``auto_now`` and
    ``auto_now_add``."""
    names = set()
    for field in model._meta.get_fields():
        if not hasattr(field, "editable"):
            continue
        if not getattr(field, "editable", True):
            names.add(field.name)
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            names.add(field.name)
    return names


# =================================================================================================
# 1. Field surface - what each form does and does not expose (L20/L22)
# =================================================================================================

def test_invoice_header_form_field_list_is_exact(tenant_a):
    form = SupplierInvoiceForm(tenant=tenant_a)
    assert list(form.fields) == _INVOICE_HEADER_FIELDS


@pytest.mark.parametrize("name", _INVOICE_HEADER_FORBIDDEN)
def test_invoice_header_form_excludes_every_system_owned_field(tenant_a, name):
    """L20/L22 - a system-owned column on the form is one crafted POST away from being written."""
    form = SupplierInvoiceForm(tenant=tenant_a)
    assert name not in form.fields
    assert name not in SupplierInvoiceForm.base_fields


def test_invoice_header_form_never_exposes_a_non_editable_column(tenant_a):
    exposed = set(SupplierInvoiceForm(tenant=tenant_a).fields)
    assert exposed & _invoice_non_editable_names(SupplierInvoice) == set()


def test_invoice_line_form_field_list_is_exact(tenant_a):
    form = SupplierInvoiceLineForm(tenant=tenant_a)
    assert list(form.fields) == _INVOICE_LINE_FIELDS


@pytest.mark.parametrize("name", _INVOICE_LINE_FORBIDDEN + ["invoice"])
def test_invoice_line_form_excludes_derived_and_parent_fields(tenant_a, name):
    """``line_total`` / ``matched_qty`` are derived; ``invoice`` comes from the URL or the
    formset instance, never the POST body."""
    assert name not in SupplierInvoiceLineForm(tenant=tenant_a).fields
    assert name not in SupplierInvoiceLineForm.base_fields


def test_invoice_line_form_never_exposes_a_non_editable_column(tenant_a):
    exposed = set(SupplierInvoiceLineForm(tenant=tenant_a).fields)
    assert exposed & _invoice_non_editable_names(SupplierInvoiceLine) == set()


def test_invoice_dispute_form_field_list_is_exact(tenant_a):
    form = InvoiceDisputeForm(tenant=tenant_a)
    assert list(form.fields) == _INVOICE_DISPUTE_FIELDS


@pytest.mark.parametrize("name", _INVOICE_DISPUTE_FORBIDDEN)
def test_invoice_dispute_form_excludes_every_system_owned_field(tenant_a, name):
    form = InvoiceDisputeForm(tenant=tenant_a)
    assert name not in form.fields
    assert name not in InvoiceDisputeForm.base_fields


def test_invoice_dispute_form_never_exposes_a_non_editable_column(tenant_a):
    exposed = set(InvoiceDisputeForm(tenant=tenant_a).fields)
    assert exposed & _invoice_non_editable_names(InvoiceDispute) == set()


def test_invoice_line_formset_base_form_field_list_is_exact():
    assert list(SupplierInvoiceLineFormSet.form.base_fields) == _INVOICE_LINE_FIELDS


def test_invoice_line_formset_prefix_is_lines(invoice_draft_a, tenant_a):
    """The prefix is the child FK's ``related_name`` - the template loop and the POST body agree
    on ``lines-*`` without either side hard-coding it twice."""
    formset = SupplierInvoiceLineFormSet(instance=invoice_draft_a,
                                         form_kwargs={"tenant": tenant_a})
    assert formset.prefix == "lines"
    assert "lines-TOTAL_FORMS" in str(formset.management_form)


def test_invoice_variance_accept_form_is_a_plain_form_with_only_a_note():
    """There is deliberately NO ModelForm over a variance - it is evidence, not input."""
    form = InvoiceVarianceAcceptForm()
    assert list(form.fields) == ["note"]
    assert not isinstance(form, forms.ModelForm)


def test_invoice_forms_package_ships_no_modelform_over_a_match_variance():
    package = importlib.import_module("apps.procurement.forms")

    offenders = []
    for name in dir(package):
        candidate = getattr(package, name)
        meta = getattr(candidate, "_meta", None)
        if getattr(meta, "model", None) is InvoiceMatchVariance:
            offenders.append(name)
    assert offenders == []


def test_invoice_capture_upload_form_carries_only_the_file():
    """The ``core.Document`` is minted by the view - the form validates a file, it does not model
    one, so no provenance column is keyable."""
    form = CaptureUploadForm()
    assert list(form.fields) == ["document_file"]
    assert not isinstance(form, forms.ModelForm)


def test_invoice_header_form_mixes_tenant_unique_before_the_model_form():
    """``TenantUniqueMixin`` FIRST is what stamps ``instance.tenant`` before ``full_clean()``;
    reversed, every CREATE would be falsely rejected as cross-tenant."""
    order = SupplierInvoiceForm.__mro__
    assert order.index(TenantUniqueMixin) < order.index(TenantModelForm)


def test_invoice_dispute_form_mixes_tenant_unique_before_the_model_form():
    order = InvoiceDisputeForm.__mro__
    assert order.index(TenantUniqueMixin) < order.index(TenantModelForm)


def test_invoice_line_form_has_no_tenant_unique_mixin(tenant_a):
    """The child carries no ``tenant`` column to stamp and no unique-together to repair."""
    assert TenantUniqueMixin not in SupplierInvoiceLineForm.__mro__
    assert isinstance(SupplierInvoiceLineForm(tenant=tenant_a), TenantModelForm)


def test_invoice_header_form_stamps_the_instance_tenant_up_front(tenant_a):
    form = SupplierInvoiceForm(tenant=tenant_a)
    assert form.instance.tenant_id == tenant_a.pk


# =================================================================================================
# 2. Required fields and the happy path
# =================================================================================================

def test_invoice_header_form_requires_vendor_number_and_date(tenant_a):
    form = SupplierInvoiceForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("vendor", "invoice_number", "invoice_date", "invoice_type", "discount_base",
                 "discount_grace_days"):
        assert name in form.errors, f"{name} should be required"


def test_invoice_header_form_rejects_a_whitespace_only_invoice_number(tenant_a, invoice_vendor_a):
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a, invoice_number="   "),
                               tenant=tenant_a)
    assert not form.is_valid()
    assert "invoice_number" in form.errors


def test_invoice_header_form_valid_create_saves_with_the_request_tenant(tenant_a,
                                                                       invoice_vendor_a):
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert re.match(r"^SIV-\d{5}$", obj.number)
    assert obj.invoice_number_norm == "SUP8001"
    assert obj.status == "draft"
    assert obj.match_status == "not_run"
    assert obj.total == Decimal("0.00")
    assert obj.approved_by_id is None and obj.journal_entry_id is None


def test_invoice_header_form_ignores_a_posted_due_date_and_derives_it(tenant_a,
                                                                     invoice_vendor_a,
                                                                     invoice_term_a):
    """A typed due date is exactly how a discount gets silently missed - the term owns it."""
    data = _invoice_header_post(invoice_vendor_a, payment_term=str(invoice_term_a.pk))
    data["due_date"] = _invoice_iso(999)
    data["discount_date"] = _invoice_iso(999)
    data["total"] = "999999.00"
    form = SupplierInvoiceForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.due_date == _invoice_day(30)
    assert obj.discount_date == _invoice_day(10)
    assert obj.total == Decimal("0.00")


def test_invoice_header_form_rejects_a_posting_date_before_the_invoice_date(tenant_a,
                                                                           invoice_vendor_a):
    form = SupplierInvoiceForm(
        _invoice_header_post(invoice_vendor_a, invoice_date=_invoice_iso(0),
                             posting_date=_invoice_iso(-3)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "posting_date" in form.errors


def test_invoice_header_form_rejects_grace_days_beyond_a_year(tenant_a, invoice_vendor_a):
    form = SupplierInvoiceForm(
        _invoice_header_post(invoice_vendor_a, discount_grace_days="400"), tenant=tenant_a)
    assert not form.is_valid()
    assert "discount_grace_days" in form.errors


def test_invoice_header_form_rejects_negative_grace_days(tenant_a, invoice_vendor_a):
    form = SupplierInvoiceForm(
        _invoice_header_post(invoice_vendor_a, discount_grace_days="-1"), tenant=tenant_a)
    assert not form.is_valid()
    assert "discount_grace_days" in form.errors


def test_invoice_line_form_requires_quantity_price_and_tax_rate(tenant_a):
    form = SupplierInvoiceLineForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("quantity", "unit_price", "tax_rate_pct"):
        assert name in form.errors, f"{name} should be required"


def test_invoice_line_form_valid_row_saves_against_its_header(tenant_a, invoice_draft_a,
                                                              gl_expense_a):
    form = SupplierInvoiceLineForm(
        _invoice_line_post(gl_account=str(gl_expense_a.pk)),
        instance=SupplierInvoiceLine(invoice=invoice_draft_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.invoice_id == invoice_draft_a.pk
    assert row.line_total == Decimal("20.00")
    assert row.matched_qty == Decimal("0.0000")
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.total == Decimal("20.00")


def test_invoice_line_form_rejects_a_tax_rate_above_one_hundred(tenant_a, invoice_draft_a,
                                                                gl_expense_a):
    form = SupplierInvoiceLineForm(
        _invoice_line_post(gl_account=str(gl_expense_a.pk), tax_rate_pct="120"),
        instance=SupplierInvoiceLine(invoice=invoice_draft_a), tenant=tenant_a)
    assert not form.is_valid()
    assert "tax_rate_pct" in form.errors


def test_invoice_dispute_form_requires_invoice_reason_amount_and_description(tenant_a):
    form = InvoiceDisputeForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("invoice", "reason_code", "disputed_amount", "description"):
        assert name in form.errors, f"{name} should be required"


def test_invoice_dispute_form_valid_create_stamps_tenant_supplier_number_and_sla(
        tenant_a, invoice_draft_a, invoice_line_a):
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_draft_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert re.match(r"^DSP-\d{5}$", obj.number)
    # ``supplier`` is denormalised in save() - never asked for, never postable.
    assert obj.supplier_id == invoice_draft_a.vendor_id
    assert obj.status == "open"
    assert obj.resolution == "" and obj.resolved_at is None and obj.raised_by_id is None
    assert obj.due_date == _invoice_day(InvoiceDispute.SLA_DAYS)


def test_invoice_dispute_form_ignores_a_posted_status_and_supplier(tenant_a, invoice_draft_a,
                                                                   invoice_line_a,
                                                                   invoice_vendor_other_a):
    data = _invoice_dispute_post(invoice_draft_a)
    data["status"] = "closed"
    data["supplier"] = str(invoice_vendor_other_a.pk)
    data["resolution"] = "withdrawn"
    data["number"] = "DSP-99999"
    form = InvoiceDisputeForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "open"
    assert obj.supplier_id == invoice_draft_a.vendor_id
    assert obj.resolution == ""
    assert obj.number != "DSP-99999"


def test_invoice_dispute_form_rejects_a_due_date_outside_the_calendar(tenant_a, invoice_draft_a,
                                                                     invoice_line_a):
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_draft_a, due_date="1899-12-31"),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert "due_date" in form.errors


# =================================================================================================
# 3. Tenant-scoped querysets - layer 1 (the narrowed <select>)
# =================================================================================================

@pytest.mark.parametrize("name", ["vendor", "purchase_order", "goods_receipt", "payment_term",
                                  "tax_code"])
def test_invoice_header_form_dropdowns_hold_no_tenant_b_rows(
        tenant_a, name, invoice_vendor_a, invoice_vendor_b, invoice_po_a, invoice_po_b,
        invoice_grn_a, invoice_grn_b, invoice_term_a, invoice_term_b, invoice_taxcode_a,
        invoice_taxcode_b):
    mine = {"vendor": invoice_vendor_a, "purchase_order": invoice_po_a,
            "goods_receipt": invoice_grn_a, "payment_term": invoice_term_a,
            "tax_code": invoice_taxcode_a}[name]
    theirs = {"vendor": invoice_vendor_b, "purchase_order": invoice_po_b,
              "goods_receipt": invoice_grn_b, "payment_term": invoice_term_b,
              "tax_code": invoice_taxcode_b}[name]
    queryset = SupplierInvoiceForm(tenant=tenant_a).fields[name].queryset
    assert mine in queryset
    assert theirs not in queryset


def test_invoice_header_form_currency_dropdown_stays_global(tenant_a, usd):
    """accounting.Currency has NO tenant column - scoping it would empty the dropdown."""
    assert usd in SupplierInvoiceForm(tenant=tenant_a).fields["currency"].queryset
    assert usd in SupplierInvoiceForm(tenant=None).fields["currency"].queryset


@pytest.mark.parametrize("name", ["vendor", "purchase_order", "goods_receipt", "payment_term",
                                  "tax_code"])
def test_invoice_header_form_offers_nothing_to_a_tenantless_user(
        name, invoice_vendor_a, invoice_po_a, invoice_grn_a, invoice_term_a, invoice_taxcode_a):
    """The superuser is ``tenant=None`` - it must not be OFFERED another workspace's rows."""
    assert SupplierInvoiceForm(tenant=None).fields[name].queryset.count() == 0


def test_invoice_header_form_tenantless_post_is_refused(invoice_vendor_a):
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a), tenant=None)
    assert not form.is_valid()
    assert "vendor" in form.errors


@pytest.mark.parametrize("name,other", [("vendor", "invoice_vendor_b"),
                                        ("purchase_order", "invoice_po_b"),
                                        ("goods_receipt", "invoice_grn_b"),
                                        ("payment_term", "invoice_term_b"),
                                        ("tax_code", "invoice_taxcode_b")])
def test_invoice_header_form_narrowed_select_refuses_a_tenant_b_pk(request, tenant_a,
                                                                   invoice_vendor_a, name, other):
    """Layer 1: the pk is not in the narrowed queryset at all."""
    foreign = request.getfixturevalue(other)
    # One dict, then the crafted key - passing ``vendor=`` twice (positionally AND through
    # ``**{name: ...}``) is a TypeError, and every OTHER field must stay a valid tenant-A value so
    # the only thing under test is the foreign pk.
    data = _invoice_header_post(invoice_vendor_a)
    data[name] = str(foreign.pk)
    form = SupplierInvoiceForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert any(_INVOICE_INVALID_CHOICE in message for message in form.errors[name])


# =================================================================================================
# 4. Tenant-scoped querysets - layer 2 (the crafted POST past the narrowed <select>)
# =================================================================================================

@pytest.mark.parametrize("name,other,model_path", [
    ("vendor", "invoice_vendor_b", "apps.core.models.Party"),
    ("payment_term", "invoice_term_b", "apps.accounting.models.PaymentTerm"),
    ("tax_code", "invoice_taxcode_b", "apps.accounting.models.TaxCode"),
])
def test_invoice_header_form_rejects_a_widened_tenant_b_pk(request, tenant_a, invoice_vendor_a,
                                                           name, other, model_path):
    """Layer 2: with the narrowing removed, the explicit ``_reject_foreign`` re-check is what has
    to refuse the foreign row - a narrowed ``<select>`` is UX, not a boundary."""
    foreign = request.getfixturevalue(other)
    data = _invoice_header_post(invoice_vendor_a)
    data[name] = str(foreign.pk)
    form = SupplierInvoiceForm(data, tenant=tenant_a)
    _invoice_widen(form, name, _invoice_model(model_path).objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors[name]
    assert not SupplierInvoice.objects.filter(invoice_number="SUP-8001").exists()


def test_invoice_header_form_rejects_a_widened_tenant_b_purchase_order(tenant_a,
                                                                      invoice_vendor_a,
                                                                      invoice_po_b):
    from apps.scm.models import PurchaseOrder

    data = _invoice_header_post(invoice_vendor_a, purchase_order=str(invoice_po_b.pk))
    form = SupplierInvoiceForm(data, tenant=tenant_a)
    _invoice_widen(form, "purchase_order", PurchaseOrder.objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors["purchase_order"]


def test_invoice_header_form_rejects_a_widened_tenant_b_goods_receipt(tenant_a, invoice_vendor_a,
                                                                     invoice_grn_b):
    data = _invoice_header_post(invoice_vendor_a, goods_receipt=str(invoice_grn_b.pk))
    form = SupplierInvoiceForm(data, tenant=tenant_a)
    _invoice_widen(form, "goods_receipt", GoodsReceiptNote.objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors["goods_receipt"]


def test_invoice_header_form_rejects_a_purchase_order_from_another_vendor(tenant_a,
                                                                         invoice_vendor_a,
                                                                         invoice_po_other_a):
    """Same tenant, WRONG supplier - L40 vendor agreement, on the field the user can change."""
    form = SupplierInvoiceForm(
        _invoice_header_post(invoice_vendor_a, purchase_order=str(invoice_po_other_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That purchase order belongs to a different vendor." in form.errors["purchase_order"]


def test_invoice_header_form_rejects_a_goods_receipt_from_another_vendor(tenant_a,
                                                                        invoice_vendor_a,
                                                                        invoice_po_other_a):
    grn = _invoice_grn_for(invoice_po_other_a)
    form = SupplierInvoiceForm(
        _invoice_header_post(invoice_vendor_a, goods_receipt=str(grn.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "That goods receipt belongs to a different vendor." in form.errors["goods_receipt"]


# =================================================================================================
# 5. Popped fields - the non-editable header and the saved dispute
# =================================================================================================

def test_invoice_header_form_keeps_the_documents_on_an_editable_invoice(tenant_a,
                                                                       invoice_draft_a):
    form = SupplierInvoiceForm(instance=invoice_draft_a, tenant=tenant_a)
    assert "purchase_order" in form.fields
    assert "goods_receipt" in form.fields


@pytest.mark.parametrize("name", ["purchase_order", "goods_receipt"])
def test_invoice_header_form_pops_the_documents_on_a_locked_invoice(tenant_a, invoice_pending_a,
                                                                    name):
    """Re-pointing a captured invoice would orphan its lines - dropped from the form rather than
    trusted to the template to hide."""
    form = SupplierInvoiceForm(instance=invoice_pending_a, tenant=tenant_a)
    assert name not in form.fields


def test_invoice_header_form_crafted_post_cannot_repoint_a_locked_invoice(tenant_a,
                                                                          invoice_pending_a,
                                                                          invoice_vendor_a,
                                                                          invoice_po_other_a):
    original = invoice_pending_a.purchase_order_id
    data = _invoice_header_post(invoice_vendor_a,
                                invoice_number=invoice_pending_a.invoice_number,
                                purchase_order=str(invoice_po_other_a.pk))
    form = SupplierInvoiceForm(data, instance=invoice_pending_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.purchase_order_id == original
    assert obj.status == "pending_approval"


def test_invoice_header_form_rekeys_a_popped_field_error_instead_of_500ing(tenant_a,
                                                                          invoice_pending_a,
                                                                          invoice_vendor_other_a):
    """``Model.clean()`` still validates the popped ``purchase_order``; Django would raise
    ``ValueError`` for a key with no matching field, i.e. a 500 on POST."""
    data = _invoice_header_post(invoice_vendor_other_a,
                                invoice_number=invoice_pending_a.invoice_number)
    form = SupplierInvoiceForm(data, instance=invoice_pending_a, tenant=tenant_a)
    assert not form.is_valid()          # no ValueError escaped
    assert NON_FIELD_ERRORS in form.errors
    assert any("different vendor" in message for message in form.errors[NON_FIELD_ERRORS])


def test_invoice_header_form_add_error_reroutes_an_unknown_field(tenant_a, invoice_pending_a):
    form = SupplierInvoiceForm(_invoice_header_post(), instance=invoice_pending_a,
                               tenant=tenant_a)
    form.is_valid()
    form.add_error("purchase_order", "manual message")
    assert "manual message" in form.errors[NON_FIELD_ERRORS]


@pytest.mark.parametrize("name", ["invoice", "invoice_line"])
def test_invoice_dispute_form_pops_the_document_fields_on_edit(tenant_a, invoice_dispute_open_a,
                                                               name):
    assert name in InvoiceDisputeForm(tenant=tenant_a).fields
    assert name not in InvoiceDisputeForm(instance=invoice_dispute_open_a, tenant=tenant_a).fields


def test_invoice_dispute_form_crafted_post_cannot_repoint_a_saved_dispute(tenant_a,
                                                                          invoice_dispute_open_a,
                                                                          invoice_captured_a):
    original_invoice = invoice_dispute_open_a.invoice_id
    original_line = invoice_dispute_open_a.invoice_line_id
    data = _invoice_dispute_post(invoice_captured_a, invoice_line="")
    form = InvoiceDisputeForm(data, instance=invoice_dispute_open_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.invoice_id == original_invoice
    assert obj.invoice_line_id == original_line


def test_invoice_dispute_form_add_error_reroutes_a_popped_field(tenant_a,
                                                                invoice_dispute_open_a):
    form = InvoiceDisputeForm(_invoice_dispute_post(), instance=invoice_dispute_open_a,
                              tenant=tenant_a)
    form.is_valid()
    form.add_error("invoice", "manual message")
    assert "manual message" in form.errors[NON_FIELD_ERRORS]


def test_invoice_dispute_form_rekeys_a_model_error_for_a_popped_field(tenant_a,
                                                                     invoice_dispute_open_a,
                                                                     invoice_captured_a,
                                                                     gl_expense_a):
    """A model-level ``invoice_line`` error still arrives on edit; re-keyed, not raised."""
    stray = SupplierInvoiceLine.objects.create(invoice=invoice_captured_a,
                                               description="Stray line",
                                               quantity=Decimal("1"),
                                               unit_price=Decimal("5.00"),
                                               gl_account=gl_expense_a)
    invoice_dispute_open_a.invoice_line = stray
    form = InvoiceDisputeForm(_invoice_dispute_post(), instance=invoice_dispute_open_a,
                              tenant=tenant_a)
    assert not form.is_valid()          # no ValueError escaped
    assert NON_FIELD_ERRORS in form.errors
    assert any("different invoice" in message for message in form.errors[NON_FIELD_ERRORS])


# =================================================================================================
# 6. The line form's two tenant-less children and its sign / account rules
# =================================================================================================

def test_invoice_line_form_po_line_dropdown_is_narrowed_to_the_header_order(tenant_a,
                                                                           invoice_draft_a,
                                                                           invoice_po_line_a,
                                                                           invoice_po_line2_a,
                                                                           invoice_po_other_a):
    form = SupplierInvoiceLineForm(instance=SupplierInvoiceLine(invoice=invoice_draft_a),
                                   tenant=tenant_a)
    queryset = form.fields["po_line"].queryset
    assert invoice_po_line_a in queryset
    assert invoice_po_line2_a in queryset
    assert invoice_po_other_a.lines.first() not in queryset


def test_invoice_line_form_po_line_dropdown_stays_wide_on_a_po_less_invoice(tenant_a,
                                                                           invoice_captured_a,
                                                                           invoice_po_line_a,
                                                                           invoice_po_other_a):
    """A service (PO-less) invoice has no order to narrow to - every tenant-A ordered line is
    offered, and none of tenant B's."""
    form = SupplierInvoiceLineForm(instance=SupplierInvoiceLine(invoice=invoice_captured_a),
                                   tenant=tenant_a)
    queryset = form.fields["po_line"].queryset
    assert invoice_po_line_a in queryset
    assert invoice_po_other_a.lines.first() in queryset


def test_invoice_line_form_po_line_dropdown_excludes_tenant_b_rows(tenant_a, invoice_captured_a,
                                                                   invoice_po_line_b):
    form = SupplierInvoiceLineForm(instance=SupplierInvoiceLine(invoice=invoice_captured_a),
                                   tenant=tenant_a)
    assert invoice_po_line_b not in form.fields["po_line"].queryset


def test_invoice_line_form_receipt_line_dropdown_is_narrowed_to_the_chosen_po_line(
        tenant_a, invoice_draft_a, invoice_po_line_a, invoice_grn_line_a, invoice_grn_short_a):
    form = SupplierInvoiceLineForm(
        instance=SupplierInvoiceLine(invoice=invoice_draft_a, po_line=invoice_po_line_a),
        tenant=tenant_a)
    queryset = form.fields["receipt_line"].queryset
    assert invoice_grn_line_a in queryset
    assert invoice_grn_short_a.lines.first() not in queryset


def test_invoice_line_form_receipt_line_dropdown_excludes_tenant_b_rows(tenant_a,
                                                                        invoice_draft_a,
                                                                        invoice_grn_line_b):
    form = SupplierInvoiceLineForm(instance=SupplierInvoiceLine(invoice=invoice_draft_a),
                                   tenant=tenant_a)
    assert invoice_grn_line_b not in form.fields["receipt_line"].queryset


@pytest.mark.parametrize("name,other,model_path", [
    ("item", "invoice_item_b", "apps.scm.models.Item"),
    ("gl_account", "gl_expense_b", "apps.accounting.models.GLAccount"),
    ("tax_code", "invoice_taxcode_b", "apps.accounting.models.TaxCode"),
])
def test_invoice_line_form_rejects_a_widened_tenant_b_pk(request, tenant_a, invoice_draft_a,
                                                         gl_expense_a, name, other, model_path):
    foreign = request.getfixturevalue(other)
    # ``gl_account`` is both the always-valid baseline AND one of the crafted scopes, so the
    # baseline is built first and the crafted key overwrites it - naming it twice in one call is a
    # TypeError.
    data = _invoice_line_post(gl_account=str(gl_expense_a.pk))
    data[name] = str(foreign.pk)
    form = SupplierInvoiceLineForm(data, instance=SupplierInvoiceLine(invoice=invoice_draft_a),
                                   tenant=tenant_a)
    _invoice_widen(form, name, _invoice_model(model_path).objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors[name]
    assert not invoice_draft_a.lines.exists()


def test_invoice_line_form_rejects_a_widened_tenant_b_po_line(tenant_a, invoice_captured_a,
                                                              invoice_po_line_b, gl_expense_a):
    """``scm.PurchaseOrderLine`` has NO tenant column - it is re-checked through its own header,
    which is the only place a tenant can be read off it."""
    data = _invoice_line_post(gl_account=str(gl_expense_a.pk), po_line=str(invoice_po_line_b.pk))
    form = SupplierInvoiceLineForm(data, instance=SupplierInvoiceLine(invoice=invoice_captured_a),
                                   tenant=tenant_a)
    _invoice_widen(form, "po_line", PurchaseOrderLine.objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors["po_line"]


def test_invoice_line_form_rejects_a_widened_tenant_b_receipt_line(tenant_a, invoice_captured_a,
                                                                   invoice_grn_line_b,
                                                                   gl_expense_a):
    data = _invoice_line_post(gl_account=str(gl_expense_a.pk),
                              receipt_line=str(invoice_grn_line_b.pk))
    form = SupplierInvoiceLineForm(data, instance=SupplierInvoiceLine(invoice=invoice_captured_a),
                                   tenant=tenant_a)
    _invoice_widen(form, "receipt_line", GoodsReceiptLine.objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors["receipt_line"]


def test_invoice_line_form_rejects_a_po_line_from_a_different_order(tenant_a, invoice_draft_a,
                                                                    invoice_po_other_a,
                                                                    gl_expense_a):
    """Same workspace, wrong order - the whole match would be judged against the wrong prices."""
    foreign_line = invoice_po_other_a.lines.first()
    data = _invoice_line_post(gl_account=str(gl_expense_a.pk), po_line=str(foreign_line.pk))
    form = SupplierInvoiceLineForm(data, instance=SupplierInvoiceLine(invoice=invoice_draft_a),
                                   tenant=tenant_a)
    _invoice_widen(form, "po_line", PurchaseOrderLine.objects.all())
    assert not form.is_valid()
    assert "That line belongs to a different purchase order." in form.errors["po_line"]


def test_invoice_line_form_rejects_a_receipt_line_booked_against_another_order_line(
        tenant_a, invoice_draft_a, invoice_po_line_a, invoice_grn_short_a, gl_expense_a):
    stray_receipt = invoice_grn_short_a.lines.first()
    data = _invoice_line_post(gl_account=str(gl_expense_a.pk), po_line=str(invoice_po_line_a.pk),
                              receipt_line=str(stray_receipt.pk))
    form = SupplierInvoiceLineForm(data, instance=SupplierInvoiceLine(invoice=invoice_draft_a),
                                   tenant=tenant_a)
    _invoice_widen(form, "receipt_line", GoodsReceiptLine.objects.all())
    assert not form.is_valid()
    assert ("That receipt line was booked against a different order line."
            in form.errors["receipt_line"])


def test_invoice_line_form_requires_a_gl_account_on_a_non_matched_invoice(tenant_a,
                                                                         invoice_draft_a):
    """``match_basis == 'none'`` means there is no ordered line to derive the expense account
    from - naming it is the only way the bill can post."""
    assert invoice_draft_a.match_basis == "none"
    form = SupplierInvoiceLineForm(_invoice_line_post(),
                                   instance=SupplierInvoiceLine(invoice=invoice_draft_a),
                                   tenant=tenant_a)
    assert not form.is_valid()
    assert ("A line on a non-PO invoice must name the GL account to post to."
            in form.errors["gl_account"])


def test_invoice_line_form_rejects_a_positive_line_on_a_credit_memo(tenant_a,
                                                                    invoice_credit_memo_a,
                                                                    gl_expense_a):
    form = SupplierInvoiceLineForm(
        _invoice_line_post(gl_account=str(gl_expense_a.pk), quantity="1", unit_price="10.00"),
        instance=SupplierInvoiceLine(invoice=invoice_credit_memo_a), tenant=tenant_a)
    assert not form.is_valid()
    assert "A credit memo line cannot carry a positive value." in form.errors["unit_price"]


def test_invoice_line_form_accepts_a_negative_line_on_a_credit_memo(tenant_a,
                                                                    invoice_credit_memo_a,
                                                                    gl_expense_a):
    form = SupplierInvoiceLineForm(
        _invoice_line_post(gl_account=str(gl_expense_a.pk), quantity="1", unit_price="-10.00"),
        instance=SupplierInvoiceLine(invoice=invoice_credit_memo_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.line_total == Decimal("-10.00")


def test_invoice_line_form_rejects_a_negative_line_on_a_standard_invoice(tenant_a,
                                                                        invoice_draft_a,
                                                                        gl_expense_a):
    form = SupplierInvoiceLineForm(
        _invoice_line_post(gl_account=str(gl_expense_a.pk), unit_price="-10.00"),
        instance=SupplierInvoiceLine(invoice=invoice_draft_a), tenant=tenant_a)
    assert not form.is_valid()
    assert "Only a credit memo may carry a negative line." in form.errors["unit_price"]


# =================================================================================================
# 7. The inline formset
# =================================================================================================

def test_invoice_line_formset_saves_a_row_and_redrives_the_header_money(tenant_a,
                                                                        invoice_draft_a,
                                                                        gl_expense_a):
    data = _invoice_formset_post([_invoice_line_post(gl_account=str(gl_expense_a.pk),
                                                     quantity="3", unit_price="10.00",
                                                     tax_rate_pct="10")])
    formset = SupplierInvoiceLineFormSet(data, instance=invoice_draft_a,
                                         form_kwargs={"tenant": tenant_a})
    assert formset.is_valid(), formset.errors
    formset.save()
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.subtotal == Decimal("30.00")
    assert invoice_draft_a.tax_total == Decimal("3.00")
    assert invoice_draft_a.total == Decimal("33.00")


def test_invoice_line_formset_rows_carry_an_inline_parent_field_not_a_postable_one(
        tenant_a, invoice_draft_a):
    formset = SupplierInvoiceLineFormSet(instance=invoice_draft_a,
                                         form_kwargs={"tenant": tenant_a})
    row = formset.forms[0]
    assert isinstance(row.fields["invoice"], InlineForeignKeyField)
    assert "invoice" not in SupplierInvoiceLineFormSet.form.base_fields


def test_invoice_line_formset_refuses_a_crafted_parent_pk(tenant_a, invoice_draft_a, invoice_b,
                                                          gl_expense_a):
    """A POSTed ``lines-0-invoice`` pointing anywhere but the formset instance is refused - the
    header comes from the URL, never the body."""
    data = _invoice_formset_post([_invoice_line_post(gl_account=str(gl_expense_a.pk),
                                                     invoice=str(invoice_b.pk))])
    formset = SupplierInvoiceLineFormSet(data, instance=invoice_draft_a,
                                         form_kwargs={"tenant": tenant_a})
    assert not formset.is_valid()
    assert not invoice_draft_a.lines.exists()
    assert invoice_b.lines.count() == 0


def test_invoice_line_formset_narrowed_row_refuses_a_tenant_b_item(tenant_a, invoice_draft_a,
                                                                   invoice_item_b, gl_expense_a):
    data = _invoice_formset_post([_invoice_line_post(gl_account=str(gl_expense_a.pk),
                                                     item=str(invoice_item_b.pk))])
    formset = SupplierInvoiceLineFormSet(data, instance=invoice_draft_a,
                                         form_kwargs={"tenant": tenant_a})
    assert not formset.is_valid()
    assert any(_INVOICE_INVALID_CHOICE in message
               for message in formset.forms[0].errors.get("item", []))
    assert not invoice_draft_a.lines.exists()


def test_invoice_line_formset_existing_row_is_narrowed_to_the_header_order(tenant_a,
                                                                          invoice_draft_a,
                                                                          invoice_line_a,
                                                                          invoice_po_other_a):
    formset = SupplierInvoiceLineFormSet(instance=invoice_draft_a,
                                         form_kwargs={"tenant": tenant_a})
    saved_row = [row for row in formset.forms if row.instance.pk][0]
    assert invoice_po_other_a.lines.first() not in saved_row.fields["po_line"].queryset


def test_invoice_line_formset_passes_the_tenant_to_every_row(tenant_a, invoice_draft_a,
                                                             invoice_item_a, invoice_item_b):
    formset = SupplierInvoiceLineFormSet(instance=invoice_draft_a,
                                         form_kwargs={"tenant": tenant_a})
    queryset = formset.forms[0].fields["item"].queryset
    assert invoice_item_a in queryset
    assert invoice_item_b not in queryset


# =================================================================================================
# 8. Dispute form - scoping, the line-through-its-header check and the amount cap
# =================================================================================================

def test_invoice_dispute_form_invoice_dropdown_excludes_tenant_b_rows(tenant_a, invoice_draft_a,
                                                                      invoice_b):
    queryset = InvoiceDisputeForm(tenant=tenant_a).fields["invoice"].queryset
    assert invoice_draft_a in queryset
    assert invoice_b not in queryset


def test_invoice_dispute_form_invoice_line_dropdown_is_scoped_through_its_header(tenant_a,
                                                                                 invoice_line_a,
                                                                                 invoice_line_b):
    """``SupplierInvoiceLine`` carries no tenant column - it is narrowed via ``invoice__tenant``."""
    queryset = InvoiceDisputeForm(tenant=tenant_a).fields["invoice_line"].queryset
    assert invoice_line_a in queryset
    assert invoice_line_b not in queryset


def test_invoice_dispute_form_line_dropdown_narrows_to_the_disputed_invoice_on_edit(
        tenant_a, invoice_dispute_escalated_a, invoice_line_a):
    """Popped on edit, but the queryset is still narrowed - belt and braces on the same rule."""
    form = InvoiceDisputeForm(instance=invoice_dispute_escalated_a, tenant=tenant_a)
    assert "invoice_line" not in form.fields
    unbound = InvoiceDisputeForm(tenant=tenant_a)
    assert invoice_line_a in unbound.fields["invoice_line"].queryset


def test_invoice_dispute_form_assigned_to_dropdown_is_tenant_scoped(tenant_a, admin_user,
                                                                    member_user, admin_b):
    queryset = InvoiceDisputeForm(tenant=tenant_a).fields["assigned_to"].queryset
    assert admin_user in queryset
    assert member_user in queryset
    assert admin_b not in queryset


@pytest.mark.parametrize("name", ["invoice", "invoice_line"])
def test_invoice_dispute_form_offers_nothing_to_a_tenantless_user(name, invoice_draft_a,
                                                                  invoice_line_a):
    assert InvoiceDisputeForm(tenant=None).fields[name].queryset.count() == 0


def test_invoice_dispute_form_narrowed_select_refuses_a_tenant_b_invoice(tenant_a, invoice_b):
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_b, disputed_amount="0.00"),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert any(_INVOICE_INVALID_CHOICE in message for message in form.errors["invoice"])


def test_invoice_dispute_form_rejects_a_widened_tenant_b_invoice(tenant_a, invoice_b):
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_b, disputed_amount="0.00"),
                              tenant=tenant_a)
    _invoice_widen(form, "invoice", SupplierInvoice.objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors["invoice"]
    assert not InvoiceDispute.objects.filter(tenant=tenant_a).exists()


def test_invoice_dispute_form_rejects_a_widened_tenant_b_invoice_line(tenant_a, invoice_draft_a,
                                                                      invoice_line_a,
                                                                      invoice_line_b):
    form = InvoiceDisputeForm(
        _invoice_dispute_post(invoice_draft_a, invoice_line=str(invoice_line_b.pk)),
        tenant=tenant_a)
    _invoice_widen(form, "invoice_line", SupplierInvoiceLine.objects.all())
    assert not form.is_valid()
    assert _INVOICE_FOREIGN in form.errors["invoice_line"]


def test_invoice_dispute_form_rejects_a_line_from_another_invoice(tenant_a, invoice_captured_a,
                                                                  invoice_line_a):
    form = InvoiceDisputeForm(
        _invoice_dispute_post(invoice_captured_a, disputed_amount="0.00",
                              invoice_line=str(invoice_line_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That line belongs to a different invoice." in form.errors["invoice_line"]


def test_invoice_dispute_form_caps_the_amount_at_the_invoice_total(tenant_a, invoice_draft_a,
                                                                   invoice_line_a):
    assert invoice_draft_a.total == Decimal("250.00")
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_draft_a, disputed_amount="999.00"),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert ("The disputed amount cannot be more than the invoice total."
            in form.errors["disputed_amount"])


def test_invoice_dispute_form_allows_the_amount_at_exactly_the_invoice_total(tenant_a,
                                                                            invoice_draft_a,
                                                                            invoice_line_a):
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_draft_a, disputed_amount="250.00"),
                              tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_invoice_dispute_form_caps_the_amount_against_a_credit_memo_by_magnitude(
        tenant_a, invoice_credit_memo_a):
    """A credit memo's total is negative by design - the SIZE of the claim is the cap."""
    assert invoice_credit_memo_a.total == Decimal("-50.00")
    ok = InvoiceDisputeForm(_invoice_dispute_post(invoice_credit_memo_a,
                                                  disputed_amount="50.00"), tenant=tenant_a)
    assert ok.is_valid(), ok.errors
    too_big = InvoiceDisputeForm(_invoice_dispute_post(invoice_credit_memo_a,
                                                       disputed_amount="50.01"), tenant=tenant_a)
    assert not too_big.is_valid()
    assert "disputed_amount" in too_big.errors


def test_invoice_dispute_form_rejects_a_negative_amount(tenant_a, invoice_draft_a,
                                                        invoice_line_a):
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_draft_a, disputed_amount="-5.00"),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert "disputed_amount" in form.errors


def test_invoice_dispute_form_edit_measures_the_amount_against_the_saved_invoice(
        tenant_a, invoice_dispute_open_a):
    """``invoice`` is popped on edit - the instance's own invoice is what the cap reads."""
    form = InvoiceDisputeForm(_invoice_dispute_post(disputed_amount="9999.00"),
                              instance=invoice_dispute_open_a, tenant=tenant_a)
    assert not form.is_valid()
    assert ("The disputed amount cannot be more than the invoice total."
            in form.errors["disputed_amount"])


# =================================================================================================
# 9. Negative-input hardening on every hand-parsed number (L35)
# =================================================================================================

@pytest.mark.parametrize("junk", _INVOICE_JUNK_DECIMALS)
def test_invoice_header_form_fx_rate_junk_is_a_field_error_not_a_500(tenant_a, invoice_vendor_a,
                                                                     junk):
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a, fx_rate=junk),
                               tenant=tenant_a)
    assert not form.is_valid()
    assert "fx_rate" in form.errors
    assert not SupplierInvoice.objects.filter(invoice_number="SUP-8001").exists()


def test_invoice_header_form_treats_a_blank_fx_rate_as_no_rate(tenant_a, invoice_vendor_a):
    """An omitted rate is "no rate", not 1.0 and not 0 - the invoice simply stays unconverted."""
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a, fx_rate=""),
                               tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["fx_rate"] is None


def test_invoice_header_form_whitespace_fx_rate_is_a_field_error(tenant_a, invoice_vendor_a):
    """Whitespace is NOT a blank on a number field - only "" is.

    Django's ``DecimalField.to_python`` treats "   " as unparseable rather than absent, and that is
    the honest answer for a rate somebody hand-posted: a field error on a 200 with nothing saved.
    Every other numeric field in the app behaves this way, and quietly reading "   " as "no rate"
    here would fork one form out of step with all of them for a value no browser can submit.
    """
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a, fx_rate="   "),
                               tenant=tenant_a)
    assert not form.is_valid()
    assert "fx_rate" in form.errors
    assert not SupplierInvoice.objects.filter(invoice_number="SUP-8001").exists()


@pytest.mark.parametrize("value", ["0", "0.000000", "-1"])
def test_invoice_header_form_rejects_a_non_positive_fx_rate(tenant_a, invoice_vendor_a, value):
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a, fx_rate=value),
                               tenant=tenant_a)
    assert not form.is_valid()
    assert "fx_rate" in form.errors


def test_invoice_header_form_rejects_an_over_max_digits_fx_rate(tenant_a, invoice_vendor_a):
    """``fx_rate`` is Decimal(14, 6) - eight integer digits, so 1e8 cannot be stored."""
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a, fx_rate="100000000"),
                               tenant=tenant_a)
    assert not form.is_valid()
    assert "fx_rate" in form.errors


def test_invoice_header_form_accepts_a_sane_fx_rate(tenant_a, invoice_vendor_a):
    form = SupplierInvoiceForm(_invoice_header_post(invoice_vendor_a, fx_rate="1.235000"),
                               tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["fx_rate"] == Decimal("1.235000")


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_invoice_safe_decimal_refuses_a_non_finite_figure(raw):
    value, error = _safe_decimal(raw, _FX_CEILING, "Conversion rate")
    assert value is None
    assert error == "Enter a finite number for Conversion rate."


@pytest.mark.parametrize("raw", ["abc", "", None, "12,34"])
def test_invoice_safe_decimal_refuses_garbage(raw):
    value, error = _safe_decimal(raw, _FX_CEILING, "Conversion rate")
    assert value is None
    assert error == "Enter a valid number for Conversion rate."


def test_invoice_safe_decimal_refuses_an_over_ceiling_figure():
    value, error = _safe_decimal("1e400", _FX_CEILING, "Conversion rate")
    assert value is None
    assert error == "Conversion rate is too large."


def test_invoice_safe_decimal_accepts_a_finite_in_range_figure():
    value, error = _safe_decimal(" 12.5 ", _FX_CEILING, "Conversion rate")
    assert value == Decimal("12.5")
    assert error is None


@pytest.mark.parametrize("junk", _INVOICE_JUNK_DECIMALS)
def test_invoice_dispute_form_amount_junk_is_a_field_error_not_a_500(tenant_a, invoice_draft_a,
                                                                     invoice_line_a, junk):
    form = InvoiceDisputeForm(_invoice_dispute_post(invoice_draft_a, disputed_amount=junk),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert "disputed_amount" in form.errors
    assert not InvoiceDispute.objects.filter(tenant=tenant_a).exists()


def test_invoice_dispute_form_rejects_an_over_max_digits_amount(tenant_a, invoice_draft_a,
                                                                invoice_line_a):
    form = InvoiceDisputeForm(
        _invoice_dispute_post(invoice_draft_a, disputed_amount="1000000000000.00"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "disputed_amount" in form.errors


@pytest.mark.parametrize("junk", _INVOICE_JUNK_DECIMALS)
@pytest.mark.parametrize("field", ["quantity", "unit_price"])
def test_invoice_line_form_number_junk_is_a_field_error_not_a_500(tenant_a, invoice_draft_a,
                                                                  gl_expense_a, field, junk):
    form = SupplierInvoiceLineForm(
        _invoice_line_post(gl_account=str(gl_expense_a.pk), **{field: junk}),
        instance=SupplierInvoiceLine(invoice=invoice_draft_a), tenant=tenant_a)
    assert not form.is_valid()
    assert field in form.errors
    assert not invoice_draft_a.lines.exists()


@pytest.mark.parametrize("field,value", [("quantity", "10000000000"),
                                         ("unit_price", "1000000000000")])
def test_invoice_line_form_rejects_an_over_ceiling_figure(tenant_a, invoice_draft_a,
                                                          gl_expense_a, field, value):
    form = SupplierInvoiceLineForm(
        _invoice_line_post(gl_account=str(gl_expense_a.pk), **{field: value}),
        instance=SupplierInvoiceLine(invoice=invoice_draft_a), tenant=tenant_a)
    assert not form.is_valid()
    assert field in form.errors


# =================================================================================================
# 10. The two plain (non-model) forms
# =================================================================================================

def test_invoice_variance_accept_form_treats_the_note_as_optional():
    form = InvoiceVarianceAcceptForm({"note": ""})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["note"] == ""


def test_invoice_variance_accept_form_rejects_a_note_over_five_hundred_characters():
    form = InvoiceVarianceAcceptForm({"note": "x" * 501})
    assert not form.is_valid()
    assert "note" in form.errors


def test_invoice_variance_accept_form_accepts_a_note_at_the_cap():
    form = InvoiceVarianceAcceptForm({"note": "x" * 500})
    assert form.is_valid(), form.errors


def test_invoice_capture_upload_form_requires_a_file():
    form = CaptureUploadForm({}, {})
    assert not form.is_valid()
    assert "document_file" in form.errors


def test_invoice_capture_upload_form_accepts_a_pdf():
    upload = SimpleUploadedFile("supplier-invoice.pdf", b"%PDF-1.4 not really a pdf")
    form = CaptureUploadForm({}, {"document_file": upload})
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("name", ["payload.exe", "script.js", "archive.tar.gz", "macro.docm"])
def test_invoice_capture_upload_form_rejects_a_disallowed_extension(name):
    upload = SimpleUploadedFile(name, b"MZ definitely not an invoice")
    form = CaptureUploadForm({}, {"document_file": upload})
    assert not form.is_valid()
    assert any("is not allowed" in message for message in form.errors["document_file"])


class _InvoiceSizedUpload(SimpleUploadedFile):
    """Tiny in-memory payload that declares a huge size - crosses the cap without allocating."""

    def __init__(self, name, declared_size):
        super().__init__(name=name, content=b"%PDF-1.4")
        self._declared_size = declared_size

    @property
    def size(self):
        return self._declared_size

    @size.setter
    def size(self, value):
        pass  # UploadedFile.__init__ writes the real byte count; the declaration wins here


def test_invoice_capture_upload_form_rejects_an_oversized_file():
    """The cap is core's 20 MB, imported LOCALLY so procurement's CatalogManagement 2 MB limit
    cannot shadow it."""
    upload = _InvoiceSizedUpload("huge.pdf", MAX_UPLOAD_BYTES + 1)
    form = CaptureUploadForm({}, {"document_file": upload})
    assert not form.is_valid()
    assert any(str(MAX_UPLOAD_BYTES // (1024 * 1024)) in message
               for message in form.errors["document_file"])


def test_invoice_capture_upload_form_accepts_a_file_at_the_cap():
    upload = _InvoiceSizedUpload("just-fits.pdf", MAX_UPLOAD_BYTES)
    form = CaptureUploadForm({}, {"document_file": upload})
    assert form.is_valid(), form.errors
