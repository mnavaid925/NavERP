"""Sales 8.17 — SalesAlertTrigger views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.crud import paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.forms.WorkflowProcessAutomation.SalesAlertTriggers import (
    SalesAlertTriggerForm,
)
from apps.sales.models.MobileSales.MobileDealAlerts import MobileDealAlert
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.WorkflowProcessAutomation.SalesAlertTriggers import (
    SAT_TO_MDA_ALERT_TYPE,
    SalesAlertTrigger,
)

# Delivery this pass = RECORD ROWS ONLY (contract §3.4): firing writes sales.MobileDealAlert
# rows; email/SMS/push transport is deferred to 8.18 (GAP-sales-8.17-05). "all" broadcast
# creates no rows because it needs a transport.
MAX_ALERT_RECIPIENTS = 50


def fire_alert_trigger(trigger, *, user=None, record=None, now=None):
    """Write MobileDealAlert rows for the trigger's audience. Returns the created alerts."""
    now = now or timezone.now()
    trigger.mark_evaluated(now=now)
    if not trigger.is_active or trigger.is_on_cooldown(now=now):
        return []
    if trigger.audience_kind == "role" and trigger.audience_role_id:
        recipients = list(User.objects.filter(
            tenant=trigger.tenant, role=trigger.audience_role, is_active=True
        ).order_by("pk")[:MAX_ALERT_RECIPIENTS])           # User.role is a FK (accounts/models.py:69)
    elif trigger.audience_kind == "user":
        recipients = list(trigger.audience_users.filter(is_active=True).order_by("pk")[:MAX_ALERT_RECIPIENTS])
    elif trigger.audience_kind == "owner" and record is not None:
        owner = getattr(record, "owner", None)
        recipients = [owner] if owner is not None and owner.is_active else []
    else:
        recipients = []   # "all" broadcast needs a transport — GAP-sales-8.17-05
    alerts = []
    for recipient in recipients:
        alerts.append(MobileDealAlert.objects.create(
            tenant=trigger.tenant,
            recipient=recipient,
            alert_type=SAT_TO_MDA_ALERT_TYPE.get(trigger.alert_type, "checkin_reminder"),
            title=trigger.name[:200],
            message=f"Alert trigger '{trigger.name}' fired for {trigger.get_target_entity_display()} records.",
            urgency=trigger.severity,
            related_opportunity=record if isinstance(record, Opportunity) else None,
            related_quote=record if isinstance(record, CPQQuote) else None,
        ))
    if alerts:
        trigger.mark_fired(now=now)
    if user is not None:
        write_audit_log(user, trigger, "update",
                        changes={"action": "alert_fired", "recipients": str(len(alerts))},
                        tenant=trigger.tenant)
    return alerts


@login_required
def sales_alert_trigger_list(request):
    tenant = request.tenant
    qs = SalesAlertTrigger.objects.filter(tenant=tenant).select_related(
        "audience_role", "notification_rule"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q))

    alert_type = request.GET.get("alert_type", "").strip()
    if alert_type in {value for value, _ in SalesAlertTrigger.ALERT_TYPE_CHOICES}:
        qs = qs.filter(alert_type=alert_type)

    severity = request.GET.get("severity", "").strip()
    if severity in {value for value, _ in SalesAlertTrigger.SEVERITY_CHOICES}:
        qs = qs.filter(severity=severity)

    audience_kind = request.GET.get("audience_kind", "").strip()
    if audience_kind in {value for value, _ in SalesAlertTrigger.AUDIENCE_KIND_CHOICES}:
        qs = qs.filter(audience_kind=audience_kind)

    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)

    page_obj = paginate(request, qs, 15)
    context = {
        "alert_triggers": page_obj.object_list,
        "page_obj": page_obj,
        "alert_type_choices": SalesAlertTrigger.ALERT_TYPE_CHOICES,
        "severity_choices": SalesAlertTrigger.SEVERITY_CHOICES,
        "audience_kind_choices": SalesAlertTrigger.AUDIENCE_KIND_CHOICES,
    }
    return render(request, "sales/workflowprocessautomation/salesalerttrigger/list.html", context)


@login_required
def sales_alert_trigger_detail(request, pk):
    alert_trigger = get_object_or_404(
        SalesAlertTrigger.objects.filter(tenant=request.tenant).select_related(
            "audience_role", "notification_rule"
        ),
        pk=pk,
    )
    context = {
        "alert_trigger": alert_trigger,
        "audience_users": list(alert_trigger.audience_users.all().order_by("pk")),
    }
    return render(request, "sales/workflowprocessautomation/salesalerttrigger/detail.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_alert_trigger_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = SalesAlertTriggerForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=tenant)
            messages.success(request, f"Alert trigger '{obj.name}' created.")
            return redirect("sales:sales_alert_trigger_detail", pk=obj.pk)
    else:
        form = SalesAlertTriggerForm(tenant=tenant)

    context = {
        "form": form,
        "alert_trigger": None,
        "is_edit": False,
    }
    return render(request, "sales/workflowprocessautomation/salesalerttrigger/form.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_alert_trigger_edit(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesAlertTrigger.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = SalesAlertTriggerForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "update", tenant=tenant)
            messages.success(request, f"Alert trigger '{obj.name}' updated.")
            return redirect("sales:sales_alert_trigger_detail", pk=obj.pk)
    else:
        form = SalesAlertTriggerForm(instance=obj, tenant=tenant)

    context = {
        "form": form,
        "alert_trigger": obj,
        "is_edit": True,
    }
    return render(request, "sales/workflowprocessautomation/salesalerttrigger/form.html", context)


@login_required
@require_POST
@tenant_admin_required
@transaction.atomic
def sales_alert_trigger_delete(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesAlertTrigger.objects.filter(tenant=tenant), pk=pk)
    name = obj.name
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Alert trigger '{name}' deleted.")
    return redirect("sales:sales_alert_trigger_list")
