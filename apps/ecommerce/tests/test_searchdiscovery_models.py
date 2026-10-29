"""Unit and invariant tests for eCommerce 9.7 Search & Product Discovery models.

Covers:
- SearchSynonym
- SearchFacetConfig
- SearchMerchandisingRule
- SearchQueryLog

Naming conventions enforced:
- Test functions: test_searchdiscovery_*
- Module-level helpers: _searchdiscovery_*
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.models import Party
from apps.ecommerce.models import (
    SearchSynonym,
    SearchFacetConfig,
    SearchMerchandisingRule,
    SearchQueryLog,
    CatalogProduct,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    SEARCHDISCOVERY_MODEL_FIELDS,
    SEARCHDISCOVERY_CHOICES,
    _searchdiscovery_synonym,
    _searchdiscovery_facet_config,
    _searchdiscovery_merchandising_rule,
    _searchdiscovery_query_log,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_searchdiscovery_*)
# ==============================================================================

def _searchdiscovery_make_product(tenant, name="Test Product"):
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        status="active",
    )


def _searchdiscovery_make_category(tenant, name="Test Category"):
    return StoreCategory.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
    )


# ==============================================================================
# Contract Verification Tests
# ==============================================================================

def test_searchdiscovery_model_fields_contract():
    model_classes = {
        "SearchSynonym": SearchSynonym,
        "SearchFacetConfig": SearchFacetConfig,
        "SearchMerchandisingRule": SearchMerchandisingRule,
        "SearchQueryLog": SearchQueryLog,
    }
    for model_name, expected_fields in SEARCHDISCOVERY_MODEL_FIELDS.items():
        cls = model_classes[model_name]
        actual_fields = {f.name for f in cls._meta.get_fields()}
        for field in expected_fields:
            assert field in actual_fields, f"Field '{field}' missing on {model_name}"


def test_searchdiscovery_choices_contract():
    assert tuple(SearchSynonym.SYNONYM_TYPE_CHOICES) == SEARCHDISCOVERY_CHOICES["SearchSynonym"]["synonym_type"]
    assert tuple(SearchFacetConfig.SOURCE_TYPE_CHOICES) == SEARCHDISCOVERY_CHOICES["SearchFacetConfig"]["source_type"]
    assert tuple(SearchFacetConfig.WIDGET_TYPE_CHOICES) == SEARCHDISCOVERY_CHOICES["SearchFacetConfig"]["widget_type"]
    assert tuple(SearchFacetConfig.FILTER_LOGIC_CHOICES) == SEARCHDISCOVERY_CHOICES["SearchFacetConfig"]["filter_logic"]
    assert tuple(SearchMerchandisingRule.RULE_TYPE_CHOICES) == SEARCHDISCOVERY_CHOICES["SearchMerchandisingRule"]["rule_type"]
    assert tuple(SearchMerchandisingRule.ACTION_TYPE_CHOICES) == SEARCHDISCOVERY_CHOICES["SearchMerchandisingRule"]["action_type"]


# ==============================================================================
# SearchSynonym Model Tests
# ==============================================================================

def test_searchdiscovery_synonym_creation_and_autonumber(tenant_a):
    syn = _searchdiscovery_synonym(tenant_a, root_term="laptop", synonyms="notebook, ultrabook")
    assert syn.pk is not None
    assert syn.number.startswith("ESYM-")
    assert syn.root_term == "laptop"
    assert syn.synonym_type == "two_way"
    assert syn.hit_count == 0
    assert syn.is_active is True
    assert "laptop" in str(syn)


def test_searchdiscovery_synonym_methods(tenant_a):
    syn = _searchdiscovery_synonym(tenant_a, root_term="shoes", synonyms="sneakers, trainers, kicks")
    assert syn.get_synonym_list() == ["sneakers", "trainers", "kicks"]
    assert len(syn.get_synonym_list()) == 3


def test_searchdiscovery_synonym_clean_replacement(tenant_a):
    syn = SearchSynonym(
        tenant=tenant_a,
        name="Invalid Replacement",
        synonym_type="replacement",
        root_term="old",
        synonyms="new1, new2",
    )
    with pytest.raises(ValidationError) as exc_info:
        syn.clean()
    assert "synonyms" in exc_info.value.message_dict


# ==============================================================================
# SearchFacetConfig Model Tests
# ==============================================================================

def test_searchdiscovery_facet_config_creation_and_autonumber(tenant_a):
    fc = _searchdiscovery_facet_config(tenant_a, name="Price Tier", code="price_range", source_type="price", widget_type="price_slider")
    assert fc.pk is not None
    assert fc.number.startswith("ESFC-")
    assert fc.code == "price_range"
    assert fc.widget_type == "price_slider"
    assert "Price Tier" in str(fc)


def test_searchdiscovery_facet_config_clean_cross_tenant_category_scope(tenant_a, tenant_b):
    cat_b = _searchdiscovery_make_category(tenant_b, name="Category B")
    fc = SearchFacetConfig(
        tenant=tenant_a,
        name="Category Filter",
        code="cat_scope",
        source_type="category",
        category_scope=cat_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        fc.clean()
    assert "category_scope" in exc_info.value.message_dict


def test_searchdiscovery_facet_config_clean_variant_option(tenant_a):
    fc = SearchFacetConfig(
        tenant=tenant_a,
        name="Color Filter",
        code="color",
        source_type="variant_option",
        option_key="",
    )
    with pytest.raises(ValidationError) as exc_info:
        fc.clean()
    assert "option_key" in exc_info.value.message_dict


# ==============================================================================
# SearchMerchandisingRule Model Tests
# ==============================================================================

def test_searchdiscovery_merchandising_rule_creation_and_autonumber(tenant_a, ecom_product_a):
    rule = _searchdiscovery_merchandising_rule(
        tenant_a,
        name="Pin Product A",
        rule_type="query",
        action_type="pin",
        trigger_query="featured",
        pin_position=1,
        boosted_product=ecom_product_a,
    )
    assert rule.pk is not None
    assert rule.number.startswith("ESMR-")
    assert rule.action_type == "pin"
    assert rule.pin_position == 1
    assert "Pin Product A" in str(rule)


def test_searchdiscovery_merchandising_rule_clean_dangerous_uri(tenant_a, ecom_product_a):
    rule = SearchMerchandisingRule(
        tenant=tenant_a,
        name="XSS Attempt",
        rule_type="query",
        action_type="redirect",
        trigger_query="hack",
        redirect_url="javascript:alert(1)",
    )
    with pytest.raises(ValidationError) as exc_info:
        rule.clean()
    assert "redirect_url" in exc_info.value.message_dict


def test_searchdiscovery_merchandising_rule_clean_cross_tenant_relations(tenant_a, tenant_b, ecom_product_a):
    prod_b = _searchdiscovery_make_product(tenant_b, name="Product B")
    cat_b = _searchdiscovery_make_category(tenant_b, name="Category B")

    rule_prod = SearchMerchandisingRule(
        tenant=tenant_a,
        name="Cross Tenant Product",
        rule_type="query",
        action_type="boost",
        trigger_query="boots",
        boosted_product=prod_b,
    )
    with pytest.raises(ValidationError) as exc_prod:
        rule_prod.clean()
    assert "boosted_product" in exc_prod.value.message_dict

    rule_cat = SearchMerchandisingRule(
        tenant=tenant_a,
        name="Cross Tenant Category",
        rule_type="category",
        action_type="banner",
        banner_title="Category Sale",
        target_category=cat_b,
    )
    with pytest.raises(ValidationError) as exc_cat:
        rule_cat.clean()
    assert "target_category" in exc_cat.value.message_dict


# ==============================================================================
# SearchQueryLog Model Tests
# ==============================================================================

def test_searchdiscovery_query_log_creation_and_autonumber(tenant_a):
    log = _searchdiscovery_query_log(
        tenant_a,
        query_text="  running shoes  ",
        normalized_query="running shoes",
        results_count=0,
    )
    assert log.pk is not None
    assert log.number.startswith("ESQL-")
    assert log.is_zero_result is True
    assert "running shoes" in str(log)


def test_searchdiscovery_query_log_clean_cross_tenant_customer(tenant_a, tenant_b):
    customer_b = Party.objects.create(tenant=tenant_b, name="Customer B", kind="person")
    log = SearchQueryLog(
        tenant=tenant_a,
        query_text="boots",
        normalized_query="boots",
        results_count=1,
        customer=customer_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        log.clean()
    assert "customer" in exc_info.value.message_dict


def test_searchdiscovery_query_log_clean_cross_tenant_clicked_product(tenant_a, tenant_b):
    prod_b = _searchdiscovery_make_product(tenant_b, name="Clicked Product B")
    log = SearchQueryLog(
        tenant=tenant_a,
        query_text="sandals",
        normalized_query="sandals",
        results_count=1,
        clicked_product=prod_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        log.clean()
    assert "clicked_product" in exc_info.value.message_dict
