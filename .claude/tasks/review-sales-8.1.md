# Review — NavERP 8.1 Lead Management

Base: `b18d08fbca4a38eabf9e444b025fb9c4eba4bd34`

## Code-fixer status — deduplicated

The six reviewer passes below are retained verbatim, including their source-local IDs. The canonical ledger above is the deduplicated status record; source IDs are not reused for status tracking.

- [x] fixed C1 — Converted-lead qualification/reconversion and archived-assessment reopening are rejected (Pass 1/2, F-C1, Q-C1/Q-C3, S-C1).
- [x] fixed C2 — Assessment archive is tenant-admin-only and hidden from members (Pass 1/2, F-C2, Q-C2).
- [x] fixed C3 — Nurture resume/reactivation is tenant-admin-only and hidden from members (Pass 1/2, F-C3, Q-I14, S-I2).
- [x] fixed I1 — Sales handoff and CRM conversion share an outer transaction (Pass 1/2, S-I4, Q-I18).
- [x] fixed I2 — Handoff replay is idempotent and follow-up tasks are deduplicated (Pass 1/2, Q-I19).
- [x] fixed I3 — `LeadNurtureEnrollment` has per-tenant `(tenant, number)` uniqueness in migration `0003_leadnurtureenrollment_tenant_number_uniq` (Pass 1/2, Q-I16, S-M1).
- [x] fixed I4 — Routing JSON rejects unhashable fields/operators, nested/unbounded values, and non-finite numbers (Pass 1/2, Q-I9/Q-I10, S-M2).
- [x] fixed I5 — Score correction validates inverse delta in the form and catches service validation errors (Pass 1/2, Q-I2, F-I7, S-M3).
- [x] fixed I6 — A score event can have one correction, while idempotency-key replay compares the complete payload (Pass 1/2, Q-I1/Q-I3, S-I5).
- [x] fixed I7 — Qualification transitions append transition-specific compensating score facts (Pass 1/2, Q-I4, S-I5).
- [x] fixed I8 — Preview and persisted routing reject converted leads and archived assessments (Pass 1/2, Q-I6/Q-I7, S-I9).
- [x] fixed I9 — Qualification invokes deterministic routing after a qualified decision (Pass 1/2, Q-I5).
- [x] fixed I10 — Round-robin capacity excludes the target lead and groups owner counts (Pass 1/2, S-I9, PI4).
- [x] fixed I11 — Invalid activation input is rejected before the lifecycle service runs (Pass 1/2, Q-I11, F-I8, S-M4).
- [x] fixed I12 — Nurture exit reasons are constrained by target status (Pass 1/2, Q-I12, S-I3).
- [x] fixed I13 — Convert-exit is admin-gated and requires a verified CRM opportunity (Pass 1/2, Q-I13, S-I3).
- [x] fixed I14 — Enrollment identity fields are editable only while pending, including admin protection (Pass 1/2, Q-I15, S-I3/S-I7).
- [x] fixed I15 — Consent evidence and Sales qualification free text are redacted from generic audit changes (Pass 1/2, S-I8).
- [x] fixed I16 — Dedicated rule preview evaluates the selected rule (Pass 1/2, Q-I8, F-I5).
- [x] fixed I17 — Qualification route preview is linked and rendered (Pass 1/2, F-I3).
- [x] fixed I18 — Recompute lead IDs use `as_db_int` and reject zero/overflow values (Pass 1/2, F-I3, S-M5).
- [x] fixed I19 — Routing owners, fallback owners, territory managers, and admin selectors are tenant/activity validated (Pass 2, S-M7).
- [x] fixed I20 — CRM ordinary lead forms expose no score/rating workflow fields; member forms omit status/owner and conversion is admin-gated (S-I1).
- [x] fixed I21 — Lead-scoped Sales lists, details, actions, and overview querysets apply configured Sales data scope (S-I6).
- [~] skipped — S-I6 routing-rule configuration scope — routing rules are tenant-wide configuration with no truthful row owner; applying `last_assigned_owner` would hide unassigned rules and misrepresent access.
- [x] fixed I22 — Django admin cannot mutate post-activation identity/consent or terminal qualification fields (S-I7).
- [x] fixed I23 — CRM conversion detects an existing source opportunity and does not mint duplicate identity rows (S-C1).
- [x] fixed M1 — Fixed, territory, and round-robin persisted assignments update last-assignment metadata (Pass 1/2, Q-M1).
- [x] fixed M2 — Contracted Sales context keys are supplied where templates consume them (Pass 2).
- [x] fixed M3 — Overview links to CRM capture and campaign registers (Pass 2).
- [x] fixed — M4 documentation and Sales skill ownership — `README.md`, `NavERP.md`, `NavERP-ERD.md`, and `.claude/skills/sales/SKILL.md` now describe 8.1's as-built boundary; concurrent documentation changes were preserved.
- [x] fixed M5 — `/sales/` now has a staff root route (Pass 2, Q-M3).
- [x] fixed M6 — Routing conditions render as copyable JSON (Pass 2, F-M3).
- [x] fixed M7 — Detail pages expose consistent action controls/sidebar actions (Pass 2, F-I3).
- [x] fixed F-I1 — Overview conversion uses a CSRF-protected POST handoff control rather than a GET link (Pass 3, Q-M2).
- [x] fixed F-I2 — Admin-only routing, handoff, activation, resume, and archive controls are hidden from members (Pass 3, S-M8).
- [x] fixed F-I4 — Paused enrollment preserves its next-touch target on resume (Pass 3).
- [x] fixed F-I6 — Sales list filters have accessible labels (Pass 3).
- [x] fixed F-I9 — Nurture form explains active-purpose/evidence prerequisites (Pass 3).
- [x] fixed F-I10 — Overview distinguishes Sales qualification from CRM state and labels handoff as conversion (Pass 3).
- [x] fixed F-I11 — Detail pages render recorder, assignment, and assessment evidence (Pass 3).
- [x] fixed F-M1 — Stat icon modifiers use the theme's defined colour names (Pass 3).
- [x] fixed F-M2 — Status badges cover qualified, partial, disqualified, pending, completed, and terminal states (Pass 3).
- [x] fixed F-M4 — GET preview forms do not emit CSRF tokens (Pass 3).
- [x] fixed F-M5 — Complete, reply, pause, and cancel actions confirm destructive transitions (Pass 3).
- [x] fixed F-M6 — Overview derives nurture state from all displayed leads with separators (Pass 3, I19).
- [x] fixed PI1 — Overview duplicate detection matches only the bounded displayed-lead set (Pass 4, I19).
- [x] fixed PI4 — Round-robin capacity uses grouped counts and excludes the target lead; the separate CRM index redesign remains outside this fix (Pass 4, I10).
- [x] fixed PM1 — Qualification preview/detail enrollment queries select their CRM campaign relation (Pass 4).
- [~] skipped — PI2/PI2 unbounded lead selectors — replacing every tenant selector with a searchable bounded control is an app-wide selector redesign and would risk hiding valid leads; correctness and tenant isolation were fixed without truncating choices.
- [~] skipped — PI3/PI3 unbounded all-rule preview evaluation — the selected-rule defect is fixed, but truncating all-rule matching would return false negatives; this needs a product-wide preview/search design.
- [~] skipped — PI5/PI5 full-history score recomputation — replacing the append-only projection with a new raw-projection/index design is outside this bounded correctness fix.
- [~] skipped — PI6/PI6 app-wide indexes and date-filter redesign — no Sales-wide selector/index migration was undertaken; only correctness-relevant bounded query changes were made.
- [x] fixed PI7 — Replay uses bounded task lookup and reuses the open follow-up row instead of appending a duplicate (Pass 4, I2).
- [~] skipped — PM2 bulk nurture exits — per-row locked transitions preserve the required audit/transition semantics; a bulk update redesign is performance-only and was explicitly deferred.

