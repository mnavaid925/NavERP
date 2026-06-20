"""Module 0.1 views: subscription/billing (Stripe + manual fallback), branding,
encryption keys (reveal-once), health metrics, and the onboarding wizard.

Security notes are flagged inline with WARNING. The Stripe webhook is the only
CSRF-exempt endpoint and is safe because every event is signature-verified.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log

from . import stripe_utils
from .forms import (
    BrandingSettingForm,
    EncryptionKeyForm,
    HealthMetricForm,
    OnboardingForm,
    SubscriptionForm,
    SubscriptionInvoiceForm,
)
from .models import (
    BrandingSetting,
    EncryptionKey,
    HealthMetric,
    Subscription,
    SubscriptionInvoice,
)

KEY_REVEAL_SESSION = "_key_reveal"


# ============================================================= Subscriptions
@tenant_admin_required
def subscription_list(request):
    return crud_list(
        request, Subscription.objects.filter(tenant=request.tenant),
        "tenants/subscription_list.html",
        search_fields=["plan", "status"],
        filters=[("status", "status", False), ("plan", "plan", False)],
        extra_context={"status_choices": Subscription.STATUS_CHOICES,
                       "plan_choices": Subscription.PLAN_CHOICES,
                       "stripe_enabled": stripe_utils.is_enabled()},
    )


@tenant_admin_required
def subscription_create(request):
    return crud_create(request, form_class=SubscriptionForm, template="tenants/subscription_form.html",
                       success_url="tenants:subscription_list")


@tenant_admin_required
def subscription_detail(request, pk):
    obj = get_object_or_404(Subscription, pk=pk, tenant=request.tenant)
    return render(request, "tenants/subscription_detail.html", {
        "obj": obj,
        "invoices": obj.invoices.order_by("-issued_on")[:50],  # cap embedded list
        "stripe_enabled": stripe_utils.is_enabled(),
    })


@tenant_admin_required
def subscription_edit(request, pk):
    return crud_edit(request, model=Subscription, pk=pk, form_class=SubscriptionForm,
                     template="tenants/subscription_form.html", success_url="tenants:subscription_list")


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


# ========================================================= SubscriptionInvoice
@tenant_admin_required
def subscriptioninvoice_list(request):
    return crud_list(
        request, SubscriptionInvoice.objects.filter(tenant=request.tenant).select_related("subscription"),
        "tenants/subscriptioninvoice_list.html",
        search_fields=["number"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": SubscriptionInvoice.STATUS_CHOICES},
    )


@tenant_admin_required
def subscriptioninvoice_create(request):
    return crud_create(request, form_class=SubscriptionInvoiceForm,
                       template="tenants/subscriptioninvoice_form.html",
                       success_url="tenants:subscriptioninvoice_list")


@tenant_admin_required
def subscriptioninvoice_detail(request, pk):
    obj = get_object_or_404(SubscriptionInvoice.objects.select_related("subscription"),
                            pk=pk, tenant=request.tenant)
    return render(request, "tenants/subscriptioninvoice_detail.html", {"obj": obj})


@tenant_admin_required
def subscriptioninvoice_edit(request, pk):
    return crud_edit(request, model=SubscriptionInvoice, pk=pk, form_class=SubscriptionInvoiceForm,
                     template="tenants/subscriptioninvoice_form.html",
                     success_url="tenants:subscriptioninvoice_list")


@tenant_admin_required
@require_POST
def subscriptioninvoice_delete(request, pk):
    return crud_delete(request, model=SubscriptionInvoice, pk=pk,
                       success_url="tenants:subscriptioninvoice_list")


# ============================================================== Branding
@tenant_admin_required
def brandingsetting_list(request):
    return crud_list(
        request, BrandingSetting.objects.filter(tenant=request.tenant),
        "tenants/brandingsetting_list.html", search_fields=["email_from_name"],
    )


@tenant_admin_required
def brandingsetting_create(request):
    existing = BrandingSetting.objects.filter(tenant=request.tenant).first()
    if existing:  # OneToOne — edit the existing record instead of failing on the unique constraint
        return redirect("tenants:brandingsetting_edit", pk=existing.pk)
    return crud_create(request, form_class=BrandingSettingForm,
                       template="tenants/brandingsetting_form.html",
                       success_url="tenants:brandingsetting_list")


@tenant_admin_required
def brandingsetting_detail(request, pk):
    obj = get_object_or_404(BrandingSetting, pk=pk, tenant=request.tenant)
    return render(request, "tenants/brandingsetting_detail.html", {"obj": obj})


@tenant_admin_required
def brandingsetting_edit(request, pk):
    return crud_edit(request, model=BrandingSetting, pk=pk, form_class=BrandingSettingForm,
                     template="tenants/brandingsetting_form.html",
                     success_url="tenants:brandingsetting_list")


@tenant_admin_required
@require_POST
def brandingsetting_delete(request, pk):
    return crud_delete(request, model=BrandingSetting, pk=pk, success_url="tenants:brandingsetting_list")


# ========================================================== Encryption keys
@tenant_admin_required
def encryptionkey_list(request):
    return crud_list(
        request, EncryptionKey.objects.filter(tenant=request.tenant),
        "tenants/encryptionkey_list.html",
        search_fields=["name", "prefix"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": EncryptionKey.STATUS_CHOICES},
    )


@tenant_admin_required
def encryptionkey_create(request):
    if request.method == "POST":
        form = EncryptionKeyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            key = form.save(commit=False)
            key.tenant = request.tenant
            plaintext = EncryptionKey.generate_plaintext()
            key.set_secret(plaintext)
            key.save()
            write_audit_log(request.user, key, "create")
            # L25: reveal the plaintext exactly once via a pop-once session key (never via messages).
            request.session[KEY_REVEAL_SESSION] = {"pk": key.pk, "secret": plaintext}
            messages.success(request, "Encryption key created. Copy the secret now — it won't be shown again.")
            return redirect("tenants:encryptionkey_detail", pk=key.pk)
    else:
        form = EncryptionKeyForm(tenant=request.tenant)
    return render(request, "tenants/encryptionkey_form.html", {"form": form, "is_edit": False})


@tenant_admin_required
def encryptionkey_detail(request, pk):
    obj = get_object_or_404(EncryptionKey, pk=pk, tenant=request.tenant)
    reveal = request.session.pop(KEY_REVEAL_SESSION, None)
    plaintext_once = reveal["secret"] if reveal and reveal.get("pk") == obj.pk else None
    return render(request, "tenants/encryptionkey_detail.html",
                  {"obj": obj, "plaintext_once": plaintext_once})


@tenant_admin_required
def encryptionkey_edit(request, pk):
    return crud_edit(request, model=EncryptionKey, pk=pk, form_class=EncryptionKeyForm,
                     template="tenants/encryptionkey_form.html",
                     success_url="tenants:encryptionkey_list")


@tenant_admin_required
@require_POST
def encryptionkey_rotate(request, pk):
    key = get_object_or_404(EncryptionKey, pk=pk, tenant=request.tenant)
    plaintext = EncryptionKey.generate_plaintext()
    key.set_secret(plaintext)
    key.status = "active"
    key.last_rotated_at = timezone.now()
    key.save()
    write_audit_log(request.user, key, "update", {"action": "rotate"})
    request.session[KEY_REVEAL_SESSION] = {"pk": key.pk, "secret": plaintext}
    messages.success(request, "Key rotated. Copy the new secret now — it won't be shown again.")
    return redirect("tenants:encryptionkey_detail", pk=key.pk)


@tenant_admin_required
@require_POST
def encryptionkey_delete(request, pk):
    return crud_delete(request, model=EncryptionKey, pk=pk, success_url="tenants:encryptionkey_list")


# ============================================================ Health metrics
@tenant_admin_required
def healthmetric_list(request):
    return crud_list(
        request, HealthMetric.objects.filter(tenant=request.tenant),
        "tenants/healthmetric_list.html",
        search_fields=["metric"],
        filters=[("metric", "metric", False), ("status", "status", False)],
        extra_context={"metric_choices": HealthMetric.METRIC_CHOICES,
                       "status_choices": HealthMetric.STATUS_CHOICES},
    )


@tenant_admin_required
def healthmetric_create(request):
    return crud_create(request, form_class=HealthMetricForm, template="tenants/healthmetric_form.html",
                       success_url="tenants:healthmetric_list")


@tenant_admin_required
def healthmetric_detail(request, pk):
    obj = get_object_or_404(HealthMetric, pk=pk, tenant=request.tenant)
    return render(request, "tenants/healthmetric_detail.html", {"obj": obj})


@tenant_admin_required
def healthmetric_edit(request, pk):
    return crud_edit(request, model=HealthMetric, pk=pk, form_class=HealthMetricForm,
                     template="tenants/healthmetric_form.html", success_url="tenants:healthmetric_list")


@tenant_admin_required
@require_POST
def healthmetric_delete(request, pk):
    return crud_delete(request, model=HealthMetric, pk=pk, success_url="tenants:healthmetric_list")


# =============================================================== Onboarding
@tenant_admin_required
def onboarding(request):
    if request.tenant is None:
        messages.info(request, "Onboarding applies to a tenant workspace. Sign in as a tenant admin.")
        return redirect("dashboard:home")
    form = OnboardingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        plan = form.cleaned_data["plan"]
        sub = Subscription.objects.filter(tenant=request.tenant).first() or Subscription(tenant=request.tenant)
        sub.plan = plan
        sub.seats = form.cleaned_data["seats"]
        sub.status = "trialing"
        if not sub.started_on:
            sub.started_on = timezone.localdate()
        sub.renews_on = timezone.localdate() + timezone.timedelta(days=14)
        sub.save()

        branding, _ = BrandingSetting.objects.get_or_create(tenant=request.tenant)
        branding.primary_color = form.cleaned_data["primary_color"]
        branding.accent_color = form.cleaned_data["accent_color"]
        if form.cleaned_data.get("logo"):
            branding.logo = form.cleaned_data["logo"]
        branding.save()

        request.tenant.plan = plan
        request.tenant.save(update_fields=["plan"])
        messages.success(request, "Workspace configured. Welcome aboard!")
        return redirect("dashboard:home")
    return render(request, "tenants/onboarding_wizard.html", {"form": form})
