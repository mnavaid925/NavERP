"""core — 0.11 bullets 1, 2 and 5: the workflow registry, approval limits and process monitoring.

**0.11 does NOT declare a workflow engine, and that is the whole design.** The repo already contains
~71 approval/workflow/escalation models across crm, hrm, inventory, procurement, projects and scm —
`procurement.ApprovalRoutingRule`, `procurement.EscalationPolicy`, `crm.WorkflowRule`,
`inventory.TransferApproval`, `hrm.OfferApproval`, `projects.ProjectApprovalGate`, and more. Each of
those engines decides its own routing and writes its own decision rows, and a platform engine that
tried to own those decisions would be the L36 mistake at the largest possible scale.

So 0.11 owns the three things NOBODY owns:

1. **The registry** — `WorkflowDefinition` + `WorkflowStep` say which workflows exist, which engine
   backs each one, and what routing it is *supposed* to follow. That is bullet 1's "process modelling"
   and bullet 2's "hierarchies" as DOCUMENTATION of the engines, which is what an operator actually
   needs and what nothing else provides.
2. **The platform-level limits and SLA rules** — `ApprovalLimit` and `SlaRule`. Procurement 6.3 has an
   `EscalationPolicy` for procurement; there is no equivalent for the other modules.
3. **Process monitoring** — a COMPUTED board that reads the real approval tables
   (`apps/core/workflow.py` enumerates twelve of them) and reports backlog, aging and bottlenecks.

`WorkflowStep` is deliberately NOT enforced. A step that claimed to control routing would be a second
source of truth against the engine that actually decides.
"""
from apps.core.models._base import *  # noqa: F401,F403


class WorkflowDefinition(models.Model):
    """One business process, and which existing engine backs it."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="workflow_definitions", db_index=True)
    name = models.CharField(max_length=200)
    module_slug = models.CharField(max_length=40)
    #: The model that actually holds this process's decision rows, as `app_label.Model`. A STRING,
    #: not a ContentType FK: the registry must be able to describe a process whose model is
    #: registered later, and a data map of workflows is about intent, not about a live row.
    engine_label = models.CharField(
        max_length=120, blank=True,
        help_text="The model holding the decision rows, e.g. procurement.RequisitionApproval.")
    description = models.TextField(blank=True)
    owner_role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="owned_workflows",
                                   help_text="Who owns this process, not who approves in it.")
    is_active = models.BooleanField(default=True)
    #: How long this process should take. Used by the monitoring board to flag aging items, and it is
    #: a RECORDED target — nothing escalates on it (see `SlaRule` for that, which is also recorded).
    target_hours = models.PositiveIntegerField(default=48)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["module_slug", "name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "module_slug"], name="wfdef_tenant_module_idx")]

    @property
    def is_monitored(self):
        """True when `engine_label` names one of the tables the monitoring board actually reads."""
        from apps.core.workflow import monitored_labels
        return bool(self.engine_label) and self.engine_label in monitored_labels()

    def __str__(self):
        return f"{self.name} ({self.module_slug})"


class WorkflowStep(models.Model):
    """One step of a process, as DOCUMENTATION of what the backing engine does.

    Not enforced. `approver_role` records who the engine routes to; it does not make the engine route
    there. Stated on the page so the register cannot be mistaken for a control.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="workflow_steps", db_index=True)
    definition = models.ForeignKey("core.WorkflowDefinition", on_delete=models.CASCADE,
                                   related_name="steps")
    sequence = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=200)
    approver_role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="workflow_steps")
    #: A parallel step is taken at the same time as its siblings in the same sequence number.
    is_parallel = models.BooleanField(default=False)
    #: The value above which this step is required. Null means "always".
    threshold_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["definition", "sequence", "id"]
        unique_together = ("definition", "sequence", "name")
        indexes = [models.Index(fields=["tenant", "definition"], name="wfstep_tenant_def_idx")]

    def __str__(self):
        return f"{self.definition.name} · {self.sequence}. {self.name}"


class ApprovalLimit(models.Model):
    """A platform-level approval threshold: how much this role may approve in this module.

    Records the authority. Nothing here blocks an approval — each module's engine decides — so the
    page says the limit is a reference and the monitoring board is where a breach would be seen.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="approval_limits", db_index=True)
    module_slug = models.CharField(max_length=40)
    role = models.ForeignKey("accounts.Role", on_delete=models.CASCADE, related_name="approval_limits")
    max_amount = models.DecimalField(max_digits=14, decimal_places=2,
                                     help_text="Above this, the approval must escalate.")
    currency_code = models.CharField(max_length=8, blank=True, default="USD")
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module_slug", "role__name"]
        unique_together = ("tenant", "module_slug", "role")
        indexes = [models.Index(fields=["tenant", "module_slug"], name="aplimit_tenant_module_idx")]

    def __str__(self):
        return f"{self.module_slug} · {self.role} ≤ {self.max_amount}"


class SlaRule(models.Model):
    """A generic escalation rule. Procurement 6.3 has one for procurement; this is the platform's.

    **Records an intended response, and nothing acts on it.** The repo has no scheduler, so a rule
    that claimed to auto-approve after N hours would be a promise nothing keeps. The `action` is what
    an operator is told should happen, and the monitoring board shows what is actually overdue.
    """

    ACTION_CHOICES = [
        ("remind", "Remind the approver"),
        ("escalate", "Escalate to the next tier"),
        ("auto_approve", "Auto-approve on timeout"),
        ("auto_reject", "Auto-reject on timeout"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="sla_rules", db_index=True)
    name = models.CharField(max_length=200)
    module_slug = models.CharField(max_length=40)
    engine_label = models.CharField(max_length=120, blank=True,
                                    help_text="Optional: restrict the rule to one engine.")
    hours = models.PositiveIntegerField(help_text="Hours after which the rule fires.")
    action = models.CharField(max_length=12, choices=ACTION_CHOICES, default="remind")
    escalate_to_role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="sla_rules")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module_slug", "hours"]
        indexes = [models.Index(fields=["tenant", "module_slug"], name="slarule_tenant_module_idx")]

    def __str__(self):
        return f"{self.name} ({self.hours}h → {self.get_action_display()})"
