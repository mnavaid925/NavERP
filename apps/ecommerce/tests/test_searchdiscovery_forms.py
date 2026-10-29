"""Form validation, exclusion, and tenant isolation tests for eCommerce 9.7 Search & Product Discovery.

Covers:
- SearchSynonymForm
- SearchFacetConfigForm
- SearchMerchandisingRuleForm
- SearchQueryLogForm
- SearchQueryLogFilterForm

Naming conventions enforced:
- Test functions: test_searchdiscovery_*
- Module-level helpers: _searchdiscovery_*
"""
import pytest
from django import forms

from apps.core.models import Party
from apps.ecommerce.forms.SearchDiscovery.SearchSynonyms import SearchSynonymForm
from apps.ecommerce.forms.SearchDiscovery.SearchFacetConfigs import SearchFacetConfigForm
from apps.ecommerce.forms.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRuleForm
from apps.ecommerce.forms.SearchDiscovery.SearchQueryLogs import (
    SearchQueryLogForm,
    SearchQueryLogFilterForm,
)
from apps.ecommerce.models import (
    SearchSynonym,
    SearchFacetConfig,
    SearchMerchandisingRule,
    SearchQueryLog,
    CatalogProduct,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    SEARCHDISCOVERY_FORM_FIELDS,
    _searchdiscovery_synonym,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_searchdiscovery_*)
# ==============================================================================

def _searchdiscovery_make_product(tenant, name="Form Product"):
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        status="active",
    )


def _searchdiscovery_make_category(tenant, name="Form Category"):
    return StoreCategory.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
    )


# ==============================================================================
# Form Contract & Exclusion Tests
# ==============================================================================

def test_searchdiscovery_form_fields_contract():
    form_classes = {
        "SearchSynonymForm": SearchSynonymForm,
        "SearchFacetConfigForm": SearchFacetConfigForm,
        "SearchMerchandisingRuleForm": SearchMerchandisingRuleForm,
        "SearchQueryLogFilterForm": SearchQueryLogFilterForm,
    }
    for form_name, expected_fields in SEARCHDISCOVERY_FORM_FIELDS.items():
        cls = form_classes[form_name]
        if hasattr(cls, "Meta") and hasattr(cls.Meta, "fields"):
            actual_fields = tuple(cls.Meta.fields)
        else:
            actual_fields = tuple(cls.base_fields.keys())
        assert actual_fields == expected_fields, f"Field mismatch on {form_name}"


def test_searchdiscovery_form_exclusions_prevent_mass_assignment():
    # SearchSynonymForm
    syn_fields = SearchSynonymForm.Meta.fields
    for forbidden in ("tenant", "number", "hit_count", "created_at", "updated_at"):
        assert forbidden not in syn_fields, f"{forbidden} must be excluded from SearchSynonymForm"

    # SearchFacetConfigForm
    fc_fields = SearchFacetConfigForm.Meta.fields
    for forbidden in ("tenant", "number", "created_at", "updated_at"):
        assert forbidden not in fc_fields, f"{forbidden} must be excluded from SearchFacetConfigForm"

    # SearchMerchandisingRuleForm
    rule_fields = SearchMerchandisingRuleForm.Meta.fields
    for forbidden in ("tenant", "number", "created_at", "updated_at"):
        assert forbidden not in rule_fields, f"{forbidden} must be excluded from SearchMerchandisingRuleForm"

    # SearchQueryLogForm
    log_fields = SearchQueryLogForm.Meta.fields
    for forbidden in ("tenant", "number", "execution_time_ms", "ip_address", "created_at", "updated_at"):
        assert forbidden not in log_fields, f"{forbidden} must be excluded from SearchQueryLogForm"


# ==============================================================================
# SearchSynonymForm Tests
# ==============================================================================

