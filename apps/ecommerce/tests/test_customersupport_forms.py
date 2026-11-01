"""Unit and contract tests for eCommerce 9.14 Customer Service & Support forms.

Covers:
1. Contract verification (CUSTOMERSUPPORT_FORM_FIELDS for all 4 forms):
   - CustomerSupportTicketForm
   - KnowledgeBaseArticleForm
   - OrderIssueClaimForm
   - CustomerSatisfactionSurveyForm
   - Assert system and auto-generated fields are excluded across all forms.
2. CustomerSupportTicketForm:
   - Valid submission with tenant scoping and save verification.
   - Minimal valid submission (guest ticket without customer/order/agent).
   - Form field widgets, input types, and CSS classes.
   - Required field and email format validation.
   - Tenant foreign key queryset scoping (customer, order, assigned_agent).
   - Cross-tenant IDOR protection via reject_foreign (foreign customer or order rejected).
   - Intra-tenant consistency validation (rejects order not belonging to selected customer).
3. KnowledgeBaseArticleForm:
   - Valid submission with tenant scoping and save verification.
   - Minimal submission with model-level auto-slug generation.
   - Widget and field validations.
   - Author queryset scoping to active users.
   - TenantUniqueMixin MRO order and instance tenant assignment on init.
   - Slug uniqueness within tenant (clean multi-tenant slug reuse).
4. OrderIssueClaimForm:
   - Valid submission with tenant scoping and save verification.
   - Minimal submission with optional fields omitted.
   - Field validations and required field enforcement.
   - Tenant queryset scoping (order, customer, ticket, reviewed_by).
   - Cross-tenant IDOR protection via reject_foreign (foreign order, customer, ticket).
   - Non-negative validation on claimed_amount and approved_amount.
   - Intra-tenant consistency validation (rejects order not belonging to customer).
5. CustomerSatisfactionSurveyForm:
   - Valid submission with tenant scoping and save verification.
   - Minimal submission with optional fields omitted.
   - Field validations and required field enforcement.
   - Tenant queryset scoping (ticket, order, customer, agent_rated, reviewed_by).
   - Cross-tenant IDOR protection via reject_foreign (foreign ticket, order, customer).
   - Rating score boundary validation:
     * CSAT surveys (ticket_csat, order_delivery_csat) enforce 1 <= score <= 5.
     * NPS surveys (storefront_nps) enforce 0 <= score <= 10.
   - Intra-tenant consistency validation (rejects order not belonging to customer).

Conventions enforced:
- Test functions: test_customersupport_*
- Module-level helpers: _customersupport_*
"""
from decimal import Decimal
import pytest
from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import Party
from apps.ecommerce.forms import (
    CustomerSatisfactionSurveyForm,
    CustomerSupportTicketForm,
    KnowledgeBaseArticleForm,
    OrderIssueClaimForm,
)
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin
from apps.ecommerce.models import (
    CustomerAccountProfile,
    CustomerSatisfactionSurvey,
    CustomerSupportTicket,
    EcommerceOrder,
    KnowledgeBaseArticle,
    OrderIssueClaim,
)
from apps.ecommerce.tests.conftest import (
    CUSTOMERSUPPORT_FORM_FIELDS,
    _customersupport_article,
    _customersupport_claim,
    _customersupport_survey,
    _customersupport_ticket,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_customersupport_*)
# ==============================================================================

def _customersupport_widen(form, field_name, queryset):
    """Widens a form field queryset to test reject_foreign defense-in-depth in clean()."""
    form.fields[field_name].queryset = queryset


def _customersupport_create_customer(tenant, name="Alt Customer"):
    """Create an alternate Party and CustomerAccountProfile for mismatch testing."""
    party = Party.objects.create(tenant=tenant, name=name, kind="person")
    return CustomerAccountProfile.objects.create(tenant=tenant, customer=party)


def _customersupport_create_inactive_user(username="inactive_support_staff"):
    """Create an inactive User to verify active-user queryset scoping."""
    User = get_user_model()
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpassword123",
        is_active=False,
    )


def _customersupport_ticket_payload(customer=None, order=None, **overrides):
    """Return a valid form payload for CustomerSupportTicketForm."""
    payload = {
        "customer": customer.pk if customer else "",
        "order": order.pk if order else "",
        "assigned_agent": "",
        "subject": "Missing item from delivery package",
        "customer_name": "Valued Shopper",
        "customer_email": "shopper@example.com",
        "customer_phone": "+1 (555) 019-2834",
        "channel": "email",
        "category": "order_tracking_wismo",
        "priority": "medium",
        "status": "new",
        "initial_message": "Hello, my shipment arrived but item SKU-123 is missing from the package.",
        "resolution_summary": "",
        "internal_notes": "Checked shipment packing slip against order line items.",
        "is_bot_handled": False,
        "bot_handoff_reason": "",
    }
    payload.update(overrides)
    return payload


def _customersupport_article_payload(**overrides):
    """Return a valid form payload for KnowledgeBaseArticleForm."""
    payload = {
        "title": "Hassle-Free 30-Day Returns Policy",
        "slug": "hassle-free-30-day-returns-policy",
        "category": "returns_refunds",
        "summary": "Step-by-step instructions for initiating returns and downloading prepaid shipping labels.",
        "content": "All unworn items with tags attached can be returned within 30 days of shipment receipt.",
        "status": "published",
        "target_audience": "all_visitors",
        "is_featured": True,
        "keywords": "returns, refund, label, carrier, exchange",
        "author": "",
    }
    payload.update(overrides)
    return payload


