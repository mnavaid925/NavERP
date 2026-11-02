from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.FraudRisk.AccountSecurityAlerts import AccountSecurityAlertForm
from apps.ecommerce.models.FraudRisk.AccountSecurityAlerts import AccountSecurityAlert
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def account_security_alert_list(request):
    qs = ecommerce_scope(
        AccountSecurityAlert.objects.select_related("user", "party", "assigned_investigator", "resolved_by"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(party__name__icontains=search_query)
            | Q(ip_address__icontains=search_query)
            | Q(location_info__icontains=search_query)
            | Q(incident_details__icontains=search_query)
        )

    type_filter = request.GET.get("type", "").strip()
    if type_filter:
        qs = qs.filter(alert_type=type_filter)

    severity_filter = request.GET.get("severity", "").strip()
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    total_count = qs.count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "alerts": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "search_query": search_query,
        "type_filter": type_filter,
        "severity_filter": severity_filter,
        "status_filter": status_filter,
        "type_choices": AccountSecurityAlert.ALERT_TYPE_CHOICES,
        "severity_choices": AccountSecurityAlert.SEVERITY_CHOICES,
        "status_choices": AccountSecurityAlert.STATUS_CHOICES,
    }
    return render(request, "ecommerce/fraud_risk/account_security_alert/list.html", context)


@login_required
def account_security_alert_create(request):
    if request.method == "POST":
        form = AccountSecurityAlertForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.tenant = request.tenant
            if alert.status in ["resolved_legitimate", "confirmed_threat", "dismissed"] and not alert.resolved_at:
                alert.resolved_at = timezone.now()
                if not alert.resolved_by:
                    alert.resolved_by = request.user
            alert.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="AccountSecurityAlert",
                object_id=alert.pk,
                changes={"alert_type": alert.alert_type, "severity": alert.severity, "status": alert.status},
            )
            messages.success(request, f"Security alert {alert.number} created.")
            return redirect("ecommerce:account_security_alert_detail", pk=alert.pk)
    else:
        form = AccountSecurityAlertForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/fraud_risk/account_security_alert/form.html", context)


@login_required
def account_security_alert_detail(request, pk):
    alert = ecommerce_object(
        request,
        AccountSecurityAlert,
        pk,
        select_related=("user", "party", "assigned_investigator", "resolved_by"),
    )
    context = {
        "alert": alert,
    }
    return render(request, "ecommerce/fraud_risk/account_security_alert/detail.html", context)


@login_required
def account_security_alert_edit(request, pk):
    alert = ecommerce_object(request, AccountSecurityAlert, pk)
    if request.method == "POST":
        form = AccountSecurityAlertForm(request.POST, instance=alert, tenant=request.tenant)
        if form.is_valid():
            alert = form.save(commit=False)
            if alert.status in ["resolved_legitimate", "confirmed_threat", "dismissed"] and not alert.resolved_at:
                alert.resolved_at = timezone.now()
                if not alert.resolved_by:
                    alert.resolved_by = request.user
            alert.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="AccountSecurityAlert",
                object_id=alert.pk,
                changes={"status": alert.status, "severity": alert.severity},
            )
            messages.success(request, f"Security alert {alert.number} updated.")
            return redirect("ecommerce:account_security_alert_detail", pk=alert.pk)
    else:
        form = AccountSecurityAlertForm(instance=alert, tenant=request.tenant)

    context = {
        "form": form,
        "alert": alert,
        "is_edit": True,
    }
    return render(request, "ecommerce/fraud_risk/account_security_alert/form.html", context)


@login_required
@require_POST
def account_security_alert_delete(request, pk):
    alert = ecommerce_object(request, AccountSecurityAlert, pk)
    number = alert.number
    alert.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="AccountSecurityAlert",
        object_id=pk,
        changes={"number": number},
    )
    messages.success(request, f"Security alert {number} deleted.")
    return redirect("ecommerce:account_security_alert_list")
