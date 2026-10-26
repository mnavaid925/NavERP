# CONTRACT — Sales 8.17 Workflow & Process Automation (FROZEN, pre-build)

Module 8 (`sales`), sub-module 8.17. This file is the build contract for Phase 3.3/3.4. Every name,
message, field, context key, route and file path below is PINNED — verified against real code on
BASE `15b30066` (plan at `.claude/tasks/todo.md` lines 17531–17816). Where this contract and the
plan disagree, **this contract wins** (it was resolved against the code); see "Deviations from the
plan" at the end. Do not re-litigate pinned decisions. Do not invent names not listed here.

**Next migration: `0031`** — verified `apps/sales/migrations/` ends at
`0030_contractobligation_sales_obl_ten_sub_idx_and_more.py`. Re-verify the number at generation
time (L43/L51/L53) and run `django.core.checks.run_checks()` in-process BEFORE `makemigrations` (L65).

---

## 0. File map

NEW files (create in this order, entity by entity — models → forms → views → urls → templates per entity):

```
apps/sales/models/WorkflowProcessAutomation/__init__.py
apps/sales/models/WorkflowProcessAutomation/SalesProcessDefinitions.py
apps/sales/models/WorkflowProcessAutomation/SalesAssignmentRules.py
apps/sales/models/WorkflowProcessAutomation/SalesApprovalDecisions.py
apps/sales/models/WorkflowProcessAutomation/SalesAlertTriggers.py
apps/sales/forms/WorkflowProcessAutomation/__init__.py
apps/sales/forms/WorkflowProcessAutomation/SalesProcessDefinitions.py
apps/sales/forms/WorkflowProcessAutomation/SalesAssignmentRules.py
apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py
apps/sales/forms/WorkflowProcessAutomation/SalesAlertTriggers.py
apps/sales/views/WorkflowProcessAutomation/__init__.py
apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py
apps/sales/views/WorkflowProcessAutomation/SalesAssignmentRules.py
apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py
apps/sales/views/WorkflowProcessAutomation/SalesAlertTriggers.py
apps/sales/urls/WorkflowProcessAutomation/__init__.py
apps/sales/urls/WorkflowProcessAutomation/SalesProcessDefinitions.py
apps/sales/urls/WorkflowProcessAutomation/SalesAssignmentRules.py
apps/sales/urls/WorkflowProcessAutomation/SalesApprovalDecisions.py
apps/sales/urls/WorkflowProcessAutomation/SalesAlertTriggers.py
templates/sales/workflowprocessautomation/salesprocessdefinition/{list,detail,form}.html
templates/sales/workflowprocessautomation/salesassignmentrule/{list,detail,form}.html
templates/sales/workflowprocessautomation/salesapprovaldecision/{list,detail,form}.html
templates/sales/workflowprocessautomation/salesalerttrigger/{list,detail,form}.html
```

EDITED shared files (Integrate only, surgical Edit — never rewrite; L43/L59):

```
apps/sales/models/__init__.py          (re-export block + __all__ additions)
apps/sales/forms/__init__.py           (re-export block + __all__ additions)
apps/sales/views/__init__.py           (re-export block + startswith prefixes)
apps/sales/urls/__init__.py            (import + concatenation)
apps/sales/admin.py                    (4 ModelAdmins appended + import extension)
apps/core/navigation.py                (LIVE_LINKS["8.17"] entry)
apps/sales/management/commands/seed_sales.py   (_seed_workflow_process_automation)
apps/sales/migrations/0031_*.py        (generated)
```

Global conventions: absolute imports only inside the packages; docstring header on every new file
(`"""Sales 8.17 — <Entity> <layer>."""`); after writing each Python file run
`venv\Scripts\python.exe -c "import ast; ast.parse(open(r'<path>', encoding='utf-8').read())"` (L64).
`tenant` FK is inherited from `TenantOwned`/`TenantNumbered` — NEVER redeclare it. Numbering via
`TenantNumbered` (`NUMBER_PREFIX` + race-safe `next_number`, raises `IntegrityError` after 5
collisions — L62); never hand-roll numbers. Audit via `write_audit_log(user, obj, action,
changes=None, tenant=None)` from `apps.core.utils` — there is NO `log_action` (plan §h).

Verified FK targets (all grep-checked): `accounts.User` / `accounts.Role` (Role: tenant FK, name —
**no `is_active` field**), `crm.Lead` / `crm.Opportunity` / `crm.Case` / `crm.Territory` (Territory
has `manager` FK and `is_active`), `scm.SalesOrder`, `sales.CPQQuote` (has `header_discount_pct`,
`approval_status`, `approval_rule`, `approved_by`, `approved_at`, `approval_note`, `owner`),
`sales.OrderHold`, `sales.CustomerContract`, `sales.CustomerSubscription`, `sales.QuoteApprovalRule`
(`approver_role` is a **CharField**, NOT a Role FK; no `required_tiers` field anywhere in sales),
`sales.MobileDealAlert`, `core.JobDefinition`, `core.NotificationRule` (tenant FK present),
`core.WorkflowDefinition` (**has a tenant FK** → registry row is per-tenant, seeded, not Integrate).

Related-name registry check: `grep -rn "sales_wpa" apps/` → **zero hits**; every `sales_wpa_*`
related_name below is free. Module-level constant names `TARGET_ENTITY_CHOICES`,
`TARGET_KIND_CHOICES`, `PROCESS_NODE_TYPES`, `SAT_TO_MDA_ALERT_TYPE`,
`validate_process_conditions`, `validate_process_nodes` are free in `apps/sales/`.
**CAUTION:** `apps/sales/models/__init__.py` already re-exports a module-level `ALERT_TYPE_CHOICES`
(8.16). Therefore ALL 8.17 choices constants are CLASS attributes except the four module-level
names listed above.

---

## 1. Models

All four extend `TenantNumbered` (`from apps.sales.models._base import TenantNumbered` — explicit
import, 8.16 style, NOT `import *`). Base gives: `tenant` FK, `number` Char(20) `editable=False`,
`created_at`, `updated_at` (auto_now — include `"updated_at"` in every `save(update_fields=[...])`).

### 1.1 `apps/sales/models/WorkflowProcessAutomation/SalesProcessDefinitions.py`

Module header imports:

```python
import json
import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered
```

Module-level constants (PINNED — shared with SAR/SAT/views via absolute import):

```python
TARGET_ENTITY_CHOICES = [
    ("lead", "Lead"),
    ("opportunity", "Opportunity"),
    ("quote", "Quote"),
    ("order", "Order"),
    ("case", "Case"),
    ("contract", "Contract"),
    ("subscription", "Subscription"),
]

PROCESS_NODE_TYPES = {"approval", "assign", "notify", "update_field", "create_task", "wait", "branch"}

PROCESS_OPERATORS = {"eq", "ne", "in", "not_in", "contains", "icontains", "gt", "gte", "lt", "lte", "is_set", "is_empty"}
MAX_PROCESS_CONDITIONS = 20
MAX_PROCESS_JSON_BYTES = 16 * 1024
MAX_PROCESS_NODES = 20
MAX_NODE_PARAMS = 20
MAX_REQUIRED_FIELDS = 20
```

Helper functions (verbatim clones of the 8.1 helpers in
`apps/sales/models/LeadManagement/LeadRoutingRules.py` lines 23–41):

```python
def _reject_json_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _is_scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _relation_belongs_to_tenant(instance, field_name):
    if not instance.tenant_id:
        return True
    field = instance._meta.get_field(field_name)
    related_id = getattr(instance, f"{field_name}_id", None)
    if not related_id:
        return True
    related_model = field.remote_field.model
    return related_model._default_manager.filter(pk=related_id, tenant_id=instance.tenant_id).exists()
```

#### `validate_process_conditions(value, is_catch_all=False)`

Clone of `validate_routing_conditions` with IDENTICAL bounds and messages, except: the 8.1
`ROUTING_FIELDS` whitelist is DROPPED (8.17 conditions span 7 entities) — `field` may be any
non-empty str ≤ 255. Pinned error messages, in raise order:

1. str input that fails `json.loads(value, parse_constant=_reject_json_constant)` → `"Conditions must be valid JSON."`
2. not a list → `"Conditions must be a list."`
3. `len(value) > MAX_PROCESS_CONDITIONS` → `"A process rule may contain at most 20 conditions."`
4. empty list and `not is_catch_all` → `"An empty rule must be explicitly marked as a catch-all."`
5. `json.dumps(value, ensure_ascii=False, allow_nan=False)` raises → `"Conditions contain an unsupported value."`
6. encoded > `MAX_PROCESS_JSON_BYTES` → `"Conditions must be 16 KiB or smaller."`
7. item not dict or `set(condition) != {"field", "operator", "value"}` → `"Each condition must contain only field, operator, and value."`
8. field not str, empty, or > 255 → `"Condition fields must be 1 to 255 characters."`
9. operator not str or not in `PROCESS_OPERATORS` → `f"Unsupported condition operator: {operator}"`
10. `in`/`not_in`: value not list, empty, or > 20 → `"List operators require 1 to 20 scalar values."`; any non-scalar item → `"List operator values must be finite scalar values."`; any str item > 255 → `"Condition values must be 255 characters or fewer."`
11. `is_set`/`is_empty`: value not (bool or None) → `"Set operators accept only true, false, or null."`
12. other operators: not `_is_scalar(value)` → `"Condition values must be finite scalars or bounded lists."`
13. str value > 255 → `"Condition values must be 255 characters or fewer."`

Returns the normalized list of `{"field": ..., "operator": ..., "value": ...}` dicts.

#### `validate_process_nodes(value)`

```python
def validate_process_nodes(value):
    # str -> json.loads(parse_constant=_reject_json_constant); failures:
    #   "Nodes must be valid JSON."
    # not list -> "Nodes must be a list."
    # len > MAX_PROCESS_NODES -> "A process may contain at most 20 nodes."
    # json.dumps(allow_nan=False) failure -> "Nodes contain an unsupported value."
    # encoded > MAX_PROCESS_JSON_BYTES -> "Nodes must be 16 KiB or smaller."
    # per item:
    #   not dict or set(node) != {"seq", "type", "params"}
    #       -> "Each node must contain only seq, type, and params."
    #   seq not int (bool rejected) or < 1 or > 999
    #       -> "Node seq must be an integer from 1 to 999."
    #   type not str or not in PROCESS_NODE_TYPES -> f"Unsupported node type: {kind}"
    #   params not dict or len(params) > MAX_NODE_PARAMS
    #       -> "Node params must be a dict of at most 20 keys."
    #   param key not str / empty / > 100 -> "Node param keys must be 1 to 100 characters."
    #   key == "required_fields": must be list of <= MAX_REQUIRED_FIELDS strs each <= 255,
    #       else "required_fields must be at most 20 strings of 255 characters or fewer."
    #   other values: not _is_scalar -> "Node param values must be finite scalars."
    #   str value > 255 -> "Node param values must be 255 characters or fewer."
    # duplicate seq values -> "Node seq values must be unique."
    # returns normalized [{"seq": int, "type": str, "params": dict}]
```

#### `SalesProcessDefinition(TenantNumbered)` — `NUMBER_PREFIX = "SPD"`

Class attributes:

```python
STATUS_CHOICES = [("draft", "Draft"), ("active", "Active"), ("paused", "Paused"), ("archived", "Archived")]
TRIGGER_EVENT_CHOICES = [
    ("created", "Record Created"),
    ("updated", "Record Updated"),
    ("stage_changed", "Stage Changed"),
    ("field_value", "Field Matches Value"),
    ("date_reached", "Date Reached"),
    ("inactivity", "Inactivity Window"),
]
```

| Field | Definition (exact) |
|---|---|
| `name` | `models.CharField(max_length=200)` |
| `description` | `models.TextField(blank=True)` |
| `version` | `models.PositiveIntegerField(default=1)` — system-managed; NEVER on a form; bumped by the edit view on status change |
| `status` | `models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")` |
| `target_entity` | `models.CharField(max_length=16, choices=TARGET_ENTITY_CHOICES)` — required, no default |
| `trigger_event` | `models.CharField(max_length=16, choices=TRIGGER_EVENT_CHOICES, default="created")` |
| `trigger_field` | `models.CharField(max_length=100, blank=True)` |
| `trigger_value` | `models.CharField(max_length=200, blank=True)` |
| `conditions` | `models.JSONField(default=list, blank=True)` — validated in `clean()` |
| `nodes` | `models.JSONField(default=list, blank=True)` — validated in `clean()` |
| `max_enrollments` | `models.PositiveSmallIntegerField(default=1)` |
| `priority` | `models.PositiveSmallIntegerField(default=100)` |
| `is_active` | `models.BooleanField(default=True)` |
| `owner` | `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_wpa_owned_processes")` — set by the view to `request.user`, never on a form |
| `job_definition` | `models.ForeignKey("core.JobDefinition", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_wpa_process_jobs")` — scheduler-owned, never on a form |