def _customersupport_claim_payload(order, customer=None, ticket=None, **overrides):
    """Return a valid form payload for OrderIssueClaimForm."""
    payload = {
        "order": order.pk if hasattr(order, "pk") else order,
        "customer": customer.pk if customer and hasattr(customer, "pk") else (customer or ""),
        "ticket": ticket.pk if ticket and hasattr(ticket, "pk") else (ticket or ""),
        "claim_type": "damaged_item",
        "status": "submitted",
        "claimed_amount": "49.99",
        "approved_amount": "0.00",
        "resolution_action": "pending",
        "carrier_tracking_number": "1Z9999999999999999",
        "photo_evidence_url": "https://storage.example.com/claims/damage_proof.jpg",
        "customer_notes": "The outer carton was crushed in transit and the glass bottle inside was broken.",
        "decision_notes": "",
        "reviewed_by": "",
    }
    payload.update(overrides)
    return payload


def _customersupport_survey_payload(ticket=None, order=None, customer=None, **overrides):
    """Return a valid form payload for CustomerSatisfactionSurveyForm."""
    payload = {
        "ticket": ticket.pk if ticket and hasattr(ticket, "pk") else (ticket or ""),
        "order": order.pk if order and hasattr(order, "pk") else (order or ""),
        "customer": customer.pk if customer and hasattr(customer, "pk") else (customer or ""),
        "survey_type": "ticket_csat",
        "rating_score": 5,
        "sentiment": "positive",
        "feedback_comment": "Support agent resolved my issue within five minutes. Fantastic service!",
        "agent_rated": "",
        "follow_up_status": "not_required",
        "follow_up_notes": "",
        "reviewed_by": "",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. Contract & System Exclusions Tests
# ==============================================================================

def test_customersupport_form_fields_contract():
    """Verify all 4 Customer Support forms declare the exact contract Meta.fields."""
    assert tuple(CustomerSupportTicketForm.Meta.fields) == CUSTOMERSUPPORT_FORM_FIELDS["CustomerSupportTicketForm"]
    assert tuple(KnowledgeBaseArticleForm.Meta.fields) == CUSTOMERSUPPORT_FORM_FIELDS["KnowledgeBaseArticleForm"]
    assert tuple(OrderIssueClaimForm.Meta.fields) == CUSTOMERSUPPORT_FORM_FIELDS["OrderIssueClaimForm"]
    assert tuple(CustomerSatisfactionSurveyForm.Meta.fields) == CUSTOMERSUPPORT_FORM_FIELDS["CustomerSatisfactionSurveyForm"]


def test_customersupport_forms_system_fields_excluded():
    """Verify tenant, number, timestamps, and model-managed SLA/metrics are excluded from forms."""
    forms_to_test = [
        (CustomerSupportTicketForm, (
            "tenant", "number", "created_at", "updated_at",
            "sla_first_response_due_at", "sla_resolution_due_at",
            "first_responded_at", "resolved_at", "is_sla_breached",
        )),
        (KnowledgeBaseArticleForm, (
            "tenant", "number", "created_at", "updated_at",
            "view_count", "helpful_votes", "unhelpful_votes",
        )),
        (OrderIssueClaimForm, (
            "tenant", "number", "created_at", "updated_at",
            "resolved_at",
        )),
        (CustomerSatisfactionSurveyForm, (
            "tenant", "number", "created_at", "updated_at",
        )),
    ]

    for form_cls, forbidden_fields in forms_to_test:
        meta_fields = form_cls.Meta.fields
        for forbidden in forbidden_fields:
            assert forbidden not in meta_fields, f"Forbidden field '{forbidden}' exposed in {form_cls.__name__}.Meta.fields"

        # Instantiate form to verify unbound fields dictionary also excludes them
        instance_form = form_cls()
        for forbidden in forbidden_fields:
            assert forbidden not in instance_form.fields, f"Forbidden field '{forbidden}' present in {form_cls.__name__}.fields"


# ==============================================================================
# 2. CustomerSupportTicketForm Tests
# ==============================================================================

def test_customersupport_ticket_form_widgets_and_css_classes():
    """Verify widget types, HTML attributes, CSS classes, and placeholders on CustomerSupportTicketForm."""
    form = CustomerSupportTicketForm()

    # Widget types
    assert isinstance(form.fields["customer"].widget, forms.Select)
    assert isinstance(form.fields["order"].widget, forms.Select)
    assert isinstance(form.fields["assigned_agent"].widget, forms.Select)
    assert isinstance(form.fields["subject"].widget, forms.TextInput)
    assert isinstance(form.fields["customer_name"].widget, forms.TextInput)
    assert isinstance(form.fields["customer_email"].widget, forms.EmailInput)
    assert isinstance(form.fields["customer_phone"].widget, forms.TextInput)
    assert isinstance(form.fields["channel"].widget, forms.Select)
    assert isinstance(form.fields["category"].widget, forms.Select)
    assert isinstance(form.fields["priority"].widget, forms.Select)
    assert isinstance(form.fields["status"].widget, forms.Select)
    assert isinstance(form.fields["initial_message"].widget, forms.Textarea)
    assert isinstance(form.fields["resolution_summary"].widget, forms.Textarea)
    assert isinstance(form.fields["internal_notes"].widget, forms.Textarea)
    assert isinstance(form.fields["is_bot_handled"].widget, forms.CheckboxInput)
    assert isinstance(form.fields["bot_handoff_reason"].widget, forms.TextInput)

    # CSS classes
    assert "form-select" in form.fields["customer"].widget.attrs["class"]
    assert "form-select" in form.fields["order"].widget.attrs["class"]
    assert "form-select" in form.fields["assigned_agent"].widget.attrs["class"]
    assert "form-input" in form.fields["subject"].widget.attrs["class"]
    assert "form-input" in form.fields["customer_name"].widget.attrs["class"]
    assert "form-input" in form.fields["customer_email"].widget.attrs["class"]
    assert "form-input" in form.fields["customer_phone"].widget.attrs["class"]
    assert "form-select" in form.fields["channel"].widget.attrs["class"]
    assert "form-select" in form.fields["category"].widget.attrs["class"]
    assert "form-select" in form.fields["priority"].widget.attrs["class"]
    assert "form-select" in form.fields["status"].widget.attrs["class"]
    assert "form-textarea" in form.fields["initial_message"].widget.attrs["class"]
    assert "form-textarea" in form.fields["resolution_summary"].widget.attrs["class"]
    assert "form-textarea" in form.fields["internal_notes"].widget.attrs["class"]
    assert "form-checkbox" in form.fields["is_bot_handled"].widget.attrs["class"]
    assert "form-input" in form.fields["bot_handoff_reason"].widget.attrs["class"]

    # Placeholders
    assert "placeholder" in form.fields["subject"].widget.attrs
    assert "placeholder" in form.fields["customer_name"].widget.attrs
    assert "placeholder" in form.fields["customer_email"].widget.attrs
    assert "placeholder" in form.fields["initial_message"].widget.attrs


def test_customersupport_ticket_form_valid_full_submission(tenant_a, ecom_profile_a, ecom_order_a, admin_user):
    """Submitting valid ticket with all fields binds tenant, creates model with ESTK number."""
    payload = _customersupport_ticket_payload(
        customer=ecom_profile_a,
        order=ecom_order_a,
        assigned_agent=admin_user.pk,
        subject="Defective power supply on Server Unit",
        customer_phone="+1 (555) 987-6543",
        is_bot_handled=True,
        bot_handoff_reason="Escalated due to hardware fault warranty inquiry",
    )
    form = CustomerSupportTicketForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    ticket = form.save()
    assert ticket.pk is not None
    assert ticket.tenant == tenant_a
    assert ticket.number.startswith("ESTK-")
    assert ticket.customer == ecom_profile_a
    assert ticket.order == ecom_order_a
    assert ticket.assigned_agent == admin_user
    assert ticket.subject == "Defective power supply on Server Unit"
    assert ticket.is_bot_handled is True
    assert ticket.bot_handoff_reason == "Escalated due to hardware fault warranty inquiry"


def test_customersupport_ticket_form_valid_minimal_guest_submission(tenant_a):
    """Submitting guest ticket omitting customer, order, assigned_agent, and optional notes succeeds."""
    payload = _customersupport_ticket_payload(
        customer=None,
        order=None,
        assigned_agent="",
        customer_phone="",
        resolution_summary="",
        internal_notes="",
        bot_handoff_reason="",
    )
    form = CustomerSupportTicketForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    ticket = form.save()
    assert ticket.pk is not None
    assert ticket.tenant == tenant_a
    assert ticket.customer is None
    assert ticket.order is None
    assert ticket.assigned_agent is None
    assert ticket.customer_email == "shopper@example.com"


def test_customersupport_ticket_form_required_fields_validation(tenant_a):
    """Omitting mandatory fields produces form validation errors."""
    form = CustomerSupportTicketForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "subject" in form.errors
    assert "customer_name" in form.errors
    assert "customer_email" in form.errors
    assert "channel" in form.errors
    assert "category" in form.errors
    assert "priority" in form.errors
    assert "status" in form.errors
    assert "initial_message" in form.errors


def test_customersupport_ticket_form_invalid_email_validation(tenant_a):
    """Providing a malformed email triggers EmailField validation error."""
    payload = _customersupport_ticket_payload(customer_email="not-a-valid-email-address")
    form = CustomerSupportTicketForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer_email" in form.errors


def test_customersupport_ticket_form_tenant_queryset_scoping(
    tenant_a, tenant_b, ecom_profile_a, ecom_profile_b, ecom_order_a, ecom_order_b, admin_user
):
    """CustomerSupportTicketForm scopes customer/order querysets to bound tenant and users to active."""
    inactive_user = _customersupport_create_inactive_user()
    form = CustomerSupportTicketForm(tenant=tenant_a)

    # Scoping customer
    customer_qs = form.fields["customer"].queryset
    assert ecom_profile_a in customer_qs
    assert ecom_profile_b not in customer_qs

    # Scoping order
    order_qs = form.fields["order"].queryset
    assert ecom_order_a in order_qs
    assert ecom_order_b not in order_qs

    # Scoping assigned_agent (active users only)
    agent_qs = form.fields["assigned_agent"].queryset
    assert admin_user in agent_qs
    assert inactive_user not in agent_qs


def test_customersupport_ticket_form_cross_tenant_idor_customer(tenant_a, tenant_b, ecom_profile_b):
    """Submitting a customer profile from tenant_b in a tenant_a form fails reject_foreign validation."""
    payload = _customersupport_ticket_payload(customer=ecom_profile_b)
    form = CustomerSupportTicketForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "customer", CustomerAccountProfile.objects.all())
    assert not form.is_valid()
    assert "customer" in form.errors
    assert "That record belongs to another workspace." in form.errors["customer"]


