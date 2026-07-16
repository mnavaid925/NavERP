"""HRM 3.8 Offer Management — Backgroundverification views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.OfferManagement._helpers import _bgv_or_404
from apps.hrm.models import (
    BGV_CHECK_TYPE_CHOICES,
    BGV_MANUAL_TRANSITION_STATUSES,
    BGV_RESULT_CHOICES,
    BGV_STATUS_CHOICES,
    BGV_VENDOR_CHOICES,
    BackgroundVerification,
)
from apps.hrm.forms import (
    BackgroundVerificationForm,
)
from apps.hrm.views.OfferManagement._helpers import _bgv_or_404


# --------------------------------------------------------------- Background Verification (3.8)
@login_required
def backgroundverification_list(request):
    qs = (BackgroundVerification.objects.filter(tenant=request.tenant)
          .select_related("offer__application__candidate").order_by("-created_at"))
    return crud_list(
        request, qs, "hrm/offer/backgroundverification/list.html",
        search_fields=["number", "offer__number", "offer__application__candidate__first_name",
                       "offer__application__candidate__last_name"],
        filters=[("status", "status", False), ("check_type", "check_type", False),
                 ("vendor", "vendor", False)],
        extra_context={
            "status_choices": BGV_STATUS_CHOICES,
            "check_type_choices": BGV_CHECK_TYPE_CHOICES,
            "vendor_choices": BGV_VENDOR_CHOICES,
        },
    )


@login_required
def backgroundverification_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = BackgroundVerificationForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Background check {obj.number} created.")
            return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    else:
        form = BackgroundVerificationForm(tenant=request.tenant,
                                          initial={"offer": request.GET.get("offer") or None})
    return render(request, "hrm/offer/backgroundverification/form.html", {"form": form, "is_edit": False})


@login_required
def backgroundverification_detail(request, pk):
    obj = get_object_or_404(
        BackgroundVerification.objects.filter(tenant=request.tenant)
        .select_related("offer__application__candidate", "initiated_by"), pk=pk)
    return render(request, "hrm/offer/backgroundverification/detail.html", {
        "obj": obj,
        "status_choices": BGV_STATUS_CHOICES,
        "result_choices": BGV_RESULT_CHOICES,
        # The manual-transition subset the "Update Status" dropdown offers (kept in lockstep with the
        # view guard below via the shared BGV_MANUAL_TRANSITION_STATUSES constant).
        "transition_status_choices": [(v, lbl) for v, lbl in BGV_STATUS_CHOICES
                                      if v in BGV_MANUAL_TRANSITION_STATUSES],
    })


@login_required
def backgroundverification_edit(request, pk):
    # Locked once completed (mirrors offer_edit / jobrequisition_edit) — a completed check's vendor/type/
    # consent/report is an audited record, not re-editable.
    obj = get_object_or_404(BackgroundVerification.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status == "completed":
        messages.error(request, "A completed background check can no longer be edited.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    return crud_edit(request, model=BackgroundVerification, pk=pk, form_class=BackgroundVerificationForm,
                     template="hrm/offer/backgroundverification/form.html",
                     success_url="hrm:backgroundverification_list")


@tenant_admin_required
@require_POST
def backgroundverification_delete(request, pk):
    return crud_delete(request, model=BackgroundVerification, pk=pk,
                       success_url="hrm:backgroundverification_list")


@tenant_admin_required  # running a background check is a privileged HR/compliance action
@require_POST
def backgroundverification_initiate(request, pk):
    # Consent-before-initiation gate (the Checkr/BambooHR "candidate must authorize" finding).
    obj = _bgv_or_404(request, pk)
    if obj.status not in ("not_started", "consent_pending"):
        messages.error(request, "This check has already been initiated.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    if not obj.consent_given:
        obj.status = "consent_pending"
        obj.save(update_fields=["status", "updated_at"])
        messages.error(request, "Candidate consent is required before initiating the check.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    obj.status = "initiated"
    obj.initiated_at = timezone.now()
    obj.initiated_by = request.user
    if obj.consent_date is None:
        obj.consent_date = timezone.now()
    obj.save(update_fields=["status", "initiated_at", "initiated_by", "consent_date", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "initiate", "vendor": obj.vendor})
    messages.success(request, f"Background check {obj.number} initiated.")
    return redirect("hrm:backgroundverification_detail", pk=obj.pk)


@tenant_admin_required  # advancing a compliance check is a privileged HR action
@require_POST
def backgroundverification_mark_status(request, pk):
    # Manual stand-in for the deferred vendor webhook: move the check through its intermediate statuses.
    obj = _bgv_or_404(request, pk)
    new_status = request.POST.get("status", "")
    if new_status not in BGV_MANUAL_TRANSITION_STATUSES:
        messages.error(request, "Invalid status transition.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    if obj.status in ("not_started", "consent_pending"):
        messages.error(request, "Initiate the check before updating its progress.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    obj.status = new_status
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": f"status:{new_status}"})
    messages.success(request, "Background-check status updated.")
    return redirect("hrm:backgroundverification_detail", pk=obj.pk)


@tenant_admin_required  # stamping the Clear/Consider verdict is a hire-relevant compliance decision
@require_POST
def backgroundverification_complete(request, pk):
    obj = _bgv_or_404(request, pk)
    if obj.status == "completed":
        messages.info(request, "This check is already completed.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    result = request.POST.get("result", "")
    if result not in dict(BGV_RESULT_CHOICES):
        messages.error(request, "Select a valid result (Clear / Consider / Not Applicable).")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    obj.status = "completed"
    obj.result = result
    obj.completed_at = timezone.now()
    obj.save(update_fields=["status", "result", "completed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "complete", "result": result})
    messages.success(request, f"Background check {obj.number} completed ({obj.get_result_display()}).")
    return redirect("hrm:backgroundverification_detail", pk=obj.pk)
