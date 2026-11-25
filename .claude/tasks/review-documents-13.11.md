# Code Review Findings — Module 13.11 (Workflow Automation & BPM)

- **App / Scope**: `apps/documents/` (Workflow Automation & BPM — 13.11)
- **Diff Range**: `94f9702edf6efa95c99eaf54423d2868ab598e66...HEAD`
- **Review Passes Completed (1–6, strictly serial)**:
  1. `code-reviewer` (`64bed511`)
  2. `explorer` (`080f955d`)
  3. `frontend-reviewer` (`90013c00`)
  4. `performance-reviewer` (`337d132e`)
  5. `qa-smoke-tester` report-only (`43192cb5`)
  6. `security-reviewer` (`64bed511`)

---

## Critical

### C1 — Dark-mode (`html.dark`) contrast failure renders pop-once HMAC secret, card headings, and JSON/trace panels unreadable
- **Found by:** frontend-reviewer
- **Locations:**
  - `templates/documents/workflow_automation/webhook_trigger/detail.html:26-30`
  - `templates/documents/workflow_automation/routing_rule/detail.html:135,142,147`
  - `templates/documents/workflow_automation/process_instance/detail.html:95`
  - `templates/documents/workflow_automation/routing_rule/simulator.html:85,111`
  - `templates/documents/workflow_automation/process_definition/designer.html:62,64,75,87,90,99,103,122`
  - All 15 templates in `templates/documents/workflow_automation/` (`<h2 class="... text-slate-800">` and `text-slate-700/800/900`)
- **Problem:** Under `html.dark` (`static/css/theme.css:42-58`), `body` text is `#e2e8f0` and `--card-bg` is `#1e293b`. Raw `bg-white` / `bg-slate-50` blocks (including the pop-once `revealed_secret`) inherit `#e2e8f0` text onto white backgrounds, while `text-slate-800` matches `#1e293b` card backgrounds.
- **Fix:** Drop `text-slate-800` on `.card-header h2` elements (or add `dark:text-slate-100`), add `dark:bg-slate-800`/`dark:bg-slate-900`/`dark:text-slate-100`/`dark:border-slate-700` to all `bg-white`/`bg-slate-50`/`bg-amber-50` panels, and give `text-slate-700`/`800`/`900` inside cards/tables explicit `dark:text-slate-200`/`100` pairs.
- **Status:** [x] fixed — dark-mode contrast pairs added across all 15 `workflow_automation` templates (`0cc33938`..`9e959bde`)

### C2 — `.btn.btn-icon.btn-danger` & `.btn.btn-icon.btn-outline` CSS cascade conflict breaks list button contrast and hover state
- **Found by:** frontend-reviewer
- **Locations:**
  - `templates/documents/workflow_automation/process_definition/list.html:163,166,170,178`
  - `templates/documents/workflow_automation/routing_rule/list.html:163,166,169,175`
  - `templates/documents/workflow_automation/process_instance/list.html:167,171,179`
  - `templates/documents/workflow_automation/webhook_trigger/list.html:148,151,157`
- **Problem:** In `static/css/theme.css:274-280`, `.btn-icon` is defined after `.btn-danger` and `.btn-outline`, overriding white danger text with muted grey on red backgrounds and resetting outline borders to transparent.
- **Fix:** Replace `btn btn-icon btn-danger` with `btn btn-icon danger` (`theme.css:280`) and replace `btn btn-icon btn-outline` with `btn btn-icon` across all 4 list templates.
- **Status:** [x] fixed — replaced `btn-danger`/`btn-outline` with `btn-icon` / `danger` modifiers across all 4 list templates (`33f919a5`, `e5e505fd`, `41f75415`, `8d6c9d8c`)

### C3 — `compute_process_analytics` full-table `list(qs)` materialization, unused JOINs, index-defeating `__date` filter, and SLA/terminal WIP miscounting
- **Found by:** performance-reviewer, qa-smoke-tester
- **Locations:**
  - `apps/documents/services/workflow_automation.py:1187-1303`
  - `apps/documents/views/WorkflowAutomation/WorkflowAnalytics.py:26-32`
- **Problem:** `compute_process_analytics` joins 3 unused FKs, loads full JSON/text blobs into Python `list(qs)`, loops in Python for 7 KPIs, wraps `started_at` in `__date` lookups (defeating `doc_dpin_tnt_str_idx`), excludes `"sla_breached"` from `active_wip`, counts cancelled/completed rows in `active_waiting` if trace lacks `exited_at`, ignores `process_def_id` on `top_rules`, and silently returns empty results when `date_from > date_to`.
- **Fix:** Use timezone-aware datetime bounds on `started_at` (`gte`/`lt`), aggregate scalar KPIs (including `status="sla_breached"` in `active_wip`) in one SQL `.aggregate(...)`, drop unused `select_related`, extract percentiles/trace fields via `.values_list(...)` (excluding terminal runs from `active_waiting`), filter `top_rules` by `process_def_id`, and emit a warning message on `date_from > date_to`.
- **Status:** [x] fixed — optimize `compute_process_analytics` SQL aggregation, date bounds, and active WIP + warn on inverted date range (`11a08caf`, `a01b79fc`)

