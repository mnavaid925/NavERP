"""Procurement 6.9 - Catalog Management form tests.

These four forms are the crafted-POST boundary for the catalogue stack: foreign FKs land
field errors, the model's pricing/window rules surface through the form as FIELD errors,
the punch-out shared secret is create-only and never rendered back, the upload form
enforces its extension allowlist + 2 MB cap, and every tenant-scoped dropdown excludes
other workspaces while the global currency master stays visible.
"""
import datetime

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.procurement.forms import (
    CatalogItemForm,
    CatalogPriceTierForm,
    CatalogUploadBatchForm,
    PunchOutEndpointForm,
)
from apps.procurement.forms.CatalogManagement.UploadBatches import MAX_UPLOAD_BYTES
from apps.scm.models import Item, SupplierContract, UOM

pytestmark = pytest.mark.django_db


# -- local builders -----------------------------------------------------------------------------------

class _CatalogmgmtSizedUpload(SimpleUploadedFile):
    """Tiny in-memory payload that declares a huge size - crosses the cap without allocating."""

    def __init__(self, name, declared_size):
        super().__init__(name=name, content=b"name\nrow")
        self._declared_size = declared_size

    @property
    def size(self):
        return self._declared_size

    @size.setter
    def size(self, value):
        pass  # UploadFile.__init__ writes the real byte count; the declaration wins here


@pytest.fixture
def _catalogmgmt_media(tmp_path):
    """MEDIA_ROOT pointed at a throwaway dir so upload saves cannot touch the repo."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        yield tmp_path


# -- 1. Meta.fields contract --------------------------------------------------------------------------

def test_catalogmgmt_meta_fields_match_contract_exactly():
    """Mass-assignment guard: each form exposes EXACTLY the contract field list - status,
    number and server-side counters are never writable through a POST."""
    assert CatalogItemForm.Meta.fields == [
        "source_type", "item", "supplier", "contract", "name", "supplier_part_no",
        "description", "manufacturer", "uom", "currency", "base_price",
        "category_text", "is_preferred", "is_active"]
    assert not {"status", "number", "rejection_reason",
                "submitted_by", "submitted_at", "approved_by", "approved_at",
                "created_by"} & set(CatalogItemForm.Meta.fields)

    assert CatalogPriceTierForm.Meta.fields == [
        "catalog_item", "min_quantity", "unit_price", "discount_pct",
        "valid_from", "valid_until", "contract"]
    assert not {"status", "submitted_by", "approved_by", "approved_at"} \
        & set(CatalogPriceTierForm.Meta.fields)

    assert PunchOutEndpointForm.Meta.fields == [
        "party", "name", "protocol", "punchout_url", "username",
        "shared_secret", "enabled", "notes"]
    assert not {"number", "last_session_at"} & set(PunchOutEndpointForm.Meta.fields)

    assert CatalogUploadBatchForm.Meta.fields == ["party", "file", "notes"]
    assert not {"number", "original_filename", "status",
                "rows_parsed", "rows_accepted", "rows_rejected", "error_log",
                "validated_by", "validated_at"} & set(CatalogUploadBatchForm.Meta.fields)


def test_catalogmgmt_instantiated_fields_match_meta_on_create(tenant_a):
    for form_class in (CatalogItemForm, CatalogPriceTierForm,
                       PunchOutEndpointForm, CatalogUploadBatchForm):
        form = form_class(tenant=tenant_a)
        assert set(form.fields) == set(form_class.Meta.fields), form_class.__name__


# -- 2. CatalogItemForm -------------------------------------------------------------------------------

def test_catalogmgmt_catalogitem_internal_without_item_is_field_error(tenant_a):
    form = CatalogItemForm({"source_type": "internal"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors
    assert any("must point at a stock item" in message
               for message in form.errors["item"])


def test_catalogmgmt_catalogitem_internal_foreign_item_rejected(tenant_a, tenant_b, admin_b):
    foreign_uom = UOM.objects.create(tenant=tenant_b, code="BX", name="Box")
    foreign_item = Item.objects.create(tenant=tenant_b, sku="GLOBEX-1",
                                       name="Globex-only part", uom=foreign_uom)
    data = {"source_type": "internal", "item": str(foreign_item.pk), "name": "Cross grab"}

    # Layer 1 (TenantModelForm): scoped choices refuse the pk outright.
    scoped = CatalogItemForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "item" in scoped.errors

    # Layer 2 (_reject_foreign): with unscoped choices the hand-posted foreign pk still
    # lands as the exact rule message.
    loose = CatalogItemForm(data)
    assert not loose.is_valid()
    assert "That record belongs to another workspace." in loose.errors["item"]


def test_catalogmgmt_catalogitem_supplier_product_requires_name(tenant_a):
    form = CatalogItemForm({"source_type": "supplier_product"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


def test_catalogmgmt_catalogitem_valid_create_stamps_tenant_preclean_and_saves(
        tenant_a, item_a):
    data = {"source_type": "internal", "item": str(item_a.pk),
            "name": "A4 copy paper (preferred buy)", "base_price": "4.20"}
    form = CatalogItemForm(data, tenant=tenant_a)
    # TenantUniqueMixin stamped the instance BEFORE clean() - this is what lets the
    # model's same-workspace FK check and unique validation work on CREATE.
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)          # views stamp nothing further on create
    assert obj.tenant_id == tenant_a.pk
    assert not obj.number                  # assigned once by TenantNumbered.save()
    assert obj.status == "draft"           # status is not a form field
    obj.save()
    assert obj.number.startswith("PCI")


def test_catalogmgmt_catalogitem_same_tenant_internal_item_accepted(
        tenant_a, catalog_item_approved_a, item_a):
    """Positive control: the guard refuses other workspaces' rows, not every row."""
    data = {"source_type": "internal", "item": str(item_a.pk),
            "name": "Second internal mirror", "base_price": "5.10"}
    form = CatalogItemForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["item"] == item_a


