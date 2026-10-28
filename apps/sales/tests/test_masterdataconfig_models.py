"""Unit tests for Sales 8.19 Master Data & Configuration models.

Subslug: masterdataconfig
Prefix for test functions: test_masterdataconfig_*
Prefix for helper functions: _masterdataconfig_*

Covers:
1. SalesPriceBookEntry:
   - Auto-numbering prefix 'PBE-' and sequence per tenant.
   - String representation __str__.
   - Field defaults, min_quantity validator, and pricing_model choices.
   - Model-level clean() validations:
     - Floor price cannot exceed list price.
     - Expiration date cannot precede effective start date.
     - Volume tier breaks must be a JSON array.
     - Cross-tenant rejection for price_book, product, and item.
   - Meta constraints:
     - Unique (tenant, number)
     - Unique (tenant, price_book, product, currency_code)

2. SalesCustomEntityDefinition:
   - Auto-numbering prefix 'SCO-' and sequence per tenant.
   - String representation __str__.
   - Field defaults, target_model choices, and field_type choices.
   - Model-level clean() validations:
     - Entity code lowercase/strip normalization.
     - Formula expression required for field_type='formula'.
     - Lookup target model required for lookup/master_detail.
     - Picklist options must be a JSON array.
     - Regex pattern validation for validation_rule.
   - Meta constraints:
     - Unique (tenant, number)
     - Unique (tenant, target_model, entity_code)

3. SalesMethodology:
   - Auto-numbering prefix 'SMD-' and sequence per tenant.
   - String representation __str__.
   - Field defaults, framework choices, and min_passing_score validators.
   - Model-level clean() validations:
     - Qualification criteria must be a JSON array.
     - Cross-tenant rejection for pipeline and gating_stage.
     - Stage must belong to the selected pipeline.
   - Meta constraints:
     - Unique (tenant, number)
     - Unique (tenant, name)

4. SalesRegionalSetting:
   - Auto-numbering prefix 'SRG-' and sequence per tenant.
   - String representation __str__.
   - Field defaults and choices (region_code, date_format, number_format, tax_display_mode, compliance_framework).
   - Cooling-off days MaxValueValidator(365).
   - Model-level clean() validations:
     - Primary currency uppercase/strip normalization.
     - Supported currencies must be a JSON array.
     - Default configuration must be active.
   - Custom save() logic:
     - Single active default regional profile scoping within the active tenant.
   - Meta constraints:
     - Unique (tenant, number)
     - Unique (tenant, region_code)
"""
from decimal import Decimal
import re
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.crm.models import PriceBook, Product
from apps.sales.models import (
    Pipeline,
    PipelineStage,
    SalesCustomEntityDefinition,
    SalesMethodology,
    SalesPriceBookEntry,
    SalesRegionalSetting,
)
from apps.scm.models import Item

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_masterdataconfig_*)
# ==============================================================================

def _masterdataconfig_price_book(tenant, name="Global Standard Price Book", currency_code="USD", **overrides):
    defaults = {
        "tenant": tenant,
        "name": name,
        "currency_code": currency_code,
        "region": "global",
        "tier": "standard",
        "price_adjustment_pct": Decimal("0.00"),
        "is_default": False,
        "is_active": True,
        "description": "Standard pricing catalog.",
    }
    defaults.update(overrides)
    return PriceBook.objects.create(**defaults)


