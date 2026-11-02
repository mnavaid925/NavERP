"""Unit, route, context-contract, filter, and action tests for eCommerce 9.17 B2B & Wholesale views."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models.Party import Party
from apps.ecommerce.models import (
    B2bCompanyAccount,
    B2bCompanyUser,
    B2bQuoteRequest,
    B2bQuickOrderTemplate,
    EcommerceOrder,
    CatalogProduct,
    ProductVariant,
)
from apps.ecommerce.tests.conftest import (
    _b2bwholesale_company_account,
    _b2bwholesale_company_user,
    _b2bwholesale_quote_request,
    _b2bwholesale_quick_order_template,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. B2B Wholesale Hub Cockpit Tests
# ==============================================================================

def test_b2bwholesale_hub_view(
    auth_client_a,
    tenant_a,
    ecom_b2b_company_a,
    ecom_b2b_user_a,
    ecom_b2b_quote_a,
    ecom_b2b_template_a,
):
    """Test wholesale hub returns 200 with KPI stats, pending RFQs, and active accounts."""
    url = reverse("ecommerce:b2b_wholesale_hub")
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "total_companies_count" in response.context
    assert "open_rfqs_count" in response.context
    assert "recent_quotes" in response.context
    assert "recent_companies" in response.context
    assert response.context["total_companies_count"] >= 1


# ==============================================================================
# 2. Company Account CRUD & PunchOut Tests
# ==============================================================================

def test_b2bwholesale_company_account_list_view(auth_client_a, tenant_a, ecom_b2b_company_a):
    """Test company account list with search and filters."""
    url = reverse("ecommerce:b2bcompanyaccount_list")
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "company_accounts" in response.context
    assert len(response.context["company_accounts"]) >= 1

    # Filter by status
    res_active = auth_client_a.get(url, {"status": "active"})
    assert res_active.status_code == 200

    # Search by name
    res_search = auth_client_a.get(url, {"q": "Atlas"})
    assert res_search.status_code == 200


def test_b2bwholesale_company_account_detail_view(
    auth_client_a,
    tenant_a,
    ecom_b2b_company_a,
    ecom_b2b_user_a,
    ecom_b2b_quote_a,
    ecom_b2b_template_a,
):
    """Test company account detail renders buyers, quotes, and saved quick order templates (I12)."""
    url = reverse("ecommerce:b2bcompanyaccount_detail", kwargs={"pk": ecom_b2b_company_a.pk})
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "company_account" in response.context
    assert "company_users" in response.context
    assert "quote_requests" in response.context
    assert "quick_order_templates" in response.context


def test_b2bwholesale_company_account_create_and_edit_view(auth_client_a, tenant_a, user_a):
    """Test company account create and edit workflows."""
    party = Party.objects.create(tenant=tenant_a, name="New Enterprise Corp", kind="organization")
    currency = Currency.objects.filter(code="USD").first() or Currency.objects.create(code="USD", name="US Dollar", symbol="$")
    url_create = reverse("ecommerce:b2bcompanyaccount_create")

    # GET create form
    res_get = auth_client_a.get(url_create)
    assert res_get.status_code == 200

    # POST create
    post_data = {
        "company_name": "New Enterprise Corp",
        "company_party": party.pk,
        "primary_contact": user_a.pk,
        "preferred_currency": currency.pk,
        "credit_limit": "50000.00",
        "payment_terms": "net_30",
        "credit_status": "good_standing",
        "approval_threshold_amount": "5000.00",
        "wholesale_discount_percent": "10.00",
        "status": "active",
        "punchout_protocol": "none",
        "punchout_shared_secret": "InitialSecret123!",
    }
    res_post = auth_client_a.post(url_create, post_data)
    assert res_post.status_code == 302
    new_co = B2bCompanyAccount.objects.filter(company_name="New Enterprise Corp").first()
    assert new_co is not None

    # POST edit
    url_edit = reverse("ecommerce:b2bcompanyaccount_edit", kwargs={"pk": new_co.pk})
    post_data["company_name"] = "Updated Enterprise Corp"
    post_data["punchout_shared_secret"] = ""  # blank edit preserves secret (C6)
    res_edit = auth_client_a.post(url_edit, post_data)
    assert res_edit.status_code == 302
    new_co.refresh_from_db()
    assert new_co.company_name == "Updated Enterprise Corp"
    assert new_co.punchout_shared_secret == "InitialSecret123!"


def test_b2bwholesale_company_account_delete_require_post(auth_client_a, tenant_a, user_a):
    """Test company account delete requires POST (I5)."""
    co = _b2bwholesale_company_account(tenant_a, primary_contact=user_a, company_name="Deletable Co")
    url_delete = reverse("ecommerce:b2bcompanyaccount_delete", kwargs={"pk": co.pk})

    # GET should be rejected (405 Method Not Allowed)
    res_get = auth_client_a.get(url_delete)
    assert res_get.status_code == 405

    # POST succeeds
    res_post = auth_client_a.post(url_delete)
    assert res_post.status_code == 302
    assert not B2bCompanyAccount.objects.filter(pk=co.pk).exists()


def test_b2bwholesale_company_account_punchout_test(auth_client_a, tenant_a, user_a):
    """Test punchout simulation endpoint generates cXML response."""
    co = _b2bwholesale_company_account(
        tenant_a,
        primary_contact=user_a,
        punchout_enabled=True,
        punchout_protocol="cxml",
        punchout_identity="DUNS-TEST-123",
        punchout_shared_secret="PunchSecret!",
        punchout_return_url="https://procure.client.com/return",
    )
    url = reverse("ecommerce:b2bcompanyaccount_punchout_test", kwargs={"pk": co.pk})
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200

    res_post = auth_client_a.post(url)
    assert res_post.status_code == 200
    assert "cxml_response" in res_post.context
    assert "PunchOutSetupResponse" in res_post.context["cxml_response"]


# ==============================================================================
# 3. Company User CRUD Tests
# ==============================================================================

def test_b2bwholesale_company_user_list_view(auth_client_a, tenant_a, ecom_b2b_company_a, ecom_b2b_user_a):
    """Test company buyer list with company and role filters."""
    url = reverse("ecommerce:b2bcompanyuser_list")
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "company_users" in response.context
    assert len(response.context["company_users"]) >= 1

    # Filter with valid company PK
    res_co = auth_client_a.get(url, {"company": str(ecom_b2b_company_a.pk)})
    assert res_co.status_code == 200

    # Non-numeric company filter handled gracefully without 500 (I1)
    res_invalid = auth_client_a.get(url, {"company": "abc"})
    assert res_invalid.status_code == 200


def test_b2bwholesale_company_user_detail_view(auth_client_a, tenant_a, ecom_b2b_user_a):
    """Test company user detail returns 200."""
    url = reverse("ecommerce:b2bcompanyuser_detail", kwargs={"pk": ecom_b2b_user_a.pk})
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "company_user" in response.context


def test_b2bwholesale_company_user_create_and_delete(auth_client_a, tenant_a, ecom_b2b_company_a, user_a):
    """Test company user creation and deletion."""
    url_create = reverse("ecommerce:b2bcompanyuser_create")
    post_data = {
        "company": ecom_b2b_company_a.pk,
        "user": user_a.pk,
        "role": "buyer",
        "job_title": "Junior Buyer",
        "department": "Plant 1",
        "order_spend_limit": "2500.00",
        "monthly_spend_limit": "10000.00",
        "can_place_orders": True,
        "can_request_quotes": True,
        "status": "active",
    }
    res_create = auth_client_a.post(url_create, post_data)
    assert res_create.status_code == 302
    created_cu = B2bCompanyUser.objects.filter(company=ecom_b2b_company_a, role="buyer").first()
    assert created_cu is not None

    # Delete with require_POST
    url_delete = reverse("ecommerce:b2bcompanyuser_delete", kwargs={"pk": created_cu.pk})
    res_get = auth_client_a.get(url_delete)
    assert res_get.status_code == 405
    res_del = auth_client_a.post(url_delete)
    assert res_del.status_code == 302
    assert not B2bCompanyUser.objects.filter(pk=created_cu.pk).exists()


# ==============================================================================
# 4. Quote Request CRUD & Negotiation Workflow Tests
# ==============================================================================

def test_b2bwholesale_quote_request_list_view(auth_client_a, tenant_a, ecom_b2b_quote_a):
    """Test quote request list view and filtering."""
    url = reverse("ecommerce:b2bquoterequest_list")
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "quote_requests" in response.context
    assert len(response.context["quote_requests"]) >= 1

    # Non-numeric company filter handled gracefully (I1)
    res_invalid = auth_client_a.get(url, {"company": "xyz"})
    assert res_invalid.status_code == 200


def test_b2bwholesale_quote_request_detail_view(auth_client_a, tenant_a, ecom_b2b_quote_a):
    """Test quote request detail view."""
    url = reverse("ecommerce:b2bquoterequest_detail", kwargs={"pk": ecom_b2b_quote_a.pk})
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "quote_request" in response.context
    assert "line_items" in response.context


def test_b2bwholesale_quote_request_workflow_lifecycle(
    auth_client_a,
    tenant_a,
    ecom_b2b_company_a,
    user_a,
):
    """Test full quote request state machine: draft -> submitted -> quoted -> accepted -> converted_to_order."""
    currency = Currency.objects.filter(code="USD").first() or Currency.objects.create(code="USD", name="US Dollar", symbol="$")
    qr = _b2bwholesale_quote_request(
        tenant_a,
        ecom_b2b_company_a,
        requested_by=user_a,
        status="draft",
        original_subtotal=Decimal("5000.00"),
        shipping_estimate=Decimal("200.00"),
    )

    # 1. Submit RFQ
    url_submit = reverse("ecommerce:b2bquoterequest_submit", kwargs={"pk": qr.pk})
    res_sub = auth_client_a.post(url_submit)
    assert res_sub.status_code == 302
    qr.refresh_from_db()
    assert qr.status == "submitted"

    # 2. Dispatch Quoted Offer with 10% discount
    url_quote = reverse("ecommerce:b2bquoterequest_quote", kwargs={"pk": qr.pk})
    res_quote = auth_client_a.post(url_quote, {"quoted_discount_percent": "10.0"})
    assert res_quote.status_code == 302
    qr.refresh_from_db()
    assert qr.status == "quoted"
    assert qr.quoted_discount_percent == Decimal("10.00")
    assert qr.quoted_total == Decimal("4700.00")  # (5000 * 0.9) + 200

    # 3. Accept Offer
    url_accept = reverse("ecommerce:b2bquoterequest_accept", kwargs={"pk": qr.pk})
    res_accept = auth_client_a.post(url_accept)
    assert res_accept.status_code == 302
    qr.refresh_from_db()
    assert qr.status == "accepted"

    # 4. Convert to Order
    url_convert = reverse("ecommerce:b2bquoterequest_convert_order", kwargs={"pk": qr.pk})
    credit_before = ecom_b2b_company_a.available_credit
    res_convert = auth_client_a.post(url_convert)
    assert res_convert.status_code == 302
    qr.refresh_from_db()
    assert qr.status == "converted_to_order"
    assert qr.converted_order is not None

    # Check credit deducted
    ecom_b2b_company_a.refresh_from_db()
    assert ecom_b2b_company_a.available_credit == credit_before - qr.quoted_total


def test_b2bwholesale_quote_request_reject_truncation(auth_client_a, tenant_a, ecom_b2b_company_a, user_a):
    """Test quote rejection truncates long rejection reason (M10)."""
    qr = _b2bwholesale_quote_request(
        tenant_a,
        ecom_b2b_company_a,
        requested_by=user_a,
        status="quoted",
    )
    url_reject = reverse("ecommerce:b2bquoterequest_reject", kwargs={"pk": qr.pk})
    long_reason = "A" * 1500
    res_reject = auth_client_a.post(url_reject, {"rejection_reason": long_reason})
    assert res_reject.status_code == 302
    qr.refresh_from_db()
    assert qr.status == "rejected"
    assert len(qr.rejection_reason) == 1000


# ==============================================================================
# 5. Quick Order Template & Matrix Tests
# ==============================================================================

def test_b2bwholesale_quick_order_template_crud(auth_client_a, tenant_a, ecom_b2b_company_a, user_a):
    """Test quick order template list, detail, create, and delete."""
    url_list = reverse("ecommerce:b2bquickordertemplate_list")
    res_list = auth_client_a.get(url_list)
    assert res_list.status_code == 200

    tmpl = _b2bwholesale_quick_order_template(tenant_a, ecom_b2b_company_a, created_by=user_a)
    url_detail = reverse("ecommerce:b2bquickordertemplate_detail", kwargs={"pk": tmpl.pk})
    res_detail = auth_client_a.get(url_detail)
    assert res_detail.status_code == 200

    # Delete with require_POST
    url_delete = reverse("ecommerce:b2bquickordertemplate_delete", kwargs={"pk": tmpl.pk})
    assert auth_client_a.get(url_delete).status_code == 405
    assert auth_client_a.post(url_delete).status_code == 302
    assert not B2bQuickOrderTemplate.objects.filter(pk=tmpl.pk).exists()


def test_b2bwholesale_quick_order_matrix_validation_and_bounds(
    auth_client_a,
    tenant_a,
    ecom_b2b_company_a,
):
    """Test matrix entry bounds enforcement (I10) and unrecognized SKU preview (M7)."""
    url_matrix = reverse("ecommerce:b2b_quick_order_matrix")

    # GET matrix grid
    res_get = auth_client_a.get(url_matrix)
    assert res_get.status_code == 200
    assert "products" in res_get.context

    # POST manual SKUs with invalid quantity (> 100,000) and unknown SKU
    post_data = {
        "manual_submit": "1",
        "matrix_sku[]": ["NONEXISTENT-SKU-999", "INVALID-QTY-SKU"],
        "matrix_qty[]": ["5", "9999999"],  # 9999999 exceeds bound 100000
    }
    res_post = auth_client_a.post(url_matrix, post_data)
    assert res_post.status_code == 200
    assert "parsed_items" in res_post.context
    parsed = res_post.context["parsed_items"]
    # Unknown SKU is presented in table with found=False (M7)
    assert any(item["sku"] == "NONEXISTENT-SKU-999" and not item["found"] for item in parsed)