def test_customersupport_ticket_form_cross_tenant_idor_order(tenant_a, tenant_b, ecom_order_b):
    """Submitting an order from tenant_b in a tenant_a form fails reject_foreign validation."""
    payload = _customersupport_ticket_payload(order=ecom_order_b)
    form = CustomerSupportTicketForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "order", EcommerceOrder.objects.all())
    assert not form.is_valid()
    assert "order" in form.errors
    assert "That record belongs to another workspace." in form.errors["order"]


def test_customersupport_ticket_form_intra_tenant_shopper_consistency_valid(tenant_a, ecom_profile_a, ecom_order_a):
    """Providing customer and order that reference the same party passes consistency clean check."""
    payload = _customersupport_ticket_payload(customer=ecom_profile_a, order=ecom_order_a)
    form = CustomerSupportTicketForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_customersupport_ticket_form_intra_tenant_shopper_consistency_mismatch(tenant_a, ecom_order_a):
    """Providing customer and order belonging to different shoppers under the same tenant fails validation."""
    alt_profile = _customersupport_create_customer(tenant_a, name="Mismatched Shopper Profile")
    payload = _customersupport_ticket_payload(customer=alt_profile, order=ecom_order_a)
    form = CustomerSupportTicketForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors
    assert "The selected order does not belong to the selected customer profile." in form.errors["order"]


