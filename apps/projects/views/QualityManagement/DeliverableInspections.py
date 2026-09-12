"""Projects 7.6 — DeliverableInspection views: the inspection register, its CRUD and the
record / accept / reject lifecycle verbs.

The register carries one **pre-scoped lens** — ``?overdue=1``. ``crud_list``'s ``filters`` are
**field lookups only** — ``is_overdue`` is a Python property, so the lens cannot be a filter spec;
it is **pre-scoped here**, before ``crud_list`` paginates, out of the three real columns
(``planned_date``, ``inspected_date``, ``status``) so the database does the work (the 7.5
``rsk_list`` idiom).

The decision verbs keep the evidence order the model's ``is_locked`` implies: an inspection is
**recorded** first (``qci_record`` — result + inspected date, row stays live) and only then
**decided** (``qci_accept`` / ``qci_reject`` — the decision moves ``usage_decision`` AND the status
to a terminal together, which is what freezes the row). ``qci_record`` therefore never writes a
terminal status: a pass recorded on a row still awaiting its acceptance decision must not lock the
row out of that decision.
"""
from datetime import date

from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import DeliverableInspectionForm, InspectionAcceptanceForm
from apps.projects.models import DeliverableInspection
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages, redirect,
                                         render, require_POST, write_audit_log)
from apps.projects.views._helpers import owners, projects

#: Live statuses an un-executed inspection can sit in — the ``?overdue=1`` lens reads them.
_LIVE_STATUSES = ("planned", "in_progress")

_LOCKED_MSG = ("An inspection with a recorded decision or a terminal status is frozen evidence "
               "and cannot be edited or deleted.")


