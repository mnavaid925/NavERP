"""Inventory 5.1 — form boundary.

The forms ARE the security boundary a crafted POST meets first: tenant-stamped uniques that
render as field errors instead of 500ing, the foreign-item rejection, the upload cap, and the
create path that must NOT false-reject (the SEC-1 regression).
"""
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.inventory.forms import ItemAttributeForm, ItemPriceForm, ProductFileForm

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ ItemAttributeForm


class TestItemAttributeForm:
    def test_duplicate_name_renders_error_not_integrityerror(self, tenant_a, item_a):
        """The mixin stamps instance.tenant so validate_unique actually runs — a duplicate is a
        rendered error, never an IntegrityError on save."""
        ItemAttributeForm(data={
            "item": item_a.pk, "name": "Color", "value": "Red", "unit": "", "sequence": "0",
        }, tenant=tenant_a).save()
        form = ItemAttributeForm(data={
            "item": item_a.pk, "name": "Color", "value": "Blue", "unit": "", "sequence": "0",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert any("already exist" in msg or "Color" in msg
                   for msgs in form.errors.values() for msg in msgs)

    def test_rejects_foreign_item(self, tenant_a, item_b):
        """The scoped dropdown refuses a foreign pk at choice-validation ("Select a valid
        choice"); _reject_foreign is the belt-and-braces layer beneath it. Either message is a
        rejection — assert invalid + nothing saved, not one exact wording."""
        form = ItemAttributeForm(data={
            "item": item_b.pk, "name": "Size", "value": "M", "unit": "", "sequence": "0",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["item"]
        assert form.instance.pk is None  # save() would raise on an invalid form anyway

    def test_valid_create(self, tenant_a, item_a):
        form = ItemAttributeForm(data={
            "item": item_a.pk, "name": "Width", "value": "600", "unit": "mm", "sequence": "10",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk

    def test_crafted_post_cannot_set_tenant(self, tenant_a, tenant_b, item_a, client_a):
        """`tenant` is excluded from every form — mass-assigning it in POST data changes nothing,
        and crud_create stamps request.tenant afterwards regardless."""
        from apps.inventory.models import ItemAttribute
        response = client_a.post(reverse("inventory:itemattribute_create"), data={
            "item": item_a.pk, "name": "Grade", "value": "A", "unit": "",
            "sequence": "0", "tenant": tenant_b.pk,
        })
        assert response.status_code == 302
        row = ItemAttribute.objects.get(item=item_a, name="Grade")
        assert row.tenant_id == tenant_a.pk


# ------------------------------------------------------------------ ItemPriceForm


class TestItemPriceForm:
    def test_create_passes_with_mixin_tenant_stamp(self, tenant_a, item_a):
        """SEC-1's twin on the price path: model clean() compares tenants during full_clean, so
        the mixin's stamp must be present on CREATE too."""
        form = ItemPriceForm(data={
            "item": item_a.pk, "price_type": "retail", "unit_price": "12.00",
            "currency": "", "min_quantity": "1", "valid_from": "", "valid_until": "",
            "is_active": "on", "notes": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.unit_price == Decimal("12.00")

    def test_rejects_foreign_item(self, tenant_a, item_b):
        form = ItemPriceForm(data={
            "item": item_b.pk, "price_type": "retail", "unit_price": "9.00",
            "min_quantity": "1", "is_active": "on",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["item"]
        assert form.instance.pk is None

    def test_inverted_window_is_field_error(self, tenant_a, item_a):
        form = ItemPriceForm(data={
            "item": item_a.pk, "price_type": "promotional", "unit_price": "10.00",
            "min_quantity": "1", "valid_from": "2026-04-01", "valid_until": "2026-03-01",
            "is_active": "on",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "valid_until" in form.errors

    def test_inactive_currency_stays_selectable_on_edit(self, tenant_a, item_a, price_a):
        """A currency deactivated AFTER the row was saved must remain on its edit form, or an
         untouched save would silently NULL the field."""
        from apps.accounting.models import Currency
        currency = Currency.objects.create(code="XXZ", name="Test Dollar", symbol="X")
        price_a.currency = currency
        price_a.save(update_fields=["currency"])
        currency.is_active = False
        currency.save(update_fields=["is_active"])

        form = ItemPriceForm(instance=price_a, tenant=tenant_a)
        assert currency in form.fields["currency"].queryset


# ------------------------------------------------------------------ ProductFileForm


class TestProductFileForm:
    def test_url_only_create_is_valid(self, tenant_a, item_a):
        """THE SEC-1 regression: before the fix every create was falsely rejected as
        cross-tenant because the instance had no tenant during full_clean()."""
        form = ProductFileForm(data={
            "item": item_a.pk, "kind": "photo", "title": "Shot",
            "url": "https://files.example.com/p.jpg", "file": "", "is_primary": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk

    def test_neither_file_nor_url_refused(self, tenant_a, item_a):
        form = ProductFileForm(data={
            "item": item_a.pk, "kind": "other", "title": "Empty",
            "url": "", "file": "", "is_primary": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["file"]  # keyed on a field the form has, so it renders

    def test_disallowed_extension_refused(self, tenant_a, item_a):
        """The upload must travel in ``files=``, where real multipart requests put it — in
        ``data=`` the form never sees it and only the model's file-or-url rule would fire."""
        form = ProductFileForm(
            data={
                "item": item_a.pk, "kind": "other", "title": "Script",
                "url": "", "is_primary": "",
            },
            files={"file": SimpleUploadedFile("payload.html", b"<h1>x</h1>")},
            tenant=tenant_a)
        assert not form.is_valid()
        assert any("not allowed" in msg for msg in form.errors["file"])

    def test_oversized_upload_refused(self, tenant_a, item_a, monkeypatch):
        """The size cap, exercised against a THRESHOLD patched down to 10 bytes so the suite
        never allocates a 20 MB buffer. The model's file-or-url error may join the list (the
        cap's add_error removes the upload from cleaned_data before the instance is built), so
        assert the message appears anywhere among the file errors."""
        import apps.inventory.forms.Catalog.ProductFiles as pf_module
        from apps.inventory.forms._common import MAX_UPLOAD_BYTES
        monkeypatch.setattr(pf_module, "MAX_UPLOAD_BYTES", 10)
        assert MAX_UPLOAD_BYTES == 20 * 1024 * 1024  # the real constant is untouched
        form = ProductFileForm(
            data={
                "item": item_a.pk, "kind": "manual", "title": "Huge",
                "url": "", "is_primary": "",
            },
            files={"file": SimpleUploadedFile("big.pdf", b"x" * 11)},
            tenant=tenant_a)
        assert not form.is_valid()
        joined = " | ".join(form.errors.get("file", []))
        assert "20 MB" in joined

    def test_rejects_foreign_item(self, tenant_a, item_b):
        form = ProductFileForm(data={
            "item": item_b.pk, "kind": "photo", "title": "Smuggled",
            "url": "https://files.example.com/x.jpg", "file": "", "is_primary": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["item"]
        assert form.instance.pk is None
