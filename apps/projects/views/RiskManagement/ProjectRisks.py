"""Projects 7.5 — ProjectRisk views: the risk register, its CRUD and its three lifecycle verbs.

The register is the page four of the five 7.5 bullets land on, so it carries the most derived
lenses. ``crud_list``'s ``filters`` are **field lookups only** — ``score``, ``severity_band`` and
``is_review_overdue`` are Python properties, so a ``?band=`` / ``?review_due=`` lens cannot be a
filter spec. Each one is therefore **pre-scoped here**, before ``crud_list`` paginates, and built
out of real columns so the database does the work.

Verbs (POST-only, GET → 405): ``realize`` (the risk happened — and mints the linked ``ProjectIssue``,
the risk→issue bridge), ``close`` (retire it, capturing the lesson) and ``reopen`` (admin-only; a
closed register row is evidence, so reopening it is a privileged act).
"""
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import ProjectRiskForm, RiskClosureForm
from apps.projects.models import ProjectRisk
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import owners, projects

BAND_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")]

#: The statuses a risk can still be acted on from — everything but the two terminal ones.
_LIVE_STATUSES = ("identified", "assessing", "response_planned", "monitoring")

_LOCKED_MSG = ("A realized or closed risk is frozen evidence and cannot be edited or deleted — "
               "reopen it (admins) to make changes.")


def _band_q(band):
    """The ``?band=`` lens as a real-column ``Q``.

    ``severity_band`` is a property, so the band is reconstructed from the ``(probability, impact)``
    pairs whose product falls inside that band's range. Exact, database-side, and it cannot drift
    from :attr:`ProjectRisk.SEVERITY_BANDS` because it reads it.
    """
    bounds = ProjectRisk.SEVERITY_BANDS.get(band)
    if not bounds:
        return None
    low, high = bounds
    cond = Q()
    for probability in range(1, 6):
        for impact in range(1, 6):
            if low <= probability * impact <= high:
                cond |= Q(probability=probability, impact=impact)
    return cond