# -- 3. CatalogPriceTierForm --------------------------------------------------------------------------

def test_catalogmgmt_tier_window_reversed_is_field_error(
        tenant_a, catalog_item_pending_a):
    data = {"catalog_item": str(catalog_item_pending_a.pk), "min_quantity": "25",
            "unit_price": "30.00",
            "valid_from": datetime.date(2026, 1, 10).strftime("%Y-%m-%d"),
            "valid_until": datetime.date(2026, 1, 1).strftime("%Y-%m-%d")}
    form = CatalogPriceTierForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert "valid_until" in form.errors
    assert any("precede" in message.lower() for message in form.errors["valid_until"])


def test_catalogmgmt_tier_discount_over_100_rejected(tenant_a, catalog_item_pending_a):
    base = {"catalog_item": str(catalog_item_pending_a.pk), "min_quantity": "25",
            "unit_price": "30.00"}
    over = CatalogPriceTierForm(dict(base, discount_pct="150"), tenant=tenant_a)
    assert not over.is_valid()
    assert "discount_pct" in over.errors
    at_cap = CatalogPriceTierForm(dict(base, discount_pct="100"), tenant=tenant_a)
    assert at_cap.is_valid(), at_cap.errors          # 100% is the inclusive ceiling


def test_catalogmgmt_tier_blank_both_pricing_unit_price_required(
        tenant_a, catalog_item_pending_a):
    """Read the model: unit_price has no blank=True, discount_pct does - so BOTH blank is
    NOT allowed; unit_price alone prices the break and leaves discount_pct None."""
    both_blank = CatalogPriceTierForm(
        {"catalog_item": str(catalog_item_pending_a.pk), "min_quantity": "5"},
        tenant=tenant_a)
    assert not both_blank.is_valid()
    assert "unit_price" in both_blank.errors

    unit_only = CatalogPriceTierForm(
        {"catalog_item": str(catalog_item_pending_a.pk), "min_quantity": "7",
         "unit_price": "31.00"}, tenant=tenant_a)
    assert unit_only.is_valid(), unit_only.errors
    obj = unit_only.save()
    assert obj.discount_pct is None
    assert obj.unit_price == __import__("decimal").Decimal("31.00")
    assert obj.status == "draft"           # status moves only through approve/retire/cancel


