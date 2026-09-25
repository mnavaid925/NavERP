from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db.models import (
    CharField,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce

from django.utils import timezone

from apps.core.models import AuditLog
from apps.crm.models import CalendarEvent, CommunicationLog, CrmTask, Opportunity
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import OpportunityCompetitor
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome, WinLossReason
from apps.sales.models.OpportunityPipeline.Pipelines import OpportunityPipelinePlacement


SALES_HEALTH_CHOICES = [
    ("on_track", "On Track"),
    ("watch", "Watch"),
    ("at_risk", "At Risk"),
]
SALES_HEALTH_ACTIVITY_WINDOW_DAYS = 14
SALES_HEALTH_NEXT_STEP_SOON_DAYS = 3
SALES_HEALTH_CLOSE_SOON_DAYS = 3
SALES_HEALTH_STAGE_WATCH_RATIO = 0.75
SALES_HEALTH_ACTIVITY_MIN_STAGE_DAYS = 7
SALES_UNSPECIFIED_CURRENCY = "Unspecified"
SALES_UNSPECIFIED_CURRENCY_FILTER = "__unspecified__"


def _sales_guarded_id(value):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 < parsed <= 9223372036854775807 else None


def _sales_currency_expressions():
    try:
        Opportunity._meta.get_field("currency")
    except FieldDoesNotExist:
        return (
            Value(None, output_field=IntegerField()),
            Value(SALES_UNSPECIFIED_CURRENCY, output_field=CharField()),
        )
    return F("opportunity__currency_id"), F("opportunity__currency__code")


def _sales_placement_queryset(
    tenant,
    *,
    pipeline_id=None,
    owner_id=None,
    territory_id=None,
    currency=None,
):
    tenant_id = getattr(tenant, "pk", tenant)
    if tenant_id is None:
        return OpportunityPipelinePlacement.objects.none()
    queryset = OpportunityPipelinePlacement.objects.filter(tenant=tenant)
    pipeline_id = _sales_guarded_id(pipeline_id)
    owner_id = _sales_guarded_id(owner_id)
    territory_id = _sales_guarded_id(territory_id)
    if pipeline_id is not None:
        queryset = queryset.filter(pipeline_id=pipeline_id)
    if owner_id is not None:
        queryset = queryset.filter(opportunity__owner_id=owner_id)
    if territory_id is not None:
        queryset = queryset.filter(opportunity__territory_id=territory_id)
    if currency:
        if currency == SALES_UNSPECIFIED_CURRENCY_FILTER:
            queryset = queryset.filter(opportunity__currency__isnull=True)
        else:
            queryset = queryset.filter(opportunity__currency__code=str(currency).strip().upper())
    return queryset


def _sales_weighted_expression():
    probability = Coalesce(F("probability_override"), F("current_stage__probability"))
    return ExpressionWrapper(
        F("opportunity__amount") * probability / 100,
        output_field=DecimalField(max_digits=20, decimal_places=2),
    )


def _sales_rollup_stale_counts(queryset, as_of):
    fields = [
        "pipeline_id",
        "current_stage_id",
        "stage_entered_at",
        "current_stage__target_days",
    ]
    try:
        Opportunity._meta.get_field("currency")
    except FieldDoesNotExist:
        has_currency = False
    else:
        has_currency = True
        fields.append("opportunity__currency_id")
    counts = {}
    for row in queryset.values_list(*fields):
        pipeline_id, stage_id, stage_entered_at, target_days = row[:4]
        if target_days is None:
            continue
        stage_age_days = max(0, (as_of - stage_entered_at).days)
        if stage_age_days <= target_days:
            continue
        currency_id = row[4] if has_currency else None
        key = (pipeline_id, stage_id, currency_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def sales_pipeline_rollups(
    tenant,
    *,
    pipeline_id=None,
    owner_id=None,
    territory_id=None,
    currency=None,
    as_of=None,
):
    as_of = as_of or timezone.now()
    currency_id_expression, currency_code_expression = _sales_currency_expressions()
    queryset = _sales_placement_queryset(
        tenant,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
        territory_id=territory_id,
        currency=currency,
    )
    stale_counts = _sales_rollup_stale_counts(queryset, as_of)
    aggregate_rows = (
        queryset.values(
            "pipeline_id",
            "pipeline__name",
            "current_stage_id",
            "current_stage__name",
            "current_stage__sequence",
            "current_stage__stage_kind",
            currency_id=currency_id_expression,
            currency_code=currency_code_expression,
        )
        .annotate(
            count=Count("id"),
            amount=Sum("opportunity__amount"),
            weighted_amount=_sales_weighted_expression(),
        )
        .order_by(
            "pipeline_id",
            "current_stage__sequence",
            "currency_code",
        )
    )
    result = []
    for row in aggregate_rows:
        code = row["currency_code"] or SALES_UNSPECIFIED_CURRENCY
        stale_key = (row["pipeline_id"], row["current_stage_id"], row["currency_id"])
        result.append(
            {
                "pipeline_id": row["pipeline_id"],
                "pipeline_name": row["pipeline__name"],
                "stage_id": row["current_stage_id"],
                "stage_name": row["current_stage__name"],
                "sequence": row["current_stage__sequence"],
                "stage_sequence": row["current_stage__sequence"],
                "stage_kind": row["current_stage__stage_kind"],
                "currency_id": row["currency_id"],
                "currency_code": code,
                "currency_label": code,
                "count": row["count"] or 0,
                "stale_count": stale_counts.get(stale_key, 0),
                "amount": Decimal(row["amount"] or 0),
                "weighted_amount": Decimal(row["weighted_amount"] or 0),
            }
        )
    return result


def sales_pipeline_currency_totals(
    tenant,
    *,
    pipeline_id=None,
    owner_id=None,
    territory_id=None,
):
    currency_id_expression, currency_code_expression = _sales_currency_expressions()
    queryset = _sales_placement_queryset(
        tenant,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
        territory_id=territory_id,
    )
    rows = queryset.values(
        currency_id=currency_id_expression,
        currency_code=currency_code_expression,
    ).annotate(
        count=Count("id"),
        open_count=Count("id", filter=Q(current_stage__stage_kind="open")),
        won_count=Count("id", filter=Q(current_stage__stage_kind="won")),
        lost_count=Count("id", filter=Q(current_stage__stage_kind="lost")),
        amount=Sum("opportunity__amount"),
        won_amount=Sum(
            "opportunity__amount",
            filter=Q(current_stage__stage_kind="won"),
        ),
        weighted_amount=_sales_weighted_expression(),
    ).order_by("currency_code")
    result = []
    for row in rows:
        code = row["currency_code"] or SALES_UNSPECIFIED_CURRENCY
        result.append(
            {
                "currency_id": row["currency_id"],
                "currency_code": code,
                "currency_label": code,
                "filter_value": code if row["currency_id"] is not None else SALES_UNSPECIFIED_CURRENCY_FILTER,
                "count": row["count"] or 0,
                "open_count": row["open_count"] or 0,
                "won_count": row["won_count"] or 0,
                "lost_count": row["lost_count"] or 0,
                "amount": Decimal(row["amount"] or 0),
                "pipeline_amount": Decimal(row["amount"] or 0),
                "won_amount": Decimal(row["won_amount"] or 0),
                "weighted_amount": Decimal(row["weighted_amount"] or 0),
            }
        )
    return result


def sales_stage_age_rows(
    tenant,
    *,
    pipeline_id=None,
    owner_id=None,
    territory_id=None,
    currency=None,
    date_from=None,
    date_to=None,
    health=None,
    as_of=None,
):
    as_of = as_of or timezone.now()
    health = str(health or "").strip().lower()
    if health and health not in dict(SALES_HEALTH_CHOICES):
        health = ""
    queryset = _sales_placement_queryset(
        tenant,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
        territory_id=territory_id,
        currency=currency,
    ).select_related(
        "pipeline",
        "current_stage",
        "opportunity",
        "opportunity__owner",
        "opportunity__territory",
        "opportunity__account",
        "opportunity__currency",
    )
    if date_from is not None:
        queryset = queryset.filter(stage_entered_at__date__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(stage_entered_at__date__lte=date_to)
    placement_list = list(queryset)
    health_projection = {}
    if health:
        health_projection = opportunity_pipeline_health_projection(
            tenant,
            [placement.opportunity for placement in placement_list],
            placement_list,
            as_of=as_of,
        )
    rows = []
    for placement in placement_list:
        health_row = health_projection.get(placement.opportunity_id)
        if health and (health_row is None or health_row["status"] != health):
            continue
        age_seconds = max(0, int((as_of - placement.stage_entered_at).total_seconds()))
        stage_age_days = age_seconds // 86400
        target_days = placement.current_stage.target_days
        opportunity_currency = getattr(placement.opportunity, "currency", None)
        currency_code = opportunity_currency.code if opportunity_currency is not None else SALES_UNSPECIFIED_CURRENCY
        owner = placement.opportunity.owner
        territory = placement.opportunity.territory
        account = placement.opportunity.account
        rows.append(
            {
                "pipeline_id": placement.pipeline_id,
                "pipeline_name": placement.pipeline.name,
                "stage_id": placement.current_stage_id,
                "stage_name": placement.current_stage.name,
                "stage_kind": placement.current_stage.stage_kind,
                "opportunity_id": placement.opportunity_id,
                "opportunity_number": placement.opportunity.number,
                "opportunity_name": placement.opportunity.name,
                "account_name": account.name if account is not None else None,
                "owner_id": placement.opportunity.owner_id,
                "owner_name": (
                    owner.get_full_name() or owner.username
                    if owner is not None
                    else None
                ),
                "territory_id": placement.opportunity.territory_id,
                "territory_name": territory.name if territory is not None else None,
                "currency_id": getattr(placement.opportunity, "currency_id", None),
                "currency_code": currency_code,
                "currency_label": currency_code,
                "amount": Decimal(placement.opportunity.amount or 0),
                "effective_probability": placement.effective_probability,
                "weighted_amount": Decimal(placement.opportunity.amount or 0)
                * placement.effective_probability
                / 100,
                "stage_age_days": stage_age_days,
                "target_days": target_days,
                "is_stale": target_days is not None and stage_age_days > target_days,
                "stage_entered_at": placement.stage_entered_at,
                "close_date": placement.opportunity.close_date,
            }
        )
    return sorted(rows, key=lambda row: (-row["stage_age_days"], row["opportunity_number"]))


def _sales_add_health_factor(factors, key, label, severity, detail, date=None):
    factors.append(
        {
            "key": key,
            "label": label,
            "severity": severity,
            "detail": detail,
            "date": date.isoformat() if date is not None else None,
        }
    )


def opportunity_pipeline_health(
    opportunity,
    placement=None,
    *,
    now=None,
    last_activity_at=None,
):
    now = now or timezone.now()
    if last_activity_at is not None and last_activity_at > now:
        last_activity_at = None
    local_today = timezone.localtime(now).date()
    factors = []
    stage_entered_at = (
        placement.stage_entered_at
        if placement is not None
        else (opportunity.stage_changed_at or opportunity.created_at)
    ) or now
    stage_age_days = max(0, (now - stage_entered_at).days)
    target_days = placement.current_stage.target_days if placement is not None else None
    if opportunity.stage == "closed_won":
        _sales_add_health_factor(
            factors,
            "closed_won",
            "Closed won",
            "info",
            "The opportunity is closed won.",
            opportunity.close_date,
        )
        status = "on_track"
    elif opportunity.stage == "closed_lost":
        _sales_add_health_factor(
            factors,
            "closed_lost",
            "Closed lost",
            "info",
            "The opportunity is closed lost.",
            opportunity.close_date,
        )
        status = "on_track"
    else:
        close_date = opportunity.close_date
        if close_date is not None and close_date < local_today:
            _sales_add_health_factor(
                factors,
                "overdue_close_date",
                "Close date overdue",
                "at_risk",
                "The expected close date has passed.",
                close_date,
            )
        elif close_date is not None and (close_date - local_today).days <= SALES_HEALTH_CLOSE_SOON_DAYS:
            _sales_add_health_factor(
                factors,
                "close_date_soon",
                "Close date approaching",
                "watch",
                "The expected close date is approaching.",
                close_date,
            )
        elif close_date is None:
            _sales_add_health_factor(
                factors,
                "missing_close_date",
                "Close date missing",
                "watch",
                "Set a close date to make the forecast actionable.",
            )
        next_step = (opportunity.next_step or "").strip()
        next_step_due_date = getattr(opportunity, "next_step_due_date", None)
        if next_step_due_date is not None and next_step_due_date < local_today:
            _sales_add_health_factor(
                factors,
                "overdue_next_step",
                "Next step overdue",
                "at_risk",
                "The next-step due date has passed.",
                next_step_due_date,
            )
        elif next_step_due_date is not None and (next_step_due_date - local_today).days <= SALES_HEALTH_NEXT_STEP_SOON_DAYS:
            _sales_add_health_factor(
                factors,
                "next_step_due_soon",
                "Next step approaching",
                "watch",
                "The next-step due date is approaching.",
                next_step_due_date,
            )
        if not next_step or next_step_due_date is None:
            missing_parts = []
            if not next_step:
                missing_parts.append("text")
            if next_step_due_date is None:
                missing_parts.append("due date")
            _sales_add_health_factor(
                factors,
                "missing_next_step",
                "Next step incomplete",
                "watch",
                "Add the missing next-step " + " and ".join(missing_parts) + ".",
            )
        if target_days is not None:
            if stage_age_days > target_days:
                _sales_add_health_factor(
                    factors,
                    "stage_overdue",
                    "Stage target exceeded",
                    "at_risk",
                    "The opportunity has remained in this stage beyond its target.",
                )
            elif stage_age_days >= target_days * SALES_HEALTH_STAGE_WATCH_RATIO:
                _sales_add_health_factor(
                    factors,
                    "stage_aging",
                    "Stage age approaching target",
                    "watch",
                    "The opportunity is approaching its stage target.",
                )
        if stage_age_days >= SALES_HEALTH_ACTIVITY_MIN_STAGE_DAYS:
            if last_activity_at is None or (
                now - last_activity_at
            ).days > SALES_HEALTH_ACTIVITY_WINDOW_DAYS:
                _sales_add_health_factor(
                    factors,
                    "no_recent_activity",
                    "No recent activity",
                    "at_risk",
                    "No qualifying activity has been recorded recently.",
                )
        if opportunity.account_id is None:
            _sales_add_health_factor(
                factors,
                "missing_account",
                "Account missing",
                "watch",
                "Link the opportunity to an account.",
            )
        if opportunity.primary_contact_id is None:
            _sales_add_health_factor(
                factors,
                "missing_contact",
                "Primary contact missing",
                "watch",
                "Link a primary contact to the opportunity.",
            )
        if opportunity.owner_id is None:
            _sales_add_health_factor(
                factors,
                "missing_owner",
                "Owner missing",
                "watch",
                "Assign one accountable opportunity owner.",
            )
        if Decimal(opportunity.amount or 0) <= 0:
            _sales_add_health_factor(
                factors,
                "missing_amount",
                "Amount missing",
                "watch",
                "Set a positive opportunity amount.",
            )
        severities = {factor["severity"] for factor in factors}
        if "at_risk" in severities:
            status = "at_risk"
        elif "watch" in severities:
            status = "watch"
        else:
            status = "on_track"
    return {
        "status": status,
        "factors": factors,
        "stage_age_days": stage_age_days,
        "target_days": target_days,
        "last_activity_at": last_activity_at.isoformat() if last_activity_at is not None else None,
        "as_of": now.isoformat(),
    }


def _sales_latest_activity_by_opportunity(tenant, opportunity_ids, as_of):
    latest = {}
    task_rows = (
        CrmTask.objects.filter(tenant=tenant, related_opportunity_id__in=opportunity_ids, updated_at__lte=as_of)
        .values("related_opportunity_id")
        .annotate(latest=Max("updated_at"))
    )
    communication_rows = (
        CommunicationLog.objects.filter(
            tenant=tenant,
            related_opportunity_id__in=opportunity_ids,
            occurred_at__lte=as_of,
        )
        .values("related_opportunity_id")
        .annotate(latest=Max("occurred_at"))
    )
    calendar_rows = (
        CalendarEvent.objects.filter(
            tenant=tenant,
            related_opportunity_id__in=opportunity_ids,
            start__lte=as_of,
        )
        .values("related_opportunity_id")
        .annotate(latest=Max("start"))
    )
    content_type = ContentType.objects.get_for_model(Opportunity)
    audit_rows = (
        AuditLog.objects.filter(
            tenant=tenant,
            content_type=content_type,
            object_id__in=opportunity_ids,
            at__lte=as_of,
        )
        .values("object_id")
        .annotate(latest=Max("at"))
    )
    for rows in (task_rows, communication_rows, calendar_rows, audit_rows):
        for row in rows:
            opportunity_id = row.get("related_opportunity_id", row.get("object_id"))
            candidate = row["latest"]
            if candidate is not None and (
                opportunity_id not in latest or candidate > latest[opportunity_id]
            ):
                latest[opportunity_id] = candidate
    return latest


def opportunity_pipeline_health_projection(
    tenant,
    opportunities=None,
    placements=None,
    *,
    as_of=None,
):
    tenant_id = getattr(tenant, "pk", tenant)
    if tenant_id is None:
        return {}
    as_of = as_of or timezone.now()
    if opportunities is None:
        opportunity_queryset = Opportunity.objects.filter(tenant=tenant)
    else:
        opportunity_ids = [opportunity.pk for opportunity in opportunities]
        opportunity_queryset = Opportunity.objects.filter(
            tenant=tenant,
            pk__in=opportunity_ids,
        )
    opportunity_list = list(opportunity_queryset)
    opportunity_ids = [opportunity.pk for opportunity in opportunity_list]
    if not opportunity_ids:
        return {}
    if placements is None:
        placement_list = list(
            OpportunityPipelinePlacement.objects.filter(
                tenant=tenant,
                opportunity_id__in=opportunity_ids,
            ).select_related("current_stage")
        )
    else:
        placement_list = [
            placement
            for placement in placements
            if placement.tenant_id == tenant_id and placement.opportunity_id in opportunity_ids
        ]
    placement_by_opportunity = {
        placement.opportunity_id: placement for placement in placement_list
    }
    latest_activity = _sales_latest_activity_by_opportunity(tenant, opportunity_ids, as_of)
    projection = {}
    for opportunity in opportunity_list:
        health = opportunity_pipeline_health(
            opportunity,
            placement=placement_by_opportunity.get(opportunity.pk),
            now=as_of,
            last_activity_at=latest_activity.get(opportunity.pk),
        )
        projection[opportunity.pk] = {
            "opportunity_id": opportunity.pk,
            "status": health["status"],
            "health_status": health["status"],
            "factors": health["factors"],
            "stage_age_days": health["stage_age_days"],
            "target_days": health["target_days"],
            "last_activity_at": health["last_activity_at"],
            "as_of": health["as_of"],
        }
    return projection


def sales_health_counts(tenant, opportunities=None, placements=None, *, as_of=None):
    projection = opportunity_pipeline_health_projection(
        tenant,
        opportunities,
        placements,
        as_of=as_of,
    )
    counts = {"on_track": 0, "watch": 0, "at_risk": 0}
    for health in projection.values():
        counts[health["status"]] += 1
    return counts


def _sales_outcome_currency_filter(queryset, currency):
    if not currency:
        return queryset
    try:
        Opportunity._meta.get_field("currency")
    except FieldDoesNotExist:
        if currency in {SALES_UNSPECIFIED_CURRENCY_FILTER, SALES_UNSPECIFIED_CURRENCY}:
            return queryset
        return queryset.none()
    if currency in {SALES_UNSPECIFIED_CURRENCY_FILTER, SALES_UNSPECIFIED_CURRENCY}:
        return queryset.filter(opportunity__currency__isnull=True)
    code = getattr(currency, "code", currency)
    return queryset.filter(opportunity__currency__code=str(code).strip().upper())


def _sales_outcome_queryset(
    tenant,
    *,
    pipeline_id=None,
    owner_id=None,
    territory_id=None,
    currency=None,
    date_from=None,
    date_to=None,
):
    tenant_id = getattr(tenant, "pk", tenant)
    if tenant_id is None:
        return OpportunityOutcome.objects.none()
    queryset = OpportunityOutcome.objects.filter(tenant_id=tenant_id)
    pipeline_id = _sales_guarded_id(pipeline_id)
    owner_id = _sales_guarded_id(owner_id)
    territory_id = _sales_guarded_id(territory_id)
    if pipeline_id is not None:
        queryset = queryset.filter(
            opportunity__sales_pipeline_placement__pipeline_id=pipeline_id,
        )
    if owner_id is not None:
        queryset = queryset.filter(opportunity__owner_id=owner_id)
    if territory_id is not None:
        queryset = queryset.filter(opportunity__territory_id=territory_id)
    if date_from is not None:
        queryset = queryset.filter(closed_at__date__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(closed_at__date__lte=date_to)
    return _sales_outcome_currency_filter(queryset, currency)


def sales_win_loss_rows(
    tenant,
    pipeline_id=None,
    owner_id=None,
    territory_id=None,
    currency=None,
    date_from=None,
    date_to=None,
):
    currency_id_expression, currency_code_expression = _sales_currency_expressions()
    queryset = _sales_outcome_queryset(
        tenant,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
        territory_id=territory_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    grouped = queryset.values(
        "result",
        "reason_id",
        "reason__code",
        "reason__name",
        "reason__category",
        "reason__sequence",
        "opportunity__sales_pipeline_placement__pipeline_id",
        "opportunity__sales_pipeline_placement__pipeline__name",
        currency_id=currency_id_expression,
        currency_code=currency_code_expression,
    ).annotate(
        count=Count("id"),
        amount=Sum("opportunity__amount"),
        first_closed_at=Min("closed_at"),
        last_closed_at=Max("closed_at"),
    ).order_by()
    result_labels = dict(OpportunityOutcome.RESULT_CHOICES)
    category_labels = dict(WinLossReason.CATEGORY_CHOICES)
    rows = []
    for row in grouped:
        currency_code = row["currency_code"]
        category = row["reason__category"]
        rows.append(
            {
                "result": row["result"],
                "result_label": result_labels.get(row["result"]),
                "reason_id": row["reason_id"],
                "reason_code": row["reason__code"],
                "reason_name": row["reason__name"],
                "reason_category": category,
                "category": category,
                "category_label": category_labels.get(category),
                "reason_sequence": row["reason__sequence"],
                "pipeline_id": row["opportunity__sales_pipeline_placement__pipeline_id"],
                "pipeline_name": row["opportunity__sales_pipeline_placement__pipeline__name"],
                "currency_id": row["currency_id"],
                "currency_code": currency_code,
                "currency_label": currency_code or SALES_UNSPECIFIED_CURRENCY,
                "currency_filter_value": currency_code if currency_code is not None else SALES_UNSPECIFIED_CURRENCY_FILTER,
                "count": row["count"] or 0,
                "outcome_count": row["count"] or 0,
                "amount": Decimal(row["amount"] or 0),
                "total_amount": Decimal(row["amount"] or 0),
                "first_closed_at": row["first_closed_at"],
                "last_closed_at": row["last_closed_at"],
            }
        )
    rows.sort(
        key=lambda row: (
            row["result"] or "",
            row["reason_sequence"] if row["reason_sequence"] is not None else 2147483647,
            row["reason_code"] or "",
            row["currency_code"] or "",
            row["pipeline_name"] or "",
        )
    )
    return rows


def sales_competitor_rows(
    tenant,
    pipeline_id=None,
    owner_id=None,
    territory_id=None,
    currency=None,
    date_from=None,
    date_to=None,
):
    currency_id_expression, currency_code_expression = _sales_currency_expressions()
    queryset = _sales_outcome_queryset(
        tenant,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
        territory_id=territory_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    grouped = queryset.values(
        "result",
        "competitor_link__relationship",
        "competitor_link__competitor_profile_id",
        "competitor_link__competitor_profile__party_id",
        "competitor_link__competitor_profile__party__name",
        "opportunity__sales_pipeline_placement__pipeline_id",
        "opportunity__sales_pipeline_placement__pipeline__name",
        currency_id=currency_id_expression,
        currency_code=currency_code_expression,
    ).annotate(
        count=Count("id"),
        competitor_link_count=Count("competitor_link_id", distinct=True),
        amount=Sum("opportunity__amount"),
        first_closed_at=Min("closed_at"),
        last_closed_at=Max("closed_at"),
    ).order_by()
    result_labels = dict(OpportunityOutcome.RESULT_CHOICES)
    relationship_labels = dict(OpportunityCompetitor.RELATIONSHIP_CHOICES)
    rows = []
    for row in grouped:
        currency_code = row["currency_code"]
        competitor_name = row["competitor_link__competitor_profile__party__name"]
        relationship = row["competitor_link__relationship"]
        rows.append(
            {
                "result": row["result"],
                "result_label": result_labels.get(row["result"]),
                "competitor_link_count": row["competitor_link_count"] or 0,
                "competitor_id": row["competitor_link__competitor_profile_id"],
                "competitor_profile_id": row["competitor_link__competitor_profile_id"],
                "competitor_party_id": row["competitor_link__competitor_profile__party_id"],
                "competitor_name": competitor_name,
                "competitor": competitor_name,
                "relationship": relationship,
                "relationship_label": relationship_labels.get(relationship),
                "pipeline_id": row["opportunity__sales_pipeline_placement__pipeline_id"],
                "pipeline_name": row["opportunity__sales_pipeline_placement__pipeline__name"],
                "currency_id": row["currency_id"],
                "currency_code": currency_code,
                "currency_label": currency_code or SALES_UNSPECIFIED_CURRENCY,
                "currency_filter_value": currency_code if currency_code is not None else SALES_UNSPECIFIED_CURRENCY_FILTER,
                "count": row["count"] or 0,
                "outcome_count": row["count"] or 0,
                "amount": Decimal(row["amount"] or 0),
                "total_amount": Decimal(row["amount"] or 0),
                "first_closed_at": row["first_closed_at"],
                "last_closed_at": row["last_closed_at"],
            }
        )
    rows.sort(
        key=lambda row: (
            row["competitor_name"] or "",
            row["relationship"] or "",
            row["result"] or "",
            row["currency_code"] or "",
            row["pipeline_name"] or "",
        )
    )
    return rows
