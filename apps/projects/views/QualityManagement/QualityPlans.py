"""Projects 7.6 — QualityPlan views: the planning register, its CRUD and its two lifecycle verbs.

The register carries the planning lens and the review-due lens. ``crud_list``'s ``filters`` are
**field lookups only** — ``is_review_overdue`` is a Python property, so a ``?review_due=`` lens
cannot be a filter spec. It is therefore **pre-scoped here**, before ``crud_list`` paginates, and
built out of real columns so the database does the work (the 7.5 ``rsk_list`` idiom).

Verbs (POST-only, GET → 405): ``approve`` (a draft plan is activated, stamping the approver and the
moment) and ``supersede`` (admin-only — an active plan is retired in favour of a new one, so
retiring it is a privileged act; L27).
"""
from apps.core.crud import as_db_int
from apps.projects.forms import QualityPlanForm
from apps.projects.models import QualityPlan
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import owners, projects

_LOCKED_MSG = ("A superseded or closed plan is frozen evidence and cannot be edited or deleted — "
               "approve a new plan to supersede it.")


@login_required
def qpl_list(request):
    qs = (QualityPlan.objects.filter(tenant=request.tenant)
          .select_related("project", "wbs_node", "source_risk", "owner", "approved_by"))
    # ``is_review_overdue`` is a property, so the lens is reconstructed from real columns here.
    if request.GET.get("review_due") == "1" or request.GET.get("overdue") == "1":
        qs = qs.filter(planned_review_date__lt=timezone.localdate(),
                       status__in=("draft", "active"))
    return crud_list(
        request, qs, "projects/quality/qualityplan/list.html",
        search_fields=["number", "title", "description", "acceptance_criteria",
                       "standard_reference"],
        filters=[("project", "project_id", True),
                 ("status", "status", False),
                 ("verification_method", "verification_method", False),
                 ("owner", "owner_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "status_choices": QualityPlan.STATUS_CHOICES,
            "verification_method_choices": QualityPlan.VERIFICATION_METHOD_CHOICES,
            "owners": owners(request.tenant),
        },
    )


@login_required
def qpl_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = QualityPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Quality plan {obj.number} created.")
            return redirect("projects:qpl_detail", pk=obj.pk)
    else:
        form = QualityPlanForm(tenant=request.tenant,
                               initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/quality/qualityplan/form.html",
                  {"form": form, "is_edit": False})


@login_required
def qpl_detail(request, pk):
    obj = get_object_or_404(
        QualityPlan.objects.select_related(
            "project", "wbs_node", "source_risk", "owner", "approved_by", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/quality/qualityplan/detail.html", {
        "obj": obj,
        "linked_reviews": obj.reviews.select_related("reviewer"),
        "linked_inspections": obj.inspections.select_related("inspector", "milestone"),
        "linked_defects": obj.defects.select_related("owner"),
    })


@login_required
def qpl_edit(request, pk):
    obj = get_object_or_404(QualityPlan, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qpl_detail", pk=obj.pk)
    return crud_edit(
        request, model=QualityPlan, pk=pk, form_class=QualityPlanForm,
        template="projects/quality/qualityplan/form.html", success_url="projects:qpl_list")


@login_required
@require_POST
def qpl_delete(request, pk):
    obj = get_object_or_404(QualityPlan, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qpl_detail", pk=obj.pk)
    return crud_delete(request, model=QualityPlan, pk=pk, success_url="projects:qpl_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def qpl_approve(request, pk):
    """Activate a draft plan, stamping the approver and the moment in the same request."""
    obj = get_object_or_404(QualityPlan, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft plan can be approved.")
        return redirect("projects:qpl_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "active"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "approve", "from": previous, "to": obj.status})
    messages.success(request, f"Approved {obj.number}.")
    return redirect("projects:qpl_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def qpl_supersede(request, pk):
    """Admin-only: an active plan is retired in favour of a new one, so retiring it is a
    privileged act."""
    obj = get_object_or_404(QualityPlan, pk=pk, tenant=request.tenant)
    if obj.status != "active":
        messages.error(request, "Only an active plan can be superseded.")
        return redirect("projects:qpl_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "superseded"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "supersede", "from": previous, "to": obj.status})
    messages.success(request, f"Superseded {obj.number}.")
    return redirect("projects:qpl_detail", pk=obj.pk)
