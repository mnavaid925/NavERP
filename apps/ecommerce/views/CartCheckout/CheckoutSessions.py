from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounting.models import TaxCode
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CartCheckout.CheckoutSessions import CheckoutSessionForm
from apps.ecommerce.models.CartCheckout.CheckoutSessions import CheckoutSession
from apps.ecommerce.models.CartCheckout.PaymentMethods import PaymentMethodConfig
from apps.ecommerce.models.CartCheckout.ShippingMethods import ShippingMethodConfig
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def checkoutsession_list(request):
    """List checkout sessions with status and checkout flow filtering."""
    qs = ecommerce_scope(CheckoutSession.objects.all(), request).select_related("customer", "cart")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(email__icontains=q)
            | Q(shipping_name__icontains=q)
            | Q(cart__number__icontains=q)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_flow = request.GET.get("flow_type", "").strip()
    if current_flow:
        qs = qs.filter(flow_type=current_flow)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "sessions": page_obj.object_list,
        "status_choices": CheckoutSession.STATUS_CHOICES,
        "flow_choices": CheckoutSession.FLOW_TYPE_CHOICES,
        "current_q": q,
        "current_status": current_status,
        "current_flow": current_flow,
    }
    return render(request, "ecommerce/cartcheckout/checkoutsession/list.html", context)


@login_required
def checkoutsession_detail(request, pk):
    """View details of a checkout session, including shipping, billing, and tax breakdown."""
    session = ecommerce_object(
        request,
        CheckoutSession,
        pk,
        select_related=("cart", "customer", "shipping_method", "payment_method", "tax_code"),
        prefetch_related=("cart__items__product", "cart__items__variant"),
    )
    tax_codes = TaxCode.objects.filter(tenant=request.tenant).order_by("name")
    shipping_methods = ShippingMethodConfig.objects.filter(tenant=request.tenant, is_active=True).order_by("sort_order", "name")
    payment_methods = PaymentMethodConfig.objects.filter(tenant=request.tenant, is_active=True).order_by("display_order", "name")

    context = {
        "session": session,
        "cart": session.cart,
        "tax_codes": tax_codes,
        "shipping_methods": shipping_methods,
        "payment_methods": payment_methods,
    }
    return render(request, "ecommerce/cartcheckout/checkoutsession/detail.html", context)


@login_required
def checkoutsession_create(request):
    """Create a new checkout session."""
    if request.method == "POST":
        form = CheckoutSessionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            session = form.save(commit=False)
            session.tenant = request.tenant
            session.save()
            write_audit_log(
                request.user,
                session,
                "create",
                {"number": session.number, "status": session.status},
            )
            messages.success(request, f"Checkout session {session.number} created successfully.")
            return redirect("ecommerce:checkoutsession_detail", pk=session.pk)
    else:
        form = CheckoutSessionForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/cartcheckout/checkoutsession/form.html", context)


@login_required
def checkoutsession_edit(request, pk):
    """Edit an existing checkout session."""
    session = ecommerce_object(request, CheckoutSession, pk)

    if request.method == "POST":
        form = CheckoutSessionForm(request.POST, instance=session, tenant=request.tenant)
        if form.is_valid():
            session = form.save()
            write_audit_log(
                request.user,
                session,
                "update",
                {"number": session.number, "status": session.status},
            )
            messages.success(request, f"Checkout session {session.number} updated successfully.")
            return redirect("ecommerce:checkoutsession_detail", pk=session.pk)
    else:
        form = CheckoutSessionForm(instance=session, tenant=request.tenant)

    context = {
        "form": form,
        "session": session,
        "is_edit": True,
    }
    return render(request, "ecommerce/cartcheckout/checkoutsession/form.html", context)


@login_required
@require_POST
def checkoutsession_delete(request, pk):
    """Delete a checkout session."""
    session = ecommerce_object(request, CheckoutSession, pk)
    number = session.number
    session.delete()
    write_audit_log(
        request.user,
        session,
        "delete",
        {"number": number},
    )
    messages.success(request, f"Checkout session {number} was deleted.")
    return redirect("ecommerce:checkoutsession_list")


@login_required
@require_POST
def checkoutsession_advance(request, pk):
    """Advance checkout session to its next step in the conversion funnel."""
    session = ecommerce_object(request, CheckoutSession, pk)
    old_step = session.current_step
    session.advance_step()
    write_audit_log(
        request.user,
        session,
        "advance",
        {"from_step": old_step, "to_step": session.current_step},
    )
    messages.success(
        request,
        f"Checkout session {session.number} advanced to step '{session.get_current_step_display()}'.",
    )
    return redirect("ecommerce:checkoutsession_detail", pk=session.pk)