### C4 — Boolean `False` and numeric `0` values coerce to `""` in `evaluate_condition_clause`
- **Found by:** code-reviewer, qa-smoke-tester
- **Locations:** `apps/documents/services/workflow_automation.py:319-358`
- **Problem:** `str(actual or "")` and `str(expected or "")` collapse `False` (e.g. `document.is_locked=False`) and `0` (`current_version_no=0`) to `""`, causing `eq "false"`, `ne "false"`, `in "0, 1"`, `not_in`, `contains`, and `regex_match` to fail or false-match.
- **Fix:** Replace `str(x or "")` with explicit helper `_as_eval_str(val)` preserving `"false"`/`"true"` for booleans and `"0"` for zero (`"" if val is None else ("true" if val is True else ("false" if val is False else str(val)))`).
- **Status:** [x] fixed — preserve boolean `False` and numeric `0` in `evaluate_condition_clause` (`d62577eb`)

### C5 — Empty `DocumentMetadataValue` (`value_text=""`) resolves to `"—"` via `display_value`, bypassing `is_empty` and `required_metadata` gates
- **Found by:** code-reviewer, explorer, qa-smoke-tester
- **Locations:** `apps/documents/services/workflow_automation.py:438-440,657-660`
- **Problem:** `build_document_context()` reads `mv.display_value`, returning `"—"` for blank strings, `"Yes"`/`"No"` for booleans, and 80-char truncated JSON, causing `is_empty` and `required_metadata` gates to pass falsely on empty rows.
- **Fix:** Add `_extract_metadata_value(mv)` reading raw typed columns (`value_number`, `value_date`, `value_boolean`, `value_json`, `value_text`) returning `""`/`None` when blank and normalized booleans.
- **Status:** [x] fixed — extract raw typed metadata in `build_document_context` instead of `display_value` (`e27a7ddc`)

### C6 — Seeded `DRUL-00003` fails `.full_clean()` (`target_document_type="invoice"` & `0.80` scale) and `proc_contract` uses `"condition_label"` instead of `"condition"`
- **Found by:** code-reviewer, explorer, qa-smoke-tester
- **Locations:** `apps/documents/management/commands/seed_documents.py:2200,2337-2357`
- **Problem:** `"invoice"` is invalid in `Document.DOCUMENT_TYPE_CHOICES`; OCR `confidence_score` is seeded on 0–100 scale (`98.20`) rather than `0.80`; `proc_contract`'s `n_gw -> n_legal` edge lacks `"condition"`, causing simulation and runtime routing on confidential contracts to fall through to `"Standard"`. Published blueprints are not graph-validated at seed time.
- **Fix:** Change `target_document_type` to valid choice (`"report"` or `""`), change threshold to `"80.0"`, add `"condition": {"source": "document", "field": "classification", "op": "in", "value": ["confidential", "restricted"]}` to `seed_documents.py:2200`, assert `validate_graph()["is_valid"]` for seeded published definitions, and verify existing seeded tenant rows cleanly.
- **Status:** [x] fixed — fix seeded DRUL `target_document_type`, OCR scale, and contract gateway condition (`05288299`)

### C7 — BPM blueprint state machine & authorization bypasses (`launch archived/deprecated/draft`, `publish archived`, `deprecate draft`, non-admin `published` edits, designer active on `archived`)
- **Found by:** code-reviewer, explorer, frontend-reviewer, qa-smoke-tester, security-reviewer
- **Locations:**
  - `apps/documents/views/WorkflowAutomation/DocumentProcessDefinitions.py:185-216,239-321`
  - `apps/documents/forms/WorkflowAutomation/DocumentProcessDefinitions.py:129-153`
  - `apps/documents/forms/WorkflowAutomation/DocumentProcessInstances.py:45-47`
  - `apps/documents/services/workflow_automation.py:827-968`
  - `templates/documents/workflow_automation/process_definition/{detail,designer}.html`
- **Problem:** Instances can be launched from `draft`/`deprecated`/`archived`/inactive definitions; `publish` accepts `archived` records; `deprecate` accepts `draft`/`archived` records; non-admin users can edit `"published"` blueprints or save broken BPMN graphs via `designer` without `@tenant_admin_required` or `validate_process_graph()`; `designer.html` displays active save controls when `archived` and drops unlaned nodes / transition conditions.
- **Fix:** Restrict instance launches to `status="published", is_active=True` in both `DocumentProcessInstanceForm` and `start_process_instance()`; gate edits/designer saves on `status == "published"` to tenant admins AND enforce `validate_process_graph()` in `ProcessDesignerForm.clean()`; reject `archived` in `publish` and non-`published` in `deprecate`; hide Launch/Publish/Save controls in `detail.html`/`designer.html` accordingly, add `"Unassigned / Other Lane"` node card, transition conditions, and `non_field_errors`.
- **Status:** [x] fixed — enforce published active blueprint launches, graph validation, transition state guards, and admin/archived UI sync (`247ab524`, `265c30b3`, `a64a4007`, `ebe9daef`, `dd32c1f2`, `fd63689f`, `172319c8`, `fbc1d9c0`)

### C8 — `advance_process_instance()` ignores transition conditions, skips `DocumentApprovalWorkflow` creation on `approval_subprocess`, lacks `select_for_update()` locking & transition authorization, and drops `escalated`/`rejected`/`cancelled` trace & events
- **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
- **Locations:**
  - `apps/documents/services/workflow_automation.py:745-755,898-910,969-1141`
  - `apps/documents/views/WorkflowAutomation/DocumentProcessInstances.py:218-261`
  - `templates/documents/workflow_automation/process_instance/detail.html:144-190`
