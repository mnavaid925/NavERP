"""Inventory 5.1 — model invariants.

The catalog layer's whole contract lives at the model boundary: the per-SKU attribute
uniqueness, the file-or-url rule, the one-cover-per-product rule, and margin/markup that
answer ``None`` rather than fabricate a figure when the cost basis is missing.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.inventory.models import ItemAttribute, ItemPrice, ProductFile

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ ItemAttribute


class TestItemAttribute:
    def test_unique_name_per_item(self, tenant_a, item_a):
        """(tenant, item, name) is a hard constraint — a second 'Color' cannot exist."""
        ItemAttribute.objects.create(tenant=tenant_a, item=item_a, name="Color", value="Red")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ItemAttribute.objects.create(
                    tenant=tenant_a, item=item_a, name="Color", value="Blue")

    def test_same_name_on_second_item_is_fine(self, tenant_a, item_a):
        from apps.scm.models import Item
        other = Item.objects.create(tenant=tenant_a, sku="CAT-2", name="Other Widget")
        row = ItemAttribute.objects.create(
            tenant=tenant_a, item=other, name="Color", value="Red")
        assert row.pk is not None

    def test_clean_rejects_foreign_item(self, tenant_a, tenant_b, item_b):
        attr = ItemAttribute(
            tenant=tenant_a, item=item_b, name="Size", value="M")
        # full_clean runs model clean() — the DB-boundary twin of the form's _reject_foreign.
        with pytest.raises(ValidationError) as err:
            attr.full_clean()
        assert "item" in err.value.message_dict

    def test_display_value_joins_unit(self, tenant_a, item_a):
        attr = ItemAttribute.objects.create(
            tenant=tenant_a, item=item_a, name="Width", value="600", unit="mm")
        assert attr.display_value == "600 mm"

    def test_display_value_without_unit_has_no_stray_space(self, tenant_a, item_a):
        attr = ItemAttribute.objects.create(
            tenant=tenant_a, item=item_a, name="Grade", value="A")
        assert attr.display_value == "A"

    def test_str_with_and_without_item(self, tenant_a, item_a):
        attr = ItemAttribute(tenant=tenant_a, name="Color")
        assert attr.__str__().startswith("?")  # unsaved/no-item guard
        attr = ItemAttribute.objects.create(
            tenant=tenant_a, item=item_a, name="Color", value="Red")
        assert item_a.sku in str(attr)


# ------------------------------------------------------------------ ItemPrice


class TestItemPrice:
    def test_margin_against_standard_cost(self, price_a):
        # 12.00 over an 8.00 cost: margin (12-8)/12 = 33.33%, markup (12-8)/8 = 50.00%.
        assert price_a.margin_pct == Decimal("33.33")
        assert price_a.markup_pct == Decimal("50.00")

    def test_markup_none_at_zero_cost_basis(self, tenant_a):
        """standard_cost=0 is scm.Item's 'not costed yet' default — neither figure may fabricate
        an answer from it (margin would otherwise paint every uncosted SKU as a perfect 100%)."""
        from apps.scm.models import Item
        item = Item.objects.create(tenant=tenant_a, sku="NOCOST-1", name="Uncosted")
        price = ItemPrice.objects.create(
            tenant=tenant_a, item=item, price_type="retail", unit_price=Decimal("10.00"))
        assert price.markup_pct is None
        assert price.margin_pct is None

    def test_both_none_without_item(self, tenant_a):
        """An unsaved-pointer row must never read a foreign item's cost."""
        price = ItemPrice(tenant=tenant_a, price_type="retail", unit_price=Decimal("10.00"))
        assert price.margin_pct is None
        assert price.markup_pct is None

    def test_margin_zero_priced_row(self, tenant_a, item_a):
        price = ItemPrice.objects.create(
            tenant=tenant_a, item=item_a, price_type="clearance", unit_price=Decimal("0"))
        assert price.margin_pct is None
        # markup still answers: cost 8, price 0 → -100%
        assert price.markup_pct == Decimal("-100.00")

    def test_covers_window(self, tenant_a, item_a):
        import datetime
        price = ItemPrice.objects.create(
            tenant=tenant_a, item=item_a, price_type="promotional", unit_price=Decimal("10"),
            valid_from=datetime.date(2026, 3, 1), valid_until=datetime.date(2026, 3, 31))
        assert price.covers(datetime.date(2026, 3, 15))
        assert not price.covers(datetime.date(2026, 4, 1))

    def test_open_ended_window_stays_open(self, tenant_a, item_a):
        import datetime
        price = ItemPrice.objects.create(
            tenant=tenant_a, item=item_a, price_type="retail", unit_price=Decimal("10"),
            valid_from=datetime.date(2026, 1, 1))
        assert price.covers(datetime.date(2030, 1, 1))

    def test_clean_rejects_inverted_window(self, tenant_a, item_a):
        import datetime
        price = ItemPrice(
            tenant=tenant_a, item=item_a, unit_price=Decimal("10"),
            valid_from=datetime.date(2026, 4, 1), valid_until=datetime.date(2026, 3, 1))
        with pytest.raises(ValidationError) as err:
            price.full_clean()
        assert "valid_until" in err.value.message_dict

    def test_clean_rejects_foreign_item(self, tenant_a, item_b):
        price = ItemPrice(tenant=tenant_a, item=item_b, unit_price=Decimal("10"))
        with pytest.raises(ValidationError) as err:
            price.full_clean()
        assert "item" in err.value.message_dict

    def test_negative_price_refused(self, tenant_a, item_a):
        with pytest.raises(ValidationError):
            price = ItemPrice(tenant=tenant_a, item=item_a, unit_price=Decimal("-1"))
            price.full_clean()


