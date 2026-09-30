"""Sales 8.7 — the territory rule views: register, detail, CRUD, and the two POST verbs.

A `TerritoryRule` does not define a territory: it says which *existing* `crm.Territory` an account
matching a typed condition set belongs to, and `assignment_scope="subtree"` fans that out over the
descendants of the target. 8.7 EXTENDS `crm.Territory` by FK and declares it again nowhere.

The two verbs are deliberately asymmetric, and the difference is the whole point of the sub-module:

* `territory_rule_run` **commits**. It writes the assignment rows AND stamps the rule's frozen
  evidence (`last_run_at` / `last_run_matched_count`) inside ONE `transaction.atomic()` block, so a
  rule can never claim a run it did not have, and a run can never lose its receipt.
* `territory_rebalance_preview` in the sibling boards module is the **dry run**. It writes nothing
  and is the reason the commit verb is allowed to be blunt.

The run reuses `evaluate_territory_rules` from the boards module — the SAME evaluator the preview
used, so what the preview showed and what the run writes cannot disagree.
"""
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.crud import as_db_int
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.TerritoryQuotaManagement.TerritoryRules import TerritoryRuleForm
from apps.sales.models.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignment,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import TerritoryRule
from apps.sales.views._common import *
from apps.sales.views.TerritoryQuotaManagement.TerritoryBoards import (
    MAX_BOARD_ACCOUNTS,
    evaluate_territory_rules,
    rule_target_territories,
    territory_index,
    tenant_territories,
)

LIST_TEMPLATE = "sales/territoryquotamanagement/territoryrule/list.html"
DETAIL_TEMPLATE = "sales/territoryquotamanagement/territoryrule/detail.html"
FORM_TEMPLATE = "sales/territoryquotamanagement/territoryrule/form.html"

#: Per-page value for the register, carried into the template as `page_size`.
PAGE_SIZE = 15

#: The `active` GET filter carries "active"/"inactive", NOT "True"/"False" — so `crud_list`'s own
#: boolean mapping cannot narrow on it and the mapping is done here, before pagination.
ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]


def _rule_queryset(request):
    return (
        TerritoryRule.objects.filter(tenant=request.tenant)
        .select_related("target_territory")
    )


def _choice_context():
    """The four choice lists every rule page renders. One source, four pages."""
    return {
        "segment_type_choices": TerritoryRule.SEGMENT_TYPE_CHOICES,
        "match_mode_choices": TerritoryRule.MATCH_MODE_CHOICES,
        "alignment_type_choices": TerritoryRule.ALIGNMENT_TYPE_CHOICES,
        "assignment_scope_choices": TerritoryRule.ASSIGNMENT_SCOPE_CHOICES,
    }


@login_required
def territory_rule_list(request):
    """The rule register: search, six GET filters, and the run's own receipt per row."""
    queryset = _rule_queryset(request)
    segment_type = request.GET.get("segment_type", "")
    if segment_type in dict(TerritoryRule.SEGMENT_TYPE_CHOICES):
        queryset = queryset.filter(segment_type=segment_type)
    match_mode = request.GET.get("match_mode", "")
    if match_mode in dict(TerritoryRule.MATCH_MODE_CHOICES):
        queryset = queryset.filter(match_mode=match_mode)
    alignment_type = request.GET.get("alignment_type", "")
    if alignment_type in dict(TerritoryRule.ALIGNMENT_TYPE_CHOICES):
        queryset = queryset.filter(alignment_type=alignment_type)
    assignment_scope = request.GET.get("assignment_scope", "")
    if assignment_scope in dict(TerritoryRule.ASSIGNMENT_SCOPE_CHOICES):
        queryset = queryset.filter(assignment_scope=assignment_scope)
    # as_db_int: `?target_territory=abc` and an over-range id are SKIPPED, never handed to the driver.
    target_territory_id = as_db_int(request.GET.get("target_territory"))
    if target_territory_id:
        queryset = queryset.filter(target_territory_id=target_territory_id)
    active = request.GET.get("active", "")
    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)

    base = _rule_queryset(request)
    stats = {
        "total": base.count(),
        "active": base.filter(is_active=True).count(),
        "catch_all": base.filter(is_catch_all=True).count(),
        "never_run": base.filter(last_run_at__isnull=True).count(),
    }
    return crud_list(
        request,
        queryset,
        LIST_TEMPLATE,
        search_fields=["number", "name", "description"],
        extra_context={
            "page_size": PAGE_SIZE,
            **_choice_context(),
            "active_choices": ACTIVE_CHOICES,
            "territories": tenant_territories(request.tenant),
            "stats": stats,
            "segment_type": segment_type,
            "match_mode": match_mode,
            "alignment_type": alignment_type,
            "assignment_scope": assignment_scope,
            "target_territory_id": target_territory_id or "",
            "active": active,
        },
        per_page=PAGE_SIZE,
    )


