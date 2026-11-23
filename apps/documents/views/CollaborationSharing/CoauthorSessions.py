import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.CollaborationSharing.CoauthorSessions import CoauthorSessionForm
from apps.documents.models.CollaborationSharing.CoauthorSessions import CoauthorSession
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.views._common import documents_object, documents_scope


@login_required
def coauthor_session_list(request):
    base_qs = documents_scope(CoauthorSession.objects.all(), request).select_related(
        "document", "user", "draft", "version"
    )

    counts = base_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        idle=Count("id", filter=Q(status="idle")),
        disconnected=Count("id", filter=Q(status="disconnected")),
    )
    total_count = counts["total"]
    active_count = counts["active"]
    idle_count = counts["idle"]
    disconnected_count = counts["disconnected"]

    qs = base_qs
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(document__title__icontains=q)
            | Q(guest_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(current_section__icontains=q)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    doc_id = request.GET.get("document", "").strip()
    if doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "sessions": page_obj.object_list,
        "status_choices": CoauthorSession.STATUS_CHOICES,
        "total_count": total_count,
        "active_count": active_count,
        "idle_count": idle_count,
        "disconnected_count": disconnected_count,
        "q": q,
        "current_status": current_status,
    }
    return render(request, "documents/collaboration_sharing/coauthor_session/list.html", context)


@login_required
def coauthor_session_detail(request, pk):
    session = documents_object(
        request,
        CoauthorSession,
        pk,
        select_related=["document", "version", "draft", "user"],
    )
    context = {
        "session": session,
    }
    return render(request, "documents/collaboration_sharing/coauthor_session/detail.html", context)


@login_required
def coauthor_session_create(request):
    if request.method == "POST":
        form = CoauthorSessionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            session = form.save(commit=False)
            session.tenant = request.tenant
            session.save()
            form.save_m2m()
            write_audit_log(request.user, session, "create", tenant=request.tenant)

            DocumentActivity.objects.create(
                tenant=request.tenant,
                document=session.document,
                actor=request.user,
                action_type="coauthor_joined",
                summary=f"Collaborator '{session.display_name}' joined coauthoring session on '{session.document.title}'",
                notification_channel="in_app",
            )

            messages.success(request, f"Co-authoring session {session.number} created successfully.")
            return redirect("documents:coauthor_session_detail", pk=session.pk)
    else:
        initial = {}
        doc_id = request.GET.get("document")
        if doc_id and doc_id.isdigit():
            initial["document"] = int(doc_id)
        form = CoauthorSessionForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "session": None,
        "is_edit": False,
    }
    return render(request, "documents/collaboration_sharing/coauthor_session/form.html", context)


def _can_manage_coauthor_session(user, session):
    if getattr(user, "is_tenant_admin", False) or user.is_superuser:
        return True
    if session.user_id == user.id:
        return True
    if session.document and getattr(session.document, "owner_id", None) == user.id:
        return True
    return False


@login_required
def coauthor_session_edit(request, pk):
    session = documents_object(request, CoauthorSession, pk, select_related=["document"])
    if not _can_manage_coauthor_session(request.user, session):
        messages.error(request, "You do not have permission to edit this co-authoring session.")
        return redirect("documents:coauthor_session_detail", pk=session.pk)
    if request.method == "POST":
        form = CoauthorSessionForm(request.POST, instance=session, tenant=request.tenant)
        if form.is_valid():
            session = form.save()
            write_audit_log(request.user, session, "update", tenant=request.tenant)
            messages.success(request, f"Co-authoring session {session.number} updated successfully.")
            return redirect("documents:coauthor_session_detail", pk=session.pk)
    else:
        form = CoauthorSessionForm(instance=session, tenant=request.tenant)

    context = {
        "form": form,
        "session": session,
        "is_edit": True,
    }
    return render(request, "documents/collaboration_sharing/coauthor_session/form.html", context)


@login_required
@require_POST
def coauthor_session_delete(request, pk):
    session = documents_object(request, CoauthorSession, pk, select_related=["document"])
    if not _can_manage_coauthor_session(request.user, session):
        messages.error(request, "You do not have permission to delete this co-authoring session.")
        return redirect("documents:coauthor_session_detail", pk=session.pk)
    session_num = session.number
    write_audit_log(request.user, session, "delete", tenant=request.tenant)
    session.delete()
    messages.success(request, f"Co-authoring session {session_num} deleted successfully.")
    return redirect("documents:coauthor_session_list")


@login_required
@require_POST
def coauthor_session_heartbeat(request, session_token):
    session = get_object_or_404(
        CoauthorSession.objects.filter(tenant=request.tenant),
        session_token=session_token,
    )
    cursor_data = request.POST.get("cursor_position")
    section = request.POST.get("current_section")
    is_editing = request.POST.get("is_editing")

    if cursor_data:
        try:
            cursor_data = json.loads(cursor_data)
        except (TypeError, ValueError):
            cursor_data = None

    session.heartbeat(cursor_data=cursor_data, section=section, is_editing=is_editing)
    return JsonResponse({
        "status": "ok",
        "session_status": session.status,
        "last_heartbeat": session.last_heartbeat.isoformat(),
    })
