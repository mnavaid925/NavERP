"""Projects 7.9 — Channel views: the channel register, its CRUD and the archive toggle.

The register's three lenses are plain ``crud_list`` ``filters`` — ``?project=<pk>`` (an int-FK
lookup, ``as_db_int``-guarded by ``crud_list``, and ``0`` skipped because it is a pk lookup),
``?kind=`` (an enum, whose junk values ``crud_list``'s ``_enum_values`` guard ignores rather than
silently emptying the register — L11) and ``?is_archived=`` (a BooleanField, whose stringified
``True``/``False`` values ``crud_list`` maps).

``message_count`` is a ``Count("messages")`` ANNOTATION on the queryset, never a model property:
a ``.count()`` property re-queries once per rendered row and defeats any prefetch — the 7.8
``checklist_progress`` lesson.

``chn_detail`` builds the thread tree in PYTHON from ONE materialized message list. It must not
be tempted into ``obj.messages.filter(parent=root)`` per thread: that is the 31-queries-per-render
shape the 7.8 `tsk_detail` fix removed.

``chn_archive`` is the ONE writer of ``is_archived``/``archived_by``/``archived_at`` — a toggle,
so the un-archive goes through the SAME verb + audit (one writer per direction), with ``previous``
captured BEFORE mutating.
"""
from django.db.models import Count

from apps.projects.forms import ChannelForm, ChannelMessageForm
from apps.projects.models import Channel
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages, redirect,
                                         render, require_POST, timezone, write_audit_log)
from apps.projects.views._helpers import projects


@login_required
def chn_list(request):
    qs = (Channel.objects.filter(tenant=request.tenant)
          .select_related("project")
          .annotate(message_count=Count("messages")))
    return crud_list(
        request, qs, "projects/collaboration/channel/list.html",
        search_fields=["number", "name", "topic"],
        filters=[("project", "project_id", True), ("kind", "kind", False),
                 ("is_archived", "is_archived", False)],
        extra_context={"projects": projects(request.tenant)},
    )


@login_required
def chn_detail(request, pk):
    obj = get_object_or_404(
        Channel.objects.filter(tenant=request.tenant)
                       .select_related("project", "created_by", "archived_by"),
        pk=pk)
    # ONE query for the whole conversation, then the tree is assembled in Python. `threads` is a
    # list of {"root": ChannelMessage, "replies": list[ChannelMessage]} in (created_at, id) order.
    rows = list(obj.messages.select_related("parent", "created_by")
                .order_by("created_at", "id"))
    roots = [row for row in rows if row.parent_id is None]
    replies = {}
    for row in rows:
        if row.parent_id is not None:
            replies.setdefault(row.parent_id, []).append(row)
    threads = [{"root": root, "replies": replies.get(root.pk, [])} for root in roots]
    return render(request, "projects/collaboration/channel/detail.html", {
        "obj": obj,
        "threads": threads,
        "message_count": len(rows),
        "reply_count": len(rows) - len(roots),
        "message_form": ChannelMessageForm(tenant=request.tenant,
                                           initial={"channel": obj.pk}),
        "shares": (obj.document_shares.filter(is_active=True)
                   .select_related("document", "shared_with")),
    })


@login_required
def chn_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ChannelForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Channel {obj.number} created.")
            return redirect("projects:chn_detail", pk=obj.pk)
    else:
        form = ChannelForm(tenant=request.tenant)
    return render(request, "projects/collaboration/channel/form.html",
                  {"form": form, "is_edit": False})


@login_required
def chn_edit(request, pk):
    return crud_edit(
        request, model=Channel, pk=pk, form_class=ChannelForm,
        template="projects/collaboration/channel/form.html", success_url="projects:chn_list")


@login_required
@require_POST
def chn_delete(request, pk):
    return crud_delete(request, model=Channel, pk=pk, success_url="projects:chn_list")


# -- lifecycle verb -----------------------------------------------------------------------------

@login_required
@require_POST
def chn_archive(request, pk):
    """Toggle the archive state — the ONE writer of ``is_archived``/``archived_by``/``archived_at``.

    Archiving stamps all three together; unarchiving clears all three — the un-archive goes
    through the SAME verb + audit, one writer per direction. ``previous`` is captured BEFORE
    mutating so the audit entry always shows the direction of the flip.
    """
    obj = get_object_or_404(Channel, pk=pk, tenant=request.tenant)
    previous = obj.is_archived
    if previous:
        obj.is_archived = False
        obj.archived_by = None
        obj.archived_at = None
    else:
        obj.is_archived = True
        obj.archived_by = request.user
        obj.archived_at = timezone.now()
    obj.save(update_fields=["is_archived", "archived_by", "archived_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "chn_archive", "from": previous, "to": obj.is_archived})
    if obj.is_archived:
        messages.success(request, f"Archived channel {obj.number} — {obj.name}.")
    else:
        messages.success(request, f"Reopened channel {obj.number} — {obj.name}.")
    return redirect("projects:chn_detail", pk=obj.pk)
