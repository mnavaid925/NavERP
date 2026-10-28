"""Views for SalesPriceBookEntry model."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import PriceBook
from apps.sales.forms.MasterDataConfiguration.SalesPriceBookEntries import SalesPriceBookEntryForm
from apps.sales.models.MasterDataConfiguration.SalesPriceBookEntries import SalesPriceBookEntry


@login_required
def pbe_list(request):
    """List and filter sales price book entries."""
    tenant = request.tenant
    qs = SalesPriceBookEntry.objects.filter(tenant=tenant).select_related(
        "price_book", "product", "item"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(sku_code__icontains=q)
            | Q(product__name__icontains=q)
            | Q(price_book__name__icontains=q)
            | Q(notes__icontains=q)
        )

    selected_price_book = request.GET.get("price_book", "").strip()
    if selected_price_book and selected_price_book.isdigit():
        qs = qs.filter(price_book_id=int(selected_price_book))

    selected_pricing_model = request.GET.get("pricing_model", "").strip()
    if selected_pricing_model:
        qs = qs.filter(pricing_model=selected_pricing_model)

    selected_active = request.GET.get("is_active", "").strip()
    if selected_active in ["true", "1"]:
        qs = qs.filter(is_active=True)
    elif selected_active in ["false", "0"]:
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    price_books = PriceBook.objects.filter(tenant=tenant)

    context = {
        "page_obj": page_obj,
        "entries": page_obj.object_list,
        "price_book_entries": page_obj.object_list,
        "price_books": price_books,
        "pricing_models": SalesPriceBookEntry.PRICING_MODEL_CHOICES,
        "q": q,
        "selected_price_book": selected_price_book,
        "selected_pricing_model": selected_pricing_model,
        "selected_active": selected_active,
    }
    return render(request, "sales/masterdataconfiguration/pricebookentry/list.html", context)


@login_required
def pbe_detail(request, pk):
    """Detail view for a specific price book entry."""
    entry = get_object_or_404(
        SalesPriceBookEntry.objects.filter(tenant=request.tenant).select_related(
            "price_book", "product", "item"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/masterdataconfiguration/pricebookentry/detail.html",
        {"entry": entry, "price_book_entry": entry},
    )


@login_required
@tenant_admin_required
def pbe_create(request):
    """Create a new price book entry."""
    if request.method == "POST":
        form = SalesPriceBookEntryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.tenant = request.tenant
            entry.save()
            write_audit_log(
                request.user,
                entry,
                "create",
                {"detail": f"Created price book entry {entry.number} for {entry.product.name}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Price book entry {entry.number} created successfully.")
            return redirect("sales:pbe_detail", pk=entry.pk)
    else:
        form = SalesPriceBookEntryForm(tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/pricebookentry/form.html",
        {"form": form, "entry": None, "price_book_entry": None, "is_edit": False},
    )


@login_required
@tenant_admin_required
def pbe_edit(request, pk):
    """Edit an existing price book entry."""
    entry = get_object_or_404(
        SalesPriceBookEntry.objects.filter(tenant=request.tenant).select_related("price_book", "product"),
        pk=pk,
    )
    if request.method == "POST":
        form = SalesPriceBookEntryForm(request.POST, instance=entry, tenant=request.tenant)
        if form.is_valid():
            entry = form.save()
            write_audit_log(
                request.user,
                entry,
                "update",
                {"detail": f"Updated price book entry {entry.number}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Price book entry {entry.number} updated successfully.")
            return redirect("sales:pbe_detail", pk=entry.pk)
    else:
        form = SalesPriceBookEntryForm(instance=entry, tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/pricebookentry/form.html",
        {"form": form, "entry": entry, "price_book_entry": entry, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def pbe_delete(request, pk):
    """Delete a price book entry."""
    entry = get_object_or_404(
        SalesPriceBookEntry.objects.filter(tenant=request.tenant).select_related("price_book", "product"),
        pk=pk,
    )
    num = entry.number
    write_audit_log(
        request.user,
        entry,
        "delete",
        {"detail": f"Deleted price book entry {num}"},
        tenant=request.tenant,
    )
    entry.delete()
    messages.success(request, f"Price book entry {num} deleted.")
    return redirect("sales:pbe_list")