# ==============================================================================
# 3. KnowledgeBaseArticleForm Tests
# ==============================================================================

def test_customersupport_article_form_widgets_and_css_classes():
    """Verify widget types, HTML attributes, and CSS classes on KnowledgeBaseArticleForm."""
    form = KnowledgeBaseArticleForm()

    assert isinstance(form.fields["title"].widget, forms.TextInput)
    assert isinstance(form.fields["slug"].widget, forms.TextInput)
    assert isinstance(form.fields["category"].widget, forms.Select)
    assert isinstance(form.fields["summary"].widget, forms.Textarea)
    assert isinstance(form.fields["content"].widget, forms.Textarea)
    assert isinstance(form.fields["status"].widget, forms.Select)
    assert isinstance(form.fields["target_audience"].widget, forms.Select)
    assert isinstance(form.fields["is_featured"].widget, forms.CheckboxInput)
    assert isinstance(form.fields["keywords"].widget, forms.TextInput)
    assert isinstance(form.fields["author"].widget, forms.Select)

    assert "form-input" in form.fields["title"].widget.attrs["class"]
    assert "form-input" in form.fields["slug"].widget.attrs["class"]
    assert "form-select" in form.fields["category"].widget.attrs["class"]
    assert "form-textarea" in form.fields["summary"].widget.attrs["class"]
    assert "form-textarea" in form.fields["content"].widget.attrs["class"]
    assert "form-select" in form.fields["status"].widget.attrs["class"]
    assert "form-select" in form.fields["target_audience"].widget.attrs["class"]
    assert "form-checkbox" in form.fields["is_featured"].widget.attrs["class"]
    assert "form-input" in form.fields["keywords"].widget.attrs["class"]
    assert "form-select" in form.fields["author"].widget.attrs["class"]


def test_customersupport_article_form_valid_full_submission(tenant_a, admin_user):
    """Submitting valid article with author and all fields assigns tenant and saves successfully."""
    payload = _customersupport_article_payload(
        title="Payment Security & Encryption Standards",
        slug="payment-security-encryption-standards",
        category="account_security",
        author=admin_user.pk,
    )
    form = KnowledgeBaseArticleForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    article = form.save()
    assert article.pk is not None
    assert article.tenant == tenant_a
    assert article.number.startswith("EKBA-")
    assert article.title == "Payment Security & Encryption Standards"
    assert article.slug == "payment-security-encryption-standards"
    assert article.author == admin_user
    assert article.category == "account_security"


def test_customersupport_article_form_valid_minimal_auto_slug(tenant_a):
    """Omitting optional slug, keywords, and author allows form save with model auto-slug generation."""
    payload = _customersupport_article_payload(
        title="International Customs and Duties Guide",
        slug="",
        keywords="",
        author="",
    )
    form = KnowledgeBaseArticleForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    article = form.save()
    assert article.pk is not None
    assert article.slug == "international-customs-and-duties-guide"
    assert article.author is None
    assert article.keywords == ""


def test_customersupport_article_form_required_fields_validation(tenant_a):
    """Omitting title, category, summary, content, status, target_audience triggers errors."""
    form = KnowledgeBaseArticleForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "category" in form.errors
    assert "summary" in form.errors
    assert "content" in form.errors
    assert "status" in form.errors
    assert "target_audience" in form.errors


def test_customersupport_article_form_author_queryset_scoping(admin_user):
    """KnowledgeBaseArticleForm scopes author queryset to active users only."""
    inactive_user = _customersupport_create_inactive_user()
    form = KnowledgeBaseArticleForm()
    author_qs = form.fields["author"].queryset
    assert admin_user in author_qs
    assert inactive_user not in author_qs


def test_customersupport_article_form_tenant_unique_mixin_mro_and_init(tenant_a):
    """TenantUniqueMixin precedes TenantModelForm in MRO and stamps instance.tenant on init."""
    order = KnowledgeBaseArticleForm.__mro__
    assert order.index(TenantUniqueMixin) < order.index(TenantModelForm)
    form = KnowledgeBaseArticleForm(tenant=tenant_a)
    assert form.instance.tenant == tenant_a