```python
class Meta:
    ordering = ["priority", "name", "id"]
    indexes = [
        models.Index(fields=["tenant", "status"], name="sales_spd_tnt_status_idx"),
    ]

def clean(self):
    super().clean()
    self.conditions = validate_process_conditions(self.conditions, is_catch_all=True)
    self.nodes = validate_process_nodes(self.nodes)
    if self.trigger_event == "field_value":
        if not self.trigger_field:
            raise ValidationError({"trigger_field": "A field-value trigger needs a trigger field."})
        if not self.trigger_value:
            raise ValidationError({"trigger_value": "A field-value trigger needs a comparison value."})
    if not _relation_belongs_to_tenant(self, "owner"):
        raise ValidationError({"owner": "Choose an active user from this workspace."})
    if not _relation_belongs_to_tenant(self, "job_definition"):
        raise ValidationError({"job_definition": "Choose a job definition from this workspace."})

def __str__(self):
    return f"{self.number} — {self.name}"
```

### 1.2 `apps/sales/models/WorkflowProcessAutomation/SalesAssignmentRules.py`

Imports: `from django.conf import settings`, `from django.core.exceptions import ValidationError`,
`from django.db import models`, `from apps.accounts.models import User`,
`from apps.sales.models._base import TenantNumbered`, and
`from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import _relation_belongs_to_tenant, validate_process_conditions`.
(`_relation_belongs_to_tenant` is imported, not re-cloned — single source of truth inside the package.)

#### `SalesAssignmentRule(TenantNumbered)` — `NUMBER_PREFIX = "SAR"`

Class attributes:

```python
TARGET_ENTITY_CHOICES = [("lead", "Lead"), ("opportunity", "Opportunity"), ("case", "Case")]
MATCH_MODE_CHOICES = [("all", "All conditions"), ("any", "Any condition")]
ASSIGNMENT_MODE_CHOICES = [
    ("fixed_owner", "Fixed Owner"),
    ("round_robin", "Round Robin"),
    ("load_balanced", "Load Balanced"),
    ("territory_manager", "Territory Manager"),
    ("escalate_manager", "Escalate to Manager"),
]
```

(Class-level `TARGET_ENTITY_CHOICES` intentionally shadows the module-level import name inside this
class only — SAR targets the 3 CRM entities; for `lead` the resolver MUST delegate to 8.1's
`LeadRoutingRule` decision path, never re-decide a lead owner.)

| Field | Definition (exact) |
|---|---|
| `name` | `models.CharField(max_length=200)` |
| `target_entity` | `models.CharField(max_length=16, choices=TARGET_ENTITY_CHOICES)` |
| `match_mode` | `models.CharField(max_length=8, choices=MATCH_MODE_CHOICES, default="all")` |
| `conditions` | `models.JSONField(default=list, blank=True)` |
| `is_catch_all` | `models.BooleanField(default=False)` |
| `assignment_mode` | `models.CharField(max_length=20, choices=ASSIGNMENT_MODE_CHOICES)` — required, no default |
| `default_owner` | FK User, `SET_NULL, null=True, blank=True, related_name="sales_wpa_default_assignments"` |
| `eligible_owners` | `models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="sales_wpa_eligible_assignments")` |
| `fallback_owner` | FK User, `SET_NULL, null=True, blank=True, related_name="sales_wpa_fallback_assignments"` |
| `territory` | FK `"crm.Territory"`, `SET_NULL, null=True, blank=True, related_name="sales_wpa_assignment_rules"` |
| `max_open_records` | `models.PositiveSmallIntegerField(null=True, blank=True)` |
| `cursor` | `models.PositiveIntegerField(default=0, editable=False)` |
| `last_assigned_owner` | FK User, `SET_NULL, null=True, blank=True, editable=False, related_name="sales_wpa_last_assignments"` |
| `last_assigned_at` | `models.DateTimeField(null=True, blank=True, editable=False)` |
| `escalate_after_hours` | `models.PositiveSmallIntegerField(null=True, blank=True)` |
| `escalate_to` | FK User, `SET_NULL, null=True, blank=True, related_name="sales_wpa_escalation_assignments"` |
| `priority` | `models.PositiveSmallIntegerField(default=100)` |
| `is_active` | `models.BooleanField(default=True)` |

```python
class Meta:
    ordering = ["priority", "name", "id"]
    constraints = [models.UniqueConstraint(fields=["tenant", "name"], name="sales_sar_tnt_name_uniq")]
    indexes = [
        models.Index(fields=["tenant", "target_entity", "is_active"], name="sales_sar_tnt_entity_idx"),
    ]
```

`clean()` (8.1 `LeadRoutingRule.clean` shape; tenant guards are no-ops on the form path —
L49-addendum — the FORM clean() in §2.2 repeats them with the form-held tenant):

```python
def clean(self):
    super().clean()
    self.conditions = validate_process_conditions(self.conditions, self.is_catch_all)
    for field_name in ("default_owner", "fallback_owner", "escalate_to"):
        if not _relation_belongs_to_tenant(self, field_name):
            raise ValidationError({field_name: "Choose an active user from this workspace."})
        value = getattr(self, field_name, None)
        if value is not None and not value.is_active:
            raise ValidationError({field_name: "Choose an active user from this workspace."})
    if not _relation_belongs_to_tenant(self, "territory"):
        raise ValidationError({"territory": "Choose a territory from this workspace."})
    if self.assignment_mode == "fixed_owner" and not self.default_owner_id:
        raise ValidationError({"default_owner": "A fixed-owner rule needs a default owner."})
    if self.assignment_mode == "territory_manager" and not self.territory_id:
        raise ValidationError({"territory": "A territory-manager rule needs a territory."})
    if self.assignment_mode == "territory_manager" and self.territory_id and not self.territory.manager_id:
        raise ValidationError({"territory": "The selected territory has no manager."})
    if self.assignment_mode == "escalate_manager" and not self.escalate_to_id:
        raise ValidationError({"escalate_to": "An escalation rule needs an escalation target."})
    if self.assignment_mode == "escalate_manager" and not self.escalate_after_hours:
        raise ValidationError({"escalate_after_hours": "An escalation rule needs an escalation window."})
    if self.pk:
        invalid_owners = [owner for owner in self.eligible_owners.all() if owner.tenant_id != self.tenant_id or not owner.is_active]
        if invalid_owners:
            raise ValidationError({"eligible_owners": "Choose active owners from this workspace."})
        if self.assignment_mode == "round_robin" and not self.eligible_owners.exists():
            raise ValidationError({"eligible_owners": "A round-robin rule needs eligible owners."})
        if self.assignment_mode == "load_balanced" and not self.eligible_owners.exists():
            raise ValidationError({"eligible_owners": "A load-balanced rule needs eligible owners."})

def __str__(self):
    return self.name
```

### 1.3 `apps/sales/models/WorkflowProcessAutomation/SalesApprovalDecisions.py`

Imports: `from django.conf import settings`, `from django.core.exceptions import ValidationError`,
`from django.db import models`, `from apps.sales.models._base import TenantNumbered`.

Module-level constant:

```python
TARGET_KIND_CHOICES = [
    ("quote", "Quote"),
    ("order_hold", "Order Hold"),
    ("contract", "Contract"),
]
```

#### `SalesApprovalDecision(TenantNumbered)` — `NUMBER_PREFIX = "SAD"`

Pattern source: `apps/procurement/models/ApprovalWorkflowEngine/Approvals.py::RequisitionApproval`
— one immutable decision row per tier, snapshotted `tier_count`, "pending = absence of a row".

Class attributes:

```python
APPROVAL_KIND_CHOICES = [
    ("discount", "Discount"),
    ("credit", "Credit"),
    ("exception", "Exception"),
    ("contract", "Contract"),
]
DECISION_CHOICES = [("approved", "Approved"), ("rejected", "Rejected")]
```

| Field | Definition (exact) |
|---|---|
| `approval_kind` | `models.CharField(max_length=10, choices=APPROVAL_KIND_CHOICES)` — required |
| `quote` | FK `"sales.CPQQuote"`, `PROTECT, null=True, blank=True, related_name="sales_wpa_quote_decisions"` |
| `order_hold` | FK `"sales.OrderHold"`, `PROTECT, null=True, blank=True, related_name="sales_wpa_order_hold_decisions"` |
| `contract` | FK `"sales.CustomerContract"`, `PROTECT, null=True, blank=True, related_name="sales_wpa_contract_decisions"` |
| `target_key` | `models.CharField(max_length=40, editable=False, blank=True, default="")` — computed `"<kind>:<pk>"` |
| `record_label` | `models.CharField(max_length=200, blank=True)` |
| `approval_rule` | FK `"sales.QuoteApprovalRule"`, `SET_NULL, null=True, blank=True, related_name="sales_wpa_decisions"` |
| `tier` | `models.PositiveSmallIntegerField()` |
| `tier_count` | `models.PositiveSmallIntegerField()` |
| `approver_role` | FK `"accounts.Role"`, `SET_NULL, null=True, blank=True, related_name="sales_wpa_role_decisions"` |
| `approver` | FK User, `SET_NULL, null=True, blank=True, related_name="sales_wpa_decided"` |
| `decision` | `models.CharField(max_length=8, choices=DECISION_CHOICES)` — required |
| `comment` | `models.TextField(blank=True)` |
| `requested_by` | FK User, `SET_NULL, null=True, blank=True, related_name="sales_wpa_requested"` |
| `requested_at` | `models.DateTimeField(null=True, blank=True)` |
| `due_at` | `models.DateTimeField(null=True, blank=True)` |
| `decided_at` | `models.DateTimeField(auto_now_add=True, editable=False)` |

```python
class Meta:
    ordering = ["target_key", "tier", "id"]   # deterministic — L61
    constraints = [
        models.UniqueConstraint(fields=["tenant", "target_key", "tier"], name="sales_sad_tnt_tgt_tier_uniq"),
    ]
    indexes = [
        models.Index(fields=["tenant", "decision"], name="sales_sad_tnt_decision_idx"),
    ]
```

Methods (PINNED):

```python
TARGET_FIELDS = (("quote", "quote_id"), ("order_hold", "order_hold_id"), ("contract", "contract_id"))

def compute_target_key(self):
    for kind, attr in self.TARGET_FIELDS:
        pk = getattr(self, attr, None)
        if pk:
            return f"{kind}:{pk}"
    return ""

def save(self, *args, **kwargs):
    self.target_key = self.compute_target_key()
    super().save(*args, **kwargs)

@property
def is_final_tier(self):
    return self.tier >= self.tier_count

def clean(self):
    super().clean()
    targets = sum(1 for _, attr in self.TARGET_FIELDS if getattr(self, attr, None))
    if targets != 1:
        raise ValidationError("Set exactly one approval target (quote, order hold, or contract).")
    if self.tier_count and self.tier > self.tier_count:
        raise ValidationError({"tier": "A tier cannot exceed the chain length."})

@classmethod
def record(cls, tenant, *, quote=None, order_hold=None, contract=None, approval_kind,
           tier, tier_count, decision, approver=None, approver_role=None, approval_rule=None,
           requested_by=None, requested_at=None, due_at=None, record_label="", comment=""):
    """Append one decision row — called INSIDE the deciding view's atomic block (procurement pattern)."""
    return cls.objects.create(
        tenant=tenant, quote=quote, order_hold=order_hold, contract=contract,
        approval_kind=approval_kind, tier=tier, tier_count=tier_count, decision=decision,
        approver=approver, approver_role=approver_role, approval_rule=approval_rule,
        requested_by=requested_by, requested_at=requested_at, due_at=due_at,
        record_label=(record_label or "")[:200], comment=(comment or "")[:2000])

def __str__(self):
    return f"{self.number or 'SAD'} · {self.target_key} tier {self.tier}/{self.tier_count} {self.decision}"
```

L57: never `annotate()` an alias named `is_final_tier` (it is a `@property`).

### 1.4 `apps/sales/models/WorkflowProcessAutomation/SalesAlertTriggers.py`

Imports: `from django.conf import settings`, `from django.core.exceptions import ValidationError`,
`from django.db import models`, `from django.utils import timezone`,
`from apps.sales.models._base import TenantNumbered`, and
`from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import TARGET_ENTITY_CHOICES, _relation_belongs_to_tenant, validate_process_conditions`.

