"""Procurement 6.8 Contract Management — ContractMilestone views.

**Obligation & Milestone Management**: a cross-contract register of deliverables,
payment milestones and penalties, with the complete/waive verbs. Status never moves
through the edit form — only through the verbs, which stamp who/when together with
the audit row.
"""
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.crud import crud_list

from apps.procurement.forms import ContractMilestoneForm
from apps.procurement.models import ContractMilestone
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import SupplierContract

KIND_CHOICES = [value for value in ContractMilestone.KIND_CHOICES]
STATUS_CHOICES = [value for value in ContractMilestone.STATUS_CHOICES]


def _safe_next(request):
    """POST ``next`` honoured only as a same-host target. Scheme-relative URLs
    ("//evil.com") and absolute URLs fall back to the caller's default — a bare
    ``redirect(request.POST.get(...))`` here would be an open redirect."""
    candidate = request.POST.get("next")
    if candidate and url_has_allowed_host_and_scheme(
            candidate, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return candidate
    return None


@login_required
def milestone_list(request):
    qs = (ContractMilestone.objects.filter(tenant=request.tenant)
          .select_related("contract"))
    kind = request.GET.get("kind", "")
    if kind:
        qs = qs.filter(kind=kind)
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    lens = request.GET.get("lens", "")
    if lens == "overdue":
        today = timezone.localdate()
        qs = (qs.filter(status__in=ContractMilestone.OPEN_STATUSES)
              .filter(due_date__lt=today))
    return crud_list(
        request, qs, "procurement/contractsmanagement/milestones/list.html",
        search_fields=["number", "title", "contract__number"],
        filters=[("status", "status", False)],
        extra_context={"kind_choices": KIND_CHOICES, "status_choices": STATUS_CHOICES,
                       "lens": lens},
    )


def _get_milestone(request, pk):
    return get_object_or_404(
        ContractMilestone.objects.select_related("contract"),
        pk=pk, tenant=request.tenant)


def _milestone_form(request, instance, contract=None):
    """Create/edit. On create the contract comes from ?contract= (or POST); on edit it
    is fixed — moving a milestone between agreements would corrupt their histories."""
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before adding milestones.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if not is_edit:
        contract_pk = request.POST.get("contract") or request.GET.get("contract")
        contract = get_object_or_404(SupplierContract,
                                     pk=contract_pk or 0, tenant=request.tenant)
    if request.method == "POST":
        form = ContractMilestoneForm(request.POST, instance=instance,
                                     tenant=request.tenant)
        if form.is_valid():
            milestone = form.save(commit=False)
            milestone.tenant = request.tenant
            if not is_edit:
                milestone.contract = contract
            milestone.save()
            write_audit_log(request.user, milestone, "update" if is_edit else "create")
            messages.success(request, f"Milestone {milestone.number} saved.")
            return redirect("procurement:milestone_list")
    else:
        form = ContractMilestoneForm(instance=instance, tenant=request.tenant)
    return render(request, "procurement/contractsmanagement/milestones/form.html",
                  {"form": form, "obj": instance, "is_edit": is_edit,
                   "contract": contract})


@login_required
def milestone_create(request):
    return _milestone_form(request, None)


@login_required
def milestone_edit(request, pk):
    obj = _get_milestone(request, pk)
    if obj.status not in ContractMilestone.OPEN_STATUSES:
        messages.error(request,
                       f"This milestone is {obj.get_status_display().lower()} and its "
                       f"terms are frozen.")
        return redirect("procurement:milestone_list")
    return _milestone_form(request, obj)


@login_required
@require_POST
def milestone_complete(request, pk):
    obj = _get_milestone(request, pk)
    action = request.POST.get("action", "complete")
    if action not in ("complete", "waive"):
        messages.error(request, "Unknown milestone action.")
        return redirect("procurement:milestone_list")
    if obj.status not in ContractMilestone.OPEN_STATUSES:
        messages.error(request,
                       f"This milestone is already {obj.get_status_display().lower()}.")
        return redirect("procurement:milestone_list")
    now = timezone.now()
    obj.status = "completed" if action == "complete" else "waived"
    obj.completed_at = now
    obj.completed_by = request.user
    obj.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
    write_audit_log(request.user, obj, f"milestone_{action}")
    messages.success(request,
                     f"Milestone {obj.number} {'completed' if action == 'complete' else 'waived'}.")
    return redirect(_safe_next(request)
                    or reverse("procurement:contract_detail",
                               args=[obj.contract_id]))


@login_required
@require_POST
def milestone_delete(request, pk):
    obj = _get_milestone(request, pk)
    if obj.status not in ContractMilestone.OPEN_STATUSES:
        messages.error(request,
                       f"A {obj.get_status_display().lower()} milestone is part of the "
                       f"agreement's history and cannot be deleted.")
        return redirect("procurement:milestone_list")
    number = obj.number
    obj.delete()
    write_audit_log(request.user, obj, "delete")
    messages.success(request, f"Milestone {number} deleted.")
    return redirect(_safe_next(request) or reverse("procurement:milestone_list"))