def test_customersupport_article_form_allows_same_slug_cross_tenant(tenant_a, tenant_b, admin_user, admin_b):
    """Articles in different tenants can have the same slug cleanly without colliding."""
    article_a = _customersupport_article(
        tenant_a,
        title="Order Cancellation Window",
        slug="order-cancellation-window",
        author=admin_user,
    )

    payload_b = _customersupport_article_payload(
        title="Order Cancellation Window",
        slug=article_a.slug,
        author=admin_b.pk,
    )
    form_b = KnowledgeBaseArticleForm(data=payload_b, tenant=tenant_b)
    assert form_b.is_valid(), form_b.errors

    article_b = form_b.save()
    assert article_b.tenant == tenant_b
    assert article_b.slug == article_a.slug


# ==============================================================================
# 4. OrderIssueClaimForm Tests
# ==============================================================================

def test_customersupport_claim_form_widgets_and_css_classes():
    """Verify widget types, HTML attributes, and CSS classes on OrderIssueClaimForm."""
    form = OrderIssueClaimForm()

    assert isinstance(form.fields["order"].widget, forms.Select)
    assert isinstance(form.fields["customer"].widget, forms.Select)
    assert isinstance(form.fields["ticket"].widget, forms.Select)
    assert isinstance(form.fields["claim_type"].widget, forms.Select)
    assert isinstance(form.fields["status"].widget, forms.Select)
    assert isinstance(form.fields["claimed_amount"].widget, forms.NumberInput)
    assert isinstance(form.fields["approved_amount"].widget, forms.NumberInput)
    assert isinstance(form.fields["resolution_action"].widget, forms.Select)
    assert isinstance(form.fields["carrier_tracking_number"].widget, forms.TextInput)
    assert isinstance(form.fields["photo_evidence_url"].widget, forms.URLInput)
    assert isinstance(form.fields["customer_notes"].widget, forms.Textarea)
    assert isinstance(form.fields["decision_notes"].widget, forms.Textarea)
    assert isinstance(form.fields["reviewed_by"].widget, forms.Select)

    assert "form-select" in form.fields["order"].widget.attrs["class"]
    assert "form-select" in form.fields["customer"].widget.attrs["class"]
    assert "form-select" in form.fields["ticket"].widget.attrs["class"]
    assert "form-input" in form.fields["claimed_amount"].widget.attrs["class"]
    assert "form-input" in form.fields["approved_amount"].widget.attrs["class"]
    assert "form-input" in form.fields["carrier_tracking_number"].widget.attrs["class"]
    assert "form-input" in form.fields["photo_evidence_url"].widget.attrs["class"]
    assert "form-textarea" in form.fields["customer_notes"].widget.attrs["class"]
    assert "form-textarea" in form.fields["decision_notes"].widget.attrs["class"]
    assert "form-select" in form.fields["reviewed_by"].widget.attrs["class"]


def test_customersupport_claim_form_valid_full_submission(
    tenant_a, ecom_order_a, ecom_profile_a, ecom_customersupport_ticket_a, admin_user
):
    """Submitting valid claim with all fields binds tenant, creates model with ECLM number."""
    payload = _customersupport_claim_payload(
        order=ecom_order_a,
        customer=ecom_profile_a,
        ticket=ecom_customersupport_ticket_a,
        claimed_amount="85.50",
        approved_amount="85.50",
        resolution_action="full_refund",
        decision_notes="Approved after carrier confirmed transit crushing incident.",
        reviewed_by=admin_user.pk,
    )
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    claim = form.save()
    assert claim.pk is not None
    assert claim.tenant == tenant_a
    assert claim.number.startswith("ECLM-")
    assert claim.order == ecom_order_a
    assert claim.customer == ecom_profile_a
    assert claim.ticket == ecom_customersupport_ticket_a
    assert claim.claimed_amount == Decimal("85.50")
    assert claim.approved_amount == Decimal("85.50")
    assert claim.resolution_action == "full_refund"
    assert claim.reviewed_by == admin_user


def test_customersupport_claim_form_valid_minimal_submission(tenant_a, ecom_order_a):
    """Submitting claim omitting optional customer, ticket, notes, and reviewer succeeds."""
    payload = _customersupport_claim_payload(
        order=ecom_order_a,
        customer=None,
        ticket=None,
        approved_amount="0.00",
        carrier_tracking_number="",
        photo_evidence_url="",
        decision_notes="",
        reviewed_by="",
    )
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    claim = form.save()
    assert claim.pk is not None
    assert claim.tenant == tenant_a
    assert claim.customer is None
    assert claim.ticket is None
    assert claim.approved_amount == Decimal("0.00")
    assert claim.reviewed_by is None


def test_customersupport_claim_form_required_fields_validation(tenant_a):
    """Omitting mandatory order, claim_type, status, claimed_amount, resolution_action, customer_notes fails."""
    form = OrderIssueClaimForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors
    assert "claim_type" in form.errors
    assert "status" in form.errors
    assert "claimed_amount" in form.errors
    assert "resolution_action" in form.errors
    assert "customer_notes" in form.errors


