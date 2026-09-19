"""Projects 7.17 — ProjectWebhookEndpoint and Delivery views."""
import json
import time
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST

from apps.projects.forms.WorkflowAutomation.Webhooks import (
    ProjectWebhookEndpointForm,
    WebhookTestPingForm,
)
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.WorkflowAutomation.Webhooks import (
    ProjectWebhookDelivery,
    ProjectWebhookEndpoint,
)
from apps.projects.views._common import *


@login_required
def pwh_list(request):
    """List webhook endpoints with search and filters."""
    qs = ProjectWebhookEndpoint.objects.filter(tenant=request.tenant).select_related("project")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q) | Q(target_url__icontains=q))

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("true", "1", "active"):
        qs = qs.filter(is_active=True)
    elif is_active in ("false", "0", "inactive"):
        qs = qs.filter(is_active=False)

    project_id = request.GET.get("project", "").strip()
    if project_id:
        qs = qs.filter(project_id=project_id)

    total_count = ProjectWebhookEndpoint.objects.filter(tenant=request.tenant).count()
    active_count = ProjectWebhookEndpoint.objects.filter(tenant=request.tenant, is_active=True).count()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deliveries_today = ProjectWebhookDelivery.objects.filter(tenant=request.tenant, attempted_at__gte=today_start).count()
    failed_today = ProjectWebhookDelivery.objects.filter(
        tenant=request.tenant, attempted_at__gte=today_start, status="failed"
    ).count()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/workflowautomation/webhook/list.html",
        {
            "webhooks": page_obj.object_list,
            "page_obj": page_obj,
            "projects": Project.objects.filter(tenant=request.tenant),
            "stats": {
                "total": total_count,
                "active": active_count,
                "deliveries_today": deliveries_today,
                "failed_today": failed_today,
            },
            "q": q,
            "is_active": is_active,
            "project_id": project_id,
        },
    )


@login_required
def pwh_detail(request, pk):
    """Detail view for a ProjectWebhookEndpoint with delivery log and ping tester."""
    webhook = get_object_or_404(
        ProjectWebhookEndpoint.objects.select_related("project"),
        pk=pk,
        tenant=request.tenant,
    )
    deliveries = ProjectWebhookDelivery.objects.filter(tenant=request.tenant, webhook=webhook).order_by("-attempted_at")[:15]

    revealed_secret = None
    reveal_data = request.session.pop("_whk_secret_reveal", None)
    if reveal_data and reveal_data.get("pk") == webhook.pk:
        revealed_secret = reveal_data.get("secret")

    return render(
        request,
        "projects/workflowautomation/webhook/detail.html",
        {
            "webhook": webhook,
            "deliveries": deliveries,
            "test_form": WebhookTestPingForm(),
            "revealed_secret": revealed_secret,
        },
    )


@login_required
def pwh_create(request):
    """Create a new ProjectWebhookEndpoint."""
    if request.method == "POST":
        form = ProjectWebhookEndpointForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            webhook = form.save(commit=False)
            webhook.tenant = request.tenant
            raw_secret = webhook.generate_secret()
            webhook.save()
            request.session["_whk_secret_reveal"] = {"pk": webhook.pk, "secret": raw_secret}
            write_audit_log(
                user=request.user,
                obj=webhook,
                action="create",
                changes={"description": f"Created webhook endpoint {webhook.number}: {webhook.name}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Webhook endpoint {webhook.number} created with generated HMAC secret.")
            return redirect("projects:pwh_detail", pk=webhook.pk)
    else:
        initial = {
            "event_types": ["task.created", "task.completed", "gate.approved"],
        }
        if request.GET.get("project"):
            initial["project"] = request.GET.get("project")
        form = ProjectWebhookEndpointForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "projects/workflowautomation/webhook/form.html",
        {
            "form": form,
            "webhook": None,
            "is_edit": False,
        },
    )