- **Problem:** Read-modify-write happens outside `transaction.atomic()` without `select_for_update()`; `advance_process_instance()` ignores `edge.get("condition")` on gateways; entering `approval_subprocess` sets `waiting_approval` with `approval_workflow=None`; any tenant user can force-complete or cancel any instance; `escalated` closes trace cleanly without adding an open `sla_breached` entry or dispatching `process.sla_breached` webhooks/audit; `cancel` leaves trace open (`exited_at=None`) and skips audit logging.
- **Fix:** Acquire `select_for_update()` inside `transaction.atomic()` in `advance_process_instance` and `process_instance_cancel`; evaluate gateway transition `condition`s via `build_document_context()`; share `_spawn_approval_workflow_for_instance()` (setting `due_date`) for both `start` and `advance`; restrict `outcome="completed"` & `cancel` to tenant admin or `initiated_by` (and `advance` to admin or `current_assignee` when assigned) in view + template; emit `DocumentAuditTrail` on reject/escalate/cancel, append open `sla_breached` step + trigger `process.sla_breached` webhooks on escalation, and close open trace step on `cancel`.
- **Status:** [x] fixed — lock advance/cancel, evaluate gateway conditions, spawn approval workflows, enforce transition permissions, and log SLA/reject/cancel events (`d9a9470d`, `97354297`, `783b5639`)

---

## Important

### I1 — Webhook & Routing Rule `create`/`edit` bypass `@tenant_admin_required`
- **Found by:** security-reviewer
- **Locations:**
  - `apps/documents/views/WorkflowAutomation/DocumentWebhookTriggers.py:118-176`
  - `apps/documents/views/WorkflowAutomation/DocumentRoutingRules.py:127-190`
  - `templates/documents/workflow_automation/webhook_trigger/{list,detail}.html`
  - `templates/documents/workflow_automation/routing_rule/{list,detail}.html`
- **Problem:** Non-admin users can create/edit webhooks (capturing HMAC secrets via `_dwhk_secret_reveal` or changing `target_url`/`headers`) and create/edit/toggle active routing rules, bypassing `@tenant_admin_required` on `rotate_secret`/`delete`/`toggle`.
- **Fix:** Decorate `webhook_trigger_create`, `webhook_trigger_edit`, `routing_rule_create`, and `routing_rule_edit` with `@tenant_admin_required` and guard Create/Edit template actions with `{% if user.is_superuser or user.is_tenant_admin %}`.
- **Status:** [x] fixed — require `@tenant_admin_required` on webhook & routing rule create/edit views and gate list/detail UI buttons (`e652375d`, `62ee1a64`, `69e26669`, `dd1cac81`, `dbe77996`, `4b821fde`)

### I2 — `webhook_trigger_test_ping` & `webhook_trigger_simulate_inbound` fail open on invalid/cross-tenant POSTs and inactive triggers
- **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
- **Locations:**
  - `apps/documents/views/WorkflowAutomation/DocumentWebhookTriggers.py:208-284`
  - `templates/documents/workflow_automation/webhook_trigger/detail.html:154`
- **Problem:** Invalid `WebhookTestPingForm` POSTs still fire and log success; `simulate_inbound` runs when `is_active=False` and accepts non-numeric/foreign `document_id` cleanly as `None`; inbound simulator card hides when `process_definition` is blank and shows on outbound triggers that link a `process_definition`.
- **Fix:** Add explicit error/redirect branches rejecting invalid `WebhookTestPingForm` and non-empty invalid/foreign `document_id`; block `simulate_inbound` when `not webhook.is_active`; show inbound simulation card when `webhook.direction == 'inbound_webhook'`.
- **Status:** [x] fixed — reject invalid test ping forms, inactive inbound triggers, and bad document IDs + show inbound card by direction (`c6c1b53e`, `df228247`)

### I3 — Multi-tenant form FK exposure (`owner`/`current_assignee`/`tenant=None`), cross-document `version`, and service-boundary tenant assertions
- **Found by:** code-reviewer, explorer, security-reviewer
- **Locations:**
  - `apps/documents/forms/WorkflowAutomation/{DocumentProcessDefinitions,DocumentRoutingRules,DocumentProcessInstances,DocumentWebhookTriggers}.py`
  - `apps/documents/services/workflow_automation.py:586-968`
- **Problem:** Forms omit `tenant=tenant` on `owner`/`current_assignee`, omit `else: queryset = Model.objects.none()` when `self.tenant is None`, allow mismatched `version.document_id != document.pk`, and service entry points don't assert `document.tenant_id == tenant.id` and matching FK tenants before writing.
- **Fix:** Filter `owner`/`current_assignee` by `tenant=tenant, is_active=True`, add `else: .none()` fallbacks for every tenant-scoped field, enforce `version.document_id == document.pk` in `DocumentProcessInstanceForm.clean()`, and verify tenant ownership at `evaluate_routing_rules` / `start_process_instance` service boundaries. *(Add Notes item for app-wide `if self.tenant:` sibling forms.)*
- **Status:** [x] fixed — add empty queryset fallbacks when tenant missing, filter active tenant users, validate version document ownership, and assert tenant boundaries (`09a228ed`, `4e8f1d47`, `f8334a7b`, `5a96d60c`, `98e88d8c`)

### I4 — Internal 13.11 webhook dispatch gaps (`routing.matched`, `process.sla_breached`, instant-end `process.completed`), missing `filter_document_type`/`direction` filters, and `record_simulated_delivery` race
- **Found by:** code-reviewer, explorer, performance-reviewer
- **Locations:**
  - `apps/documents/services/workflow_automation.py:769-782,913-917,952-967,1005-1011,1078-1105`
  - `apps/documents/models/WorkflowAutomation/DocumentWebhookTriggers.py:214-234`
