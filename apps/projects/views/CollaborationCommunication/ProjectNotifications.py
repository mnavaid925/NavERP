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

**All three write verbs are scoped to the CALLER's own rows.** An inbox is personal: a row is one
person's delivery, not shared evidence, so clearing a teammate's unread badge (or destroying their
row) is a privilege escalation with no upside. ``ntf_mark_all_read`` was already caller-scoped;
``ntf_mark_read`` and ``ntf_delete`` carry ``recipient=request.user`` for the same reason — a
teammate's row is a 404, exactly like another workspace's row. The templates offer the two
controls only on rows the viewer owns (the L27 converse rule).
"""
from apps.projects.models import ProjectNotification
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages, redirect,
                                         require_POST, timezone, write_audit_log)
from apps.projects.views._helpers import owners, projects


@login_required
def ntf_list(request):
    qs = (ProjectNotification.objects.filter(tenant=request.tenant)
          # `message` is here because the register's Source column renders `obj.message.number`
          # — without it every row that carries a message costs one extra query (up to per_page
          # per render). The detail view already selected it; this closes the list's gap.
          .select_related("project", "recipient", "channel", "message", "task", "meeting",
                          "triggered_by"))
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

    Scoped to the caller: a teammate's row is a 404, not something you may clear (see the module
    docstring). ``ntf_mark_all_read`` and the model's per-recipient-delivery ruling agree.
    """
    obj = get_object_or_404(ProjectNotification, pk=pk, tenant=request.tenant,
                            recipient=request.user)
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

    One ``UPDATE`` for the whole batch, not one per row. ``auto_now`` does not fire on
    ``queryset.update()``, so ``updated_at`` is stamped explicitly here rather than left stale —
    the concern the per-row save used to address, met head-on instead of side-stepped. One audit
    entry covers the batch (the ``rte_approve_week`` precedent) — the verb is one action, not N.
    """
    qs = ProjectNotification.objects.filter(
        tenant=request.tenant, recipient=request.user, is_read=False)
    count = qs.count()
    if not count:
        messages.info(request, "Your inbox is already clear.")
        return redirect("projects:ntf_list")
    # One representative row for the single audit entry, captured BEFORE the update (after it the
    # queryset is empty).
    first = qs.first()
    now = timezone.now()
    qs.update(is_read=True, read_at=now, updated_at=now)
    write_audit_log(request.user, first, "update",
                    changes={"verb": "ntf_mark_all_read", "from": count, "to": 0})
    messages.success(request, f"Marked {count} notification{'s' if count != 1 else ''} as read.")
    return redirect("projects:ntf_list")


@login_required
@require_POST
def ntf_delete(request, pk):
    """Dismiss one of the CALLER's own notification rows.

    Unlike 7.8's block evidence, an inbox row IS deletable — it is one person's delivery record,
    not shared evidence, and an inbox you cannot clear is a worse inbox (see the model docstring).

    ``crud_delete`` cannot express the extra ``recipient`` predicate (it fetches on ``pk`` +
    ``tenant`` only), so the fetch is hand-rolled the way ``agi_delete``/``mai_delete`` are: a
    teammate's row is a 404, exactly like another workspace's.
    """
    obj = get_object_or_404(ProjectNotification, pk=pk, tenant=request.tenant,
                            recipient=request.user)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Notification dismissed.")
    return redirect("projects:ntf_list")
