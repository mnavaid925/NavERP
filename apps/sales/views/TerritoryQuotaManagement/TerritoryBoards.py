"""Sales 8.7 — the four derived, READ-ONLY territory boards.

Each board is a pure function of tables that already have owners: ``crm.Territory`` /
``crm.SalesQuota`` (CRM 1.2), ``core.Party`` / ``crm.AccountProfile`` / ``crm.Opportunity``
(CRM core), ``sales.AccountClassification`` / ``sales.ForecastPeriod`` (8.3 / 8.4) and 8.7's own
four tables. No board owns a table, a seeder row or an admin registration, and **no board writes**:
``territory_rebalance_preview`` is the dry run, and the commit verb is ``territory_rule_run`` in the
sibling ``TerritoryRules`` module.

**THE MONEY RULE (contract §10.5).** Every money and percentage figure below is ``Decimal`` computed
in PYTHON over a fetched set — never ``Sum()``, never ``F()``, never a DB-side division, never a
float. The board queries are exactly where the temptation appears, because an aggregate queryset is
one line and a Python loop is ten; the SQLite integer-division trap **silently drops fractional cents
rather than raising**, so an aggregate board is not a slow board, it is a WRONG one that renders.

**THE RULE ENGINE (contract §7).** This module evaluates an 8.7 rule against an account, which is
two jobs and no more: build the ACCOUNT-side value map over the entities the evaluator actually
reads, and compose the conditions with the operator evaluator 8.1's routing engine already ships —
``apps.sales.services._condition_matches`` — in the same ``all`` / ``any`` shape as its
``_rule_matches``. It is a sibling of that engine, never a second copy of it. The vocabulary is the
model's own closed allow-list (``TerritoryRule``'s ``TERRITORY_FIELDS``); no field outside it is
ever produced here.

The evaluator, its value map and the assignment picture live here rather than in a sixth helper
module because two modules in THIS sub-module need them (``TerritoryBoards`` and the run verb in
``TerritoryRules``), and the rule entity is the natural owner of the semantics.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.crud import as_db_int
from apps.core.models import Party
from apps.crm.models import AccountProfile, Opportunity, SalesQuota, Territory
from apps.sales.models.ContactAccountManagement.AccountClassifications import AccountClassification
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignment,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryMembers import TerritoryMember
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import TerritoryRule
# The ONE operator evaluator, imported from 8.1's engine. Writing a second one here is the single
# most likely way 8.7 forks 8.1, which the contract names as its biggest non-goal (§1 item 8).
from apps.sales.services import _condition_matches
from apps.sales.views._common import *
from apps.sales.views._helpers import is_tenant_admin

#: As-built precedents, reused rather than re-invented: `AccountBoards.py:30` MAX_BOARD_ACCOUNTS =
#: 500, `ForecastBoards.py:62-63` MAX_PERIODS = 200 and MAX_ROWS = 200 (contract §17 item 5).
MAX_BOARD_ACCOUNTS = 500
MAX_ROWS = 200
MAX_PERIODS = 200

#: How many active SECONDARY + OVERLAY alignments one account may carry. The coverage-gap board
#: reports "over the cap"; the plan pinned the cap's EXISTENCE, not its number, so this is the
#: build-time choice and it is written down here rather than buried in the query.
MAX_ACTIVE_AUXILIARY_ALIGNMENTS = 2

HUNDRED = Decimal("100")
ZERO = Decimal("0")
CENTS = Decimal("0.01")
TENTH = Decimal("0.1")


# =============================================================================
# ===== Decimal helpers — every figure on every board goes through these ====
# =============================================================================


def _pct(numerator, denominator):
    """``numerator / denominator`` as a 0-100 ``Decimal``, or ``None`` when the denominator is zero.

    ``None``, never ``0``: a quota of zero is a missing denominator, and printing ``0%`` for it
    asserts an attainment the board did not measure.
    """
    if not denominator:
        return None
    return (Decimal(numerator) * HUNDRED / Decimal(denominator)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _money(value):
    """A money figure as a 2-dp ``Decimal``. ``ROUND_HALF_UP`` so a half cent rounds UP, not to
    even and not toward zero — the same direction ``TerritoryMember._check_split_sums`` reports."""
    return Decimal(value or ZERO).quantize(CENTS, rounding=ROUND_HALF_UP)


# =============================================================================
# ===== The shared read helpers                                                 =
# =============================================================================


def tenant_territories(tenant, active_only=True):
    """Same-tenant ``crm.Territory``, READ. 8.7 never writes a territory (contract §0.3)."""
    if tenant is None:
        return Territory.objects.none()
    queryset = Territory.objects.filter(tenant=tenant)
    return queryset.filter(is_active=True) if active_only else queryset


def _tenant_organizations(tenant, q=""):
    """Same-tenant organization accounts, bounded. Organizations only: a person is not assignable
    to a territory, which the assignment model enforces as well as the dropdown."""
    if tenant is None:
        return Party.objects.none()
    queryset = Party.objects.filter(tenant=tenant, kind="organization")
    if q:
        queryset = queryset.filter(name__icontains=q)
    return queryset.order_by("name")


def _period_label(period):
    number = period.get_period_number_display() if hasattr(period, "get_period_number_display") else period.period_number
    return f"{period.get_period_type_display()} {period.period_year} · {number}"


# =============================================================================
# ===== The rule evaluator — a SIBLING of 8.1's engine, never a second copy   ==
# =============================================================================


def _build_account_profile_map(tenant, account_ids):
    if not account_ids or tenant is None:
        return {}
    return {
        profile.party_id: profile
        for profile in AccountProfile.objects.filter(tenant=tenant, party_id__in=account_ids)
    }


def _build_account_classification_map(tenant, account_ids):
    if not account_ids or tenant is None:
        return {}
    return {
        classification.account_id: classification
        for classification in AccountClassification.objects.filter(
            tenant=tenant, account_id__in=account_ids
        )
    }


def account_territory_values(tenant, accounts, profiles=None, classifications=None):
    """The ACCOUNT-side value map for ``TERRITORY_FIELDS``, over a fetched set of accounts.

    Built once per board and reused for every rule, because the map costs one query per source and
    the rules are many. ``Decimal`` / ``int`` / ``bool`` / ``str`` throughout — never a float, which
    would lose cents before ``_condition_matches`` ever saw them.

    Sources, per the model's own allow-list: ``crm.AccountProfile`` (industry, annual_revenue,
    employee_count, address_country / _city / _state / _postal), ``sales.AccountClassification``
    (tier, lifecycle_stage), a ``crm.Opportunity`` open-deal probe, ``core.Party.name``, and the
    ``is_named_account`` flag read off the live ledger.
    """
    account_ids = [account.pk for account in accounts]
    if not account_ids:
        return {}
    if profiles is None:
        profiles = _build_account_profile_map(tenant, account_ids)
    if classifications is None:
        classifications = _build_account_classification_map(tenant, account_ids)
    open_ids = set(
        Opportunity.objects.filter(
            tenant=tenant, account_id__in=account_ids, stage__in=Opportunity.OPEN_STAGES
        ).values_list("account_id", flat=True)
    )
    named_ids = set(
        AccountTerritoryAssignment.objects.filter(
            tenant=tenant,
            account_id__in=account_ids,
            assignment_source="named_account",
            effective_to__isnull=True,
        ).values_list("account_id", flat=True)
    )
    values = {}
    for account in accounts:
        profile = profiles.get(account.pk)
        classification = classifications.get(account.pk)
        values[account.pk] = {
            "industry": profile.industry if profile else "",
            "annual_revenue": profile.annual_revenue if profile else ZERO,
            "employee_count": profile.employee_count if profile else 0,
            "country": profile.address_country if profile else "",
            "city": profile.address_city if profile else "",
            "state": profile.address_state if profile else "",
            "postal_code": profile.address_postal if profile else "",
            "tier": classification.tier if classification else "",
            "lifecycle_stage": classification.lifecycle_stage if classification else "",
            "is_named_account": account.pk in named_ids,
            "has_open_opportunity": account.pk in open_ids,
            "account_name": account.name,
        }
    return values


def territory_rule_matches(rule, values):
    """Does this rule claim this account? The SAME composition as ``services._rule_matches``.

    An empty ``conditions`` matches everything, which is exactly what ``is_catch_all`` means; the
    model already refuses an empty rule that is NOT catch-all, so there is no third case here.
    """
    if not rule.conditions:
        return True
    results = []
    for condition in rule.conditions:
        if not isinstance(condition, dict) or not {"field", "operator", "value"}.issubset(condition):
            return False
        results.append(
            _condition_matches(values.get(condition["field"]), condition["operator"], condition["value"])
        )
    return all(results) if rule.match_mode == "all" else any(results)


def territory_index(territories):
    """``({pk: Territory}, {parent_id: [pk, …]})`` for a fetched territory set."""
    by_pk = {territory.pk: territory for territory in territories}
    children = {}
    for territory in territories:
        if territory.parent_id:
            children.setdefault(territory.parent_id, []).append(territory.pk)
    return by_pk, children


def rule_target_territories(rule, by_pk, children):
    """The territories ONE rule writes: its target, plus every descendant when the scope is
    ``subtree`` (a BFS over ``crm.Territory.parent``, bounded, so a self-referential parent chain
    cannot spin). ``exact`` — the default — is the target alone."""
    target = by_pk.get(rule.target_territory_id)
    if target is None:
        return []
    if rule.assignment_scope != "subtree":
        return [target]
    reached = {target.pk}
    pending = [target.pk]
    steps = 0
    while pending:
        steps += 1
        if steps > len(by_pk) + 1:
            break
        current = pending.pop()
        for child_pk in children.get(current, []):
            if child_pk not in reached:
                reached.add(child_pk)
                pending.append(child_pk)
    return [by_pk[pk] for pk in sorted(reached, key=lambda pk: (by_pk[pk].name, pk))]


def assignment_picture(tenant, account_ids):
    """``{account_id: {…}}`` — the CURRENT coverage over a fetched set of accounts.

    ``open_territory_ids`` is ``effective_to IS NULL``, computed here and never stored as a
    boolean (the model's own comment: L37, derive, don't remember). ``current_territory`` is the
    account's open PRIMARY row, because a primary placement is the account's home territory.
    """
    rows = list(
        AccountTerritoryAssignment.objects.filter(
            tenant=tenant, account_id__in=list(account_ids)
        ).select_related("territory")
    )
    picture = {
        account_id: {
            "open_territory_ids": set(),
            "current_territory": None,
            "current_pk": None,
            "primary_count": 0,
            "aux_count": 0,
        }
        for account_id in account_ids
    }
    for row in rows:
        entry = picture.get(row.account_id)
        if entry is None:
            continue
        if row.effective_to is not None:
            continue
        if row.territory_id:
            entry["open_territory_ids"].add(row.territory_id)
        if row.alignment_type == "primary":
            entry["primary_count"] += 1
            if entry["current_territory"] is None:
                entry["current_territory"] = row.territory
                entry["current_pk"] = row.pk
        else:
            entry["aux_count"] += 1
    return picture


def effective_rules(rules, day):
    """The rules actually in force: active, effective on ``day``, and carrying a target. Order is
    the model's ``Meta.ordering`` — ``priority`` then id, lower wins — which is the tie-break the
    evaluator relies on."""
    return [
        rule
        for rule in rules
        if rule.is_active and rule.target_territory_id and rule.is_effective_on(day)
    ]


def evaluate_territory_rules(
    tenant, accounts, rules, by_pk, children, picture=None, values=None,
    profiles=None, classifications=None,
):
    """Every placement the given rules would write, plus the accounts no rule claimed.

    Returns ``(diff_rows, unmatched_accounts)``. One ``diff_rows`` entry per
    ``(account, proposed_territory)`` pair, so a ``subtree`` rule that matches one account against
    three territories produces the three rows a run would actually write rather than one summary
    row that under-reports it. A higher-priority rule claims an account outright: a lower-priority
    rule does not also get it.
    """
    account_ids = [account.pk for account in accounts]
    if picture is None:
        picture = assignment_picture(tenant, account_ids)
    if profiles is None:
        profiles = _build_account_profile_map(tenant, account_ids)
    if classifications is None:
        classifications = _build_account_classification_map(tenant, account_ids)
    if values is None:
        values = account_territory_values(
            tenant, accounts, profiles=profiles, classifications=classifications
        )
    day = timezone.localdate()
    diff_rows = []
    unmatched = []
    matched_ids = set()
    for rule in rules:
        for account in accounts:
            if account.pk in matched_ids:
                continue
            if not territory_rule_matches(rule, values.get(account.pk, {})):
                continue
            matched_ids.add(account.pk)
            entry = picture.get(account.pk, {})
            for proposed in rule_target_territories(rule, by_pk, children):
                if proposed.pk in entry.get("open_territory_ids", set()):
                    action = "unchanged"
                elif entry.get("current_territory") is None:
                    action = "add"
                else:
                    action = "move"
                diff_rows.append({
                    "account": account,
                    "profile": profiles.get(account.pk),
                    "classification": classifications.get(account.pk),
                    "current_territory": entry.get("current_territory"),
                    "proposed_territory": proposed,
                    "rule": rule,
                    "action": action,
                })
    # A "remove" is a placement a matched account currently holds that NO rule proposes any more.
    # Only emitted for a matched account, so it never double-reports one already in `unmatched`.
    proposed_by_account = {}
    for row in diff_rows:
        proposed_by_account.setdefault(row["account"].pk, set()).add(row["proposed_territory"].pk)
    for account in accounts:
        if account.pk not in matched_ids:
            unmatched.append(account)
            continue
        entry = picture.get(account.pk, {})
        current = entry.get("current_territory")
        if current is not None and current.pk not in proposed_by_account.get(account.pk, set()):
            diff_rows.append({
                "account": account,
                "profile": profiles.get(account.pk),
                "classification": classifications.get(account.pk),
                "current_territory": current,
                "proposed_territory": None,
                "rule": None,
                "action": "remove",
            })
    return diff_rows, unmatched


def _diff_stats(diff_rows, accounts_scanned):
    stats = {"accounts_scanned": accounts_scanned, "moves": 0, "adds": 0, "removes": 0, "unchanged": 0}
    for row in diff_rows:
        stats[row["action"] + "s" if row["action"] != "unchanged" else "unchanged"] += 1
    return stats


# =============================================================================
# ===== 10.1  territory_rebalance_preview — the dry run                        =
# =============================================================================


@login_required
def territory_rebalance_preview(request):
    """What the active rules WOULD write, before anything is written. **This view never saves.**"""
    tenant = request.tenant
    q = request.GET.get("q", "").strip()
    segment_type = request.GET.get("segment_type", "")
    if segment_type not in dict(TerritoryRule.SEGMENT_TYPE_CHOICES):
        segment_type = ""
    selected_rule_id = as_db_int(request.GET.get("rule"))
    caveats = []

    if tenant is None:
        return render(request, "sales/territoryquotamanagement/boards/rebalance_preview.html", {
            "rules": TerritoryRule.objects.none(),
            "territories": Territory.objects.none(),
            "segment_type_choices": TerritoryRule.SEGMENT_TYPE_CHOICES,
            "selected_rule_id": selected_rule_id or "",
            "q": q,
            "segment_type": segment_type,
            "diff_rows": [],
            "unmatched_rows": [],
            "stats": _diff_stats([], 0),
            "caveats": ["This user has no tenant workspace selected, so there is nothing to rebalance."],
            "can_run": False,
        })

    rules = list(TerritoryRule.objects.filter(tenant=tenant).select_related("target_territory")[:MAX_ROWS])
    if len(rules) >= MAX_ROWS:
        caveats.append(f"Only the first {MAX_ROWS} rules by priority were read; narrow the scope if the tail matters.")
    candidate_rules = effective_rules(rules, timezone.localdate())
    inactive = len(rules) - len(candidate_rules)
    if inactive:
        caveats.append(
            f"{inactive} of {len(rules)} rules are inactive, undated or have no target territory and were not evaluated."
        )
    if segment_type:
        candidate_rules = [rule for rule in candidate_rules if rule.segment_type == segment_type]
    if selected_rule_id:
        narrowed = [rule for rule in candidate_rules if rule.pk == selected_rule_id]
        if not narrowed:
            caveats.append("The selected rule is not one of the rules in force today, so nothing was diffed for it.")
        candidate_rules = narrowed

    territories = list(tenant_territories(tenant))
    by_pk, children = territory_index(territories)
    accounts = list(_tenant_organizations(tenant, q)[:MAX_BOARD_ACCOUNTS])
    account_ids = [account.pk for account in accounts]
    profiles = _build_account_profile_map(tenant, account_ids)
    classifications = _build_account_classification_map(tenant, account_ids)
    diff_rows, unmatched_accounts = evaluate_territory_rules(
        tenant, accounts, candidate_rules, by_pk, children,
        profiles=profiles, classifications=classifications,
    )
    stats = _diff_stats(diff_rows, len(accounts))

    unmatched_rows = [
        {
            "account": account,
            "profile": profiles.get(account.pk),
            "classification": classifications.get(account.pk),
            "current_territory": None,
            "proposed_territory": None,
            "rule": None,
            "action": "unmatched",
        }
        for account in unmatched_accounts
    ]
    if unmatched_accounts:
        caveats.append(f"{len(unmatched_accounts)} accounts matched no rule in force; they keep whatever placement they already have.")
    if stats["removes"]:
        caveats.append(
            f"{stats['removes']} placements are no longer proposed by any rule. A run OPENS the new rows; "
            "it does not close a superseded one — close it on the assignment register, which is a "
            "deliberate act about a book's history."
        )
    if any(rule.assignment_scope == "subtree" for rule in candidate_rules):
        caveats.append("A subtree rule lists one row per descendant territory; a run writes one row per listed territory.")
    if len(accounts) >= MAX_BOARD_ACCOUNTS:
        caveats.append(f"Only the first {MAX_BOARD_ACCOUNTS} accounts by name were scanned.")
    caveats.append("This board is a dry run. It writes nothing; the commit is the rule's Run action.")

    return render(request, "sales/territoryquotamanagement/boards/rebalance_preview.html", {
        "rules": rules,
        "territories": territories,
        "segment_type_choices": TerritoryRule.SEGMENT_TYPE_CHOICES,
        "selected_rule_id": selected_rule_id or "",
        "q": q,
        "segment_type": segment_type,
        "diff_rows": diff_rows,
        "unmatched_rows": unmatched_rows,
        "stats": stats,
        "caveats": caveats,
        "can_run": bool(candidate_rules) and is_tenant_admin(request.user),
    })


# =============================================================================
# ===== 10.2  territory_coverage_gap                                          ==
# =============================================================================


@login_required
def territory_coverage_gap(request):
    """Every way coverage can be incomplete, surfaced rather than hidden (research §5.6)."""
    tenant = request.tenant
    q = request.GET.get("q", "").strip()
    caveats = []
    if tenant is None:
        return render(request, "sales/territoryquotamanagement/boards/coverage_gap.html", {
            "uncovered_rows": [],
            "unassigned_rows": [],
            "over_assigned_rows": [],
            "manager_less_rows": [],
            "orphan_rows": [],
            "orphaned_pair_rows": [],
            "territories": Territory.objects.none(),
            "q": q,
            "stats": {
                "accounts_total": 0, "uncovered": 0, "unassigned": 0,
                "over_assigned": 0, "manager_less": 0, "orphans": 0,
            },
            "caveats": ["This user has no tenant workspace selected, so there is nothing to check."],
        })

    accounts = list(_tenant_organizations(tenant, q)[:MAX_BOARD_ACCOUNTS])
    account_ids = [account.pk for account in accounts]
    territories = list(tenant_territories(tenant, active_only=False))
    by_pk, children = territory_index(territories)
    rules = effective_rules(
        list(TerritoryRule.objects.filter(tenant=tenant).select_related("target_territory")[:MAX_ROWS]),
        timezone.localdate(),
    )
    picture = assignment_picture(tenant, account_ids)
    profiles = _build_account_profile_map(tenant, account_ids)
    classifications = _build_account_classification_map(tenant, account_ids)
    _, unmatched_accounts = evaluate_territory_rules(
        tenant, accounts, rules, by_pk, children, picture=picture,
        profiles=profiles, classifications=classifications,
    )

    def _account_row(account):
        return {
            "account": account,
            "profile": profiles.get(account.pk),
            "classification": classifications.get(account.pk),
        }

    uncovered_rows = [_account_row(account) for account in unmatched_accounts]
    unassigned_rows = [
        _account_row(account)
        for account in accounts
        if not picture.get(account.pk, {}).get("open_territory_ids")
    ]
    over_assigned_rows = []
    for account in accounts:
        entry = picture.get(account.pk, {})
        if entry["primary_count"] > 1 or entry["aux_count"] > MAX_ACTIVE_AUXILIARY_ALIGNMENTS:
            over_assigned_rows.append({
                **_account_row(account),
                "primary_count": entry["primary_count"],
                "auxiliary_count": entry["aux_count"],
                "territories": sorted(
                    (by_pk[pk].number for pk in entry["open_territory_ids"] if pk in by_pk),
                ),
            })

    manager_less_rows = [
        territory
        for territory in tenant_territories(tenant)
        if territory.manager_id is None
        and (not q or q.casefold() in territory.name.casefold())
    ]
    orphan_rows = [
        row
        for row in AccountTerritoryAssignment.objects.filter(
            tenant=tenant, territory__isnull=True, effective_to__isnull=True
        ).select_related("account")
        if not q or q.casefold() in str(row.account).casefold()
    ]
    orphaned_pair_rows = list(
        TerritoryMember.objects.filter(tenant=tenant, effective_to__isnull=True, member_role="sdr")
        .filter(Q(paired_user__isnull=True) | Q(paired_user__is_active=False))
        .select_related("territory", "user", "paired_user")[:MAX_ROWS]
    )

    if not rules:
        caveats.append("No rule is in force today, so every scanned account reads as uncovered.")
    if len(accounts) >= MAX_BOARD_ACCOUNTS:
        caveats.append(f"Only the first {MAX_BOARD_ACCOUNTS} accounts by name were scanned.")
    if orphan_rows:
        caveats.append(
            f"{len(orphan_rows)} live assignments point at no territory. A deleted CRM territory orphans its "
            "rows (SET_NULL) rather than destroying the history of a coverage decision."
        )
    if orphaned_pair_rows:
        caveats.append(f"{len(orphaned_pair_rows)} live memberships pair with no active account executive.")
    if manager_less_rows:
        caveats.append(
            f"{len(manager_less_rows)} active territories have no manager, so 8.1's territory-manager routing "
            "has nobody to hand a lead to there."
        )
    if unassigned_rows:
        caveats.append(f"{len(unassigned_rows)} scanned accounts hold no live assignment at all.")

    return render(request, "sales/territoryquotamanagement/boards/coverage_gap.html", {
        "uncovered_rows": uncovered_rows,
        "unassigned_rows": unassigned_rows,
        "over_assigned_rows": over_assigned_rows,
        "manager_less_rows": manager_less_rows,
        "orphan_rows": orphan_rows,
        "orphaned_pair_rows": orphaned_pair_rows,
        "territories": territories,
        "q": q,
        "stats": {
            "accounts_total": len(accounts),
            "uncovered": len(uncovered_rows),
            "unassigned": len(unassigned_rows),
            "over_assigned": len(over_assigned_rows),
            "manager_less": len(manager_less_rows),
            "orphans": len(orphan_rows) + len(orphaned_pair_rows),
        },
        "caveats": caveats,
    })


# =============================================================================
# ===== 10.3  territory_performance                                            ==
# =============================================================================


@login_required
def territory_performance(request):
    """Attainment per territory for one forecast period, every figure summed in Python."""
    tenant = request.tenant
    q = request.GET.get("q", "").strip()
    caveats = []
    periods = (
        list(
            ForecastPeriod.objects.filter(tenant=tenant)
            .select_related("reporting_currency")
            .order_by("-period_year", "-period_number", "period_type")[:MAX_PERIODS]
        )
        if tenant is not None
        else []
    )
    period_choices = [(period.pk, _period_label(period)) for period in periods]
    selected_period_id = as_db_int(request.GET.get("period"))
    period = next((p for p in periods if p.pk == selected_period_id), None)
    if period is None and periods:
        period = periods[0]
    territories = list(tenant_territories(tenant, active_only=False)[:MAX_ROWS]) if tenant else []
    empty_summary = {
        "attainment_amount": None,
        "quota_amount": None,
        "overall_attainment_pct": None,
        "period_elapsed_pct": None,
    }
    empty_top_bottom = {"top": [], "bottom": []}
    if period is None:
        return render(request, "sales/territoryquotamanagement/boards/performance.html", {
            "period": None,
            "periods": periods,
            "period_choices": period_choices,
            "selected_period_id": selected_period_id or "",
            "rows": [],
            "summary": empty_summary,
            "top_bottom": empty_top_bottom,
            "territories": territories,
            "q": q,
            "caveats": [
                "No forecast period exists in this workspace, so there is no window to measure attainment against."
            ],
        })

    # --- READ, never re-derived: ForecastPeriod.period_elapsed_pct is 8.4's own property.
    elapsed_pct = period.period_elapsed_pct
    if q:
        territories = [t for t in territories if q.casefold() in t.name.casefold()]
    territory_ids = [territory.pk for territory in territories]

    # --- The accounts each territory currently owns, from the LIVE ledger.
    open_assignments = list(
        AccountTerritoryAssignment.objects.filter(
            tenant=tenant,
            territory_id__in=territory_ids,
            effective_to__isnull=True,
        ).values_list("territory_id", "account_id")
    )
    account_ids_by_territory = {}
    for territory_id, account_id in open_assignments:
        account_ids_by_territory.setdefault(territory_id, set()).add(account_id)

    # --- Quotas. `crm.SalesQuota.target_amount` is READ; 8.7 never writes a quota amount (§0.3).
    quota_rows = list(
        SalesQuota.objects.filter(
            tenant=tenant,
            territory_id__in=territory_ids,
            period_type=period.period_type,
            period_year=period.period_year,
            period_number=period.period_number,
        ).select_related("territory")
    )
    quota_by_territory = {territory_id: ZERO for territory_id in territory_ids}
    seen_quota_keys = {}
    duplicate_quota_warnings = []
    for quota in quota_rows:
        # (tenant, owner, period) is NOT unique on crm.SalesQuota when territory is NULL, so a
        # duplicate is REPORTED here rather than allowed to double a territory's quota (§6.6).
        key = (quota.territory_id, quota.owner_id, quota.period_type, quota.period_year, quota.period_number)
        if key in seen_quota_keys:
            duplicate_quota_warnings.append(
                f"{quota.territory.number if quota.territory_id else '—'} has more than one quota for one "
                "owner in this period; only the first was counted."
            )
            continue
        seen_quota_keys[key] = quota.pk
        if quota.territory_id in quota_by_territory:
            quota_by_territory[quota.territory_id] += Decimal(quota.target_amount or ZERO)
    if duplicate_quota_warnings:
        caveats.append(duplicate_quota_warnings[0])

    # --- Deals for the owned accounts, fetched via subquery and grouped in Python.
    assignment_accounts = AccountTerritoryAssignment.objects.filter(
        tenant=tenant,
        territory_id__in=territory_ids,
        effective_to__isnull=True,
    ).values("account_id")
    opportunities = (
        list(
            Opportunity.objects.filter(tenant=tenant, account_id__in=assignment_accounts)
            .only("pk", "account_id", "stage", "amount", "currency_id", "close_date")
        )
        if territory_ids
        else []
    )
    currency_ids = {o.currency_id for o in opportunities if o.currency_id}
    multi_currency = len(currency_ids) > 1
    if multi_currency:
        # Summing across currencies would be a wrong number, not a slow one, so the money columns
        # are withheld and the fact is stated (§6.7 / §10.5).
        caveats.append(
            "The deals behind these accounts are booked in more than one currency, so attainment and "
            "pipeline are withheld rather than added across currencies."
        )
    elif currency_ids and period.reporting_currency_id and currency_ids != {period.reporting_currency_id}:
        reporting_curr_code = period.reporting_currency.code if period.reporting_currency else "—"
        caveats.append(
            f"These deals are booked in one currency that is not {reporting_curr_code}, "
            "the period's reporting currency."
        )

    attainment = {territory_id: ZERO for territory_id in territory_ids}
    pipeline = {territory_id: ZERO for territory_id in territory_ids}
    window_ok = bool(period.start_date and period.end_date)
    if not window_ok:
        caveats.append("This period carries no date window, so every closed-won deal is counted against it.")
    for territory_id, account_ids in account_ids_by_territory.items():
        for opportunity in opportunities:
            if opportunity.account_id not in account_ids:
                continue
            if opportunity.stage not in Opportunity.OPEN_STAGES:
                if opportunity.stage != "closed_won" or multi_currency:
                    continue
                if window_ok and not (
                    period.start_date <= (opportunity.close_date or period.end_date) <= period.end_date
                ):
                    continue
                attainment[territory_id] += Decimal(opportunity.amount or ZERO)
            elif not multi_currency:
                pipeline[territory_id] += Decimal(opportunity.amount or ZERO)

    member_counts = {
        territory_id: 0
        for territory_id in territory_ids
    }
    for territory_id, _ in TerritoryMember.objects.filter(
        tenant=tenant, territory_id__in=territory_ids, effective_to__isnull=True
    ).values_list("territory_id", "user_id"):
        member_counts[territory_id] = member_counts.get(territory_id, 0) + 1

    total_quota = sum(quota_by_territory.values(), ZERO)
    rows = []
    for territory in territories:
        quota_amount = _money(quota_by_territory[territory.pk])
        attainment_amount = None if multi_currency else _money(attainment[territory.pk])
        pipeline_amount = None if multi_currency else _money(pipeline[territory.pk])
        attainment_pct = (
            None
            if multi_currency
            else _pct(attainment[territory.pk], quota_by_territory[territory.pk])
        )
        rows.append({
            "territory": territory,
            "quota_amount": quota_amount,
            "attainment_amount": attainment_amount,
            "pipeline_amount": pipeline_amount,
            "attribution_pct": _pct(quota_by_territory[territory.pk], total_quota),
            "attainment_pct": attainment_pct,
            # Pacing = attainment against TIME, not against the target: 120% of target halfway
            # through the period is ahead of pace, which attainment_pct alone cannot say.
            "pacing_pct": (
                None
                if attainment_pct is None or not elapsed_pct
                else (attainment_pct * HUNDRED / elapsed_pct).quantize(CENTS, rounding=ROUND_HALF_UP)
            ),
            "elapsed_pct": elapsed_pct,
            "account_count": len(account_ids_by_territory.get(territory.pk, ())),
            "member_count": member_counts.get(territory.pk, 0),
            # `balance_profile` is an ACCEPTANCE SPEC, not a score: every axis, no single answer
            # (§10.5). Equalising territories on one of them is the documented failure mode.
            "balance_profile": {
                "account_count": len(account_ids_by_territory.get(territory.pk, ())),
                "member_count": member_counts.get(territory.pk, 0),
                "quota_share_pct": _pct(quota_by_territory[territory.pk], total_quota),
                "open_pipeline_deals": None if multi_currency else sum(
                    1
                    for opportunity in opportunities
                    if opportunity.stage in Opportunity.OPEN_STAGES
                    and opportunity.account_id in account_ids_by_territory.get(territory.pk, set())
                ),
            },
        })
    ranked = [row for row in rows if row["attainment_pct"] is not None]
    top_bottom = {
        "top": sorted(ranked, key=lambda row: row["attainment_pct"], reverse=True)[:5],
        "bottom": sorted(ranked, key=lambda row: row["attainment_pct"])[:5],
    }
    total_attainment = None if multi_currency else _money(sum(attainment.values(), ZERO))
    summary = {
        "attainment_amount": total_attainment,
        "quota_amount": _money(total_quota),
        "overall_attainment_pct": None if multi_currency else _pct(sum(attainment.values(), ZERO), total_quota),
        "period_elapsed_pct": elapsed_pct,
    }
    if multi_currency:
        summary["attainment_amount"] = None
        summary["overall_attainment_pct"] = None
    caveats.append(
        "Attainment counts the closed-won deals of each territory's own live-assigned accounts. It is a "
        "book view, not a commission view: deal credit stays with 8.10."
    )
    if not quota_rows:
        caveats.append(
            "No CRM quota is recorded for this period, so every attainment percentage is withheld — there "
            "is no denominator."
        )

    return render(request, "sales/territoryquotamanagement/boards/performance.html", {
        "period": period,
        "periods": periods,
        "period_choices": period_choices,
        "selected_period_id": period.pk,
        "rows": rows,
        "summary": summary,
        "top_bottom": top_bottom,
        "territories": territories,
        "q": q,
        "caveats": caveats,
    })


# =============================================================================
# ===== 10.4  territory_white_space                                           ==
# =============================================================================


@login_required
def territory_white_space(request):
    """Which accounts no one owns, and which are owned only by an overlay.

    8.3 owns the ACCOUNT-level white space; this board is the TERRITORY-scoped cut of it, and it
    cross-links to 8.3's page rather than restating it (non-goal §1 item 9).
    """
    tenant = request.tenant
    q = request.GET.get("q", "").strip()
    selected_tier = request.GET.get("tier", "")
    if selected_tier not in dict(AccountClassification.TIER_CHOICES):
        selected_tier = ""
    selected_lifecycle_stage = request.GET.get("lifecycle_stage", "")
    if selected_lifecycle_stage not in dict(AccountClassification.LIFECYCLE_STAGE_CHOICES):
        selected_lifecycle_stage = ""
    selected_industry = request.GET.get("industry", "").strip()
    caveats = []

    accounts_qs = _tenant_organizations(tenant, q)
    if selected_tier:
        accounts_qs = accounts_qs.filter(sales_account_classification__tier=selected_tier)
    if selected_lifecycle_stage:
        accounts_qs = accounts_qs.filter(sales_account_classification__lifecycle_stage=selected_lifecycle_stage)
    if selected_industry:
        accounts_qs = accounts_qs.filter(crm_account_profile__industry=selected_industry)

    accounts = (
        list(accounts_qs[:MAX_BOARD_ACCOUNTS])
        if tenant is not None
        else []
    )
    if len(accounts) >= MAX_BOARD_ACCOUNTS:
        caveats.append(f"Only the first {MAX_BOARD_ACCOUNTS} matching accounts by name were scanned.")
    account_ids = [account.pk for account in accounts]
    picture = assignment_picture(tenant, account_ids) if account_ids else {}
    by_pk, _ = territory_index(
        list(tenant_territories(tenant, active_only=False)[:MAX_ROWS]) if tenant else []
    )
    profiles = _build_account_profile_map(tenant, account_ids)
    classifications = _build_account_classification_map(tenant, account_ids)
    opportunities = (
        list(
            Opportunity.objects.filter(tenant=tenant, account_id__in=account_ids)
            .filter(stage__in=Opportunity.OPEN_STAGES)
            .only("pk", "account_id", "amount", "currency_id")
        )
        if account_ids
        else []
    )
    deals_by_account = {}
    for opportunity in opportunities:
        deals_by_account.setdefault(opportunity.account_id, []).append(opportunity)
    currency_ids = {o.currency_id for o in opportunities if o.currency_id}
    multi_currency = len(currency_ids) > 1
    if multi_currency:
        caveats.append("Open pipeline is booked in more than one currency, so it is not added up here.")

    rows = []
    for account in accounts:
        entry = picture.get(account.pk, {})
        alignment_rows = {}
        for territory_id in entry.get("open_territory_ids", set()):
            alignment_rows[territory_id] = None
        covered_territories = [by_pk[pk] for pk in sorted(alignment_rows) if pk in by_pk]
        primary_territory = entry.get("current_territory")
        if primary_territory is not None or len(covered_territories) > 1:
            coverage_state = "covered"
        elif covered_territories:
            coverage_state = "overlay_only"
        else:
            coverage_state = "uncovered"
        account_deals = deals_by_account.get(account.pk, [])
        pipeline_amount = (
            None
            if multi_currency
            else _money(sum((Decimal(o.amount or ZERO) for o in account_deals), ZERO))
        )
        classification = classifications.get(account.pk)
        gap = ""
        if classification is None:
            gap = "No classification on file, so no tier governs this account."
        elif account_deals and classification.lifecycle_stage in {"prospect", "nurture", "dormant"}:
            gap = (
                f"Carries {len(account_deals)} open deal(s) but is still classified "
                f"{classification.get_lifecycle_stage_display()}."
            )
        elif not classification.review_due_on:
            gap = "Classification carries no review date, so its tier has never been re-confirmed."
        if selected_tier and (classification is None or classification.tier != selected_tier):
            continue
        if selected_lifecycle_stage and (
            classification is None or classification.lifecycle_stage != selected_lifecycle_stage
        ):
            continue
        if selected_industry and (profiles.get(account.pk) is None or profiles.get(account.pk).industry != selected_industry):
            continue
        rows.append({
            "account": account,
            "profile": profiles.get(account.pk),
            "classification": classification,
            "covered_territories": covered_territories,
            "coverage_state": coverage_state,
            "opportunity_count": len(account_deals),
            "pipeline_amount": pipeline_amount,
            "classification_gap": gap,
        })

    # `segments` is the same fetched set grouped by tier. No key names were pinned (§17 item 9), so
    # these are the build-time choice; an unclassified account groups under "Unclassified" rather
    # than being dropped, because an unclassified account is exactly what this board is looking for.
    segments = []
    for tier in [choice[0] for choice in AccountClassification.TIER_CHOICES] + [""]:
        label = dict(AccountClassification.TIER_CHOICES).get(tier, "Unclassified")
        group = [
            row
            for row in rows
            if (row["classification"].tier if row["classification"] else "") == tier
        ]
        if not group:
            continue
        segments.append({
            "label": label,
            "tier": tier,
            "accounts": len(group),
            "covered": sum(1 for row in group if row["coverage_state"] == "covered"),
            "uncovered": sum(1 for row in group if row["coverage_state"] == "uncovered"),
            "overlay_only": sum(1 for row in group if row["coverage_state"] == "overlay_only"),
            "opportunity_count": sum(row["opportunity_count"] for row in group),
        })
    if not selected_tier and not selected_lifecycle_stage:
        uncovered = [row for row in rows if row["coverage_state"] == "uncovered"]
        if uncovered:
            caveats.append(
                f"{len(uncovered)} scanned accounts hold no live assignment. Assigning one by hand is the "
                "supported path; there is no geospatial balancing here (non-goal §1 item 1)."
            )

    return render(request, "sales/territoryquotamanagement/boards/white_space.html", {
        "rows": rows,
        "segments": segments,
        "tier_choices": AccountClassification.TIER_CHOICES,
        "lifecycle_stage_choices": AccountClassification.LIFECYCLE_STAGE_CHOICES,
        "selected_tier": selected_tier,
        "selected_lifecycle_stage": selected_lifecycle_stage,
        "selected_industry": selected_industry,
        "q": q,
        "stats": {
            "accounts_scanned": len(accounts),
            "covered": sum(1 for row in rows if row["coverage_state"] == "covered"),
            "uncovered": sum(1 for row in rows if row["coverage_state"] == "uncovered"),
            "overlay_only": sum(1 for row in rows if row["coverage_state"] == "overlay_only"),
        },
        "caveats": caveats,
        "account_white_space_url": reverse("sales:account_white_space"),
    })
