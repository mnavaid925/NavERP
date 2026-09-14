"""Projects 7.9 — the merged activity feed (bullet 5: "Activity Streams & Feeds").

One GET-only page, no model — the ``task_board`` / ``gantt_timeline`` / ``risk_analysis``
precedent. It merges the four 7.9 registers with the tenant's ``core.AuditLog`` trail into one
reverse-chronological stream: "chronological project updates, audit trails" from the bullet.

**Why the audit half is dropped when a project lens is on.** ``core.AuditLog`` stores only a GFK
(``content_type``/``object_id``) and a free-text ``target``. It cannot be attributed to a project
without a join per row type, and inferring it from ``target`` would be a fabricated attribution —
worse than an omission, because the reader cannot tell it is wrong. So a project-filtered feed is
the four collaboration sources, and the page says so out loud rather than quietly showing fewer
rows than the user asked for.

**Bounded work.** Each source is counted with one ``COUNT`` (the figures are exact and pre-cap)
and then fetched with its own ``_SOURCE_CAP`` slice, so a tenant with a decade of history still
costs ten queries. The merged list is truncated to ``_FEED_CAP``.

**Filter params — exactly three.** ``?project=`` (``as_db_int``, degrading to the unfiltered feed
with a warning), ``?kind=`` (allow-listed against ``_FEED_KINDS``) and ``?days=`` (allow-listed
against the three window choices). Every one is L11/L35-guarded: a junk value is IGNORED, never a
500 and never a silently emptied page.
"""
from datetime import timedelta

from django.urls import reverse

from apps.core.crud import as_db_int
from apps.core.models import AuditLog
from apps.projects.models import (ChannelMessage, DocumentShare, Meeting, Project,
                                 ProjectNotification)
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, messages, render, timezone
from apps.projects.views._helpers import projects

_FEED_KINDS = [
    ("message", "Channel Message"),
    ("meeting", "Meeting"),
    ("share", "Document Share"),
    ("notification", "Notification"),
    ("audit", "Audit Trail"),
]
_WINDOW_CHOICES = [(7, "Last 7 days"), (30, "Last 30 days"), (90, "Last 90 days")]
_DEFAULT_DAYS = 30
_FEED_CAP = 100      # entries rendered
_SOURCE_CAP = 100    # rows fetched per source before the merge

#: Colour-named badge classes ONLY (L33) — the semantic -success/-warning/-danger variants do not
#: exist in theme.css and render unstyled.
_KIND_BADGES = {
    "message": "badge-info",
    "meeting": "badge-green",
    "share": "badge-amber",
    "notification": "badge-muted",
    "audit": "badge-slate",
}

_KIND_VALUES = {value for value, _ in _FEED_KINDS}
_WINDOW_VALUES = {value for value, _ in _WINDOW_CHOICES}
_KIND_LABELS = dict(_FEED_KINDS)


