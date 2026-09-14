"""Projects 7.9 — ProjectNotification views: the inbox, its read verbs and the dismiss.

**No create and no edit route exists, by the evidence-row ruling** (see the model docstring): a
notification is minted by a trigger — ``msg_create``/``msg_edit``, the seeder, later 7.17's rule
engine — so a hand-written one would be a lie in the inbox. There is therefore no
``forms/CollaborationCommunication/ProjectNotifications.py`` either; the layer set is three, not
four, for this entity.

The register's four lenses are plain ``crud_list`` ``filters`` — ``?project=<pk>`` and
``?recipient=<pk>`` (int-FK lookups, ``as_db_int``-guarded and skipped when ``0``) and the two
enums ``?kind=``/``?is_read=``. ``?mine=1`` is a fifth, PRE-SCOPED before ``crud_list`` (only the
exact string ``"1"`` activates it — the 7.8 ``tbk_list ?active=1`` idiom) because it is a pair of
conditions, not one filter.

``ntf_mark_read`` is the ONE writer of ``is_read``/``read_at`` — a toggle, so marking something
unread again goes through the SAME verb + audit, ``previous`` captured BEFORE mutating.
``ntf_mark_all_read`` is deliberately scoped to the CALLER's own unread rows: an inbox is
personal, and a bulk verb that could clear a teammate's is a privilege escalation with no upside.
"""
from apps.projects.models import ProjectNotification
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages, redirect,
                                         require_POST, timezone, write_audit_log)
from apps.projects.views._helpers import owners, projects


@login_required
def ntf_list(request):
    qs = (ProjectNotification.objects.filter(tenant=request.tenant)
          .select_related("project", "recipient", "channel", "task", "meeting", "triggered_by"))
    # The "my inbox" lens is a PAIR of conditions, so it is applied before crud_list rather than
    # expressed as one filter tuple. Only the exact string "1" activates it.
    mine = request.GET.get("mine") == "1"
    if mine:
        qs = qs.filter(recipient=request.user)
    return crud_list(
        request, qs, "projects/collaboration/notification/list.html",
        search_fields=["number", "title", "body"],
        filters=[("project", "project_id", True), ("recipient", "recipient_id", True),
                 ("kind", "kind", False), ("is_read", "is_read", False)],
        extra_context={
            "projects": projects(request.tenant),
            "recipients": owners(request.tenant),
            "kind_choices": ProjectNotification.KIND_CHOICES,
            "mine": mine,
            "unread_count": ProjectNotification.objects.filter(
                tenant=request.tenant, recipient=request.user, is_read=False).count(),
        },
    )


@login_required
def ntf_detail(request, pk):
    return crud_detail(
        request, model=ProjectNotification, pk=pk,
        template="projects/collaboration/notification/detail.html",
        select_related=("project", "recipient", "channel", "message", "task", "meeting",
                        "triggered_by", "created_by"))


@login_required
@require_POST
def ntf_mark_read(request, pk):
    """Toggle the read state — the ONE writer of ``is_read``/``read_at``.

    Read stamps both together; unread clears both — the "mark unread" goes through the SAME verb +
    audit, one writer per direction, with ``previous`` captured BEFORE mutating.
    """
    obj = get_object_or_404(ProjectNotification, pk=pk, tenant=request.tenant)
    previous = obj.is_read
    if previous:
        obj.is_read = False
        obj.read_at = None
    else:
        obj.is_read = True
        obj.read_at = timezone.now()
    obj.save(update_fields=["is_read", "read_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "ntf_mark_read", "from": previous, "to": obj.is_read})
    if obj.is_read:
        messages.success(request, f"Marked {obj.number} as read.")
    else:
        messages.success(request, f"Marked {obj.number} as unread.")
    return redirect("projects:ntf_detail", pk=obj.pk)


@login_required
@require_POST
def ntf_mark_all_read(request):
    """Clear the CALLER's own unread rows. Never a teammate's — an inbox is personal.

    Saved row by row rather than with one ``queryset.update()``: ``auto_now`` fires only on
    ``save()``, so a bulk update would leave every ``updated_at`` stale. The inbox is small, and
    the per-row save keeps the audit trail's timestamps honest. One audit entry covers the batch
    (the ``rte_approve_week`` precedent) — the verb is one action, not N.
    """
    rows = list(ProjectNotification.objects.filter(
        tenant=request.tenant, recipient=request.user, is_read=False))
    if not rows:
        messages.info(request, "Your inbox is already clear.")
        return redirect("projects:ntf_list")
    now = timezone.now()
    for row in rows:
        row.is_read = True
        row.read_at = now
        row.save(update_fields=["is_read", "read_at", "updated_at"])
    count = len(rows)
    write_audit_log(request.user, rows[0], "update",
                    changes={"verb": "ntf_mark_all_read", "from": count, "to": 0})
    messages.success(request, f"Marked {count} notification{'s' if count != 1 else ''} as read.")
    return redirect("projects:ntf_list")


@login_required
@require_POST
def ntf_delete(request, pk):
    """Dismiss one of the tenant's notification rows.

    Unlike 7.8's block evidence, an inbox row IS deletable — it is one person's delivery record,
    not shared evidence, and an inbox you cannot clear is a worse inbox (see the model docstring).
    """
    return crud_delete(request, model=ProjectNotification, pk=pk,
                       success_url="projects:ntf_list")