def _masterdataconfig_product(tenant, name="Enterprise Platform License", sku=None, **overrides):
    if sku is None:
        sku = f"SKU-{timezone.now().strftime('%f')[:6]}"
    defaults = {
        "tenant": tenant,
        "name": name,
        "sku": sku,
        "product_type": "subscription",
        "unit_price": Decimal("1200.00"),
        "cost": Decimal("400.00"),
        "tax_pct": Decimal("0.00"),
        "is_active": True,
        "description": "Enterprise cloud platform license.",
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


def _masterdataconfig_item(tenant, sku=None, name="Hardware Appliance", **overrides):
    if sku is None:
        sku = f"ITM-{timezone.now().strftime('%f')[:6]}"
    defaults = {
        "tenant": tenant,
        "sku": sku,
        "name": name,
        "item_type": "stock",
        "tracking": "none",
        "costing_method": "weighted_avg",
    }
    defaults.update(overrides)
    return Item.objects.create(**defaults)


def _masterdataconfig_pipeline(tenant, name="Enterprise Sales Pipeline", **overrides):
    defaults = {
        "tenant": tenant,
        "name": name,
        "is_active": True,
        "is_default": False,
    }
    defaults.update(overrides)
    return Pipeline.objects.create(**defaults)


def _masterdataconfig_stage(tenant, pipeline, name="Technical Validation", code=None, **overrides):
    if code is None:
        code = f"stage_{timezone.now().strftime('%f')[:6]}"
    defaults = {
        "tenant": tenant,
        "pipeline": pipeline,
        "name": name,
        "code": code,
        "sequence": 10,
        "stage_kind": "open",
        "crm_stage_key": "qualification",
        "probability": 25,
        "forecast_category": "pipeline",
    }
    defaults.update(overrides)
    return PipelineStage.objects.create(**defaults)


def _masterdataconfig_price_book_entry(tenant, price_book=None, product=None, **overrides):
    if price_book is None:
        price_book = _masterdataconfig_price_book(tenant)
    if product is None:
        product = _masterdataconfig_product(tenant)
    defaults = {
        "tenant": tenant,
        "price_book": price_book,
        "product": product,
        "sku_code": product.sku,
        "currency_code": "USD",
        "list_price": Decimal("1200.00"),
        "floor_price": Decimal("900.00"),
        "pricing_model": "flat",
        "min_quantity": Decimal("1.00"),
        "volume_tier_breaks": [{"min_qty": 10, "discount_pct": 5.0, "unit_price": 1140.0}],
        "is_active": True,
        "notes": "Standard catalog entry.",
    }
    defaults.update(overrides)
    return SalesPriceBookEntry.objects.create(**defaults)


def _masterdataconfig_custom_entity(tenant, name="Deal Authority Level", entity_code="deal_auth_lvl", **overrides):
    defaults = {
        "tenant": tenant,
        "name": name,
        "entity_code": entity_code,
        "target_model": "opportunity",
        "field_type": "picklist",
        "is_required": False,
        "formula_expression": "",
        "lookup_target_model": "",
        "picklist_options": ["VP", "Director", "C-Level"],
        "validation_rule": "^(VP|Director|C-Level)$",
        "display_order": 10,
        "is_active": True,
        "description": "Executive sign-off authority level required for opportunity closure.",
    }
    defaults.update(overrides)
    return SalesCustomEntityDefinition.objects.create(**defaults)


def _masterdataconfig_methodology(tenant, name="MEDDPICC Enterprise Framework", framework="meddpicc", **overrides):
    defaults = {
        "tenant": tenant,
        "name": name,
        "framework": framework,
        "min_passing_score": 75,
        "is_mandatory_gate": True,
        "qualification_criteria": [
            {"key": "metrics", "label": "Quantifiable business impact identified", "weight": 20, "is_required": True},
            {"key": "economic_buyer", "label": "Direct sponsor with budget authority", "weight": 20, "is_required": True},
        ],
        "coaching_guidelines": "Ensure champion is tested before scheduling final presentation.",
        "is_active": True,
    }
    defaults.update(overrides)
    return SalesMethodology.objects.create(**defaults)


def _masterdataconfig_regional_setting(tenant, name="North America Commercial Terms", region_code="NA", **overrides):
    defaults = {
        "tenant": tenant,
        "name": name,
        "region_code": region_code,
        "primary_currency": "USD",
        "supported_currencies": ["USD", "CAD"],
        "date_format": "MM/DD/YYYY",
        "number_format": "1,234.56",
        "tax_display_mode": "tax_exclusive",
        "default_quote_terms": "Net 30 days upon invoice delivery.",
        "statutory_disclaimer": "Subject to standard regional sales warranties.",
        "compliance_framework": "sox_revenue",
        "cooling_off_days": 14,
        "is_default": False,
        "is_active": True,
    }
    defaults.update(overrides)
    return SalesRegionalSetting.objects.create(**defaults)


def _masterdataconfig_make_duplicate_entry(tenant, price_book, product, number):
    obj = SalesPriceBookEntry(
        tenant=tenant,
        price_book=price_book,
        product=product,
        list_price=Decimal("100.00"),
        floor_price=Decimal("50.00"),
    )
    obj.number = number
    return obj


def _masterdataconfig_make_duplicate_custom_entity(tenant, number):
    obj = SalesCustomEntityDefinition(
        tenant=tenant,
        name="Dup Test",
        entity_code="dup_test",
        target_model="opportunity",
    )
    obj.number = number
    return obj


def _masterdataconfig_make_duplicate_methodology(tenant, number):
    obj = SalesMethodology(
        tenant=tenant,
        name="Dup Meth Test",
        framework="meddic",
    )
    obj.number = number
    return obj


def _masterdataconfig_make_duplicate_regional_setting(tenant, number):
    obj = SalesRegionalSetting(
        tenant=tenant,
        name="Dup Reg Test",
        region_code="APAC",
    )
    obj.number = number
    return obj


# ==============================================================================
# 1. SalesPriceBookEntry Tests
# ==============================================================================

def test_masterdataconfig_pbe_number_prefix_and_tenant_sequence(tenant_a, tenant_b):
    """Auto-numbering starts with PBE- and sequence is isolated per tenant."""
    assert SalesPriceBookEntry.NUMBER_PREFIX == "PBE"

    pb_a = _masterdataconfig_price_book(tenant_a, name="Price Book A")
    prod_a1 = _masterdataconfig_product(tenant_a, name="Prod A1", sku="SKU-A1")
    prod_a2 = _masterdataconfig_product(tenant_a, name="Prod A2", sku="SKU-A2")

    pb_b = _masterdataconfig_price_book(tenant_b, name="Price Book B")
    prod_b1 = _masterdataconfig_product(tenant_b, name="Prod B1", sku="SKU-B1")

    pbe_a1 = _masterdataconfig_price_book_entry(tenant_a, price_book=pb_a, product=prod_a1)
    pbe_a2 = _masterdataconfig_price_book_entry(tenant_a, price_book=pb_a, product=prod_a2)
    pbe_b1 = _masterdataconfig_price_book_entry(tenant_b, price_book=pb_b, product=prod_b1)

    assert re.match(r"^PBE-\d{5}$", pbe_a1.number)
    assert re.match(r"^PBE-\d{5}$", pbe_a2.number)
    assert re.match(r"^PBE-\d{5}$", pbe_b1.number)

    assert pbe_a1.number == "PBE-00001"
    assert pbe_a2.number == "PBE-00002"
    assert pbe_b1.number == "PBE-00001"

    # Re-saving preserves number
    orig_num = pbe_a1.number
    pbe_a1.notes = "Updated notes."
    pbe_a1.save()
    pbe_a1.refresh_from_db()
    assert pbe_a1.number == orig_num


def test_masterdataconfig_pbe_str_representation(tenant_a):
    """String representation formats number, price book, product, currency and list price."""
    pb = _masterdataconfig_price_book(tenant_a, name="Corporate Catalog")
    prod = _masterdataconfig_product(tenant_a, name="CRM Pro Suite", sku="CRM-PRO")
    pbe = _masterdataconfig_price_book_entry(
        tenant_a,
        price_book=pb,
        product=prod,
        currency_code="USD",
        list_price=Decimal("1500.00"),
    )
    expected = f"{pbe.number} · Corporate Catalog - CRM Pro Suite (USD 1500.00)"
    assert str(pbe) == expected


def test_masterdataconfig_pbe_field_defaults_and_choices(tenant_a):
    """Verify default values, min_quantity validator, and choice definitions."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)
    pbe = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("100.00"),
    )
    assert pbe.sku_code == ""
    assert pbe.currency_code == "USD"
    assert pbe.floor_price == Decimal("0.00")
    assert pbe.pricing_model == "flat"
    assert pbe.min_quantity == Decimal("1.00")
    assert pbe.volume_tier_breaks == []
    assert pbe.valid_from is None
    assert pbe.valid_to is None
    assert pbe.is_active is True
    assert pbe.notes == ""

    expected_choices = [
        ("flat", "Flat Unit Price"),
        ("tier_volume", "Volume Tier Discount"),
        ("tier_graduated", "Graduated / Bracket Pricing"),
        ("cost_markup", "Cost-Plus Markup"),
    ]
    assert SalesPriceBookEntry.PRICING_MODEL_CHOICES == expected_choices


def test_masterdataconfig_pbe_floor_price_cannot_exceed_list_price(tenant_a):
    """clean() rejects floor price strictly greater than list price."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    # Floor exceeds list price
    pbe_invalid = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("100.00"),
        floor_price=Decimal("120.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe_invalid.clean()
    assert "floor_price" in exc_info.value.message_dict
    assert "Floor price cannot exceed list price." in exc_info.value.message_dict["floor_price"]

    # Floor equals list price -> valid
    pbe_equal = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("100.00"),
        floor_price=Decimal("100.00"),
    )
    pbe_equal.clean()

    # Floor below list price -> valid
    pbe_valid = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("100.00"),
        floor_price=Decimal("80.00"),
    )
    pbe_valid.clean()


