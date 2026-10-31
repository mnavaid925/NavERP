from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.ecommerce.models import (
    CustomerSubscription,
    SubscriptionBoxCuration,
    SubscriptionPlan,
    SubscriptionRetentionAction,
)


@pytest.mark.django_db
class TestSubscriptionCommerceModels:
    def test_subscription_plan_creation_and_numbering(self, tenant_a, ecom_product_a):
        plan = SubscriptionPlan.objects.create(
            tenant=tenant_a,
            name="Weekly Coffee Drop",
            code="weekly-coffee",
            plan_type="subscribe_save",
            frequency="weekly",
            billing_interval_days=7,
            discount_percentage=Decimal("15.00"),
            target_product=ecom_product_a,
        )
        assert plan.number.startswith("ESPL-")
        assert "Weekly Coffee Drop" in str(plan)
        assert plan.is_active is True

    def test_subscription_plan_validation(self, tenant_a):
        plan = SubscriptionPlan(
            tenant=tenant_a,
            name="Invalid Discount Plan",
            discount_percentage=Decimal("150.00"),  # > 100
        )
        with pytest.raises(ValidationError):
            plan.clean()

    def test_customer_subscription_recurring_total_and_clean(self, tenant_a, ecom_subscription_plan_a, ecom_product_a, ecom_profile_a):
        sub = CustomerSubscription.objects.create(
            tenant=tenant_a,
            plan=ecom_subscription_plan_a,
            product=ecom_product_a,
            customer_profile=ecom_profile_a,
            unit_price=Decimal("100.00"),
            quantity=2,
            recurring_discount_pct=Decimal("20.00"),
            next_billing_date=timezone.now().date(),
        )
        assert sub.number.startswith("ESUB-")
        # 100 * 2 = 200, minus 20% = 160
        assert sub.recurring_total == Decimal("160.00")

    def test_customer_subscription_variant_mismatch_validation(self, tenant_a, tenant_b, ecom_subscription_plan_a, ecom_product_a, ecom_product_b, ecom_profile_a):
        from apps.ecommerce.models import ProductVariant

        variant_b = ProductVariant.objects.create(
            tenant=tenant_a,
            product=ecom_product_b,  # Variant belongs to different product
            sku="SKU-MISMATCH-1",
            name="Mismatched Variant",
        )
        sub = CustomerSubscription(
            tenant=tenant_a,
            plan=ecom_subscription_plan_a,
            product=ecom_product_a,
            variant=variant_b,
            customer_profile=ecom_profile_a,
            unit_price=Decimal("50.00"),
            next_billing_date=timezone.now().date(),
        )
        with pytest.raises(ValidationError):
            sub.clean()

    def test_customer_subscription_negative_price_validation(self, tenant_a, ecom_subscription_plan_a, ecom_product_a, ecom_profile_a):
        sub = CustomerSubscription(
            tenant=tenant_a,
            plan=ecom_subscription_plan_a,
            product=ecom_product_a,
            customer_profile=ecom_profile_a,
            unit_price=Decimal("-10.00"),
            next_billing_date=timezone.now().date(),
        )
        with pytest.raises(ValidationError):
            sub.clean()

    def test_subscription_box_curation_creation_and_clean(self, tenant_a, ecom_subscription_plan_a, ecom_product_a):
        today = timezone.now().date()
        curation = SubscriptionBoxCuration.objects.create(
            tenant=tenant_a,
            plan=ecom_subscription_plan_a,
            primary_product=ecom_product_a,
            name="Holiday Discovery Box",
            code="holiday-discovery-2026",
            cycle_identifier="2026-12",
            start_date=today,
            end_date=today + timezone.timedelta(days=31),
        )
        assert curation.number.startswith("ESBX-")
        assert "Holiday Discovery Box" in str(curation)

        # Invalid dates: end_date before start_date
        invalid_curation = SubscriptionBoxCuration(
            tenant=tenant_a,
            plan=ecom_subscription_plan_a,
            primary_product=ecom_product_a,
            name="Bad Dates Box",
            start_date=today + timezone.timedelta(days=10),
            end_date=today,
        )
        with pytest.raises(ValidationError):
            invalid_curation.clean()

    def test_subscription_retention_action_creation_and_consistency(self, tenant_a, ecom_customer_subscription_a, ecom_profile_b):
        action = SubscriptionRetentionAction.objects.create(
            tenant=tenant_a,
            subscription=ecom_customer_subscription_a,
            customer_profile=ecom_customer_subscription_a.customer_profile,
            trigger_type="cancel_intent",
            cancellation_reason="too_much_product",
            offered_action="discount_cycle",
            offer_discount_pct=Decimal("15.00"),
            outcome="deflected",
        )
        assert action.number.startswith("ESRT-")
        assert "cancel_intent" in str(action)

        # Customer profile mismatch
        invalid_action = SubscriptionRetentionAction(
            tenant=tenant_a,
            subscription=ecom_customer_subscription_a,
            customer_profile=ecom_profile_b,  # profile from different user/tenant
            trigger_type="cancel_intent",
            cancellation_reason="too_much_product",
            offered_action="none",
        )
        with pytest.raises(ValidationError):
            invalid_action.clean()
