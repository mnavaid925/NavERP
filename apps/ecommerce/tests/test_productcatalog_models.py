"""Comprehensive unit and invariant tests for eCommerce 9.1 Product Catalog models.

Covers:
- StoreCategory
- CatalogProduct
- ProductVariant
- ProductRelationship

Naming conventions enforced:
- Test functions: test_productcatalog_*
- Module-level helpers: _productcatalog_*
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    StoreCategory,
    CatalogProduct,
    ProductVariant,
    ProductRelationship,
)
from apps.ecommerce.tests.conftest import (
    _productcatalog_category,
    _productcatalog_product,
    _productcatalog_variant,
    _productcatalog_relationship,
)
from apps.scm.models import Item

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_productcatalog_*)
# ==============================================================================

def _productcatalog_create_scm_item(tenant, sku="SCM-TEST-01", name="SCM Test Item"):
    """Helper to create an SCM Item for FK validation tests."""
    return Item.objects.create(
        tenant=tenant,
        sku=sku,
        name=name,
    )


def _productcatalog_force_number(model_cls, tenant, number, **kwargs):
    """Instantiate and save an object with an explicitly forced number."""
    instance = model_cls(tenant=tenant, **kwargs)
    instance.number = number
    instance.save()
    return instance


# ==============================================================================
# StoreCategory Tests
# ==============================================================================

def test_productcatalog_storecategory_defaults_and_fields(tenant_a):
    """Test StoreCategory default values, field assignments, and model invariants."""
    cat = StoreCategory.objects.create(
        tenant=tenant_a,
        name="Smartphones",
        slug="smartphones",
    )
    assert cat.display_order == 0
    assert cat.is_active is True
    assert cat.include_in_menu is True
    assert cat.parent is None
    assert cat.description == ""
    assert cat.image_url == ""
    assert cat.meta_title == ""
    assert cat.meta_description == ""
    assert cat.created_at is not None
    assert cat.updated_at is not None


def test_productcatalog_storecategory_str_representation(tenant_a):
    """Test StoreCategory __str__ returns the category name."""
    cat = _productcatalog_category(tenant_a, name="Home Appliances")
    assert str(cat) == "Home Appliances"


def test_productcatalog_storecategory_autonumber_generation(tenant_a, tenant_b):
    """Test StoreCategory auto-numbers generate with ECAT- prefix and tenant sequence."""
    cat1 = _productcatalog_category(tenant_a, name="Laptops 1", slug="laptops-1")
    cat2 = _productcatalog_category(tenant_a, name="Laptops 2", slug="laptops-2")
    cat_b = _productcatalog_category(tenant_b, name="Laptops B", slug="laptops-b")

    assert cat1.number.startswith("ECAT-")
    assert cat2.number.startswith("ECAT-")
    assert cat_b.number.startswith("ECAT-")

    # Sequential continuity in tenant_a
    seq1 = int(cat1.number.split("-")[-1])
    seq2 = int(cat2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_productcatalog_storecategory_unique_number_per_tenant(tenant_a, tenant_b):
    """Test unique constraint on (tenant, number) for StoreCategory."""
    cat1 = _productcatalog_category(tenant_a, name="Audio", slug="audio")
    
    # Same number in different tenant is allowed
    cat_other = _productcatalog_force_number(
        StoreCategory,
        tenant=tenant_b,
        number=cat1.number,
        name="Audio Other",
        slug="audio-other",
    )
    assert cat_other.number == cat1.number

    # Duplicate number within the same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_force_number(
                StoreCategory,
                tenant=tenant_a,
                number=cat1.number,
                name="Duplicate Audio",
                slug="dup-audio",
            )


def test_productcatalog_storecategory_unique_slug_per_tenant(tenant_a, tenant_b):
    """Test unique constraint on (tenant, slug) for StoreCategory."""
    _productcatalog_category(tenant_a, name="Gaming", slug="gaming-slug")

    # Same slug in different tenant is allowed
    cat_b = _productcatalog_category(tenant_b, name="Gaming B", slug="gaming-slug")
    assert cat_b.slug == "gaming-slug"

    # Same slug in the same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_category(tenant_a, name="Gaming Duplicate", slug="gaming-slug")


def test_productcatalog_storecategory_clean_cross_tenant_parent(tenant_a, tenant_b):
    """Test clean() raises ValidationError if parent belongs to another tenant."""
    parent_b = _productcatalog_category(tenant_b, name="Parent B", slug="parent-b")
    child_a = StoreCategory(
        tenant=tenant_a,
        name="Child A",
        slug="child-a",
        parent=parent_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        child_a.clean()
    assert "parent" in exc_info.value.message_dict


def test_productcatalog_storecategory_clean_self_parent(tenant_a):
    """Test clean() raises ValidationError if category is set as its own parent."""
    cat = _productcatalog_category(tenant_a, name="Electronics", slug="electronics")
    cat.parent = cat
    with pytest.raises(ValidationError) as exc_info:
        cat.clean()
    assert "parent" in exc_info.value.message_dict
    assert "cannot be its own parent" in exc_info.value.message_dict["parent"][0]


def test_productcatalog_storecategory_clean_ancestor_cycle(tenant_a):
    """Test clean() detects circular hierarchy (A -> B -> C -> A) and raises ValidationError."""
    root = _productcatalog_category(tenant_a, name="Root", slug="root")
    middle = _productcatalog_category(tenant_a, name="Middle", slug="middle", parent=root)
    leaf = _productcatalog_category(tenant_a, name="Leaf", slug="leaf", parent=middle)

    # Creating a cycle by pointing root's parent to leaf
    root.parent = leaf
    with pytest.raises(ValidationError) as exc_info:
        root.clean()
    assert "parent" in exc_info.value.message_dict
    assert "Circular category hierarchy detected" in exc_info.value.message_dict["parent"][0]


def test_productcatalog_storecategory_breadcrumbs_and_full_path(tenant_a):
    """Test get_breadcrumbs() and full_path property for multi-level hierarchy."""
    root = _productcatalog_category(tenant_a, name="Computers", slug="computers")
    level2 = _productcatalog_category(tenant_a, name="Components", slug="components", parent=root)
    leaf = _productcatalog_category(tenant_a, name="Graphics Cards", slug="gpus", parent=level2)

    crumbs = leaf.get_breadcrumbs()
    assert len(crumbs) == 3
    assert crumbs[0]["name"] == "Computers"
    assert crumbs[1]["name"] == "Components"
    assert crumbs[2]["name"] == "Graphics Cards"
    assert leaf.full_path == "Computers > Components > Graphics Cards"


def test_productcatalog_storecategory_breadcrumbs_cycle_break(tenant_a):
    """Test get_breadcrumbs() terminates gracefully if a cycle exists in memory."""
    cat1 = _productcatalog_category(tenant_a, name="Cat 1", slug="cat-1")
    cat2 = _productcatalog_category(tenant_a, name="Cat 2", slug="cat-2", parent=cat1)

    # Bypass clean and manually create loop in instance references
    cat1.parent = cat2

    # Should not trigger RecursionError or infinite loop
    crumbs = cat1.get_breadcrumbs()
    assert len(crumbs) >= 1
    assert cat1.full_path != ""


def test_productcatalog_storecategory_meta_ordering_and_indexes(tenant_a):
    """Verify StoreCategory ordering by display_order, name and verify index configuration."""
    cat_b = _productcatalog_category(tenant_a, name="Beta", slug="beta", display_order=10)
    cat_a = _productcatalog_category(tenant_a, name="Alpha", slug="alpha", display_order=5)
    cat_c = _productcatalog_category(tenant_a, name="Gamma", slug="gamma", display_order=5)

    qs = list(StoreCategory.objects.filter(tenant=tenant_a))
    assert qs[0] == cat_a
    assert qs[1] == cat_c
    assert qs[2] == cat_b

    indexes = [idx.name for idx in StoreCategory._meta.indexes]
    assert "ecom_cat_tnt_act_ord_idx" in indexes


# ==============================================================================
# CatalogProduct Tests
# ==============================================================================

def test_productcatalog_product_defaults_and_fields(tenant_a):
    """Test CatalogProduct default values, status choices, and invariants."""
    prod = CatalogProduct.objects.create(
        tenant=tenant_a,
        name="Wireless Mouse",
        slug="wireless-mouse",
    )
    assert prod.status == "draft"
    assert prod.visibility == "storefront"
    assert prod.brand == ""
    assert prod.short_description == ""
    assert prod.description == ""
    assert prod.hero_image_url == ""
    assert prod.video_url == ""
    assert prod.is_featured is False
    assert prod.is_digital is False
    assert prod.published_at is None
    assert prod.created_at is not None
    assert prod.updated_at is not None
    assert prod.number.startswith("EPRD-")


def test_productcatalog_product_str_representation(tenant_a):
    """Test CatalogProduct __str__ returns 'name (number)' format."""
    prod = _productcatalog_product(tenant_a, name="Mechanical Keyboard", slug="mech-keyboard")
    assert str(prod) == f"Mechanical Keyboard ({prod.number})"


def test_productcatalog_product_autonumber_generation(tenant_a, tenant_b):
    """Test CatalogProduct auto-numbers generate with EPRD- prefix and tenant sequence."""
    p1 = _productcatalog_product(tenant_a, name="Monitor 1", slug="mon-1")
    p2 = _productcatalog_product(tenant_a, name="Monitor 2", slug="mon-2")
    pb = _productcatalog_product(tenant_b, name="Monitor B", slug="mon-b")

    assert p1.number.startswith("EPRD-")
    assert p2.number.startswith("EPRD-")
    assert pb.number.startswith("EPRD-")

    seq1 = int(p1.number.split("-")[-1])
    seq2 = int(p2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_productcatalog_product_unique_number_per_tenant(tenant_a, tenant_b):
    """Test unique constraint on (tenant, number) for CatalogProduct."""
    p1 = _productcatalog_product(tenant_a, name="Headphones A", slug="headphones-a")

    # Same number in tenant_b allowed
    p_other = _productcatalog_force_number(
        CatalogProduct,
        tenant=tenant_b,
        number=p1.number,
        name="Headphones B",
        slug="headphones-b",
    )
    assert p_other.number == p1.number

    # Duplicate number within tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_force_number(
                CatalogProduct,
                tenant=tenant_a,
                number=p1.number,
                name="Duplicate Headphones",
                slug="dup-headphones",
            )


def test_productcatalog_product_unique_slug_per_tenant(tenant_a, tenant_b):
    """Test unique constraint on (tenant, slug) for CatalogProduct."""
    _productcatalog_product(tenant_a, name="Webcam", slug="webcam-4k")

    # Same slug across tenants allowed
    pb = _productcatalog_product(tenant_b, name="Webcam B", slug="webcam-4k")
    assert pb.slug == "webcam-4k"

    # Same slug within tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_product(tenant_a, name="Webcam Duplicate", slug="webcam-4k")


def test_productcatalog_product_clean_cross_tenant_category(tenant_a, tenant_b):
    """Test clean() rejects primary_category belonging to another tenant."""
    cat_b = _productcatalog_category(tenant_b, name="Category B", slug="cat-b")
    prod = CatalogProduct(
        tenant=tenant_a,
        name="Product Cross Cat",
        slug="prod-cross-cat",
        primary_category=cat_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        prod.clean()
    assert "primary_category" in exc_info.value.message_dict


def test_productcatalog_product_clean_cross_tenant_item(tenant_a, tenant_b):
    """Test clean() rejects item belonging to another tenant."""
    item_b = _productcatalog_create_scm_item(tenant_b, sku="ITEM-B-01")
    prod = CatalogProduct(
        tenant=tenant_a,
        name="Product Cross Item",
        slug="prod-cross-item",
        item=item_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        prod.clean()
    assert "item" in exc_info.value.message_dict


def test_productcatalog_product_calculate_pim_completeness(tenant_a):
    """Test PIM completeness scoring rubric (0 to 100%)."""
    cat = _productcatalog_category(tenant_a, name="Peripherals", slug="peripherals")

    # Bare minimal product
    prod = CatalogProduct(tenant=tenant_a, name="", slug="")
    assert prod.calculate_pim_completeness() == 0

    # Name (+15) and Slug (+10) = 25
    prod.name = "Ergonomic Keyboard"
    prod.slug = "ergonomic-keyboard"
    assert prod.calculate_pim_completeness() == 25

    # Short description (+15) = 40
    prod.short_description = "Split layout keyboard."
    assert prod.calculate_pim_completeness() == 40

    # Full description (+15) = 55
    prod.description = "Detailed breakdown of the ergonomic features."
    assert prod.calculate_pim_completeness() == 55

    # Primary category (+15) = 70
    prod.primary_category = cat
    assert prod.calculate_pim_completeness() == 70

    # Hero image (+15) = 85
    prod.hero_image_url = "https://example.com/keyboard.jpg"
    assert prod.calculate_pim_completeness() == 85

    # Brand (+15) = 100
    prod.brand = "KeyWorks"
    assert prod.calculate_pim_completeness() == 100

    # Saving automatically updates pim_completeness column
    prod.save()
    assert prod.pim_completeness == 100


def test_productcatalog_product_save_published_at_stamping(tenant_a):
    """Test that setting status to 'active' stamps published_at automatically if null."""
    prod = _productcatalog_product(tenant_a, name="Draft Product", slug="draft-prod", status="draft")
    assert prod.published_at is None

    # Transition to active
    prod.status = "active"
    prod.save()
    assert prod.published_at is not None
    orig_published_at = prod.published_at

    # Subsequent save does not overwrite existing published_at
    prod.name = "Draft Product Updated"
    prod.save()
    assert prod.published_at == orig_published_at


def test_productcatalog_product_price_range_display(tenant_a, ecom_product_a):
    """Test price_range_display property for varying variant configurations."""
    # 1. No variants
    assert ecom_product_a.price_range_display == "No price set"

    # 2. Only inactive variant
    v_inactive = _productcatalog_variant(
        tenant_a,
        ecom_product_a,
        sku="INACT-01",
        price=Decimal("49.9900"),
        is_active=False,
    )
    assert ecom_product_a.price_range_display == "No price set"

    # 3. Single active variant
    v1 = _productcatalog_variant(
        tenant_a,
        ecom_product_a,
        sku="ACT-01",
        price=Decimal("49.9900"),
        is_active=True,
    )
    assert ecom_product_a.price_range_display == "$49.99"

    # 4. Two active variants with same price
    v2 = _productcatalog_variant(
        tenant_a,
        ecom_product_a,
        sku="ACT-02",
        price=Decimal("49.9900"),
        is_active=True,
    )
    assert ecom_product_a.price_range_display == "$49.99"

    # 5. Multiple active variants with different prices
    v3 = _productcatalog_variant(
        tenant_a,
        ecom_product_a,
        sku="ACT-03",
        price=Decimal("89.9900"),
        is_active=True,
    )
    assert ecom_product_a.price_range_display == "$49.99 - $89.99"


def test_productcatalog_product_variants_count_and_active_variants(tenant_a, ecom_product_a):
    """Test variant counts and active variants filtering."""
    v1 = _productcatalog_variant(tenant_a, ecom_product_a, sku="VCNT-01", is_active=True)
    v2 = _productcatalog_variant(tenant_a, ecom_product_a, sku="VCNT-02", is_active=False)

    assert ecom_product_a.total_variants_count == 2

    # Active variants check (both property check and relationship check)
    if hasattr(ecom_product_a, "active_variants"):
        res = list(ecom_product_a.active_variants)
        assert v1 in res
        assert v2 not in res
    else:
        active_list = list(ecom_product_a.variants.filter(is_active=True))
        assert v1 in active_list
        assert v2 not in active_list


def test_productcatalog_product_meta_indexes_and_ordering():
    """Verify CatalogProduct indexes and meta ordering configuration."""
    ordering = CatalogProduct._meta.ordering
    assert ordering == ["-created_at", "name"]

    indexes = [idx.name for idx in CatalogProduct._meta.indexes]
    assert "ecom_prd_tnt_stat_vis_idx" in indexes
    assert "ecom_prd_tnt_brand_idx" in indexes
    assert "ecom_prd_tnt_created_idx" in indexes


# ==============================================================================
# ProductVariant Tests
# ==============================================================================

def test_productcatalog_variant_defaults_and_fields(tenant_a, ecom_product_a):
    """Test ProductVariant default values, decimal precision, and invariants."""
    var = ProductVariant.objects.create(
        tenant=tenant_a,
        product=ecom_product_a,
        sku="TEST-DEFAULT-01",
        name="Default Option",
    )
    assert var.price == Decimal("0.0000")
    assert var.compare_at_price is None
    assert var.cost_price == Decimal("0.0000")
    assert var.weight_kg == Decimal("0.000")
    assert var.is_active is True
    assert var.sort_order == 0
    assert var.option_values == {}
    assert var.barcode == ""
    assert var.image_url == ""
    assert var.item is None
    assert var.number.startswith("PVR-")


def test_productcatalog_variant_str_representation(tenant_a, ecom_product_a):
    """Test ProductVariant __str__ format: 'sku · name ($price)'."""
    var = _productcatalog_variant(
        tenant_a,
        ecom_product_a,
        sku="SKU-100",
        name="Silver 256GB",
        price=Decimal("799.0000"),
    )
    assert str(var) == "SKU-100 · Silver 256GB ($799.00)"


def test_productcatalog_variant_autonumber_generation(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test ProductVariant auto-numbers generate with PVR- prefix and tenant sequence."""
    v1 = _productcatalog_variant(tenant_a, ecom_product_a, sku="PVR-SEQ-1")
    v2 = _productcatalog_variant(tenant_a, ecom_product_a, sku="PVR-SEQ-2")
    vb = _productcatalog_variant(tenant_b, ecom_product_b, sku="PVR-SEQ-B")

    assert v1.number.startswith("PVR-")
    assert v2.number.startswith("PVR-")
    assert vb.number.startswith("PVR-")

    seq1 = int(v1.number.split("-")[-1])
    seq2 = int(v2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_productcatalog_variant_unique_number_per_tenant(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test unique constraint on (tenant, number) for ProductVariant."""
    v1 = _productcatalog_variant(tenant_a, ecom_product_a, sku="VAR-NUM-1")

    # Same number in tenant_b allowed
    v_other = _productcatalog_force_number(
        ProductVariant,
        tenant=tenant_b,
        number=v1.number,
        product=ecom_product_b,
        sku="VAR-NUM-B",
        name="Var B",
    )
    assert v_other.number == v1.number

    # Duplicate number within tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_force_number(
                ProductVariant,
                tenant=tenant_a,
                number=v1.number,
                product=ecom_product_a,
                sku="VAR-NUM-DUP",
                name="Var Dup",
            )


def test_productcatalog_variant_unique_sku_per_tenant(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test unique constraint on (tenant, sku) for ProductVariant."""
    _productcatalog_variant(tenant_a, ecom_product_a, sku="UNIQUE-SKU-99")

    # Same SKU in tenant_b allowed
    vb = _productcatalog_variant(tenant_b, ecom_product_b, sku="UNIQUE-SKU-99")
    assert vb.sku == "UNIQUE-SKU-99"

    # Same SKU within tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_variant(tenant_a, ecom_product_a, sku="UNIQUE-SKU-99")


def test_productcatalog_variant_clean_cross_tenant_product(tenant_a, tenant_b, ecom_product_b):
    """Test clean() rejects parent product belonging to another tenant."""
    var = ProductVariant(
        tenant=tenant_a,
        product=ecom_product_b,
        sku="CROSS-PRD-SKU",
        name="Cross Prd Var",
    )
    with pytest.raises(ValidationError) as exc_info:
        var.clean()
    assert "product" in exc_info.value.message_dict


def test_productcatalog_variant_clean_cross_tenant_item(tenant_a, tenant_b, ecom_product_a):
    """Test clean() rejects fulfillment SCM item belonging to another tenant."""
    item_b = _productcatalog_create_scm_item(tenant_b, sku="ITEM-FULFILL-B")
    var = ProductVariant(
        tenant=tenant_a,
        product=ecom_product_a,
        sku="CROSS-ITEM-SKU",
        name="Cross Item Var",
        item=item_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        var.clean()
    assert "item" in exc_info.value.message_dict


def test_productcatalog_variant_clean_option_values_dict_validation(tenant_a, ecom_product_a):
    """Test clean() ensures option_values is a valid JSON dictionary."""
    var = ProductVariant(
        tenant=tenant_a,
        product=ecom_product_a,
        sku="BAD-OPTS-SKU",
        name="Bad Opts Var",
        option_values=["Color", "Red"],  # List instead of dict
    )
    with pytest.raises(ValidationError) as exc_info:
        var.clean()
    assert "option_values" in exc_info.value.message_dict


def test_productcatalog_variant_is_on_sale(tenant_a, ecom_product_a):
    """Test is_on_sale boolean property based on compare_at_price > price."""
    var = _productcatalog_variant(tenant_a, ecom_product_a, price=Decimal("100.0000"))

    # compare_at_price is None
    var.compare_at_price = None
    assert var.is_on_sale is False

    # compare_at_price lower or equal
    var.compare_at_price = Decimal("90.0000")
    assert var.is_on_sale is False

    var.compare_at_price = Decimal("100.0000")
    assert var.is_on_sale is False

    # compare_at_price higher
    var.compare_at_price = Decimal("129.9900")
    assert var.is_on_sale is True


def test_productcatalog_variant_options_summary(tenant_a, ecom_product_a):
    """Test options_summary formatted string or fallback to variant name."""
    var = _productcatalog_variant(
        tenant_a,
        ecom_product_a,
        name="Default Spec",
        option_values={"Size": "Large", "Color": "Midnight"},
    )
    assert var.options_summary == "Size: Large, Color: Midnight"

    # Empty option_values falls back to name
    var.option_values = {}
    assert var.options_summary == "Default Spec"


def test_productcatalog_variant_margin_pct(tenant_a, ecom_product_a):
    """Test margin_pct calculation and zero-guards."""
    # Price $100, cost $60 -> margin = 40.0%
    var = _productcatalog_variant(
        tenant_a,
        ecom_product_a,
        price=Decimal("100.0000"),
        cost_price=Decimal("60.0000"),
    )
    assert var.margin_pct == 40.0

    # Price $0 -> margin = 0.0
    var.price = Decimal("0.0000")
    assert var.margin_pct == 0.0

    # Cost $0 -> margin = 0.0
    var.price = Decimal("100.0000")
    var.cost_price = Decimal("0.0000")
    assert var.margin_pct == 0.0


def test_productcatalog_variant_meta_indexes_and_ordering():
    """Verify ProductVariant indexes and meta ordering."""
    assert ProductVariant._meta.ordering == ["sort_order", "sku"]
    indexes = [idx.name for idx in ProductVariant._meta.indexes]
    assert "ecom_pvr_tnt_prd_act_idx" in indexes
    assert "ecom_pvr_tnt_barc_idx" in indexes


# ==============================================================================
# ProductRelationship Tests
# ==============================================================================

def test_productcatalog_relationship_defaults_and_fields(tenant_a, ecom_product_a):
    """Test ProductRelationship default values and fields."""
    target_prod = _productcatalog_product(tenant_a, name="Gaming Mouse", slug="gaming-mouse")
    rel = ProductRelationship.objects.create(
        tenant=tenant_a,
        source_product=ecom_product_a,
        target_product=target_prod,
    )
    assert rel.relationship_type == "cross_sell"
    assert rel.discount_pct == Decimal("0.00")
    assert rel.is_active is True
    assert rel.sort_order == 0
    assert rel.notes == ""
    assert rel.number.startswith("PRL-")
    assert rel.created_at is not None
    assert rel.updated_at is not None


def test_productcatalog_relationship_str_representation(tenant_a, ecom_product_a):
    """Test ProductRelationship __str__ format: 'Source -> Target (Type)'."""
    target_prod = _productcatalog_product(tenant_a, name="Protective Sleeve", slug="protective-sleeve")
    rel = _productcatalog_relationship(
        tenant_a,
        source_product=ecom_product_a,
        target_product=target_prod,
        relationship_type="accessory",
    )
    assert str(rel) == f"{ecom_product_a.name} -> {target_prod.name} (Accessory)"


def test_productcatalog_relationship_autonumber_generation(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test ProductRelationship auto-numbers generate with PRL- prefix and tenant sequence."""
    t1 = _productcatalog_product(tenant_a, name="Target 1", slug="t-1")
    t2 = _productcatalog_product(tenant_a, name="Target 2", slug="t-2")
    tb = _productcatalog_product(tenant_b, name="Target B", slug="t-b")

    r1 = _productcatalog_relationship(tenant_a, ecom_product_a, t1)
    r2 = _productcatalog_relationship(tenant_a, ecom_product_a, t2)
    rb = _productcatalog_relationship(tenant_b, ecom_product_b, tb)

    assert r1.number.startswith("PRL-")
    assert r2.number.startswith("PRL-")
    assert rb.number.startswith("PRL-")

    seq1 = int(r1.number.split("-")[-1])
    seq2 = int(r2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_productcatalog_relationship_unique_number_per_tenant(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test unique constraint on (tenant, number) for ProductRelationship."""
    t1 = _productcatalog_product(tenant_a, name="Target Rel 1", slug="t-rel-1")
    tb = _productcatalog_product(tenant_b, name="Target Rel B", slug="t-rel-b")

    r1 = _productcatalog_relationship(tenant_a, ecom_product_a, t1)

    # Same number in tenant_b allowed
    r_other = _productcatalog_force_number(
        ProductRelationship,
        tenant=tenant_b,
        number=r1.number,
        source_product=ecom_product_b,
        target_product=tb,
        relationship_type="cross_sell",
    )
    assert r_other.number == r1.number

    # Duplicate number within tenant_a raises IntegrityError
    t2 = _productcatalog_product(tenant_a, name="Target Rel 2", slug="t-rel-2")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_force_number(
                ProductRelationship,
                tenant=tenant_a,
                number=r1.number,
                source_product=ecom_product_a,
                target_product=t2,
                relationship_type="cross_sell",
            )


def test_productcatalog_relationship_unique_source_target_type(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test unique constraint on (tenant, source_product, target_product, relationship_type)."""
    t1 = _productcatalog_product(tenant_a, name="Target P1", slug="tp-1")
    _productcatalog_relationship(tenant_a, ecom_product_a, t1, relationship_type="cross_sell")

    # Different relationship_type for same pair allowed
    r_upsell = _productcatalog_relationship(tenant_a, ecom_product_a, t1, relationship_type="up_sell")
    assert r_upsell.relationship_type == "up_sell"

    # Same pair and type in tenant_b allowed
    tb_target = _productcatalog_product(tenant_b, name="Target PB", slug="tp-b")
    rb = _productcatalog_relationship(tenant_b, ecom_product_b, tb_target, relationship_type="cross_sell")
    assert rb.relationship_type == "cross_sell"

    # Duplicate in tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _productcatalog_relationship(tenant_a, ecom_product_a, t1, relationship_type="cross_sell")


def test_productcatalog_relationship_clean_self_relationship(tenant_a, ecom_product_a):
    """Test clean() raises ValidationError if source_product equals target_product."""
    rel = ProductRelationship(
        tenant=tenant_a,
        source_product=ecom_product_a,
        target_product=ecom_product_a,
        relationship_type="cross_sell",
    )
    with pytest.raises(ValidationError) as exc_info:
        rel.clean()
    assert "target_product" in exc_info.value.message_dict
    assert "cannot have a merchandising relationship with itself" in exc_info.value.message_dict["target_product"][0]


def test_productcatalog_relationship_clean_cross_tenant_source(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test clean() raises ValidationError if source_product belongs to another workspace."""
    t1 = _productcatalog_product(tenant_a, name="Target Clean 1", slug="t-clean-1")
    rel = ProductRelationship(
        tenant=tenant_a,
        source_product=ecom_product_b,  # tenant_b product
        target_product=t1,
        relationship_type="cross_sell",
    )
    with pytest.raises(ValidationError) as exc_info:
        rel.clean()
    assert "source_product" in exc_info.value.message_dict


def test_productcatalog_relationship_clean_cross_tenant_target(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """Test clean() raises ValidationError if target_product belongs to another workspace."""
    rel = ProductRelationship(
        tenant=tenant_a,
        source_product=ecom_product_a,
        target_product=ecom_product_b,  # tenant_b product
        relationship_type="cross_sell",
    )
    with pytest.raises(ValidationError) as exc_info:
        rel.clean()
    assert "target_product" in exc_info.value.message_dict


def test_productcatalog_relationship_meta_indexes_and_ordering(tenant_a, ecom_product_a):
    """Verify ProductRelationship indexes and meta ordering."""
    p_z = _productcatalog_product(tenant_a, name="Zebra", slug="zebra")
    p_a = _productcatalog_product(tenant_a, name="Antelope", slug="antelope")

    r1 = _productcatalog_relationship(tenant_a, ecom_product_a, p_z, sort_order=10)
    r2 = _productcatalog_relationship(tenant_a, ecom_product_a, p_a, sort_order=5)

    qs = list(ProductRelationship.objects.filter(tenant=tenant_a, source_product=ecom_product_a))
    assert qs[0] == r2
    assert qs[1] == r1

    indexes = [idx.name for idx in ProductRelationship._meta.indexes]
    assert "ecom_prl_tnt_src_type_idx" in indexes