def test_customersupport_claim_form_tenant_queryset_scoping(
    tenant_a,
    tenant_b,
    ecom_order_a,
    ecom_order_b,
    ecom_profile_a,
    ecom_profile_b,
    ecom_customersupport_ticket_a,
    ecom_customersupport_ticket_b,
    admin_user,
):
    """OrderIssueClaimForm scopes foreign key querysets to current workspace."""
    inactive_user = _customersupport_create_inactive_user()
    form = OrderIssueClaimForm(tenant=tenant_a)

    order_qs = form.fields["order"].queryset
    assert ecom_order_a in order_qs
    assert ecom_order_b not in order_qs

    customer_qs = form.fields["customer"].queryset
    assert ecom_profile_a in customer_qs
    assert ecom_profile_b not in customer_qs

    ticket_qs = form.fields["ticket"].queryset
    assert ecom_customersupport_ticket_a in ticket_qs
    assert ecom_customersupport_ticket_b not in ticket_qs

    reviewer_qs = form.fields["reviewed_by"].queryset
    assert admin_user in reviewer_qs
    assert inactive_user not in reviewer_qs


def test_customersupport_claim_form_cross_tenant_idor_order(tenant_a, tenant_b, ecom_order_b):
    """Submitting order from tenant_b in tenant_a claim form is rejected with cross-workspace error."""
    payload = _customersupport_claim_payload(order=ecom_order_b)
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "order", EcommerceOrder.objects.all())
    assert not form.is_valid()
    assert "order" in form.errors
    assert "That record belongs to another workspace." in form.errors["order"]


def test_customersupport_claim_form_cross_tenant_idor_customer(tenant_a, tenant_b, ecom_order_a, ecom_profile_b):
    """Submitting customer from tenant_b in tenant_a claim form is rejected with cross-workspace error."""
    payload = _customersupport_claim_payload(order=ecom_order_a, customer=ecom_profile_b)
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "customer", CustomerAccountProfile.objects.all())
    assert not form.is_valid()
    assert "customer" in form.errors
    assert "That record belongs to another workspace." in form.errors["customer"]


def test_customersupport_claim_form_cross_tenant_idor_ticket(
    tenant_a, tenant_b, ecom_order_a, ecom_customersupport_ticket_b
):
    """Submitting ticket from tenant_b in tenant_a claim form is rejected with cross-workspace error."""
    payload = _customersupport_claim_payload(order=ecom_order_a, ticket=ecom_customersupport_ticket_b)
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "ticket", CustomerSupportTicket.objects.all())
    assert not form.is_valid()
    assert "ticket" in form.errors
    assert "That record belongs to another workspace." in form.errors["ticket"]


def test_customersupport_claim_form_negative_claimed_amount_rejected(tenant_a, ecom_order_a):
    """Negative claimed_amount is rejected with clear validation error message."""
    payload = _customersupport_claim_payload(order=ecom_order_a, claimed_amount="-15.00")
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "claimed_amount" in form.errors
    assert "Claimed amount cannot be negative." in form.errors["claimed_amount"]


def test_customersupport_claim_form_negative_approved_amount_rejected(tenant_a, ecom_order_a):
    """Negative approved_amount is rejected with clear validation error message."""
    payload = _customersupport_claim_payload(order=ecom_order_a, approved_amount="-5.00")
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "approved_amount" in form.errors
    assert "Approved amount cannot be negative." in form.errors["approved_amount"]


def test_customersupport_claim_form_zero_amounts_valid(tenant_a, ecom_order_a):
    """Zero claimed and approved amounts are valid for warranty exchange or repair claims."""
    payload = _customersupport_claim_payload(
        order=ecom_order_a,
        claimed_amount="0.00",
        approved_amount="0.00",
        resolution_action="replacement_reship",
    )
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_customersupport_claim_form_intra_tenant_shopper_consistency_valid(tenant_a, ecom_order_a, ecom_profile_a):
    """Claim with matching customer profile and order shopper succeeds cleanly."""
    payload = _customersupport_claim_payload(order=ecom_order_a, customer=ecom_profile_a)
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_customersupport_claim_form_intra_tenant_shopper_consistency_mismatch(tenant_a, ecom_order_a):
    """Claim with order belonging to shopper A but customer profile of shopper B is rejected."""
    alt_profile = _customersupport_create_customer(tenant_a, name="Other Shopper For Claim")
    payload = _customersupport_claim_payload(order=ecom_order_a, customer=alt_profile)
    form = OrderIssueClaimForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors
    assert "The selected order does not belong to the selected customer profile." in form.errors["order"]


# ==============================================================================
# 5. CustomerSatisfactionSurveyForm Tests
# ==============================================================================

def test_customersupport_survey_form_widgets_and_css_classes():
    """Verify widget types, HTML attributes, and CSS classes on CustomerSatisfactionSurveyForm."""
    form = CustomerSatisfactionSurveyForm()

    assert isinstance(form.fields["ticket"].widget, forms.Select)
    assert isinstance(form.fields["order"].widget, forms.Select)
    assert isinstance(form.fields["customer"].widget, forms.Select)
    assert isinstance(form.fields["survey_type"].widget, forms.Select)
    assert isinstance(form.fields["rating_score"].widget, forms.NumberInput)
    assert isinstance(form.fields["sentiment"].widget, forms.Select)
    assert isinstance(form.fields["feedback_comment"].widget, forms.Textarea)
    assert isinstance(form.fields["agent_rated"].widget, forms.Select)
    assert isinstance(form.fields["follow_up_status"].widget, forms.Select)
    assert isinstance(form.fields["follow_up_notes"].widget, forms.Textarea)
    assert isinstance(form.fields["reviewed_by"].widget, forms.Select)

    assert "form-select" in form.fields["ticket"].widget.attrs["class"]
    assert "form-select" in form.fields["order"].widget.attrs["class"]
    assert "form-select" in form.fields["customer"].widget.attrs["class"]
    assert "form-select" in form.fields["survey_type"].widget.attrs["class"]
    assert "form-input" in form.fields["rating_score"].widget.attrs["class"]
    assert "form-select" in form.fields["sentiment"].widget.attrs["class"]
    assert "form-textarea" in form.fields["feedback_comment"].widget.attrs["class"]
    assert "form-select" in form.fields["agent_rated"].widget.attrs["class"]
    assert "form-select" in form.fields["follow_up_status"].widget.attrs["class"]
    assert "form-textarea" in form.fields["follow_up_notes"].widget.attrs["class"]
    assert "form-select" in form.fields["reviewed_by"].widget.attrs["class"]


