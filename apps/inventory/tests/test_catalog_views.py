"""Inventory 5.1 — views.

Every route renders for its own tenant, narrows under its declared filters, and the detail
pages pass SCOPED, SELF-EXCLUDED siblings (the SEC-3 contract the templates now loop).
"""
import pytest
from decimal import Decimal
from django.urls import reverse

pytestmark = pytest.mark.django_db

ALL_GET_PAGES = [
    "inventory:overview",
    "inventory:itemattribute_list", "inventory:itemattribute_create",
    "inventory:itemprice_list", "inventory:itemprice_create",
    "inventory:productfile_list", "inventory:productfile_create",
]


@pytest.mark.parametrize("url_name", ALL_GET_PAGES)
def test_pages_render_200(client_a, url_name):
    assert client_a.get(reverse(url_name)).status_code == 200


def test_detail_and_edit_render_200(client_a, attribute_a, price_a, product_file_a):
    for name, pk in [
        ("inventory:itemattribute_detail", attribute_a.pk),
        ("inventory:itemattribute_edit", attribute_a.pk),
        ("inventory:itemprice_detail", price_a.pk),
        ("inventory:itemprice_edit", price_a.pk),
        ("inventory:productfile_detail", product_file_a.pk),
        ("inventory:productfile_edit", product_file_a.pk),
    ]:
        assert client_a.get(reverse(name, args=[pk])).status_code == 200


def test_anonymous_is_redirected_to_login(client, attribute_a):
    response = client.get(reverse("inventory:itemattribute_list"))
    assert response.status_code == 302
    assert "login" in response.url


def test_attribute_list_search_matches_value(client_a, tenant_a, item_a):
    from apps.inventory.models import ItemAttribute
    ItemAttribute.objects.create(tenant=tenant_a, item=item_a, name="Voltage", value="230")
    hit = client_a.get(reverse("inventory:itemattribute_list") + "?q=230")
    assert b"Voltage" in hit.content
    miss = client_a.get(reverse("inventory:itemattribute_list") + "?q=zebra")
    assert b"Voltage" not in miss.content


def test_price_list_filters_by_type(client_a, tenant_a, item_a, price_a):
    from apps.inventory.models import ItemPrice
    ItemPrice.objects.create(
        tenant=tenant_a, item=item_a, price_type="wholesale",
        unit_price=Decimal("9.00"), min_quantity=10)
    wholesale_page = client_a.get(reverse("inventory:itemprice_list") + "?price_type=wholesale")
    # the filtered page shows the 9.00 wholesale row and NOT the retail row's 12.00 figure
    assert b"9.00" in wholesale_page.content
    assert b"12.00" not in wholesale_page.content
    retail_page = client_a.get(reverse("inventory:itemprice_list") + "?price_type=retail")
    assert b"12.00" in retail_page.content
    assert b"9.00" not in retail_page.content


def test_file_list_kind_filter(client_a, product_file_a):
    page = client_a.get(reverse("inventory:productfile_list") + "?kind=safety_sheet")
    assert product_file_a.title.encode() not in page.content
    page = client_a.get(reverse("inventory:productfile_list") + "?kind=photo")
    assert product_file_a.title.encode() in page.content


def test_junk_get_params_degrade_not_500(client_a):
    """L11: non-pk and over-range values skip the filter instead of raising."""
    base = reverse("inventory:itemattribute_list")
    assert client_a.get(base + "?item=abc").status_code == 200
    assert client_a.get(base + "?item=999999999999999999999").status_code == 200
    assert client_a.get(base + "?item=%C2%B2").status_code == 200  # superscript two


