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
from django.db.models import Count, DecimalField, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.models import ContactMethod, Party, PartyRole
from apps.core.utils import write_audit_log

from .forms import (
    AccountForm,
    CampaignForm,
    CaseForm,
    ContactForm,
    CrmTaskForm,
    KnowledgeArticleForm,
    LeadForm,
    OpportunityForm,
)
from .models import (
    INDUSTRY_CHOICES,
    AccountProfile,
    Campaign,
    Case,
    ContactProfile,
    CrmTask,
    KnowledgeArticle,
    Lead,
    Opportunity,
)


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
        # Explicit tenant scope (defense-in-depth) — never trust a reverse-FK manager alone.
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, source_lead=obj).select_related("account")[:20],
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
        "tasks": CrmTask.objects.filter(
            tenant=request.tenant, related_opportunity=obj).select_related("owner")[:20],
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
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, campaign=obj).select_related("account")[:20],
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
        request, Case.objects.filter(tenant=request.tenant).select_related("account", "owner"),
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
        request, KnowledgeArticle.objects.filter(tenant=request.tenant).defer("body"),
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
        request, CrmTask.objects.filter(tenant=request.tenant).select_related("owner"),
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


# ===================== Accounts & Contacts — core.Party + CRM profile (1.1) =================
# Accounts/Contacts ARE the shared core.Party (one identity, many roles); CRM owns a one-to-one
# AccountProfile/ContactProfile carrying the rich fields. Full CRUD here manages the Party + its
# profile together. Routes are keyed by Party pk. Delete removes the underlying Party (cascading
# the profile/roles/addresses); opportunities/cases keep their rows with the link SET_NULL.
@login_required
def account_list(request):
    return crud_list(
        request,
        Party.objects.filter(tenant=request.tenant, kind="organization")
        .select_related("crm_account_profile", "crm_account_profile__owner"),
        "crm/account_list.html", search_fields=["name", "tax_id"],
        filters=[("industry", "crm_account_profile__industry", False),
                 ("source", "crm_account_profile__source", False)],
        extra_context={"industry_choices": INDUSTRY_CHOICES, "source_choices": Lead.SOURCE_CHOICES},
    )


@login_required
def account_detail(request, pk):
    obj = get_object_or_404(
        Party.objects.filter(tenant=request.tenant, kind="organization")
        .select_related("crm_account_profile", "crm_account_profile__owner",
                        "crm_account_profile__parent_account")
        .prefetch_related("roles", "addresses", "contact_methods"),
        pk=pk)
    return render(request, "crm/account_detail.html", {
        "obj": obj,
        "profile": getattr(obj, "crm_account_profile", None),
        "opportunities": Opportunity.objects.filter(tenant=request.tenant, account=obj).select_related("owner")[:20],
        "cases": Case.objects.filter(tenant=request.tenant, account=obj).select_related("owner")[:20],
        "child_accounts": AccountProfile.objects.filter(tenant=request.tenant, parent_account=obj).select_related("party")[:20],
        "stakeholders": ContactProfile.objects.filter(tenant=request.tenant, account=obj).select_related("party")[:20],
    })


@login_required
def account_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = AccountForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                party = Party.objects.create(
                    tenant=request.tenant, kind="organization",
                    name=form.cleaned_data["name"], tax_id=form.cleaned_data.get("tax_id", ""))
                profile = form.save(commit=False)
                profile.tenant = request.tenant
                profile.party = party
                profile.save()
            write_audit_log(request.user, party, "create")
            messages.success(request, "Account created.")
            return redirect("crm:account_detail", pk=party.pk)
    else:
        form = AccountForm(tenant=request.tenant)
    return render(request, "crm/account_form.html", {"form": form, "is_edit": False})


@login_required
def account_edit(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="organization")
    # Bind to the existing profile, or a new (unsaved) one carrying the party — so the form's
    # parent-account self-exclusion works and the profile INSERT happens inside the atomic block.
    profile = (AccountProfile.objects.filter(party=party).first()
               or AccountProfile(party=party, tenant=request.tenant))
    form = AccountForm(request.POST or None, instance=profile, tenant=request.tenant,
                       initial={"name": party.name, "tax_id": party.tax_id})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            party.name = form.cleaned_data["name"]
            party.tax_id = form.cleaned_data.get("tax_id", "")
            party.save(update_fields=["name", "tax_id"])
            p = form.save(commit=False)
            p.tenant = request.tenant
            p.party = party
            p.save()
        write_audit_log(request.user, party, "update")
        messages.success(request, "Account updated.")
        return redirect("crm:account_detail", pk=party.pk)
    return render(request, "crm/account_form.html", {"form": form, "is_edit": True, "obj": party})


@tenant_admin_required  # deleting a shared core.Party identity is privileged (cross-module blast radius)
@require_POST
def account_delete(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="organization")
    write_audit_log(request.user, party, "delete")
    party.delete()
    messages.success(request, "Account deleted.")
    return redirect("crm:account_list")


