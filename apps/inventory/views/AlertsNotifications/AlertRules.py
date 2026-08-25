"""Inventory 5.16 Alerts & Notifications — AlertRule CRUD views."""
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.AlertsNotifications.AlertRules import AlertRuleForm
from apps.inventory.models.AlertsNotifications.AlertRules import AlertRule
from apps.inventory.views._common import *  # noqa: F401,F403


@login_required
def alertrule_list(request):
    """The watch-rule catalog behind the alert inbox."""
    qs = AlertRule.objects.filter(tenant=request.tenant).select_related("item", "location")

    valid_types = dict(AlertRule.TYPE_CHOICES)
    alert_type = request.GET.get("type", "").strip()
    if alert_type and alert_type not in valid_types:
        alert_type = ""
    if alert_type:
        qs = qs.filter(alert_type=alert_type)

    # BooleanField filter — mapped by hand so ?is_active=False means False, not "every row".
    state = request.GET.get("is_active", "").strip()
    if state == "True":
        qs = qs.filter(is_active=True)
    elif state == "False":
        qs = qs.filter(is_active=False)
        state = "False"
    else:
        state = ""

    return crud_list(
        request,
        qs,
        "inventory/alerts/alertrule/list.html",
        search_fields=["name", "notes", "email_recipients", "item__sku", "location__code"],
        filters=(),
        extra_context={
            "type_choices": AlertRule.TYPE_CHOICES,
            "type": alert_type,
            "state": state,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def alertrule_detail(request, pk):
    """View a rule plus its alert history (latest 50 - SQL-limited, never unbounded)."""
    rule = get_object_or_404(
        AlertRule.objects.filter(tenant=request.tenant).select_related("item", "location"), pk=pk)
    recent_alerts = rule.alerts.all()[:50]
    return render(
        request,
        "inventory/alerts/alertrule/detail.html",
        {
            "obj": rule,
            "recent_alerts": recent_alerts,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def alertrule_create(request):
    """Create a watch rule."""
    return crud_create(
        request,
        form_class=AlertRuleForm,
        template="inventory/alerts/alertrule/form.html",
        success_url="inventory:alertrule_list",
    )


@tenant_admin_required
def alertrule_edit(request, pk):
    """Edit a watch rule."""
    return crud_edit(
        request,
        model=AlertRule,
        pk=pk,
        form_class=AlertRuleForm,
        template="inventory/alerts/alertrule/form.html",
        success_url="inventory:alertrule_list",
    )


@tenant_admin_required
@require_POST
def alertrule_delete(request, pk):
    """Delete a watch rule (raised alerts survive with their snapshot)."""
    return crud_delete(
        request,
        model=AlertRule,
        pk=pk,
        success_url="inventory:alertrule_list",
    )
