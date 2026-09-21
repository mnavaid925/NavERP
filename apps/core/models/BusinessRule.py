"""core — 0.11 bullet 4: the Business Rules Engine.

crm 1.10 already has a `WorkflowRule` that evaluates conditions for CRM records. This is the
PLATFORM-level equivalent: one registry any module can consult, so a rule about procurement approval
thresholds does not have to live in crm.

**What this does and does not do — the distinction is the point.**

It RECORDS a rule and EVALUATES it on request: `evaluate_rules()` returns the rules whose conditions
matched a context, in priority order, with their recommended action. That is a real decision-support
engine and it is fully testable.

It does NOT execute the action. There is no cross-module action executor here, and building one would
mean this app reaching into 71 approval engines and mutating their rows — the L36 mistake at the
largest scale, and a silent data change nobody asked for. So the caller acts, and reports what it did
via `BusinessRuleLog.action_taken`. A rule whose action nothing performs is still useful — it makes
the policy explicit and the log shows it was consulted — but the page says so rather than implying
enforcement.
"""
from apps.core.models._base import *  # noqa: F401,F403


class BusinessRule(models.Model):
    """An if-then rule: a condition over a context, and a recommended action."""

    TRIGGER_CHOICES = [
        ("on_create", "On create"),
        ("on_update", "On update"),
        ("on_status_change", "On status change"),
        ("on_approval", "On approval decision"),
        ("on_evaluation", "On manual evaluation"),
    ]
    ACTION_CHOICES = [
        ("flag", "Flag for attention"),
        ("require_approval", "Require an approval"),
        ("notify_role", "Notify a role"),
        ("block", "Block the operation"),
        ("set_field", "Set a field"),
    ]
    #: The comparison operators `evaluate_condition()` understands. Kept small and explicit: a
    #: condition language nobody can enumerate is one nobody can audit.
    OPERATORS = ("eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "is_set", "is_empty")

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="business_rules", db_index=True)
    name = models.CharField(max_length=200)
    module_slug = models.CharField(max_length=40)
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default="on_create")
    #: `{"all": [{"field": "amount", "op": "gt", "value": 10000}, ...]}` or `{"any": [...]}`.
    #: JSON rather than a DSL: the shape is inspectable in the DB and the evaluator is 30 lines.
    condition = models.JSONField(default=dict, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default="flag")
    #: What the action needs — a role id for `notify_role`, a field/value pair for `set_field`.
    action_payload = models.JSONField(default=dict, blank=True)
    #: Lower fires first. Matters when two rules match and their actions conflict.
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "module_slug", "trigger"], name="brule_tenant_mod_trig_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_trigger_display()} → {self.get_action_display()})"


class BusinessRuleLog(models.Model):
    """One evaluation: what was consulted, what matched, and what the CALLER did about it."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="business_rule_logs", db_index=True)
    #: SET_NULL, not CASCADE: the log is the evidence that a rule fired, and it must survive the rule
    #: being retired — otherwise deleting a rule would erase the record of what it did.
    rule = models.ForeignKey("core.BusinessRule", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="logs")
    module_slug = models.CharField(max_length=40)
    trigger = models.CharField(max_length=20)
    context = models.JSONField(default=dict, blank=True)
    matched = models.BooleanField(default=False)
    #: What the caller says it did. Free text because the action belongs to the calling module; this
    #: app never performs it, so it cannot know more than it is told.
    action_taken = models.CharField(max_length=255, blank=True)
    evaluated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="+")
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-evaluated_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "-evaluated_at"], name="brlog_tenant_at_idx"),
            models.Index(fields=["tenant", "module_slug"], name="brlog_tenant_module_idx"),
        ]

    def __str__(self):
        return f"{self.module_slug} · {self.trigger} · {'matched' if self.matched else 'no match'}"