Module-level constant (8.16 `MobileDealAlert.ALERT_TYPE_CHOICES` is CLOSED — every SAT type maps
to an existing MDA value; verified against `apps/sales/models/MobileSales/MobileDealAlerts.py`):

```python
SAT_TO_MDA_ALERT_TYPE = {
    "deal_inactivity": "checkin_reminder",
    "stage_change": "deal_stage_changed",
    "milestone": "attainment_milestone",
    "approval_requested": "quote_approval_required",
    "sla_breach": "checkin_reminder",
    "contract_expiry": "contract_expiring",
    "quota_attainment": "attainment_milestone",
}
```

#### `SalesAlertTrigger(TenantNumbered)` — `NUMBER_PREFIX = "SAT"`

Class docstring (MANDATORY — records the user-ruled divergence):

```python
class SalesAlertTrigger(TenantNumbered):
    """Sales-scoped alert trigger.

    AUDIENCE_KIND_CHOICES is a sales-scoped variant of core.NotificationRule.AUDIENCE_CHOICES
    (Notification.py:95 = role / user / party / all): here ``owner`` (the record's owning rep)
    REPLACES core's ``party``, because a sales alert audience is the deal owner, not the
    customer party. This divergence is intentional, not drift.
    """
```

Class attributes:

```python
ALERT_TYPE_CHOICES = [
    ("deal_inactivity", "Deal Inactivity"),
    ("stage_change", "Stage Change"),
    ("milestone", "Milestone Reached"),
    ("approval_requested", "Approval Requested"),
    ("sla_breach", "SLA Breach"),
    ("contract_expiry", "Contract Expiry"),
    ("quota_attainment", "Quota Attainment"),
]
SEVERITY_CHOICES = [
    ("low", "Low Priority"),
    ("normal", "Normal"),
    ("high", "High Priority"),
    ("urgent", "Urgent Action Required"),
]
AUDIENCE_KIND_CHOICES = [
    ("role", "Everyone holding a role"),
    ("user", "Named users"),
    ("owner", "The record owner"),
    ("all", "Everyone in the workspace"),
]
```

(`SEVERITY_CHOICES` values mirror `MobileDealAlert.URGENCY_CHOICES` exactly so `severity` can be
written straight into `MobileDealAlert.urgency`.)

| Field | Definition (exact) |
|---|---|
| `name` | `models.CharField(max_length=200)` |
| `alert_type` | `models.CharField(max_length=24, choices=ALERT_TYPE_CHOICES, default="deal_inactivity")` |
| `target_entity` | `models.CharField(max_length=16, choices=TARGET_ENTITY_CHOICES)` |
| `conditions` | `models.JSONField(default=list, blank=True)` |
| `inactivity_days` | `models.PositiveSmallIntegerField(null=True, blank=True)` |
| `severity` | `models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="normal")` |
| `audience_kind` | `models.CharField(max_length=10, choices=AUDIENCE_KIND_CHOICES, default="all")` |
| `audience_role` | FK `"accounts.Role"`, `SET_NULL, null=True, blank=True, related_name="sales_wpa_audience_roles"` |
| `audience_users` | `models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="sales_wpa_alert_audiences")` |
| `notification_rule` | FK `"core.NotificationRule"`, `SET_NULL, null=True, blank=True, related_name="sales_wpa_alert_triggers"` |
| `cooldown_hours` | `models.PositiveSmallIntegerField(default=24)` |
| `last_evaluated_at` | `models.DateTimeField(null=True, blank=True, editable=False)` |
| `last_fired_at` | `models.DateTimeField(null=True, blank=True, editable=False)` |
| `fire_count` | `models.PositiveIntegerField(default=0, editable=False)` |
| `priority` | `models.PositiveSmallIntegerField(default=100)` |
| `is_active` | `models.BooleanField(default=True)` |

```python
class Meta:
    ordering = ["priority", "name", "id"]
    indexes = [
        models.Index(fields=["tenant", "alert_type", "is_active"], name="sales_sat_tnt_type_idx"),
    ]

def is_on_cooldown(self, now=None):
    if self.last_fired_at is None:
        return False
    now = now or timezone.now()
    return self.last_fired_at + timezone.timedelta(hours=self.cooldown_hours) > now

def mark_evaluated(self, now=None):
    self.last_evaluated_at = now or timezone.now()
    self.save(update_fields=["last_evaluated_at", "updated_at"])

def mark_fired(self, now=None):
    now = now or timezone.now()
    self.last_fired_at = now
    self.last_evaluated_at = now
    self.fire_count += 1
    self.save(update_fields=["last_fired_at", "last_evaluated_at", "fire_count", "updated_at"])

def clean(self):
    super().clean()
    self.conditions = validate_process_conditions(self.conditions, is_catch_all=True)
    if not _relation_belongs_to_tenant(self, "audience_role"):
        raise ValidationError({"audience_role": "Choose a role from this workspace."})
    if not _relation_belongs_to_tenant(self, "notification_rule"):
        raise ValidationError({"notification_rule": "Choose a notification rule from this workspace."})
    if self.audience_kind == "role" and not self.audience_role_id:
        raise ValidationError({"audience_role": "A role-audience trigger needs a role."})
    if self.alert_type in {"deal_inactivity", "sla_breach"} and not self.inactivity_days:
        raise ValidationError({"inactivity_days": "An inactivity trigger needs a day window."})
    if self.pk and self.audience_kind == "user" and not self.audience_users.exists():
        raise ValidationError({"audience_users": "A user-audience trigger needs at least one recipient."})

def __str__(self):
    return f"{self.number} — {self.name}"
```

### 1.5 Package `__init__` — `apps/sales/models/WorkflowProcessAutomation/__init__.py`

```python
from .SalesAlertTriggers import SAT_TO_MDA_ALERT_TYPE, SalesAlertTrigger
from .SalesApprovalDecisions import TARGET_KIND_CHOICES, SalesApprovalDecision
from .SalesAssignmentRules import SalesAssignmentRule
from .SalesProcessDefinitions import (
    PROCESS_NODE_TYPES,
    TARGET_ENTITY_CHOICES,
    SalesProcessDefinition,
    validate_process_conditions,
    validate_process_nodes,
)
```

---

## 2. Forms

All ModelForms inherit **`TenantModelForm` from `apps.core.forms`** (verified sibling:
`apps/sales/forms/MobileSales/MobileDealAlerts.py:5,18`). `TenantModelForm.__init__` takes
`tenant=None` and auto-applies `form-select` / `form-textarea` / `form-input` widget classes and
datetime-local/date widgets — declare widgets ONLY where deviating (placeholders, rows). Every
form uses an explicit `fields = [...]` list — never `exclude` (L22: system/derived fields are
structurally unrenderable). `apps/sales/forms/_common.py` provides `TenantUniqueMixin`,
`TenantActionForm` (`__init__(self, *args, tenant=None, **kwargs)` → `self.tenant`),
`_reject_foreign(form, cleaned, names)` (message: `"That record belongs to another workspace."`)
and `tenant_users(tenant)` (= `User.objects.filter(tenant=tenant, is_active=True)`).
**`accounts.Role` has NO `is_active` field** — narrow roles with `Role.objects.filter(tenant=self.tenant)` only.
No FilterForm classes ship (list views parse GET params by hand — §3).

### 2.1 `SalesProcessDefinitionForm(TenantModelForm)` — forms/WorkflowProcessAutomation/SalesProcessDefinitions.py

```python
class Meta:
    model = SalesProcessDefinition
    fields = [
        "name", "description", "status", "target_entity", "trigger_event",
        "trigger_field", "trigger_value", "conditions", "nodes",
        "max_enrollments", "priority", "is_active",
    ]
    widgets = {
        "conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 5,
            "placeholder": '[{"field": "status", "operator": "eq", "value": "open"}]'}),
        "nodes": forms.Textarea(attrs={"class": "form-textarea", "rows": 7,
            "placeholder": '[{"seq": 1, "type": "notify", "params": {}}]'}),
    }
```

(Excluded, never rendered: `tenant`, `number`, `version`, `owner`, `job_definition`,
`created_at`, `updated_at`.)

- `clean_conditions()`: `return validate_process_conditions(self.cleaned_data.get("conditions") or [], is_catch_all=True)` — validator `ValidationError`s propagate verbatim.
- `clean_nodes()`: `return validate_process_nodes(self.cleaned_data.get("nodes") or [])`.
- `clean()`: if `cleaned_data.get("trigger_event") == "field_value"`: missing `trigger_field` → `self.add_error("trigger_field", "A field-value trigger needs a trigger field.")`; missing `trigger_value` → `self.add_error("trigger_value", "A field-value trigger needs a comparison value.")`.

### 2.2 `SalesAssignmentRuleForm(TenantUniqueMixin, TenantModelForm)` — .../SalesAssignmentRules.py

`TenantUniqueMixin` enforces the `("tenant", "name")` uniqueness with the form-held tenant.

```python
class Meta:
    model = SalesAssignmentRule
    fields = [
        "name", "target_entity", "match_mode", "conditions", "is_catch_all",
        "assignment_mode", "default_owner", "eligible_owners", "fallback_owner",
        "territory", "max_open_records", "escalate_after_hours", "escalate_to",
        "priority", "is_active",
    ]
    widgets = {
        "conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 5,
            "placeholder": '[{"field": "status", "operator": "eq", "value": "open"}]'}),
    }
```

(Excluded: `tenant`, `number`, `cursor`, `last_assigned_owner`, `last_assigned_at`,
`created_at`, `updated_at`.)

- `__init__`: when `self.tenant is not None` narrow `default_owner`, `fallback_owner`,
  `escalate_to`, `eligible_owners` → `tenant_users(self.tenant)`; `territory` →
  `Territory.objects.filter(tenant=self.tenant, is_active=True)` (import
  `from apps.crm.models import Territory`).
- `clean_conditions()`: `return validate_process_conditions(self.cleaned_data.get("conditions") or [], self.cleaned_data.get("is_catch_all"))`.
- `clean()`: first `_reject_foreign(self, self.cleaned_data, ["default_owner", "fallback_owner", "escalate_to", "territory"])`; then mode checks (form path is authoritative — L49-addendum):
  - `fixed_owner` and no `default_owner` → `add_error("default_owner", "A fixed-owner rule needs a default owner.")`
  - `round_robin` and no `eligible_owners` → `add_error("eligible_owners", "A round-robin rule needs eligible owners.")`
  - `load_balanced` and no `eligible_owners` → `add_error("eligible_owners", "A load-balanced rule needs eligible owners.")`
  - `territory_manager` and no `territory` → `add_error("territory", "A territory-manager rule needs a territory.")`; territory set but `territory.manager_id` falsy → `add_error("territory", "The selected territory has no manager.")`
  - `escalate_manager` and no `escalate_to` → `add_error("escalate_to", "An escalation rule needs an escalation target.")`; no `escalate_after_hours` → `add_error("escalate_after_hours", "An escalation rule needs an escalation window.")`

### 2.3 `SalesApprovalDecisionForm(TenantModelForm)` — .../SalesApprovalDecisions.py (manual ledger entry, `_create` only)

```python
class Meta:
    model = SalesApprovalDecision
    fields = [
        "approval_kind", "quote", "order_hold", "contract", "record_label",
        "approval_rule", "tier", "tier_count", "approver_role", "approver",
        "decision", "comment", "requested_by", "requested_at", "due_at",
    ]
```

(Excluded: `tenant`, `number`, `target_key` (computed in `save()`), `decided_at` (auto — L22),
`created_at`, `updated_at`.)

- `__init__` narrowing (tenant-scoped): `quote` → `CPQQuote.objects.filter(tenant=self.tenant)`;
  `order_hold` → `OrderHold.objects.filter(tenant=self.tenant)`; `contract` →
  `CustomerContract.objects.filter(tenant=self.tenant)`; `approval_rule` →
  `QuoteApprovalRule.objects.filter(tenant=self.tenant)`; `approver_role` →
  `Role.objects.filter(tenant=self.tenant)` (NO is_active — Role lacks the field);
  `approver`, `requested_by` → `tenant_users(self.tenant)`.
- `clean()`: exactly one of `quote`/`order_hold`/`contract` in `cleaned_data`, else
  `raise ValidationError("Set exactly one approval target (quote, order hold, or contract).")`;
  `tier > tier_count` → `add_error("tier", "A tier cannot exceed the chain length.")`.
  Tenant membership is guaranteed by the narrowed querysets (no `_reject_foreign` needed).

### 2.4 `SalesApprovalDecisionEditForm(TenantModelForm)` — same file

```python
class Meta:
    model = SalesApprovalDecision
    fields = ["comment", "due_at"]
```