No unclassified canonical finding remains open; the explicitly marked skips are deliberate scope/performance exceptions. Verification limitations caused only by unrelated shared-tree work are recorded in the final report.

## Follow-up contract/runtime fixes

- [x] fixed — Restored optional `notes` to `LeadNurtureExitForm`; lifecycle views now pass the contracted value.
- [x] fixed — Archive validation now requires `assessed_by`, and `assessed_at` is stamped for archive decisions; the existing service supplies the acting admin without changing seed shapes or migrations.
- [x] fixed — CRM member lead forms skip workflow-field errors when `status`/`owner` are removed, while admin converted-lead reopen and reassignment checks remain intact.

## Fixer verification

- `manage.py check`: passed.
- `manage.py makemigrations sales --check --dry-run`: passed with no Sales changes.
- `sales/migrations/0003_leadnurtureenrollment_tenant_number_uniq.py`: applied to the development database.
- `seed_sales`: the 8.1-only tree completed twice; both current direct reruns fail before 8.1 work because the concurrent 8.3 seeder queries the unrelated, not-yet-migrated `crm_opportunity.currency_id` column.
- Isolated `config.settings_test` Sales lifecycle/smoke module: 10 passed.
- Existing CRM form, conversion/security, and view tests: 175 passed under `config.settings_test` with migrations disabled for the shared-tree model drift.
- Sales template compilation: 12 passed; Sales URL reversals: 39 passed.
- Full-project migration drift and the direct development `seed_sales` rerun remain blocked only by unrelated Projects/CRM/8.3 changes; no unrelated file was changed by this fixer.