def test_catalogmgmt_tier_foreign_catalog_item_rejected(tenant_a, catalog_item_b):
    data = {"catalog_item": str(catalog_item_b.pk), "min_quantity": "5",
            "unit_price": "9.00"}
    scoped = CatalogPriceTierForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "catalog_item" in scoped.errors

    loose = CatalogPriceTierForm(data)     # unscoped choices: layer 2 must still catch it
    assert not loose.is_valid()
    assert "That record belongs to another workspace." in loose.errors["catalog_item"]


def test_catalogmgmt_tier_foreign_contract_rejected(tenant_a, tenant_b, supplier_a,
                                                    supplier_b, catalog_item_approved_a):
    _, party_b = supplier_b
    foreign_contract = SupplierContract.objects.create(
        tenant=tenant_b, party=party_b, title="Globex frame agreement")
    _, party_a = supplier_a
    own_contract = SupplierContract.objects.create(
        tenant=tenant_a, party=party_a, title="Northwind frame agreement")

    data = {"catalog_item": str(catalog_item_approved_a.pk), "min_quantity": "25",
            "unit_price": "28.00", "contract": str(foreign_contract.pk)}
    scoped = CatalogPriceTierForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "contract" in scoped.errors

    loose = CatalogPriceTierForm(data)
    assert not loose.is_valid()
    assert "That record belongs to another workspace." in loose.errors["contract"]

    own = CatalogPriceTierForm(dict(data, contract=str(own_contract.pk)), tenant=tenant_a)
    assert own.is_valid(), own.errors      # positive control: same workspace passes
    assert own.cleaned_data["contract"] == own_contract


# -- 4. PunchOutEndpointForm --------------------------------------------------------------------------

def test_catalogmgmt_punchout_create_secret_write_only_password_input(tenant_a):
    create_form = PunchOutEndpointForm(tenant=tenant_a)
    assert "shared_secret" in create_form.fields
    widget = create_form.fields["shared_secret"].widget
    assert isinstance(widget, forms.PasswordInput)
    assert widget.render_value is False
    html = str(PunchOutEndpointForm(initial={"shared_secret": "hunter2"}, tenant=tenant_a))
    assert 'type="password"' in html
    assert "hunter2" not in html           # render_value=False: the secret never echoes


def test_catalogmgmt_punchout_create_accepts_secret_and_stamps_tenant(
        tenant_a, supplier_a):
    _, party = supplier_a
    data = {"party": str(party.pk), "name": "Amazon Business (sandbox)",
            "protocol": "cxml", "punchout_url": "https://sandbox.example.com/cxml",
            "username": "acme-buyer", "shared_secret": "hunter2", "enabled": "on"}
    form = PunchOutEndpointForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.shared_secret == "hunter2"
    assert obj.tenant_id == tenant_a.pk
    assert obj.protocol == "cxml"


def test_catalogmgmt_punchout_edit_drops_secret_field_keeps_stored_value(
        tenant_a, punchout_endpoint_a):
    endpoint = punchout_endpoint_a
    endpoint.shared_secret = "stored-secret"
    endpoint.save(update_fields=["shared_secret"])

    edit_form = PunchOutEndpointForm(instance=endpoint, tenant=tenant_a)
    assert "shared_secret" not in edit_form.fields
    assert "shared_secret" in PunchOutEndpointForm.Meta.fields  # create-side contract intact
    assert "shared_secret" not in str(edit_form)                # never rendered either

    data = {"party": str(endpoint.party_id), "name": "Renamed sandbox",
            "protocol": "oci", "punchout_url": "https://sandbox.example.com/oci",
            "username": "acme-buyer", "enabled": "on"}
    bound = PunchOutEndpointForm(data, instance=endpoint, tenant=tenant_a)
    assert bound.is_valid(), bound.errors   # posting WITHOUT a secret validates fine
    bound.save()
    endpoint.refresh_from_db()
    assert endpoint.shared_secret == "stored-secret"
    assert endpoint.name == "Renamed sandbox"


# -- 5. CatalogUploadBatchForm ------------------------------------------------------------------------

CSV_BYTES = (b"name,supplier_part_no,unit_price,uom_code,category_text\r\n"
             b"Safety gloves,NW-GLOVE-D1,34.90,EA,Safety\r\n")


