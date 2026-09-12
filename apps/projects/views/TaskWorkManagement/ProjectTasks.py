"""Projects 7.8 — ProjectTask execution views: the execution edit page, the four single verbs
and the bulk update (bullet 1's "bulk operations").

Route map (``urls/TaskWorkManagement/ProjectTasks.py``, under 7.2's existing ``tasks/``
segment): ``tasks/bulk-update/`` (LITERAL FIRST — ``<int:pk>`` must never shadow it),
``tasks/<int:pk>/execute|start|complete|block|unblock/``. Every verb except ``tsk_execute``
(GET+POST, the ``crud_edit`` delegation) is POST-only.

The verbs are the ONE writers of the execution stamps the forms can never reach: ``tsk_start``
stamps ``actual_start`` exactly once (from ``planned``), ``tsk_complete`` stamps ``actual_end``
and ``percent_complete=100`` exactly once (from ``in_progress``). Both refuse while the task is
blocked — blocking is DERIVED (Ruling 3), so the refusal names the live source: the active
``TaskBlock`` number when a manual block stands, the unfinished FS/SS predecessor numbers when
the dependency network holds the task. ``previous`` is captured BEFORE mutating (the 7.4/7.6
stamp-verb idiom) and the audit action is the 10-char-safe ``update``/``create`` with the verb
in ``changes``.

``tsk_bulk_update`` is the ``rte_approve_week`` bulk idiom, but PER-ROW: every id gets the
single verbs' transition gating and one audit entry per applied field change, a refused row is
skipped with its own error message (never aborts the batch), and every id is fetched through a
tenant-scoped queryset — a forged id can never write outside the workspace.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.crud import as_db_int
# Direct sub-module imports for this vertical's own modules: the forms/models package re-exports
# land in the Integrate step. ProjectTask is already re-exported by the models package.
from apps.projects.forms.TaskWorkManagement.ProjectTasks import TaskExecutionForm
from apps.projects.forms.TaskWorkManagement.TaskBlocks import TaskBlockForm, TaskUnblockForm
from apps.projects.models import ProjectTask
from apps.projects.models.TaskWorkManagement.TaskBlocks import TaskBlock
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages, redirect,
                                         require_POST, write_audit_log)


def _unfinished_predecessor_numbers(obj):
    """The predecessor numbers whose links currently block — the same rule the derived
    ``is_dependency_blocked`` property computes: FS links from a predecessor not yet
    done/cancelled, SS links from one still planned."""
    numbers = []
    for link in obj.predecessor_links.select_related("predecessor"):
        if link.link_type == "finish_to_start" \
                and link.predecessor.status not in ("done", "cancelled"):
            numbers.append(link.predecessor.number)
        elif link.link_type == "start_to_start" and link.predecessor.status == "planned":
            numbers.append(link.predecessor.number)
    return numbers


def _blocker_source(obj):
    """The human-readable blocker source for a refusal message — the active ``TaskBlock``
    number when a manual block stands (one open blocker at a time, so it names THE row), the
    unfinished FS/SS predecessor numbers when the dependency network holds the task."""
    if obj.is_manually_blocked:
        block = obj.blocks.filter(unblocked_at__isnull=True).first()
        if block is not None:
            return f"block {block.number}"
    numbers = _unfinished_predecessor_numbers(obj)
    if numbers:
        return "unfinished predecessor{} {}".format(
            "s" if len(numbers) > 1 else "", ", ".join(numbers))
    return "an unknown blocker"


@login_required
def tsk_execute(request, pk):
    """The execution edit page — the six form-writable execution fields, nothing else.

    Delegates to the house ``crud_edit`` (tenant-scoped fetch inside, POST audit ``update``
    with ``crud._changed(form)``; the form's field list is the guard that keeps plan fields
    unreachable). ``success_url`` targets the task's own detail page, whose route takes the
    pk ``crud_edit``'s bare ``redirect(name)`` cannot carry — so it is pre-resolved here.
    """
    return crud_edit(
        request, model=ProjectTask, pk=pk, form_class=TaskExecutionForm,
        template="projects/taskwork/task_execution.html",
        success_url=reverse("projects:tsk_detail", args=[pk]))


# -- lifecycle verbs -----------------------------------------------------------------------------

@login_required
@require_POST
def tsk_start(request, pk):
    """Planned → in progress, stamping ``actual_start`` exactly once (verb-written only)."""
    obj = get_object_or_404(ProjectTask, pk=pk, tenant=request.tenant)
    if obj.status != "planned":
        messages.error(request, f"Task {obj.number} is not planned — only a planned task can "
                                f"be started.")
        return redirect("projects:tsk_detail", pk=obj.pk)
    if obj.is_blocked:
        messages.error(request, f"Task {obj.number} cannot be started while blocked by "
                                f"{_blocker_source(obj)}.")
        return redirect("projects:tsk_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "in_progress"
    obj.actual_start = timezone.localdate()
    obj.save(update_fields=["status", "actual_start", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "start", "from": previous, "to": obj.status})
    messages.success(request, f"Started task {obj.number}.")
    return redirect("projects:tsk_detail", pk=obj.pk)


@login_required
@require_POST
def tsk_complete(request, pk):
    """In progress → done, stamping ``actual_end`` and ``percent_complete=100`` exactly once.

    Hard-refused while the task is blocked — the refusal message names the source (the active
    TaskBlock number, or the unfinished FS/SS predecessor numbers).
    """
    obj = get_object_or_404(ProjectTask, pk=pk, tenant=request.tenant)
    if obj.status != "in_progress":
        messages.error(request, f"Task {obj.number} is not in progress — only an in-progress "
                                f"task can be completed.")
        return redirect("projects:tsk_detail", pk=obj.pk)
    if obj.is_blocked:
        messages.error(request, f"Task {obj.number} cannot be completed while blocked by "
                                f"{_blocker_source(obj)}.")
        return redirect("projects:tsk_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "done"
    obj.actual_end = timezone.localdate()
    obj.percent_complete = Decimal("100")
    obj.save(update_fields=["status", "actual_end", "percent_complete", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "complete", "from": previous, "to": obj.status})
    messages.success(request, f"Completed task {obj.number}.")
    return redirect("projects:tsk_detail", pk=obj.pk)


@login_required
@require_POST
def tsk_block(request, pk):
    """Raise this task's next ``TaskBlock`` evidence row — minted ONLY here.

    One open blocker at a time: while one stands the verb refuses, so
    ``is_manually_blocked`` always names THE row. The stamps (``blocked_by``/``blocked_at``/
    ``created_by``) are written here, never by any form.
    """
    obj = get_object_or_404(ProjectTask, pk=pk, tenant=request.tenant)
    active = obj.blocks.filter(unblocked_at__isnull=True).first()
    if active is not None:
        messages.error(request, f"Task {obj.number} already has an open block ({active.number})"
                                f" — one open blocker at a time; unblock it first.")
        return redirect("projects:tsk_detail", pk=obj.pk)
    form = TaskBlockForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("projects:tsk_detail", pk=obj.pk)
    block = TaskBlock.objects.create(
        tenant=request.tenant, task=obj,
        reason=form.cleaned_data["reason"],
        unblock_criteria=form.cleaned_data["unblock_criteria"],
        blocked_by=request.user, blocked_at=timezone.now(), created_by=request.user)
    write_audit_log(request.user, block, "create",
                    changes={"verb": "block", "task": obj.number})
    messages.success(request, f"Block {block.number} raised on task {obj.number}.")
    return redirect("projects:tsk_detail", pk=obj.pk)


@login_required
@require_POST
def tsk_unblock(request, pk):
    """Close the task's active block — exactly once, with the resolution trail.

    Unblock-twice is refused (``messages.info``): once ``unblocked_at`` is set the row is
    closed evidence. ``previous`` (the block's active state) is captured BEFORE mutating.
    """
    obj = get_object_or_404(ProjectTask, pk=pk, tenant=request.tenant)
    block = obj.blocks.filter(unblocked_at__isnull=True).first()
    if block is None:
        messages.info(request, f"Task {obj.number} has no active block to clear.")
        return redirect("projects:tsk_detail", pk=obj.pk)
    form = TaskUnblockForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("projects:tsk_detail", pk=obj.pk)
    previous = "active" if block.unblocked_at is None else "resolved"  # captured BEFORE mutating
    block.unblocked_by = request.user
    block.unblocked_at = timezone.now()
    block.resolution_note = form.cleaned_data["resolution_note"]
    block.save(update_fields=["unblocked_by", "unblocked_at", "resolution_note", "updated_at"])
    write_audit_log(request.user, block, "update",
                    changes={"verb": "unblock", "from": previous, "to": "resolved"})
    messages.success(request, f"Block {block.number} cleared from task {obj.number}.")
    return redirect("projects:tsk_detail", pk=obj.pk)


#: The two status values whose transitions carry a single verb's gating row-by-row:
#: ``in_progress`` is ``tsk_start``'s target (planned + unblocked, stamps ``actual_start``),
#: ``done`` is ``tsk_complete``'s (in progress + unblocked, stamps ``actual_end`` and
#: ``percent_complete=100``). ``planned``/``cancelled`` have no verb — they are the planning
#: write, applied directly like ``TaskForm``'s own status field.
_VERB_GATED_STATUSES = ("in_progress", "done")


@login_required
@require_POST
def tsk_bulk_update(request):
    """Bullet 1's bulk operations: status / assignee / priority over the multi-selected ids.

    Every id is fetched through a tenant-scoped queryset (a forged or stale id resolves to
    nothing and never writes), every status transition re-runs the single verbs' gating
    row-by-row, a refused row is skipped with its own error message without aborting the batch,
    and each applied field change gets its own audit entry.
    """
    status_value = (request.POST.get("status") or "").strip()
    if status_value and status_value not in dict(ProjectTask.STATUS_CHOICES):
        messages.error(request, "That status is not one of the task statuses.")
        return redirect("projects:tsk_list")
    priority_value = (request.POST.get("priority") or "").strip()
    if priority_value and priority_value not in dict(ProjectTask.PRIORITY_CHOICES):
        messages.error(request, "That priority is not one of the task priorities.")
        return redirect("projects:tsk_list")
    assignee_id = as_db_int(request.POST.get("assignee", ""))
    assignee = None
    if assignee_id is not None:
        # Existence only — the User FK is deliberately not tenant-rejected (the TaskForm.owner
        # precedent: users can be tenant-less, e.g. the superuser).
        assignee = get_user_model().objects.filter(pk=assignee_id).first()
        if assignee is None:
            messages.error(request, "That assignee does not exist.")
            return redirect("projects:tsk_list")
    if not status_value and priority_value == "" and assignee is None:
        messages.error(request, "Pick at least one field to update.")
        return redirect("projects:tsk_list")

    task_ids = [tid for tid in (as_db_int(raw) for raw in request.POST.getlist("task_ids"))
                if tid is not None]
    if not task_ids:
        messages.info(request, "No tasks were selected.")
        return redirect("projects:tsk_list")

    updated = refused = 0
    for task_id in task_ids:
        obj = ProjectTask.objects.filter(tenant=request.tenant, pk=task_id).first()
        if obj is None:
            refused += 1
            continue

        previous_status = obj.status
        previous_assignee = obj.assignee
        previous_priority = obj.priority
        status_changed = bool(status_value) and status_value != previous_status
        assignee_changed = assignee is not None and obj.assignee_id != assignee.pk
        priority_changed = bool(priority_value) and priority_value != previous_priority

        # -- the status transition, gated row-by-row like the single verbs -----------------------
        if status_changed and status_value in _VERB_GATED_STATUSES:
            if obj.is_blocked:
                refused += 1
                messages.error(request, f"Task {obj.number} skipped — blocked by "
                                        f"{_blocker_source(obj)}.")
                continue
            if status_value == "in_progress" and previous_status != "planned":
                refused += 1
                messages.error(request, f"Task {obj.number} skipped — only a planned task can "
                                        f"be started.")
                continue
            if status_value == "done" and previous_status != "in_progress":
                refused += 1
                messages.error(request, f"Task {obj.number} skipped — only an in-progress task "
                                        f"can be completed.")
                continue
        if not (status_changed or assignee_changed or priority_changed):
            messages.info(request, f"Task {obj.number} skipped — already in that state.")
            continue

        update_fields = []
        if status_changed:
            obj.status = status_value
            update_fields.append("status")
            if status_value == "in_progress":  # tsk_start's stamps, carried row-by-row
                obj.actual_start = timezone.localdate()
                update_fields.append("actual_start")
            elif status_value == "done":  # tsk_complete's stamps
                obj.actual_end = timezone.localdate()
                obj.percent_complete = Decimal("100")
                update_fields.extend(["actual_end", "percent_complete"])
        if assignee_changed:
            obj.assignee = assignee
            update_fields.append("assignee")
        if priority_changed:
            obj.priority = priority_value
            update_fields.append("priority")
        obj.save(update_fields=update_fields + ["updated_at"])

        # One audit entry PER applied field change — the batch verb, the field, the direction.
        if status_changed:
            write_audit_log(request.user, obj, "update",
                            changes={"verb": "bulk_update", "field": "status",
                                     "from": previous_status, "to": status_value})
        if assignee_changed:
            write_audit_log(request.user, obj, "update",
                            changes={"verb": "bulk_update", "field": "assignee",
                                     "from": str(previous_assignee) if previous_assignee else None,
                                     "to": str(assignee)})
        if priority_changed:
            write_audit_log(request.user, obj, "update",
                            changes={"verb": "bulk_update", "field": "priority",
                                     "from": previous_priority, "to": priority_value})
        updated += 1

    if updated:
        messages.success(request, f"Bulk update applied to {updated} task(s)"
                                  + (f"; {refused} skipped." if refused else "."))
    elif refused:
        messages.error(request, f"No tasks updated — {refused} skipped.")
    return redirect("projects:tsk_list")
