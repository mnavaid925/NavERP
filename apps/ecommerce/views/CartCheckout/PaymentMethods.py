from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CartCheckout.PaymentMethods import PaymentMethodConfigForm
from apps.ecommerce.models.CartCheckout.PaymentMethods import PaymentMethodConfig
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def paymentmethodconfig_list(request):
    """List payment method configurations with provider and category filters."""
    qs = ecommerce_scope(PaymentMethodConfig.objects.all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(provider__icontains=q)
            | Q(instructions__icontains=q)
        )

    current_provider = request.GET.get("provider", "").strip()
    if current_provider:
        qs = qs.filter(provider=current_provider)

    current_category = request.GET.get("method_category", "").strip()
    if current_category:
        qs = qs.filter(method_category=current_category)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "methods": page_obj.object_list,
        "provider_choices": PaymentMethodConfig.PROVIDER_CHOICES,
        "category_choices": PaymentMethodConfig.CATEGORY_CHOICES,
        "current_q": q,
        "current_provider": current_provider,
        "current_category": current_category,
    }
    return render(request, "ecommerce/cartcheckout/paymentmethodconfig/list.html", context)


@login_required
def paymentmethodconfig_detail(request, pk):
    """View details of a payment gateway method."""
    method = ecommerce_object(request, PaymentMethodConfig, pk)

    context = {
        "method": method,
    }
    return render(request, "ecommerce/cartcheckout/paymentmethodconfig/detail.html", context)


@login_required
def paymentmethodconfig_create(request):
    """Create a new payment method configuration."""
    if request.method == "POST":
        form = PaymentMethodConfigForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            method = form.save(commit=False)
            method.tenant = request.tenant
            method.save()
            write_audit_log(
                request.user,
                method,
                "create",
                {"name": method.name, "provider": method.provider},
            )
            messages.success(request, f"Payment method '{method.name}' created successfully.")
            return redirect("ecommerce:paymentmethodconfig_detail", pk=method.pk)
    else:
        form = PaymentMethodConfigForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/cartcheckout/paymentmethodconfig/form.html", context)


@login_required
def paymentmethodconfig_edit(request, pk):
    """Edit an existing payment method configuration."""
    method = ecommerce_object(request, PaymentMethodConfig, pk)

    if request.method == "POST":
        form = PaymentMethodConfigForm(request.POST, instance=method, tenant=request.tenant)
        if form.is_valid():
            method = form.save()
            write_audit_log(
                request.user,
                method,
                "update",
                {"name": method.name, "provider": method.provider},
            )
            messages.success(request, f"Payment method '{method.name}' updated successfully.")
            return redirect("ecommerce:paymentmethodconfig_detail", pk=method.pk)
    else:
        form = PaymentMethodConfigForm(instance=method, tenant=request.tenant)

    context = {
        "form": form,
        "method": method,
        "is_edit": True,
    }
    return render(request, "ecommerce/cartcheckout/paymentmethodconfig/form.html", context)


@login_required
@require_POST
def paymentmethodconfig_delete(request, pk):
    """Delete a payment method configuration."""
    method = ecommerce_object(request, PaymentMethodConfig, pk)
    name = method.name
    method.delete()
    write_audit_log(
        request.user,
        method,
        "delete",
        {"name": name},
    )
    messages.success(request, f"Payment method '{name}' was deleted.")
    return redirect("ecommerce:paymentmethodconfig_list")


@login_required
@require_POST
def paymentmethodconfig_toggle(request, pk):
    """Toggle active state of a payment method."""
    method = ecommerce_object(request, PaymentMethodConfig, pk)
    method.is_active = not method.is_active
    method.save(update_fields=["is_active", "updated_at"])
    write_audit_log(
        request.user,
        method,
        "toggle",
        {"is_active": method.is_active},
    )
    state_str = "activated" if method.is_active else "deactivated"
    messages.success(request, f"Payment method '{method.name}' {state_str}.")
    return redirect("ecommerce:paymentmethodconfig_detail", pk=method.pk)
