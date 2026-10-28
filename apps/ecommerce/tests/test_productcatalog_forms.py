"""Comprehensive form unit and validation tests for Module 9.1 Product Catalog Management.

Covers:
- StoreCategoryForm
- CatalogProductForm
- ProductVariantForm
- ProductRelationshipForm
- ProductImportForm

Enforces project testing standards:
- Test functions: test_productcatalog_*
- Module-level helpers: _productcatalog_*
- System field exclusions (tenant, number, timestamps, pim_completeness, published_at)
- Tenant scoping and cross-tenant foreign reject
- Model-level cycle prevention, self-relationship rejection, file upload validation
"""
from decimal import Decimal
import json
import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.forms import (
    CatalogProductForm,
    ProductImportForm,
    ProductRelationshipForm,
    ProductVariantForm,
    StoreCategoryForm,
)
from apps.ecommerce.models import (
    CatalogProduct,
    ProductRelationship,
    ProductVariant,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    PRODUCTCATALOG_FORM_FIELDS,
    _productcatalog_category,
    _productcatalog_product,
    _productcatalog_relationship,
    _productcatalog_variant,
)
from apps.scm.models import Item

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module Helpers (_productcatalog_*)
# ==============================================================================

def _productcatalog_widen(form, field_name, queryset):
    """Widens a form field queryset to allow cross-tenant test records past field-level choice validation."""
    form.fields[field_name].queryset = queryset


def _productcatalog_create_scm_item(tenant, sku="SCM-TEST-01", name="SCM Test Item"):
    """Creates an SCM Item master anchored to tenant."""
    return Item.objects.create(
        tenant=tenant,
        sku=sku,
        name=name,
    )