No clean methods. Used by `sales_approval_decision_edit` ONLY (the register is otherwise immutable).

### 2.5 `SalesApprovalDecisionActionForm(TenantActionForm)` — same file (approve/reject POST body)

```python
class SalesApprovalDecisionActionForm(TenantActionForm):
    target_kind = forms.ChoiceField(choices=TARGET_KIND_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}))
    target_id = forms.IntegerField(min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-input"}))
    approval_kind = forms.ChoiceField(required=False,
        choices=[("", "Auto (from target)")] + list(SalesApprovalDecision.APPROVAL_KIND_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}))
    tier_count = forms.IntegerField(required=False, min_value=1, max_value=9,
        widget=forms.NumberInput(attrs={"class": "form-input"}),
        help_text="Chain length; defaults to the longest existing chain for this target.")
    comment = forms.CharField(required=False, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}))
```

Import `TARGET_KIND_CHOICES` and `SalesApprovalDecision` from
`apps.sales.models.WorkflowProcessAutomation.SalesApprovalDecisions`. No clean methods —
target existence/tenancy is enforced in the deciding view via tenant-scoped
`get_object_or_404` (IDOR-safe).

### 2.6 `SalesAlertTriggerForm(TenantModelForm)` — .../SalesAlertTriggers.py

```python
class Meta:
    model = SalesAlertTrigger
    fields = [
        "name", "alert_type", "target_entity", "conditions", "inactivity_days",
        "severity", "audience_kind", "audience_role", "audience_users",
        "notification_rule", "cooldown_hours", "priority", "is_active",
    ]
    widgets = {
        "conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 5,
            "placeholder": '[{"field": "status", "operator": "eq", "value": "open"}]'}),
    }
```

(Excluded: `tenant`, `number`, `last_evaluated_at`, `last_fired_at`, `fire_count`,
`created_at`, `updated_at` — all derived, L22.)

- `__init__` narrowing: `audience_role` → `Role.objects.filter(tenant=self.tenant)`;
  `audience_users` → `tenant_users(self.tenant)`; `notification_rule` →
  `NotificationRule.objects.filter(tenant=self.tenant)` (import
  `from apps.core.models.Notification import NotificationRule`; tenant FK verified at Notification.py:107).
- `clean_conditions()`: `return validate_process_conditions(self.cleaned_data.get("conditions") or [], is_catch_all=True)`.
- `clean()`: `_reject_foreign(self, self.cleaned_data, ["audience_role", "notification_rule"])`;
  `audience_kind == "role"` without `audience_role` → `add_error("audience_role", "A role-audience trigger needs a role.")`;
  `audience_kind == "user"` without `audience_users` → `add_error("audience_users", "A user-audience trigger needs at least one recipient.")`;
  `alert_type in {"deal_inactivity", "sla_breach"}` without `inactivity_days` → `add_error("inactivity_days", "An inactivity trigger needs a day window.")`.

### 2.7 Package `__init__` — `apps/sales/forms/WorkflowProcessAutomation/__init__.py`

```python
from .SalesAlertTriggers import SalesAlertTriggerForm
from .SalesApprovalDecisions import (
    SalesApprovalDecisionActionForm,
    SalesApprovalDecisionEditForm,
    SalesApprovalDecisionForm,
)
from .SalesAssignmentRules import SalesAssignmentRuleForm
from .SalesProcessDefinitions import SalesProcessDefinitionForm
```

---

## 3. Views

Function-based, hand-written in the 8.15/8.16 style (NOT the `crud_*` helpers — their context keys
`object_list`/`obj` violate the pinned contract below). **`apps/sales/views/_common.py` does NOT
export `Q`, `F`, `transaction`, `Paginator`, `Max` or `ValidationError` (L54 §4)** — every view
file imports Django pieces explicitly. Common import spine per view file:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
```

Decorator stacks (copy 8.15 `CustomerContracts.py` verbatim — `tenant_admin_required` itself wraps
`login_required`, decorators.py:13–22):

- list / detail: `@login_required`
- create / edit: `@login_required` → `@tenant_admin_required` → `@transaction.atomic`
- delete / run / approve / reject: `@login_required` → `@require_POST` → `@tenant_admin_required` → `@transaction.atomic`

Pagination (L9): `page_obj = paginate(request, qs, 15)` from `apps.core.crud` — it attaches
`page.window`, which `templates/partials/pagination.html` REQUIRES. **No `is_paginated` key** (the
partial does not read it). Every list queryset is tenant-filtered and relies on the model Meta
ordering (deterministic — L61).

String-enum GET filters (L11/L44): build `valid = {value for value, _ in <CHOICES>}`; apply the
filter only when the raw GET value is in `valid`; junk → skip (fall back to unfiltered, never 500,
never an empty page). Integer GET filters: `as_db_int(request.GET.get(...))` → apply only when not `None`.

### 3.1 `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py`

Extra imports: forms `SalesProcessDefinitionForm`; models `SalesAlertTrigger`,
`SalesProcessDefinition`, `TARGET_ENTITY_CHOICES` (+ `validate_process_conditions` NOT needed here);
`from apps.crm.models import Case, Lead, Opportunity`; `from apps.scm.models import SalesOrder`;
`from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract`;
`from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription`;
`from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote`;
`from apps.sales.views.WorkflowProcessAutomation.SalesAlertTriggers import fire_alert_trigger`.

Module constants:

```python
SPD_TARGET_MODELS = {
    "lead": Lead,
    "opportunity": Opportunity,
    "quote": CPQQuote,
    "order": SalesOrder,
    "case": Case,
    "contract": CustomerContract,
    "subscription": CustomerSubscription,
}
MAX_RUN_RECORDS = 100
```

Helper `_evaluate_condition(record, condition)` (module-level, private — NOT re-exported):

```python
def _evaluate_condition(record, condition):
    field = condition.get("field")
    operator = condition.get("operator")
    value = condition.get("value")
    actual = getattr(record, field, None)
    try:
        if operator == "eq":
            return actual == value
        if operator == "ne":
            return actual != value
        if operator == "in":
            return actual in (value or [])
        if operator == "not_in":
            return actual not in (value or [])
        if operator == "contains":
            return value in str(actual or "")
        if operator == "icontains":
            return str(value or "").lower() in str(actual or "").lower()
        if operator == "gt":
            return actual is not None and actual > value
        if operator == "gte":
            return actual is not None and actual >= value
        if operator == "lt":
            return actual is not None and actual < value
        if operator == "lte":
            return actual is not None and actual <= value
        if operator == "is_set":
            return bool(actual) is bool(value)
        if operator == "is_empty":
            return (actual in (None, "", [], {})) is bool(value)
    except TypeError:
        return False
    return False
```

(Decimal-vs-int comparisons work natively; anything unorderable returns False, never raises.)

| View | Route name | Behavior |
|---|---|---|
| `sales_process_definition_list(request)` | `sales_process_definition_list` | qs = `SalesProcessDefinition.objects.filter(tenant=request.tenant).select_related("owner")`. GET filters below. `page_obj = paginate(request, qs, 15)`. Render `"sales/workflowprocessautomation/salesprocessdefinition/list.html"`. |
| `sales_process_definition_detail(request, pk)` | `..._detail` | `get_object_or_404(SalesProcessDefinition.objects.filter(tenant=request.tenant).select_related("owner", "job_definition"), pk=pk)`. Render `.../detail.html`. |
| `sales_process_definition_create(request)` | `..._create` | POST: `form = SalesProcessDefinitionForm(request.POST, tenant=tenant)`; valid → `obj = form.save(commit=False); obj.tenant = tenant; obj.owner = request.user; obj.save()` (+ `form.save_m2m()` not needed — no M2M); `write_audit_log(request.user, obj, "create", tenant=tenant)`; `messages.success(request, f"Process definition '{obj.name}' created.")`; redirect detail. GET: `form = SalesProcessDefinitionForm(tenant=tenant)`. Render `.../form.html`. |
| `sales_process_definition_edit(request, pk)` | `..._edit` | POST valid → `obj = form.save(commit=False)`; `if "status" in form.changed_data: obj.version += 1`; `obj.save()`; audit `"update"`; message `f"Process definition '{obj.name}' updated."`; redirect detail. |
| `sales_process_definition_delete(request, pk)` | `..._delete` | Capture `name`; `write_audit_log(request.user, obj, "delete", tenant=tenant)` BEFORE `obj.delete()`; `messages.success(request, f"Process definition '{name}' deleted.")`; redirect list. |
| `sales_process_definition_run(request, pk)` | `..._run` | See below. |

**SPD list GET filters (PINNED):**

| Param | Handling |
|---|---|
| `q` | `qs.filter(Q(name__icontains=q) \| Q(description__icontains=q) \| Q(number__icontains=q))` |
| `status` | valid = `{v for v, _ in SalesProcessDefinition.STATUS_CHOICES}` → `qs.filter(status=...)` |
| `target_entity` | valid from `TARGET_ENTITY_CHOICES` → `qs.filter(target_entity=...)` |
| `trigger_event` | valid from `SalesProcessDefinition.TRIGGER_EVENT_CHOICES` → `qs.filter(trigger_event=...)` |

**SPD list context (5 keys):**

| Key | Value |
|---|---|
| `process_definitions` | `page_obj.object_list` |
| `page_obj` | `paginate(request, qs, 15)` result |
| `status_choices` | `SalesProcessDefinition.STATUS_CHOICES` |
| `target_entity_choices` | `TARGET_ENTITY_CHOICES` |
| `trigger_event_choices` | `SalesProcessDefinition.TRIGGER_EVENT_CHOICES` |

**SPD detail context (1 key):** `process_definition`.

**SPD create context (3 keys):** `form`, `process_definition` = `None`, `is_edit` = `False`.
**SPD edit context (3 keys):** `form`, `process_definition` = obj, `is_edit` = `True`.

**`sales_process_definition_run` (bounded on-access evaluation — scheduler parked, GAP-sales-8.17-01):**

1. `obj = get_object_or_404(SalesProcessDefinition.objects.filter(tenant=tenant), pk=pk)`
2. If `obj.status != "active"`: `messages.error(request, "Only an active process definition can run.")`; redirect detail.
3. `records = list(SPD_TARGET_MODELS[obj.target_entity].objects.filter(tenant=tenant).order_by("pk")[:MAX_RUN_RECORDS])` — `evaluated = len(records)`.
4. `matched = sum(1 for record in records if all(_evaluate_condition(record, c) for c in obj.conditions))` (empty conditions = everything matches).
5. For each node in `obj.nodes` with `node["type"] == "notify"`: `trigger_id = as_db_int(node["params"].get("alert_trigger_id"))`; if not None → `trigger = SalesAlertTrigger.objects.filter(tenant=tenant, pk=trigger_id).first()`; if trigger → `fire_alert_trigger(trigger, user=request.user)`.
6. `write_audit_log(request.user, obj, "update", changes={"action": "process_run", "evaluated": str(evaluated), "matched": str(matched), "nodes": str(len(obj.nodes))}, tenant=tenant)`
7. `messages.success(request, f"Process '{obj.name}' evaluated {evaluated} record(s); {matched} matched.")`; redirect detail.

### 3.2 `apps/sales/views/WorkflowProcessAutomation/SalesAssignmentRules.py`

Extra imports: `SalesAssignmentRuleForm`; `SalesAssignmentRule`; `from apps.crm.models import Territory`.

Five views `sales_assignment_rule_{list,detail,create,edit,delete}(request[, pk])` — identical
create/edit/delete choreography to §3.1 with messages:
`f"Assignment rule '{obj.name}' created."` / `"...updated."` / `"...deleted."` and audit verbs
`"create"` / `"update"` / `"delete"`. Create/edit set nothing beyond `obj.tenant = tenant` on
`commit=False` save. **No owner-assignment resolution ships this pass** — for `lead` targets the
future resolver MUST delegate to 8.1's `LeadRoutingRule` path (plan §f); this pass ships the rule
register + CRUD.

**SAR list qs:** `SalesAssignmentRule.objects.filter(tenant=request.tenant).select_related("default_owner", "territory", "last_assigned_owner")`.

**SAR list GET filters (PINNED):**

| Param | Handling |
|---|---|
| `q` | `Q(name__icontains=q) \| Q(number__icontains=q)` |
| `target_entity` | valid from `SalesAssignmentRule.TARGET_ENTITY_CHOICES` |
| `assignment_mode` | valid from `SalesAssignmentRule.ASSIGNMENT_MODE_CHOICES` |
| `is_active` | `"active"` → `qs.filter(is_active=True)`; `"inactive"` → `qs.filter(is_active=False)`; anything else → skip |
| `territory` | `territory_id = as_db_int(request.GET.get("territory"))`; `if territory_id is not None: qs = qs.filter(territory_id=territory_id)` (L11 — validated BEFORE the `_id=` filter) |

**SAR list context (5 keys):** `assignment_rules` = `page_obj.object_list`, `page_obj`,
`target_entity_choices` = `SalesAssignmentRule.TARGET_ENTITY_CHOICES`,
`assignment_mode_choices` = `SalesAssignmentRule.ASSIGNMENT_MODE_CHOICES`,
`territories` = `Territory.objects.filter(tenant=request.tenant, is_active=True).order_by("name")`.

**SAR detail context (2 keys):** `assignment_rule` (select_related `"default_owner",
"fallback_owner", "territory", "last_assigned_owner", "escalate_to"`),
`eligible_owners` = `list(assignment_rule.eligible_owners.all().order_by("pk"))`.

**SAR create context (3):** `form`, `assignment_rule` = `None`, `is_edit` = `False`. **Edit (3):** `form`, `assignment_rule` = obj, `is_edit` = `True`.

### 3.3 `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py`

Extra imports: `from django.db.models import Max`; the three SAD forms; models
`SalesApprovalDecision`, `TARGET_KIND_CHOICES`;
`from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract`;
`from apps.sales.models.OrderManagement.OrderHolds import OrderHold`;
`from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote`.

Module constants:

```python
SAD_TARGET_MODELS = {"quote": CPQQuote, "order_hold": OrderHold, "contract": CustomerContract}
TARGET_KIND_TO_APPROVAL_KIND = {"quote": "discount", "order_hold": "credit", "contract": "contract"}
```

| View | Behavior |
|---|---|
| `sales_approval_decision_list(request)` | qs = `SalesApprovalDecision.objects.filter(tenant=request.tenant).select_related("approver", "quote", "order_hold", "contract")`. Filters below. Render `.../salesapprovaldecision/list.html`. |
| `sales_approval_decision_detail(request, pk)` | Chain view — see below. |
| `sales_approval_decision_create(request)` | Manual ledger entry via `SalesApprovalDecisionForm`; `commit=False` → `obj.tenant = tenant` → save; audit `"create"`; `messages.success(request, f"Approval decision '{obj.number}' recorded.")`; redirect detail. Context (3): `form`, `approval_decision` = `None`, `is_edit` = `False`. |
| `sales_approval_decision_edit(request, pk)` | Uses **`SalesApprovalDecisionEditForm`** (comment/due_at ONLY); audit `"update"`; message `f"Approval decision '{obj.number}' updated."`. Context (3): `form`, `approval_decision` = obj, `is_edit` = `True`. |
| `sales_approval_decision_delete(request, pk)` | Mis-entry correction; audit `"delete"` before delete; `messages.success(request, f"Approval decision '{number}' deleted.")`; redirect list. |
| `sales_approval_decision_approve(request)` | `return _sales_approval_decide(request, "approved")` |
| `sales_approval_decision_reject(request)` | `return _sales_approval_decide(request, "rejected")` |

**SAD list GET filters (PINNED):**

| Param | Handling |
|---|---|
| `q` | `Q(number__icontains=q) \| Q(record_label__icontains=q) \| Q(comment__icontains=q)` |
| `approval_kind` | valid from `SalesApprovalDecision.APPROVAL_KIND_CHOICES` |
| `decision` | valid from `SalesApprovalDecision.DECISION_CHOICES` |
| `target_kind` | valid from `TARGET_KIND_CHOICES` → `qs.filter(target_key__startswith=f"{kind}:")` |

**SAD list context (5 keys):** `approval_decisions` = `page_obj.object_list`, `page_obj`,
`approval_kind_choices` = `SalesApprovalDecision.APPROVAL_KIND_CHOICES`,
`decision_choices` = `SalesApprovalDecision.DECISION_CHOICES`,
`target_kind_choices` = `TARGET_KIND_CHOICES`.

**SAD detail** — `decision = get_object_or_404(SalesApprovalDecision.objects.filter(tenant=tenant).select_related("approver", "approver_role", "approval_rule", "requested_by", "quote", "order_hold", "contract"), pk=pk)`; then:

```python
chain = list(SalesApprovalDecision.objects.filter(tenant=tenant, target_key=decision.target_key)
             .select_related("approver", "approver_role"))          # Meta ordering: target_key, tier, id