@login_required
def qci_list(request):
    qs = (DeliverableInspection.objects.filter(tenant=request.tenant)
          .select_related("project", "wbs_node", "quality_plan", "milestone", "inspector",
                          "accepted_by", "accepted_by_party"))
    if request.GET.get("overdue") == "1":
        # ``is_overdue`` is a property, so the lens is reconstructed from its real columns — a
        # planned date that has passed while the inspection has not been executed.
        qs = qs.filter(Q(planned_date__lt=timezone.localdate(),
                         inspected_date__isnull=True,
                         status__in=_LIVE_STATUSES))
    return crud_list(
        request, qs, "projects/quality/deliverableinspection/list.html",
        search_fields=["number", "title", "description", "findings"],
        filters=[("project", "project_id", True),
                 ("inspection_type", "inspection_type", False),
                 ("result", "result", False),
                 ("usage_decision", "usage_decision", False),
                 ("status", "status", False),
                 ("inspector", "inspector_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "inspection_type_choices": DeliverableInspection.INSPECTION_TYPE_CHOICES,
            "result_choices": DeliverableInspection.RESULT_CHOICES,
            "usage_decision_choices": DeliverableInspection.USAGE_DECISION_CHOICES,
            "status_choices": DeliverableInspection.STATUS_CHOICES,
            "owners": owners(request.tenant),
        },
    )


@login_required
def qci_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = DeliverableInspectionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Inspection {obj.number} created.")
            return redirect("projects:qci_detail", pk=obj.pk)
    else:
        form = DeliverableInspectionForm(
            tenant=request.tenant, initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/quality/deliverableinspection/form.html",
                  {"form": form, "is_edit": False})


@login_required
def qci_detail(request, pk):
    obj = get_object_or_404(
        DeliverableInspection.objects.select_related(
            "project", "wbs_node", "quality_plan", "milestone", "inspector", "accepted_by",
            "accepted_by_party", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/quality/deliverableinspection/detail.html", {
        "obj": obj,
        "defects": obj.defects.select_related("owner"),
        "accept_form": InspectionAcceptanceForm(tenant=request.tenant),
        # The record panel's select reads the model's own vocabulary — the contract's three
        # context keys plus this one, without which the panel would hardcode the choices.
        "result_choices": DeliverableInspection.RESULT_CHOICES,
    })


@login_required
def qci_edit(request, pk):
    obj = get_object_or_404(DeliverableInspection, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qci_detail", pk=obj.pk)
    return crud_edit(
        request, model=DeliverableInspection, pk=pk, form_class=DeliverableInspectionForm,
        template="projects/quality/deliverableinspection/form.html", success_url="projects:qci_list")


@login_required
@require_POST
def qci_delete(request, pk):
    obj = get_object_or_404(DeliverableInspection, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qci_detail", pk=obj.pk)
    return crud_delete(request, model=DeliverableInspection, pk=pk, success_url="projects:qci_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def qci_record(request, pk):
    """Record the execution: the result and the inspected date, keeping the row live.

    The status moves to ``in_progress`` (from ``planned``/``on_hold``) and never to a terminal —
    the terminal statuses are written together with the usage decision, and writing one early
    would let ``is_locked`` lock the row out of the decision it is still owed.
    """
    obj = get_object_or_404(DeliverableInspection, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qci_detail", pk=obj.pk)
    result = request.POST.get("result", "")
    if result not in dict(DeliverableInspection.RESULT_CHOICES) or result == "pending":
        messages.error(request, "Record a result of pass, fail, conditional or not applicable.")
        return redirect("projects:qci_detail", pk=obj.pk)
    inspected_date = timezone.localdate()
    raw_date = (request.POST.get("inspected_date") or "").strip()
    if raw_date:
        try:
            inspected_date = date.fromisoformat(raw_date)
        except ValueError:
            messages.error(request, "The inspected date must be an ISO date (YYYY-MM-DD).")
            return redirect("projects:qci_detail", pk=obj.pk)
    previous = obj.status
    obj.result = result
    obj.inspected_date = inspected_date
    if obj.status in ("planned", "on_hold"):
        obj.status = "in_progress"
    obj.save(update_fields=["result", "inspected_date", "status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "record", "from": previous, "to": obj.status,
                             "result": result})
    messages.success(request, f"Recorded {obj.get_result_display()} on {obj.number}.")
    return redirect("projects:qci_detail", pk=obj.pk)


@login_required
@require_POST
def qci_accept(request, pk):
    """Take the acceptance decision: usage decision + acceptor stamps + ``passed``, together.

    Requires a recorded result first — accepting an inspection that has not been executed would
    create an acceptance record with no evidence behind it. The decision and the status move in
    one save, which is the moment ``is_locked`` freezes the row.
    """
    obj = get_object_or_404(DeliverableInspection, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qci_detail", pk=obj.pk)
    if obj.result == "pending":
        messages.error(request, "Record the inspection result before taking the acceptance "
                                "decision.")
        return redirect("projects:qci_detail", pk=obj.pk)
    form = InspectionAcceptanceForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("projects:qci_detail", pk=obj.pk)
    party = form.cleaned_data["accepted_by_party"]
    if party is not None and party.tenant_id != request.tenant.pk:
        # The queryset already scopes the dropdown; this is the crafted-POST re-check behind it.
        messages.error(request, "That party belongs to another workspace.")
        return redirect("projects:qci_detail", pk=obj.pk)
    previous = obj.usage_decision
    obj.usage_decision = form.cleaned_data["usage_decision"]
    obj.accepted_by = request.user
    obj.accepted_by_party = party
    obj.accepted_at = timezone.now()
    obj.acceptance_note = form.cleaned_data["acceptance_note"]
    obj.status = "passed"
    obj.save(update_fields=["usage_decision", "accepted_by", "accepted_by_party", "accepted_at",
                            "acceptance_note", "status", "updated_at"])
    write_audit_log(request.user, obj, "accept",
                    changes={"verb": "accept", "from": previous, "to": obj.usage_decision})
    messages.success(request, f"Accepted {obj.number} — {obj.get_usage_decision_display()}.")
    return redirect("projects:qci_detail", pk=obj.pk)


@login_required
@require_POST
def qci_reject(request, pk):
    """Reject the deliverable: ``usage_decision="reject"`` + ``failed``, together — the mirror of
    ``qci_accept``, with the same recorded-result precondition."""
    obj = get_object_or_404(DeliverableInspection, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:qci_detail", pk=obj.pk)
    if obj.result == "pending":
        messages.error(request, "Record the inspection result before taking the acceptance "
                                "decision.")
        return redirect("projects:qci_detail", pk=obj.pk)
    previous = obj.usage_decision
    obj.usage_decision = "reject"
    obj.status = "failed"
    obj.save(update_fields=["usage_decision", "status", "updated_at"])
    write_audit_log(request.user, obj, "reject",
                    changes={"verb": "reject", "from": previous, "to": obj.usage_decision})
    messages.success(request, f"Rejected {obj.number} — the punch list carries what must be fixed.")
    return redirect("projects:qci_detail", pk=obj.pk)
