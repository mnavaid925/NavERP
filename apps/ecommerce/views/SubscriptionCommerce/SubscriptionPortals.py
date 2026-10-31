import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.models.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscription
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionAction
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def subscription_portal(request):
    subs_qs = ecommerce_scope(CustomerSubscription.objects.all(), request).select_related(
        "customer_profile__customer", "customer_profile__user", "plan", "product", "variant"
    )

    active_subscriptions = subs_qs.filter(status="active").order_by("next_billing_date")[:25]
    paused_subscriptions = subs_qs.filter(status="paused").order_by("-updated_at")[:25]
    retention_actions = ecommerce_scope(SubscriptionRetentionAction.objects.all(), request).select_related(
        "subscription", "customer_profile__customer", "customer_profile__user"
    ).order_by("-created_at")[:10]

    total_subscribers = subs_qs.filter(status="active").count()
    mrr_multiplier = Case(
        When(plan__frequency="weekly", then=Value(Decimal("4.3333"))),
        When(plan__frequency="biweekly", then=Value(Decimal("2.1667"))),
        When(plan__frequency="monthly", then=Value(Decimal("1.0000"))),
        When(plan__frequency="bimonthly", then=Value(Decimal("0.5000"))),
        When(plan__frequency="quarterly", then=Value(Decimal("0.3333"))),
        When(plan__frequency="annual", then=Value(Decimal("0.0833"))),
        default=Value(Decimal("1.0000")),
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )
    cycle_net = F("unit_price") * F("quantity") * (Value(Decimal("1.0000")) - F("recurring_discount_pct") / Value(Decimal("100.0000")))
    mrr_agg = subs_qs.filter(status="active").aggregate(
        total_mrr=Coalesce(
            Sum(cycle_net * mrr_multiplier, output_field=DecimalField(max_digits=14, decimal_places=2)),
            Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
        )
    )
    monthly_recurring_revenue = (mrr_agg["total_mrr"] or Decimal("0.00")).quantize(Decimal("0.01"))

    context = {
        "active_subscriptions": active_subscriptions,
        "paused_subscriptions": paused_subscriptions,
        "retention_actions": retention_actions,
        "total_subscribers": total_subscribers,
        "monthly_recurring_revenue": monthly_recurring_revenue,
    }
    return render(request, "ecommerce/subscriptioncommerce/portal/portal.html", context)


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def subscription_portal_skip(request, pk):
    subscription = ecommerce_object(request, CustomerSubscription, pk)
    if not subscription.plan.allow_skip:
        messages.error(request, f"Plan '{subscription.plan.name}' does not permit delivery skips.")
        return redirect("ecommerce:subscription_portal")

    # Shift next billing date by 30 days or cadence
    old_date = subscription.next_billing_date
    subscription.next_billing_date = old_date + datetime.timedelta(days=30)
    if subscription.next_delivery_date:
        subscription.next_delivery_date = subscription.next_delivery_date + datetime.timedelta(days=30)
    subscription.save(update_fields=["next_billing_date", "next_delivery_date", "updated_at"])

    SubscriptionRetentionAction.objects.create(
        tenant=request.tenant,
        subscription=subscription,
        customer_profile=subscription.customer_profile,
        trigger_type="pause_request",
        cancellation_reason="temporary_break",
        offered_action="free_skip",
        outcome="deflected",
        notes=f"Subscriber skipped delivery cycle from {old_date} to {subscription.next_billing_date}.",
    )

    write_audit_log(
        request.user,
        subscription,
        "update",
        {"action": "skip_cycle", "new_date": str(subscription.next_billing_date)},
        tenant=request.tenant,
    )
    messages.success(request, f"Upcoming cycle skipped. Next billing moved to {subscription.next_billing_date}.")
    return redirect("ecommerce:subscription_portal")


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def subscription_portal_pause(request, pk):
    subscription = ecommerce_object(request, CustomerSubscription, pk)
    if not subscription.plan.allow_pause:
        messages.error(request, f"Plan '{subscription.plan.name}' does not permit pausing.")
        return redirect("ecommerce:subscription_portal")

    pause_days = min(subscription.plan.max_pause_days, 60)
    subscription.status = "paused"
    subscription.paused_until = timezone.now().date() + datetime.timedelta(days=pause_days)
    subscription.save(update_fields=["status", "paused_until", "updated_at"])

    SubscriptionRetentionAction.objects.create(
        tenant=request.tenant,
        subscription=subscription,
        customer_profile=subscription.customer_profile,
        trigger_type="pause_request",
        cancellation_reason="temporary_break",
        offered_action="pause_duration",
        outcome="paused",
        notes=f"Subscriber paused delivery for {pause_days} days until {subscription.paused_until}.",
    )

    write_audit_log(
        request.user,
        subscription,
        "update",
        {"action": "pause_subscription", "paused_until": str(subscription.paused_until)},
        tenant=request.tenant,
    )
    messages.warning(request, f"Subscription {subscription.number} paused until {subscription.paused_until}.")
    return redirect("ecommerce:subscription_portal")


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def subscription_portal_resume(request, pk):
    subscription = ecommerce_object(request, CustomerSubscription, pk)
    subscription.status = "active"
    subscription.paused_until = None
    subscription.next_billing_date = timezone.now().date() + datetime.timedelta(days=7)
    subscription.save(update_fields=["status", "paused_until", "next_billing_date", "updated_at"])

    write_audit_log(
        request.user,
        subscription,
        "update",
        {"action": "resume_subscription", "next_billing": str(subscription.next_billing_date)},
        tenant=request.tenant,
    )
    messages.success(request, f"Subscription {subscription.number} reactivated. Next billing on {subscription.next_billing_date}.")
    return redirect("ecommerce:subscription_portal")


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def subscription_portal_deflect(request, pk):
    subscription = ecommerce_object(request, CustomerSubscription, pk)
    reason = request.POST.get("reason", "too_much_product")
    action_choice = request.POST.get("action_choice", "discount_cycle")

    if action_choice == "discount_cycle":
        subscription.recurring_discount_pct = min(Decimal("50.00"), subscription.recurring_discount_pct + Decimal("15.00"))
        subscription.save(update_fields=["recurring_discount_pct", "updated_at"])
        outcome = "deflected"
        offer = "discount_cycle"
        discount_val = Decimal("15.00")
        msg = f"Applied 15% deflection discount to subscription {subscription.number}."
    elif action_choice == "pause_duration":
        subscription.status = "paused"
        subscription.paused_until = timezone.now().date() + datetime.timedelta(days=60)
        subscription.save(update_fields=["status", "paused_until", "updated_at"])
        outcome = "paused"
        offer = "pause_duration"
        discount_val = Decimal("0.00")
        msg = f"Subscription {subscription.number} paused for 60 days instead of cancelling."
    else:
        subscription.status = "cancelled"
        subscription.cancelled_at = timezone.now()
        subscription.cancellation_reason = reason
        subscription.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
        outcome = "cancelled"
        offer = "none"
        discount_val = Decimal("0.00")
        msg = f"Subscription {subscription.number} has been cancelled per customer request."

    SubscriptionRetentionAction.objects.create(
        tenant=request.tenant,
        subscription=subscription,
        customer_profile=subscription.customer_profile,
        trigger_type="cancel_intent",
        cancellation_reason=reason,
        offered_action=offer,
        offer_discount_pct=discount_val,
        outcome=outcome,
        notes=f"Self-service portal exit flow: chose {action_choice} with reason {reason}.",
    )

    write_audit_log(
        request.user,
        subscription,
        "update",
        {"action": "retention_flow", "outcome": outcome},
        tenant=request.tenant,
    )

    if outcome == "deflected":
        messages.success(request, msg)
    elif outcome == "paused":
        messages.info(request, msg)
    else:
        messages.warning(request, msg)

    return redirect("ecommerce:subscription_portal")
