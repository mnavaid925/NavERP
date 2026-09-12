"""Projects 7.8 — TaskChecklistItem views: the checklist register, its CRUD and the check verb.

The register's two lenses are plain ``crud_list`` ``filters`` — ``?task=<pk>`` (an int-FK lookup,
``as_db_int``-guarded by ``crud_list``) and ``?is_done=`` (a BooleanField lookup, whose stringified
``True``/``False`` values ``crud_list`` maps and whose junk values it skips rather than 500ing —
L11). ``?task=`` also preselects the task on the create form (the ``qdf_create`` shape).

``tcl_check`` is the ONE writer of ``is_done``/``done_by``/``done_at`` — open → done stamps all
three, done → open clears all three (the un-tick goes through the SAME verb + audit — one writer
per direction), with ``previous`` captured BEFORE mutating. It redirects to the item detail: the
task-detail panel's tick button lands there too — no ``?next=`` plumbing this pass (documented
trade-off). ``label``/``sequence`` stay editable on done items (only the stamps are verb-only), so
``tcl_edit``/``tcl_delete`` carry no lock guard.
"""
from apps.core.crud import as_db_int
# Direct sub-module imports for this vertical's own modules: the forms/models package re-exports
# land in the Integrate step. ProjectTask is already re-exported by the models package.
from apps.projects.forms.TaskWorkManagement.TaskChecklistItems import TaskChecklistItemForm
from apps.projects.models import ProjectTask
from apps.projects.models.TaskWorkManagement.TaskChecklistItems import TaskChecklistItem
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages, redirect,
                                         render, require_POST, write_audit_log)


@login_required
def tcl_list(request):
    qs = (TaskChecklistItem.objects.filter(tenant=request.tenant)
          .select_related("task", "task__project", "done_by"))
    return crud_list(
        request, qs, "projects/taskwork/checklistitem/list.html",
        search_fields=["number", "label"],
        filters=[("task", "task_id", True), ("is_done", "is_done", False)],
        extra_context={
            "tasks": ProjectTask.objects.filter(tenant=request.tenant)
                        .select_related("project").order_by("number"),
        },
    )


@login_required
def tcl_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = TaskChecklistItemForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Checklist item {obj.number} added to the checklist.")
            return redirect("projects:tcl_detail", pk=obj.pk)
    else:
        form = TaskChecklistItemForm(tenant=request.tenant,
                                     initial={"task": as_db_int(request.GET.get("task", ""))})
    return render(request, "projects/taskwork/checklistitem/form.html",
                  {"form": form, "is_edit": False})


@login_required
def tcl_detail(request, pk):
    return crud_detail(
        request, model=TaskChecklistItem, pk=pk,
        template="projects/taskwork/checklistitem/detail.html",
        select_related=("task", "task__project", "done_by", "created_by"))


@login_required
def tcl_edit(request, pk):
    return crud_edit(
        request, model=TaskChecklistItem, pk=pk, form_class=TaskChecklistItemForm,
        template="projects/taskwork/checklistitem/form.html", success_url="projects:tcl_list")


@login_required
@require_POST
def tcl_delete(request, pk):
    return crud_delete(request, model=TaskChecklistItem, pk=pk, success_url="projects:tcl_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def tcl_check(request, pk):
    """Toggle the tick — the ONE writer of ``is_done``/``done_by``/``done_at``.

    Open → done stamps all three together; done → open clears all three — the un-tick goes
    through the SAME verb + audit, one writer per direction. ``previous`` is captured BEFORE
    mutating so the audit entry always shows the direction of the flip.
    """
    obj = get_object_or_404(TaskChecklistItem, pk=pk, tenant=request.tenant)
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
                    changes={"verb": "tcl_check", "from": previous, "to": obj.is_done})
    if obj.is_done:
        messages.success(request, f"Checked {obj.number} — {obj.label}.")
    else:
        messages.success(request, f"Unchecked {obj.number} — {obj.label}.")
    return redirect("projects:tcl_detail", pk=obj.pk)
