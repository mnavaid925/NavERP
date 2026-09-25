from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from apps.core.crud import as_db_int, apply_search
from apps.core.models import Activity, ContactMethod, Document, Party
from apps.crm.models import (
    AccountProfile,
    CalendarEvent,
    CommunicationLog,
    ContactProfile,
    HealthScore,
    HealthScoreHistory,
    Opportunity,
)
from apps.accounting.models import Invoice
from apps.scm.models import SalesOrder
from apps.sales.models.ContactAccountManagement.AccountClassifications import AccountClassification
from apps.sales.models.ContactAccountManagement.AccountPlans import AccountPlan
from apps.sales.models.ContactAccountManagement.AccountStakeholders import AccountStakeholder
from apps.sales.models.ContactAccountManagement.PartyEnrichment import PartyEnrichmentEvent
from apps.sales.services import account_coverage_data, account_hierarchy_rows, account_rollups
from apps.sales.views._common import *

MAX_BOARD_ACCOUNTS = 500


def _tenant_accounts(request):
    if request.tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")


def _descendant_ids(rows, root_id):
    children = {}
    row_ids = {row["party"].pk for row in rows}
    for row in rows:
        parent_id = row["profile"].parent_account_id
        children.setdefault(parent_id, []).append(row["party"].pk)
    if root_id not in row_ids:
        return set()
    found = set()
    pending = [root_id]
    steps = 0
    while pending:
        steps += 1
        if steps > max(len(rows) * 2, 1):
            break
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(children.get(current, []))
    return found


@login_required
def account_hierarchy(request):
    all_rows = account_hierarchy_rows(request.tenant) if request.tenant is not None else []
    rows = list(all_rows)
    q = request.GET.get("q", "").strip()
    if q:
        rows = [row for row in rows if q.casefold() in row["party"].name.casefold()]
    view_mode = request.GET.get("view_mode", "tree")
    if view_mode not in {"tree", "roots", "leaves", "parent", "descendants"}:
        view_mode = "tree"
    root_id = as_db_int(request.GET.get("root"))
    parent_id = as_db_int(request.GET.get("parent"))
    selected = next((row for row in all_rows if row["party"].pk in {root_id, parent_id}), None)
    if view_mode == "roots":
        rows = [row for row in rows if row["is_root"]]
    elif view_mode == "leaves":
        rows = [row for row in rows if row["is_leaf"]]
    elif view_mode == "parent" and parent_id:
        rows = [row for row in rows if row["profile"].parent_account_id == parent_id]
    elif view_mode == "descendants" and root_id:
        ids = _descendant_ids(all_rows, root_id)
        rows = [row for row in rows if row["party"].pk in ids]
    rollup_rows = [
        {
            "account": row["party"],
            "profile": row["profile"],
            "rollup": row["rollup"],
            "rollup_available": row["rollup_available"],
            "descendant_count": row["descendant_count"],
        }
        for row in all_rows
    ]
    currency_rollups = {}
    root_rows = [row for row in all_rows if row["is_root"] and row["rollup_available"]]
    for row in root_rows:
        for currency, values in row["rollup"].get("currencies", {}).items():
            target = currency_rollups.setdefault(
                currency,
                {"opportunity": Decimal("0"), "weighted": Decimal("0"), "orders": Decimal("0"), "invoices": Decimal("0")},
            )
            for field_name, amount in values.items():
                target[field_name] += amount
    stats = {
        "total": len(all_rows),
        "roots": sum(1 for row in all_rows if row["is_root"]),
        "leaves": sum(1 for row in all_rows if row["is_leaf"]),
        "cycles": sum(1 for row in all_rows if row["cycle_detected"]),
    }
    return render(request, "sales/contactaccountmanagement/account_hierarchy.html", {
        "accounts": [row["party"] for row in rows],
        "account_rows": rows,
        "roots": [row["party"] for row in all_rows if row["is_root"]],
        "selected_account": selected["party"] if selected else None,
        "view_mode": view_mode,
        "view_mode_choices": [("tree", "Full hierarchy"), ("roots", "Roots"), ("leaves", "Leaves"), ("parent", "Direct children"), ("descendants", "All descendants")],
        "q": q,
        "root_id": root_id or "",
        "parent_id": parent_id or "",
        "rollup_rows": rollup_rows,
        "stats": stats,
        "currency_rollups": currency_rollups,
        "caveats": [
            "Hierarchy visibility does not grant access to related records.",
            "Commercial values remain separated by verified currency.",
            f"The hierarchy board shows at most {MAX_BOARD_ACCOUNTS} tenant accounts.",
        ],
    })