- **Problem:** Missing webhook dispatch for `routing.matched`, `process.sla_breached`, and direct start->end `process.completed`; missing `filter_document_type` check and `direction__in=("outbound_webhook", "middleware_callback")` filter; `record_simulated_delivery` reads `delivery_history_json` outside `transaction.atomic()` without `select_for_update()`.
- **Fix:** Extract `_dispatch_event_webhooks(...)` enforcing `direction__in`, SQL `process_definition` filter, `filter_document_type`, and `.select_related("tenant")`, call across all 4 events, and lock/combine the update in `record_simulated_delivery`.
- **Status:** [x] fixed — unify `_dispatch_event_webhooks` across all 4 events with direction/type filters and lock `record_simulated_delivery` (`ed81a154`, `5fcce29f`)

### I5 — `process_instance_delete` stale `instance_count`, missing `ProtectedError` on definition delete, and editable immutable-like FKs in `process_instance_edit`
- **Found by:** code-reviewer, explorer, qa-smoke-tester
- **Locations:**
  - `apps/documents/views/WorkflowAutomation/DocumentProcessInstances.py:172-215`
  - `apps/documents/forms/WorkflowAutomation/DocumentProcessInstances.py:22-29`
  - `apps/documents/views/WorkflowAutomation/DocumentProcessDefinitions.py:165-190`
- **Problem:** Deleting an instance leaves `process_definition.instance_count` inflated; edit form permits swapping `process_definition`/`document` mid-flight without resetting `step_trace_json` or updating `instance_count`; definition delete lacks `except ProtectedError` guard.
- **Fix:** Atomically decrement `instance_count` on `process_instance_delete`, disable `process_definition` and `document` on edit (`self.instance.pk`), and catch `ProtectedError` in `process_definition_delete`.
- **Status:** [x] fixed — decrement `instance_count` atomically on delete, disable instance FKs on edit, and catch `ProtectedError` (`1eefe530`, `5742c7f4`, `2362c1ca`)

### I6 — Zero automatic event hooks from DMS 13.1–13.5 / 13.3 approval decisions into 13.11 (undocumented gap or opt-in wiring)
- **Found by:** explorer
- **Locations:** `apps/documents/views/{VersionControl,ApprovalWorkflow,StorageRepository,MetadataIndexing}/*.py`, `.claude/tasks/todo.md:370-375`
- **Problem:** DMS 13.1–13.5 views and 13.3 approval completion handlers never invoke `evaluate_routing_rules`, `start_process_instance`, `dispatch_simulated_webhook`, or advance waiting `DocumentProcessInstance` rows; not yet captured in a gap file.
- **Fix:** Either wire minimal opt-in safe hooks for `13.3` approval-linked instances (`approval_workflow`) if clean without risking regression across existing suites, OR record the cross-module automatic upload/OCR/version/metadata/approval event hook scope formally in `.claude/tasks/gaps-documents-13.11.md` and link it in `todo.md` (Phase 7). *(Evaluate safely; definitely document any deferred automatic hooks in `gaps-documents-13.11.md`.)*
- **Status:** [~] skipped — deferred to Phase 7 gap register (.claude/tasks/gaps-documents-13.11.md): opt-in automatic event-bus triggers across DMS 13.1–13.5 and 13.3 approval callbacks require dedicated cross-sub-module signal design so prior sub-module suites are unaffected

### I7 — `else_branch_enabled`, `block_validation`, simulator toast, `min_confidence` validation, and model-level `conditions_json`/`validation_rules_json` validation gaps
- **Found by:** code-reviewer, explorer, qa-smoke-tester
- **Locations:**
  - `apps/documents/services/workflow_automation.py:649-678,794-800`
  - `apps/documents/models/WorkflowAutomation/DocumentRoutingRules.py:213-216`
  - `apps/documents/views/WorkflowAutomation/DocumentRoutingRules.py:254-256`
- **Problem:** `used_else` ignores `else_action_json["route_action"]` and omits audit log; `block_validation` with empty `validation_rules_json` passes silently; simulator flashes green success when rules are blocked by validation; bad `min_confidence` silently passes (`validation_errors=[]`); `DocumentRoutingRule.clean()` skips `conditions_json`/`validation_rules_json` validation.
- **Fix:** Execute supported else fallback actions with tenant verification + `log_document_event`; fail loudly on malformed `min_confidence` / empty `block_validation` config; enforce operator/regex/validation-rule checks in `DocumentRoutingRule.clean()`; flash warning on simulator validation blocks.
- **Status:** [x] fixed — execute else actions, harden `min_confidence`/`block_validation`, validate rules in model `clean()`, and warn on simulator block (`99b6bb50`, `24a0d176`, `5e4ba649`)

### I8 — ReDoS hardening & `regex_match` error handling
- **Found by:** code-reviewer, security-reviewer
- **Locations:**
  - `apps/documents/services/workflow_automation.py:351-357`
  - `apps/documents/forms/WorkflowAutomation/DocumentRoutingRules.py:144-152`
  - `apps/documents/models/WorkflowAutomation/DocumentRoutingRules.py:213-216`
- **Problem:** Uncapped subject strings + nested quantifiers in user regexes risk worker backtracking stalls; model `clean()` allows invalid regex syntax.
- **Fix:** Reject nested-quantifier patterns, cap regex length `<= 200`, slice subject string (`[:1000]`), wrap `re.search` in `try/except re.error`, and validate at model `clean()`.
- **Status:** [x] fixed — enforce ReDoS validation, subject slicing, and `re.error` handling across service, model, and form (`99b6bb50`, `24a0d176`, `256bb71e`)

