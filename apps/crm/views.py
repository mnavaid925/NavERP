"""CRM (Module 1) views — function-based, ``@login_required``, tenant-scoped.

Full CRUD for the six CRM-owned models via the shared ``apps.core.crud`` helpers (search +
int-FK-guarded filters + windowed pagination + audit), plus:
  * Account/Contact "lenses" over ``core.Party`` (1.1 — no duplication of the shared master),
  * one-click Lead conversion (creates Party + roles + an Opportunity),
  * a CRM analytics overview (1.6) using the dashboard's json_script + Chart.js pattern.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, DecimalField, F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.models import ContactMethod, Party, PartyRole
from apps.core.utils import write_audit_log

from .forms import (
    CampaignForm,
    CaseForm,
    CrmTaskForm,
    KnowledgeArticleForm,
    LeadForm,
    OpportunityForm,
)
from .models import Campaign, Case, CrmTask, KnowledgeArticle, Lead, Opportunity


# ===================================================================== Leads (1.1)
@login_required
def lead_list(request):
    return crud_list(
        request, Lead.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/lead_list.html",
        search_fields=["name", "company", "email", "number"],
        filters=[("status", "status", False), ("rating", "rating", False), ("source", "source", False)],
        extra_context={"status_choices": Lead.STATUS_CHOICES,
                       "rating_choices": Lead.RATING_CHOICES,
                       "source_choices": Lead.SOURCE_CHOICES},
    )


@login_required
def lead_create(request):
    return crud_create(request, form_class=LeadForm, template="crm/lead_form.html",
                       success_url="crm:lead_list")


@login_required
def lead_detail(request, pk):
    obj = get_object_or_404(Lead.objects.select_related("owner", "converted_party"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/lead_detail.html", {
        "obj": obj,
        "opportunities": obj.opportunities.select_related("account")[:20],
    })


@login_required
def lead_edit(request, pk):
    return crud_edit(request, model=Lead, pk=pk, form_class=LeadForm,
                     template="crm/lead_form.html", success_url="crm:lead_list")


@login_required
@require_POST
def lead_delete(request, pk):
    return crud_delete(request, model=Lead, pk=pk, success_url="crm:lead_list")


@login_required
@require_POST
def lead_convert(request, pk):
    """One-click conversion (1.1): Lead -> Account (org Party) + Contact (person Party) +
    Opportunity. Idempotent guard: a converted lead is not re-converted."""
    lead = get_object_or_404(Lead, pk=pk, tenant=request.tenant)
    if lead.status == "converted":
        messages.info(request, "This lead has already been converted.")
        return redirect("crm:lead_detail", pk=lead.pk)
    with transaction.atomic():
        account = None
        if lead.company:
            account = Party.objects.create(tenant=request.tenant, kind="organization", name=lead.company)
            PartyRole.objects.create(tenant=request.tenant, party=account, role="customer",
                                     status="active", start_date=timezone.localdate())
        contact = Party.objects.create(tenant=request.tenant, kind="person", name=lead.name)
        PartyRole.objects.create(tenant=request.tenant, party=contact, role="contact",
                                 status="active", start_date=timezone.localdate())
        if lead.email:
            ContactMethod.objects.create(tenant=request.tenant, party=contact, kind="email", value=lead.email)
        opp = Opportunity.objects.create(
            tenant=request.tenant, name=f"{lead.company or lead.name} Opportunity",
            account=account, primary_contact=contact, stage="prospecting",
            amount=lead.est_value, probability=10, owner=lead.owner, source_lead=lead,
        )
        lead.status = "converted"
        lead.converted_party = account or contact
        lead.save(update_fields=["status", "converted_party", "updated_at"])
    write_audit_log(request.user, lead, "update", {"action": "convert"})
    write_audit_log(request.user, opp, "create")
    messages.success(request, f"Lead converted — opportunity {opp.number} created.")
    return redirect("crm:opportunity_detail", pk=opp.pk)


# ============================================================= Opportunities (1.2)
@login_required
def opportunity_list(request):
    return crud_list(
        request, Opportunity.objects.filter(tenant=request.tenant).select_related("account", "owner"),
        "crm/opportunity_list.html",
        search_fields=["name", "number"],
        filters=[("stage", "stage", False), ("account", "account_id", True)],
        extra_context={"stage_choices": Opportunity.STAGE_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def opportunity_create(request):
    return crud_create(request, form_class=OpportunityForm, template="crm/opportunity_form.html",
                       success_url="crm:opportunity_list")


@login_required
def opportunity_detail(request, pk):
    obj = get_object_or_404(
        Opportunity.objects.select_related("account", "primary_contact", "owner", "source_lead", "campaign"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/opportunity_detail.html", {
        "obj": obj,
        "tasks": obj.tasks.select_related("owner")[:20],
    })


@login_required
def opportunity_edit(request, pk):
    return crud_edit(request, model=Opportunity, pk=pk, form_class=OpportunityForm,
                     template="crm/opportunity_form.html", success_url="crm:opportunity_list")


@login_required
@require_POST
def opportunity_delete(request, pk):
    return crud_delete(request, model=Opportunity, pk=pk, success_url="crm:opportunity_list")


# ================================================================ Campaigns (1.3)
@login_required
def campaign_list(request):
    return crud_list(
        request, Campaign.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/campaign_list.html",
        search_fields=["name", "number"],
        filters=[("status", "status", False), ("type", "type", False)],
        extra_context={"status_choices": Campaign.STATUS_CHOICES,
                       "type_choices": Campaign.TYPE_CHOICES},
    )


@login_required
def campaign_create(request):
    return crud_create(request, form_class=CampaignForm, template="crm/campaign_form.html",
                       success_url="crm:campaign_list")


@login_required
def campaign_detail(request, pk):
    obj = get_object_or_404(Campaign.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/campaign_detail.html", {
        "obj": obj,
        "opportunities": obj.opportunities.select_related("account")[:20],
    })


@login_required
def campaign_edit(request, pk):
    return crud_edit(request, model=Campaign, pk=pk, form_class=CampaignForm,
                     template="crm/campaign_form.html", success_url="crm:campaign_list")


@login_required
@require_POST
def campaign_delete(request, pk):
    return crud_delete(request, model=Campaign, pk=pk, success_url="crm:campaign_list")


# ============================================================ Cases / Tickets (1.4)
@login_required
def case_list(request):
    return crud_list(
        request, Case.objects.filter(tenant=request.tenant).select_related("account", "contact", "owner"),
        "crm/case_list.html",
        search_fields=["subject", "number"],
        filters=[("status", "status", False), ("priority", "priority", False), ("type", "type", False)],
        extra_context={"status_choices": Case.STATUS_CHOICES,
                       "priority_choices": Case.PRIORITY_CHOICES,
                       "type_choices": Case.TYPE_CHOICES},
    )


@login_required
def case_create(request):
    return crud_create(request, form_class=CaseForm, template="crm/case_form.html",
                       success_url="crm:case_list")


@login_required
def case_detail(request, pk):
    obj = get_object_or_404(Case.objects.select_related("account", "contact", "owner"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/case_detail.html", {"obj": obj})


@login_required
def case_edit(request, pk):
    return crud_edit(request, model=Case, pk=pk, form_class=CaseForm,
                     template="crm/case_form.html", success_url="crm:case_list")


@login_required
@require_POST
def case_delete(request, pk):
    return crud_delete(request, model=Case, pk=pk, success_url="crm:case_list")


# ====================================================== Knowledge Base / Solutions (1.4)
@login_required
def knowledgearticle_list(request):
    return crud_list(
        request, KnowledgeArticle.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/knowledgearticle_list.html",
        search_fields=["title", "category", "number"],
        filters=[("status", "status", False), ("visibility", "visibility", False)],
        extra_context={"status_choices": KnowledgeArticle.STATUS_CHOICES,
                       "visibility_choices": KnowledgeArticle.VISIBILITY_CHOICES},
    )


@login_required
def knowledgearticle_create(request):
    return crud_create(request, form_class=KnowledgeArticleForm,
                       template="crm/knowledgearticle_form.html",
                       success_url="crm:knowledgearticle_list")


@login_required
def knowledgearticle_detail(request, pk):
    # Count a view via an atomic F() update (tenant-scoped); bypasses save() so it neither
    # touches updated_at nor re-numbers.
    KnowledgeArticle.objects.filter(pk=pk, tenant=request.tenant).update(views_count=F("views_count") + 1)
    obj = get_object_or_404(KnowledgeArticle.objects.select_related("owner"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/knowledgearticle_detail.html", {"obj": obj})


@login_required
def knowledgearticle_edit(request, pk):
    return crud_edit(request, model=KnowledgeArticle, pk=pk, form_class=KnowledgeArticleForm,
                     template="crm/knowledgearticle_form.html",
                     success_url="crm:knowledgearticle_list")


@login_required
@require_POST
def knowledgearticle_delete(request, pk):
    return crud_delete(request, model=KnowledgeArticle, pk=pk,
                       success_url="crm:knowledgearticle_list")


# =============================================================== Tasks (1.5)
@login_required
def task_list(request):
    return crud_list(
        request, CrmTask.objects.filter(tenant=request.tenant).select_related("owner", "party"),
        "crm/task_list.html",
        search_fields=["subject", "number"],
        filters=[("status", "status", False), ("priority", "priority", False), ("type", "type", False)],
        extra_context={"status_choices": CrmTask.STATUS_CHOICES,
                       "priority_choices": CrmTask.PRIORITY_CHOICES,
                       "type_choices": CrmTask.TYPE_CHOICES},
    )


@login_required
def task_create(request):
    return crud_create(request, form_class=CrmTaskForm, template="crm/task_form.html",
                       success_url="crm:task_list")


@login_required
def task_detail(request, pk):
    obj = get_object_or_404(
        CrmTask.objects.select_related("owner", "party", "related_opportunity"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/task_detail.html", {"obj": obj})


@login_required
def task_edit(request, pk):
    return crud_edit(request, model=CrmTask, pk=pk, form_class=CrmTaskForm,
                     template="crm/task_form.html", success_url="crm:task_list")


@login_required
@require_POST
def task_delete(request, pk):
    return crud_delete(request, model=CrmTask, pk=pk, success_url="crm:task_list")


# ============================== Accounts & Contacts — lenses over core.Party (1.1) ==========
# Accounts/Contacts ARE the shared core.Party (one record, many roles); CRM provides
# read-oriented lenses. Mutations live on the core party pages (no duplicate master tables).
@login_required
def account_list(request):
    return crud_list(
        request,
        Party.objects.filter(tenant=request.tenant, kind="organization").prefetch_related("roles"),
        "crm/account_list.html", search_fields=["name", "tax_id"],
    )


@login_required
def account_detail(request, pk):
    obj = get_object_or_404(
        Party.objects.filter(tenant=request.tenant, kind="organization")
        .prefetch_related("roles", "addresses", "contact_methods"),
        pk=pk)
    return render(request, "crm/account_detail.html", {
        "obj": obj,
        "opportunities": Opportunity.objects.filter(tenant=request.tenant, account=obj).select_related("owner")[:20],
        "cases": Case.objects.filter(tenant=request.tenant, account=obj).select_related("owner")[:20],
    })


@login_required
def contact_list(request):
    return crud_list(
        request,
        Party.objects.filter(tenant=request.tenant, kind="person").prefetch_related("roles"),
        "crm/contact_list.html", search_fields=["name"],
    )


@login_required
def contact_detail(request, pk):
    obj = get_object_or_404(
        Party.objects.filter(tenant=request.tenant, kind="person")
        .prefetch_related("roles", "contact_methods"),
        pk=pk)
    return render(request, "crm/contact_detail.html", {
        "obj": obj,
        "opportunities": Opportunity.objects.filter(tenant=request.tenant, primary_contact=obj).select_related("account")[:20],
        "cases": Case.objects.filter(tenant=request.tenant, contact=obj).select_related("owner")[:20],
    })


# ===================================================== Analytics & Reporting overview (1.6)
@login_required
def overview(request):
    tenant = request.tenant
    stats = {"open_leads": 0, "pipeline": 0, "weighted": 0, "win_rate": 0,
             "open_cases": 0, "open_tasks": 0, "active_campaigns": 0}
    stage_rows, rating_rows, recent_opps = [], [], []
    if tenant is not None:
        leads = Lead.objects.filter(tenant=tenant)
        opps = Opportunity.objects.filter(tenant=tenant)
        cases = Case.objects.filter(tenant=tenant)

        stats["open_leads"] = leads.exclude(status__in=["converted", "unqualified"]).count()
        # DB-side pipeline + weighted-forecast sums (no full-row fetch).
        agg = opps.filter(stage__in=Opportunity.OPEN_STAGES).aggregate(
            pipeline=Sum("amount"),
            weighted=Sum(F("amount") * F("probability"),
                         output_field=DecimalField(max_digits=18, decimal_places=2)),
        )
        stats["pipeline"] = agg["pipeline"] or 0
        stats["weighted"] = (agg["weighted"] or 0) / 100
        won = opps.filter(stage="closed_won").count()
        closed = opps.filter(stage__in=["closed_won", "closed_lost"]).count()
        stats["win_rate"] = round(won / closed * 100) if closed else 0
        stats["open_cases"] = cases.filter(status__in=Case.OPEN_STATUSES).count()
        stats["open_tasks"] = CrmTask.objects.filter(tenant=tenant, status__in=CrmTask.OPEN_STATUSES).count()
        stats["active_campaigns"] = Campaign.objects.filter(tenant=tenant, status="active").count()

        stage_rows = list(opps.values("stage").annotate(c=Count("id")).order_by("stage"))
        rating_rows = list(leads.values("rating").annotate(c=Count("id")).order_by("rating"))
        recent_opps = list(opps.select_related("account", "owner").order_by("-created_at")[:8])

    stage_display = dict(Opportunity.STAGE_CHOICES)
    rating_display = dict(Lead.RATING_CHOICES)
    context = {
        "stats": stats,
        "recent_opps": recent_opps,
        "chart_stage_labels": [stage_display.get(r["stage"], r["stage"]) for r in stage_rows],
        "chart_stage_data": [r["c"] for r in stage_rows],
        "chart_rating_labels": [rating_display.get(r["rating"], r["rating"]) for r in rating_rows],
        "chart_rating_data": [r["c"] for r in rating_rows],
    }
    return render(request, "crm/overview.html", context)
