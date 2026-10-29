from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CartCheckout.Carts import CartForm
from apps.ecommerce.models.CartCheckout.Carts import Cart
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def cart_list(request):
    """List shopping carts with search and status filtering."""
    qs = ecommerce_scope(Cart.objects.all(), request).select_related("customer")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(email__icontains=q)
            | Q(session_key__icontains=q)
            | Q(coupon_code__icontains=q)
            | Q(customer__name__icontains=q)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "carts": page_obj.object_list,
        "status_choices": Cart.STATUS_CHOICES,
        "current_q": q,
        "current_status": current_status,
    }
    return render(request, "ecommerce/cartcheckout/cart/list.html", context)


@login_required
def cart_detail(request, pk):
    """Display cart contents, line items, and totals."""
    cart = ecommerce_object(
        request,
        Cart,
        pk,
        select_related=("customer",),
        prefetch_related=("items__product", "items__variant"),
    )
    items = cart.items.select_related("product", "variant").all()

    context = {
        "cart": cart,
        "items": items,
    }
    return render(request, "ecommerce/cartcheckout/cart/detail.html", context)


@login_required
def cart_create(request):
    """Create a new cart."""
    if request.method == "POST":
        form = CartForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cart = form.save(commit=False)
            cart.tenant = request.tenant
            cart.save()
            cart.recalculate_totals()
            write_audit_log(
                request.user,
                cart,
                "create",
                {"number": cart.number, "status": cart.status},
            )
            messages.success(request, f"Cart {cart.number} created successfully.")
            return redirect("ecommerce:cart_detail", pk=cart.pk)
    else:
        form = CartForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/cartcheckout/cart/form.html", context)


@login_required
def cart_edit(request, pk):
    """Edit cart parameters."""
    cart = ecommerce_object(request, Cart, pk)

    if request.method == "POST":
        form = CartForm(request.POST, instance=cart, tenant=request.tenant)
        if form.is_valid():
            cart = form.save()
            cart.recalculate_totals()
            write_audit_log(
                request.user,
                cart,
                "update",
                {"number": cart.number, "status": cart.status},
            )
            messages.success(request, f"Cart {cart.number} updated successfully.")
            return redirect("ecommerce:cart_detail", pk=cart.pk)
    else:
        form = CartForm(instance=cart, tenant=request.tenant)

    context = {
        "form": form,
        "cart": cart,
        "is_edit": True,
    }
    return render(request, "ecommerce/cartcheckout/cart/form.html", context)


@login_required
@require_POST
def cart_delete(request, pk):
    """Delete a cart."""
    cart = ecommerce_object(request, Cart, pk)
    number = cart.number
    cart.delete()
    write_audit_log(
        request.user,
        cart,
        "delete",
        {"number": number},
    )
    messages.success(request, f"Cart {number} was deleted.")
    return redirect("ecommerce:cart_list")


@login_required
@require_POST
def cart_recover(request, pk):
    """Generate recovery token and mark recovery notification timestamp."""
    cart = ecommerce_object(request, Cart, pk)
    token = cart.generate_recovery_token()
    cart.recovery_sent_at = timezone.now()
    if cart.status == Cart.STATUS_ACTIVE:
        cart.status = Cart.STATUS_ABANDONED
        cart.abandoned_at = timezone.now()
    cart.save(update_fields=["recovery_token", "recovery_sent_at", "status", "abandoned_at", "updated_at"])

    write_audit_log(
        request.user,
        cart,
        "recover",
        {"token": token, "sent_at": str(cart.recovery_sent_at)},
    )
    messages.success(
        request,
        f"Abandonment recovery token generated for Cart {cart.number}. Recovery link dispatched.",
    )
    return redirect("ecommerce:cart_detail", pk=cart.pk)