## Pass 1 — code-reviewer

### Critical

- **C1 — Converted-lead qualification can undo conversion.** `apps/sales/services.py:150` can project a later qualification decision onto a `converted` CRM lead. Reject decisions for converted leads under the locked lead row and hide the actions in the detail template.
- **C2 — Archive bypasses tenant-admin authorization.** `apps/sales/views/LeadManagement/LeadQualifications.py:145` allows ordinary members to archive a meaningful assessment. Gate archive with `tenant_admin_required` and hide it from members.
- **C3 — Members can reactivate paused nurture.** `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:116` allows `/resume/` without the admin gate. Gate resume and hide the action for members.

### Important

- **I1 — Handoff side effects are not atomic with conversion.** `apps/sales/services.py:378` and `apps/crm/views/CoreData/Leads.py:73` split conversion from nurture exits/tasks/audit. Use one outer transaction.
- **I2 — Repeated handoff duplicates follow-up tasks/audit.** `apps/sales/services.py:380` creates another task after an already-converted lead. Make replay an idempotent no-op and deduplicate tasks.
- **I3 — Enrollment numbers lack per-tenant uniqueness.** `apps/sales/models/LeadManagement/LeadNurtureEnrollments.py:54` has no `(tenant, number)` constraint. Add it and migrate.
- **I4 — Malformed routing JSON can raise.** `apps/sales/models/LeadManagement/LeadRoutingRules.py:46` uses set membership before type checks and accepts non-standard finite-number cases. Validate field/operator strings strictly and reject non-finite JSON values.
- **I5 — Invalid correction delta can 500.** `apps/sales/views/LeadManagement/LeadScoreEvents.py:84` lets a form-valid non-inverse delta reach an uncaught `ValidationError`. Validate in the form and catch defensively.
- **I6 — An event can be corrected repeatedly.** `apps/sales/services.py:93` lacks one-correction/idempotency enforcement. Add a deterministic correction key/constraint.
- **I7 — Qualification transitions do not compensate prior score facts.** `apps/sales/services.py:153` reuses a permanent status key, so repeat transitions do not create a compensating ledger. Append transition-specific inverse facts.
- **I8 — Routing accepts converted leads and archived assessments.** `apps/sales/services.py:261` needs an explicit unrouted result for both preview and persisted run.
- **I9 — Qualification does not invoke routing.** `apps/sales/services.py:154` never calls the resolver, so qualification does not assign an owner/task.
- **I10 — Round-robin capacity counts the target lead.** `apps/sales/services.py:250` can skip the current owner incorrectly. Exclude `lead.pk` from open-lead counts.
- **I11 — Invalid activation input still activates.** `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:80` uses `None` after form failure. Stop before calling the service.
- **I12 — Exit reasons are not transition-specific.** `apps/sales/forms/LeadManagement/LeadNurtureEnrollments.py:30` accepts contradictory reasons. Enforce a target/reason map.
- **I13 — Members can forge a converted nurture exit.** `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:142` does not verify CRM conversion. Gate it to verified conversion or make it internal.
- **I14 — Paused enrollments remain editable after activation.** `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:59` should allow ordinary edits only while pending.
- **I15 — Consent evidence enters audit changes.** `apps/sales/forms/LeadManagement/LeadNurtureEnrollments.py:10` exposes a sensitive evidence field to the generic CRUD audit serializer. Redact it.
- **I16 — Rule preview can show another rule's owner.** `apps/sales/views/LeadManagement/LeadRoutingRules.py:82` omits `rule=obj` from `preview_routing`.
- **I17 — Qualification route preview has no rendered UI.** `apps/sales/views/LeadManagement/LeadQualifications.py:167` computes a result that the detail template does not display.
- **I18 — Oversized recompute IDs bypass the integer guard.** `apps/sales/views/LeadManagement/LeadScoreEvents.py:109` should use `as_db_int` and reject zero/overflow values.

