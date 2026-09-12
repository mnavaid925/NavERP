"""Projects 7.8 — TaskBlock views: the read-only evidence register and its detail page.

**``tbk_list``/``tbk_detail`` are the ONLY TaskBlock routes** — the evidence-row ruling ships no
``tbk_create``/``tbk_edit``/``tbk_delete`` (rows are minted ONLY by ``tsk_block`` and closed ONLY
by ``tsk_unblock``, both task verbs), and the list carries NO delete/Actions-edit column.

The register's one derived lens is ``?active=1`` — the open-blocker view. ``crud_list``'s
``filters`` are **field lookups only** and ``is_active`` is a Python property, not a column, so
the lens cannot be a filter spec: it is **pre-scoped here**, before ``crud_list`` (the
``?overdue=1`` idiom in QualityManagement), and only the exact string ``"1"`` activates it —
junk ``?active=`` values are ignored, not treated as a narrowing request (L11).

The detail page is the frozen-evidence view. It binds the two verb bodies read-only —
``block_form`` and ``unblock_form`` — whose panels POST to the TASK routes
(``projects:tsk_block`` / ``projects:tsk_unblock`` with ``obj.task_id``); the unblock panel
renders only while ``obj.is_active``.
"""
from django.db.models import Q

# Direct sub-module imports for this vertical's own modules: the forms/models package re-exports
# land in the Integrate step. ProjectTask is already re-exported by the models package.
from apps.projects.forms.TaskWorkManagement.TaskBlocks import TaskBlockForm, TaskUnblockForm
from apps.projects.models import ProjectTask
from apps.projects.models.TaskWorkManagement.TaskBlocks import TaskBlock
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required


@login_required
def tbk_list(request):
    qs = (TaskBlock.objects.filter(tenant=request.tenant)
          .select_related("task", "task__project", "blocked_by", "unblocked_by"))
    if request.GET.get("active") == "1":
        # The open-blocker lens, pre-scoped BEFORE crud_list: `is_active` is a property, not a
        # column, so it cannot be a crud_list filter spec (the ?overdue=1 idiom).
        qs = qs.filter(Q(unblocked_at__isnull=True))
    return crud_list(
        request, qs, "projects/taskwork/block/list.html",
        search_fields=["number", "reason", "unblock_criteria", "resolution_note"],
        filters=[("task", "task_id", True)],
        extra_context={
            "tasks": ProjectTask.objects.filter(tenant=request.tenant)
                        .select_related("project").order_by("number"),
        },
    )


@login_required
def tbk_detail(request, pk):
    return crud_detail(
        request, model=TaskBlock, pk=pk,
        template="projects/taskwork/block/detail.html",
        select_related=("task", "task__project", "blocked_by", "unblocked_by", "created_by"),
        extra_context={"block_form": TaskBlockForm(), "unblock_form": TaskUnblockForm()})
