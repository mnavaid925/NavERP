from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.ApprovalWorkflow.DocumentReviewComments import (
    CommentReplyForm,
    CommentResolveForm,
    DocumentReviewCommentForm,
)
from apps.documents.models import DocumentReviewComment
from apps.documents.views._common import documents_object, documents_scope


@login_required
def review_comment_list(request):
    qs = documents_scope(
        DocumentReviewComment.objects.select_related("document", "version", "workflow", "author", "resolved_by"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(content__icontains=q)
            | Q(selected_text__icontains=q)
            | Q(number__icontains=q)
            | Q(document__title__icontains=q)
            | Q(author__username__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    ann_type = request.GET.get("annotation_type", "").strip()
    if ann_type:
        qs = qs.filter(annotation_type=ann_type)

    blocking = request.GET.get("is_blocking", "").strip()
    if blocking == "1":
        qs = qs.filter(is_blocking=True)
    elif blocking == "0":
        qs = qs.filter(is_blocking=False)

    wf_id = request.GET.get("workflow", "").strip()
    if wf_id and wf_id.isdigit():
        qs = qs.filter(workflow_id=int(wf_id))

    total_count = qs.count()
    open_blocking_count = DocumentReviewComment.objects.filter(
        tenant=request.tenant,
        is_blocking=True,
        status="open",
    ).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    comments = paginator.get_page(page_number)

    context = {
        "comments": comments,
        "status_choices": DocumentReviewComment.STATUS_CHOICES,
        "annotation_type_choices": DocumentReviewComment.ANNOTATION_TYPE_CHOICES,
        "status_css": DocumentReviewComment.STATUS_CSS,
        "annotation_type_css": DocumentReviewComment.ANNOTATION_TYPE_CSS,
        "open_blocking_count": open_blocking_count,
        "total_count": total_count,
    }
    return render(request, "documents/approval_workflow/document_review_comment/list.html", context)


@login_required
def review_comment_detail(request, pk):
    comment = documents_object(
        request,
        DocumentReviewComment,
        pk,
        select_related=("document", "version", "workflow", "author", "resolved_by", "parent"),
        prefetch_related=("replies__author",),
    )

    replies = comment.replies.all().order_by("created_at")

    context = {
        "comment": comment,
        "status_css": comment.status_css_class,
        "annotation_type_css": comment.annotation_type_css_class,
        "replies": replies,
        "reply_form": CommentReplyForm(),
        "resolve_form": CommentResolveForm(),
    }
    return render(request, "documents/approval_workflow/document_review_comment/detail.html", context)


@login_required
def review_comment_create(request):
    if request.method == "POST":
        form = DocumentReviewCommentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            comm = form.save(commit=False)
            comm.tenant = request.tenant
            comm.author = request.user
            comm.status = "open"
            comm.save()
            write_audit_log(request.user, comm, "create", tenant=request.tenant)
            messages.success(request, f"Review annotation {comm.number} added.")
            if comm.workflow:
                return redirect("documents:workflow_detail", pk=comm.workflow.pk)
            return redirect("documents:review_comment_detail", pk=comm.pk)
    else:
        initial = {}
        doc_id = request.GET.get("document")
        if doc_id and doc_id.isdigit():
            initial["document"] = doc_id
        wf_id = request.GET.get("workflow")
        if wf_id and wf_id.isdigit():
            initial["workflow"] = wf_id
        form = DocumentReviewCommentForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "comment": None,
        "is_edit": False,
    }
    return render(request, "documents/approval_workflow/document_review_comment/form.html", context)


@login_required
def review_comment_edit(request, pk):
    comment = documents_object(request, DocumentReviewComment, pk)
    if request.method == "POST":
        form = DocumentReviewCommentForm(request.POST, instance=comment, tenant=request.tenant)
        if form.is_valid():
            comment = form.save()
            write_audit_log(request.user, comment, "update", tenant=request.tenant)
            messages.success(request, f"Review comment {comment.number} updated.")
            return redirect("documents:review_comment_detail", pk=comment.pk)
    else:
        form = DocumentReviewCommentForm(instance=comment, tenant=request.tenant)

    context = {
        "form": form,
        "comment": comment,
        "is_edit": True,
    }
    return render(request, "documents/approval_workflow/document_review_comment/form.html", context)


@login_required
@require_POST
def review_comment_delete(request, pk):
    comment = documents_object(request, DocumentReviewComment, pk)
    number = comment.number
    wf = comment.workflow
    write_audit_log(request.user, comment, "delete", tenant=request.tenant)
    comment.delete()
    messages.success(request, f"Review comment {number} deleted.")
    if wf:
        return redirect("documents:workflow_detail", pk=wf.pk)
    return redirect("documents:review_comment_list")


@login_required
@require_POST
def review_comment_resolve(request, pk):
    comment = documents_object(request, DocumentReviewComment, pk)
    form = CommentResolveForm(request.POST)
    if form.is_valid():
        status = form.cleaned_data["status"]
        notes = form.cleaned_data["resolution_notes"]
        comment.status = status
        comment.resolution_notes = notes
        comment.resolved_by = request.user
        comment.resolved_at = timezone.now()
        comment.save(update_fields=["status", "resolution_notes", "resolved_by", "resolved_at", "updated_at"])
        write_audit_log(request.user, comment, "resolve", tenant=request.tenant)
        messages.success(request, f"Review comment {comment.number} marked as {comment.get_status_display()}.")
    else:
        messages.error(request, "Please provide valid resolution information.")
    return redirect("documents:review_comment_detail", pk=comment.pk)


@login_required
@require_POST
def review_comment_reply(request, pk):
    parent_comment = documents_object(request, DocumentReviewComment, pk)
    form = CommentReplyForm(request.POST)
    if form.is_valid():
        reply_content = form.cleaned_data["content"]
        reply = DocumentReviewComment.objects.create(
            tenant=request.tenant,
            document=parent_comment.document,
            version=parent_comment.version,
            workflow=parent_comment.workflow,
            author=request.user,
            annotation_type=parent_comment.annotation_type,
            page_number=parent_comment.page_number,
            content=reply_content,
            parent=parent_comment,
            status="open",
            is_blocking=False,
        )
        write_audit_log(request.user, reply, "create", tenant=request.tenant)
        messages.success(request, "Reply added to discussion thread.")
    else:
        messages.error(request, "Reply content cannot be empty.")
    return redirect("documents:review_comment_detail", pk=parent_comment.pk)