def test_searchdiscovery_synonym_form_valid(tenant_a):
    form = SearchSynonymForm(
        data={
            "name": "Shoes Synonyms",
            "synonym_type": "two_way",
            "root_term": "shoes",
            "synonyms": "sneakers, trainers, kicks",
            "is_active": True,
            "notes": "Valid test note",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a


def test_searchdiscovery_synonym_form_empty_synonyms(tenant_a):
    form = SearchSynonymForm(
        data={
            "name": "Empty Synonyms",
            "synonym_type": "two_way",
            "root_term": "jacket",
            "synonyms": "   ",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "synonyms" in form.errors


# ==============================================================================
# SearchFacetConfigForm Tests
# ==============================================================================

def test_searchdiscovery_facet_config_form_valid(tenant_a):
    cat_a = _searchdiscovery_make_category(tenant_a, "Shoes Category")
    form = SearchFacetConfigForm(
        data={
            "name": "Brand",
            "code": "brand",
            "source_type": "brand",
            "widget_type": "checkbox",
            "filter_logic": "disjunctive",
            "display_order": 5,
            "max_values_shown": 10,
            "category_scope": cat_a.pk,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.category_scope == cat_a


def test_searchdiscovery_facet_config_form_rejects_foreign_tenant_category(tenant_a, tenant_b):
    cat_b = _searchdiscovery_make_category(tenant_b, "Competitor Category")
    form = SearchFacetConfigForm(
        data={
            "name": "Brand",
            "code": "brand_injected",
            "source_type": "brand",
            "widget_type": "checkbox",
            "filter_logic": "disjunctive",
            "display_order": 5,
            "max_values_shown": 10,
            "category_scope": cat_b.pk,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "category_scope" in form.errors


# ==============================================================================
# SearchMerchandisingRuleForm Tests
# ==============================================================================

def test_searchdiscovery_merchandising_rule_form_valid(tenant_a, ecom_product_a):
    form = SearchMerchandisingRuleForm(
        data={
            "name": "Boost Sneaker Rule",
            "rule_type": "query",
            "trigger_query": "running shoes",
            "match_type": "exact",
            "action_type": "boost",
            "boosted_product": ecom_product_a.pk,
            "boost_weight": 30,
            "priority": 10,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a


def test_searchdiscovery_merchandising_rule_form_rejects_dangerous_redirect_url(tenant_a):
    form = SearchMerchandisingRuleForm(
        data={
            "name": "Malicious Redirect",
            "rule_type": "query",
            "trigger_query": "hacked",
            "match_type": "exact",
            "action_type": "redirect",
            "redirect_url": "javascript:alert('xss')",
            "priority": 1,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "redirect_url" in form.errors


def test_searchdiscovery_merchandising_rule_form_rejects_protocol_relative_url(tenant_a):
    form = SearchMerchandisingRuleForm(
        data={
            "name": "Protocol Relative Redirect",
            "rule_type": "query",
            "trigger_query": "offsite",
            "match_type": "exact",
            "action_type": "redirect",
            "redirect_url": "//evil.com/phish",
            "priority": 1,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "redirect_url" in form.errors


def test_searchdiscovery_merchandising_rule_form_rejects_foreign_product(tenant_a, tenant_b):
    prod_b = _searchdiscovery_make_product(tenant_b, "Competitor Product")
    form = SearchMerchandisingRuleForm(
        data={
            "name": "Cross Tenant Product Rule",
            "rule_type": "query",
            "trigger_query": "boots",
            "match_type": "exact",
            "action_type": "boost",
            "boosted_product": prod_b.pk,
            "boost_weight": 10,
            "priority": 1,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "boosted_product" in form.errors


# ==============================================================================
# SearchQueryLogFilterForm Tests
# ==============================================================================

def test_searchdiscovery_query_log_filter_form_valid():
    form = SearchQueryLogFilterForm(
        data={
            "q": "shoes",
            "is_zero_result": "true",
            "sort_order": "relevance",
        }
    )
    assert form.is_valid()
    assert form.cleaned_data["q"] == "shoes"
    assert form.cleaned_data["is_zero_result"] == "true"
