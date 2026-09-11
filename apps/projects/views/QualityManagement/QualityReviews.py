"""Projects 7.6 — QualityReview views: the review register, its CRUD and its two lifecycle verbs.

The register carries three **pre-scoped lenses** — ``?kind=assurance``, ``?kind=improvement`` and
``?overdue=1``. ``crud_list``'s ``filters`` are **field lookups only** — ``is_improvement`` and
``is_improvement_overdue`` are Python properties, so a ``?kind=`` or ``?overdue=`` lens cannot be a
filter spec. Each is therefore **pre-scoped here**, before ``crud_list`` paginates, and built out of
real columns so the database does the work (the 7.5 ``rsk_list`` idiom). An **unrecognised** ``kind``
narrows nothing: a stale bookmark or a hand-edited URL is not a narrowing request, so the full
register renders rather than an empty page.

Verbs (POST-only, GET → 405): ``report`` (an in-progress review is reported) and ``close`` (a
reported review is retired, stamping ``closed_at``). A closed or cancelled row is frozen evidence,
so ``qrv_edit``/``qrv_delete`` refuse it.
"""
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import QualityReviewForm
from apps.projects.models import QualityReview
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import owners, projects

#: The bullet-2 assurance half and the bullet-4 improvement half of the shared review vocabulary.
_ASSURANCE_TYPES = ("methodology_review", "compliance_check", "gate_review")
_IMPROVEMENT_TYPES = ("kaizen_event", "retrospective", "maturity_assessment")

#: The improvement statuses that can still be overdue — everything but the two terminals.
_OPEN_IMPROVEMENT_STATUSES = ("planned", "in_progress")

_LOCKED_MSG = ("A closed or cancelled review is frozen evidence and cannot be edited or deleted.")


@login_required
def qrv_list(request):
    qs = (QualityReview.objects.filter(tenant=request.tenant)
          .select_related("project", "wbs_node", "quality_plan", "reviewer", "improvement_owner"))
    # ``is_improvement`` is a property, so the lens is reconstructed from the real ``review_type``
    # column here. An unrecognised ``kind`` narrows nothing — never an empty page for a stale URL.
    kind = request.GET.get("kind")
    if kind == "assurance":
        qs = qs.filter(Q(review_type__in=_ASSURANCE_TYPES))
    elif kind == "improvement":
        qs = qs.filter(Q(review_type__in=_IMPROVEMENT_TYPES))
    if request.GET.get("overdue") == "1":
        # ``is_improvement_overdue`` is a property, so the lens is reconstructed from its two real
        # columns — a due date that has passed while the improvement action is still open.
        qs = qs.filter(Q(improvement_due_date__lt=timezone.localdate(),
                         improvement_status__in=_OPEN_IMPROVEMENT_STATUSES))
    return crud_list(
        request, qs, "projects/quality/qualityreview/list.html",
        search_fields=["number", "title", "scope", "findings", "improvement_action"],
        filters=[("project", "project_id", True),
                 ("review_type", "review_type", False),
                 ("status", "status", False),
                 ("improvement_status", "improvement_status", False),
                 ("reviewer", "reviewer_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "review_type_choices": QualityReview.REVIEW_TYPE_CHOICES,
            "status_choices": QualityReview.STATUS_CHOICES,
            "improvement_status_choices": QualityReview.IMPROVEMENT_STATUS_CHOICES,
            "owners": owners(request.tenant),
        },
    )


@login_required
def qrv_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = QualityReviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Quality review {obj.number} created.")
            return redirect("projects:qrv_detail", pk=obj.pk)
    else:
        form = QualityReviewForm(tenant=request.tenant,
                                 initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/quality/qualityreview/form.html",
                  {"form": form, "is_edit": False})


@login_required
def qrv_detail(request, pk):
    obj = get_object_or_404(
        QualityReview.objects.select_related(
            "project", "wbs_node", "quality_plan", "reviewer", "improvement_owner", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/quality/qualityreview/detail.html", {"obj": obj})


@login_required
def qrv_edit(request, pk):
    obj = get_object_or_404(QualityReview, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qrv_detail", pk=obj.pk)
    return crud_edit(
        request, model=QualityReview, pk=pk, form_class=QualityReviewForm,
        template="projects/quality/qualityreview/form.html", success_url="projects:qrv_list")


@login_required
@require_POST
def qrv_delete(request, pk):
    obj = get_object_or_404(QualityReview, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qrv_detail", pk=obj.pk)
    return crud_delete(request, model=QualityReview, pk=pk, success_url="projects:qrv_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def qrv_report(request, pk):
    """Report a live review — the findings are captured, so the row becomes evidence.

    A review is reported from ``planned`` or ``in_progress``: ``status`` is OFF the model form and
    there is no separate start verb, so accepting only ``in_progress`` here would strand every
    review on ``planned`` (nothing else writes that transition)."""
    obj = get_object_or_404(QualityReview, pk=pk, tenant=request.tenant)
    if obj.status not in ("planned", "in_progress"):
        messages.error(request, "Only a planned or in-progress review can be reported.")
        return redirect("projects:qrv_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "reported"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "report", "from": previous, "to": obj.status})
    messages.success(request, f"Reported {obj.number}.")
    return redirect("projects:qrv_detail", pk=obj.pk)


@login_required
@require_POST
def qrv_close(request, pk):
    """Retire a reported review, stamping ``closed_at`` — the only writer of that stamp."""
    obj = get_object_or_404(QualityReview, pk=pk, tenant=request.tenant)
    if obj.status != "reported":
        messages.error(request, "Only a reported review can be closed.")
        return redirect("projects:qrv_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "closed"
    obj.closed_at = timezone.now()
    obj.save(update_fields=["status", "closed_at", "updated_at"])
    write_audit_log(request.user, obj, "close",
                    changes={"verb": "close", "from": previous, "to": obj.status})
    messages.success(request, f"Closed {obj.number}.")
    return redirect("projects:qrv_detail", pk=obj.pk)
