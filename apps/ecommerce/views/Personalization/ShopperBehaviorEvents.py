from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.models.Personalization.ShopperBehaviorEvents import ShopperBehaviorEvent
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def shopperbehaviorevent_list(request):
    qs = ecommerce_scope(ShopperBehaviorEvent.objects.all(), request).select_related(
        "product", "category", "customer_profile", "user"
    )

    search_query = request.GET.get("q", "").strip()
    event_type = request.GET.get("event_type", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(session_key__icontains=search_query)
            | Q(referrer_url__icontains=search_query)
            | Q(product__name__icontains=search_query)
        )

    if event_type:
        qs = qs.filter(event_type=event_type)

    paginator = Paginator(qs, 30)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "events": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "selected_type": event_type,
        "event_type_choices": ShopperBehaviorEvent.EVENT_TYPE_CHOICES,
    }
    return render(request, "ecommerce/personalization/shopperbehaviorevent/list.html", context)


@login_required
def shopperbehaviorevent_detail(request, pk):
    event = ecommerce_object(request, ShopperBehaviorEvent, pk)
    context = {
        "event": event,
    }
    return render(request, "ecommerce/personalization/shopperbehaviorevent/detail.html", context)


@login_required
@tenant_admin_required
@require_POST
def shopperbehaviorevent_delete(request, pk):
    event = ecommerce_object(request, ShopperBehaviorEvent, pk)
    number = event.number
    event.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "delete",
        "ShopperBehaviorEvent",
        pk,
        f"Deleted shopper behavior event ({number})",
    )
    messages.success(request, f"Behavior event '{number}' deleted.")
    return redirect("ecommerce:shopperbehaviorevent_list")
