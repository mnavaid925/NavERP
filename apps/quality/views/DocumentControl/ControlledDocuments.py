import csv
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.quality.forms.DocumentControl.ControlledDocuments import (
    ControlledDocumentForm,
    ControlledDocumentRevisionForm,
)
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def controlled_document_list(request):
    qs = quality_scope(ControlledDocument.objects.all(), request).select_related("department", "owner")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(revision__icontains=q)
            | Q(description__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(lifecycle_state=status_filter)

    type_filter = request.GET.get("type", "").strip()
    if type_filter:
        qs = qs.filter(document_type=type_filter)

    dept_filter = request.GET.get("department", "").strip()
    if dept_filter and dept_filter.isdigit():
        qs = qs.filter(department_id=int(dept_filter))

    latest_filter = request.GET.get("latest", "1").strip()
    if latest_filter == "1":
        qs = qs.filter(is_latest_revision=True)
    elif latest_filter == "0":
        qs = qs.filter(is_latest_revision=False)

    today = timezone.now().date()
    stats = {
        "total": qs.count(),
        "effective": qs.filter(lifecycle_state="effective").count(),
        "in_review": qs.filter(lifecycle_state__in=["in_review", "pending_approval"]).count(),
        "draft": qs.filter(lifecycle_state="draft").count(),
        "overdue_reviews": qs.filter(
            lifecycle_state="effective", next_review_date__lt=today
        ).count(),
    }

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    department_choices = OrgUnit.objects.filter(tenant=request.tenant)

    context = {
        "documents": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "q": q,
        "status_choices": ControlledDocument.LIFECYCLE_STATE_CHOICES,
        "type_choices": ControlledDocument.DOCUMENT_TYPE_CHOICES,
        "department_choices": department_choices,
        "stats": stats,
    }
    return render(request, "quality/documentcontrol/controlled_document/list.html", context)


@login_required
def controlled_document_create(request):
    if request.method == "POST":
        form = ControlledDocumentForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                doc = form.save(commit=False)
                doc.tenant = request.tenant
                if not doc.owner_id:
                    doc.owner = request.user
                doc.save()
                write_audit_log(request.user, doc, "create", tenant=request.tenant)
            messages.success(request, f"Controlled document {doc.number} ({doc.title}) created.")
            return redirect("quality:controlled_document_detail", pk=doc.pk)
    else:
        form = ControlledDocumentForm(tenant=request.tenant, initial={"owner": request.user})

    return render(
        request,
        "quality/documentcontrol/controlled_document/form.html",
        {"form": form, "title": "Create Controlled Document", "action": "Create"},
    )


@login_required
def controlled_document_detail(request, pk):
    doc = quality_object(
        request,
        ControlledDocument,
        pk,
        select_related=["department", "owner", "supersedes", "superseded_by"],
    )

    change_orders = doc.change_orders.all().select_related("requested_by")[:10]
    signatures = doc.signature_manifests.all().select_related("signer")[:20]
    acknowledgments = doc.acknowledgments.all().select_related("user")[:20]

    # Find revision family
    revision_history = (
        ControlledDocument.objects.filter(tenant=request.tenant, title=doc.title)
        .order_by("-created_at")
        .exclude(pk=doc.pk)
    )

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    can_edit = not doc.is_locked
    can_submit = doc.lifecycle_state == "draft"
    can_approve = is_admin and doc.lifecycle_state in {"in_review", "pending_approval"}
    can_make_effective = is_admin and doc.lifecycle_state == "approved"
    can_obsolete = is_admin and doc.lifecycle_state == "effective"
    can_revise = doc.lifecycle_state == "effective"
    can_sign = True

    context = {
        "document": doc,
        "change_orders": change_orders,
        "signatures": signatures,
        "acknowledgments": acknowledgments,
        "revision_history": revision_history,
        "is_admin": is_admin,
        "can_edit": can_edit,
        "can_submit": can_submit,
        "can_approve": can_approve,
        "can_make_effective": can_make_effective,
        "can_obsolete": can_obsolete,
        "can_revise": can_revise,
        "can_sign": can_sign,
    }
    return render(request, "quality/documentcontrol/controlled_document/detail.html", context)


@login_required
def controlled_document_edit(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.is_locked:
        messages.error(request, f"Document {doc.number} is {doc.get_lifecycle_state_display()} and cannot be modified directly.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    if request.method == "POST":
        form = ControlledDocumentForm(request.POST, request.FILES, instance=doc, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                doc = form.save()
                write_audit_log(request.user, doc, "update", tenant=request.tenant)
            messages.success(request, f"Controlled document {doc.number} updated.")
            return redirect("quality:controlled_document_detail", pk=doc.pk)
    else:
        form = ControlledDocumentForm(instance=doc, tenant=request.tenant)

    return render(
        request,
        "quality/documentcontrol/controlled_document/form.html",
        {"form": form, "document": doc, "title": f"Edit {doc.number}", "action": "Save Changes"},
    )


@login_required
@require_POST
def controlled_document_delete(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.is_effective or doc.is_locked:
        messages.error(request, f"Cannot delete document in '{doc.get_lifecycle_state_display()}' state.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    with transaction.atomic():
        write_audit_log(request.user, doc, "delete", tenant=request.tenant)
        doc.delete()
    messages.success(request, f"Document {doc.number} deleted.")
    return redirect("quality:controlled_document_list")


@login_required
@require_POST
def controlled_document_submit(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.lifecycle_state != "draft":
        messages.error(request, "Only draft documents can be submitted for review.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    with transaction.atomic():
        doc.lifecycle_state = "in_review"
        doc.save(update_fields=["lifecycle_state", "updated_at"])
        write_audit_log(request.user, doc, "submit", tenant=request.tenant)
    messages.success(request, f"Document {doc.number} submitted for review.")
    return redirect("quality:controlled_document_detail", pk=doc.pk)


@login_required
@require_POST
@tenant_admin_required
def controlled_document_approve(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.lifecycle_state not in {"in_review", "pending_approval"}:
        messages.error(request, "Document is not currently pending review/approval.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    with transaction.atomic():
        doc.lifecycle_state = "approved"
        doc.save(update_fields=["lifecycle_state", "updated_at"])
        write_audit_log(request.user, doc, "approve", tenant=request.tenant)
    messages.success(request, f"Document {doc.number} approved.")
    return redirect("quality:controlled_document_detail", pk=doc.pk)


@login_required
@require_POST
@tenant_admin_required
def controlled_document_make_effective(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.lifecycle_state != "approved":
        messages.error(request, "Document must be approved before making it effective.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    today = timezone.now().date()
    with transaction.atomic():
        doc.lifecycle_state = "effective"
        if not doc.effective_date:
            doc.effective_date = today
        if not doc.next_review_date:
            interval = doc.review_interval_months or 12
            doc.next_review_date = doc.effective_date + timedelta(days=interval * 30)

        # Supersede predecessor if linked
        if doc.supersedes:
            old_doc = doc.supersedes
            old_doc.lifecycle_state = "superseded"
            old_doc.is_latest_revision = False
            old_doc.superseded_by = doc
            old_doc.save(update_fields=["lifecycle_state", "is_latest_revision", "superseded_by", "updated_at"])
            write_audit_log(request.user, old_doc, "supersede", tenant=request.tenant)

        doc.is_latest_revision = True
        doc.save()
        write_audit_log(request.user, doc, "effective", tenant=request.tenant)

    messages.success(request, f"Document {doc.number} Rev {doc.revision} is now EFFECTIVE.")
    return redirect("quality:controlled_document_detail", pk=doc.pk)


@login_required
@require_POST
@tenant_admin_required
def controlled_document_obsolete(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.lifecycle_state != "effective":
        messages.error(request, "Only effective documents can be retired to obsolete.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    with transaction.atomic():
        doc.lifecycle_state = "obsolete"
        doc.archived_at = timezone.now()
        doc.is_latest_revision = False
        doc.save(update_fields=["lifecycle_state", "archived_at", "is_latest_revision", "updated_at"])
        write_audit_log(request.user, doc, "obsolete", tenant=request.tenant)

    messages.warning(request, f"Document {doc.number} marked as OBSOLETE.")
    return redirect("quality:controlled_document_detail", pk=doc.pk)


@login_required
def controlled_document_new_revision(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.lifecycle_state != "effective":
        messages.error(request, "New revisions can only be branched from currently effective documents.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    if request.method == "POST":
        form = ControlledDocumentRevisionForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                new_doc = ControlledDocument(
                    tenant=request.tenant,
                    title=doc.title,
                    document_type=doc.document_type,
                    department=doc.department,
                    owner=request.user,
                    revision=form.cleaned_data["revision"],
                    classification=doc.classification,
                    file=form.cleaned_data.get("file") or doc.file,
                    description=form.cleaned_data.get("description") or doc.description,
                    change_summary=form.cleaned_data["change_summary"],
                    review_interval_months=doc.review_interval_months,
                    retention_years=doc.retention_years,
                    supersedes=doc,
                    lifecycle_state="draft",
                    is_latest_revision=False,
                )
                new_doc.save()
                write_audit_log(request.user, new_doc, "create", tenant=request.tenant)
            messages.success(request, f"New draft revision {new_doc.revision} branched from {doc.number}.")
            return redirect("quality:controlled_document_detail", pk=new_doc.pk)
    else:
        # Suggest next revision
        try:
            parts = doc.revision.split(".")
            next_rev = f"{parts[0]}.{int(parts[1]) + 1}" if len(parts) > 1 else f"{int(parts[0]) + 1}.0"
        except (ValueError, IndexError):
            next_rev = f"{doc.revision}.1"
        form = ControlledDocumentRevisionForm(tenant=request.tenant, initial={"revision": next_rev})

    return render(
        request,
        "quality/documentcontrol/controlled_document/form.html",
        {"form": form, "document": doc, "title": f"Branch Revision for {doc.number}", "action": "Branch Draft Revision"},
    )


@login_required
def controlled_document_export(request):
    qs = quality_scope(ControlledDocument.objects.all(), request).select_related("department", "owner")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="controlled_documents.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow(["Number", "Title", "Type", "Revision", "State", "Classification", "Department", "Owner", "Effective Date", "Next Review Date"])
    for d in qs:
        writer.writerow([
            csv_safe(d.number),
            csv_safe(d.title),
            csv_safe(d.get_document_type_display()),
            csv_safe(d.revision),
            csv_safe(d.get_lifecycle_state_display()),
            csv_safe(d.get_classification_display()),
            csv_safe(d.department.name if d.department else ""),
            csv_safe(d.owner.username if d.owner else ""),
            csv_safe(d.effective_date),
            csv_safe(d.next_review_date),
        ])
    return response


@login_required
def document_archive_vault(request):
    qs = quality_scope(
        ControlledDocument.objects.filter(lifecycle_state__in=["superseded", "obsolete", "archived"]),
        request,
    ).select_related("department", "owner")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(revision__icontains=q)
            | Q(description__icontains=q)
        )

    stats = {
        "total_vault": qs.count(),
        "superseded": qs.filter(lifecycle_state="superseded").count(),
        "obsolete": qs.filter(lifecycle_state="obsolete").count(),
        "archived": qs.filter(lifecycle_state="archived").count(),
    }

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "vault_documents": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "q": q,
        "stats": stats,
    }
    return render(request, "quality/documentcontrol/document_archive_vault.html", context)
