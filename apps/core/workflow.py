"""core — 0.11's mechanisms: the approval-monitoring source table and the rule evaluator.

Two jobs, both kept out of the views so they are testable with fixed inputs.

**`approval_backlog()`** reads the REAL approval tables that already exist across the repo. It
declares them in one table rather than guessing, and the table records a distinction that probing
turned up and that matters:

* five of the eight are genuine **in-flight queues** — they have a state a row can sit in while it
  waits (`pending`, `pending_review`, …), so "how many are waiting and how long" is a real question;
* three record only a **decision** (`approved`/`rejected`) with no waiting state at all. Every row in
  those is already decided; the in-flight state lives on the PARENT record (the requisition, the
  transfer, the purchase order), not on the approval row. Reporting them as queues would be a
  fabricated backlog, so they are reported as decided-volume instead.

**`evaluate_rules()`** evaluates a `BusinessRule` condition against a context dict and returns the
matches in priority order. It does not EXECUTE anything — see `apps/core/models/BusinessRule.py` for
why that boundary is deliberate.
"""
from django.apps import apps as django_apps

#: label -> (state field, open states). An EMPTY `open_states` means the table records decisions only
#: and has no waiting state, so it cannot contribute to a backlog.
#:
#: Verified by introspecting each model's choices rather than assumed — see the module docstring.
APPROVAL_SOURCES = {
    "crm.ApprovalRequest": ("status", {"pending"}),
    "hrm.RequisitionApproval": ("status", {"pending"}),
    "hrm.OfferApproval": ("status", {"pending"}),
    "projects.ClientApprovalRequest": ("status", {"draft", "pending_review", "revision_requested"}),
    "projects.ProjectApprovalGate": ("status", {"pending", "escalated"}),
    # Decision logs — no open state. Kept in the table so the board can say WHY they are not queues.
    "inventory.PurchaseOrderApproval": ("decision", set()),
    "inventory.TransferApproval": ("decision", set()),
    "procurement.RequisitionApproval": ("decision", set()),
}

#: Monitored models that are NOT approval queues at all, and the reason. Listed so the board can
#: account for every approval-ish model it found instead of silently dropping four of them.
NON_QUEUE_SOURCES = {
    "crm.WorkflowLog": "an execution log, not a queue",
    "projects.WorkflowExecutionLog": "an execution log, not a queue",
    "scm.ClientSLA": "an SLA definition, not an approval",
    "hrm.HelpdeskSLAPolicy": "an SLA definition, not an approval",
}


def monitored_labels():
    """Every approval-ish label the board accounts for, queues and non-queues alike."""
    return set(APPROVAL_SOURCES) | set(NON_QUEUE_SOURCES)