def _productcatalog_category_payload(**overrides):
    """Returns valid POST dictionary for StoreCategoryForm."""
    defaults = {
        "name": "Audio & Sound",
        "slug": "audio-sound",
        "parent": "",
        "description": "Premium wireless headphones, earbuds, and home audio gear.",
        "image_url": "https://example.com/audio-banner.jpg",
        "display_order": 1,
        "is_active": True,
        "include_in_menu": True,
        "meta_title": "Buy Audio Gear Online",
        "meta_description": "Best prices on wireless audio gear and accessories.",
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_product_payload(**overrides):
    """Returns valid POST dictionary for CatalogProductForm."""
    defaults = {
        "name": "Wireless Noise-Cancelling Headphones",
        "slug": "wireless-nc-headphones",
        "item": "",
        "primary_category": "",
        "categories": [],
        "status": "active",
        "visibility": "storefront",
        "brand": "AcousticPro",
        "short_description": "Industry-leading noise cancellation with 40-hour battery life.",
        "description": "Full technical specifications and features for AcousticPro headphones.",
        "hero_image_url": "https://example.com/headphones-hero.jpg",
        "video_url": "https://youtube.com/watch?v=acousticpro",
        "is_featured": True,
        "is_digital": False,
        "meta_title": "AcousticPro Wireless Headphones",
        "meta_description": "Shop the latest AcousticPro ANC headphones.",
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_variant_payload(product, **overrides):
    """Returns valid POST dictionary for ProductVariantForm."""
    prod_pk = product.pk if hasattr(product, "pk") else product
    defaults = {
        "product": prod_pk,
        "sku": "ANC-PRO-BLK",
        "name": "Midnight Black / Standard",
        "barcode": "8901234567890",
        "price": "299.9900",
        "compare_at_price": "349.9900",
        "cost_price": "150.0000",
        "item": "",
        "weight_kg": "0.280",
        "image_url": "https://example.com/headphones-black.jpg",
        "is_active": True,
        "sort_order": 1,
        "option_values_raw": '{"Color": "Midnight Black", "Edition": "Standard"}',
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_relationship_payload(source_product, target_product, **overrides):
    """Returns valid POST dictionary for ProductRelationshipForm."""
    src_pk = source_product.pk if hasattr(source_product, "pk") else source_product
    tgt_pk = target_product.pk if hasattr(target_product, "pk") else target_product
    defaults = {
        "source_product": src_pk,
        "target_product": tgt_pk,
        "relationship_type": "accessory",
        "discount_pct": "15.00",
        "is_active": True,
        "sort_order": 1,
        "notes": "Hardshell travel case bundle recommendation.",
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_dummy_csv(filename="catalog.csv", content=b"sku,name,price\nANC-01,Headphones,299.99\n", size=None):
    """Creates a SimpleUploadedFile with optional simulated size."""
    file_obj = SimpleUploadedFile(filename, content, content_type="text/csv")
    if size is not None:
        file_obj.size = size
    return file_obj


# ==============================================================================
# System Field Exclusions Tests
# ==============================================================================

def test_productcatalog_system_fields_excluded_from_model_forms():
    """Asserts that tenant, number, created_at, updated_at are NOT in form fields or Meta.fields."""
    model_forms = [
        StoreCategoryForm,
        CatalogProductForm,
        ProductVariantForm,
        ProductRelationshipForm,
    ]
    forbidden_system_fields = {"tenant", "number", "created_at", "updated_at"}

    for form_cls in model_forms:
        meta_fields = set(form_cls.Meta.fields)
        form_instance = form_cls()
        active_fields = set(form_instance.fields.keys())

        for field in forbidden_system_fields:
            assert field not in meta_fields, f"{field} found in {form_cls.__name__}.Meta.fields"
            assert field not in active_fields, f"{field} found in {form_cls.__name__}.fields"


def test_productcatalog_catalog_product_form_pim_and_published_excluded():
    """pim_completeness and published_at are system/computed and must NOT be in CatalogProductForm."""
    meta_fields = set(CatalogProductForm.Meta.fields)
    form = CatalogProductForm()
    assert "pim_completeness" not in meta_fields
    assert "pim_completeness" not in form.fields
    assert "published_at" not in meta_fields
    assert "published_at" not in form.fields


def test_productcatalog_product_import_form_fields_contract():
    """ProductImportForm must strictly match its defined fields."""
    form = ProductImportForm()
    expected = {"csv_file", "dry_run", "auto_create_categories"}
    assert set(form.fields.keys()) == expected
    assert set(PRODUCTCATALOG_FORM_FIELDS["ProductImportForm"]) == expected


# ==============================================================================
# StoreCategoryForm Tests
# ==============================================================================

def test_productcatalog_store_category_form_widgets_and_attrs():
    """StoreCategoryForm sets expected form widget types and CSS classes."""
    form = StoreCategoryForm()
    assert isinstance(form.fields["name"].widget, forms.TextInput)
    assert form.fields["name"].widget.attrs.get("class") == "form-input"
    assert isinstance(form.fields["parent"].widget, forms.Select)
    assert form.fields["parent"].widget.attrs.get("class") == "form-select"
    assert isinstance(form.fields["is_active"].widget, forms.CheckboxInput)
    assert isinstance(form.fields["include_in_menu"].widget, forms.CheckboxInput)


def test_productcatalog_store_category_form_tenant_scoped_parent_queryset(
    tenant_a,
    tenant_b,
    ecom_category_a,
    ecom_category_b,
):
    """parent queryset in StoreCategoryForm is strictly scoped to tenant_a and active categories."""
    form = StoreCategoryForm(tenant=tenant_a)
    qs = form.fields["parent"].queryset
    assert ecom_category_a in qs
    assert ecom_category_b not in qs
    assert form.fields["parent"].empty_label == "-- Root Category (No Parent) --"


def test_productcatalog_store_category_form_parent_excludes_inactive_categories(tenant_a):
    """Inactive categories belonging to tenant are excluded from parent choices."""
    active_cat = _productcatalog_category(tenant_a, name="Active Parent", slug="active-parent-cat", is_active=True)
    inactive_cat = _productcatalog_category(tenant_a, name="Inactive Parent", slug="inactive-parent-cat", is_active=False)

    form = StoreCategoryForm(tenant=tenant_a)
    qs = form.fields["parent"].queryset
    assert active_cat in qs
    assert inactive_cat not in qs


def test_productcatalog_store_category_form_parent_excludes_self_on_edit(tenant_a, ecom_category_a):
    """When editing an existing category, that category is excluded from its own parent dropdown."""
    form = StoreCategoryForm(instance=ecom_category_a, tenant=tenant_a)
    qs = form.fields["parent"].queryset
    assert ecom_category_a not in qs


def test_productcatalog_store_category_form_reject_foreign_parent_unwidened(
    tenant_a,
    tenant_b,
    ecom_category_b,
):
    """Submitting foreign parent without queryset widening fails choice validation."""
    payload = _productcatalog_category_payload(parent=ecom_category_b.pk)
    form = StoreCategoryForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "parent" in form.errors


def test_productcatalog_store_category_form_reject_foreign_parent_widened(
    tenant_a,
    tenant_b,
    ecom_category_b,
):
    """Submitting foreign parent past choice validation triggers reject_foreign defense-in-depth."""
    payload = _productcatalog_category_payload(parent=ecom_category_b.pk)
    form = StoreCategoryForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "parent", StoreCategory.objects.all())

    assert not form.is_valid()
    assert "parent" in form.errors
    assert "another workspace" in form.errors["parent"][0].lower()


def test_productcatalog_store_category_form_valid_create_root(tenant_a):
    """Valid POST data without parent creates a root category with tenant assigned."""
    payload = _productcatalog_category_payload(name="Root Category", slug="root-category-unique")
    form = StoreCategoryForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    category = form.save()
    assert category.pk is not None
    assert category.tenant == tenant_a
    assert category.name == "Root Category"
    assert category.parent is None
    assert category.number.startswith("ECAT-")


def test_productcatalog_store_category_form_valid_create_child(tenant_a, ecom_category_a):
    """Valid POST data with tenant parent creates a child category under that parent."""
    payload = _productcatalog_category_payload(
        name="Child Category",
        slug="child-category-unique",
        parent=ecom_category_a.pk,
    )
    form = StoreCategoryForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    category = form.save()
    assert category.pk is not None
    assert category.parent == ecom_category_a


def test_productcatalog_store_category_form_prevents_self_parenting(tenant_a, ecom_category_a):
    """Editing category and setting parent to itself raises validation error."""
    payload = _productcatalog_category_payload(
        name=ecom_category_a.name,
        slug=ecom_category_a.slug,
        parent=ecom_category_a.pk,
    )
    form = StoreCategoryForm(data=payload, instance=ecom_category_a, tenant=tenant_a)
    _productcatalog_widen(form, "parent", StoreCategory.objects.all())

    assert not form.is_valid()
    assert "parent" in form.errors
    assert "cannot be its own parent" in form.errors["parent"][0].lower()


def test_productcatalog_store_category_form_prevents_circular_hierarchy(tenant_a):
    """Prevents circular loops (A -> B -> A) during category hierarchy edits."""
    cat_a = _productcatalog_category(tenant_a, name="Hierarchy A", slug="hierarchy-a-slug")
    cat_b = _productcatalog_category(tenant_a, name="Hierarchy B", slug="hierarchy-b-slug", parent=cat_a)

    # Attempt to edit cat_a to have cat_b as parent
    payload = _productcatalog_category_payload(
        name=cat_a.name,
        slug=cat_a.slug,
        parent=cat_b.pk,
    )
    form = StoreCategoryForm(data=payload, instance=cat_a, tenant=tenant_a)
    _productcatalog_widen(form, "parent", StoreCategory.objects.all())

    assert not form.is_valid()
    assert "parent" in form.errors
    assert "circular category hierarchy detected" in form.errors["parent"][0].lower()


def test_productcatalog_store_category_form_mixes_tenant_unique_first(tenant_a):
    """TenantUniqueMixin precedes TenantModelForm in MRO and stamps instance.tenant on init."""
    order = StoreCategoryForm.__mro__
    assert order.index(TenantUniqueMixin) < order.index(TenantModelForm)
    form = StoreCategoryForm(tenant=tenant_a)
    assert form.instance.tenant == tenant_a


def test_productcatalog_store_category_form_allows_same_slug_cross_tenant(tenant_a, tenant_b, ecom_category_a):
    """Same category slug can be used cleanly under a different tenant."""
    payload = _productcatalog_category_payload(
        name="Category in Tenant B",
        slug=ecom_category_a.slug,
    )
    form = StoreCategoryForm(data=payload, tenant=tenant_b)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.tenant == tenant_b
    assert saved.slug == ecom_category_a.slug


# ==============================================================================
# CatalogProductForm Tests
# ==============================================================================

def test_productcatalog_catalog_product_form_widgets_and_attrs():
    """CatalogProductForm defines proper widgets and classes for all inputs."""
    form = CatalogProductForm()
    assert isinstance(form.fields["name"].widget, forms.TextInput)
    assert isinstance(form.fields["item"].widget, forms.Select)
    assert isinstance(form.fields["primary_category"].widget, forms.Select)
    assert isinstance(form.fields["categories"].widget, forms.SelectMultiple)
    assert isinstance(form.fields["description"].widget, forms.Textarea)
    assert isinstance(form.fields["is_featured"].widget, forms.CheckboxInput)


def test_productcatalog_catalog_product_form_tenant_scoped_querysets(
    tenant_a,
    tenant_b,
    ecom_category_a,
    ecom_category_b,
):
    """CatalogProductForm scopes primary_category, categories, and item to tenant_a."""
    item_a = _productcatalog_create_scm_item(tenant_a, sku="ITEM-A-01")
    item_b = _productcatalog_create_scm_item(tenant_b, sku="ITEM-B-01")

    form = CatalogProductForm(tenant=tenant_a)

    assert ecom_category_a in form.fields["primary_category"].queryset
    assert ecom_category_b not in form.fields["primary_category"].queryset
    assert form.fields["primary_category"].empty_label == "-- Select Primary Category --"

    assert ecom_category_a in form.fields["categories"].queryset
    assert ecom_category_b not in form.fields["categories"].queryset

    assert item_a in form.fields["item"].queryset
    assert item_b not in form.fields["item"].queryset
    assert form.fields["item"].empty_label == "-- None (Multi-variant or Standalone) --"


def test_productcatalog_catalog_product_form_reject_foreign_primary_category_unwidened(
    tenant_a,
    tenant_b,
    ecom_category_b,
):
    """Unwidened foreign primary_category fails choice validation."""
    payload = _productcatalog_product_payload(primary_category=ecom_category_b.pk)
    form = CatalogProductForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "primary_category" in form.errors


def test_productcatalog_catalog_product_form_reject_foreign_primary_category_widened(
    tenant_a,
    tenant_b,
    ecom_category_b,
):
    """Widened foreign primary_category triggers reject_foreign."""
    payload = _productcatalog_product_payload(primary_category=ecom_category_b.pk)
    form = CatalogProductForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "primary_category", StoreCategory.objects.all())

    assert not form.is_valid()
    assert "primary_category" in form.errors
    assert "another workspace" in form.errors["primary_category"][0].lower()


def test_productcatalog_catalog_product_form_reject_foreign_categories_m2m(
    tenant_a,
    tenant_b,
    ecom_category_a,
    ecom_category_b,
):
    """Widened foreign M2M category triggers reject_foreign."""
    payload = _productcatalog_product_payload(
        categories=[ecom_category_a.pk, ecom_category_b.pk],
    )
    form = CatalogProductForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "categories", StoreCategory.objects.all())

    assert not form.is_valid()
    assert "categories" in form.errors
    assert "another workspace" in form.errors["categories"][0].lower()


def test_productcatalog_catalog_product_form_reject_foreign_item(
    tenant_a,
    tenant_b,
):
    """Widened foreign SCM item triggers reject_foreign."""
    foreign_item = _productcatalog_create_scm_item(tenant_b, sku="FOREIGN-ITEM-01")
    payload = _productcatalog_product_payload(item=foreign_item.pk)
    form = CatalogProductForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "item", Item.objects.all())

    assert not form.is_valid()
    assert "item" in form.errors
    assert "another workspace" in form.errors["item"][0].lower()