### I9 — Latent SSRF hardening (NAT64 `64:ff9b::/96`, short metadata hostnames, dispatch re-check) & `custom_headers` normalization/denylist
- **Found by:** code-reviewer, security-reviewer
- **Locations:**
  - `apps/documents/services/workflow_automation.py:18-172,1145-1184`
  - `apps/documents/models/WorkflowAutomation/DocumentWebhookTriggers.py:169-178`
- **Problem:** Missing `64:ff9b::/96` NAT64 extraction and `metadata`/`instance-data` hostnames in SSRF checks; `DocumentWebhookTrigger.clean()` discards sanitized return of `validate_flat_headers()`; `custom_headers` allows RFC-invalid names, unbounded size, and security headers (`Host`, `Authorization`, `Cookie`, `Content-Length`, `Transfer-Encoding`, `Connection`, `X-NavERP-Signature-256`).
- **Fix:** Add NAT64 + short metadata hostnames + runtime `validate_dms_webhook_url` re-check at dispatch; enforce RFC 7230 token names + size/count limits + denylist in `validate_flat_headers` and assign returned dict in `clean()`.
- **Status:** [x] fixed — harden webhook SSRF with NAT64/metadata blocks, dispatch re-check, and normalized RFC 7230 headers (`a6c00225`, `6d7d42b9`)

### I10 — `get_signing_secret()` swallows `ImproperlyConfigured` decryption errors silently
- **Found by:** code-reviewer, security-reviewer
- **Locations:** `apps/documents/models/WorkflowAutomation/DocumentWebhookTriggers.py:187-193`
- **Problem:** `except Exception: return ""` degrades failed decryption into unsigned webhook envelopes instead of failing closed.
- **Fix:** Call `decrypt(self.signing_secret)` directly without swallowing crypto errors.
- **Status:** [x] fixed — fail closed on signing secret decryption in `get_signing_secret()` (`6d7d42b9`)

### I11 — Django Admin changelist `1 + 3N`/`1 + N` N+1 queries and missing `raw_id_fields`
- **Found by:** performance-reviewer
- **Locations:** `apps/documents/admin.py:410-505`
- **Problem:** New `ModelAdmin` classes omit `list_select_related`, `raw_id_fields`, and `.defer(...)` on large JSON/text fields.
- **Fix:** Configure `list_select_related`, `raw_id_fields`, and `get_queryset().defer(...)` across all four 13.11 admin classes.
- **Status:** [x] fixed — add `list_select_related`, `raw_id_fields`, and changelist `.defer()` across 13.11 admin classes (`7970e684`)

### I12 — Un-deferred `DocumentVersion.extracted_text` / `DocumentOcrJob.extracted_full_text` and lazy FK loads in `build_document_context` & `evaluate_routing_rules`
- **Found by:** performance-reviewer
- **Locations:**
  - `apps/documents/services/workflow_automation.py:429-470,507-510,602-609,686,695-782`
  - `apps/documents/forms/WorkflowAutomation/DocumentRoutingRules.py:206-211`
- **Problem:** `build_document_context` fetches un-projected `DocumentVersion` and `DocumentOcrJob` rows and lazy-loads `department`/`owner`; `evaluate_routing_rules` & `RoutingRuleSimulatorForm` miss nested `select_related`, double-write `DocumentAuditTrail` on `move_to_folder`, and update counters per unmatched rule in loop.
- **Fix:** Use `.values(...)`/`.only(...)` in `build_document_context`, add full `select_related` in `evaluate_routing_rules` & `RoutingRuleSimulatorForm`, consolidate audit logging per rule, and batch unmatched rule counter increments.
- **Status:** [x] fixed — optimize `build_document_context`, routing rule evaluation queries, audit logs, and batched counter updates (`b9f1b470`, `c10077ec`)

### I13 — Bypassed `prefetch_related`, 15 separate `.count()` KPI queries, unused list JOINs / heavy un-deferred JSON blobs, and over-wide dropdowns
- **Found by:** performance-reviewer
- **Locations:** `apps/documents/views/WorkflowAutomation/*.py`, `apps/documents/forms/WorkflowAutomation/*.py`
- **Problem:** `process_definition_detail` wastes prefetches immediately overridden by `.filter().order_by()`; 4 list views execute 3–4 separate count queries and load un-displayed JSON/ciphertext columns + unused `select_related` JOINs; forms load full `DocumentVersion`/`DocumentProcessDefinition` JSON blobs; `webhook_trigger_detail` queries `Document` twice.
- **Fix:** Remove bypassed `prefetch_related`; collapse list KPIs into 1 `.aggregate(...)` per list view; trim unused JOINs and `.defer(...)` large columns on lists; project dropdowns with `.only(...)` and scope `version` by `document_id` when known.
- **Status:** [x] fixed — collapse list KPIs into aggregates, trim JOINs/blobs, and project form/view dropdowns (`92cd36f7`, `f8c6b399`, `fd0ae7e0`, `27a23464`, `dd841859`, `ddfc620b`, `3db3b945`, `3e116256`, `ca04ebf0`, `7c2ea349`)

