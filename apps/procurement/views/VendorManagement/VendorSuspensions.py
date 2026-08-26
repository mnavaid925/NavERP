"""Procurement 6.4 Vendor Management — VendorSuspension (block register) views.

Requesting a block is open to any workspace member (the register names its filer);
deciding, lifting and editing/deleting pending rows are tenant-admin gated — the same
split 6.2 puts on amendments. A decided row is immutable history: corrections are new
filings, never edits of the record.
"""
from django.db import transaction
from django.db.models import Count, Q

from apps.core.utils import write_audit_log
from apps.procurement.forms import (
    SuspensionDecisionForm,
    SuspensionLiftForm,
    VendorSuspensionForm,
)
from apps.procurement.models import VendorSuspension
from apps.procurement.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    return (VendorSuspension.objects.filter(tenant=tenant)
            .select_related("supplier", "po_reference", "requested_by", "decided_by",
                            "lifted_by"))


def _is_admin(request):
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


@login_required
def vsu_list(request):
    # Join-free COUNT for the footer badges: aggregate() does not strip unused
    # select_related joins, so building it off _scoped would drag five LEFT JOINs through
    # a whole-tenant COUNT on every render.
    totals = VendorSuspension.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        requested=Count("id", filter=Q(status="requested")),
        active=Count("id", filter=Q(status="active")),
    )
    return crud_list(
        request, _scoped(request.tenant), "procurement/vendormanagement/suspension/list.html",
        search_fields=["number", "supplier__name", "reason", "decision_note", "lift_note"],
        filters=[("status", "status", False)],
        extra_context={
            "status_choices": VendorSuspension.STATUS_CHOICES,
            "kind_choices": VendorSuspension.KIND_CHOICES,
            "total_count": totals["total"],
            "requested_count": totals["requested"],
            "active_count": totals["active"],
            "today": timezone.localdate(),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def vsu_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "procurement/vendormanagement/suspension/detail.html", {
        "obj": obj,
        "decision_form": SuspensionDecisionForm(),
        "lift_form": SuspensionLiftForm(),
        "today": timezone.localdate(),
        "is_admin": _is_admin(request),
    })


@login_required
def vsu_create(request):
    """Raise a block REQUEST (any member); an admin decides it separately.

    Mirrors ``crud_create`` exactly (tenant stamping included) plus the one thing the
    generic helper cannot do: stamp ``requested_by`` from the session user.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = VendorSuspensionForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                if hasattr(obj, "tenant_id"):
                    obj.tenant = request.tenant
                obj.requested_by = request.user
                obj.save()
                form.save_m2m()
            write_audit_log(request.user, obj, "create")
            messages.success(request,
                             f"Suspension request {obj.number} filed — it now waits for a "
                             f"workspace admin to decide.")
            return redirect("procurement:vsu_detail", pk=obj.pk)
    else:
        form = VendorSuspensionForm(tenant=request.tenant,
                                    initial={"starts_on": timezone.localdate()})
    return render(request, "procurement/vendormanagement/suspension/form.html", {
        "form": form,
        "is_edit": False,
    })


@tenant_admin_required
def vsu_edit(request, pk):
    # The whole edit runs INSIDE a row lock: crud_edit re-fetches and saves on its own, and an
    # unlocked pre-check would leave the window where an admin approving concurrently turns this
    # into an edit of decided history. Holding select_for_update until the outer atomic exits —
    # i.e. until after crud_edit's save commits — closes that race.
    with transaction.atomic():
        locked = get_object_or_404(VendorSuspension.objects.select_for_update(),
                                   pk=pk, tenant=request.tenant)
        if locked.status != "requested":
            messages.error(request,
                           "A decided suspension is immutable history — file a new "
                           "register entry instead.")
            return redirect("procurement:vsu_detail", pk=pk)
        return crud_edit(
            request, model=VendorSuspension, pk=pk, form_class=VendorSuspensionForm,
            template="procurement/vendormanagement/suspension/form.html",
            # A bare url NAME must be reversible without arguments — "…:vsu_detail" needs
            # <int:pk> and would NoReverseMatch after the save had already committed.
            success_url="procurement:vsu_list",
        )


@tenant_admin_required
@require_POST
def vsu_delete(request, pk):
    """Pending-junk removal only. A DECIDED row is register history — deleting an active
    block would silently unblock a supplier outside any audited lift, so the gate refuses
    anything past 'requested'."""
    obj = get_object_or_404(VendorSuspension, pk=pk, tenant=request.tenant)
    if obj.status != "requested":
        messages.error(request,
                       f"{obj.number} has been decided ({obj.get_status_display()}) — "
                       f"register history cannot be deleted. Lift it instead if it is "
                       f"in force.")
        return redirect("procurement:vsu_detail", pk=obj.pk)
    return crud_delete(request, model=VendorSuspension, pk=pk,
                       success_url="procurement:vsu_list")


def _decision_note(request):
    """The optional note from SuspensionDecisionForm, or None when the POST carries an
    INVALID one (e.g. over the 2000-char cap). None means "bounce": deciding anyway and
    silently dropping what the admin typed would hollow out the trail — the same contract
    vsu_lift holds with its mandatory reason."""
    form = SuspensionDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request,
                       "Decision note must be 2000 characters or fewer — nothing was decided.")
        return None
    return form.cleaned_data["note"]


@tenant_admin_required
@require_POST
def vsu_approve(request, pk):
    """Put the block in force atomically; the row is locked and its pending-ness
    re-checked inside the transaction, so a double-submit cannot decide twice."""
    note = _decision_note(request)
    if note is None:
        return redirect("procurement:vsu_detail", pk=pk)
    with transaction.atomic():
        obj = get_object_or_404(VendorSuspension.objects.select_for_update()
                                .select_related("supplier"),
                                pk=pk, tenant=request.tenant)
        if obj.status != "requested":
            messages.info(request, "This register entry has already been decided.")
            return redirect("procurement:vsu_detail", pk=pk)
        obj.status = "active"
        obj.decided_by = request.user
        obj.decided_at = timezone.now()
        obj.decision_note = note[:2000]
        obj.save(update_fields=["status", "decided_by", "decided_at", "decision_note",
                                "updated_at"])
        write_audit_log(request.user, obj, "approve")
    messages.success(request,
                     f"Supplier blocked — {obj.get_kind_display()} {obj.number} is now "
                     f"in force against {obj.supplier.name}.")
    return redirect("procurement:vsu_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def vsu_reject(request, pk):
    note = _decision_note(request)
    if note is None:
        return redirect("procurement:vsu_detail", pk=pk)
    with transaction.atomic():
        obj = get_object_or_404(VendorSuspension.objects.select_for_update()
                                .select_related("supplier"),
                                pk=pk, tenant=request.tenant)
        if obj.status != "requested":
            messages.info(request, "This register entry has already been decided.")
            return redirect("procurement:vsu_detail", pk=pk)
        obj.status = "rejected"
        obj.decided_by = request.user
        obj.decided_at = timezone.now()
        obj.decision_note = note[:2000]
        obj.save(update_fields=["status", "decided_by", "decided_at", "decision_note",
                                "updated_at"])
        write_audit_log(request.user, obj, "reject")
    messages.success(request, f"Suspension request {obj.number} rejected.")
    return redirect("procurement:vsu_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def vsu_lift(request, pk):
    """Take an active block off the vendor. The reason is mandatory — an unexplained
    unblock would hollow out the register."""
    with transaction.atomic():
        obj = get_object_or_404(VendorSuspension.objects.select_for_update()
                                .select_related("supplier"),
                                pk=pk, tenant=request.tenant)
        if obj.status != "active":
            messages.info(request, "Only an in-force block can be lifted.")
            return redirect("procurement:vsu_detail", pk=pk)
        form = SuspensionLiftForm(request.POST)
        if not form.is_valid():
            messages.error(request,
                           "Give a reason when lifting a block — the register keeps the why.")
            return redirect("procurement:vsu_detail", pk=pk)
        obj.status = "lifted"
        obj.lifted_by = request.user
        obj.lifted_at = timezone.now()
        obj.lift_note = form.cleaned_data["lift_note"][:2000]
        obj.save(update_fields=["status", "lifted_by", "lifted_at", "lift_note",
                                "updated_at"])
        write_audit_log(request.user, obj, "lift")
    messages.success(request,
                     f"Block lifted — {obj.supplier.name} can receive POs again.")
    return redirect("procurement:vsu_detail", pk=obj.pk)