rejected_exists = any(row.decision == "rejected" for row in chain)
approved_count = sum(1 for row in chain if row.decision == "approved")
tier_count = max((row.tier_count for row in chain), default=1)
pending_tier = None if rejected_exists or approved_count >= tier_count else approved_count + 1
kind, _, pk_str = decision.target_key.partition(":")
target_object = SAD_TARGET_MODELS.get(kind) and SAD_TARGET_MODELS[kind].objects.filter(
    tenant=tenant, pk=as_db_int(pk_str)).first() or None
action_form = (SalesApprovalDecisionActionForm(tenant=tenant, initial={
    "target_kind": kind, "target_id": as_db_int(pk_str), "tier_count": tier_count,
    "approval_kind": TARGET_KIND_TO_APPROVAL_KIND.get(kind, ""),
}) if pending_tier is not None else None)
```

**SAD detail context (6 keys):** `approval_decision`, `chain`, `target_object`, `pending_tier`,
`tier_count`, `action_form`.

**`_sales_approval_decide(request, decision)`** (module-private; procurement
`approval_decide` pattern — `select_for_update()` inside the view's atomic block):

1. `form = SalesApprovalDecisionActionForm(request.POST, tenant=tenant)`; invalid → `messages.error(request, "Fix the decision form before signing.")`; redirect `sales:sales_approval_decision_list`.
2. `kind = form.cleaned_data["target_kind"]`, `target_id = form.cleaned_data["target_id"]`.
3. `target = get_object_or_404(SAD_TARGET_MODELS[kind].objects.select_for_update(), pk=target_id, tenant=tenant)` — IDOR-safe 404.
4. `target_key = f"{kind}:{target.pk}"`; `chain = SalesApprovalDecision.objects.filter(tenant=tenant, target_key=target_key)`.
5. `if chain.filter(decision="rejected").exists():` → `messages.error(request, "This approval chain is closed — a rejection already ended it.")`; redirect list.
6. Quote-only guards: `if kind == "quote" and target.approval_status in {"approved", "rejected"}:` → `messages.error(request, f"Quote '{target.number}' already has a final approval status.")`; redirect list. `if kind == "quote" and target.owner_id == request.user.pk:` → `messages.error(request, "You cannot sign an approval on a quote you own.")`; redirect list (separation of duties, procurement pattern).
7. `tier_count = form.cleaned_data.get("tier_count") or chain.aggregate(Max("tier_count"))["tier_count__max"] or 1`; `tier = chain.filter(decision="approved").count() + 1` (deterministic — L61).
8. `if tier > tier_count:` → `messages.error(request, "Every tier in this chain is already signed.")`; redirect list.
9. `approval_kind = form.cleaned_data.get("approval_kind") or TARGET_KIND_TO_APPROVAL_KIND[kind]`.
10. `row = SalesApprovalDecision.record(tenant, quote=target if kind == "quote" else None, order_hold=target if kind == "order_hold" else None, contract=target if kind == "contract" else None, approval_kind=approval_kind, tier=tier, tier_count=tier_count, decision=decision, approver=request.user, approval_rule=(target.approval_rule if kind == "quote" else None), requested_by=request.user, requested_at=timezone.now(), record_label=(target.number or str(target))[:200], comment=form.cleaned_data.get("comment", ""))`.
    (`approver_role` stays `None` this pass — `QuoteApprovalRule.approver_role` is a CharField, not a Role FK; see Deviations.)
11. Quote spine flips (`save(update_fields=[...])`, always including `"updated_at"`):
    - `decision == "approved" and tier >= tier_count` → `target.approval_status = "approved"; target.approved_by = request.user; target.approved_at = timezone.now(); target.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])`
    - `decision == "rejected"` (ANY tier closes the chain) → same three fields with `approval_status = "rejected"`.
    - `order_hold` / `contract` targets: **decision row + audit only** — their own action verbs (8.6 hold release, 8.15 contract workflow) own their state transitions; SAD never flips them this pass.
12. `write_audit_log(request.user, row, "create", changes={"action": "tier_approve" if decision == "approved" else "tier_reject", "tier": f"{tier}/{tier_count}", "target": target_key}, tenant=tenant)`
13. `messages.success(request, f"Tier {tier} of {tier_count} {decision}.")`; redirect `sales:sales_approval_decision_detail` with `pk=row.pk`.

### 3.4 `apps/sales/views/WorkflowProcessAutomation/SalesAlertTriggers.py`

Extra imports: `from apps.accounts.models import User`; `SalesAlertTriggerForm`; models
`SalesAlertTrigger`, `SAT_TO_MDA_ALERT_TYPE`;
`from apps.sales.models.MobileSales.MobileDealAlerts import MobileDealAlert`;
`from apps.crm.models import Opportunity`;
`from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote`.

Module constants: `MAX_ALERT_RECIPIENTS = 50`.

**`fire_alert_trigger(trigger, *, user=None, record=None, now=None)`** (module-level PUBLIC helper —
tests import it from this module; NOT re-exported through `apps/sales/views/__init__.py`):

```python
def fire_alert_trigger(trigger, *, user=None, record=None, now=None):
    """Write MobileDealAlert rows for the trigger's audience. Returns the created alerts."""
    now = now or timezone.now()
    trigger.mark_evaluated(now=now)
    if not trigger.is_active or trigger.is_on_cooldown(now=now):
        return []
    if trigger.audience_kind == "role" and trigger.audience_role_id:
        recipients = list(User.objects.filter(
            tenant=trigger.tenant, role=trigger.audience_role, is_active=True
        ).order_by("pk")[:MAX_ALERT_RECIPIENTS])           # User.role is a FK (accounts/models.py:69)
    elif trigger.audience_kind == "user":
        recipients = list(trigger.audience_users.filter(is_active=True).order_by("pk")[:MAX_ALERT_RECIPIENTS])
    elif trigger.audience_kind == "owner" and record is not None:
        owner = getattr(record, "owner", None)
        recipients = [owner] if owner is not None and owner.is_active else []
    else:
        recipients = []   # "all" broadcast needs a transport — GAP-sales-8.17-05
    alerts = []
    for recipient in recipients:
        alerts.append(MobileDealAlert.objects.create(
            tenant=trigger.tenant,
            recipient=recipient,
            alert_type=SAT_TO_MDA_ALERT_TYPE.get(trigger.alert_type, "checkin_reminder"),
            title=trigger.name[:200],
            message=f"Alert trigger '{trigger.name}' fired for {trigger.get_target_entity_display()} records.",
            urgency=trigger.severity,
            related_opportunity=record if isinstance(record, Opportunity) else None,
            related_quote=record if isinstance(record, CPQQuote) else None,
        ))
    if alerts:
        trigger.mark_fired(now=now)
    if user is not None:
        write_audit_log(user, trigger, "update",
                        changes={"action": "alert_fired", "recipients": str(len(alerts))},
                        tenant=trigger.tenant)
    return alerts
