"""Projects 7.6 — QualityDefect views: the punch list, its CRUD and the resolve / close /
raise-issue verbs.

The register carries one **pre-scoped lens** — ``?overdue=1``. ``crud_list``'s ``filters`` are
**field lookups only** — ``is_overdue`` is a Python property, so the lens is **pre-scoped here**
before ``crud_list`` paginates, out of the two real columns (the 7.5 ``rsk_list`` idiom).

``qdf_raise_issue`` is the bridge to 7.5's issue register — the exact ``rsk_realize`` idiom: the
defect and the issue are one fact seen from two registers, so the pair is written atomically and
both sides are audited. The defect keeps its quality-native disposition; the issue carries the
RAID treatment. It refuses a second bridge — a defect that already became an issue cannot raise
another one.
"""
from django.db import transaction
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import DefectResolutionForm, QualityDefectForm
from apps.projects.models import DeliverableInspection, QualityDefect
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages, redirect,
                                         render, require_POST, write_audit_log)
from apps.projects.views._helpers import owners, projects

#: Live statuses an un-dispositioned defect can sit in — the ``?overdue=1`` lens reads them.
_LIVE_STATUSES = ("open", "in_progress")

#: The defect→issue severity mapping (contract §2.4): the defect vocabulary's four bands onto the
#: issue register's four bands. Critical maps to itself; a punch-list "major" is a RAID "high".
_ISSUE_SEVERITY = {"critical": "critical", "major": "high", "minor": "medium",
                   "observation": "low"}

_LOCKED_MSG = ("A resolved or closed defect is frozen evidence and cannot be edited or deleted.")


