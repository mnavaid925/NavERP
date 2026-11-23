from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.CollaborationSharing.DocumentTasks import DocumentTaskForm
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_task_list(request):
    base_qs = documents_scope(DocumentTask.objects.all(), request).select_related(
        "document", "assigned_to", "assigned_by", "assigned_org_unit", "review_comment"
    )

    now_date = timezone.now().date()
    total_count = base_qs.count()
    pending_count = base_qs.filter(status="pending").count()
    in_progress_count = base_qs.filter(status="in_progress").count()
    completed_count = base_qs.filter(status="completed").count()
    overdue_count = base_qs.exclude(status__in=["completed", "cancelled"]).filter(due_date__lt=now_date).count()

    qs = base_qs
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(document__title__icontains=q)
            | Q(assigned_to__username__icontains=q)
            | Q(assigned_to__first_name__icontains=q)
        )

    current_task_type = request.GET.get("task_type", "").strip()
    if current_task_type:
        qs = qs.filter(task_type=current_task_type)

    current_priority = request.GET.get("priority", "").strip()
    if current_priority:
        qs = qs.filter(priority=current_priority)

    current_status = request.GET.get("status", "").strip()
    if current_status == "overdue":
        qs = qs.exclude(status__in=["completed", "cancelled"]).filter(due_date__lt=now_date)
    elif current_status:
        qs = qs.filter(status=current_status)

    assigned_to_filter = request.GET.get("assigned_to", "").strip()
    if assigned_to_filter == "me":
        qs = qs.filter(assigned_to=request.user)
    elif assigned_to_filter.isdigit():
        qs = qs.filter(assigned_to_id=int(assigned_to_filter))

    doc_id = request.GET.get("document", "").strip()
    if doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    user_model = get_user_model()
    users = user_model.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "username")

    context = {
        "page_obj": page_obj,
        "tasks": page_obj.object_list,
        "task_type_choices": DocumentTask.TASK_TYPE_CHOICES,
        "priority_choices": DocumentTask.PRIORITY_CHOICES,
        "status_choices": DocumentTask.STATUS_CHOICES,
        "total_count": total_count,
        "pending_count": pending_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
        "overdue_count": overdue_count,
        "q": q,
        "current_task_type": current_task_type,
        "current_priority": current_priority,
        "current_status": current_status,
        "assigned_to_filter": assigned_to_filter,
        "users": users,
    }
    return render(request, "documents/collaboration_sharing/document_task/list.html", context)


@login_required
def document_task_detail(request, pk):
    task = documents_object(
        request,
        DocumentTask,
        pk,
        select_related=["document", "version", "review_comment", "review_comment__author", "assigned_to", "assigned_by", "assigned_org_unit", "completed_by"],
    )
    context = {
        "task": task,
    }
    return render(request, "documents/collaboration_sharing/document_task/detail.html", context)


@login_required
def document_task_create(request):
    if request.method == "POST":
        form = DocumentTaskForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.tenant = request.tenant
            task.save()
            form.save_m2m()
            write_audit_log(request.user, task, "create", tenant=request.tenant)

            DocumentActivity.objects.create(
                tenant=request.tenant,
                document=task.document,
                actor=request.user,
                target_user=task.assigned_to,
                action_type="task_assigned",
                summary=f"Task '{task.title}' assigned to {task.assigned_to.get_full_name() if task.assigned_to else 'team'}",
                notification_channel="in_app",
            )

            messages.success(request, f"Document task {task.number} created successfully.")
            return redirect("documents:document_task_detail", pk=task.pk)
    else:
        initial = {}
        doc_id = request.GET.get("document")
        if doc_id and doc_id.isdigit():
            initial["document"] = int(doc_id)
        comment_id = request.GET.get("review_comment")
        if comment_id and comment_id.isdigit():
            initial["review_comment"] = int(comment_id)
        form = DocumentTaskForm(initial=initial, tenant=request.tenant, user=request.user)

    context = {
        "form": form,
        "task": None,
        "is_edit": False,
    }
    return render(request, "documents/collaboration_sharing/document_task/form.html", context)


@login_required
def document_task_edit(request, pk):
    task = documents_object(request, DocumentTask, pk)
    if request.method == "POST":
        form = DocumentTaskForm(request.POST, instance=task, tenant=request.tenant, user=request.user)
        if form.is_valid():
            task = form.save()
            write_audit_log(request.user, task, "update", tenant=request.tenant)
            messages.success(request, f"Document task {task.number} updated successfully.")
            return redirect("documents:document_task_detail", pk=task.pk)
    else:
        form = DocumentTaskForm(instance=task, tenant=request.tenant, user=request.user)

    context = {
        "form": form,
        "task": task,
        "is_edit": True,
    }
    return render(request, "documents/collaboration_sharing/document_task/form.html", context)


@login_required
@require_POST
def document_task_delete(request, pk):
    task = documents_object(request, DocumentTask, pk)
    task_num = task.number
    write_audit_log(request.user, task, "delete", tenant=request.tenant)
    task.delete()
    messages.success(request, f"Document task {task_num} deleted successfully.")
    return redirect("documents:document_task_list")


@login_required
@require_POST
def document_task_toggle_complete(request, pk):
    task = documents_object(request, DocumentTask, pk)
    if task.status == "completed":
        task.reopen()
        write_audit_log(request.user, task, "update", tenant=request.tenant)
        messages.info(request, f"Task {task.number} reopened.")
    else:
        notes = request.POST.get("completion_notes", "").strip()
        task.complete(user=request.user, notes=notes)
        write_audit_log(request.user, task, "complete", tenant=request.tenant)

        DocumentActivity.objects.create(
            tenant=request.tenant,
            document=task.document,
            actor=request.user,
            target_user=task.assigned_by,
            action_type="task_completed",
            summary=f"Task '{task.title}' was completed by {request.user.get_full_name() or request.user.username}",
            notification_channel="in_app",
        )
        messages.success(request, f"Task {task.number} marked as completed.")

    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect("documents:document_task_detail", pk=task.pk)
