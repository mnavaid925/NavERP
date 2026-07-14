"""CRM 1.10 Automation & Workflow Engine — _engine views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ApprovalRequest,
    Case,
    ContractDocument,
    Expense,
    HealthScore,
    Lead,
    Opportunity,
    Webhook,
    WebhookDelivery,
    WorkflowLog,
)


# ---- 1.10 Workflow execution engine + Webhooks ------------------------------------------
_RULE_ENTITY_MODELS = {
    "lead": Lead, "opportunity": Opportunity, "case": Case, "expense": Expense,
    "contract": ContractDocument, "health_score": HealthScore,
}


_RULE_RUN_LIMIT = 50  # cap records evaluated per manual run (bounded engine)


def _safe_record_field(record, name):
    """Read a stored column value off a record for condition evaluation. SAFE: allowlist — only the
    model's concrete, NON-relation DB columns are readable (by attname). This rejects dunder/private
    names, methods, @property getters, FK objects/managers, and any security-bearing token field that
    isn't a plain column; it also means iterating records can't trigger a per-record FK lazy-load
    (security-review)."""
    if not name:
        return None
    allowed = {f.attname for f in record._meta.concrete_fields if not f.is_relation}
    if name not in allowed:
        return None
    return getattr(record, name, None)


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
    """Record a (signed) delivery for a webhook. The real outbound HTTP POST is **deferred**."""
    # WARNING (SSRF): when implementing the real POST: (1) https-only scheme; (2) resolve the host
    # ONCE, reject private/loopback/link-local/169.254.169.254 (cloud-metadata) ranges, then connect
    # to the PINNED resolved IP — do NOT re-resolve at connect time (prevents DNS rebinding); (3) allow
    # port 443 only (block internal port scans); (4) disable redirects; (5) short connect+read timeout;
    # (6) cap the response read + never log/store the body. Never POST to a raw user-supplied URL without that.
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
    # Hoist the (constant) active-webhook set out of the record loop — no per-record N+1 (code-review).
    active_webhooks = list(Webhook.objects.filter(
        tenant=rule.tenant, is_active=True,
        trigger_entity=rule.trigger_entity, trigger_event=rule.trigger_event))
    # _safe_record_field reads only concrete non-relation columns (already loaded with the row), so
    # iterating records never triggers a per-record FK lazy-load — no select_related needed (perf+security-review).
    records = Model.objects.filter(tenant=rule.tenant).order_by("-id")[:_RULE_RUN_LIMIT]
    for rec in records:
        summary["evaluated"] += 1
        if not _eval_conditions(rec, rule.conditions):
            continue
        summary["matched"] += 1
        label = str(rec)[:255]
        try:
            # Per-record savepoint: a DB error here rolls back only this record, so the failure
            # WorkflowLog below still commits (a poisoned shared atomic would lose it — code-review).
            with transaction.atomic():
                for action in actions:
                    atype = (action.get("type") if isinstance(action, dict) else "") or ""
                    params = action.get("params", {}) if isinstance(action, dict) else {}
                    if atype == "webhook":
                        for wh in active_webhooks:
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