### I14 — Missing composite DB indexes for hot runtime and list queries (requires migration `0024`)
- **Found by:** performance-reviewer
- **Locations:** `apps/documents/models/WorkflowAutomation/{DocumentProcessInstances,DocumentRoutingRules,DocumentWebhookTriggers}.py`
- **Problem:** Missing composite indexes for `(tenant, department)` and `(tenant, status, -started_at)` on instances, `(tenant, is_active, trigger_event, priority)` and `(tenant, route_action)` on routing rules, and `(tenant, is_active, trigger_event)` on webhook triggers.
- **Fix:** Add all 5 composite indexes (`<= 30` chars) and generate & apply migration `0024`.
- **Status:** [x] fixed — add 5 composite indexes and apply incremental migration 0024 (`f10fb5bf`, `964aefe8`, `eaa6fd59`, `12056469`)

### I15 — Duplicate JSON parsing / pagination / integer-parsing helper logic across 13.11 views and forms
- **Found by:** code-reviewer
- **Locations:** `apps/documents/views/WorkflowAutomation/*.py`, `apps/documents/forms/WorkflowAutomation/*.py`
- **Problem:** Repeated pagination and JSON/integer coercion helpers copy-pasted across files.
- **Fix:** Extract clean shared helpers (e.g. `apps/documents/views/_common.py` or `apps/documents/forms/WorkflowAutomation/_common.py`) and reuse cleanly.
- **Status:** [x] fixed — extract and reuse `parse_json_field_value`, `paginate_queryset`, and `parse_int_param` helpers (`02487d10`, `4612e30d`, `c7b73c74`, `b1af48c2`, `c8b6cc91`, `b728884c`, `21e625ed`, `c74a6f0a`, `095798fb`, `bb0b6efa`, `5ad5a346`)

### I16 — Raw Python `dict`/`list` `repr()` rendered in `routing_rule/detail.html` & `webhook_trigger/detail.html`
- **Found by:** code-reviewer, frontend-reviewer, qa-smoke-tester
- **Locations:**
  - `templates/documents/workflow_automation/routing_rule/detail.html:117,135,142,147`
  - `templates/documents/workflow_automation/webhook_trigger/detail.html:119`
- **Problem:** Python `{'key': 'val'}` and list `['a', 'b']` reprs appear directly in HTML instead of valid formatted JSON / structured rows.
- **Fix:** Pass pre-formatted `json.dumps(..., indent=2)` strings from views (and format `c.value` lists cleanly).
- **Status:** [x] fixed — pass and render formatted JSON payloads and list values on routing rule and webhook detail (`18286f07`, `7b6e45f0`, `7faddcf0`, `6e9db4a7`)

### I17 — Checkbox `.form-group` stacks vertically without `flex-row`, uses missing `form-checkbox` class, and omits checkbox errors
- **Found by:** frontend-reviewer
- **Locations:**
  - `templates/documents/workflow_automation/{process_definition/form.html,routing_rule/form.html,routing_rule/simulator.html,webhook_trigger/form.html}`
  - `apps/documents/forms/WorkflowAutomation/*.py`
- **Problem:** Missing `flex-row` leaves `.form-group`'s `flex-direction: column` stacking checkbox above label, `form-checkbox` is undefined in `theme.css` (`form-check`), and field errors on checkboxes aren't displayed.
- **Fix:** Update widget class to `form-check`, add `flex-row items-center gap-2` in templates, and render `{{ field.errors }}`.
- **Status:** [x] fixed — use `form-check` class, align checkbox rows, and render field errors across forms and templates (`ddd5c730`, `82784290`, `7506c964`, `98ceab54`, `fae3645c`, `f68bbc2b`, `2d25866a`)

### I18 — Pop-once secret banner lacks Copy button; SLA/step/delivery badge severity mismatches on instance & webhook detail
- **Found by:** code-reviewer, frontend-reviewer
- **Locations:**
  - `templates/documents/workflow_automation/webhook_trigger/detail.html:25-33,117`
  - `templates/documents/workflow_automation/process_instance/detail.html:19,128`
- **Problem:** Revealed secret banner has no one-click Copy button; instance detail checks only `is_sla_breached` (`"SLA On Track"` on red badge when `status == 'sla_breached'`); step outcomes `rejected`/`escalated` and delivery log `failed` render as `badge-info`.
- **Fix:** Add safe Copy button (`navigator.clipboard.writeText`), match `sla_badge` condition on line 19, and color-code outcome and delivery status pills accurately.
- **Status:** [x] fixed — add clipboard copy button for secret banner and align SLA/step/delivery status badges (`41c45b09`, `07167c76`)

### I19 — Missing `.form-help` schema guidance on JSON fields & missing instance telemetry (`error_message`, `context_variables_json`, `version`, `department`, `blueprint_nodes`, `non_field_errors`)
- **Found by:** explorer, frontend-reviewer
- **Locations:** `templates/documents/workflow_automation/{*/form.html,process_definition/designer.html,process_instance/detail.html,routing_rule/simulator.html}`
- **Problem:** JSON textareas lack schema hints; `process_instance/detail.html` omits `error_message`, formatted `context_variables_json`, `version`, `department`, and visual `blueprint_nodes` progression; `advance_form` and `simulator` omit `non_field_errors` / field errors.
- **Fix:** Add `<div class="form-help">` schema hints, render missing instance fields & visual node progression bar, and show form errors cleanly.
- **Status:** [x] fixed — add `.form-help` schema hints, instance telemetry & node progression, and form error rendering (`c4247e0f`, `19373855`, `c749f6b6`, `cb0f1ee6`, `f010c0fd`, `e324a16f`, `95064422`, `1d8a5cc3`)