def test_masterdataconfig_pbe_validity_dates_order_validation(tenant_a):
    """clean() ensures valid_to does not precede valid_from."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)
    today = timezone.localdate()

    pbe = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("100.00"),
        valid_from=today,
        valid_to=today - timezone.timedelta(days=5),
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe.clean()
    assert "valid_to" in exc_info.value.message_dict
    assert "Expiration date cannot precede effective start date." in exc_info.value.message_dict["valid_to"]

    # Valid dates
    pbe.valid_to = today + timezone.timedelta(days=30)
    pbe.clean()


def test_masterdataconfig_pbe_volume_tier_breaks_must_be_list(tenant_a):
    """clean() validates that volume_tier_breaks is a JSON array (list)."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    pbe = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("100.00"),
        volume_tier_breaks={"tier_1": 10},  # Dict instead of list
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe.clean()
    assert "volume_tier_breaks" in exc_info.value.message_dict

    # Valid list
    pbe.volume_tier_breaks = [{"min_qty": 10, "discount_pct": 5.0}]
    pbe.clean()


def test_masterdataconfig_pbe_cross_tenant_isolation_price_book(tenant_a, tenant_b):
    """clean() rejects price_book belonging to a different tenant."""
    pb_b = _masterdataconfig_price_book(tenant_b, name="Price Book B")
    prod_a = _masterdataconfig_product(tenant_a, name="Product A")

    pbe = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb_b,
        product=prod_a,
        list_price=Decimal("100.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe.clean()
    assert "price_book" in exc_info.value.message_dict
    assert "Price book must belong to the active workspace." in exc_info.value.message_dict["price_book"]


def test_masterdataconfig_pbe_cross_tenant_isolation_product(tenant_a, tenant_b):
    """clean() rejects product belonging to a different tenant."""
    pb_a = _masterdataconfig_price_book(tenant_a, name="Price Book A")
    prod_b = _masterdataconfig_product(tenant_b, name="Product B")

    pbe = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb_a,
        product=prod_b,
        list_price=Decimal("100.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe.clean()
    assert "product" in exc_info.value.message_dict
    assert "Product must belong to the active workspace." in exc_info.value.message_dict["product"]


def test_masterdataconfig_pbe_cross_tenant_isolation_item(tenant_a, tenant_b):
    """clean() rejects inventory item belonging to a different tenant."""
    pb_a = _masterdataconfig_price_book(tenant_a, name="Price Book A")
    prod_a = _masterdataconfig_product(tenant_a, name="Product A")
    item_b = _masterdataconfig_item(tenant_b, name="Item B")

    pbe = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb_a,
        product=prod_a,
        item=item_b,
        list_price=Decimal("100.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe.clean()
    assert "item" in exc_info.value.message_dict
    assert "Inventory item must belong to the active workspace." in exc_info.value.message_dict["item"]

    # Same tenant item succeeds
    item_a = _masterdataconfig_item(tenant_a, name="Item A")
    pbe.item = item_a
    pbe.clean()


def test_masterdataconfig_pbe_min_value_validators(tenant_a):
    """full_clean() validates min values for list_price, floor_price, min_quantity."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    # Negative list price
    pbe1 = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("-10.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe1.full_clean()
    assert "list_price" in exc_info.value.message_dict

    # Zero min_quantity (MinValueValidator is 0.01)
    pbe2 = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        list_price=Decimal("10.00"),
        min_quantity=Decimal("0.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        pbe2.full_clean()
    assert "min_quantity" in exc_info.value.message_dict


def test_masterdataconfig_pbe_unique_constraints(tenant_a, tenant_b):
    """Enforce sales_pbe_tenant_num_uniq and sales_pbe_bk_prd_cur_uniq."""
    pb_a = _masterdataconfig_price_book(tenant_a, name="PB A")
    prod_a = _masterdataconfig_product(tenant_a, name="Prod A")

    entry1 = _masterdataconfig_price_book_entry(
        tenant_a,
        price_book=pb_a,
        product=prod_a,
        currency_code="USD",
    )
    assert entry1.number == "PBE-00001"

    # Duplicate number on same tenant raises IntegrityError
    dup_num = _masterdataconfig_make_duplicate_entry(tenant_a, pb_a, prod_a, "PBE-00001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_num.save()

    # Duplicate (tenant, price_book, product, currency_code) raises IntegrityError
    dup_entry = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb_a,
        product=prod_a,
        currency_code="USD",
        list_price=Decimal("200.00"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_entry.save()

    # Different currency code on same product succeeds
    eur_entry = _masterdataconfig_price_book_entry(
        tenant_a,
        price_book=pb_a,
        product=prod_a,
        currency_code="EUR",
    )
    assert eur_entry.pk is not None

    # Same product/currency on tenant_b succeeds
    pb_b = _masterdataconfig_price_book(tenant_b, name="PB B")
    prod_b = _masterdataconfig_product(tenant_b, name="Prod B")
    b_entry = _masterdataconfig_price_book_entry(
        tenant_b,
        price_book=pb_b,
        product=prod_b,
        currency_code="USD",
    )
    assert b_entry.pk is not None


# ==============================================================================
# 2. SalesCustomEntityDefinition Tests
# ==============================================================================

def test_masterdataconfig_sco_number_prefix_and_tenant_sequence(tenant_a, tenant_b):
    """Auto-numbering starts with SCO- and sequence is isolated per tenant."""
    assert SalesCustomEntityDefinition.NUMBER_PREFIX == "SCO"

    sco_a1 = _masterdataconfig_custom_entity(tenant_a, name="Custom A1", entity_code="c_a1")
    sco_a2 = _masterdataconfig_custom_entity(tenant_a, name="Custom A2", entity_code="c_a2")
    sco_b1 = _masterdataconfig_custom_entity(tenant_b, name="Custom B1", entity_code="c_b1")

    assert re.match(r"^SCO-\d{5}$", sco_a1.number)
    assert re.match(r"^SCO-\d{5}$", sco_a2.number)
    assert re.match(r"^SCO-\d{5}$", sco_b1.number)

    assert sco_a1.number == "SCO-00001"
    assert sco_a2.number == "SCO-00002"
    assert sco_b1.number == "SCO-00001"

    # Re-saving preserves number
    orig_num = sco_a1.number
    sco_a1.description = "Updated description."
    sco_a1.save()
    sco_a1.refresh_from_db()
    assert sco_a1.number == orig_num


def test_masterdataconfig_sco_str_representation(tenant_a):
    """String representation formats number, target model display, name, and entity code."""
    sco = _masterdataconfig_custom_entity(
        tenant_a,
        name="Contract Tier",
        entity_code="contract_tier_c",
        target_model="customer_contract",
    )
    expected = f"{sco.number} · Customer Contract (sales.CustomerContract) - Contract Tier (contract_tier_c)"
    assert str(sco) == expected


def test_masterdataconfig_sco_field_defaults_and_choices(tenant_a):
    """Verify default values and choices for SalesCustomEntityDefinition."""
    sco = SalesCustomEntityDefinition(tenant=tenant_a, name="Default Field", entity_code="default_field")
    assert sco.target_model == "opportunity"
    assert sco.field_type == "text"
    assert sco.is_required is False
    assert sco.formula_expression == ""
    assert sco.lookup_target_model == ""
    assert sco.picklist_options == []
    assert sco.validation_rule == ""
    assert sco.display_order == 10
    assert sco.is_active is True
    assert sco.description == ""

    assert len(SalesCustomEntityDefinition.TARGET_MODEL_CHOICES) == 6
    assert len(SalesCustomEntityDefinition.FIELD_TYPE_CHOICES) == 12


def test_masterdataconfig_sco_entity_code_normalization(tenant_a):
    """clean() strips whitespace and converts entity_code to lowercase."""
    sco = SalesCustomEntityDefinition(
        tenant=tenant_a,
        name="Field Code Test",
        entity_code="  DEAL_MARGIN_PCT_C  ",
    )
    sco.clean()
    assert sco.entity_code == "deal_margin_pct_c"


def test_masterdataconfig_sco_formula_expression_required(tenant_a):
    """clean() requires formula_expression when field_type='formula'."""
    sco = SalesCustomEntityDefinition(
        tenant=tenant_a,
        name="Formula Field",
        entity_code="margin_formula",
        field_type="formula",
        formula_expression="",
    )
    with pytest.raises(ValidationError) as exc_info:
        sco.clean()
    assert "formula_expression" in exc_info.value.message_dict
    assert "Formula expression is required when field type is 'Formula'." in exc_info.value.message_dict["formula_expression"]

    # Valid formula
    sco.formula_expression = "(amount - total_cost) / amount * 100"
    sco.clean()


def test_masterdataconfig_sco_lookup_target_model_required(tenant_a):
    """clean() requires lookup_target_model for lookup and master_detail fields."""
    for ftype in ["lookup", "master_detail"]:
        sco = SalesCustomEntityDefinition(
            tenant=tenant_a,
            name="Relationship Field",
            entity_code=f"rel_{ftype}",
            field_type=ftype,
            lookup_target_model="",
        )
        with pytest.raises(ValidationError) as exc_info:
            sco.clean()
        assert "lookup_target_model" in exc_info.value.message_dict
        assert "Lookup target model is required for relationship fields." in exc_info.value.message_dict["lookup_target_model"]

        # Valid target
        sco.lookup_target_model = "core.Party"
        sco.clean()


def test_masterdataconfig_sco_picklist_options_validation(tenant_a):
    """clean() validates that picklist_options is a JSON array (list)."""
    for ftype in ["picklist", "multi_picklist"]:
        sco = SalesCustomEntityDefinition(
            tenant=tenant_a,
            name="Options Field",
            entity_code=f"opts_{ftype}",
            field_type=ftype,
            picklist_options={"invalid": "dict"},
        )
        with pytest.raises(ValidationError) as exc_info:
            sco.clean()
        assert "picklist_options" in exc_info.value.message_dict

        # Valid list
        sco.picklist_options = ["Tier 1", "Tier 2", "Tier 3"]
        sco.clean()


def test_masterdataconfig_sco_regex_validation_rule(tenant_a):
    """clean() validates that validation_rule compiles as a valid regular expression."""
    # Invalid regex (unmatched bracket)
    sco_invalid = SalesCustomEntityDefinition(
        tenant=tenant_a,
        name="Regex Test",
        entity_code="regex_test",
        validation_rule="[A-Z0-9-",
    )
    with pytest.raises(ValidationError) as exc_info:
        sco_invalid.clean()
    assert "validation_rule" in exc_info.value.message_dict
    assert "Invalid regular expression pattern" in exc_info.value.message_dict["validation_rule"][0]

    # Valid regex
    sco_valid = SalesCustomEntityDefinition(
        tenant=tenant_a,
        name="Regex Test Valid",
        entity_code="regex_test_valid",
        validation_rule=r"^[A-Z]{3}-\d{4}$",
    )
    sco_valid.clean()

    # Empty regex passes
    sco_empty = SalesCustomEntityDefinition(
        tenant=tenant_a,
        name="Regex Empty",
        entity_code="regex_empty",
        validation_rule="",
    )
    sco_empty.clean()


def test_masterdataconfig_sco_unique_constraints(tenant_a, tenant_b):
    """Enforce sales_sco_tenant_num_uniq and sales_sco_tnt_tgt_code_uniq."""
    sco1 = _masterdataconfig_custom_entity(
        tenant_a,
        name="Risk Score",
        entity_code="risk_score",
        target_model="opportunity",
    )
    assert sco1.number == "SCO-00001"

    # Duplicate number on same tenant raises IntegrityError
    dup_num = _masterdataconfig_make_duplicate_custom_entity(tenant_a, "SCO-00001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_num.save()

    # Duplicate (tenant, target_model, entity_code) raises IntegrityError
    dup_sco = SalesCustomEntityDefinition(
        tenant=tenant_a,
        name="Risk Score Copy",
        entity_code="risk_score",
        target_model="opportunity",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_sco.save()

    # Same entity_code on different target_model succeeds
    diff_target = _masterdataconfig_custom_entity(
        tenant_a,
        name="Contract Risk Score",
        entity_code="risk_score",
        target_model="customer_contract",
    )
    assert diff_target.pk is not None

    # Same entity_code and target_model on tenant_b succeeds
    b_sco = _masterdataconfig_custom_entity(
        tenant_b,
        name="Risk Score B",
        entity_code="risk_score",
        target_model="opportunity",
    )
    assert b_sco.pk is not None


# ==============================================================================
# 3. SalesMethodology Tests
# ==============================================================================

def test_masterdataconfig_smd_number_prefix_and_tenant_sequence(tenant_a, tenant_b):
    """Auto-numbering starts with SMD- and sequence is isolated per tenant."""
    assert SalesMethodology.NUMBER_PREFIX == "SMD"

    smd_a1 = _masterdataconfig_methodology(tenant_a, name="Methodology A1")
    smd_a2 = _masterdataconfig_methodology(tenant_a, name="Methodology A2")
    smd_b1 = _masterdataconfig_methodology(tenant_b, name="Methodology B1")

    assert re.match(r"^SMD-\d{5}$", smd_a1.number)
    assert re.match(r"^SMD-\d{5}$", smd_a2.number)
    assert re.match(r"^SMD-\d{5}$", smd_b1.number)

    assert smd_a1.number == "SMD-00001"
    assert smd_a2.number == "SMD-00002"
    assert smd_b1.number == "SMD-00001"

    # Re-saving preserves number
    orig_num = smd_a1.number
    smd_a1.coaching_guidelines = "Updated guidelines."
    smd_a1.save()
    smd_a1.refresh_from_db()
    assert smd_a1.number == orig_num


def test_masterdataconfig_smd_str_representation(tenant_a):
    """String representation formats number, name, and framework display."""
    smd = _masterdataconfig_methodology(
        tenant_a,
        name="Strategic Value Gating",
        framework="spin",
    )
    expected = f"{smd.number} · Strategic Value Gating (SPIN (Situation, Problem, Implication, Need-Payoff))"
    assert str(smd) == expected


def test_masterdataconfig_smd_field_defaults_and_choices(tenant_a):
    """Verify default values and choices for SalesMethodology."""
    smd = SalesMethodology(tenant=tenant_a, name="Default Methodology")
    assert smd.framework == "meddic"
    assert smd.pipeline is None
    assert smd.gating_stage is None
    assert smd.min_passing_score == 70
    assert smd.is_mandatory_gate is False
    assert smd.qualification_criteria == []
    assert smd.coaching_guidelines == ""
    assert smd.is_active is True

    assert len(SalesMethodology.FRAMEWORK_CHOICES) == 8


def test_masterdataconfig_smd_qualification_criteria_must_be_list(tenant_a):
    """clean() validates that qualification_criteria is a JSON array (list)."""
    smd = SalesMethodology(
        tenant=tenant_a,
        name="Criteria Test",
        qualification_criteria={"metric": "fail"},  # Dict instead of list
    )
    with pytest.raises(ValidationError) as exc_info:
        smd.clean()
    assert "qualification_criteria" in exc_info.value.message_dict

    # Valid list
    smd.qualification_criteria = [{"key": "metrics", "label": "Metrics", "weight": 25}]
    smd.clean()


def test_masterdataconfig_smd_cross_tenant_isolation_pipeline(tenant_a, tenant_b):
    """clean() rejects pipeline belonging to a different tenant."""
    pipe_b = _masterdataconfig_pipeline(tenant_b, name="Pipeline B")
    smd = SalesMethodology(
        tenant=tenant_a,
        name="Cross Tenant Pipe",
        pipeline=pipe_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        smd.clean()
    assert "pipeline" in exc_info.value.message_dict
    assert "Pipeline must belong to the active workspace." in exc_info.value.message_dict["pipeline"]


def test_masterdataconfig_smd_cross_tenant_isolation_stage(tenant_a, tenant_b):
    """clean() rejects gating_stage belonging to a different tenant."""
    pipe_b = _masterdataconfig_pipeline(tenant_b, name="Pipeline B")
    stage_b = _masterdataconfig_stage(tenant_b, pipe_b, name="Stage B")

    smd = SalesMethodology(
        tenant=tenant_a,
        name="Cross Tenant Stage",
        gating_stage=stage_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        smd.clean()
    assert "gating_stage" in exc_info.value.message_dict
    assert "Gating stage must belong to the active workspace." in exc_info.value.message_dict["gating_stage"]


def test_masterdataconfig_smd_stage_must_belong_to_selected_pipeline(tenant_a):
    """clean() ensures gating stage belongs to the selected pipeline."""
    pipe1 = _masterdataconfig_pipeline(tenant_a, name="Enterprise Pipeline 1")
    pipe2 = _masterdataconfig_pipeline(tenant_a, name="Enterprise Pipeline 2")
    stage2 = _masterdataconfig_stage(tenant_a, pipe2, name="Proposal Stage 2")

    smd = SalesMethodology(
        tenant=tenant_a,
        name="Stage Mismatch Test",
        pipeline=pipe1,
        gating_stage=stage2,
    )
    with pytest.raises(ValidationError) as exc_info:
        smd.clean()
    assert "gating_stage" in exc_info.value.message_dict
    assert "Gating stage must belong to the selected pipeline." in exc_info.value.message_dict["gating_stage"]

    # Matching pipeline and stage succeeds
    stage1 = _masterdataconfig_stage(tenant_a, pipe1, name="Proposal Stage 1")
    smd.gating_stage = stage1
    smd.clean()


def test_masterdataconfig_smd_min_passing_score_validators(tenant_a):
    """full_clean() validates min_passing_score bounds (0 to 100)."""
    # Exceeds 100
    smd_high = SalesMethodology(
        tenant=tenant_a,
        name="High Score Test",
        min_passing_score=105,
    )
    with pytest.raises(ValidationError) as exc_info:
        smd_high.full_clean()
    assert "min_passing_score" in exc_info.value.message_dict

    # Negative score (field is PositiveIntegerField + MinValueValidator(0))
    smd_neg = SalesMethodology(
        tenant=tenant_a,
        name="Neg Score Test",
        min_passing_score=-5,
    )
    with pytest.raises(ValidationError) as exc_info:
        smd_neg.full_clean()
    assert "min_passing_score" in exc_info.value.message_dict

    # Edge cases 0 and 100 are valid
    smd_zero = SalesMethodology(tenant=tenant_a, name="Zero Score", min_passing_score=0)
    smd_zero.full_clean()

    smd_hundred = SalesMethodology(tenant=tenant_a, name="Hundred Score", min_passing_score=100)
    smd_hundred.full_clean()


def test_masterdataconfig_smd_unique_constraints(tenant_a, tenant_b):
    """Enforce sales_smd_tenant_num_uniq and sales_smd_tnt_name_uniq."""
    smd1 = _masterdataconfig_methodology(tenant_a, name="Enterprise MEDDIC Gate")
    assert smd1.number == "SMD-00001"

    # Duplicate number on same tenant raises IntegrityError
    dup_num = _masterdataconfig_make_duplicate_methodology(tenant_a, "SMD-00001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_num.save()

    # Duplicate (tenant, name) raises IntegrityError
    dup_smd = SalesMethodology(tenant=tenant_a, name="Enterprise MEDDIC Gate")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_smd.save()

    # Same name on tenant_b succeeds
    b_smd = _masterdataconfig_methodology(tenant_b, name="Enterprise MEDDIC Gate")
    assert b_smd.pk is not None


# ==============================================================================
# 4. SalesRegionalSetting Tests
# ==============================================================================

def test_masterdataconfig_srg_number_prefix_and_tenant_sequence(tenant_a, tenant_b):
    """Auto-numbering starts with SRG- and sequence is isolated per tenant."""
    assert SalesRegionalSetting.NUMBER_PREFIX == "SRG"

    srg_a1 = _masterdataconfig_regional_setting(tenant_a, name="Regional A1", region_code="NA")
    srg_a2 = _masterdataconfig_regional_setting(tenant_a, name="Regional A2", region_code="EMEA")
    srg_b1 = _masterdataconfig_regional_setting(tenant_b, name="Regional B1", region_code="NA")

    assert re.match(r"^SRG-\d{5}$", srg_a1.number)
    assert re.match(r"^SRG-\d{5}$", srg_a2.number)
    assert re.match(r"^SRG-\d{5}$", srg_b1.number)

    assert srg_a1.number == "SRG-00001"
    assert srg_a2.number == "SRG-00002"
    assert srg_b1.number == "SRG-00001"

    # Re-saving preserves number
    orig_num = srg_a1.number
    srg_a1.default_quote_terms = "Net 45 payment terms."
    srg_a1.save()
    srg_a1.refresh_from_db()
    assert srg_a1.number == orig_num


def test_masterdataconfig_srg_str_representation(tenant_a):
    """String representation formats number, name, region code, and primary currency."""
    srg = _masterdataconfig_regional_setting(
        tenant_a,
        name="DACH Enterprise Commercial",
        region_code="DACH",
        primary_currency="EUR",
    )
    expected = f"{srg.number} · DACH Enterprise Commercial (DACH - EUR)"
    assert str(srg) == expected


def test_masterdataconfig_srg_field_defaults_and_choices(tenant_a):
    """Verify default values and choices for SalesRegionalSetting."""
    srg = SalesRegionalSetting(tenant=tenant_a, name="Default Regional")
    assert srg.region_code == "GLOBAL"
    assert srg.primary_currency == "USD"
    assert srg.supported_currencies == []
    assert srg.date_format == "YYYY-MM-DD"
    assert srg.number_format == "1,234.56"
    assert srg.tax_display_mode == "tax_exclusive"
    assert srg.default_quote_terms == ""
    assert srg.statutory_disclaimer == ""
    assert srg.compliance_framework == "standard"
    assert srg.cooling_off_days == 14
    assert srg.is_default is False
    assert srg.is_active is True

    assert len(SalesRegionalSetting.REGION_CODE_CHOICES) == 7
    assert len(SalesRegionalSetting.DATE_FORMAT_CHOICES) == 4
    assert len(SalesRegionalSetting.NUMBER_FORMAT_CHOICES) == 3
    assert len(SalesRegionalSetting.TAX_DISPLAY_CHOICES) == 2
    assert len(SalesRegionalSetting.COMPLIANCE_CHOICES) == 5


def test_masterdataconfig_srg_primary_currency_normalization(tenant_a):
    """clean() strips whitespace and converts primary_currency to uppercase."""
    srg = SalesRegionalSetting(
        tenant=tenant_a,
        name="Currency Normalization",
        primary_currency="  eur  ",
    )
    srg.clean()
    assert srg.primary_currency == "EUR"


def test_masterdataconfig_srg_supported_currencies_validation(tenant_a):
    """clean() validates that supported_currencies is a JSON array (list)."""
    srg = SalesRegionalSetting(
        tenant=tenant_a,
        name="Currencies Format Test",
        supported_currencies="USD,EUR",  # String instead of list
    )
    with pytest.raises(ValidationError) as exc_info:
        srg.clean()
    assert "supported_currencies" in exc_info.value.message_dict

    # Valid list
    srg.supported_currencies = ["USD", "EUR", "GBP"]
    srg.clean()


def test_masterdataconfig_srg_default_profile_must_be_active(tenant_a):
    """clean() enforces that is_default profile cannot be inactive."""
    srg = SalesRegionalSetting(
        tenant=tenant_a,
        name="Inactive Default",
        is_default=True,
        is_active=False,
    )
    with pytest.raises(ValidationError) as exc_info:
        srg.clean()
    assert "is_default" in exc_info.value.message_dict
    assert "The default regional configuration must be active." in exc_info.value.message_dict["is_default"]

    # Active default succeeds
    srg.is_active = True
    srg.clean()


def test_masterdataconfig_srg_save_single_active_default_scoping(tenant_a, tenant_b):
    """save() demotes previous is_default profiles only within the same tenant."""
    # Profile 1 on tenant_a is set as default
    p1_a = _masterdataconfig_regional_setting(
        tenant_a,
        name="Profile 1 A",
        region_code="NA",
        is_default=True,
    )
    assert p1_a.is_default is True

    # Profile 2 on tenant_a is set as default -> p1_a is demoted
    p2_a = _masterdataconfig_regional_setting(
        tenant_a,
        name="Profile 2 A",
        region_code="EMEA",
        is_default=True,
    )
    p1_a.refresh_from_db()
    assert p1_a.is_default is False
    assert p2_a.is_default is True

    # Profile 1 on tenant_b is set as default -> p2_a on tenant_a remains True
    p1_b = _masterdataconfig_regional_setting(
        tenant_b,
        name="Profile 1 B",
        region_code="NA",
        is_default=True,
    )
    p2_a.refresh_from_db()
    assert p2_a.is_default is True
    assert p1_b.is_default is True

    # Demoting p2_a by re-promoting p1_a
    p1_a.is_default = True
    p1_a.save()
    p1_a.refresh_from_db()
    p2_a.refresh_from_db()
    p1_b.refresh_from_db()

    assert p1_a.is_default is True
    assert p2_a.is_default is False
    assert p1_b.is_default is True


def test_masterdataconfig_srg_cooling_off_days_max_validator(tenant_a):
    """full_clean() validates that cooling_off_days cannot exceed 365."""
    srg_invalid = SalesRegionalSetting(
        tenant=tenant_a,
        name="Invalid Cooling Period",
        cooling_off_days=366,
    )
    with pytest.raises(ValidationError) as exc_info:
        srg_invalid.full_clean()
    assert "cooling_off_days" in exc_info.value.message_dict

    # 365 days is valid
    srg_valid = SalesRegionalSetting(
        tenant=tenant_a,
        name="Valid Max Cooling Period",
        cooling_off_days=365,
    )
    srg_valid.full_clean()


def test_masterdataconfig_srg_unique_constraints(tenant_a, tenant_b):
    """Enforce sales_srg_tenant_num_uniq and sales_srg_tnt_reg_uniq."""
    srg1 = _masterdataconfig_regional_setting(tenant_a, name="NA Terms", region_code="NA")
    assert srg1.number == "SRG-00001"

    # Duplicate number on same tenant raises IntegrityError
    dup_num = _masterdataconfig_make_duplicate_regional_setting(tenant_a, "SRG-00001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_num.save()

    # Duplicate (tenant, region_code) raises IntegrityError
    dup_srg = SalesRegionalSetting(tenant=tenant_a, name="NA Terms Duplicate", region_code="NA")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_srg.save()

    # Same region_code on tenant_b succeeds
    b_srg = _masterdataconfig_regional_setting(tenant_b, name="NA Terms B", region_code="NA")
    assert b_srg.pk is not None
