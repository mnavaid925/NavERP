"""Stripe (test-mode) helpers. Everything degrades gracefully when keys are absent:
``is_enabled()`` is False, the UI shows a "configure Stripe" state, and billing falls
back to a manual mark-paid flow — so the app runs fully without any Stripe config.
"""
from django.conf import settings


def is_enabled():
    return bool(getattr(settings, "STRIPE_ENABLED", False))


def _client():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def price_for_plan(plan):
    mapping = {
        "starter": getattr(settings, "STRIPE_PRICE_STARTER", ""),
        "pro": getattr(settings, "STRIPE_PRICE_PRO", ""),
        "enterprise": getattr(settings, "STRIPE_PRICE_ENTERPRISE", ""),
    }
    return mapping.get(plan, "")


def create_checkout_session(subscription, success_url, cancel_url):
    """Create a Stripe Checkout Session for a subscription, or None if not configurable."""
    if not is_enabled():
        return None
    price = price_for_plan(subscription.plan)
    if not price:
        return None
    stripe = _client()
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price, "quantity": subscription.seats or 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(subscription.pk),
        customer=subscription.stripe_customer_id or None,
        metadata={"subscription_id": str(subscription.pk), "tenant_id": str(subscription.tenant_id)},
    )
