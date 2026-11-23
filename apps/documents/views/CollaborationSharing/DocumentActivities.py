from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.CollaborationSharing.DocumentActivities import DocumentActivityForm
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_activity_list(request):
    base_qs = documents_scope(DocumentActivity.objects.all(), request).select_related(
        "document", "actor", "target_user"
    )

    total_count = base_qs.count()
    unread_count = base_qs.filter(target_user=request.user, is_read=False).count()

    qs = base_qs
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(summary__icontains=q)
            | Q(document__title__icontains=q)
            | Q(actor__username__icontains=q)
            | Q(actor__first_name__icontains=q)
            | Q(guest_name__icontains=q)
        )

    current_action_type = request.GET.get("action_type", "").strip()
    if current_action_type:
        qs = qs.filter(action_type=current_action_type)

    current_filter = request.GET.get("filter", "all").strip()
    if current_filter == "unread":
        qs = qs.filter(target_user=request.user, is_read=False)
    elif current_filter == "targeted":
        qs = qs.filter(target_user=request.user)
    elif current_filter == "my_actions":
        qs = qs.filter(actor=request.user)

    doc_id = request.GET.get("document", "").strip()
    if doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "activities": page_obj.object_list,
        "action_type_choices": DocumentActivity.ACTION_TYPE_CHOICES,
        "total_count": total_count,
        "unread_count": unread_count,
        "q": q,
        "current_action_type": current_action_type,
        "current_filter": current_filter,
    }
    return render(request, "documents/collaboration_sharing/document_activity/list.html", context)


@login_required
def document_activity_detail(request, pk):
    activity = documents_object(
        request,
        DocumentActivity,
        pk,
        select_related=["document", "actor", "target_user"],
    )
    if activity.target_user == request.user and not activity.is_read:
        activity.mark_as_read()

    context = {
        "activity": activity,
    }
    return render(request, "documents/collaboration_sharing/document_activity/detail.html", context)


@login_required
@require_POST
def document_activity_mark_read(request, pk):
    activity = get_object_or_404(
        DocumentActivity.objects.filter(tenant=request.tenant, target_user=request.user),
        pk=pk,
    )
    activity.mark_as_read()
    messages.success(request, f"Activity {activity.number} marked as read.")
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect("documents:document_activity_list")


@login_required
@require_POST
def document_activity_mark_all_read(request):
    unread_qs = DocumentActivity.objects.filter(
        tenant=request.tenant,
        target_user=request.user,
        is_read=False,
    )
    count = unread_qs.update(is_read=True, read_at=timezone.now(), updated_at=timezone.now())
    messages.success(request, f"Marked {count} activity notifications as read.")
    return redirect("documents:document_activity_list")