### Minor

- **M1 — Fixed/territory assignments do not update last-assignment metadata.** `apps/sales/services.py:296` updates cursor/last owner only for round robin; update metadata for every successful persisted run.

## Verification noted by reviewer

`manage.py check`, migration drift check, all 38 Sales route reversals, and 12 template compilations passed.

## Pass 2 — explorer

### Critical

- **C1 — Converted-lead qualification can undo conversion.** `apps/sales/services.py:150-152` and `apps/sales/views/LeadManagement/LeadQualifications.py:135-136` can change a converted CRM lead back to qualified/unqualified. Reject the decision and hide actions.
- **C2 — Members can archive meaningful assessments.** `apps/sales/views/LeadManagement/LeadQualifications.py:145-148` exposes archive to every logged-in user and `templates/sales/leadmanagement/leadqualification/detail.html:18` exposes the form.
- **C3 — Members can reactivate paused nurture.** `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:116-119` makes resume login-only while activation is admin-gated; the detail template exposes resume.

### Important

- **I1 — Handoff is neither atomic nor replay-idempotent.** `apps/sales/services.py:370-392` and `apps/crm/services.py:12-41` split conversion from exits/tasks/audit; replay creates another task.
- **I2 — Nurture numbers are not unique per tenant.** `apps/sales/models/LeadManagement/LeadNurtureEnrollments.py:54-60` and migration 0001 lack `(tenant, number)`.
- **I3 — Routing JSON can raise or accept unsafe values.** `apps/sales/models/LeadManagement/LeadRoutingRules.py:43-61` checks set membership before type checks, does not bound list members, and accepts non-standard numeric JSON.
- **I4 — Correction workflow can 500 or double-append.** `apps/sales/views/LeadManagement/LeadScoreEvents.py:83-100` lacks inverse validation/catch; `apps/sales/services.py:87-92` lacks correction uniqueness.
- **I5 — Idempotency replay accepts conflicting payloads.** `apps/sales/services.py:87-92` returns an existing event without comparing event type/delta/reason/source.
- **I6 — Qualification transitions do not compensate prior score facts.** `apps/sales/services.py:150-159` uses permanent status keys and no inverse transition facts.
- **I7 — Qualification never invokes routing.** `apps/sales/services.py:150-160` omits the resolver, owner assignment, and follow-up task.
- **I8 — Routing accepts converted leads/archived assessments and miscounts capacity.** `apps/sales/services.py:260-309` lacks eligibility guards and includes the target lead in capacity counts.
- **I9 — Invalid activation input still activates.** `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:79-82` calls the service after form failure.
- **I10 — Nurture exit reasons/conversion exits are untrustworthy.** `apps/sales/forms/LeadManagement/LeadNurtureEnrollments.py:29-31` and `apps/sales/services.py:337-361` do not enforce target/reason compatibility or verify CRM conversion.
- **I11 — Paused/active enrollment edits bypass lifecycle controls.** `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:56-62` and `apps/sales/admin.py:44-51` leave post-activation identity fields editable.
- **I12 — Consent evidence is copied into immutable audit logs.** `apps/sales/forms/LeadManagement/LeadNurtureEnrollments.py:10` exposes it to the generic CRUD audit serializer.
- **I13 — Rule-specific preview can show another rule.** The dedicated preview route omits `rule=obj` in `apps/sales/views/LeadManagement/LeadRoutingRules.py:76-89`.
- **I14 — Qualification preview and several actions have no staff UI.** `apps/sales/views/LeadManagement/LeadQualifications.py:160-175` computes a result the detail template does not render; score recompute, qualification partial/recalculate, and nurture convert-exit are not linked.
- **I15 — Oversized recompute IDs can overflow.** `apps/sales/views/LeadManagement/LeadScoreEvents.py:108-111` uses `isdecimal()` rather than `as_db_int()`.
- **I16 — Admin can create cross-tenant routing ownership.** `apps/sales/models/LeadManagement/LeadRoutingRules.py:84` and admin M2M do not validate every eligible owner/territory manager tenant.
- **I17 — Seed can reuse a same-name non-drip campaign.** `apps/sales/management/commands/seed_sales.py:141-151` looks up only tenant/name and may later fail activation.
- **I18 — Overview conversion is a GET link to a POST-only CRM view.** `templates/sales/overview.html:6` renders a plain anchor to `crm:lead_convert`.
- **I19 — Overview truncates enrollments before deriving lead cells.** `apps/sales/views/LeadManagement/Overview.py:20` and `templates/sales/overview.html:6` can show blank nurture state for older rows.