@login_required
def pwh_edit(request, pk):
    """Edit an existing ProjectWebhookEndpoint."""
    webhook = get_object_or_404(ProjectWebhookEndpoint, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectWebhookEndpointForm(request.POST, instance=webhook, tenant=request.tenant)
        if form.is_valid():
            webhook = form.save()
            write_audit_log(
                user=request.user,
                obj=webhook,
                action="update",
                changes={"description": f"Updated webhook endpoint {webhook.number}: {webhook.name}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Webhook endpoint {webhook.number} updated successfully.")
            return redirect("projects:pwh_detail", pk=webhook.pk)
    else:
        form = ProjectWebhookEndpointForm(instance=webhook, tenant=request.tenant)

    return render(
        request,
        "projects/workflowautomation/webhook/form.html",
        {
            "form": form,
            "webhook": webhook,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def pwh_delete(request, pk):
    """Delete a ProjectWebhookEndpoint."""
    webhook = get_object_or_404(ProjectWebhookEndpoint, pk=pk, tenant=request.tenant)
    number = webhook.number
    name = webhook.name
    webhook.delete()
    write_audit_log(
        user=request.user,
        obj=None,
        action="delete",
        changes={"description": f"Deleted webhook endpoint {number}: {name}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Webhook endpoint {number} deleted successfully.")
    return redirect("projects:pwh_list")


@login_required
@require_POST
def pwh_toggle_active(request, pk):
    """Toggle active state of a ProjectWebhookEndpoint."""
    webhook = get_object_or_404(ProjectWebhookEndpoint, pk=pk, tenant=request.tenant)
    webhook.is_active = not webhook.is_active
    webhook.save(update_fields=["is_active", "updated_at"])
    state = "activated" if webhook.is_active else "deactivated"
    write_audit_log(
        user=request.user,
        obj=webhook,
        action="toggle",
        changes={"description": f"{state.capitalize()} webhook endpoint {webhook.number}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Webhook endpoint {webhook.number} {state}.")
    return redirect("projects:pwh_detail", pk=webhook.pk)


@login_required
@require_POST
def pwh_test_ping(request, pk):
    """Emit a simulated test ping delivery to the webhook endpoint."""
    webhook = get_object_or_404(ProjectWebhookEndpoint, pk=pk, tenant=request.tenant)
    form = WebhookTestPingForm(request.POST)

    event_type = "test.ping"
    payload = {
        "event": event_type,
        "webhook": webhook.number,
        "tenant_id": request.tenant.pk,
        "timestamp": timezone.now().isoformat(),
        "data": {"message": "Test ping from NavERP iPaaS dispatcher", "user": request.user.username},
    }

    if form.is_valid():
        event_type = form.cleaned_data["event_type"]
        custom = form.cleaned_data.get("custom_payload")
        if custom:
            try:
                payload["data"] = json.loads(custom)
            except Exception:
                pass

    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = webhook.compute_signature(payload_bytes)

    delivery = ProjectWebhookDelivery.objects.create(
        tenant=request.tenant,
        webhook=webhook,
        event=event_type,
        payload=payload,
        signature=sig,
        status="simulated",
        status_code=200,
        response_body='{"ok": true, "simulated": true, "received": true}',
        duration_ms=45,
    )

    webhook.last_status_code = 200
    webhook.last_fired_at = timezone.now()
    webhook.save(update_fields=["last_status_code", "last_fired_at", "updated_at"])

    write_audit_log(
        user=request.user,
        obj=webhook,
        action="ping",
        changes={"description": f"Test ping dispatched for {webhook.number} (Delivery #{delivery.pk})"},
        tenant=request.tenant,
    )
    messages.success(request, f"Simulated ping dispatched to {webhook.target_url} (Signature: {sig[:12]}...).")
    return redirect("projects:pwh_detail", pk=webhook.pk)


@login_required
@require_POST
def pwh_rotate_secret(request, pk):
    """Rotate HMAC-SHA256 signing secret for the webhook endpoint."""
    webhook = get_object_or_404(ProjectWebhookEndpoint, pk=pk, tenant=request.tenant)
    new_raw = webhook.generate_secret()
    webhook.save(update_fields=["secret", "updated_at"])
    request.session["_whk_secret_reveal"] = {"pk": webhook.pk, "secret": new_raw}

    write_audit_log(
        user=request.user,
        obj=webhook,
        action="rotate",
        changes={"description": f"Rotated HMAC secret for webhook {webhook.number}"},
        tenant=request.tenant,
    )
    messages.success(request, f"HMAC secret rotated successfully for {webhook.number}. Please update your receiver.")
    return redirect("projects:pwh_detail", pk=webhook.pk)


@login_required
def pwh_delivery_list(request):
    """List webhook delivery attempt records across all webhooks."""
    qs = ProjectWebhookDelivery.objects.filter(tenant=request.tenant).select_related("webhook")

    webhook_id = request.GET.get("webhook", "").strip()
    if webhook_id:
        qs = qs.filter(webhook_id=webhook_id)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/workflowautomation/webhook/delivery_list.html",
        {
            "deliveries": page_obj.object_list,
            "page_obj": page_obj,
            "status_choices": ProjectWebhookDelivery.STATUS_CHOICES,
            "webhook_id": webhook_id,
        },
    )


@login_required
def pwh_delivery_detail(request, pk):
    """View full payload, headers, signature and response body of a webhook delivery attempt."""
    delivery = get_object_or_404(
        ProjectWebhookDelivery.objects.select_related("webhook"),
        pk=pk,
        tenant=request.tenant,
    )

    return render(
        request,
        "projects/workflowautomation/webhook/delivery_detail.html",
        {
            "delivery": delivery,
        },
    )
