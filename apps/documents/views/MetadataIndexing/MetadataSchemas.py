import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.MetadataIndexing.MetadataSchemas import MetadataSchemaForm
from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema


@login_required
def metadata_schema_list(request):
    """
    Sub-module 13.5: List all tenant metadata schemas with search and filtering.
    """
    tenant = request.tenant
    qs = MetadataSchema.objects.filter(tenant=tenant)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains(q)) |
            Q(code__icontains(q)) |
            Q(description__icontains(q))
        )

    target_type = request.GET.get("target_type", "").strip()
    if target_type:
        qs = qs.filter(target_type=target_type)

    is_active_param = request.GET.get("is_active", "").strip()
    if is_active_param in ["true", "1"]:
        qs = qs.filter(is_active=True)
    elif is_active_param in ["false", "0"]:
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "schemas": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "q": q,
        "target_type": target_type,
        "is_active": is_active_param,
        "target_type_choices": MetadataSchema.TARGET_TYPE_CHOICES,
    }
    return render(request, "documents/metadata_indexing/metadata_schema/list.html", context)


@login_required
def metadata_schema_create(request):
    """
    Create a new metadata schema definition.
    """
    tenant = request.tenant
    if request.method == "POST":
        form = MetadataSchemaForm(request.POST, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                schema = form.save(commit=False)
                schema.tenant = tenant
                schema.created_by = request.user
                schema.save()
                write_audit_log(request.user, schema, "create", tenant=tenant)
            messages.success(request, f"Metadata Schema '{schema.name}' created successfully.")
            return redirect("documents:metadata_schema_detail", pk=schema.pk)
    else:
        form = MetadataSchemaForm(tenant=tenant)

    context = {
        "form": form,
        "is_edit": False,
        "target_type_choices": MetadataSchema.TARGET_TYPE_CHOICES,
        "inheritance_mode_choices": MetadataSchema.INHERITANCE_MODE_CHOICES,
    }
    return render(request, "documents/metadata_indexing/metadata_schema/form.html", context)


@login_required
def metadata_schema_detail(request, pk):
    """
    Detailed inspection of a metadata schema and its field definitions.
    """
    tenant = request.tenant
    schema = get_object_or_404(
        MetadataSchema.objects.select_related("created_by", "target_folder"),
        pk=pk,
        tenant=tenant,
    )

    fields_list = schema.parsed_fields
    values = schema.metadata_values.filter(tenant=tenant).select_related("document", "version").order_by("-created_at")
    values_count = values.count()

    context = {
        "schema": schema,
        "obj": schema,
        "fields_list": fields_list,
        "values": values,
        "values_count": values_count,
        "target_type_badge": schema.target_type_badge,
        "status_badge": schema.status_badge,
    }
    return render(request, "documents/metadata_indexing/metadata_schema/detail.html", context)


@login_required
def metadata_schema_edit(request, pk):
    """
    Modify an existing metadata schema.
    """
    tenant = request.tenant
    schema = get_object_or_404(MetadataSchema, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = MetadataSchemaForm(request.POST, instance=schema, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                updated_schema = form.save(commit=False)
                updated_schema.version_number += 1
                updated_schema.save()
                write_audit_log(request.user, updated_schema, "update", tenant=tenant)
            messages.success(request, f"Metadata Schema '{updated_schema.name}' updated successfully (v{updated_schema.version_number}).")
            return redirect("documents:metadata_schema_detail", pk=updated_schema.pk)
    else:
        form = MetadataSchemaForm(instance=schema, tenant=tenant)

    context = {
        "form": form,
        "schema": schema,
        "obj": schema,
        "is_edit": True,
        "target_type_choices": MetadataSchema.TARGET_TYPE_CHOICES,
        "inheritance_mode_choices": MetadataSchema.INHERITANCE_MODE_CHOICES,
    }
    return render(request, "documents/metadata_indexing/metadata_schema/form.html", context)


@login_required
@require_POST
def metadata_schema_delete(request, pk):
    """
    Delete a metadata schema.
    """
    tenant = request.tenant
    schema = get_object_or_404(MetadataSchema, pk=pk, tenant=tenant)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    if not is_admin:
        messages.error(request, f"Metadata Schema '{schema.name}' requires administrator authorization to delete.")
        return redirect("documents:metadata_schema_detail", pk=schema.pk)

    name = schema.name
    with transaction.atomic():
        write_audit_log(request.user, schema, "delete", tenant=tenant)
        schema.delete()
    messages.success(request, f"Metadata Schema '{name}' deleted successfully.")
    return redirect("documents:metadata_schema_list")
