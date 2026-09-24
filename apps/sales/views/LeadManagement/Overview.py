from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import ContactMethod
from apps.crm.models import Lead
from apps.sales.models import LeadNurtureEnrollment, LeadQualification, LeadRoutingRule, LeadScoreEvent
from apps.sales.services import handoff_lead
from apps.sales.views._common import messages, sales_leads, sales_scope


@login_required
def lead_overview(request):
    lead_qs = sales_leads(request)
    leads = list(lead_qs.select_related("owner", "sales_qualification").order_by("-created_at")[:50])
    lead_ids = [lead.pk for lead in leads]
    qualifications = sales_scope(
        LeadQualification.objects.filter(tenant=request.tenant).select_related("lead", "assessed_by"),
        request,
        "lead__owner",
    ).order_by("-updated_at")[:20]
    routing_rules = LeadRoutingRule.objects.filter(tenant=request.tenant).select_related("territory", "default_owner", "fallback_owner").prefetch_related("eligible_owners")[:20]
    enrollments = list(
        LeadNurtureEnrollment.objects.filter(tenant=request.tenant, lead_id__in=lead_ids)
        .select_related("lead", "email_campaign")
        .order_by("-created_at")
    )
    latest_score_events = sales_scope(
        LeadScoreEvent.objects.filter(tenant=request.tenant).select_related("lead"),
        request,
        "lead__owner",
    ).order_by("-occurred_at", "-id")[:20]
    email_query = Q()
    for lead in leads:
        if lead.email:
            email_query |= Q(value__iexact=lead.email.strip())
    email_map = {}
    if email_query:
        for method in ContactMethod.objects.filter(tenant=request.tenant, kind="email").filter(email_query).values("value", "party_id", "party__name"):
            email_map.setdefault(method["value"].strip().casefold(), method)
    duplicate_warnings = []
    for lead in leads:
        match = email_map.get((lead.email or "").strip().casefold()) if lead.email else None
        if match:
            duplicate_warnings.append({"lead": lead, "party_name": match["party__name"], "reason": "Email matches an existing Party."})
    enrollment_states = {}
    for enrollment in enrollments:
        enrollment_states.setdefault(enrollment.lead_id, []).append(enrollment.get_status_display())
    enrollment_labels = {lead_id: " / ".join(states) for lead_id, states in enrollment_states.items()}
    stats = {
        "total_leads": lead_qs.count(),
        "qualified_leads": sales_scope(
            LeadQualification.objects.filter(tenant=request.tenant, status="qualified"),
            request,
            "lead__owner",
        ).count(),
        "active_nurture": sales_scope(
            LeadNurtureEnrollment.objects.filter(tenant=request.tenant, status="active"),
            request,
            "lead__owner",
        ).count(),
        "average_score": lead_qs.aggregate(value=Avg("score"))["value"] or 0,
        "routing_rule_count": LeadRoutingRule.objects.filter(tenant=request.tenant, is_active=True).count(),
    }
    return render(request, "sales/overview.html", {
        "stats": stats,
        "leads": leads,
        "qualifications": qualifications,
        "routing_rules": routing_rules,
        "enrollments": enrollments,
        "enrollment_states": enrollment_states,
        "enrollment_labels": enrollment_labels,
        "latest_score_events": latest_score_events,
        "duplicate_warnings": duplicate_warnings[:20],
        "recent_activity": latest_score_events,
    })


@require_POST
@tenant_admin_required
def lead_handoff(request, pk):
    lead = get_object_or_404(sales_leads(request), pk=pk)
    qualification = sales_scope(
        LeadQualification.objects.filter(tenant=request.tenant, lead=lead),
        request,
        "lead__owner",
    ).first()
    if qualification is None or qualification.status != "qualified":
        messages.error(request, "A qualified assessment is required before handoff.")
        return redirect("sales:lead_overview")
    try:
        opportunity = handoff_lead(lead, request.tenant, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:lead_overview")
    messages.success(request, f"Lead handed off to opportunity {opportunity.number}.")
    return redirect("crm:opportunity_detail", pk=opportunity.pk)