### I20 — Contract doc drift on `validate_graph()` return type
- **Found by:** explorer
- **Locations:** `.claude/tasks/contract-documents-13.11.md:107`, `.claude/tasks/todo.md:268`
- **Problem:** Contract specifies a 3-tuple `(is_valid, errors, warnings)` while code returns `dict` `{"is_valid", "errors", "warnings", "node_count", "transition_count"}`.
- **Fix:** Update `.claude/tasks/contract-documents-13.11.md` and `todo.md` to document the implemented dict return structure.
- **Status:** [x] fixed — align `validate_graph()` / `validate_process_graph()` dict return contract in spec and todo (`b7670f99`, `91fa026e`)

---

## Minor

### M1 — Stale `doc_ctx` across sequential rules & substring/empty `source_folder.slug` tag match
- **Found by:** code-reviewer, qa-smoke-tester
- **Locations:** `apps/documents/services/workflow_automation.py:614,628-634`
- **Problem:** Later live rules see stale `doc_ctx`; `folder_slug not in tags_lower` matches substrings and empty slugs.
- **Fix:** Refresh `doc_ctx` after mutating rule execution and match exact comma-split stripped tags with `bool(folder_slug)`.
- **Status:** [x] fixed — refresh `doc_ctx` after live rules and exact-match `source_folder` tags (`00879457`)

### M2 — Lazy `Tenant` / `ProcessDefinition` / `OrgUnit` queries and bare `.save()` in `advance_process_instance`
- **Found by:** performance-reviewer
- **Locations:**
  - `apps/documents/services/workflow_automation.py:926,1082,1132`
  - `apps/documents/views/WorkflowAutomation/DocumentProcessInstances.py:205,221-226,250`
  - `apps/documents/views/WorkflowAutomation/DocumentWebhookTriggers.py:209,243-245`
- **Problem:** `start_process_instance` accesses `.department` instead of `_id`; delete/cancel views call `__str__` (`process_definition.code`) without `select_related("process_definition")`; advance/ping views omit `select_related("tenant")`; `advance_process_instance` calls bare `.save()`.
- **Fix:** Add `select_related("tenant", "process_definition")`, use `*_id` fallback, and pass explicit `update_fields` on `advance_process_instance`.
- **Status:** [x] fixed — use `department_id`, `select_related` on instance/webhook actions, and `update_fields` on advance (`1e178dd1`, `19214e70`, `89888192`, `d9a9470d`)

### M3 — `DocumentProcessDefinitionForm` `code` normalization timing & `None`-safe `< 1` model `clean()` guards
- **Found by:** code-reviewer
- **Locations:**
  - `apps/documents/models/WorkflowAutomation/DocumentProcessDefinitions.py:148-160`
  - `apps/documents/models/WorkflowAutomation/DocumentRoutingRules.py:213-216`
  - `apps/documents/forms/WorkflowAutomation/DocumentProcessDefinitions.py:66-95`
- **Problem:** Lowercase `code` checked before uppercasing; integer `< 1` checks fail with `TypeError` when `None`.
- **Fix:** Normalize `code` in `clean_code()` and verify `(tenant, code, version_number)` uniqueness in `clean()`; guard integer `< 1` checks with `is not None`.
- **Status:** [x] fixed — guard `None` integers in `clean()` and normalize `code` before uniqueness check (`66444086`, `cf9eed9c`)

### M4 — Partial JSON default overwrite on definition create & `write_audit_log` outside `transaction.atomic()`
- **Found by:** code-reviewer
- **Locations:**
  - `apps/documents/views/WorkflowAutomation/DocumentProcessDefinitions.py:159-162`
  - `apps/documents/views/WorkflowAutomation/DocumentProcessInstances.py:149,240`
  - `apps/documents/views/WorkflowAutomation/DocumentWebhookTriggers.py:232,268,282`
- **Problem:** Empty `nodes_json` overwrites user-provided `swimlanes_json`/`transitions_json`; `write_audit_log` sits outside service atomic transactions.
- **Fix:** Default each JSON list field independently when empty and wrap service call + `write_audit_log` inside `with transaction.atomic():`.
- **Status:** [x] fixed — default definition JSON arrays independently and wrap service + audit log atomically (`50dce6a6`, `98d612d8`, `dfd3cf10`)

### M5 — JSON payload byte-size/depth cap (`<= 65536` bytes) & `_dwhk_secret_reveal` malformed/TTL cleanup
- **Found by:** security-reviewer
- **Locations:**
  - `apps/documents/forms/WorkflowAutomation/*.py`
  - `apps/documents/views/WorkflowAutomation/DocumentWebhookTriggers.py:99-103`
- **Problem:** Unbounded `json.loads()` inputs and abandoned/malformed `_dwhk_secret_reveal` session entries persist indefinitely if user skips target page.
- **Fix:** Cap raw JSON textarea payload length (`<= 65536` bytes) & nesting depth; pop non-dict/expired (`>120s`) reveal payloads unconditionally.
- **Status:** [x] fixed — enforce 65536-byte/depth-20 JSON cap and 120s TTL + malformed session cleanup (`02487d10`, `7763976d`)

### M6 — Legal-hold & locked-record guard before routing mutations
- **Found by:** security-reviewer
- **Locations:** `apps/documents/services/workflow_automation.py:497-584,703-716`
- **Problem:** Routing mutations overwrite `Document` fields even if active `DocumentLegalHold` or locked `RecordDeclaration` exists.
- **Fix:** Check `document.legal_holds.filter(is_active=True).exists() or document.record_declarations.filter(is_locked=True).exists()` before applying `Document` mutations in live routing execution.
- **Status:** [x] fixed — block live routing mutations on documents under active legal hold or locked record (`8188f4f4`)

