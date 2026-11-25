import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
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
from apps.documents.views._common import (
    documents_object,
    documents_scope,
    paginate_queryset,
    parse_int_param,
)


@login_required
def webhook_trigger_list(request):
    qs = documents_scope(
        DocumentWebhookTrigger.objects.defer(
            "custom_headers",
            "payload_template_json",
            "delivery_history_json",
            "signing_secret",
            "description",
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

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(is_active=True)),
        simulated_count=Count("id", filter=Q(last_status="simulated")),
        total_fires=Sum("fire_count"),
    )

    page_obj = paginate_queryset(qs, request, per_page=15)

    context = {
        "webhooks": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": stats["total_count"] or 0,
        "active_count": stats["active_count"] or 0,
        "simulated_count": stats["simulated_count"] or 0,
        "total_fires": stats["total_fires"] or 0,
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

    delivery_history = [
        {
            **(entry if isinstance(entry, dict) else {"payload": entry}),
            "payload_json": json.dumps(
                entry.get("payload") if isinstance(entry, dict) else entry,
                sort_keys=True,
            ),
        }
        for entry in reversed(webhook.delivery_history_json or [])
    ]
    all_docs = list(
        Document.objects.filter(tenant=request.tenant)
        .only("id", "number", "title", "current_version_label", "created_at", "tenant_id")
        .order_by("-created_at", "title")
    )
    tenant_documents = all_docs[:25]
    ping_form = WebhookTestPingForm(tenant=request.tenant)
    ping_form.fields["document"].choices = [("", "Sample Payload (No Document)")] + [
        (d.pk, str(d)) for d in all_docs
    ]

    context = {
        "webhook": webhook,
        "revealed_secret": revealed_secret,
        "delivery_history": delivery_history,
        "custom_headers_json": json.dumps(webhook.custom_headers or {}, indent=2),
        "payload_template_json": json.dumps(webhook.payload_template_json or {}, indent=2),
        "ping_form": ping_form,
        "tenant_documents": tenant_documents,
    }
    return render(request, "documents/workflow_automation/webhook_trigger/detail.html", context)


@login_required
@tenant_admin_required
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
@tenant_admin_required
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
    webhook = documents_object(request, DocumentWebhookTrigger, pk, select_related=("tenant",))
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
    webhook = documents_object(request, DocumentWebhookTrigger, pk, select_related=("tenant",))
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
    webhook = documents_object(request, DocumentWebhookTrigger, pk, select_related=("tenant",))
    form = WebhookTestPingForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        first_err = next(iter(form.errors.values()), ["Invalid test ping parameters."])[0]
        messages.error(request, f"Test ping rejected: {first_err}")
        return redirect("documents:webhook_trigger_detail", pk=webhook.pk)

    event_name = form.cleaned_data.get("event_override") or webhook.trigger_event
    doc = form.cleaned_data.get("document")

    payload_data = {
        "test_ping": True,
        "triggered_by": request.user.username,
        "document_number": doc.number if doc else "SAMPLE-DOC",
        "document_title": doc.title if doc else "Sample Document Payload",
    }
    with transaction.atomic():
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
        request, DocumentWebhookTrigger, pk, select_related=("tenant", "process_definition")
    )
    if not webhook.is_active:
        messages.warning(
            request,
            f"Webhook trigger {webhook.number} is paused. Activate it before simulating inbound events.",
        )
        return redirect("documents:webhook_trigger_detail", pk=webhook.pk)

    doc_id = request.POST.get("document_id", "").strip()
    doc = None
    if doc_id:
        _, parsed_doc_id = parse_int_param(doc_id)
        if parsed_doc_id is None:
            messages.error(request, "Invalid target document identifier.")
            return redirect("documents:webhook_trigger_detail", pk=webhook.pk)
        doc = Document.objects.filter(tenant=request.tenant, pk=parsed_doc_id).first()
        if doc is None:
            messages.error(request, "Selected target document was not found in this workspace.")
            return redirect("documents:webhook_trigger_detail", pk=webhook.pk)

    if webhook.process_definition_id and doc is not None:
        try:
            with transaction.atomic():
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
        except ValidationError as exc:
            with transaction.atomic():
                dispatch_simulated_webhook(
                    webhook,
                    "inbound.trigger",
                    {"note": f"Callback logged; process launch skipped ({exc.messages[0]})", "document": doc.number},
                    document=doc,
                    actor=request.user,
                    request=request,
                )
                write_audit_log(request.user, webhook, "inbound", tenant=request.tenant)
            messages.warning(
                request,
                f"Simulated inbound callback logged, but linked blueprint could not launch: {exc.messages[0]}",
            )
            return redirect("documents:webhook_trigger_detail", pk=webhook.pk)
        messages.success(
            request,
            f"Simulated inbound webhook triggered process instance {inst.number} for {doc.number}.",
        )
    else:
        with transaction.atomic():
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