@tenant_admin_required
def territory_rule_create(request):
    return crud_create(
        request,
        form_class=TerritoryRuleForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:territory_rule_list"),
        extra_context={**_choice_context(), "territories": tenant_territories(request.tenant)},
    )


@login_required
def territory_rule_detail(request, pk):
    obj = get_object_or_404(_rule_queryset(request), pk=pk)
    today = timezone.localdate()
    generated_assignments = AccountTerritoryAssignment.objects.filter(
        tenant=request.tenant, rule=obj
    ).select_related("account", "territory")[:200]
    caveats = []
    is_runnable = bool(obj.is_active and obj.target_territory_id and obj.is_effective_on(today))
    if not obj.target_territory_id:
        caveats.append("This rule names no target territory, so a run would refuse it.")
    elif not obj.is_active:
        caveats.append("This rule is inactive, so a run would refuse it.")
    elif not obj.is_effective_on(today):
        caveats.append("This rule is outside its effective window today, so a run would refuse it.")
    if obj.target_territory_id and not tenant_territories(request.tenant, active_only=False).filter(
        pk=obj.target_territory_id
    ).exists():
        caveats.append("The target territory is not an active territory any more.")
    if obj.assignment_scope == "subtree":
        caveats.append("A subtree rule writes one assignment per descendant territory of the target.")
    if obj.last_run_at is None:
        caveats.append("This rule has never been run, so it has produced no assignments yet.")
    return render(request, DETAIL_TEMPLATE, {
        "obj": obj,
        **_choice_context(),
        "generated_assignments": generated_assignments,
        "is_runnable": is_runnable,
        "caveats": caveats,
    })


@tenant_admin_required
def territory_rule_edit(request, pk):
    return crud_edit(
        request,
        model=TerritoryRule,
        pk=pk,
        form_class=TerritoryRuleForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:territory_rule_detail", args=[pk]),
        extra_context={**_choice_context(), "territories": tenant_territories(request.tenant)},
    )


@require_POST
@login_required
@tenant_admin_required
def territory_rule_delete(request, pk):
    obj = get_object_or_404(_rule_queryset(request), pk=pk)
    generated = AccountTerritoryAssignment.objects.filter(tenant=request.tenant, rule=obj).count()
    with transaction.atomic():
        locked = TerritoryRule.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        write_audit_log(
            request.user,
            locked,
            "delete",
            {
                "action": "territory_rule",
                "name": locked.name,
                "target_territory_id": locked.target_territory_id,
                "generated_assignments": generated,
            },
            tenant=request.tenant,
        )
        locked.delete()
    messages.success(request, "Territory rule deleted.")
    return redirect("sales:territory_rule_list")


