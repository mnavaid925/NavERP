from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.AnalyticsBi.AttributionTouchpoints import AttributionTouchpointForm
from apps.ecommerce.models.AnalyticsBi.AttributionTouchpoints import AttributionTouchpoint
from apps.ecommerce.views._common import ecommerce_object


@login_required
def attributiontouchpoint_list(request):
    qs = AttributionTouchpoint.objects.filter(tenant=request.tenant).select_related(
        "order", "cart", "campaign", "affiliate"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(utm_source__icontains=query)
            | Q(utm_campaign__icontains=query)
            | Q(order__number__icontains=query)
        )

    selected_channel = request.GET.get("channel", "").strip()
    if selected_channel:
        qs = qs.filter(channel_type=selected_channel)

    selected_model = request.GET.get("model", "").strip()
    if selected_model:
        qs = qs.filter(attribution_model=selected_model)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/analytics_bi/attribution_touchpoint/list.html",
        {
            "touchpoints": page_obj,
            "channel_choices": AttributionTouchpoint.CHANNEL_CHOICES,
            "attribution_model_choices": AttributionTouchpoint.ATTRIBUTION_MODEL_CHOICES,
            "selected_channel": selected_channel,
            "selected_model": selected_model,
            "query": query,
            "page_obj": page_obj,
            "paginator": paginator,
        },
    )


@login_required
def attributiontouchpoint_detail(request, pk):
    touchpoint = ecommerce_object(
        request,
        AttributionTouchpoint,
        pk,
        select_related=("order", "cart", "campaign", "affiliate"),
    )
    return render(
        request,
        "ecommerce/analytics_bi/attribution_touchpoint/detail.html",
        {"touchpoint": touchpoint},
    )


@login_required
def attributiontouchpoint_create(request):
    if request.method == "POST":
        form = AttributionTouchpointForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            touchpoint = form.save(commit=False)
            touchpoint.tenant = request.tenant
            touchpoint.save()
            write_audit_log(
                request.tenant,
                request.user,
                "CREATE",
                "AttributionTouchpoint",
                touchpoint.pk,
                f"Created attribution touchpoint {touchpoint.number} ({touchpoint.channel_type})",
            )
            messages.success(request, f"Attribution touchpoint {touchpoint.number} created successfully.")
            return redirect("ecommerce:attributiontouchpoint_detail", pk=touchpoint.pk)
    else:
        form = AttributionTouchpointForm(
            tenant=request.tenant,
            initial={"touchpoint_timestamp": timezone.now()},
        )

    return render(
        request,
        "ecommerce/analytics_bi/attribution_touchpoint/form.html",
        {"form": form, "touchpoint": None},
    )


@login_required
def attributiontouchpoint_edit(request, pk):
    touchpoint = ecommerce_object(
        request,
        AttributionTouchpoint,
        pk,
        select_related=("order", "cart", "campaign", "affiliate"),
    )
    if request.method == "POST":
        form = AttributionTouchpointForm(
            request.POST, instance=touchpoint, tenant=request.tenant
        )
        if form.is_valid():
            touchpoint = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "UPDATE",
                "AttributionTouchpoint",
                touchpoint.pk,
                f"Updated attribution touchpoint {touchpoint.number}",
            )
            messages.success(request, f"Attribution touchpoint {touchpoint.number} updated successfully.")
            return redirect("ecommerce:attributiontouchpoint_detail", pk=touchpoint.pk)
    else:
        form = AttributionTouchpointForm(instance=touchpoint, tenant=request.tenant)

    return render(
        request,
        "ecommerce/analytics_bi/attribution_touchpoint/form.html",
        {"form": form, "touchpoint": touchpoint},
    )


@require_POST
@login_required
@tenant_admin_required
def attributiontouchpoint_delete(request, pk):
    touchpoint = ecommerce_object(request, AttributionTouchpoint, pk)
    number = touchpoint.number
    touchpoint.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "DELETE",
        "AttributionTouchpoint",
        pk,
        f"Deleted attribution touchpoint {number}",
    )
    messages.success(request, f"Attribution touchpoint {number} was deleted.")
    return redirect("ecommerce:attributiontouchpoint_list")
