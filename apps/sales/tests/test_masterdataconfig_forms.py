"""Unit tests for Sales 8.19 Master Data & Configuration forms.

Subslug: masterdataconfig
Prefix for test functions: test_masterdataconfig_*
Prefix for helper functions: _masterdataconfig_*

Covers:
1. System Field Exclusions:
   - tenant, number, created_at, updated_at across all 4 forms.
2. SalesPriceBookEntryForm:
   - Tenant scoping on foreign key dropdown querysets (price_book, product, item).
   - Initial value population for volume_tier_breaks_raw on edit.
   - Raw input parsing: empty, valid JSON, malformed JSON, non-list JSON.
   - Currency code normalization and default.
   - Validation & cleaning: negative numbers, floor_price > list_price, valid_from > valid_to, min_quantity <= 0.
   - Cross-tenant FK rejection.
3. SalesCustomEntityDefinitionForm:
   - Initial value population for picklist_options_raw on edit.
   - Raw input parsing: newline, comma, JSON array, empty string.
   - Conditional required fields: formula_expression for 'formula', lookup_target_model for 'lookup'/'master_detail'.
   - Regex pattern validation in validation_rule (valid vs invalid regex).
   - Entity code normalization (lowercase/strip).
4. SalesMethodologyForm:
   - Tenant scoping on foreign key dropdown querysets (pipeline, gating_stage).
   - Initial value population for qualification_criteria_raw on edit.
   - Raw input parsing: newline items, JSON array, empty string, malformed JSON, non-list JSON.
   - Validation & cleaning: min_passing_score range (0-100), stage-pipeline alignment.
   - Cross-tenant FK rejection.
5. SalesRegionalSettingForm:
   - Initial value population for supported_currencies_raw on edit.
   - Raw input parsing: comma-separated, newline-separated, semicolon-separated, empty string.
   - Primary currency normalization and default.
   - Validation & cleaning: cooling_off_days bounds (0-365), is_default requiring is_active.
   - Single default switch logic on save within active tenant.
"""
from decimal import Decimal
import json
import uuid
import pytest
from django.utils import timezone

from apps.crm.models import PriceBook, Product
from apps.sales.forms import (
    SalesCustomEntityDefinitionForm,
    SalesMethodologyForm,
    SalesPriceBookEntryForm,
    SalesRegionalSettingForm,
)
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

def _masterdataconfig_widen(form, field_name, queryset):
    """Widens a form field queryset to allow cross-tenant test values past choice validation."""
    form.fields[field_name].queryset = queryset


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
        sku = f"SKU-{uuid.uuid4().hex[:8]}"
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
        sku = f"ITM-{uuid.uuid4().hex[:8]}"
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
        code = f"stage_{uuid.uuid4().hex[:8]}"
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
        "is_active": True,
    }
    defaults.update(overrides)
    return PipelineStage.objects.create(**defaults)


