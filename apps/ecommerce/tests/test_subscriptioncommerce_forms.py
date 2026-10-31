from decimal import Decimal
import pytest
from django.utils import timezone

from apps.ecommerce.forms.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscriptionForm
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionBoxCurations import SubscriptionBoxCurationForm
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlanForm
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionActionForm


@pytest.mark.django_db
class TestSubscriptionCommerceForms:
    def test_subscription_plan_form_valid(self, tenant_a, ecom_product_a):
        form = SubscriptionPlanForm(
            data={
                "name": "Artisan Tea Box",
                "code": "artisan-tea-box",
                "plan_type": "curated_box",
                "frequency": "monthly",
                "billing_interval_days": 30,
                "discount_percentage": "10.00",
                "target_product": ecom_product_a.pk,
                "allow_pause": True,
                "max_pause_days": 60,
                "allow_skip": True,
                "is_active": True,
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors
        plan = form.save()
        assert plan.pk is not None
        assert plan.tenant == tenant_a

    def test_customer_subscription_form_valid_and_started_at_omitted(self, tenant_a, ecom_subscription_plan_a, ecom_product_a, ecom_profile_a):
        form = CustomerSubscriptionForm(
            data={
                "customer_profile": ecom_profile_a.pk,
                "plan": ecom_subscription_plan_a.pk,
                "product": ecom_product_a.pk,
                "status": "active",
                "quantity": 2,
                "unit_price": "29.99",
                "recurring_discount_pct": "10.00",
                "next_billing_date": str(timezone.now().date() + timezone.timedelta(days=30)),
                "shipping_address_line": "123 High Street, London",
                "payment_method_ref": "pm_tok_test_abc",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors
        sub = form.save()
        assert sub.started_at is not None
        assert sub.quantity == 2

    def test_customer_subscription_form_variant_product_mismatch(self, tenant_a, ecom_subscription_plan_a, ecom_product_a, ecom_product_b, ecom_profile_a):
        from apps.ecommerce.models import ProductVariant

        variant_b = ProductVariant.objects.create(
            tenant=tenant_a,
            product=ecom_product_b,
            sku="SKU-MISMATCH-FORM",
            name="Mismatched Variant",
        )
        form = CustomerSubscriptionForm(
            data={
                "customer_profile": ecom_profile_a.pk,
                "plan": ecom_subscription_plan_a.pk,
                "product": ecom_product_a.pk,
                "variant": variant_b.pk,
                "status": "active",
                "quantity": 1,
                "unit_price": "15.00",
                "recurring_discount_pct": "0.00",
                "next_billing_date": str(timezone.now().date()),
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "variant" in form.errors

    def test_subscription_box_curation_form_valid(self, tenant_a, ecom_subscription_plan_a, ecom_product_a):
        form = SubscriptionBoxCurationForm(
            data={
                "plan": ecom_subscription_plan_a.pk,
                "primary_product": ecom_product_a.pk,
                "name": "Winter Solstice Box",
                "code": "winter-solstice-2026",
                "cycle_identifier": "2026-12",
                "theme_title": "Winter Warmth",
                "start_date": str(timezone.now().date()),
                "end_date": str(timezone.now().date() + timezone.timedelta(days=30)),
                "is_active": True,
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors
        cur = form.save()
        assert cur.cycle_identifier == "2026-12"

    def test_subscription_retention_action_form_valid(self, tenant_a, ecom_customer_subscription_a):
        form = SubscriptionRetentionActionForm(
            data={
                "subscription": ecom_customer_subscription_a.pk,
                "customer_profile": ecom_customer_subscription_a.customer_profile.pk,
                "trigger_type": "cancel_intent",
                "cancellation_reason": "too_expensive",
                "offered_action": "discount_cycle",
                "offer_discount_pct": "15.00",
                "outcome": "deflected",
                "churn_risk_score": "60.00",
                "notes": "Offered 15% discount for 3 cycles",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors
        act = form.save()
        assert act.outcome == "deflected"

    def test_subscription_retention_action_form_customer_mismatch(self, tenant_a, ecom_customer_subscription_a, ecom_profile_b):
        form = SubscriptionRetentionActionForm(
            data={
                "subscription": ecom_customer_subscription_a.pk,
                "customer_profile": ecom_profile_b.pk,  # Mismatched profile
                "trigger_type": "cancel_intent",
                "cancellation_reason": "too_expensive",
                "offered_action": "none",
                "outcome": "cancelled",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "customer_profile" in form.errors