def _workspace_context(request, account):
    from apps.crm.models import CrmTask

    profile = AccountProfile.objects.filter(
        tenant=request.tenant,
        party=account,
        party__tenant=request.tenant,
        party__kind="organization",
    ).first()
    classification = AccountClassification.objects.filter(tenant=request.tenant, account=account).select_related("account", "classified_by").first()
    stakeholders = list(AccountStakeholder.objects.filter(tenant=request.tenant, account=account).select_related("contact").order_by("contact__name", "role")[:500])
    primary_contacts = list(
        ContactProfile.objects.filter(
            tenant=request.tenant,
            party__tenant=request.tenant,
            party__kind="person",
            account=account,
            account__tenant=request.tenant,
            account__kind="organization",
        ).select_related("party", "owner")[:500]
    )
    plans = list(AccountPlan.objects.filter(tenant=request.tenant, account=account).only("id", "number", "title", "status", "period_start", "period_end", "account_id", "created_at").order_by("-period_start", "-created_at")[:20])
    opportunities = list(
        Opportunity.objects.filter(
            tenant=request.tenant,
            account=account,
            account__tenant=request.tenant,
            account__kind="organization",
        ).only("id", "number", "name", "stage", "amount", "close_date", "account_id", "created_at").order_by("-created_at")[:20]
    )
    orders = list(
        SalesOrder.objects.filter(
            tenant=request.tenant,
            customer=account,
            customer__tenant=request.tenant,
            customer__kind="organization",
        ).select_related("currency").only("id", "number", "status", "total", "currency_id", "order_date", "customer_id", "created_at").order_by("-created_at")[:20]
    )
    invoices = list(
        Invoice.objects.filter(
            tenant=request.tenant,
            party=account,
            party__tenant=request.tenant,
            party__kind="organization",
        ).select_related("currency").only("id", "number", "status", "total", "currency_id", "issue_date", "party_id").order_by("-issue_date")[:20]
    )
    health = HealthScore.objects.filter(tenant=request.tenant, account=account).order_by("-computed_at", "-id").first()
    health_history = list(HealthScoreHistory.objects.filter(tenant=request.tenant, account=account).only("id", "account_id", "score", "tier", "computed_at").order_by("-computed_at")[:10])
    tasks = list(CrmTask.objects.filter(tenant=request.tenant, party=account, status__in=["open", "in_progress"]).only("id", "subject", "status", "due_date", "party_id").order_by("due_date", "-created_at")[:20])
    activities = []
    latest_communication = None
    for item in Activity.objects.filter(tenant=request.tenant, party=account).only("id", "kind", "subject", "created_at", "party_id").order_by("-created_at")[:20]:
        activities.append({"kind": item.get_kind_display(), "subject": item.subject, "at": item.created_at})
    for item in CommunicationLog.objects.filter(tenant=request.tenant, party=account).only("id", "channel", "subject", "outcome", "occurred_at", "party_id").order_by("-occurred_at")[:20]:
        if latest_communication is None:
            latest_communication = item
        activities.append({"kind": item.get_channel_display(), "subject": item.subject or item.get_outcome_display(), "at": item.occurred_at})
    for item in CalendarEvent.objects.filter(tenant=request.tenant, party=account).only("id", "event_type", "title", "start", "party_id").order_by("-start")[:20]:
        activities.append({"kind": item.get_event_type_display(), "subject": item.title, "at": item.start})
    activities.sort(key=lambda value: value["at"], reverse=True)
    document_filter = Q(content_type=ContentType.objects.get_for_model(Party), object_id=account.pk)
    if profile is not None:
        document_filter |= Q(content_type=ContentType.objects.get_for_model(AccountProfile), object_id=profile.pk)
    documents = list(Document.objects.filter(tenant=request.tenant).filter(document_filter).order_by("-uploaded_at")[:20])
    coverage = account_coverage_data(request.tenant, account)
    rollups = account_rollups(request.tenant, [account.pk]).get(account.pk, {})
    enrichment = list(PartyEnrichmentEvent.objects.filter(tenant=request.tenant, party=account).only("id", "kind", "status", "source_name", "occurred_at", "party_id").order_by("-occurred_at")[:10])
    return {
        "account": account,
        "profile": profile,
        "classification": classification,
        "stakeholders": stakeholders,
        "primary_contacts": primary_contacts,
        "plans": plans,
        "opportunities": opportunities,
        "orders": orders,
        "invoices": invoices,
        "health": health,
        "health_history": health_history,
        "activities": activities[:50],
        "tasks": tasks,
        "documents": documents,
        "coverage": coverage,
        "interaction_recency": latest_communication,
        "currency_rollups": rollups.get("currencies", {}),
        "opportunity_rollups": rollups,
        "realized_rollups": rollups,
        "enrichment_events": enrichment,
        "white_space_note": "Exact product white-space is incomplete until CRM Product and SCM Item have a governed mapping.",
        "caveats": ["Account and contact identity/profile edits remain in CRM.", "Health is the current CRM HealthScore, not a Sales classification.", "Task and activity panels are recent evidence, not complete account history."],
    }