@login_required
def rsk_list(request):
    qs = (ProjectRisk.objects.filter(tenant=request.tenant)
          .select_related("project", "wbs_node", "owner", "identified_by", "contingency_account"))
    band = request.GET.get("band", "").strip()
    band_q = _band_q(band) if band else None
    if band_q is not None:
        qs = qs.filter(band_q)
    if request.GET.get("review_due") == "1" or request.GET.get("overdue") == "1":
        qs = qs.filter(review_date__lt=timezone.localdate(), status__in=_LIVE_STATUSES)
    if request.GET.get("top") == "1":
        # ``score`` is a property, so the register orders by its two columns (a stable DB ordering
        # that puts the same rows on top) — the top-risk list on risk_monitoring uses the same one.
        qs = qs.order_by("-probability", "-impact", "-cost_impact", "-id")
    return crud_list(
        request, qs, "projects/risk/projectrisk/list.html",
        search_fields=["number", "title", "description", "cause", "effect"],
        filters=[("project", "project_id", True),
                 ("category", "category", False),
                 ("risk_type", "risk_type", False),
                 ("status", "status", False),
                 ("owner", "owner_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "category_choices": ProjectRisk.CATEGORY_CHOICES,
            "risk_type_choices": ProjectRisk.RISK_TYPE_CHOICES,
            "status_choices": ProjectRisk.STATUS_CHOICES,
            "strategy_choices": ProjectRisk.RESPONSE_STRATEGY_CHOICES,
            "band_choices": BAND_CHOICES,
            "owners": owners(request.tenant),
        },
    )


@login_required
def rsk_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectRiskForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            if not obj.identified_by_id:
                obj.identified_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Risk {obj.number} logged.")
            return redirect("projects:rsk_detail", pk=obj.pk)
    else:
        form = ProjectRiskForm(tenant=request.tenant,
                               initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/risk/projectrisk/form.html",
                  {"form": form, "is_edit": False})


@login_required
def rsk_detail(request, pk):
    obj = get_object_or_404(
        ProjectRisk.objects.select_related(
            "project", "wbs_node", "owner", "identified_by", "contingency_account", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/risk/projectrisk/detail.html", {
        "obj": obj,
        "response_actions": obj.response_actions.select_related("owner").order_by("due_date", "id"),
        "linked_issues": obj.issues.select_related("owner").order_by("-created_at", "-id"),
    })


@login_required
def rsk_edit(request, pk):
    obj = get_object_or_404(ProjectRisk, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:rsk_detail", pk=obj.pk)
    return crud_edit(
        request, model=ProjectRisk, pk=pk, form_class=ProjectRiskForm,
        template="projects/risk/projectrisk/form.html", success_url="projects:rsk_list")


@login_required
@require_POST
def rsk_delete(request, pk):
    obj = get_object_or_404(ProjectRisk, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:rsk_detail", pk=obj.pk)
    return crud_delete(request, model=ProjectRisk, pk=pk, success_url="projects:rsk_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def rsk_realize(request, pk):
    """The risk happened. Realizing it mints the linked ``ProjectIssue`` — the one place a risk
    becomes an issue, so the two registers cannot drift about which risk materialized."""
    from apps.projects.models import ProjectIssue

    obj = get_object_or_404(ProjectRisk, pk=pk, tenant=request.tenant)
    if obj.status == "closed":
        messages.error(request, "A closed risk cannot be realized — reopen it first.")
        return redirect("projects:rsk_detail", pk=obj.pk)
    if obj.status == "realized":
        messages.info(request, "That risk is already realized.")
        return redirect("projects:rsk_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "realized"
    obj.save(update_fields=["status", "updated_at"])
    issue = ProjectIssue.objects.create(
        tenant=request.tenant, project=obj.project, wbs_node=obj.wbs_node, risk=obj,
        title=obj.title[:255], description=obj.effect or obj.description,
        # ``severity_band``'s four values are exactly SEVERITY_CHOICES' four values.
        severity=obj.severity_band, owner=obj.owner, raised_by=request.user,
        identified_date=timezone.localdate(), created_by=request.user)
    write_audit_log(request.user, obj, "realize",
                    changes={"verb": "realize", "from": previous, "to": obj.status,
                             "issue": issue.number})
    write_audit_log(request.user, issue, "create")
    messages.success(request, f"Risk {obj.number} realized — issue {issue.number} raised.")
    return redirect("projects:rsk_detail", pk=obj.pk)


@login_required
@require_POST
def rsk_close(request, pk):
    """Retire the risk, capturing the lesson it leaves behind. Allowed from any live status —
    a risk nobody responded to can still be closed, and the lesson is the point."""
    obj = get_object_or_404(ProjectRisk, pk=pk, tenant=request.tenant)
    if obj.status == "closed":
        messages.info(request, "That risk is already closed.")
        return redirect("projects:rsk_detail", pk=obj.pk)
    form = RiskClosureForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Could not close the risk — please retry.")
        return redirect("projects:rsk_detail", pk=obj.pk)
    previous = obj.status
    lesson = form.cleaned_data.get("lessons_learned", "").strip()
    if lesson:
        obj.lessons_learned = lesson
    obj.status = "closed"
    obj.closed_at = timezone.now()
    obj.save(update_fields=["status", "closed_at", "lessons_learned", "updated_at"])
    write_audit_log(request.user, obj, "close",
                    changes={"verb": "close", "from": previous, "to": obj.status})
    messages.success(request, f"Closed {obj.number}.")
    return redirect("projects:rsk_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def rsk_reopen(request, pk):
    """Admin-only: a closed register row is evidence, so putting it back on the register is a
    privileged act."""
    obj = get_object_or_404(ProjectRisk, pk=pk, tenant=request.tenant)
    if obj.status != "closed":
        messages.error(request, "Only a closed risk can be reopened.")
        return redirect("projects:rsk_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "monitoring"
    obj.closed_at = None
    obj.save(update_fields=["status", "closed_at", "updated_at"])
    write_audit_log(request.user, obj, "reopen",
                    changes={"verb": "reopen", "from": previous, "to": obj.status})
    messages.success(request, f"Reopened {obj.number}.")
    return redirect("projects:rsk_detail", pk=obj.pk)
