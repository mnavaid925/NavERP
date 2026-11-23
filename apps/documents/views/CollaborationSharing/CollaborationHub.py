from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.core.models import Employment
from apps.documents.models.CollaborationSharing.CoauthorSessions import CoauthorSession
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask
from apps.documents.views._common import documents_scope


@login_required
def collaboration_hub(request):
    """Central Collaboration Workspace unifying shared items, assigned tasks, active presence sessions, and live activity streams."""
    tenant = request.tenant
    user = request.user
    now = timezone.now()
    now_date = now.date()

    user_party = getattr(user, "party", None)
    employment = (
        Employment.objects.filter(tenant=tenant, party=user_party).order_by("-id").first()
        if user_party
        else None
    )
    user_org_unit = employment.org_unit if employment else None

    # 1. Shares targeting the current user
    shared_with_me_filter = Q(shared_with_user=user)
    if user_org_unit:
        shared_with_me_filter |= Q(shared_with_org_unit=user_org_unit)
    
    shared_with_me = DocumentShare.objects.filter(
        tenant=tenant,
        is_active=True,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).filter(
        shared_with_me_filter
    ).select_related("document", "folder", "shared_by").order_by("-created_at")

    # 2. Shares created by current user
    shared_by_me = DocumentShare.objects.filter(
        tenant=tenant,
        shared_by=user,
    ).select_related("document", "folder", "shared_with_user", "shared_with_org_unit").order_by("-created_at")

    # 3. Tasks assigned to current user
    my_tasks_filter = Q(assigned_to=user)
    if user_org_unit:
        my_tasks_filter |= Q(assigned_org_unit=user_org_unit)
    my_tasks = DocumentTask.objects.filter(
        tenant=tenant,
    ).filter(my_tasks_filter).exclude(status="cancelled").select_related("document", "assigned_by", "assigned_org_unit").order_by("due_date", "-created_at")

    # 4. Activity feed
    activity_feed = DocumentActivity.objects.filter(
        tenant=tenant,
    ).select_related("document", "actor", "target_user").order_by("-created_at")[:25]

    # 5. Active co-authoring sessions
    active_sessions = CoauthorSession.objects.filter(
        tenant=tenant,
        status="active",
    ).select_related("document", "user", "draft").order_by("-last_heartbeat")[:10]

    # KPI counts
    task_counts = my_tasks.aggregate(
        active=Count("id", filter=Q(status__in=["pending", "in_progress"])),
        overdue=Count("id", filter=~Q(status="completed") & Q(due_date__lt=now_date)),
    )
    stat_my_tasks_count = task_counts["active"]
    stat_overdue_tasks_count = task_counts["overdue"]
    stat_shares_by_me_count = shared_by_me.filter(is_active=True).count()
    stat_shares_with_me_count = shared_with_me.count()
    stat_unread_activities_count = DocumentActivity.objects.filter(
        tenant=tenant,
        target_user=user,
        is_read=False,
    ).count()

    active_tab = request.GET.get("tab", "shared_with_me").strip()
    if active_tab == "activity_feed":
        active_tab = "activity"
    if active_tab not in ("shared_with_me", "shared_by_me", "my_tasks", "activity"):
        active_tab = "shared_with_me"

    context = {
        "active_tab": active_tab,
        "shared_with_me": shared_with_me[:20],
        "shared_by_me": shared_by_me[:20],
        "my_tasks": my_tasks[:20],
        "activity_feed": activity_feed,
        "active_sessions": active_sessions,
        "stat_my_tasks_count": stat_my_tasks_count,
        "stat_overdue_tasks_count": stat_overdue_tasks_count,
        "stat_shares_by_me_count": stat_shares_by_me_count,
        "stat_shares_with_me_count": stat_shares_with_me_count,
        "stat_unread_activities_count": stat_unread_activities_count,
    }
    return render(request, "documents/collaboration_sharing/collaboration_hub.html", context)