### Minor

- **M1 — Several contracted context keys are unused or absent.** Nurture create/edit omit `leads`, `drip_campaigns`, `consent_purposes`, and `owners`; overview aliases `recent_activity`; some action forms are ignored by templates.
- **M2 — Fixed/territory routing leaves last-assignment metadata blank.** `apps/sales/services.py:296-303` updates metadata only for round robin.
- **M3 — Overview omits CRM capture/campaign links.** `templates/sales/overview.html:4-10` has no `crm:formsubmission_list` or campaign link.
- **M4 — Documentation ownership/status remains stale.** `NavERP.md:69`, `README.md:1201`, and `NavERP-ERD.md:470` still describe Module 8/Sales ownership incorrectly; the Sales skill is absent.
- **M5 — `/sales/` has no root route.** `config/urls.py:20` mounts the app, but `apps/sales/urls/__init__.py:9-15` defines no root redirect; `/sales/` is 404.
- **M6 — Routing conditions display Python repr, not copyable JSON.** `templates/sales/leadmanagement/leadroutingrule/detail.html:10` renders `{{ obj.conditions }}` directly.
- **M7 — Detail actions are not in a consistent Actions sidebar.** Qualification, routing, and nurture details use page headers only.

## Pass 3 — frontend-reviewer

### Critical

- **F-C1 — Converted leads expose qualification decisions.** `templates/sales/leadmanagement/leadqualification/detail.html:15-18` only checks archived state, while the service can change a converted CRM lead back to qualified/unqualified. Hide actions and reject server-side.
- **F-C2 — Archive is exposed to ordinary staff.** `templates/sales/leadmanagement/leadqualification/detail.html:18` and `apps/sales/views/LeadManagement/LeadQualifications.py:145-148` let members archive meaningful assessments. Gate and hide for admins.
- **F-C3 — Paused nurture resume is exposed to ordinary staff.** `templates/sales/leadmanagement/leadnurtureenrollment/detail.html:13` and `apps/sales/views/LeadManagement/LeadNurtureEnrollments.py:116-119` bypass the activation boundary. Gate and hide for admins.

### Important

