"""Security, IDOR isolation, authorization, and audit trail tests for eCommerce 9.17 B2B & Wholesale Commerce."""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    B2bCompanyAccount,
    B2bCompanyUser,
    B2bQuoteRequest,
    B2bQuickOrderTemplate,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. Multi-Tenant IDOR Isolation Tests (Cross-Tenant 404s)
# ==============================================================================

def test_b2bwholesale_idor_company_account_detail(auth_client_a, ecom_b2b_company_b):
    """Tenant A client requesting Tenant B Company Account detail returns 404."""
    url = reverse("ecommerce:b2bcompanyaccount_detail", args=[ecom_b2b_company_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_b2bwholesale_idor_company_account_edit(auth_client_a, ecom_b2b_company_b):
    """Tenant A client requesting Tenant B Company Account edit returns 404 on GET and POST."""
    url = reverse("ecommerce:b2bcompanyaccount_edit", args=[ecom_b2b_company_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"company_name": "Tampered Name"}).status_code == 404

    ecom_b2b_company_b.refresh_from_db()
    assert ecom_b2b_company_b.company_name != "Tampered Name"


def test_b2bwholesale_idor_company_account_delete(auth_client_a, ecom_b2b_company_b):
    """Tenant A client POSTing to Tenant B Company Account delete returns 404 and does not delete."""
    url = reverse("ecommerce:b2bcompanyaccount_delete", args=[ecom_b2b_company_b.pk])
    assert auth_client_a.post(url).status_code == 404
    assert B2bCompanyAccount.objects.filter(pk=ecom_b2b_company_b.pk).exists() is True


def test_b2bwholesale_idor_company_account_punchout(auth_client_a, ecom_b2b_company_b):
    """Tenant A client POSTing to Tenant B punchout test simulator returns 404."""
    url = reverse("ecommerce:b2bcompanyaccount_punchout_test", args=[ecom_b2b_company_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url).status_code == 404


def test_b2bwholesale_idor_company_user_detail(auth_client_a, ecom_b2b_user_b):
    """Tenant A client requesting Tenant B Company User detail returns 404."""
    url = reverse("ecommerce:b2bcompanyuser_detail", args=[ecom_b2b_user_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_b2bwholesale_idor_company_user_edit(auth_client_a, ecom_b2b_user_b):
    """Tenant A client requesting Tenant B Company User edit returns 404 on GET and POST."""
    url = reverse("ecommerce:b2bcompanyuser_edit", args=[ecom_b2b_user_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"job_title": "Tampered Title"}).status_code == 404

    ecom_b2b_user_b.refresh_from_db()
    assert ecom_b2b_user_b.job_title != "Tampered Title"


def test_b2bwholesale_idor_company_user_delete(auth_client_a, ecom_b2b_user_b):
    """Tenant A client POSTing to Tenant B Company User delete returns 404 and does not delete."""
    url = reverse("ecommerce:b2bcompanyuser_delete", args=[ecom_b2b_user_b.pk])
    assert auth_client_a.post(url).status_code == 404
    assert B2bCompanyUser.objects.filter(pk=ecom_b2b_user_b.pk).exists() is True


def test_b2bwholesale_idor_quote_request_detail(auth_client_a, ecom_b2b_quote_b):
    """Tenant A client requesting Tenant B Quote Request detail returns 404."""
    url = reverse("ecommerce:b2bquoterequest_detail", args=[ecom_b2b_quote_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_b2bwholesale_idor_quote_request_edit(auth_client_a, ecom_b2b_quote_b):
    """Tenant A client requesting Tenant B Quote Request edit returns 404 on GET and POST."""
    url = reverse("ecommerce:b2bquoterequest_edit", args=[ecom_b2b_quote_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"buyer_notes": "Tampered Notes"}).status_code == 404


def test_b2bwholesale_idor_quote_request_workflow_actions(auth_client_a, ecom_b2b_quote_b):
    """Tenant A client POSTing to Tenant B quote workflow actions returns 404."""
    for action in ["submit", "quote", "accept", "reject", "convert_order"]:
        url = reverse(f"ecommerce:b2bquoterequest_{action}", args=[ecom_b2b_quote_b.pk])
        assert auth_client_a.post(url, {"quoted_discount_percent": "10.0"}).status_code == 404


def test_b2bwholesale_idor_quick_order_template_detail(auth_client_a, ecom_b2b_template_b):
    """Tenant A client requesting Tenant B Quick Order Template detail returns 404."""
    url = reverse("ecommerce:b2bquickordertemplate_detail", args=[ecom_b2b_template_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_b2bwholesale_idor_quick_order_template_edit(auth_client_a, ecom_b2b_template_b):
    """Tenant A client requesting Tenant B Quick Order Template edit returns 404."""
    url = reverse("ecommerce:b2bquickordertemplate_edit", args=[ecom_b2b_template_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"name": "Tampered Template"}).status_code == 404


def test_b2bwholesale_idor_quick_order_template_delete(auth_client_a, ecom_b2b_template_b):
    """Tenant A client POSTing to Tenant B Quick Order Template delete returns 404 and does not delete."""
    url = reverse("ecommerce:b2bquickordertemplate_delete", args=[ecom_b2b_template_b.pk])
    assert auth_client_a.post(url).status_code == 404
    assert B2bQuickOrderTemplate.objects.filter(pk=ecom_b2b_template_b.pk).exists() is True


# ==============================================================================
# 2. Tenant Isolation in List Views
# ==============================================================================

def test_b2bwholesale_tenant_isolation_in_lists(
    auth_client_a,
    tenant_a,
    tenant_b,
    ecom_b2b_company_a,
    ecom_b2b_company_b,
    ecom_b2b_user_a,
    ecom_b2b_user_b,
    ecom_b2b_quote_a,
    ecom_b2b_quote_b,
    ecom_b2b_template_a,
    ecom_b2b_template_b,
):
    """Tenant A sees only its own companies, users, quotes, templates; Tenant B records excluded."""
    # Companies
    res_co = auth_client_a.get(reverse("ecommerce:b2bcompanyaccount_list"))
    co_pks = {c.pk for c in res_co.context["company_accounts"]}
    assert ecom_b2b_company_a.pk in co_pks
    assert ecom_b2b_company_b.pk not in co_pks

    # Users
    res_usr = auth_client_a.get(reverse("ecommerce:b2bcompanyuser_list"))
    usr_pks = {u.pk for u in res_usr.context["company_users"]}
    assert ecom_b2b_user_a.pk in usr_pks
    assert ecom_b2b_user_b.pk not in usr_pks

    # Quotes
    res_qr = auth_client_a.get(reverse("ecommerce:b2bquoterequest_list"))
    qr_pks = {q.pk for q in res_qr.context["quote_requests"]}
    assert ecom_b2b_quote_a.pk in qr_pks
    assert ecom_b2b_quote_b.pk not in qr_pks

    # Templates
    res_tmpl = auth_client_a.get(reverse("ecommerce:b2bquickordertemplate_list"))
    tmpl_pks = {t.pk for t in res_tmpl.context["quick_order_templates"]}
    assert ecom_b2b_template_a.pk in tmpl_pks
    assert ecom_b2b_template_b.pk not in tmpl_pks


# ==============================================================================
# 3. Unauthenticated Access Protection
# ==============================================================================

def test_b2bwholesale_unauthenticated_redirects(client, ecom_b2b_company_a):
    """Anonymous requests to protected endpoints redirect to login (302)."""
    protected_urls = [
        reverse("ecommerce:b2b_wholesale_hub"),
        reverse("ecommerce:b2bcompanyaccount_list"),
        reverse("ecommerce:b2bcompanyaccount_create"),
        reverse("ecommerce:b2bcompanyaccount_detail", args=[ecom_b2b_company_a.pk]),
        reverse("ecommerce:b2bcompanyuser_list"),
        reverse("ecommerce:b2bquoterequest_list"),
        reverse("ecommerce:b2bquickordertemplate_list"),
        reverse("ecommerce:b2b_quick_order_matrix"),
    ]
    for url in protected_urls:
        res = client.get(url)
        assert res.status_code == 302
        assert "/accounts/login/" in res.url or "/login/" in res.url