def test_customersupport_survey_form_valid_full_submission(
    tenant_a, ecom_customersupport_ticket_a, ecom_order_a, ecom_profile_a, admin_user
):
    """Submitting valid survey with ticket, order, customer, agent, and reviewer assigns tenant and saves model."""
    payload = _customersupport_survey_payload(
        ticket=ecom_customersupport_ticket_a,
        order=ecom_order_a,
        customer=ecom_profile_a,
        survey_type="ticket_csat",
        rating_score=5,
        sentiment="positive",
        agent_rated=admin_user.pk,
        follow_up_status="not_required",
        follow_up_notes="Closed-loop verification complete.",
        reviewed_by=admin_user.pk,
    )
    form = CustomerSatisfactionSurveyForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    survey = form.save()
    assert survey.pk is not None
    assert survey.tenant == tenant_a
    assert survey.number.startswith("ECSF-")
    assert survey.ticket == ecom_customersupport_ticket_a
    assert survey.order == ecom_order_a
    assert survey.customer == ecom_profile_a
    assert survey.rating_score == 5
    assert survey.sentiment == "positive"
    assert survey.agent_rated == admin_user
    assert survey.reviewed_by == admin_user


def test_customersupport_survey_form_valid_minimal_submission(tenant_a):
    """Submitting storefront NPS survey omitting optional ticket, order, customer, agent, notes succeeds."""
    payload = _customersupport_survey_payload(
        ticket=None,
        order=None,
        customer=None,
        survey_type="storefront_nps",
        rating_score=9,
        sentiment="positive",
        agent_rated="",
        feedback_comment="",
        follow_up_notes="",
        reviewed_by="",
    )
    form = CustomerSatisfactionSurveyForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    survey = form.save()
    assert survey.pk is not None
    assert survey.tenant == tenant_a
    assert survey.survey_type == "storefront_nps"
    assert survey.rating_score == 9
    assert survey.ticket is None
    assert survey.order is None
    assert survey.customer is None


def test_customersupport_survey_form_required_fields_validation(tenant_a):
    """Omitting survey_type, rating_score, sentiment, or follow_up_status produces errors."""
    form = CustomerSatisfactionSurveyForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "survey_type" in form.errors
    assert "rating_score" in form.errors
    assert "sentiment" in form.errors
    assert "follow_up_status" in form.errors


def test_customersupport_survey_form_tenant_queryset_scoping(
    tenant_a,
    tenant_b,
    ecom_customersupport_ticket_a,
    ecom_customersupport_ticket_b,
    ecom_order_a,
    ecom_order_b,
    ecom_profile_a,
    ecom_profile_b,
    admin_user,
):
    """CustomerSatisfactionSurveyForm scopes ticket, order, customer, and staff user querysets."""
    inactive_user = _customersupport_create_inactive_user()
    form = CustomerSatisfactionSurveyForm(tenant=tenant_a)

    ticket_qs = form.fields["ticket"].queryset
    assert ecom_customersupport_ticket_a in ticket_qs
    assert ecom_customersupport_ticket_b not in ticket_qs

    order_qs = form.fields["order"].queryset
    assert ecom_order_a in order_qs
    assert ecom_order_b not in order_qs

    customer_qs = form.fields["customer"].queryset
    assert ecom_profile_a in customer_qs
    assert ecom_profile_b not in customer_qs

    agent_qs = form.fields["agent_rated"].queryset
    assert admin_user in agent_qs
    assert inactive_user not in agent_qs

    reviewer_qs = form.fields["reviewed_by"].queryset
    assert admin_user in reviewer_qs
    assert inactive_user not in reviewer_qs


def test_customersupport_survey_form_cross_tenant_idor_ticket(
    tenant_a, tenant_b, ecom_customersupport_ticket_b
):
    """Submitting ticket from tenant_b in tenant_a survey form fails reject_foreign validation."""
    payload = _customersupport_survey_payload(ticket=ecom_customersupport_ticket_b)
    form = CustomerSatisfactionSurveyForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "ticket", CustomerSupportTicket.objects.all())
    assert not form.is_valid()
    assert "ticket" in form.errors
    assert "That record belongs to another workspace." in form.errors["ticket"]


def test_customersupport_survey_form_cross_tenant_idor_order(tenant_a, tenant_b, ecom_order_b):
    """Submitting order from tenant_b in tenant_a survey form fails reject_foreign validation."""
    payload = _customersupport_survey_payload(order=ecom_order_b)
    form = CustomerSatisfactionSurveyForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "order", EcommerceOrder.objects.all())
    assert not form.is_valid()
    assert "order" in form.errors
    assert "That record belongs to another workspace." in form.errors["order"]