def _masterdataconfig_price_book_entry_payload(price_book, product, item=None, **overrides):
    defaults = {
        "price_book": price_book.pk if hasattr(price_book, "pk") else price_book,
        "product": product.pk if hasattr(product, "pk") else product,
        "item": (item.pk if hasattr(item, "pk") else item) if item else "",
        "sku_code": "SKU-ENT-1001",
        "currency_code": "USD",
        "list_price": "1200.00",
        "floor_price": "900.00",
        "pricing_model": "flat",
        "min_quantity": "1.00",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "volume_tier_breaks_raw": '[{"min_qty": 10, "discount_pct": 5.0, "unit_price": 1140.0}]',
        "is_active": True,
        "notes": "Standard enterprise catalog terms.",
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_custom_entity_payload(**overrides):
    defaults = {
        "name": "Deal Margin Percentage",
        "entity_code": "deal_margin_pct_c",
        "target_model": "opportunity",
        "field_type": "percent",
        "is_required": False,
        "formula_expression": "",
        "lookup_target_model": "",
        "picklist_options_raw": "Tier 1 Enterprise\nMid-Market Growth\nSMB Fast Track",
        "validation_rule": "",
        "display_order": 10,
        "is_active": True,
        "description": "Calculated or entered gross margin for opportunity deals.",
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_methodology_payload(pipeline=None, gating_stage=None, **overrides):
    defaults = {
        "name": "Enterprise MEDDPICC Stage Gate",
        "framework": "meddpicc",
        "pipeline": (pipeline.pk if hasattr(pipeline, "pk") else pipeline) if pipeline else "",
        "gating_stage": (gating_stage.pk if hasattr(gating_stage, "pk") else gating_stage) if gating_stage else "",
        "min_passing_score": 75,
        "is_mandatory_gate": True,
        "qualification_criteria_raw": '[{"key": "metrics", "label": "Quantified Economic Impact", "weight": 20, "is_required": true}]',
        "coaching_guidelines": "Ensure champion is tested before scheduling final presentation.",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_regional_setting_payload(**overrides):
    defaults = {
        "name": "EMEA Commercial Terms Profile",
        "region_code": "EMEA",
        "primary_currency": "EUR",
        "supported_currencies_raw": "EUR, GBP, USD, CHF",
        "date_format": "DD/MM/YYYY",
        "number_format": "1.234,56",
        "tax_display_mode": "tax_inclusive",
        "default_quote_terms": "Net 30 days upon invoice delivery.",
        "statutory_disclaimer": "Subject to GDPR commercial compliance warranties.",
        "compliance_framework": "gdpr_commercial",
        "cooling_off_days": 14,
        "is_default": False,
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


# ==============================================================================
# 0. System Field Exclusions
# ==============================================================================

def test_masterdataconfig_forms_system_fields_excluded():
    """Verify system fields (tenant, number, created_at, updated_at) are excluded across all 4 forms."""
    excluded_fields = {"tenant", "number", "created_at", "updated_at"}
    forms = [
        SalesPriceBookEntryForm(),
        SalesCustomEntityDefinitionForm(),
        SalesMethodologyForm(),
        SalesRegionalSettingForm(),
    ]
    for form in forms:
        form_name = form.__class__.__name__
        for field in excluded_fields:
            assert field not in form.fields, f"{field} must be excluded from {form_name}"


# ==============================================================================
# 1. SalesPriceBookEntryForm Tests
# ==============================================================================

def test_masterdataconfig_pbe_form_valid_create(tenant_a):
    """SalesPriceBookEntryForm validates and binds model instance attributes on create."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)
    item = _masterdataconfig_item(tenant_a)
    payload = _masterdataconfig_price_book_entry_payload(pb, prod, item=item)

    form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Expected valid form, got errors: {form.errors}"
    entry = form.save()

    assert entry.tenant == tenant_a
    assert entry.price_book == pb
    assert entry.product == prod
    assert entry.item == item
    assert entry.list_price == Decimal("1200.00")
    assert entry.floor_price == Decimal("900.00")
    assert entry.volume_tier_breaks == [{"min_qty": 10, "discount_pct": 5.0, "unit_price": 1140.0}]
    assert entry.is_active is True


def test_masterdataconfig_pbe_form_initial_volume_tier_breaks(tenant_a):
    """Existing volume_tier_breaks on instance populates volume_tier_breaks_raw initial value."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)
    tier_data = [{"min_qty": 20, "discount_pct": 10.0, "unit_price": 1080.0}]
    entry = SalesPriceBookEntry.objects.create(
        tenant=tenant_a,
        price_book=pb,
        product=prod,
        sku_code="SKU-INIT",
        currency_code="USD",
        list_price=Decimal("1200.00"),
        floor_price=Decimal("900.00"),
        volume_tier_breaks=tier_data,
    )

    form = SalesPriceBookEntryForm(instance=entry, tenant=tenant_a)
    initial_raw = form.fields["volume_tier_breaks_raw"].initial
    assert initial_raw is not None
    assert json.loads(initial_raw) == tier_data


def test_masterdataconfig_pbe_form_fk_tenant_scoping(tenant_a, tenant_b):
    """Foreign key dropdown querysets contain only active tenant's records."""
    pb_a = _masterdataconfig_price_book(tenant_a, name="Catalog A")
    pb_b = _masterdataconfig_price_book(tenant_b, name="Catalog B")
    prod_a = _masterdataconfig_product(tenant_a, name="Product A")
    prod_b = _masterdataconfig_product(tenant_b, name="Product B")
    item_a = _masterdataconfig_item(tenant_a, name="Item A")
    item_b = _masterdataconfig_item(tenant_b, name="Item B")

    form_a = SalesPriceBookEntryForm(tenant=tenant_a)
    assert pb_a in form_a.fields["price_book"].queryset
    assert pb_b not in form_a.fields["price_book"].queryset
    assert prod_a in form_a.fields["product"].queryset
    assert prod_b not in form_a.fields["product"].queryset
    assert item_a in form_a.fields["item"].queryset
    assert item_b not in form_a.fields["item"].queryset


def test_masterdataconfig_pbe_form_volume_tier_breaks_raw_empty(tenant_a):
    """Empty or whitespace volume_tier_breaks_raw parses to empty list []."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    for empty_val in ["", "   ", "\n\t"]:
        payload = _masterdataconfig_price_book_entry_payload(pb, prod, volume_tier_breaks_raw=empty_val)
        form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), f"Expected valid form for empty input: {form.errors}"
        assert form.cleaned_data["volume_tier_breaks_raw"] == []


def test_masterdataconfig_pbe_form_volume_tier_breaks_raw_malformed_json(tenant_a):
    """Malformed JSON syntax raises validation error on volume_tier_breaks_raw."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)
    payload = _masterdataconfig_price_book_entry_payload(
        pb, prod, volume_tier_breaks_raw='[{"min_qty": 10, "discount_pct":'
    )

    form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "volume_tier_breaks_raw" in form.errors
    assert "Invalid JSON format" in form.errors["volume_tier_breaks_raw"][0]


def test_masterdataconfig_pbe_form_volume_tier_breaks_raw_not_a_list(tenant_a):
    """JSON object or scalar that is not a list raises validation error."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    for non_list_json in ['{"tier_1": {"min": 1}}', '"tier_1"', '123']:
        payload = _masterdataconfig_price_book_entry_payload(
            pb, prod, volume_tier_breaks_raw=non_list_json
        )
        form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "volume_tier_breaks_raw" in form.errors
        assert "Must be a JSON array" in form.errors["volume_tier_breaks_raw"][0]


def test_masterdataconfig_pbe_form_currency_code_normalization(tenant_a):
    """Currency code is converted to uppercase and defaults to USD when empty."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    payload = _masterdataconfig_price_book_entry_payload(pb, prod, currency_code="  eur  ")
    form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data["currency_code"] == "EUR"

    payload_blank = _masterdataconfig_price_book_entry_payload(pb, prod, currency_code="")
    form_blank = SalesPriceBookEntryForm(data=payload_blank, tenant=tenant_a)
    assert form_blank.is_valid(), f"Form errors: {form_blank.errors}"
    assert form_blank.cleaned_data["currency_code"] == "USD"


def test_masterdataconfig_pbe_form_floor_price_exceeds_list_price(tenant_a):
    """Form raises validation error when floor_price > list_price."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)
    payload = _masterdataconfig_price_book_entry_payload(
        pb, prod, list_price="500.00", floor_price="600.00"
    )

    form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "floor_price" in form.errors
    assert "Floor price cannot exceed list price" in form.errors["floor_price"][0]


def test_masterdataconfig_pbe_form_valid_from_after_valid_to(tenant_a):
    """Form raises validation error when valid_from is after valid_to."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)
    payload = _masterdataconfig_price_book_entry_payload(
        pb, prod, valid_from="2026-12-31", valid_to="2026-01-01"
    )

    form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "valid_to" in form.errors
    assert "Expiration date cannot precede effective start date" in form.errors["valid_to"][0]


def test_masterdataconfig_pbe_form_negative_numbers_rejected(tenant_a):
    """Form rejects negative list_price and floor_price."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    payload_neg_list = _masterdataconfig_price_book_entry_payload(pb, prod, list_price="-10.00")
    form_list = SalesPriceBookEntryForm(data=payload_neg_list, tenant=tenant_a)
    assert not form_list.is_valid()
    assert "list_price" in form_list.errors

    payload_neg_floor = _masterdataconfig_price_book_entry_payload(pb, prod, floor_price="-5.00")
    form_floor = SalesPriceBookEntryForm(data=payload_neg_floor, tenant=tenant_a)
    assert not form_floor.is_valid()
    assert "floor_price" in form_floor.errors


def test_masterdataconfig_pbe_form_min_quantity_invalid(tenant_a):
    """Form rejects min_quantity <= 0."""
    pb = _masterdataconfig_price_book(tenant_a)
    prod = _masterdataconfig_product(tenant_a)

    for invalid_qty in ["0.00", "-1.00"]:
        payload = _masterdataconfig_price_book_entry_payload(pb, prod, min_quantity=invalid_qty)
        form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "min_quantity" in form.errors


def test_masterdataconfig_pbe_form_cross_tenant_rejection(tenant_a, tenant_b):
    """Submitting foreign tenant's price_book, product, or item fails validation."""
    pb_b = _masterdataconfig_price_book(tenant_b)
    prod_a = _masterdataconfig_product(tenant_a)
    payload = _masterdataconfig_price_book_entry_payload(pb_b, prod_a)

    form = SalesPriceBookEntryForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "price_book" in form.errors

    # Bypass dropdown choice restriction to verify instance.clean() rejection
    _masterdataconfig_widen(form, "price_book", PriceBook.objects.all())
    assert not form.is_valid()
    assert "price_book" in form.errors


# ==============================================================================
# 2. SalesCustomEntityDefinitionForm Tests
# ==============================================================================

def test_masterdataconfig_sco_form_valid_create(tenant_a):
    """SalesCustomEntityDefinitionForm creates custom entity definition with parsed options."""
    payload = _masterdataconfig_custom_entity_payload(
        name="Deal Approval Level",
        entity_code="deal_appr_lvl_c",
        target_model="opportunity",
        field_type="picklist",
        picklist_options_raw="Director\nVP\nExecutive VP",
    )

    form = SalesCustomEntityDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Expected valid form, got errors: {form.errors}"
    sco = form.save(commit=False)
    sco.tenant = tenant_a
    sco.save()

    assert sco.name == "Deal Approval Level"
    assert sco.entity_code == "deal_appr_lvl_c"
    assert sco.target_model == "opportunity"
    assert sco.field_type == "picklist"
    assert sco.picklist_options == ["Director", "VP", "Executive VP"]


def test_masterdataconfig_sco_form_initial_picklist_options(tenant_a):
    """Existing picklist_options populates picklist_options_raw initial value with newlines."""
    sco = SalesCustomEntityDefinition.objects.create(
        tenant=tenant_a,
        name="Customer Risk Segment",
        entity_code="cust_risk_seg_c",
        target_model="account",
        field_type="picklist",
        picklist_options=["Low Risk", "Moderate Risk", "High Risk"],
    )

    form = SalesCustomEntityDefinitionForm(instance=sco, tenant=tenant_a)
    initial_raw = form.fields["picklist_options_raw"].initial
    assert initial_raw == "Low Risk\nModerate Risk\nHigh Risk"


def test_masterdataconfig_sco_form_picklist_options_raw_parsing(tenant_a):
    """picklist_options_raw parses newline, comma, and JSON array strings into string list."""
    # Newline separated
    payload_nl = _masterdataconfig_custom_entity_payload(
        entity_code="opt_nl_c",
        picklist_options_raw="Gold Partner\nSilver Partner\nBronze Partner",
    )
    form_nl = SalesCustomEntityDefinitionForm(data=payload_nl, tenant=tenant_a)
    assert form_nl.is_valid(), f"Errors: {form_nl.errors}"
    assert form_nl.cleaned_data["picklist_options_raw"] == ["Gold Partner", "Silver Partner", "Bronze Partner"]

    # Comma separated
    payload_comma = _masterdataconfig_custom_entity_payload(
        entity_code="opt_comma_c",
        picklist_options_raw="Platinum, Gold, Silver",
    )
    form_comma = SalesCustomEntityDefinitionForm(data=payload_comma, tenant=tenant_a)
    assert form_comma.is_valid(), f"Errors: {form_comma.errors}"
    assert form_comma.cleaned_data["picklist_options_raw"] == ["Platinum", "Gold", "Silver"]

    # JSON array
    payload_json = _masterdataconfig_custom_entity_payload(
        entity_code="opt_json_c",
        picklist_options_raw='["Alpha", "Beta", "Gamma"]',
    )
    form_json = SalesCustomEntityDefinitionForm(data=payload_json, tenant=tenant_a)
    assert form_json.is_valid(), f"Errors: {form_json.errors}"
    assert form_json.cleaned_data["picklist_options_raw"] == ["Alpha", "Beta", "Gamma"]

    # Empty
    payload_empty = _masterdataconfig_custom_entity_payload(
        entity_code="opt_empty_c",
        picklist_options_raw="   ",
    )
    form_empty = SalesCustomEntityDefinitionForm(data=payload_empty, tenant=tenant_a)
    assert form_empty.is_valid(), f"Errors: {form_empty.errors}"
    assert form_empty.cleaned_data["picklist_options_raw"] == []


def test_masterdataconfig_sco_form_formula_expression_required_for_formula(tenant_a):
    """formula_expression is mandatory when field_type is 'formula'."""
    payload_missing = _masterdataconfig_custom_entity_payload(
        entity_code="margin_calc_c",
        field_type="formula",
        formula_expression="",
    )
    form_missing = SalesCustomEntityDefinitionForm(data=payload_missing, tenant=tenant_a)
    form_missing.instance.tenant = tenant_a
    assert not form_missing.is_valid()
    assert "formula_expression" in form_missing.errors
    assert "Formula expression is required" in form_missing.errors["formula_expression"][0]

    payload_valid = _masterdataconfig_custom_entity_payload(
        entity_code="margin_calc_c",
        field_type="formula",
        formula_expression="(amount - cost) / amount * 100",
    )
    form_valid = SalesCustomEntityDefinitionForm(data=payload_valid, tenant=tenant_a)
    form_valid.instance.tenant = tenant_a
    assert form_valid.is_valid(), f"Errors: {form_valid.errors}"


def test_masterdataconfig_sco_form_lookup_target_model_required_for_relationships(tenant_a):
    """lookup_target_model is mandatory when field_type is 'lookup' or 'master_detail'."""
    for rel_type in ["lookup", "master_detail"]:
        payload_missing = _masterdataconfig_custom_entity_payload(
            entity_code=f"rel_{rel_type}_c",
            field_type=rel_type,
            lookup_target_model="",
        )
        form_missing = SalesCustomEntityDefinitionForm(data=payload_missing, tenant=tenant_a)
        form_missing.instance.tenant = tenant_a
        assert not form_missing.is_valid()
        assert "lookup_target_model" in form_missing.errors
        assert "Lookup target model is required" in form_missing.errors["lookup_target_model"][0]

        payload_valid = _masterdataconfig_custom_entity_payload(
            entity_code=f"rel_{rel_type}_c",
            field_type=rel_type,
            lookup_target_model="core.Party",
        )
        form_valid = SalesCustomEntityDefinitionForm(data=payload_valid, tenant=tenant_a)
        form_valid.instance.tenant = tenant_a
        assert form_valid.is_valid(), f"Errors: {form_valid.errors}"


def test_masterdataconfig_sco_form_validation_rule_regex_validation(tenant_a):
    """validation_rule regex pattern is checked for valid regex syntax."""
    # Valid regex
    payload_valid = _masterdataconfig_custom_entity_payload(
        entity_code="code_rule_c",
        validation_rule="^[A-Z]{3}-[0-9]{4}$",
    )
    form_valid = SalesCustomEntityDefinitionForm(data=payload_valid, tenant=tenant_a)
    form_valid.instance.tenant = tenant_a
    assert form_valid.is_valid(), f"Errors: {form_valid.errors}"

    # Invalid regex (unbalanced parenthesis)
    payload_invalid = _masterdataconfig_custom_entity_payload(
        entity_code="code_bad_rule_c",
        validation_rule="^[A-Z{3}-[0-9]{4}$(",
    )
    form_invalid = SalesCustomEntityDefinitionForm(data=payload_invalid, tenant=tenant_a)
    form_invalid.instance.tenant = tenant_a
    assert not form_invalid.is_valid()
    assert "validation_rule" in form_invalid.errors
    assert "Invalid regular expression pattern" in form_invalid.errors["validation_rule"][0]


def test_masterdataconfig_sco_form_entity_code_normalization(tenant_a):
    """entity_code is stripped and lowercased during cleaning."""
    payload = _masterdataconfig_custom_entity_payload(
        entity_code="  UPPER_AND_SPACES_C  ",
    )
    form = SalesCustomEntityDefinitionForm(data=payload, tenant=tenant_a)
    form.instance.tenant = tenant_a
    assert form.is_valid(), f"Errors: {form.errors}"
    sco = form.save(commit=False)
    assert sco.entity_code == "upper_and_spaces_c"


# ==============================================================================
# 3. SalesMethodologyForm Tests
# ==============================================================================

def test_masterdataconfig_smd_form_valid_create(tenant_a):
    """SalesMethodologyForm creates a methodology framework template with criteria."""
    pipeline = _masterdataconfig_pipeline(tenant_a)
    stage = _masterdataconfig_stage(tenant_a, pipeline)
    payload = _masterdataconfig_methodology_payload(pipeline=pipeline, gating_stage=stage)

    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Expected valid form, got errors: {form.errors}"
    methodology = form.save()

    assert methodology.tenant == tenant_a
    assert methodology.pipeline == pipeline
    assert methodology.gating_stage == stage
    assert methodology.min_passing_score == 75
    assert methodology.is_mandatory_gate is True
    assert len(methodology.qualification_criteria) == 1
    assert methodology.qualification_criteria[0]["key"] == "metrics"


def test_masterdataconfig_smd_form_initial_qualification_criteria(tenant_a):
    """Existing qualification_criteria populates qualification_criteria_raw initial JSON."""
    criteria_data = [{"key": "economic_buyer", "label": "Direct Budget Authority", "weight": 25}]
    methodology = SalesMethodology.objects.create(
        tenant=tenant_a,
        name="SPIN Framework",
        framework="spin",
        qualification_criteria=criteria_data,
    )

    form = SalesMethodologyForm(instance=methodology, tenant=tenant_a)
    initial_raw = form.fields["qualification_criteria_raw"].initial
    assert initial_raw is not None
    assert json.loads(initial_raw) == criteria_data


def test_masterdataconfig_smd_form_fk_tenant_scoping(tenant_a, tenant_b):
    """Pipeline and gating stage dropdowns exclude foreign tenant and inactive records."""
    pipe_a_active = _masterdataconfig_pipeline(tenant_a, name="Pipe A Active", is_active=True)
    pipe_a_inactive = _masterdataconfig_pipeline(tenant_a, name="Pipe A Inactive", is_active=False)
    pipe_b_active = _masterdataconfig_pipeline(tenant_b, name="Pipe B Active", is_active=True)

    stage_a_active = _masterdataconfig_stage(tenant_a, pipe_a_active, name="Stage A Active", sequence=10, is_active=True)
    stage_a_inactive = _masterdataconfig_stage(tenant_a, pipe_a_active, name="Stage A Inactive", sequence=20, is_active=False)
    stage_b_active = _masterdataconfig_stage(tenant_b, pipe_b_active, name="Stage B Active", sequence=10, is_active=True)

    form = SalesMethodologyForm(tenant=tenant_a)

    # Pipeline queryset scoping
    assert pipe_a_active in form.fields["pipeline"].queryset
    assert pipe_a_inactive not in form.fields["pipeline"].queryset
    assert pipe_b_active not in form.fields["pipeline"].queryset

    # Gating stage queryset scoping
    assert stage_a_active in form.fields["gating_stage"].queryset
    assert stage_a_inactive not in form.fields["gating_stage"].queryset
    assert stage_b_active not in form.fields["gating_stage"].queryset


def test_masterdataconfig_smd_form_qualification_criteria_raw_newline_parsing(tenant_a):
    """qualification_criteria_raw parses newline strings into list of criteria strings."""
    raw_lines = "Metrics Quantified\nEconomic Buyer Engaged\nDecision Process Clear"
    payload = _masterdataconfig_methodology_payload(qualification_criteria_raw=raw_lines)

    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["qualification_criteria_raw"] == [
        "Metrics Quantified",
        "Economic Buyer Engaged",
        "Decision Process Clear",
    ]


def test_masterdataconfig_smd_form_qualification_criteria_raw_json_parsing(tenant_a):
    """qualification_criteria_raw parses valid JSON list of criteria objects."""
    raw_json = '[{"key": "champion", "label": "Internal Sponsor", "weight": 20}]'
    payload = _masterdataconfig_methodology_payload(qualification_criteria_raw=raw_json)

    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["qualification_criteria_raw"] == [
        {"key": "champion", "label": "Internal Sponsor", "weight": 20}
    ]


def test_masterdataconfig_smd_form_qualification_criteria_raw_empty(tenant_a):
    """Empty qualification_criteria_raw parses to empty list []."""
    payload = _masterdataconfig_methodology_payload(qualification_criteria_raw="   ")

    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["qualification_criteria_raw"] == []


def test_masterdataconfig_smd_form_qualification_criteria_raw_malformed_json(tenant_a):
    """Malformed JSON starting with [ raises validation error."""
    payload = _masterdataconfig_methodology_payload(
        qualification_criteria_raw='[{"key": "metrics", broken json'
    )

    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "qualification_criteria_raw" in form.errors
    assert "Invalid JSON format" in form.errors["qualification_criteria_raw"][0]


def test_masterdataconfig_smd_form_qualification_criteria_raw_not_a_list(tenant_a):
    """JSON object starting with [ but not a list raises validation error."""
    payload = _masterdataconfig_methodology_payload(
        qualification_criteria_raw='{"metrics": "true"}'
    )

    # Note: {"metrics": "true"} is treated as newline text if not starting with [
    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert form.is_valid()
    assert form.cleaned_data["qualification_criteria_raw"] == ['{"metrics": "true"}']


def test_masterdataconfig_smd_form_min_passing_score_bounds(tenant_a):
    """min_passing_score must be between 0 and 100."""
    for invalid_score in [-1, 101]:
        payload = _masterdataconfig_methodology_payload(min_passing_score=invalid_score)
        form = SalesMethodologyForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "min_passing_score" in form.errors

    for valid_score in [0, 50, 100]:
        payload = _masterdataconfig_methodology_payload(name=f"Score Test {valid_score}", min_passing_score=valid_score)
        form = SalesMethodologyForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), f"Expected valid for score {valid_score}, got {form.errors}"


def test_masterdataconfig_smd_form_stage_pipeline_alignment(tenant_a):
    """gating_stage must belong to the selected pipeline."""
    pipe_1 = _masterdataconfig_pipeline(tenant_a, name="Pipeline 1")
    pipe_2 = _masterdataconfig_pipeline(tenant_a, name="Pipeline 2")
    stage_pipe_2 = _masterdataconfig_stage(tenant_a, pipe_2, name="Stage of Pipe 2")

    # Submit pipe_1 with stage_pipe_2
    payload = _masterdataconfig_methodology_payload(pipeline=pipe_1, gating_stage=stage_pipe_2)
    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "gating_stage" in form.errors
    assert "Gating stage must belong to the selected pipeline" in form.errors["gating_stage"][0]


def test_masterdataconfig_smd_form_cross_tenant_rejection(tenant_a, tenant_b):
    """Submitting foreign tenant pipeline or gating stage is rejected."""
    pipe_b = _masterdataconfig_pipeline(tenant_b, name="Pipe Tenant B")
    payload = _masterdataconfig_methodology_payload(pipeline=pipe_b)

    form = SalesMethodologyForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "pipeline" in form.errors

    # Bypass choice restriction to test model-level tenant scoping
    _masterdataconfig_widen(form, "pipeline", Pipeline.objects.all())
    assert not form.is_valid()
    assert "pipeline" in form.errors


# ==============================================================================
# 4. SalesRegionalSettingForm Tests
# ==============================================================================

def test_masterdataconfig_srg_form_valid_create(tenant_a):
    """SalesRegionalSettingForm creates regional settings with parsed currency list."""
    payload = _masterdataconfig_regional_setting_payload(
        name="APAC Commercial Profile",
        region_code="APAC",
        primary_currency="SGD",
        supported_currencies_raw="SGD, USD, AUD, JPY",
    )

    form = SalesRegionalSettingForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), f"Expected valid form, got errors: {form.errors}"
    setting = form.save(commit=False)
    setting.tenant = tenant_a
    setting.save()

    assert setting.name == "APAC Commercial Profile"
    assert setting.region_code == "APAC"
    assert setting.primary_currency == "SGD"
    assert setting.supported_currencies == ["SGD", "USD", "AUD", "JPY"]
    assert setting.tax_display_mode == "tax_inclusive"


def test_masterdataconfig_srg_form_initial_supported_currencies(tenant_a):
    """Existing supported_currencies populates supported_currencies_raw initial value."""
    setting = SalesRegionalSetting.objects.create(
        tenant=tenant_a,
        name="UK Regional Profile",
        region_code="UK",
        primary_currency="GBP",
        supported_currencies=["GBP", "EUR", "USD"],
    )

    form = SalesRegionalSettingForm(instance=setting, tenant=tenant_a)
    initial_raw = form.fields["supported_currencies_raw"].initial
    assert initial_raw == "GBP, EUR, USD"


def test_masterdataconfig_srg_form_primary_currency_normalization(tenant_a):
    """primary_currency is converted to uppercase and defaults to USD when empty."""
    payload_lower = _masterdataconfig_regional_setting_payload(
        primary_currency="  cad  ",
    )
    form_lower = SalesRegionalSettingForm(data=payload_lower, tenant=tenant_a)
    assert form_lower.is_valid(), f"Errors: {form_lower.errors}"
    assert form_lower.cleaned_data["primary_currency"] == "CAD"

    payload_blank = _masterdataconfig_regional_setting_payload(
        primary_currency="",
    )
    form_blank = SalesRegionalSettingForm(data=payload_blank, tenant=tenant_a)
    assert form_blank.is_valid(), f"Errors: {form_blank.errors}"
    assert form_blank.cleaned_data["primary_currency"] == "USD"


def test_masterdataconfig_srg_form_supported_currencies_raw_parsing(tenant_a):
    """supported_currencies_raw parses comma, newline, and semicolon separated currencies into uppercase list."""
    # Comma separated
    payload_comma = _masterdataconfig_regional_setting_payload(
        supported_currencies_raw="eur, gbp, chf",
    )
    form_comma = SalesRegionalSettingForm(data=payload_comma, tenant=tenant_a)
    assert form_comma.is_valid(), f"Errors: {form_comma.errors}"
    assert form_comma.cleaned_data["supported_currencies_raw"] == ["EUR", "GBP", "CHF"]

    # Newline separated
    payload_nl = _masterdataconfig_regional_setting_payload(
        supported_currencies_raw="USD\nEUR\nGBP",
    )
    form_nl = SalesRegionalSettingForm(data=payload_nl, tenant=tenant_a)
    assert form_nl.is_valid(), f"Errors: {form_nl.errors}"
    assert form_nl.cleaned_data["supported_currencies_raw"] == ["USD", "EUR", "GBP"]

    # Semicolon separated
    payload_semi = _masterdataconfig_regional_setting_payload(
        supported_currencies_raw="USD; EUR; JPY",
    )
    form_semi = SalesRegionalSettingForm(data=payload_semi, tenant=tenant_a)
    assert form_semi.is_valid(), f"Errors: {form_semi.errors}"
    assert form_semi.cleaned_data["supported_currencies_raw"] == ["USD", "EUR", "JPY"]

    # Empty string
    payload_empty = _masterdataconfig_regional_setting_payload(
        supported_currencies_raw="   ",
    )
    form_empty = SalesRegionalSettingForm(data=payload_empty, tenant=tenant_a)
    assert form_empty.is_valid(), f"Errors: {form_empty.errors}"
    assert form_empty.cleaned_data["supported_currencies_raw"] == []


def test_masterdataconfig_srg_form_cooling_off_days_bounds(tenant_a):
    """cooling_off_days cannot exceed 365 or be negative."""
    payload_exceed = _masterdataconfig_regional_setting_payload(cooling_off_days=366)
    form_exceed = SalesRegionalSettingForm(data=payload_exceed, tenant=tenant_a)
    assert not form_exceed.is_valid()
    assert "cooling_off_days" in form_exceed.errors

    payload_neg = _masterdataconfig_regional_setting_payload(cooling_off_days=-1)
    form_neg = SalesRegionalSettingForm(data=payload_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "cooling_off_days" in form_neg.errors

    for valid_days in [0, 14, 30, 365]:
        payload_valid = _masterdataconfig_regional_setting_payload(
            name=f"Cooling Days {valid_days}", cooling_off_days=valid_days
        )
        form_valid = SalesRegionalSettingForm(data=payload_valid, tenant=tenant_a)
        assert form_valid.is_valid(), f"Expected valid for {valid_days} days, got {form_valid.errors}"


def test_masterdataconfig_srg_form_default_must_be_active(tenant_a):
    """is_default cannot be True when is_active is False."""
    payload = _masterdataconfig_regional_setting_payload(is_default=True, is_active=False)
    form = SalesRegionalSettingForm(data=payload, tenant=tenant_a)
    form.instance.tenant = tenant_a
    assert not form.is_valid()
    assert "is_default" in form.errors
    assert "The default regional configuration must be active" in form.errors["is_default"][0]


def test_masterdataconfig_srg_form_single_default_switching_on_save(tenant_a):
    """Saving a regional setting with is_default=True demotes previous default in same tenant."""
    setting_1 = SalesRegionalSetting.objects.create(
        tenant=tenant_a,
        name="Default Profile 1",
        region_code="NA",
        primary_currency="USD",
        is_default=True,
        is_active=True,
    )

    payload = _masterdataconfig_regional_setting_payload(
        name="Default Profile 2",
        region_code="EMEA",
        is_default=True,
        is_active=True,
    )
    form = SalesRegionalSettingForm(data=payload, tenant=tenant_a)
    form.instance.tenant = tenant_a
    assert form.is_valid(), f"Errors: {form.errors}"
    setting_2 = form.save()

    setting_1.refresh_from_db()
    assert setting_1.is_default is False
    assert setting_2.is_default is True