def _workspace_account(request):
    raw_account = (request.GET.get("account") or "").strip()
    if not raw_account:
        return _tenant_accounts(request).first()
    account_id = as_db_int(raw_account)
    if account_id is None:
        raise Http404
    return get_object_or_404(_tenant_accounts(request), pk=account_id)


@login_required
def account_workspace(request):
    account = _workspace_account(request)
    if account is None:
        messages.info(request, "Create a CRM account profile to open an account workspace.")
        return redirect("sales:account_hierarchy")
    context = _workspace_context(request, account)
    return render(request, "sales/contactaccountmanagement/account_workspace.html", context)


@login_required
def account_coverage(request):
    q = request.GET.get("q", "").strip()
    account_id = as_db_int(request.GET.get("account"))
    if request.GET.get("account") and (account_id is None or account_id <= 0):
        raise Http404
    role = request.GET.get("role", "")
    status = request.GET.get("status", "active")
    if role not in dict(AccountStakeholder.ROLE_CHOICES):
        role = ""
    if status not in dict(AccountStakeholder.STATUS_CHOICES):
        status = "active"
    accounts_queryset = apply_search(_tenant_accounts(request), q, ["name"])
    if account_id:
        if not accounts_queryset.filter(pk=account_id).exists():
            raise Http404
        accounts_queryset = accounts_queryset.filter(pk=account_id)
    accounts = list(accounts_queryset[:MAX_BOARD_ACCOUNTS])
    account_ids = [account.pk for account in accounts]
    primary_counts = {
        row["account_id"]: row["count"]
        for row in ContactProfile.objects.filter(
            tenant=request.tenant,
            party__tenant=request.tenant,
            party__kind="person",
            account_id__in=account_ids,
            account__tenant=request.tenant,
            account__kind="organization",
        )
        .values("account_id")
        .annotate(count=Count("pk"))
    }
    stakeholder_queryset = AccountStakeholder.objects.filter(
        tenant=request.tenant,
        account_id__in=account_ids,
        account__tenant=request.tenant,
        account__kind="organization",
        contact__tenant=request.tenant,
        contact__kind="person",
        status=status,
    )
    if role:
        stakeholder_queryset = stakeholder_queryset.filter(role=role)
    role_rows = list(
        stakeholder_queryset.values("account_id", "role")
        .annotate(count=Count("pk"))
        .order_by("account_id", "role")
    )
    role_map = {}
    stakeholder_counts = {}
    for row in role_rows:
        role_map.setdefault(row["account_id"], []).append(
            {"value": row["role"], "label": dict(AccountStakeholder.ROLE_CHOICES).get(row["role"], row["role"]), "count": row["count"]}
        )
        stakeholder_counts[row["account_id"]] = stakeholder_counts.get(row["account_id"], 0) + row["count"]
    rows = []
    for account in accounts:
        roles = role_map.get(account.pk, [])
        if role and not roles:
            continue
        role_values = {entry["value"] for entry in roles}
        primary_count = primary_counts.get(account.pk, 0)
        covered = bool(role_values) if status == "active" else False
        if status == "active" and primary_count and not role_values:
            coverage_label = "Primary affiliation"
            coverage_class = "badge-info"
        elif covered:
            coverage_label = "Covered"
            coverage_class = "badge-green"
        elif status == "former" and role_values:
            coverage_label = "Former relationship"
            coverage_class = "badge-muted"
        else:
            coverage_label = "Needs mapping"
            coverage_class = "badge-amber"
        rows.append({
            "account": account,
            "roles": roles,
            "role_values": role_values,
            "primary_count": primary_count,
            "stakeholder_count": stakeholder_counts.get(account.pk, 0),
            "covered": covered,
            "coverage_label": coverage_label,
            "coverage_class": coverage_class,
        })
    stats = {
        "accounts": len(rows),
        "with_decision_maker": sum(1 for row in rows if row["covered"] and "decision_maker" in row["role_values"]),
        "with_champion": sum(1 for row in rows if row["covered"] and "champion" in row["role_values"]),
        "with_blocker": sum(1 for row in rows if row["covered"] and "blocker" in row["role_values"]),
    }
    return render(request, "sales/contactaccountmanagement/account_coverage.html", {
        "coverage_rows": rows,
        "accounts": list(_tenant_accounts(request)[:MAX_BOARD_ACCOUNTS]),
        "role_choices": AccountStakeholder.ROLE_CHOICES,
        "status_choices": AccountStakeholder.STATUS_CHOICES,
        "q": q,
        "account_id": account_id or "",
        "role": role,
        "status": status,
        "stats": stats,
        "caveats": ["Coverage is derived from account-specific stakeholder rows and CRM primary affiliations.", "Former relationships are shown as evidence but do not count as active coverage.", "Interaction recency is available in the account workspace and is not a verified influence score."],
    })