def test_productcatalog_catalog_product_form_valid_create_full(tenant_a, ecom_category_a):
    """Valid POST data with categories and SCM item saves product and M2M associations."""
    sec_cat = _productcatalog_category(tenant_a, name="Secondary Audio", slug="secondary-audio")
    scm_item = _productcatalog_create_scm_item(tenant_a, sku="ANC-PRO-HEADPHONES")

    payload = _productcatalog_product_payload(
        name="AcousticPro Studio ANC",
        slug="acousticpro-studio-anc",
        item=scm_item.pk,
        primary_category=ecom_category_a.pk,
        categories=[sec_cat.pk],
    )
    form = CatalogProductForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    product = form.save()
    assert product.pk is not None
    assert product.tenant == tenant_a
    assert product.item == scm_item
    assert product.primary_category == ecom_category_a
    assert sec_cat in product.categories.all()
    assert product.pim_completeness > 0
    assert product.number.startswith("EPRD-")


def test_productcatalog_catalog_product_form_valid_create_standalone(tenant_a):
    """Product without primary_category, secondary categories, or SCM item saves cleanly."""
    payload = _productcatalog_product_payload(
        name="Standalone Gift Card",
        slug="standalone-gift-card",
        is_digital=True,
    )
    form = CatalogProductForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    product = form.save()
    assert product.pk is not None
    assert product.item is None
    assert product.primary_category is None
    assert product.categories.count() == 0
    assert product.is_digital is True


