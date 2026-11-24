import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.WorkflowAutomation.DocumentWebhookTriggers import (
    DocumentWebhookTriggerForm,
    WebhookTestPingForm,
)
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.WorkflowAutomation.DocumentWebhookTriggers import (
    DocumentWebhookTrigger,
)
from apps.documents.services.workflow_automation import (
    dispatch_simulated_webhook,
    start_process_instance,
)
from apps.documents.views._common import documents_object, documents_scope


@login_required
def webhook_trigger_list(request):
    qs = documents_scope(
        DocumentWebhookTrigger.objects.select_related(
            "process_definition", "connector_ref", "owner"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(target_url__icontains=q)
            | Q(description__icontains=q)
        )

    direction = request.GET.get("direction", "").strip()
    if direction:
        qs = qs.filter(direction=direction)

    trigger_event = request.GET.get("trigger_event", "").strip()
    if trigger_event:
        qs = qs.filter(trigger_event=trigger_event)

    last_status = request.GET.get("last_status", "").strip()
    if last_status:
        qs = qs.filter(last_status=last_status)

    status = request.GET.get("status", "").strip()
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    total_count = qs.count()
    active_count = qs.filter(is_active=True).count()
    simulated_count = qs.filter(last_status="simulated").count()
    total_fires = qs.aggregate(total=Sum("fire_count"))["total"] or 0

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "webhooks": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "simulated_count": simulated_count,
        "total_fires": total_fires,
        "direction_choices": DocumentWebhookTrigger.DIRECTION_CHOICES,
        "trigger_choices": DocumentWebhookTrigger.TRIGGER_EVENT_CHOICES,
        "last_status_choices": DocumentWebhookTrigger.LAST_STATUS_CHOICES,
        "q": q,
        "direction": direction,
        "trigger_event": trigger_event,
        "last_status": last_status,
        "status": status,
    }
    return render(request, "documents/workflow_automation/webhook_trigger/list.html", context)


@login_required
def webhook_trigger_detail(request, pk):
    webhook = documents_object(
        request,
        DocumentWebhookTrigger,
        pk,
        select_related=("process_definition", "connector_ref", "owner"),
    )
    revealed_secret = None
    reveal = request.session.get("_dwhk_secret_reveal")
    if isinstance(reveal, dict) and reveal.get("pk") == webhook.pk:
        request.session.pop("_dwhk_secret_reveal", None)
        revealed_secret = reveal.get("secret")

    delivery_history = list(reversed(webhook.delivery_history_json or []))
    tenant_documents = Document.objects.filter(tenant=request.tenant).order_by("-created_at")[:25]

    context = {
        "webhook": webhook,
        "revealed_secret": revealed_secret,
        "delivery_history": delivery_history,
        "ping_form": WebhookTestPingForm(tenant=request.tenant),
        "tenant_documents": tenant_documents,
    }
    return render(request, "documents/workflow_automation/webhook_trigger/detail.html", context)


@login_required
def webhook_trigger_create(request):
    if request.method == "POST":
        form = DocumentWebhookTriggerForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                webhook = form.save(commit=False)
                webhook.tenant = request.tenant
                webhook.owner = request.user
                raw_secret = webhook.generate_signing_secret()
                webhook.save()
                write_audit_log(request.user, webhook, "create", tenant=request.tenant)
            request.session["_dwhk_secret_reveal"] = {"pk": webhook.pk, "secret": raw_secret}
            messages.success(
                request,
                f"Webhook trigger {webhook.number} created. Copy your signing secret below (shown once).",
            )
            return redirect("documents:webhook_trigger_detail", pk=webhook.pk)
    else:
        form = DocumentWebhookTriggerForm(
            tenant=request.tenant,
            initial={"custom_headers": "{}", "payload_template_json": "{}"},
        )

    context = {
        "form": form,
        "webhook": None,
        "is_edit": False,
    }
    return render(request, "documents/workflow_automation/webhook_trigger/form.html", context)