@require_POST
@login_required
@tenant_admin_required
def territory_rule_run(request, pk):
    """COMMIT. Evaluate the rule, write the assignment rows, stamp the receipt — all in one
    transaction, so the receipt can never survive a failed write."""
    obj = get_object_or_404(_rule_queryset(request), pk=pk)
    today = timezone.localdate()
    if not obj.target_territory_id:
        messages.error(request, "This rule names no target territory, so there is nothing to assign.")
        return redirect("sales:territory_rule_detail", pk=obj.pk)
    if not obj.is_active:
        messages.error(request, "This rule is inactive. Activate it before running it.")
        return redirect("sales:territory_rule_detail", pk=obj.pk)
    if not obj.is_effective_on(today):
        messages.error(request, "This rule is outside its effective window today, so it will not run.")
        return redirect("sales:territory_rule_detail", pk=obj.pk)

    # Bounded exactly as the preview board scans it, so a run and its dry run can never disagree
    # about WHICH accounts were in scope — only about what the run then did with them.
    accounts = list(
        Party.objects.filter(tenant=request.tenant, kind="organization")
        .order_by("name")[:MAX_BOARD_ACCOUNTS]
    )
    territories = list(tenant_territories(request.tenant, active_only=False))
    by_pk, children = territory_index(territories)
    diff_rows, _ = evaluate_territory_rules(
        request.tenant, accounts, [obj], by_pk, children
    )
    target_ids = {territory.pk for territory in rule_target_territories(obj, by_pk, children)}
    # Only `add` and `move` are actioned. An `unchanged` row already has a live assignment in the
    # same territory, and a `remove` row is a placement a rule no longer proposes — closing that is
    # a deliberate act about a book's history, so a run reports it (see the message below) and
    # leaves the row alone. The preview's caveat says the same thing, so neither view surprises.
    actionable = [row for row in diff_rows if row["action"] in {"add", "move"}]

    created = 0
    already_present = 0
    closed_history_skipped = 0
    claimed_elsewhere = 0
    with transaction.atomic():
        for row in actionable:
            territory = row["proposed_territory"]
            if territory is None or territory.pk not in target_ids:
                continue
            existing = (
                AccountTerritoryAssignment.objects.select_for_update()
                .filter(
                    tenant=request.tenant,
                    account_id=row["account"].pk,
                    territory_id=territory.pk,
                )
                .first()
            )
            if existing is not None:
                if existing.effective_to is not None:
                    # A CLOSED row is history. Re-opening it would rewrite a past coverage decision,
                    # so the run reports it instead of overwriting it.
                    closed_history_skipped += 1
                else:
                    already_present += 1
                    if existing.rule_id and existing.rule_id != obj.pk:
                        claimed_elsewhere += 1
                continue
            effective_from = obj.effective_from if obj.effective_from and obj.effective_from > today else today
            AccountTerritoryAssignment.objects.create(
                tenant=request.tenant,
                account=row["account"],
                territory=territory,
                rule=obj,
                alignment_type=obj.alignment_type,
                assignment_source="rule",
                effective_from=effective_from,
                assigned_by=request.user,
            )
            created += 1
        # Frozen evidence, written INSIDE the same block as the rows it describes (§12).
        locked_rule = TerritoryRule.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        locked_rule.last_run_at = timezone.now()
        # MATCHED accounts, not rows written: a subtree rule writes several rows for one account,
        # and "how many accounts did this rule claim" is the question a receipt answers.
        locked_rule.last_run_matched_count = len(
            {
                row["account"].pk
                for row in diff_rows
                if row["action"] in {"add", "move", "unchanged"}
            }
        )
        locked_rule.save(update_fields=["last_run_at", "last_run_matched_count", "updated_at"])
        write_audit_log(
            request.user,
            locked_rule,
            "update",
            {
                "action": "territory_rule_run",
                "rule": locked_rule.name,
                "target_territory_id": locked_rule.target_territory_id,
                "assignment_scope": locked_rule.assignment_scope,
                "matched": locked_rule.last_run_matched_count,
                "created": created,
                "already_present": already_present,
                "closed_history_skipped": closed_history_skipped,
            },
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Rule run: {locked_rule.last_run_matched_count} account(s) matched, {created} assignment(s) written.",
    )
    if already_present:
        messages.info(request, f"{already_present} of those already had a live assignment in the same territory.")
    if closed_history_skipped:
        messages.warning(
            request,
            f"{closed_history_skipped} account(s) already have a CLOSED assignment in that territory. "
            "A run will not rewrite history — open a new one by hand if that placement should be current.",
        )
    if claimed_elsewhere:
        messages.warning(
            request,
            f"{claimed_elsewhere} live assignment(s) in that territory were made by a different rule.",
        )
    return redirect("sales:territory_rule_detail", pk=obj.pk)


@require_POST
@login_required
@tenant_admin_required
def territory_rule_toggle(request, pk):
    """Flip a rule in or out of force. POST-only: a GET link must never change a coverage rule."""
    obj = get_object_or_404(_rule_queryset(request), pk=pk)
    with transaction.atomic():
        locked = TerritoryRule.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        locked.is_active = not locked.is_active
        locked.save(update_fields=["is_active", "updated_at"])
        write_audit_log(
            request.user,
            locked,
            "update",
            {"action": "territory_rule_toggle", "rule": locked.name, "is_active": locked.is_active},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"{locked.name} is now {'active' if locked.is_active else 'inactive'}.",
    )
    return redirect("sales:territory_rule_detail", pk=obj.pk)