@login_required
def contact_list(request):
    return crud_list(
        request,
        Party.objects.filter(tenant=request.tenant, kind="person")
        .select_related("crm_contact_profile", "crm_contact_profile__account"),
        "crm/contact_list.html", search_fields=["name"],
        filters=[("source", "crm_contact_profile__source", False)],
        extra_context={"source_choices": Lead.SOURCE_CHOICES},
    )


@login_required
def contact_detail(request, pk):
    obj = get_object_or_404(
        Party.objects.filter(tenant=request.tenant, kind="person")
        .select_related("crm_contact_profile", "crm_contact_profile__account",
                        "crm_contact_profile__owner")
        .prefetch_related("roles", "contact_methods"),
        pk=pk)
    return render(request, "crm/contact_detail.html", {
        "obj": obj,
        "profile": getattr(obj, "crm_contact_profile", None),
        "opportunities": Opportunity.objects.filter(tenant=request.tenant, primary_contact=obj).select_related("account")[:20],
        "cases": Case.objects.filter(tenant=request.tenant, contact=obj).select_related("owner")[:20],
    })


@login_required
def contact_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ContactForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                party = Party.objects.create(
                    tenant=request.tenant, kind="person", name=form.cleaned_data["name"])
                profile = form.save(commit=False)
                profile.tenant = request.tenant
                profile.party = party
                profile.save()
            write_audit_log(request.user, party, "create")
            messages.success(request, "Contact created.")
            return redirect("crm:contact_detail", pk=party.pk)
    else:
        form = ContactForm(tenant=request.tenant)
    return render(request, "crm/contact_form.html", {"form": form, "is_edit": False})


@login_required
def contact_edit(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="person")
    profile = (ContactProfile.objects.filter(party=party).first()
               or ContactProfile(party=party, tenant=request.tenant))
    form = ContactForm(request.POST or None, instance=profile, tenant=request.tenant,
                       initial={"name": party.name})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            party.name = form.cleaned_data["name"]
            party.save(update_fields=["name"])
            p = form.save(commit=False)
            p.tenant = request.tenant
            p.party = party
            p.save()
        write_audit_log(request.user, party, "update")
        messages.success(request, "Contact updated.")
        return redirect("crm:contact_detail", pk=party.pk)
    return render(request, "crm/contact_form.html", {"form": form, "is_edit": True, "obj": party})


@tenant_admin_required  # deleting a shared core.Party identity is privileged (cross-module blast radius)
@require_POST
def contact_delete(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="person")
    write_audit_log(request.user, party, "delete")
    party.delete()
    messages.success(request, "Contact deleted.")
    return redirect("crm:contact_list")


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
        # Win rate: won and closed counts in a single annotated pass.
        close_agg = opps.aggregate(
            won=Count("id", filter=Q(stage="closed_won")),
            closed=Count("id", filter=Q(stage__in=["closed_won", "closed_lost"])),
        )
        stats["win_rate"] = round(close_agg["won"] / close_agg["closed"] * 100) if close_agg["closed"] else 0
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


# ============================================================================
# ===== Module 1 Extension — Sub-modules 1.7–1.12 views ======================
# ============================================================================
import secrets  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402

from .forms import (  # noqa: E402
    ApprovalRequestForm,
    ContractDocumentForm,
    CrmMilestoneForm,
    CrmProjectForm,
    DocTemplateForm,
    ExpenseForm,
    HealthScoreConfigForm,
    HealthScoreForm,
    OnboardingPlanForm,
    OnboardingStepForm,
    PartnerPortalAccessForm,
    ProductStockForm,
    PurchaseOrderForm,
    PurchaseOrderLineForm,
    SignerRecordForm,
    SurveyForm,
    TimesheetForm,
    WorkflowRuleForm,
)
from .models import (  # noqa: E402
    ApprovalRequest,
    ContractDocument,
    CrmMilestone,
    CrmProject,
    DocTemplate,
    Expense,
    HealthScore,
    HealthScoreConfig,
    OnboardingPlan,
    OnboardingStep,
    PartnerPortalAccess,
    ProductStock,
    PurchaseOrder,
    PurchaseOrderLine,
    SignerRecord,
    Survey,
    Timesheet,
    WorkflowLog,
    WorkflowRule,
    compute_health_score,
)

User = get_user_model()


# ------------------------------------------------------------ 1.7 Expenses
@login_required
def expense_list(request):
    return crud_list(
        request,
        Expense.objects.filter(tenant=request.tenant).select_related(
            "opportunity", "project", "submitted_by", "approved_by"),
        "crm/expense_list.html",
        search_fields=["number", "description", "opportunity__name"],
        filters=[("status", "status", False), ("category", "category", False)],
        extra_context={"status_choices": Expense.STATUS_CHOICES,
                       "category_choices": Expense.CATEGORY_CHOICES},
    )


@login_required
def expense_create(request):
    return crud_create(request, form_class=ExpenseForm, template="crm/expense_form.html",
                       success_url="crm:expense_list")