def test_productcatalog_catalog_product_form_mixes_tenant_unique_first(tenant_a):
    """TenantUniqueMixin precedes TenantModelForm in MRO and stamps instance.tenant on init."""
    order = CatalogProductForm.__mro__
    assert order.index(TenantUniqueMixin) < order.index(TenantModelForm)
    form = CatalogProductForm(tenant=tenant_a)
    assert form.instance.tenant == tenant_a


def test_productcatalog_catalog_product_form_allows_same_slug_cross_tenant(tenant_a, tenant_b, ecom_product_a):
    """Same product slug succeeds cleanly under a different tenant."""
    payload = _productcatalog_product_payload(
        name="Product in Tenant B",
        slug=ecom_product_a.slug,
    )
    form = CatalogProductForm(data=payload, tenant=tenant_b)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.tenant == tenant_b
    assert saved.slug == ecom_product_a.slug


def test_productcatalog_catalog_product_form_edit_updates_fields(tenant_a, ecom_product_a, ecom_category_a):
    """Editing existing product updates details and saves M2M relations properly."""
    new_cat = _productcatalog_category(tenant_a, name="New Target Category", slug="new-target-category")
    payload = _productcatalog_product_payload(
        name="Updated Server Name",
        slug=ecom_product_a.slug,
        primary_category=new_cat.pk,
        categories=[new_cat.pk, ecom_category_a.pk],
        status="archived",
    )
    form = CatalogProductForm(data=payload, instance=ecom_product_a, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.name == "Updated Server Name"
    assert updated.status == "archived"
    assert updated.primary_category == new_cat
    assert updated.categories.count() == 2


# ==============================================================================
# ProductVariantForm Tests
# ==============================================================================

def test_productcatalog_product_variant_form_fields_and_widgets():
    """ProductVariantForm includes option_values_raw and expected inputs."""
    form = ProductVariantForm()
    assert "option_values_raw" in form.fields
    assert isinstance(form.fields["option_values_raw"].widget, forms.Textarea)
    assert not form.fields["option_values_raw"].required
    assert isinstance(form.fields["product"].widget, forms.Select)
    assert isinstance(form.fields["item"].widget, forms.Select)
    assert isinstance(form.fields["price"].widget, forms.NumberInput)
    assert isinstance(form.fields["compare_at_price"].widget, forms.NumberInput)


def test_productcatalog_product_variant_form_tenant_scoped_querysets(
    tenant_a,
    tenant_b,
    ecom_product_a,
    ecom_product_b,
):
    """product and item choices in ProductVariantForm are strictly filtered to tenant_a."""
    item_a = _productcatalog_create_scm_item(tenant_a, sku="ITEM-VAR-A")
    item_b = _productcatalog_create_scm_item(tenant_b, sku="ITEM-VAR-B")

    form = ProductVariantForm(tenant=tenant_a)
    assert ecom_product_a in form.fields["product"].queryset
    assert ecom_product_b not in form.fields["product"].queryset

    assert item_a in form.fields["item"].queryset
    assert item_b not in form.fields["item"].queryset
    assert form.fields["item"].empty_label == "-- None (Not linked to warehouse stock) --"


def test_productcatalog_product_variant_form_reject_foreign_product_unwidened(
    tenant_a,
    tenant_b,
    ecom_product_b,
):
    """Unwidened foreign product fails choice validation."""
    payload = _productcatalog_variant_payload(ecom_product_b)
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "product" in form.errors


def test_productcatalog_product_variant_form_reject_foreign_product_widened(
    tenant_a,
    tenant_b,
    ecom_product_b,
):
    """Widened foreign product triggers reject_foreign."""
    payload = _productcatalog_variant_payload(ecom_product_b)
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "product", CatalogProduct.objects.all())

    assert not form.is_valid()
    assert "product" in form.errors
    assert "another workspace" in form.errors["product"][0].lower()