```

Five views `sales_alert_trigger_{list,detail,create,edit,delete}(request[, pk])` — §3.1
choreography; messages `f"Alert trigger '{obj.name}' created."` / `"...updated."` / `"...deleted."`;
audit `"create"` / `"update"` / `"delete"`.

**SAT list qs:** `SalesAlertTrigger.objects.filter(tenant=request.tenant).select_related("audience_role", "notification_rule")`.

**SAT list GET filters (PINNED):**

| Param | Handling |
|---|---|
| `q` | `Q(name__icontains=q) \| Q(number__icontains=q)` |
| `alert_type` | valid from `SalesAlertTrigger.ALERT_TYPE_CHOICES` |
| `severity` | valid from `SalesAlertTrigger.SEVERITY_CHOICES` |
| `audience_kind` | valid from `SalesAlertTrigger.AUDIENCE_KIND_CHOICES` |
| `is_active` | `"active"`/`"inactive"` → True/False; else skip |

**SAT list context (5 keys):** `alert_triggers` = `page_obj.object_list`, `page_obj`,
`alert_type_choices` = `SalesAlertTrigger.ALERT_TYPE_CHOICES`,
`severity_choices` = `SalesAlertTrigger.SEVERITY_CHOICES`,
`audience_kind_choices` = `SalesAlertTrigger.AUDIENCE_KIND_CHOICES`.

**SAT detail context (2 keys):** `alert_trigger` (select_related `"audience_role",
"notification_rule"`), `audience_users` = `list(alert_trigger.audience_users.all().order_by("pk"))`.

**SAT create context (3):** `form`, `alert_trigger` = `None`, `is_edit` = `False`. **Edit (3):** `form`, `alert_trigger` = obj, `is_edit` = `True`.

### 3.5 Package `__init__` — `apps/sales/views/WorkflowProcessAutomation/__init__.py`

```python
from .SalesAlertTriggers import (
    fire_alert_trigger,
    sales_alert_trigger_create,
    sales_alert_trigger_delete,
    sales_alert_trigger_detail,
    sales_alert_trigger_edit,
    sales_alert_trigger_list,
)
from .SalesApprovalDecisions import (
    sales_approval_decision_approve,
    sales_approval_decision_create,
    sales_approval_decision_delete,
    sales_approval_decision_detail,
    sales_approval_decision_edit,
    sales_approval_decision_list,
    sales_approval_decision_reject,
)
from .SalesAssignmentRules import (
    sales_assignment_rule_create,
    sales_assignment_rule_delete,
    sales_assignment_rule_detail,
    sales_assignment_rule_edit,
    sales_assignment_rule_list,
)
from .SalesProcessDefinitions import (
    sales_process_definition_create,
    sales_process_definition_delete,
    sales_process_definition_detail,
    sales_process_definition_edit,
    sales_process_definition_list,
    sales_process_definition_run,
)
```

(`fire_alert_trigger` is re-exported from the SUB-package for tests but is deliberately NOT added
to `apps/sales/views/__init__.py` — it does not match the `sales_*` view-name prefixes.)

---

## 4. URLs

Entity modules copy the 8.16 header shape verbatim
(`"""Sales 8.17 — <Entity> URL patterns."""`, `from django.urls import path`,
`from apps.sales.views.WorkflowProcessAutomation import <Module> as views`).
Route order (first-match-wins): list → create → collection-level literals → `<int:pk>/…` actions →
bare `<int:pk>/` detail LAST. Route prefixes `processes/`, `assignment-rules/`,
`approval-decisions/`, `alert-triggers/` verified FREE against the whole concatenated sales URL
list (nearest neighbours: `alerts/` (8.16), `approval-rules/` (8.5), `routing-rules/` (8.1); the
only greedy route in sales is `quotes/portal/<str:token>/`, scoped under `quotes/` — no shadowing).

### 4.1 `apps/sales/urls/WorkflowProcessAutomation/SalesProcessDefinitions.py`

```python
urlpatterns = [
    path("processes/", views.sales_process_definition_list, name="sales_process_definition_list"),
    path("processes/create/", views.sales_process_definition_create, name="sales_process_definition_create"),
    path("processes/<int:pk>/run/", views.sales_process_definition_run, name="sales_process_definition_run"),
    path("processes/<int:pk>/edit/", views.sales_process_definition_edit, name="sales_process_definition_edit"),
    path("processes/<int:pk>/delete/", views.sales_process_definition_delete, name="sales_process_definition_delete"),
    path("processes/<int:pk>/", views.sales_process_definition_detail, name="sales_process_definition_detail"),
]
```

### 4.2 `apps/sales/urls/WorkflowProcessAutomation/SalesAssignmentRules.py`

```python
urlpatterns = [
    path("assignment-rules/", views.sales_assignment_rule_list, name="sales_assignment_rule_list"),
    path("assignment-rules/create/", views.sales_assignment_rule_create, name="sales_assignment_rule_create"),
    path("assignment-rules/<int:pk>/edit/", views.sales_assignment_rule_edit, name="sales_assignment_rule_edit"),
    path("assignment-rules/<int:pk>/delete/", views.sales_assignment_rule_delete, name="sales_assignment_rule_delete"),
    path("assignment-rules/<int:pk>/", views.sales_assignment_rule_detail, name="sales_assignment_rule_detail"),
]
```

### 4.3 `apps/sales/urls/WorkflowProcessAutomation/SalesApprovalDecisions.py`

```python
urlpatterns = [
    path("approval-decisions/", views.sales_approval_decision_list, name="sales_approval_decision_list"),
    path("approval-decisions/create/", views.sales_approval_decision_create, name="sales_approval_decision_create"),
    path("approval-decisions/approve/", views.sales_approval_decision_approve, name="sales_approval_decision_approve"),
    path("approval-decisions/reject/", views.sales_approval_decision_reject, name="sales_approval_decision_reject"),
    path("approval-decisions/<int:pk>/edit/", views.sales_approval_decision_edit, name="sales_approval_decision_edit"),
    path("approval-decisions/<int:pk>/delete/", views.sales_approval_decision_delete, name="sales_approval_decision_delete"),
    path("approval-decisions/<int:pk>/", views.sales_approval_decision_detail, name="sales_approval_decision_detail"),
]
```

### 4.4 `apps/sales/urls/WorkflowProcessAutomation/SalesAlertTriggers.py`

```python
urlpatterns = [
    path("alert-triggers/", views.sales_alert_trigger_list, name="sales_alert_trigger_list"),
    path("alert-triggers/create/", views.sales_alert_trigger_create, name="sales_alert_trigger_create"),
    path("alert-triggers/<int:pk>/edit/", views.sales_alert_trigger_edit, name="sales_alert_trigger_edit"),
    path("alert-triggers/<int:pk>/delete/", views.sales_alert_trigger_delete, name="sales_alert_trigger_delete"),
    path("alert-triggers/<int:pk>/", views.sales_alert_trigger_detail, name="sales_alert_trigger_detail"),
]
```

### 4.5 `apps/sales/urls/WorkflowProcessAutomation/__init__.py`

```python
from .SalesAlertTriggers import urlpatterns as alert_trigger_urls
from .SalesApprovalDecisions import urlpatterns as approval_decision_urls
from .SalesAssignmentRules import urlpatterns as assignment_rule_urls
from .SalesProcessDefinitions import urlpatterns as process_urls

urlpatterns = process_urls + assignment_rule_urls + approval_decision_urls + alert_trigger_urls
```

### 4.6 `apps/sales/urls/__init__.py` (surgical Edit — TWO changes, both required, L54)

After line 54 (`from .MobileSales import urlpatterns as _mobile_sales`) insert:

```python
# 8.17 Workflow & Process Automation. Extends crm.Lead/Opportunity/Case/Territory,
# sales.CPQQuote/OrderHold/CustomerContract/QuoteApprovalRule/MobileDealAlert, scm.SalesOrder,
# accounts.User/Role, core.JobDefinition/NotificationRule by FK or as write targets; declares no
# second workflow registry, notification channel or approval gate.
from .WorkflowProcessAutomation import urlpatterns as _workflow_automation
```

After `    *_mobile_sales,` (currently line 98, BEFORE `    *_pipelines,`) insert:

```python
    # 8.17 Workflow & Process Automation.
    *_workflow_automation,
