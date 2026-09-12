"""Projects 7.2 — ScheduleBaseline views: freeze, what-if, promote.

State guards mirror 7.1's attested records (an approved charter, an attested kickoff): a FROZEN
baseline refuses edit and delete with a message, because the version-control promise of bullet 5
is that a frozen schedule cannot be quietly rewritten. What-if scenarios stay editable until
``bsl_promote`` freezes one in place of the live baseline.
"""
from django.db import transaction

from apps.projects.forms import BaselineForm
from apps.projects.models import ScheduleBaseline
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import projects

_FROZEN_MSG = ("A frozen baseline cannot be changed — freeze a new one (or promote a what-if "
               "scenario) instead.")


@login_required
def bsl_list(request):
    qs = (ScheduleBaseline.objects.filter(tenant=request.tenant)
          .select_related("project"))
    return crud_list(
        request, qs, "projects/planning/schedulebaseline/list.html",
        search_fields=["name", "number", "strategy_note", "note"],
        filters=[("project", "project_id", True),
                 ("baseline_type", "baseline_type", False)],
        extra_context={
            "baseline_type_choices": ScheduleBaseline.BASELINE_TYPE_CHOICES,
            "projects": projects(request.tenant),
        },
    )


@login_required
def bsl_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = BaselineForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if obj.baseline_type == "baseline":
                # Born frozen: snapshot the live plan, then take over as the active baseline.
                obj.freeze_snapshot()
                obj.is_active = True
            with transaction.atomic():
                if obj.is_active:
                    ScheduleBaseline.objects.filter(
                        tenant=obj.tenant_id, project=obj.project_id, is_active=True
                    ).exclude(pk=obj.pk).update(is_active=False)
                obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Baseline {obj.number} created.")
            return redirect("projects:bsl_detail", pk=obj.pk)
    else:
        form = BaselineForm(tenant=request.tenant,
                            initial={"project": request.GET.get("project", "")})
    return render(request, "projects/planning/schedulebaseline/form.html",
                  {"form": form, "is_edit": False})


@login_required
def bsl_detail(request, pk):
    obj = get_object_or_404(
        ScheduleBaseline.objects.select_related("project"), pk=pk, tenant=request.tenant)
    return render(request, "projects/planning/schedulebaseline/detail.html", {"obj": obj})


@login_required
def bsl_edit(request, pk):
    obj = get_object_or_404(ScheduleBaseline, pk=pk, tenant=request.tenant)
    if obj.is_frozen:
        messages.error(request, _FROZEN_MSG)
        return redirect("projects:bsl_detail", pk=obj.pk)
    return crud_edit(
        request, model=ScheduleBaseline, pk=pk, form_class=BaselineForm,
        template="projects/planning/schedulebaseline/form.html", success_url="projects:bsl_list")


@login_required
@require_POST
def bsl_delete(request, pk):
    obj = get_object_or_404(ScheduleBaseline, pk=pk, tenant=request.tenant)
    if obj.is_frozen:
        messages.error(request, _FROZEN_MSG)
        return redirect("projects:bsl_detail", pk=obj.pk)
    return crud_delete(request, model=ScheduleBaseline, pk=pk,
                       success_url="projects:bsl_list")


# -- baseline verbs ------------------------------------------------------------------------------
#
# Both are TENANT-ADMIN gated: activating or promoting a baseline is the decision the kickoff
# ceremony's acknowledgement (7.1's pko_mark_baseline_set) attests to. Only POST can reach them.

@login_required
@require_POST
@tenant_admin_required
def bsl_activate(request, pk):
    obj = get_object_or_404(ScheduleBaseline, pk=pk, tenant=request.tenant)
    if obj.baseline_type != "baseline":
        messages.error(request, "Only a frozen baseline can be activated — promote the "
                                "what-if scenario first.")
        return redirect("projects:bsl_detail", pk=obj.pk)
    if obj.is_active:
        messages.info(request, "That baseline is already the active one.")
        return redirect("projects:bsl_detail", pk=obj.pk)
    with transaction.atomic():
        ScheduleBaseline.objects.filter(
            tenant=obj.tenant_id, project=obj.project_id, is_active=True
        ).exclude(pk=obj.pk).update(is_active=False)
        obj.is_active = True
        obj.save(update_fields=["is_active", "updated_at"])
    write_audit_log(request.user, obj, "activate",
                    changes={"verb": "activate", "project": str(obj.project)})
    messages.success(request, f"Baseline {obj.number} is now the active baseline.")
    return redirect("projects:bsl_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def bsl_promote(request, pk):
    obj = get_object_or_404(ScheduleBaseline, pk=pk, tenant=request.tenant)
    if obj.baseline_type != "what_if":
        messages.info(request, "That row is already a frozen baseline.")
        return redirect("projects:bsl_detail", pk=obj.pk)
    # Freeze in place: snapshot the plan AS IT IS NOW under THIS name, stamp today, take over.
    obj.baseline_type = "baseline"
    obj.freeze_snapshot()
    obj.is_active = True
    with transaction.atomic():
        ScheduleBaseline.objects.filter(
            tenant=obj.tenant_id, project=obj.project_id, is_active=True
        ).exclude(pk=obj.pk).update(is_active=False)
        obj.save()
    write_audit_log(request.user, obj, "promote",
                    changes={"verb": "promote", "project": str(obj.project)})
    messages.success(request, f"What-if {obj.number} promoted to the active baseline.")
    return redirect("projects:bsl_detail", pk=obj.pk)
