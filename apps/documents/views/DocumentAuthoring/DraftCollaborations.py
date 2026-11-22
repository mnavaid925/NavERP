from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.DocumentAuthoring.DraftCollaborations import DraftCollaborationForm
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.views._common import documents_object, documents_scope
from apps.documents.views._helpers import count_words


@login_required
def collaboration_list(request):
    qs = documents_scope(DraftCollaboration.objects.select_related("draft", "author", "resolved_by"), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(comment_text__icontains=q) | Q(selected_text__icontains=q) | Q(number__icontains=q))

    entry_type = request.GET.get("entry_type", "").strip()
    if entry_type:
        qs = qs.filter(entry_type=entry_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    total_count = qs.count()
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "documents/document_authoring/draft_collaboration/list.html",
        {
            "collaborations": page_obj,
            "page_obj": page_obj,
            "search_query": q,
            "entry_type_choices": DraftCollaboration.ENTRY_TYPE_CHOICES,
            "status_choices": DraftCollaboration.STATUS_CHOICES,
            "total_count": total_count,
        },
    )


@login_required
def collaboration_detail(request, pk):
    collaboration = documents_object(
        request,
        DraftCollaboration,
        pk,
        select_related=("draft", "author", "resolved_by"),
    )
    return render(
        request,
        "documents/document_authoring/draft_collaboration/detail.html",
        {
            "collaboration": collaboration,
        },
    )


@login_required
def collaboration_create(request, draft_pk):
    draft = documents_object(request, DocumentDraft, draft_pk)
    if request.method == "POST":
        form = DraftCollaborationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                collab = form.save(commit=False)
                collab.tenant = request.tenant
                collab.draft = draft
                collab.author = request.user
                collab.status = "open"
                collab.save()
                write_audit_log(request.user, collab, "create", tenant=request.tenant)
            messages.success(request, f"Collaboration feedback #{collab.number} recorded.")
            return redirect("documents:draft_detail", pk=draft.pk)
    else:
        initial = {}
        sel = request.GET.get("selected_text")
        if sel:
            initial["selected_text"] = sel
        anchor = request.GET.get("section_anchor")
        if anchor:
            initial["section_anchor"] = anchor
        form = DraftCollaborationForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/draft_collaboration/form.html",
        {
            "form": form,
            "draft": draft,
            "is_edit": False,
        },
    )


@login_required
def collaboration_edit(request, pk):
    collaboration = documents_object(request, DraftCollaboration, pk, select_related=("draft",))
    if collaboration.author_id != request.user.id and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request, "is_tenant_admin", False)):
        messages.error(request, "You do not have permission to modify this collaboration feedback.")
        return redirect("documents:draft_detail", pk=collaboration.draft_id)

    if request.method == "POST":
        form = DraftCollaborationForm(request.POST, instance=collaboration, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                collab = form.save()
                write_audit_log(request.user, collab, "edit", tenant=request.tenant)
            messages.success(request, f"Collaboration feedback #{collab.number} updated.")
            return redirect("documents:draft_detail", pk=collab.draft_id)
    else:
        form = DraftCollaborationForm(instance=collaboration, tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/draft_collaboration/form.html",
        {
            "form": form,
            "draft": collaboration.draft,
            "collaboration": collaboration,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def collaboration_delete(request, pk):
    collaboration = documents_object(request, DraftCollaboration, pk)
    draft_pk = collaboration.draft_id
    with transaction.atomic():
        write_audit_log(request.user, collaboration, "delete", tenant=request.tenant)
        collaboration.delete()
    messages.success(request, "Collaboration comment removed.")
    return redirect("documents:draft_detail", pk=draft_pk)


@login_required
@require_POST
def collaboration_resolve(request, pk):
    collaboration = documents_object(request, DraftCollaboration, pk, select_related=("draft",))
    action = request.POST.get("action", "resolve")
    draft = collaboration.draft

    if collaboration.status != "open":
        messages.warning(request, f"Collaboration feedback is already {collaboration.get_status_display().lower()}.")
        return redirect("documents:draft_detail", pk=draft.pk)

    if action not in ("accept", "reject", "resolve"):
        messages.error(request, "Invalid resolution action.")
        return redirect("documents:draft_detail", pk=draft.pk)

    with transaction.atomic():
        if action == "accept":
            collaboration.status = "accepted"
            # Apply replacement text if present and exact match in draft body
            if collaboration.selected_text and collaboration.replacement_text and collaboration.selected_text in draft.content:
                draft.content = draft.content.replace(collaboration.selected_text, collaboration.replacement_text, 1)
                draft.word_count = count_words(draft.content)
                draft.save(update_fields=["content", "word_count", "updated_at"])
        elif action == "reject":
            collaboration.status = "rejected"
        else:
            collaboration.status = "resolved"

        collaboration.resolved_by = request.user
        collaboration.resolved_at = timezone.now()
        collaboration.save()
        write_audit_log(request.user, collaboration, f"resolve_{action}", tenant=request.tenant)

    messages.success(request, f"Collaboration feedback marked as {collaboration.get_status_display()}.")
    return redirect("documents:draft_detail", pk=draft.pk)
