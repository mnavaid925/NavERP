"""CRM (Module 1) views — function-based, ``@login_required``, tenant-scoped.

Full CRUD for the six CRM-owned models via the shared ``apps.core.crud`` helpers (search +
int-FK-guarded filters + windowed pagination + audit), plus:
  * Account/Contact "lenses" over ``core.Party`` (1.1 — no duplication of the shared master),
  * one-click Lead conversion (creates Party + roles + an Opportunity),
  * a CRM analytics overview (1.6) using the dashboard's json_script + Chart.js pattern.
"""
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, DecimalField, F, Max, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template import Context, Engine, Library
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import ContactMethod, Party, PartyRole
from apps.core.utils import write_audit_log

from .forms import (
    AccountForm,
    CalendarEventForm,
    CommunicationLogForm,
    EventAttendeeForm,
    PublicRsvpForm,
    CampaignForm,
    CampaignMemberForm,
    CaseForm,
    ContactForm,
    CrmTaskForm,
    CaseCommentForm,
    CustomerPortalAccessForm,
    EmailCampaignForm,
    EmailTemplateForm,
    KbCategoryForm,
    KnowledgeArticleForm,
    LandingPageForm,
    LeadForm,
    OpportunityForm,
    OpportunitySplitForm,
    PriceBookForm,
    ProductForm,
    PublicCommentForm,
    PublicLeadForm,
    PublicSatisfactionForm,
    QuoteForm,
    QuoteLineForm,
    SalesQuotaForm,
    SlaPolicyForm,
    TerritoryForm,
)
from .models import (
    INDUSTRY_CHOICES,
    AccountProfile,
    CalendarEvent,
    CommunicationLog,
    EventAttendee,
    Campaign,
    CampaignMember,
    Case,
    CaseComment,
    ContactProfile,
    CrmTask,
    CustomerPortalAccess,
    EmailCampaign,
    EmailTemplate,
    FormSubmission,
    KbCategory,
    KnowledgeArticle,
    LandingPage,
    Lead,
    Opportunity,
    OpportunitySplit,
    PriceBook,
    Product,
    Quote,
    QuoteLine,
    SalesQuota,
    SlaPolicy,
    Territory,
)


# ===================================================================== Leads (1.1)
@login_required
def lead_list(request):
    return crud_list(
        request, Lead.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/directory/lead/list.html",
        search_fields=["name", "company", "email", "number"],
        filters=[("status", "status", False), ("rating", "rating", False), ("source", "source", False)],
        extra_context={"status_choices": Lead.STATUS_CHOICES,
                       "rating_choices": Lead.RATING_CHOICES,
                       "source_choices": Lead.SOURCE_CHOICES},
    )


@login_required
def lead_create(request):
    return crud_create(request, form_class=LeadForm, template="crm/directory/lead/form.html",
                       success_url="crm:lead_list")


@login_required
def lead_detail(request, pk):
    obj = get_object_or_404(Lead.objects.select_related("owner", "converted_party"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/directory/lead/detail.html", {
        "obj": obj,
        # Explicit tenant scope (defense-in-depth) — never trust a reverse-FK manager alone.
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, source_lead=obj).select_related("account")[:20],
    })


@login_required
def lead_edit(request, pk):
    return crud_edit(request, model=Lead, pk=pk, form_class=LeadForm,
                     template="crm/directory/lead/form.html", success_url="crm:lead_list")


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


# ============================================================================
# ===== 1.2 Sales Force Automation (recreated) ===============================
# Opportunity Management (+ Kanban board + commission splits), Product Catalog &
# Quoting (products / price books / quote builder), and Forecasting (quotas + dashboard).
# ============================================================================

# ------------------------------------------------------------ Opportunities (1.2)
@login_required
def opportunity_list(request):
    return crud_list(
        request,
        Opportunity.objects.filter(tenant=request.tenant).select_related("account", "owner", "territory"),
        "crm/sales/opportunity/list.html",
        search_fields=["name", "number"],
        filters=[("stage", "stage", False), ("forecast_category", "forecast_category", False),
                 ("account", "account_id", True), ("territory", "territory_id", True)],
        extra_context={"stage_choices": Opportunity.STAGE_CHOICES,
                       "forecast_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name"),
                       "territories": Territory.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def opportunity_create(request):
    return crud_create(request, form_class=OpportunityForm, template="crm/sales/opportunity/form.html",
                       success_url="crm:opportunity_list")


@login_required
def opportunity_detail(request, pk):
    obj = get_object_or_404(
        Opportunity.objects.select_related(
            "account", "primary_contact", "owner", "source_lead", "campaign", "territory"),
        pk=pk, tenant=request.tenant)
    splits = OpportunitySplit.objects.filter(
        tenant=request.tenant, opportunity=obj).select_related("user")
    rev_total = splits.filter(split_type="revenue").aggregate(t=Sum("percentage"))["t"] or 0
    return render(request, "crm/sales/opportunity/detail.html", {
        "obj": obj,
        "splits": splits,
        "revenue_split_total": rev_total,
        "split_form": OpportunitySplitForm(tenant=request.tenant),
        "quotes": Quote.objects.filter(tenant=request.tenant, opportunity=obj).select_related("account")[:20],
        "tasks": CrmTask.objects.filter(
            tenant=request.tenant, related_opportunity=obj).select_related("owner")[:20],
    })


@login_required
def opportunity_edit(request, pk):
    return crud_edit(request, model=Opportunity, pk=pk, form_class=OpportunityForm,
                     template="crm/sales/opportunity/form.html", success_url="crm:opportunity_list")


@login_required
@require_POST
def opportunity_delete(request, pk):
    return crud_delete(request, model=Opportunity, pk=pk, success_url="crm:opportunity_list")


@login_required
def opportunity_board(request):
    """Kanban pipeline board — opportunities grouped into a column per stage with per-stage
    count + amount totals (aggregated DB-side; each column previews its top deals)."""
    base = Opportunity.objects.filter(tenant=request.tenant).select_related("account", "owner", "territory")
    # One grouped query for all per-stage count + amount totals (instead of 6 aggregate round-trips).
    stage_agg = {r["stage"]: r for r in base.values("stage").annotate(c=Count("id"), total=Sum("amount"))}
    columns = []
    for value, label in Opportunity.STAGE_CHOICES:
        row = stage_agg.get(value, {})
        columns.append({
            "value": value, "label": label,
            "count": row.get("c") or 0, "total": row.get("total") or 0,
            "opps": list(base.filter(stage=value).order_by("-amount")[:50]),
        })
    return render(request, "crm/sales/pipeline.html", {"columns": columns})


# Forward-only stage flow used by the board's quick-advance button.
_OPP_FLOW = ["prospecting", "qualification", "proposal", "negotiation", "closed_won"]


@login_required
@require_POST
def opportunity_advance(request, pk):
    """Advance an opportunity one stage along the win path (board/detail quick action)."""
    opp = get_object_or_404(Opportunity, pk=pk, tenant=request.tenant)
    if opp.stage in _OPP_FLOW and opp.stage != "closed_won":
        opp.stage = _OPP_FLOW[_OPP_FLOW.index(opp.stage) + 1]
        if opp.stage == "closed_won":
            opp.probability = 100
            opp.forecast_category = "closed"
        opp.save()  # save() stamps stage_changed_at
        write_audit_log(request.user, opp, "update", {"action": "advance", "stage": opp.stage})
        messages.success(request, f"Advanced to {opp.get_stage_display()}.")
    else:
        messages.info(request, "This opportunity can't be advanced further.")
    # Fixed destinations only (no user-controlled redirect → no open-redirect).
    if request.POST.get("next") == "board":
        return redirect("crm:opportunity_board")
    return redirect("crm:opportunity_detail", pk=opp.pk)


@login_required
@require_POST
def opportunitysplit_add(request, pk):
    opp = get_object_or_404(Opportunity, pk=pk, tenant=request.tenant)
    form = OpportunitySplitForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "Could not add split — check the fields.")
        return redirect("crm:opportunity_detail", pk=opp.pk)
    split = form.save(commit=False)
    split.tenant = request.tenant
    split.opportunity = opp
    try:
        split.clean()  # enforces revenue splits ≤ 100% across the opportunity
    except ValidationError as e:
        messages.error(request, "; ".join(e.messages))
        return redirect("crm:opportunity_detail", pk=opp.pk)
    split.save()
    messages.success(request, "Split added.")
    return redirect("crm:opportunity_detail", pk=opp.pk)


@login_required
@require_POST
def opportunitysplit_remove(request, split_pk):
    split = get_object_or_404(OpportunitySplit, pk=split_pk, tenant=request.tenant)
    opp_id = split.opportunity_id
    split.delete()
    messages.success(request, "Split removed.")
    return redirect("crm:opportunity_detail", pk=opp_id)


# ------------------------------------------------------------ Territories (1.2)
@login_required
def territory_list(request):
    return crud_list(
        request,
        # defer the large description TextField — not rendered on the list.
        Territory.objects.filter(tenant=request.tenant).select_related("parent", "manager").defer("description"),
        "crm/sales/territory/list.html",
        search_fields=["number", "name", "region", "segment"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def territory_create(request):
    return crud_create(request, form_class=TerritoryForm, template="crm/sales/territory/form.html",
                       success_url="crm:territory_list")


@login_required
def territory_detail(request, pk):
    obj = get_object_or_404(Territory.objects.select_related("parent", "manager"), pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/territory/detail.html", {
        "obj": obj,
        "children": Territory.objects.filter(tenant=request.tenant, parent=obj).select_related("manager"),
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, territory=obj).select_related("account")[:20],
    })


@login_required
def territory_edit(request, pk):
    return crud_edit(request, model=Territory, pk=pk, form_class=TerritoryForm,
                     template="crm/sales/territory/form.html", success_url="crm:territory_list")


@login_required
@require_POST
def territory_delete(request, pk):
    return crud_delete(request, model=Territory, pk=pk, success_url="crm:territory_list")


# ------------------------------------------------------------ Products (1.2 catalog)
@login_required
def product_list(request):
    return crud_list(
        request,
        Product.objects.filter(tenant=request.tenant).defer("description"),  # description not on the list
        "crm/sales/product/list.html",
        search_fields=["number", "name", "sku"],
        filters=[("product_type", "product_type", False), ("is_active", "is_active", False)],
        extra_context={"type_choices": Product.TYPE_CHOICES},
    )


@login_required
def product_create(request):
    return crud_create(request, form_class=ProductForm, template="crm/sales/product/form.html",
                       success_url="crm:product_list")


