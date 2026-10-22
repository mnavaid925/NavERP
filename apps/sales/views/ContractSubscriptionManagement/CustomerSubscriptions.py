"""Sales 8.15 — CustomerSubscription views."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.ContractSubscriptionManagement.CustomerSubscriptions import (
    CustomerSubscriptionFilterForm,
    CustomerSubscriptionForm,
    SubscriptionCancelForm,
    SubscriptionPauseForm,
    SubscriptionUpgradeForm,
)
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import (
    BILLING_CADENCE_CHOICES,
    PRICING_MODEL_CHOICES,
    SUBSCRIPTION_STATUS_CHOICES,
    CustomerSubscription,
)


@login_required
def customer_subscription_list(request):
    tenant = request.tenant
    qs = CustomerSubscription.objects.filter(tenant=tenant).select_related("account", "contract", "currency", "owner")

    filter_form = CustomerSubscriptionFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(
                Q(number__icontains=q)
                | Q(subscription_name__icontains=q)
                | Q(plan_code__icontains=q)
                | Q(account__name__icontains=q)
            )

        status = filter_form.cleaned_data.get("status")
        if status:
            qs = qs.filter(status=status)

        pricing_model = filter_form.cleaned_data.get("pricing_model")
        if pricing_model:
            qs = qs.filter(pricing_model=pricing_model)

        billing_cadence = filter_form.cleaned_data.get("billing_cadence")
        if billing_cadence:
            qs = qs.filter(billing_cadence=billing_cadence)

        account = filter_form.cleaned_data.get("account")
        if account:
            qs = qs.filter(account=account)

    # Aggregates
    all_subs = CustomerSubscription.objects.filter(tenant=tenant)
    total_mrr = all_subs.filter(status="active").aggregate(total=Sum("mrr"))["total"] or Decimal("0.00")
    active_count = all_subs.filter(status="active").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "subscriptions": page_obj.object_list,
        "page_obj": page_obj,
        "filter_form": filter_form,
        "status_choices": SUBSCRIPTION_STATUS_CHOICES,
        "pricing_model_choices": PRICING_MODEL_CHOICES,
        "cadence_choices": BILLING_CADENCE_CHOICES,
        "total_mrr": total_mrr,
        "active_count": active_count,
    }
    return render(request, "sales/contractsubscriptionmanagement/customersubscription/list.html", context)


@login_required
@transaction.atomic
def customer_subscription_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = CustomerSubscriptionForm(request.POST, tenant=tenant)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.tenant = tenant
            sub.mrr = sub.calculate_mrr()
            sub.save()
            write_audit_log(
                user=request.user,
                obj=sub,
                action="create",
                tenant=tenant,
            )
            messages.success(request, f"Subscription {sub.number} created successfully.")
            return redirect("sales:customer_subscription_detail", pk=sub.pk)
    else:
        initial = {}
        contract_id = request.GET.get("contract")
        if contract_id and contract_id.isdigit():
            contract = CustomerContract.objects.filter(tenant=tenant, pk=contract_id).first()
            if contract:
                initial["contract"] = contract
                initial["account"] = contract.account
                initial["currency"] = contract.currency
                initial["owner"] = contract.owner

        form = CustomerSubscriptionForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "subscription": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "sales/contractsubscriptionmanagement/customersubscription/form.html", context)


@login_required
def customer_subscription_detail(request, pk):
    tenant = request.tenant
    subscription = get_object_or_404(
        CustomerSubscription.objects.filter(tenant=tenant).select_related(
            "account", "contract", "currency", "owner", "renewal_quote"
        ),
        pk=pk,
    )
    usage_records = subscription.usage_records.all()
    obligations = subscription.obligations.all()

    context = {
        "subscription": subscription,
        "obj": subscription,
        "usage_records": usage_records,
        "obligations": obligations,
        "pause_form": SubscriptionPauseForm(),
        "cancel_form": SubscriptionCancelForm(),
        "upgrade_form": SubscriptionUpgradeForm(
            initial={"quantity": subscription.quantity, "unit_price": subscription.unit_price}
        ),
    }
    return render(request, "sales/contractsubscriptionmanagement/customersubscription/detail.html", context)


@login_required
@transaction.atomic
def customer_subscription_edit(request, pk):
    tenant = request.tenant
    subscription = get_object_or_404(CustomerSubscription.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = CustomerSubscriptionForm(request.POST, instance=subscription, tenant=tenant)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.mrr = sub.calculate_mrr()
            sub.save()
            write_audit_log(
                user=request.user,
                obj=sub,
                action="update",
                tenant=tenant,
            )
            messages.success(request, f"Subscription {sub.number} updated successfully.")
            return redirect("sales:customer_subscription_detail", pk=sub.pk)
    else:
        form = CustomerSubscriptionForm(instance=subscription, tenant=tenant)

    context = {
        "form": form,
        "subscription": subscription,
        "obj": subscription,
        "is_edit": True,
    }
    return render(request, "sales/contractsubscriptionmanagement/customersubscription/form.html", context)


@login_required
@require_POST
@transaction.atomic
def customer_subscription_delete(request, pk):
    tenant = request.tenant
    subscription = get_object_or_404(CustomerSubscription.objects.filter(tenant=tenant), pk=pk)
    number = subscription.number
    write_audit_log(
        user=request.user,
        obj=subscription,
        action="delete",
        tenant=tenant,
    )
    subscription.delete()
    messages.success(request, f"Subscription {number} deleted successfully.")
    return redirect("sales:customer_subscription_list")


@login_required
@require_POST
@transaction.atomic
def customer_subscription_pause(request, pk):
    tenant = request.tenant
    subscription = get_object_or_404(CustomerSubscription.objects.filter(tenant=tenant), pk=pk)
    subscription.status = "paused"
    subscription.paused_at = timezone.now()
    subscription.save(update_fields=["status", "paused_at", "updated_at"])
    write_audit_log(
        user=request.user,
        obj=subscription,
        action="update",
        tenant=tenant,
    )
    messages.success(request, f"Subscription {subscription.number} paused.")
    return redirect("sales:customer_subscription_detail", pk=subscription.pk)


@login_required
@require_POST
@transaction.atomic
def customer_subscription_resume(request, pk):
    tenant = request.tenant
    subscription = get_object_or_404(CustomerSubscription.objects.filter(tenant=tenant), pk=pk)
    subscription.status = "active"
    subscription.resumed_at = timezone.now()
    subscription.save(update_fields=["status", "resumed_at", "updated_at"])
    write_audit_log(
        user=request.user,
        obj=subscription,
        action="update",
        tenant=tenant,
    )
    messages.success(request, f"Subscription {subscription.number} resumed to active status.")
    return redirect("sales:customer_subscription_detail", pk=subscription.pk)


@login_required
@require_POST
@transaction.atomic
def customer_subscription_cancel(request, pk):
    tenant = request.tenant
    subscription = get_object_or_404(CustomerSubscription.objects.filter(tenant=tenant), pk=pk)
    reason = request.POST.get("cancellation_reason", "").strip()
    if not reason:
        messages.error(request, "Cancellation reason is required.")
        return redirect("sales:customer_subscription_detail", pk=subscription.pk)

    subscription.status = "cancelled"
    subscription.cancelled_at = timezone.now()
    subscription.cancellation_reason = reason
    subscription.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
    write_audit_log(
        user=request.user,
        obj=subscription,
        action="update",
        tenant=tenant,
    )
    messages.success(request, f"Subscription {subscription.number} cancelled.")
    return redirect("sales:customer_subscription_detail", pk=subscription.pk)


@login_required
@require_POST
@transaction.atomic
def customer_subscription_upgrade(request, pk):
    tenant = request.tenant
    subscription = get_object_or_404(CustomerSubscription.objects.filter(tenant=tenant), pk=pk)
    form = SubscriptionUpgradeForm(request.POST)
    if form.is_valid():
        subscription.quantity = form.cleaned_data["quantity"]
        subscription.unit_price = form.cleaned_data["unit_price"]
        subscription.mrr = subscription.calculate_mrr()
        subscription.save(update_fields=["quantity", "unit_price", "mrr", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=subscription,
            action="update",
            tenant=tenant,
        )
        messages.success(request, f"Subscription {subscription.number} upgraded successfully.")
    else:
        messages.error(request, "Invalid upgrade parameters.")
    return redirect("sales:customer_subscription_detail", pk=subscription.pk)