# ------------------------------------------------------------------ ProductFile


class TestProductFile:
    def test_file_or_url_required(self, tenant_a, item_a):
        pf = ProductFile(tenant=tenant_a, item=item_a, title="Empty", kind="other")
        with pytest.raises(ValidationError) as err:
            pf.full_clean()
        assert "file" in err.value.message_dict

    def test_extension_allowlist(self, tenant_a, item_a):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = ProductFile(
            tenant=tenant_a, item=item_a, title="Script", kind="other",
            file=SimpleUploadedFile("evil.html", b"<h1>x</h1>"), url="")
        with pytest.raises(ValidationError) as err:
            bad.full_clean()
        assert "file" in err.value.message_dict

    def test_pdf_upload_accepted(self, tenant_a, item_a):
        from django.core.files.uploadedfile import SimpleUploadedFile
        ok = ProductFile(
            tenant=tenant_a, item=item_a, title="Manual", kind="manual",
            file=SimpleUploadedFile("manual.PDF", b"%PDF-1.4 fake"), url="")
        ok.full_clean()  # must not raise; case-insensitive extension match
        ok.save()
        assert ok.file.name.startswith("inventory/products/")

    def test_new_primary_demotes_previous(self, tenant_a, item_a, product_file_a):
        assert product_file_a.is_primary
        second = ProductFile.objects.create(
            tenant=tenant_a, item=item_a, kind="photo", title="Alt shot",
            url="https://files.example.com/catalog/cat-1/alt.jpg", is_primary=True)
        product_file_a.refresh_from_db()
        second.refresh_from_db()
        assert product_file_a.is_primary is False
        assert second.is_primary is True

    def test_non_primary_save_leaves_cover_alone(self, tenant_a, item_a, product_file_a):
        ProductFile.objects.create(
            tenant=tenant_a, item=item_a, kind="datasheet", title="Sheet",
            url="https://files.example.com/catalog/cat-1/sheet.pdf")
        product_file_a.refresh_from_db()
        assert product_file_a.is_primary is True

    def test_href_prefers_uploaded_file(self, tenant_a, item_a):
        from django.core.files.uploadedfile import SimpleUploadedFile
        pf = ProductFile(
            tenant=tenant_a, item=item_a, title="Both", kind="photo",
            file=SimpleUploadedFile("p.png", b"\x89PNG fake"),
            url="https://files.example.com/x.jpg")
        pf.full_clean()
        pf.save()
        assert pf.href == pf.file.url

    def test_href_falls_back_to_url(self, product_file_a):
        assert product_file_a.href == product_file_a.url

    def test_clean_rejects_foreign_item(self, tenant_a, item_b):
        pf = ProductFile(
            tenant=tenant_a, item=item_b, title="Smuggled", kind="other",
            url="https://files.example.com/x.jpg")
        with pytest.raises(ValidationError) as err:
            pf.full_clean()
        assert "item" in err.value.message_dict

    def test_urlfield_refuses_javascript_scheme(self, tenant_a, item_a):
        pf = ProductFile(
            tenant=tenant_a, item=item_a, title="XSS", kind="other",
            url="javascript:alert(1)")
        with pytest.raises(ValidationError):
            pf.full_clean()

    def test_deleting_item_cascades_catalog_rows(self, tenant_a, item_a, attribute_a,
                                                 price_a, product_file_a):
        from apps.scm.models import Item
        Item.objects.filter(pk=item_a.pk).delete()
        assert ItemAttribute.objects.count() == 0
        assert ItemPrice.objects.count() == 0
        assert ProductFile.objects.count() == 0
