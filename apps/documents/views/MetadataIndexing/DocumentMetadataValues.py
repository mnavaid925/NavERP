from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValueForm
from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue


@login_required
def metadata_value_list(request):
    """
    Sub-module 13.5: List all document metadata values with filtering by document, data type, and validation status.
    """
    tenant = request.tenant
    qs = DocumentMetadataValue.objects.filter(tenant=tenant).select_related("document", "version", "schema")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(field_name__icontains(q)) |
            Q(field_label__icontains(q)) |
            Q(value_text__icontains(q)) |
            Q(document__title__icontains(q)) |
            Q(document__number__icontains(q))
        )

    data_type = request.GET.get("data_type", "").strip()
    if data_type:
        qs = qs.filter(data_type=data_type)

    source = request.GET.get("source", "").strip()
    if source:
        qs = qs.filter(source=source)

    validation_status = request.GET.get("validation_status", "").strip()
    if validation_status:
        qs = qs.filter(validation_status=validation_status)

    doc_id = request.GET.get("document", "").strip()
    if doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "metadata_values": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "q": q,
        "data_type": data_type,
        "source": source,
        "validation_status": validation_status,
        "data_type_choices": DocumentMetadataValue.DATA_TYPE_CHOICES,
        "source_choices": DocumentMetadataValue.SOURCE_CHOICES,
        "validation_status_choices": DocumentMetadataValue.VALIDATION_STATUS_CHOICES,
    }
    return render(request, "documents/metadata_indexing/document_metadata_value/list.html", context)


@login_required
def metadata_value_create(request):
    """
    Assign a new metadata key-value to a document.
    """
    tenant = request.tenant
    if request.method == "POST":
        form = DocumentMetadataValueForm(request.POST, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                val = form.save(commit=False)
                val.tenant = tenant
                val.updated_by = request.user
                val.last_validated_at = timezone.now()
                val.save()
                write_audit_log(request.user, val, "create", tenant=tenant)
            messages.success(request, f"Metadata property '{val.field_name}' added to {val.document.title}.")
            return redirect("documents:metadata_value_detail", pk=val.pk)
    else:
        initial = {}
        doc_id = request.GET.get("document", "").strip()
        if doc_id.isdigit():
            initial["document"] = int(doc_id)
        form = DocumentMetadataValueForm(initial=initial, tenant=tenant)

    context = {
        "form": form,
        "is_edit": False,
        "data_type_choices": DocumentMetadataValue.DATA_TYPE_CHOICES,
        "source_choices": DocumentMetadataValue.SOURCE_CHOICES,
        "validation_status_choices": DocumentMetadataValue.VALIDATION_STATUS_CHOICES,
    }
    return render(request, "documents/metadata_indexing/document_metadata_value/form.html", context)


@login_required
def metadata_value_detail(request, pk):
    """
    Detailed inspection of a document metadata value instance.
    """
    tenant = request.tenant
    val = get_object_or_404(
        DocumentMetadataValue.objects.select_related("document", "version", "schema", "updated_by"),
        pk=pk,
        tenant=tenant,
    )

    context = {
        "metadata_value": val,
        "obj": val,
        "status_badge": val.validation_status_badge,
        "source_badge": val.source_badge,
        "data_type_badge": val.data_type_badge,
    }
    return render(request, "documents/metadata_indexing/document_metadata_value/detail.html", context)


@login_required
def metadata_value_edit(request, pk):
    """
    Update an existing document metadata value.
    """
    tenant = request.tenant
    val = get_object_or_404(DocumentMetadataValue, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = DocumentMetadataValueForm(request.POST, instance=val, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                updated_val = form.save(commit=False)
                updated_val.is_overridden = True
                updated_val.updated_by = request.user
                updated_val.last_validated_at = timezone.now()
                updated_val.save()
                write_audit_log(request.user, updated_val, "update", tenant=tenant)
            messages.success(request, f"Metadata property '{updated_val.field_name}' updated successfully.")
            return redirect("documents:metadata_value_detail", pk=updated_val.pk)
    else:
        form = DocumentMetadataValueForm(instance=val, tenant=tenant)

    context = {
        "form": form,
        "metadata_value": val,
        "obj": val,
        "is_edit": True,
        "data_type_choices": DocumentMetadataValue.DATA_TYPE_CHOICES,
        "source_choices": DocumentMetadataValue.SOURCE_CHOICES,
        "validation_status_choices": DocumentMetadataValue.VALIDATION_STATUS_CHOICES,
    }
    return render(request, "documents/metadata_indexing/document_metadata_value/form.html", context)


@login_required
@require_POST
def metadata_value_delete(request, pk):
    """
    Remove a metadata value from a document.
    """
    tenant = request.tenant
    val = get_object_or_404(DocumentMetadataValue, pk=pk, tenant=tenant)
    field_name = val.field_name
    doc_pk = val.document_id
    with transaction.atomic():
        write_audit_log(request.user, val, "delete", tenant=tenant)
        val.delete()
    messages.success(request, f"Metadata property '{field_name}' deleted.")
    return redirect("documents:metadata_value_list")


@login_required
@require_POST
def metadata_value_validate(request, pk):
    """
    Execute validation check on a metadata value against type rules.
    """
    tenant = request.tenant
    val = get_object_or_404(DocumentMetadataValue, pk=pk, tenant=tenant)

    is_valid = True
    error_msg = ""

    if val.data_type in ["integer", "decimal"] and val.value_number is None and not val.value_text:
        is_valid = False
        error_msg = "Expected numeric value."
    elif val.data_type in ["date", "datetime"] and val.value_date is None and not val.value_text:
        is_valid = False
        error_msg = "Expected calendar date value."

    with transaction.atomic():
        val.validation_status = "valid" if is_valid else "invalid"
        val.validation_error = error_msg
        val.last_validated_at = timezone.now()
        val.save()
        write_audit_log(request.user, val, "validate", tenant=tenant)

    if is_valid:
        messages.success(request, f"Property '{val.field_name}' verified as valid.")
    else:
        messages.error(request, f"Property '{val.field_name}' failed validation: {error_msg}")

    return redirect("documents:metadata_value_detail", pk=val.pk)
