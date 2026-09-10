"""Projects 7.5 — RiskResponseAction views: the response plan's action register, its CRUD and its
one lifecycle verb.

Bullet **3 Response Planning** is this page. Each row executes a strategy already recorded on a
``ProjectRisk``; the register lets the project see, in one place, who owes which action, by when,
and at what cost. ``crud_list``'s ``filters`` are **field lookups only** — ``is_overdue`` is a
Python property, so the ``?overdue=1`` lens cannot be a filter spec. It is **pre-scoped here**,
before ``crud_list`` paginates, and built out of real columns so the database does the work.

The verb (POST-only, GET → 405): ``complete`` — the action finished, stamping ``completed_at``. A
completed action is frozen evidence, so ``rra_edit``/``rra_delete`` refuse it.
"""
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import RiskResponseActionForm
from apps.projects.models import ProjectRisk, RiskResponseAction
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import owners

#: The statuses an action can still be worked from — everything but the two terminal ones.
_LIVE_STATUSES = ("planned", "in_progress")

_LOCKED_MSG = ("A completed response action is frozen evidence and cannot be edited or deleted.")


@login_required
def rra_list(request):
    qs = (RiskResponseAction.objects.filter(tenant=request.tenant)
          .select_related("risk", "risk__project", "owner"))
    if request.GET.get("overdue") == "1":
        # ``is_overdue`` is a property, so the lens is reconstructed from its two real columns —
        # a due date that has passed while the action is still live.
        qs = qs.filter(Q(due_date__lt=timezone.localdate(), status__in=_LIVE_STATUSES))
    return crud_list(
        request, qs, "projects/risk/responseaction/list.html",
        search_fields=["number", "title", "description", "trigger"],
        filters=[("risk", "risk_id", True),
                 ("strategy", "strategy", False),
                 ("status", "status", False),
                 ("owner", "owner_id", True)],
        extra_context={
            "risks": ProjectRisk.objects.filter(tenant=request.tenant).order_by("number"),
            "strategy_choices": RiskResponseAction.STRATEGY_CHOICES,
            "status_choices": RiskResponseAction.STATUS_CHOICES,
            "owners": owners(request.tenant),
        },
    )


@login_required
def rra_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = RiskResponseActionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Response action {obj.number} logged.")
            return redirect("projects:rra_detail", pk=obj.pk)
    else:
        form = RiskResponseActionForm(
            tenant=request.tenant,
            initial={"risk": as_db_int(request.GET.get("risk", ""))})
    return render(request, "projects/risk/responseaction/form.html",
                  {"form": form, "is_edit": False})


@login_required
def rra_detail(request, pk):
    obj = get_object_or_404(
        RiskResponseAction.objects.select_related("risk", "risk__project", "owner", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/risk/responseaction/detail.html", {"obj": obj})


@login_required
def rra_edit(request, pk):
    obj = get_object_or_404(RiskResponseAction, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:rra_detail", pk=obj.pk)
    return crud_edit(
        request, model=RiskResponseAction, pk=pk, form_class=RiskResponseActionForm,
        template="projects/risk/responseaction/form.html", success_url="projects:rra_list")


@login_required
@require_POST
def rra_delete(request, pk):
    obj = get_object_or_404(RiskResponseAction, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:rra_detail", pk=obj.pk)
    return crud_delete(request, model=RiskResponseAction, pk=pk, success_url="projects:rra_list")


# -- lifecycle verb -----------------------------------------------------------------------------

@login_required
@require_POST
def rra_complete(request, pk):
    """The action finished. Completing it stamps ``completed_at`` — the only writer of that
    stamp, which is why the status is off the form."""
    obj = get_object_or_404(RiskResponseAction, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.info(request, "That response action is already completed.")
        return redirect("projects:rra_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "completed"
    obj.completed_at = timezone.now()
    obj.save(update_fields=["status", "completed_at", "updated_at"])
    write_audit_log(request.user, obj, "complete",
                    changes={"verb": "complete", "from": previous, "to": obj.status})
    messages.success(request, f"Completed {obj.number}.")
    return redirect("projects:rra_detail", pk=obj.pk)
