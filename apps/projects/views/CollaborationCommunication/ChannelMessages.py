"""Projects 7.9 — ChannelMessage views: the message register, its CRUD and the mention trigger.

The register's three lenses are plain ``crud_list`` ``filters`` — ``?channel=<pk>`` and
``?parent=<pk>`` (int-FK lookups, ``as_db_int``-guarded by ``crud_list`` and skipped when ``0``
because they are pk lookups) and ``?author=<pk>`` (the author lens). ``reply_count`` is a
``Count("replies")`` ANNOTATION, never a model property — a ``.count()`` property re-queries once
per rendered row (the 7.8 ``checklist_progress`` lesson).

``_notify_mentions`` is the trigger half of bullet 1: a mention is not only a highlight, it mints
a real ``ProjectNotification`` delivery row for each named teammate. It is private to this module
because both of its consumers live here (``msg_create`` and ``msg_edit``) — the ``_helpers.py``
rule reserves that file for helpers used by more than one sub-module.

**Why the rows are saved one at a time, not ``bulk_create``d.** ``ProjectNotification`` inherits
``TenantNumbered``, whose ``save()`` is what mints the per-tenant ``NTF-#####`` number. A
``bulk_create`` bypasses ``save()`` entirely, so every row would land with ``number=""`` — and the
second one would then violate ``unique_together ("tenant", "number")`` outright. A message names a
handful of people, so the honest per-row ``save()`` is the right trade; the seeder takes the same
path for the same reason.
"""
from django.db.models import Count

from apps.core.crud import _changed, as_db_int
from apps.projects.forms import ChannelMessageForm
from apps.projects.models import Channel, ChannelMessage, ProjectNotification
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, timezone,
                                         write_audit_log)
from apps.projects.views._helpers import owners


@login_required
def msg_list(request):
    qs = (ChannelMessage.objects.filter(tenant=request.tenant)
          .select_related("channel", "channel__project", "parent", "created_by")
          .annotate(reply_count=Count("replies")))
    return crud_list(
        request, qs, "projects/collaboration/message/list.html",
        search_fields=["number", "body"],
        filters=[("channel", "channel_id", True), ("parent", "parent_id", True),
                 ("author", "created_by_id", True)],
        extra_context={
            "channels": (Channel.objects.filter(tenant=request.tenant)
                         .select_related("project").order_by("number")),
            "owners": owners(request.tenant),
        },
    )


@login_required
def msg_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ChannelMessageForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            form.save_m2m()
            _notify_mentions(request, obj, obj.mentions.all())
            write_audit_log(request.user, obj, "create")
            messages.success(
                request, f"Message {obj.number} posted to {obj.channel.name}.")
            return redirect("projects:chn_detail", pk=obj.channel_id)
    else:
        form = ChannelMessageForm(tenant=request.tenant, initial={
            "channel": as_db_int(request.GET.get("channel", "")),
            "parent": as_db_int(request.GET.get("parent", "")),
        })
    return render(request, "projects/collaboration/message/form.html",
                  {"form": form, "is_edit": False})


@login_required
def msg_edit(request, pk):
    """Edit a message body and/or its audience — and notify only the people the edit ADDED.

    Not ``crud_edit``: the mention diff has to be read BEFORE ``form.save()``, because after it
    the old and new audiences are indistinguishable. Re-saving an unchanged mention list must not
    re-notify anyone.
    """
    obj = get_object_or_404(ChannelMessage.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = ChannelMessageForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            before = set(obj.mentions.values_list("pk", flat=True))
            obj = form.save()
            form.save_m2m()
            _notify_mentions(request, obj, obj.mentions.exclude(pk__in=before))
            # The edit stamp is verb-written — the form cannot reach edited_by/edited_at.
            obj.edited_by = request.user
            obj.edited_at = timezone.now()
            obj.save(update_fields=["edited_by", "edited_at", "updated_at"])
            write_audit_log(request.user, obj, "update",
                            changes={**_changed(form), "verb": "msg_edit"})
            messages.success(request, f"Message {obj.number} updated.")
            return redirect("projects:chn_detail", pk=obj.channel_id)
    else:
        form = ChannelMessageForm(instance=obj, tenant=request.tenant)
    return render(request, "projects/collaboration/message/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def msg_delete(request, pk):
    # A message has no register of its own to return to, so the delete lands on the channel
    # register (crud_delete's success_url), never on a page that just lost its subject.
    return crud_delete(request, model=ChannelMessage, pk=pk,
                       success_url="projects:chn_list")


# -- the mention trigger ------------------------------------------------------------------------

def _notify_mentions(request, message, added):
    """Mint one ``mention`` notification per newly-added mention, skipping the author.

    ``added`` is exactly the set this call is responsible for: ``msg_create`` passes every mention
    on the new message, ``msg_edit`` passes only the ones the edit introduced. You are never
    notified for mentioning yourself.

    No per-row audit is written — the trigger is recorded on the MESSAGE, which is the row that
    changed; the notifications are its delivery fan-out, not independent evidence.
    """
    recipients = [user for user in added if user.pk != request.user.pk]
    if not recipients:
        return []
    channel = message.channel
    rows = []
    for user in recipients:
        row = ProjectNotification(
            tenant=request.tenant,
            project=channel.project,
            recipient=user,
            kind="mention",
            title=f"Mentioned in {channel.number} — {channel.name}",
            body=message.body[:200],
            channel=channel,
            message=message,
            triggered_by=request.user,
            created_by=request.user,
        )
        # Not bulk_create: it bypasses TenantNumbered.save(), so `number` would stay "" and the
        # second row would break unique_together ("tenant", "number"). See the module docstring.
        row.full_clean(exclude=["number"])
        row.save()
        rows.append(row)
    return rows