- **F-I1 — Overview conversion is a broken GET link.** `templates/sales/overview.html:6` links to a POST-only CRM conversion view. Use a CSRF-protected POST form or a safe confirmation page.
- **F-I2 — Admin-only controls are visible to ordinary staff.** New Rule, Hand Off, and Activate are not conditionally hidden in `leadroutingrule/list.html:4`, `overview.html:6`, and `leadnurtureenrollment/detail.html:12`.
- **F-I3 — Several actions have no staff entry point.** Qualification partial/recalculate/route-preview, score recompute, and detail-level delete actions are not linked from templates.
- **F-I4 — Paused enrollment has competing Activate/Resume controls.** `leadnurtureenrollment/detail.html:12-13` can overwrite the existing next-touch target. Show Activate only for pending and preserve the target on Resume.
- **F-I5 — Rule preview can display a different rule.** The dedicated preview route omits `rule=obj` in `LeadRoutingRules.py:76-89`.
- **F-I6 — List filter selects lack accessible names.** Unlabelled controls occur in score, qualification, routing, and nurture list templates.
- **F-I7 — Editable inverse delta can 500.** `leadscoreevent/detail.html:29` and `LeadScoreEvents.py:83-100` allow a non-inverse form-valid delta to escape as a server error.
- **F-I8 — Invalid activation dates are silently discarded.** `leadnurtureenrollment/detail.html:12` and `LeadNurtureEnrollments.py:79-82` activate after form failure.
- **F-I9 — Consent activation prerequisites are not communicated.** `leadnurtureenrollment/form.html:5-6` does not explain that an active purpose is required before activation.
- **F-I10 — Overview overstates readiness/execution.** `Overview.py:32-37` counts CRM status as Sales qualification; the board also needs a clear state-only nurture warning and a “Convert to opportunity” label.
- **F-I11 — Detail pages omit audit evidence.** Qualification MEDDIC/notes/review, routing eligible owners, and score recorder/receipt time are not rendered.

### Minor

- **F-M1 — Stat icon modifiers use invalid names.** `overview.html:5` uses `stat-icon-blue/green/amber/purple`; `theme.css:259-264` defines `stat-icon blue/green/orange/purple/slate`.
- **F-M2 — Status badge branches are incomplete.** Disqualified and pending/completed states fall through to muted in overview/nurture templates.
- **F-M3 — Routing conditions display Python repr.** `leadroutingrule/detail.html:10` renders the list directly instead of copyable JSON.
- **F-M4 — GET preview form includes a CSRF token.** `leadroutingrule/detail.html:11` can expose the token in history/logs; the read-only GET form does not need it.
- **F-M5 — Complete/replied nurture exits lack confirmation.** `leadnurtureenrollment/detail.html:14` confirms Cancel only.
- **F-M6 — Overview nurture cells can be incomplete/ambiguous.** `Overview.py:20` limits context to 20 rows and the template prints multiple states without separators.

## Frontend verification

## Pass 4 — performance-reviewer

### Critical

None.

### Important

- **PI1 — Overview duplicate detection materializes the entire tenant.** `apps/sales/views/LeadManagement/Overview.py:22-30` loads all leads/contact methods into Python to show 20 warnings. Match only displayed leads in bounded chunks and consider a normalized contact index.
- **PI2 — Lead selectors are unbounded across pages.** `apps/sales/forms/_common.py:44-47` and score/routing/qualification/nurture pages render every tenant lead as an option, causing linear DOM/memory growth. Use bounded searchable selectors without silently hiding valid leads.
- **PI3 — Rule preview expands into an unbounded all-rule JSON evaluation.** `LeadRoutingRules.py:76-88` omits `rule=obj`, so preview loads all active rules/owners; pass the selected rule and bound all-rule evaluation.
- **PI4 — Round-robin capacity performs one COUNT per owner under locks.** `apps/sales/services.py:239-257` issues O(owner count) queries with no CRM owner/status index. Group counts in one query, exclude the target lead, and consider a CRM index.
- **PI5 — Every score append recomputes full history under lock.** `apps/sales/services.py:51-58,85-120` makes cumulative work quadratic for one lead. Maintain a locked raw projection and reserve full recompute for repair/expiry.
- **PI6 — Hot list ordering/date filters miss indexes.** Sales models lack tenant/order indexes; score/nurture date filters wrap columns in `DATE()`, defeating B-tree use. Add appropriate indexes and half-open range filters.
- **PI7 — Task replay has no indexed idempotency.** `apps/sales/services.py:304-307` scans tasks and handoff repeats writes. Add a stable idempotency key/index or an equivalent task lookup and replay guard.

### Minor