@login_required
def account_white_space(request):
    from django.db.models import Prefetch

    q = request.GET.get("q", "").strip()
    account_id = as_db_int(request.GET.get("account"))
    if request.GET.get("account") and (account_id is None or account_id <= 0):
        raise Http404
    if account_id and not _tenant_accounts(request).filter(pk=account_id).exists():
        raise Http404
    tier = request.GET.get("tier", "")
    lifecycle_stage = request.GET.get("lifecycle_stage", "")
    review_due = request.GET.get("review_due", "")
    if tier not in dict(AccountClassification.TIER_CHOICES):
        tier = ""
    if lifecycle_stage not in dict(AccountClassification.LIFECYCLE_STAGE_CHOICES):
        lifecycle_stage = ""
    if review_due not in {"overdue", "due_soon", "scheduled"}:
        review_due = ""
    today = timezone.localdate()
    classifications = AccountClassification.objects.filter(
        tenant=request.tenant,
        account__tenant=request.tenant,
        account__kind="organization",
    ).select_related("account")
    if q:
        classifications = classifications.filter(Q(account__name__icontains=q) | Q(rationale__icontains=q))
    if account_id:
        classifications = classifications.filter(account_id=account_id)
    if tier in dict(AccountClassification.TIER_CHOICES):
        classifications = classifications.filter(tier=tier)
    if lifecycle_stage in dict(AccountClassification.LIFECYCLE_STAGE_CHOICES):
        classifications = classifications.filter(lifecycle_stage=lifecycle_stage)
    if review_due == "overdue":
        classifications = classifications.filter(review_due_on__lt=today)
    elif review_due == "due_soon":
        classifications = classifications.filter(
            review_due_on__gte=today,
            review_due_on__lte=today + timedelta(days=30),
        )
    elif review_due == "scheduled":
        classifications = classifications.filter(review_due_on__isnull=False)
    classification_rows = list(classifications[:MAX_BOARD_ACCOUNTS])
    account_ids = [row.account_id for row in classification_rows]
    plan_queryset = AccountPlan.objects.filter(
        tenant=request.tenant,
        account_id__in=account_ids,
        account__tenant=request.tenant,
        account__kind="organization",
    ).select_related(
        "account", "owner"
    ).prefetch_related(
        Prefetch(
            "related_opportunities",
            queryset=Opportunity.objects.filter(tenant=request.tenant).only("number", "tenant_id", "account_id"),
            to_attr="safe_related_opportunities",
        )
    ).order_by("-period_start", "-created_at")[:1500]
    for plan in plan_queryset:
        plan.safe_related_opportunities = [
            opportunity
            for opportunity in plan.safe_related_opportunities
            if opportunity.tenant_id == request.tenant.pk
            and opportunity.account_id == plan.account_id
        ]
    plans_by_account = {}
    for plan in plan_queryset:
        plans_by_account.setdefault(plan.account_id, []).append(plan)
    opportunity_counts = {
        row["account_id"]: row["count"]
        for row in Opportunity.objects.filter(
            tenant=request.tenant,
            account_id__in=account_ids,
            account__tenant=request.tenant,
            account__kind="organization",
        )
        .values("account_id")
        .annotate(count=Count("pk"))
    }
    rows = [
        {
            "classification": classification,
            "account": classification.account,
            "plans": plans_by_account.get(classification.account_id, []),
            "plan_count": len(plans_by_account.get(classification.account_id, [])),
            "opportunity_count": opportunity_counts.get(classification.account_id, 0),
        }
        for classification in classification_rows
    ]
    return render(request, "sales/contactaccountmanagement/account_white_space.html", {
        "white_space_rows": rows,
        "accounts": list(_tenant_accounts(request)[:MAX_BOARD_ACCOUNTS]),
        "tier_choices": AccountClassification.TIER_CHOICES,
        "lifecycle_stage_choices": AccountClassification.LIFECYCLE_STAGE_CHOICES,
        "q": q,
        "account_id": account_id or "",
        "tier": tier,
        "lifecycle_stage": lifecycle_stage,
        "review_due": review_due,
        "product_mapping_note": "CRM Product and SCM Item do not yet have a governed mapping; this board does not claim complete product-level white-space.",
        "stats": {"accounts": len(rows), "with_plans": sum(1 for row in rows if row["plan_count"]), "with_opportunities": sum(1 for row in rows if row["opportunity_count"])},
        "caveats": ["White-space is a qualitative plan assessment until product mapping is governed.", "Plan evidence is capped at the 1,500 newest rows across this board.", "No dynamic segment rules or generated plans are executed."],
    })