### M7 — Filter bar `mb-0` vertical alignment & responsive grid (`*/list.html`, `analytics_dashboard.html`)
- **Found by:** frontend-reviewer
- **Locations:** `templates/documents/workflow_automation/{*/list.html,analytics_dashboard.html}`
- **Problem:** `.form-group` inside filter bars inherits `margin-bottom: 1rem` dropping buttons 16px lower; `lg:grid-cols-6/7` cramps controls at 1024px.
- **Fix:** Add `mb-0` on filter `.form-group`s and adjust responsive column layout cleanly.
- **Status:** [x] fixed — align filter `.form-group`s and responsive grid across lists and analytics (`36347a18`, `a5def9ea`, `2c667653`, `11515f6f`, `f0d8568b`)

### M8 — Pagination `.muted` left-align & inner `<div class="table-actions">` inside `<td class="text-end">`
- **Found by:** frontend-reviewer
- **Locations:** `templates/documents/workflow_automation/{*/list.html}`
- **Problem:** `<td class="table-actions">` breaks `table-cell` height borders; pagination counter uses `text-slate-500` instead of `.muted`.
- **Fix:** Wrap `.table-actions` inside `<td class="text-end">` and use `<span class="muted">` in `.pagination`.
- **Status:** [x] fixed — wrap `.table-actions` inside `<td class="text-end">` and use `.muted` in `.pagination` (`36347a18`, `a5def9ea`, `2c667653`, `11515f6f`)

### M9 — Action confirmations (`Deprecate`), draft Delete hide when `instance_count > 0`, and edit Cancel links pointing to `*_detail`
- **Found by:** frontend-reviewer
- **Locations:** `templates/documents/workflow_automation/{process_definition/{detail,list,form}.html,*/form.html}`
- **Problem:** Missing confirmation on Deprecate; Delete button shown on draft definition with `instance_count > 0`; edit Cancel goes to list instead of detail.
- **Fix:** Add `confirm(...)` on Deprecate, check `and proc.instance_count == 0` in list template, and point edit Cancel to detail view.
- **Status:** [x] fixed — add Deprecate confirmation, guard draft Delete on `instance_count == 0`, and link edit Cancel to detail (`d0324126`, `36347a18`, `d6b7a9fd`, `4fe70532`, `80752204`, `d3b421b2`)

### M10 — Routing rule list/detail missing `role`/`user`/`process` action targets & scope fields
- **Found by:** frontend-reviewer
- **Locations:** `templates/documents/workflow_automation/routing_rule/{list,detail}.html`
- **Problem:** List only shows folder/org_unit targets; detail prepends stray `" · "` and hides `source_folder`, `target_document_type`, `target_classification`, `core_rule_ref`.
- **Fix:** Render all action targets in `list.html` and clean separator-joined scope/target rows in `detail.html`.
- **Status:** [x] fixed — show all routing action targets on list and fix target/scope rendering on detail (`11515f6f`, `b1285b46`)

### M11 — Analytics UI polish (`median_cycle_minutes`, `completed_count`, `.progress` bars, `break-words`, `.page-actions` `flex-wrap`, RTL logical classes)
- **Found by:** explorer, frontend-reviewer
- **Locations:** `templates/documents/workflow_automation/{analytics_dashboard.html,*/list.html,routing_rule/simulator.html}`
- **Problem:** Unused `median_cycle_minutes`/`completed_count`, long unbroken variant signatures, `flex-wrap` missing on `.page-actions`, `ml-2`/`text-right` directional utilities.
- **Fix:** Surface median/completed KPIs and progress bars cleanly, add `break-words`, `flex-wrap`, and logical RTL utilities (`ms-2`, `text-end`).
- **Status:** [x] fixed — surface median/completed KPIs and `.progress` bars, add `break-words`/`flex-wrap`, and switch to RTL logical utilities (`f0d8568b`, `36347a18`, `a5def9ea`, `2c667653`, `11515f6f`, `c053c8ad`)

### M12 — Dead `roles`/`departments` context in `process_definition_designer` & unnecessary `version` join in `process_instance_detail`
- **Found by:** explorer, performance-reviewer
- **Locations:**
  - `apps/documents/views/WorkflowAutomation/DocumentProcessDefinitions.py:273-274`
  - `apps/documents/views/WorkflowAutomation/DocumentProcessInstances.py:115`
- **Problem:** Designer queries unused `roles`/`departments`; instance detail selects `version` (`extracted_text`) without rendering it.
- **Fix:** Remove unused `roles`/`departments` queries from designer context and drop or `.defer("version__extracted_text")` in `process_instance_detail`.
- **Status:** [x] fixed — remove unused `roles`/`departments` from designer view and defer `version__extracted_text` in `process_instance_detail` (`bfeed084`, `fec88431`)

---

## Notes (App-Wide Follow-Ups / Phase 6 & 7)
- **App-wide clone pattern (L18 — do not fork sibling modules here):** `apps/documents/forms/` has sibling ModelForms (`Documents.py:53`, `DocumentFolders.py:47`, `DocumentApprovalWorkflows.py:41`) with `if self.tenant:` lacking `else: .none()` (recommended app-wide follow-up).
- **Phase 6 Test Coverage:** Include `django_assert_max_num_queries` / N-vs-2N row-count-invariance tests (L58) across list views, analytics, and routing evaluator.
- **Phase 7 Close-out:** Update `.claude/skills/documents/SKILL.md`, `README.md`, and `.claude/tasks/gaps-documents-13.11.md` (documenting cross-sub-module auto-trigger wiring / async webhook worker scope).