- **PM1 — Qualification route preview has an enrollment N+1.** `LeadQualifications.py:167-175` omits `select_related("email_campaign")` while the template reads it.
- **PM2 — Bulk nurture exits execute per enrollment.** `services.py:365-367` performs a full transition/audit per row inside the qualification transaction; bounded bulk update/audit could reduce lock time.

## Performance verification

## Pass 5 — qa-smoke-tester

### Critical

- **Q-C1 — Converted leads can be re-qualified.** `POST /sales/qualifications/<id>/qualify/` changed a converted CRM lead back to qualified; `apps/sales/services.py:150-159`.
- **Q-C2 — Archive is member-authorized.** Member archive POST returned 302 and changed status; `LeadQualifications.py:145-148`.
- **Q-C3 — Archived assessments can be re-opened.** `POST /sales/qualifications/<id>/qualify/` changed archived to qualified; `LeadQualifications.py:82-84`.

### Important

- **Q-I1 — Idempotency accepts conflicting score payloads.** Reusing a key with a different event/delta returns the original event; `services.py:87-92`.
- **Q-I2 — Wrong inverse correction returns 500.** `LeadScoreEvents.py:81-100` and `services.py:93-99` allow the service exception to escape.
- **Q-I3 — Repeated correction is accepted.** Two inverse corrections append for one event; `services.py:93-115`.
- **Q-I4 — Qualification does not compensate prior score facts.** Qualified then disqualified produced +20 then -15 without an inverse -20; `services.py:153-159`.
- **Q-I5 — Qualification does not invoke routing.** A catch-all rule left the qualified lead owner null; `services.py:150-160`.
- **Q-I6 — Converted leads are routed.** A catch-all fixed rule assigned a converted lead; `services.py:273-309`.
- **Q-I7 — Archived assessments are routed.** `qualification_status=archived` assigned an owner; `services.py:273-309`.
- **Q-I8 — Rule-specific preview evaluates all rules.** The selected preview returned an unrelated higher-priority rule; `LeadRoutingRules.py:76-82`.
- **Q-I9 — Unhashable routing JSON returns 500.** `field: []`/`operator: []` reaches set membership; `LeadRoutingRules.py:40-49`.
- **Q-I10 — Non-finite routing JSON returns 500.** `NaN` reaches MariaDB JSON validation; `LeadRoutingRules.py:33-49`.
- **Q-I11 — Invalid activation input still activates.** Invalid `next_touch_at` returned 302 and changed pending to active; `LeadNurtureEnrollments.py:75-85`.
- **Q-I12 — Terminal reason is not target-specific.** Complete accepted `exit_reason=cancelled`; `LeadNurtureEnrollments.py:29-31`, `services.py:350-360`.
- **Q-I13 — Converted nurture exit is forgeable.** `/convert-exit/` marked an active enrollment converted while CRM lead remained new; `LeadNurtureEnrollments.py:140-143`.
- **Q-I14 — Members can resume nurture.** Member `/resume/` changed paused to active; `LeadNurtureEnrollments.py:116-119`.
- **Q-I15 — Paused enrollment identity fields remain editable.** Edit changed the lead while paused; `LeadNurtureEnrollments.py:56-62`.
- **Q-I16 — Enrollment numbers are not unique per tenant.** Explicit duplicate `number` values were accepted; `LeadNurtureEnrollments.py:54-60`.
- **Q-I17 — Cross-tenant nurture form input returns 500.** A tenant-B lead caused `RelatedObjectDoesNotExist`; `LeadNurtureEnrollments.py:62-67`.
- **Q-I18 — CRM handoff is not atomic.** A task failure left the converted lead/opportunity persisted; `services.py:370-391`.
- **Q-I19 — Handoff replay duplicates tasks.** Replay kept one opportunity but created two tasks; `services.py:378-390`, `crm/services.py:14-17`.

### Minor

- **Q-M1 — Fixed/territory assignment metadata is not recorded.** Last-assignment fields remain null; `services.py:296-303`.
- **Q-M2 — Overview CRM conversion link is broken.** GET to the anchor target returns 405; `overview.html:6`.
- **Q-M3 — `/sales/` has no root route.** `GET /sales/` returned 404; `sales/urls/__init__.py:9-15`.