@login_required
def activity_feed(request):
    tenant = request.tenant

    project = None
    project_id = as_db_int(request.GET.get("project", ""))
    if project_id is not None:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()
        if project is None:
            # A well-formed id that is not in this workspace degrades to the whole-workspace feed
            # — but it says so, rather than silently showing rows the user did not ask for.
            messages.warning(
                request,
                "That project is not in this workspace — showing the whole workspace feed.")

    kind = (request.GET.get("kind") or "").strip()
    if kind not in _KIND_VALUES:
        kind = ""
    days = as_db_int(request.GET.get("days", ""))
    if days not in _WINDOW_VALUES:
        days = _DEFAULT_DAYS

    since = timezone.now() - timedelta(days=days)
    want = {kind} if kind else set(_KIND_VALUES)
    entries = []

    # Every source's window queryset, built once. The COUNTS are exact pre-cap figures for all
    # five kinds — the stat row summarises the WINDOW, so `?kind=` narrows the STREAM, not the
    # summary (otherwise picking one kind would zero the other four cards). Only the fetch loop
    # is gated by `want`. Each source is a real DB LIMIT (the queryset is unevaluated when
    # sliced), so a decade of history still costs the same.
    message_qs = ChannelMessage.objects.filter(tenant=tenant, created_at__gte=since)
    meeting_qs = Meeting.objects.filter(tenant=tenant, created_at__gte=since)
    share_qs = DocumentShare.objects.filter(tenant=tenant, created_at__gte=since)
    notification_qs = ProjectNotification.objects.filter(tenant=tenant, created_at__gte=since)
    if project is not None:
        message_qs = message_qs.filter(channel__project_id=project.pk)
        meeting_qs = meeting_qs.filter(project_id=project.pk)
        share_qs = share_qs.filter(project_id=project.pk)
        notification_qs = notification_qs.filter(project_id=project.pk)
    # The audit trail — None under a project lens, because it cannot be attributed to one (see
    # the module docstring); that is the ONE pinned zeroing rule.
    audit_qs = (None if project is not None
                else AuditLog.objects.filter(tenant=tenant, at__gte=since))

    counts = {
        "message": message_qs.count(),
        "meeting": meeting_qs.count(),
        "share": share_qs.count(),
        "notification": notification_qs.count(),
        "audit": 0 if audit_qs is None else audit_qs.count(),
    }

    if "message" in want:
        rows = (message_qs.select_related("channel", "channel__project", "created_by")
                .order_by("-created_at", "-id")[:_SOURCE_CAP])
        for row in rows:
            entries.append({
                "at": row.created_at, "kind": "message", "actor": row.created_by,
                "project": row.channel.project,
                "label": f"{row.number} in {row.channel.name}",
                "detail": row.body[:160],
                "url": reverse("projects:chn_detail", args=[row.channel_id]),
            })

    if "meeting" in want:
        rows = (meeting_qs.select_related("project", "created_by")
                .order_by("-created_at", "-id")[:_SOURCE_CAP])
        for row in rows:
            entries.append({
                "at": row.created_at, "kind": "meeting", "actor": row.created_by,
                "project": row.project, "label": row.title,
                "detail": f"{row.get_kind_display()} · {row.get_status_display()}",
                "url": reverse("projects:mtg_detail", args=[row.pk]),
            })

    if "share" in want:
        rows = (share_qs.select_related("project", "document", "created_by")
                .order_by("-created_at", "-id")[:_SOURCE_CAP])
        for row in rows:
            entries.append({
                "at": row.created_at, "kind": "share", "actor": row.created_by,
                "project": row.project, "label": row.document.name,
                "detail": f"{row.get_access_level_display()} · v{row.document.version}",
                "url": reverse("projects:dsh_detail", args=[row.pk]),
            })

    if "notification" in want:
        rows = (notification_qs.select_related("project", "recipient", "triggered_by")
                .order_by("-created_at", "-id")[:_SOURCE_CAP])
        for row in rows:
            entries.append({
                "at": row.created_at, "kind": "notification", "actor": row.triggered_by,
                "project": row.project, "label": row.title,
                "detail": f"{row.get_kind_display()} → {row.recipient}",
                "url": reverse("projects:ntf_detail", args=[row.pk]),
            })

    if "audit" in want and audit_qs is not None:
        rows = audit_qs.select_related("user").order_by("-at")[:_SOURCE_CAP]
        for row in rows:
            entries.append({
                "at": row.at, "kind": "audit", "actor": row.user, "project": None,
                "label": row.target or "(no target)",
                "detail": row.get_action_display(), "url": None,
            })

    entries.sort(key=lambda entry: entry["at"], reverse=True)
    total_count = sum(counts.values())
    entries = entries[:_FEED_CAP]
    for entry in entries:
        entry["kind_label"] = _KIND_LABELS[entry["kind"]]
        entry["badge"] = _KIND_BADGES[entry["kind"]]

    return render(request, "projects/collaboration/activity_feed.html", {
        "projects": projects(tenant),
        "project": project,
        "kinds": _FEED_KINDS,
        "kind": kind,
        "windows": _WINDOW_CHOICES,
        "days": days,
        "since": since,
        "entries": entries,
        "counts": counts,
        "total_count": total_count,
        "entry_count": len(entries),
        "truncated": total_count > len(entries),
    })