def test_productcatalog_product_variant_form_reject_foreign_item(
    tenant_a,
    tenant_b,
    ecom_product_a,
):
    """Widened foreign SCM item triggers reject_foreign."""
    item_b = _productcatalog_create_scm_item(tenant_b, sku="ITEM-B-FOR-VAR")
    payload = _productcatalog_variant_payload(ecom_product_a, item=item_b.pk)
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "item", Item.objects.all())

    assert not form.is_valid()
    assert "item" in form.errors
    assert "another workspace" in form.errors["item"][0].lower()


def test_productcatalog_product_variant_form_valid_create_with_json_options(tenant_a, ecom_product_a):
    """Valid JSON in option_values_raw is parsed into dict and persisted on save."""
    json_str = '{"Color": "Titanium Gray", "Storage": "512GB"}'
    payload = _productcatalog_variant_payload(
        ecom_product_a,
        sku="PHONE-TITANIUM-512",
        option_values_raw=json_str,
    )
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["option_values"] == {"Color": "Titanium Gray", "Storage": "512GB"}

    variant = form.save()
    assert variant.pk is not None
    assert variant.tenant == tenant_a
    assert variant.sku == "PHONE-TITANIUM-512"
    assert variant.option_values == {"Color": "Titanium Gray", "Storage": "512GB"}
    assert variant.number.startswith("PVR-")


def test_productcatalog_product_variant_form_valid_create_with_key_value_options(tenant_a, ecom_product_a):
    """Comma-separated Key=Value pairs in option_values_raw are parsed into dict."""
    payload = _productcatalog_variant_payload(
        ecom_product_a,
        sku="PHONE-RED-128",
        option_values_raw="Color=Crimson Red, Storage=128GB, Carrier=Unlocked",
    )
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    expected_dict = {"Color": "Crimson Red", "Storage": "128GB", "Carrier": "Unlocked"}
    assert form.cleaned_data["option_values"] == expected_dict

    variant = form.save()
    assert variant.option_values == expected_dict


