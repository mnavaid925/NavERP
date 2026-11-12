"""Function-based views for Controlled Asset Documents & Revision Management (11.16)."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDocumentKnowledge.AssetDocuments import AssetDocumentForm
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetDocumentKnowledge.AssetDocuments import AssetDocument
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetDocumentKnowledge._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_asset_document_readable,
    is_tenant_admin_user,
    readable_asset_document_q,
    serve_protected_attachment,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log
from apps.scm.models.AssetManagement.Assets import Asset


def _next_revision_label(current_label, next_seq):
    """Advance revision label cleanly (Rev A -> Rev B, Rev 1 -> Rev 2, else Rev N)."""
    label = (current_label or "").strip()
    if label.startswith("Rev ") and len(label) == 5 and label[-1].isalpha():
        ch = label[-1].upper()
        if "A" <= ch < "Z":
            return f"Rev {chr(ord(ch) + 1)}"
        if ch == "Z":
            return "Rev AA"
    return f"Rev {next_seq}"


_DOC_LIST_SELECT_RELATED = (
    "operational_asset",
    "asset_category",
    "checked_out_by",
    "supersedes",
)
_DOC_EXPORT_SELECT_RELATED = ("operational_asset",)


def _filter_document_queryset(
    request, base_qs, select_related=_DOC_LIST_SELECT_RELATED
):
    """Apply search and dropdown GET filters to an AssetDocument queryset."""
    qs = base_qs.select_related(*select_related) if select_related else base_qs
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(tag_code__icontains=search_query)
            | Q(manufacturer_ref__icontains=search_query)
            | Q(change_request_ref__icontains=search_query)
            | Q(revision_label__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "document_class",
        allowed_values={val for val, _ in AssetDocument.DOCUMENT_CLASS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "access_classification",
        allowed_values={val for val, _ in AssetDocument.ACCESS_CLASSIFICATION_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "change_type",
        allowed_values={val for val, _ in AssetDocument.CHANGE_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in AssetDocument.STATUS_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "operational_asset")
    qs = apply_fk_filter(qs, request, "asset_category")
    qs = apply_fk_filter(qs, request, "org_unit")
    return qs


def _build_document_list_context(request, base_qs, filtered_qs):
    """Assemble shared KPI, filter dropdown, and paginated context for document lists."""
    today = timezone.localdate()
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    kpis = base_qs.aggregate(
        total_count=Count("id"),
        approved_count=Count(
            "id", filter=Q(status="approved", is_current_revision=True)
        ),
        in_review_count=Count("id", filter=Q(status="in_review")),
        expiring_soon_count=Count(
            "id",
            filter=Q(
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=30),
            ),
        ),
        checked_out_count=Count("id", filter=Q(checked_out_by__isnull=False)),
        draft_count=Count("id", filter=Q(status="draft")),
    )

    return {
        "documents": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": kpis["total_count"] or 0,
        "approved_count": kpis["approved_count"] or 0,
        "in_review_count": kpis["in_review_count"] or 0,
        "expiring_soon_count": kpis["expiring_soon_count"] or 0,
        "checked_out_count": kpis["checked_out_count"] or 0,
        "draft_count": kpis["draft_count"] or 0,
        "class_choices": AssetDocument.DOCUMENT_CLASS_CHOICES,
        "classification_choices": AssetDocument.ACCESS_CLASSIFICATION_CHOICES,
        "change_type_choices": AssetDocument.CHANGE_TYPE_CHOICES,
        "status_choices": AssetDocument.STATUS_CHOICES,
        "assets_list": Asset.objects.filter(tenant=request.tenant).order_by("name"),
        "categories": AssetCategory.objects.filter(tenant=request.tenant).order_by(
            "name"
        ),
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "search_query": request.GET.get("q", "").strip(),
    }


@login_required
def asset_document_list(request):
    """Controlled asset documentation repository list view."""
    base_qs = assets_scope(AssetDocument.objects.all(), request).filter(
        readable_asset_document_q(request.user)
    )
    filtered_qs = _filter_document_queryset(request, base_qs).defer(
        "spec_delta_notes", "review_notes", "description"
    )
    context = _build_document_list_context(request, base_qs, filtered_qs)
    return render(
        request,
        "assets/assetdocumentknowledge/asset_document/list.html",
        context,
    )


_CHANGE_QUEUE_Q = (
    Q(status__in=["draft", "in_review"])
    | Q(revision_sequence__gt=1)
    | Q(supersedes__isnull=False)
    | Q(checked_out_by__isnull=False)
    | ~Q(change_type="new_issue")
)


@login_required
def asset_document_change_list(request):
    """Version control, engineering change requests, and review queue view."""
    base_qs = (
        assets_scope(AssetDocument.objects.all(), request)
        .filter(readable_asset_document_q(request.user))
        .filter(_CHANGE_QUEUE_Q)
    )
    filtered_qs = _filter_document_queryset(request, base_qs).defer(
        "spec_delta_notes", "review_notes", "description"
    )
    context = _build_document_list_context(request, base_qs, filtered_qs)
    return render(
        request,
        "assets/assetdocumentknowledge/asset_document/changes.html",
        context,
    )


@login_required
def asset_document_export_csv(request):
    """Export filtered tenant AssetDocuments as an injection-hardened CSV."""
    base_qs = assets_scope(AssetDocument.objects.all(), request).filter(
        readable_asset_document_q(request.user)
    )
    if request.GET.get("scope", "").strip() == "changes":
        base_qs = base_qs.filter(_CHANGE_QUEUE_Q)
    filtered_qs = (
        _filter_document_queryset(
            request, base_qs, select_related=_DOC_EXPORT_SELECT_RELATED
        )
        .only(
            "id",
            "number",
            "title",
            "document_class",
            "access_classification",
            "revision_label",
            "is_current_revision",
            "change_type",
            "change_request_ref",
            "status",
            "effective_date",
            "expiry_date",
            "file_checksum",
            "operational_asset",
        )[:10000]
        .iterator(chunk_size=1000)
    )
    headers = [
        "Document #",
        "Title",
        "Class",
        "Access",
        "Revision",
        "Current?",
        "Change Type",
        "ECR Ref",
        "Status",
        "Asset",
        "Effective Date",
        "Expiry Date",
        "SHA-256",
    ]
    rows = (
        [
            doc.number,
            doc.title,
            doc.get_document_class_display(),
            doc.get_access_classification_display(),
            doc.revision_label,
            "Yes" if doc.is_current_revision else "No",
            doc.get_change_type_display(),
            doc.change_request_ref,
            doc.get_status_display(),
            str(doc.operational_asset) if doc.operational_asset else "",
            doc.effective_date.isoformat() if doc.effective_date else "",
            doc.expiry_date.isoformat() if doc.expiry_date else "",
            doc.short_checksum,
        ]
        for doc in filtered_qs
    )
    return csv_export_response(
        filename="asset_documents_11_16.csv",
        headers=headers,
        rows=rows,
    )


_DOC_LINEAGE_FIELDS = (
    "id",
    "tenant_id",
    "number",
    "revision_label",
    "revision_sequence",
    "is_current_revision",
    "change_type",
    "change_request_ref",
    "access_classification",
    "owner_id",
    "reviewer_id",
    "status",
    "effective_date",
    "supersedes_id",
)


@login_required
def asset_document_detail(request, pk):
    """Controlled document detail view with revision chain, checkout state, and cross-links."""
    doc = assets_object(
        request,
        AssetDocument,
        pk,
        queryset=assets_scope(AssetDocument.objects.all(), request).filter(
            readable_asset_document_q(request.user)
        ),
        select_related=(
            "operational_asset",
            "fixed_asset",
            "asset_model",
            "asset_category",
            "specification_template",
            "warranty",
            "compliance_framework",
            "vendor_party",
            "core_document",
            "org_unit",
            "owner",
            "reviewer",
            "approved_by",
            "checked_out_by",
            "supersedes__supersedes__supersedes__supersedes",
        ),
    )

    chain_seen = {doc.pk}
    ancestors = []
    cur = doc
    for _ in range(25):
        next_id = cur.supersedes_id
        if not next_id or next_id in chain_seen:
            break
        if "supersedes" in cur._state.fields_cache:
            nxt = cur._state.fields_cache["supersedes"]
        else:
            nxt = (
                AssetDocument.objects.filter(tenant=request.tenant, pk=next_id)
                .filter(readable_asset_document_q(request.user))
                .only(*_DOC_LINEAGE_FIELDS)
                .first()
            )
        if (
            nxt is None
            or nxt.pk in chain_seen
            or nxt.tenant_id != request.tenant.pk
            or not is_asset_document_readable(nxt, request.user)
        ):
            break
        chain_seen.add(nxt.pk)
        ancestors.append(nxt)
        cur = nxt

    descendants = []
    frontier_ids = [doc.pk]
    while frontier_ids and len(descendants) < 25:
        children = list(
            AssetDocument.objects.filter(
                tenant=request.tenant, supersedes_id__in=frontier_ids
            )
            .filter(readable_asset_document_q(request.user))
            .only(*_DOC_LINEAGE_FIELDS)
            .order_by("revision_sequence", "pk")
        )
        next_frontier = []
        for child in children:
            if child.pk in chain_seen:
                continue
            chain_seen.add(child.pk)
            descendants.append(child)
            next_frontier.append(child.pk)
            if len(descendants) >= 25:
                break
        frontier_ids = next_frontier

    revision_history = list(reversed(ancestors)) + [doc] + descendants
    revision_history.sort(
        key=lambda item: (item.revision_sequence, item.pk),
        reverse=True,
    )

    linked_procedures = (
        doc.operating_procedures.filter(tenant=request.tenant).order_by("-updated_at")
        if hasattr(doc, "operating_procedures")
        else AssetDocument.objects.none()
    )
    linked_articles = (
        doc.knowledge_articles.filter(tenant=request.tenant).order_by("-updated_at")
        if hasattr(doc, "knowledge_articles")
        else AssetDocument.objects.none()
    )

    is_admin = is_tenant_admin_user(request.user)
    checkout_ok = doc.checked_out_by_id in (None, request.user.id) or is_admin
    context = {
        "document": doc,
        "revision_history": revision_history,
        "linked_procedures": linked_procedures,
        "linked_articles": linked_articles,
        "can_edit": doc.status in AssetDocument.EDITABLE_STATUSES and checkout_ok,
        "can_approve": is_admin and doc.status in AssetDocument.EDITABLE_STATUSES,
        "can_checkin": (
            doc.checked_out_by_id is not None
            and (doc.checked_out_by_id == request.user.id or is_admin)
        ),
    }
    return render(
        request,
        "assets/assetdocumentknowledge/asset_document/detail.html",
        context,
    )


@login_required
def asset_document_create(request):
    """Create a new controlled asset document or draft revision."""
    if request.method == "POST":
        form = AssetDocumentForm(
            request.POST, request.FILES, tenant=request.tenant, user=request.user
        )
        if form.is_valid():
            doc = form.save(commit=False)
            doc.tenant = request.tenant
            doc.owner = request.user
            doc.status = "draft"
            if doc.supersedes_id:
                doc.is_current_revision = False
                doc.revision_sequence = max(2, (doc.supersedes.revision_sequence or 1) + 1)
            else:
                doc.is_current_revision = True
                doc.revision_sequence = 1
            doc.save()
            write_audit_log(request.user, doc, "create", tenant=request.tenant)
            messages.success(request, f"Created document {doc.number}.")
            return redirect("assets:asset_document_detail", pk=doc.pk)
    else:
        form = AssetDocumentForm(tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/assetdocumentknowledge/asset_document/form.html",
        {
            "form": form,
            "document": None,
            "is_edit": False,
            "title": "New Asset Document",
        },
    )


@login_required
def asset_document_edit(request, pk):
    """Edit an unlocked Draft / In-Review controlled document."""
    doc = assets_object(
        request,
        AssetDocument,
        pk,
        queryset=assets_scope(AssetDocument.objects.all(), request).filter(
            readable_asset_document_q(request.user)
        ),
    )
    if doc.is_locked:
        messages.warning(
            request,
            f"Document {doc.number} is {doc.get_status_display()} and cannot be edited. Create a new revision instead.",
        )
        return redirect("assets:asset_document_detail", pk=doc.pk)
    if (
        doc.checked_out_by_id is not None
        and doc.checked_out_by_id != request.user.id
        and not is_tenant_admin_user(request.user)
    ):
        messages.error(
            request,
            f"Document {doc.number} is currently checked out by {doc.checked_out_by}.",
        )
        return redirect("assets:asset_document_detail", pk=doc.pk)

    if request.method == "POST":
        form = AssetDocumentForm(
            request.POST,
            request.FILES,
            instance=doc,
            tenant=request.tenant,
            user=request.user,
        )
        if form.is_valid():
            updated = form.save(commit=False)
            updated.is_current_revision = not bool(updated.supersedes_id)
            if updated.supersedes_id:
                updated.revision_sequence = max(
                    2, (updated.supersedes.revision_sequence or 1) + 1
                )
            else:
                updated.revision_sequence = 1
            updated.save()
            write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Updated document {updated.number}.")
            return redirect("assets:asset_document_detail", pk=updated.pk)
    else:
        form = AssetDocumentForm(instance=doc, tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/assetdocumentknowledge/asset_document/form.html",
        {
            "form": form,
            "document": doc,
            "is_edit": True,
            "title": f"Edit {doc.number}",
        },
    )


@login_required
@require_POST
@tenant_admin_required
def asset_document_delete(request, pk):
    """Delete an unlocked Draft / In-Review asset document."""
    doc = assets_object(
        request,
        AssetDocument,
        pk,
        queryset=assets_scope(AssetDocument.objects.all(), request).filter(
            readable_asset_document_q(request.user)
        ),
    )
    if doc.is_locked:
        messages.error(
            request,
            f"Cannot delete {doc.number} in status {doc.get_status_display()}. Archive it instead.",
        )
        return redirect("assets:asset_document_detail", pk=doc.pk)
    doc_number = doc.number
    write_audit_log(request.user, doc, "delete", tenant=request.tenant)
    doc.delete()
    messages.success(request, f"Deleted document {doc_number}.")
    return redirect("assets:asset_document_list")


@login_required
def asset_document_download(request, pk):
    """Download the controlled document attachment cleanly as an attachment with nosniff."""
    doc = assets_object(
        request,
        AssetDocument,
        pk,
        queryset=assets_scope(AssetDocument.objects.all(), request).filter(
            readable_asset_document_q(request.user)
        ),
    )
    return serve_protected_attachment(doc, file_attr="file", original_filename_attr="original_filename")


@login_required
@require_POST
def asset_document_submit_review(request, pk):
    """Transition a Draft document into In Review."""
    with transaction.atomic():
        doc = assets_object(
            request,
            AssetDocument,
            pk,
            queryset=assets_scope(AssetDocument.objects.all(), request)
            .filter(readable_asset_document_q(request.user))
            .select_for_update(),
        )
        if doc.status != "draft":
            messages.warning(
                request,
                f"Document {doc.number} must be in Draft status to submit for review.",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)
        if (
            doc.checked_out_by_id is not None
            and doc.checked_out_by_id != request.user.id
            and not is_tenant_admin_user(request.user)
        ):
            messages.error(
                request,
                f"Document {doc.number} is currently checked out by {doc.checked_out_by}.",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)
        doc.status = "in_review"
        doc.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, doc, "review", tenant=request.tenant)
    messages.success(request, f"Submitted {doc.number} for engineering review.")
    return redirect("assets:asset_document_detail", pk=doc.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_document_approve_release(request, pk):
    """Approve & release a document revision and atomically supersede its predecessor."""
    with transaction.atomic():
        doc = assets_object(
            request,
            AssetDocument,
            pk,
            queryset=assets_scope(AssetDocument.objects.all(), request)
            .filter(readable_asset_document_q(request.user))
            .select_for_update(),
        )
        if doc.status not in ("draft", "in_review"):
            messages.warning(
                request,
                f"Document {doc.number} cannot be approved from {doc.get_status_display()}.",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)
        if doc.checked_out_by_id is not None and doc.checked_out_by_id != request.user.id:
            messages.error(
                request,
                f"Document {doc.number} is currently checked out by {doc.checked_out_by}. Check it in before approving.",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)

        if doc.supersedes_id:
            prev = (
                AssetDocument.objects.select_for_update()
                .filter(tenant=request.tenant, pk=doc.supersedes_id)
                .first()
            )
            if prev is not None and prev.status != "archived":
                prev.status = "superseded"
                prev.is_current_revision = False
                prev.save(
                    update_fields=["status", "is_current_revision", "updated_at"]
                )

        doc.status = "approved"
        doc.is_current_revision = True
        doc.checked_out_by = None
        doc.checked_out_at = None
        doc.approved_by = request.user
        doc.approved_at = timezone.now()
        if doc.effective_date is None:
            doc.effective_date = timezone.localdate()
        doc.save(
            update_fields=[
                "status",
                "is_current_revision",
                "checked_out_by",
                "checked_out_at",
                "approved_by",
                "approved_at",
                "effective_date",
                "updated_at",
            ]
        )
        write_audit_log(request.user, doc, "approve", tenant=request.tenant)
    messages.success(request, f"Approved and released {doc.number} ({doc.revision_label}).")
    return redirect("assets:asset_document_detail", pk=doc.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_document_return_to_draft(request, pk):
    """Return an In-Review document back to Draft for revisions."""
    with transaction.atomic():
        doc = assets_object(
            request,
            AssetDocument,
            pk,
            queryset=assets_scope(AssetDocument.objects.all(), request)
            .filter(readable_asset_document_q(request.user))
            .select_for_update(),
        )
        if doc.status != "in_review":
            messages.warning(
                request,
                f"Only In Review documents can be returned to Draft ({doc.number}).",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)
        doc.status = "draft"
        doc.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, doc, "draft", tenant=request.tenant)
    messages.info(request, f"Returned {doc.number} to Draft.")
    return redirect("assets:asset_document_detail", pk=doc.pk)


@login_required
@require_POST
def asset_document_checkout(request, pk):
    """Acquire an advisory checkout lock on an editable document."""
    with transaction.atomic():
        doc = assets_object(
            request,
            AssetDocument,
            pk,
            queryset=assets_scope(AssetDocument.objects.all(), request)
            .filter(readable_asset_document_q(request.user))
            .select_for_update(),
        )
        if doc.is_locked:
            messages.warning(
                request,
                f"Document {doc.number} is {doc.get_status_display()} and cannot be checked out.",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)
        if doc.checked_out_by_id == request.user.id:
            messages.info(request, f"Document {doc.number} is already checked out by you.")
            return redirect("assets:asset_document_detail", pk=doc.pk)
        if doc.checked_out_by_id is not None:
            messages.error(
                request,
                f"Document {doc.number} is already checked out by {doc.checked_out_by}.",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)
        doc.checked_out_by = request.user
        doc.checked_out_at = timezone.now()
        doc.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
        write_audit_log(request.user, doc, "checkout", tenant=request.tenant)
    messages.success(request, f"Checked out {doc.number} for editing.")
    return redirect("assets:asset_document_detail", pk=doc.pk)


@login_required
@require_POST
def asset_document_checkin(request, pk):
    """Release an advisory checkout lock (checkout owner or tenant admin)."""
    with transaction.atomic():
        doc = assets_object(
            request,
            AssetDocument,
            pk,
            queryset=assets_scope(AssetDocument.objects.all(), request)
            .filter(readable_asset_document_q(request.user))
            .select_for_update(),
        )
        if doc.checked_out_by_id is None:
            messages.info(request, f"Document {doc.number} is not currently checked out.")
            return redirect("assets:asset_document_detail", pk=doc.pk)
        if doc.checked_out_by_id != request.user.id and not is_tenant_admin_user(
            request.user
        ):
            messages.error(
                request,
                f"Only {doc.checked_out_by} or a tenant administrator can check in {doc.number}.",
            )
            return redirect("assets:asset_document_detail", pk=doc.pk)
        doc.checked_out_by = None
        doc.checked_out_at = None
        doc.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
        write_audit_log(request.user, doc, "checkin", tenant=request.tenant)
    messages.success(request, f"Checked in {doc.number}.")
    return redirect("assets:asset_document_detail", pk=doc.pk)


@login_required
@require_POST
def asset_document_create_revision(request, pk):
    """Create a new Draft child revision superseding this document without losing the current approved issue."""
    with transaction.atomic():
        source = assets_object(
            request,
            AssetDocument,
            pk,
            queryset=assets_scope(AssetDocument.objects.all(), request)
            .filter(readable_asset_document_q(request.user))
            .select_for_update(),
        )
        if source.status == "archived":
            messages.warning(
                request,
                f"Archived document {source.number} cannot spawn a new revision.",
            )
            return redirect("assets:asset_document_detail", pk=source.pk)
        next_seq = (source.revision_sequence or 1) + 1
        new_rev = AssetDocument(
            tenant=request.tenant,
            title=source.title,
            document_class=source.document_class,
            access_classification=source.access_classification,
            tag_code=source.tag_code,
            manufacturer_ref=source.manufacturer_ref,
            document_language=source.document_language,
            storage_location_ref=source.storage_location_ref,
            revision_label=_next_revision_label(source.revision_label, next_seq),
            revision_sequence=next_seq,
            supersedes=source,
            is_current_revision=False,
            change_type=(
                "spec_update"
                if source.change_type == "new_issue"
                else source.change_type
            ),
            change_request_ref="",
            redline_summary="",
            spec_delta_notes="",
            expiry_date=source.expiry_date,
            retention_years=source.retention_years,
            status="draft",
            owner=request.user,
            reviewer=source.reviewer,
            description=source.description,
            org_unit=source.org_unit,
            operational_asset=source.operational_asset,
            fixed_asset=source.fixed_asset,
            asset_model=source.asset_model,
            asset_category=source.asset_category,
            specification_template=source.specification_template,
            warranty=source.warranty,
            compliance_framework=source.compliance_framework,
            vendor_party=source.vendor_party,
            core_document=source.core_document,
        )
        new_rev.save()
        write_audit_log(
            request.user,
            new_rev,
            "revise",
            changes={"supersedes": source.number},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Created draft revision {new_rev.number} ({new_rev.revision_label}) superseding {source.number}.",
    )
    return redirect("assets:asset_document_detail", pk=new_rev.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_document_archive(request, pk):
    """Archive a controlled document revision and release any checkout lock."""
    with transaction.atomic():
        doc = assets_object(
            request,
            AssetDocument,
            pk,
            queryset=assets_scope(AssetDocument.objects.all(), request)
            .filter(readable_asset_document_q(request.user))
            .select_for_update(),
        )
        if doc.status == "archived":
            messages.info(request, f"Document {doc.number} is already archived.")
            return redirect("assets:asset_document_detail", pk=doc.pk)
        doc.status = "archived"
        doc.is_current_revision = False
        doc.checked_out_by = None
        doc.checked_out_at = None
        doc.save(
            update_fields=[
                "status",
                "is_current_revision",
                "checked_out_by",
                "checked_out_at",
                "updated_at",
            ]
        )
        write_audit_log(request.user, doc, "archive", tenant=request.tenant)
    messages.success(request, f"Archived document {doc.number}.")
    return redirect("assets:asset_document_detail", pk=doc.pk)