@login_required
def expense_detail(request, pk):
    obj = get_object_or_404(
        Expense.objects.select_related("opportunity", "project", "submitted_by", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/expense_detail.html", {"obj": obj})


@login_required
def expense_edit(request, pk):
    return crud_edit(request, model=Expense, pk=pk, form_class=ExpenseForm,
                     template="crm/expense_form.html", success_url="crm:expense_list")


@login_required
@require_POST
def expense_delete(request, pk):
    return crud_delete(request, model=Expense, pk=pk, success_url="crm:expense_list")


@tenant_admin_required  # approving is a privileged action — a manager/admin, not the submitter
@require_POST
def expense_approve(request, pk):
    obj = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    obj.status = "approved"
    obj.approved_by = request.user
    obj.save(update_fields=["status", "approved_by", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Expense {obj.number} approved.")
    return redirect("crm:expense_detail", pk=obj.pk)


@tenant_admin_required  # rejecting is a privileged action — a manager/admin, not the submitter
@require_POST
def expense_reject(request, pk):
    obj = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    obj.status = "rejected"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Expense {obj.number} rejected.")
    return redirect("crm:expense_detail", pk=obj.pk)


# ------------------------------------------------------------ 1.8 Projects
@login_required
def crmproject_list(request):
    return crud_list(
        request,
        CrmProject.objects.filter(tenant=request.tenant).select_related(
            "account", "owner", "source_opportunity"),
        "crm/crmproject_list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": CrmProject.STATUS_CHOICES},
    )


@login_required
def crmproject_create(request):
    return crud_create(request, form_class=CrmProjectForm, template="crm/crmproject_form.html",
                       success_url="crm:crmproject_list")


@login_required
def crmproject_detail(request, pk):
    obj = get_object_or_404(
        CrmProject.objects.select_related("account", "owner", "source_opportunity"),
        pk=pk, tenant=request.tenant)
    timesheets = Timesheet.objects.filter(tenant=request.tenant, project=obj)
    hours = timesheets.aggregate(total=Sum("hours"),
                                 billable=Sum("hours", filter=Q(is_billable=True)))
    expense_total = Expense.objects.filter(
        tenant=request.tenant, project=obj, status="approved").aggregate(t=Sum("amount"))["t"] or 0
    return render(request, "crm/crmproject_detail.html", {
        "obj": obj,
        "milestones": obj.milestones.filter(tenant=request.tenant).select_related("assignee"),
        "total_hours": hours["total"] or 0,
        "billable_hours": hours["billable"] or 0,
        "expense_total": expense_total,
    })


@login_required
def crmproject_edit(request, pk):
    return crud_edit(request, model=CrmProject, pk=pk, form_class=CrmProjectForm,
                     template="crm/crmproject_form.html", success_url="crm:crmproject_list")


@login_required
@require_POST
def crmproject_delete(request, pk):
    return crud_delete(request, model=CrmProject, pk=pk, success_url="crm:crmproject_list")


@login_required
@require_POST
def opportunity_to_project(request, pk):
    """1.8: convert a won Opportunity into a delivery Project (idempotent)."""
    opp = get_object_or_404(Opportunity, pk=pk, tenant=request.tenant)
    if opp.stage != "closed_won":
        messages.error(request, "Only won opportunities can be converted to a project.")
        return redirect("crm:opportunity_detail", pk=opp.pk)
    existing = CrmProject.objects.filter(tenant=request.tenant, source_opportunity=opp).first()
    if existing:
        messages.info(request, f"Project {existing.number} already exists for this opportunity.")
        return redirect("crm:crmproject_detail", pk=existing.pk)
    project = CrmProject.objects.create(
        tenant=request.tenant, name=f"{opp.name} — Delivery", account=opp.account,
        source_opportunity=opp, status="planning", budget=opp.amount, owner=opp.owner,
        description=f"Auto-created from won opportunity {opp.number}.")
    write_audit_log(request.user, project, "create", {"from_opportunity": opp.number})
    messages.success(request, f"Project {project.number} created from {opp.number}.")
    return redirect("crm:crmproject_detail", pk=project.pk)


# ------------------------------------------------------------ 1.8 Milestones
@login_required
def crmmilestone_list(request):
    return crud_list(
        request,
        CrmMilestone.objects.filter(tenant=request.tenant).select_related("project", "assignee"),
        "crm/crmmilestone_list.html",
        search_fields=["number", "title"],
        filters=[("status", "status", False), ("project", "project_id", True)],
        extra_context={"status_choices": CrmMilestone.STATUS_CHOICES,
                       "kind_choices": CrmMilestone.KIND_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def crmmilestone_create(request):
    return crud_create(request, form_class=CrmMilestoneForm, template="crm/crmmilestone_form.html",
                       success_url="crm:crmmilestone_list")


@login_required
def crmmilestone_detail(request, pk):
    obj = get_object_or_404(
        CrmMilestone.objects.select_related("project", "assignee", "parent"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/crmmilestone_detail.html", {
        "obj": obj,
        "subtasks": CrmMilestone.objects.filter(tenant=request.tenant, parent=obj).select_related("assignee"),
    })


@login_required
def crmmilestone_edit(request, pk):
    return crud_edit(request, model=CrmMilestone, pk=pk, form_class=CrmMilestoneForm,
                     template="crm/crmmilestone_form.html", success_url="crm:crmmilestone_list")


@login_required
@require_POST
def crmmilestone_delete(request, pk):
    return crud_delete(request, model=CrmMilestone, pk=pk, success_url="crm:crmmilestone_list")


# ------------------------------------------------------------ 1.8 Timesheets
@login_required
def timesheet_list(request):
    return crud_list(
        request,
        Timesheet.objects.filter(tenant=request.tenant).select_related(
            "project", "employee", "milestone", "client"),
        "crm/timesheet_list.html",
        search_fields=["number", "description", "employee__username"],
        filters=[("status", "status", False), ("project", "project_id", True),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": Timesheet.STATUS_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def timesheet_create(request):
    return crud_create(request, form_class=TimesheetForm, template="crm/timesheet_form.html",
                       success_url="crm:timesheet_list")


@login_required
def timesheet_detail(request, pk):
    obj = get_object_or_404(
        Timesheet.objects.select_related("project", "employee", "milestone", "client", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/timesheet_detail.html", {"obj": obj})


@login_required
def timesheet_edit(request, pk):
    return crud_edit(request, model=Timesheet, pk=pk, form_class=TimesheetForm,
                     template="crm/timesheet_form.html", success_url="crm:timesheet_list")


@login_required
@require_POST
def timesheet_delete(request, pk):
    return crud_delete(request, model=Timesheet, pk=pk, success_url="crm:timesheet_list")


# ------------------------------------------------------------ 1.9 Document templates
@login_required
def doctemplate_list(request):
    return crud_list(
        request,
        DocTemplate.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/doctemplate_list.html",
        search_fields=["number", "name"],
        filters=[("template_type", "template_type", False), ("is_active", "is_active", False)],
        extra_context={"type_choices": DocTemplate.TYPE_CHOICES},
    )


@login_required
def doctemplate_create(request):
    return crud_create(request, form_class=DocTemplateForm, template="crm/doctemplate_form.html",
                       success_url="crm:doctemplate_list")


@login_required
def doctemplate_detail(request, pk):
    obj = get_object_or_404(DocTemplate.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/doctemplate_detail.html", {
        "obj": obj,
        "contract_count": ContractDocument.objects.filter(tenant=request.tenant, template=obj).count(),
    })


@login_required
def doctemplate_edit(request, pk):
    return crud_edit(request, model=DocTemplate, pk=pk, form_class=DocTemplateForm,
                     template="crm/doctemplate_form.html", success_url="crm:doctemplate_list")


@login_required
@require_POST
def doctemplate_delete(request, pk):
    return crud_delete(request, model=DocTemplate, pk=pk, success_url="crm:doctemplate_list")


# ------------------------------------------------------------ 1.9 Contract documents
@login_required
def contractdocument_list(request):
    return crud_list(
        request,
        ContractDocument.objects.filter(tenant=request.tenant).select_related(
            "template", "opportunity", "account", "owner"),
        "crm/contractdocument_list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("opportunity", "opportunity_id", True)],
        extra_context={"status_choices": ContractDocument.STATUS_CHOICES,
                       "opportunities": Opportunity.objects.filter(tenant=request.tenant).order_by("-created_at")[:200]},
    )


@login_required
def contractdocument_create(request):
    return crud_create(request, form_class=ContractDocumentForm,
                       template="crm/contractdocument_form.html",
                       success_url="crm:contractdocument_list")


@login_required
def contractdocument_detail(request, pk):
    obj = get_object_or_404(
        ContractDocument.objects.select_related("template", "opportunity", "account", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/contractdocument_detail.html", {
        "obj": obj,
        "signers": obj.signers.select_related("signer_party").all(),
        "signer_form": SignerRecordForm(tenant=request.tenant),
    })


@login_required
def contractdocument_edit(request, pk):
    return crud_edit(request, model=ContractDocument, pk=pk, form_class=ContractDocumentForm,
                     template="crm/contractdocument_form.html", success_url="crm:contractdocument_list")


@login_required
@require_POST
def contractdocument_delete(request, pk):
    return crud_delete(request, model=ContractDocument, pk=pk, success_url="crm:contractdocument_list")


@login_required
@require_POST
def contractdocument_add_signer(request, pk):
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    form = SignerRecordForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        signer = form.save(commit=False)
        signer.tenant = request.tenant
        signer.contract = contract
        signer.token = secrets.token_urlsafe(32)
        signer.save()
        write_audit_log(request.user, contract, "update",
                        {"action": "add_signer", "email": signer.signer_email})
        messages.success(request, "Signer added.")
    else:
        messages.error(request, "Could not add signer — name and email are required.")
    return redirect("crm:contractdocument_detail", pk=contract.pk)


@login_required
@require_POST
def contractdocument_remove_signer(request, pk, signer_pk):
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    signer = get_object_or_404(SignerRecord, pk=signer_pk, contract=contract, tenant=request.tenant)
    signer.delete()
    messages.success(request, "Signer removed.")
    return redirect("crm:contractdocument_detail", pk=contract.pk)


def sign_document(request, token):
    """Public e-signature page (1.9) — token-scoped, no login. The 32-byte URL-safe
    token is the bearer credential; an unguessable token gates access to one signer row."""
    signer = get_object_or_404(SignerRecord.objects.select_related("contract"), token=token)
    contract = signer.contract
    already = signer.signed_at is not None or signer.declined_at is not None
    if request.method == "POST" and not already:
        with transaction.atomic():
            # Row-lock the signer to avoid a double-sign / lost-update race between two
            # concurrent last-signer POSTs (re-check state inside the lock).
            signer = (SignerRecord.objects.select_for_update()
                      .select_related("contract").get(pk=signer.pk))
            contract = signer.contract
            if signer.signed_at is None and signer.declined_at is None:
                signer.ip_address = request.META.get("REMOTE_ADDR")
                if request.POST.get("action") == "decline":
                    signer.declined_at = timezone.now()
                    signer.save(update_fields=["declined_at", "ip_address"])
                    contract.status = "declined"
                    contract.save(update_fields=["status", "updated_at"])
                else:
                    signer.signed_at = timezone.now()
                    signer.save(update_fields=["signed_at", "ip_address"])
                    if not contract.signers.filter(signed_at__isnull=True).exists():
                        contract.status = "signed"
                        contract.signed_at = timezone.now()
                        contract.save(update_fields=["status", "signed_at", "updated_at"])
                    elif contract.status in ("draft", "sent"):
                        contract.status = "viewed"
                        contract.save(update_fields=["status", "updated_at"])
        return redirect("crm:sign_document", token=token)
    if signer.viewed_at is None:
        signer.viewed_at = timezone.now()
        signer.save(update_fields=["viewed_at"])
    return render(request, "crm/sign_document.html",
                  {"signer": signer, "contract": contract, "already": already})


# ------------------------------------------------------------ 1.10 Workflow rules
@login_required
def workflowrule_list(request):
    return crud_list(
        request,
        WorkflowRule.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/workflowrule_list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False), ("trigger_entity", "trigger_entity", False)],
        extra_context={"entity_choices": WorkflowRule.ENTITY_CHOICES,
                       "event_choices": WorkflowRule.EVENT_CHOICES},
    )


@login_required
def workflowrule_create(request):
    return crud_create(request, form_class=WorkflowRuleForm, template="crm/workflowrule_form.html",
                       success_url="crm:workflowrule_list")


@login_required
def workflowrule_detail(request, pk):
    obj = get_object_or_404(WorkflowRule.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflowrule_detail.html", {
        "obj": obj,
        "logs": WorkflowLog.objects.filter(tenant=request.tenant, rule=obj)[:10],
    })


@login_required
def workflowrule_edit(request, pk):
    return crud_edit(request, model=WorkflowRule, pk=pk, form_class=WorkflowRuleForm,
                     template="crm/workflowrule_form.html", success_url="crm:workflowrule_list")


@login_required
@require_POST
def workflowrule_delete(request, pk):
    return crud_delete(request, model=WorkflowRule, pk=pk, success_url="crm:workflowrule_list")


# ------------------------------------------------------------ 1.10 Workflow logs (read-only)
@login_required
def workflowlog_list(request):
    return crud_list(
        request,
        WorkflowLog.objects.filter(tenant=request.tenant).select_related("rule"),
        "crm/workflowlog_list.html",
        search_fields=["record_label", "error_msg"],
        filters=[("status", "status", False), ("rule", "rule_id", True)],
        extra_context={"status_choices": WorkflowLog.STATUS_CHOICES,
                       "rules": WorkflowRule.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def workflowlog_detail(request, pk):
    obj = get_object_or_404(WorkflowLog.objects.select_related("rule"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflowlog_detail.html", {"obj": obj})


# ------------------------------------------------------------ 1.10 Approval requests
@login_required
def approvalrequest_list(request):
    return crud_list(
        request,
        ApprovalRequest.objects.filter(tenant=request.tenant).select_related(
            "approver", "requested_by", "rule"),
        "crm/approvalrequest_list.html",
        search_fields=["number", "subject", "record_label"],
        filters=[("status", "status", False), ("approver", "approver_id", True)],
        extra_context={"status_choices": ApprovalRequest.STATUS_CHOICES,
                       "approvers": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def approvalrequest_create(request):
    return crud_create(request, form_class=ApprovalRequestForm,
                       template="crm/approvalrequest_form.html", success_url="crm:approvalrequest_list")


@login_required
def approvalrequest_detail(request, pk):
    obj = get_object_or_404(
        ApprovalRequest.objects.select_related("approver", "requested_by", "rule"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/approvalrequest_detail.html", {"obj": obj})


@login_required
def approvalrequest_edit(request, pk):
    return crud_edit(request, model=ApprovalRequest, pk=pk, form_class=ApprovalRequestForm,
                     template="crm/approvalrequest_form.html", success_url="crm:approvalrequest_list")


@login_required
@require_POST
def approvalrequest_delete(request, pk):
    return crud_delete(request, model=ApprovalRequest, pk=pk, success_url="crm:approvalrequest_list")


@tenant_admin_required  # approval decisions are privileged (manager/admin only)
@require_POST
def approvalrequest_approve(request, pk):
    obj = get_object_or_404(ApprovalRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approved_at = timezone.now()
        obj.reason = request.POST.get("reason", obj.reason)
        obj.save(update_fields=["status", "approved_at", "reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, f"{obj.number} approved.")
    return redirect("crm:approvalrequest_detail", pk=obj.pk)


@tenant_admin_required  # approval decisions are privileged (manager/admin only)
@require_POST
def approvalrequest_reject(request, pk):
    obj = get_object_or_404(ApprovalRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.rejected_at = timezone.now()
        obj.reason = request.POST.get("reason", obj.reason)
        obj.save(update_fields=["status", "rejected_at", "reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"{obj.number} rejected.")
    return redirect("crm:approvalrequest_detail", pk=obj.pk)


# ------------------------------------------------------------ 1.11 Onboarding plans
@login_required
def onboardingplan_list(request):
    return crud_list(
        request,
        OnboardingPlan.objects.filter(tenant=request.tenant).select_related("account", "owner"),
        "crm/onboardingplan_list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("account", "account_id", True)],
        extra_context={"status_choices": OnboardingPlan.STATUS_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def onboardingplan_create(request):
    return crud_create(request, form_class=OnboardingPlanForm,
                       template="crm/onboardingplan_form.html", success_url="crm:onboardingplan_list")


@login_required
def onboardingplan_detail(request, pk):
    obj = get_object_or_404(OnboardingPlan.objects.select_related("account", "owner"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/onboardingplan_detail.html", {
        "obj": obj,
        "steps": obj.steps.select_related("assignee").all(),
        "step_form": OnboardingStepForm(tenant=request.tenant),
    })


@login_required
def onboardingplan_edit(request, pk):
    return crud_edit(request, model=OnboardingPlan, pk=pk, form_class=OnboardingPlanForm,
                     template="crm/onboardingplan_form.html", success_url="crm:onboardingplan_list")


@login_required
@require_POST
def onboardingplan_delete(request, pk):
    return crud_delete(request, model=OnboardingPlan, pk=pk, success_url="crm:onboardingplan_list")


@login_required
@require_POST
def onboardingstep_add(request, pk):
    plan = get_object_or_404(OnboardingPlan, pk=pk, tenant=request.tenant)
    form = OnboardingStepForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        step = form.save(commit=False)
        step.tenant = request.tenant
        step.plan = plan
        step.save()
        messages.success(request, "Step added.")
    else:
        messages.error(request, "Could not add step — a title is required.")
    return redirect("crm:onboardingplan_detail", pk=plan.pk)


@login_required
@require_POST
def onboardingstep_complete(request, step_pk):
    step = get_object_or_404(OnboardingStep.objects.select_related("plan"),
                             pk=step_pk, tenant=request.tenant)
    step.completed_at = None if step.completed_at else timezone.now()  # toggle
    step.save(update_fields=["completed_at"])
    plan = step.plan
    if not plan.steps.filter(tenant=request.tenant, completed_at__isnull=True).exists():
        plan.status = "completed"
        plan.completed_at = timezone.now()
        plan.save(update_fields=["status", "completed_at", "updated_at"])
    return redirect("crm:onboardingplan_detail", pk=step.plan_id)


@login_required
@require_POST
def onboardingstep_delete(request, step_pk):
    step = get_object_or_404(OnboardingStep, pk=step_pk, tenant=request.tenant)
    plan_id = step.plan_id
    step.delete()
    messages.success(request, "Step removed.")
    return redirect("crm:onboardingplan_detail", pk=plan_id)


# ------------------------------------------------------------ 1.11 Health scores
@login_required
def healthscore_list(request):
    return crud_list(
        request,
        HealthScore.objects.filter(tenant=request.tenant).select_related("account"),
        "crm/healthscore_list.html",
        search_fields=["number", "account__name"],
        filters=[("tier", "tier", False)],
        extra_context={"tier_choices": HealthScore.TIER_CHOICES},
    )


@login_required
def healthscore_create(request):
    return crud_create(request, form_class=HealthScoreForm, template="crm/healthscore_form.html",
                       success_url="crm:healthscore_list")


@login_required
def healthscore_detail(request, pk):
    obj = get_object_or_404(HealthScore.objects.select_related("account"), pk=pk, tenant=request.tenant)
    return render(request, "crm/healthscore_detail.html", {"obj": obj})


@login_required
def healthscore_edit(request, pk):
    return crud_edit(request, model=HealthScore, pk=pk, form_class=HealthScoreForm,
                     template="crm/healthscore_form.html", success_url="crm:healthscore_list")


@login_required
@require_POST
def healthscore_delete(request, pk):
    return crud_delete(request, model=HealthScore, pk=pk, success_url="crm:healthscore_list")


@login_required
@require_POST
def recompute_health_score(request, pk):
    obj = get_object_or_404(HealthScore.objects.select_related("account"), pk=pk, tenant=request.tenant)
    compute_health_score(obj.account, request.tenant)
    messages.success(request, "Health score recomputed.")
    return redirect("crm:healthscore_detail", pk=obj.pk)


@login_required
def health_config_edit(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before configuring health scoring.")
        return redirect("dashboard:home")
    config, _ = HealthScoreConfig.objects.get_or_create(tenant=request.tenant)
    if request.method == "POST":
        form = HealthScoreConfigForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, config, "update")
            messages.success(request, "Health-scoring weights saved.")
            return redirect("crm:healthscore_list")
    else:
        form = HealthScoreConfigForm(instance=config, tenant=request.tenant)
    return render(request, "crm/health_config_form.html", {"form": form, "config": config})


# ------------------------------------------------------------ 1.11 Surveys
@login_required
def survey_list(request):
    return crud_list(
        request,
        Survey.objects.filter(tenant=request.tenant).select_related("account", "contact", "related_case"),
        "crm/survey_list.html",
        search_fields=["number", "feedback_text", "account__name"],
        filters=[("survey_type", "survey_type", False), ("classification", "classification", False),
                 ("account", "account_id", True)],
        extra_context={"type_choices": Survey.TYPE_CHOICES,
                       "classification_choices": Survey.CLASSIFICATION_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def survey_create(request):
    return crud_create(request, form_class=SurveyForm, template="crm/survey_form.html",
                       success_url="crm:survey_list")


@login_required
def survey_detail(request, pk):
    obj = get_object_or_404(Survey.objects.select_related("account", "contact", "related_case"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/survey_detail.html", {"obj": obj})


@login_required
def survey_edit(request, pk):
    return crud_edit(request, model=Survey, pk=pk, form_class=SurveyForm,
                     template="crm/survey_form.html", success_url="crm:survey_list")


@login_required
@require_POST
def survey_delete(request, pk):
    return crud_delete(request, model=Survey, pk=pk, success_url="crm:survey_list")


def survey_respond(request, token):
    """Public survey-response page (1.11) — token-scoped, no login."""
    survey = get_object_or_404(Survey, token=token)
    if request.method == "POST" and survey.responded_at is None:
        raw = request.POST.get("score", "")
        # Clamp to the model's 0–10 range — this is a public endpoint, never trust the POST.
        survey.score = max(0, min(10, int(raw))) if raw.isdigit() else None
        survey.feedback_text = request.POST.get("feedback_text", "").strip()
        survey.responded_at = timezone.now()
        survey.save()  # save() auto-classifies NPS
        return redirect("crm:survey_respond", token=token)
    return render(request, "crm/survey_respond.html", {"survey": survey})


# ------------------------------------------------------------ 1.12 Product stock
@login_required
def productstock_list(request):
    return crud_list(
        request,
        ProductStock.objects.filter(tenant=request.tenant),
        "crm/productstock_list.html",
        search_fields=["number", "name", "sku"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def productstock_create(request):
    return crud_create(request, form_class=ProductStockForm, template="crm/productstock_form.html",
                       success_url="crm:productstock_list")


@login_required
def productstock_detail(request, pk):
    obj = get_object_or_404(ProductStock, pk=pk, tenant=request.tenant)
    return render(request, "crm/productstock_detail.html", {"obj": obj})


@login_required
def productstock_edit(request, pk):
    return crud_edit(request, model=ProductStock, pk=pk, form_class=ProductStockForm,
                     template="crm/productstock_form.html", success_url="crm:productstock_list")


@login_required
@require_POST
def productstock_delete(request, pk):
    return crud_delete(request, model=ProductStock, pk=pk, success_url="crm:productstock_list")


# ------------------------------------------------------------ 1.12 Purchase orders
@login_required
def crm_po_list(request):
    return crud_list(
        request,
        PurchaseOrder.objects.filter(tenant=request.tenant).select_related("vendor", "owner"),
        "crm/crm_po_list.html",
        search_fields=["number", "vendor__name", "notes"],
        filters=[("status", "status", False), ("vendor", "vendor_id", True)],
        extra_context={"status_choices": PurchaseOrder.STATUS_CHOICES,
                       "vendors": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def crm_po_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            po = form.save(commit=False)
            po.tenant = request.tenant
            po.save()
            write_audit_log(request.user, po, "create")
            messages.success(request, f"Purchase order {po.number} created — add line items below.")
            return redirect("crm:crm_po_detail", pk=po.pk)
    else:
        form = PurchaseOrderForm(tenant=request.tenant)
    return render(request, "crm/crm_po_form.html", {"form": form, "is_edit": False})


@login_required
def crm_po_detail(request, pk):
    obj = get_object_or_404(PurchaseOrder.objects.select_related("vendor", "owner"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/crm_po_detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("product").all(),
        "line_form": PurchaseOrderLineForm(tenant=request.tenant),
    })


@login_required
def crm_po_edit(request, pk):
    return crud_edit(request, model=PurchaseOrder, pk=pk, form_class=PurchaseOrderForm,
                     template="crm/crm_po_form.html", success_url="crm:crm_po_list")


@login_required
@require_POST
def crm_po_delete(request, pk):
    return crud_delete(request, model=PurchaseOrder, pk=pk, success_url="crm:crm_po_list")


@login_required
@require_POST
def crm_po_add_line(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    form = PurchaseOrderLineForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        with transaction.atomic():
            line = form.save(commit=False)
            line.tenant = request.tenant
            line.purchase_order = po
            line.save()
            po.recalc_total()
        messages.success(request, "Line item added.")
    else:
        messages.error(request, "Could not add line — item name is required.")
    return redirect("crm:crm_po_detail", pk=po.pk)


@login_required
@require_POST
def crm_po_remove_line(request, pk, line_pk):
    po = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    line = get_object_or_404(PurchaseOrderLine, pk=line_pk, purchase_order=po, tenant=request.tenant)
    with transaction.atomic():
        line.delete()
        po.recalc_total()
    messages.success(request, "Line item removed.")
    return redirect("crm:crm_po_detail", pk=po.pk)


@login_required
@require_POST
def crm_po_receive(request, pk):
    """1.12: mark a PO received and add its quantities to linked ProductStock on-hand."""
    po = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if po.status not in ("draft", "sent"):
        messages.info(request, "Only a draft or sent purchase order can be received.")
        return redirect("crm:crm_po_detail", pk=po.pk)
    with transaction.atomic():
        for line in po.lines.select_related("product"):
            if line.product_id:
                ProductStock.objects.filter(pk=line.product_id, tenant=request.tenant).update(
                    on_hand_qty=F("on_hand_qty") + line.quantity)
        po.status = "received"
        po.received_at = timezone.now()
        po.save(update_fields=["status", "received_at", "updated_at"])
    write_audit_log(request.user, po, "update", {"action": "receive"})
    messages.success(request, f"PO {po.number} received — stock levels updated.")
    return redirect("crm:crm_po_detail", pk=po.pk)


# ------------------------------------------------------------ 1.12 Partner portal access (admin)
@login_required
def partnerportalaccess_list(request):
    return crud_list(
        request,
        PartnerPortalAccess.objects.filter(tenant=request.tenant).select_related(
            "partner_party", "portal_user"),
        "crm/partnerportalaccess_list.html",
        search_fields=["number", "partner_party__name", "portal_user__username"],
        filters=[("is_active", "is_active", False), ("access_level", "access_level", False)],
        extra_context={"access_choices": PartnerPortalAccess.ACCESS_CHOICES},
    )


@login_required
def partnerportalaccess_create(request):
    return crud_create(request, form_class=PartnerPortalAccessForm,
                       template="crm/partnerportalaccess_form.html",
                       success_url="crm:partnerportalaccess_list")


@login_required
def partnerportalaccess_detail(request, pk):
    obj = get_object_or_404(
        PartnerPortalAccess.objects.select_related("partner_party", "portal_user"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/partnerportalaccess_detail.html", {"obj": obj})


@login_required
def partnerportalaccess_edit(request, pk):
    return crud_edit(request, model=PartnerPortalAccess, pk=pk, form_class=PartnerPortalAccessForm,
                     template="crm/partnerportalaccess_form.html",
                     success_url="crm:partnerportalaccess_list")


@login_required
@require_POST
def partnerportalaccess_delete(request, pk):
    return crud_delete(request, model=PartnerPortalAccess, pk=pk,
                       success_url="crm:partnerportalaccess_list")


# ------------------------------------------------------------ 1.12 Partner portal (partner-facing)
def _portal_access(request):
    """Return the active PartnerPortalAccess row for the logged-in portal user, or None."""
    if not request.user.is_authenticated:
        return None
    return (PartnerPortalAccess.objects
            .filter(portal_user=request.user, tenant=request.tenant, is_active=True)
            .select_related("partner_party").first())


@login_required
def portal_dashboard(request):
    access = _portal_access(request)
    if access is None:
        messages.error(request, "You don't have partner portal access.")
        return redirect("dashboard:home")
    po_count = PurchaseOrder.objects.filter(tenant=access.tenant_id, vendor=access.partner_party).count()
    return render(request, "crm/portal_dashboard.html", {"access": access, "po_count": po_count})


@login_required
def portal_po_list(request):
    access = _portal_access(request)
    if access is None:
        messages.error(request, "You don't have partner portal access.")
        return redirect("dashboard:home")
    orders = (PurchaseOrder.objects
              .filter(tenant=access.tenant_id, vendor=access.partner_party)
              .order_by("-created_at"))
    return render(request, "crm/portal_po_list.html", {"access": access, "orders": orders})


@login_required
def portal_stock(request):
    access = _portal_access(request)
    if access is None or not access.can_view_stock:
        messages.error(request, "You don't have access to stock levels.")
        return redirect("crm:portal_dashboard" if access else "dashboard:home")
    products = ProductStock.objects.filter(tenant=access.tenant_id, is_active=True).order_by("name")
    return render(request, "crm/portal_stock.html", {"access": access, "products": products})