```

Total url names added: **23** (20 standard CRUD + `sales_process_definition_run` +
`sales_approval_decision_approve` + `sales_approval_decision_reject`).

---

## 5. Templates (12)

All extend `base.html`; copy block/breadcrumb/card/table structure from the house reference
`templates/sales/mobilesales/mobiledealalert/{list,detail,form}.html`. `{% include %}` paths stay
root-relative (`partials/…`). Every template comment is a single-line `{# … #}` (L2). Badge classes
are colour-named ONLY — verified against `static/css/theme.css:286-291`: `badge-green`,
`badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist; `badge-success`,
`badge-danger`, `badge-warning`, `badge-purple` DO NOT (L33). Every badge `{% if %}` chain ends
with `{% else %}<span class="badge badge-muted">{{ obj.get_<field>_display }}</span>{% endif %}`.

Nullable-FK displays are wrapped in `{% if %}…{% else %}—{% endif %}` (L10): `owner`,
`job_definition`, `default_owner`, `fallback_owner`, `territory`, `last_assigned_owner`,
`escalate_to`, `approver`, `approver_role`, `approval_rule`, `requested_by`, `audience_role`,
`notification_rule`, `quote`, `order_hold`, `contract`, `target_object`. User display =
`{{ x.get_full_name }}` INSIDE the guard.

Pagination on every list page, after the table (the partial itself guards `num_pages > 1` /
`has_previous` / `has_next` and iterates `page_obj.window` — L9):

```django
{% include "partials/pagination.html" %}
```

Filter selects preserve state via raw `request.GET` string compares; pk compares use
`|stringformat:"d"` (never `|slugify`). House pattern:

```django
<select name="status" class="form-select" onchange="this.form.submit()">
    <option value="">All Statuses</option>
    {% for value, label in status_choices %}
        <option value="{{ value }}" {% if request.GET.status == value %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
</select>
```

(Territory select: `{% if request.GET.territory == territory.pk|stringformat:"d" %}selected{% endif %}`.)
Filter forms are `<form method="get">` with a `q` text input named `q`
(`value="{{ request.GET.q|default:'' }}"`) and a submit button; the selects live in the same form.

Delete controls (list Actions column AND detail sidebar) — POST + csrf + confirm, NO user-typed
values interpolated into `confirm()` (L42):

```django
<form method="post" action="{% url 'sales:sales_process_definition_delete' pk=process_definition.pk %}"
      class="inline" onsubmit="return confirm('Delete this process definition?');">
    {% csrf_token %}
    <button type="submit" class="btn-icon text-danger" title="Delete">{% include "partials/icons/trash-2.html" %}</button>
</form>
```

(Confirm strings: `'Delete this process definition?'`, `'Delete this assignment rule?'`,
`'Delete this approval decision?'`, `'Delete this alert trigger?'`. If `partials/icons/…` includes
do not exist, inline the same lucide `<svg>` markup the 8.16 templates use — copy from
`templates/sales/mobilesales/mobiledealalert/list.html`.)

### 5.1 `salesprocessdefinition/list.html`

Reads: `process_definitions`, `page_obj`, `status_choices`, `target_entity_choices`,
`trigger_event_choices`, `request.GET`. Columns: Number (`{{ obj.number }}`), Name, Target
(`get_target_entity_display`), Trigger (`get_trigger_event_display`), Version, Status badge
(`draft→badge-slate, active→badge-green, paused→badge-amber, archived→badge-muted`), Active badge
(`is_active` True→`badge-green` "Active" / False→`badge-muted` "Inactive"), Priority, Actions
(eye → detail, pencil → edit, trash → delete-POST). `{% empty %}` row: "No process definitions
yet." Row loop variable name: `process_definition` (iterate `process_definitions`).

### 5.2 `salesprocessdefinition/detail.html`

Reads: `process_definition` only. Header: `{{ process_definition.number }}` + name + status badge
+ is_active badge. Sidebar actions: Edit link, **Run now** POST form
(`action="{% url 'sales:sales_process_definition_run' pk=process_definition.pk %}"` + csrf, no
confirm), Delete POST+confirm, Back to list. Body: version, priority, max_enrollments, owner
(guarded), job_definition (guarded), trigger event/field/value, **conditions rendered as a
readable table** (loop `process_definition.conditions`, columns Field / Operator / Value — never a
raw JSON dump), **nodes as an ordered table** (loop `process_definition.nodes`, columns Seq / Type
/ Params; show `node.params.required_fields` as a comma-joined list when present).

### 5.3 `salesprocessdefinition/form.html`

Reads: `form`, `process_definition`, `is_edit`. Single `<form method="post">{% csrf_token %}`
rendering every field via a pinned field loop — `{% for field in form.visible_fields %}` with
`{{ field.label_tag }}{{ field }}{{ field.errors }}{% endfor %}`; excluded system
fields cannot appear because the form's `fields` list omits them (L22). Title:
`{% if is_edit %}Edit Process Definition{% else %}New Process Definition{% endif %}`. Save +
Cancel (cancel → detail when `is_edit`, else list).

### 5.4 `salesassignmentrule/list.html`

Reads: `assignment_rules`, `page_obj`, `target_entity_choices`, `assignment_mode_choices`,
`territories`, `request.GET`. Filters: `q`, target_entity, assignment_mode, is_active select
(`"" / active / inactive` hardcoded options), territory select (loop `territories`). Columns:
Number, Name, Target, Mode badge (`badge-info`), Priority, Last assigned (guarded
`assignment_rule.last_assigned_owner.get_full_name`), Active badge, Actions. `{% empty %}`: "No
assignment rules yet."

### 5.5 `salesassignmentrule/detail.html`

Reads: `assignment_rule`, `eligible_owners`. Mode-specific config table (default_owner /
eligible_owners list / fallback_owner / territory + its manager / max_open_records /
escalate_after_hours / escalate_to — each guarded when nullable), round-robin state block
(`cursor`, `last_assigned_owner`, `last_assigned_at` — read-only, guarded), conditions table,
Edit/Delete/Back actions.

### 5.6 `salesassignmentrule/form.html`

Same skeleton as 5.3; title "Edit Assignment Rule" / "New Assignment Rule"; renders `eligible_owners`
as the multi-select from the form.

### 5.7 `salesapprovaldecision/list.html`

Reads: `approval_decisions`, `page_obj`, `approval_kind_choices`, `decision_choices`,
`target_kind_choices`, `request.GET`. Columns: Number, Target (`{{ row.target_key }}` + guarded
`record_label`), Kind badge (`badge-info`), Tier (`{{ row.tier }}/{{ row.tier_count }}`), Decision
badge (`approved→badge-green, rejected→badge-red`), Approver (guarded), Decided at
(`{{ row.decided_at|date:"Y-m-d H:i" }}`), Actions (eye / pencil / trash). `{% empty %}`: "No
approval decisions yet." Row loop variable: `approval_decision` is RESERVED for the detail page —
use `decision_row` in the list loop to avoid shadowing confusion.

### 5.8 `salesapprovaldecision/detail.html`

Reads: `approval_decision`, `chain`, `target_object`, `pending_tier`, `tier_count`, `action_form`.
Header: number + decision badge + tier `{{ approval_decision.tier }}/{{ approval_decision.tier_count }}`
+ final-tier marker `{% if approval_decision.is_final_tier %}<span class="badge badge-info">Final Tier</span>{% endif %}`.
Chain table: loop `chain` — Tier, Decision badge, Approver (guarded), Comment, Decided at.
Target panel: `{% if target_object %}` show its number/label `{% else %}` "Target record not
available." Pending panel: `{% if pending_tier %}` render TWO POST forms (approve →
`{% url 'sales:sales_approval_decision_approve' %}`, reject → `..._reject`), each with
`{% csrf_token %}`, `action_form.target_kind` / `action_form.target_id` /
`action_form.approval_kind` / `action_form.tier_count` rendered as hidden-ish inputs (render via
`{{ action_form.target_kind }}` etc. inside each form; the browser posts the current values) and
`{{ action_form.comment }}` visible textarea; reject form gets
`onsubmit="return confirm('Reject this approval chain?');"`. `{% else %}` show "This chain is
closed." Edit/Delete/Back actions.

### 5.9 `salesapprovaldecision/form.html`

Same skeleton as 5.3; title "Record Approval Decision" (create) / "Edit Approval Decision"
(edit — only `comment` and `due_at` inputs exist because the edit form's `fields` list is
`["comment", "due_at"]`).

### 5.10 `salesalerttrigger/list.html`

Reads: `alert_triggers`, `page_obj`, `alert_type_choices`, `severity_choices`,
`audience_kind_choices`, `request.GET`. Filters: `q`, alert_type, severity, audience_kind,
is_active (`"" / active / inactive`). Columns: Number, Name, Type badge (`badge-info`), Target,
Severity badge (`low→badge-muted, normal→badge-info, high→badge-amber, urgent→badge-red`),
Audience (`get_audience_kind_display`), Cooldown (`{{ alert_trigger.cooldown_hours }}h`), Fires
(`fire_count`), Active badge, Actions. `{% empty %}`: "No alert triggers yet."

### 5.11 `salesalerttrigger/detail.html`

Reads: `alert_trigger`, `audience_users`. Severity + is_active badges; conditions table; audience
block (audience_role guarded, audience_users list); delivery route panel: `notification_rule`
(guarded) + static note "Firing writes sales.MobileDealAlert rows for user-targeted audiences;
email/SMS/push transport is deferred (GAP-sales-8.17-05)."; derived stats read-only
(`cooldown_hours`, `fire_count`, `last_fired_at`, `last_evaluated_at` — datetimes guarded with
`{% if %}`); Edit/Delete/Back actions.

### 5.12 `salesalerttrigger/form.html`

Same skeleton as 5.3; title "Edit Alert Trigger" / "New Alert Trigger"; renders `audience_users`
multi-select.

---

## 6. Admin (`apps/sales/admin.py` — surgical Edit: extend the `.models` import + append 4 classes)

Import extension inside the existing `from .models import (` block (alphabetical position within
the appended 8.17 comment section at the END of the import list, before the closing paren):

```python
    # 8.17 Workflow & Process Automation
    SalesProcessDefinition,
    SalesAssignmentRule,
    SalesApprovalDecision,
    SalesAlertTrigger,
```

NO `TenantScopedAdmin` exists in this repo (grep = 0) — plain `admin.ModelAdmin`, copying the
`LeadRoutingRuleAdmin` shape at `apps/sales/admin.py:138`. Append after the last existing
registration:

```python
@admin.register(SalesProcessDefinition)
class SalesProcessDefinitionAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "target_entity", "trigger_event", "status", "version", "priority", "is_active", "tenant")
    list_filter = ("status", "target_entity", "trigger_event", "is_active", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("tenant", "number", "version", "created_at", "updated_at")
    list_select_related = ("owner", "job_definition")


@admin.register(SalesAssignmentRule)
class SalesAssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "target_entity", "assignment_mode", "priority", "is_active", "last_assigned_owner", "tenant")
    list_filter = ("assignment_mode", "target_entity", "match_mode", "is_active", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("tenant", "number", "cursor", "last_assigned_owner", "last_assigned_at", "created_at", "updated_at")
    list_select_related = ("default_owner", "territory", "fallback_owner", "last_assigned_owner", "escalate_to")
    filter_horizontal = ("eligible_owners",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if db_field.name in {"default_owner", "fallback_owner", "escalate_to"} and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant, is_active=True)
        if db_field.name == "territory" and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if db_field.name == "eligible_owners" and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant, is_active=True)
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(SalesApprovalDecision)
class SalesApprovalDecisionAdmin(admin.ModelAdmin):
    """Read-only decision register (PartyEnrichmentEventAdmin precedent — the register IS the history)."""
    list_display = ("number", "target_key", "approval_kind", "tier", "tier_count", "decision", "approver", "decided_at", "tenant")
    list_filter = ("approval_kind", "decision", "tenant")
    search_fields = ("number", "target_key", "record_label", "comment")
    readonly_fields = ("tenant", "number", "approval_kind", "quote", "order_hold", "contract", "target_key", "record_label", "approval_rule", "tier", "tier_count", "approver_role", "approver", "decision", "comment", "requested_by", "requested_at", "due_at", "decided_at", "created_at", "updated_at")
    list_select_related = ("quote", "order_hold", "contract", "approval_rule", "approver_role", "approver", "requested_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SalesAlertTrigger)
class SalesAlertTriggerAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "alert_type", "target_entity", "severity", "audience_kind", "cooldown_hours", "fire_count", "is_active", "tenant")
    list_filter = ("alert_type", "severity", "audience_kind", "is_active", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("tenant", "number", "last_evaluated_at", "last_fired_at", "fire_count", "created_at", "updated_at")
    list_select_related = ("audience_role", "notification_rule")
    filter_horizontal = ("audience_users",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if db_field.name == "audience_role" and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant)  # Role has NO is_active
        if db_field.name == "notification_rule" and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if db_field.name == "audience_users" and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant, is_active=True)
        return super().formfield_for_manytomany(db_field, request, **kwargs)
```

---

## 7. Integrate (single writer, after all 16 entity files + 12 templates exist — verify first, L21/L54)

### 7.1 `apps/sales/models/__init__.py`

Insert AFTER the 8.16 `from .MobileSales import (...)` block (ends line 162):

```python
# 8.17 Workflow & Process Automation. Reuses crm.Lead/Opportunity/Case/Territory,
# sales.CPQQuote/OrderHold/CustomerContract/QuoteApprovalRule/MobileDealAlert, scm.SalesOrder,
# accounts.User/Role, core.JobDefinition/NotificationRule/WorkflowDefinition.
from .WorkflowProcessAutomation import (
    PROCESS_NODE_TYPES,
    SAT_TO_MDA_ALERT_TYPE,
    TARGET_ENTITY_CHOICES,
    TARGET_KIND_CHOICES,
    SalesAlertTrigger,
    SalesApprovalDecision,
    SalesAssignmentRule,
    SalesProcessDefinition,
    validate_process_conditions,
    validate_process_nodes,
)
```

Append to `__all__` AFTER the `# 8.16 Mobile Sales` section (before the closing `]`):

```python
    # 8.17 Workflow & Process Automation
    "SalesProcessDefinition", "SalesAssignmentRule", "SalesApprovalDecision", "SalesAlertTrigger",
    "validate_process_conditions", "validate_process_nodes",
    "TARGET_ENTITY_CHOICES", "TARGET_KIND_CHOICES", "PROCESS_NODE_TYPES", "SAT_TO_MDA_ALERT_TYPE",
```

### 7.2 `apps/sales/forms/__init__.py`

Insert AFTER the 8.16 block (ends line 138):

```python
# 8.17 Workflow & Process Automation
from .WorkflowProcessAutomation import (
    SalesAlertTriggerForm,
    SalesApprovalDecisionActionForm,
    SalesApprovalDecisionEditForm,
    SalesApprovalDecisionForm,
    SalesAssignmentRuleForm,
    SalesProcessDefinitionForm,
)
```

Append to `__all__` after the 8.16 section:

```python
    # 8.17 Workflow & Process Automation
    "SalesProcessDefinitionForm", "SalesAssignmentRuleForm",
    "SalesApprovalDecisionForm", "SalesApprovalDecisionEditForm",
    "SalesApprovalDecisionActionForm", "SalesAlertTriggerForm",
```

### 7.3 `apps/sales/views/__init__.py`

Insert AFTER the 8.16 `from .MobileSales import (...)` block (ends line 460): the 23-name import
block from §4.6-style listing — exactly:

```python
# 8.17 Workflow & Process Automation
from .WorkflowProcessAutomation import (
    sales_alert_trigger_create,
    sales_alert_trigger_delete,
    sales_alert_trigger_detail,
    sales_alert_trigger_edit,
    sales_alert_trigger_list,
    sales_approval_decision_approve,
    sales_approval_decision_create,
    sales_approval_decision_delete,
    sales_approval_decision_detail,
    sales_approval_decision_edit,
    sales_approval_decision_list,
    sales_approval_decision_reject,
    sales_assignment_rule_create,
    sales_assignment_rule_delete,
    sales_assignment_rule_detail,
    sales_assignment_rule_edit,
    sales_assignment_rule_list,
    sales_process_definition_create,
    sales_process_definition_delete,
    sales_process_definition_detail,
    sales_process_definition_edit,
    sales_process_definition_list,
    sales_process_definition_run,
)
```

Add to the `__all__` startswith tuple AFTER `"mobile_sales_dashboard",`:

```python
        # 8.17 Workflow & Process Automation
        "sales_process_definition_", "sales_assignment_rule_",
        "sales_approval_decision_", "sales_alert_trigger_",
```

(`fire_alert_trigger` intentionally not re-exported here — see §3.5.)

### 7.4 `apps/sales/urls/__init__.py` — per §4.6.

### 7.5 `apps/core/navigation.py` — LIVE_LINKS

Insert the `"8.17"` entry IMMEDIATELY after the `"8.16"` closing brace (line 2616) and before the
trailing `# NO sidebar key` comment block — VERBATIM from the plan:

```python
    "8.17": {
        # OWNERSHIP RULING (L36/L37/L55)
        # Reuses crm.Lead/crm.Opportunity/crm.Case as assignment + trigger targets (CRM owns them);
        # reuses sales.CPQQuote/OrderHold/CustomerContract as approval targets; sales.QuoteApprovalRule (8.5) as the gate;
        # reuses sales.LeadRoutingRule (8.1) + crm.Territory/8.7 TerritoryRule for owner resolution (no second decision);
        # reuses core.NotificationRule/Template/Channel (0.11) for delivery routing and sales.MobileDealAlert (8.16) as the record-side alert row;
        # reuses core.JobDefinition for time-based trigger registration; registers into core.WorkflowDefinition (0.11 registry).
        # Zero duplicate workflow-registry, notification-channel, approval-gate, or enrichment tables declared.
        "Visual Process Designer": "sales:sales_process_definition_list",
        "Auto-Assignment Rules": "sales:sales_assignment_rule_list",
        "Approval Workflows": "sales:sales_approval_decision_list",
        "Notification & Alert Engine": "sales:sales_alert_trigger_list",
        "Data Enrichment & Cleansing": "sales:party_enrichment_list",  # no new model — bullet 5's auto-update half IS 8.3's PartyEnrichmentEvent (verified live route); duplicate-cluster/merge half deferred to gaps-sales-8.17.md
    },
```

No other navigation edits. No `config/settings.py` / `config/urls.py` changes.

### 7.6 Migration

1. In-process: `from django.core import checks; checks.run_checks()` → must be clean BEFORE generating (L65).
2. `venv\Scripts\python.exe manage.py makemigrations sales` → expect `0031_*.py` (re-verify the leaf number first — L43/L51/L53).
3. `venv\Scripts\python.exe manage.py migrate`.

---

## 8. Seeder (`apps/sales/management/commands/seed_sales.py` — surgical Edit)

Signature follows the HOUSE convention `(self, tenant, owner)` (every existing `_seed_*` method uses
`owner`; the plan's `(self, tenant, user)` is overridden — see Deviations). In `_seed_tenant`,
insert ONE line after `self._seed_mobile_sales(tenant, owner)` (line 204):

```python
        self._seed_workflow_process_automation(tenant, owner)
```

Method (appended after `_seed_mobile_sales`), idempotent — existence guard + `transaction.atomic()`
(same shape as `_seed_mobile_sales` at line 3893). Import additions at the top of the file follow
the existing absolute-import style:

```python
from apps.sales.models.WorkflowProcessAutomation.SalesAlertTriggers import SalesAlertTrigger
from apps.sales.models.WorkflowProcessAutomation.SalesApprovalDecisions import SalesApprovalDecision
from apps.sales.models.WorkflowProcessAutomation.SalesAssignmentRules import SalesAssignmentRule
from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import SalesProcessDefinition
from apps.core.models.Workflow import WorkflowDefinition
from apps.crm.models import Territory
```

Pinned rows (deterministic picks use `.order_by("pk").first()` — L61):

1. Guard: `if SalesProcessDefinition.objects.filter(tenant=tenant).exists(): return`.
2. `quote = CPQQuote.objects.filter(tenant=tenant).order_by("pk").first()`; `territory = Territory.objects.filter(tenant=tenant).order_by("pk").first()`; `second_user = User.objects.filter(tenant=tenant, is_active=True).exclude(pk=owner.pk).order_by("pk").first()`.
3. **SAT first** (SPD notify node references it):
   - `sat1 = SalesAlertTrigger.objects.create(tenant=tenant, name="Deal Inactivity Watcher", alert_type="deal_inactivity", target_entity="opportunity", severity="high", audience_kind="all", inactivity_days=7, cooldown_hours=24, priority=10, conditions=[{"field": "status", "operator": "eq", "value": "open"}])`
   - `sat2 = SalesAlertTrigger.objects.create(tenant=tenant, name="Stage Change Notifier", alert_type="stage_change", target_entity="opportunity", severity="normal", audience_kind="user", priority=20)`; then `sat2.audience_users.add(owner)`.
4. **SPD:**
   - `spd1 = SalesProcessDefinition.objects.create(tenant=tenant, name="Quote Discount Approval Flow", description="Two-tier sign-off when a quote header discount reaches 20%.", status="active", target_entity="quote", trigger_event="field_value", trigger_field="header_discount_pct", trigger_value="20", owner=owner, priority=10, conditions=[{"field": "header_discount_pct", "operator": "gte", "value": 20}], nodes=[{"seq": 1, "type": "approval", "params": {"approval_kind": "discount", "tier_count": 2}}, {"seq": 2, "type": "notify", "params": {"alert_trigger_id": sat2.pk}}, {"seq": 3, "type": "create_task", "params": {"title": "Follow up on discounted quote"}}])`
   - `spd2 = SalesProcessDefinition.objects.create(tenant=tenant, name="Lead Welcome Onboarding", status="draft", target_entity="lead", trigger_event="created", owner=owner, priority=20, nodes=[{"seq": 1, "type": "assign", "params": {"mode": "round_robin"}}])`
5. **SAR:**
   - `sar1 = SalesAssignmentRule.objects.create(tenant=tenant, name="Opportunity Round Robin Pool", target_entity="opportunity", match_mode="all", assignment_mode="round_robin", is_catch_all=True, priority=10)`; `sar1.eligible_owners.add(owner)` plus `second_user` when not None.
   - `sar2`: if `territory is not None` → `SalesAssignmentRule.objects.create(tenant=tenant, name="Case Territory Manager Route", target_entity="case", assignment_mode="territory_manager", territory=territory, priority=20)`; else fall back to `assignment_mode="round_robin"`, `is_catch_all=True`, no territory, same name (so the row exists on tenants without territories).
6. **SAD 2-tier chain on `quote` (when `quote is not None`)** — tier 1 approved row via the record path; tier 2 pending = ABSENCE of a row:
   ```python
   SalesApprovalDecision.record(
       tenant, quote=quote, approval_kind="discount", tier=1, tier_count=2,
       decision="approved", approver=owner, requested_by=owner,
       requested_at=timezone.now(), record_label=(quote.number or quote.name)[:200],
       comment="Seeded tier-1 sign-off.")
   ```
7. **WorkflowDefinition registry row (per-tenant — the model HAS a tenant FK):**
   ```python
   WorkflowDefinition.objects.get_or_create(
       tenant=tenant, name="Sales Approval Workflow",
       defaults={"module_slug": "sales", "engine_label": "sales.SalesApprovalDecision",
                 "description": "Sales 8.17 multi-tier approval register (SalesApprovalDecision).",
                 "target_hours": 48})
   ```
   (Verified against `apps/core/models/Workflow.py:27-52`: `owner_role` is a NULLABLE FK — omit it;
   `unique_together` is `("tenant", "name")` so get_or_create is race-safe here.)
8. Whole body wrapped in `with transaction.atomic():` like `_seed_mobile_sales`.

`handle()` success line: extend the existing text list with `8.17` (edit the f-string at line 164:
`"... 8.14, 8.15, 8.16, and 8.17 seed complete."` — match whatever the current literal says and
append; surgical edit only).

Run TWICE in verification; second run must produce identical counts.

---

## 9. Verification / smoke (Phase 3.5 pins)

- `venv\Scripts\python.exe manage.py makemigrations --check --dry-run` → `No changes detected` (after migrate).
- `venv\Scripts\python.exe manage.py check` → 0 issues.
- All 23 url names reverse cleanly (`reverse("sales:sales_process_definition_run", args=[1])` etc.) — no `NoReverseMatch`.
- `seed_sales` twice → identical counts; assert strings present: `"Quote Discount Approval Flow"`,
  `"Opportunity Round Robin Pool"`, `"Deal Inactivity Watcher"`, and one number starting `"SAD-"`.
- temp/ sweep as `admin_acme` / `password` (L34 — NOT `password123`), content assertions (L3/L8):
  - 4 list pages → 200 containing `SPD-`, `SAR-`, `SAD-`, `SAT-` respectively.
  - 4 detail + 4 create + 4 edit → 200.
  - `sales_process_definition_run` POST on the seeded active SPD → 302 + "evaluated" in messages.
  - `sales_approval_decision_approve` POST (body: target_kind=quote, target_id=seeded quote pk,
    tier_count=2, comment) → 302; a second `SAD-` row exists with `tier=2`; quote
    `approval_status == "approved"` (final tier).
  - Junk params on every list: `?page=999`, `?status=invalid`, `?territory=999999999999`,
    `?target_kind=nope` → 200, unfiltered fallback, no 500 (L11).
  - Cross-tenant IDOR: `admin_globex` pks on all 4 detail/edit/delete → 404 for `admin_acme`.
  - Grep rendered HTML: zero `{#` / `{% comment` leaks; zero `badge-success|badge-danger|badge-warning|badge-purple` (L33).
- Sidebar: `LIVE_LINKS["8.17"]` present, 5 bullets resolve to distinct staff-reachable hrefs (L30).
- `.agents/tasks/gaps-sales-8.17.md` created at Integrate with GAP-sales-8.17-01..08 verbatim from the plan.

Lesson checklist enforced by this contract: L2 (single-line template comments), L7 (every context
key pinned above), L9 (`paginate()` + `page.window` partial), L10 (nullable-FK guards), L11
(`as_db_int` before `_id=` filters; junk enums skipped), L22 (system/derived fields excluded via
explicit `fields` lists), L33 (colour-named badges only), L39/L49-addendum (exactly-one-target in
Model.clean IS tenant-independent so it fires on the form path; tenant-membership checks live in
form clean + queryset narrowing), L42 (no user text in confirm()), L43/L51/L53/L59 (surgical
shared-file edits; migration number re-verified; no peer contract claims these four model names),
L47 (final test run unfiltered, never `-k`), L54 (§4 — explicit Django imports; BOTH urls edits),
L57 (never annotate over `is_final_tier`), L61 (Meta ordering + explicit `.order_by("pk")` before
`.first()`), L62 (`TenantNumbered` only), L64 (`ast.parse` every written file), L65 (max_length
fits longest value — verified: `territory_manager`=17≤20, `approval_requested`=18≤24,
`subscription`=12≤16, `stage_changed`=13≤16, `archived`=8≤10, `exception`=9≤10,
`rejected`=8≤8; index/constraint names ≤30 chars — longest is `sales_sad_tnt_tgt_tier_uniq`=27).

---

## 10. Deviations from the plan (code wins — L28)

1. **6 form classes, not 4.** The plan's own CRUD shape needs `SalesApprovalDecisionEditForm`
   (comment/due_at only) and the approve/reject actions need `SalesApprovalDecisionActionForm`
   (`TenantActionForm`). Pinned in §2.3–2.5.
2. **Seeder signature `(self, tenant, owner)`** — every existing `_seed_*` method in
   `seed_sales.py` takes `owner`; the plan said `user`.
3. **`core.WorkflowDefinition` registry row moved from Integrate to the per-tenant seeder** —
   `WorkflowDefinition` HAS a tenant FK (`apps/core/models/Workflow.py`), so "ONE registry row"
   is impossible; `get_or_create(tenant=tenant, name="Sales Approval Workflow", ...)` per tenant (§8.7).
4. **`is_paginated` dropped.** `templates/partials/pagination.html` reads only `page_obj`
   (+ `page_obj.window`, attached solely by `apps.core.crud.paginate`). All lists use
   `paginate(request, qs, 15)`; context carries `page_obj` only.
5. **FK-queryset context keys dropped:** the plan's `eligible_owner_users`, `notification_rules`,
   `approver_roles`, `task_templates` are consumed by nothing — dropdowns are narrowed in form
   `__init__` (house pattern). Only `territories` survives (SAR list filter bar).
6. **Conditions validator drops the 8.1 `ROUTING_FIELDS` whitelist** (8.17 conditions span 7
   entities): `field` = any non-empty str ≤ 255; bounds and all other messages identical; the
   count message reads "A process rule may contain at most 20 conditions." and the operator
   message `f"Unsupported condition operator: {operator}"`.
7. **23 url names, not "24 standard + 3".** Actual: 20 standard CRUD routes + run/approve/reject.
8. **`tier_count` source re-pinned.** The plan said tier resolution "reads
   `QuoteApprovalRule.approver_role`" — in real code that is a CharField (role NAME), not a Role
   FK, and NO `required_tiers` field exists anywhere in sales. Pinned: the action form carries
   optional `tier_count` (1–9); the view falls back to `Max("tier_count")` over the target's
   existing chain, else 1; `tier = count(approved rows) + 1` (procurement's deterministic shape).
   `approver_role` stays NULL on view-created rows.
9. **`SAT_TO_MDA_ALERT_TYPE` mapping constant added** — 8.16's module-level `ALERT_TYPE_CHOICES`
   is CLOSED and already re-exported from `apps/sales/models/__init__.py`; SAT firing maps its own
   (class-attr) types onto existing MDA values instead of extending the 8.16 constant. All other
   8.17 choices are class attributes for the same collision reason.
10. **OrderHold / CustomerContract targets get NO state flip this pass** — decision row + audit
    only; 8.6/8.15's own action verbs own those transitions (avoids a second writer on their
    status fields). Quote is the only spine that flips (`approval_status`/`approved_by`/`approved_at`).
11. **`audience_kind="all"` / `"owner"` firing is limited**: `owner` resolves only when a `record`
    with an `owner` attr is passed; `all` creates no rows this pass (broadcast needs transport —
    GAP-sales-8.17-05). `role`/`user` audiences are fully wired. `User.role` is a FK
    (accounts/models.py:69) — recipient query is `User.objects.filter(tenant=..., role=..., is_active=True)`.
12. **`_relation_belongs_to_tenant` imported, not re-cloned**, by SAR/SAT model files from
    `SalesProcessDefinitions.py` (single source of truth inside the package; the 8.7 clone-locally
    precedent produced drift risk across 3 files).