def approval_backlog(tenant, aging_hours=48):
    """Read every declared approval source for one tenant.

    Returns `{"queues": [...], "decision_logs": [...], "skipped": [...]}` where each queue row carries
    its open count, the age of its oldest item and how many have breached `aging_hours`. A source whose
    model or state field is missing is reported as skipped WITH the reason — never silently dropped,
    because a monitoring board that quietly omits a queue is worse than one that shows nothing.
    """
    from django.utils import timezone

    now = timezone.now()
    queues, decision_logs, skipped = [], [], []

    for label, (state_field, open_states) in sorted(APPROVAL_SOURCES.items()):
        app_label, model_name = label.split(".")
        try:
            model = django_apps.get_model(app_label, model_name)
        except LookupError:
            skipped.append({"label": label, "reason": "model not found"})
            continue
        names = {f.name for f in model._meta.concrete_fields}
        if "tenant" not in names or state_field not in names:
            skipped.append({"label": label, "reason": "no tenant or state field"})
            continue

        base = model.objects.filter(tenant=tenant)
        if not open_states:
            decision_logs.append({
                "label": label,
                "decided": base.count(),
                "reason": "records decisions only — the in-flight state is on the parent record",
            })
            continue

        open_qs = base.filter(**{f"{state_field}__in": sorted(open_states)})
        open_count = open_qs.count()
        oldest = None
        breached = 0
        if "created_at" in names:
            oldest_row = open_qs.order_by("created_at").first()
            if oldest_row is not None:
                oldest = oldest_row.created_at
                cutoff = now - timezone.timedelta(hours=aging_hours)
                breached = open_qs.filter(created_at__lt=cutoff).count()
        queues.append({
            "label": label,
            "state_field": state_field,
            "open_states": sorted(open_states),
            "open": open_count,
            "oldest": oldest,
            "oldest_hours": int((now - oldest).total_seconds() // 3600) if oldest else None,
            "breached": breached,
            "has_age": "created_at" in names,
        })

    for label, reason in sorted(NON_QUEUE_SOURCES.items()):
        skipped.append({"label": label, "reason": reason})

    return {
        "queues": queues,
        "decision_logs": decision_logs,
        "skipped": skipped,
        "total_open": sum(q["open"] for q in queues),
        "total_breached": sum(q["breached"] for q in queues),
        "aging_hours": aging_hours,
    }


# ------------------------------------------------------------------ the rule evaluator
def _get_field(context, path):
    """Resolve a dotted path against a context dict. Missing -> None rather than raising."""
    current = context
    for part in str(path).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def evaluate_condition(condition, context):
    """Evaluate one condition tree against a context. Returns (matched, reasons).

    Shape: `{"all": [clause, ...]}` or `{"any": [clause, ...]}`, where a clause is
    `{"field": "amount", "op": "gt", "value": 10000}`. An EMPTY or malformed condition matches
    nothing and says why — a rule with no condition that fired on everything would be a footgun, and
    a rule that silently matched nothing would be invisible.
    """
    reasons = []
    if not isinstance(condition, dict) or not condition:
        return False, ["no condition defined"]

    for mode in ("all", "any"):
        if mode not in condition:
            continue
        clauses = condition.get(mode)
        if not isinstance(clauses, list) or not clauses:
            return False, ["%s has no clauses" % mode]
        results = []
        for clause in clauses:
            if not isinstance(clause, dict):
                results.append(False)
                reasons.append("clause is not an object")
                continue
            field = clause.get("field")
            op = clause.get("op", "eq")
            expected = clause.get("value")
            actual = _get_field(context, field)
            ok = _compare(actual, op, expected)
            results.append(ok)
            reasons.append("%s %s %r -> %s (actual %r)" % (field, op, expected, ok, actual))
        matched = all(results) if mode == "all" else any(results)
        return matched, reasons

    return False, ["condition must use 'all' or 'any'"]


def _compare(actual, op, expected):
    """One comparison. Every branch is defensive: a context value of the wrong type must evaluate
    False, not raise inside a page render."""
    if op == "is_set":
        return actual is not None and actual != ""
    if op == "is_empty":
        return actual is None or actual == ""
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return isinstance(expected, (list, tuple, set)) and actual in expected
    if op == "not_in":
        return isinstance(expected, (list, tuple, set)) and actual not in expected
    if op == "contains":
        return isinstance(actual, str) and isinstance(expected, str) and expected in actual
    if op in ("gt", "gte", "lt", "lte"):
        try:
            left, right = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {"gt": left > right, "gte": left >= right,
                "lt": left < right, "lte": left <= right}[op]
    return False


def evaluate_rules(tenant, module_slug, trigger, context, *, log=False, user=None):
    """Return the ACTIVE rules for this module+trigger whose conditions match, in priority order.

    Nothing is executed. The caller reads `rule.action` / `rule.action_payload` and decides; if it
    passes `log=True` the evaluation is recorded, and the caller can then set `action_taken` on the
    returned log rows to say what it did. That split is what keeps a platform rules engine from
    silently mutating another module's data.
    """
    from .models import BusinessRule, BusinessRuleLog

    matches = []
    for rule in (BusinessRule.objects
                 .filter(tenant=tenant, module_slug=module_slug, trigger=trigger, is_active=True)
                 .order_by("priority", "name")):
        ok, reasons = evaluate_condition(rule.condition, context)
        if not ok:
            continue
        entry = {"rule": rule, "action": rule.action, "payload": rule.action_payload,
                 "reasons": reasons, "log": None}
        if log:
            entry["log"] = BusinessRuleLog.objects.create(
                tenant=tenant, rule=rule, module_slug=module_slug, trigger=trigger,
                context=context, matched=True, evaluated_by=user,
            )
        matches.append(entry)
    return matches
