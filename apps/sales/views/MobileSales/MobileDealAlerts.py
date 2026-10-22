"""Sales 8.16 — MobileDealAlert views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.MobileSales.MobileDealAlerts import (
    MobileDealAlertFilterForm,
    MobileDealAlertForm,
)
from apps.sales.models.MobileSales.MobileDealAlerts import (
    ALERT_TYPE_CHOICES,
    URGENCY_CHOICES,
    MobileDealAlert,
)


@login_required
def mobile_deal_alert_list(request):
    tenant = request.tenant
    qs = (
        MobileDealAlert.objects.filter(tenant=tenant)
        .select_related("recipient", "device", "related_opportunity", "related_quote", "related_route")
        .order_by("-created_at")
    )

    filter_form = MobileDealAlertFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(message__icontains=q) | Q(number__icontains=q))

        alert_type = filter_form.cleaned_data.get("alert_type")
        if alert_type:
            qs = qs.filter(alert_type=alert_type)

        urgency = filter_form.cleaned_data.get("urgency")
        if urgency:
            qs = qs.filter(urgency=urgency)

        is_read = filter_form.cleaned_data.get("is_read")
        if is_read == "0":
            qs = qs.filter(is_read=False)
        elif is_read == "1":
            qs = qs.filter(is_read=True)

        recipient = filter_form.cleaned_data.get("recipient")
        if recipient:
            qs = qs.filter(recipient=recipient)

    all_alerts = MobileDealAlert.objects.filter(tenant=tenant)
    total_alerts_count = all_alerts.count()
    unread_alerts_count = all_alerts.filter(is_read=False).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "alerts": page_obj.object_list,
        "filter_form": filter_form,
        "alert_type_choices": ALERT_TYPE_CHOICES,
        "urgency_choices": URGENCY_CHOICES,
        "total_alerts_count": total_alerts_count,
        "unread_alerts_count": unread_alerts_count,
    }
    return render(request, "sales/mobilesales/mobiledealalert/list.html", context)


@login_required
def mobile_deal_alert_detail(request, pk):
    tenant = request.tenant
    alert = get_object_or_404(
        MobileDealAlert.objects.filter(tenant=tenant).select_related(
            "recipient", "device", "related_opportunity", "related_quote", "related_route"
        ),
        pk=pk,
    )

    # Auto-mark as read if current user is the recipient and it's unread
    if not alert.is_read and alert.recipient == request.user:
        alert.mark_as_read()
        write_audit_log(
            request.user,
            alert,
            "update",
            changes={"action": "auto_mark_read"},
            tenant=tenant,
        )

    context = {
        "alert": alert,
    }
    return render(request, "sales/mobilesales/mobiledealalert/detail.html", context)


@login_required
@transaction.atomic
def mobile_deal_alert_create(request):
    tenant = request.tenant
    initial = {"recipient": request.user}
    device_id = request.GET.get("device")
    if device_id and device_id.isdigit():
        initial["device"] = device_id

    if request.method == "POST":
        form = MobileDealAlertForm(request.POST, tenant=tenant)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.tenant = tenant
            alert.push_status = "sent"
            alert.push_sent_at = timezone.now()
            alert.save()
            write_audit_log(
                request.user,
                alert,
                "create",
                tenant=tenant,
            )
            messages.success(request, f"Mobile Alert '{alert.title}' dispatched successfully.")
            return redirect("sales:mobile_deal_alert_detail", pk=alert.pk)
    else:
        form = MobileDealAlertForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "alert": None,
        "is_edit": False,
    }
    return render(request, "sales/mobilesales/mobiledealalert/form.html", context)


@login_required
@transaction.atomic
def mobile_deal_alert_edit(request, pk):
    tenant = request.tenant
    alert = get_object_or_404(MobileDealAlert.objects.filter(tenant=tenant), pk=pk)

    if request.method == "POST":
        form = MobileDealAlertForm(request.POST, instance=alert, tenant=tenant)
        if form.is_valid():
            alert = form.save()
            write_audit_log(
                request.user,
                alert,
                "update",
                tenant=tenant,
            )
            messages.success(request, f"Mobile Alert '{alert.title}' updated successfully.")
            return redirect("sales:mobile_deal_alert_detail", pk=alert.pk)
    else:
        form = MobileDealAlertForm(instance=alert, tenant=tenant)

    context = {
        "form": form,
        "alert": alert,
        "is_edit": True,
    }
    return render(request, "sales/mobilesales/mobiledealalert/form.html", context)


@login_required
@require_POST
@transaction.atomic
def mobile_deal_alert_delete(request, pk):
    tenant = request.tenant
    alert = get_object_or_404(MobileDealAlert.objects.filter(tenant=tenant), pk=pk)
    is_admin = bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))
    if alert.recipient != request.user and not is_admin:
        messages.error(request, "Only the recipient or a tenant administrator may delete this alert.")
        return redirect("sales:mobile_deal_alert_list")
    title = alert.title
    write_audit_log(
        request.user,
        alert,
        "delete",
        tenant=tenant,
    )
    alert.delete()
    messages.success(request, f"Mobile Alert '{title}' deleted successfully.")
    return redirect("sales:mobile_deal_alert_list")


@login_required
@require_POST
@transaction.atomic
def mobile_deal_alert_mark_read(request, pk):
    tenant = request.tenant
    alert = get_object_or_404(MobileDealAlert.objects.filter(tenant=tenant), pk=pk)
    is_admin = bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))
    if alert.recipient != request.user and not is_admin:
        messages.error(request, "Only the recipient or a tenant administrator may update this alert.")
        return redirect("sales:mobile_deal_alert_detail", pk=alert.pk)
    alert.mark_as_read()
    write_audit_log(
        request.user,
        alert,
        "update",
        changes={"action": "mark_read"},
        tenant=tenant,
    )
    messages.success(request, f"Alert '{alert.title}' marked as read.")
    return redirect("sales:mobile_deal_alert_detail", pk=alert.pk)
