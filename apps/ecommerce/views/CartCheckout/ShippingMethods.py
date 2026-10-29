from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CartCheckout.ShippingMethods import ShippingMethodConfigForm
from apps.ecommerce.models.CartCheckout.ShippingMethods import ShippingMethodConfig
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def shippingmethodconfig_list(request):
    """List shipping method configurations with carrier and calculation type filters."""
    qs = ecommerce_scope(ShippingMethodConfig.objects.all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(description__icontains=q)
        )

    current_carrier = request.GET.get("carrier", "").strip()
    if current_carrier:
        qs = qs.filter(carrier=current_carrier)

    current_calc = request.GET.get("calculation_type", "").strip()
    if current_calc:
        qs = qs.filter(calculation_type=current_calc)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "methods": page_obj.object_list,
        "carrier_choices": ShippingMethodConfig.CARRIER_CHOICES,
        "calc_type_choices": ShippingMethodConfig.CALC_TYPE_CHOICES,
        "current_q": q,
        "current_carrier": current_carrier,
        "current_calc": current_calc,
    }
    return render(request, "ecommerce/cartcheckout/shippingmethodconfig/list.html", context)


@login_required
def shippingmethodconfig_detail(request, pk):
    """View details of a shipping method configuration."""
    method = ecommerce_object(request, ShippingMethodConfig, pk)

    context = {
        "method": method,
    }
    return render(request, "ecommerce/cartcheckout/shippingmethodconfig/detail.html", context)


@login_required
def shippingmethodconfig_create(request):
    """Create a new shipping method configuration."""
    if request.method == "POST":
        form = ShippingMethodConfigForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            method = form.save(commit=False)
            method.tenant = request.tenant
            method.save()
            write_audit_log(
                request.user,
                method,
                "create",
                {"name": method.name, "code": method.code},
            )
            messages.success(request, f"Shipping method '{method.name}' created successfully.")
            return redirect("ecommerce:shippingmethodconfig_detail", pk=method.pk)
    else:
        form = ShippingMethodConfigForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/cartcheckout/shippingmethodconfig/form.html", context)


@login_required
def shippingmethodconfig_edit(request, pk):
    """Edit an existing shipping method configuration."""
    method = ecommerce_object(request, ShippingMethodConfig, pk)

    if request.method == "POST":
        form = ShippingMethodConfigForm(request.POST, instance=method, tenant=request.tenant)
        if form.is_valid():
            method = form.save()
            write_audit_log(
                request.user,
                method,
                "update",
                {"name": method.name, "code": method.code},
            )
            messages.success(request, f"Shipping method '{method.name}' updated successfully.")
            return redirect("ecommerce:shippingmethodconfig_detail", pk=method.pk)
    else:
        form = ShippingMethodConfigForm(instance=method, tenant=request.tenant)

    context = {
        "form": form,
        "method": method,
        "is_edit": True,
    }
    return render(request, "ecommerce/cartcheckout/shippingmethodconfig/form.html", context)


@login_required
@require_POST
def shippingmethodconfig_delete(request, pk):
    """Delete a shipping method configuration."""
    method = ecommerce_object(request, ShippingMethodConfig, pk)
    name = method.name
    method.delete()
    write_audit_log(
        request.user,
        method,
        "delete",
        {"name": name},
    )
    messages.success(request, f"Shipping method '{name}' was deleted.")
    return redirect("ecommerce:shippingmethodconfig_list")


@login_required
@require_POST
def shippingmethodconfig_toggle(request, pk):
    """Toggle active state of a shipping method."""
    method = ecommerce_object(request, ShippingMethodConfig, pk)
    method.is_active = not method.is_active
    method.save(update_fields=["is_active", "updated_at"])
    write_audit_log(
        request.user,
        method,
        "toggle",
        {"is_active": method.is_active},
    )
    state_str = "activated" if method.is_active else "deactivated"
    messages.success(request, f"Shipping method '{method.name}' {state_str}.")
    return redirect("ecommerce:shippingmethodconfig_detail", pk=method.pk)
