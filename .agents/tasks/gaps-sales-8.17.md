# Gap Register — Sub-module 8.17: Workflow & Process Automation (Module 8: Sales Management System)

> Tracks features, transports, and execution runtimes deferred to future passes or external services.
> Entries are IMMUTABLE: close by ticking `- [x]` with the resolving commit SHA or passing test —
> never delete an entry.

---

### GAP-sales-8.17-01: Process execution runtime / background scheduler runs
- **Verbatim from plan**: timed unattended evaluation of SPD triggers and SAT scans on `core.JobScheduler`; this pass ships definitions, bounded on-access evaluation helpers, and the `sales_process_definition_run` POST action (8.7 precedent). → later pass / 8.18 wiring
- **Owner**: `sales:8.17` / `sales:8.18` (Integration Hub)
- **Waiting For / Blocked On**: A background scheduler worker process. `core.JobDefinition` registration exists and the seeder registers the sales engine, but no NavERP worker polls it — the same constraint 8.16 parked APNs/FCM against.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Active `SalesProcessDefinition` triggers and due `SalesAlertTrigger` scans are evaluated unattended on a timer, without a user hitting the `run` action, and `SalesAlertTrigger.last_evaluated_at` advances without a request.

---

### GAP-sales-8.17-02: Duplicate cluster + merge workflow tables (`SalesDuplicateCluster` / `SalesDuplicateMerge`)
- **Verbatim from plan**: bullet 5's second half; destructive multi-table re-parenting deserves its own contract + pass. Detection stays loggable via `PartyEnrichmentEvent(kind='duplicate_check')`
- **Owner**: `sales:8.17` (deferred) — needs its own frozen contract
- **Waiting For / Blocked On**: A dedicated pre-build contract covering multi-table re-parenting semantics and rollback, since merging parties destructively moves child rows across modules (crm/scm/accounting).
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Duplicate candidate clusters can be detected, reviewed, and merged with all child records re-parented to the surviving `core.Party`, inside a reversible transaction, with an audit trail.

---

### GAP-sales-8.17-03: Approval delegation (out-of-office grants) + parallel approval branches
- **Verbatim from plan**: procurement `ApprovalDelegation` / `core.WorkflowStep.is_parallel` are the patterns; would be 5th/6th models this pass
- **Owner**: `sales:8.17` (deferred — scope held to 4 models this pass)
- **Waiting For / Blocked On**: Next sub-module pass; would add a 5th/6th model beyond the pinned 4-model build scope.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: An approver can grant a dated out-of-office delegation that routes their tier to a delegate, and a tier can require N approvers in parallel rather than strictly sequentially.

---

### GAP-sales-8.17-04: Weighted / skill-based / availability-aware routing modes
- **Verbatim from plan**: handed in by 8.1 Q12/Q13; needs eligible-owner weights + seller-capacity data; mode set stays closed this pass
- **Owner**: `sales:8.17` / `sales:8.1` (Lead Management)
- **Waiting For / Blocked On**: Per-eligible-owner weight data and seller-capacity/open-workload figures, which no current sales model stores. Inherited as an open question from 8.1 (Q12/Q13).
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: `SalesAssignmentRule.assignment_mode` supports weighted, skill-based, and availability-aware resolution using stored owner weights and live workload, with the mode set still closed and validated.

---

### GAP-sales-8.17-05: Email/SMS/push transport for alerts
- **Verbatim from plan**: no mailer/push gateway wired in repo; 8.16 parked APNs/FCM to 8.18. Alert rows + `core.Notification*` routing records ship now
- **Owner**: `sales:8.17` / `sales:8.18` (Integration Hub)
- **Waiting For / Blocked On**: An outbound transport (ESP, SMS gateway, or APNs/FCM relay). Consistent with deviation 11, `audience_kind="all"` therefore creates NO rows this pass — broadcast needs transport.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: A fired `SalesAlertTrigger` dispatches through `core.NotificationChannel`/`Template`/`Rule` to a real transport, and `audience_kind="all"` produces recipient rows rather than being a no-op.

---

### GAP-sales-8.17-06: AI-suggested automations / copilot flow generation
- **Verbatim from plan**: (Agentforce/Freddy/Creatio-AI class) — integration/later
- **Owner**: `sales:8.17` / `sales:8.18` (Integration Hub)
- **Waiting For / Blocked On**: An LLM/automation-suggestion integration; no such service is wired in the repo.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: The Visual Process Designer can propose process nodes/conditions from natural-language intent and let a user accept them into a draft `SalesProcessDefinition`.

---

### GAP-sales-8.17-07: True graphical drag-and-drop node canvas
- **Verbatim from plan**: ordered-step HTMX sortable UI ships now; a node-graph editor is front-end-heavy with no data-model value
- **Owner**: `sales:8.17` (front-end deferred)
- **Waiting For / Blocked On**: Front-end investment only — the ordered-step `nodes` JSON schema already supports branching, so no data-model change is required.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Users can visually drag nodes onto a canvas and wire branch edges, persisting to the same `nodes` JSON that the ordered-step UI writes.

---

### GAP-sales-8.17-08: `SalesProcessRun` dedicated execution-log table
- **Verbatim from plan**: (4.6) — folded into `SalesApprovalDecision` + `core.AuditLog` this pass
- **Owner**: `sales:8.17` (deferred by design)
- **Waiting For / Blocked On**: A decision that per-node execution telemetry is worth its own table; this pass deliberately folds run history into `SalesApprovalDecision` rows plus `core.AuditLog`.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Each process evaluation persists one `SalesProcessRun` row per node with timing/outcome, queryable independently of the approval register and the audit log.

---

### GAP-sales-8.17-09: Duplicate manual `SalesApprovalDecision` raises `IntegrityError` (HTTP 500) instead of a form error
- **Observed at**: Phase 3.4 Integrate (reported by the entity-3 build agent; NOT fixed here by instruction — left for the Phase 4 reviewers / Phase 5 code-fixer).
- **Owner**: `sales:8.17` entity 3 (`SalesApprovalDecisions`) → Phase 5 `code-fixer`
- **Waiting For / Blocked On**: Phase 4 review findings file `.claude/tasks/review-sales-8.17.md`, then Phase 5 fix.
- **Detail**: `SalesApprovalDecisionForm` deliberately does not use `TenantUniqueMixin`, and its `UniqueConstraint` on `(tenant, target_key, tier)` cannot be form-validated because `target_key` is `editable=False` and is still `""` when `_post_clean()` runs (`save()` at `SalesApprovalDecisions.py:134-135` is what recomputes it). A duplicate manual ledger entry therefore hits the DB constraint → `IntegrityError` → HTTP 500. The `approve`/`reject` decide path is immune (it computes `tier` from the existing chain).
- **Integrate verification**: the seeder does NOT trigger this — all 17 seeded SAD rows were written via `SalesApprovalDecision.record()` → `objects.create()` → `save()`, so all 17 have a non-empty `target_key`, and no `(tenant, target_key, tier)` duplicate exists in the dev DB.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Submitting the manual decision form with a `(tenant, target_key, tier)` combination that already exists renders a form validation error (no 500), covered by a test in `test_workflowautomation_forms.py`.
