import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlertForm
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_search_alert_list(request):
    qs = documents_scope(DocumentSearchAlert.objects.all(), request).select_related("saved_search", "subscriber")

    if not getattr(request.user, "is_tenant_admin", False):
        qs = qs.filter(subscriber=request.user)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(saved_search__name__icontains=q) | Q(notes__icontains=q))

    frequency = request.GET.get("frequency", "").strip()
    if frequency:
        qs = qs.filter(frequency=frequency)

    delivery = request.GET.get("delivery_channel", "").strip()
    if delivery:
        qs = qs.filter(delivery_channel=delivery)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    total_count = qs.count()
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "documents/search_discovery/document_search_alert/list.html",
        {
            "page_obj": page_obj,
            "search_alerts": page_obj.object_list,
            "total_count": total_count,
            "frequency_choices": DocumentSearchAlert.FREQUENCY_CHOICES,
            "delivery_choices": DocumentSearchAlert.DELIVERY_CHOICES,
            "status_choices": DocumentSearchAlert.STATUS_CHOICES,
        },
    )


@login_required
def document_search_alert_detail(request, pk):
    search_alert = documents_object(
        request,
        DocumentSearchAlert,
        pk,
        select_related=("saved_search", "subscriber"),
    )

    if search_alert.subscriber != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to view this search alert.")

    # Fetch recently matched documents if any IDs recorded
    matched_ids = search_alert.get_last_result_ids_list()
    matched_documents = Document.objects.filter(
        tenant=request.tenant,
        pk__in=matched_ids,
    ).select_related("owner", "department")[:10] if matched_ids else []

    return render(
        request,
        "documents/search_discovery/document_search_alert/detail.html",
        {
            "search_alert": search_alert,
            "matched_documents": matched_documents,
        },
    )


@login_required
def document_search_alert_create(request):
    initial = {}
    saved_search_id = request.GET.get("saved_search", "").strip()
    if saved_search_id and saved_search_id.isdigit():
        saved_search = DocumentSavedSearch.objects.filter(
            tenant=request.tenant,
            pk=int(saved_search_id),
        ).first()
        if saved_search:
            initial["saved_search"] = saved_search

    if request.method == "POST":
        form = DocumentSearchAlertForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            search_alert = form.save(commit=False)
            search_alert.tenant = request.tenant
            search_alert.subscriber = request.user
            search_alert.save()
            write_audit_log(request.user, search_alert, "create", tenant=request.tenant)
            messages.success(request, f"Search alert '{search_alert.number}' created successfully.")
            return redirect("documents:document_search_alert_detail", pk=search_alert.pk)
    else:
        form = DocumentSearchAlertForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "documents/search_discovery/document_search_alert/form.html",
        {
            "form": form,
            "search_alert": None,
            "is_edit": False,
        },
    )


@login_required
def document_search_alert_edit(request, pk):
    search_alert = documents_object(request, DocumentSearchAlert, pk)

    if search_alert.subscriber != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to edit this search alert.")

    if request.method == "POST":
        form = DocumentSearchAlertForm(request.POST, instance=search_alert, tenant=request.tenant)
        if form.is_valid():
            search_alert = form.save()
            write_audit_log(request.user, search_alert, "update", tenant=request.tenant)
            messages.success(request, f"Search alert '{search_alert.number}' updated successfully.")
            return redirect("documents:document_search_alert_detail", pk=search_alert.pk)
    else:
        form = DocumentSearchAlertForm(instance=search_alert, tenant=request.tenant)

    return render(
        request,
        "documents/search_discovery/document_search_alert/form.html",
        {
            "form": form,
            "search_alert": search_alert,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def document_search_alert_delete(request, pk):
    search_alert = documents_object(request, DocumentSearchAlert, pk)

    if search_alert.subscriber != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to delete this search alert.")

    num = search_alert.number
    write_audit_log(request.user, search_alert, "delete", tenant=request.tenant)
    search_alert.delete()
    messages.success(request, f"Search alert '{num}' was deleted.")
    return redirect("documents:document_search_alert_list")


@login_required
@require_POST
def document_search_alert_toggle_active(request, pk):
    search_alert = documents_object(request, DocumentSearchAlert, pk)

    if search_alert.subscriber != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to modify this search alert.")

    search_alert.is_active = not search_alert.is_active
    search_alert.status = "active" if search_alert.is_active else "paused"
    search_alert.save(update_fields=["is_active", "status"])
    write_audit_log(request.user, search_alert, "toggle", tenant=request.tenant)

    status_str = "activated" if search_alert.is_active else "paused"
    messages.success(request, f"Search alert '{search_alert.number}' has been {status_str}.")
    return redirect(request.META.get("HTTP_REFERER", "documents:document_search_alert_list"))


@login_required
@require_POST
def document_search_alert_run_check(request, pk):
    search_alert = documents_object(
        request,
        DocumentSearchAlert,
        pk,
        select_related=("saved_search",),
    )

    if search_alert.subscriber != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to execute this check.")

    saved_search = search_alert.saved_search
    # Run matched document query
    docs_qs = Document.objects.filter(tenant=request.tenant)
    if saved_search.query_text:
        docs_qs = docs_qs.filter(
            Q(title__icontains=saved_search.query_text) |
            Q(description__icontains=saved_search.query_text) |
            Q(number__icontains=saved_search.query_text)
        )

    filters = saved_search.get_filters_dict()
    if filters.get("document_type"):
        docs_qs = docs_qs.filter(document_type=filters["document_type"])
    if filters.get("classification"):
        docs_qs = docs_qs.filter(classification=filters["classification"])
    if filters.get("status"):
        docs_qs = docs_qs.filter(status=filters["status"])

    current_ids = list(docs_qs.values_list("pk", flat=True)[:50])
    old_ids = set(search_alert.get_last_result_ids_list())
    new_delta_count = len([x for x in current_ids if x not in old_ids])

    search_alert.new_matches_count = new_delta_count
    search_alert.last_result_ids = json.dumps(current_ids)
    search_alert.last_checked_at = timezone.now()
    if new_delta_count > 0:
        search_alert.last_notified_at = timezone.now()
    search_alert.save(update_fields=["new_matches_count", "last_result_ids", "last_checked_at", "last_notified_at"])

    write_audit_log(request.user, search_alert, "execute", tenant=request.tenant)
    messages.success(request, f"Alert check complete: {len(current_ids)} total matches, {new_delta_count} new since last check.")
    return redirect("documents:document_search_alert_detail", pk=search_alert.pk)