@login_required
def webhook_trigger_edit(request, pk):
    webhook = documents_object(request, DocumentWebhookTrigger, pk)
    if request.method == "POST":
        form = DocumentWebhookTriggerForm(request.POST, instance=webhook, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                updated = form.save()
                write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Webhook trigger {updated.number} updated.")
            return redirect("documents:webhook_trigger_detail", pk=updated.pk)
    else:
        form = DocumentWebhookTriggerForm(
            instance=webhook,
            tenant=request.tenant,
            initial={
                "custom_headers": json.dumps(webhook.custom_headers or {}, indent=2),
                "payload_template_json": json.dumps(webhook.payload_template_json or {}, indent=2),
            },
        )

    context = {
        "form": form,
        "webhook": webhook,
        "is_edit": True,
    }
    return render(request, "documents/workflow_automation/webhook_trigger/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def webhook_trigger_delete(request, pk):
    webhook = documents_object(request, DocumentWebhookTrigger, pk)
    number = webhook.number
    with transaction.atomic():
        write_audit_log(request.user, webhook, "delete", tenant=request.tenant)
        webhook.delete()
    messages.success(request, f"Webhook trigger {number} deleted.")
    return redirect("documents:webhook_trigger_list")


@login_required
@require_POST
@tenant_admin_required
def webhook_trigger_rotate_secret(request, pk):
    webhook = documents_object(request, DocumentWebhookTrigger, pk)
    with transaction.atomic():
        raw_secret = webhook.generate_signing_secret()
        webhook.save(update_fields=["signing_secret", "signing_secret_prefix", "updated_at"])
        write_audit_log(request.user, webhook, "rotate", tenant=request.tenant)
    request.session["_dwhk_secret_reveal"] = {"pk": webhook.pk, "secret": raw_secret}
    messages.success(request, f"HMAC signing secret rotated for {webhook.number} (shown once below).")
    return redirect("documents:webhook_trigger_detail", pk=webhook.pk)


@login_required
@require_POST
def webhook_trigger_test_ping(request, pk):
    webhook = documents_object(request, DocumentWebhookTrigger, pk)
    form = WebhookTestPingForm(request.POST, tenant=request.tenant)
    event_name = webhook.trigger_event
    doc = None
    if form.is_valid():
        if form.cleaned_data.get("event_override"):
            event_name = form.cleaned_data["event_override"]
        doc = form.cleaned_data.get("document")

    payload_data = {
        "test_ping": True,
        "triggered_by": request.user.username,
        "document_number": doc.number if doc else "SAMPLE-DOC",
        "document_title": doc.title if doc else "Sample Document Payload",
    }
    dispatch_simulated_webhook(
        webhook,
        event_name,
        payload_data,
        document=doc,
        actor=request.user,
        request=request,
    )
    write_audit_log(request.user, webhook, "ping", tenant=request.tenant)
    messages.success(
        request,
        f"Simulated signed webhook delivery recorded for {webhook.number} (zero outbound HTTP).",
    )
    return redirect("documents:webhook_trigger_detail", pk=webhook.pk)


@login_required
@require_POST
def webhook_trigger_simulate_inbound(request, pk):
    webhook = documents_object(
        request, DocumentWebhookTrigger, pk, select_related=("process_definition",)
    )
    doc_id = request.POST.get("document_id", "").strip()
    doc = None
    if doc_id and doc_id.isdigit():
        doc = Document.objects.filter(tenant=request.tenant, pk=int(doc_id)).first()

    if webhook.process_definition_id and doc is not None:
        inst = start_process_instance(
            tenant=request.tenant,
            process_definition=webhook.process_definition,
            document=doc,
            actor=request.user,
            context_variables={"inbound_webhook": webhook.number},
            request=request,
        )
        dispatch_simulated_webhook(
            webhook,
            "inbound.trigger",
            {"launched_instance": inst.number, "document": doc.number},
            document=doc,
            actor=request.user,
            request=request,
        )
        write_audit_log(request.user, webhook, "inbound", tenant=request.tenant)
        messages.success(
            request,
            f"Simulated inbound webhook triggered process instance {inst.number} for {doc.number}.",
        )
    else:
        dispatch_simulated_webhook(
            webhook,
            "inbound.trigger",
            {"note": "Simulated inbound callback payload received locally"},
            document=doc,
            actor=request.user,
            request=request,
        )
        write_audit_log(request.user, webhook, "inbound", tenant=request.tenant)
        messages.info(request, f"Simulated inbound event logged for {webhook.number}.")
    return redirect("documents:webhook_trigger_detail", pk=webhook.pk)
