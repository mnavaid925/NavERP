from functools import partial

from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.models import ConsentPurpose
from apps.crm.models import EmailCampaign, Lead
from apps.sales.forms import LeadNurtureActivationForm, LeadNurtureEnrollmentForm, LeadNurtureExitForm
from apps.sales.models import LeadNurtureEnrollment
from apps.sales.services import activate_nurture, transition_nurture
from apps.sales.views._common import *


@login_required
def lead_nurture_enrollment_list(request):
    queryset = sales_scope(
        LeadNurtureEnrollment.objects.filter(tenant=request.tenant).select_related("lead", "email_campaign", "owner", "consent_purpose"),
        request,
        "lead__owner",
    )
    next_touch = request.GET.get("next_touch", "")
    today = timezone.now()
    if next_touch == "overdue":
        queryset = queryset.filter(next_touch_at__lt=today)
    elif next_touch == "today":
        queryset = queryset.filter(next_touch_at__date=today.date())
    return crud_list(
        request,
        queryset,
        "sales/leadmanagement/leadnurtureenrollment/list.html",
        search_fields=["number", "lead__number", "lead__name", "email_campaign__name", "notes"],
        filters=[("status", "status", False), ("trigger_kind", "trigger_kind", False), ("email_campaign", "email_campaign_id", True), ("owner", "owner_id", True)],
        extra_context={
            "status_choices": LeadNurtureEnrollment.STATUS_CHOICES,
            "trigger_kind_choices": LeadNurtureEnrollment.TRIGGER_KIND_CHOICES,
            "drip_campaigns": EmailCampaign.objects.filter(tenant=request.tenant, send_type="drip"),
            "owners": User.objects.filter(tenant=request.tenant, is_active=True),
            "leads": sales_leads(request),
            "next_touch": next_touch,
        },
    )


@login_required
def lead_nurture_enrollment_create(request):
    return crud_create(
        request,
        form_class=partial(LeadNurtureEnrollmentForm, leads=sales_leads(request)),
        template="sales/leadmanagement/leadnurtureenrollment/form.html",
        success_url="sales:lead_nurture_enrollment_list",
        extra_context={
            "leads": sales_leads(request),
            "drip_campaigns": EmailCampaign.objects.filter(tenant=request.tenant, send_type="drip"),
            "consent_purposes": ConsentPurpose.objects.filter(tenant=request.tenant, is_active=True),
            "owners": User.objects.filter(tenant=request.tenant, is_active=True),
        },
    )


@login_required
def lead_nurture_enrollment_detail(request, pk):
    obj = sales_object(
        request,
        LeadNurtureEnrollment,
        "lead__owner",
        pk,
        select_related=("lead", "email_campaign", "consent_purpose", "owner"),
    )
    return render(request, "sales/leadmanagement/leadnurtureenrollment/detail.html", {
        "obj": obj,
        "lead": obj.lead,
        "email_campaign": obj.email_campaign,
        "consent_purpose": obj.consent_purpose,
        "activation_form": LeadNurtureActivationForm(initial={"next_touch_at": obj.next_touch_at}),
        "exit_form": LeadNurtureExitForm(),
    })


@login_required
def lead_nurture_enrollment_edit(request, pk):
    obj = sales_object(request, LeadNurtureEnrollment, "lead__owner", pk)
    if obj.status != "pending":
        messages.info(request, "Only pending enrollments can edit identity fields; use lifecycle actions afterward.")
        return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)
    return crud_edit(
        request,
        model=LeadNurtureEnrollment,
        pk=pk,
        form_class=partial(LeadNurtureEnrollmentForm, leads=sales_leads(request)),
        template="sales/leadmanagement/leadnurtureenrollment/form.html",
        success_url="sales:lead_nurture_enrollment_list",
        extra_context={
            "leads": sales_leads(request),
            "drip_campaigns": EmailCampaign.objects.filter(tenant=request.tenant, send_type="drip"),
            "consent_purposes": ConsentPurpose.objects.filter(tenant=request.tenant, is_active=True),
            "owners": User.objects.filter(tenant=request.tenant, is_active=True),
        },
        audit_redacted_fields=("consent_evidence", "notes"),
    )


@require_POST
@login_required
def lead_nurture_enrollment_delete(request, pk):
    obj = sales_object(request, LeadNurtureEnrollment, "lead__owner", pk, select_related=("lead",))
    if obj.status != "pending" or obj.lead.status == "converted":
        messages.error(request, "Only a pending enrollment for an unconverted lead can be deleted.")
        return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)
    return crud_delete(request, model=LeadNurtureEnrollment, pk=pk, success_url="sales:lead_nurture_enrollment_list")


@require_POST
@tenant_admin_required
def lead_nurture_enrollment_activate(request, pk):
    obj = get_object_or_404(LeadNurtureEnrollment, pk=pk, tenant=request.tenant)
    form = LeadNurtureActivationForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "Choose a valid next-touch target before activation.")
        return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)
    try:
        activate_nurture(obj, request.tenant, request.user, next_touch_at=form.cleaned_data.get("next_touch_at"))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)
    messages.success(request, "Nurture enrollment activated as recorded state; no message was sent.")
    return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)


def _transition(request, pk, target_status, default_reason=""):
    obj = sales_object(request, LeadNurtureEnrollment, "lead__owner", pk, select_related=("lead",))
    reason = default_reason
    notes = ""
    if target_status in {"completed", "cancelled", "replied", "converted"}:
        form = LeadNurtureExitForm(request.POST, target_status=target_status, tenant=request.tenant, initial={"exit_reason": default_reason})
        if not form.is_valid():
            messages.error(request, "A valid exit reason is required for this transition.")
            return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)
        reason = form.cleaned_data["exit_reason"]
        notes = form.cleaned_data.get("notes", "")
    try:
        transition_nurture(obj, request.tenant, request.user, target_status, exit_reason=reason, notes=notes)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)
    messages.success(request, f"Enrollment marked {target_status.replace('_', ' ')}.")
    return redirect("sales:lead_nurture_enrollment_detail", pk=obj.pk)


@require_POST
@login_required
def lead_nurture_enrollment_pause(request, pk):
    return _transition(request, pk, "paused")


@require_POST
@tenant_admin_required
def lead_nurture_enrollment_resume(request, pk):
    return _transition(request, pk, "active")


@require_POST
@login_required
def lead_nurture_enrollment_complete(request, pk):
    return _transition(request, pk, "completed", "completed")


@require_POST
@login_required
def lead_nurture_enrollment_cancel(request, pk):
    return _transition(request, pk, "cancelled", "cancelled")


@require_POST
@login_required
def lead_nurture_enrollment_reply(request, pk):
    return _transition(request, pk, "replied", "replied")


@require_POST
@tenant_admin_required
def lead_nurture_enrollment_convert_exit(request, pk):
    return _transition(request, pk, "converted", "converted")