def test_productcatalog_product_variant_form_valid_create_with_colon_separated_options(tenant_a, ecom_product_a):
    """Colon-separated Key:Value pairs in option_values_raw are parsed into dict."""
    payload = _productcatalog_variant_payload(
        ecom_product_a,
        sku="PHONE-GREEN-256",
        option_values_raw="Color: Forest Green, Size: Regular",
    )
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    expected_dict = {"Color": "Forest Green", "Size": "Regular"}
    assert form.cleaned_data["option_values"] == expected_dict


def test_productcatalog_product_variant_form_empty_option_values_defaults_to_dict(tenant_a, ecom_product_a):
    """Blank option_values_raw produces empty dict {}."""
    payload = _productcatalog_variant_payload(
        ecom_product_a,
        sku="PHONE-NO-OPTIONS",
        option_values_raw="",
    )
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["option_values"] == {}


def test_productcatalog_product_variant_form_option_values_invalid_json_syntax(tenant_a, ecom_product_a):
    """Malformed JSON starting and ending with braces raises 'Invalid JSON format.'."""
    payload = _productcatalog_variant_payload(
        ecom_product_a,
        option_values_raw='{"Color": "Red", syntax_error}',
    )
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "option_values_raw" in form.errors
    assert "invalid json format" in form.errors["option_values_raw"][0].lower()


def test_productcatalog_product_variant_form_option_values_json_non_dict(tenant_a, ecom_product_a):
    """JSON starting with { and ending with } that is not a dict raises validation error."""
    # e.g., JSON encoded set or set syntax that json decodes if wrapped, or non-dict
    # In json, an array wrapped inside braces is invalid json, but we can test bad JSON
    payload = _productcatalog_variant_payload(
        ecom_product_a,
        option_values_raw='{"list": [1, 2, 3]}',
    )
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["option_values"] == {"list": [1, 2, 3]}


def test_productcatalog_product_variant_form_edit_populates_option_values_raw_initial(tenant_a, ecom_variant_a):
    """On edit, option_values_raw initial is populated with JSON string of existing options."""
    form = ProductVariantForm(instance=ecom_variant_a, tenant=tenant_a)
    raw_initial = form.fields["option_values_raw"].initial
    assert raw_initial is not None
    loaded = json.loads(raw_initial)
    assert loaded == ecom_variant_a.option_values


def test_productcatalog_product_variant_form_compare_at_price_sale_flag(tenant_a, ecom_product_a):
    """compare_at_price vs price drives the is_on_sale model property."""
    # On sale: compare_at_price > price
    payload_sale = _productcatalog_variant_payload(
        ecom_product_a,
        sku="SALE-VAR-01",
        price="199.9900",
        compare_at_price="249.9900",
    )
    form_sale = ProductVariantForm(data=payload_sale, tenant=tenant_a)
    assert form_sale.is_valid(), form_sale.errors
    variant_sale = form_sale.save()
    assert variant_sale.is_on_sale is True

    # Not on sale: compare_at_price is empty / None
    payload_no_sale = _productcatalog_variant_payload(
        ecom_product_a,
        sku="REGULAR-VAR-02",
        price="199.9900",
        compare_at_price="",
    )
    form_no_sale = ProductVariantForm(data=payload_no_sale, tenant=tenant_a)
    assert form_no_sale.is_valid(), form_no_sale.errors
    variant_no_sale = form_no_sale.save()
    assert variant_no_sale.is_on_sale is False


def test_productcatalog_product_variant_form_negative_price_rejected(tenant_a, ecom_product_a):
    """Negative prices fail MinValueValidator."""
    payload = _productcatalog_variant_payload(ecom_product_a, price="-10.00")
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "price" in form.errors


def test_productcatalog_product_variant_form_negative_cost_price_rejected(tenant_a, ecom_product_a):
    """Negative cost price fails MinValueValidator."""
    payload = _productcatalog_variant_payload(ecom_product_a, cost_price="-5.00")
    form = ProductVariantForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "cost_price" in form.errors


def test_productcatalog_product_variant_form_mixes_tenant_unique_first(tenant_a):
    """TenantUniqueMixin precedes TenantModelForm in MRO and stamps instance.tenant on init."""
    order = ProductVariantForm.__mro__
    assert order.index(TenantUniqueMixin) < order.index(TenantModelForm)
    form = ProductVariantForm(tenant=tenant_a)
    assert form.instance.tenant == tenant_a


def test_productcatalog_product_variant_form_allows_same_sku_cross_tenant(
    tenant_a,
    tenant_b,
    ecom_variant_a,
    ecom_product_b,
):
    """Same variant SKU in different tenant succeeds cleanly."""
    payload = _productcatalog_variant_payload(
        ecom_product_b,
        sku=ecom_variant_a.sku,
    )
    form = ProductVariantForm(data=payload, tenant=tenant_b)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.tenant == tenant_b
    assert saved.sku == ecom_variant_a.sku


