from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import Document
from apps.core.utils import write_audit_log
from apps.documents.forms.DocumentAuthoring.DocumentDrafts import DocumentDraftForm
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.views._common import documents_object, documents_scope
from apps.documents.views._helpers import compute_text_diff, count_words, substitute_tokens


@login_required
def draft_list(request):
    qs = documents_scope(DocumentDraft.objects.select_related("template", "author", "department"), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q) | Q(content__icontains=q))

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    document_type = request.GET.get("document_type", "").strip()
    if document_type:
        qs = qs.filter(document_type=document_type)

    sync_status = request.GET.get("sync_status", "").strip()
    if sync_status:
        qs = qs.filter(sync_status=sync_status)

    total_count = qs.count()
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "documents/document_authoring/document_draft/list.html",
        {
            "drafts": page_obj,
            "page_obj": page_obj,
            "search_query": q,
            "status_choices": DocumentDraft.DRAFT_STATUS_CHOICES,
            "document_type_choices": DocumentDraft.DOCUMENT_TYPE_CHOICES,
            "sync_status_choices": DocumentDraft.SYNC_STATUS_CHOICES,
            "total_count": total_count,
        },
    )


@login_required
def draft_detail(request, pk):
    draft = documents_object(
        request,
        DocumentDraft,
        pk,
        select_related=("template", "author", "department", "related_party", "promoted_document"),
        prefetch_related=("collaborations", "collaborations__author"),
    )
    collaborations = draft.collaborations.all().order_by("-created_at")

    return render(
        request,
        "documents/document_authoring/document_draft/detail.html",
        {
            "draft": draft,
            "collaborations": collaborations,
        },
    )


@login_required
def draft_create(request):
    if request.method == "POST":
        form = DocumentDraftForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                draft = form.save(commit=False)
                draft.tenant = request.tenant
                draft.author = request.user
                draft.word_count = count_words(draft.content)
                draft.save()
                form.save_m2m()
                write_audit_log(request.user, draft, "create", tenant=request.tenant)
            messages.success(request, f"Document draft '{draft.title}' created successfully.")
            return redirect("documents:draft_detail", pk=draft.pk)
    else:
        form = DocumentDraftForm(tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/document_draft/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def draft_edit(request, pk):
    draft = documents_object(request, DocumentDraft, pk)
    if request.method == "POST":
        form = DocumentDraftForm(request.POST, instance=draft, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                draft = form.save(commit=False)
                draft.word_count = count_words(draft.content)
                draft.save()
                form.save_m2m()
                write_audit_log(request.user, draft, "edit", tenant=request.tenant)
            messages.success(request, f"Document draft '{draft.title}' updated successfully.")
            return redirect("documents:draft_detail", pk=draft.pk)
    else:
        form = DocumentDraftForm(instance=draft, tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/document_draft/form.html",
        {
            "form": form,
            "draft": draft,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def draft_delete(request, pk):
    draft = documents_object(request, DocumentDraft, pk)
    title = draft.title
    with transaction.atomic():
        write_audit_log(request.user, draft, "delete", tenant=request.tenant)
        draft.delete()
    messages.success(request, f"Document draft '{title}' deleted successfully.")
    return redirect("documents:draft_list")


@login_required
def draft_canvas(request, pk):
    draft = documents_object(
        request,
        DocumentDraft,
        pk,
        select_related=("template", "author", "department"),
        prefetch_related=("collaborations", "collaborations__author"),
    )
    collaborations = [c for c in draft.collaborations.all() if c.status == "open"]
    available_tokens = draft.template.available_tokens if draft.template else {}

    return render(
        request,
        "documents/document_authoring/document_draft/canvas.html",
        {
            "draft": draft,
            "collaborations": collaborations,
            "available_tokens": available_tokens,
        },
    )


@login_required
@require_POST
def draft_autosave(request, pk):
    draft = documents_object(request, DocumentDraft, pk)
    content = request.POST.get("content", "")
    with transaction.atomic():
        draft.content = content
        draft.auto_save_timestamp = timezone.now()
        draft.word_count = count_words(content)
        draft.save(update_fields=["content", "auto_save_timestamp", "word_count", "updated_at"])
    return JsonResponse(
        {
            "status": "saved",
            "word_count": draft.word_count,
            "saved_at": draft.auto_save_timestamp.strftime("%H:%M:%S"),
        }
    )


@login_required
def draft_compare(request, pk):
    draft = documents_object(request, DocumentDraft, pk, select_related=("template",))
    template = draft.template
    has_template = template is not None
    diff_lines = []
    if has_template and template.content:
        diff_lines = compute_text_diff(template.content, draft.content)

    return render(
        request,
        "documents/document_authoring/document_draft/compare.html",
        {
            "draft": draft,
            "template": template,
            "has_template": has_template,
            "diff_lines": diff_lines,
        },
    )


@login_required
def draft_resolve_conflict(request, pk):
    draft = documents_object(request, DocumentDraft, pk)
    if request.method == "POST":
        resolved_content = request.POST.get("resolved_content", "")
        with transaction.atomic():
            draft.content = resolved_content
            draft.sync_status = "resolved"
            draft.word_count = count_words(resolved_content)
            draft.save()
            write_audit_log(request.user, draft, "edit", tenant=request.tenant)
        messages.success(request, f"Sync conflict on '{draft.title}' resolved successfully.")
        return redirect("documents:draft_detail", pk=draft.pk)

    return render(
        request,
        "documents/document_authoring/document_draft/conflict_resolution.html",
        {
            "draft": draft,
        },
    )


@login_required
@require_POST
def draft_promote(request, pk):
    draft = documents_object(request, DocumentDraft, pk)
    if draft.status == "promoted":
        messages.warning(request, f"Draft '{draft.title}' has already been promoted to an official document.")
        return redirect("documents:draft_detail", pk=draft.pk)
    if draft.status == "discarded":
        messages.error(request, f"Discarded draft '{draft.title}' cannot be promoted.")
        return redirect("documents:draft_detail", pk=draft.pk)
    if draft.sync_status == "conflict_pending":
        messages.error(request, f"Draft '{draft.title}' has unresolved sync conflicts and cannot be promoted.")
        return redirect("documents:draft_detail", pk=draft.pk)

    with transaction.atomic():
        # Create or link core.Document
        doc = Document.objects.create(
            tenant=request.tenant,
            name=draft.title,
            file=ContentFile((draft.content or "").encode("utf-8"), name=f"{draft.number}.html"),
            classification="internal",
            version="1.0",
        )
        draft.status = "promoted"
        draft.promoted_at = timezone.now()
        draft.promoted_version = "1.0"
        draft.promoted_document = doc
        draft.save()
        write_audit_log(request.user, draft, "promote", tenant=request.tenant)

    messages.success(request, f"Draft '{draft.title}' successfully promoted to official Document Version 1.0.")
    return redirect("documents:draft_detail", pk=draft.pk)
