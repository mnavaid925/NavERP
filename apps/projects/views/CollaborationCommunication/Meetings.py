"""Projects 7.9 — Meeting views: the register, the lifecycle verbs, minutes and the two children.

The register's four lenses are plain ``crud_list`` ``filters`` — ``?project=<pk>`` (an int-FK
lookup, ``as_db_int``-guarded and skipped when ``0``) and the three enums ``?kind=``, ``?status=``,
``?mode=`` (whose junk values the ``_enum_values`` guard ignores rather than silently emptying the
register — L11).

**All three register figures are ANNOTATIONS, never properties.** ``agenda_total``,
``agenda_covered`` and ``open_actions`` are conditional ``Count``s over two different joins, so
``distinct=True`` is mandatory — without it each ``Count`` would multiply by the other join's row
count and the totals would be nonsense. A ``.count()`` property on the model would re-query once
per rendered row instead (the 7.8 ``checklist_progress`` lesson), which is why §3.4 deliberately
ships no ``agenda_progress`` property and ``mtg_detail`` computes its two figures in Python over
the ONE materialized list it already has.

**The lifecycle verbs.** ``mtg_start`` / ``mtg_complete`` / ``mtg_cancel`` each move exactly one
edge of the status machine and stamp their own actual-time field; every one captures ``previous``
BEFORE mutating. ``mtg_minutes`` writes the minutes and their stamps and **does not touch
``status``** — writing up a meeting is not completing it.

**The child verbs.** ``agi_cover`` and ``mai_toggle`` are the ONE writers of their tick state,
toggles in both directions, with ``previous`` captured first. The two child CREATE views stamp
``meeting`` from the URL pk (the forms deliberately exclude it), and the two DELETE views redirect
to the MEETING rather than to a register that does not exist for either child.
"""
from django.db.models import Count, Q

from apps.core.crud import _changed
from apps.projects.forms import (MeetingActionItemForm, MeetingAgendaItemForm, MeetingForm,
                                MeetingMinutesForm)
from apps.projects.models import Meeting, MeetingActionItem, MeetingAgendaItem
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (as_db_int, get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, timezone,
                                         write_audit_log)
from apps.projects.views._helpers import projects


@login_required
def mtg_list(request):
    qs = (Meeting.objects.filter(tenant=request.tenant)
          .select_related("project")
          .annotate(
              agenda_total=Count("agenda_items", distinct=True),
              agenda_covered=Count("agenda_items",
                                   filter=Q(agenda_items__is_covered=True), distinct=True),
              open_actions=Count("action_items",
                                 filter=Q(action_items__is_done=False), distinct=True)))
    return crud_list(
        request, qs, "projects/collaboration/meeting/list.html",
        search_fields=["number", "title", "location"],
        filters=[("project", "project_id", True), ("kind", "kind", False),
                 ("status", "status", False), ("mode", "mode", False)],
        extra_context={
            "projects": projects(request.tenant),
            "status_choices": Meeting.STATUS_CHOICES,
            "kind_choices": Meeting.KIND_CHOICES,
            "mode_choices": Meeting.MODE_CHOICES,
        },
    )


@login_required
def mtg_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = MeetingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Meeting {obj.number} scheduled.")
            return redirect("projects:mtg_detail", pk=obj.pk)
    else:
        form = MeetingForm(tenant=request.tenant,
                           initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/collaboration/meeting/form.html",
                  {"form": form, "is_edit": False})


@login_required
def mtg_detail(request, pk):
    obj = get_object_or_404(
        Meeting.objects.filter(tenant=request.tenant)
                       .select_related("project", "minutes_by", "created_by"),
        pk=pk)
    # ONE query each, then the two derived figures are counted in Python over those lists — the
    # model ships no such property on purpose (see the module docstring).
    agenda_items = list(obj.agenda_items.select_related("presenter").order_by("sequence", "id"))
    action_items = list(obj.action_items.select_related("assignee", "task").order_by("id"))
    return render(request, "projects/collaboration/meeting/detail.html", {
        "obj": obj,
        "agenda_items": agenda_items,
        "action_items": action_items,
        "agenda_total": len(agenda_items),
        "agenda_covered": sum(1 for item in agenda_items if item.is_covered),
        "open_action_count": sum(1 for item in action_items if not item.is_done),
        "overdue_action_count": sum(1 for item in action_items if item.is_overdue),
        "minutes_form": MeetingMinutesForm(initial={"minutes": obj.minutes}),
        "agenda_form": MeetingAgendaItemForm(tenant=request.tenant),
        "action_form": MeetingActionItemForm(tenant=request.tenant),
    })


