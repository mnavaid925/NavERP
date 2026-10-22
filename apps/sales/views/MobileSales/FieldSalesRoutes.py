"""Sales 8.16 — FieldSalesRoute views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.utils import write_audit_log
from apps.sales.forms.MobileSales.FieldSalesRoutes import (
    FieldSalesRouteFilterForm,
    FieldSalesRouteForm,
)
from apps.sales.models.MobileSales.FieldSalesRoutes import (
    ROUTE_STATUS_CHOICES,
    FieldSalesRoute,
)


@login_required
def field_sales_route_list(request):
    tenant = request.tenant
    qs = FieldSalesRoute.objects.filter(tenant=tenant).select_related("sales_rep")

    filter_form = FieldSalesRouteFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q) | Q(start_location__icontains=q))

        status = filter_form.cleaned_data.get("status")
        if status:
            qs = qs.filter(status=status)

        sales_rep = filter_form.cleaned_data.get("sales_rep")
        if sales_rep:
            qs = qs.filter(sales_rep=sales_rep)

        route_date = filter_form.cleaned_data.get("route_date")
        if route_date:
            qs = qs.filter(route_date=route_date)

    all_routes = FieldSalesRoute.objects.filter(tenant=tenant)
    total_routes_count = all_routes.count()
    active_routes_count = all_routes.filter(status__in=["scheduled", "in_progress"]).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    sales_reps = User.objects.filter(tenant=tenant, is_active=True)

    context = {
        "page_obj": page_obj,
        "routes": page_obj.object_list,
        "filter_form": filter_form,
        "status_choices": ROUTE_STATUS_CHOICES,
        "sales_reps": sales_reps,
        "total_routes_count": total_routes_count,
        "active_routes_count": active_routes_count,
    }
    return render(request, "sales/mobilesales/fieldsalesroute/list.html", context)


@login_required
def field_sales_route_detail(request, pk):
    tenant = request.tenant
    route = get_object_or_404(FieldSalesRoute.objects.filter(tenant=tenant).select_related("sales_rep"), pk=pk)
    stops = route.check_ins.filter(tenant=tenant).select_related("party", "resulting_quote", "contact").order_by("stop_number")

    context = {
        "route": route,
        "stops": stops,
        "completion_rate": route.completion_rate_pct,
    }
    return render(request, "sales/mobilesales/fieldsalesroute/detail.html", context)


@login_required
@transaction.atomic
def field_sales_route_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = FieldSalesRouteForm(request.POST, tenant=tenant)
        if form.is_valid():
            route = form.save(commit=False)
            route.tenant = tenant
            route.save()
            write_audit_log(
                request.user,
                route,
                "create",
                tenant=tenant,
            )
            messages.success(request, f"Sales Route '{route.name}' created successfully.")
            return redirect("sales:field_sales_route_detail", pk=route.pk)
    else:
        form = FieldSalesRouteForm(tenant=tenant, initial={"sales_rep": request.user})

    context = {
        "form": form,
        "route": None,
        "is_edit": False,
    }
    return render(request, "sales/mobilesales/fieldsalesroute/form.html", context)


@login_required
@transaction.atomic
def field_sales_route_edit(request, pk):
    tenant = request.tenant
    route = get_object_or_404(FieldSalesRoute.objects.filter(tenant=tenant), pk=pk)

    if request.method == "POST":
        form = FieldSalesRouteForm(request.POST, instance=route, tenant=tenant)
        if form.is_valid():
            route = form.save()
            write_audit_log(
                request.user,
                route,
                "update",
                tenant=tenant,
            )
            messages.success(request, f"Sales Route '{route.name}' updated successfully.")
            return redirect("sales:field_sales_route_detail", pk=route.pk)
    else:
        form = FieldSalesRouteForm(instance=route, tenant=tenant)

    context = {
        "form": form,
        "route": route,
        "is_edit": True,
    }
    return render(request, "sales/mobilesales/fieldsalesroute/form.html", context)


@login_required
@require_POST
@transaction.atomic
def field_sales_route_delete(request, pk):
    tenant = request.tenant
    route = get_object_or_404(FieldSalesRoute.objects.filter(tenant=tenant), pk=pk)
    name = route.name
    write_audit_log(
        request.user,
        route,
        "delete",
        tenant=tenant,
    )
    route.delete()
    messages.success(request, f"Sales Route '{name}' deleted successfully.")
    return redirect("sales:field_sales_route_list")


@login_required
@require_POST
@transaction.atomic
def field_sales_route_optimize(request, pk):
    tenant = request.tenant
    route = get_object_or_404(FieldSalesRoute.objects.filter(tenant=tenant), pk=pk)
    if route.status in ["completed", "cancelled"]:
        messages.error(request, f"Cannot optimize route '{route.name}' because it is {route.get_status_display().lower()}.")
        return redirect("sales:field_sales_route_detail", pk=route.pk)
    route.optimization_status = "optimized"
    route.save(update_fields=["optimization_status"])
    write_audit_log(
        request.user,
        route,
        "update",
        changes={"action": "optimize"},
        tenant=tenant,
    )
    messages.success(request, f"Route '{route.name}' sequence optimized successfully.")
    return redirect("sales:field_sales_route_detail", pk=route.pk)
