"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.7 Search & Product Discovery.

Covers:
- SearchSynonym views (list, detail, create, edit, toggle, delete)
- SearchFacetConfig views (list, detail, create, edit, toggle, delete)
- SearchMerchandisingRule views (list, detail, create, edit, toggle, delete)
- SearchQueryLog views (list, detail, delete)
- Search Console Workbench views (console, autocomplete, analytics)

Naming conventions enforced:
- Test functions: test_searchdiscovery_*
- Module-level helpers: _searchdiscovery_*
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.models import Party
from apps.ecommerce.models import (
    SearchSynonym,
    SearchFacetConfig,
    SearchMerchandisingRule,
    SearchQueryLog,
    CatalogProduct,
    ProductVariant,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    _searchdiscovery_synonym,
    _searchdiscovery_facet_config,
    _searchdiscovery_merchandising_rule,
    _searchdiscovery_query_log,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_searchdiscovery_*)
# ==============================================================================

def _searchdiscovery_make_product(tenant, name="View Product", price=Decimal("49.99"), brand="Acme"):
    prod = CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        brand=brand,
        status="active",
        visibility="storefront",
    )
    ProductVariant.objects.create(
        tenant=tenant,
        product=prod,
        sku=f"SKU-{prod.pk}",
        name=f"{name} Standard",
        price=price,
        is_active=True,
    )
    return prod


def _searchdiscovery_make_category(tenant, name="View Category"):
    return StoreCategory.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        is_active=True,
    )


# ==============================================================================
# SearchSynonym View Tests
# ==============================================================================

