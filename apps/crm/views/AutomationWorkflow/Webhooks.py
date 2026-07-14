"""CRM 1.10 Automation & Workflow Engine — Webhooks views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Webhook,
    WebhookDelivery,
    WorkflowRule,
)
from apps.crm.forms import (
    WebhookForm,
)
from ._engine import _deliver_webhook


@login_required
def webhook_list(request):
    return crud_list(
        request,
        (Webhook.objects.filter(tenant=request.tenant).annotate(delivery_count=Count("deliveries"))
         .order_by("-created_at")),  # annotate()+GROUP BY drops the Meta default ordering
        "crm/workflow/webhook/list.html",
        search_fields=["number", "name", "target_url"],
        filters=[("is_active", "is_active", False), ("trigger_entity", "trigger_entity", False),
                 ("trigger_event", "trigger_event", False)],
        extra_context={"entity_choices": WorkflowRule.ENTITY_CHOICES,
                       "event_choices": WorkflowRule.EVENT_CHOICES},
    )


@tenant_admin_required  # webhook config (target URL = future SSRF surface + signing secret) is admin-level (code-review)
def webhook_create(request):
    return crud_create(request, form_class=WebhookForm, template="crm/workflow/webhook/form.html",
                       success_url="crm:webhook_list")


@login_required
def webhook_detail(request, pk):
    obj = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/webhook/detail.html",
                  {"obj": obj, "deliveries": obj.deliveries.order_by("-created_at")[:10]})


@tenant_admin_required  # admin-level (code-review)
def webhook_edit(request, pk):
    return crud_edit(request, model=Webhook, pk=pk, form_class=WebhookForm,
                     template="crm/workflow/webhook/form.html", success_url="crm:webhook_list")


@tenant_admin_required  # admin-level (code-review)
@require_POST
def webhook_delete(request, pk):
    return crud_delete(request, model=Webhook, pk=pk, success_url="crm:webhook_list")


@tenant_admin_required
@require_POST
def webhook_test(request, pk):
    """1.10 — fire a signed test delivery for a webhook (records a WebhookDelivery; HTTP deferred)."""
    webhook = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)
    payload = json.dumps({"event": "manual.test", "webhook": webhook.number,
                          "at": timezone.now().isoformat()})
    _deliver_webhook(webhook, "manual.test", payload)
    write_audit_log(request.user, webhook, "update", {"action": "test"})
    messages.success(request, f"Test delivery recorded for {webhook.number} (real HTTP delivery is deferred).")
    return redirect("crm:webhook_detail", pk=pk)


@login_required
def webhookdelivery_list(request):
    return crud_list(
        request,
        WebhookDelivery.objects.filter(tenant=request.tenant).select_related("webhook").defer("payload"),
        "crm/workflow/webhookdelivery/list.html",
        search_fields=["event", "webhook__name"],
        filters=[("status", "status", False), ("webhook", "webhook_id", True)],
        extra_context={"status_choices": WebhookDelivery.STATUS_CHOICES,
                       "webhooks": Webhook.objects.filter(tenant=request.tenant).only("id", "number", "name").order_by("name")},
    )


@login_required
def webhookdelivery_detail(request, pk):
    obj = get_object_or_404(WebhookDelivery.objects.select_related("webhook"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/webhookdelivery/detail.html", {"obj": obj})
