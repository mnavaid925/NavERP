"""Sales 8.8 — Sales Activity & Task Management. OWNERSHIP RULING (L36/L37), one of its four
durable homes (the others: this sub-module's `contract-sales-8.8.md`, the `LIVE_LINKS["8.8"]`
comment in `apps/core/navigation.py`, and `.claude/tasks/lessons.md`).

**8.8 EXTENDS the CRM 1.5 activity stack. It declares no second activity, task or calendar master.**

CRM 1.5 ("Activity & Communication Management") shipped first and is already fully live — its three
`LIVE_LINKS["1.5"]` bullets point at `crm:task_list`, `crm:calendarevent_list` and
`crm:communicationlog_list`, and all three models are real tables with real views, forms and seeded
rows:

* `crm.CommunicationLog` (`COM-`) — the interaction itself: `channel`, `direction`, `subject`,
  `body`, `party`, `owner`, `related_opportunity`, `related_case`, `occurred_at`,
  `duration_seconds`, `outcome`, `logged_via`, `email_message_id`.
* `crm.CrmTask` (`TASK-`) — the to-do, **including** single-task recurrence
  (`recurrence` / `recurrence_interval` / `recurrence_until` / `recurrence_parent`, with
  `_spawn_next_occurrence()` running inside `save()`'s own `transaction.atomic()`).
* `crm.CalendarEvent` (`EVT-`) + `crm.EventAttendee` — the meeting, **including** `sync_source`
  (manual/google/outlook/ical) and a login-free `public_token` for invite / RSVP / `.ics`.

**This is the most tempting application of L36 in the project so far, because 8.8's title and CRM
1.5's title are near-synonyms** — "Sales Activity & Task Management" against "Activity &
Communication Management". The module with "Activity" in its title does **not** get to re-declare the
activity. This is L37 ("the module named for the domain still extends the spine rather than declaring
its own master") applied to a *name* collision rather than a domain collision.

**What a `class Activity`, `class Task`, `class Meeting`, `class Call` or `class EmailLog` with its
own `channel` / `due_date` / `start` / `end` columns under `apps/sales/models/` is: a bug, not a
variant.** The 8.8 models that *look* like a second stack are all the same shape instead — a required
or optional **FK onto the CRM 1.2/1.5 owner**, plus only the columns that owner does not have:

| 8.8 model | Reaches its subject through | Adds what CRM does not have |
|---|---|---|
| `ActivityLog` (`SAL-`) | required 1:1 `communication_log` FK | sales attribution (deal / account / territory / rep) + frozen email open-click-reply counters |
| `TaskTemplate` (`TTPL-`) | **generates** `crm.CrmTask` rows | the template → many-tasks fan-out, and the generation receipt |
| `SalesPlanCycle` (`SPC-`) | reads `crm.CrmTask` / `crm.CalendarEvent` / `ActivityLog` | the day/week window and its activity **goals** (actuals are derived, never stored — L37) |
| `ActivityType` (`ATY-`) | nothing | the configurable type **catalogue** — `CommunicationLog.channel` and `CrmTask.type` are both closed 5-value fields |

**Three of the four genuinely have no owner anywhere in the project**, which is why the ruling costs
nothing: the recurring-task *template*, the email open/click/reply *tracking*, and *activity goals* are
all new tables, while the one thing that is owned (the activity itself) is read through a FK.

**Vocabulary is IMPORTED, never re-spelled** (the `ROUTING_OPERATORS` rule 8.7 followed against 8.1):
`ActivityType.kind` ← `CommunicationLog.CHANNEL_CHOICES`, `ActivityType.default_outcome` ←
`CommunicationLog.OUTCOME_CHOICES`, `TaskTemplate.task_type` ← `CrmTask.TYPE_CHOICES`,
`TaskTemplate.priority` ← `CrmTask.PRIORITY_CHOICES`. A copied literal list is how the two drift apart
and one of them quietly stops rejecting what the other rejects.
"""
from .ActivityTypes import ActivityType
from .ActivityLogs import (
    AUTO_CAPTURE_SOURCES,
    CAPTURE_SOURCE_CHOICES,
    ActivityLog,
)
from .TaskTemplates import TaskTemplate, TaskTemplateStep
from .SalesPlanCycles import ActivityGoal, SalesPlanCycle

__all__ = [
    "ActivityType",
    "ActivityLog",
    "CAPTURE_SOURCE_CHOICES",
    "AUTO_CAPTURE_SOURCES",
    "TaskTemplate",
    "TaskTemplateStep",
    "SalesPlanCycle",
    "ActivityGoal",
]