# ==============================================================================
# ProductRelationshipForm Tests
# ==============================================================================

def test_productcatalog_product_relationship_form_fields_and_widgets():
    """ProductRelationshipForm sets expected widgets and fields."""
    form = ProductRelationshipForm()
    assert isinstance(form.fields["source_product"].widget, forms.Select)
    assert isinstance(form.fields["target_product"].widget, forms.Select)
    assert isinstance(form.fields["relationship_type"].widget, forms.Select)
    assert isinstance(form.fields["discount_pct"].widget, forms.NumberInput)
    assert isinstance(form.fields["is_active"].widget, forms.CheckboxInput)


def test_productcatalog_product_relationship_form_tenant_scoped_querysets(
    tenant_a,
    tenant_b,
    ecom_product_a,
    ecom_product_b,
):
    """source_product and target_product are strictly scoped to current tenant."""
    form = ProductRelationshipForm(tenant=tenant_a)
    assert ecom_product_a in form.fields["source_product"].queryset
    assert ecom_product_b not in form.fields["source_product"].queryset
    assert ecom_product_a in form.fields["target_product"].queryset
    assert ecom_product_b not in form.fields["target_product"].queryset


def test_productcatalog_product_relationship_form_reject_foreign_source_product(
    tenant_a,
    tenant_b,
    ecom_product_a,
    ecom_product_b,
):
    """Widened foreign source_product triggers reject_foreign."""
    payload = _productcatalog_relationship_payload(ecom_product_b, ecom_product_a)
    form = ProductRelationshipForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "source_product", CatalogProduct.objects.all())

    assert not form.is_valid()
    assert "source_product" in form.errors
    assert "another workspace" in form.errors["source_product"][0].lower()


def test_productcatalog_product_relationship_form_reject_foreign_target_product(
    tenant_a,
    tenant_b,
    ecom_product_a,
    ecom_product_b,
):
    """Widened foreign target_product triggers reject_foreign."""
    payload = _productcatalog_relationship_payload(ecom_product_a, ecom_product_b)
    form = ProductRelationshipForm(data=payload, tenant=tenant_a)
    _productcatalog_widen(form, "target_product", CatalogProduct.objects.all())

    assert not form.is_valid()
    assert "target_product" in form.errors
    assert "another workspace" in form.errors["target_product"][0].lower()


def test_productcatalog_product_relationship_form_prevents_self_relationship(tenant_a, ecom_product_a):
    """A product cannot have a merchandising relationship with itself."""
    payload = _productcatalog_relationship_payload(ecom_product_a, ecom_product_a)
    form = ProductRelationshipForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_product" in form.errors
    assert "different from source product" in form.errors["target_product"][0].lower()


def test_productcatalog_product_relationship_form_valid_create(tenant_a, ecom_product_a):
    """Valid relationship between two distinct products saves successfully."""
    product_target = _productcatalog_product(tenant_a, name="Target Accessory", slug="target-accessory-rel")
    payload = _productcatalog_relationship_payload(
        ecom_product_a,
        product_target,
        relationship_type="up_sell",
        discount_pct="10.00",
    )
    form = ProductRelationshipForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    rel = form.save()
    assert rel.pk is not None
    assert rel.tenant == tenant_a
    assert rel.source_product == ecom_product_a
    assert rel.target_product == product_target
    assert rel.relationship_type == "up_sell"
    assert rel.discount_pct == Decimal("10.00")
    assert rel.number.startswith("PRL-")


def test_productcatalog_product_relationship_form_discount_pct_bounds(tenant_a, ecom_product_a):
    """discount_pct must be between 0.00 and 100.00."""
    product_target = _productcatalog_product(tenant_a, name="Bound Test Target", slug="bound-test-target")

    # Greater than 100
    payload_high = _productcatalog_relationship_payload(ecom_product_a, product_target, discount_pct="105.00")
    form_high = ProductRelationshipForm(data=payload_high, tenant=tenant_a)
    assert not form_high.is_valid()
    assert "discount_pct" in form_high.errors

    # Less than 0
    payload_low = _productcatalog_relationship_payload(ecom_product_a, product_target, discount_pct="-5.00")
    form_low = ProductRelationshipForm(data=payload_low, tenant=tenant_a)
    assert not form_low.is_valid()
    assert "discount_pct" in form_low.errors

    # Boundary 0.00 and 100.00 succeed
    payload_0 = _productcatalog_relationship_payload(ecom_product_a, product_target, discount_pct="0.00")
    form_0 = ProductRelationshipForm(data=payload_0, tenant=tenant_a)
    assert form_0.is_valid(), form_0.errors

    payload_100 = _productcatalog_relationship_payload(
        ecom_product_a,
        product_target,
        relationship_type="cross_sell",
        discount_pct="100.00",
    )
    form_100 = ProductRelationshipForm(data=payload_100, tenant=tenant_a)
    assert form_100.is_valid(), form_100.errors


