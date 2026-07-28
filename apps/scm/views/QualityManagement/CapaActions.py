"""SCM 4.9 Quality Management — CapaAction views: the fixed status ladder and its verification.

open → investigating → in_progress → pending_verification → closed, with ``not_effective`` sending
the action BACK to ``investigating`` (QT9's re-open) rather than closing it. There is no rules
engine and no configurable approval matrix — see the model docstring for why that is deferred
rather than half-built.

``capaaction_verify`` is the only ``@tenant_admin_required`` view here: the effectiveness check is
the formal sign-off that the fix worked, and it is the step that closes the record.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_acting_party, _date_window, _item_qs, _need_tenant,
                                     _supplier_parties)
from apps.scm.forms._common import _employee_parties
from apps.scm.models import CapaAction
from apps.scm.forms import CapaActionForm, CapaTaskFormSet, CapaVerificationForm


@login_required
def capaaction_list(request):
    qs = (CapaAction.objects.filter(tenant=request.tenant)
          .select_related("owner", "supplier", "item", "nonconformance", "audit")
          .annotate(open_tasks=Count("tasks", distinct=True,
                                     filter=Q(tasks__status__in=("open", "in_progress"))))
          # Explicit: annotate() sets a GROUP BY, which unsets QuerySet.ordered and makes the
          # paginator warn on every page load (4.8 finding).
          .order_by("-id"))
    qs = _date_window(qs, request.GET, "due_date")
    if request.GET.get("overdue", "").strip() == "yes":
        qs = qs.filter(due_date__lt=timezone.localdate()).exclude(
            status__in=("closed", "cancelled"))
    stats = CapaAction.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status__in=("open", "investigating", "in_progress"))),
        overdue=Count("id", filter=Q(due_date__lt=timezone.localdate())
                      & ~Q(status__in=("closed", "cancelled"))),
        pending_verification=Count("id", filter=Q(status="pending_verification")),
        not_effective=Count("id", filter=Q(effectiveness_result="not_effective")),
    )
    return crud_list(
        request, qs, "scm/quality/capaaction/list.html",
        search_fields=["number", "title", "problem_statement", "root_cause", "notes"],
        filters=[("status", "status", False), ("action_type", "action_type", False),
                 ("priority", "priority", False), ("source", "source", False),
                 ("owner", "owner_id", True), ("supplier", "supplier_id", True),
                 # `items` was already in extra_context; without this tuple the dropdown rendered
                 # but selecting an item did nothing — a filter that silently no-ops is worse than
                 # no filter, because the empty result looks like real data.
                 ("item", "item_id", True)],
        extra_context={
            "status_choices": CapaAction.STATUS_CHOICES,
            "type_choices": CapaAction.ACTION_TYPE_CHOICES,
            "priority_choices": CapaAction.PRIORITY_CHOICES,
            "source_choices": CapaAction.SOURCE_CHOICES,
            "items": _item_qs(request.tenant),
            "owners": _employee_parties(request.tenant),
            "suppliers": _supplier_parties(request.tenant),
            "stats": stats,
        },
    )


@login_required
def capaaction_create(request):
    return _capaaction_form(request, instance=None)


@login_required
def capaaction_edit(request, pk):
    obj = get_object_or_404(CapaAction, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and can no "
                                "longer be edited.")
        return redirect("scm:capaaction_detail", pk=pk)
    return _capaaction_form(request, instance=obj)


def _capaaction_form(request, instance):
    """Header + task formset in ONE transaction.

    ``formset.instance = form.instance`` before ``formset.is_valid()`` is load-bearing: the task
    formset's clean() compares each task's due date against the PARENT's, and on create the formset
    would otherwise be validating against an empty ``CapaAction()`` whose ``due_date`` is None —
    silently no-opping on exactly the path it exists for (the shipped 4.8 BOM-form bug).
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:capaaction_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = CapaActionForm(request.POST, instance=instance, tenant=request.tenant)
        formset = CapaTaskFormSet(request.POST, instance=instance,
                                  form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance
        if form_ok and formset.is_valid():
            with transaction.atomic():
                capa = form.save(commit=False)
                capa.tenant = request.tenant
                capa.save()
                formset.instance = capa
                formset.save()
            write_audit_log(request.user, capa, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{capa.number} saved.")
            return redirect("scm:capaaction_detail", pk=capa.pk)
    else:
        form = CapaActionForm(instance=instance, tenant=request.tenant)
        formset = CapaTaskFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/quality/capaaction/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def capaaction_detail(request, pk):
    obj = get_object_or_404(
        CapaAction.objects.select_related("owner", "supplier", "item", "nonconformance__item",
                                          "audit", "verified_by"),
        pk=pk, tenant=request.tenant)
    tasks = list(obj.tasks.select_related("owner").all())
    return render(request, "scm/quality/capaaction/detail.html", {
        "obj": obj,
        "tasks": tasks,
        # Counted off the rows already in memory — the implement guard asks the same question, and
        # a second aggregate on a page that has just fetched every task is a wasted query.
        "open_task_count": sum(1 for task in tasks
                               if task.status in ("open", "in_progress")),
        "verification_form": CapaVerificationForm(
            tenant=request.tenant,
            initial={"verified_on": timezone.localdate()}),
    })


@login_required
@require_POST
def capaaction_delete(request, pk):
    obj = get_object_or_404(CapaAction, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only an open, investigating or in-progress action can be deleted "
                                "— cancel it instead so its history survives.")
        return redirect("scm:capaaction_detail", pk=pk)
    return crud_delete(request, model=CapaAction, pk=pk, success_url="scm:capaaction_list")


# ============================================================= lifecycle
def _transition(request, pk, *, from_statuses, to_status, verb, stamp=None):
    """Shared status move — lock, re-read INSIDE the transaction, guard, stamp, audit, redirect."""
    with transaction.atomic():
        obj = get_object_or_404(CapaAction.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in from_statuses:
            messages.error(request, f"{obj.number} can't be {verb} from "
                                    f"{obj.get_status_display().lower()}.")
            return redirect("scm:capaaction_detail", pk=pk)
        fields = ["status", "updated_at"]
        obj.status = to_status
        for field, value in (stamp or {}).items():
            setattr(obj, field, value)
            fields.append(field)
        obj.save(update_fields=list(dict.fromkeys(fields)))
    write_audit_log(request.user, obj, "update", {"action": verb, "status": to_status})
    messages.success(request, f"{obj.number} {verb}.")
    return redirect("scm:capaaction_detail", pk=pk)


@login_required
@require_POST
def capaaction_start(request, pk):
    return _transition(request, pk, from_statuses=("open",), to_status="investigating",
                       verb="moved to investigating")


@login_required
@require_POST
def capaaction_progress(request, pk):
    return _transition(request, pk, from_statuses=("investigating",), to_status="in_progress",
                       verb="moved to in progress")


@login_required
@require_POST
def capaaction_cancel(request, pk):
    return _transition(request, pk, from_statuses=("open", "investigating", "in_progress",
                                                   "pending_verification"),
                       to_status="cancelled", verb="cancelled")


@login_required
@require_POST
def capaaction_implement(request, pk):
    """Mark the action implemented and hand it to verification.

    Three refusals, each naming exactly what is missing. They are the whole reason a CAPA register
    beats a task list: an action closed without a root cause, without a date to check it on, or
    with half its plan still to do is an action that will come back.
    """
    with transaction.atomic():
        obj = get_object_or_404(CapaAction.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status != "in_progress":
            messages.error(request, f"{obj.number} can't be implemented from "
                                    f"{obj.get_status_display().lower()}.")
            return redirect("scm:capaaction_detail", pk=pk)
        if not (obj.root_cause or "").strip():
            messages.error(request, "Record the root cause before marking this implemented — a "
                                    "fix without one cannot be verified as effective.")
            return redirect("scm:capaaction_detail", pk=pk)
        if obj.effectiveness_due_date is None:
            messages.error(request, "Set the effectiveness due date before implementing — that is "
                                    "when the fix gets checked.")
            return redirect("scm:capaaction_detail", pk=pk)
        outstanding = obj.tasks.filter(status__in=("open", "in_progress")).count()
        if outstanding:
            messages.error(request, f"{outstanding} task(s) on the action plan are still open.")
            return redirect("scm:capaaction_detail", pk=pk)
        obj.status = "pending_verification"
        obj.implemented_on = timezone.localdate()
        obj.save(update_fields=["status", "implemented_on", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    {"action": "implement", "implemented_on": str(obj.implemented_on)})
    messages.success(request, f"{obj.number} implemented — it is now awaiting an effectiveness "
                              f"check by {obj.effectiveness_due_date:%d %b %Y}.")
    return redirect("scm:capaaction_detail", pk=pk)


@tenant_admin_required
@require_POST
def capaaction_verify(request, pk):
    """The effectiveness sign-off — the only tenant-admin gate in this module.

    ``effective`` closes the record. ``not_effective`` sends it back to ``investigating`` with the
    notes recorded: a fix that did not work is new information about the root cause, not a filing
    error, so the register keeps the action alive rather than closing it with a caveat.
    """
    # Resolve the object — and therefore the TENANT — before touching the form. With the form
    # first, a POST carrying a foreign pk and an invalid payload short-circuited to a redirect
    # without the tenant check ever running: it disclosed nothing and changed nothing, but the
    # tenant boundary should not be reachable-past on any path. Cheap: this action is a
    # human-rate admin sign-off, and the authoritative read is still the locked one below.
    get_object_or_404(CapaAction.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = CapaVerificationForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("scm:capaaction_detail", pk=pk)
    result = form.cleaned_data["effectiveness_result"]
    verified_by = form.cleaned_data.get("verified_by") or _acting_party(request)
    verified_on = form.cleaned_data.get("verified_on") or timezone.localdate()
    notes = (form.cleaned_data.get("verification_notes") or "").strip()
    with transaction.atomic():
        obj = get_object_or_404(CapaAction.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status != "pending_verification":
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — only an "
                                    "action awaiting verification can be signed off.")
            return redirect("scm:capaaction_detail", pk=pk)
        obj.effectiveness_result = result
        obj.verified_by = verified_by
        obj.verified_on = verified_on
        obj.verification_notes = notes
        fields = ["effectiveness_result", "verified_by", "verified_on", "verification_notes",
                  "status", "updated_at"]
        if result == "effective":
            obj.status = "closed"
            obj.closed_on = timezone.now()
            fields.append("closed_on")
        else:
            obj.status = "investigating"
        obj.save(update_fields=list(dict.fromkeys(fields)))
    write_audit_log(request.user, obj, "update",
                    {"action": "verify", "effectiveness_result": result, "status": obj.status})
    if result == "effective":
        messages.success(request, f"{obj.number} verified effective and closed.")
    else:
        messages.success(request, f"{obj.number} was not effective — it is back at investigating "
                                  "with the verification notes recorded.")
    return redirect("scm:capaaction_detail", pk=pk)