@login_required
def mtg_edit(request, pk):
    return crud_edit(
        request, model=Meeting, pk=pk, form_class=MeetingForm,
        template="projects/collaboration/meeting/form.html", success_url="projects:mtg_list")


@login_required
@require_POST
def mtg_delete(request, pk):
    return crud_delete(request, model=Meeting, pk=pk, success_url="projects:mtg_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def mtg_start(request, pk):
    """``scheduled`` → ``in_progress``, stamping the real start time."""
    obj = get_object_or_404(Meeting, pk=pk, tenant=request.tenant)
    if obj.status != "scheduled":
        messages.error(request, f"{obj.number} is {obj.get_status_display()|lower} — only a "
                                f"scheduled meeting can be started.")
        return redirect("projects:mtg_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "in_progress"
    obj.actual_start = timezone.now()
    obj.save(update_fields=["status", "actual_start", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "mtg_start", "from": previous, "to": obj.status})
    messages.success(request, f"Meeting {obj.number} started.")
    return redirect("projects:mtg_detail", pk=obj.pk)


@login_required
@require_POST
def mtg_complete(request, pk):
    """``in_progress`` → ``completed``, stamping the real end time."""
    obj = get_object_or_404(Meeting, pk=pk, tenant=request.tenant)
    if obj.status != "in_progress":
        messages.error(request, f"{obj.number} is {obj.get_status_display()|lower} — only a "
                                f"meeting in progress can be completed.")
        return redirect("projects:mtg_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "completed"
    obj.actual_end = timezone.now()
    obj.save(update_fields=["status", "actual_end", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "mtg_complete", "from": previous, "to": obj.status})
    messages.success(request, f"Meeting {obj.number} completed.")
    return redirect("projects:mtg_detail", pk=obj.pk)


@login_required
@require_POST
def mtg_cancel(request, pk):
    """``scheduled``/``in_progress`` → ``cancelled``. A terminal meeting cannot be cancelled."""
    obj = get_object_or_404(Meeting, pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "cancelled"):
        messages.info(request, f"{obj.number} is already {obj.get_status_display()|lower} — "
                               f"nothing to cancel.")
        return redirect("projects:mtg_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "mtg_cancel", "from": previous, "to": obj.status})
    messages.success(request, f"Meeting {obj.number} cancelled.")
    return redirect("projects:mtg_detail", pk=obj.pk)


@login_required
def mtg_minutes(request, pk):
    """Capture the minutes — the ONE writer of ``minutes``/``minutes_by``/``minutes_at``.

    Deliberately does NOT move ``status``: writing up a meeting is not completing it. Completion
    is ``mtg_complete``'s, and conflating the two would let a minute close a meeting nobody closed.
    """
    obj = get_object_or_404(Meeting.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = MeetingMinutesForm(request.POST)
        if form.is_valid():
            previous = bool(obj.minutes)
            obj.minutes = form.cleaned_data["minutes"]
            obj.minutes_by = request.user
            obj.minutes_at = timezone.now()
            obj.save(update_fields=["minutes", "minutes_by", "minutes_at", "updated_at"])
            write_audit_log(request.user, obj, "update",
                            changes={"verb": "mtg_minutes", "from": previous, "to": True})
            messages.success(request, f"Minutes captured for {obj.number}.")
            return redirect("projects:mtg_detail", pk=obj.pk)
    else:
        form = MeetingMinutesForm(initial={"minutes": obj.minutes})
    return render(request, "projects/collaboration/meeting/minutes.html",
                  {"form": form, "obj": obj, "is_edit": True})


# -- agenda items -------------------------------------------------------------------------------

@login_required
def agi_create(request, pk):
    """Add an agenda line. The meeting comes from the URL — the form excludes the FK."""
    meeting = get_object_or_404(Meeting, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = MeetingAgendaItemForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.meeting = meeting
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Agenda item {obj.number} added to {meeting.number}.")
            return redirect("projects:mtg_detail", pk=meeting.pk)
    else:
        form = MeetingAgendaItemForm(tenant=request.tenant)
    return render(request, "projects/collaboration/meeting/agendaitem/form.html",
                  {"form": form, "meeting": meeting, "is_edit": False})


@login_required
def agi_edit(request, pk):
    obj = get_object_or_404(MeetingAgendaItem.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = MeetingAgendaItemForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", changes=_changed(form))
            messages.success(request, f"Agenda item {obj.number} updated.")
            return redirect("projects:mtg_detail", pk=obj.meeting_id)
    else:
        form = MeetingAgendaItemForm(instance=obj, tenant=request.tenant)
    return render(request, "projects/collaboration/meeting/agendaitem/form.html",
                  {"form": form, "obj": obj, "meeting": obj.meeting, "is_edit": True})


@login_required
@require_POST
def agi_delete(request, pk):
    """Delete an agenda line and land back on its meeting — a child has no register to return to."""
    obj = get_object_or_404(MeetingAgendaItem, pk=pk, tenant=request.tenant)
    meeting_pk = obj.meeting_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Agenda item deleted.")
    return redirect("projects:mtg_detail", pk=meeting_pk)


@login_required
@require_POST
def agi_cover(request, pk):
    """Toggle the agenda line's covered state — the ONE writer of ``is_covered``/``covered_*``."""
    obj = get_object_or_404(MeetingAgendaItem, pk=pk, tenant=request.tenant)
    previous = obj.is_covered
    if previous:
        obj.is_covered = False
        obj.covered_by = None
        obj.covered_at = None
    else:
        obj.is_covered = True
        obj.covered_by = request.user
        obj.covered_at = timezone.now()
    obj.save(update_fields=["is_covered", "covered_by", "covered_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "agi_cover", "from": previous, "to": obj.is_covered})
    if obj.is_covered:
        messages.success(request, f"Covered agenda item {obj.number} — {obj.title}.")
    else:
        messages.success(request, f"Reopened agenda item {obj.number} — {obj.title}.")
    return redirect("projects:mtg_detail", pk=obj.meeting_id)


# -- action items -------------------------------------------------------------------------------

@login_required
def mai_create(request, pk):
    """Add an action item. The meeting comes from the URL — the form excludes the FK."""
    meeting = get_object_or_404(Meeting, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = MeetingActionItemForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.meeting = meeting
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Action item {obj.number} added to {meeting.number}.")
            return redirect("projects:mtg_detail", pk=meeting.pk)
    else:
        form = MeetingActionItemForm(tenant=request.tenant)
    return render(request, "projects/collaboration/meeting/actionitem/form.html",
                  {"form": form, "meeting": meeting, "is_edit": False})


@login_required
def mai_edit(request, pk):
    obj = get_object_or_404(MeetingActionItem.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = MeetingActionItemForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", changes=_changed(form))
            messages.success(request, f"Action item {obj.number} updated.")
            return redirect("projects:mtg_detail", pk=obj.meeting_id)
    else:
        form = MeetingActionItemForm(instance=obj, tenant=request.tenant)
    return render(request, "projects/collaboration/meeting/actionitem/form.html",
                  {"form": form, "obj": obj, "meeting": obj.meeting, "is_edit": True})


@login_required
@require_POST
def mai_delete(request, pk):
    obj = get_object_or_404(MeetingActionItem, pk=pk, tenant=request.tenant)
    meeting_pk = obj.meeting_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Action item deleted.")
    return redirect("projects:mtg_detail", pk=meeting_pk)


@login_required
@require_POST
def mai_toggle(request, pk):
    """Toggle the action's done state — the ONE writer of ``is_done``/``done_by``/``done_at``."""
    obj = get_object_or_404(MeetingActionItem, pk=pk, tenant=request.tenant)
    previous = obj.is_done
    if previous:
        obj.is_done = False
        obj.done_by = None
        obj.done_at = None
    else:
        obj.is_done = True
        obj.done_by = request.user
        obj.done_at = timezone.now()
    obj.save(update_fields=["is_done", "done_by", "done_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "mai_toggle", "from": previous, "to": obj.is_done})
    if obj.is_done:
        messages.success(request, f"Closed action item {obj.number}.")
    else:
        messages.success(request, f"Reopened action item {obj.number}.")
    return redirect("projects:mtg_detail", pk=obj.meeting_id)