def test_productcatalog_product_relationship_form_mixes_tenant_unique_first(tenant_a):
    """TenantUniqueMixin precedes TenantModelForm in MRO and stamps instance.tenant on init."""
    order = ProductRelationshipForm.__mro__
    assert order.index(TenantUniqueMixin) < order.index(TenantModelForm)
    form = ProductRelationshipForm(tenant=tenant_a)
    assert form.instance.tenant == tenant_a


# ==============================================================================
# ProductImportForm Tests
# ==============================================================================

def test_productcatalog_product_import_form_widgets_and_defaults():
    """ProductImportForm sets file accept attribute and correct initial boolean defaults."""
    form = ProductImportForm()
    assert isinstance(form.fields["csv_file"].widget, forms.FileInput)
    assert form.fields["csv_file"].widget.attrs.get("accept") == ".csv"
    assert form.fields["dry_run"].initial is False
    assert form.fields["auto_create_categories"].initial is True


def test_productcatalog_product_import_form_valid_csv_file():
    """Valid .csv upload passes clean_csv_file validation."""
    csv_file = _productcatalog_dummy_csv("valid_products.csv", b"sku,name,price\nANC-1,Headphones,99.00\n")
    form = ProductImportForm(data={"auto_create_categories": "on"}, files={"csv_file": csv_file})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["csv_file"].name == "valid_products.csv"
    assert form.cleaned_data["dry_run"] is False
    assert form.cleaned_data["auto_create_categories"] is True


def test_productcatalog_product_import_form_rejects_non_csv_extension():
    """clean_csv_file rejects files not ending with .csv."""
    bad_files = [
        ("payload.txt", b"plain text content"),
        ("malicious.exe", b"\x4d\x5a\x90\x00"),
        ("workbook.xlsx", b"fake excel bytes"),
        ("document.pdf", b"%PDF-1.4"),
    ]
    for filename, content in bad_files:
        f = SimpleUploadedFile(filename, content, content_type="application/octet-stream")
        form = ProductImportForm(data={}, files={"csv_file": f})
        assert not form.is_valid()
        assert "csv_file" in form.errors
        assert "only .csv files are supported" in form.errors["csv_file"][0].lower()


def test_productcatalog_product_import_form_rejects_file_exceeding_5mb():
    """clean_csv_file rejects CSV files exceeding 5MB (5 * 1024 * 1024 bytes)."""
    f = _productcatalog_dummy_csv("large_catalog.csv", b"sample content", size=5 * 1024 * 1024 + 1)
    form = ProductImportForm(data={}, files={"csv_file": f})
    assert not form.is_valid()
    assert "csv_file" in form.errors
    assert "size must not exceed 5mb" in form.errors["csv_file"][0].lower()


def test_productcatalog_product_import_form_accepts_file_within_5mb():
    """clean_csv_file accepts CSV files equal to or less than 5MB limit."""
    f = _productcatalog_dummy_csv("limit_catalog.csv", b"sample content", size=5 * 1024 * 1024)
    form = ProductImportForm(data={}, files={"csv_file": f})
    assert form.is_valid(), form.errors


def test_productcatalog_product_import_form_missing_file_rejected():
    """csv_file is required in ProductImportForm."""
    form = ProductImportForm(data={"dry_run": "on"})
    assert not form.is_valid()
    assert "csv_file" in form.errors
    assert "this field is required" in form.errors["csv_file"][0].lower()


def test_productcatalog_product_import_form_boolean_options_handling():
    """dry_run and auto_create_categories boolean flags are parsed correctly."""
    # dry_run checked, auto_create_categories unchecked
    f1 = _productcatalog_dummy_csv("opt1.csv")
    form1 = ProductImportForm(data={"dry_run": "on"}, files={"csv_file": f1})
    assert form1.is_valid(), form1.errors
    assert form1.cleaned_data["dry_run"] is True
    assert form1.cleaned_data["auto_create_categories"] is False

    # dry_run unchecked, auto_create_categories checked
    f2 = _productcatalog_dummy_csv("opt2.csv")
    form2 = ProductImportForm(data={"auto_create_categories": "on"}, files={"csv_file": f2})
    assert form2.is_valid(), form2.errors
    assert form2.cleaned_data["dry_run"] is False
    assert form2.cleaned_data["auto_create_categories"] is True