def test_customersupport_survey_form_cross_tenant_idor_customer(tenant_a, tenant_b, ecom_profile_b):
    """Submitting customer profile from tenant_b in tenant_a survey form fails reject_foreign validation."""
    payload = _customersupport_survey_payload(customer=ecom_profile_b)
    form = CustomerSatisfactionSurveyForm(data=payload, tenant=tenant_a)
    _customersupport_widen(form, "customer", CustomerAccountProfile.objects.all())
    assert not form.is_valid()
    assert "customer" in form.errors
    assert "That record belongs to another workspace." in form.errors["customer"]


def test_customersupport_survey_form_csat_rating_boundary_enforcement(tenant_a):
    """CSAT survey types (ticket_csat, order_delivery_csat) require rating score between 1 and 5."""
    # Test ticket_csat below minimum (0)
    payload_ticket_low = _customersupport_survey_payload(survey_type="ticket_csat", rating_score=0)
    form = CustomerSatisfactionSurveyForm(data=payload_ticket_low, tenant=tenant_a)
    assert not form.is_valid()
    assert "rating_score" in form.errors
    assert "CSAT surveys require a rating score between 1 and 5." in form.errors["rating_score"]

    # Test ticket_csat above maximum (6)
    payload_ticket_high = _customersupport_survey_payload(survey_type="ticket_csat", rating_score=6)
    form = CustomerSatisfactionSurveyForm(data=payload_ticket_high, tenant=tenant_a)
    assert not form.is_valid()
    assert "rating_score" in form.errors
    assert "CSAT surveys require a rating score between 1 and 5." in form.errors["rating_score"]

    # Test ticket_csat boundaries (1 and 5 are valid)
    form_min = CustomerSatisfactionSurveyForm(
        data=_customersupport_survey_payload(survey_type="ticket_csat", rating_score=1),
        tenant=tenant_a,
    )
    assert form_min.is_valid(), form_min.errors

    form_max = CustomerSatisfactionSurveyForm(
        data=_customersupport_survey_payload(survey_type="ticket_csat", rating_score=5),
        tenant=tenant_a,
    )
    assert form_max.is_valid(), form_max.errors

    # Test order_delivery_csat below minimum (0) and above maximum (7)
    form_delivery_low = CustomerSatisfactionSurveyForm(
        data=_customersupport_survey_payload(survey_type="order_delivery_csat", rating_score=0),
        tenant=tenant_a,
    )
    assert not form_delivery_low.is_valid()
    assert "rating_score" in form_delivery_low.errors

    form_delivery_high = CustomerSatisfactionSurveyForm(
        data=_customersupport_survey_payload(survey_type="order_delivery_csat", rating_score=7),
        tenant=tenant_a,
    )
    assert not form_delivery_high.is_valid()
    assert "rating_score" in form_delivery_high.errors

    # Test order_delivery_csat valid middle value (3)
    form_delivery_valid = CustomerSatisfactionSurveyForm(
        data=_customersupport_survey_payload(survey_type="order_delivery_csat", rating_score=3),
        tenant=tenant_a,
    )
    assert form_delivery_valid.is_valid(), form_delivery_valid.errors


def test_customersupport_survey_form_nps_rating_boundary_enforcement(tenant_a):
    """NPS survey type (storefront_nps) requires rating score between 0 and 10."""
    # Test storefront_nps below minimum (-1)
    payload_nps_low = _customersupport_survey_payload(survey_type="storefront_nps", rating_score=-1)
    form = CustomerSatisfactionSurveyForm(data=payload_nps_low, tenant=tenant_a)
    assert not form.is_valid()
    assert "rating_score" in form.errors

    # Test storefront_nps above maximum (11)
    payload_nps_high = _customersupport_survey_payload(survey_type="storefront_nps", rating_score=11)
    form = CustomerSatisfactionSurveyForm(data=payload_nps_high, tenant=tenant_a)
    assert not form.is_valid()
    assert "rating_score" in form.errors
    assert "NPS surveys require a rating score between 0 and 10." in form.errors["rating_score"]

    # Test storefront_nps valid boundaries (0 and 10)
    form_nps_0 = CustomerSatisfactionSurveyForm(
        data=_customersupport_survey_payload(survey_type="storefront_nps", rating_score=0, sentiment="negative"),
        tenant=tenant_a,
    )
    assert form_nps_0.is_valid(), form_nps_0.errors

    form_nps_10 = CustomerSatisfactionSurveyForm(
        data=_customersupport_survey_payload(survey_type="storefront_nps", rating_score=10, sentiment="positive"),
        tenant=tenant_a,
    )
    assert form_nps_10.is_valid(), form_nps_10.errors


def test_customersupport_survey_form_intra_tenant_shopper_consistency_valid(tenant_a, ecom_order_a, ecom_profile_a):
    """Survey with matching customer profile and order shopper succeeds cleanly."""
    payload = _customersupport_survey_payload(order=ecom_order_a, customer=ecom_profile_a)
    form = CustomerSatisfactionSurveyForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_customersupport_survey_form_intra_tenant_shopper_consistency_mismatch(tenant_a, ecom_order_a):
    """Survey with order belonging to shopper A but customer profile of shopper B is rejected."""
    alt_profile = _customersupport_create_customer(tenant_a, name="Mismatched Survey Shopper")
    payload = _customersupport_survey_payload(order=ecom_order_a, customer=alt_profile)
    form = CustomerSatisfactionSurveyForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors
    assert "The selected order does not belong to the selected customer profile." in form.errors["order"]