@login_required
def account_workspace_export(request):
    account = _workspace_account(request)
    if account is None:
        return HttpResponse(status=404)
    classification = AccountClassification.objects.filter(tenant=request.tenant, account=account).first()
    health = HealthScore.objects.filter(tenant=request.tenant, account=account).order_by("-computed_at", "-id").first()
    rollups = account_rollups(request.tenant, [account.pk]).get(account.pk, {"currencies": {}})
    currencies = rollups.get("currencies", {}) or {
        "unspecified": {"opportunity": Decimal("0"), "weighted": Decimal("0"), "orders": Decimal("0"), "invoices": Decimal("0")}
    }
    rows = (
        (
            account.name,
            classification.get_tier_display() if classification else "Unclassified",
            classification.get_lifecycle_stage_display() if classification else "Unavailable",
            health.score if health else "Unavailable",
            currency,
            values.get("opportunity", Decimal("0")),
            values.get("weighted", Decimal("0")),
            values.get("orders", Decimal("0")),
            values.get("invoices", Decimal("0")),
        )
        for currency, values in currencies.items()
    )
    return csv_export_response(
        request,
        filename=f"account-{account.pk}-workspace.csv",
        dataset="account_workspace",
        headers=["Account", "Tier", "Lifecycle", "Health score", "Currency", "Open opportunities", "Weighted pipeline", "Orders", "Invoices"],
        rows=rows,
        filters={"account": account.pk},
    )
