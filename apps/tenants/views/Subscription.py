"""tenants — Subscription views (split from apps/tenants/views.py)."""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    Subscription,
    SubscriptionInvoice,
)
from apps.tenants.forms import (
    SubscriptionForm,
)


# ============================================================= Subscriptions
@tenant_admin_required
def subscription_list(request):
    return crud_list(
        request, Subscription.objects.filter(tenant=request.tenant),
        "tenants/subscription/list.html",
        search_fields=["plan", "status"],
        filters=[("status", "status", False), ("plan", "plan", False)],
        extra_context={"status_choices": Subscription.STATUS_CHOICES,
                       "plan_choices": Subscription.PLAN_CHOICES,
                       "stripe_enabled": stripe_utils.is_enabled()},
    )


@tenant_admin_required
def subscription_create(request):
    return crud_create(request, form_class=SubscriptionForm, template="tenants/subscription/form.html",
                       success_url="tenants:subscription_list")


@tenant_admin_required
def subscription_detail(request, pk):
    obj = get_object_or_404(Subscription, pk=pk, tenant=request.tenant)
    return render(request, "tenants/subscription/detail.html", {
        "obj": obj,
        "invoices": obj.invoices.order_by("-issued_on")[:50],  # cap embedded list
        "stripe_enabled": stripe_utils.is_enabled(),
    })


@tenant_admin_required
def subscription_edit(request, pk):
    return crud_edit(request, model=Subscription, pk=pk, form_class=SubscriptionForm,
                     template="tenants/subscription/form.html", success_url="tenants:subscription_list")


@tenant_admin_required
@require_POST
def subscription_delete(request, pk):
    return crud_delete(request, model=Subscription, pk=pk, success_url="tenants:subscription_list")


@tenant_admin_required
@require_POST
def subscription_checkout(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, tenant=request.tenant)
    if not stripe_utils.is_enabled():
        messages.info(request, "Stripe is not configured. Use “Mark as paid” to record payment manually.")
        return redirect("tenants:subscription_detail", pk=sub.pk)
    return_url = reverse("tenants:stripe_return")
    success = request.build_absolute_uri(f"{return_url}?status=success&sub={sub.pk}")
    cancel = request.build_absolute_uri(f"{return_url}?status=cancel&sub={sub.pk}")
    try:
        session = stripe_utils.create_checkout_session(sub, success, cancel)
    except Exception as exc:  # surfacing Stripe/config errors without a 500
        messages.error(request, f"Could not start checkout: {exc}")
        return redirect("tenants:subscription_detail", pk=sub.pk)
    if session is None or not getattr(session, "url", None):
        messages.error(request, "Stripe price IDs are not configured for this plan.")
        return redirect("tenants:subscription_detail", pk=sub.pk)
    return redirect(session.url)


@tenant_admin_required
@require_POST
def subscription_mark_paid(request, pk):
    """Manual settlement when Stripe is not configured."""
    sub = get_object_or_404(Subscription, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        sub.status = "active"
        if not sub.started_on:
            sub.started_on = timezone.localdate()
        sub.renews_on = timezone.localdate() + timezone.timedelta(days=30)
        sub.save()
        invoice = SubscriptionInvoice.objects.create(
            tenant=sub.tenant, subscription=sub, status="paid", amount=sub.amount,
            issued_on=timezone.localdate(), paid_at=timezone.now(),
        )
    write_audit_log(request.user, sub, "update", {"action": "mark_paid"})
    write_audit_log(request.user, invoice, "create")
    messages.success(request, "Subscription marked as paid and an invoice was recorded.")
    return redirect("tenants:subscription_detail", pk=sub.pk)


@tenant_admin_required
def stripe_return(request):
    result = request.GET.get("status", "")
    sub = Subscription.objects.filter(pk=request.GET.get("sub"), tenant=request.tenant).first()
    return render(request, "tenants/stripe_return.html", {"result": result, "obj": sub})


@csrf_exempt
@require_POST
def stripe_webhook(request):
    # WARNING: never trust an unverified event. Require the signing secret + valid signature.
    if not stripe_utils.is_enabled() or not getattr(settings, "STRIPE_WEBHOOK_SECRET", ""):
        return HttpResponse(status=400)
    import stripe

    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        # WARNING: reject tampered/forged payloads.
        return HttpResponse(status=400)

    etype = event["type"]
    data = event["data"]["object"]

    # WARNING: always match events back to our records via Stripe-issued ids /
    # client_reference_id we set — never via caller-supplied tenant params.
    if etype == "checkout.session.completed":
        sub = Subscription.objects.filter(pk=data.get("client_reference_id")).first()
        if sub:
            sub.stripe_customer_id = data.get("customer") or sub.stripe_customer_id
            sub.stripe_subscription_id = data.get("subscription") or sub.stripe_subscription_id
            sub.status = "active"
            sub.save()
    elif etype == "invoice.paid":
        sub = Subscription.objects.filter(stripe_subscription_id=data.get("subscription")).first()
        if sub:
            inv_id = data.get("id", "")
            # Idempotent: Stripe retries — don't double-record.
            if inv_id and not SubscriptionInvoice.objects.filter(stripe_invoice_id=inv_id).exists():
                SubscriptionInvoice.objects.create(
                    tenant=sub.tenant, subscription=sub, status="paid",
                    amount=Decimal(data.get("amount_paid", 0)) / 100,
                    issued_on=timezone.localdate(), paid_at=timezone.now(), stripe_invoice_id=inv_id,
                )
            if sub.status != "active":
                sub.status = "active"
                sub.save(update_fields=["status"])
    elif etype == "invoice.payment_failed":
        Subscription.objects.filter(stripe_subscription_id=data.get("subscription")).update(status="past_due")
    elif etype == "customer.subscription.updated":
        sub = Subscription.objects.filter(stripe_subscription_id=data.get("id")).first()
        if sub:
            valid = dict(Subscription.STATUS_CHOICES)
            new_status = data.get("status")
            if new_status in valid:
                sub.status = new_status
                sub.save(update_fields=["status"])
    elif etype == "customer.subscription.deleted":
        Subscription.objects.filter(stripe_subscription_id=data.get("id")).update(status="canceled")

    return HttpResponse(status=200)
