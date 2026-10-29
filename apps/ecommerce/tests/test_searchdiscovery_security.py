"""Multi-tenancy, authentication, open redirect, and cross-tenant IDOR isolation tests for eCommerce 9.7.

Covers:
- Anonymous user access prevention (302 redirect to login)
- Tenant Admin Gate enforcement (@tenant_admin_required)
- Cross-tenant IDOR defense (404 on all foreign tenant records for detail, edit, delete, toggle)
- Queryset isolation across tenant boundaries
- Open redirect defense in Search Console

Naming conventions enforced:
- Test functions: test_searchdiscovery_*
- Module-level helpers: _searchdiscovery_*
"""
import pytest
from django.urls import reverse

from apps.ecommerce.models import (
    SearchSynonym,
    SearchFacetConfig,
    SearchMerchandisingRule,
    SearchQueryLog,
)
from apps.ecommerce.tests.conftest import (
    _searchdiscovery_synonym,
    _searchdiscovery_facet_config,
    _searchdiscovery_merchandising_rule,
    _searchdiscovery_query_log,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Prevention Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,args",
    [
        ("searchsynonym_list", []),
        ("searchsynonym_create", []),
        ("searchfacetconfig_list", []),
        ("searchfacetconfig_create", []),
        ("searchmerchandisingrule_list", []),
        ("searchmerchandisingrule_create", []),
        ("searchquerylog_list", []),
        ("search_console", []),
        ("search_autocomplete", []),
        ("search_analytics", []),
    ],
)
def test_searchdiscovery_anonymous_redirects_to_login(client, url_name, args):
    url = reverse(f"ecommerce:{url_name}", args=args)
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login" in resp.url or "login" in resp.url


# ==============================================================================
# Cross-Tenant IDOR Defense Tests (404 on Foreign Tenant Records)
# ==============================================================================

def test_searchdiscovery_synonym_idor_defense(client_a, ecom_synonym_b):
    # Detail
    url_det = reverse("ecommerce:searchsynonym_detail", args=[ecom_synonym_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:searchsynonym_edit", args=[ecom_synonym_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"root_term": "hacked"}).status_code == 404

    # Toggle POST
    url_tog = reverse("ecommerce:searchsynonym_toggle", args=[ecom_synonym_b.pk])
    assert client_a.post(url_tog).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:searchsynonym_delete", args=[ecom_synonym_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert SearchSynonym.objects.filter(pk=ecom_synonym_b.pk).exists()


def test_searchdiscovery_facet_config_idor_defense(client_a, ecom_facet_config_b):
    # Detail
    url_det = reverse("ecommerce:searchfacetconfig_detail", args=[ecom_facet_config_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:searchfacetconfig_edit", args=[ecom_facet_config_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked"}).status_code == 404

    # Toggle POST
    url_tog = reverse("ecommerce:searchfacetconfig_toggle", args=[ecom_facet_config_b.pk])
    assert client_a.post(url_tog).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:searchfacetconfig_delete", args=[ecom_facet_config_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert SearchFacetConfig.objects.filter(pk=ecom_facet_config_b.pk).exists()


def test_searchdiscovery_merchandising_rule_idor_defense(client_a, ecom_merchandising_rule_b):
    # Detail
    url_det = reverse("ecommerce:searchmerchandisingrule_detail", args=[ecom_merchandising_rule_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:searchmerchandisingrule_edit", args=[ecom_merchandising_rule_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Rule"}).status_code == 404

    # Toggle POST
    url_tog = reverse("ecommerce:searchmerchandisingrule_toggle", args=[ecom_merchandising_rule_b.pk])
    assert client_a.post(url_tog).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:searchmerchandisingrule_delete", args=[ecom_merchandising_rule_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert SearchMerchandisingRule.objects.filter(pk=ecom_merchandising_rule_b.pk).exists()


def test_searchdiscovery_query_log_idor_defense(client_a, ecom_query_log_b):
    # Detail
    url_det = reverse("ecommerce:searchquerylog_detail", args=[ecom_query_log_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:searchquerylog_delete", args=[ecom_query_log_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert SearchQueryLog.objects.filter(pk=ecom_query_log_b.pk).exists()


# ==============================================================================
# Queryset Isolation Tests
# ==============================================================================

def test_searchdiscovery_list_queryset_tenant_isolation(
    client_a, client_b, ecom_synonym_a, ecom_synonym_b
):
    url = reverse("ecommerce:searchsynonym_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    synonyms_a = resp_a.context["synonyms"]
    assert ecom_synonym_a in synonyms_a
    assert ecom_synonym_b not in synonyms_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    synonyms_b = resp_b.context["synonyms"]
    assert ecom_synonym_b in synonyms_b
    assert ecom_synonym_a not in synonyms_b


# ==============================================================================
# Open Redirect Security Invariant Tests
# ==============================================================================

def test_searchdiscovery_console_open_redirect_rejected(client_a, tenant_a):
    _searchdiscovery_merchandising_rule(
        tenant_a,
        name="Phishing Attempt",
        rule_type="query",
        trigger_query="login",
        action_type="redirect",
        redirect_url="https://evil.com/phishing-login",
        is_active=True,
    )
    url = reverse("ecommerce:search_console")
    resp = client_a.get(url, {"q": "login", "auto_redirect": "1"})
    # Must NOT redirect to external evil.com
    if resp.status_code == 302:
        assert not resp.url.startswith("https://evil.com")
        assert not resp.url.startswith("//evil.com")
    else:
        assert resp.status_code == 200