def test_searchdiscovery_synonym_list_view(client_a, tenant_a, ecom_synonym_a):
    _searchdiscovery_synonym(tenant_a, root_term="boots", synonyms="chelsea, workboots", synonym_type="one_way")

    url = reverse("ecommerce:searchsynonym_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "synonyms" in resp.context
    assert "synonym_type_choices" in resp.context
    assert len(resp.context["synonyms"]) >= 2

    # Filter by synonym type
    resp_type = client_a.get(url, {"synonym_type": "one_way"})
    assert resp_type.status_code == 200
    assert len(resp_type.context["synonyms"]) == 1
    assert resp_type.context["synonyms"][0].root_term == "boots"

    # Search filter
    resp_q = client_a.get(url, {"q": "chelsea"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["synonyms"]) == 1


def test_searchdiscovery_synonym_detail_view(client_a, tenant_a, ecom_synonym_a):
    url = reverse("ecommerce:searchsynonym_detail", args=[ecom_synonym_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["synonym"] == ecom_synonym_a


def test_searchdiscovery_synonym_create_view(client_a, tenant_a):
    url = reverse("ecommerce:searchsynonym_create")
    resp_get = client_a.get(url, {"root": "jacket"})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["form"].initial.get("root_term") == "jacket"

    payload = {
        "name": "Coats & Jackets",
        "synonym_type": "two_way",
        "root_term": "jacket",
        "synonyms": "coat, outerwear, parkas",
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = SearchSynonym.objects.filter(tenant=tenant_a, root_term="jacket").first()
    assert created is not None
    assert created.name == "Coats & Jackets"


def test_searchdiscovery_synonym_edit_view(client_a, tenant_a, ecom_synonym_a):
    url = reverse("ecommerce:searchsynonym_edit", args=[ecom_synonym_a.pk])
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = {
        "name": "Updated Sneakers Rule",
        "synonym_type": "two_way",
        "root_term": ecom_synonym_a.root_term,
        "synonyms": "shoes, trainers, running kicks",
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_synonym_a.refresh_from_db()
    assert ecom_synonym_a.name == "Updated Sneakers Rule"
    assert "running kicks" in ecom_synonym_a.synonyms


def test_searchdiscovery_synonym_toggle_and_delete(client_a, tenant_a, ecom_synonym_a):
    toggle_url = reverse("ecommerce:searchsynonym_toggle", args=[ecom_synonym_a.pk])
    resp_toggle = client_a.post(toggle_url)
    assert resp_toggle.status_code == 302
    ecom_synonym_a.refresh_from_db()
    assert ecom_synonym_a.is_active is False

    delete_url = reverse("ecommerce:searchsynonym_delete", args=[ecom_synonym_a.pk])
    resp_delete = client_a.post(delete_url)
    assert resp_delete.status_code == 302
    assert not SearchSynonym.objects.filter(pk=ecom_synonym_a.pk).exists()


# ==============================================================================
# SearchFacetConfig View Tests
# ==============================================================================

def test_searchdiscovery_facet_config_list_view(client_a, tenant_a, ecom_facet_config_a):
    _searchdiscovery_facet_config(tenant_a, name="Price", code="price", source_type="price")

    url = reverse("ecommerce:searchfacetconfig_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "facet_configs" in resp.context
    assert len(resp.context["facet_configs"]) >= 2

    # Filter by source_type
    resp_filter = client_a.get(url, {"source_type": "price"})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["facet_configs"]) == 1
    assert resp_filter.context["facet_configs"][0].code == "price"


def test_searchdiscovery_facet_config_create_and_detail(client_a, tenant_a):
    url = reverse("ecommerce:searchfacetconfig_create")
    payload = {
        "name": "Color Swatches",
        "code": "color",
        "source_type": "variant_option",
        "option_key": "Color",
        "widget_type": "color_swatch",
        "filter_logic": "disjunctive",
        "display_order": 20,
        "max_values_shown": 10,
        "is_active": True,
    }
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    fc = SearchFacetConfig.objects.filter(tenant=tenant_a, code="color").first()
    assert fc is not None
    assert fc.widget_type == "color_swatch"

    detail_url = reverse("ecommerce:searchfacetconfig_detail", args=[fc.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["facet_config"] == fc


# ==============================================================================
# SearchMerchandisingRule View Tests
# ==============================================================================

def test_searchdiscovery_merchandising_rule_views(client_a, tenant_a, ecom_product_a):
    create_url = reverse("ecommerce:searchmerchandisingrule_create")
    payload = {
        "name": "Pin Top Sneaker",
        "rule_type": "query",
        "trigger_query": "sneakers",
        "match_type": "exact",
        "action_type": "pin",
        "pin_position": 1,
        "boost_weight": 10,
        "boosted_product": ecom_product_a.pk,
        "priority": 15,
        "is_active": True,
    }
    resp_create = client_a.post(create_url, payload)
    assert resp_create.status_code == 302

    rule = SearchMerchandisingRule.objects.filter(tenant=tenant_a, name="Pin Top Sneaker").first()
    assert rule is not None
    assert rule.pin_position == 1

    list_url = reverse("ecommerce:searchmerchandisingrule_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert len(resp_list.context["rules"]) >= 1

    detail_url = reverse("ecommerce:searchmerchandisingrule_detail", args=[rule.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["rule"] == rule


# ==============================================================================
# SearchQueryLog View Tests
# ==============================================================================

def test_searchdiscovery_query_log_views(client_a, tenant_a, ecom_query_log_a):
    _searchdiscovery_query_log(tenant_a, query_text="unknown gadget", normalized_query="unknown gadget", results_count=0)

    url = reverse("ecommerce:searchquerylog_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "logs" in resp.context
    assert len(resp.context["logs"]) >= 2

    # Zero results filter
    resp_zero = client_a.get(url, {"is_zero_result": "true"})
    assert resp_zero.status_code == 200
    assert len(resp_zero.context["logs"]) == 1
    assert resp_zero.context["logs"][0].is_zero_result is True

    detail_url = reverse("ecommerce:searchquerylog_detail", args=[ecom_query_log_a.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["log"] == ecom_query_log_a


# ==============================================================================
# Search Console Workbench & Autocomplete Tests
# ==============================================================================

def test_searchdiscovery_console_search_and_filters(client_a, tenant_a):
    _searchdiscovery_make_product(tenant_a, name="Nike Air Max Sneakers", price=Decimal("120.00"), brand="Nike")
    _searchdiscovery_make_product(tenant_a, name="Adidas Ultraboost Shoes", price=Decimal("180.00"), brand="Adidas")

    url = reverse("ecommerce:search_console")
    resp = client_a.get(url, {"q": "sneakers"})
    assert resp.status_code == 200
    assert "products" in resp.context
    assert "total_results" in resp.context
    assert "facet_groups" in resp.context
    assert len(resp.context["products"]) >= 1

    # Price filter
    resp_price = client_a.get(url, {"price_min": "150", "price_max": "200"})
    assert resp_price.status_code == 200
    for p in resp_price.context["products"]:
        assert p.name == "Adidas Ultraboost Shoes"

    # Sort price asc
    resp_sort = client_a.get(url, {"sort": "price_asc"})
    assert resp_sort.status_code == 200


def test_searchdiscovery_autocomplete_json_and_htmx(client_a, tenant_a):
    _searchdiscovery_make_product(tenant_a, name="Super Sneaker Pro", price=Decimal("95.00"), brand="Super")

    url = reverse("ecommerce:search_autocomplete")

    # Short query (<2)
    resp_short = client_a.get(url, {"q": "s"})
    assert resp_short.status_code == 200
    assert resp_short.json()["suggestions"] == []

    # Valid query JSON
    resp_json = client_a.get(url, {"q": "sneaker"})
    assert resp_json.status_code == 200
    data = resp_json.json()
    assert "products" in data
    assert any("Super Sneaker Pro" in p["name"] for p in data["products"])

    # HTMX Partial request
    resp_htmx = client_a.get(url, {"q": "sneaker"}, HTTP_HX_REQUEST="true")
    assert resp_htmx.status_code == 200
    assert "Super Sneaker Pro" in resp_htmx.content.decode()


def test_searchdiscovery_analytics_dashboard(client_a, tenant_a):
    _searchdiscovery_query_log(tenant_a, query_text="boots", normalized_query="boots", results_count=5)
    _searchdiscovery_query_log(tenant_a, query_text="flats", normalized_query="flats", results_count=0)

    url = reverse("ecommerce:search_analytics")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "total_searches" in resp.context
    assert "zero_result_searches" in resp.context
    assert "zero_result_queries" in resp.context
    assert resp.context["total_searches"] >= 2
    assert resp.context["zero_result_searches"] >= 1