## QA verification

## Pass 6 — security-reviewer

### Critical

- **S-C1 — Converted leads can be re-qualified and reconverted.** `apps/sales/services.py:141-159`, `apps/crm/services.py:14-40`, and `LeadQualifications.py:102-124` let a member change converted status back to qualified, then create another Party/Contact/Opportunity. Lock/recheck terminal state, reject converted/archived decisions, and make conversion detect existing identity/opportunity.

### Important

- **S-I1 — Lower-privilege CRM paths bypass Sales qualification/handoff gates.** `apps/crm/forms/CoreData/Leads.py:11-12` and `LeadViews.py:66-77` allow members to edit status/owner and convert directly. Remove workflow fields from the generic form and enforce one explicit lifecycle boundary.
- **S-I2 — Members can archive and reactivate through alternate actions.** `LeadQualifications.py:145-148` and `LeadNurtureEnrollments.py:116-119` bypass role gates; centralize transition authorization in the service.
- **S-I3 — Nurture lifecycle/consent invariants are forgeable.** `LeadNurtureEnrollments.py:29-31,56-62,90-105,140-143` and `services.py:312-360` allow contradictory exits, post-activation identity edits, and forged conversion; activation does not lock the lead.
- **S-I4 — Handoff is not atomic or replay-idempotent.** `services.py:370-391`, `crm/services.py:12-41`, and the CRM view split conversion from exits/tasks/audit; replay duplicates tasks.
- **S-I5 — Score events can replay, repeatedly correct, or suppress transitions.** `services.py:84-120,150-159` lacks payload comparison/one-correction enforcement/compensating qualification facts.
- **S-I6 — Configured Sales module row-level scopes are ignored.** `Overview.py:17-30` and all Sales lists/details/actions never call `apply_data_scope`; build a scoped lead queryset and use it everywhere.
- **S-I7 — Django admin bypasses lifecycle controls.** `apps/sales/admin.py:24-51` leaves post-activation identity/consent and qualified assessment fields editable.
- **S-I8 — Sensitive qualification/consent text enters immutable audit logs.** `LeadQualifications.py:10-16`, `LeadNurtureEnrollments.py:10`, and `apps/core/crud.py:217-219,270-280` serialize free text; redact/allowlist these fields.
- **S-I9 — Routing capacity is race-prone and owner eligibility is not revalidated.** `services.py:239-257,273-303` counts under separate locks, includes the target lead, and can select suspended/foreign owners.

### Minor

- **S-M1 — Enrollment numbers are not unique per tenant.** `LeadNurtureEnrollments.py:54-60`, `_base.py:31-40`, and migration 0001 lack `(tenant, number)` uniqueness.
- **S-M2 — Malformed routing JSON can raise or reach MariaDB as invalid JSON.** `LeadRoutingRules.py:21-63` needs strict type/string/finite validation.
- **S-M3 — Form-valid non-inverse score correction can 500.** `LeadScoreEvents.py:17-34`, `LeadScoreEvents.py:81-100`, and `services.py:93-99`.
- **S-M4 — Invalid activation input still activates.** `LeadNurtureEnrollments.py:75-85` ignores form failure.
- **S-M5 — Oversized recompute IDs bypass the integer guard.** `LeadScoreEvents.py:103-115` uses `isdecimal()`.
- **S-M6 — Cross-tenant nurture FK input fails with 500.** `LeadNurtureEnrollments.py:62-67` dereferences a missing required relation after form rejection.
- **S-M7 — Foreign routing owners/territory managers can enter through admin.** `LeadRoutingRules.py:82-116` and admin M2M/FK scopes are not tenant-safe.
- **S-M8 — Member UI exposes admin-only controls.** Routing, overview, and nurture templates show controls whose views are admin-gated.

## Security verification

No ordinary web endpoint IDOR, CSRF bypass, `csrf_exempt`, unsafe redirect, raw SQL, eval/dynamic import, SSRF, unsafe `|safe`, or plaintext secret exposure was found. Primary tenant scoping and POST method gates passed; the findings above are reachable workflow/configuration gaps.
