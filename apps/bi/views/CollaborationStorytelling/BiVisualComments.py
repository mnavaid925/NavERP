from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.CollaborationStorytelling.BiVisualComments import BiVisualCommentForm
from apps.bi.models.CollaborationStorytelling.BiDataStories import BiDataStory
from apps.bi.models.CollaborationStorytelling.BiVisualComments import BiVisualComment
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def bi_visual_comment_list(request):
    qs = bi_scope(BiVisualComment.objects.all(), request).select_related(
        "dashboard", "widget", "report", "story", "author", "resolved_by", "parent_comment"
    )

    counts = qs.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status="open")),
        resolved=Count("id", filter=Q(status="resolved")),
    )
    total_count = counts["total"] or 0
    open_count = counts["open"] or 0
    resolved_count = counts["resolved"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(content__icontains=q)
            | Q(number__icontains=q)
            | Q(slide_id__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    target_type = request.GET.get("target_type", "").strip()
    if target_type:
        qs = qs.filter(target_type=target_type)

    priority = request.GET.get("priority", "").strip()
    if priority:
        qs = qs.filter(priority=priority)

    dashboard_id = request.GET.get("dashboard", "").strip()
    if dashboard_id and dashboard_id.isdigit():
        qs = qs.filter(dashboard_id=int(dashboard_id))

    story_id = request.GET.get("story", "").strip()
    if story_id and story_id.isdigit():
        qs = qs.filter(story_id=int(story_id))

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    dashboards = BiDashboard.objects.filter(tenant=request.tenant).order_by("title")
    stories = BiDataStory.objects.filter(tenant=request.tenant).order_by("title")

    context = {
        "comments": page_obj,
        "bi_visual_comments": page_obj,
        "total_count": total_count,
        "open_count": open_count,
        "resolved_count": resolved_count,
        "status_choices": BiVisualComment.STATUS_CHOICES,
        "target_type_choices": BiVisualComment.TARGET_TYPE_CHOICES,
        "priority_choices": BiVisualComment.PRIORITY_CHOICES,
        "dashboards": dashboards,
        "stories": stories,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bivisualcomment/list.html",
        context,
    )


@login_required
def bi_visual_comment_create(request):
    initial = {}
    d_id = request.GET.get("dashboard", "").strip()
    if d_id and d_id.isdigit():
        d = BiDashboard.objects.filter(tenant=request.tenant, pk=int(d_id)).first()
        if d:
            initial["dashboard"] = d
            initial["target_type"] = "dashboard"

    s_id = request.GET.get("story", "").strip()
    if s_id and s_id.isdigit():
        s = BiDataStory.objects.filter(tenant=request.tenant, pk=int(s_id)).first()
        if s:
            initial["story"] = s
            initial["target_type"] = "story"

    p_id = request.GET.get("parent", "").strip()
    if p_id and p_id.isdigit():
        p = BiVisualComment.objects.filter(tenant=request.tenant, pk=int(p_id)).first()
        if p:
            initial["parent_comment"] = p
            initial["target_type"] = p.target_type
            initial["dashboard"] = p.dashboard
            initial["story"] = p.story

    if request.method == "POST":
        form = BiVisualCommentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                comment = form.save(commit=False)
                comment.tenant = request.tenant
                comment.author = request.user
                comment.save()
                write_audit_log(
                    request.user,
                    comment,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(request, f"Comment '{comment.number}' posted successfully.")
            return redirect("bi:bi_visual_comment_detail", pk=comment.pk)
    else:
        form = BiVisualCommentForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bivisualcomment/form.html",
        {"form": form, "title": "Post New Visual Comment", "is_edit": False},
    )


@login_required
def bi_visual_comment_detail(request, pk):
    comment = bi_object(
        request,
        BiVisualComment,
        pk,
        select_related=("dashboard", "widget", "report", "story", "parent_comment", "author", "resolved_by"),
    )

    replies = comment.replies.select_related("author").order_by("created_at")

    context = {
        "comment": comment,
        "bi_visual_comment": comment,
        "obj": comment,
        "replies": replies,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bivisualcomment/detail.html",
        context,
    )


@login_required
def bi_visual_comment_edit(request, pk):
    comment = bi_object(request, BiVisualComment, pk)
    can_manage = (
        request.user == comment.author
        or request.user.is_superuser
        or getattr(request, "is_tenant_admin", False)
        or getattr(request.user, "is_tenant_admin", False)
    )
    if not can_manage:
        messages.error(request, "You can only edit your own comments.")
        return redirect("bi:bi_visual_comment_detail", pk=comment.pk)

    if request.method == "POST":
        form = BiVisualCommentForm(request.POST, instance=comment, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                comment = form.save()
                write_audit_log(
                    request.user,
                    comment,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(request, f"Comment '{comment.number}' updated successfully.")
            return redirect("bi:bi_visual_comment_detail", pk=comment.pk)
    else:
        form = BiVisualCommentForm(instance=comment, tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bivisualcomment/form.html",
        {
            "form": form,
            "title": f"Edit Comment: {comment.number}",
            "comment": comment,
            "bi_visual_comment": comment,
            "obj": comment,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def bi_visual_comment_delete(request, pk):
    comment = bi_object(request, BiVisualComment, pk)
    can_manage = (
        request.user == comment.author
        or request.user.is_superuser
        or getattr(request, "is_tenant_admin", False)
        or getattr(request.user, "is_tenant_admin", False)
    )
    if not can_manage:
        messages.error(request, "You can only delete your own comments.")
        return redirect("bi:bi_visual_comment_detail", pk=comment.pk)

    number = comment.number
    with transaction.atomic():
        write_audit_log(
            request.user,
            comment,
            "delete",
            tenant=request.tenant,
        )
        comment.delete()
    messages.success(request, f"Comment '{number}' deleted successfully.")
    return redirect("bi:bi_visual_comment_list")


@login_required
@require_POST
def bi_visual_comment_resolve(request, pk):
    comment = bi_object(request, BiVisualComment, pk)
    with transaction.atomic():
        comment.mark_resolved(request.user)
        write_audit_log(
            request.user,
            comment,
            "update",
            changes={"status": "resolved"},
            tenant=request.tenant,
        )
    messages.success(request, f"Comment '{comment.number}' marked as resolved.")
    return redirect("bi:bi_visual_comment_detail", pk=comment.pk)