class TestDetailSiblings:
    def test_price_siblings_exclude_self(self, client_a, tenant_a, item_a, price_a):
        """SEC-3/QA-2: the 'Other prices' table is scoped AND self-excluded by the view —
        with exactly one row the empty state renders truthfully."""
        from apps.inventory.models import ItemPrice
        other = ItemPrice.objects.create(
            tenant=tenant_a, item=item_a, price_type="wholesale",
            unit_price=Decimal("9.50"), min_quantity=10)
        content = client_a.get(reverse("inventory:itemprice_detail", args=[price_a.pk])).content
        # the real sibling's detail link renders; self's own detail link appears only in the
        # page header/edit/delete cluster, never inside the sibling table
        assert f"prices/{other.pk}/".encode() in content
        sibling_table = content.split(b"Other Prices")[1]
        assert f"prices/{price_a.pk}/".encode() not in sibling_table

    def test_attribute_siblings_exclude_self(self, client_a, tenant_a, item_a, attribute_a):
        """SEC-3/QA-2: the sibling section is scoped AND self-excluded — assert inside the
        section only (self's name legitimately appears in the page <h1>)."""
        from apps.inventory.models import ItemAttribute
        ItemAttribute.objects.create(
            tenant=tenant_a, item=item_a, name="Size", value="M", sequence=20)
        content = client_a.get(
            reverse("inventory:itemattribute_detail", args=[attribute_a.pk])).content
        siblings_section = content.split(b"Other Attributes")[1]
        assert b">Size<" in siblings_section
        assert b">Color<" not in siblings_section

    def test_file_siblings_exclude_self(self, client_a, tenant_a, item_a, product_file_a):
        from apps.inventory.models import ProductFile
        ProductFile.objects.create(
            tenant=tenant_a, item=item_a, kind="datasheet", title="Spec sheet",
            url="https://files.example.com/catalog/cat-1/sheet.pdf")
        content = client_a.get(
            reverse("inventory:productfile_detail", args=[product_file_a.pk])).content
        siblings_section = content.split(b"Other Files")[1]
        assert b"Spec sheet" in siblings_section
        assert b">Widget photo<" not in siblings_section

    def test_price_siblings_survive_poisoned_write(self, client_a, tenant_a, tenant_b, item_a,
                                                   price_a):
        """The view-level tenant filter is the LAST line of defence: even a raw write that
        bypassed every form/model guard (foreign-tenant row on OUR item) cannot render."""
        from apps.inventory.models import ItemPrice
        ItemPrice.objects.create(tenant=tenant_b, item=item_a, price_type="wholesale",
                                 unit_price=Decimal("1.00"))
        content = client_a.get(
            reverse("inventory:itemprice_detail", args=[price_a.pk])).content
        assert b"Globex" not in content.split(b"Other Prices")[1]
        assert b"1.00" not in content.split(b"Other Prices")[1]


class TestCrudFlows:
    def test_create_edit_delete_attribute(self, client_a, item_a, attribute_a):
        url = reverse("inventory:itemattribute_create")
        response = client_a.post(url, data={
            "item": item_a.pk, "name": "Material", "value": "Steel", "unit": "",
            "sequence": "20",
        })
        assert response.status_code == 302
        edit_url = reverse("inventory:itemattribute_edit", args=[attribute_a.pk])
        response = client_a.post(edit_url, data={
            "item": item_a.pk, "name": "Color", "value":"Matte Black", "unit": "",
            "sequence": "10",
        })
        assert response.status_code == 302
        attribute_a.refresh_from_db()
        assert attribute_a.value == "Matte Black"
        delete_url = reverse("inventory:itemattribute_delete", args=[attribute_a.pk])
        assert client_a.get(delete_url).status_code == 405      # GET is refused…
        assert client_a.post(delete_url).status_code == 302     # …POST deletes
        from apps.inventory.models import ItemAttribute
        assert not ItemAttribute.objects.filter(pk=attribute_a.pk).exists()

    def test_overview_counts_render(self, client_a, attribute_a, price_a, product_file_a):
        content = client_a.get(reverse("inventory:overview")).content
        assert b"Catalog Completeness" in content
        assert b"Price Rows" in content