@login_required
def qdf_list(request):
    qs = (QualityDefect.objects.filter(tenant=request.tenant)
          .select_related("project", "wbs_node", "quality_plan", "inspection", "project_issue",
                          "owner", "resolved_by"))
    if request.GET.get("overdue") == "1":
        # ``is_overdue`` is a property, so the lens is reconstructed from its two real columns —
        # a due date that has passed while the defect is still open.
        qs = qs.filter(Q(due_date__lt=timezone.localdate(), status__in=_LIVE_STATUSES))
    return crud_list(
        request, qs, "projects/quality/qualitydefect/list.html",
        search_fields=["number", "title", "description", "root_cause", "resolution_note"],
        filters=[("project", "project_id", True),
                 ("severity", "severity", False),
                 ("status", "status", False),
                 ("disposition", "disposition", False),
                 ("defect_category", "defect_category", False),
                 ("owner", "owner_id", True),
                 ("inspection", "inspection_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "severity_choices": QualityDefect.SEVERITY_CHOICES,
            "status_choices": QualityDefect.STATUS_CHOICES,
            "disposition_choices": QualityDefect.DISPOSITION_CHOICES,
            "defect_category_choices": QualityDefect.DEFECT_CATEGORY_CHOICES,
            "owners": owners(request.tenant),
            "inspections": DeliverableInspection.objects.filter(tenant=request.tenant)
                          .select_related("project").order_by("-created_at"),
        },
    )


@login_required
def qdf_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = QualityDefectForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Defect {obj.number} added to the punch list.")
            return redirect("projects:qdf_detail", pk=obj.pk)
    else:
        form = QualityDefectForm(tenant=request.tenant,
                                 initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/quality/qualitydefect/form.html",
                  {"form": form, "is_edit": False})


@login_required
def qdf_detail(request, pk):
    obj = get_object_or_404(
        QualityDefect.objects.select_related(
            "project", "wbs_node", "quality_plan", "inspection", "project_issue", "owner",
            "resolved_by", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/quality/qualitydefect/detail.html", {
        "obj": obj,
        "resolution_form": DefectResolutionForm(),
    })


@login_required
def qdf_edit(request, pk):
    obj = get_object_or_404(QualityDefect, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qdf_detail", pk=obj.pk)
    return crud_edit(
        request, model=QualityDefect, pk=pk, form_class=QualityDefectForm,
        template="projects/quality/qualitydefect/form.html", success_url="projects:qdf_list")


@login_required
@require_POST
def qdf_delete(request, pk):
    obj = get_object_or_404(QualityDefect, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qdf_detail", pk=obj.pk)
    return crud_delete(request, model=QualityDefect, pk=pk, success_url="projects:qdf_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def qdf_resolve(request, pk):
    """Disposition the defect: root cause + resolution note + the resolver stamps, together.

    Allowed from either live status — an ``open`` defect can be resolved without a separate
    start step, for the same reason ``qrv_report`` accepts ``planned``: ``status`` is OFF the
    model form and there is no start verb, so requiring ``in_progress`` would strand the row.
    """
    obj = get_object_or_404(QualityDefect, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qdf_detail", pk=obj.pk)
    form = DefectResolutionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("projects:qdf_detail", pk=obj.pk)
    previous = obj.status
    obj.root_cause = form.cleaned_data["root_cause"]
    obj.resolution_note = form.cleaned_data["resolution_note"]
    obj.resolved_by = request.user
    obj.resolved_at = timezone.now()
    obj.status = "resolved"
    obj.save(update_fields=["root_cause", "resolution_note", "resolved_by", "resolved_at",
                            "status", "updated_at"])
    write_audit_log(request.user, obj, "resolve",
                    changes={"verb": "resolve", "from": previous, "to": obj.status})
    messages.success(request, f"Resolved {obj.number}.")
    return redirect("projects:qdf_detail", pk=obj.pk)


@login_required
@require_POST
def qdf_close(request, pk):
    """Retire a resolved defect — the only transition out of ``resolved``, stamping nothing but
    the audit trail (the resolver stamps were written by ``qdf_resolve``)."""
    obj = get_object_or_404(QualityDefect, pk=pk, tenant=request.tenant)
    if obj.status != "resolved":
        messages.error(request, "Only a resolved defect can be closed.")
        return redirect("projects:qdf_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "closed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "close",
                    changes={"verb": "close", "from": previous, "to": obj.status})
    messages.success(request, f"Closed {obj.number}.")
    return redirect("projects:qdf_detail", pk=obj.pk)


@login_required
@require_POST
def qdf_raise_issue(request, pk):
    """Raise a 7.5 ``ProjectIssue`` from this defect — the defect→issue bridge (Ruling 2).

    The defect and the issue are one fact seen from two registers, so the pair is written
    atomically and both sides are audited (the ``rsk_realize`` idiom). The issue inherits the
    defect's severity via the band mapping, and the defect keeps its quality-native disposition.
    A defect that already became an issue cannot raise another one.
    """
    from apps.projects.models import ProjectIssue

    obj = get_object_or_404(QualityDefect, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "A resolved or closed defect cannot raise an issue — it is "
                                "already dispositioned.")
        return redirect("projects:qdf_detail", pk=obj.pk)
    if obj.project_issue_id:
        messages.info(request, f"That defect already raised issue {obj.project_issue.number}.")
        return redirect("projects:qdf_detail", pk=obj.pk)
    previous = obj.status
    with transaction.atomic():
        issue = ProjectIssue.objects.create(
            tenant=request.tenant, project=obj.project, wbs_node=obj.wbs_node,
            title=obj.title[:255], description=obj.description,
            severity=_ISSUE_SEVERITY[obj.severity], owner=obj.owner, raised_by=request.user,
            identified_date=timezone.localdate(), created_by=request.user)
        obj.project_issue = issue
        obj.save(update_fields=["project_issue", "updated_at"])
        write_audit_log(request.user, obj, "update",
                        changes={"verb": "raise_issue", "issue": issue.number})
        write_audit_log(request.user, issue, "create")
    messages.success(request, f"Defect {obj.number} raised as issue {issue.number}.")
    return redirect("projects:qdf_detail", pk=obj.pk)
