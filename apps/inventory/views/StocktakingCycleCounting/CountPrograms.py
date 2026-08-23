"""Inventory 5.11 Stocktaking & Cycle Counting — CountProgram views.

CRUD plus the one bespoke verb, ``run``: mint today's spine count sheet for the
program's scope. Refusals (no scope) are the model's ValidationErrors surfaced as
flash messages; an already-run day reuses the existing sheet and says so.
"""
from django.utils import timezone

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import CountProgramForm
from apps.inventory.models import CountProgram


def _scoped(tenant):
    return CountProgram.objects.filter(tenant=tenant).select_related("location")


@login_required
def countprogram_list(request):
    qs = _scoped(request.tenant)
    due_today = [p for p in qs if p.is_due(timezone.localdate())]
    return crud_list(
        request, qs, "inventory/stocktake/countprogram/list.html",
        search_fields=["name", "notes", "location__code"],
        filters=[("frequency", "frequency", False), ("active", "is_active", False)],
        extra_context={
            "frequency_choices": CountProgram.FREQUENCY_CHOICES,
            "due_count": len(due_today),
            "today": timezone.localdate(),
        },
    )


@login_required
def countprogram_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    # The sheets this program has minted, newest first — provenance via the notes
    # marker the model stamps at generate time.
    from apps.scm.models import CycleCountTask
    recent = (CycleCountTask.objects.filter(
                tenant=obj.tenant_id,
                notes__startswith=f"Via count program {obj.number}")
              .select_related("location")[:10])
    return render(request, "inventory/stocktake/countprogram/detail.html", {
        "obj": obj,
        "recent_tasks": recent,
        "is_due": obj.is_due(timezone.localdate()),
    })


@login_required
def countprogram_create(request):
    return crud_create(
        request, form_class=CountProgramForm,
        template="inventory/stocktake/countprogram/form.html",
        success_url="inventory:countprogram_list",
    )


@login_required
def countprogram_edit(request, pk):
    return crud_edit(
        request, model=CountProgram, pk=pk, form_class=CountProgramForm,
        template="inventory/stocktake/countprogram/form.html",
        success_url="inventory:countprogram_list",
    )


@login_required
@require_POST
def countprogram_delete(request, pk):
    return crud_delete(request, model=CountProgram, pk=pk,
                       success_url="inventory:countprogram_list")


@login_required
@require_POST
def countprogram_run(request, pk):
    """Run the cadence now: mint (or reuse) today's spine sheet for this program."""
    obj = get_object_or_404(CountProgram, pk=pk, tenant=request.tenant)
    try:
        task, created = obj.generate_tasks(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("inventory:countprogram_detail", pk=obj.pk)
    if created:
        messages.success(
            request, f"{obj.number} ran — count sheet {task.number} scheduled in SCM.")
    else:
        messages.info(
            request, f"{obj.number} already produced {task.number} today — reused it.")
    return redirect("scm:cyclecounttask_detail", pk=task.pk)