@login_required
def product_detail(request, pk):
    obj = get_object_or_404(Product, pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/product/detail.html", {"obj": obj})


@login_required
def product_edit(request, pk):
    return crud_edit(request, model=Product, pk=pk, form_class=ProductForm,
                     template="crm/sales/product/form.html", success_url="crm:product_list")


@login_required
@require_POST
def product_delete(request, pk):
    return crud_delete(request, model=Product, pk=pk, success_url="crm:product_list")


# ------------------------------------------------------------ Price books (1.2)
@login_required
def pricebook_list(request):
    return crud_list(
        request,
        PriceBook.objects.filter(tenant=request.tenant).defer("description"),  # description not on the list
        "crm/sales/pricebook/list.html",
        search_fields=["number", "name", "region", "tier"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def pricebook_create(request):
    return crud_create(request, form_class=PriceBookForm, template="crm/sales/pricebook/form.html",
                       success_url="crm:pricebook_list")


@login_required
def pricebook_detail(request, pk):
    obj = get_object_or_404(PriceBook, pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/pricebook/detail.html", {"obj": obj})


@login_required
def pricebook_edit(request, pk):
    return crud_edit(request, model=PriceBook, pk=pk, form_class=PriceBookForm,
                     template="crm/sales/pricebook/form.html", success_url="crm:pricebook_list")


@login_required
@require_POST
def pricebook_delete(request, pk):
    return crud_delete(request, model=PriceBook, pk=pk, success_url="crm:pricebook_list")


# ------------------------------------------------------------ Quotes (1.2 quoting)
@login_required
def quote_list(request):
    return crud_list(
        request,
        Quote.objects.filter(tenant=request.tenant).select_related("account", "opportunity", "owner"),
        "crm/sales/quote/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("opportunity", "opportunity_id", True)],
        extra_context={"status_choices": Quote.STATUS_CHOICES,
                       "opportunities": Opportunity.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def quote_create(request):
    return crud_create(request, form_class=QuoteForm, template="crm/sales/quote/form.html",
                       success_url="crm:quote_list")


@login_required
def quote_detail(request, pk):
    obj = get_object_or_404(
        Quote.objects.select_related("account", "opportunity", "price_book", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/quote/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("product"),
        "line_form": QuoteLineForm(tenant=request.tenant),
    })


@login_required
def quote_edit(request, pk):
    return crud_edit(request, model=Quote, pk=pk, form_class=QuoteForm,
                     template="crm/sales/quote/form.html", success_url="crm:quote_list")


@login_required
@require_POST
def quote_delete(request, pk):
    return crud_delete(request, model=Quote, pk=pk, success_url="crm:quote_list")


@login_required
def quote_print(request, pk):
    """Print-styled quote (login-gated — quotes carry pricing, so no public token endpoint)."""
    obj = get_object_or_404(
        Quote.objects.select_related("account", "opportunity", "price_book", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/quote/print.html", {
        "obj": obj, "lines": obj.lines.select_related("product")})


@login_required
@require_POST
def quoteline_add(request, pk):
    quote = get_object_or_404(Quote.objects.select_related("price_book"), pk=pk, tenant=request.tenant)
    if quote.status not in Quote.OPEN_STATUSES:
        messages.info(request, "Only a draft or sent quote can be edited.")
        return redirect("crm:quote_detail", pk=quote.pk)
    form = QuoteLineForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "Could not add line — check the fields.")
        return redirect("crm:quote_detail", pk=quote.pk)
    line = form.save(commit=False)
    line.tenant = request.tenant
    line.quote = quote
    # Default price/desc/tax from the product, adjusted by the quote's price book.
    if line.product_id:
        if not line.unit_price:
            base = line.product.unit_price
            line.unit_price = quote.price_book.adjusted_price(base) if quote.price_book else base
        if not line.tax_pct:
            line.tax_pct = line.product.tax_pct
        if not line.description:
            line.description = line.product.name
    line.order = quote.lines.count()
    with transaction.atomic():
        line.save()
        quote.recalc_totals()
    messages.success(request, "Line added.")
    return redirect("crm:quote_detail", pk=quote.pk)


@login_required
@require_POST
def quoteline_remove(request, line_pk):
    line = get_object_or_404(QuoteLine.objects.select_related("quote"), pk=line_pk, tenant=request.tenant)
    quote = line.quote
    with transaction.atomic():
        line.delete()
        quote.recalc_totals()
    messages.success(request, "Line removed.")
    return redirect("crm:quote_detail", pk=quote.pk)


# Quote send/accept/decline + opportunity_advance stay @login_required (NOT @tenant_admin_required):
# pipeline progression is day-to-day rep work (cf. Salesforce/HubSpot deal ownership). The
# tenant-admin gate in this codebase is reserved for financial posting / workspace config. All
# transitions are audit-logged.
@login_required
@require_POST
def quote_send(request, pk):
    quote = get_object_or_404(Quote, pk=pk, tenant=request.tenant)
    if quote.status != "draft":
        messages.info(request, "Only a draft quote can be sent.")
        return redirect("crm:quote_detail", pk=quote.pk)
    quote.status = "sent"
    quote.sent_at = timezone.now()
    quote.save(update_fields=["status", "sent_at", "updated_at"])
    write_audit_log(request.user, quote, "update", {"action": "send"})
    messages.success(request, f"{quote.number} marked as sent.")
    return redirect("crm:quote_detail", pk=quote.pk)


@login_required
@require_POST
def quote_accept(request, pk):
    quote = get_object_or_404(Quote, pk=pk, tenant=request.tenant)
    if quote.status != "sent":
        messages.info(request, "Only a sent quote can be accepted.")
        return redirect("crm:quote_detail", pk=quote.pk)
    quote.status = "accepted"
    quote.accepted_at = timezone.now()
    quote.save(update_fields=["status", "accepted_at", "updated_at"])
    write_audit_log(request.user, quote, "update", {"action": "accept"})
    messages.success(request, f"{quote.number} accepted.")
    return redirect("crm:quote_detail", pk=quote.pk)


@login_required
@require_POST
def quote_decline(request, pk):
    quote = get_object_or_404(Quote, pk=pk, tenant=request.tenant)
    if quote.status != "sent":
        messages.info(request, "Only a sent quote can be declined.")
        return redirect("crm:quote_detail", pk=quote.pk)
    quote.status = "declined"
    quote.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, quote, "update", {"action": "decline"})
    messages.success(request, f"{quote.number} declined.")
    return redirect("crm:quote_detail", pk=quote.pk)


# ------------------------------------------------------------ Sales quotas (1.2)
@login_required
def salesquota_list(request):
    return crud_list(
        request,
        SalesQuota.objects.filter(tenant=request.tenant).select_related("owner", "territory"),
        "crm/sales/salesquota/list.html",
        search_fields=["number", "owner__username", "territory__name"],
        filters=[("period_type", "period_type", False), ("territory", "territory_id", True)],
        extra_context={"period_choices": SalesQuota.PERIOD_CHOICES,
                       "territories": Territory.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def salesquota_create(request):
    return crud_create(request, form_class=SalesQuotaForm, template="crm/sales/salesquota/form.html",
                       success_url="crm:salesquota_list")


@login_required
def salesquota_detail(request, pk):
    obj = get_object_or_404(SalesQuota.objects.select_related("owner", "territory"), pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/salesquota/detail.html", {"obj": obj})


@login_required
def salesquota_edit(request, pk):
    return crud_edit(request, model=SalesQuota, pk=pk, form_class=SalesQuotaForm,
                     template="crm/sales/salesquota/form.html", success_url="crm:salesquota_list")


@login_required
@require_POST
def salesquota_delete(request, pk):
    return crud_delete(request, model=SalesQuota, pk=pk, success_url="crm:salesquota_list")


# ------------------------------------------------------------ Forecast dashboard (1.2)
@login_required
def forecast(request):
    """Weighted-pipeline-by-forecast-category + quota-attainment dashboard (DB-side aggregates)."""
    tenant = request.tenant
    cats, quotas = [], []
    totals = {"pipeline": 0, "weighted": 0, "won": 0, "target": 0}
    if tenant is not None:
        opps = Opportunity.objects.filter(tenant=tenant)
        cat_display = dict(Opportunity.FORECAST_CATEGORY_CHOICES)
        for r in opps.values("forecast_category").annotate(
                count=Count("id"), total=Sum("amount"),
                weighted=Sum(F("amount") * F("probability"),
                             output_field=DecimalField(max_digits=18, decimal_places=2))
        ).order_by("forecast_category"):
            cats.append({"label": cat_display.get(r["forecast_category"], r["forecast_category"]),
                         "count": r["count"], "total": r["total"] or 0,
                         "weighted": (r["weighted"] or 0) / 100})
        open_agg = opps.filter(stage__in=Opportunity.OPEN_STAGES).aggregate(
            pipeline=Sum("amount"),
            weighted=Sum(F("amount") * F("probability"),
                         output_field=DecimalField(max_digits=18, decimal_places=2)))
        totals["pipeline"] = open_agg["pipeline"] or 0
        totals["weighted"] = (open_agg["weighted"] or 0) / 100
        totals["won"] = opps.filter(stage="closed_won").aggregate(t=Sum("amount"))["t"] or 0
        # Quota attainment: closed-won booked per (owner, territory) in one grouped query. A
        # territory-scoped quota matches its (owner, territory) bucket; a null-territory quota
        # matches the owner's total across all territories.
        won = opps.filter(stage="closed_won").values_list("owner", "territory").annotate(t=Sum("amount"))
        won_by_owner_terr = {(o, terr): (t or 0) for o, terr, t in won}
        won_by_owner = {}
        for (o, terr), t in won_by_owner_terr.items():
            won_by_owner[o] = won_by_owner.get(o, 0) + t
        for q in SalesQuota.objects.filter(tenant=tenant).select_related("owner", "territory"):
            if q.territory_id:
                attained = won_by_owner_terr.get((q.owner_id, q.territory_id), 0)
            else:
                attained = won_by_owner.get(q.owner_id, 0)
            target = q.target_amount or 0
            totals["target"] += target
            quotas.append({"q": q, "attained": attained,
                           "pct": max(0, round(float(attained) / float(target) * 100)) if target else 0})
    return render(request, "crm/sales/forecast.html", {
        "cats": cats, "quotas": quotas, "totals": totals,
        "chart_labels": [c["label"] for c in cats],
        "chart_data": [float(c["total"]) for c in cats],
    })


# ============================================================================
# ===== 1.3 Marketing Automation (recreated) =================================
# Campaign Management (+ target-list segmentation), Email Marketing (templates +
# blasts/drip/A-B + tracking), and Landing Pages & Forms (public web-to-lead).
# ============================================================================

def _client_ip(request):
    """Best-effort client IP for a public submission. Uses REMOTE_ADDR only —
    X-Forwarded-For is client-spoofable, so we never trust it for storage.
    # WARNING: behind a reverse proxy REMOTE_ADDR is the proxy IP. For accurate visitor IPs in
    # production, resolve via django-ipware with a configured trusted-proxy count."""
    return request.META.get("REMOTE_ADDR") or None


# ------------------------------------------------------------ Campaigns (1.3)
@login_required
def campaign_list(request):
    return crud_list(
        request, Campaign.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/marketing/campaign/list.html",
        search_fields=["name", "number"],
        filters=[("status", "status", False), ("type", "type", False),
                 ("objective", "objective", False)],
        extra_context={"status_choices": Campaign.STATUS_CHOICES,
                       "type_choices": Campaign.TYPE_CHOICES,
                       "objective_choices": Campaign.OBJECTIVE_CHOICES},
    )


@login_required
def campaign_create(request):
    return crud_create(request, form_class=CampaignForm, template="crm/marketing/campaign/form.html",
                       success_url="crm:campaign_list")


@login_required
def campaign_detail(request, pk):
    obj = get_object_or_404(
        Campaign.objects.select_related("owner", "parent_campaign"), pk=pk, tenant=request.tenant)
    members_qs = CampaignMember.objects.filter(tenant=request.tenant, campaign=obj)
    # Single aggregate for the funnel stats — no per-row loop, no N+1.
    agg = members_qs.aggregate(
        total=Count("id"),
        responded=Count("id", filter=Q(status__in=CampaignMember.RESPONDED_STATUSES)),
    )
    total, responded = agg["total"] or 0, agg["responded"] or 0
    return render(request, "crm/marketing/campaign/detail.html", {
        "obj": obj,
        "members": members_qs.select_related("party", "lead")[:50],
        "member_total": total,
        "responded_count": responded,
        "response_rate": (responded / total * 100) if total else None,
        "email_campaigns": EmailCampaign.objects.filter(
            tenant=request.tenant, campaign=obj).select_related("template")[:20],
        "landing_pages": LandingPage.objects.filter(
            tenant=request.tenant, campaign=obj)[:20],
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, campaign=obj).select_related("account")[:20],
        "member_status_choices": CampaignMember.STATUS_CHOICES,
    })


@login_required
def campaign_edit(request, pk):
    return crud_edit(request, model=Campaign, pk=pk, form_class=CampaignForm,
                     template="crm/marketing/campaign/form.html", success_url="crm:campaign_list")


@login_required
@require_POST
def campaign_delete(request, pk):
    return crud_delete(request, model=Campaign, pk=pk, success_url="crm:campaign_list")


# ------------------------------------------------------------ Campaign members (1.3)
@login_required
def campaignmember_list(request):
    return crud_list(
        request,
        CampaignMember.objects.filter(tenant=request.tenant).select_related("campaign", "party", "lead"),
        "crm/marketing/campaignmember/list.html",
        search_fields=["member_name", "member_email", "campaign__name"],
        filters=[("status", "status", False), ("campaign", "campaign_id", True)],
        extra_context={"status_choices": CampaignMember.STATUS_CHOICES,
                       "campaigns": Campaign.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def campaignmember_create(request):
    return crud_create(request, form_class=CampaignMemberForm,
                       template="crm/marketing/campaignmember/form.html",
                       success_url="crm:campaignmember_list")


@login_required
def campaignmember_detail(request, pk):
    obj = get_object_or_404(
        CampaignMember.objects.select_related("campaign", "party", "lead"), pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/campaignmember/detail.html", {"obj": obj})


@login_required
def campaignmember_edit(request, pk):
    return crud_edit(request, model=CampaignMember, pk=pk, form_class=CampaignMemberForm,
                     template="crm/marketing/campaignmember/form.html",
                     success_url="crm:campaignmember_list")


@login_required
@require_POST
def campaignmember_delete(request, pk):
    return crud_delete(request, model=CampaignMember, pk=pk, success_url="crm:campaignmember_list")


@login_required
@require_POST
def campaignmember_add(request, pk):
    """Inline add on the campaign detail page — quick manual list entry."""
    campaign = get_object_or_404(Campaign, pk=pk, tenant=request.tenant)
    name = request.POST.get("member_name", "").strip()[:255]
    if not name:
        messages.error(request, "A member name is required.")
        return redirect("crm:campaign_detail", pk=campaign.pk)
    status = request.POST.get("status", "targeted")
    if status not in dict(CampaignMember.STATUS_CHOICES):
        status = "targeted"
    email = request.POST.get("member_email", "").strip()[:254]
    if email:
        try:  # the inline shortcut bypasses the EmailField form — validate here too.
            validate_email(email)
        except ValidationError:
            email = ""
    CampaignMember.objects.create(
        tenant=request.tenant, campaign=campaign, member_name=name,
        member_email=email, status=status)
    messages.success(request, "Member added to the campaign.")
    return redirect("crm:campaign_detail", pk=campaign.pk)


@login_required
@require_POST
def campaignmember_remove(request, member_pk):
    member = get_object_or_404(CampaignMember, pk=member_pk, tenant=request.tenant)
    campaign_id = member.campaign_id
    member.delete()
    messages.success(request, "Member removed.")
    return redirect("crm:campaign_detail", pk=campaign_id)


# ------------------------------------------------------------ Email templates (1.3)
@login_required
def emailtemplate_list(request):
    return crud_list(
        request,
        # defer the large HTML body — it's never shown on the list.
        EmailTemplate.objects.filter(tenant=request.tenant).select_related("owner").defer("body"),
        "crm/marketing/emailtemplate/list.html",
        search_fields=["number", "name", "subject"],
        filters=[("category", "category", False), ("is_active", "is_active", False)],
        extra_context={"category_choices": EmailTemplate.CATEGORY_CHOICES},
    )


@login_required
def emailtemplate_create(request):
    return crud_create(request, form_class=EmailTemplateForm,
                       template="crm/marketing/emailtemplate/form.html",
                       success_url="crm:emailtemplate_list")


@login_required
def emailtemplate_detail(request, pk):
    obj = get_object_or_404(EmailTemplate.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/emailtemplate/detail.html", {"obj": obj})


@login_required
def emailtemplate_edit(request, pk):
    return crud_edit(request, model=EmailTemplate, pk=pk, form_class=EmailTemplateForm,
                     template="crm/marketing/emailtemplate/form.html",
                     success_url="crm:emailtemplate_list")


@login_required
@require_POST
def emailtemplate_delete(request, pk):
    return crud_delete(request, model=EmailTemplate, pk=pk, success_url="crm:emailtemplate_list")


# ------------------------------------------------------------ Email campaigns / blasts (1.3)
@login_required
def emailcampaign_list(request):
    return crud_list(
        request,
        EmailCampaign.objects.filter(tenant=request.tenant).select_related("campaign", "template", "owner"),
        "crm/marketing/emailcampaign/list.html",
        search_fields=["number", "name", "campaign__name"],
        filters=[("status", "status", False), ("send_type", "send_type", False),
                 ("campaign", "campaign_id", True)],
        extra_context={"status_choices": EmailCampaign.STATUS_CHOICES,
                       "send_type_choices": EmailCampaign.SEND_TYPE_CHOICES,
                       "campaigns": Campaign.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def emailcampaign_create(request):
    return crud_create(request, form_class=EmailCampaignForm,
                       template="crm/marketing/emailcampaign/form.html",
                       success_url="crm:emailcampaign_list")


@login_required
def emailcampaign_detail(request, pk):
    obj = get_object_or_404(
        EmailCampaign.objects.select_related("campaign", "template", "variant_template", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/emailcampaign/detail.html", {"obj": obj})


@login_required
def emailcampaign_edit(request, pk):
    return crud_edit(request, model=EmailCampaign, pk=pk, form_class=EmailCampaignForm,
                     template="crm/marketing/emailcampaign/form.html",
                     success_url="crm:emailcampaign_list")


@login_required
@require_POST
def emailcampaign_delete(request, pk):
    return crud_delete(request, model=EmailCampaign, pk=pk, success_url="crm:emailcampaign_list")


@tenant_admin_required  # firing a blast is privileged + irreversible — mirrors expense_approve/crm_po_receive
@require_POST
def emailcampaign_send(request, pk):
    """Simulate a send: snapshot recipient count from the campaign's members, stamp the
    send, and advance any 'targeted' members to 'sent'. (No real ESP — metrics are modelled,
    not delivered.) recipients_count/sent_count/sent_at are system-set here, never via the form."""
    blast = get_object_or_404(EmailCampaign.objects.select_related("campaign"), pk=pk, tenant=request.tenant)
    recipients = CampaignMember.objects.filter(tenant=request.tenant, campaign=blast.campaign).count()
    with transaction.atomic():
        # Conditional UPDATE claims the row atomically: a second concurrent POST sees the status
        # already advanced and updates 0 rows, so the metrics can never be double-counted.
        claimed = EmailCampaign.objects.filter(pk=blast.pk, tenant=request.tenant).exclude(
            status__in=("sending", "sent", "cancelled")).update(
            recipients_count=recipients, sent_count=recipients, status="sent",
            sent_at=timezone.now())
        if not claimed:
            messages.info(request, "This email campaign has already been sent or cancelled.")
            return redirect("crm:emailcampaign_detail", pk=blast.pk)
        CampaignMember.objects.filter(
            tenant=request.tenant, campaign=blast.campaign, status="targeted").update(status="sent")
    write_audit_log(request.user, blast, "update", {"action": "send", "recipients": recipients})
    messages.success(request, f"{blast.number} sent to {recipients} recipient(s).")
    return redirect("crm:emailcampaign_detail", pk=blast.pk)


# ------------------------------------------------------------ Landing pages (1.3)
@login_required
def landingpage_list(request):
    return crud_list(
        request,
        # defer the large HTML body — it's never shown on the list.
        LandingPage.objects.filter(tenant=request.tenant).select_related(
            "campaign", "routing_owner").defer("body"),
        "crm/marketing/landingpage/list.html",
        search_fields=["number", "name", "headline", "slug"],
        filters=[("status", "status", False), ("campaign", "campaign_id", True)],
        extra_context={"status_choices": LandingPage.STATUS_CHOICES,
                       "campaigns": Campaign.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def landingpage_create(request):
    return crud_create(request, form_class=LandingPageForm,
                       template="crm/marketing/landingpage/form.html",
                       success_url="crm:landingpage_list")


@login_required
def landingpage_detail(request, pk):
    obj = get_object_or_404(
        LandingPage.objects.select_related("campaign", "routing_owner", "owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/landingpage/detail.html", {
        "obj": obj,
        "submissions": FormSubmission.objects.filter(
            tenant=request.tenant, landing_page=obj).select_related(
            "converted_lead").defer("message")[:20],  # message not shown in the panel
    })


@login_required
def landingpage_edit(request, pk):
    return crud_edit(request, model=LandingPage, pk=pk, form_class=LandingPageForm,
                     template="crm/marketing/landingpage/form.html",
                     success_url="crm:landingpage_list")


@login_required
@require_POST
def landingpage_delete(request, pk):
    return crud_delete(request, model=LandingPage, pk=pk, success_url="crm:landingpage_list")


@tenant_admin_required  # publishing exposes a live public web-to-lead URL — admin-gated
@require_POST
def landingpage_publish(request, pk):
    """Toggle a landing page between draft and published. Publishing makes it live on a public
    URL accepting leads, so this transition is admin-only (the content form excludes `status`)."""
    page = get_object_or_404(LandingPage, pk=pk, tenant=request.tenant)
    new_status = "draft" if page.status == "published" else "published"
    LandingPage.objects.filter(pk=page.pk, tenant=request.tenant).update(status=new_status)
    write_audit_log(request.user, page, "update",
                    {"action": "publish" if new_status == "published" else "unpublish"})
    messages.success(request, f"{page.number} is now {new_status}.")
    return redirect("crm:landingpage_detail", pk=page.pk)


def landing_public(request, token):
    """Public landing page + web-to-lead form (1.3). No login; the unguessable public_token is
    the bearer credential and only a *published* page resolves (draft/archived → 404). CSRF is
    enforced by the template's {% csrf_token %}; the tenant-authored body is rendered ESCAPED.
    # WARNING: unauthenticated endpoint — add per-IP rate-limiting (django-ratelimit) or a WAF
    # throttle in production to stop scripted FormSubmission floods."""
    page = get_object_or_404(
        LandingPage.objects.select_related("campaign"), public_token=token, status="published")
    form = PublicLeadForm()
    if request.method == "POST":
        form = PublicLeadForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                FormSubmission.objects.create(
                    tenant=page.tenant, landing_page=page,
                    name=cd["name"], email=cd["email"],
                    phone=cd["phone"] if page.capture_phone else "",
                    company=cd["company"] if page.capture_company else "",
                    message=cd["message"] if page.capture_message else "",
                    status="new", routed_to=page.routing_owner, ip_address=_client_ip(request),
                )
                LandingPage.objects.filter(pk=page.pk).update(submission_count=F("submission_count") + 1)
            # Post/Redirect/Get — a browser refresh after submit won't re-post the form.
            return redirect(f"{reverse('crm:landing_public', args=[token])}?submitted=1")
    return render(request, "crm/marketing/landing_public.html", {
        "page": page, "form": form, "submitted": request.GET.get("submitted") == "1"})


# ------------------------------------------------------------ Form submissions (1.3, read-mostly)
@login_required
def formsubmission_list(request):
    return crud_list(
        request,
        FormSubmission.objects.filter(tenant=request.tenant).select_related(
            "landing_page", "routed_to", "converted_lead"),
        "crm/marketing/formsubmission/list.html",
        search_fields=["name", "email", "company", "landing_page__name"],
        filters=[("status", "status", False), ("landing_page", "landing_page_id", True)],
        extra_context={"status_choices": FormSubmission.STATUS_CHOICES,
                       "landing_pages": LandingPage.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def formsubmission_detail(request, pk):
    obj = get_object_or_404(
        FormSubmission.objects.select_related("landing_page", "routed_to", "converted_lead"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/formsubmission/detail.html", {"obj": obj})


@login_required
@require_POST
def formsubmission_delete(request, pk):
    return crud_delete(request, model=FormSubmission, pk=pk, success_url="crm:formsubmission_list")


@login_required
@require_POST
def formsubmission_convert(request, pk):
    """Turn a captured submission into a CRM Lead, routed to the landing page's owner.
    Idempotent — a submission already linked to a lead is left untouched."""
    sub = get_object_or_404(
        FormSubmission.objects.select_related("landing_page", "routed_to"), pk=pk, tenant=request.tenant)
    if sub.converted_lead_id:
        messages.info(request, "This submission was already converted to a lead.")
        return redirect("crm:formsubmission_detail", pk=sub.pk)
    lp = sub.landing_page
    owner = sub.routed_to or (lp.routing_owner if lp else None)
    with transaction.atomic():
        lead = Lead.objects.create(
            tenant=request.tenant, name=sub.name, company=sub.company, email=sub.email,
            phone=sub.phone, source=(lp.lead_source if lp else "web"), status="new",
            owner=owner, description=sub.message,
        )
        sub.converted_lead = lead
        sub.status = "converted"
        sub.routed_to = owner
        sub.save(update_fields=["converted_lead", "status", "routed_to"])
    write_audit_log(request.user, lead, "create", {"from": "form_submission", "submission": sub.pk})
    write_audit_log(request.user, sub, "update", {"action": "convert", "lead": lead.pk})
    messages.success(request, f"Converted to lead {lead.number}.")
    return redirect("crm:lead_detail", pk=lead.pk)


# ============================================================ Cases / Tickets (1.4)
@login_required
def case_list(request):
    return crud_list(
        request,
        Case.objects.filter(tenant=request.tenant).select_related("account", "owner").defer(
            "description", "satisfaction_comment"),  # large TextFields not shown on the list
        "crm/service/case/list.html",
        search_fields=["subject", "number"],
        filters=[("status", "status", False), ("priority", "priority", False), ("type", "type", False)],
        extra_context={"status_choices": Case.STATUS_CHOICES,
                       "priority_choices": Case.PRIORITY_CHOICES,
                       "type_choices": Case.TYPE_CHOICES},
    )


@login_required
def case_create(request):
    return crud_create(request, form_class=CaseForm, template="crm/service/case/form.html",
                       success_url="crm:case_list")


@login_required
def case_detail(request, pk):
    obj = get_object_or_404(
        Case.objects.select_related("account", "contact", "owner", "sla_policy"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/service/case/detail.html", {
        "obj": obj,
        "comments": CaseComment.objects.filter(
            tenant=request.tenant, case=obj).select_related("author"),
        "comment_form": CaseCommentForm(tenant=request.tenant),
    })


@login_required
def case_edit(request, pk):
    return crud_edit(request, model=Case, pk=pk, form_class=CaseForm,
                     template="crm/service/case/form.html", success_url="crm:case_list")


@login_required
@require_POST
def case_delete(request, pk):
    return crud_delete(request, model=Case, pk=pk, success_url="crm:case_list")


@login_required
@require_POST
def case_comment_add(request, pk):
    """Add a reply/note to a case's conversation thread. The first PUBLIC agent reply stamps
    the SLA first-response clock (``first_responded_at``)."""
    case = get_object_or_404(Case, pk=pk, tenant=request.tenant)
    form = CaseCommentForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "A comment body is required.")
        return redirect("crm:case_detail", pk=case.pk)
    comment = form.save(commit=False)
    comment.tenant = request.tenant
    comment.case = case
    comment.author = request.user
    comment.author_name = request.user.get_full_name() or request.user.username
    with transaction.atomic():
        comment.save()
        if comment.is_public:
            # Atomic claim — only the first public reply stamps the SLA first-response clock
            # (no read-check-write race between two agents replying concurrently).
            Case.objects.filter(pk=case.pk, first_responded_at__isnull=True).update(
                first_responded_at=timezone.now(), updated_at=timezone.now())
    messages.success(request, "Comment added.")
    return redirect("crm:case_detail", pk=case.pk)


# ====================================================== Knowledge Base / Solutions (1.4)
@login_required
def knowledgearticle_list(request):
    return crud_list(
        request,
        KnowledgeArticle.objects.filter(tenant=request.tenant).select_related("kb_category").defer("body"),
        "crm/service/knowledgearticle/list.html",
        search_fields=["title", "category", "number"],
        filters=[("status", "status", False), ("visibility", "visibility", False),
                 ("kb_category", "kb_category_id", True)],
        extra_context={"status_choices": KnowledgeArticle.STATUS_CHOICES,
                       "visibility_choices": KnowledgeArticle.VISIBILITY_CHOICES,
                       "categories": KbCategory.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def knowledgearticle_create(request):
    return crud_create(request, form_class=KnowledgeArticleForm,
                       template="crm/service/knowledgearticle/form.html",
                       success_url="crm:knowledgearticle_list")


@login_required
def knowledgearticle_detail(request, pk):
    # Count a view via an atomic F() update (tenant-scoped); bypasses save() so it neither
    # touches updated_at nor re-numbers.
    KnowledgeArticle.objects.filter(pk=pk, tenant=request.tenant).update(views_count=F("views_count") + 1)
    obj = get_object_or_404(KnowledgeArticle.objects.select_related("owner", "kb_category"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/service/knowledgearticle/detail.html", {"obj": obj})


@login_required
def knowledgearticle_edit(request, pk):
    return crud_edit(request, model=KnowledgeArticle, pk=pk, form_class=KnowledgeArticleForm,
                     template="crm/service/knowledgearticle/form.html",
                     success_url="crm:knowledgearticle_list")


@login_required
@require_POST
def knowledgearticle_delete(request, pk):
    return crud_delete(request, model=KnowledgeArticle, pk=pk,
                       success_url="crm:knowledgearticle_list")


# ------------------------------------------------------------ SLA policies (1.4)
@login_required
def slapolicy_list(request):
    return crud_list(
        request, SlaPolicy.objects.filter(tenant=request.tenant).defer("description"),
        "crm/service/slapolicy/list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@tenant_admin_required  # SLA policy is tenant-wide config (is_default drives every case's SLA)
def slapolicy_create(request):
    return crud_create(request, form_class=SlaPolicyForm, template="crm/service/slapolicy/form.html",
                       success_url="crm:slapolicy_list")


@login_required
def slapolicy_detail(request, pk):
    obj = get_object_or_404(SlaPolicy, pk=pk, tenant=request.tenant)
    return render(request, "crm/service/slapolicy/detail.html", {"obj": obj})


@tenant_admin_required
def slapolicy_edit(request, pk):
    return crud_edit(request, model=SlaPolicy, pk=pk, form_class=SlaPolicyForm,
                     template="crm/service/slapolicy/form.html", success_url="crm:slapolicy_list")


@tenant_admin_required
@require_POST
def slapolicy_delete(request, pk):
    return crud_delete(request, model=SlaPolicy, pk=pk, success_url="crm:slapolicy_list")


# ------------------------------------------------------------ KB categories (1.4)
@login_required
def kbcategory_list(request):
    return crud_list(
        request,
        KbCategory.objects.filter(tenant=request.tenant).select_related("parent").defer("description", "slug"),
        "crm/service/kbcategory/list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def kbcategory_create(request):
    return crud_create(request, form_class=KbCategoryForm, template="crm/service/kbcategory/form.html",
                       success_url="crm:kbcategory_list")


@login_required
def kbcategory_detail(request, pk):
    obj = get_object_or_404(KbCategory.objects.select_related("parent"), pk=pk, tenant=request.tenant)
    return render(request, "crm/service/kbcategory/detail.html", {
        "obj": obj,
        "children": KbCategory.objects.filter(
            tenant=request.tenant, parent=obj).only("pk", "number", "name", "order"),
        "articles": KnowledgeArticle.objects.filter(
            tenant=request.tenant, kb_category=obj).only("pk", "number", "title", "status")[:50],
    })


@login_required
def kbcategory_edit(request, pk):
    return crud_edit(request, model=KbCategory, pk=pk, form_class=KbCategoryForm,
                     template="crm/service/kbcategory/form.html", success_url="crm:kbcategory_list")


@login_required
@require_POST
def kbcategory_delete(request, pk):
    return crud_delete(request, model=KbCategory, pk=pk, success_url="crm:kbcategory_list")


# ------------------------------------------------------------ Customer portal access (1.4, admin)
@login_required
def customerportalaccess_list(request):
    return crud_list(
        request,
        CustomerPortalAccess.objects.filter(tenant=request.tenant).select_related("customer_party", "portal_user"),
        "crm/service/customerportalaccess/list.html",
        search_fields=["number", "customer_party__name", "portal_user__username"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@tenant_admin_required  # granting a customer a portal login that reads their cases is an IAM action
def customerportalaccess_create(request):
    return crud_create(request, form_class=CustomerPortalAccessForm,
                       template="crm/service/customerportalaccess/form.html",
                       success_url="crm:customerportalaccess_list")


@login_required
def customerportalaccess_detail(request, pk):
    obj = get_object_or_404(
        CustomerPortalAccess.objects.select_related("customer_party", "portal_user"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/service/customerportalaccess/detail.html", {"obj": obj})


@tenant_admin_required
def customerportalaccess_edit(request, pk):
    return crud_edit(request, model=CustomerPortalAccess, pk=pk, form_class=CustomerPortalAccessForm,
                     template="crm/service/customerportalaccess/form.html",
                     success_url="crm:customerportalaccess_list")


@tenant_admin_required
@require_POST
def customerportalaccess_delete(request, pk):
    return crud_delete(request, model=CustomerPortalAccess, pk=pk,
                       success_url="crm:customerportalaccess_list")


# ------------------------------------------------------------ Public help-desk pages (1.4, no login)
def case_public(request, token):
    """Public case-status tracking page — no login; the unguessable token is the bearer credential.
    Shows status/SLA + PUBLIC comments only (internal notes never leak) and lets the customer post a
    reply or a CSAT rating. CSRF-protected via the template tag; tenant taken from the case itself.
    # WARNING: unauthenticated POST — add per-IP rate-limiting (django-ratelimit) or a WAF throttle
    # in production to stop public comment floods."""
    case = get_object_or_404(
        Case.objects.select_related("sla_policy", "owner", "contact"), public_token=token)
    sat_form = PublicSatisfactionForm()
    comment_form = PublicCommentForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "comment":
            comment_form = PublicCommentForm(request.POST)
            if comment_form.is_valid():
                CaseComment.objects.create(
                    tenant=case.tenant, case=case, author=None,
                    author_name=(case.contact.name if case.contact else "Customer"),
                    body=comment_form.cleaned_data["body"], is_public=True)
                return redirect("crm:case_public", token=token)
        elif action == "satisfaction" and case.satisfaction_rating is None:  # CSAT submitted once
            sat_form = PublicSatisfactionForm(request.POST)
            if sat_form.is_valid():
                # Atomic guard — a concurrent second submit updates 0 rows (can't overwrite the
                # rating); mirrors the first_responded_at claim, no TOCTOU race.
                Case.objects.filter(pk=case.pk, satisfaction_rating__isnull=True).update(
                    satisfaction_rating=int(sat_form.cleaned_data["rating"]),
                    satisfaction_comment=sat_form.cleaned_data["comment"],
                    satisfaction_at=timezone.now(), updated_at=timezone.now())
                return redirect("crm:case_public", token=token)
    return render(request, "crm/service/case_public.html", {
        "case": case,
        "comments": CaseComment.objects.filter(
            tenant=case.tenant, case=case, is_public=True).select_related("author"),
        "sat_form": sat_form, "comment_form": comment_form,
    })


def kb_public(request, token):
    """Public KB article page — no login; only a published + external article resolves (drafts and
    internal articles → 404). Counts a view via an atomic F() bump."""
    article = get_object_or_404(
        KnowledgeArticle.objects.select_related("kb_category"),
        public_token=token, status="published", visibility="external")
    KnowledgeArticle.objects.filter(pk=article.pk).update(views_count=F("views_count") + 1)
    return render(request, "crm/service/kb_public.html", {"article": article})


@require_POST
def kb_helpful(request, token):
    """Public helpful/not-helpful vote on a KB article (CSRF-protected, F() increment).
    # WARNING: unauthenticated — add per-IP rate-limiting in production to prevent vote stuffing."""
    article = get_object_or_404(
        KnowledgeArticle, public_token=token, status="published", visibility="external")
    vote = request.POST.get("vote")
    if vote == "yes":
        KnowledgeArticle.objects.filter(pk=article.pk).update(helpful_count=F("helpful_count") + 1)
    elif vote == "no":
        KnowledgeArticle.objects.filter(pk=article.pk).update(not_helpful_count=F("not_helpful_count") + 1)
    return redirect("crm:kb_public", token=token)


# ------------------------------------------------------------ Customer self-service portal (1.4, login)
def _customer_portal_access(request):
    """Return the active CustomerPortalAccess for the logged-in portal user, or None."""
    if not request.user.is_authenticated:
        return None
    return (CustomerPortalAccess.objects
            .filter(portal_user=request.user, tenant=request.tenant, is_active=True)
            .select_related("customer_party").first())


@login_required
def portal_case_list(request):
    access = _customer_portal_access(request)
    if access is None:
        messages.error(request, "You don't have customer portal access.")
        return redirect("dashboard:home")
    party = access.customer_party
    if party is None:  # WARNING: without this, Q(account=None)|Q(contact=None) would match
        # every unlinked case in the tenant — leaking cases to a misconfigured portal account.
        messages.error(request, "Your portal account has no linked customer — contact support.")
        return redirect("dashboard:home")
    cases = (Case.objects.filter(tenant=request.tenant)
             .filter(Q(account=party) | Q(contact=party))
             .select_related("owner").order_by("-created_at"))
    page_obj = paginate(request, cases)
    return render(request, "crm/service/portal_case_list.html", {
        "access": access, "object_list": page_obj.object_list, "page_obj": page_obj})


@login_required
def portal_case_detail(request, pk):
    access = _customer_portal_access(request)
    if access is None:
        messages.error(request, "You don't have customer portal access.")
        return redirect("dashboard:home")
    party = access.customer_party
    if party is None:  # no linked customer → no scope; refuse rather than match null-party cases
        messages.error(request, "Your portal account has no linked customer — contact support.")
        return redirect("dashboard:home")
    # Scoped to the portal user's own party — they can never open another customer's case.
    case = get_object_or_404(
        Case.objects.filter(tenant=request.tenant).filter(Q(account=party) | Q(contact=party)), pk=pk)
    comment_form = PublicCommentForm()
    if request.method == "POST":
        if not access.can_submit_cases:  # explicit reject (don't silently no-op a crafted POST)
            messages.error(request, "You don't have permission to reply.")
            return redirect("crm:portal_case_detail", pk=case.pk)
        comment_form = PublicCommentForm(request.POST)
        if comment_form.is_valid():
            CaseComment.objects.create(
                tenant=request.tenant, case=case, author=request.user,
                author_name=request.user.get_full_name() or request.user.username,
                body=comment_form.cleaned_data["body"], is_public=True)
            messages.success(request, "Your reply was sent.")
            return redirect("crm:portal_case_detail", pk=case.pk)
    return render(request, "crm/service/portal_case_detail.html", {
        "access": access, "case": case,
        "comments": CaseComment.objects.filter(
            tenant=request.tenant, case=case, is_public=True).select_related("author"),
        "comment_form": comment_form,
    })


@login_required
def portal_case_create(request):
    access = _customer_portal_access(request)
    if access is None or not access.can_submit_cases:
        messages.error(request, "You can't submit support tickets.")
        return redirect("crm:portal_case_list" if access else "dashboard:home")
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()[:255]
        if not subject:
            messages.error(request, "A subject is required.")
        else:
            priority = request.POST.get("priority", "medium")
            if priority not in dict(Case.PRIORITY_CHOICES):
                priority = "medium"
            # Force the party + origin server-side — a portal user can't file for another customer.
            default_sla = SlaPolicy.objects.filter(
                tenant=request.tenant, is_default=True, is_active=True).first()
            case = Case.objects.create(
                tenant=request.tenant, subject=subject,
                description=request.POST.get("description", "").strip()[:5000],
                priority=priority, status="new", origin="portal",
                account=access.customer_party, sla_policy=default_sla)
            messages.success(request, f"Ticket {case.number} submitted.")
            return redirect("crm:portal_case_detail", pk=case.pk)
    return render(request, "crm/service/portal_case_form.html", {
        "access": access, "priority_choices": Case.PRIORITY_CHOICES})


# =============================================================== Tasks (1.5)
@login_required
def task_list(request):
    return crud_list(
        request, CrmTask.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/activities/task/list.html",
        search_fields=["subject", "number"],
        filters=[("status", "status", False), ("priority", "priority", False), ("type", "type", False)],
        extra_context={"status_choices": CrmTask.STATUS_CHOICES,
                       "priority_choices": CrmTask.PRIORITY_CHOICES,
                       "type_choices": CrmTask.TYPE_CHOICES},
    )


@login_required
def task_create(request):
    return crud_create(request, form_class=CrmTaskForm, template="crm/activities/task/form.html",
                       success_url="crm:task_list")


@login_required
def task_detail(request, pk):
    obj = get_object_or_404(
        CrmTask.objects.select_related(
            "owner", "party", "related_opportunity", "related_case", "recurrence_parent"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/activities/task/detail.html", {"obj": obj})


@login_required
def task_edit(request, pk):
    return crud_edit(request, model=CrmTask, pk=pk, form_class=CrmTaskForm,
                     template="crm/activities/task/form.html", success_url="crm:task_list")


@login_required
@require_POST
def task_delete(request, pk):
    return crud_delete(request, model=CrmTask, pk=pk, success_url="crm:task_list")


# ===================== Calendar Events (1.5 Calendar Integration) ===========================
@login_required
def calendarevent_list(request):
    return crud_list(
        request,
        CalendarEvent.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/activities/calendarevent/list.html",
        search_fields=["title", "number", "location"],
        filters=[("status", "status", False), ("event_type", "event_type", False)],
        extra_context={"status_choices": CalendarEvent.STATUS_CHOICES,
                       "type_choices": CalendarEvent.TYPE_CHOICES},
    )


@login_required
def calendarevent_create(request):
    return crud_create(request, form_class=CalendarEventForm,
                       template="crm/activities/calendarevent/form.html",
                       success_url="crm:calendarevent_list")


@login_required
def calendarevent_detail(request, pk):
    event = get_object_or_404(
        CalendarEvent.objects.select_related("owner", "party", "related_opportunity", "related_case"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/activities/calendarevent/detail.html", {
        "obj": event,
        "attendees": event.attendees.select_related("party").all(),
        "attendee_form": EventAttendeeForm(tenant=request.tenant),  # L7: always pass the add form
    })


@login_required
def calendarevent_edit(request, pk):
    return crud_edit(request, model=CalendarEvent, pk=pk, form_class=CalendarEventForm,
                     template="crm/activities/calendarevent/form.html",
                     success_url="crm:calendarevent_list")


@login_required
@require_POST
def calendarevent_delete(request, pk):
    return crud_delete(request, model=CalendarEvent, pk=pk, success_url="crm:calendarevent_list")


# ----- EventAttendee inline actions (managed on the event detail page) ----------------------
@login_required
@require_POST
def event_attendee_add(request, event_pk):
    event = get_object_or_404(CalendarEvent, pk=event_pk, tenant=request.tenant)
    form = EventAttendeeForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        email = cd.get("email") or None
        if email:
            # Upsert by (event, email) — avoids the unique_together IntegrityError on re-add.
            EventAttendee.objects.update_or_create(
                event=event, email=email,
                defaults={"tenant": event.tenant, "party": cd.get("party"), "name": cd["name"],
                          "rsvp_status": cd["rsvp_status"], "is_organizer": cd["is_organizer"]})
        else:
            attendee = form.save(commit=False)
            attendee.tenant = event.tenant
            attendee.event = event
            attendee.save()
        messages.success(request, "Attendee added.")
    else:
        messages.error(request, "Could not add attendee — check the name/email and try again.")
    return redirect("crm:calendarevent_detail", pk=event_pk)


@login_required
@require_POST
def event_attendee_delete(request, pk):
    attendee = get_object_or_404(EventAttendee, pk=pk, tenant=request.tenant)
    event_pk = attendee.event_id
    attendee.delete()
    messages.success(request, "Attendee removed.")
    return redirect("crm:calendarevent_detail", pk=event_pk)


# ----- Public meeting-invite pages (no login — the token is the bearer credential) ----------
def event_invite(request, token):
    """Public meeting invite + RSVP (1.5). No login; the unguessable ``public_token`` gates one
    event. The RSVP upserts an ``EventAttendee`` by email. CSRF enforced by the template tag;
    tenant taken from the event itself.
    # WARNING: unauthenticated POST — add per-IP rate-limiting (django-ratelimit) or a WAF throttle
    # in production to stop public RSVP floods."""
    event = get_object_or_404(
        CalendarEvent.objects.select_related("owner", "party"), public_token=token)
    form = PublicRsvpForm()
    if request.method == "POST":
        form = PublicRsvpForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # First response wins: the invite token is shared with every invitee, so an anonymous
            # visitor who knows another invitee's email must not overwrite a response already on file.
            existing = EventAttendee.objects.filter(event=event, email=cd["email"]).first()
            if existing and existing.rsvp_status != "no_response":
                messages.info(request, "A response for that email is already recorded.")
            else:
                EventAttendee.objects.update_or_create(
                    event=event, email=cd["email"],
                    defaults={"tenant": event.tenant, "name": cd["name"],
                              "rsvp_status": cd["rsvp_status"], "responded_at": timezone.now()})
                messages.success(request, "Thanks — your response has been recorded.")
            return redirect("crm:event_invite", token=token)
    return render(request, "crm/activities/event_invite.html", {
        "event": event, "attendees": event.attendees.all(), "form": form,
    })


def event_ics(request, token):
    """Public iCalendar (.ics) export for one event (1.5) — the realistic, offline-true version of
    "add to Google/Outlook/iCal". No login; the ``public_token`` is the bearer credential. Times
    are emitted in UTC (``...Z``) so any calendar app imports them unambiguously."""
    event = get_object_or_404(CalendarEvent, public_token=token)

    def _ics_dt(dt):
        return dt.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ") if dt else ""

    def _esc(text):  # RFC 5545 TEXT escaping (strip bare CR first — no meaning in a TEXT value)
        return (str(text or "").replace("\r", "").replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))

    def _fold(line):  # RFC 5545 §3.1: fold content lines >75 octets (continuation = leading space)
        if len(line) <= 74:
            return line
        out = [line[:74]]
        for i in range(74, len(line), 73):
            out.append(line[i:i + 73])
        return "\r\n ".join(out)

    end = event.end or event.start
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NavERP//CRM 1.5//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{event.number}-{event.public_token}@naverp",
        f"DTSTAMP:{_ics_dt(timezone.now())}",
        f"DTSTART:{_ics_dt(event.start)}",
        f"DTEND:{_ics_dt(end)}",
        f"SUMMARY:{_esc(event.title)}",
        f"LOCATION:{_esc(event.location)}",
        f"DESCRIPTION:{_esc(event.description)}",
        f"STATUS:{'CANCELLED' if event.status == 'cancelled' else 'CONFIRMED'}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    resp = HttpResponse("\r\n".join(_fold(ln) for ln in lines) + "\r\n",
                        content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{event.number}.ics"'
    return resp


# ===================== Communication Logs (1.5 Email & Call Integration) =====================
@login_required
def communicationlog_list(request):
    return crud_list(
        request,
        CommunicationLog.objects.filter(tenant=request.tenant).select_related("party"),
        "crm/activities/communicationlog/list.html",
        search_fields=["subject", "number", "body"],
        filters=[("channel", "channel", False), ("direction", "direction", False),
                 ("logged_via", "logged_via", False)],
        extra_context={"channel_choices": CommunicationLog.CHANNEL_CHOICES,
                       "direction_choices": CommunicationLog.DIRECTION_CHOICES,
                       "logged_via_choices": CommunicationLog.LOGGED_VIA_CHOICES},
    )


@login_required
def communicationlog_create(request):
    return crud_create(request, form_class=CommunicationLogForm,
                       template="crm/activities/communicationlog/form.html",
                       success_url="crm:communicationlog_list")


@login_required
def communicationlog_detail(request, pk):
    obj = get_object_or_404(
        CommunicationLog.objects.select_related("party", "owner", "related_opportunity", "related_case"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/activities/communicationlog/detail.html", {"obj": obj})


@login_required
def communicationlog_edit(request, pk):
    return crud_edit(request, model=CommunicationLog, pk=pk, form_class=CommunicationLogForm,
                     template="crm/activities/communicationlog/form.html",
                     success_url="crm:communicationlog_list")


@login_required
@require_POST
def communicationlog_delete(request, pk):
    return crud_delete(request, model=CommunicationLog, pk=pk, success_url="crm:communicationlog_list")


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
        "crm/directory/account/list.html", search_fields=["name", "tax_id"],
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
    return render(request, "crm/directory/account/detail.html", {
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
    return render(request, "crm/directory/account/form.html", {"form": form, "is_edit": False})


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
    return render(request, "crm/directory/account/form.html", {"form": form, "is_edit": True, "obj": party})


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
        "crm/directory/contact/list.html", search_fields=["name"],
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
    return render(request, "crm/directory/contact/detail.html", {
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
    return render(request, "crm/directory/contact/form.html", {"form": form, "is_edit": False})


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
    return render(request, "crm/directory/contact/form.html", {"form": form, "is_edit": True, "obj": party})


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
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import secrets  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402

from .forms import (  # noqa: E402
    ApprovalRequestForm,
    ContractDocumentForm,
    CrmMilestoneForm,
    CrmProjectForm,
    DealInvoiceForm,
    DocTemplateForm,
    DocumentVersionForm,
    ExpenseForm,
    HealthScoreConfigForm,
    HealthScoreForm,
    OnboardingPlanForm,
    OnboardingStepForm,
    PartnerPortalAccessForm,
    PaymentReceiptForm,
    ProductStockForm,
    PurchaseOrderForm,
    PurchaseOrderLineForm,
    ResourceAllocationForm,
    SignerRecordForm,
    SurveyForm,
    TimesheetForm,
    WebhookForm,
    WorkflowRuleForm,
)
from .models import (  # noqa: E402
    ApprovalRequest,
    ContractDocument,
    CrmMilestone,
    CrmProject,
    DealInvoice,
    DocTemplate,
    DocumentVersion,
    Expense,
    HealthScore,
    HealthScoreConfig,
    OnboardingPlan,
    OnboardingStep,
    PartnerPortalAccess,
    PaymentReceipt,
    ProductStock,
    PurchaseOrder,
    PurchaseOrderLine,
    ResourceAllocation,
    SignerRecord,
    Survey,
    Timesheet,
    Webhook,
    WebhookDelivery,
    WorkflowLog,
    WorkflowRule,
    compute_health_score,
)
# 1.7 Finance & Billing reuses the ACCOUNTING ledger (Module 2 owns it — lesson L29): the CRM
# layer creates draft Invoices + reads their status/allocations, never a second ledger.
from apps.accounting.models import Currency, Invoice, InvoiceLine, PaymentAllocation  # noqa: E402

User = get_user_model()


# ------------------------------------------------------------ 1.7 Expenses
@login_required
def expense_list(request):
    return crud_list(
        request,
        Expense.objects.filter(tenant=request.tenant).select_related(
            "opportunity", "project", "submitted_by", "approved_by"),
        "crm/finance/expense/list.html",
        search_fields=["number", "description", "opportunity__name"],
        filters=[("status", "status", False), ("category", "category", False)],
        extra_context={"status_choices": Expense.STATUS_CHOICES,
                       "category_choices": Expense.CATEGORY_CHOICES},
    )


@login_required
def expense_create(request):
    # Custom create (not crud_create) so submitted_by is system-set to the current user and
    # status stays the model default "draft" — neither is accepted from the form.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.submitted_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("crm:expense_list")
    else:
        form = ExpenseForm(tenant=request.tenant)
    return render(request, "crm/finance/expense/form.html", {"form": form, "is_edit": False})


@login_required
def expense_detail(request, pk):
    obj = get_object_or_404(
        Expense.objects.select_related("opportunity", "project", "submitted_by", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/finance/expense/detail.html", {"obj": obj})


@login_required
def expense_edit(request, pk):
    return crud_edit(request, model=Expense, pk=pk, form_class=ExpenseForm,
                     template="crm/finance/expense/form.html", success_url="crm:expense_list")


@login_required
@require_POST
def expense_delete(request, pk):
    return crud_delete(request, model=Expense, pk=pk, success_url="crm:expense_list")


@login_required
@require_POST
def expense_submit(request, pk):
    # The owner submits their own draft expense for approval (draft -> submitted).
    obj = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "submitted"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Expense {obj.number} submitted for approval.")
    return redirect("crm:expense_detail", pk=obj.pk)


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


# ------------------------------------------------------------ 1.7 Invoicing (DealInvoice)
# CRM-owned wrapper over the accounting ledger (L29): the conversion creates a DRAFT
# accounting.Invoice; issuing/GL-posting + cash application stay in Accounting (draft hand-off).
_CCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹",
                "AUD": "$", "CAD": "$", "CHF": "CHF", "CNY": "¥"}


def _ccy_symbol(code):
    """A display symbol for a currency code so an auto-created Currency isn't symbol-less."""
    return _CCY_SYMBOLS.get(code, "")


@login_required
def dealinvoice_list(request):
    # Annotate confirmed amount-paid + derived balance via a correlated Subquery so the list does
    # NOT fire one PaymentAllocation aggregate per row (performance-review N+1). Matches the
    # property's ``payment__status="confirmed"`` filter exactly. invoice.total is free (select_related).
    dec = DecimalField(max_digits=18, decimal_places=2)
    paid_sq = Subquery(
        PaymentAllocation.objects.filter(invoice=OuterRef("invoice"), payment__status="confirmed")
        .values("invoice").annotate(t=Sum("allocated_amount")).values("t"),
        output_field=DecimalField(max_digits=18, decimal_places=2))
    qs = (DealInvoice.objects.filter(tenant=request.tenant)
          .select_related("opportunity", "account", "invoice", "recurring_invoice")
          .annotate(amt_paid=Coalesce(paid_sq, Value(Decimal("0")), output_field=dec))
          .annotate(bal_due=Coalesce(F("invoice__total"), Value(Decimal("0")), output_field=dec)
                    - F("amt_paid")))
    return crud_list(
        request, qs,
        "crm/finance/dealinvoice/list.html",
        search_fields=["number", "account__name", "opportunity__name", "invoice__number"],
        filters=[("status", "invoice__status", False)],
        extra_context={"status_choices": Invoice.STATUS_CHOICES},
    )


@login_required
@require_POST
def dealinvoice_from_quote(request, quote_pk):
    """One-click quote→invoice conversion (1.7 Invoicing). Generates a DRAFT accounting.Invoice
    from an ACCEPTED quote — carrying line items, per-line + quote-level discount, and tax — and
    wraps it in a DealInvoice. The net unit price folds both discounts so invoice.total == quote.total."""
    quote = get_object_or_404(
        Quote.objects.select_related("account", "opportunity"), pk=quote_pk, tenant=request.tenant)
    existing = DealInvoice.objects.filter(tenant=request.tenant, quote=quote).first()
    if existing:  # idempotent — a converted quote jumps to its existing wrapper
        messages.info(request, f"This quote was already converted ({existing.number}).")
        return redirect("crm:dealinvoice_detail", pk=existing.pk)
    if quote.status != "accepted":
        messages.error(request, "Only an accepted quote can be converted to an invoice.")
        return redirect("crm:quote_detail", pk=quote.pk)
    if quote.account_id is None:
        messages.error(request, "This quote has no account (bill-to). Set an account before converting.")
        return redirect("crm:quote_detail", pk=quote.pk)
    lines = list(quote.lines.all())
    if not lines:
        messages.error(request, "This quote has no line items to invoice.")
        return redirect("crm:quote_detail", pk=quote.pk)

    code = (quote.currency_code or "USD").upper()[:3]  # clamp to the Currency.code max_length
    quote_disc = (Decimal(100) - Decimal(quote.discount_pct or 0)) / Decimal(100)
    with transaction.atomic():
        currency, _ = Currency.objects.get_or_create(
            code=code, defaults={"name": code, "symbol": _ccy_symbol(code)})
        inv = Invoice.objects.create(
            tenant=request.tenant, party=quote.account, issue_date=timezone.localdate(),
            status="draft", currency=currency,
            notes=f"Generated from quote {quote.number}" + (f" — {quote.name}" if quote.name else ""))
        for ln in lines:
            line_disc = (Decimal(100) - Decimal(ln.discount_pct or 0)) / Decimal(100)
            net_unit = (Decimal(ln.unit_price or 0) * line_disc * quote_disc).quantize(Decimal("0.01"))
            InvoiceLine.objects.create(
                invoice=inv, description=(ln.description or "Item")[:255],
                quantity=(ln.quantity or Decimal(1)), unit_price=net_unit,
                tax_rate_pct=(ln.tax_pct or Decimal(0)))
        inv.recalc_totals()
        deal = DealInvoice.objects.create(
            tenant=request.tenant, opportunity=quote.opportunity, quote=quote,
            account=quote.account, invoice=inv, notes=f"Converted from quote {quote.number}.")
    write_audit_log(request.user, deal, "create",
                    changes={"action": "convert_quote", "quote": quote.number, "invoice": inv.number})
    messages.success(request, f"Quote {quote.number} converted → invoice {inv.number} (draft). "
                              "Issue it from Accounting to post it to the ledger.")
    return redirect("crm:dealinvoice_detail", pk=deal.pk)


@login_required
def dealinvoice_create(request):
    # Custom create (not crud_create): ``invoice`` is editable=False on the model, so its value is
    # taken from the form's explicit field and set here. The conversion action is the usual path.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = DealInvoiceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.invoice = form.cleaned_data.get("invoice")
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Deal invoice {obj.number} created.")
            return redirect("crm:dealinvoice_detail", pk=obj.pk)
    else:
        form = DealInvoiceForm(tenant=request.tenant)
    return render(request, "crm/finance/dealinvoice/form.html", {"form": form, "is_edit": False})


@login_required
def dealinvoice_detail(request, pk):
    obj = get_object_or_404(
        DealInvoice.objects.select_related(
            "opportunity", "account", "quote", "invoice", "invoice__currency", "recurring_invoice"),
        pk=pk, tenant=request.tenant)
    # Each ledger allocation against the linked invoice is a partial/milestone payment.
    allocations = (obj.invoice.allocations.select_related("payment") if obj.invoice_id else [])
    receipts = obj.receipts.select_related("payment")
    # Deal margin = revenue (opportunity amount) − non-billable, non-rejected expenses on the deal.
    margin = None
    if obj.opportunity_id:
        revenue = obj.opportunity.amount or Decimal("0")
        cost = (Expense.objects.filter(tenant=request.tenant, opportunity_id=obj.opportunity_id,
                                       is_billable=False).exclude(status="rejected")
                .aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        margin = {"revenue": revenue, "cost": cost, "profit": revenue - cost,
                  "pct": ((revenue - cost) / revenue * 100) if revenue else None}
    # Precompute paid/balance once (the property hits the DB) so the template doesn't call
    # amount_paid() twice — once directly and once inside balance_due (performance-review #2).
    amount_paid = obj.amount_paid
    balance_due = obj.invoice_total - amount_paid
    return render(request, "crm/finance/dealinvoice/detail.html", {
        "obj": obj, "allocations": allocations, "receipts": receipts, "margin": margin,
        "amount_paid": amount_paid, "balance_due": balance_due,
    })


@login_required
def dealinvoice_edit(request, pk):
    obj = get_object_or_404(DealInvoice, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = DealInvoiceForm(request.POST, instance=obj, tenant=request.tenant, editing=True)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Updated successfully.")
            return redirect("crm:dealinvoice_detail", pk=obj.pk)
    else:
        form = DealInvoiceForm(instance=obj, tenant=request.tenant, editing=True)
    return render(request, "crm/finance/dealinvoice/form.html", {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def dealinvoice_delete(request, pk):
    # Deletes the CRM wrapper ONLY — the ledger invoice in Accounting is left untouched.
    return crud_delete(request, model=DealInvoice, pk=pk, success_url="crm:dealinvoice_list")


# ------------------------------------------------------------ 1.7 Payment Tracking (PaymentReceipt)
@login_required
def paymentreceipt_list(request):
    return crud_list(
        request,
        PaymentReceipt.objects.filter(tenant=request.tenant).select_related(
            "deal_invoice", "deal_invoice__invoice", "payment"),
        "crm/finance/paymentreceipt/list.html",
        search_fields=["number", "deal_invoice__number", "gateway_txn_id"],
        filters=[("method", "method", False), ("gateway", "gateway", False)],
        extra_context={"method_choices": PaymentReceipt.METHOD_CHOICES,
                       "gateway_choices": PaymentReceipt.GATEWAY_CHOICES},
    )


@login_required
def paymentreceipt_create(request):
    return crud_create(request, form_class=PaymentReceiptForm,
                       template="crm/finance/paymentreceipt/form.html",
                       success_url="crm:paymentreceipt_list")


@login_required
def paymentreceipt_detail(request, pk):
    obj = get_object_or_404(
        PaymentReceipt.objects.select_related(
            "deal_invoice", "deal_invoice__invoice", "deal_invoice__account", "payment"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/finance/paymentreceipt/detail.html", {"obj": obj})


@login_required
def paymentreceipt_edit(request, pk):
    return crud_edit(request, model=PaymentReceipt, pk=pk, form_class=PaymentReceiptForm,
                     template="crm/finance/paymentreceipt/form.html",
                     success_url="crm:paymentreceipt_list")


@login_required
@require_POST
def paymentreceipt_delete(request, pk):
    return crud_delete(request, model=PaymentReceipt, pk=pk, success_url="crm:paymentreceipt_list")


@login_required
def paymentreceipt_print(request, pk):
    """Standalone printable receipt (browser print → PDF). Server-side PDF (weasyprint) deferred."""
    obj = get_object_or_404(
        PaymentReceipt.objects.select_related(
            "deal_invoice", "deal_invoice__invoice", "deal_invoice__account", "payment"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/finance/paymentreceipt/receipt.html",
                  {"obj": obj, "tenant": request.tenant})


# ------------------------------------------------------------ 1.8 Projects
@login_required
def crmproject_list(request):
    # Annotate milestone counts so the progress bar (progress_pct) doesn't query per row.
    qs = (CrmProject.objects.filter(tenant=request.tenant)
          .select_related("account", "owner", "source_opportunity")
          .annotate(ms_total=Count("milestones"),
                    ms_done=Count("milestones", filter=Q(milestones__status="completed")))
          .order_by("-created_at"))  # explicit: annotate()+GROUP BY drops the Meta default ordering
    return crud_list(
        request, qs,
        "crm/projects/crmproject/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": CrmProject.STATUS_CHOICES},
    )


@login_required
def crmproject_create(request):
    return crud_create(request, form_class=CrmProjectForm, template="crm/projects/crmproject/form.html",
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
    return render(request, "crm/projects/crmproject/detail.html", {
        "obj": obj,
        "milestones": obj.milestones.filter(tenant=request.tenant).select_related("assignee"),
        "total_hours": hours["total"] or 0,
        "billable_hours": hours["billable"] or 0,
        "expense_total": expense_total,
    })


@login_required
def crmproject_edit(request, pk):
    return crud_edit(request, model=CrmProject, pk=pk, form_class=CrmProjectForm,
                     template="crm/projects/crmproject/form.html", success_url="crm:crmproject_list")


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
        "crm/projects/crmmilestone/list.html",
        search_fields=["number", "title"],
        filters=[("status", "status", False), ("project", "project_id", True)],
        extra_context={"status_choices": CrmMilestone.STATUS_CHOICES,
                       "kind_choices": CrmMilestone.KIND_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def crmmilestone_create(request):
    return crud_create(request, form_class=CrmMilestoneForm, template="crm/projects/crmmilestone/form.html",
                       success_url="crm:crmmilestone_list")


@login_required
def crmmilestone_detail(request, pk):
    obj = get_object_or_404(
        CrmMilestone.objects.select_related("project", "assignee", "parent"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/projects/crmmilestone/detail.html", {
        "obj": obj,
        "subtasks": CrmMilestone.objects.filter(tenant=request.tenant, parent=obj).select_related("assignee"),
    })


@login_required
def crmmilestone_edit(request, pk):
    return crud_edit(request, model=CrmMilestone, pk=pk, form_class=CrmMilestoneForm,
                     template="crm/projects/crmmilestone/form.html", success_url="crm:crmmilestone_list")


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
        "crm/projects/timesheet/list.html",
        search_fields=["number", "description", "employee__username"],
        filters=[("status", "status", False), ("project", "project_id", True),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": Timesheet.STATUS_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def timesheet_create(request):
    return crud_create(request, form_class=TimesheetForm, template="crm/projects/timesheet/form.html",
                       success_url="crm:timesheet_list")


@login_required
def timesheet_detail(request, pk):
    obj = get_object_or_404(
        Timesheet.objects.select_related("project", "employee", "milestone", "client", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/projects/timesheet/detail.html", {"obj": obj})


@login_required
def timesheet_edit(request, pk):
    # Lock down post-approval edits: once submitted/approved, the hours an approval was granted for
    # must not be silently mutated (code-review). Re-open by rejecting first.
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected timesheet can be edited.")
        return redirect("crm:timesheet_detail", pk=obj.pk)
    return crud_edit(request, model=Timesheet, pk=pk, form_class=TimesheetForm,
                     template="crm/projects/timesheet/form.html", success_url="crm:timesheet_list")


@login_required
@require_POST
def timesheet_delete(request, pk):
    # An approved (audited) timesheet must not be silently erased; only draft/rejected are deletable
    # (the template hides the button for other states — guard the view too) (security-review).
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected timesheet can be deleted.")
        return redirect("crm:timesheet_detail", pk=obj.pk)
    return crud_delete(request, model=Timesheet, pk=pk, success_url="crm:timesheet_list")


# ---- 1.8 Timesheet approval workflow (status off the form — advanced only here) ----------
@login_required
@require_POST
def timesheet_submit(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    # Only the time logger (or an admin) may submit it — not an arbitrary colleague (security-review).
    if not (obj.employee_id == request.user.pk or request.user.is_superuser
            or request.user.is_tenant_admin):
        messages.error(request, "You can only submit your own timesheet.")
        return redirect("crm:timesheet_detail", pk=obj.pk)
    if obj.status == "draft":
        obj.status = "submitted"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Timesheet {obj.number} submitted for approval.")
    return redirect("crm:timesheet_detail", pk=obj.pk)


@tenant_admin_required  # approving is privileged — a manager/admin, not the time logger
@require_POST
def timesheet_approve(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    obj.status = "approved"
    obj.approved_by = request.user
    obj.save(update_fields=["status", "approved_by", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Timesheet {obj.number} approved.")
    return redirect("crm:timesheet_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def timesheet_reject(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    obj.status = "rejected"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Timesheet {obj.number} rejected.")
    return redirect("crm:timesheet_detail", pk=obj.pk)


# ------------------------------------------------------------ 1.8 Resource Allocation
@login_required
def resourceallocation_list(request):
    return crud_list(
        request,
        ResourceAllocation.objects.filter(tenant=request.tenant).select_related("project", "assignee"),
        "crm/projects/resourceallocation/list.html",
        search_fields=["number", "role", "assignee__username", "project__name"],
        filters=[("status", "status", False), ("project", "project_id", True),
                 ("assignee", "assignee_id", True)],
        extra_context={"status_choices": ResourceAllocation.STATUS_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def resourceallocation_create(request):
    return crud_create(request, form_class=ResourceAllocationForm,
                       template="crm/projects/resourceallocation/form.html",
                       success_url="crm:resourceallocation_list")


@login_required
def resourceallocation_detail(request, pk):
    obj = get_object_or_404(
        ResourceAllocation.objects.select_related("project", "assignee"), pk=pk, tenant=request.tenant)
    return render(request, "crm/projects/resourceallocation/detail.html", {"obj": obj})


@login_required
def resourceallocation_edit(request, pk):
    return crud_edit(request, model=ResourceAllocation, pk=pk, form_class=ResourceAllocationForm,
                     template="crm/projects/resourceallocation/form.html",
                     success_url="crm:resourceallocation_list")


@login_required
@require_POST
def resourceallocation_delete(request, pk):
    return crud_delete(request, model=ResourceAllocation, pk=pk, success_url="crm:resourceallocation_list")


DEFAULT_WEEKLY_CAPACITY = Decimal("40")  # planned-hours capacity per person per week (future: per-employee)


@login_required
def resource_workload(request):
    """1.8 Resource Allocation — the workload/capacity board: per person, planned (allocations) vs.
    logged (timesheets) vs. capacity over a date window, flagging overbooked / free capacity. Two
    grouped aggregates (allocations + timesheets) — no per-person N+1."""
    today = timezone.localdate()
    default_start = today - timedelta(days=today.weekday())  # this week's Monday
    start = parse_date(request.GET.get("start", "") or "") or default_start
    end = parse_date(request.GET.get("end", "") or "") or (start + timedelta(days=27))  # 4 weeks
    if end < start:
        end = start + timedelta(days=27)
    weeks = Decimal((end - start).days + 1) / Decimal(7)
    capacity = (DEFAULT_WEEKLY_CAPACITY * weeks).quantize(Decimal("0.01"))

    # Planned: allocations overlapping the window (prorated in Python via overlap_hours).
    allocs = list(ResourceAllocation.objects.filter(tenant=request.tenant)
                  .exclude(status="cancelled")
                  .filter(Q(end_date__gte=start) | Q(end_date__isnull=True), start_date__lte=end)
                  .select_related("assignee"))
    planned_by_user, name_by_user = {}, {}
    for a in allocs:
        if a.assignee_id is None:
            continue
        planned_by_user[a.assignee_id] = planned_by_user.get(a.assignee_id, Decimal("0")) + a.overlap_hours(start, end)
        name_by_user[a.assignee_id] = a.assignee

    # Logged: timesheet hours grouped by employee in the window (one query).
    logged_by_user = {r["employee"]: (r["h"] or Decimal("0")) for r in
                      Timesheet.objects.filter(tenant=request.tenant, date__gte=start, date__lte=end)
                      .exclude(status="rejected")  # rejected hours aren't real logged work (code-review)
                      .values("employee").annotate(h=Sum("hours"))}

    user_ids = {uid for uid in (set(planned_by_user) | set(logged_by_user)) if uid is not None}
    missing = [uid for uid in user_ids if uid not in name_by_user]
    if missing:  # resolve names for people who only have timesheets (no allocation)
        for u in User.objects.filter(tenant=request.tenant, pk__in=missing):
            name_by_user[u.pk] = u

    rows = []
    for uid in user_ids:
        planned = planned_by_user.get(uid, Decimal("0"))
        logged = logged_by_user.get(uid, Decimal("0"))
        util = int(planned / capacity * 100) if capacity else 0
        rows.append({"user": name_by_user.get(uid), "planned": planned, "logged": logged,
                     "capacity": capacity, "available": capacity - planned,
                     "util_pct": util, "overbooked": planned > capacity})
    rows.sort(key=lambda r: r["planned"], reverse=True)
    return render(request, "crm/projects/workload.html",
                  {"rows": rows, "start": start, "end": end, "capacity": capacity})


@login_required
def crmproject_board(request):
    """1.8 Projects — Kanban board: milestones grouped into status columns (optional ?project=)."""
    projects = list(CrmProject.objects.filter(tenant=request.tenant).order_by("name"))
    qs = CrmMilestone.objects.filter(tenant=request.tenant).select_related("project", "assignee")
    project_id = request.GET.get("project", "").strip()
    selected_project = None
    if project_id.isdigit():
        pid = int(project_id)
        qs = qs.filter(project_id=pid)
        selected_project = next((p for p in projects if p.pk == pid), None)  # scan the list — no 2nd query
    ms_list = list(qs)  # evaluate once; bucket per column in Python (no re-query)
    columns = [{"value": v, "label": label, "cards": [m for m in ms_list if m.status == v]}
               for v, label in CrmMilestone.STATUS_CHOICES]
    return render(request, "crm/projects/board.html", {
        "columns": columns, "projects": projects, "selected_project": selected_project,
        "status_choices": CrmMilestone.STATUS_CHOICES,
    })


@login_required
@require_POST
def crmmilestone_move(request, pk):
    """1.8 Kanban — move a milestone to a new status from the board (save() stamps completed_at)."""
    obj = get_object_or_404(CrmMilestone, pk=pk, tenant=request.tenant)
    new_status = request.POST.get("status", "")
    if new_status in {v for v, _ in CrmMilestone.STATUS_CHOICES} and new_status != obj.status:
        obj.status = new_status
        obj.save()
        write_audit_log(request.user, obj, "update", {"action": "move", "status": new_status})
        messages.success(request, f"{obj.number} → {obj.get_status_display()}.")
    url = reverse("crm:crmproject_board")
    proj = request.POST.get("project", "")
    return redirect(f"{url}?project={proj}" if proj.isdigit() else url)


# ------------------------------------------------------------ 1.9 Document templates
@login_required
def doctemplate_list(request):
    return crud_list(
        request,
        DocTemplate.objects.filter(tenant=request.tenant).select_related("owner").defer("body"),
        "crm/documents/doctemplate/list.html",
        search_fields=["number", "name"],
        filters=[("template_type", "template_type", False), ("is_active", "is_active", False)],
        extra_context={"type_choices": DocTemplate.TYPE_CHOICES},
    )


@tenant_admin_required  # authoring a server-rendered template body is privileged (security-review)
def doctemplate_create(request):
    return crud_create(request, form_class=DocTemplateForm, template="crm/documents/doctemplate/form.html",
                       success_url="crm:doctemplate_list")


@login_required
def doctemplate_detail(request, pk):
    obj = get_object_or_404(DocTemplate.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/documents/doctemplate/detail.html", {
        "obj": obj,
        "contract_count": ContractDocument.objects.filter(tenant=request.tenant, template=obj).count(),
    })


@tenant_admin_required  # authoring a server-rendered template body is privileged (security-review)
def doctemplate_edit(request, pk):
    return crud_edit(request, model=DocTemplate, pk=pk, form_class=DocTemplateForm,
                     template="crm/documents/doctemplate/form.html", success_url="crm:doctemplate_list")


@tenant_admin_required  # symmetric with create/edit — template authoring is admin-only (security-review)
@require_POST
def doctemplate_delete(request, pk):
    return crud_delete(request, model=DocTemplate, pk=pk, success_url="crm:doctemplate_list")


# ------------------------------------------------------------ 1.9 Contract documents
@login_required
def contractdocument_list(request):
    return crud_list(
        request,
        ContractDocument.objects.filter(tenant=request.tenant).select_related(
            "template", "opportunity", "account", "owner").defer("body_snapshot"),
        "crm/documents/contractdocument/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("opportunity", "opportunity_id", True)],
        extra_context={"status_choices": ContractDocument.STATUS_CHOICES,
                       "opportunities": Opportunity.objects.filter(tenant=request.tenant).only("id", "number", "name").order_by("-created_at")[:200]},
    )


@login_required
def contractdocument_create(request):
    return crud_create(request, form_class=ContractDocumentForm,
                       template="crm/documents/contractdocument/form.html",
                       success_url="crm:contractdocument_list")


@login_required
def contractdocument_detail(request, pk):
    obj = get_object_or_404(
        ContractDocument.objects.select_related("template", "opportunity", "account", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/documents/contractdocument/detail.html", {
        "obj": obj,
        "signers": obj.signers.all(),  # signer_party isn't rendered — no JOIN needed (perf-review)
        "signer_form": SignerRecordForm(tenant=request.tenant),
        "versions": obj.versions.select_related("created_by").all(),
        "version_form": DocumentVersionForm(tenant=request.tenant),
    })


@login_required
def contractdocument_edit(request, pk):
    return crud_edit(request, model=ContractDocument, pk=pk, form_class=ContractDocumentForm,
                     template="crm/documents/contractdocument/form.html", success_url="crm:contractdocument_list")


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
        signer.order = contract.signers.count() + 1  # append after existing signers
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
    # Refuse any action on an expired contract (legal/state-machine integrity).
    if contract.expires_at and contract.expires_at < timezone.now():
        if contract.status not in ("signed", "declined", "expired"):
            contract.status = "expired"
            contract.save(update_fields=["status", "updated_at"])
        return render(request, "crm/documents/sign_document.html",
                      {"signer": signer, "contract": contract, "already": True, "expired": True})
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
    return render(request, "crm/documents/sign_document.html",
                  {"signer": signer, "contract": contract, "already": already})


# ---- 1.9 Document Generation + File Repository (version control) -------------------------
def _safe_doc_context(contract):
    """A string-only render context for DocTemplate bodies — NO model instances, so a user-authored
    template body can't traverse attributes or call methods (template-injection safe). Autoescape on."""
    acc, opp = contract.account, contract.opportunity
    return {
        "today": timezone.localdate().isoformat(),
        "contract": {"name": contract.name, "number": contract.number},
        "account": {"name": acc.name if acc else ""},
        "opportunity": {"name": opp.name if opp else "", "number": opp.number if opp else "",
                        "amount": str(opp.amount) if opp else ""},
        "owner": (contract.owner.get_full_name() or contract.owner.username) if contract.owner_id else "",
    }


# Isolated engine for rendering user-authored DocTemplate bodies. Its only builtins are RESTRICTED
# libraries carrying every Django default tag/filter EXCEPT the escape-bypass members (the
# ``safe``/``safeseq``/``json_script`` filters + the ``autoescape`` tag) and EXCEPT ``loader_tags``
# (so ``{% include %}``/``{% extends %}``/``{% load %}`` are invalid tags). A body can therefore only
# use ``{{ vars }}``, normal filters and ``{% if %}/{% for %}`` with auto-escaping ALWAYS on — it can
# never disable escaping, store raw markup, pull in internal templates, or load tag libs
# (security-review). Combined with the string-only ``_safe_doc_context`` (no model instances).
import django.template.defaultfilters as _doc_default_filters  # noqa: E402
import django.template.defaulttags as _doc_default_tags  # noqa: E402

_DOC_FILTER_LIB = Library()
for _fname, _ffn in _doc_default_filters.register.filters.items():
    if _fname not in {"safe", "safeseq", "json_script"}:
        _DOC_FILTER_LIB.filter(_fname, _ffn)
_DOC_TAG_LIB = Library()
for _tname, _tfn in _doc_default_tags.register.tags.items():
    if _tname != "autoescape":
        _DOC_TAG_LIB.tag(_tname, _tfn)


class _IsolatedDocEngine(Engine):
    default_builtins = []  # no auto builtins — restricted Library instances are injected directly below


_DOC_ENGINE = _IsolatedDocEngine(dirs=[], app_dirs=False, libraries={})
# Engine's ``builtins=`` / ``libraries=`` kwargs expect dotted import PATHS, not Library objects, so set
# the parsed builtins directly to our restricted libraries (no loader_tags / safe / safeseq / autoescape).
_DOC_ENGINE.template_builtins = [_DOC_TAG_LIB, _DOC_FILTER_LIB]


def _render_doc_body(contract):
    """Render a contract's linked template body against the safe context + isolated engine."""
    return _DOC_ENGINE.from_string(contract.template.body or "").render(Context(_safe_doc_context(contract)))


@login_required
@require_POST
def contractdocument_generate(request, pk):
    """1.9 Document Generation — render the linked template's merge variables into the contract body
    and capture it as a new immutable DocumentVersion. Rendered with a restricted string-only context
    + isolated engine so a template body can't reach model attributes/methods or include other files."""
    contract = get_object_or_404(
        ContractDocument.objects.select_related("template", "account", "opportunity", "owner"),
        pk=pk, tenant=request.tenant)  # the render reads all four FKs — avoid lazy per-FK queries
    if contract.status != "draft":
        messages.error(request, "Only a draft contract can be generated — its body is locked once sent.")
        return redirect("crm:contractdocument_detail", pk=pk)
    if contract.template_id is None:
        messages.error(request, "Link a document template first, then generate.")
        return redirect("crm:contractdocument_detail", pk=pk)
    try:
        rendered = _render_doc_body(contract)
    except Exception as e:  # a malformed template must not 500 the page  # noqa: BLE001
        messages.error(request, f"Template error: {e}")
        return redirect("crm:contractdocument_detail", pk=pk)
    with transaction.atomic():
        next_no = (contract.versions.aggregate(m=Max("version_no"))["m"] or 0) + 1
        contract.body_snapshot = rendered
        contract.current_version = next_no
        contract.save(update_fields=["body_snapshot", "current_version", "updated_at"])
        DocumentVersion.objects.create(
            tenant=request.tenant, contract=contract, version_no=next_no, body_snapshot=rendered,
            change_note=f"Generated from {contract.template.number}", created_by=request.user)
    write_audit_log(request.user, contract, "update", {"action": "generate", "version": next_no})
    messages.success(request, f"Generated v{next_no} from {contract.template.number}.")
    return redirect("crm:contractdocument_detail", pk=pk)


@login_required
@require_POST
def contractdocument_version_add(request, pk):
    """1.9 File Repository — capture a new revision: an uploaded file + the current body snapshot."""
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    if contract.status in ("signed", "declined"):
        messages.error(request, "Can't add revisions to a signed or declined contract.")
        return redirect("crm:contractdocument_detail", pk=pk)
    form = DocumentVersionForm(request.POST, request.FILES, tenant=request.tenant)
    if form.is_valid():
        with transaction.atomic():
            next_no = (contract.versions.aggregate(m=Max("version_no"))["m"] or 0) + 1
            ver = form.save(commit=False)
            ver.tenant = request.tenant
            ver.contract = contract
            ver.version_no = next_no
            ver.body_snapshot = contract.body_snapshot
            ver.created_by = request.user
            ver.save()
            contract.current_version = next_no
            contract.save(update_fields=["current_version", "updated_at"])
        write_audit_log(request.user, contract, "update", {"action": "version_add", "version": next_no})
        messages.success(request, f"Revision v{next_no} added.")
    else:
        messages.error(request, "Could not add the revision — check the file type/size.")
    return redirect("crm:contractdocument_detail", pk=contract.pk)


@login_required
@require_POST
def contractdocument_send(request, pk):
    """1.9 — move a draft contract → sent (needs a generated body + at least one signer)."""
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    if contract.status != "draft":
        messages.info(request, "Only a draft contract can be sent.")
        return redirect("crm:contractdocument_detail", pk=pk)
    if not contract.body_snapshot:
        messages.error(request, "Generate the document body before sending.")
        return redirect("crm:contractdocument_detail", pk=pk)
    if not contract.signers.exists():
        messages.error(request, "Add at least one signer before sending.")
        return redirect("crm:contractdocument_detail", pk=pk)
    contract.status = "sent"
    contract.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, contract, "update", {"action": "send"})
    messages.success(request, f"Contract {contract.number} marked as sent — share each signer's link.")
    return redirect("crm:contractdocument_detail", pk=pk)


@login_required
def documentversion_detail(request, pk):
    """Read-only view of one immutable contract revision (snapshot + file download)."""
    obj = get_object_or_404(
        DocumentVersion.objects.select_related("contract", "created_by"), pk=pk, tenant=request.tenant)
    return render(request, "crm/documents/documentversion/detail.html", {"obj": obj})


@login_required
def document_repository(request):
    """1.9 File Repository — contracts organized by account/deal, with version counts."""
    qs = (ContractDocument.objects.filter(tenant=request.tenant)
          .select_related("account", "opportunity", "owner")
          .annotate(version_count=Count("versions"))
          .defer("body_snapshot")
          .order_by("-created_at"))  # annotate()+GROUP BY drops the Meta default ordering
    return crud_list(
        request, qs, "crm/documents/repository.html",
        search_fields=["number", "name", "account__name", "opportunity__name"],
        filters=[("status", "status", False), ("account", "account_id", True),
                 ("opportunity", "opportunity_id", True)],
        extra_context={
            "status_choices": ContractDocument.STATUS_CHOICES,
            "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").only("id", "name").order_by("name"),
            "opportunities": Opportunity.objects.filter(tenant=request.tenant).only("id", "number", "name").order_by("-created_at")[:200],
        },
    )


# ------------------------------------------------------------ 1.10 Workflow rules
@login_required
def workflowrule_list(request):
    return crud_list(
        request,
        WorkflowRule.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/workflow/workflowrule/list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False), ("trigger_entity", "trigger_entity", False)],
        extra_context={"entity_choices": WorkflowRule.ENTITY_CHOICES,
                       "event_choices": WorkflowRule.EVENT_CHOICES},
    )


@login_required
def workflowrule_create(request):
    return crud_create(request, form_class=WorkflowRuleForm, template="crm/workflow/workflowrule/form.html",
                       success_url="crm:workflowrule_list")


@login_required
def workflowrule_detail(request, pk):
    obj = get_object_or_404(WorkflowRule.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/workflowrule/detail.html", {
        "obj": obj,
        "logs": WorkflowLog.objects.filter(tenant=request.tenant, rule=obj)[:10],
    })


@login_required
def workflowrule_edit(request, pk):
    return crud_edit(request, model=WorkflowRule, pk=pk, form_class=WorkflowRuleForm,
                     template="crm/workflow/workflowrule/form.html", success_url="crm:workflowrule_list")


@login_required
@require_POST
def workflowrule_delete(request, pk):
    return crud_delete(request, model=WorkflowRule, pk=pk, success_url="crm:workflowrule_list")


# ------------------------------------------------------------ 1.10 Workflow logs (read-only)
@login_required
def workflowlog_list(request):
    return crud_list(
        request,
        WorkflowLog.objects.filter(tenant=request.tenant).select_related("rule").defer("error_msg"),
        "crm/workflow/workflowlog/list.html",
        search_fields=["record_label", "error_msg"],
        filters=[("status", "status", False), ("rule", "rule_id", True)],
        extra_context={"status_choices": WorkflowLog.STATUS_CHOICES,
                       "rules": WorkflowRule.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")},
    )


@login_required
def workflowlog_detail(request, pk):
    obj = get_object_or_404(WorkflowLog.objects.select_related("rule"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/workflowlog/detail.html", {"obj": obj})


# ------------------------------------------------------------ 1.10 Approval requests
@login_required
def approvalrequest_list(request):
    return crud_list(
        request,
        ApprovalRequest.objects.filter(tenant=request.tenant).select_related(
            "approver", "requested_by", "rule"),
        "crm/workflow/approvalrequest/list.html",
        search_fields=["number", "subject", "record_label"],
        filters=[("status", "status", False), ("approver", "approver_id", True)],
        extra_context={"status_choices": ApprovalRequest.STATUS_CHOICES,
                       "approvers": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def approvalrequest_create(request):
    return crud_create(request, form_class=ApprovalRequestForm,
                       template="crm/workflow/approvalrequest/form.html", success_url="crm:approvalrequest_list")


@login_required
def approvalrequest_detail(request, pk):
    obj = get_object_or_404(
        ApprovalRequest.objects.select_related("approver", "requested_by", "rule"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/approvalrequest/detail.html", {"obj": obj})


@login_required
def approvalrequest_edit(request, pk):
    return crud_edit(request, model=ApprovalRequest, pk=pk, form_class=ApprovalRequestForm,
                     template="crm/workflow/approvalrequest/form.html", success_url="crm:approvalrequest_list")


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


# ---- 1.10 Workflow execution engine + Webhooks ------------------------------------------
_RULE_ENTITY_MODELS = {
    "lead": Lead, "opportunity": Opportunity, "case": Case, "expense": Expense,
    "contract": ContractDocument, "health_score": HealthScore,
}
_RULE_RUN_LIMIT = 50  # cap records evaluated per manual run (bounded engine)


def _safe_record_field(record, name):
    """Read a scalar attribute off a record for condition evaluation. SAFE: rejects private/dunder
    names and callables (no method calls / relation traversal) — only a plain stored value."""
    if not name or name.startswith("_"):
        return None
    value = getattr(record, name, None)
    return None if callable(value) else value


def _eval_conditions(record, conditions):
    """AND of ``[{field, operator, value}]``. Empty/invalid → matches (a rule with no conditions fires
    on every candidate). Unknown operators or bad numeric casts → that condition fails (safe default)."""
    if not isinstance(conditions, list):
        return True
    for cond in conditions:
        if not isinstance(cond, dict):
            return False
        actual = _safe_record_field(record, str(cond.get("field", "")))
        op, target = cond.get("operator", "eq"), cond.get("value", "")
        a, t = ("" if actual is None else str(actual)), str(target)
        try:
            if op == "eq":
                ok = a == t
            elif op == "ne":
                ok = a != t
            elif op in ("gt", "lt", "gte", "lte"):
                fa, ft = float(actual), float(target)
                ok = {"gt": fa > ft, "lt": fa < ft, "gte": fa >= ft, "lte": fa <= ft}[op]
            elif op == "contains":
                ok = t in a
            elif op == "icontains":
                ok = t.lower() in a.lower()
            else:
                ok = False
        except (TypeError, ValueError):
            ok = False
        if not ok:
            return False
    return True


def _webhook_payload(event, record):
    return json.dumps({"event": event, "record": str(record), "id": record.pk,
                       "at": timezone.now().isoformat()}, default=str)


def _deliver_webhook(webhook, event, payload):
    """Record a (signed) delivery for a webhook. The real outbound HTTP POST is **deferred**.
    # WARNING: SSRF — when implementing the real POST, require https, resolve the host and REJECT
    # private/loopback/link-local/169.254.169.254 (cloud-metadata) ranges, disable redirects, set a
    # short timeout, and cap the response size. Never POST to a raw user-supplied URL without that."""
    sig = ""
    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return WebhookDelivery.objects.create(
        tenant=webhook.tenant, webhook=webhook, event=event, payload=payload,
        signature=sig, status="pending")


def _run_rule(rule, user):
    """Evaluate ``rule`` against ≤``_RULE_RUN_LIMIT`` recent tenant records of its trigger entity and
    fire matching actions, logging each to WorkflowLog. Bounded + tenant-scoped. Returns a summary."""
    Model = _RULE_ENTITY_MODELS.get(rule.trigger_entity)
    summary = {"evaluated": 0, "matched": 0, "actions": 0}
    if Model is None:
        WorkflowLog.objects.create(tenant=rule.tenant, rule=rule, record_label="(no entity)",
                                   status="skipped", error_msg="Unknown trigger entity.")
        return summary
    event = f"{rule.trigger_entity}.{rule.trigger_event}"
    actions = rule.actions if isinstance(rule.actions, list) else []
    records = Model.objects.filter(tenant=rule.tenant).order_by("-id")[:_RULE_RUN_LIMIT]
    with transaction.atomic():
        for rec in records:
            summary["evaluated"] += 1
            if not _eval_conditions(rec, rule.conditions):
                continue
            summary["matched"] += 1
            label = str(rec)[:255]
            try:
                for action in actions:
                    atype = (action.get("type") if isinstance(action, dict) else "") or ""
                    params = action.get("params", {}) if isinstance(action, dict) else {}
                    if atype == "webhook":
                        for wh in Webhook.objects.filter(tenant=rule.tenant, is_active=True,
                                                         trigger_entity=rule.trigger_entity,
                                                         trigger_event=rule.trigger_event):
                            _deliver_webhook(wh, event, _webhook_payload(event, rec))
                            summary["actions"] += 1
                    elif atype == "approval":
                        ApprovalRequest.objects.create(
                            tenant=rule.tenant, rule=rule,
                            subject=(params.get("subject") or rule.name)[:255],
                            record_label=label, requested_by=user, status="pending")
                        summary["actions"] += 1
                    else:
                        summary["actions"] += 1  # alert/assign/email — logged note (real send deferred)
                WorkflowLog.objects.create(tenant=rule.tenant, rule=rule, record_label=label, status="success")
            except Exception as e:  # one record's failure must not abort the whole run  # noqa: BLE001
                WorkflowLog.objects.create(tenant=rule.tenant, rule=rule, record_label=label,
                                           status="failed", error_msg=str(e)[:2000])
    return summary


@tenant_admin_required
@require_POST
def workflowrule_run(request, pk):
    """1.10 — manually run a rule now (evaluate conditions + fire actions over recent records, bounded)."""
    rule = get_object_or_404(WorkflowRule, pk=pk, tenant=request.tenant)
    if not rule.is_active:
        messages.error(request, "Activate the rule before running it.")
        return redirect("crm:workflowrule_detail", pk=pk)
    s = _run_rule(rule, request.user)
    write_audit_log(request.user, rule, "update", {"action": "run", **s})
    messages.success(request, f"Ran {rule.number}: {s['matched']}/{s['evaluated']} matched, "
                              f"{s['actions']} action(s) fired.")
    return redirect("crm:workflowrule_detail", pk=pk)


@login_required
def webhook_list(request):
    return crud_list(
        request,
        (Webhook.objects.filter(tenant=request.tenant).annotate(delivery_count=Count("deliveries"))
         .order_by("-created_at")),  # annotate()+GROUP BY drops the Meta default ordering
        "crm/workflow/webhook/list.html",
        search_fields=["number", "name", "target_url"],
        filters=[("is_active", "is_active", False), ("trigger_entity", "trigger_entity", False),
                 ("trigger_event", "trigger_event", False)],
        extra_context={"entity_choices": WorkflowRule.ENTITY_CHOICES,
                       "event_choices": WorkflowRule.EVENT_CHOICES},
    )


@login_required
def webhook_create(request):
    return crud_create(request, form_class=WebhookForm, template="crm/workflow/webhook/form.html",
                       success_url="crm:webhook_list")


@login_required
def webhook_detail(request, pk):
    obj = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/webhook/detail.html",
                  {"obj": obj, "deliveries": obj.deliveries.all()[:10]})


@login_required
def webhook_edit(request, pk):
    return crud_edit(request, model=Webhook, pk=pk, form_class=WebhookForm,
                     template="crm/workflow/webhook/form.html", success_url="crm:webhook_list")


@login_required
@require_POST
def webhook_delete(request, pk):
    return crud_delete(request, model=Webhook, pk=pk, success_url="crm:webhook_list")


@tenant_admin_required
@require_POST
def webhook_test(request, pk):
    """1.10 — fire a signed test delivery for a webhook (records a WebhookDelivery; HTTP deferred)."""
    webhook = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)
    payload = json.dumps({"event": "manual.test", "webhook": webhook.number,
                          "at": timezone.now().isoformat()})
    _deliver_webhook(webhook, "manual.test", payload)
    write_audit_log(request.user, webhook, "update", {"action": "test"})
    messages.success(request, f"Test delivery recorded for {webhook.number} (real HTTP delivery is deferred).")
    return redirect("crm:webhook_detail", pk=pk)


@login_required
def webhookdelivery_list(request):
    return crud_list(
        request,
        WebhookDelivery.objects.filter(tenant=request.tenant).select_related("webhook").defer("payload"),
        "crm/workflow/webhookdelivery/list.html",
        search_fields=["event", "webhook__name"],
        filters=[("status", "status", False), ("webhook", "webhook_id", True)],
        extra_context={"status_choices": WebhookDelivery.STATUS_CHOICES,
                       "webhooks": Webhook.objects.filter(tenant=request.tenant).only("id", "number", "name").order_by("name")},
    )


@login_required
def webhookdelivery_detail(request, pk):
    obj = get_object_or_404(WebhookDelivery.objects.select_related("webhook"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/webhookdelivery/detail.html", {"obj": obj})


# ------------------------------------------------------------ 1.11 Onboarding plans
@login_required
def onboardingplan_list(request):
    return crud_list(
        request,
        OnboardingPlan.objects.filter(tenant=request.tenant).select_related("account", "owner").prefetch_related("steps"),
        "crm/success/onboardingplan/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("account", "account_id", True)],
        extra_context={"status_choices": OnboardingPlan.STATUS_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def onboardingplan_create(request):
    return crud_create(request, form_class=OnboardingPlanForm,
                       template="crm/success/onboardingplan/form.html", success_url="crm:onboardingplan_list")


@login_required
def onboardingplan_detail(request, pk):
    obj = get_object_or_404(OnboardingPlan.objects.select_related("account", "owner"),
                            pk=pk, tenant=request.tenant)
    steps = list(obj.steps.select_related("assignee").all())
    done = sum(1 for s in steps if s.completed_at is not None)
    return render(request, "crm/success/onboardingplan/detail.html", {
        "obj": obj,
        "steps": steps,
        "progress_pct": round(done / len(steps) * 100) if steps else 0,  # from the already-fetched steps
        "step_form": OnboardingStepForm(tenant=request.tenant),
    })


@login_required
def onboardingplan_edit(request, pk):
    return crud_edit(request, model=OnboardingPlan, pk=pk, form_class=OnboardingPlanForm,
                     template="crm/success/onboardingplan/form.html", success_url="crm:onboardingplan_list")


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
        step.order = plan.steps.count()  # append after existing steps
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
        "crm/success/healthscore/list.html",
        search_fields=["number", "account__name"],
        filters=[("tier", "tier", False)],
        extra_context={"tier_choices": HealthScore.TIER_CHOICES},
    )


@login_required
def healthscore_create(request):
    return crud_create(request, form_class=HealthScoreForm, template="crm/success/healthscore/form.html",
                       success_url="crm:healthscore_list")


@login_required
def healthscore_detail(request, pk):
    obj = get_object_or_404(HealthScore.objects.select_related("account"), pk=pk, tenant=request.tenant)
    return render(request, "crm/success/healthscore/detail.html", {"obj": obj})


@login_required
def healthscore_edit(request, pk):
    return crud_edit(request, model=HealthScore, pk=pk, form_class=HealthScoreForm,
                     template="crm/success/healthscore/form.html", success_url="crm:healthscore_list")


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


@tenant_admin_required  # health-scoring weights are a tenant-wide privileged setting
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
    return render(request, "crm/success/health_config/form.html", {"form": form, "config": config})


# ------------------------------------------------------------ 1.11 Surveys
@login_required
def survey_list(request):
    return crud_list(
        request,
        Survey.objects.filter(tenant=request.tenant).select_related("account", "contact", "related_case"),
        "crm/success/survey/list.html",
        search_fields=["number", "feedback_text", "account__name"],
        filters=[("survey_type", "survey_type", False), ("classification", "classification", False),
                 ("account", "account_id", True)],
        extra_context={"type_choices": Survey.TYPE_CHOICES,
                       "classification_choices": Survey.CLASSIFICATION_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def survey_create(request):
    return crud_create(request, form_class=SurveyForm, template="crm/success/survey/form.html",
                       success_url="crm:survey_list")


@login_required
def survey_detail(request, pk):
    obj = get_object_or_404(Survey.objects.select_related("account", "contact", "related_case"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/success/survey/detail.html", {"obj": obj})


@login_required
def survey_edit(request, pk):
    return crud_edit(request, model=Survey, pk=pk, form_class=SurveyForm,
                     template="crm/success/survey/form.html", success_url="crm:survey_list")


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
        # Public endpoint — cap feedback length to prevent unbounded-storage abuse.
        survey.feedback_text = request.POST.get("feedback_text", "").strip()[:4000]
        survey.responded_at = timezone.now()
        survey.save()  # save() auto-classifies NPS
        return redirect("crm:survey_respond", token=token)
    return render(request, "crm/success/survey/respond.html", {"survey": survey})


# ------------------------------------------------------------ 1.12 Product stock
@login_required
def productstock_list(request):
    return crud_list(
        request,
        ProductStock.objects.filter(tenant=request.tenant),
        "crm/vendor/productstock/list.html",
        search_fields=["number", "name", "sku"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def productstock_create(request):
    return crud_create(request, form_class=ProductStockForm, template="crm/vendor/productstock/form.html",
                       success_url="crm:productstock_list")


@login_required
def productstock_detail(request, pk):
    obj = get_object_or_404(ProductStock, pk=pk, tenant=request.tenant)
    return render(request, "crm/vendor/productstock/detail.html", {"obj": obj})


@login_required
def productstock_edit(request, pk):
    return crud_edit(request, model=ProductStock, pk=pk, form_class=ProductStockForm,
                     template="crm/vendor/productstock/form.html", success_url="crm:productstock_list")


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
        "crm/vendor/crm_po/list.html",
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
    return render(request, "crm/vendor/crm_po/form.html", {"form": form, "is_edit": False})


@login_required
def crm_po_detail(request, pk):
    obj = get_object_or_404(PurchaseOrder.objects.select_related("vendor", "owner"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/vendor/crm_po/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("product").all(),
        "line_form": PurchaseOrderLineForm(tenant=request.tenant),
    })


@login_required
def crm_po_edit(request, pk):
    return crud_edit(request, model=PurchaseOrder, pk=pk, form_class=PurchaseOrderForm,
                     template="crm/vendor/crm_po/form.html", success_url="crm:crm_po_list")


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
            line.order = po.lines.count()  # append after existing lines
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


@tenant_admin_required  # receiving mutates inventory (irreversible) — privileged action
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
        "crm/vendor/partnerportalaccess/list.html",
        search_fields=["number", "partner_party__name", "portal_user__username"],
        filters=[("is_active", "is_active", False), ("access_level", "access_level", False)],
        extra_context={"access_choices": PartnerPortalAccess.ACCESS_CHOICES},
    )


@login_required
def partnerportalaccess_create(request):
    return crud_create(request, form_class=PartnerPortalAccessForm,
                       template="crm/vendor/partnerportalaccess/form.html",
                       success_url="crm:partnerportalaccess_list")


@login_required
def partnerportalaccess_detail(request, pk):
    obj = get_object_or_404(
        PartnerPortalAccess.objects.select_related("partner_party", "portal_user"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/vendor/partnerportalaccess/detail.html", {"obj": obj})


@login_required
def partnerportalaccess_edit(request, pk):
    return crud_edit(request, model=PartnerPortalAccess, pk=pk, form_class=PartnerPortalAccessForm,
                     template="crm/vendor/partnerportalaccess/form.html",
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
    po_count = PurchaseOrder.objects.filter(tenant=request.tenant, vendor=access.partner_party).count()
    return render(request, "crm/vendor/portal_dashboard.html", {"access": access, "po_count": po_count})


@login_required
def portal_po_list(request):
    access = _portal_access(request)
    if access is None:
        messages.error(request, "You don't have partner portal access.")
        return redirect("dashboard:home")
    orders = (PurchaseOrder.objects
              .filter(tenant=request.tenant, vendor=access.partner_party)
              .order_by("-created_at"))
    page_obj = paginate(request, orders)
    return render(request, "crm/vendor/portal_po/list.html",
                  {"access": access, "object_list": page_obj.object_list, "page_obj": page_obj})


@login_required
def portal_stock(request):
    access = _portal_access(request)
    if access is None or not access.can_view_stock:
        messages.error(request, "You don't have access to stock levels.")
        return redirect("crm:portal_dashboard" if access else "dashboard:home")
    products = ProductStock.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    page_obj = paginate(request, products)
    return render(request, "crm/vendor/portal_stock.html",
                  {"access": access, "object_list": page_obj.object_list, "page_obj": page_obj})


# ============================================================================
# ===== Module 1.6 — Analytics & Reporting ===================================
# Saved per-user dashboards (widgets computed LIVE on render) + saved standard
# reports (4 canned types) with point-in-time snapshots. All compute lives in
# apps/crm/analytics.py; views stay thin and tenant-scope every queryset.
# ============================================================================
from .analytics import compute_report, compute_widget  # noqa: E402
from .forms import (  # noqa: E402
    AnalyticsDashboardForm,
    AnalyticsReportForm,
    DashboardWidgetForm,
)
from .models import (  # noqa: E402
    AnalyticsDashboard,
    AnalyticsReport,
    DashboardWidget,
    ReportSnapshot,
)


# ----- Dashboards -----------------------------------------------------------
@login_required
def dashboard_list(request):
    qs = AnalyticsDashboard.objects.filter(tenant=request.tenant).select_related("owner")
    return crud_list(
        request, qs, "crm/analytics/dashboard/list.html",
        search_fields=["name", "number", "description"],
        filters=[("owner", "owner_id", True)],
        extra_context={"owners": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


def _can_share_dashboards(user):
    # Publishing (is_shared) / defaulting (is_default) a dashboard is a tenant-wide setting,
    # so it is restricted to tenant admins (or superuser) — security-review finding.
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


@login_required
def dashboard_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    can_share = _can_share_dashboards(request.user)
    if request.method == "POST":
        form = AnalyticsDashboardForm(request.POST, tenant=request.tenant, can_share=can_share)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("crm:dashboard_detail", pk=obj.pk)
    else:
        form = AnalyticsDashboardForm(tenant=request.tenant, can_share=can_share)
    return render(request, "crm/analytics/dashboard/form.html", {"form": form, "is_edit": False})


@login_required
def dashboard_detail(request, pk):
    dashboard = get_object_or_404(
        AnalyticsDashboard.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    cols = {"one": 1, "two": 2, "three": 3}.get(dashboard.layout, 2)
    span_map = {"small": 1, "medium": 2, "large": 3, "full": cols}
    rendered, chart_configs = [], []
    for w in dashboard.widgets.filter(tenant=request.tenant):
        result = compute_widget(w)
        rendered.append({"widget": w, "result": result, "span": min(span_map.get(w.size, 1), cols)})
        # Only true Chart.js charts go to JS; KPI/gauge/table render as HTML.
        if result.get("kind") == "series" and w.chart_type in ("bar", "line", "pie", "doughnut"):
            chart_configs.append({"id": w.pk, "type": w.chart_type,
                                  "labels": result.get("labels", []), "data": result.get("data", [])})
    return render(request, "crm/analytics/dashboard/detail.html",
                  {"obj": dashboard, "rendered_widgets": rendered, "chart_configs": chart_configs, "cols": cols})


@login_required
def dashboard_edit(request, pk):
    obj = get_object_or_404(AnalyticsDashboard, pk=pk, tenant=request.tenant)
    can_share = _can_share_dashboards(request.user)
    if request.method == "POST":
        form = AnalyticsDashboardForm(request.POST, instance=obj, tenant=request.tenant, can_share=can_share)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Updated successfully.")
            return redirect("crm:dashboard_detail", pk=obj.pk)
    else:
        form = AnalyticsDashboardForm(instance=obj, tenant=request.tenant, can_share=can_share)
    return render(request, "crm/analytics/dashboard/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def dashboard_delete(request, pk):
    return crud_delete(request, model=AnalyticsDashboard, pk=pk, success_url="crm:dashboard_list")


# ----- Dashboard widgets (children of a dashboard) --------------------------
@login_required
def widget_create(request, dash_pk):
    dashboard = get_object_or_404(AnalyticsDashboard, pk=dash_pk, tenant=request.tenant)
    if request.method == "POST":
        form = DashboardWidgetForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            widget = form.save(commit=False)
            widget.tenant = request.tenant
            widget.dashboard = dashboard
            last = dashboard.widgets.order_by("-position").first()
            widget.position = (last.position + 1) if last else 0
            widget.save()
            write_audit_log(request.user, widget, "create")
            messages.success(request, "Widget added.")
            return redirect("crm:dashboard_detail", pk=dashboard.pk)
    else:
        form = DashboardWidgetForm(tenant=request.tenant)
    return render(request, "crm/analytics/widget/form.html",
                  {"form": form, "is_edit": False, "dashboard": dashboard})


@login_required
def widget_edit(request, pk):
    widget = get_object_or_404(DashboardWidget, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = DashboardWidgetForm(request.POST, instance=widget, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Widget updated.")
            return redirect("crm:dashboard_detail", pk=widget.dashboard_id)
    else:
        form = DashboardWidgetForm(instance=widget, tenant=request.tenant)
    return render(request, "crm/analytics/widget/form.html",
                  {"form": form, "is_edit": True, "obj": widget, "dashboard": widget.dashboard})


@login_required
@require_POST
def widget_delete(request, pk):
    widget = get_object_or_404(DashboardWidget, pk=pk, tenant=request.tenant)
    dash_pk = widget.dashboard_id
    write_audit_log(request.user, widget, "delete")
    widget.delete()
    messages.success(request, "Widget removed.")
    return redirect("crm:dashboard_detail", pk=dash_pk)


@login_required
@require_POST
def widget_move(request, pk, direction):
    """Reorder a widget one slot up/down. Normalizes positions to 0..n-1 so it is robust even
    when several widgets share the default position 0."""
    widget = get_object_or_404(DashboardWidget, pk=pk, tenant=request.tenant)
    order = list(widget.dashboard.widgets.filter(tenant=request.tenant).order_by("position", "id"))
    idx = next((i for i, w in enumerate(order) if w.pk == widget.pk), None)
    if idx is not None and direction in ("up", "down"):
        swap = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap < len(order):
            order[idx], order[swap] = order[swap], order[idx]
            to_update = []
            for i, w in enumerate(order):
                if w.position != i:
                    w.position = i
                    to_update.append(w)
            if to_update:
                DashboardWidget.objects.bulk_update(to_update, ["position"])  # one statement, not N
                write_audit_log(request.user, widget, "update", {"action": "move", "direction": direction})
    return redirect("crm:dashboard_detail", pk=widget.dashboard_id)


# ----- Standard reports -----------------------------------------------------
@login_required
def report_list(request):
    qs = AnalyticsReport.objects.filter(tenant=request.tenant).select_related("owner")
    return crud_list(
        request, qs, "crm/analytics/report/list.html",
        search_fields=["name", "number", "description"],
        filters=[("report_type", "report_type", False)],
        extra_context={"report_type_choices": AnalyticsReport._meta.get_field("report_type").choices},
    )


@login_required
def report_create(request):
    return crud_create(
        request, form_class=AnalyticsReportForm,
        template="crm/analytics/report/form.html", success_url="crm:report_list")


@login_required
def report_detail(request, pk):
    report = get_object_or_404(
        AnalyticsReport.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    result = compute_report(report)
    # Stamp last_run_at without bumping updated_at (system field; .update() bypasses auto_now).
    now = timezone.now()
    AnalyticsReport.objects.filter(pk=report.pk).update(last_run_at=now)
    report.last_run_at = now
    # Cap + defer the heavy summary/data JSON columns — the list panel only needs the header fields.
    snapshots = (report.snapshots.filter(tenant=request.tenant)
                 .select_related("generated_by")
                 .only("pk", "title", "generated_at", "generated_by__username",
                       "generated_by__first_name", "generated_by__last_name")[:50])
    return render(request, "crm/analytics/report/detail.html",
                  {"obj": report, "result": result, "snapshots": snapshots})


@login_required
def report_edit(request, pk):
    return crud_edit(
        request, model=AnalyticsReport, pk=pk, form_class=AnalyticsReportForm,
        template="crm/analytics/report/form.html",
        success_url=reverse("crm:report_detail", args=[pk]))


@login_required
@require_POST
def report_delete(request, pk):
    return crud_delete(request, model=AnalyticsReport, pk=pk, success_url="crm:report_list")


@login_required
@require_POST
def report_favorite(request, pk):
    report = get_object_or_404(AnalyticsReport, pk=pk, tenant=request.tenant)
    report.is_favorite = not report.is_favorite
    report.save(update_fields=["is_favorite", "updated_at"])
    write_audit_log(request.user, report, "update", {"is_favorite": report.is_favorite})
    messages.success(request, "Pinned to top." if report.is_favorite else "Unpinned.")
    return redirect("crm:report_detail", pk=report.pk)


@login_required
@require_POST
def report_snapshot(request, pk):
    report = get_object_or_404(AnalyticsReport, pk=pk, tenant=request.tenant)
    result = compute_report(report)
    with transaction.atomic():
        snap = ReportSnapshot.objects.create(
            tenant=request.tenant, report=report,
            title="{} — {:%Y-%m-%d %H:%M}".format(report.name, timezone.now()),
            generated_by=request.user if request.user.is_authenticated else None,
            summary=result.get("summary", []),
            data={k: result.get(k) for k in
                  ("columns", "rows", "chart_type", "chart_label", "chart_labels", "chart_data")},
        )
        AnalyticsReport.objects.filter(pk=report.pk).update(last_run_at=timezone.now())
        write_audit_log(request.user, snap, "create")
    messages.success(request, "Snapshot saved.")
    return redirect("crm:snapshot_detail", pk=snap.pk)


# ----- Report snapshots -----------------------------------------------------
@login_required
def snapshot_detail(request, pk):
    snap = get_object_or_404(
        ReportSnapshot.objects.select_related("report", "generated_by"), pk=pk, tenant=request.tenant)
    return render(request, "crm/analytics/snapshot/detail.html", {"obj": snap})


@login_required
@require_POST
def snapshot_delete(request, pk):
    snap = get_object_or_404(ReportSnapshot, pk=pk, tenant=request.tenant)
    report_pk = snap.report_id
    write_audit_log(request.user, snap, "delete")
    snap.delete()
    messages.success(request, "Snapshot deleted.")
    return redirect("crm:report_detail", pk=report_pk)
