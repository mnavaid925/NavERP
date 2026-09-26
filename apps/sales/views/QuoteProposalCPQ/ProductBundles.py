"""Views for ProductBundleOption management."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Product
from apps.sales.forms.QuoteProposalCPQ.ProductBundles import ProductBundleOptionForm
from apps.sales.models.QuoteProposalCPQ.ProductBundles import ProductBundleOption


@login_required
def product_bundle_list(request):
    """List and filter CPQ product bundle options."""
    tenant = request.tenant
    qs = ProductBundleOption.objects.filter(tenant=tenant).select_related(
        "bundle_product", "component_product", "component_item", "depends_on_product"
    )

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(number__icontains=q) |
            Q(bundle_product__name__icontains=q) |
            Q(component_product__name__icontains=q) |
            Q(option_group__icontains=q)
        )

    # Filters
    bundle_id = request.GET.get("bundle", "").strip()
    if bundle_id:
        qs = qs.filter(bundle_product_id=bundle_id)

    option_group = request.GET.get("option_group", "").strip()
    if option_group:
        qs = qs.filter(option_group=option_group)

    compatibility_rule = request.GET.get("compatibility_rule", "").strip()
    if compatibility_rule:
        qs = qs.filter(compatibility_rule=compatibility_rule)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ["true", "1"]:
        qs = qs.filter(is_active=True)
    elif is_active in ["false", "0"]:
        qs = qs.filter(is_active=False)

    stats = {
        "total": ProductBundleOption.objects.filter(tenant=tenant).count(),
        "active": ProductBundleOption.objects.filter(tenant=tenant, is_active=True).count(),
        "required": ProductBundleOption.objects.filter(tenant=tenant, is_required=True).count(),
        "with_rules": ProductBundleOption.objects.filter(tenant=tenant).exclude(compatibility_rule="none").count(),
    }

    # Groups & bundle products for filters
    bundle_products = Product.objects.filter(
        tenant=tenant,
        bundle_options__isnull=False
    ).distinct().order_by("name")

    option_groups = ProductBundleOption.objects.filter(
        tenant=tenant
    ).values_list("option_group", flat=True).distinct().order_by("option_group")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "bundles": page_obj,
        "bundle_products": bundle_products,
        "option_groups": option_groups,
        "compatibility_choices": ProductBundleOption.COMPATIBILITY_CHOICES,
        "stats": stats,
    }
    return render(request, "sales/quote_proposal_cpq/productbundleoption/list.html", context)


@login_required
@tenant_admin_required
def product_bundle_create(request):
    """Create a new ProductBundleOption."""
    if request.method == "POST":
        form = ProductBundleOptionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            bundle_opt = form.save(commit=False)
            bundle_opt.tenant = request.tenant
            bundle_opt.save()
            write_audit_log(request.user, "create", "ProductBundleOption", bundle_opt.id, f"Created bundle option {bundle_opt.number}")
            messages.success(request, f"Bundle option {bundle_opt.name} created successfully.")
            return redirect("sales:product_bundle_detail", pk=bundle_opt.pk)
    else:
        initial = {}
        if request.GET.get("bundle"):
            initial["bundle_product"] = request.GET.get("bundle")
        form = ProductBundleOptionForm(tenant=request.tenant, initial=initial)

    return render(request, "sales/quote_proposal_cpq/productbundleoption/form.html", {
        "form": form,
        "is_create": True,
    })


@login_required
def product_bundle_detail(request, pk):
    """View details of a ProductBundleOption."""
    bundle_opt = get_object_or_404(
        ProductBundleOption.objects.select_related(
            "bundle_product", "component_product", "component_item", "depends_on_product"
        ),
        pk=pk,
        tenant=request.tenant
    )
    sibling_options = ProductBundleOption.objects.filter(
        tenant=request.tenant,
        bundle_product=bundle_opt.bundle_product
    ).exclude(pk=bundle_opt.pk).select_related("component_product")

    return render(request, "sales/quote_proposal_cpq/productbundleoption/detail.html", {
        "bundle": bundle_opt,
        "sibling_options": sibling_options,
    })


@login_required
@tenant_admin_required
def product_bundle_edit(request, pk):
    """Edit a ProductBundleOption."""
    bundle_opt = get_object_or_404(ProductBundleOption, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = ProductBundleOptionForm(request.POST, instance=bundle_opt, tenant=request.tenant)
        if form.is_valid():
            bundle_opt = form.save()
            write_audit_log(request.user, "update", "ProductBundleOption", bundle_opt.id, f"Updated bundle option {bundle_opt.number}")
            messages.success(request, f"Bundle option {bundle_opt.name} updated successfully.")
            return redirect("sales:product_bundle_detail", pk=bundle_opt.pk)
    else:
        form = ProductBundleOptionForm(instance=bundle_opt, tenant=request.tenant)

    return render(request, "sales/quote_proposal_cpq/productbundleoption/form.html", {
        "form": form,
        "bundle": bundle_opt,
        "is_create": False,
    })


@require_POST
@login_required
@tenant_admin_required
def product_bundle_delete(request, pk):
    """Delete a ProductBundleOption."""
    bundle_opt = get_object_or_404(ProductBundleOption, pk=pk, tenant=request.tenant)
    name = bundle_opt.name
    opt_id = bundle_opt.id
    bundle_opt.delete()
    write_audit_log(request.user, "delete", "ProductBundleOption", opt_id, f"Deleted bundle option {name}")
    messages.success(request, f"Bundle option {name} deleted successfully.")
    return redirect("sales:product_bundle_list")
