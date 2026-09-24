from datetime import timedelta
from functools import partial

from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.crm.models import Lead
from apps.sales.forms import LeadQualificationDecisionForm, LeadQualificationForm, LeadRoutingPreviewForm
from apps.sales.models import LeadQualification
from apps.sales.services import apply_qualification_decision, preview_routing, recompute_lead_score
from apps.sales.views._common import *


@login_required
def lead_qualification_list(request):
    queryset = sales_scope(
        LeadQualification.objects.filter(tenant=request.tenant).select_related("lead", "assessed_by"),
        request,
        "lead__owner",
    )
    review_due = request.GET.get("review_due", "")
    today = timezone.localdate()
    if review_due == "overdue":
        queryset = queryset.filter(next_review_on__lt=today)
    elif review_due == "today":
        queryset = queryset.filter(next_review_on=today)
    elif review_due == "week":
        queryset = queryset.filter(next_review_on__gte=today, next_review_on__lte=today + timedelta(days=7))
    return crud_list(
        request,
        queryset,
        "sales/leadmanagement/leadqualification/list.html",
        search_fields=["lead__number", "lead__name", "lead__company", "notes", "need_summary"],
        filters=[
            ("status", "status", False), ("framework", "framework", False),
            ("country", "country_code", False), ("region", "region", False),
            ("seniority", "seniority", False), ("budget_status", "budget_status", False),
            ("authority_level", "authority_level", False), ("assessor", "assessed_by_id", True),
        ],
        extra_context={
            "status_choices": LeadQualification.STATUS_CHOICES,
            "framework_choices": LeadQualification.FRAMEWORK_CHOICES,
            "seniority_choices": LeadQualification.SENIORITY_CHOICES,
            "budget_status_choices": LeadQualification.BUDGET_STATUS_CHOICES,
            "authority_level_choices": LeadQualification.AUTHORITY_LEVEL_CHOICES,
            "assessors": User.objects.filter(tenant=request.tenant, is_active=True).only("pk", "username", "email"),
            "leads": sales_leads(request).only("pk", "number", "name"),
            "review_due": review_due,
        },
    )


@login_required
def lead_qualification_create(request):
    return crud_create(
        request,
        form_class=partial(LeadQualificationForm, leads=sales_leads(request)),
        template="sales/leadmanagement/leadqualification/form.html",
        success_url="sales:lead_qualification_list",
        extra_context={"leads": sales_leads(request).only("pk", "number", "name")},
    )


@login_required
def lead_qualification_detail(request, pk):
    obj = sales_object(
        request,
        LeadQualification,
        "lead__owner",
        pk,
        select_related=("lead", "assessed_by", "budget_currency"),
    )
    score_events = obj.lead.sales_score_events.filter(tenant=request.tenant).select_related("recorded_by")[:20]
    enrollments = obj.lead.sales_nurture_enrollments.filter(tenant=request.tenant).select_related("email_campaign")[:20]
    return render(request, "sales/leadmanagement/leadqualification/detail.html", {
        "obj": obj,
        "lead": obj.lead,
        "score_events": score_events,
        "enrollments": enrollments,
        "routing_preview": None,
        "preview_form": LeadRoutingPreviewForm(tenant=request.tenant, leads=sales_leads(request), initial={"lead": obj.lead_id}),
        "decision_form": LeadQualificationDecisionForm(initial={"status": obj.status}),
    })


@login_required
def lead_qualification_edit(request, pk):
    obj = sales_object(request, LeadQualification, "lead__owner", pk)
    if obj.status == "archived" or obj.lead.status == "converted":
        messages.info(request, "Archived or converted assessments are read-only.")
        return redirect("sales:lead_qualification_detail", pk=obj.pk)
    return crud_edit(
        request,
        model=LeadQualification,
        pk=pk,
        form_class=partial(LeadQualificationForm, leads=sales_leads(request)),
        template="sales/leadmanagement/leadqualification/form.html",
        success_url="sales:lead_qualification_list",
        extra_context={"leads": sales_leads(request).only("pk", "number", "name")},
        audit_redacted_fields=("need_summary", "economic_buyer", "decision_criteria", "decision_process", "technical_requirements", "pain_points", "success_metrics", "disqualification_reason", "notes"),
    )


@require_POST
@login_required
def lead_qualification_delete(request, pk):
    obj = sales_object(request, LeadQualification, "lead__owner", pk, select_related=("lead",))
    if obj.status != "unassessed" or obj.lead.status == "converted":
        messages.error(request, "Only an unassessed lead record without a conversion can be deleted.")
        return redirect("sales:lead_qualification_detail", pk=obj.pk)
    return crud_delete(request, model=LeadQualification, pk=pk, success_url="sales:lead_qualification_list")


def _decide_qualification(request, pk, expected_status):
    obj = sales_object(request, LeadQualification, "lead__owner", pk, select_related=("lead",))
    form = LeadQualificationDecisionForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "The qualification decision could not be saved.")
        return redirect("sales:lead_qualification_detail", pk=obj.pk)
    if form.cleaned_data["status"] != expected_status:
        messages.error(request, "That transition is not available from this action.")
        return redirect("sales:lead_qualification_detail", pk=obj.pk)
    try:
        apply_qualification_decision(
            obj,
            request.tenant,
            request.user,
            status=expected_status,
            disqualification_reason=form.cleaned_data.get("disqualification_reason", ""),
            notes=form.cleaned_data.get("notes", ""),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:lead_qualification_detail", pk=obj.pk)
    messages.success(request, f"Qualification marked {expected_status.replace('_', ' ')}.")
    return redirect("sales:lead_qualification_detail", pk=obj.pk)


@require_POST
@login_required
def lead_qualification_partial(request, pk):
    return _decide_qualification(request, pk, "partially_qualified")


@require_POST
@login_required
def lead_qualification_qualify(request, pk):
    return _decide_qualification(request, pk, "qualified")


@require_POST
@login_required
def lead_qualification_disqualify(request, pk):
    return _decide_qualification(request, pk, "disqualified")


@require_POST
@tenant_admin_required
def lead_qualification_archive(request, pk):
    return _decide_qualification(request, pk, "archived")


@require_POST
@login_required
def lead_qualification_recalculate(request, pk):
    obj = sales_object(request, LeadQualification, "lead__owner", pk, select_related=("lead",))
    try:
        recompute_lead_score(obj.lead, request.tenant, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:lead_qualification_detail", pk=obj.pk)
    messages.success(request, "Lead score projection refreshed.")
    return redirect("sales:lead_qualification_detail", pk=obj.pk)


@login_required
def lead_qualification_route_preview(request, pk):
    obj = sales_object(request, LeadQualification, "lead__owner", pk, select_related=("lead",))
    form = LeadRoutingPreviewForm(request.GET or None, tenant=request.tenant, leads=sales_leads(request), initial={"lead": obj.lead_id})
    result = None
    if request.GET and form.is_valid():
        result = preview_routing(form.cleaned_data["lead"], request.tenant)
    return render(request, "sales/leadmanagement/leadqualification/detail.html", {
        "obj": obj,
        "lead": obj.lead,
        "score_events": obj.lead.sales_score_events.filter(tenant=request.tenant).select_related("recorded_by")[:20],
        "enrollments": obj.lead.sales_nurture_enrollments.filter(tenant=request.tenant).select_related("email_campaign")[:20],
        "routing_preview": result,
        "preview_form": form,
        "decision_form": LeadQualificationDecisionForm(initial={"status": obj.status}),
    })