def test_catalogmgmt_upload_csv_accepted_stamps_original_filename(
        tenant_a, supplier_a, _catalogmgmt_media):
    _, party = supplier_a
    upload = SimpleUploadedFile("northwind.csv", CSV_BYTES)
    form = CatalogUploadBatchForm({"party": str(party.pk), "notes": "Q3 price file"},
                                  {"file": upload}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    batch = form.save(commit=False)
    assert batch.tenant_id == tenant_a.pk  # TenantUniqueMixin stamp, view parity
    assert not batch.original_filename     # not a form field - empty until save()
    batch.save()                           # model save() stamps from file.name
    assert batch.original_filename == "northwind.csv"
    assert batch.number.startswith("CUB")
    assert batch.status == "received"


def test_catalogmgmt_upload_bad_extension_rejected(tenant_a, supplier_a):
    _, party = supplier_a
    for name in ("payload.exe", "dossier.pdf"):
        upload = SimpleUploadedFile(name, b"MZ fake content")
        form = CatalogUploadBatchForm({"party": str(party.pk)}, {"file": upload},
                                      tenant=tenant_a)
        assert not form.is_valid(), name
        assert "file" in form.errors
        assert any("csv" in message.lower() for message in form.errors["file"])


def test_catalogmgmt_upload_oversized_rejected_just_over_cap(tenant_a, supplier_a):
    _, party = supplier_a
    just_over = _CatalogmgmtSizedUpload("big.csv", MAX_UPLOAD_BYTES + 1)
    form = CatalogUploadBatchForm({"party": str(party.pk)}, {"file": just_over},
                                  tenant=tenant_a)
    assert not form.is_valid()
    assert "file" in form.errors
    assert any("MB" in message for message in form.errors["file"])
    assert any(str(MAX_UPLOAD_BYTES // (1024 * 1024)) in message
               for message in form.errors["file"])


def test_catalogmgmt_upload_at_cap_accepted(tenant_a, supplier_a):
    _, party = supplier_a
    at_cap = _CatalogmgmtSizedUpload("big.csv", MAX_UPLOAD_BYTES)
    form = CatalogUploadBatchForm({"party": str(party.pk)}, {"file": at_cap},
                                  tenant=tenant_a)
    assert form.is_valid(), form.errors    # the cap itself is inclusive


# -- 6. Tenant scoping of dropdowns -------------------------------------------------------------------

def test_catalogmgmt_dropdowns_exclude_other_workspaces_currency_global(
        tenant_a, tenant_b, usd, item_a, supplier_a, supplier_b, catalog_item_b):
    foreign_uom = UOM.objects.create(tenant=tenant_b, code="BX", name="Box")
    foreign_item = Item.objects.create(tenant=tenant_b, sku="GLOBEX-1",
                                       name="Globex-only part", uom=foreign_uom)
    _, party_b = supplier_b
    foreign_contract = SupplierContract.objects.create(
        tenant=tenant_b, party=party_b, title="Globex frame agreement")

    item_form = CatalogItemForm(tenant=tenant_a)
    assert not item_form.fields["item"].queryset.filter(pk=foreign_item.pk).exists()
    assert item_form.fields["item"].queryset.filter(pk=item_a.pk).exists()
    # accounting.Currency is GLOBAL - visible regardless of the form's workspace.
    assert usd in item_form.fields["currency"].queryset

    tier_form = CatalogPriceTierForm(tenant=tenant_a)
    assert not tier_form.fields["catalog_item"].queryset.filter(pk=catalog_item_b.pk).exists()
    assert not tier_form.fields["contract"].queryset.filter(pk=foreign_contract.pk).exists()

    endpoint_form = PunchOutEndpointForm(tenant=tenant_a)
    assert not endpoint_form.fields["party"].queryset.filter(pk=party_b.pk).exists()

    upload_form = CatalogUploadBatchForm(tenant=tenant_a)
    assert not upload_form.fields["party"].queryset.filter(pk=party_b.pk).exists()

    # Without a tenant kwarg the queryset filter is skipped entirely - which is exactly
    # why the _reject_foreign layer-2 re-check exists for that path (tested above).
    loose_scope = CatalogItemForm()
    assert loose_scope.fields["item"].queryset.filter(pk=foreign_item.pk).exists()
